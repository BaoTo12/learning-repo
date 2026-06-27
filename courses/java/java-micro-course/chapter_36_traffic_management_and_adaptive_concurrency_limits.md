# Chapter 36: Traffic Management & Adaptive Concurrency Limits

A distributed microservice architecture offers many potential failure points. Network partitions, hardware decay, noisy neighbors, and traffic spikes can cause individual microservice instances to run slowly or fail. If the routing system continues to send requests to failing instances, response times will degrade across the entire cluster, causing a cascading outage. 

To maintain reliability, we must implement active traffic management. This chapter covers the technical design and implementation of load balancing strategies and call resiliency patterns. We will analyze round-robin platform load balancers, gateway-level load balancing algorithms (including "Join the Shortest Queue"), instance-reported utilization health indicators, the "Choice of Two" load balancing algorithm, client-side load balancing with service discovery registries (Consul/Eureka), hedge request patterns to mitigate tail latencies, call resiliency patterns (Retries, Rate Limiters, Bulkheads, Circuit Breakers) using Resilience4j and Istio service meshes, and reactive network-level backpressure using RSocket.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Identify why traditional round-robin platform load balancing is insufficient for heterogeneous JVM performance.
2. Compare the efficiency of Join the Shortest Queue (JSQ) load balancing under single vs. multi-node load balancer setups.
3. Configure Spring Boot Actuator custom Service Level Objectives (SLOs) to report real-time utilization.
4. Apply the Choice of Two selection algorithm to prevent load balancer herding.
5. Configure Spring Cloud Commons client-side load balancers with zone preference and health checks.
6. Design hedge request patterns in client code to cut off P99 tail latencies.
7. Differentiate between Rate Limiters, Bulkheads, and Circuit Breakers in Resilience4j.
8. Implement Resilience4j Rate Limiters inside Spring WebFlux routing functions.
9. Configure Istio DestinationRules to apply connection pool bulkheads.
10. Evaluate the trade-offs of service mesh vs. application-level resiliency using decision matrices.
11. Explain how RSocket bidirectionally propagates network-level backpressure.

---

## 36.1 Load Balancing: Platform vs. Gateway Architectures

In a cloud environment, microservice instances exhibit varying latencies. A noisy neighbor on the same VM hypervisor, a thread pool exhaustion, or a local JVM Garbage Collection pause can temporarily degrade a single instance's response time:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//bb026ae1-2070-4e47-976e-a311eb596585/markdown_4/imgs/img_in_chart_box_143_672_864_1067.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A37Z%2F-1%2F%2F4b743d319d376c286c71fee86b7fa1e160266512ac6d9399bcd7ce0a5aeb4c77" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-1. REST endpoint latency trace showing worst-case maximum (max) spikes vs P99 percentiles</div> </div>

We query these latency anomalies in Prometheus:

```promql
# Query max latency for /persons endpoint
http_server_requests_seconds_max{uri="/persons"}
```

```promql
# Query P99 latency for /persons endpoint
histogram_quantile(0.99, sum(rate(http_server_requests_seconds_bucket{uri="/persons"}[5m])) by (le))
```

Traditional platform load balancers (like AWS ALB or round-robin DNS) route traffic blindly, sending an equal share of requests to slow instances. To route around sluggish instances, we use an **API Gateway** acting as a smart load balancer:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5ec19d58-9570-4e3d-8c3a-d259e6a8c5c4/markdown_0/imgs/img_in_image_box_308_565_695_977.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A38Z%2F-1%2F%2F5438961f0ab0c6e390355200085ecfcd091af372dc834a64dfb5bfa33e1cdda2" alt="Image" width="38%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-2. Smart API Gateway routing user requests to internal microservices</div> </div>

---

## 36.2 Join the Shortest Queue (JSQ) Mechanics

A simple adaptive load balancing algorithm is **Join the Shortest Queue (JSQ)**. Rather than alternating instances round-robin, the gateway tracks the number of active, in-flight requests it has sent to each downstream instance and directs new traffic to the instance with the fewest in-flight requests.

### 1. Single Load Balancer Node
If a single gateway instance manages all traffic, JSQ functions optimally:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5ec19d58-9570-4e3d-8c3a-d259e6a8c5c4/markdown_1/imgs/img_in_image_box_145_638_862_923.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A39Z%2F-1%2F%2F93671b55ab24ee9d35ad686fae6625bce946e6fc33e82272220b77b21a478dfd" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-3. JSQ algorithm under a single load balancer node routing requests</div> </div>

