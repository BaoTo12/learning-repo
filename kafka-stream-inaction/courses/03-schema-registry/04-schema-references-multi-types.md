# Module 04: Schema References & Multi-Event Topics

To minimize duplication and enforce modular code structures, Kafka applications can use **Schema References** to import and reuse nested schema definitions. In addition, references enable streaming multiple related event types into a single topic in a controlled manner. This module details how to structure references across Avro, Protobuf, and JSON Schema, registers them sequentially in Gradle, and configures producer clients to publish multi-type payloads safely.

---

## 1. Structuring Schema References

References allow one schema definition (the **referrer**) to depend on another registered schema (the **referee**).

---

### 1.1 Apache Avro References
In Avro, nested records are referenced by using their fully qualified name string as the field type.

#### 1. Referee Schema (`person.avsc`)
```json
{
  "type": "record",
  "namespace": "bbejeck.chapter_3.avro",
  "name": "PersonAvro",
  "fields": [
    {"name": "name", "type": "string"},
    {"name": "address", "type": "string"},
    {"name": "age", "type": "int"}
  ]
}
```

#### 2. Referrer Schema (`company.avsc`)
```json
{
  "type": "record",
  "namespace": "bbejeck.chapter_3.avro",
  "name": "CompanyAvro",
  "fields": [
    {"name": "name", "type": "string"},
    {
      "name": "executives",
      "type": {
        "type": "array",
        "items": "bbejeck.chapter_3.avro.PersonAvro"
      },
      "default": []
    }
  ]
}
```

---

### 1.2 Protocol Buffers References
Protobuf handles schema references natively via the `import` statement.

#### 1. Referee Schema (`person.proto`)
```protobuf
syntax = "proto3";
package bbejeck.chapter_3.proto;
option java_multiple_files = true;

message Person {
  string name = 1;
  string address = 2;
  int32 age = 3;
}
```

#### 2. Referrer Schema (`company.proto`)
```protobuf
syntax = "proto3";
package bbejeck.chapter_3.proto;
import "person.proto"; // Imports the referee definition
option java_multiple_files = true;

message Company {
  string name = 1;
  repeated Person executives = 2; // Uses imported message
}
```

---

### 1.3 JSON Schema References
JSON Schema uses the `$ref` element to refer to local or remote schema files.

#### Referrer Schema (`company.json`)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Company",
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "executives": {
      "type": "array",
      "items": {
        "$ref": "person.json"
      }
    }
  }
}
```

---

## 2. Registering Referencing Schemas in Gradle

When registering a schema that has dependencies, the **referee** schema must be registered in Schema Registry *before* the **referrer** schema is uploaded.

In `build.gradle`, register them in order and attach the reference mappings using `.addReference()`:

```groovy
schemaRegistry {
    url = 'http://localhost:8081'
    register {
        // 1. Register the referee (dependency) first
        subject('person', 'src/main/avro/person.avsc', 'AVRO')
        
        // 2. Register the referrer and map the reference
        subject('company-value', 'src/main/avro/company.avsc', 'AVRO')
            .addReference('bbejeck.chapter_3.avro.PersonAvro', 'person', 1)
    }
}
```

*Parameters for `.addReference()`*:
1.  **Reference Name**: For Avro, the fully qualified schema name. For Protobuf, the exact file import path (`person.proto`). For JSON Schema, the `$ref` file path (`person.json`).
2.  **Subject**: The registered subject containing the dependency schema (`person`).
3.  **Version**: The version number of the dependency schema in that subject.

---

## 3. Multi-Event Topics: Design Patterns & Configuration

Sometimes, you need to produce multiple different event types to the same Kafka topic (e.g., streaming a sequence of `PlaneEvent`, `TruckEvent`, and `DeliveryEvent` where temporal ordering is critical).

```
┌─────────────────────────────────────────────────────────────┐
│                 TOPIC: inventory-events                     │
├─────────────────────┬───────────────────┬───────────────────┤
│    [PlaneEvent]     │   [TruckEvent]    │  [DeliveryEvent]  │
│      Offset 0       │     Offset 1      │     Offset 2      │
└─────────────────────┴───────────────────┴───────────────────┘
```

To prevent the topic from becoming a dump for unvalidated objects, you can restrict the topic to a predefined set of types using schema references.

### 3.1 The Avro Union Reference Pattern
Create a union schema `all_events.avsc` that acts as an index of permitted schemas:
```json
[
  "bbejeck.chapter_3.avro.TruckEvent",
  "bbejeck.chapter_3.avro.PlaneEvent",
  "bbejeck.chapter_3.avro.DeliveryEvent"
]
```

### 3.2 CRITICAL Producer Configurations for Multi-Event Topics
If you write a Java producer to publish one of these classes (e.g., `PlaneEvent`) using default settings, the producer's auto-registration mechanism will overwrite the union schema in Schema Registry, breaking downstream validation. 

You must configure the producer with the following settings:

```java
// Disable auto-registration to prevent overwriting the union schema
producerProps.put(AbstractKafkaSchemaSerDeConfig.AUTO_REGISTER_SCHEMAS, false);

// Force the serializer to resolve the schema from the latest version in the registry
producerProps.put(AbstractKafkaSchemaSerDeConfig.USE_LATEST_VERSION, true);
```

### Why these settings are mandatory:
1.  **`AUTO_REGISTER_SCHEMAS = false`**: Stops the producer from attempting to register `PlaneEvent` directly to the `inventory-events-value` subject.
2.  **`USE_LATEST_VERSION = true`**: Tells the serializer to look up the active union schema registered under `inventory-events-value`. When serializing, it checks if `PlaneEvent` matches one of the types defined inside the union.
