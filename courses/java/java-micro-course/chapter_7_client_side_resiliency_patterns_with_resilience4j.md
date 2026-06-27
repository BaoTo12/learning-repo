# Chapter 7: Client-Side Resiliency Patterns with Resilience4j

In a microservices architecture, services communicate with each other over the network. Network communication is subject to partial failures: down networks, slow hosts, packet loss, or crashed containers. If a service consumer calls a slow downstream dependency synchronously, it can exhaust its thread pool waiting for responses, causing a cascading failure that takes down the entire system.

This chapter covers the core **client-side resiliency patterns** used to protect microservices from cascading failures. We will analyze the transition from the deprecated Netflix Hystrix library to the modern **Resilience4j** framework. We will explore the mechanics and state transitions of the **Circuit Breaker** pattern, implement **Fallback** behaviors, isolate thread pools using the **Bulkhead** pattern, configure automated **Retries**, and enforce **Rate Limiters**. Finally, we will configure these patterns in Spring Boot using YAML properties and Java annotations.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain how partial service failures cascade into system-wide outages.
2. Outline the mechanics of the **Circuit Breaker** pattern and its three states (CLOSED, OPEN, HALF-OPEN).
3. Apply the **Fallback** pattern to return clean default values when a downstream call fails.
4. Implement the **Bulkhead** pattern to isolate resources using thread pools and semaphores.
5. Configure the **Retry** pattern to handle transient network glitches.
6. Configure the **Rate Limiter** pattern to restrict invocation frequencies.
7. Implement Resilience4j annotations and properties inside Spring Boot services.
8. Resolve ThreadLocal context propagation issues when using different bulkhead isolation strategies.
9. Deploy dynamic configurations using Spring Cloud Config and refresh Actuator bus reload loops.
10. Programmatically configure circuit breakers using the Resilience4j core registry Java DSL.
11. Implement custom task decorators to propagate ThreadLocal contexts across thread pool boundaries.
12. Analyze default execution priority of aspects and customize priority configurations in YAML.
13. Register programmatic event listeners to monitor state transitions, errors, and metrics.
14. Distinguish and ignore business-level validation exceptions vs system-level failures in configurations.
15. Customize Spring Boot Actuator Health Indicators to avoid container liveness rolling restarts.
16. Expose Prometheus metrics endpoints via Micrometer libraries to build Grafana dashboards.


---

## 7.1 Cascading Failures and the Need for Resiliency

In a monolithic application, method calls between components are executed in-memory. In a microservices architecture, in-memory calls are replaced by remote calls over the network.

Consider a scenario where Service B blocks waiting for Service C to respond:
1. **Thread Exhaustion**: Service B's threads block waiting for Service C.
2. **Cascading Failure**: Service B runs out of threads to handle new incoming requests from Service A.
3. **Outage**: Service A's threads block waiting for Service B, taking down the entry-point APIs and impacting the end-user.

To protect microservices from cascading failures, we place client-side resiliency patterns between the service consumer and the downstream services:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//721d8e25-b770-4847-9090-4f118875f640/markdown_3/imgs/img_in_image_box_199_199_836_778.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A38Z%2F-1%2F%2F38d6dbccb60a1ec8d09d2ab0c345544c7a485bb94fae373ed1faa6d38960d938" alt="Image" width="59%" /></div>
<div style="text-align: center;">Figure 7.1: The four client resiliency patterns act as a protective buffer between a service consumer and the service.</div>

Without resiliency patterns, a failure in a single leaf service (such as a third-party inventory database) can propagate upstream, exhausting connection pools and bringing down the entire platform:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a38e20e3-55e3-4657-9df5-1b9a216dc0b6/markdown_1/imgs/img_in_image_box_156_105_933_853.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A37Z%2F-1%2F%2F9cd75d54bce20ca059e50a65bfe16dee31f7319d19e37a73a62eb7d3ff7540c9" alt="Image" width="73%" /></div>
<div style="text-align: center;">Figure 7.2: An application can be thought of as a graph of interconnected dependencies. If you don't manage the remote calls among them, one poorly behaving remote resource can bring down all the services in the graph.</div>

When we implement a circuit breaker, the client delegates the remote call invocation to a middleman (the circuit breaker). If calls are slow or fail, the circuit breaker interrupts the request, failing fast and preventing resource exhaustion:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a38e20e3-55e3-4657-9df5-1b9a216dc0b6/markdown_2/imgs/img_in_image_box_151_384_948_843.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A38Z%2F-1%2F%2F039030d9b1539937157cbaabc35b8e5cc27f2658b898d1986ad87d4a5fe62b0d" alt="Image" width="75%" /></div>
<div style="text-align: center;">Figure 7.3: The circuit breaker trips and allows a misbehaving service call to fail quickly and gracefully.</div>

