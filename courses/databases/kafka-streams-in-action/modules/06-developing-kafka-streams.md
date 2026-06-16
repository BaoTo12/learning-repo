# Module 06 — Developing Kafka Streams

In this module, we will explore the native stream processing library of the Apache Kafka ecosystem: **Kafka Streams**. We will examine the core architecture of Kafka Streams, highlighting its nature as a client-side library rather than a dedicated server cluster. We will study stream processing topologies, building a Directed Acyclic Graph (DAG) consisting of source, processor, and sink nodes. We will dive into Kafka Streams configuration essentials, including `application.id`, `bootstrap.servers`, and custom Serdes (Serializer/Deserializer) for type safety. We will implement key stream operations like filtering, mapping values, side-effect peeking, flat-mapping, and dynamic splitting/branching. Additionally, we will cover advanced topics like the network cost of key mutations (repartitioning), naming topology nodes for metrics, dynamic message routing using a `TopicNameExtractor`, and interactive development techniques using state cleanups. Finally, we will complete hands-on labs including a yelling app, a retail purchase pipeline with card masking and branching, and topology visualization.

---

## 1. Academic Lecture: Kafka Streams Core Architecture & DSL

### Basic Level: Library Nature, Topologies & KStreams

#### The Client Library Concept (Not a Cluster)
Unlike other stream processing engines such as Apache Flink, Apache Spark Streaming, or Apache Storm, **Kafka Streams is not a cluster runtime**. It is a lightweight, client-side Java library. You do not deploy your Kafka Streams code onto a dedicated streaming server cluster. Instead, you import the library dependency (`org.apache.kafka:kafka-streams`) into your standard Java or Kotlin application and run it as a regular JVM process (e.g., a Spring Boot service, a Docker container, or a Kubernetes pod).

This design provides massive operational advantages:
* **No Extra Infrastructure**: You do not need to set up, monitor, or maintain a separate cluster of streaming servers.
* **Standard DevOps Workflows**: Scaling, upgrading, monitoring, and deploying your application uses the exact same pipelines and tools as your other microservices.
* **Embedded Execution**: The stream processing logic runs directly within your application process, minimizing external network hops and latency.

##### Analogy: The Smart Sorting Robot
> Imagine a physical retail warehouse with a central high-speed **Conveyor Belt** (Kafka).
> * **Spark/Flink Approach**: To label and sort packages, you build a completely separate, secondary warehouse building across the street (a Flink cluster) with its own supervisors, power supplies, and managers. You load packages from the first conveyor belt into trucks, drive them to the second warehouse, process them, and drive them back.
> * **Kafka Streams Approach**: Instead of a separate building, you simply buy a small, smart **Robotic Arm** (Kafka Streams library) and bolt it directly to the wall of your existing warehouse, right next to the conveyor belt. The arm runs on the same electricity and sits in the same room as your existing operations. If you get more packages, you just bolt a second robotic arm next to the first one. They coordinate automatically using the conveyor belt.

#### Stream Processing Topology: Source → Processor → Sink
In Kafka Streams, your processing logic is defined as a **Topology**. A topology is a Directed Acyclic Graph (DAG) of processing steps (nodes) connected by streams of records (edges).

There are three primary types of nodes in a topology:
1. **Source Node**: The entry point of your topology. It consumes raw byte records from one or more Kafka topics, uses configured Serdes to deserialize them into Java objects, and forwards them to downstream processor nodes.
2. **Processor Node**: An intermediate step that receives deserialized records, applies business logic (e.g., transforming, filtering, or routing), and forwards the modified records to downstream children nodes.
3. **Sink Node**: The terminal point of your topology. It receives processed Java objects, serializes them into bytes, and writes them out to a target Kafka topic.

```text
  [ Kafka Topic: input-topic ]
              │ (Raw Bytes)
              ▼
    ┌───────────────────┐
    │    Source Node    │ (Deserializes bytes to Java Objects)
    └─────────┬─────────┘
              │ (Stream of Java Objects)
              ▼
    ┌───────────────────┐
    │  Processor Node   │ (Transforms, filters, or routes records)
    └─────────┬─────────┘
              │ (Stream of Java Objects)
              ▼
    ┌───────────────────┐
    │     Sink Node     │ (Serializes Java Objects back to bytes)
    └─────────┬─────────┘
              │ (Raw Bytes)
              ▼
  [ Kafka Topic: output-topic ]
```

