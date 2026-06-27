# Chapter 15: Event-Driven Architectures with Spring Cloud Stream and Kafka

In a microservices architecture, services must exchange data asynchronously to maintain loose coupling and high availability. Direct REST communication creates dependencies and reduces system availability. If Service A makes a synchronous HTTP request to Service B, Service A's availability becomes directly dependent on Service B's uptime, network latency, and database performance. To build a resilient, scalable system, we use an **Event-Driven Architecture (EDA)**.

This chapter covers the implementation of event-driven microservices using **Spring Cloud Stream** and **Apache Kafka**. We will analyze Kafka's architecture—including topics, partitions, and consumer groups—and configure Spring Cloud Stream binders and bindings inside Spring Boot properties. Finally, we will write Java implementations of message publishers and consumers using both annotation-based (`@StreamListener`) and functional Java 8 styles, culminating in a complete **Distributed Caching** use case using Redis and Kafka.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the architectural advantages of Event-Driven Architecture (EDA) over synchronous HTTP communication.
2. Outline the roles of **Topics**, **Partitions**, and **Offsets** in Apache Kafka.
3. Detail how **Consumer Groups** scale message consumption while maintaining execution order.
4. Configure Spring Cloud Stream binders and destination bindings in properties files.
5. Implement message publishing logic using Spring Cloud Stream message channels.
6. Build message consumers using legacy `@StreamListener` annotations and custom channels.
7. Implement a complete **Distributed Caching** pipeline using Redis, Kafka, and Spring Data.
8. Compare legacy annotation-driven mappings with the modern Spring Cloud Stream functional programming model.

---

## 15.1 Apache Kafka Architecture: Topics, Partitions, and Groups

Apache Kafka is a high-throughput, distributed event streaming platform designed to handle real-time data feeds. It functions as a commit log where events are structured sequentially, stored across clusters, and replicated for fault tolerance.

### 1. Topics
A topic is a logical channel or category to which events are published. Topics are append-only logs, and events are immutable records.

### 2. Partitions
To scale horizontally, Kafka divides a topic into multiple **Partitions** distributed across a cluster of brokers.
* **Ordering**: Kafka guarantees message ordering *only within a single partition*.
* **Routing**: The producer assigns events a routing partition key (e.g., `orderId`). Kafka hashes the key to route all events with the same key to the same partition, guaranteeing ordered delivery.

### 3. Offsets and Consumer Groups
An offset is a sequential integer ID that Kafka assigns to each message inside a partition. Consumers track their progress by committing the read offset.

Multiple consumer instances can join a **Consumer Group**:
* Kafka assigns each partition to exactly one consumer instance within a group. This allows you to scale consumption horizontally (up to the number of partitions) without duplicate delivery.
* If a consumer instance fails, Kafka rebalances the partitions among the remaining active instances in the group.

---

## 15.2 Spring Cloud Stream Core Concepts

**Spring Cloud Stream** is a framework that simplifies building event-driven microservices. It abstracts the underlying messaging system (the message broker) by introducing platform-neutral components:

* **Source**: A Spring-annotated interface that serializes a Plain Old Java Object (POJO) into a message and publishes it to a channel.
* **Channel**: An abstraction over the message queue or topic. Code binds to named channels rather than broker-specific queues, decoupling logic from configuration.
* **Binder**: An implementation adapter that integrates Spring Cloud Stream with a specific message broker (e.g., Kafka, RabbitMQ).
* **Sink**: A listener component that receives messages from a channel and deserializes them back into Java POJOs for processing.

The diagram below shows how these components facilitate message flow between publishing and consuming services:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1c07b341-4dc4-46bc-8a19-42f13d638423/markdown_2/imgs/img_in_image_box_159_98_944_1073.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A40Z%2F-1%2F%2F8ea47c4a11cdd30ea98a34691427fc78928c6c9fa73edcd97e084007c89b78fb" alt="Image" width="73%" /></div>
<div style="text-align: center;">Figure 15.1: As a message is published and consumed, it flows through a series of Spring Cloud Stream components that abstract away the underlying messaging platform.</div>

---

## 15.3 Writing a Simple Message Producer and Consumer

