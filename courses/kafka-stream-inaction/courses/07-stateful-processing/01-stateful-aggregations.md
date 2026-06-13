# Module 01: Stateful Aggregations & Caching

Unlike stateless transformations, which evaluate events in isolation, **stateful operations** require tracking and remembering information across multiple events. In a distributed stream processing topology, this requires localized, queryable state storage, transactional safety, and robust caching.

This module details the stateful aggregation operators in the Kafka Streams DSL, key-grouping requirements, caching mechanics, and state store storage selections.

---

## 1. Stateful vs. Stateless Processing Paradigms

*   **Stateless Operations** (e.g. `filter`, `mapValues`): Do not maintain memory. Each record is processed independently. If the JVM crashes, the application starts processing subsequent messages without needing to reconstruct historical context.
*   **Stateful Operations** (e.g. `aggregate`, `reduce`, `count`, `join`): Require memory of past events. To calculate a running average, count user visits, or join two streams within a time window, the application must query previously saved records.

---

## 2. Stateful Operators: Reduce, Aggregate, and Count

Before performing any aggregation in the DSL, you must group the stream. This creates a `KGroupedStream` from which you execute stateful aggregations.

### 2.1 The Key-Grouping Prerequisites
*   **`groupByKey()`**: Groups records by their existing key. Since the key is unchanged, no repartitioning occurs.
*   **`groupBy(KeyValueMapper)`**: Groups records by a newly computed key. **Triggers downstream repartitioning** before the aggregation executes because record keys determine partition destinations.

---

### 2.2 The `reduce` Operator
*   **Definition**: Combines incoming values of the same key into a single accumulated value.
*   **Type Constraint**: The output value type **must be the same** as the input value type.
*   **Lifecycle**: No initializer function is needed; the first record that arrives for a key serves as the initial value.

#### Reduce Example: Running Player Score Sums
```java
KStream<String, Double> playerScores = builder.stream("poker-game",
        Consumed.with(Serdes.String(), Serdes.Double()));

playerScores.groupByKey()
            .reduce(Double::sum, Materialized.as("Running-Scores-Store"))
            .toStream()
            .to("total-scores", Produced.with(Serdes.String(), Serdes.Double()));
```

---

### 2.3 The `aggregate` Operator
*   **Definition**: Aggregates incoming values of the same key into a custom result.
*   **Type Flexibility**: The output value type **can be different** from the input value type.
*   **Lifecycle**: Requires a user-supplied **`Initializer`** to define the starting value, and an **`Aggregator`** to apply the transformation.

#### Case Study: Customer Stock Transaction Summaries
We want to consume a stream of individual stock transactions and aggregate them into a custom `TransactionSummary` containing total bought/sold volume, highest/lowest price, and dollar values.

##### Domain Models:
```java
public record Transaction(String symbol, double sharePrice, long numberShares, boolean isPurchase) {}
public record TransactionSummary(double purchaseDollarAmount, long purchaseShareVolume) {}
```

##### Aggregator Code:
```java
package com.enterprise.streams.aggregations;

import org.apache.kafka.streams.kstream.Aggregator;

public class StockAggregator implements Aggregator<String, Transaction, TransactionSummary> {

    @Override
    public TransactionSummary apply(String symbolKey, Transaction txn, TransactionSummary aggregate) {
        if (txn.isPurchase()) {
            double additionalDollars = txn.numberShares() * txn.sharePrice();
            long newVolume = aggregate.purchaseShareVolume() + txn.numberShares();
            double newDollars = aggregate.purchaseDollarAmount() + additionalDollars;
            return new TransactionSummary(newDollars, newVolume);
        }
        return aggregate;
    }
}
```

##### Integration Pipeline:
```java
KStream<String, Transaction> txStream = builder.stream("stock-transactions",
        Consumed.with(Serdes.String(), txnSerde));

// Grouping by symbol (since key is client-id). Triggers repartitioning.
txStream.groupBy((key, value) -> value.symbol(), Grouped.with(Serdes.String(), txnSerde))
        .aggregate(
                () -> new TransactionSummary(0.0, 0L), // Initializer
                new StockAggregator(),                  // Aggregator
                Materialized.as("Stock-Agg-Store")      // State Store configuration
        )
        .toStream()
        .to("stock-aggregations", Produced.with(Serdes.String(), summarySerde));
```

