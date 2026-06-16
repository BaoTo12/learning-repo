# Module 09 — Windowing and Timestamps

In this module, we will learn how Kafka Streams processes time. We will cover why windowing is needed to group events by time. We will look at the four different window types in Kafka Streams: Tumbling, Hopping, Session, and Sliding. We will see how windows align to the epoch, and how to read windowed results using `Windowed<K>` keys and `WindowedSerdes`. Next, we will discuss how Kafka Streams handles out-of-order data using grace periods and log retention. We will study the `suppress()` operator to emit only final window results and look at buffer limits. Finally, we will cover the three notions of time (event time, ingestion time, and processing time), how the `TimestampExtractor` interface works, and how to write a custom extractor. We will close with four hands-on labs with complete code structures and detailed configuration tables.

---

## 1. Academic Lecture: Windowing Types & Timestamp Processing

### Basic Level: Windowing Needs, Epoch Alignment & Retrieving Results

#### Why Windowing is Needed
In stream processing, data arrives continuously. Unlike a traditional database table with a fixed size, a stream has no end. Because of this, you cannot perform operations like counting the "total" number of purchases or calculating the "average" transaction value over the entire stream, because the stream never stops.
**Windowing** solves this problem by spliting the stream into finite buckets of time. This allows you to run aggregations over specific intervals (such as "purchases in the last 5 minutes" or "hourly login counts").

#### The Four Window Types in Kafka Streams

##### 1. Tumbling Windows
* **Definition**: Fixed-size, non-overlapping, contiguous time windows.
* **Characteristics**: A tumbling window starts at a set time and lasts for a fixed duration. When it ends, a new window begins immediately. A record belongs to exactly one window.
* **Java Method**: `TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(1))`
* **Analogy**: A clock striking every hour. Purchases from 12:00 to 01:00 go into one bucket, and purchases from 01:00 to 02:00 go into the next.

```text
  Stream:   ──[Event A (12:00:15)]──[Event B (12:00:45)]──[Event C (12:01:10)]──
  Windows:  |◄─── Tumbling Window 1 (12:00) ───►|◄─── Tumbling Window 2 (12:01) ───►|
```

##### 2. Hopping Windows
* **Definition**: Fixed-size, overlapping time windows defined by a size and an advance interval (hop).
* **Characteristics**: The advance interval determines how frequently a new window opens. If the advance interval is smaller than the window size, the windows overlap, and a single record can belong to multiple windows.
* **Java Method**: `TimeWindows.ofSizeAndGrace(Duration.ofMinutes(5), grace).advanceBy(Duration.ofMinutes(1))`
* **Analogy**: A 5-minute moving average graph that updates every 1 minute.

```text
  Window 1 (12:00 - 12:05)  [===================]
  Window 2 (12:01 - 12:06)      [===================]
  Window 3 (12:02 - 12:07)          [===================]
```

##### 3. Session Windows
* **Definition**: Dynamic, activity-based windows defined by periods of inactivity (inactivity gap).
* **Characteristics**: Session windows do not have a fixed size. They are driven by individual key behavior. A window stays open as long as new events for that key keep arriving before the inactivity gap expires. If no events arrive for longer than the gap duration, the session closes. A new event starts a new session.
* **Java Method**: `SessionWindows.ofInactivityGapWithNoGrace(Duration.ofMinutes(30))`
* **Analogy**: A user browsing an e-commerce website. Their session is kept open as long as they click on a page at least once every 30 minutes. If they walk away for 40 minutes, their next click starts a new session.

```text
  Key A Events:  ──[Click]───10m───[Click]──────────45m──────────[Click]──
  Sessions:      |◄────── Session 1 ──────►|                     |◄─ Session 2 ─►|
```

##### 4. Sliding Windows
* **Definition**: Event-driven, floating windows defined by a maximum time difference.
* **Characteristics**: Sliding windows align to the records themselves rather than epoch boundaries. A sliding window is created every time a record enters or leaves the window. It is used to evaluate relationships between events that occur close to each other.
* **Java Method**: `SlidingWindows.ofTimeDifferenceAndGrace(Duration.ofSeconds(30), grace)`
* **Analogy**: Checking if a user entered their password incorrectly three times within any 30-second window.

#### Window Time Alignment
Kafka Streams windows are aligned to the Unix epoch (January 1, 1970, UTC). For example, a 5-minute tumbling window will always start at 00:00, 00:05, 00:10, and so on. They do not start when your application boots up. This ensures that if your application restarts, or if you run multiple instances in parallel, all tasks calculate identical window boundaries.