We will construct a messaging flow where our Order Service publishes a change event to a Kafka topic when order data changes, and the Kitchen Service consumes the message.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1c07b341-4dc4-46bc-8a19-42f13d638423/markdown_4/imgs/img_in_image_box_199_104_938_646.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A41Z%2F-1%2F%2Fb1a500d15d69f763fd9e5e4577ae1e68037ac61b281b4c261761fe2465d38782" alt="Image" width="69%" /></div>
<div style="text-align: center;">Figure 15.2: When the order service data changes, it publishes a message to orderChangeTopic.</div>

### 15.3.1 Configuring Apache Kafka and Redis in Docker

We define Zookeeper (which manages the Kafka cluster nodes and topic configurations), Kafka, and Redis services in our `docker-compose.yml`:

```yaml
version: "3.7"
services:
  zookeeper:
    image: wurstmeister/zookeeper:latest
    ports:
      - "2181:2181"
    networks:
      backend:
        aliases:
          - "zookeeper"

  kafkaserver:
    image: wurstmeister/kafka:latest
    ports:
      - "9092:9092"
    environment:
      - KAFKA_ADVERTISED_HOST_NAME=kafka
      - KAFKA_ADVERTISED_PORT=9092
      - KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181
      - KAFKA_CREATE_TOPICS=orgChangeTopic:1:1
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock"
    depends_on:
      - zookeeper
    networks:
      backend:
        aliases:
          - "kafka"

  redisserver:
    image: redis:alpine
    ports:
      - "6379:6379"
    networks:
      backend:
        aliases:
          - "redis"
```

To boot these services, run the following command in the directory containing the compose file:
```bash
docker-compose -f docker-compose.yml up -d
```

---

### 15.3.2 Writing the Message Producer (Order Service)

First, add dependencies for core Spring Cloud Stream and its Kafka binder inside `order-service/pom.xml`:


```xml
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-stream</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-stream-kafka</artifactId>
</dependency>
```

We enable bindings in the Order Service's bootstrap class:

```java
package com.ftgo.order;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.context.config.annotation.RefreshScope;
import org.springframework.cloud.stream.annotation.EnableBinding;
import org.springframework.cloud.stream.messaging.Source;

@SpringBootApplication
@RefreshScope
@EnableBinding(Source.class)
public class OrderServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(OrderServiceApplication.class, args);
    }
}
```

*Note: `@EnableBinding(Source.class)` registers an output channel defined in Spring Cloud Stream's default `Source` interface.*

Next, implement the `UserContext` class to make correlation metadata available to our message payloads via thread-local variables:

```java
package com.ftgo.order.utils;

import org.springframework.stereotype.Component;

@Component
public class UserContext {
    public static final String CORRELATION_ID = "ftgo-correlation-id";
    public static final String AUTH_TOKEN     = "Authorization";
    public static final String USER_ID        = "ftgo-user-id";
    public static final String RESTAURANT_ID  = "ftgo-restaurant-id";

    private static final ThreadLocal<String> correlationId = new ThreadLocal<>();
    private static final ThreadLocal<String> authToken     = new ThreadLocal<>();
    private static final ThreadLocal<String> userId        = new ThreadLocal<>();
    private static final ThreadLocal<String> restaurantId  = new ThreadLocal<>();

    public static String getCorrelationId() { return correlationId.get(); }
    public static void setCorrelationId(String cid) { correlationId.set(cid); }
    public static String getAuthToken() { return authToken.get(); }
    public static void setAuthToken(String token) { authToken.set(token); }
    public static String getUserId() { return userId.get(); }
    public static void setUserId(String uid) { userId.set(uid); }
    public static String getRestaurantId() { return restaurantId.get(); }
    public static void setRestaurantId(String oid) { restaurantId.set(oid); }
}
```

Now, create the `SimpleSourceBean` containing the message publishing logic:

```java
package com.ftgo.order.events.source;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.stream.messaging.Source;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.stereotype.Component;
import com.ftgo.order.events.model.OrderChangeModel;
import com.ftgo.order.utils.UserContext;

@Component
public class SimpleSourceBean {
    private final Source source;
    private static final Logger logger = LoggerFactory.getLogger(SimpleSourceBean.class);

    public SimpleSourceBean(Source source) {
        this.source = source;
    }

    public void publishOrderChange(ActionEnum action, String orderId) {
        logger.debug("Sending Kafka message {} for Order Id: {}", action, orderId);
        
        OrderChangeModel change = new OrderChangeModel(
                OrderChangeModel.class.getSimpleName(),
                action.toString(),
                orderId,
                UserContext.getCorrelationId()
        );

        source.output().send(MessageBuilder.withPayload(change).build());
    }
}
```

