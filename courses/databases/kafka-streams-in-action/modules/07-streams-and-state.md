# Module 07 — Streams and State

In this module, we will explore stateful stream processing in Apache Kafka. We will analyze the core difference between stateless and stateful operations, identifying the architectural trade-offs of both. We will study why state is necessary for aggregations, joins, and deduplication. We will cover the `groupBy()` and `groupByKey()` DSL operators, understanding key repartitioning requirements and topology optimizations. We will examine the three aggregation primitives (`count()`, `aggregate()`, and `reduce()`) along with their functional interfaces (`Aggregator` and `Reducer`). We will look into Stream-Stream Joins, detailing inner, left-outer, and outer joins, `JoinWindows`, `ValueJoiner`, and the critical co-partitioning requirement. Finally, we will investigate the underlying local State Stores backed by RocksDB or in-memory tables, their JVM fault tolerance via internal changelog topics, standby replicas for low-latency failovers, naming strategies for stateful operations, and changelog configuration overrides.

---

## 1. Academic Lecture: Stateful Processing, Joins & State Stores

### Basic Level: Stateful Operations vs. Stateless Operations & Aggregation Primitives

#### Stateless vs. Stateful Operations
In stream processing, operations are divided into two categories:
* **Stateless Operations**: The application processes each incoming record completely in isolation. To execute the operation, it only inspects the fields of the current record. Examples include `filter()` and `mapValues()`. Because there is no historical context required, stateless operations are easy to scale and recover from failures instantly.
* **Stateful Operations**: To process the current record, the application must recall or look up information about previously processed records. Examples include calculating a running average, summing order totals, or joining two event streams together. This requires a **State Store** (a local database) to save historical contexts.

##### Stateful Trade-offs
While stateful processing is extremely powerful, it introduces design and operations trade-offs:
1. **Memory & Disk Footprint**: Stateful applications require local disk space (to store the databases) and off-heap memory (to run the database cache).
2. **Recovery Latency**: If an application instance crashes, the new instance must rebuild its local state stores from historical logs before it can resume processing.
3. **Data Replication**: Changes to the local state must be continuously written back to the Kafka brokers for backup (durable changelogs), increasing network and disk overhead.

##### Analogy: The Warehouse Packer vs. The Inventory Tally Clerk
> Think of two employees in a logistics warehouse:
> * **The Packer (Stateless)**: A worker stands at a table. Packages arrive one by one. The worker looks at the current package, puts a "FRAGILE" sticker on it if it contains glass, and pushes it down the line. The worker does not need to remember what package went by 5 minutes ago to sticker the current one.
> * **The Tally Clerk (Stateful)**: A clerk sits at a desk with a notebook (State Store). Every time a package for a specific customer passes, the clerk looks up the customer's name in the notebook, adds the weight of the current package to their historical total, writes the new total down, and flags if the customer has shipped more than 100 kg today. The clerk cannot do their job without the notebook (State). If the notebook gets lost, the clerk must sit down and reread all the shipping receipts from the morning to rebuild the numbers (State Restoration).

#### Why State is Needed
State is required whenever your business logic spans across multiple events:
* **Aggregations**: Calculating metrics over time (e.g., counting purchases per customer, summing transaction values, or tracking the minimum temperature recorded).
* **Joins**: Combining events from two streams that happen within a certain time window (e.g., matching a purchase event with a customer loyalty swipe event).
* **Deduplication**: Filtering out duplicate events by remembering what record keys have been seen within a specific time frame (e.g., ignoring duplicate API requests).

#### The Three Aggregation Primitives
Kafka Streams provides three primary ways to summarize grouped data:

##### 1. `count()`
Increments an integer counter by 1 for every record that arrives for a given key. It is the simplest stateful operator.
* *Functional Signature*: Returns a `KTable<K, Long>`.

##### 2. `reduce()`
Combines incoming values sequentially into a single value of the **same type** (e.g., taking an incoming stream of numbers and summing them).
* *Functional Interface*: `Reducer<V>`. The `apply(V value1, V value2)` method merges two values of type `V` and returns a value of type `V`.
* *Characteristics*: Does not require an initial seed value. The first record that arrives for a key acts as the seed.