#### KStream: The Unbounded Stream of Records
A `KStream` is the core abstraction in the Kafka Streams DSL. It represents an **unbounded, continuous stream of structured records**. 
* **Key-Value Pairs**: Every record in a `KStream` consists of a key and a value (`KeyValue<K, V>`).
* **Append-Only / Insert-Only**: By default, a `KStream` treats every arriving record as an independent insert event. For example, if two records arrive with the same key, they do not overwrite each other; instead, they are both appended to the stream sequentially.
* **Unbounded**: The stream has no defined beginning or end. Records are processed as they arrive in real time, one by one.

#### Building a Topology with StreamsBuilder
To build a processing topology, you use the `StreamsBuilder` class. The `StreamsBuilder` provides a high-level functional API (the DSL) that allows you to define streams, map values, filter events, and route them to target topics in a clean, fluent syntax. Once you have defined your processing graph, you call `builder.build()` to compile the DSL instructions into a physical `Topology` object, which is then passed to the `KafkaStreams` execution client.

---

### Intermediate Level: Configurations, Serdes & DSL Operations

#### Configuration Essentials
Before starting your streaming application, you must define a set of configuration properties. While Kafka Streams has dozens of settings, three are absolutely mandatory:

##### 1. `application.id`
This configuration uniquely identifies your streaming application. It plays multiple critical roles:
* **Consumer Group ID**: Kafka Streams uses this value as the group ID for the embedded consumers. This means if you run multiple instances of your application with the same `application.id`, they will automatically form a consumer group and split the topic partitions among themselves to scale out processing.
* **Client ID Prefix**: All internal consumers, producers, and administrative clients will prefix their IDs with this string, making it easy to identify them in broker logs.
* **Local State Directory**: Kafka Streams stores local state databases (like RocksDB) in a folder named after this ID under your system's temp folder (`/tmp/kafka-streams/<application.id>`).

##### 2. `bootstrap.servers`
A comma-separated list of broker hostnames and ports (e.g., `localhost:9092,localhost:9093`) that the application uses to establish its initial connection to the Kafka cluster.

##### 3. Default Serdes
You must specify default Serdes for record keys and values so that Kafka Streams knows how to translate them to and from bytes:
* `default.key.serde`: The Serde class used for keys.
* `default.value.serde`: The Serde class used for values.

#### Serdes (Serializer + Deserializer)
Brokers only store and transmit raw arrays of bytes (`byte[]`). They have no concept of data types, object schemas, or classes. To perform stream processing, your application must translate these bytes.
A **Serde** (a portmanteau of **Ser**ializer and **De**serializer) wraps these two components:
* **Deserializer**: Converts incoming byte arrays from a Kafka topic into Java objects.
* **Serializer**: Converts outgoing Java objects back into byte arrays to be written to a Kafka topic.

```text
               Consumer Path (Ingest):
               ┌──────────┐      Deserializer      ┌─────────────┐
  [ byte[] ] ─►│  Source  │ ─────────────────────►│ Java Object │
               └──────────┘                        └─────────────┘
               
               Producer Path (Egress):
               ┌──────────┐       Serializer       ┌──────────┐
  [ byte[] ] ◄─│   Sink   │ ◄──────────────────────│ Java Obj │
               └──────────┘                        └──────────┘
```

The `org.apache.kafka.common.serialization.Serdes` utility class provides built-in Serde implementations for basic Java types:
* `Serdes.String()`
* `Serdes.Integer()`
* `Serdes.Long()`
* `Serdes.Double()`
* `Serdes.Bytes()`
* `Serdes.ByteArray()`

#### Kafka Streams + Schema Registry (Avro Serdes)
For production systems passing complex domain objects (like JSON, Avro, or Protobuf), manually writing serializers is error-prone. Instead, you integrate with a Confluent-compatible **Schema Registry**.

When using Avro with the Schema Registry:
1. You use a schema-aware Serde, such as Confluent's `SpecificAvroSerde` (which uses generated Java classes from Avro files).
2. You configure the Serde with the URL of the Schema Registry.
3. The Serde handles registering schemas dynamically when writing, and fetching schemas from the registry when reading.