The payload utilizes an enum containing the data modification states:

```java
package com.ftgo.order.events.source;

public enum ActionEnum {
    GET,
    CREATED,
    UPDATED,
    DELETED
}
```

Define the event payload model POJO:

```java
package com.ftgo.order.events.model;

public class OrderChangeModel {
    private String type;
    private String action;
    private String orderId;
    private String correlationId;

    public OrderChangeModel() {}

    public OrderChangeModel(String type, String action, String orderId, String correlationId) {
        this.type = type;
        this.action = action;
        this.orderId = orderId;
        this.correlationId = correlationId;
    }

    public String getType() { return type; }
    public void setType(String type) { this.type = type; }
    public String getAction() { return action; }
    public void setAction(String action) { this.action = action; }
    public String getOrderId() { return orderId; }
    public void setOrderId(String orderId) { this.orderId = orderId; }
    public String getCorrelationId() { return correlationId; }
    public void setCorrelationId(String correlationId) { this.correlationId = correlationId; }
}
```

Configure how the output channel binds to Kafka inside `order-service.properties` hosted on the Config Server:

```properties
# Map Spring Cloud Stream output channel to orderChangeTopic
spring.cloud.stream.bindings.output.destination=orderChangeTopic
spring.cloud.stream.bindings.output.content-type=application/json
spring.cloud.stream.kafka.binder.zkNodes=localhost:2181
spring.cloud.stream.kafka.binder.brokers=localhost:9092
```

We execute this publishing behavior inside our core business service layer:

```java
package com.ftgo.order.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ftgo.order.model.Order;
import com.ftgo.order.repository.OrderRepository;
import com.ftgo.order.events.source.SimpleSourceBean;
import com.ftgo.order.events.source.ActionEnum;
import java.util.UUID;

@Service
public class OrderService {
    @Autowired
    private OrderRepository repository;

    @Autowired
    private SimpleSourceBean simpleSourceBean;

    public Order create(Order order) {
        order.setOrderId(UUID.randomUUID().toString());
        order = repository.save(order);
        
        // Publish event to Kafka
        simpleSourceBean.publishOrderChange(ActionEnum.CREATED, order.getOrderId());
        return order;
    }
}
```

#### Rationale: What Data Should We Put in the Message?
A critical design question is: *How much data should we package inside a published message payload?*

There are two primary paradigms:
1. **Event-Carried State Transfer**: You package the complete, updated object representation inside the message. Downstream services update their local states immediately.
   * *Pro*: Avoids query callbacks to the source service.
   * *Con*: Payload overhead increases. If updates fail or arrive out of sequence, consumer caches can become persistently inconsistent.
2. **Lightweight Notification**: You publish only the entity identifier (e.g., `orderId`) and event type (e.g., `UPDATED`). The consumer uses this ID to fetch fresh data from the master service.
   * *Pro*: Guarantees downstream processors always load the exact current state.
   * *Con*: Creates a network fetch call immediately after message receipt.

*For our caching design, we adopt lightweight notifications. Downstream services receive the identifier and immediately purge local records to eliminate stale cached reads.*


---

### 15.3.3 Writing the Message Consumer (Kitchen Service)

Next, we establish a listener in the Kitchen Service to process order update notifications.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1c69c5f6-6e1c-416f-b549-37c81f1d7e29/markdown_2/imgs/img_in_image_box_197_478_802_652.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A40Z%2F-1%2F%2Faa01c3f81152f38c77afeeb6f0a0f44ebd00fc52cd5aabb1c204bd8d5db804d1" alt="Image" width="56%" /></div>
<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1c69c5f6-6e1c-416f-b549-37c81f1d7e29/markdown_2/imgs/img_in_image_box_166_672_892_1211.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A40Z%2F-1%2F%2Fce54d394b47a7928aab2341721a96ce9a524814a46b9928341ab698a3b3d0c42" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 15.3: When a message comes into the Kafka orderChangeTopic, the kitchen service responds.</div>

We configure the bootstrap class inside the Kitchen Service using `@EnableBinding(Sink.class)`:

```java
package com.ftgo.kitchen;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.stream.annotation.EnableBinding;
import org.springframework.cloud.stream.annotation.StreamListener;
import org.springframework.cloud.stream.messaging.Sink;
import com.ftgo.order.events.model.OrderChangeModel;

@SpringBootApplication
@EnableBinding(Sink.class)
public class KitchenServiceApplication {
    private static final Logger logger = LoggerFactory.getLogger(KitchenServiceApplication.class);

    public static void main(String[] args) {
        SpringApplication.run(KitchenServiceApplication.class, args);
    }

    @StreamListener(Sink.INPUT)
    public void loggerSink(OrderChangeModel orderChange) {
        logger.debug("Received an {} event for order id {}",
                orderChange.getAction(), orderChange.getOrderId());
    }
}
```

*Note: `@StreamListener(Sink.INPUT)` listens to the inbound channel and automatically deserializes payloads.*

Map the consumer input to the destination topic inside `kitchen-service.properties`:

```properties
# Map input channel to target Kafka topic
spring.cloud.stream.bindings.input.destination=orderChangeTopic
spring.cloud.stream.bindings.input.content-type=application/json
# Configure the consumer group
spring.cloud.stream.bindings.input.group=kitchenGroup
spring.cloud.stream.kafka.binder.zkNodes=localhost:2181
spring.cloud.stream.kafka.binder.brokers=localhost:9092
```

The `spring.cloud.stream.bindings.input.group` configures a **Consumer Group** called `kitchenGroup`. The group acts as a mechanism to distribute partition processing safely:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1c69c5f6-6e1c-416f-b549-37c81f1d7e29/markdown_4/imgs/img_in_image_box_205_764_908_1160.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A41Z%2F-1%2F%2Fcc55b3d000490a6b1aae1bd48475205a00e704c7a561d12c0a6846d9d3c0807d" alt="Image" width="66%" /></div>
<div style="text-align: center;">Figure 15.4: The consumer group guarantees that a message is only processed once by a group of service instances.</div>

---

### 15.3.4 Testing the Message Service

To see the system in action:
1. Issue a POST request via Postman to add an order:

```http
POST http://localhost:8072/order/v1/restaurant/1/order
Content-Type: application/json
Authorization: Bearer <JWT_ACCESS_TOKEN>

{
    "restaurantId": "1",
    "consumerId": "1001",
    "items": [
        {
            "menuItemId": "pizza-01",
            "name": "Cheese Pizza",
            "price": 12.99,
            "quantity": 2
        }
    ]
}
```

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1d66b742-a6be-4d0d-8a9b-8ab9c52d32d2/markdown_0/imgs/img_in_image_box_183_738_930_1129.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A42Z%2F-1%2F%2F132d761f2b2e56ac4513cc9548a8515f477e45310fdc1d98c397c793355a7409" alt="Image" width="70%" /></div>
<div style="text-align: center;">Figure 15.5: Creating a new order service record using the order service.</div>

2. Verify that the output logs confirm publication and consumption:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//1d66b742-a6be-4d0d-8a9b-8ab9c52d32d2/markdown_1/imgs/img_in_image_box_155_110_948_355.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A43Z%2F-1%2F%2Fe082680e5a97c36e91b1f696b2b091a4f09684f86e7ba7da386aa8098cb980a9" alt="Image" width="74%" /></div>
<div style="text-align: center;">Figure 15.6: The console shows the message from the order service being sent and then received.</div>

---

## 15.4 Distributed Caching with Redis and Kafka

Distributed caches improve lookup performance and reduce direct load on backend databases. However, caches introduce **Data Consistency** challenges. If an order updates its details in the database, the cache remains stale unless cleared.

We implement the following distributed caching flow:

```
  Kitchen Service                 Redis Cache               Order Service
         |                             |                             |
         |--- 1. Check Cache --------->|                             |
         |    (Cache Miss)             |                             |
         |                             |                             |
         |--- 2. GET HTTP ------------>+---------------------------->|
         |                              (Fetch Order record)         |
         |<-- 3. Return Order Data ----+----------------------------|
         |                             |                             |
         |--- 4. Write Cache --------->|                             |
         |                             |                             |
         |                             |                 * Data Updated *
         |                             |                             |
         |                             |<-- 5. Order Event ----------|
         |                             |    (DELETE / Invalidate)    |
```