##### 3. `aggregate()`
Accumulates incoming values into a **different type** than the stream records (e.g., taking incoming transaction records and accumulating them into a complex `SummaryReport` object).
* *Functional Interface*: `Aggregator<K, V, VA>`. The `apply(K key, V value, VA aggregate)` method takes the record key, the incoming record value, and the current accumulated aggregate object, and returns the updated aggregate object.
* *Characteristics*: Requires an **Initializer** function (`Initializer<VA>`) to create the empty starting state object (the seed) for a key before any records arrive.

---

### Intermediate Level: Grouping, Stream-Stream Joins & Co-partitioning

#### Grouping: `groupBy()` vs. `groupByKey()`
To perform an aggregation, you must first group your stream. Kafka Streams offers two methods:
* **`groupByKey()`**: Groups the stream using the existing keys of the records.
  * *Repartitioning Impact*: **None**. Since the keys are unchanged, the records are guaranteed to already reside on the correct partition on the broker.
* **`groupBy()`**: Modifies the record key using a mapper function (e.g., grouping transaction records by their `symbol` field instead of their original `transactionId` key).
  * *Repartitioning Impact*: **High**. Because the keys are modified, Kafka Streams must write the records back to a temporary internal topic and consume them again to guarantee that records with the same new key land on the same stream task.

#### Stream-Stream Joins
A stream-stream join correlates events from two separate `KStream` objects based on their keys within a specific time window. Kafka Streams supports three types:

```text
  Stream A (Left):  ───(Key: "A", Val: 10)────────(Key: "B", Val: 20)───►
                              ▲                          ▲
                              │     JOIN WINDOW          │
                              ▼                          ▼
  Stream B (Right): ───(Key: "A", Val: "X")─────────────────────────────►
```

1. **Inner Join (`join()`)**: Emits a joined record only if a record with the same key arrives on **both** streams within the configured time window. If either side is missing, nothing is written downstream.
2. **Left-Outer Join (`leftJoin()`)**: Always emits a record when a record arrives on the left (calling) stream. If a matching record exists on the right stream within the window, they are combined. If no match exists on the right, it emits the left value combined with a `null` right value.
3. **Outer Join (`outerJoin()`)**: Emits a record whenever a record arrives on **either** stream. If a match exists on the other side, they are combined. If not, it emits the record combined with `null` for the other side.

#### JoinWindows
Because streams are unbounded and records arrive at different times, you cannot perform an infinite database-style join. You must restrict the join to a temporal window.
* **Window Math**: When a record with key `K` and timestamp $T_A$ arrives on Stream A, it searches Stream B's state store for records with key `K` whose timestamps $T_B$ fall in the range:
  $$T_B \in [T_A - 	ext{beforeWindow}, T_A + 	ext{afterWindow}]$$
* **No Grace Window**: Once the window expires, records that arrive too late are ignored for the join.

#### ValueJoiner & StreamJoined
* **`ValueJoiner<V1, V2, VR>`**: The functional interface that merges the two matched values. Its `apply(V1 leftValue, V2 rightValue)` method returns the final enriched object `VR`.
* **`StreamJoined`**: The configuration helper used to specify the Serdes for keys and values of both streams, name the join step, and name the internal state stores used to hold the records during the window.

#### Co-partitioning Requirement
For a stream-stream join to work correctly, the input topics **must be co-partitioned**:
1. Both topics must have the **exact same number of partitions**.
2. Both topics must use the **same key serialization format** (e.g., both keys must be serialized as String, or both as Integer).
3. Both topics must use the **same partitioning strategy** (so matching keys are written to the same partition index).

*Why?* Kafka Streams assigns task instances based on partition indices (e.g., Task 0 processes Partition 0 of Topic A and Partition 0 of Topic B). If partition counts differ, or keys are hashed differently, matching keys will land on different tasks on different machines, and the join will fail silently (generating zero results).

---

