# Chapter 5: Service Registry and Discovery

In a distributed microservices architecture, services must communicate with each other over the network. To make a call, a service needs to know the network location (IP address and port) of the target service. In a traditional environment, these locations are static. In a cloud environment, however, service instances are ephemeral: containers are created, terminated, and rescheduled dynamically, assigning them unpredictable IP addresses.

This chapter covers the conceptual and technical implementation of service registry and discovery. We will compare traditional DNS and load-balancing architectures with dynamic cloud-based service discovery. We will build a **Spring Cloud Netflix Eureka** server from scratch and register client microservices with it. Finally, we will compare three client invocation libraries: Spring Discovery Client, load-balanced RestTemplate, and OpenFeign.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain why traditional DNS and static load balancers fail in dynamic cloud environments.
2. Describe the four core operations of cloud service discovery: registration, lookup, information sharing, and health monitoring.
3. Compare client-side load balancing with server-side load balancing.
4. Build a standalone **Eureka Service Registry Server** using Spring Cloud.
5. Register client microservices with the Eureka server and explain why `preferIpAddress` is critical in container environments.
6. Retrieve service instance metadata using Eureka's REST API and monitor services via the Eureka Dashboard.
7. Call remote services using a low-level **DiscoveryClient**, a load-balanced **RestTemplate**, and a declarative **OpenFeign** client interface.

---

## 5.1 Where's My Service? The Limits of DNS and Load Balancers

In traditional corporate data centers, service location resolution relies on a combination of a Domain Name Service (DNS) and a network load balancer:

![Figure 5.1: DNS and load balancer resolution model](https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1dc6c1ed-5c6d-4f75-8926-8a86e169f75c/markdown_4/imgs/img_in_image_box_167_231_930_855.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A38Z%2F-1%2F%2F065da0c766b018b6787fcb7e13b145405426b938f62a056b9a0618f4e0b02e72)
*Figure 5.1: Legacy service location resolution using static IP addresses and network load balancers.*

1. The service consumer calls a DNS hostname (e.g. `http://myservice.company.com/api`).
2. The DNS maps the hostname to the IP address of a dedicated network load balancer.
3. The load balancer receives the request and forwards it to one of a static group of servers.

### Why This Model Fails in Cloud-Based Microservices:
* **Single Point of Failure**: The network load balancer becomes a centralized choke point. If the load balancer fails, all services sitting behind it become unreachable.
* **Scaling Constraints**: Traditional load balancers scale vertically. High licensing costs and rigid redundancy configurations limit horizontal expansion.
* **Static Routing**: Traditional load balancers are designed for static servers. They cannot dynamically handle rapid container creation, termination, or IP changes.
* **Manual Translation Layers**: Defining routing rules requires manual administrative updates to routing tables, preventing autonomous deployments.

---

## 5.2 Cloud Service Discovery Design

The dynamic nature of cloud containers requires a highly available, decentralized service discovery mechanism:

* **Highly Available**: A clustered environment where registry lookups are replicated peer-to-peer.
* **Load Balanced**: Requests are dynamically distributed across all available service instances.
* **Resilient Client-Side Caching**: Service addresses are cached locally on the consumer side. If the registry server crashes, the clients can continue calling active services using their local cache.
* **Fault Tolerant**: Automatic detection of service health; unhealthy containers are evicted without manual intervention.

### Service Discovery Concepts
A service discovery system coordinates four basic operational tasks:

![Figure 5.2: Service discovery concepts flow](https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0a94a473-29b9-49f8-872e-43a944ae9e01/markdown_2/imgs/img_in_image_box_159_577_942_1138.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A37Z%2F-1%2F%2Ffb28c1ad0e567c81791ea38da7d1e4c87286a3923cd03cc3bde9e05dd1b63dda)
*Figure 5.2: The operational steps of service registration, replication, health checking, and client lookups.*

1. **Service Registration**: When a microservice instance starts up, it registers its IP address, port, and service identifier (e.g. `licensing-service`) with the service registry.
2. **Client Lookup (Resolution)**: When a calling service needs to invoke another service, it queries the registry to obtain a list of healthy instances for that service.
3. **Information Sharing**: Service registry nodes share registration details peer-to-peer using replication protocols to ensure high availability.
4. **Health Monitoring**: Registered services send periodic heartbeat signals to the registry. If a service fails to send a heartbeat within a specified window, the registry marks it as unhealthy and evicts it from the active routing list.

