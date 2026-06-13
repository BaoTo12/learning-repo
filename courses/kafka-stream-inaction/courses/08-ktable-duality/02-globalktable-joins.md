# Module 02: GlobalKTable Mechanics & Joins

While the `KTable` shards partition data across running instances to enable horizontal scaling, certain use cases require reference datasets to be fully local on every node. The **GlobalKTable** abstraction provides a fully replicated lookup table on every running worker node, enabling flexible enrichment joins.

This module details the design, trade-offs, and join semantics of `GlobalKTable`.

---

## 1. What is a GlobalKTable?

A **GlobalKTable** differs fundamentally from a standard `KTable` in partition distribution:
*   **`KTable` (Sharded)**: Sourced partition-by-partition. If your input topic has 3 partitions and you have 3 worker instances, each instance hosts a local state store containing exactly 1 partition of the dataset.
*   **`GlobalKTable` (Replicated)**: Sourced in full. Every running instance of your application consumes **all partitions** of the source topic, building an identical, full copy of the dataset in local disk-based stores on every worker.

```
                  [ Topic: Users (3 Partitions) ]
                       │             │             │
        ┌──────────────┴─────────────┼─────────────┴──────────────┐
        ▼                            ▼                            ▼
┌───────────────┐            ┌───────────────┐            ┌───────────────┐
│   Instance 1  │            │   Instance 2  │            │   Instance 3  │
│               │            │               │            │               │
│ GlobalKTable  │            │ GlobalKTable  │            │ GlobalKTable  │
│ (All Part.    │            │ (All Part.    │            │ (All Part.    │
│  0, 1, and 2) │            │  0, 1, and 2) │            │  0, 1, and 2) │
└───────────────┘            └───────────────┘            └───────────────┘
```

### 1.1 Operational Profiles and Backup Storage
*   **No Changelog Topic**: Unlike `KTable`, Kafka Streams does **not** create a separate internal changelog topic to back a `GlobalKTable`. Because the table fully consumes its source topic, the source topic itself acts as the recovery log. On a crash or restart, the node rebuilds the table directly from the source topic.
*   **Off-Thread Updates**: Global state stores are updated by a dedicated, separate thread (**GlobalStreamThread**) that runs independently of your topology's processing threads. Incoming updates to the global table are written immediately to the local store without waiting for timestamp alignments.

---

## 2. Stream-GlobalKTable Joins

Joining a stream against a `KTable` requires both topics to be co-partitioned. If they are not, you must insert a repartition step. Joining against a `GlobalKTable` eliminates this requirement.

```
       [ Stream Record ] ────► KeyValueMapper ────► Extracted Key (e.g. "Sensor-1")
                                                       │
                                                       ▼ (Direct local lookup)
                                             [ Local GlobalKTable Store ]
                                                       │
                                                       ▼
                                              [ Enriched Record ]
```

### 2.1 The Key-Extractor Lifecycle (`KeyValueMapper`)
Because the global store is replicated on every node, **the stream record does not need to have the same key as the table**. It can even have a `null` key. 
You supply a `KeyValueMapper` to extract the lookup key from the stream record's value or headers:

```java
KeyValueMapper<String, SensorReading, String> sensorIdExtractor = 
    (streamKey, readingValue) -> readingValue.sensorId();
```

---

## 3. Designing a Stream-GlobalKTable Join

Let's build a pipeline that consumes keyless sensor telemetry (`SensorReading`) from a `KStream` and enriches it with metadata (`SensorMetadata`) from a `GlobalKTable` using the sensor's ID.

##### Domain Models:
```java
public record SensorReading(String sensorId, double temperature, long timestamp) {}
public record SensorMetadata(String sensorId, String location, String model) {}
public record EnrichedSensorData(String sensorId, double temperature, String location, String model) {}
```

##### Integration Pipeline:
```java
package com.enterprise.streams.global;

import org.apache.kafka.common.serialization.Serde;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.GlobalKTable;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Produced;

public class GlobalTableJoinTopology {

    public Topology buildTopology(
            Serde<SensorReading> readingSerde,
            Serde<SensorMetadata> metadataSerde,
            Serde<EnrichedSensorData> enrichedSerde) {

        StreamsBuilder builder = new StreamsBuilder();
        Serde<String> stringSerde = Serdes.String();

        // 1. Load the reference metadata into a GlobalKTable
        GlobalKTable<String, SensorMetadata> metadataTable = builder.globalTable(
                "sensor-metadata",
                Consumed.with(stringSerde, metadataSerde)
        );

        // 2. Consume keyless sensor telemetry stream (KStream has null keys)
        KStream<String, SensorReading> readingStream = builder.stream(
                "sensor-telemetry",
                Consumed.with(Serdes.String(), readingSerde)
        );

        // 3. Define the Joiner logic
        // ValueJoiner receives: (LeftValue, RightValue) -> EnrichedValue
        KStream<String, EnrichedSensorData> enrichedStream = readingStream.join(
                metadataTable,
                (streamKey, reading) -> reading.sensorId(), // KeyValueMapper (extract lookup key)
                (reading, metadata) -> {                    // ValueJoiner
                    if (metadata == null) {
                        return new EnrichedSensorData(reading.sensorId(), reading.temperature(), "Unknown", "Unknown");
                    }
                    return new EnrichedSensorData(
                            reading.sensorId(),
                            reading.temperature(),
                            metadata.location(),
                            metadata.model()
                    );
                }
        );

        // 4. Output the enriched data (preserves the stream's original key - which is null)
        enrichedStream.to(
                "enriched-telemetry",
                Produced.with(Serdes.String(), enrichedSerde)
        );

        return builder.build();
    }
}
```

---

## 4. Architectural Trade-offs

*   **Disk Spills**: Each worker node must have enough local storage to hold the *entire* global topic. If the topic is 100 GB, three worker instances will consume a total of 300 GB across your cluster.
*   **Network Utilization**: Scaling out your application JVMs increases network consumption because every new worker instance must read the entire source topic.
*   **Consistency Semantics**: Because the GlobalStateStore updates out-of-band on a separate thread, there is a risk of **read lag**. A stream record might be processed a fraction of a millisecond before the global thread applies a corresponding table update.