#### Retrieving Windowed Results: Windowed Keys
When you perform a windowed aggregation, the resulting key is not just your original key type `K`. Instead, it is wrapped in a **`Windowed<K>`** object.
The `Windowed<K>` key contains two parts:
1. **The original key**: Retrieved using `windowedKey.key()`.
2. **The window boundary**: Retrieved using `windowedKey.window()`, which provides `.start()` and `.end()` timestamps in milliseconds.

To serialize and deserialize these keys, you must use **`WindowedSerdes`** (for example, `WindowedSerdes.timeWindowedSerdeFrom(String.class, windowSize)`).

---

### Intermediate Level: Grace Periods, Changelog Retention & Suppression

#### Out-of-Order Data and the Grace Period
In a distributed system, network delays, client reconnections, or clock skews can cause records to arrive late at the stream processor. If a window has a size of 1 minute and spans from 12:00 to 12:01, what happens to a record that was created at 12:00:30 but does not arrive until 12:05:00?
To handle this, Kafka Streams uses a **Grace Period**:
* **Definition**: An additional period of time after the window ends during which the window remains open to accept late-arriving records.
* **Behavior**: If the grace period is set to 10 seconds, the 12:00 to 12:01 window will accept new records until the stream time reaches 12:01:10. If a record with a timestamp of 12:00:30 arrives *after* the stream time has passed 12:01:10, it is considered late data and is dropped.

```text
  Window: [12:00 - 12:01] 
  Grace Period: 10 seconds (Ends at 12:01:10)
  
  Record timestamp 12:00:30 arrives when stream time is 12:01:05 ──► ACCEPTED (Window updated)
  Record timestamp 12:00:30 arrives when stream time is 12:01:15 ──► DROPPED (Late data)
```

#### Changelog Retention Configuration
When a windowed state store is created, Kafka Streams automatically creates a corresponding changelog topic on the broker to back up the store.
To ensure the changelog topic does not grow forever, you must configure how long the broker keeps window data. This is configured via:
* **`StreamsConfig.WINDOW_STORE_CHANGE_LOG_ADDITIONAL_RETENTION_MS_CONFIG`**: This adds extra retention time to the window changelog topic beyond the window size + grace period. This guarantees that during restarts, Kafka Streams can restore the state store even if recovery takes time.

#### Suppressing Windowed Results
By default, when you aggregate a windowed stream, Kafka Streams emits an updated record to the downstream topic **every time** a new event arrives. If a 1-minute tumbling window receives 100 purchases, it will emit 100 updates downstream.
If you only want to know the *final* count at the end of the minute, sending 100 updates is wasteful. To solve this, you use the **`suppress()`** operator.

```java
.suppress(Suppressed.untilWindowCloses(BufferConfig.unbounded()))
```

* **`untilWindowCloses`**: Instructs the stream processor to hold back updates in an in-memory buffer. It only emits a single, final output record for a window once the grace period has passed and the window closes.
* **`untilTimeLimit`**: Emits updates after a fixed time limit, even if the window is still open.
* **Strict vs. Eager Buffering Trade-offs**:
  * *Eager (No Suppression)*: Low latency. Downstream consumers see updates immediately, but they receive many duplicate updates for the same window.
  * *Strict (untilWindowCloses)*: High latency (must wait for window + grace period to end), but minimal network traffic (exactly one event per key per window) and no intermediate states.

---

### Advanced Level: Timestamp Extractors & Stream Time Progression

#### Timestamps in Kafka Streams
Kafka Streams recognizes three notions of time:
1. **Event Time**: The time when the event occurred at the source (e.g., printed on a physical store receipt). This is embedded inside the record payload.
2. **Ingestion Time**: The time when the event was appended to the log partition on the Kafka broker.
3. **Processing Time**: The time when the record is processed by the Kafka Streams application instance (wall-clock time of the server).

#### The TimestampExtractor Interface
To determine which timestamp to associate with a record, Kafka Streams uses the `TimestampExtractor` interface. It defines a single method:

```java
long extract(ConsumerRecord<Object, Object> record, long partitionTime);
```
* `record`: The incoming consumer record.
* `partitionTime`: The highest timestamp seen so far in this partition (used as a fallback).
* Return value: The epoch millisecond timestamp to assign to the record.