---

### Client-Side Load Balancing
Instead of invoking the Service Discovery Server on every API call (which introduces network latency), a consumer uses **Client-Side Load Balancing**:

![Figure 5.3: Client-side caching and load balancing](https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//0a94a473-29b9-49f8-872e-43a944ae9e01/markdown_4/imgs/img_in_image_box_279_193_939_882.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A39Z%2F-1%2F%2Fc46b060a463419fee2b2157b4d040878007aeb56baa6c814511a449aa3019ead)
*Figure 5.3: Client-side load balancing caches service locations locally on the calling microservice.*

1. **Query and Cache**: The client contacts the service registry once, fetches the list of active service instances, and caches this list locally.
2. **Local Routing**: When the client calls a service, it distributes requests across the cached instances (e.g. using a round-robin algorithm) without querying the registry.
3. **Background Updates**: A background thread periodically contacts the registry to refresh the local cache with the latest health status.

---

## 5.3 Building the Eureka Service Server

The Spring Cloud Netflix Eureka server provides service discovery. We bootstrap it using Spring Initializr, importing: `Eureka Server`, `Config Client`, and `Spring Boot Actuator`.

### The Maven POM Configuration
Create the following file in `eurekaserver/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>com.optimagrowth</groupId>
        <artifactId>parent-pom</artifactId>
        <version>1.0.0-SNAPSHOT</version>
        <relativePath>../pom.xml</relativePath>
    </parent>

    <artifactId>eureka-server</artifactId>
    <name>Eureka Service Registry Server</name>

    <dependencies>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-netflix-eureka-server</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-config</artifactId>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

---

### The Eureka Server Application Class
Create the bootstrap class inside `com.ftgo.eureka.EurekaServerApplication.java` and annotate it with `@EnableEurekaServer`:

```java
package com.ftgo.eureka;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.netflix.eureka.server.EnableEurekaServer;

@SpringBootApplication
@EnableEurekaServer // Activates the Eureka Service Registry features
public class EurekaServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(EurekaServerApplication.class, args);
    }
}
```

---

### Configuring the Eureka Server
Create `eurekaserver/src/main/resources/bootstrap.yml` to retrieve configurations from the Config Server:

```yaml
spring:
  application:
    name: eureka-server
  profiles:
    active: dev
  cloud:
    config:
      uri: http://localhost:8071
```

Define the Eureka configuration parameters inside the Config Server repository (`eureka-server-dev.yml`):

```yaml
server:
  port: 8070 # Standard port for Eureka server registry

eureka:
  client:
    # Tell Eureka client libraries not to register this registry instance itself
    registerWithEureka: false
    # Tell Eureka client libraries not to pull a copy of the registry locally
    fetchRegistry: false
    serviceUrl:
      defaultZone: http://localhost:8070/eureka/
  server:
    # Wait 5 minutes for peer servers to replicate registry details before starting
    waitTimeInMsWhenSyncEmpty: 0
```

---

## 5.4 Registering Eureka Clients

Now, we will register `order-service` and `kitchen-service` as client services with the Eureka registry.

### 1. Add Client Maven Dependency
Add the Eureka client starter dependency to `order-service/pom.xml`:

```xml
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-netflix-eureka-client</artifactId>
</dependency>
```

---

### 2. Configure Client Properties
Add the Eureka properties to the service configuration file in the Config Server repository (`order-service-dev.yml`):

```yaml
eureka:
  instance:
    # Register the service using its IP address instead of its hostname
    preferIpAddress: true
  client:
    # Enable the Eureka client libraries
    enabled: true
    # Tells the client to fetch a local copy of the registry cache
    fetchRegistry: true
    # Tells the client to register itself with the Eureka server
    registerWithEureka: true
    serviceUrl:
      defaultZone: http://localhost:8070/eureka/