### 1. Spring Data Redis Configuration

First, define the Redis properties in your configuration file:
```properties
redis.server=localhost
redis.port=6379
```

Add dependencies to `pom.xml`:
```xml
<dependency>
    <groupId>org.springframework.data</groupId>
    <artifactId>spring-data-redis</artifactId>
</dependency>
<dependency>
    <groupId>redis.clients</groupId>
    <artifactId>jedis</artifactId>
    <type>jar</type>
</dependency>
```

Expose connection factory and template beans in `KitchenServiceApplication`:

```java
package com.ftgo.kitchen;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.data.redis.connection.RedisStandaloneConfiguration;
import org.springframework.data.redis.connection.jedis.JedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import com.ftgo.kitchen.config.ServiceConfig;

public class KitchenServiceApplication {
    @Autowired
    private ServiceConfig serviceConfig;

    @Bean
    public JedisConnectionFactory jedisConnectionFactory() {
        String hostname = serviceConfig.getRedisServer();
        int port = Integer.parseInt(serviceConfig.getRedisPort());
        RedisStandaloneConfiguration config = new RedisStandaloneConfiguration(hostname, port);
        return new JedisConnectionFactory(config);
    }

    @Bean
    public RedisTemplate<String, Object> redisTemplate() {
        RedisTemplate<String, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(jedisConnectionFactory());
        return template;
    }
}
```

The config parameters are read using a standard `@Component`:

```java
package com.ftgo.kitchen.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class ServiceConfig {
    @Value("${redis.server}")
    private String redisServer;

    @Value("${redis.port}")
    private String redisPort;

    public String getRedisServer() { return redisServer; }
    public String getRedisPort() { return redisPort; }
}
```

---

### 2. Redis Repository and Hash Model

Define the Redis hash repository for storing order records:

```java
package com.ftgo.kitchen.repository;

import org.springframework.data.repository.CrudRepository;
import org.springframework.stereotype.Repository;
import com.ftgo.kitchen.model.Order;

@Repository
public interface OrderRedisRepository extends CrudRepository<Order, String> {
}
```

Create the hash mapping entity model:

```java
package com.ftgo.kitchen.model;

import org.springframework.data.redis.core.RedisHash;
import org.springframework.data.annotation.Id;
import java.io.Serializable;

@RedisHash("order")
public class Order implements Serializable {
    private static final long serialVersionUID = 1L;

    @Id
    private String orderId;
    private String restaurantId;
    private String consumerId;
    private double totalAmount;
    private String state;

    public Order() {}

    public String getOrderId() { return orderId; }
    public void setOrderId(String orderId) { this.orderId = orderId; }
    public String getRestaurantId() { return restaurantId; }
    public void setRestaurantId(String restaurantId) { this.restaurantId = restaurantId; }
    public String getConsumerId() { return consumerId; }
    public void setConsumerId(String consumerId) { this.consumerId = consumerId; }
    public double getTotalAmount() { return totalAmount; }
    public void setTotalAmount(double totalAmount) { this.totalAmount = totalAmount; }
    public String getState() { return state; }
    public void setState(String state) { this.state = state; }
}
```

---

### 3. Rest Client Cache Lookup Implementation

Configure the `OrderRestTemplateClient` to check the cache before routing REST calls:

```java
package com.ftgo.kitchen.service.client;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import com.ftgo.kitchen.model.Order;
import com.ftgo.kitchen.repository.OrderRedisRepository;

@Component
public class OrderRestTemplateClient {
    @Autowired
    private RestTemplate restTemplate;

    @Autowired
    private OrderRedisRepository redisRepository;

    private static final Logger logger = LoggerFactory.getLogger(OrderRestTemplateClient.class);

    private Order checkRedisCache(String orderId) {
        try {
            return redisRepository.findById(orderId).orElse(null);
        } catch (Exception ex) {
            logger.error("Error retrieving order {} from Redis cache: {}", orderId, ex.getMessage());
            return null; // Fall back to HTTP call on cache error
        }
    }

    private void cacheOrderObject(Order order) {
        try {
            redisRepository.save(order);
        } catch (Exception ex) {
            logger.error("Unable to cache order {} in Redis: {}", order.getOrderId(), ex.getMessage());
        }
    }

    public Order getOrder(String orderId) {
        Order order = checkRedisCache(orderId);
        if (order != null) {
            logger.debug("Successfully retrieved order {} from Redis cache: {}", orderId, order);
            return order;
        }

        logger.debug("Cache miss! Querying downstream order service...");
        ResponseEntity<Order> restExchange = restTemplate.exchange(
                "http://gateway-server:8072/order/v1/restaurant/1/order/{orderId}",
                HttpMethod.GET,
                null,
                Order.class,
                orderId
        );

        order = restExchange.getBody();
        if (order != null) {
            cacheOrderObject(order);
        }
        return order;
    }
}
```