---

## 7.2 The Circuit Breaker Pattern: States and Transitions

The circuit breaker pattern monitors calls using a finite state machine that transitions through three primary states:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//4dd42f2e-1447-4b50-b01b-137d531604af/markdown_1/imgs/img_in_image_box_201_652_705_867.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A38Z%2F-1%2F%2F705ae3f0e8c8685794c556a0b0bf027aaae77875513004551f7ddda7ee767f7e" alt="Image" width="47%" /></div>
<div style="text-align: center;">Figure 7.4: Resilience4j circuit breaker states: closed, open, and half-open.</div>

### 1. CLOSED
The circuit is closed, and requests pass through. The circuit breaker monitors call results (success = 0, failure = 1) using a **Ring Bit Buffer**:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//4dd42f2e-1447-4b50-b01b-137d531604af/markdown_2/imgs/img_in_image_box_184_108_497_414.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A38Z%2F-1%2F%2Fd09deb139f4fefaeddb959d49e52e438495fef22d5c48d3b5cf5fb689b552f26" alt="Image" width="29%" /></div>
<div style="text-align: center;">Figure 7.5: Resilience4j circuit breaker ring bit buffer with 12 results. This ring contains 0 for successful requests and 1 when calls fail.</div>

* *Calculation Threshold*: The ring buffer must be filled before the failure rate can be calculated. If the buffer size is 12, a minimum of 12 requests must occur. The circuit will not trip if only 11 calls fail.
* *Transition*: If the failure rate (or the percentage of slow calls) exceeds the configured threshold, the circuit transitions to the **OPEN** state.

### 2. OPEN
All requests fail immediately, throwing a `CallNotPermittedException`. The client does not call the downstream service, preventing resource utilization.
* *Transition*: The circuit remains in this state for a configured time before transitioning to the **HALF-OPEN** state.

### 3. HALF-OPEN
A limited number of test requests pass through to evaluate the health of the downstream service.
* *Transition to CLOSED*: If the test requests succeed and the failure rate falls below the threshold, the circuit returns to **CLOSED**.
* *Transition to OPEN*: If the test requests fail or the failure rate remains high, the circuit returns to **OPEN** and resets the timer.

---

## 7.3 Implementing Resilience4j in Spring Boot

Resilience4j is a modular fault-tolerance library designed for Java 8 and functional programming. It is the recommended replacement for Netflix Hystrix, which is now in maintenance mode.

It wraps remote calls to databases, microservices, and external APIs:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//4dd42f2e-1447-4b50-b01b-137d531604af/markdown_3/imgs/img_in_image_box_199_98_922_893.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A39Z%2F-1%2F%2F367ef37f9e5252a10b5e28f352d699be2dc259e9bb8f4720d615ab0c2528ec1c" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 7.6: Resilience4j sits between each remote resource call and protects the client. It doesn't matter if the remote resource calls a database or a REST-based service.</div>

### 1. Maven Dependencies Setup
Include the Resilience4j Boot library, AOP, and core modules in `pom.xml`:

```xml
<properties>
    <resilience4j.version>1.7.0</resilience4j.version>
</properties>

<dependencies>
    <dependency>
        <groupId>io.github.resilience4j</groupId>
        <artifactId>resilience4j-spring-boot2</artifactId>
        <version>${resilience4j.version}</version>
    </dependency>
    <dependency>
        <groupId>io.github.resilience4j</groupId>
        <artifactId>resilience4j-circuitbreaker</artifactId>
        <version>${resilience4j.version}</version>
    </dependency>
    <dependency>
        <groupId>io.github.resilience4j</groupId>
        <artifactId>resilience4j-timelimiter</artifactId>
        <version>${resilience4j.version}</version>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-aop</artifactId>
    </dependency>
</dependencies>
```

---

### 2. Customizing the Circuit Breaker
Configure the instances inside your configuration properties file (`application.yml`):

