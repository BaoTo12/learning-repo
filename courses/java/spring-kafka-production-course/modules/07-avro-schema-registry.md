# Module 07 — Avro + Schema Registry with Spring

In this module, we will explore Apache Avro and Schema Registry integration in Spring Boot. We will cover why JSON and String serializers are risky in production microservices and explain how Schema Registry acts as a contract validator. We will compare SpecificRecord and GenericRecord options. Next, we will study Confluent Subject Naming Strategies and compatibility enforcement rules (BACKWARD, FORWARD, FULL). We will then look at troubleshooting common Avro issues, study 5 Socratic review questions, and complete three hands-on labs with compilable code structures and Avro schemas.

---

## 1. Academic Lecture: Avro Serializers, Specific vs. Generic Records & Compatibility

### Basic Level: Schema Enforcement & Specific vs. Generic Records

#### The Danger of JSON in Decoupled Pipelines
In a decoupled microservices architecture, producers and consumers run independently. 
* **The Problem**: If you serialize messages as JSON, there is no strict contract. If the producer team updates a field name (e.g., changing `customerId` to `clientId`), the change compiles successfully on their side. However, when the message is published, all downstream consumer microservices will fail at runtime because their JSON parsers cannot map the new field name.
* **The Solution**: Use a binary format with a strict schema contract like **Apache Avro** backed by a central **Schema Registry**.

#### Apache Avro & Schema Registry
* **Avro**: A compact, binary serialization framework. It relies on schemas defined in JSON format (usually with a `.avsc` file extension). Since the schema is kept separate from the data payload, Avro payloads contain no field names or type metadata. This makes payloads extremely small and efficient.
* **Schema Registry**: A central server that stores and retrieves Avro schemas. 
  1. The producer checks the Schema Registry to see if the schema for the payload is already registered. If not, it registers it.
  2. The producer gets a unique **Schema ID** from the registry.
  3. The producer prepends this 4-byte Schema ID to the binary payload and publishes it to Kafka.
  4. The consumer reads the payload, extracts the Schema ID, fetches the corresponding schema from the registry, and deserializes the binary payload.

```text
  [ Producer ] ──(1. Get/Register Schema)──► [ Schema Registry ] ◄──(4. Fetch Schema by ID)── [ Consumer ]
        │                                             ▲                                             ▲
        │                                             │                                             │
  (2. Prepends ID)                                    │                                      (5. Deserializes)
        │                                             │                                             │
        ▼                                             │                                             │
  [ Binary + ID Payload ] ───────────────────► [ Kafka Broker ] ────────────────────────────────────┘
```

#### SpecificRecord vs GenericRecord
When working with Avro in Java, you have two options for representing records:
1. **SpecificRecord**:
   * **What it is**: Code-generation approach. You use a Maven or Gradle plugin to compile `.avsc` schema files into concrete Java classes (e.g., a `PurchaseEvent` class is generated).
   * *Pros*: Strong type safety, auto-completion in IDEs, getters/setters, clear domain objects.
   * *Cons*: Requires code generation and compiling new classes whenever the schema changes.
2. **GenericRecord**:
   * **What it is**: Dynamic approach. You read the schema dynamically at runtime. Fields are accessed using key-value calls (e.g., `record.get("customer_id")`).
   * *Pros*: Highly flexible; no need to compile new classes. Perfect for generic components like ingest pipelines, database routers, or audit loggers.
   * *Cons*: No compile-time type checking; code is prone to typos (e.g., calling `record.get("cust_id")` instead of `customer_id` will throw a runtime error).

---

### Intermediate Level: Subject Naming Strategies & Caching

#### Subject Naming Strategies
A **Subject** is the name under which a schema is registered in the Schema Registry. The registry uses **Subject Naming Strategies** to map a topic record to a schema subject:
* **TopicNameStrategy** (Default): The subject name is derived from the topic name (e.g., `<topic-name>-value` for message values, or `<topic-name>-key` for keys).
  * *Use Case*: Standard topics containing a single type of event.
* **RecordNameStrategy**: The subject name is the fully qualified name of the Avro record (e.g., `com.springkafka.course.model.PurchaseEvent`).
  * *Use Case*: Allows multiple distinct event types to be published to the same Kafka topic.
* **TopicRecordNameStrategy**: The subject name is a combination of the topic and the record name (e.g., `<topic-name>-com.springkafka.course.model.PurchaseEvent`).
  * *Use Case*: Useful when you want to restrict specific event schemas to a single topic but allow multiple schemas on that topic.