#### Built-in Extractors
Kafka Streams provides three built-in implementations:
1. **`FailOnInvalidTimestamp`** (Default): Uses the timestamp set in the Kafka record metadata (usually Event Time or Ingestion Time). If the timestamp is negative or invalid, it throws a `StreamsException` and shuts down the application.
2. **`LogAndSkipOnInvalidTimestamp`**: Uses the record metadata timestamp. If it is invalid, it logs a warning message and skips the record (drops it).
3. **`WallclockTimestampExtractor`**: Ignores metadata timestamps entirely and uses the current system time of the processing machine. This converts the application into a **processing-time** engine.

#### Custom TimestampExtractor
If your event timestamp is embedded inside a JSON field in the record value, the built-in extractors cannot read it. You must write a custom class that casts the record value and extracts the field.

#### Stream Time Progression
Time in Kafka Streams is **not** driven by the wall-clock clock of the server. Instead, it is driven by the timestamps of the records passing through the topology.
* **Stream Time**: Defined as the maximum timestamp observed so far across all processed records.
* **Progress**: When a record with timestamp T2 arrives and is processed, and T2 > Tstream, the stream time advances to T2. If no new records arrive, stream time stands still. This is crucial: if a topic becomes completely idle, windows will not close, and suppressed results will not be emitted until new records arrive to advance stream time.

---

## 2. Theory & Production Best Practices

### Window Types Comparison Matrix

| Window Type | Boundary Type | Overlapping? | Size Type | Trigger Event |
| :--- | :--- | :--- | :--- | :--- |
| **Tumbling** | Epoch-aligned | No | Fixed | Fixed time boundaries |
| **Hopping** | Epoch-aligned | Yes | Fixed | Every advance (hop) interval |
| **Session** | Data-driven | No | Dynamic | Periods of inactivity (gaps) |
| **Sliding** | Data-driven | Yes | Fixed | Record entry/exit boundaries |

### Timestamp Extractors Trade-offs

| Extractor Class | Processing Latency | Out-of-Order Safety | Use Case |
| :--- | :--- | :--- | :--- |
| `FailOnInvalidTimestamp` | Low | High | Standard setups where broker timestamps are guaranteed. |
| `LogAndSkipOnInvalidTimestamp` | Low | High | Tolerates malformed producer events without crashing. |
| `WallclockTimestampExtractor` | Extremely Low | None | Simple logging, real-time alert generation ignoring event delay. |
| **Custom Extractor** | Medium (deserialization) | High | Temporal joins requiring business/receipt timestamp accuracy. |

---

## 3. Common Errors & Troubleshooting

### 1. `StreamsException: Input record has a negative timestamp`
* **Symptom**: The application crashes during startup or record processing.
* **Root Cause**: The producer wrote records using a legacy client that did not set timestamps, or sent a negative default value.
* **Fix**: Change the default timestamp extractor in your configuration to skip invalid timestamps:
  ```properties
  default.timestamp.extractor=org.apache.kafka.streams.processor.LogAndSkipOnInvalidTimestamp
  ```

### 2. Suppressed Results are Never Emitted (Stream Time Stalled)
* **Symptom**: You configured `.suppress(untilWindowCloses(...))` but the output topic remains empty.
* **Root Cause**: The stream time has not advanced past the window close boundary (window end + grace period). This happens when the input topic partition is idle or has very few events.
* **Fix**: Ensure constant event traffic, or configure backup standby tasks to keep partition stream time advancing.

### 3. Out-of-Memory (OOM) Errors in Suppress Buffer
* **Symptom**: The JVM heap memory fills up, causing crashes.
* **Root Cause**: If you use `BufferConfig.unbounded()`, and you have millions of unique keys, the in-memory buffer will grow indefinitely.
* **Fix**: Restrict the buffer size by setting limit limits:
  ```java
  BufferConfig.maxRecords(10000).shutDownWhenFull()
  // Or:
  BufferConfig.maxBytes(10 * 1024 * 1024).emitEarlyWhenFull()
  ```

---

## 4. Hands-on Labs

### Lab 9.1 — Tumbling Window: Count purchases per 1-minute window

#### Scenario
We will consume transaction events, group them by customer ID, count the total purchases per customer in a 1-minute tumbling window, and output the window start/end boundaries to a console log.

