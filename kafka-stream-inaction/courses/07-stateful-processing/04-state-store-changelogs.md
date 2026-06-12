# Module 04: State Store Lifecycle & Durability

For stateful operations to function reliably, their underlying storage must be durable, performant, and resilient to application crashes and network rebalances. Kafka Streams solves this by combining local off-heap storage (**RocksDB**) with remote, fault-tolerant Kafka topics (**Changelog Topics**).

This module details state store internals, filesystem structures, recovery processes, standby replicas for fast failovers, and custom logging configurations.

---

## 1. Storage Engine Internals: RocksDB

By default, persistent state stores in Kafka Streams use **RocksDB**, an embedded, high-performance key-value store written in C++.
*   **Off-Heap Storage**: RocksDB runs within the same OS process but allocates memory off-heap. This keeps JVM garbage collection (GC) pauses low even when managing hundreds of gigabytes of state data.
*   **Log-Structured Merge-tree (LSM)**: RocksDB writes updates to an in-memory buffer called a MemTable. When full, the MemTable flushes to immutable Sorted String Table (SST) files on local disk. This design prioritizes high-throughput writes.

---

## 2. Filesystem Layout

State directories are created locally on each running worker instance.

### 2.1 Directory Structure
Kafka Streams uses the `state.dir` configuration (default: `/tmp/kafka-streams`) to set the root directory. Inside this directory, it structures files hierarchically:

```
[state.dir] (e.g., /tmp/kafka-streams)
   └── [application.id] (e.g., stock-transactions-app)
          ├── [Task Directory] (e.g., 0_0 - Sub-topology 0, Partition 0)
          │      ├── rocksdb
          │      │     └── [State Store Name] (e.g., Stock-Agg-Store)
          │      │            ├── 000003.sst
          │      │            ├── CURRENT
          │      │            └── MANIFEST
          │      └── .checkpoint (Tracks the last committed offset)
          └── [Task Directory] (e.g., 0_1 - Sub-topology 0, Partition 1)
```

*   **Task Directories (`SubTopology_Partition`)**: State stores are isolated per partition. Task `0_0` is the only thread accessing the store directory for Partition 0. There are no cross-thread lock contentions.

---

## 3. Durability Design: Changelog Topics

To guarantee durability, every state store is backed by an internal Kafka topic called a **Changelog Topic**.

*   **Topic Naming Convention**: `<application-id>-<state-store-name>-changelog`
*   **Log Compaction**: Changelog topics are configured with cleanup policy `compact`. This keeps only the latest record value for each key, allowing old historical records to be deleted.
*   **Durability Write Path**: When the memory cache flushes, it writes the aggregated record to the local state store and publishes the record to the changelog topic on the Kafka broker.

---

## 4. State Store Recovery & Checkpoints

If a machine crashes or a rebalance occurs, tasks are reassigned to healthy worker instances. The new worker must restore the state store's contents.

### 4.1 Checkpoint Files (`.checkpoint`)
For persistent state stores, Kafka Streams writes a `.checkpoint` file to the task directory during clean shutdowns.
*   **Checkpoint Content**: Maps state store names to the last written Kafka offsets.
*   **Recovery Optimization**: Upon restart, Kafka Streams reads the checkpoint offset and only replays records from the changelog topic *starting at that offset*, avoiding a full replay.

### 4.2 Exactly-Once Semantics (EOS) Recovery
When running in EOS mode (`processing.guarantee="exactly_once_v2"`):
*   The `.checkpoint` file is deleted when the state store opens.
*   If the application crashes unexpectedly, **no checkpoint file exists**.
*   **Safety Action**: Kafka Streams discards the local RocksDB files and performs a **complete recovery** by replaying the changelog topic from offset `0`. This guarantees that no duplicate or uncommitted transactions infect the state store.
*   If the shutdown is clean, the `.checkpoint` file is safely re-written.

---

## 5. Standby Replicas for Fast Failovers

Replaying a changelog topic for a 50 GB state store after a crash can take several minutes, stalling the processing pipeline. To resolve this, configure **Standby Replicas**.

*   **`num.standby.replicas`** (Default: 0): Defines the number of shadow tasks assigned to other nodes.
*   **Shadowing**: A standby task does not process records. Its only job is to consume from the active task's changelog topic and update its own local RocksDB state store.

```
[ Active Task (Node A) ] ──(Writes updates)──► [ Changelog Topic ]
                                                      │
                                                      ├──(Reads and updates local RocksDB)
                                                      ▼
                                           [ Standby Task (Node B) ]
```

*   **Instant Failover**: If Node A crashes, the Group Coordinator immediately promotes the standby task on Node B to active. Since Node B's local state store is already caught up, processing resumes with near-zero recovery time.

---

## 6. Customizing Changelog Topics

You can customize the underlying configurations of individual changelog topics using the `Materialized` builder's `withLoggingEnabled()` method.

#### Adjusting Cleanup Policies
If your state store has a very large key space, log compaction may not prevent disk growth. You can configure a combined `compact,delete` cleanup policy to delete older segments by age while retaining the latest values for active keys:

```java
Map<String, String> changelogConfigs = new HashMap<>();
// Combine Compaction with time-based deletion
changelogConfigs.put("cleanup.policy", "compact,delete");
changelogConfigs.put("retention.ms", "86400000"); // Delete segments older than 24 hours

KGroupedStream<String, String> grouped = input.groupByKey();

grouped.count(
    Materialized.<String, Long, KeyValueStore<Bytes, byte[]>>as("Counting-Store")
                .withLoggingEnabled(changelogConfigs) // Apply custom properties
);
```

> [!CAUTION]
> While you can disable changelog writing entirely using `.withLoggingDisabled()`, **this is highly discouraged**. If a node hosting a logging-disabled store crashes, there is no way to recover its data. The application will start processing with an empty state store, leading to data loss and corrupted business calculations.
