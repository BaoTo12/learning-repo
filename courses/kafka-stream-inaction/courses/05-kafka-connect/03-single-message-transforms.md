# Module 03: Single Message Transforms (SMTs) & Custom SMTs

In event-driven pipelines, incoming data frequently requires lightweight modifications before being written to Kafka (on the source side) or sent to target datastores (on the sink side). Rather than deploying a full-fledged streaming application (like Kafka Streams or ksqlDB) for simple field changes, Apache Kafka Connect provides **Single Message Transforms (SMTs)**.

This module details SMT behaviors, chaining configurations, performance trade-offs, and how to write a custom transformation plugin in Java.

---

## 1. What are Single Message Transforms?

SMTs are lightweight data manipulation plugins that execute on individual records in-flight. They sit between the connector task and the serialization converter.

*   **Source SMT Execution**: Executes after the connector task produces a record, but *before* the converter serializes it to bytes.
*   **Sink SMT Execution**: Executes after the converter deserializes bytes into Connect objects, but *before* the sink task writes to the target system.

```
[Source Task] ──► [ SMT (e.g., MaskField) ] ──► [ Converter (Avro/JSON) ] ──► [ Kafka Topic ]
                                                                                   │
[Sink Task]   ◄── [ SMT (e.g., Cast) ]      ◄── [ Converter (Avro/JSON) ] ◄────────┘
```

### 1.1 Out-of-the-Box Transforms
Confluent and Apache Kafka bundle several common SMTs:
*   **`ValueToKey`**: Copies fields from the record value into the record key (resulting in a Struct key).
*   **`ExtractField`**: Extracts a single field from a Struct or Map and overrides the whole key or value with that primitive.
*   **`MaskField`**: Replaces the value of a target field with a replacement mask (e.g., replacing a Social Security Number with `xxx-xx-xxxx`).
*   **`Cast`**: Converts field types (e.g., casting a String to an Integer).
*   **`ReplaceField`**: Renames or drops fields from a record.

---

## 2. Configuring SMT Chains

You can chain multiple SMTs together in a JSON configuration using a comma-separated list. **The order of SMT declaration determines execution order.**

### 2.1 The Struct-Key Extraction Pattern
When using `ValueToKey` to copy a key field (e.g., `user_name`) from a record's value to its key, the resulting key is a Struct:
`Struct{"user_name" : "artv"}`

To make the key a primitive value (e.g. just `"artv"`), you must immediately follow it with an `ExtractField` transform targeting the key.

#### Configuration Example:
```json
{
  "connector.class": "io.confluent.connect.jdbc.JdbcSourceConnector",
  "tasks.max": "1",
  
  "transforms": "copyFieldToKey,extractKeyFromStruct,maskSsn",
  
  "transforms.copyFieldToKey.type": "org.apache.kafka.connect.transforms.ValueToKey",
  "transforms.copyFieldToKey.fields": "user_name",
  
  "transforms.extractKeyFromStruct.type": "org.apache.kafka.connect.transforms.ExtractField$Key",
  "transforms.extractKeyFromStruct.field": "user_name",
  
  "transforms.maskSsn.type": "org.apache.kafka.connect.transforms.MaskField$Value",
  "transforms.maskSsn.fields": "ssn",
  "transforms.maskSsn.replacement": "xxx-xx-xxxx"
}
```

> [!IMPORTANT]
> To apply a transform to a key or a value, append **`$Key`** or **`$Value`** to the transform class name in the `.type` configuration.

### 2.2 Performance Trade-offs of SMT Chaining
Because SMTs run in-line in the connector task's processing threads:
*   **Latency Overhead**: Every added SMT adds CPU overhead. Deep chains (e.g., >3 SMTs) can reduce connector throughput.
*   **No Aggregations/Joins**: SMTs operate on *one record at a time*. They cannot perform lookups, join against other topics, or compute windowed aggregations.
*   **When to transition to Kafka Streams**: If your transformation logic requires referencing external data, joining topics, tracking state, or executing more than 3 distinct SMT steps, route the raw records to Kafka and use Kafka Streams for transformation.

---

## 3. Developing a Custom SMT

When standard SMTs cannot meet your requirements (e.g., extracting multiple specific fields, executing cryptographic hashing, or stripping HTML tags), you can write a custom transform plugin by implementing `org.apache.kafka.connect.transforms.Transformation`.

### 3.1 Implementing Key/Value Target Isolation
To allow configuration of the SMT for either keys or values, the standard pattern is to:
1.  Define an abstract parent class containing the transformation logic.
2.  Expose three abstract methods (`operatingSchema`, `operatingValue`, `newRecord`).
3.  Implement two static nested classes (`Key` and `Value`) that implement these abstract overrides.

