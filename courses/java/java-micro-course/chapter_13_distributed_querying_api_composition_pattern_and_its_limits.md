# Chapter 13: Distributed Querying: API Composition Pattern & Its Limits

In a monolithic application, querying data from multiple tables is simple. Developers can write a single SQL query with joins to retrieve and filter data across the entire database. In a microservices architecture, however, each service has its own database. Standard SQL joins across databases are impossible, requiring applications to join data across service boundaries.

This chapter covers the technical implementation of the **API Composition pattern** for distributed querying. We will analyze the roles of the **API Composer** and **Provider Services**, and examine the architectural options of executing the composer inside clients, API gateways, or standalone query services. We will compare sequential synchronous calls with parallel reactive calls using Java `CompletableFuture`, and examine the limitations of the API Composition pattern, including network overhead, reduced system availability, memory consumption under filtering/sorting operations, and eventual consistency data anomalies.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain why standard SQL joins fail in a microservices environment.
2. Formulate monolithic SQL queries and contrast them with microservices distributed queries.
3. Outline the architecture of the **API Composition pattern** and its participants.
4. Compare the design trade-offs of client-side, API gateway, and standalone composers.
5. Implement propagation of security tokens (JWT) to downstream microservices during composition.
6. Design and configure custom thread pools in Spring Boot for query concurrency.
7. Implement a resilient reactive API Composer in Java using `CompletableFuture` with fallbacks and timeout handling.
8. Calculate how parallel calls minimize query latency.
9. Calculate how distributed querying reduces overall system availability.
10. Explain the "nested-loop join" filtering limitation of API composition.
11. Analyze the performance, memory, and consistency limits of the API Composition pattern.

---

## 13.1 Monolithic Joins vs. Microservices Distributed Querying

In a monolithic application, all tables reside within a single relational database schema. If we want to retrieve the details of an order, including the customer's name, the items ordered, the preparation status, and the delivery courier's location, we can write a single SQL query that joins the respective tables:

```sql
SELECT 
    o.id AS order_id,
    o.state AS order_state,
    o.total_price AS order_total,
    c.name AS consumer_name,
    c.phone AS consumer_phone,
    t.prep_status AS ticket_preparation_status,
    t.estimated_ready_time AS ready_time,
    d.courier_id AS courier_id,
    d.status AS delivery_status,
    d.current_latitude AS lat,
    d.current_longitude AS lon
FROM orders o
INNER JOIN consumers c ON o.consumer_id = c.id
LEFT OUTER JOIN tickets t ON o.id = t.order_id
LEFT OUTER JOIN deliveries d ON o.id = d.order_id
WHERE o.id = 1001;
```

The database query engine executes this efficiently by parsing the SQL, analyzing B-Tree indexes, performing index scans or hash joins, and returning a single, consolidated result set in a single database transaction.

### The Microservices Challenge
In a database-per-service microservices architecture, these tables are partitioned into separate databases managed by entirely different services:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//33d4c296-e4fe-4cd9-83b8-3bdbb6532fce/markdown_1/imgs/img_in_image_box_183_102_910_592.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A36Z%2F-1%2F%2Fcd7648f3cee312c205c303717e0df25db1ba9d94e72a875a12d06df4909d7598" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 7.1: The findOrder() operation is invoked by a FTGO frontend module and returns the details of an Order.</div>

Because SQL queries cannot cross database boundaries and network nodes, a standard SQL join is physically impossible. To retrieve this data, the application must perform a distributed query.

The primary pattern used to solve this is the **API Composition pattern**. An **API Composer** acts as an aggregator, receiving a client query, executing queries against the downstream **Provider Services**, and merging the responses in-memory:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//33d4c296-e4fe-4cd9-83b8-3bdbb6532fce/markdown_2/imgs/img_in_image_box_200_285_927_673.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A38Z%2F-1%2F%2F1e555dc369e35e2da6b53658c0eace988fcabf949b82481ea9ee76b5bdf81d78" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 7.2: The API composition pattern consists of an API composer and two or more provider services. The API composer implements a query by querying the providers and combining the results.</div>