```yaml
resilience4j:
  circuitbreaker:
    instances:
      orderService:
        failureRateThreshold: 50
        waitDurationInOpenState: 15000
        slowCallRateThreshold: 50
        slowCallDurationThreshold: 2000
        slidingWindowSize: 10
        slidingWindowType: COUNT_BASED
        minimumNumberOfCalls: 5
        permittedNumberOfCallsInHalfOpenState: 3
        recordExceptions:
          - java.util.concurrent.TimeoutException
          - org.springframework.web.client.ResourceAccessException
```

Also, you can verify your configuration and state details at:
`http://localhost:<port>/actuator/health`

When a circuit trips and opens, subsequent requests receive errors:

```json
{
  "errors": [
    {
      "message": "CircuitBreaker 'orderService' is OPEN and does not permit further calls",
      "code": null,
      "detail": "CircuitBreaker 'orderService' is OPEN and does not permit further calls"
    }
  ]
}
```
<div style="text-align: center;">Figure 7.7: A circuit breaker error indicates the circuit breaker is now in the open state.</div>

---

### 3. Annotating Service Calls: `@CircuitBreaker`
Annotate the target method executing the remote network call:

```java
package com.ftgo.order.service;

import com.ftgo.order.model.Order;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class OrderService {

    @CircuitBreaker(name = "orderService")
    public List<Order> getOrdersByRestaurant(String restaurantId) {
        return orderRepository.findByRestaurantId(restaurantId);
    }
}
```

---

## 7.4 Fallback Processing

With a fallback strategy, when a remote call fails or is blocked by an open circuit, the circuit breaker intercepts the exception and executes an alternative code path (e.g., returns default dummy values or pulls data from a backup source):

```java
package com.ftgo.order.service;

import com.ftgo.order.model.Order;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeoutException;

@Service
public class OrderService {
    private static final Logger logger = LoggerFactory.getLogger(OrderService.class);

    @CircuitBreaker(name = "orderService", fallbackMethod = "buildFallbackOrderList")
    public List<Order> getOrdersByRestaurant(String restaurantId) throws TimeoutException {
        logger.debug("Inside getOrdersByRestaurant call...");
        // Simulating a timeout failure
        randomlyRunLong(); 
        return orderRepository.findByRestaurantId(restaurantId);
    }

    // Fallback method signature must match the original method plus a Throwable parameter
    private List<Order> buildFallbackOrderList(String restaurantId, Throwable t) {
        logger.warn("Executing fallback due to failure: {}", t.getMessage());
        List<Order> fallbackList = new ArrayList<>();
        Order order = new Order();
        order.setOrderId("0000000-00-00000");
        order.setRestaurantId(restaurantId);
        order.setState("PENDING_BACKUP_RECOVERY");
        order.setDeliveryAddress("Sorry, order system is experiencing high traffic. Please retry shortly.");
        fallbackList.add(order);
        return fallbackList;
    }

    private void randomlyRunLong() throws TimeoutException {
        int randomNum = (int) (Math.random() * 3) + 1;
        if (randomNum == 3) {
            try {
                Thread.sleep(5000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            throw new TimeoutException("Database transaction timed out!");
        }
    }
}
```

If we hit the service during a failure or open state, our dummy values are returned successfully:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0866ea52-1ce7-4f63-9173-d3e6951af802/markdown_4/imgs/img_in_image_box_203_110_925_397.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A39Z%2F-1%2F%2F4290952af50c9137368c48751887d8929dd8dcc72912a27d0b09e75f132c6ca5" alt="Image" width="67%" /></div>
<div style="text-align: center;">Figure 7.8: Your service invocation using a Resilience4j fallback.</div>

---

## 7.5 Implementing the Bulkhead Pattern

By default, Java container threads are shared. A slowdown in one remote endpoint can occupy all container worker threads, blocking requests for other, healthy endpoints.

The **Bulkhead** pattern segregates calls into separate pools. Resilience4j offers two bulkhead strategies:

### 1. Semaphore Bulkhead (Default)
Enforces concurrency limits using semaphores. Requests run on the caller's main thread, preserving local thread context.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7ccd4b5c-38a5-4fd7-af19-2691c73d0bc7/markdown_0/imgs/img_in_image_box_181_109_871_530.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A37Z%2F-1%2F%2F6ec3db8a6f1c502efff8974a42821854ec54b3c4f05512def777420d303f987a" alt="Image" width="64%" /></div>
<div style="text-align: center;">Figure 7.9: The default Resilience4j bulkhead type is the semaphore approach.</div>