### Advanced Level: RocksDB vs. In-memory, Standby Replicas, Naming Shifting & Optimizations

#### State Stores under the Hood: RocksDB vs. In-Memory
To support aggregations and joins, Kafka Streams must save records in a local state database. There are two built-in options:

##### 1. RocksDB-Backed Stores (Default)
RocksDB is an embedded, high-performance, key-value transactional database written in C++. It runs directly inside the JVM process but stores its data **off-heap** on the server's local disk.
* *Pros*: Can store datasets much larger than the available JVM heap memory. Disk-persistent, meaning JVM crashes do not lose data.
* *Cons*: Requires JNI (Java Native Interface) crossings, which add minor CPU overhead. Requires tuning off-heap memory properties.

##### 2. In-Memory Stores
Stores records directly in JVM heap memory as a Java data structure.
* *Pros*: Fastest possible lookups and writes. Excellent for small datasets or low-latency lookups.
* *Cons*: Risk of `OutOfMemoryError` if the dataset grows too large. On restart, the store is completely empty and must be rebuilt by consuming the entire changelog topic, causing significant recovery lag.

#### Changelog Topics & Checkpoint Files
To ensure fault tolerance, every state store is backed by an internal, compacted Kafka topic on the broker (named `<application.id>-<store-name>-changelog`).
* **Durability Path**: When an active task writes a record to its local RocksDB store, it also produces that record to the changelog topic.
* **Checkpoint Files**: To avoid reading the entire changelog from the beginning during a clean reboot, Kafka Streams maintains a `.checkpoint` file in the task's local disk directory. This file stores the last successfully committed partition offset. On startup, RocksDB reads this offset and only pulls subsequent records from the changelog, bringing the store online in milliseconds.

#### Standby Replicas
When a server running your Kafka Streams instance crashes, its assigned tasks are migrated to a healthy server. If the tasks are stateful, the new server must download the changelog topic to rebuild the state stores, causing a processing pause (recovery lag).

To prevent this, you can configure **Standby Replicas** (`num.standby.replicas` > 0):
* Healthy instances are assigned "standby tasks" for partitions they do not actively process.
* The standby task does not execute the business topology; its sole job is to consume the changelog topic of the active task and populate a local clone of the RocksDB database.
* If the active task server crashes, the standby task is immediately promoted to active. Since its local state store is already caught up, processing resumes with **near-zero recovery delay**.

```text
  [ Active Task (Server A) ] ───► Writes State ───► [ Changelog Topic ]
                                                           │
                                                           ▼
  [ Standby Task (Server B) ] ◄── Shadows State ◄──────────┘
```

#### Naming Stateful Operations (The Naming Shift Problem)
By default, Kafka Streams auto-generates names for state stores using sequential counters (e.g., `KSTREAM-AGGREGATE-STATE-STORE-0000000001`).

If you modify your Java code to add a stateless node (like a `filter()`) upstream of the aggregation, the global counter shifts. The next time you deploy the application:
1. The state store's generated name changes to `KSTREAM-AGGREGATE-STATE-STORE-0000000002`.
2. The application looks for a local directory on disk with the new name, finds nothing, and assumes a cold boot.
3. The application looks for the changelog topic with the new name, finds nothing, and creates a brand-new, empty changelog.
4. **Result**: Your historical state is orphaned in the old directory and old changelog topic. Your application starts with an empty database.

##### Solution: Explicit Naming
Always explicitly name your state stores, grouping steps, and joins using the configuration builders:
* `Materialized.as("my-counting-store")`
* `Grouped.as("my-grouping-step")`
* `StreamJoined.as("my-join-step")`

This "freezes" the names, ensuring that they remain identical across code updates, protecting your state durability.

#### Topology Optimizations
By default, Kafka Streams compiles your DSL code literally, creating repartition nodes for every key change.
To optimize this, configure:
```properties
topology.optimization=all
```
This tells `StreamsBuilder` to analyze the compiled graph and rewrite it (e.g., collapsing redundant repartition topics into a single repartition node), significantly reducing network and disk I/O.