---

## 13.2 Distributed Join Architecture: Downstream APIs

To implement `findOrder(orderId)`, the API Composer interacts with four provider services:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//33d4c296-e4fe-4cd9-83b8-3bdbb6532fce/markdown_3/imgs/img_in_image_box_182_455_928_882.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A39Z%2F-1%2F%2F51d6ed5ab0267e5765a9af59707bae7141b5c2a206425a0c51b4a0de9d50a731" alt="Image" width="70%" /></div>
<div style="text-align: center;">Figure 7.3: Implementing findOrder() using the API composition pattern.</div>

Each provider service exposes a REST API returning a specific subset of data by `orderId`:

### 1. Order Service API
* **Endpoint**: `GET /orders/{orderId}`
* **Response Payload JSON**:
```json
{
  "orderId": "1001",
  "consumerId": "9982",
  "restaurantId": "5504",
  "state": "APPROVED",
  "totalPrice": 25.50,
  "lineItems": [
    { "menuItemId": "pizza_01", "name": "Cheese Pizza", "price": 12.00, "quantity": 2 },
    { "menuItemId": "soda_01", "name": "Cola", "price": 1.50, "quantity": 1 }
  ]
}
```

### 2. Kitchen Service API
* **Endpoint**: `GET /tickets/order/{orderId}`
* **Response Payload JSON**:
```json
{
  "ticketId": "ticket_7761",
  "orderId": "1001",
  "preparationStatus": "READY_FOR_PICKUP",
  "estimatedReadyTime": "2026-06-27T09:30:00Z"
}
```

### 3. Delivery Service API
* **Endpoint**: `GET /deliveries/order/{orderId}`
* **Response Payload JSON**:
```json
{
  "deliveryId": "del_8891",
  "orderId": "1001",
  "status": "COURIER_PICKING_UP",
  "courierId": "courier_john",
  "latitude": 37.7749,
  "longitude": -122.4194
}
```

### 4. Accounting Service API
* **Endpoint**: `GET /payments/order/{orderId}`
* **Response Payload JSON**:
```json
{
  "paymentId": "pay_5561",
  "orderId": "1001",
  "paymentStatus": "AUTHORIZED",
  "cardType": "VISA",
  "lastFourDigits": "4321"
}
```

The API Composer's job is to orchestrate calls to these four REST endpoints, deserialize the JSON responses, and aggregate them into a single response.

---

## 13.3 Architectural Placement Options of the API Composer

The API Composer can be located in three different places in the architecture, each having specific design implications:

### Option 1: Client-Side Composition
The client application itself (e.g. a React single-page application or a mobile app) queries the provider services directly:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//33d4c296-e4fe-4cd9-83b8-3bdbb6532fce/markdown_4/imgs/img_in_image_box_202_445_694_812.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A40Z%2F-1%2F%2F8636d8cd7f3b567fe879ae8426882c42fba970e9f16e735777c9752d1a2b872f" alt="Image" width="46%" /></div>
<div style="text-align: center;">Figure 7.4: Implementing API composition in a client. The client queries the provider services to retrieve the data.</div>

* **Use Case**: Simple query orchestration within internal high-speed corporate LAN networks.
* **Design Drawback**: Public web browsers or mobile devices must download large volumes of JSON data across public networks. This creates high network latency, consumes significant bandwidth, and exposes internal microservices endpoints publicly, increasing security risks.

### Option 2: API Gateway Composition
The API Gateway acts as the API Composer, exposing a single unified public endpoint (e.g. `GET /orders/{orderId}/details`) and executing parallel downstream queries:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a1562d3d-086e-426e-b2cd-c1b9b394647a/markdown_0/imgs/img_in_image_box_180_107_684_1204.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A35Z%2F-1%2F%2Feadb8fa27f020957e2772608e373eefc91a6f05be49f7da7edc216a9f969a73f" alt="Image" width="47%" /></div>
<div style="text-align: center;">Figure 7.5: Implementing API composition in the API gateway. The API queries the provider services to retrieve the data, combines the results, and returns a response to the client.</div>