#### Complete Java Code
Create the file [TumblingWindowPurchaseApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/TumblingWindowPurchaseApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.KeyValue;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.kstream.Produced;
import org.apache.kafka.streams.kstream.TimeWindows;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.time.Instant;
import java.util.Properties;

public class TumblingWindowPurchaseApp {
    private static final Logger log = LoggerFactory.getLogger(TumblingWindowPurchaseApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "tumbling-window-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, JsonSerde.class.getName());
        props.put(StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG, 0); // View changes immediately
        return props;
    }

    public static void main(String[] args) {
        log.info("Starting Tumbling Window Purchase App...");

        StreamsBuilder builder = new StreamsBuilder();
        JsonSerde<Purchase> purchaseSerde = new JsonSerde<>();

        KStream<String, Purchase> purchaseStream = builder.stream(
            "purchases",
            Consumed.with(Serdes.String(), purchaseSerde)
        );

        // Group, window by 1-minute tumbling windows, and count
        purchaseStream
            .groupByKey()
            .windowedBy(TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(1)))
            .count(Materialized.as("windowed-purchase-counts"))
            .toStream()
            .map((windowedKey, count) -> {
                String range = String.format("[%s - %s]",
                    Instant.ofEpochMilli(windowedKey.window().start()).toString(),
                    Instant.ofEpochMilli(windowedKey.window().end()).toString()
                );
                log.info("Customer ID: {} | Window: {} | Purchase Count: {}", windowedKey.key(), range, count);
                return KeyValue.pair(windowedKey.key(), String.format("Window %s: %d", range, count));
            })
            .to("windowed-counts", Produced.with(Serdes.String(), Serdes.String()));

        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());

        streams.cleanUp();
        streams.start();
        log.info("Tumbling Window App is running!");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Stopping tumbling window app...");
            streams.close();
            log.info("App stopped.");
        }));
    }
}
```

#### Configuration Details
The following table explains what each line of the configuration properties does:

| Property Name | Value | Purpose |
| :--- | :--- | :--- |
| `StreamsConfig.APPLICATION_ID_CONFIG` | `"tumbling-window-group"` | Serves as the consumer group coordination namespace and sets local RocksDB directory targets. |
| `StreamsConfig.BOOTSTRAP_SERVERS_CONFIG` | `"localhost:9092"` | Locates the Kafka cluster bootstrap brokers. |
| `StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG` | `Serdes.String()...` | Registers String as the default key serialization. |
| `StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG`| `JsonSerde.class...` | Configures default value de/serialization to use our custom JSON serializer. |
| `StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG`| `0` | Disables internal buffer cache to ensure downstream writes happen on every message immediately. |

---

### Lab 9.2 — Session Window: Group user activity sessions

#### Scenario
We will track user sessions using a 30-minute inactivity gap. If a customer is inactive for more than 30 minutes, their session closes and subsequent events open a new session window.

#### Complete Java Code
Create the file [SessionWindowPurchaseApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/SessionWindowPurchaseApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.KeyValue;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.kstream.Produced;
import org.apache.kafka.streams.kstream.SessionWindows;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.time.Instant;
import java.util.Properties;

public class SessionWindowPurchaseApp {
    private static final Logger log = LoggerFactory.getLogger(SessionWindowPurchaseApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "session-window-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, JsonSerde.class.getName());
        props.put(StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG, 0);
        return props;
    }

    public static void main(String[] args) {
        log.info("Launching Session Window App...");

        StreamsBuilder builder = new StreamsBuilder();
        JsonSerde<Purchase> purchaseSerde = new JsonSerde<>();

        KStream<String, Purchase> purchaseStream = builder.stream(
            "purchases",
            Consumed.with(Serdes.String(), purchaseSerde)
        );

        // Group, window by 30-minute inactivity sessions, and count events
        purchaseStream
            .groupByKey()
            .windowedBy(SessionWindows.ofInactivityGapWithNoGrace(Duration.ofMinutes(30)))
            .count(Materialized.as("session-purchase-store"))
            .toStream()
            .map((windowedKey, count) -> {
                String range = String.format("[%s - %s]",
                    Instant.ofEpochMilli(windowedKey.window().start()).toString(),
                    Instant.ofEpochMilli(windowedKey.window().end()).toString()
                );
                log.info("Customer ID: {} | Session: {} | Events: {}", windowedKey.key(), range, count);
                return KeyValue.pair(windowedKey.key(), String.format("Session %s: %d", range, count));
            })
            .to("session-counts", Produced.with(Serdes.String(), Serdes.String()));

        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());

        streams.cleanUp();
        streams.start();
        log.info("Session Window App is running!");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Stopping session window app...");
            streams.close();
            log.info("App stopped.");
        }));
    }
}
```

---

### Lab 9.3 — Suppress: Emit only final window results