*Design Pattern Check: If Redis goes down, we catch the exception and fall back to the direct HTTP request. The application continues to run, degrading gracefully.*

---

## 15.5 Defining Custom Channels and Event Processing

Using default channels limits you to one consumer and one producer topic. To scale communication across multiple business topics, we define a custom interface.

### 1. Custom Channel Definition

```java
package com.ftgo.kitchen.events;

import org.springframework.cloud.stream.annotation.Input;
import org.springframework.cloud.stream.annotation.Output;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.SubscribableChannel;

public interface CustomChannels {
    String INBOUND_ORDER = "inboundOrderChanges";
    String OUTBOUND_ORDER = "outboundOrder";

    @Input(INBOUND_ORDER)
    SubscribableChannel ordersInput();

    @Output(OUTBOUND_ORDER)
    MessageChannel ordersOutput();
}
```

Update your configuration properties mapping:

```properties
spring.cloud.stream.bindings.inboundOrderChanges.destination=orderChangeTopic
spring.cloud.stream.bindings.inboundOrderChanges.content-type=application/json
spring.cloud.stream.bindings.inboundOrderChanges.group=kitchenGroup

spring.cloud.stream.bindings.outboundOrder.destination=orderChangeTopic
spring.cloud.stream.bindings.outboundOrder.content-type=application/json
```

---

### 2. Order Event Handler: Cache Invalidation

Create the event handler that invalidates the cache when it receives change events:

```java
package com.ftgo.kitchen.events.handler;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.stream.annotation.EnableBinding;
import org.springframework.cloud.stream.annotation.StreamListener;
import org.springframework.beans.factory.annotation.Autowired;
import com.ftgo.kitchen.events.CustomChannels;
import com.ftgo.order.events.model.OrderChangeModel;
import com.ftgo.kitchen.repository.OrderRedisRepository;

@EnableBinding(CustomChannels.class)
public class OrderChangeHandler {
    private static final Logger logger = LoggerFactory.getLogger(OrderChangeHandler.class);

    @Autowired
    private OrderRedisRepository redisRepository;

    @StreamListener(CustomChannels.INBOUND_ORDER)
    public void handleOrderChange(OrderChangeModel order) {
        logger.debug("Received a message with an event {} from the order service for the order id {}",
                order.getAction(), order.getOrderId());

        if ("UPDATE".equals(order.getAction()) || "DELETE".equals(order.getAction())) {
            logger.debug("Invalidating Redis cache entry for order ID: {}", order.getOrderId());
            redisRepository.deleteById(order.getOrderId());
        }
    }
}
```

Let's verify this invalidation using the console output:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b8f56ba2-50ff-4cec-894b-3a60de573bcb/markdown_0/imgs/img_in_image_box_144_101_934_555.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T09%3A47%3A39Z%2F-1%2F%2F8e8194beb28948372bbd8dea18e806ff2f1c101913b3ebd7d4646a4ce953f910" alt="Image" width="74%" /></div>
<div style="text-align: center;">Figure 15.7: The console shows the message from the order service that was sent and then received.</div>

---

## 15.6 The Functional Programming Consumer Model (Spring Cloud Stream v3+)

In Spring Cloud Stream 3.x, annotation-driven interfaces like `@EnableBinding`, `@StreamListener`, `@Input`, and `@Output` are deprecated. Instead, the framework uses standard Java 8 functional interfaces:
* `java.util.function.Supplier` (Produces messages)
* `java.util.function.Consumer` (Consumes messages)
* `java.util.function.Function` (Receives, transforms, and republishes messages)

### 15.6.1 Configuration Schema

