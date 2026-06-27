# Chapter 14: Distributed Querying: CQRS Pattern

In a microservices architecture, implementing complex queries that span multiple services is challenging. While the API Composition pattern is simple, it suffers from high network overhead, reduced system availability, and performance limits when joining large datasets in memory. To solve these limitations, we use the **Command Query Responsibility Segregation (CQRS)** pattern.

This chapter covers the technical architecture and implementation of the CQRS pattern. We will analyze the separation of concerns between the **Command Side** and the **Query Side**, explore the design of standalone query-side services, and map out denormalized read database models in NoSQL databases (such as MongoDB and DynamoDB). We will evaluate the eventual consistency replication lag, write event handlers that process events to maintain views, implement **Idempotent Event Handlers** using event tracking tables, and write a complete Spring Boot and Spring Data MongoDB implementation of a CQRS view service.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the architectural split between the Command Side and the Query Side in CQRS.
2. Compare the trade-offs of the API Composition and CQRS patterns across multiple operational dimensions.
3. Design standalone query services that subscribe to events from multiple services.
4. Define read schemas, partition keys, sort keys, and global secondary indexes in NoSQL databases.
5. Implement a Spring MVC interceptor to automatically mitigate replication lag using token headers.
6. Design idempotent event handlers with conditional update expressions.
7. Build a functional, production-ready CQRS view service in Java using Spring Data MongoDB, complete with search keywords and paginated endpoints.
8. Configure Kafka event consumer routes and message routing configurations in Spring.
9. Write a programmatic integration test using Testcontainers to verify event handler writes and read view updates.
10. Implement a DynamoDB Data Access Object (DAO) using AWS SDK v2 for paginated, index-driven queries.
11. Build an Elasticsearch CQRS search query service using the Java high-level REST client.
12. Outline methods for building and rebuilding views using event archiving and incremental snapshots.

---

## 14.1 CQRS separates Commands from Queries

Command Query Responsibility Segregation (CQRS) splits a service's persistent data model and behavior modules into two parts:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//29114d04-094b-48b3-b8e9-2c0a4d2f4619/markdown_2/imgs/img_in_image_box_200_99_931_628.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A03Z%2F-1%2F%2F0bb690a9f19916b3932b7d36aba03feb38d1fe4a9018231602eb9f6929b2d3c6" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 7.8: On the left is the non-CQRS version of the service, and on the right is the CQRS version. CQRS restructures a service into command-side and query-side modules, which have separate databases.</div>

### The Command Side (Writes)
* **Responsibility**: Handles CUD operations (HTTP POST, PUT, DELETE).
* **Focus**: Executes business logic, enforces entity invariants, and manages transactions.
* **Storage**: A write-optimized database (relational or event store).
* **Behavior**: Publishes domain events (using Outbox or Event Sourcing) whenever the state changes.

### The Query Side (Reads)
* **Responsibility**: Handles query operations (HTTP GET).
* **Focus**: Fast read operations, pagination, filtering, and text search.
* **Storage**: A read-optimized, denormalized database (e.g. MongoDB, Elasticsearch, DynamoDB).
* **Behavior**: Subscribes to the domain events emitted by the command side and updates the read replicas.

---

## 14.2 Architecture of Standalone Query Services

