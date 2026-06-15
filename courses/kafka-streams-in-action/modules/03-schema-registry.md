# Module 03 — Schema Registry

In this module, we will explore the centralized schema management and data governance platform of the Apache Kafka ecosystem: **Confluent Schema Registry**. We will study why schemas are critical to preventing breaking changes (poison pills) in data streams, examine the internal architecture and consensus mechanisms of the registry, and analyze the three supported schema formats: Apache Avro, Google Protocol Buffers (Protobuf), and JSON Schema. We will also detail subject name strategies, compatibility modes, schema references, and specific vs. generic deserializers. Finally, we will configure a Maven-based Avro code-generation build pipeline and complete hands-on REST API exercises.

---

## 1. Academic Lecture: Schema Registry Foundations

### Basic Level: Why Schemas Matter & Schema Registry Role

#### Why Schemas Matter: Data Quality Contracts
When applications communicate using Kafka, they send messages as simple arrays of bytes over the network. The brokers do not know what is inside these bytes. This means a producer application could easily write bad data (like text instead of a number) into a topic. When a consumer reads this bad data, it cannot parse it and will crash. This bad message is called a **poison pill**.

To fix this, we use a **schema**. A schema is a simple blueprint file that defines:
1.  The name of our event fields.
2.  The data types allowed (e.g., text, numbers, list).
3.  Which fields are optional and what default values they have.

##### Analogy: The Rules Office / Translator
> Imagine two people who do not speak the same language trying to trade books. 
> To help them, they hire a **Rules Office (Schema Registry)**. Every time an author publishes a new book, they register the book layout rules at the office. 
> The office gives the book layout a unique **Rules ID**. The publisher stamps this ID on the cover. 
> When the reader buys the book, they check the ID, lookup the rules dictionary, and read it easily. If the publisher writes a book that breaks the rules, the office blocks it immediately.

#### The 5-Byte Confluent Wire Protocol Header
To save network bandwidth, serializers do not send the whole schema text with every event. Instead, they write a tiny 5-byte header:

```text
 0             1             2             3             4             5
┌─────────────┬─────────────────────────────────────────────────────────┐
│ Magic Byte  │                       Schema ID                         │
│   (0x00)    │               (4-Byte Big-Endian Integer)               │
└─────────────┴─────────────────────────────────────────────────────────┘
```

##### Analogy: The Dictionary Tag
> Think of this header like a small label on a box. The first byte (magic byte) is a notice saying "this box uses a dictionary." The next 4 bytes are a number code (Schema ID) pointing to the exact page in our dictionary (Schema Registry) where the structure is defined. The rest of the bytes are the actual book text.

---

### Intermediate Level: Schema Formats & Subject Strategies

#### Comparison of Supported Schema Formats

*   **Apache Avro**: Writes schemas using simple JSON format. It is a binary format, meaning it is very small and doesn't write field names in the payload.
*   **Google Protocol Buffers (Protobuf)**: Writes schemas using a custom `.proto` file. It uses numbers (tags) to identify fields, making serialization extremely fast and compact.
*   **JSON Schema**: Writes schemas using standard JSON. It is very easy to read and works well with standard web applications.

##### Listing 3.1: Avenger Avro Schema (`avenger.avsc`)
```json
{
  "namespace": "bbejeck.chapter_3.avro",
  "type": "record",
  "name": "AvengerAvro",
  "fields": [
    {"name": "name", "type": "string"},
    {"name": "real_name", "type": "string"},
    {
      "name": "movies",
      "type": {"type": "array", "items": "string"},
      "default": []
    }
  ]
}
```

##### Listing 3.2: Avenger Protobuf Schema (`avenger.proto`)
```protobuf
syntax = "proto3";
package bbejeck.chapter_3.proto;
option java_multiple_files = true;

message Avenger {
  string name = 1;
  string real_name = 2;
  repeated string movies = 3;
}
```