* **Use Case**: Standard public-facing aggregate queries.
* **Design Drawback**: Coupling aggregate query logic into the gateway makes deployment and development harder. It is also challenging to scale because CPU-intensive aggregation tasks can slow down core gateway functions like authentication, rate limiting, and request routing. A common variant is the **Backends for Frontends (BFF)** pattern, where a dedicated API Gateway is deployed for each client platform (web, mobile, third-party API) to handle custom composition.

### Option 3: Standalone Composition Service
The API Composer is implemented as an independent microservice within the service mesh:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a1562d3d-086e-426e-b2cd-c1b9b394647a/markdown_0/imgs/img_in_image_box_180_107_684_1204.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A35Z%2F-1%2F%2Feadb8fa27f020957e2772608e373eefc91a6f05be49f7da7edc216a9f969a73f" alt="Image" width="47%" /></div>
<div style="text-align: center;">Figure 7.6: Implement a query operation used by multiple clients and services as a standalone service.</div>

* **Use Case**: Complex query operations, or query aggregations shared across multiple internal microservices.
* **Design Benefit**: Decouples aggregation from both public routing layers and specific clients, allowing the service to scale independently when query traffic rises.

---

## 13.4 Security Context and Token Propagation

In a secure microservices architecture, queries must be authorized. When the client invokes the API Composer, it provides an identity token, typically a **JSON Web Token (JWT)**, in the `Authorization` header.

The API Composer must propagate this security context to downstream provider services to ensure data authorization rules are applied:

```
[ Client ] --( JWT Token )--> [ API Composer ]
                                    |
            +-----------------------+-----------------------+
            | (JWT Token)           | (JWT Token)           | (JWT Token)
            v                       v                       v
     [ Order Service ]       [ Kitchen Service ]     [ Delivery Service ]
```

### Propagation Configuration in Spring
Downstream REST templates or WebClients must intercept outgoing network requests and inject the authenticated user's JWT:

```java
package com.ftgo.order.query.security;

import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.security.core.context.SecurityContextHolder;
import java.io.IOException;

public class JwtTokenPropagationInterceptor implements ClientHttpRequestInterceptor {

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body, ClientHttpRequestExecution execution) 
            throws IOException {
        
        // Extract authenticated security context token from thread-local holder
        Object credentials = SecurityContextHolder.getContext().getAuthentication().getCredentials();
        
        if (credentials instanceof String) {
            String jwtToken = (String) credentials;
            // Inject JWT token into outgoing HTTP headers
            request.getHeaders().add("Authorization", "Bearer " + jwtToken);
        }
        
        return execution.execute(request, body);
    }
}
```

---

## 13.5 Latency Calculations: Sequential vs. Parallel Queries

The execution model of the API Composer determines the latency of query aggregation.

### 1. Sequential Execution Latency
If the API Composer executes HTTP queries sequentially, the execution thread blocks while waiting for each response. The total latency ($T_{total}$) is the sum of the latencies of all downstream calls plus network overhead:

$$T_{total} = T_{order} + T_{kitchen} + T_{delivery} + T_{accounting} + \sum \text{network\_overhead}$$

Let's assume the average latency for each downstream service:
* $T_{order} = 220\text{ms}$
* $T_{kitchen} = 150\text{ms}$
* $T_{delivery} = 180\text{ms}$
* $T_{accounting} = 100\text{ms}$

Calculating the sequential latency yields:

$$T_{total} = 220\text{ms} + 150\text{ms} + 180\text{ms} + 100\text{ms} = 650\text{ms}$$

### 2. Parallel Execution Latency
If the API Composer executes queries in parallel using asynchronous, non-blocking threads, the requests run concurrently. The total latency is determined by the slowest downstream call plus the in-memory aggregation overhead:

$$T_{total} = \max(T_{order}, T_{kitchen}, T_{delivery}, T_{accounting}) + T_{aggregation}$$

Using the same downstream service latencies:

$$T_{total} = \max(220\text{ms}, 150\text{ms}, 180\text{ms}, 100\text{ms}) + 5\text{ms} = 225\text{ms}$$

Parallel execution reduces query latency by $65.4\%$, providing a much faster response for clients.

---

## 13.6 System Availability Mathematics in API Composition

A major drawback of the API Composition pattern is that it reduces system availability. In a distributed query, the composer depends on multiple downstream services. If any of the required services is down, the query fails or returns incomplete results.

Mathematically, the availability of a composited query endpoint ($A_{query}$) is the product of the availability of all participants:

$$A_{query} = A_{composer} \times A_{order} \times A_{kitchen} \times A_{delivery} \times A_{accounting}$$

Assume each microservice has a standard SLA availability of $99.5\%$ ($0.995$):
* $A_{composer} = 0.995$
* $A_{order} = 0.995$
* $A_{kitchen} = 0.995$
* $A_{delivery} = 0.995$
* $A_{accounting} = 0.995$

We calculate the total availability as:

$$A_{query} = 0.995 \times 0.995 \times 0.995 \times 0.995 \times 0.995 = 0.995^5 \approx 0.9752 = 97.52\%$$

The math shows that as you add more downstream services, the query endpoint's availability drops. An availability of $97.52\%$ translates to roughly **9 days of downtime per year**, compared to **1.8 days of downtime per year** for an individual service with $99.5\%$ availability.

---

## 13.7 Thread Pool Starvation and Executor Configuration

By default, Java's `CompletableFuture` runs asynchronous tasks using the JVM's shared `ForkJoinPool.commonPool()`. 

In a high-throughput production environment, this can lead to **Thread Pool Starvation**. If the common pool's threads are blocked waiting for slow HTTP responses from downstream microservices, other unrelated asynchronous tasks in the JVM will queue up or fail.

To prevent this, you should configure a dedicated, isolated thread pool (Executor) for your API Composer:

```java
package com.ftgo.order.query.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import java.util.concurrent.Executor;

@Configuration
public class ComposerExecutorConfig {

    @Bean(name = "composerExecutor")
    public Executor composerExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        // Core pool size set to handle concurrent query requests
        executor.setCorePoolSize(20);
        // Maximum pool size limit under peak load
        executor.setMaxPoolSize(100);
        // Queue capacity for pending requests before rejecting
        executor.setQueueCapacity(500);
        executor.setThreadNamePrefix("composer-query-pool-");
        // Keep-alive time for idle threads
        executor.setKeepAliveSeconds(60);
        executor.initialize();
        return executor;
    }
}
```

---

## 13.8 Resiliency and Fallback Configurations

If a downstream service is down or slow, the API Composer should handle the failure gracefully. It can do this using timeouts and fallback defaults, allowing it to return partial data instead of failing the entire request.

For example, if the **Delivery Service** is down, the API Composer can still return the order details and preparation status, but set the delivery status to `DELIVERY_INFO_TEMPORARILY_UNAVAILABLE`.

We configure this using `CompletableFuture.handle()` or `CompletableFuture.exceptionally()`:

```
                       +-------------------+
                       |    API Composer   |
                       +---------+---------+
                                 |
           +---------------------+---------------------+
           |                     |                     |
           v                     v                     v
   [ Order Service ]     [ Kitchen Service ]   [ Delivery Service ]
   (Returns Data)        (Returns Data)        (Fails / Timeout)
           |                     |                     |
           v                     v                     v
     "APPROVED"            "READY_FOR_PICKUP"      [ Fallback Handler ]
           |                     |                     |
           +---------------------+---------------------+
                                 |
                                 v
                     Unified Response Aggregate:
              Delivery Status set to "UNAVAILABLE"
```

---

## 13.9 Complete Java API Composer Implementation

Let's write a complete Spring Boot implementation for the `findOrder()` query composer. This includes custom models, WebClient configuration, thread pool execution, timeouts, and fallback logic.

### 1. Downstream Aggregate Response Models

