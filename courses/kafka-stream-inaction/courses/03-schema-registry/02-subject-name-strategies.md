# Module 02: Subject Name Strategies

Confluent Schema Registry uses **Subjects** to scope schema evolution and compatibility checks. A Subject acts as a namespace bucket for schema versions. How the Subject is named determines which topics can contain which record schemas. This module details the three subject naming strategies: `TopicNameStrategy`, `RecordNameStrategy`, and `TopicRecordNameStrategy`, explaining their architectural tradeoffs and client-side configuration.

---

## 1. The Three Subject Naming Strategies

When a producer client publishes a record, the serializer must register or fetch the schema ID from Schema Registry. The serializer calls a naming function to generate the target **Subject Name**:

```
Producer Serializer ───► SubjectNameStrategy.subjectName(...) ───► Subject Name
```

---

### 1.1 TopicNameStrategy (Default)
This strategy is the default mode. The subject name is derived strictly from the name of the topic to which the message is published.

*   **Subject Name Formats**:
    *   For record keys: `[topic-name]-key`
    *   For record values: `[topic-name]-value`
*   **Behavior**: The schema compatibility checks are bound to the specific topic.
*   **Trade-off**: This strategy enforces **single-type topics**. You cannot produce a record of a different structure (e.g., `CustomerUpdate` vs. `CustomerDelete` as raw objects) to the same topic under this strategy, as registering a different schema on the same topic-value subject will trigger a compatibility violation.

```
Topic: raw-transactions
  └── Value Subject: raw-transactions-value
        └── Version 1: Avenger Schema
        └── Version 2: Evolved Avenger Schema
```

---

### 1.2 RecordNameStrategy
This strategy derives the subject name from the fully qualified name of the serialized record class, completely ignoring the destination topic name.

*   **Subject Name Format**: `[fully-qualified-class-name]` (e.g., `bbejeck.chapter_3.avro.AvengerAvro`)
*   **Behavior**: Schema compatibility is checked globally across all topics using this record type.
*   **Trade-off**: It allows **multi-type topics**. You can produce different record types (e.g., `PlaneEvent`, `TruckEvent`, `DeliveryEvent`) to a single topic because each record maps to its own record-name subject.
*   **Risk**: Every topic across the entire enterprise cluster that uses this record class is bound to the same schema version. If you evolve the class schema in one topic, it must be backwards compatible for *every* other topic using that class.

```
Topic: raw-transactions           Topic: archive-transactions
  ├── Value: AvengerAvro    ───────┼───► Subject: bbejeck.chapter_3.avro.AvengerAvro
  └── Value: VillainAvro    ───────┼───► Subject: bbejeck.chapter_3.avro.VillainAvro
```

---

### 1.3 TopicRecordNameStrategy
This strategy merges the topic name and the fully qualified class name, providing isolated namespacing for record classes on a per-topic basis.

*   **Subject Name Formats**:
    *   For keys: `[topic-name]-[fully-qualified-class-name]`
    *   For values: `[topic-name]-[fully-qualified-class-name]`
*   **Behavior**: It allows **multi-type topics** while isolating compatibility checks to the specific topic.
*   **Use Case**: Ideal when multiple related event types are streamed to a single topic, but you want to allow different versions of those event schemas to coexist in other topics without crossing compatibilities.

```
Topic: raw-transactions
  ├── Value: AvengerAvro   ───► Subject: raw-transactions-bbejeck.chapter_3.avro.AvengerAvro
  └── Value: VillainAvro   ───► Subject: raw-transactions-bbejeck.chapter_3.avro.VillainAvro
```

---

## 2. Java Client Configurations

To override the default `TopicNameStrategy`, configure the appropriate strategy class in the producer and consumer properties:

### 2.1 Producer Configuration Example (Avro)
```java
import io.confluent.kafka.serializers.AbstractKafkaSchemaSerDeConfig;
import io.confluent.kafka.serializers.KafkaAvroSerializer;
import io.confluent.kafka.serializers.subject.RecordNameStrategy;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringSerializer;

import java.util.Properties;

public class CustomStrategyProducer {
    public static Properties createConfig() {
        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        
        // Use Schema Registry Serializer for Value
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, KafkaAvroSerializer.class.getName());
        props.put(AbstractKafkaSchemaSerDeConfig.SCHEMA_REGISTRY_URL_CONFIG, "http://localhost:8081");
        
        // Configure RecordNameStrategy for Value Serde
        props.put(AbstractKafkaSchemaSerDeConfig.VALUE_SUBJECT_NAME_STRATEGY, RecordNameStrategy.class.getName());
        
        return props;
    }
}
```

### 2.2 Consumer Configuration Example (Avro)
```java
import io.confluent.kafka.serializers.AbstractKafkaSchemaSerDeConfig;
import io.confluent.kafka.serializers.KafkaAvroDeserializer;
import io.confluent.kafka.serializers.KafkaAvroDeserializerConfig;
import io.confluent.kafka.serializers.subject.RecordNameStrategy;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.common.serialization.StringDeserializer;

import java.util.Properties;

public class CustomStrategyConsumer {
    public static Properties createConfig() {
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "record-name-strategy-group");
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        
        // Use Schema Registry Deserializer for Value
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, KafkaAvroDeserializer.class.getName());
        props.put(AbstractKafkaSchemaSerDeConfig.SCHEMA_REGISTRY_URL_CONFIG, "http://localhost:8081");
        
        // Configure RecordNameStrategy for Value Deserializer
        props.put(AbstractKafkaSchemaSerDeConfig.VALUE_SUBJECT_NAME_STRATEGY, RecordNameStrategy.class.getName());
        
        // Return Specific Avro Type rather than GenericRecord
        props.put(KafkaAvroDeserializerConfig.SPECIFIC_AVRO_READER_CONFIG, "true");
        
        return props;
    }
}
```

---

## 3. Architectural Summary Matrix

| Strategy | Multiple Types per Topic? | Schema Isolation Scope | Subject Naming Function |
| :--- | :---: | :--- | :--- |
| **`TopicNameStrategy`** | No | Topic | `topic-name + ("-key" or "-value")` |
| **`RecordNameStrategy`** | Yes | Global (All Topics) | `fully-qualified-class-name` |
| **`TopicRecordNameStrategy`** | Yes | Topic + Class | `topic-name + "-" + fully-qualified-class-name` |