##### Example Configuration for Schema Registry
```java
SpecificAvroSerde<Purchase> purchaseSerde = new SpecificAvroSerde<>();
Map<String, Object> serdeConfig = new HashMap<>();
serdeConfig.put("schema.registry.url", "http://localhost:8081");
purchaseSerde.configure(serdeConfig, false); // false means it is for record values, not keys
```

#### DSL Stream Operations

##### 1. `filter()` and `filterNot()`
* **`filter(Predicate)`**: Keeps only the records that match the given predicate condition. Non-matching records are discarded.
* **`filterNot(Predicate)`**: The inverse of `filter()`. Discards records that match the condition and keeps those that do not.
* *Characteristics*: Key-preserving. Does not change the record key or value.

##### 2. `mapValues()` vs. `map()`
* **`mapValues(ValueMapper)`**: Transforms the value of each record into a new value (possibly of a different type) while keeping the original key intact.
  * *Important*: Since the key remains unchanged, this operation **does not** trigger partition reassignment (repartitioning).
* **`map(KeyValueMapper)`**: Transforms both the key and the value of each record into a new key and value.
  * *Caution*: Changing the key means the record may belong to a different Kafka partition downstream. Therefore, this operation **always** triggers a downstream repartitioning phase if followed by a key-based operation.

##### 3. `peek()`
* **`peek(ForeachAction)`**: Allows you to inspect records (e.g., printing them to the console or writing log lines) as they flow through the stream.
* *Characteristics*: Stateless and non-mutating. It returns the exact same stream, ensuring that your inspection code does not accidentally alter the records. It is highly recommended for debugging.

##### 4. `split()` and `branch()`
* **`split()`**: Initiates a branching block to split a single stream into multiple independent streams based on predicates.
* **`branch(Predicate, Branched)`**: Defines a conditional branch. If a record matches the predicate, it is routed to this branch.
* **`defaultBranch(Branched)`**: Catches all records that did not match any of the previous predicates.
* *Usage*:
  ```java
  builder.stream("purchases")
      .split()
      .branch((k, v) -> v.getPrice() > 5.00, Branched.withConsumer(stream -> stream.to("expensive-purchases")))
      .defaultBranch(Branched.withConsumer(stream -> stream.to("regular-purchases")));
  ```

##### 5. `flatMapValues()`
* **`flatMapValues(ValueMapper)`**: Transforms a single record value into zero, one, or multiple new values, outputting them as separate records.
* *Characteristics*: Key-preserving. All generated records retain the original key, avoiding repartitioning overhead.

---

### Advanced Level: Repartitioning Costs, Naming Topology Nodes, Dynamic Routing & cleanUp()

#### Repartitioning Mechanics & Key Mutation Cost
To understand why key mutation is expensive, you must understand how Kafka handles partitions. Kafka uses a hash of the record key to determine which partition a record is written to (e.g., `hash(key) % partition_count`). This ensures that all records with the same key always land on the same partition on the brokers, which is a hard requirement for joins and stateful aggregations.

If you modify the key in your topology (e.g., using `map()` or `selectKey()`), the record's new key might hash to a different partition. Kafka Streams has no way of knowing where the record now belongs without writing it back to Kafka and reading it again.

Therefore:
1. When you call `map()` or `selectKey()`, Kafka Streams sets an internal flag on the stream indicating that the key has been modified.
2. If you follow this key mutation with a stateful operation (like `.groupByKey()`, `.join()`, or `.windowedBy()`), Kafka Streams automatically provisions an internal **repartition topic** (named `<application.id>-<node_name>-repartition`).
3. It writes the key-mutated records to this topic, and then immediately consumes them back.

##### The Repartitioning Overhead
This process is highly resource-intensive:
* **Network I/O**: Every record must be serialized, sent over the network to the Kafka broker, written to disk, read from disk, sent back over the network to the consumer, and deserialized.
* **Disk and Memory**: Increases broker storage consumption and cache pressures.
* **Latency**: Adds transit time, slowing down processing.

*Rule of Thumb*: Always prefer key-preserving operations like `mapValues()` and `flatMapValues()` over `map()` and `flatMap()` to avoid repartitioning unless changing the key is an absolute business requirement.