---

## 2. Theory & Production Best Practices

### RocksDB vs. In-Memory State Stores
Use the following comparison matrix to select the correct state store backend for your production applications:

| Feature / Metric | RocksDB Store (Default) | In-Memory Store |
| :--- | :--- | :--- |
| **Storage Medium** | Local Disk (Off-Heap) | JVM Heap Memory |
| **Capacity Limit** | Limited only by local disk size. | Limited by JVM Heap Size (OOM Risk). |
| **Read/Write Latency** | Low (microsecond range). | Extremely Low (nanosecond range). |
| **Restart Speed (Clean)** | Instant (reads `.checkpoint` file). | Slow (must rebuild from changelog). |
| **Restart Speed (Dirty)** | Moderately slow (rebuilds delta). | Slow (must rebuild from changelog). |
| **Primary Use Case** | Large tables, aggregations over long windows. | Small lookup tables, high-throughput short windows. |

---

## 3. Common Errors & Troubleshooting

### 1. `TopologyException: State store X is already added`
* **Root Cause**: You assigned duplicate explicit names using `Materialized.as()` in different parts of your code, or you tried to register the same store builder instance multiple times.
* **Fix**: Ensure every state store name within a single `application.id` is unique.

### 2. RocksDB Lock Exception
* **Symptom**: `org.rocksdb.RocksDBException: Lock file... resource temporarily unavailable`.
* **Root Cause**: Two instances of the same Kafka Streams application are running on the same server and sharing the same state directory (`/tmp/kafka-streams/`). Only one process can acquire a write lock on the local RocksDB directory.
* **Fix**: Ensure that each instance running on the same machine has a unique `state.dir` configuration path.

### 3. JVM Heap OutOfMemoryError (OOM)
* **Symptom**: JVM crashes with `java.lang.OutOfMemoryError: Java heap space`.
* **Root Cause**: Using in-memory state stores for a large key space, or configuring a join window that is too large, causing too many records to be retained in the heap.
* **Fix**:
  * Switch to RocksDB-backed stores to move the state off-heap.
  * Shorten join window durations to purge expired records faster.
  * If in-memory is required, use `Stores.lruMap(limit)` to evict old records.

---

## 4. Hands-on Labs

### Lab 7.1 — Count purchases per customer

#### Scenario
We will write a stateful streaming application that consumes retail purchases, groups them by the customer ID, counts the total transactions per customer, and writes the running counts to a target topic. We will explicitly name the state store as `purchase-counts` to ensure compatibility.