#### Registry Caching & Serialization Performance
To prevent a REST API call to the Schema Registry for every single message, the confluent serializer/deserializer uses an internal **Cache** (`SchemaRegistryClient`):
* When producing, the serializer caches the mapping of: `Avro Schema ──► Schema ID`.
* When consuming, the deserializer caches the mapping of: `Schema ID ──► Avro Schema`.
* This ensures high-throughput performance, limiting network overhead to the first time a new schema version is processed.

---

### Advanced Level: Compatibility Enforcement & Event Versioning

#### Compatibility Enforcement Modes
The Schema Registry enforces compatibility rules when a new schema version is registered. This prevents producers from registering breaking changes. The primary modes are:
* **BACKWARD** (Default): Consumers using the *new* schema can read messages written with the *old* schema.
  * *Rule*: You can delete fields, or add optional fields (fields with default values).
  * *Upgrade Path*: Upgrade consumers first, then upgrade producers.
* **FORWARD**: Consumers using the *old* schema can read messages written with the *new* schema.
  * *Rule*: You can add fields, or delete optional fields.
  * *Upgrade Path*: Upgrade producers first, then upgrade consumers.
* **FULL**: Both backward and forward compatible. Old consumers can read new messages, and new consumers can read old messages.
  * *Rule*: You can only add or delete optional fields (fields with default values).
  * *Upgrade Path*: You can upgrade producers or consumers in any order.
* **NONE**: No compatibility is checked. Any schema can be registered. Highly discouraged in production.

#### Event Versioning & Schema Resolution
Avro resolves differences between the reader's schema and the writer's schema using **Schema Resolution Rules**:
* If the writer's record contains a field not present in the reader's schema, the reader ignores it.
* If the reader's schema contains a field not present in the writer's record, the reader fills in the **Default Value** defined in the reader's schema. If no default value is defined, deserialization fails.

---

## 2. Theory & Production Best Practices

### Subject Naming Strategies Comparison

| Strategy | Subject Name Example | Single Schema Per Topic? | Multi-Schema Per Topic? | Best Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **TopicNameStrategy** | `orders-value` | Yes | No | Clean, domain-driven design with 1 topic per event type. |
| **RecordNameStrategy** | `com.example.OrderCreated` | No | Yes | Event-driven queues where multiple different types are handled together. |
| **TopicRecordNameStrategy**| `orders-com.example.Order` | No | Yes | Multi-event topics restricted by specific environments/names. |

### Compatibility Enforcement Comparison

| Compatibility Mode | Upgrade Order | Can Delete Fields? | Can Add Fields? | Safe for Production? |
| :--- | :--- | :--- | :--- | :--- |
| **BACKWARD** | Consumer First | Yes | Only with defaults | Yes (Standard) |
| **FORWARD** | Producer First | Only with defaults | Yes | Yes |
| **FULL** | Any Order | Only with defaults | Only with defaults | Yes (Safest) |
| **NONE** | Must coordinate | Yes | Yes | No |

---

## 3. Common Errors & Troubleshooting

### 1. SchemaNotFoundException
* **Symptom**: Consumer throws `SerializationException: Schema not found` or HTTP 404 error code.
* **Root Cause**: The consumer read a Schema ID from a message header, but that Schema ID does not exist in the Schema Registry. This often happens if the registry database was reset, or the consumer is pointing to a staging registry while the producer wrote to a production registry.
* **Fix**: Ensure both producer and consumer point to the identical Schema Registry URL.

### 2. Incompatible Schema Registration (422 Unprocessable Entity)
* **Symptom**: Producer fails to start or publish, showing `HttpException: Schema is incompatible: 422`.
* **Root Cause**: The producer is trying to register a modified Avro schema that violates the compatibility settings configured for that subject in the registry.
* **Fix**:
  * If the registry is set to BACKWARD compatibility, ensure any new field you added has a `default` value configured.
  * Check the schema version registry history to verify changes.

### 3. ClassCastException / SpecificRecord Deserialization Failure
* **Symptom**: Consumer throws `ClassCastException: Cannot cast GenericData$Record to SpecificRecord`.
* **Root Cause**: The consumer is configured with `KafkaAvroDeserializer` but did not set `specific.avro.reader = true`. The deserializer defaults to returning a `GenericRecord` instead of compiling it into your generated Java classes.
* **Fix**: Set `specific.avro.reader=true` in your Spring consumer properties.

