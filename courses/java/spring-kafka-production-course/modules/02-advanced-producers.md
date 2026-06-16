# Module 02 — Advanced Producers

In this module, we will explore advanced producer configurations in Spring Kafka. We will look at the internal execution flow of `KafkaTemplate.send()` and cover asynchronous publishing using Java's `CompletableFuture`. We will study how to enrich Kafka records with custom headers, track transaction correlation IDs, and write custom producer interceptors. Finally, we will cover the request-reply messaging pattern using `ReplyingKafkaTemplate` and discuss message routing techniques. We will close with Socratic review questions, hands-on labs with complete Java code structures, and detailed configuration tables.

---

## 1. Academic Lecture: Template Internals, Interceptors & Request-Reply

### Basic Level: Send Execution Flow, Asynchronous Callbacks & Headers

#### `KafkaTemplate.send()` Internals
When you invoke a send method on `KafkaTemplate`, the request goes through several internal processing steps before it reaches the network socket:
1. **Serializer Mapping**: The template uses the serializers registered in the `ProducerFactory` to convert the record key and value into raw byte arrays.
2. **Interception**: If you registered any `ProducerInterceptor` beans, the template runs their `.onSend(ProducerRecord)` callbacks to modify or log the records.
3. **Partition Assignment**: The template passes the record to the producer's internal partitioner. If a key is provided, the partitioner calculates its hash to determine the destination partition index. If no key is set, it uses the default sticky partitioner strategy.
4. **Batch Accumulator**: The record is not sent to the broker immediately. Instead, it is written to the producer's internal memory buffer (RecordAccumulator). It is grouped with other records targeting the same partition.
5. **Sender Thread**: A background execution thread retrieves the batches from the accumulator and sends them over TCP sockets to the destination brokers.

#### Asynchronous Publishing with `CompletableFuture`
In Spring Kafka, publishing is asynchronous by default. The `send()` method writes the record to the memory accumulator and returns immediately.
To capture broker confirmations (such as metadata offset and partition info) or handle connection timeouts, you register callbacks on the returned `CompletableFuture`:

```java
CompletableFuture<SendResult<String, String>> future = kafkaTemplate.send("orders", "order-123", "Value");
future.whenComplete((result, ex) -> {
    if (ex == null) {
        RecordMetadata metadata = result.getRecordMetadata();
        log.info("Delivered to Partition: {} | Offset: {}", metadata.partition(), metadata.offset());
    } else {
        log.error("Broker delivery failed", ex);
    }
});
```

#### Custom Message Headers
Kafka records (since version 0.11) include a **Headers** metadata field. Headers consist of key-value pairs where values are stored as byte arrays, allowing you to pass metadata alongside the record value without modifying the payload schema.
Spring Kafka makes adding headers straightforward using `ProducerRecord` or `MessageHeaders`:

```java
ProducerRecord<String, String> record = new ProducerRecord<>("orders", "key", "val");
record.headers().add("correlation-id", "xyz-123".getBytes(StandardCharsets.UTF_8));
```

---

### Intermediate Level: Correlation Tracking & Producer Interceptors

#### Correlation IDs in Microservices
In a distributed microservice architecture, a single user transaction can trigger multiple asynchronous calls across separate message brokers. If an error occurs, searching individual log files is difficult because there is no link between the logs.
A **Correlation ID** is a unique uuid generated at the entry point of a transaction. By writing the Correlation ID onto the Kafka record headers, downstream microservices can read the header, inject it into their logging context (MDC), and print matching log tags. This allows developers to trace the complete path of a transaction across multiple services.

#### Producer Interceptors
The raw Kafka client provides the `ProducerInterceptor<K, V>` interface. It allows you to intercept and modify records globally before they leave the application:
* **`onSend(ProducerRecord<K, V> record)`**: Called inside the `.send()` thread before serialization. You can add headers, log payloads, or modify the destination topic.
* **`onAcknowledgement(RecordMetadata metadata, Exception exception)`**: Called when the broker acknowledges receipt or throws a connection error. Useful for calculating latency metrics.
* **`close()`**: Called when the producer shuts down.

```text
  [ App Code ] ──► [ KafkaTemplate.send() ] ──► [ Interceptor.onSend() ] ──► [ Serializer ] ──► [ Broker ]
```

---

### Advanced Level: Request-Reply Pattern & Message Routing