#### Scenario
We will count purchase events in 1-minute windows with a 10-second grace period. We will use the `suppress()` operator to buffer intermediate results and emit only a single final count downstream when the window closes.

#### Complete Java Code
Create the file [SuppressedPurchaseApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/SuppressedPurchaseApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.KeyValue;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.kstream.Produced;
import org.apache.kafka.streams.kstream.Suppressed;
import org.apache.kafka.streams.kstream.Suppressed.BufferConfig;
import org.apache.kafka.streams.kstream.TimeWindows;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.time.Instant;
import java.util.Properties;

public class SuppressedPurchaseApp {
    private static final Logger log = LoggerFactory.getLogger(SuppressedPurchaseApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "suppressed-window-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, JsonSerde.class.getName());
        return props;
    }

    public static void main(String[] args) {
        log.info("Launching Suppressed Window App...");

        StreamsBuilder builder = new StreamsBuilder();
        JsonSerde<Purchase> purchaseSerde = new JsonSerde<>();

        KStream<String, Purchase> purchaseStream = builder.stream(
            "purchases",
            Consumed.with(Serdes.String(), purchaseSerde)
        );

        // Group, window by 1-minute tumbling windows + 10s grace, suppress intermediate values
        purchaseStream
            .groupByKey()
            .windowedBy(TimeWindows.ofSizeAndGrace(Duration.ofMinutes(1), Duration.ofSeconds(10)))
            .count(Materialized.as("suppressed-purchase-store"))
            .suppress(Suppressed.untilWindowCloses(BufferConfig.unbounded()))
            .toStream()
            .map((windowedKey, count) -> {
                String range = String.format("[%s - %s]",
                    Instant.ofEpochMilli(windowedKey.window().start()).toString(),
                    Instant.ofEpochMilli(windowedKey.window().end()).toString()
                );
                log.info("EMITTING FINAL RESULT -> Customer: {} | Window: {} | Count: {}", windowedKey.key(), range, count);
                return KeyValue.pair(windowedKey.key(), String.format("Final Count %s: %d", range, count));
            })
            .to("final-counts", Produced.with(Serdes.String(), Serdes.String()));

        Topology topology = builder.build();
        KafkaStreams streams = new KafkaStreams(topology, getConfig());

        streams.cleanUp();
        streams.start();
        log.info("Suppressed Window App is running!");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Stopping suppressed window app...");
            streams.close();
            log.info("App stopped.");
        }));
    }
}
```

---

### Lab 9.4 — Custom TimestampExtractor: Extract purchase date from record payload

#### Scenario
We will create a custom class implementing `TimestampExtractor` to parse and extract the `purchaseDate` field directly from the `Purchase` domain model payload rather than relying on the record metadata.

#### Custom TimestampExtractor Class
Create the file [PurchaseDateExtractor.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/PurchaseDateExtractor.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.streams.processor.TimestampExtractor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class PurchaseDateExtractor implements TimestampExtractor {
    private static final Logger log = LoggerFactory.getLogger(PurchaseDateExtractor.class);

    @Override
    public long extract(ConsumerRecord<Object, Object> record, long partitionTime) {
        // Cast the record value to the Purchase domain object
        if (record.value() instanceof Purchase) {
            Purchase purchase = (Purchase) record.value();
            long timestamp = purchase.getPurchaseDate();
            
            // Validate the extracted timestamp
            if (timestamp >= 0) {
                return timestamp;
            }
        }

        // Fallback to partition time if timestamp is invalid or class cast fails
        if (partitionTime >= 0) {
            log.warn("Invalid purchase timestamp detected. Falling back to partition time: {}", partitionTime);
            return partitionTime;
        }

        // Fallback to system current time if no other time is available
        log.warn("No timestamp available. Falling back to system wall-clock time.");
        return System.currentTimeMillis();
    }
}
```

#### Explaining Configuration Usage
To configure your Kafka Streams topology to use your custom extractor, you register it in the application configurations as follows:

```java
Properties props = new Properties();
props.put(StreamsConfig.DEFAULT_TIMESTAMP_EXTRACTOR_CLASS_CONFIG, PurchaseDateExtractor.class.getName());
```

| Property Name | Value | Purpose |
| :--- | :--- | :--- |
| `StreamsConfig.DEFAULT_TIMESTAMP_EXTRACTOR_CLASS_CONFIG` | `PurchaseDateExtractor.class...` | Configures the default timestamp extractor class for all consumed streams in this topology, overriding the default metadata-based extractor. |