### 2. Thread Pool Bulkhead
Isolates executions inside a dedicated thread pool with a bounded queue, rejecting calls only when pool resources are saturated:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7ccd4b5c-38a5-4fd7-af19-2691c73d0bc7/markdown_0/imgs/img_in_image_box_145_700_918_1056.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A37Z%2F-1%2F%2Fc8ce3756eb0fb1301e485fa877c61ae90f95ef466bab352fd60bf6b33b869f60" alt="Image" width="72%" /></div>
<div style="text-align: center;">Figure 7.10: A Resilience4j command tied to segregated thread pools.</div>

### Configuring Bulkhead Properties in `application.yml`
```yaml
resilience4j:
  bulkhead:
    instances:
      orderBulkhead:
        maxConcurrentCalls: 10
        maxWaitDuration: 10
  threadpoolbulkhead:
    instances:
      orderThreadPoolBulkhead:
        maxThreadPoolSize: 4
        coreThreadPoolSize: 2
        queueCapacity: 5
        keepAliveDuration: 20
```

Annotate the method to isolate resource execution:

```java
@CircuitBreaker(name = "orderService", fallbackMethod = "buildFallbackOrderList")
@Bulkhead(name = "orderThreadPoolBulkhead", type = Bulkhead.Type.THREADPOOL, fallbackMethod = "buildFallbackOrderList")
public List<Order> getOrdersByRestaurant(String restaurantId) {
    return orderRepository.findByRestaurantId(restaurantId);
}
```

---

## 7.6 The Retry Pattern

The **Retry** pattern automatically re-attempts failed operations to recover from transient failures (e.g. network drops, temporary downstream glitches).

Configure retry parameters:
```yaml
resilience4j:
  retry:
    instances:
      orderRetry:
        maxAttempts: 5
        waitDuration: 10000
        retryExceptions:
          - java.util.concurrent.TimeoutException
```

Attach `@Retry` to your method:
```java
@Retry(name = "orderRetry", fallbackMethod = "buildFallbackOrderList")
public List<Order> getOrdersByRestaurant(String restaurantId) {
    return orderRepository.findByRestaurantId(restaurantId);
}
```

---

## 7.7 The Rate Limiter Pattern

The **Rate Limiter** pattern limits request volumes to prevent overloading downstream services.

Configure rate limiting properties:
```yaml
resilience4j:
  ratelimiter:
    instances:
      orderRateLimiter:
        limitForPeriod: 5
        limitRefreshPeriod: 10000
        timeoutDuration: 1000
```

Implement using `@RateLimiter`:
```java
@RateLimiter(name = "orderRateLimiter", fallbackMethod = "buildFallbackOrderList")
public List<Order> getOrdersByRestaurant(String restaurantId) {
    return orderRepository.findByRestaurantId(restaurantId);
}
```

---

## 7.8 ThreadLocal Context Propagation with Resilience4j

A major drawback of running remote calls in a Thread Pool Bulkhead is that executions occur on a separate thread pool. Java `ThreadLocal` context variables—which hold correlation IDs and headers—do not automatically carry over to the new thread pool.

To resolve this issue:
1. **Use Semaphore Isolation**: If you do not require strict thread pool limits, use a Semaphore Bulkhead. Since it executes on the caller's main thread, `ThreadLocal` context is preserved naturally.
2. **Context Propagation Configuration**: If using thread pools, map correlation headers through custom thread configuration wrappers.

To test this correlation ID context propagation, call the order service while passing `ftgo-correlation-id` in the headers:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//47e368cf-85e5-4073-98f9-7f4002948ac7/markdown_0/imgs/img_in_image_box_185_110_931_411.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A37Z%2F-1%2F%2F22acccfca56b793bf333851b858a8328b92ab11211951e93804cf1322ca76149" alt="Image" width="70%" /></div>
<div style="text-align: center;">Figure 7.11: Adding a correlation ID to the order service HTTP header.</div>

Upon submission, the console logs verify context propagation across filters, controllers, and services:

```text
UserContextFilter Correlation id: TEST-CORRELATION-ID
OrderServiceController Correlation id: TEST-CORRELATION-ID
OrderService:getOrdersByRestaurant Correlation id: TEST-CORRELATION-ID
```

---

## 7.9 Dynamic Resiliency Configuration Reload (Config Server & Actuator)

In a live production environment, hardcoding thresholds like circuit breaker timeouts or failure rates in the service bundle requires compiling and redeploying the application when tuning parameters. To achieve runtime flexibility, we integrate Resilience4j with **Spring Cloud Config Server**.