##### Listing 3.3: Avenger JSON Schema (`avenger.json`)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Avenger",
  "type": "object",
  "javaType": "bbejeck.chapter_3.json.SimpleAvengerJson",
  "properties": {
    "name": { "type": "string" },
    "realName": { "type": "string" },
    "movies": {
      "type": "array",
      "items": { "type": "string" },
      "default": []
    }
  },
  "required": ["name", "realName"]
}
```

#### Subject Name Strategies
A **subject** is a folder name used to store schema versions. Schema Registry supports three ways to name this folder:

1.  **`TopicNameStrategy` (Default)**:
    *   Saves the schema under `<topic-name>-value` (or `-key`).
    *   Use this when your topic only stores a single type of event.
2.  **`RecordNameStrategy`**:
    *   Saves the schema under the name of the Java class (e.g., `com.kafkastreams.course.Purchase`).
    *   Use this when you want to put different kinds of events into the same topic.
3.  **`TopicRecordNameStrategy`**:
    *   Saves the schema under `<topic-name>-<class-name>`.
    *   Use this when you want to put different events in a topic, but you want to check compatibility separately for each topic.

---

### Advanced Level: Schema Compatibility, References, and Client SerDes

#### Schema Compatibility Modes & Evolution
When you change a schema, Schema Registry checks if it is safe to do so. The main modes are:

##### Analogy: The DVD Player
> Think of compatibility like a DVD player:
> *   **BACKWARD Compatibility** is like a **new DVD player reading old discs**. If we update the app to a new schema (new player), it must still be able to read old messages (old discs). This means you can delete fields or add optional fields (which use default values).
> *   **FORWARD Compatibility** is like an **old DVD player reading new discs**. The old consumer app must be able to read new messages written with the new schema by simply skipping the new fields. This means you can add new fields or delete optional fields.
> *   **FULL Compatibility** is a **two-way check**. Both the new and old apps can read each other's data. You are only allowed to add or delete optional fields.

| Mode | Allowed Changes | Client Upgrade Order | Description |
| :--- | :--- | :--- | :--- |
| **`BACKWARD`** (Default) | - Delete fields<br>- Add optional fields | 1. Consumers<br>2. Producers | Upgraded consumers can parse older payloads using schema defaults. |
| **`BACKWARD_TRANSITIVE`** | - Delete fields<br>- Add optional fields | 1. Consumers<br>2. Producers | Checks compatibility against **all** older schema versions. |
| **`FORWARD`** | - Add fields<br>- Delete optional fields | 1. Producers<br>2. Consumers | Old consumers ignore new fields and read new messages. |
| **`FORWARD_TRANSITIVE`** | - Add fields<br>- Delete optional fields | 1. Producers<br>2. Consumers | Old consumers can read new messages against **all** older versions. |
| **`FULL`** | - Add optional fields<br>- Delete optional fields | Any order | Dual-direction compatibility. |
| **`FULL_TRANSITIVE`** | - Add optional fields<br>- Delete optional fields | Any order | Dual-direction compatibility across all versions. |
| **`NONE`** | Any change | Any order | Disables checks entirely. High risk of breaking applications. |

#### Schema References

##### Analogy: Shared Address Cards
> Imagine a company file that includes a person's name, address, and age. If you duplicate this person info inside College files and Company files, updating the person structure is painful because you must edit multiple files.
> With **Schema References**, we write a single `Person` schema card. The `College` and `Company` schemas simply point to that card. If we update the `Person` schema, both automatically get the update.

##### Listing 3.4: Person Avro Sub-Schema (`person.avsc`)
```json
{
  "namespace": "bbejeck.chapter_3.avro",
  "type": "record",
  "name": "PersonAvro",
  "fields": [
    {"name": "name", "type": "string"},
    {"name": "address", "type": "string"},
    {"name": "age", "type": "int"}
  ]
}
```

##### Listing 3.5: Company Schema with Reference (`company.avsc`)
```json
{
  "namespace": "bbejeck.chapter_3.avro",
  "type": "record",
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

To register these with Gradle:
```groovy
register {
    subject('person', 'src/main/avro/person.avsc', 'AVRO')
    subject('company-value', 'src/main/avro/company.avsc', 'AVRO')
        .addReference("bbejeck.chapter_3.avro.PersonAvro", "person", 1)
}
```

#### Multiple Event Types on a Single Topic
To keep events in the correct sequence, we can produce different types (e.g., `TruckEvent`, `PlaneEvent`, `DeliveryEvent`) to one topic.

1.  **Avro Union**:
    *   Create a union schema `all_events.avsc` containing an array of referenced event schemas: `["bbejeck.chapter_3.avro.TruckEvent", "bbejeck.chapter_3.avro.PlaneEvent", ...]`.
    *   **CRITICAL PRODUCER CONFIGURATION**:
        *   Set `auto.register.schemas = false`
        *   Set `use.latest.version = true`
        *   *Why*: If you do not disable auto-registration, the client will register the single `TruckEvent` schema directly, deleting the union schema from the subject folder, which breaks other events.
2.  **Protobuf `oneof`**:
    *   Define a `oneof` field. Protobuf registers imported messages automatically, so leaving `auto.register.schemas=true` is safe.

#### Deserializers: Specific vs. Generic Types
When reading records, the deserializer needs to know what object to create:

*   **Specific Reader (Strong Type)**:
    *   Returns strongly typed Java class instances (e.g., `Purchase` class).
    *   *Avro Property*: Set `KafkaAvroDeserializerConfig.SPECIFIC_AVRO_READER_CONFIG = true`.
    *   *Protobuf Property*: Set `KafkaProtobufDeserializerConfig.SPECIFIC_PROTOBUF_VALUE_TYPE = AvengerSimple.class`.
    *   *JSON Schema Property*: Set `KafkaJsonDeserializerConfig.JSON_VALUE_TYPE = SimpleAvengerJson.class`.
*   **Generic Reader (Agnostic Container)**:
    *   If you do not configure the specific properties, it returns a generic wrapper:
        *   Avro: `GenericRecord` (works like a `HashMap`, lookup fields by name: `genericRecord.get("real_name")`).
        *   Protobuf: `DynamicMessage`.
        *   JSON Schema: `JsonNode` or `Map`.

---

### Serialization Without Schema Registry (For Comparison)

If you do not deploy Schema Registry, you must write your own serializers. Here is a custom example using Jackson's `ObjectMapper`.

##### Listing 3.6: Custom Jackson JSON Serializer
```java
package com.zmart.kafka.serializer;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.common.errors.SerializationException;
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
        } catch (JsonProcessingException e) {
            throw new SerializationException("Jackson serialization failed", e);
        }
    }

    @Override
    public void close() {}
}
```

##### Listing 3.7: Custom Jackson JSON Deserializer
```java
package com.zmart.kafka.serializer;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.common.errors.SerializationException;
import org.apache.kafka.common.serialization.Deserializer;
import java.io.IOException;
import java.util.Map;

public class JsonDeserializer<T> implements Deserializer<T> {
    private final ObjectMapper objectMapper = new ObjectMapper();
    private Class<T> targetClass;

    @SuppressWarnings("unchecked")
    @Override
    public void configure(Map<String, ?> configs, boolean isKey) {
        this.targetClass = (Class<T>) configs.get("json.value.type.class");
    }

    @Override
    public T deserialize(String topic, byte[] data) {
        if (data == null || data.length == 0) {
            return null;
        }
        try {
            return objectMapper.readValue(data, targetClass);
        } catch (IOException e) {
            throw new SerializationException("Jackson deserialization failed", e);
        }
    }

    @Override
    public void close() {}
}
```

---

## 2. Theory vs. Production Trade-offs

### Subject Name Strategies Comparison

| Strategy | Multiple Types per Topic | Evolve Topic Independently | Subject Counts Overhead | Recommended Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **`TopicNameStrategy`** | No | Yes | Low | Simple single-event topics. |
| **`RecordNameStrategy`** | Yes | No (Record change affects all topics) | Moderate | Standard record layouts shared globally. |
| **`TopicRecordNameStrategy`**| Yes | Yes (Scoped to context topic) | High | Complex event streams with custom contexts. |

---

## 3. Common Errors & Pitfalls

### Pitfall 1: Overwriting Avro Union Subjects
*   **Why it fails**: When using Avro union types to write multiple events to one topic, leaving `auto.register.schemas=true` will register the schema of the individual event type, deleting the union registry. This causes subsequent writes of other event types to fail.
*   **How to fix**: Always configure the producer properties to set `auto.register.schemas=false` and `use.latest.version=true`.

### Pitfall 2: ClassCastException from Omitted Specific Reader Flag
*   **Why it fails**: A consumer reads a record and expects it to be mapped to a specific generated class. However, they omit the configuration flag. The deserializer returns a `GenericRecord`, raising a `ClassCastException` at runtime:
    ```text
    java.lang.ClassCastException: class org.apache.avro.generic.GenericData$Record cannot be cast to class com.kafkastreams.course.Purchase
    ```
*   **How to fix**: Always configure `KafkaAvroDeserializerConfig.SPECIFIC_AVRO_READER_CONFIG = true` in consumer properties.

---

## 4. Socratic Review Questions

### Question 1
Why does Confluent Schema Registry utilize a Kafka topic (`_schemas`) as its write-ahead log rather than a database?

#### Answer
Using a Kafka topic as the storage layer provides high availability, fault tolerance, and durability out of the box without introducing an external database dependency. The topic `_schemas` is configured as a single-partition compacted topic. Because it is single-partitioned, it establishes a total ordering of all schema registrations, preventing race conditions where two nodes attempt to claim the same schema ID simultaneously.

### Question 2
What is the difference between `BACKWARD` and `BACKWARD_TRANSITIVE` compatibility modes, and why would you select one over the other?

#### Answer
*   `BACKWARD` mode guarantees that a new schema version (e.g., Version 3) is compatible with the immediate previous schema version (Version 2).
*   `BACKWARD_TRANSITIVE` guarantees that the new schema version is compatible with **all** previous schema versions (Version 1 and Version 2).
You select `BACKWARD_TRANSITIVE` when you have topics containing historical data spanning multiple schema versions on disk, and you want to ensure that a consumer reading from the beginning of the topic can parse every historical record without failing.

---

## 5. Hands-on Lab: Schema Definition, REST API, and Maven Code Generation

In this lab, we will write a structured Avro schema for a purchase event, register it with Schema Registry via curl, evolve the schema, verify compatibility, and configure a Maven compile process.

### Lab 3.1 — Define the Avro Schema
Create the directory structure `src/main/avro/` in your project root and save the schema definition as `purchase.avsc`:

```json
{
  "type": "record",
  "name": "Purchase",
  "namespace": "com.kafkastreams.course",
  "fields": [
    {"name": "customerId", "type": "string"},
    {"name": "itemPurchased", "type": "string"},
    {"name": "quantity", "type": "int"},
    {"name": "price", "type": "double"},
    {"name": "purchaseDate", "type": {"type": "long", "logicalType": "timestamp-millis"}}
  ]
}
```

---

### Lab 3.2 — Register the Schema via REST API
To upload the schema, format the JSON payload by escaping the nested quotes and newlines. 

Run the following curl command in your terminal (make sure Schema Registry is running on port 8081):

```bash
curl -X POST http://localhost:8081/subjects/purchases-value/versions   -H "Content-Type: application/vnd.schemaregistry.v1+json"   -d "{\"schema\": \"{\\\"type\\\": \\\"record\\\", \\\"name\\\": \\\"Purchase\\\", \\\"namespace\\\": \\\"com.kafkastreams.course\\\", \\\"fields\\\": [{\\\"name\\\": \\\"customerId\\\", \\\"type\\\": \\\"string\\\"}, {\\\"name\\\": \\\"itemPurchased\\\", \\\"type\\\": \\\"string\\\"}, {\\\"name\\\": \\\"quantity\\\", \\\"type\\\": \\\"int\\\"}, {\\\"name\\\": \\\"price\\\", \\\"type\\\": \\\"double\\\"}, {\\\"name\\\": \\\"purchaseDate\\\", \\\"type\\\": {\\\"type\\\": \\\"long\\\", \\\"logicalType\\\": \\\"timestamp-millis\\\"}}]}\"}"
```

**Expected Response Output:**
```json
{
  "id": 1
}
```

---

### Lab 3.3 — Evolve the Schema (Backward Compatible Modification)
To add a new field while maintaining `BACKWARD` compatibility (allowing older records on disk to be read by the new schema), the field must be optional. In Avro, this is achieved by defining a union type with `null` and providing a default value of `null`.

Update your local `src/main/avro/purchase.avsc` file to append the `department` field:

```json
{
  "type": "record",
  "name": "Purchase",
  "namespace": "com.kafkastreams.course",
  "fields": [
    {"name": "customerId", "type": "string"},
    {"name": "itemPurchased", "type": "string"},
    {"name": "quantity", "type": "int"},
    {"name": "price", "type": "double"},
    {"name": "purchaseDate", "type": {"type": "long", "logicalType": "timestamp-millis"}},
    {"name": "department", "type": ["null", "string"], "default": null}
  ]
}
```

---

### Lab 3.4 — Test Compatibility Before Registering
Before deploying an evolved schema, test it against the registered history:

Run the compatibility check curl command:

```bash
curl -X POST http://localhost:8081/compatibility/subjects/purchases-value/versions/latest   -H "Content-Type: application/vnd.schemaregistry.v1+json"   -d "{\"schema\": \"{\\\"type\\\": \\\"record\\\", \\\"name\\\": \\\"Purchase\\\", \\\"namespace\\\": \\\"com.kafkastreams.course\\\", \\\"fields\\\": [{\\\"name\\\": \\\"customerId\\\", \\\"type\\\": \\\"string\\\"}, {\\\"name\\\": \\\"itemPurchased\\\", \\\"type\\\": \\\"string\\\"}, {\\\"name\\\": \\\"quantity\\\", \\\"type\\\": \\\"int\\\"}, {\\\"name\\\": \\\"price\\\", \\\"type\\\": \\\"double\\\"}, {\\\"name\\\": \\\"purchaseDate\\\", \\\"type\\\": {\\\"type\\\": \\\"long\\\", \\\"logicalType\\\": \\\"timestamp-millis\\\"}}, {\\\"name\\\": \\\"department\\\", \\\"type\\\": [\\\"null\\\", \\\"string\\\"], \\\"default\\\": null}]}\"}"
```

**Expected Response Output:**
```json
{
  "is_compatible": true
}
```

Now register the evolved schema version (Version 2) to finalize registration:

```bash
curl -X POST http://localhost:8081/subjects/purchases-value/versions   -H "Content-Type: application/vnd.schemaregistry.v1+json"   -d "{\"schema\": \"{\\\"type\\\": \\\"record\\\", \\\"name\\\": \\\"Purchase\\\", \\\"namespace\\\": \\\"com.kafkastreams.course\\\", \\\"fields\\\": [{\\\"name\\\": \\\"customerId\\\", \\\"type\\\": \\\"string\\\"}, {\\\"name\\\": \\\"itemPurchased\\\", \\\"type\\\": \\\"string\\\"}, {\\\"name\\\": \\\"quantity\\\", \\\"type\\\": \\\"int\\\"}, {\\\"name\\\": \\\"price\\\", \\\"type\\\": \\\"double\\\"}, {\\\"name\\\": \\\"purchaseDate\\\", \\\"type\\\": {\\\"type\\\": \\\"long\\\", \\\"logicalType\\\": \\\"timestamp-millis\\\"}}, {\\\"name\\\": \\\"department\\\", \\\"type\\\": [\\\"null\\\", \\\"string\\\"], \\\"default\\\": null}]}\"}"
```

**Expected Response Output:**
```json
{
  "id": 2
}
```

---

### Lab 3.5 — Code Generation Using the Avro Maven Plugin
To generate Java class files from your `purchase.avsc` schema file, configure the Maven compiler inside your `pom.xml`:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0" 
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.kafkastreams.course</groupId>
    <artifactId>schema-registry-lab</artifactId>
    <version>1.0-SNAPSHOT</version>

    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <avro.version>1.11.3</avro.version>
        <confluent.version>7.6.0</confluent.version>
    </properties>

    <repositories>
        <repository>
            <id>confluent</id>
            <url>https://packages.confluent.io/maven/</url>
        </repository>
    </repositories>

    <dependencies>
        <dependency>
            <groupId>org.apache.avro</groupId>
            <artifactId>avro</artifactId>
            <version>${avro.version}</version>
        </dependency>
        <dependency>
            <groupId>io.confluent</groupId>
            <artifactId>kafka-avro-serializer</artifactId>
            <version>${confluent.version}</version>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.avro</groupId>
                <artifactId>avro-maven-plugin</artifactId>
                <version>${avro.version}</version>
                <executions>
                    <execution>
                        <phase>generate-sources</phase>
                        <goals>
                            <goal>schema</goal>
                        </goals>
                        <configuration>
                            <sourceDirectory>${project.basedir}/src/main/avro/</sourceDirectory>
                            <outputDirectory>${project.builddir}/generated-sources/avro/</outputDirectory>
                            <stringType>String</stringType>
                        </configuration>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>
</project>
```

---

### Detailed Breakdown of the Maven pom.xml & Configuration Plugins

Here is what each section inside the `pom.xml` configuration actually does in plain English:

*   `properties`: Defines shared variable settings used throughout the build script.
    *   `maven.compiler.source / target`: Tells Maven to compile and build using Java 17 logic.
    *   `avro.version`: The version of the Apache Avro library we will download.
*   `repositories`: Tells Maven where to look for packages that are not hosted on standard Maven Central.
    *   `confluent`: Points to Confluent's custom repository URL so Maven can locate and download `kafka-avro-serializer`.
*   `avro-maven-plugin`: The specific plugin compiler that translates Avro `.avsc` files into Java source code files.
*   `phase: generate-sources`: Tells Maven to run the code generation step during the `generate-sources` phase, which runs automatically before the Java compilation step.
*   `goals / schema`: Tells the plugin to execute the `schema` compilation compiler logic.
*   `sourceDirectory: src/main/avro/`: Specifies the folder path where the plugin should search for `.avsc` schema files.
*   `outputDirectory`: The directory folder path where the generated Java code (e.g., `Purchase.java`) will be saved.
*   `stringType: String`: Configures the Avro compiler to generate standard Java `String` classes for string fields instead of Avro's default `CharSequence` types (which makes Java programming much easier).

---

#### Verification Command
To compile the project and generate sources:

```bash
mvn clean compile
```

This compiles the Avro schema and generates a Java file named `Purchase.java` inside the target directory `target/generated-sources/avro/com/kafkastreams/course/Purchase.java`.
