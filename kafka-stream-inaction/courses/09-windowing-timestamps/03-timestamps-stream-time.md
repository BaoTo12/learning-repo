# Module 03: Timestamps & Stream Time Advancement

Time is the most critical dimension in stream processing. Unlike traditional batch applications that query static tables, real-time streaming engines must process event streams continuously as they unfold. To do this reliably, Kafka Streams relies on an internal concept called **Stream Time**.

This module explains the different definitions of time in event streaming, how to implement custom `TimestampExtractor` logic, and the mechanics of the Stream Time advancement algorithm.

---

## 1. Event Time vs. Ingestion Time vs. Processing Time

Kafka supports three distinct notions of time:

| Time Concept | Definition | Set By | Configuration |
|---|---|---|---|
| **Event Time** | The time when the event physically occurred in the real world. | The producing client (embedded in the `ProducerRecord` metadata). | Default mode (uses broker `CreateTime` metadata setting). |
| **Ingestion Time** | The time when the broker successfully appended the record to its local log. | The Kafka Broker (replaces the client-side timestamp). | Broker topic setting: `message.timestamp.type=LogAppendTime`. |
| **Processing Time** | The wallclock time of the system running the stream processing application. | The consumer/JVM running Kafka Streams. | Emulated via custom `TimestampExtractor` returning `System.currentTimeMillis()`. |

---

## 2. Implementing a Custom `TimestampExtractor`

By default, Kafka Streams uses the `FailOnInvalidTimestampExtractor` or the `UsePartitionTimeOnInvalidTimestampExtractor`. If a record has a negative or missing timestamp (e.g. legacy client producers), the application will crash.

Often, you want to extract event time from the **payload** of the message rather than relying on the metadata timestamp. To do this, implement the `TimestampExtractor` interface.

### Example: Extracting Timestamp from a Custom JSON Payload

Suppose we have a `SensorReading` record with the event time encoded inside the JSON body:

```java
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.streams.processor.TimestampExtractor;
import com.fasterxml.jackson.databind.ObjectMapper;

public class JsonPayloadTimestampExtractor implements TimestampExtractor {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Override
    public long extract(ConsumerRecord<Object, Object> record, long partitionTime) {
        // Fallback checks
        if (record.value() == null) {
            return fallback(record, partitionTime);
        }

        try {
            // Suppose the value is a byte array representing JSON
            byte[] payloadBytes = (byte[]) record.value();
            SensorReading reading = MAPPER.readValue(payloadBytes, SensorReading.class);
            
            long eventTime = reading.getEventTimestampEpochMs();
            if (eventTime < 0) {
                // Return partition time as a fallback instead of crashing
                return fallback(record, partitionTime);
            }
            return eventTime;
        } catch (Exception e) {
            // Log warning and fall back to partition time
            return fallback(record, partitionTime);
        }
    }

    private long fallback(ConsumerRecord<Object, Object> record, long partitionTime) {
        long metadataTimestamp = record.timestamp();
        if (metadataTimestamp >= 0) {
            return metadataTimestamp;
        }
        // If metadata is also invalid, return the current stream/partition time
        return partitionTime;
    }
}
```

### Applying the Extractor

You can configure the timestamp extractor in two ways:

#### Option 1: Globally via Configurations
```java
import org.apache.kafka.streams.StreamsConfig;
import java.util.Properties;

Properties config = new Properties();
config.put(
    StreamsConfig.DEFAULT_TIMESTAMP_EXTRACTOR_CLASS_CONFIG,
    JsonPayloadTimestampExtractor.class.getName()
);
```

#### Option 2: Per-Source Stream in the DSL
```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.Consumed;

StreamsBuilder builder = new StreamsBuilder();
builder.stream(
    "sensor-readings",
    Consumed.with(Serdes.String(), Serdes.ByteArray())
            .withTimestampExtractor(new JsonPayloadTimestampExtractor())
);
```

---

## 3. How Stream Time Advances

**Stream Time** is the internal clock of a Kafka Streams instance. It does *not* track wallclock time (JVM system time). Instead, it advances only when the application processes records. If no records arrive, Stream Time stands completely still.

### The Advancement Algorithm

Each Stream Task processes data from one or more topic partitions.

```
       Task 0-0
     /          \
Partition 0   Partition 1
(Log time: 10) (Log time: 15)
     \          /
     Min(10, 15) = 10 (Stream Time)
```

1. **Partition Time**: The maximum timestamp observed in records consumed from a specific partition.
2. **Task Stream Time**: The stream time of a task is determined by the **minimum** partition time among all partitions assigned to that task.
3. **Task Advancement**:
   * If Task 0-0 consumes from Topic A Partition 0 (whose current record has timestamp `1000`) and Topic B Partition 1 (whose current record has timestamp `1200`), the task's Stream Time is `1000`.
   * This minimum-time heuristic is crucial because it ensures that partitions are processed in a coordinated, time-ordered sequence, preventing late records in slow partitions from immediately being dropped.

---

## 4. Production Implications of Stream Time

### Partition Starvation & Out-of-Order Records
If a task consumes from two partitions, and one partition becomes completely idle (no new events arrive), the partition time for that idle partition will freeze. Because Task Stream Time is the *minimum* of all partition times, the **entire task's Stream Time will freeze**.
* **Symptoms**: Windowed aggregations on the active partition stop emitting updates (if suppressed) because the window never officially "closes" in terms of stream time.
* **Solution**: Configure `max.task.idle.ms` (default is `0` ms). When set to a positive value (e.g., `1000` ms), Kafka Streams will wait up to that long for the idle partition to receive records. If it remains idle, it will advance task stream time based *only* on the active partitions, preventing blockages.

### Clock Drift Between Brokers
If producers set event timestamps in the future due to misconfigured system clocks on client machines, those records will artificially advance Stream Time. Once Stream Time jumps forward, all subsequent valid records with correct system clocks will be treated as "late" (beyond the grace period) and discarded.
* **Best Practice**: In your `TimestampExtractor`, validate that incoming event times do not exceed `System.currentTimeMillis() + threshold` (e.g., a threshold of 5 minutes). If they do, cap them or drop them.