### 2. Multiple Load Balancer Nodes
When the gateway cluster is scaled horizontally (e.g. running three gateway instances behind a platform load balancer), JSQ coordination breaks down. Each gateway instance only tracks *its own* in-flight requests, remaining blind to requests sent by sibling gateways:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5ec19d58-9570-4e3d-8c3a-d259e6a8c5c4/markdown_2/imgs/img_in_image_box_142_299_864_578.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A40Z%2F-1%2F%2Fc9f0156ebb5abf0fa99e2597afe5b6669513ee8aaa6f19eb57394d8ec7b6889a" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-4. JSQ coordination failures under multiple independent gateway instances</div> </div>

As illustrated in Figure 7-4, Load Balancer 1 sees 0 in-flight requests to Server 3 (from its own perspective) and routes a new request there, despite Server 3 being completely saturated with 3 in-flight requests sent by Load Balancer 2.

> [!TIP]
> Avoid the temptation to build distributed state synchronization mechanisms across load balancer nodes to share in-flight request numbers. Distributed coordination adds high network overhead and latency, defeating the purpose of load balancing. Instead, use instance-reported utilization.

---

## 36.3 Instance-Reported Utilization and Custom Actuator SLOs

Rather than guessing instance load from the outside, the load balancer can query each instance's internal health state. Spring Boot Actuator can expose real-time resource utilization directly inside its health payload:

```json
{
  "status": "UP",
  "components": {
    "apiUtilization": {
      "status": "UP",
      "details": {
        "value": "1250",
        "mustBe": "<10000",
        "unit": "requests"
      }
    },
    "jvmPoolMemory": {
      "status": "UP",
      "details": {
        "value": "0.088",
        "mustBe": "<90%",
        "unit": "percent_used"
      }
    }
  }
}
```

We configure this custom utilization health component in Spring Boot:

```java
package com.ftgo.order.metrics;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.search.Search;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class UtilizationSLOConfig {

    private final MeterRegistry registry;

    public UtilizationSLOConfig(MeterRegistry registry) {
        this.registry = registry;
    }

    @Bean
    public HealthIndicator apiUtilization() {
        return () -> {
            // Retrieve HTTP server requests count for /persons
            double count = Search.in(registry)
                    .name("http.server.requests")
                    .tag("uri", "/persons")
                    .tag("outcome", "SUCCESS")
                    .timer()
                    .map(timer -> (double) timer.count())
                    .orElse(0.0);

            Health.Builder builder = count < 10000 ? Health.up() : Health.down();
            return builder
                    .withDetail("value", String.valueOf(count))
                    .withDetail("mustBe", "<10000")
                    .withDetail("unit", "requests")
                    .build();
        };
    }
}
```

When evaluating which metrics best summarize utilization, monitor the weak spot where an overabundance of traffic creates bottlenecks (e.g. database connection pools):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//2e8637c3-fe83-49ec-9fc7-0e96809b38e6/markdown_2/imgs/img_in_image_box_142_247_865_499.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A37Z%2F-1%2F%2F6d4d1a27efda27e70d8ce613c767d9c1d8f5952c8bc33f40cb5ae9063d50e371" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-6. Monitoring database connections when multiple code execution paths bottleneck at the datasource</div> </div>

---

## 36.4 The "Choice of Two" Load Balancing Heuristic

If load balancers always send traffic to the single least-utilized instance, they will trigger **Herding**. Because multiple load balancers read the same low utilization score, they will all route traffic to that same instance at the same time, immediately overloading it.

To prevent herding, we implement the **Choice of Two** algorithm:
1. Randomly select two candidate instances from the pool.
2. Compare their availability scores.
3. Route the request to the instance with the higher availability score.

### 1. Multi-factor Availability Scoring
To make the comparison robust, the availability score should aggregate three key dimensions:
* **Client Health**: The rate of connection timeouts or network errors experienced by the load balancer when calling this instance.
* **Server Utilization**: The latest utilization metric reported by the instance itself (via its health endpoint).
* **Client Utilization**: The count of active in-flight requests currently sent to this instance by *this* specific load balancer.

Aggregating these factors prevents routing requests to unhealthy instances that fail quickly (which would otherwise report artificially low utilization and short queues).

---

## 36.5 Client-Side Load Balancing and Service Discovery

