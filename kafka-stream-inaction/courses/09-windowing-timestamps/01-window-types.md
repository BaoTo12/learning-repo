# Module 01: Window Types & Time Alignment

In stream processing, unbounded aggregations (aggregations that process incoming events indefinitely) are often impractical because state stores would grow without limit, and historical trends are lost inside a single massive counter. **Windowing** solves this by segmenting stateful aggregations into discrete, time-bound buckets based on record timestamps.

This module details the four window types supported by the Kafka Streams DSL, their internal time-alignment mechanics, the structure of windowed keys, and how to query window state stores.

---

## 1. What Problem Windowing Solves

When you perform a stateful operation like `.count()` or `.aggregate()`, Kafka Streams maintains the result in a local RocksDB state store. Without windowing:
1. **Unbounded Growth**: The store retains a record for every key indefinitely.
2. **Loss of Temporal Resolution**: You only see the total running value rather than trends (e.g., "sales per hour" vs "total sales ever").
3. **No Automatic Cleanup**: Old keys that are no longer active remain in the database forever unless manually purged.

Windowing bounds the aggregation to a specific time range and allows Kafka Streams to automatically expire and clean up old window buckets after a configured retention period.

---

## 2. The Four Window Types

### A. Tumbling Windows
* **Definition**: Fixed-size, non-overlapping, and contiguous time intervals.
* **Alignment**: Aligned to the epoch. For example, a 5-minute tumbling window starting at epoch `0` will segment time into `[0, 5Min)`, `[5Min, 10Min)`, etc.
* **Use Case**: Calculating hourly page views, daily financial balances.

```java
import org.apache.kafka.streams.kstream.TimeWindows;
import java.time.Duration;

// 5-minute tumbling window (no grace period)
TimeWindows tumblingWindow = TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(5));
```

### B. Hopping Windows
* **Definition**: Fixed-size, overlapping time intervals.
* **Parameters**: Defined by a **size** and an **advance** interval.
* **Alignment**: Aligned to the epoch. If size is 5 minutes and advance is 1 minute, the windows are `[0, 5Min)`, `[1Min, 6Min)`, `[2Min, 7Min)`, etc. A single event will fall into multiple windows.
* **Use Case**: Calculating a moving 5-minute average updated every minute.

```java
import org.apache.kafka.streams.kstream.TimeWindows;
import java.time.Duration;

// 5-minute window advancing every 1 minute
TimeWindows hoppingWindow = TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(5))
                                       .advanceBy(Duration.ofMinutes(1));
```

### C. Session Windows
* **Definition**: Data-driven, dynamically sized windows based on periods of inactivity.
* **Parameters**: Defined by an **inactivity gap**. If no events for a key arrive within the gap, the window closes.
* **Merge Behavior**: If a late-arriving event bridges the inactivity gap between two separate session windows, Kafka Streams merges them into a single window, deleting the two original windows and updating the state store.
* **Use Case**: Tracking user sessions on a website.

```java
import org.apache.kafka.streams.kstream.SessionWindows;
import java.time.Duration;

// Session window with a 30-minute inactivity gap
SessionWindows sessionWindow = SessionWindows.ofInactivityGapWithNoGrace(Duration.ofMinutes(30));
```

### D. Sliding Windows
* **Definition**: Event-driven windows that float dynamically based on the timestamps of incoming records.
* **Alignment**: Unlike Hopping/Tumbling windows, sliding windows are not aligned to epoch boundaries. Instead, a window is created only when an event arrives. The window extends backwards and forwards in time by the specified window size.
* **Use Case**: Emitting an alert if a user has more than 5 failed login attempts within any 10-second interval.

```java
import org.apache.kafka.streams.kstream.SlidingWindows;
import java.time.Duration;

// Sliding window with a maximum time difference of 10 seconds
SlidingWindows slidingWindow = SlidingWindows.ofTimeDifferenceWithNoGrace(Duration.ofSeconds(10));
```

---

## 3. Windowed Keys (`Windowed<K>`)

When you perform a windowed aggregation, the output key of the resulting `KTable` is no longer the original key type `K`. Instead, it is wrapped in the `org.apache.kafka.streams.kstream.Windowed` class:

```java
public class Windowed<K> {
    private final K key;
    private final Window window;

    public K key() { return key; }
    public Window window() { return window; }
}
```
The `Window` object contains:
* `start()`: Epoch millisecond indicating when the window starts (inclusive).
* `end()`: Epoch millisecond indicating when the window ends (exclusive for time windows, inclusive for session/sliding windows).

### Serialization & Deserialization (Serdes)
If you write a windowed stream to an output topic using `.to()`, you must provide a special Serde that knows how to serialize the `Windowed<K>` key. Kafka Streams provides helper methods to construct these:

```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.kstream.WindowedSerdes;

// For Time-based windows (Tumbling, Hopping, Sliding)
Serde<Windowed<String>> timeWindowedSerde = WindowedSerdes.timeWindowedSerdeFrom(String.class);

// For Session-based windows
Serde<Windowed<String>> sessionWindowedSerde = WindowedSerdes.sessionWindowedSerdeFrom(String.class);
```

Under the hood, these Serdes serialize the key by concatenating:
1. The serialized bytes of the original key `K`.
2. The start timestamp of the window (8-byte long).
3. (Only for Session windows) The end timestamp of the window (8-byte long).

---

## 4. End-to-End DSL Implementation Example

Below is a production-focused example of a Yelling purchase counter grouped by 5-minute tumbling windows:

```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.*;
import java.time.Duration;

public class WindowedPurchaseCounter {

    public void buildTopology(StreamsBuilder builder) {
        KStream<String, Double> purchaseStream = builder.stream(
            "purchases",
            Consumed.with(Serdes.String(), Serdes.Double())
        );

        // Group by key and apply Tumbling Windows
        KTable<Windowed<String>, Long> windowedCounts = purchaseStream
            .groupByKey(Grouped.with(Serdes.String(), Serdes.Double()))
            .windowedBy(TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(5)))
            .count(Materialized.<String, Long, WindowStore<Bytes, byte[]>>as("purchases-count-store")
                .withKeySerde(Serdes.String())
                .withValueSerde(Serdes.Long()));

        // Stream the results to an output topic
        windowedCounts.toStream()
            .to(
                "purchase-counts-windowed",
                Produced.with(WindowedSerdes.timeWindowedSerdeFrom(String.class), Serdes.Long())
            );
    }
}
```

---

## 5. Querying Window State Stores (Interactive Queries)

Windowed state stores are materialized as `ReadOnlyWindowStore` instances. You can query these stores locally using the start/end timestamps or specific keys:

```java
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StoreQueryParameters;
import org.apache.kafka.streams.state.ReadOnlyWindowStore;
import org.apache.kafka.streams.state.WindowStoreIterator;
import org.apache.kafka.streams.state.KeyValueIterator;
import java.time.Instant;

public class WindowStoreQueryService {

    private final KafkaStreams streams;

    public WindowStoreQueryService(KafkaStreams streams) {
        this.streams = streams;
    }

    public void queryStore(String userId) {
        // Retrieve the read-only window store
        ReadOnlyWindowStore<String, Long> windowStore = streams.store(
            StoreQueryParameters.fromNameAndType("purchases-count-store", QueryableStoreTypes.windowStore())
        );

        Instant timeTo = Instant.now();
        Instant timeFrom = timeTo.minus(Duration.ofHours(1));

        // 1. Fetch values for a specific key over a time range
        try (WindowStoreIterator<Long> iterator = windowStore.fetch(userId, timeFrom, timeTo)) {
            while (iterator.hasNext()) {
                KeyValue<Long, Long> next = iterator.next();
                Long windowStartEpoch = next.key;
                Long count = next.value;
                System.out.printf("Window Start: %s, Count: %d%n", Instant.ofEpochMilli(windowStartEpoch), count);
            }
        }

        // 2. Fetch values for a range of keys over a time range
        try (KeyValueIterator<Windowed<String>, Long> rangeIterator = windowStore.fetchAll(timeFrom, timeTo)) {
            while (rangeIterator.hasNext()) {
                KeyValue<Windowed<String>, Long> next = rangeIterator.next();
                Windowed<String> windowedKey = next.key;
                Long count = next.value;
                System.out.printf("User: %s, Window: [%s - %s], Count: %d%n",
                    windowedKey.key(),
                    Instant.ofEpochMilli(windowedKey.window().start()),
                    Instant.ofEpochMilli(windowedKey.window().end()),
                    count
                );
            }
        }
    }
}
```

---

## 6. Architectural Trade-offs & Production Anti-Patterns

### Anti-Pattern: Unconfigured Retention Period
By default, Kafka Streams retains window store contents for **1 day**. If your application handles high-cardinality keys, a long retention period will cause RocksDB disk utilization to skyrocket.
* **Solution**: Explicitly configure retention periods on your windows using `.ofSizeAndGrace()` or `.ofSizeWithNoGrace()`, and modify the retention parameter on the `Materialized` configuration if necessary.

### Co-partitioning Constraints
Just like standard stateful joins, windowed aggregations and joins require that input streams are **co-partitioned** (matching key serialization and same partition counts). If they are not, Kafka Streams will silently produce incorrect results or throw serialization exceptions during window boundary calculations.

### Windows vs. Garbage Collection
For windowed state stores, RocksDB partitions data into physical **segments** on disk representing segments of time. When a segment's time window falls outside the retention period, the entire segment directory is deleted from disk. This is a highly efficient form of garbage collection.
* **Caution**: Do not configure window sizes that are extremely small (e.g. 1 second) with long retention periods (e.g. 1 year). This creates thousands of directories, causing filesystem degradation and file descriptor exhaustion.