#### Complete Java Code
Create the file [PurchaseCounterApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/PurchaseCounterApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.common.utils.Bytes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.Grouped;
import org.apache.kafka.streams.kstream.KGroupedStream;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.KTable;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.kstream.Produced;
import org.apache.kafka.streams.state.KeyValueStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;

public class PurchaseCounterApp {
    private static final Logger log = LoggerFactory.getLogger(PurchaseCounterApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "purchase-counter-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, JsonSerde.class.getName());
        // Disable cache during development to see every update immediately
        props.put(StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG, 0);
        return props;
    }

    public static void main(String[] args) {
        log.info("Starting Purchase Counter...");

        StreamsBuilder builder = new StreamsBuilder();
        JsonSerde<Purchase> purchaseSerde = new JsonSerde<>();

        // 1. Consume purchases with keys representing customer IDs
        KStream<String, Purchase> purchases = builder.stream(
            "purchases",
            Consumed.with(Serdes.String(), purchaseSerde)
        );

        // 2. Group the stream by the key (Customer ID)
        KGroupedStream<String, Purchase> grouped = purchases.groupByKey(
            Grouped.with(Serdes.String(), purchaseSerde)
        );

        // 3. Count records, materializing the state in a RocksDB store with a frozen name
        KTable<String, Long> purchaseCounts = grouped.count(
            Materialized.<String, Long, KeyValueStore<Bytes, byte[]>>as("purchase-counts")
                .withKeySerde(Serdes.String())
                .withValueSerde(Serdes.Long())
        );

        // 4. Convert KTable back to a stream and output to target topic
        purchaseCounts.toStream().to(
            "purchase-counts-topic",
            Produced.with(Serdes.String(), Serdes.Long())
        );

        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());

        streams.cleanUp();
        streams.start();
        log.info("Purchase Counter running!");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Shutting down counter...");
            streams.close();
            log.info("Counter stopped.");
        }));
    }
}
```

#### Configuration Details
The following table explains what each line of the configuration properties does:

| Property Name | Value | Purpose |
| :--- | :--- | :--- |
| `StreamsConfig.APPLICATION_ID_CONFIG` | `"purchase-counter-group"` | Coordinates the partition group locking and identifies local RocksDB file storage directory names. |
| `StreamsConfig.BOOTSTRAP_SERVERS_CONFIG` | `"localhost:9092"` | Set of broker addresses for connection establishment. |
| `StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG` | `Serdes.String()...` | Falls back to String serialization for record keys. |
| `StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG`| `JsonSerde.class...` | Falls back to custom Java JSON serialization for values. |
| `StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG`| `0` | Disables internal 10MB memory cache so every aggregation event is flushed downstream immediately. |

---

### Lab 7.2 — Aggregate total spend per customer

#### Scenario
We will write a stateful streaming application that aggregates the total dollar amount spent by each customer. The application will compute:
$$	ext{Transaction Spend} = 	ext{Price} 	imes 	ext{Quantity}$$
We will initialize the aggregate state with `0.0` and accumulate transaction spend per key.

#### Complete Java Code
Create the file [SpendAggregatorApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/SpendAggregatorApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.Grouped;
import org.apache.kafka.streams.kstream.KGroupedStream;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.KTable;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.kstream.Produced;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;

public class SpendAggregatorApp {
    private static final Logger log = LoggerFactory.getLogger(SpendAggregatorApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "spend-aggregator-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, JsonSerde.class.getName());
        props.put(StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG, 0); // View updates immediately
        return props;
    }

    public static void main(String[] args) {
        log.info("Starting Spend Aggregator...");

        StreamsBuilder builder = new StreamsBuilder();
        JsonSerde<Purchase> purchaseSerde = new JsonSerde<>();

        KStream<String, Purchase> purchases = builder.stream(
            "purchases",
            Consumed.with(Serdes.String(), purchaseSerde)
        );

        KGroupedStream<String, Purchase> grouped = purchases.groupByKey(
            Grouped.with(Serdes.String(), purchaseSerde)
        );

        // Compute running spend accumulation: seed with 0.0
        KTable<String, Double> totalSpend = grouped.aggregate(
            () -> 0.0, // Initializer: sets starting value to 0.0
            (key, purchase, aggregate) -> {
                double txSpend = purchase.getPrice() * purchase.getQuantity();
                return aggregate + txSpend; // Aggregator: returns updated sum
            },
            Materialized.<String, Double, org.apache.kafka.streams.state.KeyValueStore<org.apache.kafka.common.utils.Bytes, byte[]>>as("total-spend")
                .withKeySerde(Serdes.String())
                .withValueSerde(Serdes.Double())
        );

        totalSpend.toStream().to(
            "total-spend-topic",
            Produced.with(Serdes.String(), Serdes.Double())
        );

        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());

        streams.cleanUp();
        streams.start();
        log.info("Spend Aggregator running!");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Shutting down aggregator...");
            streams.close();
            log.info("Aggregator stopped.");
        }));
    }
}
```

#### Configuration Details
The following table explains what each line of the configurations does:

| Property Name | Value | Purpose |
| :--- | :--- | :--- |
| `StreamsConfig.APPLICATION_ID_CONFIG` | `"spend-aggregator-group"` | Serves as the consumer group coordination namespace and sets local RocksDB directory targets. |
| `StreamsConfig.BOOTSTRAP_SERVERS_CONFIG` | `"localhost:9092"` | Locates the Kafka cluster bootstrap brokers. |
| `StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG` | `Serdes.String()...` | Registers String as the default key serialization. |
| `StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG`| `JsonSerde.class...` | Configures default value de/serialization to use our custom JSON serializer. |
| `StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG`| `0` | Disables internal buffer cache to ensure downstream writes happen on every message immediately. |