### 7.9.1 Refreshing Circuit Breaker Properties
By hosting your configuration properties (e.g. `order-service-prod.yml`) in a centralized Git repository managed by the Config Server, you can update resilience limits dynamically:

```yaml
# Inside Git repository: order-service-prod.yml
resilience4j:
  circuitbreaker:
    instances:
      orderService:
        failureRateThreshold: 35 # Adjusted down from 50 for stricter thresholds
        waitDurationInOpenState: 10000 # Wait 10s before testing recovery
```

When you commit changes to the Git config repository, you trigger a configuration refresh by sending an empty `POST` request to the application's Actuator bus endpoint:

```bash
curl -X POST http://localhost:8081/actuator/bus-refresh
```

The Spring Cloud Bus broadcasts the event, causing the client service to invoke Spring's config refresh listeners. Resilience4j captures the update event and re-initializes runtime configurations dynamically without restarting the application context.

---

## 7.10 Programmatic Resilience4j Core Java DSL Setup

While Spring Boot annotations (`@CircuitBreaker`, `@Bulkhead`) are highly convenient, they rely on AOP aspect proxies. In some situations (e.g., legacy codebases, raw JUnit testing, or reactive code pipelines), you must configure and invoke Resilience4j patterns programmatically.

### 7.10.1 Programmatic Setup Example: `ProgrammaticResilienceDemo.java`
Below is a complete Java implementation showcasing the core configuration builder DSL:

```java
package com.ftgo.order.resilience;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import io.vavr.control.Try;

import java.time.Duration;
import java.util.concurrent.TimeoutException;
import java.util.function.Supplier;

public class ProgrammaticResilienceDemo {

    /**
     * Programmatic entry point executing functional decorator patterns.
     * Demonstrates registry setups and Vavr try recovery blocks.
     */
    public static void main(String[] args) {
        // 1. Build custom Circuit Breaker configuration schema details
        CircuitBreakerConfig config = CircuitBreakerConfig.custom()
            .failureRateThreshold(50)                               // Trip if failure percent exceeds 50%
            .ringBufferSizeInClosedState(10)                       // Evaluate failures across 10 request windows
            .waitDurationInOpenState(Duration.ofSeconds(10))        // Keep circuit open for 10 seconds before recovery
            .recordExceptions(TimeoutException.class)               // Track and count timeouts as system failures
            .build();

        // 2. Instantiate a central Registry using the default configurations
        CircuitBreakerRegistry registry = CircuitBreakerRegistry.of(config);

        // 3. Obtain or instantiate a thread-safe named CircuitBreaker from the registry
        CircuitBreaker circuitBreaker = registry.circuitBreaker("orderService");

        // 4. Define the target call supplier representing remote API requests
        Supplier<String> remoteCall = () -> {
            if (Math.random() > 0.5) {
                throw new RuntimeException("Backend database connection timed out!");
            }
            return "Order List Retrieved Successfully";
        };

        // 5. Decorate the Java functional Supplier with Circuit Breaker tracking rules
        Supplier<String> decoratedSupplier = CircuitBreaker.decorateSupplier(circuitBreaker, remoteCall);

        // 6. Execute the decorated supplier safely, trapping failures using Vavr Try blocks.
        // If the execution throws a CallNotPermittedException or generic exception,
        // recover invokes the fallback lambdas to return default degradations.
        String result = Try.ofSupplier(decoratedSupplier)
            .recover(throwable -> "Fallback: Default backup orders list (Service Degradation)")
            .get();


        System.out.println("Result: " + result);
    }
}
```

---

## 7.11 Advanced ThreadLocal Context Propagation with Custom Executors

When using the **Thread Pool Bulkhead** pattern, Resilience4j executes the decorated service calls on a dedicated thread pool rather than the main request thread. Because Java's standard `ThreadLocal` storage does not propagate variables to separate threads, variables such as correlation IDs, authentication tokens, and MDC logging parameters get lost.

To resolve this issue, we must wrap thread pool execution inside a context-propagating executor.

### 7.11.1 Context-Aware Executor Config: `ThreadContextConfig.java`
Create a custom task decorator that captures the thread-local state of the caller thread and copies it to the worker thread when execution begins:

```java
package com.ftgo.order.config;

import com.ftgo.order.utils.UserContextHolder;
import com.ftgo.order.utils.UserContext;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.task.TaskDecorator;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;

@Configuration
public class ThreadContextConfig {

    /**
     * Instantiates a context-propagating executor.
     * Maps the ThreadLocal variables of parent HTTP threads to background worker threads.
     *
     * @return Executor configured with a custom task decorator.
     */
    public Executor threadContextPropagatingExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        
        // Configure standard thread pool settings
        executor.setCorePoolSize(5);        // Minimum number of threads kept alive in the pool
        executor.setMaxPoolSize(10);       // Maximum boundary of worker threads under high load
        executor.setQueueCapacity(20);     // Buffer size for tasks waiting to be processed
        executor.setThreadNamePrefix("Resilience-Worker-");
        
        // Register the task decorator to copy ThreadLocal states across thread boundaries
        executor.setTaskDecorator(new ThreadContextDecorator());
        executor.initialize();
        return executor;
    }

    /**
     * A TaskDecorator copies state parameters from the calling thread to the running thread.
     * This is essential for tracing request hops in Resilience4j thread-pool bulkheads.
     */
    private static class ThreadContextDecorator implements TaskDecorator {
        @Override
        public Runnable decorate(Runnable runnable) {
            // 1. Capture user context on the primary parent thread (executed before context switch)
            UserContext context = UserContextHolder.getContext();
            
            return () -> {
                try {
                    // 2. Bind the user context to the active child worker thread
                    UserContextHolder.setContext(context);
                    
                    // Execute the primary task logic
                    runnable.run();
                } finally {
                    // 3. Clear context variables to prevent thread-pool memory leaks.
                    // Since threads in thread pools are reused, failing to clear ThreadLocal variables
                    // will leak trace details to subsequent, unrelated executions on this thread.
                    UserContextHolder.getContext().setCorrelationId("");
                    UserContextHolder.getContext().setAuthToken("");
                    UserContextHolder.getContext().setUserId("");
                    UserContextHolder.getContext().setRestaurantId("");
                }
            };
        }
    }
}
```

By assigning this task executor to handle execution threads, trace contexts propagate across thread pool boundaries, preventing trace fragmentation.

---

## 7.12 Exporting Resilience4j Metrics to Micrometer & Prometheus

Monitoring circuit state changes in a production environment is vital. Resilience4j integrates out-of-the-box with **Micrometer** to publish metrics to tools like Prometheus and Grafana.

### 7.12.1 Include Metrics Dependencies
To publish Resilience4j state statistics to Micrometer registries, you must include both the Micrometer Prometheus binding and the core Resilience4j Micrometer bridge dependencies inside your microservice `pom.xml`:

```xml
<dependency>
    <groupId>io.github.resilience4j</groupId>
    <artifactId>resilience4j-micrometer</artifactId>
    <version>${resilience4j.version}</version>
</dependency>
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```


### 7.12.2 Configure Actuator Metrics Exports: `application.yml`
```yaml
management:
  endpoints:
    web:
      exposure:
        include: health, info, prometheus, metrics
  metrics:
    export:
      prometheus:
        enabled: true
```

### 7.12.3 Key Prometheus Metrics Reference
Once Prometheus scrapes the `/actuator/prometheus` endpoint, you can query metrics to build Grafana visualization dashboards:

* `resilience4j_circuitbreaker_state`: Indicates the current state of the circuit (value: `0` for closed, `1` for open, `2` for half-open).
* `resilience4j_circuitbreaker_failure_rate`: The active failure rate calculated by the Ring Bit Buffer.
* `resilience4j_circuitbreaker_buffered_calls`: Total number of buffered calls in the current sliding window.
* `resilience4j_bulkhead_available_concurrent_calls`: The remaining capacity of the bulkhead queue.

---

## 7.13 Resilience4j Aspect Execution Order (AOP Priority)

When applying multiple fault-tolerance patterns on the same microservice method, the execution order of these aspects becomes critical. For example, if we annotate a method with `@Retry`, `@CircuitBreaker`, and `@Bulkhead`:

```java
@Retry(name = "orderRetry")
@CircuitBreaker(name = "orderService")
@Bulkhead(name = "orderBulkhead")
public List<Order> getOrdersByRestaurant(String restaurantId) { ... }
```

### 7.13.1 Default Aspect Order
By default, Resilience4j executes aspects in the following sequential hierarchy:

1. **Retry Aspect** (Lowest priority - executed outer-most)
2. **CircuitBreaker Aspect**
3. **RateLimiter Aspect**
4. **TimeLimiter Aspect**
5. **Bulkhead Aspect** (Highest priority - executed inner-most)