Spring binds functional beans to topics using a structured naming convention:
* **Input channel**: `<beanName>-in-<index>` (e.g., `processOrderEvent-in-0`)
* **Output channel**: `<beanName>-out-<index>` (e.g., `processOrderEvent-out-0`)

Update your properties:

```yaml
spring:
  cloud:
    function:
      definition: processOrderEvent
    stream:
      bindings:
        processOrderEvent-in-0:
          destination: orderChangeTopic
          group: functional-kitchen-group
          content-type: application/json
```

---

### 15.6.2 Functional Consumer Code

Expose a `@Bean` returning a `Consumer<T>`:

```java
package com.ftgo.kitchen.messaging;

import java.util.function.Consumer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import com.ftgo.order.events.model.OrderChangeModel;
import com.ftgo.kitchen.repository.OrderRedisRepository;

@Configuration
public class OrderEventConsumer {
    private static final Logger logger = LoggerFactory.getLogger(OrderEventConsumer.class);

    @Bean
    public Consumer<OrderChangeModel> processOrderEvent(OrderRedisRepository repository) {
        return changeModel -> {
            logger.debug("Functional Consumer processed order change event: Action={}, OrderId={}",
                    changeModel.getAction(), changeModel.getOrderId());
            
            if ("UPDATE".equals(changeModel.getAction()) || "DELETE".equals(changeModel.getAction())) {
                repository.deleteById(changeModel.getOrderId());
                logger.debug("Successfully invalidated Redis Cache for order: {}", changeModel.getOrderId());
            }
        };
    }
}
```

---

## 15.7 Dead Letter Queues (DLQ) and Error Handling

When processing events from Kafka, consumer applications can encounter parsing errors or temporary database locking exceptions. Rather than crashing the consumer thread or losing the message, we configure **Spring Cloud Stream Retries** and a **Dead Letter Queue (DLQ)**.

If a message processing fails after all retry attempts, Spring Cloud Stream routes the poisoned message to a separate Kafka DLQ topic for manual inspection and redelivery.

### 15.7.1 YAML Retries and DLQ Config

```yaml
spring:
  cloud:
    stream:
      bindings:
        processOrderEvent-in-0:
          destination: orderChangeTopic
          group: functional-kitchen-group
          consumer:
            max-attempts: 3
            back-off-initial-interval: 1000
            back-off-multiplier: 2.0
      kafka:
        bindings:
          processOrderEvent-in-0:
            consumer:
              enable-dlq: true
              dlq-name: orderChangeTopic.DLQ
```

### 15.7.2 Java Custom DLQ Header Extractor

We can inspect the routing path and failure reasons of messages directed to the DLQ by configuring a custom listener:

```java
package com.ftgo.kitchen.messaging;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.stereotype.Component;

@Component
public class KafkaDLQErrorHandler {

    private static final Logger logger = LoggerFactory.getLogger(KafkaDLQErrorHandler.class);

    @KafkaListener(topics = "orderChangeTopic.DLQ", groupId = "dlq-monitoring-group")
    public void processDeadLetterMessage(
            @Payload String payload,
            @Header(KafkaHeaders.RECEIVED_TOPIC) String topic,
            @Header(name = "x-exception-message", required = false) String exceptionMessage) {
        
        // Log the message details along with the failure exception stack
        logger.error("Dead-Letter message intercepted from topic [{}]. Raw payload: {}", topic, payload);
        logger.error("Downstream processing failure exception message: {}", exceptionMessage);
        
        // Trigger alerts to notify operations teams of data ingestion issues
    }
}
```

---


## Chapter Summary

* **Event-Driven Architecture (EDA)** improves availability and reduces coupling by replacing synchronous calls with asynchronous event publishing.
* **Apache Kafka** stores events in append-only partition logs. It ensures message ordering within a partition by hashing a routing key.
* **Consumer Groups** scale message consumption horizontally without duplicate delivery by allocating partitions among active consumer instances.
* **Spring Cloud Stream** abstracts the underlying broker by using **Binders** and **Bindings** configured in Spring Boot properties.
* We implement message publishers in Java using message channels, and implement consumers using either legacy `@StreamListener` annotations or the newer **Functional Programming** model.
* A common use case is event-driven caching: the consumer invalidates cached data in **Redis** when it receives a change event from Kafka.