For queries that require data owned by multiple microservices (such as showing a consumer's complete order history), we implement a standalone query service. 

A query service has an API consisting of only query operations—no command operations. It implements these operations by querying a view database that it keeps up-to-date by subscribing to events published by one or more other services.

Consider the **Order History Service**:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//29114d04-094b-48b3-b8e9-2c0a4d2f4619/markdown_3/imgs/img_in_image_box_183_283_826_760.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A03Z%2F-1%2F%2F7cddb3a1c18b4c5e7ee4ba626c1b476347247dcf3a42a3bea80f5a55b28cfbac" alt="Image" width="60%" /></div>
<div style="text-align: center;">Figure 7.9: The design of Order History Service, which is a query-side service. It implements the findOrderHistory() query operation by querying a database, which it maintains by subscribing to events published by multiple other services.</div>

This service subscribes to:
* `Order Service` events (e.g., `OrderCreated`, `OrderAuthorized`, `OrderCancelled`) to track basic order status.
* `Delivery Service` events (e.g., `DeliveryPickedUp`, `DeliveryDelivered`) to track delivery status and estimate delivery times.
* `Accounting Service` events (e.g., `PaymentAuthorized`) to track payment status.

---

## 14.3 Tactical View Module Design

A CQRS view module consists of a view database and three submodules:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9b075569-4449-4853-98f9-a5ffdc393dc0/markdown_1/imgs/img_in_image_box_202_105_646_471.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A27Z%2F-1%2F%2F2f9f48aef644ebe7115231870fae21c2068799fd189b478cd464cd14989f3342" alt="Image" width="41%" /></div>
<div style="text-align: center;">Figure 7.10: The design of a CQRS view module. Event handlers update the view database, which is queried by the Query API module.</div>

1. **Query API**: Implements public REST or GraphQL query endpoints.
2. **Event Handlers**: Subscribes to events from the broker and updates the view database.
3. **Data Access (DAO)**: Interfaces with the view database, encapsulating query logic and updates.

### The Order History Service Structure
The concrete class modules of the Order History Service are organized as follows:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b8a411b0-2d30-4b11-93aa-6b0148cc4a3d/markdown_2/imgs/img_in_image_box_203_231_689_680.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A21Z%2F-1%2F%2F9539bc5df4e6c3eed525fa35c286360a8215d24d4a608ad42d28341c0517877d" alt="Image" width="45%" /></div>
<div style="text-align: center;">Figure 7.12: The design of OrderHistoryService. OrderHistoryEventHandlers updates the database in response to events. The OrderHistoryQuery module implements the query operations by querying the database. These two modules use the OrderHistoryDataAccess module to access the database.</div>

---

## 14.4 API Composition vs. CQRS: Architectural Comparison

| Architectural Dimension | API Composition Pattern | CQRS Pattern |
| :--- | :--- | :--- |
| **Complexity** | Low. Directly fetch data using standard REST/gRPC client calls. | High. Requires separate databases, event pipelines, and event handlers. |
| **Data Latency** | Slow. Determined by the slowest downstream provider service. | Instant. Low latency reads since the view database pre-joins data. |
| **System Availability** | Product of composer + all provider services (drops with count). | High. Reads remain available even if downstream write services are down. |
| **Database Overhead** | High. Downstream databases process joins and search queries constantly. | Low. Downstream databases only handle primary key writes. |
| **Network Overhead** | High. Many HTTP requests are made over the network. | Low. A single HTTP query is sent to the read view replica. |
| **Query Diversity** | Poor. Highly limited when filtering or sorting across services. | High. Custom databases (e.g. Elasticsearch) can be optimized for text searches. |
| **Consistency Model** | Read-time transaction consistency. | Eventual consistency (updates are processed asynchronously). |
| **Data Storage Overhead** | Zero. No data is duplicated. | High. Data is duplicated across write and read databases. |
| **Rebuilding Effort** | Zero. | High. Schema updates require batch processing archived logs. |

---

## 14.5 Handling Eventual Consistency and Replication Lag

Because updates to the read model are asynchronous, CQRS is **eventually consistent**. There is a replication lag between the write database update and the read database synchronization.

A client application that updates an aggregate (e.g. submitting an order) and then immediately queries the view might read the old state.

### Mitigation: Command-Query Event Token Verification
To prevent users from seeing stale data, we can implement an HTTP Interceptor that checks the processed event version of the read database. If the read model is behind the version returned by the command, the query blocks and polls until the read model catches up:

```
[ Client ] --( GET /consumers/orders?expectedEventId=evt_105 )--> [ ReplicationLagInterceptor ]
                                                                             |
                                             +-------------------------------+-------------------------------+
                                             | (If View Max ID < evt_105)                                    | (If View Max ID >= evt_105)
                                             v                                                               v
                                   [ Sleep & Poll Loop ]                                           [ Proceed to Controller ]
```

#### Spring Interceptor Implementation
```java
package com.ftgo.order.query.security;

import com.ftgo.order.query.document.OrderHistoryView;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@Component
public class ReplicationLagInterceptor implements HandlerInterceptor {

    @Autowired
    private MongoTemplate mongoTemplate;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        String expectedEventId = request.getHeader("X-Expected-Event-Id");
        String orderId = request.getParameter("orderId");

        if (expectedEventId != null && orderId != null) {
            int retries = 0;
            // Poll for up to 1.5 seconds (15 retries * 100ms)
            while (retries < 15) {
                Query query = new Query(Criteria.where("orderId").is(orderId)
                        .and("processedEvents.OrderAggregate").is(expectedEventId));
                
                boolean exists = mongoTemplate.exists(query, OrderHistoryView.class);
                if (exists) {
                    return true; // The read model has caught up
                }
                
                Thread.sleep(100);
                retries++;
            }
            // If the timeout is reached, return HTTP 412 Precondition Failed
            response.setStatus(412);
            response.getWriter().write("Precondition Failed: Read view is temporarily stale.");
            return false;
        }
        return true;
    }
}
```

---

## 14.6 Designing Denormalized Read Views in NoSQL

Read databases in CQRS are denormalized. Instead of mapping objects to multiple normalized tables, we store the data in a single, easily queryable document or item structure:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b8a411b0-2d30-4b11-93aa-6b0148cc4a3d/markdown_4/imgs/img_in_image_box_202_623_875_813.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A23Z%2F-1%2F%2F3e2c6c377bd89c2e42eac616200e1893e8f8170cedbd241968a835bfafa61b2d" alt="Image" width="63%" /></div>
<div style="text-align: center;">Figure 7.13: Preliminary structure of the DynamoDB OrderHistory table.</div>

### Global Secondary Indexes (GSI)
To support sorting and pagination, NoSQL databases like DynamoDB use **composite primary keys** consisting of a **partition key** (e.g., `consumerId`) and a **sort key** (e.g., `orderCreationTime`). This allows the system to query orders for a specific customer sorted by date.

Since a table can only have one primary key, we define a **Global Secondary Index (GSI)** with `consumerId` as the partition key and `orderCreationTime` as the sort key to support sorting and pagination:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//55089480-6114-46c0-9ea9-5ee4215f962b/markdown_0/imgs/img_in_image_box_182_705_907_1163.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A18Z%2F-1%2F%2F85e44e00232e922eee8d3674f9e8764ce3d84f4dfe84b9d9eeb68ddcc44bb2d5" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 7.14: The design of the OrderHistory table and index.</div>

---

## 14.7 Idempotent Event Processing

Because message brokers guarantee **at-least-once delivery**, event handlers must handle duplicate events. If a view handles duplicate events incorrectly, the read database will diverge from the write database:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//9b075569-4449-4853-98f9-a5ffdc393dc0/markdown_4/imgs/img_in_image_box_185_626_824_880.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A40Z%2F-1%2F%2Fa354dbda919e35c0f2fa38f7ab3792d97a6fadf53ca3612bf52a03e35794ef6a" alt="Image" width="60%" /></div>
<div style="text-align: center;">Figure 7.11: The DeliveryPickedUp and DeliveryDelivered events are delivered twice, which causes the order state in view to be temporarily out-of-date.</div>

### Deduplication Mechanisms
* **Deduplication Table**: In a relational database, insert the processed event's ID into a `processed_events` table within the same transaction that updates the view.
* **Attribute Version Tracking**: In NoSQL databases, record the highest-seen event ID or sequence number for each aggregate instance in the document itself. Reject updates if the incoming event's version is less than or equal to the stored version.

For example, the document records the maximum event ID processed for each aggregate type:
```json
{
  "_id": "order_1001",
  "status": "DELIVERED",
  "eventTracker": {
    "OrderEvent": "evt_00155a32",
    "DeliveryEvent": "evt_00155b99"
  }
}
```

An update is executed conditionally:
```sql
UPDATE order_history SET status = 'PICKED_UP', eventTracker.DeliveryEvent = 'evt_00155b99'
WHERE order_id = '1001' AND (eventTracker.DeliveryEvent < 'evt_00155b99' OR eventTracker.DeliveryEvent IS NULL);
```

---

## 14.8 Complete Java CQRS View Implementation

Let's write a complete Spring Boot implementation of the **Order History Service** using **Spring Data MongoDB** as the read model database.

### 1. The Core Event Payloads

```java
package com.ftgo.order.query.events;

public class OrderCreatedEvent {
    private String orderId;
    private String consumerId;
    private String restaurantName;
    private Double totalAmount;

    public OrderCreatedEvent() {}
    public OrderCreatedEvent(String orderId, String consumerId, String restaurantName, Double totalAmount) {
        this.orderId = orderId;
        this.consumerId = consumerId;
        this.restaurantName = restaurantName;
        this.totalAmount = totalAmount;
    }

    public String getOrderId() { return orderId; }
    public String getConsumerId() { return consumerId; }
    public String getRestaurantName() { return restaurantName; }
    public Double getTotalAmount() { return totalAmount; }
}
```

```java
package com.ftgo.order.query.events;

public class DeliveryPickedUpEvent {
    private String orderId;
    private String courierId;

    public DeliveryPickedUpEvent() {}
    public DeliveryPickedUpEvent(String orderId, String courierId) {
        this.orderId = orderId;
        this.courierId = courierId;
    }

    public String getOrderId() { return orderId; }
    public String getCourierId() { return courierId; }
}
```

```java
package com.ftgo.order.query.events;

public class DeliveryDeliveredEvent {
    private String orderId;

    public DeliveryDeliveredEvent() {}
    public DeliveryDeliveredEvent(String orderId) {
        this.orderId = orderId;
    }

    public String getOrderId() { return orderId; }
}
```

---

### 2. The Denormalized View Document: `OrderHistoryView.java`

```java
package com.ftgo.order.query.document;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import java.util.HashMap;
import java.util.Map;

@Document(collection = "order_history_view")
public class OrderHistoryView {

    @Id
    private String orderId;
    private String consumerId;
    private String restaurantName;
    private Double totalAmount;
    private String orderStatus;
    private String courierId;

    // Map tracking the maximum event ID processed for each aggregate type (idempotency)
    private Map<String, String> processedEvents = new HashMap<>();

    public OrderHistoryView() {}

    public OrderHistoryView(String orderId, String consumerId, String restaurantName, Double totalAmount) {
        this.orderId = orderId;
        this.consumerId = consumerId;
        this.restaurantName = restaurantName;
        this.totalAmount = totalAmount;
        this.orderStatus = "CREATED";
    }

    public void markPickedUp(String courierId) {
        this.orderStatus = "PICKED_UP";
        this.courierId = courierId;
    }

    public void markDelivered() {
        this.orderStatus = "DELIVERED";
    }

    // Getters and Setters
    public String getOrderId() { return orderId; }
    public String getConsumerId() { return consumerId; }
    public String getRestaurantName() { return restaurantName; }
    public Double getTotalAmount() { return totalAmount; }
    public String getOrderStatus() { return orderStatus; }
    public String getCourierId() { return courierId; }
    public Map<String, String> getProcessedEvents() { return processedEvents; }
    public void setProcessedEvents(Map<String, String> processedEvents) { this.processedEvents = processedEvents; }
}
```

---

### 3. Spring Data Repository: `OrderHistoryViewRepository.java`

```java
package com.ftgo.order.query.repository;

import com.ftgo.order.query.document.OrderHistoryView;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface OrderHistoryViewRepository extends MongoRepository<OrderHistoryView, String> {
    
    // Find all orders for a customer with paginated results
    Page<OrderHistoryView> findByConsumerId(String consumerId, Pageable pageable);
    
    // Find orders matching keyword searches against restaurant name with pagination
    Page<OrderHistoryView> findByConsumerIdAndRestaurantNameContainingIgnoreCase(
        String consumerId, String restaurantNameKeyword, Pageable pageable
    );
}
```

---

### 4. Idempotent Event Handlers: `OrderHistoryEventHandlers.java`

```java
package com.ftgo.order.query.handlers;

import com.ftgo.order.query.document.OrderHistoryView;
import com.ftgo.order.query.events.*;
import com.ftgo.order.query.repository.OrderHistoryViewRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class OrderHistoryEventHandlers {

    private static final Logger logger = LoggerFactory.getLogger(OrderHistoryEventHandlers.class);

    @Autowired
    private OrderHistoryViewRepository repository;

    public void handleOrderCreated(OrderCreatedEvent event, String eventId) {
        logger.info("Processing OrderCreatedEvent for order: {}", event.getOrderId());
        
        OrderHistoryView view = repository.findById(event.getOrderId())
                .orElse(new OrderHistoryView(
                    event.getOrderId(), 
                    event.getConsumerId(), 
                    event.getRestaurantName(), 
                    event.getTotalAmount()
                ));

        // Deduplication check
        if (isDuplicateEvent(view, "OrderAggregate", eventId)) {
            logger.warn("Skipping duplicate OrderCreatedEvent event: {}", eventId);
            return;
        }

        view.getProcessedEvents().put("OrderAggregate", eventId);
        repository.save(view);
    }

    public void handleDeliveryPickedUp(DeliveryPickedUpEvent event, String eventId) {
        logger.info("Processing DeliveryPickedUpEvent for order: {}", event.getOrderId());
        
        OrderHistoryView view = repository.findById(event.getOrderId())
                .orElseThrow(() -> new IllegalStateException("View not initialized for order: " + event.getOrderId()));

        // Deduplication check
        if (isDuplicateEvent(view, "DeliveryAggregate", eventId)) {
            logger.warn("Skipping duplicate DeliveryPickedUpEvent event: {}", eventId);
            return;
        }

        view.markPickedUp(event.getCourierId());
        view.getProcessedEvents().put("DeliveryAggregate", eventId);
        repository.save(view);
    }

    public void handleDeliveryDelivered(DeliveryDeliveredEvent event, String eventId) {
        logger.info("Processing DeliveryDeliveredEvent for order: {}", event.getOrderId());
        
        OrderHistoryView view = repository.findById(event.getOrderId())
                .orElseThrow(() -> new IllegalStateException("View not initialized for order: " + event.getOrderId()));

        // Deduplication check
        if (isDuplicateEvent(view, "DeliveryAggregate", eventId)) {
            logger.warn("Skipping duplicate DeliveryDeliveredEvent event: {}", eventId);
            return;
        }

        view.markDelivered();
        view.getProcessedEvents().put("DeliveryAggregate", eventId);
        repository.save(view);
    }

    private boolean isDuplicateEvent(OrderHistoryView view, String aggregateType, String eventId) {
        String lastProcessedEventId = view.getProcessedEvents().get(aggregateType);
        // Emulate monotonic string evaluation for duplicate verification
        return eventId.equals(lastProcessedEventId);
    }
}
```

---

### 5. Spring Kafka Event Consumer configuration

```java
package com.ftgo.order.query.config;

import com.ftgo.order.query.events.*;
import com.ftgo.order.query.handlers.OrderHistoryEventHandlers;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import java.util.function.Consumer;

@Configuration
public class OrderHistoryEventConsumerConfig {

    @Autowired
    private OrderHistoryEventHandlers handlers;

    @Bean
    public Consumer<OrderCreatedEvent> orderCreatedConsumer() {
        return event -> handlers.handleOrderCreated(event, "evt_" + event.getOrderId());
    }

    @Bean
    public Consumer<DeliveryPickedUpEvent> deliveryPickedUpConsumer() {
        return event -> handlers.handleDeliveryPickedUp(event, "evt_" + event.getOrderId() + "_pickup");
    }

    @Bean
    public Consumer<DeliveryDeliveredEvent> deliveryDeliveredConsumer() {
        return event -> handlers.handleDeliveryDelivered(event, "evt_" + event.getOrderId() + "_delivered");
    }
}
```

---

### 6. Paginated Query REST Controller: `OrderHistoryQueryController.java`

```java
package com.ftgo.order.query.controller;

import com.ftgo.order.query.document.OrderHistoryView;
import com.ftgo.order.query.repository.OrderHistoryViewRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/consumers")
public class OrderHistoryQueryController {

    @Autowired
    private OrderHistoryViewRepository repository;

    @GetMapping("/{consumerId}/orders")
    public Page<OrderHistoryView> getOrderHistory(
            @PathVariable String consumerId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "15") int size) {

        // Return orders sorted by orderId (which contains timestamp) descending
        PageRequest pageRequest = PageRequest.of(page, size, Sort.by("orderId").descending());

        if (keyword != null && !keyword.trim().isEmpty()) {
            return repository.findByConsumerIdAndRestaurantNameContainingIgnoreCase(
                consumerId, keyword, pageRequest
            );
        } else {
            return repository.findByConsumerId(consumerId, pageRequest);
        }
    }
}
```

---

## 14.9 Implementing the View Database using AWS DynamoDB SDK v2

If you use AWS DynamoDB instead of MongoDB, the DAO uses the AWS DynamoDB SDK v2. The following class shows how to implement idempotent conditional updates, sorting, and pagination using the AWS SDK:

```java
package com.ftgo.order.query.repository;

import org.springframework.stereotype.Repository;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.*;
import java.util.HashMap;
import java.util.Map;

@Repository
public class OrderHistoryDaoDynamoDb {

    private final DynamoDbClient dynamoDbClient;
    private static final String TABLE_NAME = "ftgo-order-history";
    private static final String GSI_NAME = "ftgo-order-history-by-consumer-id-and-creation-time";

    public OrderHistoryDaoDynamoDb(DynamoDbClient dynamoDbClient) {
        this.dynamoDbClient = dynamoDbClient;
    }

    public void addOrder(String orderId, String consumerId, String restaurantName, Double totalAmount, String eventId) {
        Map<String, AttributeValue> item = new HashMap<>();
        item.put("orderId", AttributeValue.builder().s(orderId).build());
        item.put("consumerId", AttributeValue.builder().s(consumerId).build());
        item.put("restaurantName", AttributeValue.builder().s(restaurantName).build());
        item.put("totalAmount", AttributeValue.builder().n(totalAmount.toString()).build());
        item.put("orderStatus", AttributeValue.builder().s("CREATED").build());
        item.put("OrderAggregate", AttributeValue.builder().s(eventId).build());

        // Perform conditional put to prevent processing duplicate events
        PutItemRequest putRequest = PutItemRequest.builder()
                .tableName(TABLE_NAME)
                .item(item)
                .conditionExpression("attribute_not_exists(orderId) OR OrderAggregate < :eventId")
                .expressionAttributeValues(Map.of(":eventId", AttributeValue.builder().s(eventId).build()))
                .build();

        try {
            dynamoDbClient.putItem(putRequest);
        } catch (ConditionalCheckFailedException e) {
            // Ignore the update if it has already been processed
        }
    }

    public void notePickedUp(String orderId, String courierId, String eventId) {
        Map<String, AttributeValue> key = Map.of("orderId", AttributeValue.builder().s(orderId).build());

        // Update status and event tracking attributes
        UpdateItemRequest updateRequest = UpdateItemRequest.builder()
                .tableName(TABLE_NAME)
                .key(key)
                .updateExpression("SET orderStatus = :status, courierId = :courierId, DeliveryAggregate = :eventId")
                .conditionExpression("attribute_exists(orderId) AND (attribute_not_exists(DeliveryAggregate) OR DeliveryAggregate < :eventId)")
                .expressionAttributeValues(Map.of(
                    ":status", AttributeValue.builder().s("PICKED_UP").build(),
                    ":courierId", AttributeValue.builder().s(courierId).build(),
                    ":eventId", AttributeValue.builder().s(eventId).build()
                ))
                .build();

        try {
            dynamoDbClient.updateItem(updateRequest);
        } catch (ConditionalCheckFailedException e) {
            // Duplicate event detected, ignore
        }
    }

    public Map<String, Object> queryOrderHistory(String consumerId, int pageSize, String exclusiveStartKeyJson) {
        Map<String, Condition> keyConditions = new HashMap<>();
        keyConditions.put("consumerId", Condition.builder()
                .comparisonOperator(ComparisonOperator.EQ)
                .attributeValueList(AttributeValue.builder().s(consumerId).build())
                .build());

        QueryRequest.Builder queryBuilder = QueryRequest.builder()
                .tableName(TABLE_NAME)
                .indexName(GSI_NAME)
                .keyConditions(keyConditions)
                .limit(pageSize);

        if (exclusiveStartKeyJson != null && !exclusiveStartKeyJson.isEmpty()) {
            // Parse and apply pagination offset token
            Map<String, AttributeValue> startKey = deserializeStartKey(exclusiveStartKeyJson);
            queryBuilder.exclusiveStartKey(startKey);
        }

        QueryResponse response = dynamoDbClient.query(queryBuilder.build());
        
        Map<String, Object> result = new HashMap<>();
        result.put("items", response.items());
        if (response.hasLastEvaluatedKey()) {
            result.put("paginationToken", serializeStartKey(response.lastEvaluatedKey()));
        }
        return result;
    }

    private Map<String, AttributeValue> deserializeStartKey(String json) {
        // Parse the pagination token JSON back into a DynamoDB attribute map
        return new HashMap<>();
    }

    private String serializeStartKey(Map<String, AttributeValue> key) {
        // Serialize LastEvaluatedKey to an opaque base64/JSON string
        return "";
    }
}
```

---

## 14.10 Programmatic Integration Testing with Testcontainers

To verify that the event handlers process events correctly and update the read view database, we write an integration test. We use **Testcontainers** to run a real MongoDB instance inside a Docker container:

```java
package com.ftgo.order.query;

import com.ftgo.order.query.document.OrderHistoryView;
import com.ftgo.order.query.events.OrderCreatedEvent;
import com.ftgo.order.query.handlers.OrderHistoryEventHandlers;
import com.ftgo.order.query.repository.OrderHistoryViewRepository;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.MongoDBContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.Optional;

@SpringBootTest
@Testcontainers
public class OrderHistoryIntegrationTest {

    @Container
    public static MongoDBContainer mongoDBContainer = new MongoDBContainer("mongo:6.0");

    @DynamicPropertySource
    static void setMongoProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.data.mongodb.uri", mongoDBContainer::getReplicaSetUrl);
    }

    @Autowired
    private OrderHistoryEventHandlers eventHandlers;

    @Autowired
    private OrderHistoryViewRepository repository;

    @Test
    public void testOrderCreationSavesView() {
        String orderId = "order_9981";
        String eventId = "evt_9981";
        
        OrderCreatedEvent event = new OrderCreatedEvent(orderId, "customer_1", "Pizza Express", 45.00);

        // 1. Process Event
        eventHandlers.handleOrderCreated(event, eventId);

        // 2. Query Read Model View
        Optional<OrderHistoryView> optionalView = repository.findById(orderId);
        Assertions.assertTrue(optionalView.isPresent());
        
        OrderHistoryView view = optionalView.get();
        Assertions.assertEquals("customer_1", view.getConsumerId());
        Assertions.assertEquals("Pizza Express", view.getRestaurantName());
        Assertions.assertEquals(45.00, view.getTotalAmount());
        Assertions.assertEquals("CREATED", view.getOrderStatus());
        Assertions.assertEquals(eventId, view.getProcessedEvents().get("OrderAggregate"));

        // 3. Process Duplicate Event (Verify Idempotency)
        eventHandlers.handleOrderCreated(event, eventId);
        
        // Assert no duplicates are recorded and state remains consistent
        Assertions.assertEquals(1, repository.findById(orderId).get().getProcessedEvents().size());
    }
}
```

---

## 14.11 Querying Views using Elasticsearch

For advanced, high-performance text searches, the view database is implemented using **Elasticsearch**. Below is an example of an Elasticsearch service implementation using the Spring WebClient:

```java
package com.ftgo.order.query.repository;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Repository;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

@Repository
public class OrderSearchElasticsearchRepository {

    @Autowired
    private WebClient webClient;

    public void indexOrder(String orderId, String jsonPayload) {
        webClient.put()
                .uri("/order_history/_doc/" + orderId)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(jsonPayload)
                .retrieve()
                .toBodilessEntity()
                .subscribe();
    }

    public Mono<String> searchOrders(String query) {
        String elasticsearchQuery = "{\n" +
                "  \"query\": {\n" +
                "    \"multi_match\" : {\n" +
                "      \"query\":    \"" + query + "\",\n" +
                "      \"fields\":   [ \"restaurantName\", \"menuItems.name\" ]\n" +
                "    }\n" +
                "  }\n" +
                "}";

        return webClient.post()
                .uri("/order_history/_search")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(elasticsearchQuery)
                .retrieve()
                .bodyToMono(String.class);
    }
}
```

---

## 14.12 Rebuilding Views using Archived Events and Snapshots

In production, CQRS views must occasionally be rebuilt (e.g. to fix view logic bugs, or migrate schemas). Replaying all historical events from a message broker is impossible because brokers do not store messages indefinitely.

Instead, we use a two-step approach:

```
[ Long-term Event Archive (AWS S3) ]
                 |
                 v (Step 1: Spark Batch Processing)
      [ Daily View Snapshot ]
                 |
                 v (Step 2: Stream remaining broker events)
       [ Live View Database ]
```

1. **Batch Replay from Archives**: Fetch archived event logs from offline storage (e.g., AWS S3, Apache Iceberg) and process them using batch processing engines (e.g., Apache Spark) to reconstruct the state up to a specific checkpoint date.
2. **Incremental Catch-Up**: Stream live events from the message broker starting from the checkpoint date to catch up to the current state.

---

## 14.13 Automated View Synchronization: Kafka Connect Elasticsearch Sink

Rather than writing custom consumer applications, developers can configure **Kafka Connect** to automatically stream events from Kafka topics directly into the Elasticsearch read database:

```json
{
  "name": "elasticsearch-sink-connector",
  "config": {
    "connector.class": "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector",
    "tasks.max": "2",
    "topics": "saga-events.OrderAggregate",
    "key.ignore": "false",
    "schema.ignore": "true",
    "connection.url": "http://elasticsearch-host:9200",
    "type.name": "_doc",
    "behavior.on.null.values": "delete",
    "write.method": "upsert",
    "transforms": "route",
    "transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
    "transforms.route.regex": "saga-events.(.*)",
    "transforms.route.replacement": "order_history"
  }
}
```

---

## 14.14 Blue-Green Read View Migrations

When domain schemas mutate (e.g. adding new child attributes to the view model), rebuilding in-place can cause query outages. 

To solve this, we implement a **Blue-Green View Migration** strategy. We spin up a new query view index (Green), stream historical events to rebuild it, and then swap aliases programmatically:

```java
package com.ftgo.order.query.migration;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.stereotype.Service;

@Service
public class BlueGreenViewMigrationService {

    @Autowired
    private MongoTemplate mongoTemplate;

    public void executeMigrationSwap(String oldIndexName, String newIndexName, String aliasName) {
        // 1. Verify new index has been populated and contains data
        long documentCount = mongoTemplate.getCollection(newIndexName).countDocuments();
        if (documentCount == 0) {
            throw new IllegalStateException("Migration aborted: Green index is empty!");
        }

        // 2. Programmatically swap database aliases to direct query traffic to the new index
        System.out.println("Swapping query traffic alias [" + aliasName + "] from " + oldIndexName + " to " + newIndexName);
        
        // In MongoDB / Elasticsearch, this alias swap is an atomic operation
        // mongoTemplate.executeCommand("{ 'alias_swap': ... }");
    }
}
```

---


## Chapter Summary

* The **CQRS** pattern splits a service into a **Command Side** (optimized for CUD operations and business rules) and a **Query Side** (optimized for fast reads and text searches).
* Standalone query-side services subscribe to events from multiple microservices to build a denormalized read model.
* A CQRS view module contains a view database and three submodules: the Query API, Event Handlers, and Data Access (DAO).
* To handle the eventual consistency replication lag, client applications can pass event tokens or implement client-side optimistic UI updates.
* Event handlers must be idempotent. In NoSQL databases, they detect duplicate events by storing the highest-seen event version in the document.
* Spring Data MongoDB and NoSQL secondary indexes support sorting, filtering, and paginating denormalized read models.
* Rebuilding views is accomplished by combining batch processing of archived events with incremental catch-up of live broker events.
