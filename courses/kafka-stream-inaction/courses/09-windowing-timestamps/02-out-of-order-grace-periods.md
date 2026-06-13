# Module 02: Out-of-Order Data, Grace Periods & Suppression

In distributed event streaming architectures, records rarely arrive in perfect chronological order. Network partitions, client-side retries, and broker failovers can cause messages to land on a consumer thread minutes or hours late. 

This module explains how Kafka Streams handles late-arriving events, how to configure **grace periods**, and how to use the **Suppression API** to control when aggregated window results are emitted.

---

## 1. The Challenge of Late-Arriving (Out-of-Order) Data

Suppose you have a 5-minute Tumbling window: `[12:00, 12:05)`.
1. An event occurs at `12:02` (Event Time).
2. Due to a network glitch, the producer fails to transmit the event immediately.
3. In the meantime, other records occur and are processed at `12:06` and `12:08`. The system's internal track of time (Stream Time) advances to `12:08`.
4. The delayed event finally arrives at the broker and is processed by the stream at `12:09`.

Since the event belongs to the `[12:00, 12:05)` window, but the current time is `12:08`, should the system discard it, or update the closed window?

By default, Kafka Streams maintains window stores for a retention time (defaulting to 1 day). If an event arrives late, Kafka Streams will pull the historical window from RocksDB, update the aggregate, and emit a new record down the topology. While this ensures eventual correctness, it leads to two major production issues:
1. **Downstream Update Storms**: Downstream databases or microservices receive multiple updates for the same window.
2. **Infinite Update Loops**: Relational databases integrated via CDC (Change Data Capture) must handle retro-active inserts or updates.

---

## 2. Grace Periods

A **Grace Period** defines how long Kafka Streams will wait after the window ends to accept late-arriving events. 

* **Accepted Record**: If `Event Time >= Window Start` AND `Event Time < Window End`, and `Current Stream Time < Window End + Grace Period`, the record is accepted and aggregated into the window.
* **Dropped Record**: If `Current Stream Time >= Window End + Grace Period`, the record is considered late, is discarded, and a metric counter (`dropped-records-total`) is incremented.

### Configuring Grace Periods
In modern versions of Kafka Streams, you specify grace periods using the `.ofSizeAndGrace()` constructor:

```java
import org.apache.kafka.streams.kstream.TimeWindows;
import java.time.Duration;

// 10-minute Tumbling window with a 2-minute grace period
TimeWindows tumblingWithGrace = TimeWindows.ofSizeAndGrace(
    Duration.ofMinutes(10), 
    Duration.ofMinutes(2)
);

// 10-minute Hopping window (advancing every 1 minute) with a 2-minute grace period
TimeWindows hoppingWithGrace = TimeWindows.ofSizeAndGrace(
    Duration.ofMinutes(10), 
    Duration.ofMinutes(2)
).advanceBy(Duration.ofMinutes(1));
```

> [!WARNING]
> If you configure a window using `.ofSizeWithNoGrace()`, Kafka Streams sets the grace period to **24 hours** by default. To strictly reject late records, you must explicitly set grace to zero: `TimeWindows.ofSizeAndGrace(Duration.ofMinutes(10), Duration.ZERO)`.

---

## 3. The Suppression API

By default, Kafka Streams operates in **Eager Emit Mode**. Every time a record updates a window's value, the updated result is emitted immediately. If a window receives 100 events, it emits 100 updates.

The **Suppression API** allows you to buffer intermediate updates in a state store and emit **only the final result** when the window closes (i.e. when `Stream Time >= Window End + Grace Period`).

### DSL Implementation with Suppression

```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.*;
import java.time.Duration;

public class SuppressedAggregator {

    public void buildTopology(StreamsBuilder builder) {
        KStream<String, Double> sensorStream = builder.stream(
            "sensor-readings",
            Consumed.with(Serdes.String(), Serdes.Double())
        );

        sensorStream
            .groupByKey(Grouped.with(Serdes.String(), Serdes.Double()))
            .windowedBy(
                // 1-minute window, 10-second grace period
                TimeWindows.ofSizeAndGrace(Duration.ofMinutes(1), Duration.ofSeconds(10))
            )
            .mean(Materialized.as("sensor-mean-store"))
            
            // Suppress intermediate results until the window closes
            .suppress(
                Suppressed.untilWindowCloses(
                    // Configure an in-memory buffer limit
                    Suppressed.BufferConfig.maxRecords(1000).shutDownWhenFull()
                )
            )
            .toStream()
            .to(
                "final-sensor-averages",
                Produced.with(WindowedSerdes.timeWindowedSerdeFrom(String.class), Serdes.Double())
            );
    }
}
```

---

## 4. Buffer Configurations & Exhaustion Strategies

Since suppression buffers messages in memory/disk before the window closes, you must define how to handle buffer limits to prevent `OutOfMemoryError` failures.

### A. Shutdown When Full
* **Behavior**: If the buffer limits are exceeded, the application immediately shuts down.
* **Usage**: Ideal for strict transactional architectures where data loss or out-of-order emission is unacceptable.

```java
Suppressed.BufferConfig.maxRecords(1000).shutDownWhenFull();
Suppressed.BufferConfig.maxBytes(10 * 1024 * 1024).shutDownWhenFull(); // 10 MB limit
```

### B. Emit Early When Full
* **Behavior**: If the buffer limits are exceeded, the oldest window is emitted early (even if it has not technically closed yet).
* **Usage**: Appropriate for analytical platforms where latency matters more than strict guarantees.

```java
Suppressed.BufferConfig.maxRecords(5000).emitEarlyWhenFull();
```

---

## 5. Production Anti-Patterns & Operations

### Anti-Pattern: Memory Leaks with Suppression
Suppression buffers are kept in-memory but can spill over to RockDB if you specify `.maxRecords(N)` and configure the store backup. If buffer limits are too large, JVM Heap overhead can lead to heavy garbage collection pauses.
* **Rule of Thumb**: Estimate the cardinality of keys per window. If you have 10,000 active keys per minute, set `maxRecords` to at least `12,000` to allow breathing room, and ensure your container has adequate heap allocations.

### Anti-Pattern: Mismatched Suppression and Join Windows
If you feed a suppressed windowed stream into a stream-stream join, the join might fail because the records are delayed until the grace period ends. By the time the suppressed event is emitted, the join window on the other stream may have already closed.
* **Best Practice**: Apply suppression **after** joins, or design wide join windows that account for the suppression delay.