```

---

### The Critical Role of `preferIpAddress` in Containerized Environments
By default, Eureka clients register their container-assigned hostname (e.g., `5b41d8c36fc8` or `docker_container_name`). 

* **The Problem**: In container runtimes (like Docker or Kubernetes), hostnames are ephemeral container IDs. These hostnames cannot be resolved by other containers on the bridge network.
* **The Solution**: Setting `eureka.instance.preferIpAddress: true` tells the service client to register its internal IP address (e.g., `172.18.0.4`) with Eureka. This allows other containers on the bridge network to resolve the address and call the service.

---

### Monitoring and Querying the Registry

#### 1. The Eureka Dashboard
Open `http://localhost:8070` in your web browser. The Eureka Dashboard displays active registrations, system status, resource usage, and running instances.

#### 2. Querying the Registry REST API
You can query the registry data directly using Eureka's REST endpoints:

```bash
curl -H "Accept: application/json" http://localhost:8070/eureka/apps/order-service
```

The response returns a JSON representation of the active instances:

```json
{
  "application": {
    "name": "ORDER-SERVICE",
    "instance": [
      {
        "instanceId": "172.18.0.4:order-service:8081",
        "hostName": "172.18.0.4",
        "app": "ORDER-SERVICE",
        "ipAddr": "172.18.0.4",
        "status": "UP",
        "port": {
          "$": 8081,
          "@enabled": "true"
        }
      }
    ]
  }
}
```

---

## 5.5 Service Lookup and Invocation Mechanisms

Spring Cloud supports three distinct ways to invoke a remote microservice:

```
  +-------------------------+             +-------------------------+
  |    RestTemplate Call    |             |    OpenFeign Call       |
  +-------------------------+             +-------------------------+
  | http://organization-... |             | @FeignClient interface  |
  +------------+------------+             +------------+------------+
               |                                       |
               v                                       v
  +-----------------------------------------------------------------+
  |                Spring Cloud LoadBalancer                        |
  +-----------------------------------------------------------------+
```

### 1. Low-Level `DiscoveryClient` API
The `DiscoveryClient` class provides direct access to the Eureka registry. It fetches instances manually and does not provide client-side load balancing.

```java
```java
package com.ftgo.order.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.cloud.client.ServiceInstance;
import org.springframework.cloud.client.discovery.DiscoveryClient;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.List;

@Service
public class OrderService {

    @Autowired
    private DiscoveryClient discoveryClient;

    public void invokeWithDiscoveryClient(String ticketId) {
        // Query Eureka for instances matching the service ID
        List<ServiceInstance> instances = discoveryClient.getInstances("kitchen-service");

        if (instances.isEmpty()) {
            throw new IllegalArgumentException("No kitchen-service instances found!");
        }

        // Manually select the first instance (no load balancing logic)
        ServiceInstance instance = instances.get(0);
        String url = String.format("%s/v1/kitchen/ticket/%s", instance.getUri(), ticketId);

        RestTemplate restTemplate = new RestTemplate();
        ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
        System.out.println("DiscoveryClient Response: " + response.getBody());
    }
}
```

*Note: Use `DiscoveryClient` only when you need to inspect service metadata or list instances. For standard API calls, use client-side load balancing.*

---

### 2. Load-Balanced `RestTemplate`
This approach uses a standard `RestTemplate` bean annotated with `@LoadBalanced`. Spring intercepts requests and replaces the service name in the URL with a healthy instance IP retrieved from the local registry cache.

Define the load-balanced `RestTemplate` bean:
```java
package com.ftgo.order.config;

import org.springframework.cloud.client.loadbalancer.LoadBalanced;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

@Configuration
public class ClientConfig {
    @Bean
    @LoadBalanced // Enables client-side load balancing
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}
```

Invoke the remote service using the service ID hostname:
```java
package com.ftgo.order.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

@Service
public class OrderService {

    @Autowired
    private RestTemplate restTemplate;

    public void invokeWithLoadBalancedRestTemplate(String ticketId) {
        // The hostname 'kitchen-service' is resolved dynamically by Spring Cloud LoadBalancer
        String url = "http://kitchen-service/v1/kitchen/ticket/" + ticketId;
        ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
        System.out.println("RestTemplate Response: " + response.getBody());
    }
}
```

---

### 3. Declarative REST Client with OpenFeign
OpenFeign is a declarative REST client library. Developers define a Java interface with Spring Web annotations, and OpenFeign automatically generates the implementation proxy at runtime.

#### 1. Add OpenFeign Starter
Add the OpenFeign dependency to `order-service/pom.xml`:

```xml
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-openfeign</artifactId>
</dependency>
```

#### 2. Enable Feign Clients
Add the `@EnableFeignClients` annotation to the bootstrap class:

```java
package com.ftgo.order;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.openfeign.EnableFeignClients;