#### Naming Topology Nodes for Observability
By default, Kafka Streams auto-generates names for all topology nodes using the operation name followed by an incrementing sequence (e.g., `KSTREAM-SOURCE-0000000000`, `KSTREAM-MAPVALUES-0000000001`, `KSTREAM-SINK-0000000002`).

While this works, it introduces two severe problems:
1. **Unreadable Metrics**: When monitoring your topology metrics (CPU usage, record lag, thread states) via JMX or Prometheus, names like `KSTREAM-FILTER-0000000015` make it impossible to know which business rule is bottlenecked.
2. **Topological Instability**: If you insert a new filter node in the middle of your DSL code during a release, all auto-generated numbers downstream will shift (e.g., node `0000000008` becomes `0000000009`). Since Kafka Streams names its internal state directory folders and changelog topics after these node names, this shift **breaks backward compatibility**, causing the application to fail to find its local state on startup and trigger data corruption or full state rebuilds.

##### Best Practice: Explicit Naming
You can explicitly name nodes using `Named.as()`, `Consumed.as()`, `Produced.as()`, or `Grouped.as()`:
```java
builder.stream("transactions-topic", Consumed.with(Serdes.String(), purchaseSerde).withName("transactions-source"))
    .mapValues(CreditCardAnonymizer::anonymize, Named.as("anonymize-credit-cards"))
    .to("clean-transactions", Produced.with(Serdes.String(), purchaseSerde).withName("clean-transactions-sink"));
```

This ensures that the topology names remain stable even if you add or remove other nodes, and makes your application metrics completely self-documenting.

#### Dynamic Routing with TopicNameExtractor
Sometimes, you do not want to write records to a single hardcoded topic name. Instead, you need to route records dynamically to different topics based on:
* The record key.
* The record value.
* Metadata headers in the record context.

To achieve this, the `to()` sink method has an overload accepting a `TopicNameExtractor<K, V>`. The extractor inspects each record and returns the string name of the target topic.

##### Header-Based Topic Name Extractor Example
Here is a complete Java implementation of a custom `TopicNameExtractor` that reads a custom `"routing"` header from the record's context to determine where the message should land:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.header.Header;
import org.apache.kafka.common.header.Headers;
import org.apache.kafka.streams.processor.RecordContext;
import org.apache.kafka.streams.processor.TopicNameExtractor;
import java.nio.charset.StandardCharsets;

public class HeaderTopicNameExtractor implements TopicNameExtractor<String, String> {
    
    private final String defaultTopic;

    public HeaderTopicNameExtractor(String defaultTopic) {
        this.defaultTopic = defaultTopic;
    }