```java
package com.ftgo.order.query.dto;

import java.time.LocalDateTime;

public class OrderInfo {
    private String orderId;
    private String state;
    private Double totalPrice;

    public OrderInfo() {}
    public OrderInfo(String orderId, String state, Double totalPrice) {
        this.orderId = orderId;
        this.state = state;
        this.totalPrice = totalPrice;
    }

    public String getOrderId() { return orderId; }
    public void setOrderId(String orderId) { this.orderId = orderId; }
    public String getState() { return state; }
    public void setState(String state) { this.state = state; }
    public Double getTotalPrice() { return totalPrice; }
    public void setTotalPrice(Double totalPrice) { this.totalPrice = totalPrice; }
}
```

```java
package com.ftgo.order.query.dto;

import java.time.LocalDateTime;

public class TicketInfo {
    private String ticketId;
    private String preparationStatus;
    private LocalDateTime estimatedReadyTime;

    public TicketInfo() {}
    public TicketInfo(String ticketId, String preparationStatus, LocalDateTime estimatedReadyTime) {
        this.ticketId = ticketId;
        this.preparationStatus = preparationStatus;
        this.estimatedReadyTime = estimatedReadyTime;
    }

    public String getTicketId() { return ticketId; }
    public void setTicketId(String ticketId) { this.ticketId = ticketId; }
    public String getPreparationStatus() { return preparationStatus; }
    public void setPreparationStatus(String preparationStatus) { this.preparationStatus = preparationStatus; }
    public LocalDateTime getEstimatedReadyTime() { return estimatedReadyTime; }
    public void setEstimatedReadyTime(LocalDateTime estimatedReadyTime) { this.estimatedReadyTime = estimatedReadyTime; }
}
```

```java
package com.ftgo.order.query.dto;

public class DeliveryInfo {
    private String deliveryId;
    private String status;
    private String courierId;

    public DeliveryInfo() {}
    public DeliveryInfo(String deliveryId, String status, String courierId) {
        this.deliveryId = deliveryId;
        this.status = status;
        this.courierId = courierId;
    }

    public String getDeliveryId() { return deliveryId; }
    public void setDeliveryId(String deliveryId) { this.deliveryId = deliveryId; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getCourierId() { return courierId; }
    public void setCourierId(String courierId) { this.courierId = courierId; }
}
```

### 2. Consolidated Aggregated View Model

```java
package com.ftgo.order.query.dto;

public class ConsolidatedOrderDetails {
    private String orderId;
    private OrderInfo order;
    private TicketInfo ticket;
    private DeliveryInfo delivery;

    public ConsolidatedOrderDetails(String orderId, OrderInfo order, TicketInfo ticket, DeliveryInfo delivery) {
        this.orderId = orderId;
        this.order = order;
        this.ticket = ticket;
        this.delivery = delivery;
    }

    public String getOrderId() { return orderId; }
    public OrderInfo getOrder() { return order; }
    public TicketInfo getTicket() { return ticket; }
    public DeliveryInfo getDelivery() { return delivery; }
}
```

### 3. Downstream Client Service Implementation

```java
package com.ftgo.order.query.client;

import com.ftgo.order.query.dto.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import java.time.LocalDateTime;

@Component
public class DownstreamServiceClient {

    @Autowired
    private RestTemplate restTemplate;

    public OrderInfo fetchOrderInfo(String orderId) {
        String url = "http://order-service/orders/" + orderId;
        return restTemplate.getForObject(url, OrderInfo.class);
    }

    public TicketInfo fetchTicketInfo(String orderId) {
        String url = "http://kitchen-service/tickets/order/" + orderId;
        return restTemplate.getForObject(url, TicketInfo.class);
    }

    public DeliveryInfo fetchDeliveryInfo(String orderId) {
        String url = "http://delivery-service/deliveries/order/" + orderId;
        return restTemplate.getForObject(url, DeliveryInfo.class);
    }
}
```

### 4. The API Composer implementation with Parallel execution, Timeouts, and Fallbacks