@SpringBootApplication
@EnableFeignClients // Enables Spring Cloud OpenFeign client proxy generation
public class OrderServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(OrderServiceApplication.class, args);
    }
}
```

#### 3. Define the Feign Client Interface
Create a client interface, specifying the target service ID using the `@FeignClient` annotation:

```java
package com.ftgo.order.client;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;

// Connects to kitchen-service and balances calls automatically
@FeignClient("kitchen-service") 
public interface KitchenFeignClient {

    @GetMapping(value = "/v1/kitchen/ticket/{ticketId}", consumes = "application/json")
    String getTicket(@PathVariable("ticketId") String ticketId);
}
```

#### 4. Invoke the Declarative Client
Inject and call the interface like a standard local service class:

```java
package com.ftgo.order.service;

import com.ftgo.order.client.KitchenFeignClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class OrderService {

    @Autowired
    private KitchenFeignClient kitchenFeignClient;

    public void invokeWithFeignClient(String ticketId) {
        // Invokes the remote service via the OpenFeign proxy
        String response = kitchenFeignClient.getTicket(ticketId);
        System.out.println("FeignClient Response: " + response);
    }
}
```

---

## 5.6 Custom Spring Cloud LoadBalancer Zone-Preference Routing

In production systems deployed across multiple AWS Availability Zones (AZs), sending requests across zones introduces network latency and cross-AZ data transfer fees. We can configure **Spring Cloud LoadBalancer** to prioritize routing requests to service instances located in the same Availability Zone.

### 5.6.1 Custom LoadBalancer Configuration Class
Create the configuration class using Project Reactor APIs to filter out-of-zone instances:

```java
package com.ftgo.order.config;

import org.springframework.cloud.client.ServiceInstance;
import org.springframework.cloud.loadbalancer.core.RandomLoadBalancer;
import org.springframework.cloud.loadbalancer.core.ReactorServiceInstanceLoadBalancer;
import org.springframework.cloud.loadbalancer.core.ServiceInstanceListSupplier;
import org.springframework.cloud.loadbalancer.support.LoadBalancerClientFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.core.env.Environment;

public class CustomLoadBalancerConfiguration {

    @Bean
    public ReactorServiceInstanceLoadBalancer reactorServiceInstanceLoadBalancer(
            Environment environment,
            LoadBalancerClientFactory loadBalancerClientFactory) {
        
        String name = environment.getProperty(LoadBalancerClientFactory.PROPERTY_NAME);
        
        // Return a custom load balancer that prefers instances registered in the same zone
        return new ZonePreferenceLoadBalancer(
            loadBalancerClientFactory.getLazyProvider(name, ServiceInstanceListSupplier.class),
            name,
            environment.getProperty("eureka.instance.metadata-map.zone", "us-east-1a")
        );
    }
}
```

### 5.6.2 Implementing Zone Filtering Logic: `ZonePreferenceLoadBalancer.java`
```java
package com.ftgo.order.config;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.cloud.client.ServiceInstance;
import org.springframework.cloud.loadbalancer.core.ReactorServiceInstanceLoadBalancer;
import org.springframework.cloud.loadbalancer.core.ServiceInstanceListSupplier;
import org.springframework.cloud.loadbalancer.model.DefaultResponse;
import org.springframework.cloud.loadbalancer.model.Response;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Random;
import java.util.stream.Collectors;

public class ZonePreferenceLoadBalancer implements ReactorServiceInstanceLoadBalancer {

    private final ObjectProvider<ServiceInstanceListSupplier> position;
    private final String serviceId;
    private final String preferredZone;

    public ZonePreferenceLoadBalancer(ObjectProvider<ServiceInstanceListSupplier> position, String serviceId, String preferredZone) {
        this.position = position;
        this.serviceId = serviceId;
        this.preferredZone = preferredZone;
    }