    @Override
    public String extract(String key, String value, RecordContext recordContext) {
        Headers headers = recordContext.headers();
        if (headers != null) {
            Header routingHeader = headers.lastHeader("routing-destination");
            if (routingHeader != null && routingHeader.value() != null) {
                return new String(routingHeader.value(), StandardCharsets.UTF_8);
            }
        }
        // Fallback to default topic if header is missing
        return defaultTopic;
    }
}
```

#### Interactive Development & KafkaStreams.cleanUp()
During development and local testing, you will frequently modify your streaming topologies. These changes often make existing local state databases (stored on your laptop at `/tmp/kafka-streams/<application.id>/`) incompatible with the new code, resulting in boot crashes.

To solve this, you can call `kafkaStreams.cleanUp()` before starting the client:
* **What it does**: Deletes the local state directory on disk, wiping out local rocksdb databases, checkpoints, and task directories.
* **When to use it**: Excellent for local testing to ensure a completely clean state at boot.
* **Production Warning**: **Never call `cleanUp()` in production at startup.** If you wipe out the state of a production app with a multi-gigabyte state store, the application will be forced to rebuild its entire state from scratch by consuming the historical changelog topics from beginning. This will saturate broker network bandwidth and cause massive consumer lag and application downtime.

---

## 2. Theory & Production Best Practices

### Kafka Connect SMT vs. Kafka Streams
It is common to confuse when to use a Kafka Connect Single Message Transform (SMT) and when to use Kafka Streams. Use this guide to make the right design decision:

| Feature / Goal | Use Kafka Connect SMT | Use Kafka Streams |
| :--- | :--- | :--- |
| **Primary Focus** | Data integration (Ingest/Egress). | Event-driven application logic. |
| **Complexity** | Simple transformations (renaming fields, masking, flat routing). | Complex processing, stateful calculations, business flows. |
| **State** | **Strictly Stateless**. Cannot look up historical records or join. | **Stateful & Stateless**. Supports local state stores, windows, and joins. |
| **Source/Sink Integration** | Direct connection to external databases, files, or APIs. | Read from Kafka, write to Kafka. No direct external database drivers. |
| **Coding Required** | None (declarative JSON config for built-ins). | Java/Kotlin coding required. |

### Stream Operations Repartitioning Behavior
Be aware of which operations trigger key changes and subsequent repartitioning:

| Operation | Key Mutated? | Triggers Repartitioning? | Recommended Alternative |
| :--- | :--- | :--- | :--- |
| `mapValues()` | No | **No** | *Use this whenever key mutation isn't needed.* |
| `flatMapValues()` | No | **No** | *Use this when mapping one value to multiple values.* |
| `filter()` / `filterNot()`| No | **No** | *Safe to place anywhere.* |
| `peek()` | No | **No** | *Safe to place anywhere.* |
| `map()` | Yes | **Yes** (if followed by stateful action) | Use `mapValues()` if only values are changing. |
| `selectKey()` | Yes | **Yes** (if followed by stateful action) | Preserve key if possible. |
| `flatMap()` | Yes | **Yes** (if followed by stateful action) | Use `flatMapValues()` if key remains the same. |

---

## 3. Common Errors & Troubleshooting

### 1. `TopologyException`
* **Symptom**: Application fails to start, throwing `org.apache.kafka.streams.errors.TopologyException: Invalid topology: Topic X has already been registered`.
* **Root Cause**: You have registered multiple source nodes reading from the same topic, or you assigned duplicate explicit names to different processor nodes using `Named.as()`.
* **Fix**: Ensure all custom node names in your topology are unique. If consuming the same topic in multiple places, merge the streams or create a single source and branch it.

### 2. `SerializationException` (Poison Pills)
* **Symptom**: Application crashes with `org.apache.kafka.common.errors.SerializationException`.
* **Root Cause**: A record arrives on the input topic with a format that does not match your configured deserializer (e.g., trying to parse a corrupted string as JSON, or receiving a null value).
* **Fix**:
  * Set a custom deserialization exception handler in your configurations:
    ```properties
    default.deserialization.exception.handler=org.apache.kafka.streams.errors.LogAndContinueExceptionHandler
    ```
    This logs the corrupt record (the poison pill) and continues processing the next record, rather than crashing the entire pipeline.
  * For production, build a custom handler that routes the bad record to a Dead Letter Queue (DLQ) topic for manual inspection.

### 3. `ConfigException`
* **Symptom**: `org.apache.kafka.common.config.ConfigException: Missing required configuration...`
* **Root Cause**: Forgot to set `application.id` or `bootstrap.servers` in the properties file.
* **Fix**: Verify your properties setup block and ensure both configurations are present and populated.

---

## 4. Hands-on Labs

### Lab 6.1 — Hello World: Yelling App

#### Scenario
We will build a basic Kafka Streams application that reads message values from an input topic (`input-topic`), transforms the values to uppercase characters (effectively "yelling" them), and writes the transformed records out to an output topic (`output-topic`).

#### Complete Java Code
Create the file [KafkaStreamsYellingApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/KafkaStreamsYellingApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Produced;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;

public class KafkaStreamsYellingApp {
    private static final Logger log = LoggerFactory.getLogger(KafkaStreamsYellingApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        
        // Uniquely identifies the app and coordinates partition assignment
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "yelling-app-group");
        
        // Kafka broker connection details
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        
        // Default Serdes for translating keys and values between Java types and broker bytes
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        
        return props;
    }

    public static void main(String[] args) {
        log.info("Starting Yelling App...");

        StreamsBuilder builder = new StreamsBuilder();
        
        // Step 1: Define the Source Node consuming from 'input-topic'
        KStream<String, String> sourceStream = builder.stream(
            "input-topic", 
            Consumed.with(Serdes.String(), Serdes.String())
        );

        // Step 2: Define the Processor Node transforming string values to uppercase
        KStream<String, String> yellingStream = sourceStream.mapValues(
            value -> value.toUpperCase()
        );

        // Step 3: Define the Sink Node producing back to 'output-topic'
        yellingStream.to(
            "output-topic", 
            Produced.with(Serdes.String(), Serdes.String())
        );

        // Step 4: Build the Topology and instantiate the KafkaStreams runner
        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());

        // Step 5: Clear local state before starting (recommended for local dev)
        streams.cleanUp();

        // Step 6: Start execution threads
        streams.start();
        log.info("Yelling App started successfully!");

        // Step 7: Handle graceful shutdown when the application stops
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Shutting down Yelling App...");
            streams.close();
            log.info("Yelling App stopped.");
        }));
    }
}
```