* *The Impact*: Since the **Retry Aspect** is executed outer-most, it catches exceptions thrown by the inner aspects. If the inner Circuit Breaker is in the `OPEN` state and throws a `CallNotPermittedException`, the Retry aspect will intercept it and attempt retries. Under an open circuit, retrying is counter-productive because the calls will immediately fail anyway.

### 7.13.2 Tuning Aspect Priority in YAML
You can customize the aspect order using configurations inside `application.yml` to change aspect execution order. For instance, if you want the retry aspect to run *inside* the bulkhead aspect (so that each retry requires securing a slot in the bulkhead thread pool) or *inside* the circuit breaker (so that failures are recorded individually, but we do not retry if the circuit is open), you adjust their orders:

```yaml
resilience4j:
  retry:
    retry-aspect-order: 399         # Determines where Retry aspect executes in the AOP interceptor chain
  circuitbreaker:
    use-aspect-order: true          # Tells Resilience4j to enforce aspect priorities
    circuit-breaker-aspect-order: 400
  bulkhead:
    bulkhead-aspect-order: 401     # Bulkhead aspect runs inner-most
```

By assigning AOP order values, you dictate proxy execution flow:
* Lower integer values indicate outer-most execution aspects (run first).
* Higher integer values indicate inner-most execution aspects (run last).
* Reconfiguring the order allows you to coordinate retries, limits, and circuit breakers to match your exact service degradation architecture.


---

## 7.14 Resilience4j Event Listeners for State Transitions

For operational visibility, we must capture state changes (such as a circuit transitioning from `CLOSED` to `OPEN`) and generate telemetry alerts or write log metrics.

Resilience4j provides a clean event publishing registry that allows programmatic bean listeners:

### 7.14.1 Registry Event Configurator: `ResilienceEventListener.java`
Below is the Java registry setup class capturing and logging state transition events:

```java
package com.ftgo.order.resilience;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Configuration;

import javax.annotation.PostConstruct;

@Configuration
public class ResilienceEventListener {
    private static final Logger logger = LoggerFactory.getLogger(ResilienceEventListener.class);
    
    private final CircuitBreakerRegistry circuitBreakerRegistry;

    public ResilienceEventListener(CircuitBreakerRegistry circuitBreakerRegistry) {
        this.circuitBreakerRegistry = circuitBreakerRegistry;
    }

    @PostConstruct
    public void registerListeners() {
        CircuitBreaker cb = circuitBreakerRegistry.circuitBreaker("orderService");

        // Listen for circuit breaker state transition events
        cb.getEventPublisher()
            .onStateTransition(event -> {
                logger.warn("Circuit Breaker State Transition: {} changed state from {} to {}",
                    event.getCircuitBreakerName(),
                    event.getStateTransition().getFromState(),
                    event.getStateTransition().getToState()
                );
            })
            .onSuccess(event -> {
                logger.debug("Circuit Breaker Successful Invocation: {}", event.getCircuitBreakerName());
            })
            .onError(event -> {
                logger.error("Circuit Breaker Recorded Error: {} - Details: {}",
                    event.getCircuitBreakerName(),
                    event.getThrowable().getMessage()
                );
            });
    }
}
```

---

## 7.15 Custom Exception Recording and Exclusion Rules

By default, the circuit breaker records any instance of `java.lang.Throwable` as a failure. However, not all exceptions indicate network issues or system failure:
* **System Failures**: Connection timed out, database offline, packet drops. (Must be recorded to trip the circuit).
* **Business validation anomalies**: HTTP 400 Bad Request, invalid order payload, invalid credentials. (Should be ignored by the circuit breaker).

If we record business exceptions, validation errors from users could trigger the circuit breaker, blocking healthy requests from other users.

### 7.15.1 Configure Exception Recording Rules
Update `application.yml` properties to define explicit records and exclusions:

```yaml
resilience4j:
  circuitbreaker:
    instances:
      orderService:
        # Record only network-level exceptions
        recordExceptions:
          - java.io.IOException
          - java.util.concurrent.TimeoutException
          - org.springframework.web.client.ResourceAccessException
        # Ignore validation and business-level exceptions
        ignoreExceptions:
          - com.ftgo.order.exception.OrderValidationException
          - com.ftgo.order.exception.InvalidRestaurantIdException
```

By configuring these rules, business-level execution paths do not affect service health statistics.

---

## 7.16 Resilience4j Actuator Health Indicators Customization

