# Module 12 — Spring Kafka Streams Integration

In this module, we will discuss Spring Kafka Streams Integration. We will cover the core architecture of Kafka Streams and study the `@EnableKafkaStreams` annotation. We will examine the Streams lifecycle managed by `StreamsBuilderFactoryBean`. Next, we will cover state stores (RocksDB vs. In-memory) and explore KStream-KTable joins and windowed aggregations. Finally, we will cover troubleshooting, review Socratic questions, and implement hands-on labs with complete code structures.

---

## 1. Academic Lecture: EnableKafkaStreams, StreamsBuilderFactoryBean & State Stores

### Basic Level: Streams Design & @EnableKafkaStreams

#### What is Kafka Streams?
Kafka Streams is a client library for building applications and microservices, where the input and output data are stored in Kafka clusters. It combines the simplicity of writing standard Java applications with the power of distributed stream processing.

#### `@EnableKafkaStreams` & Auto-Configuration
In Spring Boot, you do not need to manually configure the lifecycle of Kafka Streams.
* **How it works**: Simply by adding the `@EnableKafkaStreams` annotation to a configuration class, Spring Boot auto-configures a `StreamsBuilderFactoryBean` bean. This factory bean:
  1. Instantiates a `StreamsBuilder` instance.
  2. Initiates the streams lifecycle when the Spring application context starts up.
  3. Stops the stream threads gracefully when the container stops.

---

### Intermediate Level: State Stores & Lifecycle Events

#### State Stores
Stream processing can be **stateless** (e.g. mapping or filtering messages) or **stateful** (e.g. aggregating values or joining streams). Stateful operations require a **State Store** to store intermediate calculations (such as total spend per customer).
* **RocksDB**: By default, Kafka Streams uses RocksDB (an embedded, high-performance key-value database written in C++) as its local state store. RocksDB stores data on the local disk of the microservice pod.
* **Changelog Topics**: To guarantee fault tolerance, every local state store is backed by a replicated **changelog topic** on the Kafka broker. If a pod crashes and restarts elsewhere, the new pod reads the changelog topic to reconstruct its local RocksDB store.

#### Lifecycle States
The streams application thread progresses through lifecycle states:
* `CREATED` ──► `REBALANCING` ──► `RUNNING` ◄──► `PENDING_SHUTDOWN` ──► `NOT_RUNNING`
* Spring allows you to register state listeners on the `StreamsBuilderFactoryBean` to track rebalance events or trigger alerts if a thread crashes.

---

### Advanced Level: Co-Partitioning Joins & Windowing

#### KStream-KTable Joins
Joining a real-time stream of events (`KStream` of purchases) with a static profile lookup table (`KTable` of customers) requires **Co-Partitioning**:
* **Co-Partitioning Rule**: Both the stream and the table topics *must* have the identical number of partitions, and messages must be published using the identical key and partitioner strategy.
* If partition counts do not match, Kafka Streams will throw a runtime error, or silently fail to join records because they route to different threads.

#### Windowed Aggregations
To track customer spend over time, we group data using **Windows**:
* **Tumbling Window**: Fixed-size, non-overlapping time intervals (e.g., aggregate spend from 9:00 to 9:05, then 9:05 to 9:10).
* **Hopping Window**: Fixed-size, overlapping time intervals (e.g., 5-minute window that recalculates every 1 minute).
* **Session Window**: Inactivity-based windows (e.g., groups all purchases together until the customer goes inactive for 30 minutes).

---

## 2. Theory & Production Best Practices

### KStream vs. KTable Semantics

| Feature | KStream (Event Stream) | KTable (Changelog / State) |
| :--- | :--- | :--- |
| **Interpretation** | Append-only (every message is new) | Upsert-only (latest value per key) |
| **Data Representation** | A stream of history | A snapshot of current state |
| **Materialized Store?** | No | Yes |
| **Join Behavior** | Joins values using timestamps | Joins latest state values |

### RocksDB vs. In-Memory State Stores

| Metric | RocksDB (Default) | In-Memory State Store |
| :--- | :--- | :--- |
| **Data Limit** | Bound by local disk storage capacity | Bound by JVM Heap space (RAM) |
| **Performance** | Fast (off-heap disk cache writes) | Extremely Fast (no disk serializations) |
| **Garbage Collection**| No impact on JVM garbage collection | High impact (heap memory contains store objects)|
| **State Retention** | Survives application restart | Lost on restart (must rebuild from changelog)|

---

## 3. Common Errors & Troubleshooting

### 1. Co-partitioning Mismatch Exception
* **Symptom**: Topology fails to start, throwing `TopologyException: KStream-KTable join requires co-partitioning`.
* **Root Cause**: The stream topic (e.g. `purchases` with 12 partitions) and the table topic (e.g. `customers` with 3 partitions) have different partition counts.
* **Fix**: Recreate the topics on the broker with identical partition counts.