#### Configuration Details
The following table explains what each line of the configuration properties in `getConfig()` does:

| Property Name | Value | Purpose |
| :--- | :--- | :--- |
| `StreamsConfig.APPLICATION_ID_CONFIG` | `"yelling-app-group"` | The unique identifier for this application. Defines the Consumer Group ID for partition sharing and the local state folder name. |
| `StreamsConfig.BOOTSTRAP_SERVERS_CONFIG` | `"localhost:9092"` | The network connection list of brokers that the application connects to initially. |
| `StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG` | `Serdes.String()...` | Registers the default Serializer/Deserializer for incoming and outgoing keys as String. |
| `StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG`| `Serdes.String()...` | Registers the default Serializer/Deserializer for incoming and outgoing values as String. |

#### Running the Lab
1. Start your local Kafka broker (using Docker or binary install).
2. Create the topics:
   ```bash
   kafka-topics.sh --create --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --topic input-topic
   kafka-topics.sh --create --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --topic output-topic
   ```
3. Run the Java application class `KafkaStreamsYellingApp`.
4. Start a console producer to send messages to the input topic:
   ```bash
   kafka-console-producer.sh --bootstrap-server localhost:9092 --topic input-topic
   > hello kafka streams
   > yell at me please
   ```
5. Start a console consumer on the output topic:
   ```bash
   kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic output-topic --from-beginning
   > HELLO KAFKA STREAMS
   > YELL AT ME PLEASE
   ```

---

### Lab 6.2 — Retail Pipeline

#### Scenario
You are building an event processing pipeline for ZMart transactions.
1. Read purchases from the input topic `purchases`.
2. Anonymize credit card primary account numbers (PAN) by replacing the first 12 digits of the card string with `"xxxx-xxxx-xxxx-"` (e.g., `"1234-5678-9012-3456"` becomes `"xxxx-xxxx-xxxx-3456"`).
3. Log the record metadata using `peek()` for side-effect tracking.
4. Route purchases based on criteria using `split().branch()`:
   * **Branch 1 (Patterns)**: Route purchases where the transaction price is greater than `$5.00` to the `patterns` topic.
   * **Branch 2 (Rewards)**: Route purchases where the quantity purchased is greater than `0` to the `rewards` topic.
   * **Default Branch**: Send all other records to the `discards` topic.

#### Purchase Event Model Class
Create the file [Purchase.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/Purchase.java) with the following content:

```java
package com.kafkastreams.course.labs;

import java.io.Serializable;

public class Purchase implements Serializable {
    private static final long serialVersionUID = 1L;

    private String customerId;
    private String creditCardNumber;
    private double price;
    private int quantity;

    public Purchase() {}

    public Purchase(String customerId, String creditCardNumber, double price, int quantity) {
        this.customerId = customerId;
        this.creditCardNumber = creditCardNumber;
        this.price = price;
        this.quantity = quantity;
    }

    public String getCustomerId() { return customerId; }
    public void setCustomerId(String customerId) { this.customerId = customerId; }

    public String getCreditCardNumber() { return creditCardNumber; }
    public void setCreditCardNumber(String creditCardNumber) { this.creditCardNumber = creditCardNumber; }

    public double getPrice() { return price; }
    public void setPrice(double price) { this.price = price; }

    public int getQuantity() { return quantity; }
    public void setQuantity(int quantity) { this.quantity = quantity; }

    @Override
    public String toString() {
        return "Purchase{" +
                "customerId='" + customerId + ''' +
                ", creditCardNumber='" + creditCardNumber + ''' +
                ", price=" + price +
                ", quantity=" + quantity +
                '}';
    }
}
```

