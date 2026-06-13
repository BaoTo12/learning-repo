# Module 07: Programmatic Management & Multi-Event Clients

To automate deployments and build resilient processing nodes, applications can manage cluster resources using the `Admin` API. In addition, when applications consume topics containing multiple event types (e.g., Avro unions or Protobuf oneofs), clients must safely inspect and cast payloads. This module provides complete Java implementations for programmatic topic management and multi-type payload parsing.

---

## 1. Programmatic Cluster Administration with the `Admin` API

The `org.apache.kafka.clients.admin.Admin` interface allows developers to inspect brokers, create and delete topics, alter configurations, and query consumer group offsets programmatically.

Below is a utility class demonstrating programmatic topic creation and cleanup:

```java
package bbejeck.chapter_4.admin;

import org.apache.kafka.clients.admin.Admin;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.CreateTopicsResult;
import org.apache.kafka.clients.admin.NewTopic;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;
import java.util.concurrent.ExecutionException;

public class TopicAdministrator implements AutoCloseable {

    private static final Logger LOG = LoggerFactory.getLogger(TopicAdministrator.class);
    private final Admin admin;

    public TopicAdministrator(String bootstrapServers) {
        Properties config = new Properties();
        config.put(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        this.admin = Admin.create(config);
    }

    public void createTopics(List<NewTopic> newTopics) {
        CreateTopicsResult result = admin.createTopics(newTopics);
        try {
            // Block until all topic creations are completed on the cluster
            result.all().get();
            LOG.info("Successfully created topics: {}", newTopics);
        } catch (InterruptedException | ExecutionException e) {
            LOG.error("Failed to create topics programmatically", e);
            throw new RuntimeException("Topic creation failed", e);
        }
    }

    public void deleteTopics(List<String> topicNames) {
        try {
            admin.deleteTopics(topicNames).all().get();
            LOG.info("Successfully deleted topics: {}", topicNames);
        } catch (InterruptedException | ExecutionException e) {
            LOG.error("Failed to delete topics", e);
            throw new RuntimeException("Topic deletion failed", e);
        }
    }

    public Set<String> listTopicNames() {
        try {
            return admin.listTopics().names().get();
        } catch (InterruptedException | ExecutionException e) {
            throw new RuntimeException("Failed to list topics", e);
        }
    }

    @Override
    public void close() {
        if (admin != null) {
            admin.close();
        }
    }
}
```

---

## 2. Consuming Multiple Event Types from a Single Topic

When streaming multiple related events (e.g., `LoginEvent`, `SearchEvent`, `PurchaseEvent`) in a single topic partition to guarantee chronological ordering, the consumer must dynamically resolve the payload type.

---

### 2.1 The Protocol Buffers `oneof` Switch Pattern
Protobuf enforces type safety by wrapping multiple types inside an outer container message. The compiler generates an enum case that allows you to evaluate the payload type cleanly:

```java
package bbejeck.chapter_4.sales;

import bbejeck.chapter_4.proto.Events; // Outer Protobuf wrapper
import bbejeck.chapter_4.proto.LoginEvent;
import bbejeck.chapter_4.proto.PurchaseEvent;
import bbejeck.chapter_4.proto.SearchEvent;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.serialization.StringDeserializer;
import io.confluent.kafka.serializers.KafkaProtobufDeserializer;
import io.confluent.kafka.serializers.KafkaProtobufDeserializerConfig;

import java.time.Duration;
import java.util.Collections;
import java.util.Properties;

public class ProtobufMultiEventConsumer {

    public void consume(String bootstrapServers, String topic) {
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "proto-multi-consumer-group");
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        
        // Use Protobuf Deserializer and configure the target wrapper class
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, KafkaProtobufDeserializer.class.getName());
        props.put(KafkaProtobufDeserializerConfig.SPECIFIC_PROTOBUF_VALUE_TYPE, Events.class.getName());
        props.put("schema.registry.url", "http://localhost:8081");

        try (KafkaConsumer<String, Events> consumer = new KafkaConsumer<>(props)) {
            consumer.subscribe(Collections.singletonList(topic));

            while (true) {
                ConsumerRecords<String, Events> records = consumer.poll(Duration.ofSeconds(5));
                for (ConsumerRecord<String, Events> record : records) {
                    Events outerEvent = record.value();

                    // Evaluate type using Protobuf Case enum
                    switch (outerEvent.getTypeCase()) {
                        case LOGIN_EVENT -> handleLogin(outerEvent.getLoginEvent());
                        case SEARCH_EVENT -> handleSearch(outerEvent.getSearchEvent());
                        case PURCHASE_EVENT -> handlePurchase(outerEvent.getPurchaseEvent());
                        case TYPE_NOT_SET -> throw new IllegalStateException("Event payload type not set");
                    }
                }
            }
        }
    }

    private void handleLogin(LoginEvent event) { /* ... */ }
    private void handleSearch(SearchEvent event) { /* ... */ }
    private void handlePurchase(PurchaseEvent event) { /* ... */ }
}
```

---

### 2.2 The Apache Avro Union Instance Checking Pattern
Avro does not use wrapper classes for unions; instead, the generated classes implement the `SpecificRecord` interface. The consumer uses Java pattern matching (`instanceof`) to cast the records dynamically:

```java
package bbejeck.chapter_4.sales;

import bbejeck.chapter_3.avro.PlaneEvent;
import bbejeck.chapter_3.avro.TruckEvent;
import bbejeck.chapter_3.avro.DeliveryEvent;
import org.apache.avro.specific.SpecificRecord;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.serialization.StringDeserializer;
import io.confluent.kafka.serializers.KafkaAvroDeserializer;
import io.confluent.kafka.serializers.KafkaAvroDeserializerConfig;

import java.time.Duration;
import java.util.Collections;
import java.util.Properties;

public class AvroMultiEventConsumer {

    public void consume(String bootstrapServers, String topic) {
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "avro-multi-consumer-group");
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        
        // Configure Avro Specific Reader
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, KafkaAvroDeserializer.class.getName());
        props.put(KafkaAvroDeserializerConfig.SPECIFIC_AVRO_READER_CONFIG, "true");
        props.put("schema.registry.url", "http://localhost:8081");

        try (KafkaConsumer<String, SpecificRecord> consumer = new KafkaConsumer<>(props)) {
            consumer.subscribe(Collections.singletonList(topic));

            while (true) {
                ConsumerRecords<String, SpecificRecord> records = consumer.poll(Duration.ofSeconds(5));
                for (ConsumerRecord<String, SpecificRecord> record : records) {
                    SpecificRecord value = record.value();

                    // Modern Java Pattern Matching (instanceof check + auto-casting)
                    if (value instanceof PlaneEvent planeEvent) {
                        handlePlane(planeEvent);
                    } else if (value instanceof TruckEvent truckEvent) {
                        handleTruck(truckEvent);
                    } else if (value instanceof DeliveryEvent deliveryEvent) {
                        handleDelivery(deliveryEvent);
                    } else {
                        throw new IllegalArgumentException("Unknown record class: " + value.getClass().getName());
                    }
                }
            }
        }
    }

    private void handlePlane(PlaneEvent event) { /* ... */ }
    private void handleTruck(TruckEvent event) { /* ... */ }
    private void handleDelivery(DeliveryEvent event) { /* ... */ }
}
```