### 2. InvalidStateStoreException: State Store is Migrating
* **Symptom**: Application throws `InvalidStateStoreException: State store is not open`.
* **Root Cause**: The application partition is rebalancing, and the state store is currently closed while it synchronizes offset changes.
* **Fix**: Wait for the streams lifecycle state to transition back to `RUNNING` before attempting queries, or catch the exception and retry.

### 3. RocksDB Off-Heap Memory Out of Memory (OOM)
* **Symptom**: Pod crashes with exit code 137, indicating OS killed the process.
* **Root Cause**: RocksDB allocates native C++ off-heap memory. If you run many state stores, native memory usage exceeds the Docker container memory limits.
* **Fix**: Configure a custom RocksDB config setter class to limit block cache size: `rocksdb.config.setter` configuration.

---

## 4. Socratic Review Questions

### Question 1
*Why must a KStream-KTable join be co-partitioned on both key and partition count?*
* **Answer**: Because Kafka Streams tasks are distributed by partition index. A task processing partition 2 of the `purchases` stream will only look at partition 2 of the `customers` table store. If the customer key hashes to partition 2 on the table but partition 1 on the stream, they will be processed by different tasks and the join will never occur.

### Question 2
*How does Spring Boot's `StreamsBuilderFactoryBean` simplify lifecycle coordination compared to pure Java client code?*
* **Answer**: In pure Java, you must write boilerplate code to define properties, instantiate `KafkaStreams`, register exception handlers, call `start()`, and write JVM shutdown hooks. Spring handles all of this automatically, stopping and starting streams alongside the Spring context container.

### Question 3
*What is the purpose of the changelog topic in stateful operations?*
* **Answer**: Fault tolerance. If the local RocksDB disk storage is corrupted or the application pod is relocated, the task reads the changelog topic from offset 0 to reconstruct the state store in memory/disk.

### Question 4
*What is the difference between a Tumbling Window and a Hopping Window?*
* **Answer**: Tumbling windows have a fixed size and do not overlap (e.g. size 5s, hop 5s). Hopping windows have a fixed size but overlap because their advance interval is smaller than the window size (e.g. size 5s, hop 1s).

### Question 5
*How can you track when a streams application task is currently rebalancing?*
* **Answer**: By registering a `KafkaStreams.StateListener` callback on the `StreamsBuilderFactoryBean` at startup, intercepting changes to `REBALANCING` state.

---

## 5. Hands-on Labs

### Lab 12.1 — Kafka Streams Lifecycle Configuration

#### Scenario
We will create a configuration class that registers a custom `KafkaStreamsConfiguration` bean, enabling Kafka Streams, setting RocksDB storage dirs, and tracking state changes.

#### Complete Configuration Java Code
Create the file [KafkaStreamsConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/KafkaStreamsConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsConfig;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.annotation.EnableKafkaStreams;
import org.springframework.kafka.annotation.KafkaStreamsDefaultConfiguration;
import org.springframework.kafka.config.KafkaStreamsConfiguration;
import org.springframework.kafka.config.StreamsBuilderFactoryBeanConfigurer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;

@Configuration
@EnableKafkaStreams // 1. Automatically registers StreamsBuilderFactoryBean
public class KafkaStreamsConfig {
    private static final Logger log = LoggerFactory.getLogger(KafkaStreamsConfig.class);

    // 2. Supply stream configuration parameters
    @Bean(name = KafkaStreamsDefaultConfiguration.DEFAULT_STREAMS_CONFIG_BEAN_NAME)
    public KafkaStreamsConfiguration defaultKafkaStreamsConfig() {
        Map<String, Object> props = new HashMap<>();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "spend-analytics-app");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.STATE_DIR_CONFIG, "C:/Users/Admin/Desktop/projects/learning-repo/courses/state-store");
        
        return new KafkaStreamsConfiguration(props);
    }

    // 3. Register a configurer to track streams lifecycle state changes
    @Bean
    public StreamsBuilderFactoryBeanConfigurer streamsConfigurer() {
        return factoryBean -> factoryBean.setStateListener((newState, oldState) -> {
            log.info("KAFKA STREAMS STATE TRANSITION -> Old State: {} | New State: {}", oldState, newState);
        });
    }
}
```

---

### Lab 12.2 — KStream-KTable Join

#### Scenario
We will write a topology class that joins a stream of purchases (`KStream`) with a table of customer profiles (`KTable`) based on `customerId`.

#### Complete Topology Java Code
Create the file [PurchaseJoinTopology.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/topology/PurchaseJoinTopology.java) with the following content:

```java
package com.springkafka.course.topology;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.KTable;
import org.apache.kafka.streams.kstream.Joined;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Component
public class PurchaseJoinTopology {
    private static final Logger log = LoggerFactory.getLogger(PurchaseJoinTopology.class);