By default, when you register a circuit breaker with Spring Boot Actuator, its state transitions affect the health status returned by the `/actuator/health` endpoint:
* **CLOSED**: The health indicator returns `UP`.
* **OPEN / HALF-OPEN**: The health indicator returns `DOWN`.

### 7.16.1 The Production Risk of Default Health Mappings
If a Kubernetes liveness/readiness probe or Eureka heartbeats query `/actuator/health` and find the service marked `DOWN` due to an open circuit breaker, the container scheduler will terminate and reschedule the container. This causes unnecessary service restarts and increases overall system instability, especially since the fallback method is already successfully shielding the system and routing requests to dummy values.

### 7.16.2 Tune Health Indicator Mappings
To prevent an open circuit breaker from marking the entire container instance as dead, configure the indicator behavior in `application.yml` to prevent state transitions from propagating:

```yaml
resilience4j:
  circuitbreaker:
    instances:
      orderService:
        registerHealthIndicator: true
        # Prevent an OPEN circuit from propagating a DOWN status to Actuator health
        allowHealthIndicatorToTransitionState: false
```

When set to `false`, the detailed health endpoint will still show the circuit status as `OPEN` under the details block, but the overall status of the application remains `UP`, preventing container orchestrators from triggering rolling restarts.

---

## 7.17 The Time Limiter Pattern

The **Time Limiter** pattern limits the execution duration of downstream calls, throwing a `TimeoutException` if the remote resource takes longer than the configured window.

### 7.17.1 Configure Time Limiter Properties
```yaml
resilience4j:
  timelimiter:
    instances:
      orderTimeLimiter:
        timeoutDuration: 3000 # Terminate call if execution exceeds 3s
        cancelRunningFuture: true # Cancel task execution on timeout
```

### 7.17.2 Implement using `@TimeLimiter`
Unlike other patterns, the Time Limiter requires returning asynchronous wrapper types (such as `CompletableFuture` or reactive `Mono`/`Flux`) to allow execution management on separate thread pools:

```java
@TimeLimiter(name = "orderTimeLimiter", fallbackMethod = "buildFallbackOrderFuture")
public CompletableFuture<List<Order>> getOrdersAsync(String restaurantId) {
    return CompletableFuture.supplyAsync(() -> orderRepository.findByRestaurantId(restaurantId));
}

private CompletableFuture<List<Order>> buildFallbackOrderFuture(String restaurantId, Throwable t) {
    List<Order> fallbackList = new ArrayList<>();
    Order order = new Order();
    order.setOrderId("TIMEOUT-DEGRADED");
    fallbackList.add(order);
    return CompletableFuture.completedFuture(fallbackList);
}
```

---




## Chapter Summary

* Synchronous downstream calls to slow dependencies can cause **cascading failures** that exhaust caller thread pools and take down the system.
* The **Circuit Breaker** pattern protects callers by monitoring failure rates using a **Ring Bit Buffer** and transitioning through three states: **CLOSED**, **OPEN**, and **HALF-OPEN**.
* The **Fallback** pattern executes alternative logic to return default values or cached responses when calls fail or the circuit is open.
* The **Bulkhead** pattern isolates resources (using thread pools or semaphores) to prevent a failure in one service from impacting other APIs.
* The **Retry** pattern automatically retries failed calls to handle transient network glitches.
* The **Rate Limiter** pattern restricts invocation frequencies to protect services from overload.
* When using a Thread Pool Bulkhead, you must handle ThreadLocal context propagation by implementing custom `TaskDecorator` beans to copy tracing contexts to worker threads.
* CENTRAL configurations can be reloaded dynamically at runtime using Git-backed **Spring Cloud Config Server** and the `/actuator/bus-refresh` POST endpoint without context restarts.
* A programmatic Java DSL configuration (`CircuitBreakerConfig` and `CircuitBreakerRegistry`) enables setting up resilient pipelines without Spring Boot AOP annotation dependencies.
* The execution priority of multiple aspects defaults to a hierarchy (Retry outer-most, Bulkhead inner-most) but can be reconfigured to prevent retries from running against open circuits.
* Operational state changes can be monitored and alerted on by registering listener hooks with the named `CircuitBreaker` event publisher.
* Business-level exceptions should be registered as ignored to prevent client input validations from counting against system failure thresholds.
* Actuator health mappings can be tuned to prevent container schedulers from triggering rolling restarts when a service is temporarily degraded but successfully running fallbacks.
* Prometheus metrics exports configured via Micrometer expose circuit state metrics (`resilience4j_circuitbreaker_state`) to Grafana dashboard monitors.