---

### 2.4 The `count` Operator
*   **Definition**: Tracks the total number of records processed per key.
*   **Syntactic Sugar**: Built as a shorthand wrapper for a standard aggregation that increments a `Long` value.

```java
KStream<String, String> userLogins = builder.stream("logins", Consumed.with(Serdes.String(), Serdes.String()));

userLogins.groupByKey()
          .count(Materialized.as("Login-Counts-Store"))
          .toStream()
          .to("login-totals", Produced.with(Serdes.String(), Serdes.Long()));
```

---

## 3. The Memory Caching Layer

To optimize broker traffic and state store writes, Kafka Streams inserts an **in-memory cache** directly in front of the state store.

```
                  [ Key-Value Updates ]
                            │
                            ▼
                    ┌───────────────┐
                    │ In-Memory     │
                    │ Cache         │ (Accumulates and deduplicates in-memory)
                    └───────┬───────┘
                            │ (Flushes on memory limit or commit interval)
                            ├──────────────────────────┐
                            ▼                          ▼
                   ┌─────────────────┐       ┌─────────────────┐
                   │  Local Database │       │ Changelog Topic │
                   │   (RocksDB)     │       │   (Kafka Broker)│
                   └─────────────────┘       └─────────────────┘
```

### 3.1 Caching Mechanics
1.  **Deduplication**: If a key receives updates `A -> B -> C` rapidly, the cache only stores the latest value `C`.
2.  **Flushing**: The cache flushes to the local state store and writes to the changelog topic on the broker under two conditions:
    *   **Size limit reached**: The aggregate memory used by cache buffers across threads exceeds the configured `cache.max.bytes.buffering` (default: 10 MB).
    *   **Commit interval reached**: The background thread triggers a commit cycle (default: 30,000 ms / 30 seconds).
3.  **Downstream Impact**: Downstream processors only receive the latest state updates when the cache flushes. You will not see intermediate calculations.

### 3.2 Configuring Caching
*   **Disable Globally**: Set the configuration property `StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG` to `0`. This is helpful for local development to inspect every state transition immediately.
*   **Disable Per-Store**: Use the `Materialized` configuration object:
    ```java
    Materialized.as("poker-scores").withCachingDisabled()
    ```

---

## 4. In-Memory vs. Persistent State Stores

When configuring a stateful operator, you can select the state store implementation.

| Feature | Persistent Store (Default) | In-Memory Store |
| :--- | :--- | :--- |
| **Storage Engine** | RocksDB (Local C++ database) | Java Heap Map |
| **Data Resiliency** | Durable on disk + Changelog backed | Volatile memory + Changelog backed |
| **Lookup Latency** | Low (microsecond reads, disk/page cache dependent) | Ultra-low (nanosecond reads) |
| **Restart Recovery Time** | **Fast** (reads from local checkpoint offset) | **Slow** (must replay entire changelog topic) |
| **Memory Constraints** | Safe for large datasets (off-heap memory) | Subject to JVM `OutOfMemoryError` on large key spaces |

### 4.1 Configuring an In-Memory Store
To swap the default persistent store for an in-memory store, supply a custom `StoreSupplier` to the `Materialized` configuration:

```java
pokerScoreStream.groupByKey()
                .reduce(Double::sum,
                        Materialized.<String, Double>as(
                            Stores.inMemoryKeyValueStore("memory-scores-store")
                        )
                        .withKeySerde(Serdes.String())
                        .withValueSerde(Serdes.Double())
                );
```

> [!CAUTION]
> If you utilize in-memory stores, implement a **memory eviction policy** (e.g., using `Stores.lruMap(String, int)`) if your key space is unbounded. Without eviction, your application heap will continuously grow, eventually triggering garbage collection pauses and JVM memory crashes.
