# Module 01: Spring Consumers & Producers

Spring Boot removes the boilerplate of manually instantiating and lifecycle-managing Kafka consumers and producers. By leveraging annotations like `@KafkaListener` and classes like `KafkaTemplate`, developers can easily build high-performance, message-driven Java applications.

This module details how to consume and produce messages using Spring Kafka, how to extract record metadata, and how to scale consumption using concurrency controls.

---

## 1. Spring Boot Auto-Configuration & properties

Spring Boot uses **Convention over Configuration**. By defining configurations in the `application.properties` (or `application.yml`) file, Spring Boot automatically instantiates the required producer and consumer factories.

```properties
# application.properties
spring.kafka.bootstrap-servers=localhost:9092
spring.kafka.consumer.group-id=loan-processing-group
spring.kafka.consumer.key-deserializer=org.apache.kafka.common.serialization.StringDeserializer
spring.kafka.consumer.value-deserializer=org.springframework.kafka.support.serializer.JsonDeserializer
spring.kafka.consumer.properties.spring.json.trusted.packages=*

spring.kafka.producer.key-serializer=org.apache.kafka.common.serialization.StringSerializer
spring.kafka.producer.value-serializer=org.springframework.kafka.support.serializer.JsonSerializer
```

---

## 2. Consuming Messages with `@KafkaListener`

### A. Method-Level Listener
To consume records, annotate a method with `@KafkaListener`. Spring automatically runs a listener container wrapping a `KafkaConsumer` in the background:

```java
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.stereotype.Component;

@Component
public class LoanProcessor {

    @KafkaListener(
        topics = "${loan.app.input.topic}",
        groupId = "${application.group}"
    )
    public void processLoan(
        LoanApplication loanApplication,
        @Header(KafkaHeaders.RECEIVED_MESSAGE_KEY) String key,
        @Header(KafkaHeaders.RECEIVED_TIMESTAMP) long timestamp,
        @Header(KafkaHeaders.RECEIVED_PARTITION) int partition
    ) {
        System.out.printf("Received Loan Application %s (Key: %s) on Partition: %d%n",
            loanApplication.getId(), key, partition);
        
        // Execute business logic...
    }
}
```

### B. Class-Level Listener (Consuming Multiple Types)
When a single topic contains multiple distinct record types, you can place `@KafkaListener` at the class level and annotate individual handler methods with `@KafkaHandler`. Spring will inspect the payload type and route it to the matching handler:

```java
import org.springframework.kafka.annotation.KafkaHandler;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
@KafkaListener(topics = "multi-type-topic", groupId = "multi-type-group")
public class MultiTypeEventListener {

    @KafkaHandler
    public void handleStringEvent(String stringPayload) {
        System.out.println("Processing string: " + stringPayload);
    }

    @KafkaHandler
    public void handleLongEvent(Long longPayload) {
        System.out.println("Processing long: " + longPayload);
    }

    @KafkaHandler(isDefault = true)
    public void handleDefault(Object unknownPayload) {
        System.out.println("Unknown event format: " + unknownPayload.toString());
    }
}
```

---

## 3. Producing Messages with `KafkaTemplate`

`KafkaTemplate` wraps the native `KafkaProducer`, offering high-level send overloads. Because the native producer is thread-safe, `KafkaTemplate` is also fully thread-safe and can be shared globally.

### Asynchronous Sends & Non-Blocking Callbacks
To prevent blocking the application thread, handle the send result asynchronously using the returned `CompletableFuture` (or `ListenableFuture` in older versions):

```java
import org.apache.kafka.clients.producer.RecordMetadata;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Component;
import java.util.concurrent.CompletableFuture;

@Component
public class LoanResultPublisher {

    private final KafkaTemplate<String, LoanApplication> kafkaTemplate;

    @Autowired
    public LoanResultPublisher(KafkaTemplate<String, LoanApplication> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    public void publish(String topic, String key, LoanApplication application) {
        CompletableFuture<SendResult<String, LoanApplication>> future = 
            kafkaTemplate.send(topic, key, application);

        // Async callback without blocking the main worker thread
        future.whenComplete((result, ex) -> {
            if (ex == null) {
                RecordMetadata metadata = result.getRecordMetadata();
                System.out.printf("Produced record to topic %s, Partition %d, Offset %d%n",
                    metadata.topic(), metadata.partition(), metadata.offset());
            } else {
                System.err.println("Failed to publish record: " + ex.getMessage());
            }
        });
    }
}
```

---

## 4. Scaling Consumption: Concurrency & Thread Safety

### A. Tuning Concurrency
By default, `@KafkaListener` spawns a container running a single thread with one consumer. If your topic has multiple partitions, this thread consumes from all partitions sequentially.

To scale throughput, configure **concurrency** to spin up multiple consumer threads. Optimally, set concurrency equal to the number of partitions in the topic:

#### Option 1: properties Configuration
```properties
spring.kafka.listener.concurrency=3
```

#### Option 2: Programmatic Bean Setup
```java
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;

@Configuration
public class KafkaConsumerConfig {

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, LoanApplication> kafkaListenerContainerFactory(
            ConsumerFactory<String, LoanApplication> consumerFactory) {
        
        ConcurrentKafkaListenerContainerFactory<String, LoanApplication> factory = 
            new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory);
        
        // Match the number of topic partitions to run a thread-per-partition
        factory.setConcurrency(3); 
        
        return factory;
    }
}
```

### B. Thread Safety Guarantees
* **Partition Pinning**: When concurrency is enabled, each consumer thread is pinned to specific partitions. The order of messages within a partition is preserved.
* **Stateless Listeners**: Since multiple listener threads execute the listener method concurrently, the listener class **must be stateless**. Avoid mutable instance fields; local variables are stack-bound and thread-safe.
