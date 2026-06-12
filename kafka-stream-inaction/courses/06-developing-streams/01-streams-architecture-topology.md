# Module 01: Streams Architecture & Topology

Stream processing involves taking continuous feeds of real-time event data, performing operations on that data, and outputting the results. In Apache Kafka, the native solution for this is the **Kafka Streams API**. This module details the design of processor topologies, the client-side library architecture, and how to configure and run your first application.

---

## 1. Topologies: Graphs of Processing Nodes

A Kafka Streams application defines its processing logic as a **Processor Topology**. A topology is a **Directed Acyclic Graph (DAG)** where:
*   **Nodes** represent processor steps that transform, filter, or route events.
*   **Edges** represent the flow of records between these processor steps.

```
       [ Kafka Broker Topic ] (Source)
                 │
                 ▼
         ┌───────────────┐
         │  Source Node  │  (Consumes bytes, deserializes them to objects)
         └───────┬───────┘
                 │
                 ▼
        ┌─────────────────┐
        │ Processor Node  │  (Transforms, filters, or modifies records)
        └───────┬─────────┘
                 │
                 ▼
         ┌───────────────┐
         │   Sink Node   │  (Serializes objects to bytes, writes to topic)
         └───────┬───────┘
                 │
                 ▼
       [ Kafka Broker Topic ] (Sink)
```

There are three primary types of nodes in a topology:
1.  **Source Processor Node**: A node that does not have parent nodes. It consumes record bytes directly from one or more Kafka topics, deserializes them using a key/value `Deserializer`, and forwards them to its child nodes.
2.  **Processor Node**: A node that receives records from parent nodes, applies custom business logic (e.g., mapping, filtering, enrichment), and forwards the transformed records to its child nodes.
3.  **Sink Processor Node**: A terminal node that has no child nodes. It receives records from parent nodes, serializes them using a key/value `Serializer`, and writes the bytes back to a Kafka topic.

---

## 2. Client-Side Library Execution

A critical architectural detail of Kafka Streams is its deployment model:
*   **Not a Cluster Framework**: Kafka Streams is **not** a database cluster or a server engine that runs inside your Kafka brokers. It is a standard Java library.
*   **Client JVM Application**: You build your application as a standard Java application, package it as a JAR, and run it on your own compute resources (e.g., Kubernetes pods, VM instances, or bare-metal servers).
*   **Decoupled Scaling**: The brokers only store the logs and coordinate partition assignments. Scaling the stream processing application simply involves launching or terminating instances of your Java application, which scale horizontally using consumer group protocols.

---

## 3. Creating the Hello World "Yelling" Application

To demonstrate topology construction, configuration, and lifecycles, let's look at the **Yelling App**, which consumes records, transforms the text values to uppercase, and writes them back to a destination topic.

### 3.1 Step-by-Step Topology Construction
We construct the topology using the `StreamsBuilder` class:
```java
// 1. Initialize the builder
StreamsBuilder builder = new StreamsBuilder();

// 2. Define the source node (consumes from "src-topic")
KStream<String, String> simpleFirstStream = builder.stream("src-topic",
        Consumed.with(Serdes.String(), Serdes.String()));

// 3. Define the processor node (transforms the value to uppercase)
KStream<String, String> upperCasedStream = simpleFirstStream.mapValues(value -> value.toUpperCase());

// 4. Define the sink node (writes to "out-topic")
upperCasedStream.to("out-topic", Produced.with(Serdes.String(), Serdes.String()));
```

Using the fluent API, we can chain these steps into a single statement:
```java
builder.stream("src-topic", Consumed.with(Serdes.String(), Serdes.String()))
       .mapValues(value -> value.toUpperCase())
       .to("out-topic", Produced.with(Serdes.String(), Serdes.String()));
```

---

## 4. Key Configurations: Application ID & Bootstrap Servers

To initialize the application, you must define configurations. Attempting to start the application without the two following properties will cause the runtime to throw a `ConfigException`:

1.  **`StreamsConfig.APPLICATION_ID_CONFIG`** (`application.id`):
    *   Uniquely identifies your stream processing application.
    *   Serves as the default **Consumer Group ID** for your embedded consumer threads.
    *   Serves as the prefix for all internal topics (e.g., repartitioning and changelog topics) created by Kafka Streams.
    *   Kafka Streams instances sharing the same `application.id` coordinate partition work as a single logical cluster.
2.  **`StreamsConfig.BOOTSTRAP_SERVERS_CONFIG`** (`bootstrap.servers`):
    *   A comma-separated list of host:port pairs indicating the Kafka brokers that the client establishes initial connections with.

---

## 5. Completing the Application Lifecycle

To run the application, build a `Topology` object from `StreamsBuilder` and instantiate `KafkaStreams`. 

```java
package com.enterprise.streams.yelling;

import org.apache.kafka.common.serialization.Serde;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;

public class KafkaStreamsYellingApp {
    private static final Logger log = LoggerFactory.getLogger(KafkaStreamsYellingApp.class);

    public Topology buildTopology(Properties streamProperties) {
        StreamsBuilder builder = new StreamsBuilder();
        Serde<String> stringSerde = Serdes.String();

        // Build the graph
        builder.stream("src-topic", Consumed.with(stringSerde, stringSerde))
               .mapValues(value -> value.toUpperCase())
               .to("out-topic", Produced.with(stringSerde, stringSerde));

        return builder.build(streamProperties);
    }

    public static void main(String[] args) {
        Properties config = new Properties();
        config.put(StreamsConfig.APPLICATION_ID_CONFIG, "yelling_app_id");
        config.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");

        KafkaStreamsYellingApp app = new KafkaStreamsYellingApp();
        Topology topology = app.buildTopology(config);

        // Instantiate the streams engine
        KafkaStreams streams = new KafkaStreams(topology, config);

        // Add a shutdown hook to cleanly close resources
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Shutdown hook triggered. Closing Kafka Streams...");
            streams.close();
        }));

        try {
            log.info("Starting yelling application...");
            streams.start();
            
            // Keep the main thread alive while streams is running
            Thread.sleep(Long.MAX_VALUE);
        } catch (InterruptedException e) {
            log.warn("Main thread interrupted", e);
            Thread.currentThread().interrupt();
        } finally {
            streams.close();
            log.info("Application stopped.");
        }
    }
}
```

> [!CAUTION]
> Always register a shutdown hook (`Runtime.getRuntime().addShutdownHook(...)`) that calls `streams.close()`. A clean shutdown allows the embedded consumers to notify the Group Coordinator that they are leaving the group, triggering immediate partition rebalances instead of waiting for a heartbeat session timeout.