In many cloud layouts, callers route requests directly to downstream instances without passing through an intermediate gateway:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//54b1575f-f3f7-43c9-b35b-3a75214b5d65/markdown_0/imgs/img_in_image_box_143_172_631_489.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A36Z%2F-1%2F%2F3390965b6a6bf352383c7ebb6a8b9251ffe03f1360811d56efe9cd160c16f8c3" alt="Image" width="48%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-7. Client-side load balancer layout querying Consul/Eureka registries</div> </div>

We configure client-side load balancing with zone preference and health checks using Spring Cloud Commons:

```java
package com.ftgo.order.client;

import org.springframework.cloud.client.loadbalancer.LoadBalanced;
import org.springframework.cloud.loadbalancer.annotation.LoadBalancerClient;
import org.springframework.cloud.loadbalancer.core.ServiceInstanceListSupplier;
import org.springframework.cloud.loadbalancer.support.ServiceInstanceListSuppliers;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
@LoadBalancerClient(
        name = "order-service",
        configuration = OrderServiceLoadBalancerConfig.class
)
public class ClientLoadBalancerConfig {

    @LoadBalanced
    @Bean
    public WebClient.Builder webClientBuilder() {
        return WebClient.builder();
    }
}

@Configuration
class OrderServiceLoadBalancerConfig {

    @Bean
    public ServiceInstanceListSupplier discoveryClientServiceInstanceListSupplier(
            ConfigurableApplicationContext context) {
        return ServiceInstanceListSuppliers.builder()
                .withDiscoveryClient()  // Query Consul/Eureka for instance lists
                .withZonePreference()   // Route to instances in the same cloud availability zone
                .withHealthChecks()     // Filter out instances failing TCP health checks
                .withCaching()          // Cache instance list to reduce registry load
                .build(context);
    }
}
```

---

## 36.6 Mitigating Tail Latencies: Hedge Requests

A request traversing multiple microservices is susceptible to the **Tail Latency Amplification** effect. If $N$ sequential service calls are made, and each call has a 1% chance of experiencing a slow response (top 1% latency), the probability $P$ that the overall request experiences a slow tail latency is:

$$P = (1 - 0.99^N) \times 100\%$$

For a call depth of $N = 100$, the chance of experiencing a tail latency spike is **63.3%**.

To mitigate this, we implement **Hedge Requests**:
1. Client sends a request to Instance A.
2. If Instance A does not respond within a specific timeout (e.g. the P90 latency limit of 50ms), the client sends a duplicate request to Instance B.
3. Client processes whichever response arrives first and cancels the other.

> [!WARNING]
> Hedge requests must only be used for **idempotent** operations (like read-only GET queries). Sending duplicate POST requests to charge credit cards or commit orders will cause duplicate transaction errors.

---

## 36.7 Call Resiliency Patterns: Rate Limiters, Bulkheads, and Circuit Breakers

When services experience overload, we protect them using Resilience4j:

### 1. Resilience4j Rate Limiter Implementation
A Rate Limiter restricts the number of calls allowed within a sliding time window:

```java
package com.ftgo.order.resilience;

import io.github.resilience4j.ratelimiter.RateLimiter;
import io.github.resilience4j.ratelimiter.RateLimiterConfig;
import io.github.resilience4j.ratelimiter.RateLimiterRegistry;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.server.RouterFunction;
import org.springframework.web.reactive.function.server.ServerResponse;

import java.time.Duration;

import static org.springframework.web.reactive.function.server.RouterFunctions.route;

@Configuration
public class RateLimiterRoutesConfig {

    @Bean
    public RouterFunction<ServerResponse> billingRoutes() {
        RateLimiterConfig config = RateLimiterConfig.custom()
                .limitRefreshPeriod(Duration.ofMillis(1000)) // 1 second window
                .limitForPeriod(100)                         // Max 100 requests per window
                .timeoutDuration(Duration.ofMillis(20))      // Block threads up to 20ms if saturated
                .build();

        RateLimiterRegistry registry = RateLimiterRegistry.of(config);
        RateLimiter billingRateLimiter = registry.rateLimiter("billingService");

        BillingHandler billingHandler = new BillingHandler();

        return route()
                .GET("/billing/{id}", request -> 
                    RateLimiter.decorateCheckedSupplier(billingRateLimiter, () -> 
                        billingHandler.getBillingDetails(request.pathVariable("id"))
                    ).unchecked().get()
                ).build();
    }
}

class BillingHandler {
    public ServerResponse getBillingDetails(String id) {
        return ServerResponse.ok().bodyValue("Billing Info for " + id);
    }
}
```