    @Override
    public Mono<Response<ServiceInstance>> choose(org.springframework.cloud.loadbalancer.model.Request request) {
        ServiceInstanceListSupplier supplier = position.getIfAvailable();
        if (supplier == null) {
            return Mono.just(new DefaultResponse(null));
        }
        return supplier.get().next().map(this::processInstanceList);
    }

    private Response<ServiceInstance> processInstanceList(List<ServiceInstance> instances) {
        if (instances.isEmpty()) {
            return new DefaultResponse(null);
        }

        // Filter instances matching the preferred zone metadata
        List<ServiceInstance> zoneInstances = instances.stream()
            .filter(instance -> preferredZone.equalsIgnoreCase(instance.getMetadata().get("zone")))
            .collect(Collectors.toList());

        List<ServiceInstance> targets = zoneInstances.isEmpty() ? instances : zoneInstances;
        int index = new Random().nextInt(targets.size());
        return new DefaultResponse(targets.get(index));
    }
}
```

---

## 5.7 Service Registry Resiliency: Eureka Clustered Peer-to-Peer Replication

A single Eureka instance in production represents a Single Point of Failure (SPOF). To guarantee high availability, we run multiple Eureka server instances configured as peers that continuously replicate registration state with each other.

### 5.7.1 Configure Host resolution inside `etc/hosts`
To run a cluster locally, map mock server hostnames in your OS hosts file:
```
127.0.0.1 eureka-peer1
127.0.0.1 eureka-peer2
```

### 5.7.2 Peer 1 Properties Profile (`eureka-server-peer1.yml`)
```yaml
server:
  port: 8070

eureka:
  instance:
    hostname: eureka-peer1
  client:
    registerWithEureka: true
    fetchRegistry: true
    serviceUrl:
      defaultZone: http://eureka-peer2:8072/eureka/
```

### 5.7.3 Peer 2 Properties Profile (`eureka-server-peer2.yml`)
```yaml
server:
  port: 8072

eureka:
  instance:
    hostname: eureka-peer2
  client:
    registerWithEureka: true
    fetchRegistry: true
    serviceUrl:
      defaultZone: http://eureka-peer1:8070/eureka/
```

When a microservice registers with `eureka-peer1`, the server automatically replicates the registration details to `eureka-peer2`. If one registry server crashes, the other continues serving lookups uninterrupted.

---

## 5.8 Eureka Self-Preservation Mode & Heartbeats Tuning

Under normal circumstances, if a microservice instance stops sending heartbeats to Eureka (due to crashing or shutting down), Eureka waits for a grace period and then evicts the instance from its registry.

However, if a network partition occurs between Eureka and a large number of instances, Eureka could evict healthy instances, causing cascading routing failures. To prevent this, Eureka uses **Self-Preservation Mode**:

* **How it works**: If the rate of lease renewals drops below a threshold (`eureka.server.renewalPercentThreshold`, defaulting to `85%`), Eureka enters self-preservation mode. It stops evicting any expired instances from the registry, protecting them from temporary network glitches.
* **The Caveat**: During local development, frequently starting and stopping services triggers self-preservation, causing Eureka to retain zombie instances. Therefore, we disable it locally but keep it enabled in production:

```yaml
# Local Eureka Server override configurations (eureka-server-dev.yml)
eureka:
  server:
    enable-self-preservation: false # Disable locally to avoid zombie instances
    eviction-interval-timer-in-ms: 5000 # Sweep expired registrations every 5s
```

For production clients, we tune lease times to ensure rapid discovery updates:

```yaml
# Production client settings
eureka:
  instance:
    # Send heartbeats every 10 seconds (default is 30)
    lease-renewal-interval-in-seconds: 10
    # Tell Eureka to evict if no heartbeat is received for 30 seconds (default is 90)
    lease-expiration-duration-in-seconds: 30
