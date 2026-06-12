# Module 01: KTable Semantics, Tombstones, and Aggregations

At the foundation of stream processing lies the **Stream-Table Duality**. Resolving stateful questions requires modeling streams not just as a sequence of independent events, but as a dynamic, changing dataset. In the Kafka Streams DSL, this is represented by the **KTable** abstraction.

This module details the stream-table duality, tombstone delete semantics, and the mechanics of KTable aggregations using Adders and Subtractors.

---

## 1. The Stream-Table Duality

The relationship between an event stream and a database table is reciprocal:
*   **Stream as Table**: An event stream (like a `KStream`) can be viewed as a transaction log. By replaying the log from the beginning, you reconstruct the state of a database table.
*   **Table as Stream**: A database table can be viewed as a changelog stream (like a `KTable`). By capturing every `INSERT`, `UPDATE`, and `DELETE` on a table over time, you generate a stream of state changes.

```
       EVENT STREAM (KStream)                    CHANGELOG TABLE (KTable)
 ┌────────────────────────────────┐          ┌──────────────────────────────┐
 │ Key: "AAPL", Value: $150 (T1)  │ ───────► │ AAPL ──► $152 (Latest state) │
 │ Key: "MSFT", Value: $250 (T2)  │          │ MSFT ──► $250                │
 │ Key: "AAPL", Value: $152 (T3)  │          └──────────────────────────────┘
 └────────────────────────────────┘
    (3 discrete events captured)                (2 active key rows maintained)
```

### 1.1 Operational Distinctions
*   **`KStream` (Event Stream)**: Represents insert-only semantics. Each key-value pair is an independent fact. If two records arrive with key `"AAPL"`, they represent two distinct transactions.
*   **`KTable` (Update Stream)**: Represents update-changelog semantics. The key acts as a primary key. A new record with key `"AAPL"` overwrites the previous value for `"AAPL"`.

---

## 2. Tombstone Delete Semantics

Since a `KTable` models a database table, it must support record deletion.

*   **Tombstones**: Deletion is represented by sending a record with a valid key and a **`null` value**.
*   **State Store Purging**: When a task receives a null-value record, it deletes the key from the local state store and writes a tombstone record (key with a null payload) to the internal compacted changelog topic. This allows the broker's log cleaner to eventually discard the records during compaction.
*   **API Filter Operations**: Unlike `KStream.filter()`, which simply drops records that fail a predicate, `KTable.filter()` converts non-matching records into **tombstones** (null values) and forwards them downstream. This ensures that downstream tables also purge the deleted records.

---

## 3. KTable Aggregations: Adders and Subtractors

Aggregating records in a `KTable` requires a different approach than in a `KStream`. 

### 3.1 Why Grouping by Primary Key is an Anti-Pattern
Since a `KTable` ensures only one record exists per key, executing `groupByKey()` followed by an aggregation will always yield a table containing exactly the single latest value for that key. 

To aggregate, you must group by a non-primary key field (e.g. grouping stock trades by their market sector rather than their symbol) using the `.groupBy()` operator.

---

### 3.2 The Adder & Subtractor Mechanics
Because the input to a `KTable` aggregation is an update stream, when a key's value changes, the aggregation must update accordingly:
1.  **The Subtractor**: Extracts the *previous* value of the key and subtracts it from the old group's aggregate.
2.  **The Adder**: Extracts the *new* value of the key and adds it to the new group's aggregate.

```
Incoming Update: 
  CFLT Share Price changes from $100 (Sector: Tech) to $123 (Sector: Tech)

Aggregation Pipeline Actions:
  1. Subtractor: Removes old value ($100) from the Tech sector aggregate.
  2. Adder: Adds new value ($123) to the Tech sector aggregate.
```

This ensures that the rolling sector aggregate remains accurate without double-counting updates.

---

### 3.3 Complete KTable Aggregation Implementation

Below is a complete implementation that groups stock alert prices by their market segment and maintains a running share volume and dollar volume.

##### Domain Models:
```java
public record StockAlert(String symbol, String marketSegment, long shareVolume, double sharePrice) {}
public record SegmentAggregate(long shareVolume, double dollarVolume) {}
```

##### KTable Aggregation Topology Code:
```java
package com.enterprise.streams.ktable;

import org.apache.kafka.common.serialization.Serde;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KeyValue;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.*;

public class KTableAggregationTopology {

    public Topology buildTopology(
            Serde<StockAlert> alertSerde,
            Serde<SegmentAggregate> aggSerde) {

        StreamsBuilder builder = new StreamsBuilder();
        Serde<String> stringSerde = Serdes.String();

        // 1. Create the source KTable (represents latest alerts per stock symbol)
        KTable<String, StockAlert> stockTable = builder.table(
                "stock-alerts",
                Consumed.with(stringSerde, alertSerde)
        );

        // 2. Initializer function for the aggregator state
        Initializer<SegmentAggregate> segmentInitializer = () -> new SegmentAggregate(0L, 0.0);

        // 3. Adder Aggregator: Adds the new stock alert value to the segment sum
        Aggregator<String, StockAlert, SegmentAggregate> adderAggregator = (key, newValue, currentAgg) -> {
            long newVolume = currentAgg.shareVolume() + newValue.shareVolume();
            double newDollars = currentAgg.dollarVolume() + (newValue.shareVolume() * newValue.sharePrice());
            return new SegmentAggregate(newVolume, newDollars);
        };

        // 4. Subtractor Aggregator: Removes the previous stock alert value from the segment sum
        Aggregator<String, StockAlert, SegmentAggregate> subtractorAggregator = (key, oldValue, currentAgg) -> {
            long newVolume = currentAgg.shareVolume() - oldValue.shareVolume();
            double newDollars = currentAgg.dollarVolume() - (oldValue.shareVolume() * oldValue.sharePrice());
            return new SegmentAggregate(newVolume, newDollars);
        };

        // 5. Group by Market Segment (forces repartitioning) and aggregate
        KTable<String, SegmentAggregate> segmentAggTable = stockTable.groupBy(
                (symbolKey, alert) -> KeyValue.pair(alert.marketSegment(), alert),
                Grouped.with(stringSerde, alertSerde)
        ).aggregate(
                segmentInitializer,
                adderAggregator,
                subtractorAggregator,
                Materialized.<String, SegmentAggregate, KeyValueStore<org.apache.kafka.common.utils.Bytes, byte[]>>as("Segment-Agg-Store")
                            .withKeySerde(stringSerde)
                            .withValueSerde(aggSerde)
        );

        // 6. Write results to downstream output topic
        segmentAggTable.toStream().to(
                "segment-aggregates",
                Produced.with(stringSerde, aggSerde)
        );

        return builder.build();
    }
}
```