### 2. Bulkheads
A Bulkhead limits the number of concurrent executions allowed at any instant, isolating resources (like thread pools) to prevent a failing service from exhausting all system resources.

### 3. Circuit Breakers
A Circuit Breaker monitors call error rates, switching between three states:
* **CLOSED**: Normal operation. Requests are forwarded downstream.
* **OPEN**: Error rates exceed thresholds. Requests are rejected immediately, executing fallback logic.
* **HALF_OPEN**: Periodically allows a limited number of requests to test if the downstream service has recovered.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//2a40c255-4f42-4611-8416-2c3e4208908c/markdown_0/imgs/img_in_image_box_142_109_863_302.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A23%3A41Z%2F-1%2F%2F0bded5c5ffb339c54880229c5fe7e33ad6b75dc95f82042cb7af781d4c63f684" alt="Image" width="71%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7-9. Finite state machine transitions of a circuit breaker</div> </div>

---

## 36.8 Adaptive Concurrency Limits

Rather than using statically configured limits (which go stale as downstream cluster sizes change), **Adaptive Concurrency Limits** calculate thresholds dynamically based on measured response times:

* **Gradient Limiters**:
  $$\text{Limit}_{t+1} = \text{Limit}_t \times \left( \frac{\text{RTT}_{\text{no-load}}}{\text{RTT}_{\text{actual}}} \right) + \text{QueueSize}$$
* **Vegas Limiters**: Adjust limits based on queues sizes, scaling down limits if actual latencies rise above target limits.

---

## 36.9 Resiliency Architectures: Service Mesh vs. Application Code

We compare implementing traffic policies in a service mesh (like Istio) against using application-level libraries (like Resilience4j):

| Resiliency Evaluation Dimension | Service Mesh (Istio) | Application Libraries (Resilience4j) |
| :--- | :--- | :--- |
| **Language Support (Weight = 5)** | **Low Cost (5)**: Implemented in proxy; client language-agnostic. | **High Cost (25)**: Requires distinct library implementation per language. |
| **Runtime Support (Weight = 5)** | **High Cost (25)**: Bound to specific platforms (e.g. Kubernetes). | **Low Cost (5)**: Runs on any platform that hosts JVM binaries. |
| **Deployment Complexity (Weight = 4)**| **Medium Cost (12)**: Requires sidecar injection configs. | **Low Cost (0)**: Embedded inside the JAR file. |
| **Operational Overhead (Weight = 2)** | **High Cost (10)**: Proxy processes consume high CPU/memory. | **Low Cost (2)**: No additional container allocations. |

We apply Istio bulkheads inside Kubernetes custom resources:

```yaml
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: billing-service-bulkhead
spec:
  host: billing-service
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 150 # Maximum connections to the service
      http:
        http1MaxPendingRequests: 50 # Max pending requests allowed to queue
```

---

## 36.10 Network-Level Backpressure with RSocket

To prevent overloaded services from failing, we can propagate backpressure bidirectionally across the network using the **RSocket** protocol. 

Unlike HTTP, RSocket is a persistent, connection-oriented protocol that implements Reactive Streams semantics over TCP.

### 1. Leasing Mechanics
Downstream event consumers issue **Leases** to upstream producers. A lease specifies the exact number of requests the producer is allowed to send within a given time frame. Once the lease count reaches 0, the producer stops sending traffic, buffering messages at the source until a new lease is issued, ensuring that downstream instances never experience overload.

---

## 36.11 Choice of Two Instance Prefiltering Implementation

To prevent comparing two candidates that are already marked down or on probation, the load balancer should pre-filter candidate instances before applying the Choice of Two comparison.

Below is the Java implementation of a custom load balancer pre-filtering candidate instances:

```java
package com.ftgo.gateway.loadbalancer;

import org.springframework.cloud.client.ServiceInstance;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

public class PrefilteredChoiceOfTwoLoadBalancer {

    private final Random random = new Random();

    public ServiceInstance choose(List<ServiceInstance> instances) {
        if (instances.isEmpty()) {
            return null;
        }
        if (instances.size() == 1) {
            return instances.get(0);
        }

        List<ServiceInstance> healthyCandidates = new ArrayList<>();
        
        // 1. Prefilter out instances marked unhealthy or on probation
        for (ServiceInstance instance : instances) {
            String isHealthy = instance.getMetadata().getOrDefault("healthy", "true");
            String isProbation = instance.getMetadata().getOrDefault("probation", "false");
            
            if ("true".equals(isHealthy) && "false".equals(isProbation)) {
                healthyCandidates.add(instance);
            }
        }

        // Fallback to raw instances if all are unhealthy/probational
        List<ServiceInstance> targetPool = healthyCandidates.isEmpty() ? instances : healthyCandidates;

        if (targetPool.size() == 1) {
            return targetPool.get(0);
        }

        // 2. Randomly select two distinct candidates from the pool
        int index1 = random.nextInt(targetPool.size());
        int index2;
        do {
            index2 = random.nextInt(targetPool.size());
        } while (index1 == index2 && targetPool.size() > 1);

        ServiceInstance candidate1 = targetPool.get(index1);
        ServiceInstance candidate2 = targetPool.get(index2);

        // 3. Compare their reported utilization scores and return the lower one
        double util1 = Double.parseDouble(candidate1.getMetadata().getOrDefault("utilization", "0.0"));
        double util2 = Double.parseDouble(candidate2.getMetadata().getOrDefault("utilization", "0.0"));

        return util1 <= util2 ? candidate1 : candidate2;
    }
}
```

---

## 36.12 Spring Boot Actuator Custom Health Aggregation Config

By default, Spring Boot Actuator aggregates nested component statuses using a hierarchical severity order. We configure this order in `application.yml` to ensure that if our custom `apiUtilization` SLO status is set to `OUT_OF_SERVICE` or `DOWN`, the global service status reflects this immediately:

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health, metrics, prometheus
  endpoint:
    health:
      show-details: always
      status:
        # Define status severity aggregation order
        order: "DOWN, OUT_OF_SERVICE, UP, UNKNOWN"
```

---

## 36.13 Configuring Resilience4j via `application.yml`

In production, call resiliency parameters should be declared as configuration properties, allowing SREs to tune thresholds dynamically:

```yaml
resilience4j:
  circuitbreaker:
    configs:
      default:
        slidingWindowSize: 100
        permittedNumberOfCallsInHalfOpenState: 10
        slidingWindowType: COUNT_BASED
        minimumNumberOfCalls: 20
        waitDurationInOpenState: 10000ms
        failureRateThreshold: 50
        slowCallRateThreshold: 75
        slowCallDurationThreshold: 2000ms
    instances:
      orderServiceCircuitBreaker:
        baseConfig: default
  bulkhead:
    configs:
      default:
        maxConcurrentCalls: 25
        maxWaitDuration: 20ms
    instances:
      orderServiceBulkhead:
        baseConfig: default
  ratelimiter:
    configs:
      default:
        limitForPeriod: 50
        limitRefreshPeriod: 1s
        timeoutDuration: 0ms
    instances:
      orderServiceRateLimiter:
        baseConfig: default
```

---

## 36.14 Setting up RSocket Client Leasing Configurations

To enforce network-level backpressure, we configure the RSocket requester client to require leases from the responder service:

```java
package com.ftgo.order.rsocket;

import io.rsocket.RSocket;
import io.rsocket.core.RSocketConnector;
import io.rsocket.lease.LeaseEvent;
import io.rsocket.lease.RequesterLeaseTracker;
import io.rsocket.transport.netty.client.TcpClientTransport;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.rsocket.RSocketRequester;
import org.springframework.messaging.rsocket.RSocketStrategies;
import reactor.core.publisher.Flux;

@Configuration
public class RSocketLeasingClientConfig {

    @Bean
    public RSocketRequester rSocketRequester(RSocketRequester.Builder builder, RSocketStrategies strategies) {
        RequesterLeaseTracker leaseTracker = new RequesterLeaseTracker();

        // Listen for leasing events emitted by the responder service
        Flux<LeaseEvent> leaseEvents = leaseTracker.leaseEvents();
        leaseEvents.subscribe(event -> 
            System.out.println("New lease event received: " + event.toString())
        );

        return builder
                .rsocketConnector(connector -> connector
                        // Request connection with lease negotiation enabled
                        .lease(leaseTracker)
                )
                .transport(TcpClientTransport.create("localhost", 7000));
    }
}
```

---

## 36.15 Instance Probation: Cold Start Rate Limiter

When new Java microservice instances are launched, the JVM requires time to execute class loading and JIT compiling optimizations. During this warmup period, sending full production traffic to the cold instance causes request queues to saturate, leading to elevated latency.

To prevent this, the load balancer places new instances on **Probation**, applying a ramp-up rate limit:

```java
package com.ftgo.gateway.loadbalancer;