```

---

## 5.9 Service Registry Alternatives: Consul and ZooKeeper

While Eureka is the standard registry in Spring Cloud, other service discovery platforms exist, each offering different trade-offs in terms of consistency and availability:

### 5.9.1 The CAP Theorem Trade-off in Service Registries
According to the CAP Theorem, a distributed system can guarantee at most two of three properties: Consistency, Availability, and Partition-tolerance. Service registries differ fundamentally in how they handle partitions:

* **AP Systems (Eureka)**: Prioritize availability over consistency. During a network partition, Eureka nodes keep running and allow client registrations even if they cannot replicate state. It is considered better to return slightly stale IP addresses (which client-side retries can handle) than to refuse registry queries completely.
* **CP Systems (ZooKeeper, Consul)**: Prioritize consistency over availability. ZooKeeper uses consensus protocols (like Paxos or Raft) to maintain a single source of truth. If a network partition occurs and nodes cannot form a quorum, the registry refuses queries and writes to prevent stale reads.

### 5.9.2 Service Discovery Comparison Matrix

| Metric Parameter | Netflix Eureka | HashiCorp Consul | Apache ZooKeeper |
| :--- | :--- | :--- | :--- |
| **CAP Classification** | AP (Availability / Partition-tolerance). | CP (Consistency / Partition-tolerance). | CP (Consistency / Partition-tolerance). |
| **Consensus Protocol** | Peer-to-peer custom replication. | Raft consensus algorithm. | Zab (ZooKeeper Atomic Broadcast). |
| **Health Checking** | TTL client heartbeats. | Active agent-based checks (HTTP/TCP). | TCP keep-alive sessions. |
| **Built-in Key/Value Store**| No. | Yes (fully functional configuration store). | Yes (hierarchical znode trees). |
| **Spring Cloud Support** | Yes (`spring-cloud-starter-netflix-eureka-client`). | Yes (`spring-cloud-starter-consul-discovery`). | Yes (`spring-cloud-starter-zookeeper-discovery`). |

---

## 5.10 Client-Side Registry Caching & Resiliency

To avoid querying the service registry for every HTTP request, client libraries (such as Spring Cloud LoadBalancer) cache the registry details locally in client memory.

### 5.10.1 Caching Latency (The 30-Second Rule)
By default, clients fetch the active registry details every 30 seconds:

```yaml
eureka:
  client:
    registry-fetch-interval-seconds: 30 # Fetch updates every 30s
```

This caching layer introduces a replication lag:
* **The Scenario**: If an instance of `kitchen-service` crashes, the Eureka server detects the missing heartbeat and evicts the instance. However, client-side caches in the `order-service` might still retain the old IP address for up to 30 seconds.
* **The Impact**: Calls routed to the evicted instance will fail with `Connection Refused` or `SocketTimeoutException` errors.

### 5.10.2 Resiliency Countermeasures
To protect against caching lag, developers must combine client-side load balancing with active client-side resiliency patterns:
1. **Client Retries**: Configure Spring Cloud LoadBalancer or Resilience4j to automatically retry failed requests on a different instance.
2. **Circuit Breakers**: Use circuit breakers (Resilience4j) to trip if a target instance fails repeatedly, routing requests to fallbacks.
3. **HTTP Status Interceptors**: Capture connection exceptions and force an immediate local registry cache refresh to update the instance list.

---

## 5.11 Custom OpenFeign Interceptor for Request Correlation

In microservice systems, propagating correlation IDs (like trace IDs) across downstream REST calls is necessary for distributed tracking. When using **OpenFeign**, we can automate correlation header propagation by registering a custom `RequestInterceptor`:

### 5.11.1 Context Holder class: `UserContext.java`
Keeps the correlation ID in thread-local storage:

```java
package com.ftgo.order.context;

public class UserContext {
    public static final String CORRELATION_ID = "ftgo-correlation-id";

    private static final ThreadLocal<String> correlationId = new ThreadLocal<>();

    public static String getCorrelationId() { return correlationId.get(); }
    public static void setCorrelationId(String id) { correlationId.set(id); }
    public static void clear() { correlationId.remove(); }
}
```

### 5.11.2 Interceptor Implementation: `FeignRequestInterceptor.java`
```java
package com.ftgo.order.config;

import com.ftgo.order.context.UserContext;
import feign.RequestInterceptor;
import feign.RequestTemplate;
import org.springframework.stereotype.Component;

@Component
public class FeignRequestInterceptor implements RequestInterceptor {