---

## 4. Socratic Review Questions

### Question 1
*Why must a new field in a BACKWARD-compatible Avro schema define a default value?*
* **Answer**: In BACKWARD compatibility, new consumers must be able to read old payloads. When a new consumer (with the new schema containing the new field) reads an old message (written by a producer using the old schema), the payload will lack the new field. The reader's deserializer must be able to populate that missing field with a default value. If no default value is defined, the deserializer will throw a resolution exception.

### Question 2
*Explain the difference between `RecordNameStrategy` and `TopicNameStrategy`. When would you choose the former?*
* **Answer**: `TopicNameStrategy` registers schemas using the topic name (e.g. `payments-value`), meaning a topic can only store one schema structure. `RecordNameStrategy` registers schemas using the record class name (e.g., `com.example.Debit` or `com.example.Refund`), which allows messages of completely different schemas and class types to live on the same topic. You would choose `RecordNameStrategy` when implementing a centralized Event Bus or Command Queue pattern.

### Question 3
*What payload metadata is added to a Kafka record serialized with Confluent Avro, and what is its size footprint?*
* **Answer**: A Confluent Avro record contains a 5-byte header prefix before the actual binary Avro payload. This prefix consists of 1 byte (Magic Byte, value `0`) followed by 4 bytes representing the unique Schema ID from the Schema Registry.

### Question 4
*What is Transitive Compatibility (e.g., `BACKWARD_TRANSITIVE`), and why is it important in schema evolution?*
* **Answer**: Standard compatibility (e.g., `BACKWARD`) only compares the proposed schema against the *immediately preceding* version (e.g. comparing v3 against v2). Transitive compatibility compares the proposed schema against *all* previously registered versions of the schema (e.g., comparing v3 against v2 and v1). This ensures that consumers running very old versions of your software do not crash when a new schema is deployed.

### Question 5
*How does setting `specific.avro.reader = true` change the output of the KafkaAvroDeserializer?*
* **Answer**: By default, `specific.avro.reader` is `false`, and the deserializer returns a dynamic `GenericRecord` (specifically `GenericData$Record`). Setting it to `true` instructs the deserializer to look at the writer's schema, find the corresponding generated Java class on the classpath matching the schema namespace and name, and instantiate and return that generated class (which implements `SpecificRecord`).

---

## 5. Hands-on Labs

### Lab 7.1 — Purchase Events (Producer with SpecificRecord)

#### Scenario
We will define an Avro schema for purchase events, generate the Java SpecificRecord classes, and configure a Spring Boot producer using `KafkaAvroSerializer` with the default `TopicNameStrategy`.

#### Avro Schema Definition
Create the file [PurchaseEvent.avsc](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/resources/avro/PurchaseEvent.avsc) with the following content:

```json
{
  "type": "record",
  "name": "PurchaseEvent",
  "namespace": "com.springkafka.course.avro",
  "doc": "Schema for tracking store purchase transactions",
  "fields": [
    {
      "name": "purchaseId",
      "type": "string",
      "doc": "Unique transaction identifier"
    },
    {
      "name": "customerId",
      "type": "string",
      "doc": "Identifier of purchasing customer"
    },
    {
      "name": "amount",
      "type": "double",
      "doc": "Total purchase price value"
    },
    {
      "name": "timestamp",
      "type": "long",
      "doc": "Epoch milliseconds epoch value of purchase"
    }
  ]
}
```

#### Application Properties (`application.yml`)
Add the following settings to configure the Avro Serializer and Confluent Schema Registry connection:

```yaml
spring:
  kafka:
    bootstrap-servers: localhost:9092
    producer:
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: io.confluent.connect.kafka.avro.KafkaAvroSerializer
      properties:
        schema.registry.url: http://localhost:8081
```

#### Complete Producer Java Code
Create the file [PurchaseProducer.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/producer/PurchaseProducer.java) with the following content:

```java
package com.springkafka.course.producer;

import com.springkafka.course.avro.PurchaseEvent;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class PurchaseProducer {
    private static final Logger log = LoggerFactory.getLogger(PurchaseProducer.class);

    private final KafkaTemplate<String, PurchaseEvent> kafkaTemplate;

    public PurchaseProducer(KafkaTemplate<String, PurchaseEvent> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    // Publish generated Avro SpecificRecord
    public void sendPurchase(String key, PurchaseEvent purchase) {
        log.info("Publishing Avro Purchase Event: {} | Key: {}", purchase, key);
        
        kafkaTemplate.send("purchases", key, purchase)
            .whenComplete((result, exception) -> {
                if (exception != null) {
                    log.error("Failed to publish Avro payload to broker", exception);
                } else {
                    log.info("Purchase successfully published! Metadata: {}", result.getRecordMetadata());
                }
            });
    }
}
```