#### The Request-Reply Messaging Pattern
In synchronous systems, Services make HTTP calls and block waiting for a response. In asynchronous message systems, you can achieve a similar pattern using the **Request-Reply Pattern**.
Spring Kafka implements this using **`ReplyingKafkaTemplate`**:
1. **The Request**: The client sends a record to a `request-topic`. The record header contains a `KafkaHeaders.REPLY_TOPIC` (specifying where to send the response) and a `KafkaHeaders.CORRELATION_ID`.
2. **The Server**: The downstream processor consumes the request, does the work, reads the reply topic and correlation ID from the headers, and sends the response record containing the matching correlation ID to the reply topic.
3. **The Reply**: A background consumer in `ReplyingKafkaTemplate` listens to the reply topic, matches the correlation ID against its memory map of pending requests, and completes the client's blocking thread.

```text
  Client: [ ReplyingKafkaTemplate ] ──► (Request Topic + Correlation ID Header) ──► Server
                                                                                      │
  Client: [ Complete Future ] ◄──────── (Reply Topic + Match Correlation ID) ◄─────────┘
```

#### Message Routing & TopicNameStrategy
In complex microservices, you may want to route messages to different topics dynamically based on record contents (such as customer tier or event type).
* **`TopicNameExtractor`**: In the Processor API, you can supply a custom extractor to calculate topic names dynamically for each record.
* **TopicNameStrategy**: In Schema Registry clients, you can configure how schemas are registered in subjects (e.g., `<topic-name>-value` vs. `<record-type>-value`). Using `RecordNameStrategy` allows you to write multiple distinct event types (such as `OrderCreated` and `OrderCancelled`) to a single Kafka topic.

---

## 2. Theory & Production Best Practices

### Sync vs. Async Publishing Comparison

| Metric | Synchronous (`future.get()`) | Asynchronous (`whenComplete()`) |
| :--- | :--- | :--- |
| **Throughput** | Low (waits for round-trip latency) | Extremely High (pipelined batches) |
| **Error Handling** | Simple (try-catch blocks) | Complex (callback handlers) |
| **Latency** | High (blocks execution thread) | Low (non-blocking write) |
| **Use Case** | Financial ledger entries, configuration changes | Logging, event streams, high-volume transactions |

### Point-to-Point Messaging vs. Request-Reply

| Attribute | Point-to-Point | Request-Reply |
| :--- | :--- | :--- |
| **Coupling** | Loosely coupled (fire-and-forget) | Moderately coupled (temporal block) |
| **Implementation** | Standard `KafkaTemplate` | `ReplyingKafkaTemplate` + Reply Container |
| **Latency Cost** | None | High (double network hop + matching wait) |
| **Use Case** | Async background jobs, notifications | Asynchronous lookup services |

---

## 3. Common Errors & Troubleshooting

### 1. `ReplyTimeoutException: No reply received within timeout`
* **Symptom**: Client request fails with a timeout exception.
* **Root Cause**: The downstream processing server failed to process the request within the configured reply timeout, or did not copy the correlation ID header to the reply record.
* **Fix**:
  * Check if the downstream server is running and consuming from the request topic.
  * Ensure the server writes the matching correlation ID header back to the reply record:
    ```java
    byte[] correlationId = requestRecord.headers().lastHeader(KafkaHeaders.CORRELATION_ID).value();
    replyRecord.headers().add(KafkaHeaders.CORRELATION_ID, correlationId);
    ```

### 2. Slow Interceptors Cause Producer Thread Blockages
* **Symptom**: Throughput drops and application CPU usage spikes.
* **Root Cause**: Your custom `ProducerInterceptor.onSend()` executes blocking operations (such as making database queries or fetching HTTP client metrics) on the same thread that called `kafkaTemplate.send()`.
* **Fix**: Ensure interceptor logic is non-blocking and executes in memory.

### 3. Duplicate Topic Creation Failures in Request-Reply
* **Symptom**: Startup crashes with `TopicExistsException`.
* **Root Cause**: Multiple instances of the request-reply client try to create the same reply topic at startup using conflicting partition properties.
* **Fix**: Dedicate one instance to manage topic creations, or configure the reply topic partition count in `KafkaAdmin` config.

---

## 4. Socratic Review Questions

### Question 1
*How does `ReplyingKafkaTemplate` guarantee that a response record received on a shared reply topic is routed to the correct waiting HTTP client thread?*
* **Answer**: When `ReplyingKafkaTemplate` publishes a request, it generates a unique correlation ID and writes it to the record headers. It saves this correlation ID alongside the client's pending future callback in an internal mapping database. The template's reply consumer reads all incoming records from the reply topic, extracts the correlation ID header, looks up the future in the database, and completes that specific client's thread.