#### CreditCardAnonymizer Utility Class
Create the file [CreditCardAnonymizer.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/CreditCardAnonymizer.java) with the following content:

```java
package com.kafkastreams.course.labs;

public class CreditCardAnonymizer {
    
    /**
     * Replaces the first 12 digits of a credit card string with xxxx-xxxx-xxxx- 
     * while keeping the last 4 digits visible.
     */
    public static Purchase anonymize(Purchase purchase) {
        if (purchase == null) {
            return null;
        }
        String rawCard = purchase.getCreditCardNumber();
        if (rawCard == null || rawCard.trim().isEmpty()) {
            return purchase;
        }

        // Clean formatting hyphens/spaces to check length
        String cleanCard = rawCard.replace("-", "").replace(" ", "");
        if (cleanCard.length() < 16) {
            purchase.setCreditCardNumber("xxxx-xxxx-xxxx-xxxx");
            return purchase;
        }

        String lastFour = cleanCard.substring(12);
        purchase.setCreditCardNumber("xxxx-xxxx-xxxx-" + lastFour);
        return purchase;
    }
}
```

#### Custom JSON Serde implementation
For the laboratory, we will implement a simple JSON Serializer and Deserializer using standard Java Object Input streams, wrapping it as a Serde:

Create the file [JsonSerde.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/JsonSerde.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Deserializer;
import org.apache.kafka.common.serialization.Serde;
import org.apache.kafka.common.serialization.Serializer;
import java.io.*;
import java.util.Map;

public class JsonSerde<T extends Serializable> implements Serde<T> {

    @Override
    public void configure(Map<String, ?> configs, boolean isKey) {}

    @Override
    public void close() {}

    @SuppressWarnings("unchecked")
    @Override
    public Serializer<T> serializer() {
        return (topic, data) -> {
            if (data == null) return null;
            try (ByteArrayOutputStream baos = new ByteArrayOutputStream();
                 ObjectOutputStream oos = new ObjectOutputStream(baos)) {
                oos.writeObject(data);
                return baos.toByteArray();
            } catch (IOException e) {
                throw new RuntimeException("Serialization failure", e);
            }
        };
    }

    @SuppressWarnings("unchecked")
    @Override
    public Deserializer<T> deserializer() {
        return (topic, data) -> {
            if (data == null) return null;
            try (ByteArrayInputStream bais = new ByteArrayInputStream(data);
                 ObjectInputStream ois = new ObjectInputStream(bais)) {
                return (T) ois.readObject();
            } catch (IOException | ClassNotFoundException e) {
                throw new RuntimeException("Deserialization failure", e);
            }
        };
    }
}
```

#### Pipeline Main Application Class
Create the file [ZMartRetailPipelineApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/ZMartRetailPipelineApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serde;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Branched;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Produced;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;

public class ZMartRetailPipelineApp {
    private static final Logger log = LoggerFactory.getLogger(ZMartRetailPipelineApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "zmart-retail-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, JsonSerde.class.getName());
        return props;
    }

    public static void main(String[] args) {
        log.info("Launching ZMart Retail Streaming Pipeline...");

        StreamsBuilder builder = new StreamsBuilder();
        Serde<String> stringSerde = Serdes.String();
        Serde<Purchase> purchaseSerde = new JsonSerde<>();

        // 1. Consume purchases from 'purchases' topic
        KStream<String, Purchase> rawPurchases = builder.stream(
            "purchases",
            Consumed.with(stringSerde, purchaseSerde)
        );

        // 2. Anonymize credit cards using mapValues & Log metadata using peek
        KStream<String, Purchase> processedPurchases = rawPurchases
            .mapValues(CreditCardAnonymizer::anonymize)
            .peek((key, value) -> log.info("Processing transaction for Customer ID: {} | Key: {}", 
                value != null ? value.getCustomerId() : "NULL", key));

        // 3. Route records using split().branch()
        processedPurchases.split()
            .branch(
                (k, v) -> v != null && v.getPrice() > 5.00,
                Branched.withConsumer(s -> s.to("patterns", Produced.with(stringSerde, purchaseSerde)))
            )
            .branch(
                (k, v) -> v != null && v.getQuantity() > 0,
                Branched.withConsumer(s -> s.to("rewards", Produced.with(stringSerde, purchaseSerde)))
            )
            .defaultBranch(
                Branched.withConsumer(s -> s.to("discards", Produced.with(stringSerde, purchaseSerde)))
            );

        // Build, clean local states, and start application
        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());
        
        streams.cleanUp(); // Reset state directories during development
        
        streams.start();
        log.info("ZMart Retail Pipeline application is running!");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Closing application threads...");
            streams.close();
            log.info("Application closed successfully.");
        }));
    }
}
```

#### Configuration Details
The following table explains what each line of the configuration properties does:

| Property Name | Value | Purpose |
| :--- | :--- | :--- |
| `StreamsConfig.APPLICATION_ID_CONFIG` | `"zmart-retail-group"` | Uniquely names this streaming logic. Configures group coordination and sets local checkpoint paths. |
| `StreamsConfig.BOOTSTRAP_SERVERS_CONFIG` | `"localhost:9092"` | Defines connection points for locating brokers. |
| `StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG` | `Serdes.String()...` | Outlines the fallback deserializer for keys as plain Strings. |
| `StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG`| `JsonSerde.class...` | Tells Kafka Streams to fall back to our custom JSON Java serialization handler for objects when none are provided. |

#### Running the Lab
1. Create the topics:
   ```bash
   kafka-topics.sh --create --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --topic purchases
   kafka-topics.sh --create --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --topic patterns
   kafka-topics.sh --create --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --topic rewards
   kafka-topics.sh --create --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --topic discards
   ```
2. Run `ZMartRetailPipelineApp`.
3. In verification test code or console scripts, publish serialize objects and verify that masked data is written to the correct destinations based on purchase value boundaries and quantities.

---

### Lab 6.3 — Print Topology Description

#### Scenario
To understand node structures, connections, and flow branches, we will build a utility application that creates a topology object, calls `describe()`, and prints the graph out to the system console.

#### Complete Java Code
Create the file [TopologyPrinterApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/TopologyPrinterApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Produced;

public class TopologyPrinterApp {
    public static void main(String[] args) {
        StreamsBuilder builder = new StreamsBuilder();

        // Build topology
        KStream<String, String> sourceStream = builder.stream(
            "input-topic",
            Consumed.with(Serdes.String(), Serdes.String())
        );

        sourceStream.mapValues(value -> value.toUpperCase())
                    .to("output-topic", Produced.with(Serdes.String(), Serdes.String()));

        Topology topology = builder.build();

        // Print physical description out to console
        System.out.println("=== Physical Topology Layout ===");
        System.out.println(topology.describe());
        System.out.println("=================================");
    }
}
```

#### Understanding the Printed Output
Running the application yields the following output:

```text
=== Physical Topology Layout ===
Topologies:
   Sub-topology: 0
    Source: KSTREAM-SOURCE-0000000000 (topics: [input-topic])
      --> KSTREAM-MAPVALUES-0000000001
    Processor: KSTREAM-MAPVALUES-0000000001 (stores: [])
      --> KSTREAM-SINK-0000000002
      <-- KSTREAM-SOURCE-0000000000
    Sink: KSTREAM-SINK-0000000002 (topic: output-topic)
      <-- KSTREAM-MAPVALUES-0000000001
=================================
```

##### Explanations
* **`Sub-topology: 0`**: A subset of the topology graph that can run concurrently within a single stream task. Sub-topologies are bounded by repartition topics or source/sink nodes.
* **`KSTREAM-SOURCE-0000000000`**: The source node reading from topic `input-topic`. The arrow `-->` shows it points to the downstream processor `KSTREAM-MAPVALUES-0000000001`.
* **`KSTREAM-MAPVALUES-0000000001`**: The value mapping node that performs the logic. The `-->` shows it outputs to the sink node, while the `<--` shows its input came from the source node.
* **`KSTREAM-SINK-0000000002`**: The sink node writing transformed data back to the brokers in the `output-topic`.
