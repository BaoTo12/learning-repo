# Module 04: Serialization & Schema Registry Integration

At its core, Apache Kafka operates entirely on raw byte arrays. For your Kafka Streams application to process records, it must deserialize incoming bytes into Java objects and serialize those objects back into bytes before writing them to output topics.

This module details how serialization works in Kafka Streams, how to construct custom Serdes, and how to integrate Confluent Schema Registry for robust, schema-validated event streaming.

---

## 1. The Serde Lifecycle

A **Serde** (Serializer/Deserializer) is a wrapper class that groups together a `Serializer` and a `Deserializer` for a specific data type. 

Rather than requiring you to supply four separate parameters (key serializer, value serializer, key deserializer, value deserializer) for every topology operator, the Kafka Streams DSL uses Serde instances.

### 1.1 Standard Built-In Serdes
The `org.apache.kafka.common.serialization.Serdes` factory class provides built-in Serde implementations for standard Java primitives:
*   `Serdes.String()`
*   `Serdes.Long()`
*   `Serdes.Integer()`
*   `Serdes.Double()`
*   `Serdes.Bytes()`
*   `Serdes.UUID()`

---

## 2. Developing Custom Serdes

For proprietary or complex domain objects (such as POJOs, Protocol Buffers, or Jackson-mapped models), you must write a custom Serde.

### 2.1 The Jackson JSON Serde Pattern
You can construct a generic JSON Serde using Jackson for serialization and deserialization.

#### Custom Serializer:
```java
package com.enterprise.streams.serde;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.common.serialization.Serializer;

import java.util.Map;

public class JsonSerializer<T> implements Serializer<T> {
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public void configure(Map<String, ?> configs, boolean isKey) {}

    @Override
    public byte[] serialize(String topic, T data) {
        if (data == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsBytes(data);
        } catch (Exception e) {
            throw new RuntimeException("Failed to serialize object to JSON bytes", e);
        }
    }

    @Override
    public void close() {}
}
```

#### Custom Deserializer:
```java
package com.enterprise.streams.serde;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.common.serialization.Deserializer;

import java.util.Map;

public class JsonDeserializer<T> implements Deserializer<T> {
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final Class<T> targetClass;

    public JsonDeserializer(Class<T> targetClass) {
        this.targetClass = targetClass;
    }

    @Override
    public void configure(Map<String, ?> configs, boolean isKey) {}

    @Override
    public T deserialize(String topic, byte[] data) {
        if (data == null) {
            return null;
        }
        try {
            return objectMapper.readValue(data, targetClass);
        } catch (Exception e) {
            throw new RuntimeException("Failed to deserialize JSON bytes to target object", e);
        }
    }

    @Override
    public void close() {}
}
```

#### Constructing the Custom Serde:
Combine the serializer and deserializer using `Serdes.serdeFrom(...)`:
```java
package com.enterprise.streams.serde;

import org.apache.kafka.common.serialization.Serde;
import org.apache.kafka.common.serialization.Serdes;

public class CustomSerdes {
    public static <T> Serde<T> jsonSerdeFor(Class<T> clazz) {
        return Serdes.serdeFrom(new JsonSerializer<>(), new JsonDeserializer<>(clazz));
    }
}
```

---

## 3. Schema Registry Integration

In production microservices, data schemas evolve over time. If a fields type changes or fields are deleted, downstream consumer applications can crash. **Confluent Schema Registry** acts as a centralized server that stores schemas, enforces compatibility rules (Backward, Forward, Full), and prevents invalid data from entering Kafka.

Confluent provides Schema Registry-aware Serdes (e.g., `KafkaAvroSerde`, `KafkaProtobufSerde`, `KafkaJsonSchemaSerde`) that register schemas and deserialize dynamically.

### 3.1 Initializing a Schema Registry-Aware Serde (Protobuf Example)
To configure a Schema Registry Serde:
1.  Instantiate the registry-specific Serde class.
2.  Populate a configuration map with the `schema.registry.url`.
3.  Configure the Serde instance.

```java
package com.enterprise.streams.registry;

import io.confluent.kafka.serializers.AbstractKafkaSchemaSerDeConfig;
import io.confluent.kafka.streams.serdes.protobuf.KafkaProtobufSerde;
import org.apache.kafka.common.serialization.Serde;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KStream;
import com.enterprise.models.protobuf.PurchaseOuterClass.Purchase; // Generated Protobuf Class

import java.util.HashMap;
import java.util.Map;

public class RegistrySerdeBuilder {

    public KStream<String, Purchase> buildRegistryStream(StreamsBuilder builder, String schemaRegistryUrl) {
        // 1. Create the Schema Registry-aware Protobuf Serde
        KafkaProtobufSerde<Purchase> protobufSerde = new KafkaProtobufSerde<>();

        // 2. Configure the Serde with the Schema Registry URL
        Map<String, Object> serdeConfig = new HashMap<>();
        serdeConfig.put(AbstractKafkaSchemaSerDeConfig.SCHEMA_REGISTRY_URL_CONFIG, schemaRegistryUrl);
        
        // false indicates this Serde is used for record values (not keys)
        protobufSerde.configure(serdeConfig, false);

        // 3. Use the Serde in the stream consumption operator
        return builder.stream(
                "transactions-protobuf",
                Consumed.with(org.apache.kafka.common.serialization.Serdes.String(), protobufSerde)
        );
    }
}
```

### 3.2 Key Configurations for Schema Registry Serdes
*   **`schema.registry.url`**: Location of the Schema Registry endpoint (e.g., `http://localhost:8081`).
*   **`auto.register.schemas`** (Default: `true`): If `true`, the serializer registers new schema versions automatically. Set this to `false` in production environments so that schemas must be explicitly registered via CI/CD, preventing accidental schema registrations.
*   **`use.latest.version`** (Default: `false`): If `true`, checks against the latest schema version registered in the registry instead of looking up by exact ID match.

> [!CAUTION]
> Because Kafka Streams runs embedded client instances under the hood, the same schema evolution and compatibility rules apply. If you mutate a schema structure in an upstream application, ensure the schema compatibility settings (e.g. `BACKWARD`) allow downstream Kafka Streams tasks to continue deserializing the historical partitions without throwing runtime exceptions.