### Question 2
*Why are headers preferred over embedding metadata (like correlation IDs) directly inside the JSON record payload?*
* **Answer**: Embedding metadata in the payload forces you to modify your Avro or JSON schema definitions for every event type in the enterprise. Downstream routers and interceptors would have to fully deserialize the record bytes to inspect metadata, which consumes high CPU. Headers allow middleware components (like logging interceptors and gateways) to read tracking details without deserializing the event payload.

### Question 3
*What is the execution order of `ProducerInterceptor.onSend()`, Serializers, and Partitioners inside `KafkaTemplate`?*
* **Answer**: First, `onSend()` is invoked, allowing interceptors to inspect or modify the raw Java object record. Second, the serializers convert the Java key and value objects into raw byte arrays. Finally, the partitioner is executed on the serialized bytes to determine the destination partition index.

### Question 4
*If your application uses transactional templates, can you run a request-reply loop inside the same transaction block?*
* **Answer**: No. Transactions write records to Kafka in an uncommitted state. The downstream consumer will not read the request record until the transaction is committed, but the client thread is currently blocked inside the transaction waiting for the reply, causing a deadlock.

### Question 5
*How does `RecordNameStrategy` in Confluent Schema Registry differ from the default `TopicNameStrategy`?*
* **Answer**: `TopicNameStrategy` registers schemas using the topic name as a suffix (e.g., `orders-value`). This limits the topic to a single payload type. `RecordNameStrategy` registers schemas using the fully qualified domain name of the Java class (e.g., `com.company.OrderCreated`). This allows you to publish multiple event types to the same topic safely.

---

## 5. Hands-on Labs

### Lab 2.1 — Custom Correlation and Latency Interceptor

#### Scenario
We will create a custom `ProducerInterceptor` named `CorrelationIdInterceptor` that automatically injects a unique Correlation ID header onto outgoing records if it is missing, and calculates broker confirmation latency.

#### Complete Interceptor Java Code
Create the file [CorrelationIdInterceptor.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/interceptor/CorrelationIdInterceptor.java) with the following content:

```java
package com.springkafka.course.interceptor;

import org.apache.kafka.clients.producer.ProducerInterceptor;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.clients.producer.RecordMetadata;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.UUID;

public class CorrelationIdInterceptor implements ProducerInterceptor<String, String> {
    private static final Logger log = LoggerFactory.getLogger(CorrelationIdInterceptor.class);

    @Override
    public ProducerRecord<String, String> onSend(ProducerRecord<String, String> record) {
        // 1. Check if correlation-id header is already present
        var header = record.headers().lastHeader("correlation-id");
        if (header == null) {
            String newId = UUID.randomUUID().toString();
            // 2. Append new UUID to record headers
            record.headers().add("correlation-id", newId.getBytes(StandardCharsets.UTF_8));
            log.info("Interceptor injected new Correlation ID: {} for Topic: {}", newId, record.topic());
        }
        
        // 3. Inject send timestamp header to measure broker latency
        long sendTime = System.currentTimeMillis();
        record.headers().add("send-timestamp", String.valueOf(sendTime).getBytes(StandardCharsets.UTF_8));
        
        return record;
    }

    @Override
    public void onAcknowledgement(RecordMetadata metadata, Exception exception) {
        if (exception != null) {
            log.error("Broker delivery failure recorded in interceptor", exception);
            return;
        }

        log.info("Broker delivery success callback -> Topic: {} | Partition: {} | Offset: {}",
                metadata.topic(), metadata.partition(), metadata.offset());
    }

    @Override
    public void close() {
        log.info("Closing Correlation ID Interceptor.");
    }

    @Override
    public void configure(Map<String, ?> configs) {
        log.info("Configuring interceptor with properties map.");
    }
}
```

---

### Lab 2.2 — Add metadata and tracing headers to record

#### Scenario
We will create a helper service class named `HeaderEnrichingProducer` that uses `KafkaTemplate` to publish messages with custom metadata and tracing headers.

#### Complete Service Java Code
Create the file [HeaderEnrichingProducer.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/producer/HeaderEnrichingProducer.java) with the following content:

```java
package com.springkafka.course.producer;

import org.apache.kafka.clients.producer.ProducerRecord;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;
import java.util.UUID;

@Service
public class HeaderEnrichingProducer {
    private static final Logger log = LoggerFactory.getLogger(HeaderEnrichingProducer.class);

    private final KafkaTemplate<String, String> kafkaTemplate;

    public HeaderEnrichingProducer(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    public void sendTransaction(String key, String payload, String traceParent) {
        String topic = "payment-transactions";
        log.info("Publishing enriched record with tracing parameters to topic: {}", topic);

        // 1. Create the base ProducerRecord
        ProducerRecord<String, String> record = new ProducerRecord<>(topic, key, payload);

        // 2. Add custom business and tracing headers
        record.headers().add("traceparent", traceParent.getBytes(StandardCharsets.UTF_8));
        record.headers().add("event-id", UUID.randomUUID().toString().getBytes(StandardCharsets.UTF_8));
        record.headers().add("source-client", "spring-payment-service".getBytes(StandardCharsets.UTF_8));

        // 3. Send record asynchronously and attach callbacks
        kafkaTemplate.send(record).whenComplete((result, ex) -> {
            if (ex == null) {
                log.info("Successfully delivered payment to Partition: {}", result.getRecordMetadata().partition());
            } else {
                log.error("Failed to publish payment transaction", ex);
            }
        });
    }
}
```

---

### Lab 2.3 — Request-Reply implementation

#### Scenario
We will implement a Request-Reply pattern. We will define the Spring configurations to instantiate a `ReplyingKafkaTemplate` and a matching consumer listener container, and build a REST Controller that initiates a synchronous request-reply loop to get a validation response from our downstream processor.

#### Configuration Class
Create the file [RequestReplyConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/RequestReplyConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.apache.kafka.clients.admin.NewTopic;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.config.TopicBuilder;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.listener.ConcurrentMessageListenerContainer;
import org.springframework.kafka.requestreply.ReplyingKafkaTemplate;

import java.time.Duration;

@Configuration
public class RequestReplyConfig {

    // 1. Define the request and reply topics
    @Bean
    public NewTopic requestTopic() {
        return TopicBuilder.name("order-request-topic").partitions(3).replicas(1).build();
    }

    @Bean
    public NewTopic replyTopic() {
        return TopicBuilder.name("order-reply-topic").partitions(3).replicas(1).build();
    }

    // 2. Create the replies listener container bean
    @Bean
    public ConcurrentMessageListenerContainer<String, String> repliesContainer(
            ConcurrentKafkaListenerContainerFactory<String, String> containerFactory) {
        
        ConcurrentMessageListenerContainer<String, String> container =
                containerFactory.createContainer("order-reply-topic");
        container.getContainerProperties().setGroupId("replies-group-id");
        container.setAutoStartup(false); // Managed by the ReplyingTemplate
        return container;
    }

    // 3. Define the ReplyingKafkaTemplate bean
    @Bean
    public ReplyingKafkaTemplate<String, String, String> replyingKafkaTemplate(
            ProducerFactory<String, String> producerFactory,
            ConcurrentMessageListenerContainer<String, String> repliesContainer) {
        
        ReplyingKafkaTemplate<String, String, String> template =
                new ReplyingKafkaTemplate<>(producerFactory, repliesContainer);
        // Set default timeout of 10 seconds
        template.setDefaultReplyTimeout(Duration.ofSeconds(10));
        return template;
    }
}
```

#### REST Controller Class
Create the file [RequestReplyController.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/controller/RequestReplyController.java) with the following content:

```java
package com.springkafka.course.controller;

import org.apache.kafka.clients.producer.ProducerRecord;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.kafka.requestreply.ReplyingKafkaTemplate;
import org.springframework.kafka.requestreply.RequestReplyFuture;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@RestController
@RequestMapping("/api/orders")
public class RequestReplyController {
    private static final Logger log = LoggerFactory.getLogger(RequestReplyController.class);

    private final ReplyingKafkaTemplate<String, String, String> replyingTemplate;

    public RequestReplyController(ReplyingKafkaTemplate<String, String, String> replyingTemplate) {
        this.replyingTemplate = replyingTemplate;
    }

    @PostMapping("/validate")
    public ResponseEntity<String> validateOrder(@RequestBody String orderPayload) {
        log.info("Received order validation request REST call...");

        // 1. Create a request record targeting order-request-topic
        ProducerRecord<String, String> record = new ProducerRecord<>("order-request-topic", null, orderPayload);

        // 2. Submit request-reply loop to Kafka
        RequestReplyFuture<String, String, String> replyFuture = replyingTemplate.sendAndReceive(record);

        // 3. Block and wait for reply record from downstream processor
        try {
            var consumerRecord = replyFuture.get(); // Blocks until response arrives or timeout occurs
            String response = consumerRecord.value();
            log.info("Received validation response back from broker: {}", response);
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            log.error("Request-reply transaction failed", e);
            return ResponseEntity.status(HttpStatus.GATEWAY_TIMEOUT).body("Order validation timed out.");
        }
    }
}
```