import org.springframework.cloud.client.ServiceInstance;
import java.time.Duration;
import java.time.Instant;

public class InstanceProbationLimiter {

    private static final Duration WARMUP_PERIOD = Duration.ofMinutes(2);
    private static final int INITIAL_MAX_CONCURRENCY = 5;

    public boolean isAllowed(ServiceInstance instance, int activeRequests) {
        String launchTimeMetadata = instance.getMetadata().get("launchTime");
        if (launchTimeMetadata == null) {
            return true; // No metadata, bypass probation checks
        }

        Instant launchTime = Instant.parse(launchTimeMetadata);
        Instant now = Instant.now();

        if (now.isAfter(launchTime.plus(WARMUP_PERIOD))) {
            return true; // Warmup period has expired
        }

        // Apply restricted concurrency threshold during probation
        return activeRequests < INITIAL_MAX_CONCURRENCY;
    }
}
```

---

## 36.16 SRE Mathematics: The Power of Two Choices

The **Choice of Two** algorithm relies on the **Power of Two Choices** theorem (Mitzenmacher's theorem). 

### 1. The Supermarket Model
Suppose we have $N$ load-balanced servers and a queue of incoming requests:
* **Random Selection (Choice of 1)**: If requests are directed to a randomly chosen server, the maximum queue size at any server behaves as:
  $$\text{Max Queue} \approx \frac{\ln(N)}{\ln(\ln(N))}$$
* **Power of Two Choices (Choice of 2)**: If we select two servers at random and route to the one with the shorter queue, the maximum queue size drops exponentially:
  $$\text{Max Queue} \approx \frac{\ln(\ln(N))}{\ln(2)} + O(1)$$

### 2. Diminishing Returns of Choice of $D$
While comparing 2 candidates yields an exponential reduction in queue length compared to 1, comparing 3 or more candidates ($D \ge 3$) offers almost no further reduction in queue size, while significantly increasing the CPU cost of searching and polling. Thus, Choice of Two ($D = 2$) represents the mathematical sweet spot for distributed load balancing.

---

## 36.17 Circuit Breaker Fallback Implementation Patterns

When a circuit breaker transitions to the `OPEN` state, downstream calls are blocked. To protect the user experience, developers must configure fallback handlers:

```java
package com.ftgo.order.resilience;

import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import java.util.Collections;
import java.util.List;

@Service
public class OrderServiceWithFallbacks {

    @CircuitBreaker(name = "billingService", fallbackMethod = "fallbackBillingHistory")
    public Mono<List<String>> getBillingHistory(String customerId) {
        // Query downstream billing microservice
        return WebClientUtils.get("/billing/" + customerId);
    }

    // Fallback signature must match the original method and include Throwable parameter
    public Mono<List<String>> fallbackBillingHistory(String customerId, Throwable ex) {
        System.err.println("Billing service failed! Returning empty static list. Reason: " + ex.getMessage());
        
        // 1. Silent static fallback: return empty collection
        return Mono.just(Collections.emptyList());
    }

    @CircuitBreaker(name = "paymentService", fallbackMethod = "fallbackPayment")
    public Mono<String> processPayment(String orderId, double amount) {
        return WebClientUtils.post("/payment", orderId, amount);
    }