---

### Lab 7.3 — Stream-Stream join: correlate purchases with loyalty events

#### Scenario
We will join two incoming streams:
1. `purchases` (carrying purchases key-value records).
2. `loyalty-events` (carrying user loyalty event data).

If a purchase event and a loyalty event occur with the **same customer ID key** within a **5-minute window**, we will join them to create an `EnrichedPurchase` record and write it to `enriched-purchases`.

#### LoyaltyEvent Model Class
Create the file [LoyaltyEvent.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/LoyaltyEvent.java) with the following content:

```java
package com.kafkastreams.course.labs;

import java.io.Serializable;

public class LoyaltyEvent implements Serializable {
    private static final long serialVersionUID = 1L;

    private String customerId;
    private String tier;
    private int pointsEarned;

    public LoyaltyEvent() {}

    public LoyaltyEvent(String customerId, String tier, int pointsEarned) {
        this.customerId = customerId;
        this.tier = tier;
        this.pointsEarned = pointsEarned;
    }

    public String getCustomerId() { return customerId; }
    public void setCustomerId(String customerId) { this.customerId = customerId; }

    public String getTier() { return tier; }
    public void setTier(String tier) { this.tier = tier; }

    public int getPointsEarned() { return pointsEarned; }
    public void setPointsEarned(int pointsEarned) { this.pointsEarned = pointsEarned; }

    @Override
    public String toString() {
        return "LoyaltyEvent{" +
                "customerId='" + customerId + ''' +
                ", tier='" + tier + ''' +
                ", pointsEarned=" + pointsEarned +
                '}';
    }
}
```

#### EnrichedPurchase Model Class
Create the file [EnrichedPurchase.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/EnrichedPurchase.java) with the following content:

```java
package com.kafkastreams.course.labs;

import java.io.Serializable;

public class EnrichedPurchase implements Serializable {
    private static final long serialVersionUID = 1L;

    private Purchase purchase;
    private LoyaltyEvent loyaltyEvent;

    public EnrichedPurchase() {}

    public EnrichedPurchase(Purchase purchase, LoyaltyEvent loyaltyEvent) {
        this.purchase = purchase;
        this.loyaltyEvent = loyaltyEvent;
    }

    public Purchase getPurchase() { return purchase; }
    public void setPurchase(Purchase purchase) { this.purchase = purchase; }

    public LoyaltyEvent getLoyaltyEvent() { return loyaltyEvent; }
    public void setLoyaltyEvent(LoyaltyEvent loyaltyEvent) { this.loyaltyEvent = loyaltyEvent; }

    @Override
    public String toString() {
        return "EnrichedPurchase{" +
                "purchase=" + purchase +
                ", loyaltyEvent=" + loyaltyEvent +
                '}';
    }
}
```