```java
package com.ftgo.order.query.composer;

import com.ftgo.order.query.client.DownstreamServiceClient;
import com.ftgo.order.query.dto.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.concurrent.*;

@Service
public class OrderApiComposer {

    private static final Logger logger = LoggerFactory.LoggerFactory.getLogger(OrderApiComposer.class);

    @Autowired
    private DownstreamServiceClient client;

    @Autowired
    @Qualifier("composerExecutor")
    private Executor executor;

    public ConsolidatedOrderDetails composeOrderDetails(String orderId) {
        logger.info("Starting API composition query for order ID: {}", orderId);

        // 1. Fetch Order Info (Primary critical service call)
        CompletableFuture<OrderInfo> orderFuture = CompletableFuture.supplyAsync(
            () -> client.fetchOrderInfo(orderId), executor
        ).orTimeout(1000, TimeUnit.MILLISECONDS) // Apply a 1-second timeout
         .exceptionally(ex -> {
             logger.error("Failed to retrieve critical order details info. Order ID: {}", orderId, ex);
             // Fail fast if the primary order details are missing
             throw new CompletionException(new IllegalStateException("Critical Order Service unavailable!", ex));
         });

        // 2. Fetch Ticket Info (Kitchen Service) with fallback
        CompletableFuture<TicketInfo> ticketFuture = CompletableFuture.supplyAsync(
            () -> client.fetchTicketInfo(orderId), executor
        ).orTimeout(800, TimeUnit.MILLISECONDS) // Apply an 800ms timeout
         .handle((ticket, ex) -> {
             if (ex != null) {
                 logger.warn("Kitchen Service call failed/timed out. Applying fallback response for Order ID: {}", orderId);
                 // Fallback: Return empty/unconfirmed ticket status details
                 return new TicketInfo("N/A", "INFORMATION_UNAVAILABLE", LocalDateTime.now());
             }
             return ticket;
         });

        // 3. Fetch Delivery Info (Delivery Service) with fallback
        CompletableFuture<DeliveryInfo> deliveryFuture = CompletableFuture.supplyAsync(
            () -> client.fetchDeliveryInfo(orderId), executor
        ).orTimeout(800, TimeUnit.MILLISECONDS) // Apply an 800ms timeout
         .handle((delivery, ex) -> {
             if (ex != null) {
                 logger.warn("Delivery Service call failed/timed out. Applying fallback response for Order ID: {}", orderId);
                 // Fallback: Return courier offline status details
                 return new DeliveryInfo("N/A", "COURIER_INFO_UNAVAILABLE", "UNASSIGNED");
             }
             return delivery;
         });

        // 4. Wait for all threads to complete
        CompletableFuture<Void> aggregationFuture = CompletableFuture.allOf(orderFuture, ticketFuture, deliveryFuture);
        
        try {
            aggregationFuture.join(); // Blocks parent thread until parallel futures complete
            
            OrderInfo order = orderFuture.join();
            TicketInfo ticket = ticketFuture.join();
            DeliveryInfo delivery = deliveryFuture.join();

            logger.info("Successfully completed API composition aggregation for Order ID: {}", orderId);
            return new ConsolidatedOrderDetails(orderId, order, ticket, delivery);
            
        } catch (CompletionException ex) {
            logger.error("API Composition failed because a critical service call was lost. Order ID: {}", orderId, ex);
            throw new IllegalStateException("API composition failed due to downstream service outage", ex);
        }
    }
}
```

---

## 13.11 Implementing Resilient Downstream Fallbacks in Java

When querying provider services, a single transient failure or network timeout should not cause the entire distributed query to crash. 

To maintain high availability, the API Composer can use **Fallback Providers**. If a downstream provider service (like Delivery Service) fails or times out, the composer intercepts the error and returns a cached or degraded static fallback payload:

```java
package com.ftgo.order.composition.fallback;

import com.ftgo.order.composition.DeliveryInfo;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import java.time.LocalDateTime;

@Component
public class DeliveryServiceFallbackProvider {

    private static final Logger logger = LoggerFactory.getLogger(DeliveryServiceFallbackProvider.class);

    public DeliveryInfo getFallbackDelivery(Long orderId, Throwable exception) {
        // Intercept failure and log the anomaly details
        logger.warn("Delivery Service query failed for Order ID: {}. Triggering fallback. Reason: {}", 
                orderId, exception.getMessage());

        // Return a degraded, static fallback payload to maintain partial availability
        DeliveryInfo fallback = new DeliveryInfo();
        fallback.setOrderId(orderId);
        fallback.setStatus("STATUS_UNAVAILABLE");
        fallback.setEstimatedDeliveryTime(LocalDateTime.now().plusHours(1));
        fallback.setCourierName("System Default Courier");
        
        return fallback;
    }
}
```

---

## 13.12 API Composition Cache Warming and In-Memory Data Prefetching

Querying downstream databases on every API request can saturate provider databases. To optimize performance, we implement a **Redis-based Cache Warming** pipeline. 

As downstream entities are updated, event listeners pre-fetch and warm cache structures inside the API Composer, allowing it to resolve distributed queries from memory:

```java
package com.ftgo.order.composition.cache;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;

@Component
public class APICompositionCacheWarmer {

    @Autowired
    private StringRedisTemplate redisTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    public void prefetchAndWarm(String orderId, Object dataPayload) {
        try {
            String cacheKey = "cache:composition:orders:" + orderId;
            String jsonPayload = objectMapper.writeValueAsString(dataPayload);
            
            // Warm cache with a 10-minute time-to-live (TTL) expiration window
            redisTemplate.opsForValue().set(cacheKey, jsonPayload, Duration.ofMinutes(10));
            
            System.out.println("API Composition cache warmed successfully for key: " + cacheKey);
        } catch (Exception ex) {
            // Fail silently to prevent cache issues from blocking order validation
            System.err.println("API Composition cache warming failed: " + ex.getMessage());
        }
    }
}
```

---

## 13.13 Distributed Tracing: OpenTelemetry Context Propagation

To trace distributed query performance across multiple services, the API Composer must inject trace context headers (`traceparent`, `tracestate`) into outgoing HTTP queries:

```java
package com.ftgo.order.composition.telemetry;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.propagation.TextMapPropagator;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Component
public class OpenTelemetryTracePropagationInterceptor implements ClientHttpRequestInterceptor {

    @Autowired
    private OpenTelemetry openTelemetry;

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body, ClientHttpRequestExecution execution) 
            throws IOException {
        
        Context currentContext = Context.current();
        TextMapPropagator propagator = openTelemetry.getPropagators().getTextMapPropagator();
        
        // Inject current span context into outgoing request headers
        propagator.inject(currentContext, request, (carrier, key, value) -> {
            if (carrier != null) {
                carrier.getHeaders().add(key, value);
            }
        });
        
        return execution.execute(request, body);
    }
}
```

---

## 13.14 Protecting Downstream Providers: Client-Side Rate Limiting

Because each incoming composition query translates to multiple downstream HTTP requests, the API Composer can quickly overload provider databases. 

We configure a **Bucket4j-based Rate Limiter** to limit incoming queries and protect downstream capacity:

```java
package com.ftgo.order.composition.ratelimit;

import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.Refill;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import javax.servlet.*;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.time.Duration;

@Component
public class APICompositionRateLimitFilter implements Filter {

    // Allow 100 requests per minute with a greedy refill rate of 100 tokens
    private final Bucket bucket = Bucket.builder()
            .addLimit(Bandwidth.classic(100, Refill.greedy(100, Duration.ofMinutes(1))))
            .build();

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain) 
            throws IOException, ServletException {
        
        if (bucket.tryConsume(1)) {
            // Token acquired, proceed with query execution
            chain.doFilter(request, response);
        } else {
            // Bucket empty: Reject call and return HTTP 429 Too Many Requests
            HttpServletResponse httpResponse = (HttpServletResponse) response;
            httpResponse.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
            httpResponse.setContentType("text/plain");
            httpResponse.getWriter().write("API Composition query rate limit exceeded! Try again later.");
        }
    }
}
```