    public Mono<String> fallbackPayment(String orderId, double amount, Throwable ex) {
        System.err.println("Payment service failed! Rejecting immediately to avoid double spend.");
        
        // 2. Fail Fast fallback: throw custom exception to prevent downstream waste
        return Mono.error(new PaymentSystemUnavailableException("Payment gateway unreachable."));
    }
}
```

---

## 36.18 Active Polling vs. Passive Tracking in Choice of Two

When measuring downstream instance utilization, SREs choose between two telemetry collections models:

* **Active Polling**:
  * **Mechanism**: The load balancer sends HTTP health queries to instances at a fixed interval (e.g. every 5 seconds).
  * **Trade-off**: Provides fresh utilization stats even when request throughput is low, but adds system load (polling request volume scales linearly with the number of load balancer nodes).
* **Passive Tracking (In-Flight Sniffing)**:
  * **Mechanism**: The load balancer records response latencies and status codes of user requests passing through it, updating its local representation of the instance's availability dynamically.
  * **Trade-off**: Zero additional network load, but metrics go stale if a service is idle or receives low throughput, leaving the load balancer blind to changes until a new request arrives.

---

## 36.19 Caching Anomalies in Client-Side Discovery Clients

Under client-side load balancing, services fetch instance addresses from Consul/Eureka registries and cache them locally (typically for 35 seconds). This caching introduces **Discovery Lag**:

* **The Problem**: If an instance crashes, the registry registers the loss immediately, but the client continues to route requests to the dead IP address until its local cache expires.
* **Tuning Refresh Intervals**: SREs tune local fetch configurations to minimize this window:
  ```yaml
  # Configure fast Eureka client registry fetch intervals in Spring Boot
  eureka:
    client:
      registryFetchIntervalSeconds: 5
  ```
* **Fallback Retries**: Configure client-side load balancers to automatically retry failed requests on a different instance if a connection error is encountered before the cache refreshes.

---

## 36.20 Bulkhead Configurations: Threadpool vs. Semaphore Isolation

Resilience4j provides two distinct bulkhead isolation models:

### 1. Threadpool Isolation
Allocates a dedicated execution queue and thread pool for each target service.
* **Pros**: Threads are isolated. If a downstream service hangs, the thread pool saturates, but the parent application threads remain unblocked. Can enforce timeouts preemptively.
* **Cons**: Context-switching overhead between multiple thread pools degrades CPU performance.

### 2. Semaphore Isolation
Uses atomic counters (semaphores) to limit concurrent entry to a block of code.
* **Pros**: Low resource overhead.
* **Cons**: Borrowing threads directly from the parent application pool means slow calls can block upstream request processing if timeout configurations are misaligned.

---




## 36.21 Summary of Traffic Management and Resiliency Configurations

This table summarizes the configurations, rules, and parameters used to build traffic management systems:

| Resiliency Element | Term / Config Selector | Main Implementation Target | Scope Location |
| :--- | :--- | :--- | :--- |
| **In-Flight Tracking**| JSQ Algorithm | Routes traffic to the least busy instance. | API Gateway |
| **SLO Health Component**| `ServiceLevelObjective` | Exposes utilization status inside Actuator. | Spring Bean |
| **Herding Prevention**| Choice of Two | Selects randomly between two candidates. | Load Balancer |
| **Zone Preference** | `withZonePreference()` | Directs traffic to instances in the same zone. | Client Config |
| **Tail Latency Limit**| Hedge Requests | Sends duplicate requests on timeout. | Client Config |
| **Sliding Window** | `limitRefreshPeriod` | Configures interval periods for rate limits. | Resilience4j |
| **Bulkhead Limit** | `maxConnections` | Restricts concurrent TCP connection allocations. | Istio Rule |
| **Backpressure Protocol**| RSocket Lease | Restricts requests dynamically using leases. | Network Layer |

---

## Chapter Summary

* Standard round-robin load balancing fails to handle JVM performance drift, requiring smarter gateway-level routing.
* Join the Shortest Queue (JSQ) tracks in-flight requests, but coordination falls apart under multiple load balancer nodes.
* Spring Boot Actuator can expose custom Service Level Objectives (SLOs) to report real-time utilization.
* The Choice of Two algorithm selects and compares two random instances to prevent herding.
* Client-side load balancers query Eureka/Consul registries directly, applying zone preferences to reduce cross-zone latency.
* Hedge requests send duplicate queries to different instances on timeout, cutting off tail latencies for idempotent GET requests.
* Call resiliency patterns include Rate Limiters (limiting rates per interval), Bulkheads (limiting concurrent executions), and Circuit Breakers (intercepting failures).
* Adaptive concurrency limits adjust threshold parameters dynamically based on actual response times.
* Service meshes externalize resiliency policies to sidecar proxies, but increase resource overhead and operational complexity.
* RSocket bidirectionally propagates network-level backpressure using leases to prevent downstream overload.
* Use custom load balancer pre-filtering rules to exclude instances that are under probation or marked unhealthy.
* Configure custom Spring Boot Actuator status ordering to immediately bubble up degraded utilization statuses.
* Declare Resilience4j registries and instance properties in YAML configuration files to enable dynamic SRE tuning.
* Implement RSocket client lease connector configurations to enable network-level backpressure handshakes.
* Apply probation constraints to newly launched JVM instances to prevent queue saturation during warmups.
* Apply the mathematical Power of Two Choices theorem to minimize maximum queue lengths with minimal search cost.
* Design silent static fallbacks or fail-fast exceptions inside circuit breaker handlers to protect the user experience.
* Distinguish between active polling and passive tracking methods when measuring downstream server utilization.
* Tune local Eureka/Consul refresh registry intervals to minimize discovery lag and cache anomalies.
* Choose between Threadpool bulkhead isolation (preemptive timeouts, high CPU overhead) and Semaphore isolation (low resource usage, no preemptive timeouts).
---

## 36.12 Production-Grade Adaptive Concurrency Limiting: Netflix Concurrency Limits WebFlux Filter

When a downstream service slows down, traditional microservice thread pools saturate immediately. Instead of hard-coding fixed queue sizes or request limits (which fail under changing traffic profiles), modern reactive systems implement **Adaptive Concurrency Limiting**. 

Adaptive Concurrency Limiting dynamically adjusts the concurrency threshold based on real-time round-trip latency measurements using algorithms like **Gradient** or **Vegas**. When latency increases, the concurrency limit is automatically reduced to prevent queue bottlenecks, sending immediate backpressure (`HTTP 429 Too Many Requests`) to clients.

```
+---------------------------------------------------------------------------------+
|                       ADAPTIVE CONCURRENCY LIMITS GATE                          |
+---------------------------------------------------------------------------------+
|                                                                                 |
|   [ Incoming WebFlux Request ]                                                  |
|               │                                                                 |
|               ▼ (Acquires concurrency token)                                    |
|   [ ConcurrencyLimiter (GradientLimit) ] ──(Limit Exceeded?)──► [ HTTP 429 ]    |
|               │                                                                 |
|               ▼ (Token acquired)                                                |
|   [ Reactive WebFilter Execution ]                                              |
|               │                                                                 |
|               ▼ (Measures execution latency RTT)                                |
|   [ Release Token & Recalculate Limit ]                                         |
|                                                                                 |
+---------------------------------------------------------------------------------+
```

---

### The WebFlux Filter Configuration: `OrderReviewsConcurrencyLimitConfig.java`
Below is the complete configuration registering a Netflix Concurrency Limits `WebFilter` for the **review-service** using Spring WebFlux. We configure a **Gradient Limiter** that measures request latencies and adjusts the concurrency windows dynamically.

```java
package com.ftgo.review.concurrency;