    @Override
    public void apply(RequestTemplate template) {
        String correlationId = UserContext.getCorrelationId();
        if (correlationId != null) {
            // Automatically append the correlation ID to the outbound request header
            template.header(UserContext.CORRELATION_ID, correlationId);
        }
    }
}
```

By configuring this interceptor bean, OpenFeign intercepts every outbound client invocation, ensuring transaction tracking context is preserved across service hops.

### 5.11.3 Declarative Feign Configuration: Logger Level and Custom Error Decoders
In enterprise setups, you need to customize OpenFeign's default behaviors, such as logging verbosity and handling downstream errors. We define a local client configuration bean:

```java
package com.ftgo.order.config;

import feign.Logger;
import feign.codec.ErrorDecoder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class FeignClientConfig {

    @Bean
    public Logger.Level feignLoggerLevel() {
        // Log all headers, requests, responses, and metadata for troubleshooting
        return Logger.Level.FULL;
    }

    @Bean
    public ErrorDecoder errorDecoder() {
        return new CustomFeignErrorDecoder();
    }
}
```

We register this custom decoder class to parse downstream errors:

```java
package com.ftgo.order.config;

import feign.Response;
import feign.codec.ErrorDecoder;

public class CustomFeignErrorDecoder implements ErrorDecoder {
    private final ErrorDecoder defaultDecoder = new Default();

    @Override
    public Exception decode(String methodKey, Response response) {
        if (response.status() == 404) {
            return new IllegalArgumentException("Requested resource not found on target microservice");
        }
        if (response.status() == 503) {
            return new IllegalStateException("Target service is currently unavailable or undergoing maintenance");
        }
        return defaultDecoder.decode(methodKey, response);
    }
}
```

To bind this config, reference it directly inside the client interface annotation:

```java
@FeignClient(name = "kitchen-service", configuration = FeignClientConfig.class)
```

---


## 5.12 Hardening Service Registry with HTTP Basic Authentication

To secure the Eureka dashboard and registration endpoints from rogue instances or metadata queries, we secure the server with HTTP Basic Authentication:

### 5.12.1 Add Security Dependency to Eureka Server
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-security</artifactId>
</dependency>
```

### 5.12.2 Configure Security Class in Eureka Server
By default, Spring Security enables CSRF checks, which will block client registrations (`POST /eureka/apps`). We must disable CSRF for registration endpoints:

```java
package com.ftgo.eureka.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;

@Configuration
public class WebSecurityConfig extends WebSecurityConfigurerAdapter {

    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .csrf()
            .ignoringAntMatchers("/eureka/**") // Disable CSRF for registration endpoints
            .and()
            .authorizeRequests()
            .anyRequest().authenticated()
            .and()
            .httpBasic();
    }
}
```

### 5.12.3 Configure Client Mappings to use Credentials
Update client default zones in `bootstrap.yml` configuration (e.g. inside `order-service-dev.yml` in config repository) to pass credentials inside the service URL:

```yaml
eureka:
  client:
    serviceUrl:
      defaultZone: http://eureka-admin:SuperSecureEurekaPassword123@localhost:8070/eureka/
```

With this configured, clients can register securely, and unauthorized requests to the Eureka Dashboard (port `8070`) are blocked.

---
## Chapter Summary

* Traditional **DNS and static load balancers** fail in dynamic cloud environments due to static configurations and single-point-of-failure constraints.
* Dynamic **service discovery** coordinates service registration, lookups, information sharing, and health heartbeats.
* **Client-side load balancing** improves efficiency by caching instance locations locally on the consumer client, eliminating network lookups for every call.
* Standalone **Eureka Servers** manage registrations and display active instances via the Eureka Dashboard.
* Eureka clients register their locations using **`preferIpAddress: true`** to resolve address lookup problems in container environments.
* Interservice communication is implemented using the low-level **`DiscoveryClient`** API, a load-balanced **`RestTemplate`**, or a declarative **OpenFeign** proxy client.
* Modern client-side load balancing uses **Spring Cloud LoadBalancer** configured with **Zone-Preference Routing** to prioritize routing to instances inside the same availability zone.
* Service registry high-availability is achieved by clustering **Eureka Servers** as peers that replicate registration details mutually in a peer-to-peer network.
* **Self-Preservation Mode** prevents Eureka from evicting healthy services during transient network splits, while heartbeat and lease renewal metrics are tuned to match environment stability.
* OpenFeign clients automate trace metadata propagation by integrating custom **`RequestInterceptor`** beans to inject correlation IDs into downstream requests dynamically.