---



## 13.15 Architectural Limits and Drawbacks of API Composition

While the API Composition pattern is a good default pattern for distributed joins, it has major scalability, performance, and memory limits:

### 1. High Network Traffic and Aggregator CPU Load
Each query triggers multiple RPC calls over the network, increasing traffic, resource usage, and load on the provider databases.

### 2. In-Memory "Nested-Loop Joins" under Filtering and Sorting
The most severe limitation of API composition is performing joins on large datasets where provider services do not store the attributes used for filtering or sorting.

Consider the order history search query: *"find all orders for customer John where order status is pending, prepared by a restaurant named Pizza Palace."*
* Only **Order Service** and **Kitchen Service** store details about menu items and restaurant links.
* **Delivery Service** and **Accounting Service** only reference order records by ID, without menu item strings or restaurant names.
* If the composer attempts to perform a join, it cannot pass the restaurant search keywords to Delivery or Accounting. It is forced to download John's entire history (thousands of order rows) from those services, downloading massive arrays of records across the network to join and filter them in memory:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//a1562d3d-086e-426e-b2cd-c1b9b394647a/markdown_4/imgs/img_in_image_box_112_232_907_760.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A40Z%2F-1%2F%2F5e97a02b2f59115786a138f0184387173ff3aa1512d722c665fce000505a8621" alt="Image" width="74%" /></div>
<div style="text-align: center;">Figure 7.7: API composition can't efficiently retrieve a consumer's orders, because some providers, such as Delivery Service, don't store the attributes used for filtering.</div>

This forces developers to implement complex, custom query processing execution engines inside service memories rather than focusing on business value.

### 3. Data Consistency Issues
Because the provider databases are updated at different times (eventual consistency), the API Composer might read inconsistent data during a query. 
* *Example*: The composer could read an order state as `APPROVED` from the Order Service, but read a ticket state as `CANCELLED` from the Kitchen Service if it queries the services while a rollback transaction is running.

To solve these limitations for complex queries, applications must use the **CQRS (Command Query Responsibility Segregation) pattern**.

---

## 13.16 Summary of API Composition and Resilient Query Routing


This table summarizes the elements and configurations used to implement API composition:

| Composition Element | Config / Term | Main Implementation Target | Layer Location |
| :--- | :--- | :--- | :--- |
| **API Composer** | Aggregator Service | Coordinates requests across provider databases. | Application Layer |
| **Provider Service**| Delivery Service | Downstream database storing raw entity fields. | Infrastructure |
| **Parallel Executor**| `composerExecutor` | ThreadPoolTaskExecutor running calls in parallel. | Configuration |
| **Timeout Boundary**| `orTimeout(800)` | Prevents slow responses from blocking threads. | Future Pipeline |
| **Fallback Method** | `handle()` | Returns degraded default payloads on timeout. | Future Pipeline |
| **Cache Warmer** | Redis prefetching | Warms memory keys to eliminate database reads. | Integration |
| **JWT Interceptor** | Token relay | Injector propagating credentials downstream. | Security Layer |

---

## Chapter Summary

* In a microservices architecture, standard SQL joins cannot span databases, requiring the application to perform distributed joins.
* Under the **API Composition pattern**, an **API Composer** queries downstream **Provider Services** and aggregates their responses in-memory before returning the result.
* The API composer can reside in the client application, the API Gateway, or a standalone query service.
* To minimize latency, the composer should execute calls in parallel (e.g. using Java `CompletableFuture`) rather than sequentially.
* Security context propagation must be configured using interceptors to pass JWT credentials to downstream services.
* Isolating execution threads in dedicated thread pools prevents ForkJoinPool starvation.
* The API Composition pattern has several drawbacks:
  * **Overhead**: Increased network traffic and resource load on provider services.
  * **Reduced Availability**: The query endpoint's availability is the product of the availability of all involved services.
  * **Memory Consumption**: Large datasets cannot be joined efficiently in-memory.
  * **Consistency**: The composer can retrieve inconsistent data due to eventual consistency across databases.