---

### Lab 7.2 — Customer Events (Consumer with GenericRecord & SpecificRecord)

#### Scenario
We will define an Avro schema for customer profile events. We will configure a consumer group that can deserialize messages using both SpecificRecord and GenericRecord patterns.

#### Avro Schema Definition
Create the file [CustomerEvent.avsc](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/resources/avro/CustomerEvent.avsc) with the following content:

```json
{
  "type": "record",
  "name": "CustomerEvent",
  "namespace": "com.springkafka.course.avro",
  "doc": "Schema for tracking customer profile updates",
  "fields": [
    {
      "name": "customerId",
      "type": "string"
    },
    {
      "name": "fullName",
      "type": "string"
    },
    {
      "name": "email",
      "type": "string"
    }
  ]
}
```

#### Application Properties (`application.yml`)
The properties below define the consumer settings, setting the schema registry URL and enabling the specific Avro reader configuration:

```yaml
spring:
  kafka:
    bootstrap-servers: localhost:9092
    consumer:
      group-id: customer-insights-group
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: io.confluent.connect.kafka.avro.KafkaAvroDeserializer
      properties:
        schema.registry.url: http://localhost:8081
        specific.avro.reader: true
```

#### Complete SpecificRecord Consumer Java Code
Create the file [SpecificCustomerConsumer.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/consumer/SpecificCustomerConsumer.java) with the following content:

```java
package com.springkafka.course.consumer;

import com.springkafka.course.avro.CustomerEvent;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class SpecificCustomerConsumer {
    private static final Logger log = LoggerFactory.getLogger(SpecificCustomerConsumer.class);

    // 1. Consume using generated SpecificRecord class
    @KafkaListener(id = "specific-customer-listener", topics = "customers")
    public void consumeSpecific(CustomerEvent event) {
        log.info("Received SpecificRecord Event -> Customer ID: {} | Name: {} | Email: {}",
                event.getCustomerId(), event.getFullName(), event.getEmail());
    }
}
```

#### Complete GenericRecord Consumer Java Code
Create the file [GenericCustomerConsumer.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/consumer/GenericCustomerConsumer.java) with the following content:

```java
package com.springkafka.course.consumer;

import org.apache.avro.generic.GenericRecord;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class GenericCustomerConsumer {
    private static final Logger log = LoggerFactory.getLogger(GenericCustomerConsumer.class);

    // 2. Consume dynamically using GenericRecord
    @KafkaListener(id = "generic-customer-listener", topics = "customers", containerFactory = "genericKafkaListenerContainerFactory")
    public void consumeGeneric(GenericRecord record) {
        log.info("Received GenericRecord Event!");
        
        // Fields are accessed dynamically using string key lookups
        String customerId = record.get("customerId").toString();
        String fullName = record.get("fullName").toString();
        String email = record.get("email").toString();
        
        log.info("Parsed GenericRecord details -> ID: {} | Name: {} | Email: {}", customerId, fullName, email);
    }
}
```

---

### Lab 7.3 — Event Evolution Demo

#### Scenario
We will walk through the process of evolving the `CustomerEvent` schema. We will add an optional field, verify compatibility rules, and illustrate the runtime behavior of different client versions.

#### Step 1: Schema Evolution (v1 to v2)
We want to add a new field, `membershipStatus` (e.g. `SILVER`, `GOLD`), to our schema. To ensure this change is **BACKWARD compatible**, we must assign it a **default value** so old records (which lack this field) can be resolved.

Create the updated schema file [CustomerEventV2.avsc](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/resources/avro/CustomerEventV2.avsc) with the following content:

```json
{
  "type": "record",
  "name": "CustomerEvent",
  "namespace": "com.springkafka.course.avro",
  "doc": "Evolved schema for tracking customer profile updates with membership status",
  "fields": [
    {
      "name": "customerId",
      "type": "string"
    },
    {
      "name": "fullName",
      "type": "string"
    },
    {
      "name": "email",
      "type": "string"
    },
    {
      "name": "membershipStatus",
      "type": "string",
      "default": "STANDARD",
      "doc": "New field added with backward compatible default value"
    }
  ]
}
```

