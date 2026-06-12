# Module 05: Raw Serdes & Custom Serializers

While Confluent Schema Registry provides data governance, there are cases—such as simple internal prototypes, legacy environments, or restricted network configurations—where you need to serialize and deserialize messages without an external registry. This module demonstrates how to implement custom serializers and deserializers in Java by implementing Kafka's raw client interfaces and utilizing the Jackson library.

---

## 1. Custom Serializer Implementation

To serialize Java objects to JSON byte arrays without a registry, implement the `org.apache.kafka.common.serialization.Serializer` interface.

```java
package bbejeck.serializers;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.common.errors.SerializationException;
import org.apache.kafka.common.serialization.Serializer;

import java.util.Map;

/**
 * A generic JSON Serializer that converts Java POJOs into byte arrays using Jackson.
 *
 * @param <T> The class type to serialize.
 */
public class JacksonSerializer<T> implements Serializer<T> {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public void configure(Map<String, ?> configs, boolean isKey) {
        // Optional initialization logic. Called during client bootstrap.
    }

    @Override
    public byte[] serialize(String topic, T data) {
        if (data == null) {
            return null;
        }
        try {
            // Convert POJO object to serialized JSON byte array
            return objectMapper.writeValueAsBytes(data);
        } catch (JsonProcessingException e) {
            throw new SerializationException("Error serializing JSON payload for topic: " + topic, e);
        }
    }

    @Override
    public void close() {
        // Cleanup resources if necessary. Called during client shutdown.
    }
}
```

---

## 2. Custom Deserializer Implementation

To convert JSON byte arrays back into typed Java objects, implement the `org.apache.kafka.common.serialization.Deserializer` interface.

```java
package bbejeck.serializers;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.common.errors.SerializationException;
import org.apache.kafka.common.serialization.Deserializer;

import java.io.IOException;
import java.util.Map;

/**
 * A generic JSON Deserializer that converts JSON byte arrays back into typed Java POJOs.
 *
 * @param <T> The target class type to deserialize into.
 */
public class JacksonDeserializer<T> implements Deserializer<T> {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private Class<T> targetClass;

    @SuppressWarnings("unchecked")
    @Override
    public void configure(Map<String, ?> configs, boolean isKey) {
        // Extract the target class type dynamically from configuration if required,
        // or configure default mappings.
        String classConfigKey = isKey ? "json.key.class" : "json.value.class";
        String className = (String) configs.get(classConfigKey);
        try {
            if (className != null) {
                this.targetClass = (Class<T>) Class.forName(className);
            }
        } catch (ClassNotFoundException e) {
            throw new SerializationException("Target class " + className + " not found for deserializer", e);
        }
    }

    @Override
    public T deserialize(String topic, byte[] data) {
        if (data == null) {
            return null;
        }
        if (targetClass == null) {
            throw new SerializationException("Target class not configured for JacksonDeserializer");
        }
        try {
            // Convert JSON byte array back to Java object instance
            return objectMapper.readValue(data, targetClass);
        } catch (IOException e) {
            throw new SerializationException("Error deserializing payload on topic: " + topic, e);
        }
    }

    @Override
    public void close() {
        // Cleanup resources
    }
}
```

---

## 3. Configuring Java Clients with Custom Serdes

When configuring the Kafka clients, supply the fully qualified class names of your custom classes to the serializer or deserializer configuration parameters.

### 3.1 Producer Setup
```java
Properties props = new Properties();
props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());

// Configure custom JacksonSerializer for the record value
props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JacksonSerializer.class.getName());
```

### 3.2 Consumer Setup
```java
Properties props = new Properties();
props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
props.put(ConsumerConfig.GROUP_ID_CONFIG, "jackson-consumer-group");
props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());

// Configure custom JacksonDeserializer for the record value
props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, JacksonDeserializer.class.getName());

// Supply the target class mapping configuration for the deserializer
props.put("json.value.class", "bbejeck.chapter_3.json.SimpleAvenger");
```

---

## 4. Comparison: With vs. Without Schema Registry

| Architectural Dimension | Custom Jackson Serde (No Registry) | Schema Registry (Avro / Protobuf) |
| :--- | :--- | :--- |
| **Data Governance** | None. Any client can write any JSON structure, risking consumer failures. | High. Enforces compatibility contracts at the producer boundary. |
| **Payload Size** | Larger. JSON field names are stored as strings in every message payload. | Small. Payload contains only binary data, mapped to a 4-byte Schema ID. |
| **Integration** | Difficult to map to streaming engines (like ksqlDB or external Connect sinks) without writing custom conversion code. | Seamless. Out-of-the-box support for Kafka Streams, Connect, and ksqlDB. |
| **Setup Overhead** | Extremely low. Requires no external services or network lookups. | Moderate. Requires deploying and maintaining the Schema Registry. |