### 3.2 Schema Cache
If a record contains an embedded schema (`schemas.enable=true`), you must update the `Schema` object. Rebuilding `Schema` objects repeatedly is highly CPU-intensive. To prevent this, use a schema cache (e.g. Confluent's `SimpleHeaderCache` or a bounded `LinkedHashMap`) to reuse previously modified schemas.

### 3.3 Custom Multi-Field Extractor Implementation

Below is a complete implementation of a custom SMT (`MultiFieldExtract`) that filters and retains only the fields specified in a comma-separated list.

```java
package com.enterprise.connect.transforms;

import org.apache.kafka.common.cache.Cache;
import org.apache.kafka.common.cache.LRUCache;
import org.apache.kafka.common.cache.SynchronizedCache;
import org.apache.kafka.common.config.ConfigDef;
import org.apache.kafka.connect.connector.ConnectRecord;
import org.apache.kafka.connect.data.Field;
import org.apache.kafka.connect.data.Schema;
import org.apache.kafka.connect.data.SchemaBuilder;
import org.apache.kafka.connect.data.Struct;
import org.apache.kafka.connect.transforms.Transformation;
import org.apache.kafka.connect.transforms.util.SimpleConfig;

import java.util.*;

public abstract class MultiFieldExtract<R extends ConnectRecord<R>> implements Transformation<R> {

    public static final String FIELDS_CONFIG = "fields";
    public static final ConfigDef CONFIG_DEF = new ConfigDef()
            .define(FIELDS_CONFIG, ConfigDef.Type.LIST, ConfigDef.Importance.HIGH, "Fields to extract and retain");

    private Set<String> fieldNamesToExtract;
    private Cache<Schema, Schema> schemaUpdateCache;

    @Override
    public void configure(Map<String, ?> configs) {
        SimpleConfig config = new SimpleConfig(CONFIG_DEF, configs);
        this.fieldNamesToExtract = new HashSet<>(config.getList(FIELDS_CONFIG));
        this.schemaUpdateCache = new SynchronizedCache<>(new LRUCache<>(64));
    }

    @Override
    public R apply(R record) {
        if (operatingValue(record) == null) {
            return record; // Handle tombstone/null records
        }

        if (operatingSchema(record) == null) {
            return applySchemaless(record);
        } else {
            return applyWithSchema(record);
        }
    }

    private R applySchemaless(R record) {
        Object value = operatingValue(record);
        if (!(value instanceof Map)) {
            throw new IllegalArgumentException("Schemaless records must be represented as Maps");
        }

        @SuppressWarnings("unchecked")
        Map<String, Object> originalMap = (Map<String, Object>) value;
        Map<String, Object> newMap = new LinkedHashMap<>();

        for (String fieldName : fieldNamesToExtract) {
            if (originalMap.containsKey(fieldName)) {
                newMap.put(fieldName, originalMap.get(fieldName));
            }
        }

        return newRecord(record, null, newMap);
    }

    private R applyWithSchema(R record) {
        Object value = operatingValue(record);
        if (!(value instanceof Struct)) {
            throw new IllegalArgumentException("Schema-based records must be represented as Structs");
        }

        Struct struct = (Struct) value;
        Schema originalSchema = struct.schema();

        // Retrieve or build the updated schema from cache
        Schema updatedSchema = schemaUpdateCache.get(originalSchema);
        if (updatedSchema == null) {
            updatedSchema = makeUpdatedSchema(originalSchema);
            schemaUpdateCache.put(originalSchema, updatedSchema);
        }

        Struct updatedStruct = new Struct(updatedSchema);
        for (Field field : updatedSchema.fields()) {
            updatedStruct.put(field.name(), struct.get(field.name()));
        }

        return newRecord(record, updatedSchema, updatedStruct);
    }

    private Schema makeUpdatedSchema(Schema originalSchema) {
        SchemaBuilder builder = SchemaBuilder.struct().name(originalSchema.name());
        if (originalSchema.isOptional()) {
            builder.optional();
        }

        for (Field field : originalSchema.fields()) {
            if (fieldNamesToExtract.contains(field.name())) {
                builder.field(field.name(), field.schema());
            }
        }
        return builder.build();
    }

    @Override
    public ConfigDef config() {
        return CONFIG_DEF;
    }

    @Override
    public void close() {
        schemaUpdateCache = null;
    }

    // Abstract methods overridden by Key/Value implementations
    protected abstract Schema operatingSchema(R record);
    protected abstract Object operatingValue(R record);
    protected abstract R newRecord(R record, Schema newSchema, Object newValue);

    // Inner class targeting the record key
    public static class Key<R extends ConnectRecord<R>> extends MultiFieldExtract<R> {
        @Override
        protected Schema operatingSchema(R record) { return record.keySchema(); }
        @Override
        protected Object operatingValue(R record) { return record.key(); }
        @Override
        protected R newRecord(R record, Schema newSchema, Object newValue) {
            return record.newRecord(record.topic(), record.kafkaPartition(), newSchema, newValue, record.valueSchema(), record.value(), record.timestamp());
        }
    }

    // Inner class targeting the record value
    public static class Value<R extends ConnectRecord<R>> extends MultiFieldExtract<R> {
        @Override
        protected Schema operatingSchema(R record) { return record.valueSchema(); }
        @Override
        protected Object operatingValue(R record) { return record.value(); }
        @Override
        protected R newRecord(R record, Schema newSchema, Object newValue) {
            return record.newRecord(record.topic(), record.kafkaPartition(), record.keySchema(), record.key(), newSchema, newValue, record.timestamp());
        }
    }
}
```

#### Configuring the Custom SMT in properties/JSON:
Once compiled into a JAR and placed in the worker's `plugin.path`, configure the custom SMT like so:
```json
"transforms": "filterFields",
"transforms.filterFields.type": "com.enterprise.connect.transforms.MultiFieldExtract$Value",
"transforms.filterFields.fields": "symbol,price,timestamp"
```