    // 1. Spring auto-injects StreamsBuilder from factory bean config
    @Autowired
    public void buildPipeline(StreamsBuilder streamsBuilder) {
        log.info("Initializing Purchase KStream-KTable Join Topology...");

        // 2. Consume Customer Profiles as a KTable
        KTable<String, String> customerTable = streamsBuilder.table(
            "customers",
            Consumed.with(Serdes.String(), Serdes.String())
        );

        // 3. Consume Purchases as a KStream
        KStream<String, String> purchaseStream = streamsBuilder.stream(
            "purchases",
            Consumed.with(Serdes.String(), Serdes.String())
        );

        // 4. Join Stream and Table using customerId as key
        KStream<String, String> enrichedStream = purchaseStream.join(
            customerTable,
            (purchaseJson, customerJson) -> {
                log.info("Match found! Joining Purchase: {} with Customer Profile: {}", purchaseJson, customerJson);
                return String.format("{\"purchase\":%s,\"customer\":%s}", purchaseJson, customerJson);
            },
            Joined.with(Serdes.String(), Serdes.String(), Serdes.String())
        );

        // 5. Output enriched results back to Kafka
        enrichedStream.to("enriched-purchases");
    }
}
```

---

### Lab 12.3 — Windowed Spend Aggregator

#### Scenario
We will create a stateful aggregation topology that tracks total customer spend over tumbling 5-minute windows and materializes the state in a local store named `"customer-spend-store"`.

#### Complete Aggregation Topology Java Code
Create the file [SpendAggregatorTopology.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/topology/SpendAggregatorTopology.java) with the following content:

```java
package com.springkafka.course.topology;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.common.utils.Bytes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.*;
import org.apache.kafka.streams.state.WindowStore;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Duration;

@Component
public class SpendAggregatorTopology {

    @Autowired
    public void buildAggregation(StreamsBuilder streamsBuilder) {
        // Consume purchases stream
        KStream<String, String> purchaseStream = streamsBuilder.stream(
            "purchases",
            Consumed.with(Serdes.String(), Serdes.String())
        );

        // Tumbling window configuration: 5-minute size duration
        TimeWindows tumblingWindow = TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(5));

        purchaseStream
            .mapValues(val -> Double.parseDouble(val)) // Parse price value from JSON string
            .groupByKey(Grouped.with(Serdes.String(), Serdes.Double())) // Group by customer ID key
            .windowedBy(tumblingWindow) // Apply tumbling window
            .aggregate(
                () -> 0.0, // Initializer
                (key, newPrice, aggPrice) -> aggPrice + newPrice, // Aggregator logic
                Materialized.<String, Double, WindowStore<Bytes, byte[]>>as("customer-spend-store")
                    .withKeySerde(Serdes.String())
                    .withValueSerde(Serdes.Double())
            );
    }
}
```

---

### Step-by-Step Code Walkthrough & Parameter Configuration Tables

#### Step-by-Step Code Walkthrough

##### Lab 12.1 Walkthrough
1. **`@EnableKafkaStreams`**: Scans for classes with custom topology configurations.
2. **`STATE_DIR_CONFIG`**: Configures the local directory path on disk where RocksDB will persist the state files.
3. **`StreamsBuilderFactoryBeanConfigurer`**: Hooks into the Spring context container lifecycle, printing transition details.

##### Lab 12.2 Walkthrough
1. **`streamsBuilder.table`**: Creates a materialized state store for the topic records, matching keys to update local records.
2. **`KStream.join`**: Looks up incoming purchases against the local state table. If matches are found, it triggers the callback function.

##### Lab 12.3 Walkthrough
1. **`windowedBy`**: Triggers windowing mechanics.
2. **`Materialized.as("customer-spend-store")`**: Materializes the aggregated totals into a local RocksDB instance, exposing query targets.

---

### Configuration Parameter Tables

#### Spring Boot Kafka Streams Configuration Properties

| Property Key | Expected Type | Description |
| :--- | :--- | :--- |
| `APPLICATION_ID_CONFIG` | `String` | Unique application ID serving as the coordinator consumer group name. |
| `DEFAULT_KEY_SERDE_CLASS_CONFIG` | `Class` | Default serializer/deserializer class matching key types. |
| `DEFAULT_VALUE_SERDE_CLASS_CONFIG`| `Class` | Default serializer/deserializer class matching value types. |
| `STATE_DIR_CONFIG` | `String` | The local system directory path where RockDB storage files are persisted. |