#### Join Main Application Class
Create the file [LoyaltyJoinApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/LoyaltyJoinApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.JoinWindows;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Produced;
import org.apache.kafka.streams.kstream.StreamJoined;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.Properties;

public class LoyaltyJoinApp {
    private static final Logger log = LoggerFactory.getLogger(LoyaltyJoinApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "loyalty-join-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, JsonSerde.class.getName());
        return props;
    }

    public static void main(String[] args) {
        log.info("Launching Loyalty Correlation Join Engine...");

        StreamsBuilder builder = new StreamsBuilder();
        JsonSerde<Purchase> purchaseSerde = new JsonSerde<>();
        JsonSerde<LoyaltyEvent> loyaltySerde = new JsonSerde<>();
        JsonSerde<EnrichedPurchase> enrichedSerde = new JsonSerde<>();

        // 1. Consume the first stream (purchases)
        KStream<String, Purchase> purchases = builder.stream(
            "purchases",
            Consumed.with(Serdes.String(), purchaseSerde)
        );

        // 2. Consume the second stream (loyalty events)
        KStream<String, LoyaltyEvent> loyalties = builder.stream(
            "loyalty-events",
            Consumed.with(Serdes.String(), loyaltySerde)
        );

        // 3. Perform the stream-stream inner join over a 5-minute window
        KStream<String, EnrichedPurchase> enrichedStream = purchases.join(
            loyalties,
            (purchase, loyalty) -> {
                log.info("Match found for key! Joining values: {} + {}", purchase, loyalty);
                return new EnrichedPurchase(purchase, loyalty); // ValueJoiner logic
            },
            JoinWindows.ofTimeDifferenceWithNoGrace(Duration.ofMinutes(5)),
            StreamJoined.with(Serdes.String(), purchaseSerde, loyaltySerde)
                .withName("purchase-loyalty-join-node")
                .withStoreName("purchase-loyalty-join-stores")
        );

        // 4. Output the result to output topic
        enrichedStream.to(
            "enriched-purchases",
            Produced.with(Serdes.String(), enrichedSerde)
        );

        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());

        streams.cleanUp();
        streams.start();
        log.info("Loyalty Correlation Join engine active!");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Tearing down join application...");
            streams.close();
            log.info("Join application shutdown completed.");
        }));
    }
}
```

#### Configuration Details
The following table explains what each line of the configurations does:

| Property Name | Value | Purpose |
| :--- | :--- | :--- |
| `StreamsConfig.APPLICATION_ID_CONFIG` | `"loyalty-join-group"` | Coordinates the partitions lock and names local RocksDB state directories. |
| `StreamsConfig.BOOTSTRAP_SERVERS_CONFIG` | `"localhost:9092"` | List of brokers to join. |
| `StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG` | `Serdes.String()...` | Default key deserializer class config set to String. |
| `StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG`| `JsonSerde.class...` | Fallback value deserializer configuration targeting custom JSON. |

---

### Lab 7.4 — Observe the changelog topic and state store directory

#### Step-by-Step Instructions

##### 1. Locate the Local RocksDB Files
When you run a stateful application (like `PurchaseCounterApp`), Kafka Streams creates a directory on your filesystem to store its local state databases.

1. Open your terminal.
2. Launch a Java Shell by typing:
   ```bash
   jshell
   ```
3. Run the following command inside `jshell` to view the temporary path directory on your OS:
   ```java
   System.getProperty("java.io.tmpdir")
   ```
   *For Windows, this is usually outputted as `C:\Users\<Username>\AppData\Local\Temp`.*
4. Navigate to that path in your file explorer, and look for a directory named `kafka-streams`.
5. Under `kafka-streams`, you will see a folder matching the application ID (e.g., `purchase-counter-group`).
6. Inside that, navigate down the directory tree. You will find:
   * Tasks folders named as `0_0`, `0_1`, etc. (representing `subtopologyId_partitionId`).
   * A subfolder named `rocksdb`.
   * A subfolder named after your materialized store (`purchase-counts`). This folder contains the physical `.sst` database files.

##### 2. Inspect the Broker Changelog Topics
Every state store has a backing changelog topic. When Kafka Streams starts up, it automatically creates these topics on the broker.

1. Run the topic listing command to verify the presence of the changelogs:
   ```bash
   kafka-topics.sh --list --bootstrap-server localhost:9092
   ```
2. You will observe topics matching the naming pattern:
   * `purchase-counter-group-purchase-counts-changelog`
   * `spend-aggregator-group-total-spend-changelog`
   * `loyalty-join-group-purchase-loyalty-join-stores-left-changelog`
   * `loyalty-join-group-purchase-loyalty-join-stores-right-changelog`
3. Because these topics are configured with a **log compaction cleanup policy**, they keep only the latest value for each key. You can confirm the topic configuration by running:
   ```bash
   kafka-topics.sh --describe --bootstrap-server localhost:9092 --topic purchase-counter-group-purchase-counts-changelog
   ```
   *You will see the configuration output `cleanup.policy=compact`, ensuring database values do not grow indefinitely on the broker.*