import com.netflix.concurrency.limits.Limiter;
import com.netflix.concurrency.limits.limiter.AbstractLimiter;
import com.netflix.concurrency.limits.limit.GradientLimit;
import com.netflix.concurrency.limits.limiter.SimpleLimiter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

import java.util.Optional;
import java.util.concurrent.TimeUnit;

@Configuration
public class OrderReviewsConcurrencyLimitConfig {

    /**
     * Instantiates an adaptive Gradient Limiter that monitors round-trip times (RTT)
     * and dynamically updates concurrency windows.
     */
    @Bean
    public Limiter<ServerWebExchange> concurrencyLimiter() {
        GradientLimit gradientLimit = GradientLimit.newBuilder()
                .initialLimit(20)
                .minLimit(5)
                .maxLimit(100)
                .smoothing(0.2) // Exponential smoothing parameter for baseline RTT updates
                .build();

        return SimpleLimiter.newBuilder()
                .limit(gradientLimit)
                .build();
    }

    /**
     * WebFilter intercepts WebFlux routing chains, enforcing limits and injecting 429 codes.
     */
    @Bean
    public WebFilter concurrencyLimitFilter(Limiter<ServerWebExchange> limiter) {
        return (exchange, chain) -> {
            long startTime = System.nanoTime();

            // Attempt to acquire execution context token
            Optional<Limiter.Listener> listenerOpt = limiter.acquire(exchange);

            if (listenerOpt.isEmpty()) {
                // Return immediate 429 Too Many Requests if concurrency threshold is breached
                exchange.getResponse().setStatusCode(HttpStatus.TOO_MANY_REQUESTS);
                return exchange.getResponse().setComplete();
            }

            Limiter.Listener listener = listenerOpt.get();

            return chain.filter(exchange)
                    .doOnSuccess(v -> {
                        long duration = System.nanoTime() - startTime;
                        // Release token and feed response latency (RTT) back to the Gradient algorithm
                        listener.onSuccess();
                    })
                    .doOnError(t -> {
                        // Release token and notify the limiter of system failure
                        listener.onIgnore();
                    });
        };
    }
}
```