#### Step 2: Registering v2 Schema
When a v2 producer starts and writes the record, it registers the new schema with Schema Registry:
1. Schema Registry checks the proposed v2 schema against the active compatibility rules (BACKWARD).
2. It verifies that `membershipStatus` has a default value `"STANDARD"`.
3. The registry registers the schema as **Version 2** of the subject `customers-value` and returns a new Schema ID.

#### Step 3: Runtime Evolution Scenarios

```text
  [ Scenario A: Old Consumer parses New v2 Payload ]
  Writer Schema (v2) contains 'membershipStatus'  ──►  Reader Schema (v1) ignores 'membershipStatus' field.
  
  [ Scenario B: New Consumer parses Old v1 Payload ]
  Writer Schema (v1) lacks 'membershipStatus'     ──►  Reader Schema (v2) resolves field using default value '"STANDARD"'.
```

##### Scenario A: Old Consumer (v1 schema) reads New Message (v2 payload)
* **What happens**: The v1 consumer fetches the v2 writer schema from the registry. It notices that the v2 schema contains the `membershipStatus` field which is not in its local v1 reader schema. It simply ignores the field and processes the other fields safely.

##### Scenario B: New Consumer (v2 schema) reads Old Message (v1 payload)
* **What happens**: The v2 consumer fetches the v1 writer schema from the registry. It notices that the old message does not contain the `membershipStatus` field. It falls back to the default value defined in its v2 schema, resolving the field value as `"STANDARD"`, and continues processing.

---

### Step-by-Step Code Walkthrough & Parameter Configuration Tables

#### Step-by-Step Code Walkthrough

##### Lab 7.1 Walkthrough
1. **Avro Schema Definition**: We define fields using JSON names and specific types. The schema namespace compiles into the Java package namespace.
2. **`value-serializer`**: We define `KafkaAvroSerializer` as the value serializer class. It intercepts outbound Java SpecificRecords, coordinates with Schema Registry to register and map schemas, and compiles the 5-byte header prefix into the payload.
3. **`schema.registry.url`**: Configures the connection location for Confluent Schema Registry.

##### Lab 7.2 Walkthrough
1. **`specific.avro.reader`**: Setting this property to `true` directs the `KafkaAvroDeserializer` to convert the binary payload directly into the SpecificRecord class (`CustomerEvent`) instead of returning a generic record wrapper.
2. **`GenericCustomerConsumer`**: When using `GenericRecord`, we do not use compiled model classes. The consumer accesses values dynamically via `.get("field")` calls. This allows the application code to start up and run without needing local compiled schemas on the classpath.

##### Lab 7.3 Walkthrough
1. **`default` field value**: Configures default values for new fields. This is the cornerstone of Schema Evolution compatibility.
2. **Schema Registry compatibility enforcement**: Prevents breaking changes from being registered. Schema Registry will throw an error at startup if a developer introduces a schema changes that breaks reader/writer resolution rules.

---

### Configuration Parameter Tables

The tables below describe every configuration property, class type, and property attribute used in the hands-on configurations.

#### Spring Boot Kafka Avro Serializer/Deserializer Configurations

| Property Key | Expected Value Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `schema.registry.url` | `String` | None | The REST URL endpoint of the Confluent Schema Registry instance. |
| `specific.avro.reader` | `Boolean` | `false` | If `true`, the deserializer instantiates compiled class types (`SpecificRecord`) instead of returning generic records. |
| `auto.register.schemas` | `Boolean` | `true` | If `true`, the serializer automatically registers new schemas to the registry if they do not exist. |
| `value.subject.name.strategy` | `Class` | `TopicNameStrategy` | The naming strategy class used to construct the schema subject registration name (e.g. `TopicNameStrategy`, `RecordNameStrategy`). |
| `max.schemas.per.subject` | `Integer` | `1000` | The maximum capacity limit of the internal schema cache map before entries are evicted. |

#### Avro Schema JSON Keys

| JSON Key | Type | Description |
| :--- | :--- | :--- |
| `type` | `String` | The schema category wrapper (e.g., `record`, `enum`, `array`). |
| `name` | `String` | The class name representation of the record. |
| `namespace` | `String` | The package group name mapping to Java namespace structures. |
| `fields` | `JSON Array` | The list of attribute fields containing names, types, and defaults. |
| `default` | `String/Integer/etc.` | The fallback value assigned to the field if missing in a writer payload. Required for backward compatibility. |
