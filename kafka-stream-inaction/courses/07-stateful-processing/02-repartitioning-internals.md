# Module 02: Repartitioning Internals & Optimizations

In distributed stream processing, records must reside on the correct partition to ensure data consistency and co-partitioning. In Kafka, partitions are calculated using record keys. If you mutate a record's key, it will likely belong on a different partition. 

This module details how repartitioning works, the triggers that cause it, the performance costs associated with it, and how to optimize your topologies to prevent redundant repartition topics.

---

## 1. What is Repartitioning?

**Repartitioning** is the process of writing records with updated keys back to a temporary topic and immediately consuming them. 

```
┌────────────────────────────────────────────────────────────────┐
│                         SUB-TOPOLOGY 0                         │
│                                                                │
│ [Source Topic] ──► [Key Changing Node] ──► [Internal Sink]     │
└───────────────────────────────────────────────────┬────────────┘
                                                    │ (Writes to Kafka)
                                                    ▼
                                          [ Repartition Topic ]
                                                    │
                                                    ▼ (Consumes from Kafka)
┌───────────────────────────────────────────────────┴────────────┐
│                         SUB-TOPOLOGY 1                         │
│                                                                │
│ [Internal Source] ──► [Stateful Node] ──► [Sink Topic]         │
└────────────────────────────────────────────────────────────────┘
```

Under the hood, Kafka Streams inserts a new sink node to produce the records to the broker, which routes them to partition buckets based on the new key. A new source node is then registered to consume these records back into the next step of the topology. This split forms a new **Sub-topology**.

### 1.1 Repartitioning Triggers
Repartitioning is triggered when a **Key-Mutating Operator** is followed by a **Key-Dependent Operator**.

*   **Key-Mutating Operators**: `map`, `flatMap`, `selectKey`, or custom processors that can alter keys.
*   **Key-Dependent Operators**: `groupByKey`, `groupBy`, `join`, `leftJoin`, `outerJoin`, `aggregate`, `reduce`, or `count`.

If a key is changed but no downstream operation relies on the key (e.g. mapping the key and immediately writing it to a final output topic), the repartitioning is omitted (the record is partitioned naturally by the producer inside the sink node).

---

## 2. Redundant Repartitions: The Performance Cost

Because repartitioning requires writing data over the network to a broker and reading it back, it introduces:
*   **Latency**: Extra network hops degrade real-time performance.
*   **Broker Load**: Write and read I/O operations increase broker CPU usage.
*   **Storage Overhead**: Repartition topics consume disk space (although actively purged).

A common architectural bug is generating **redundant repartition topics** when branching a key-mutated stream.

#### Redundant Repartitioning Example:
```java
KStream<String, String> originalStream = builder.stream("input-topic");

// 1. Mutate key (repartitionRequired is set to true)
KStream<String, String> mutatedStream = originalStream.selectKey((k, v) -> v.split("-")[0]);

// 2. Perform aggregation (Triggers Repartition Topic 1)
mutatedStream.groupByKey().count().toStream().to("counts");

// 3. Perform join (Triggers Repartition Topic 2)
mutatedStream.join(otherStream, 
    (v1, v2) -> v1 + v2, 
    JoinWindows.ofTimeDifferenceWithNoGrace(Duration.ofMinutes(5))
).to("joined");
```
Here, because `mutatedStream` has its internal `repartitionRequired` flag set to `true`, **every** key-dependent child operator will trigger its own separate repartition topic, resulting in two duplicate repartition topics.

---

## 3. Resolving Redundant Repartitions

You can optimize the topology and eliminate redundant repartitioning topics using two approaches: **Proactive Repartitioning** or **Topology Optimizations**.

### 3.1 Proactive Repartitioning
You can manually force a single repartitioning operation using `KStream.repartition()`. This returns a new `KStream` with its `repartitionRequired` flag set to `false`, preventing downstream operations from triggering additional repartitioning.

```java
// 1. Mutate key
KStream<String, String> mutatedStream = originalStream.selectKey((k, v) -> v.split("-")[0]);

// 2. Proactively repartition once
KStream<String, String> repartitionedStream = mutatedStream.repartition(
    Repartitioned.<String, String>as("optimized-key-repartition")
                 .withKeySerde(Serdes.String())
                 .withValueSerde(Serdes.String())
);

// 3. Subsequent operations share the same repartitioned stream (NO redundant topics)
repartitionedStream.groupByKey().count().toStream().to("counts");
repartitionedStream.join(otherStream, 
    (v1, v2) -> v1 + v2, 
    JoinWindows.ofTimeDifferenceWithNoGrace(Duration.ofMinutes(5))
).to("joined");
```

#### Why Explicit Repartition Naming Matters
By providing `"optimized-key-repartition"` in the `Repartitioned` configuration, you ensure that the internal topic is named:
`<application-id>-optimized-key-repartition-repartition`

Explicit names are stable. If you add or remove operators elsewhere in the topology, this repartition topic name will not shift, avoiding data loss and ensuring migration safety during redeployments.

---

### 3.2 Automatic Topology Optimizations (Recommended)
Instead of manually identifying and optimizing repartition nodes, you can configure the Kafka Streams engine to analyze the DAG and optimize the topology automatically during compilation.

To enable optimizations:
1.  Add `StreamsConfig.TOPOLOGY_OPTIMIZATION_CONFIG` to your configuration properties.
2.  Pass the properties when building the topology (`builder.build(properties)`).

```java
Properties streamProperties = new Properties();
streamProperties.put(StreamsConfig.APPLICATION_ID_CONFIG, "optimized-pipeline");
streamProperties.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");

// Enable topological optimizations
streamProperties.put(StreamsConfig.TOPOLOGY_OPTIMIZATION_CONFIG, StreamsConfig.OPTIMIZE);

StreamsBuilder builder = new StreamsBuilder();

// Define topology (even with redundant branches)...
KStream<String, String> originalStream = builder.stream("input-topic");
KStream<String, String> mutatedStream = originalStream.selectKey((k, v) -> v.split("-")[0]);
mutatedStream.groupByKey().count().toStream().to("counts");
mutatedStream.join(otherStream, ...);

// Compile the topology with the optimization properties
Topology topology = builder.build(streamProperties);
```

When you pass the optimized properties to `builder.build()`, Kafka Streams traverses the logical DAG, identifies that the same key-mutated stream is branched for multiple key-dependent operators, removes the redundant repartition nodes, and inserts a single optimized repartition node.

> [!WARNING]
> Optimization is an **opt-in** behavior. If you build the topology via `builder.build()` without passing the optimized properties, Kafka Streams compiles the raw physical topology with all redundant repartition topics.
