# Module 10 — The Processor API

In this module, we will explore the low-level Processor API in Kafka Streams. We will cover when to use the low-level Processor API instead of the high-level DSL. We will learn how to build a manual processing topology using the `Topology` class by adding source nodes, processor nodes, state stores, and sink nodes. We will examine the lifecycle of the `Processor` interface, the metadata capabilities of `ProcessorContext` and `Record`, and how to schedule periodic tasks using punctuators. We will compare stream-time punctuation and wall-clock punctuation. Finally, we will cover how to manage state stores (RocksDB vs. in-memory), configure logging and caching, perform custom data-driven aggregations, and integrate low-level processors into a high-level DSL pipeline. We will close with Socratic review questions, hands-on labs with complete code structures, and detailed configuration tables.

---

## 1. Academic Lecture: Manual Topologies & Custom Processing

### Basic Level: Low-Level Needs, Topology Elements & Suppliers

#### When to Use the Processor API
The high-level Streams DSL provides declarative operators like `map`, `filter`, and `groupBy`. However, some advanced use cases require more control:
* **Custom State Logic**: Modifying local databases based on custom application logic that does not fit standard aggregation templates.
* **Fine-Grained Forwarding**: Emitting zero, one, or multiple records downstream under specific conditions, or sending them to different target topics dynamically.
* **Time-Driven Actions (Punctuation)**: Running a task periodically (such as "every 10 seconds of stream time, scan a database and delete expired items").

For these cases, Kafka Streams provides the Low-Level **Processor API**.

#### Building a Topology with the `Topology` Class
In the DSL, you define your logic using a `StreamsBuilder`. Under the hood, this builder automatically compiles your code into a graph of nodes.
In the Processor API, you bypass `StreamsBuilder` entirely. You construct the execution graph manually using the **`Topology`** class.

A manual topology is built from three types of nodes:
1. **Source Node**: Consumes raw byte records from one or more Kafka topics, deserializes them, and forwards them to downstream processors. Created via `topology.addSource(...)`.
2. **Processor Node**: Performs custom business logic on incoming records. Created via `topology.addProcessor(...)`.
3. **Sink Node**: Serializes processed records and writes them to a target Kafka topic. Created via `topology.addSink(...)`.

```text
  [ Source Node ] (topic: stock-transactions)
         │
         ▼
  [ Processor Node ] (StockPerformanceProcessor) <─── Attached Store (stock-performance-store)
         │
         ▼
  [ Sink Node ] (topic: stock-performance)
```

#### Processor Suppliers and Lifecycles
When registering a processor node in the topology, you do not pass a single instance of your processor class. Instead, you pass a **`ProcessorSupplier`**:

```java
topology.addProcessor("my-processor", () -> new MyProcessor(), "source-node");
```

##### Why Use a Supplier?
Kafka Streams runs your topology across multiple threads (tasks) in parallel. Each task must have its own isolated processor instance to prevent thread-safety bugs. The `ProcessorSupplier` acts as a factory, generating a fresh, dedicated processor instance for each task thread.

---

### Intermediate Level: Processor Lifecycle, Context & Punctuators

#### The Processor Interface Lifecycle
A custom processor class implements the modern `Processor<K, V, KO, VO>` interface (from the `org.apache.kafka.streams.processor.api` package), which defines three lifecycle methods:

##### 1. `init(ProcessorContext<KO, VO> context)`
* Called once when the processor instance is initialized by the task thread.
* Used to save a reference to the `ProcessorContext`, retrieve handles to local state stores, and schedule punctuation timers.

##### 2. `process(Record<K, V> record)`
* Called for every record arriving at this node.
* The incoming record is wrapped in a `Record<K, V>` object. You read the input key and value, update state stores, inspect metadata (like partition, offset, and headers), and decide if and when to forward outputs downstream.

##### 3. `close()`
* Called when the processor is shut down by the task thread.
* Used to clean up resources, close database connections, or commit final states.

#### The ProcessorContext
The `ProcessorContext` is the controller that connects your processor to the Kafka Streams runtime. It provides several essential capabilities:
* **State Store Retrieval**: Call `context.getStateStore("store-name")` to access a localized database.
* **Record Forwarding**: Call `context.forward(Record<KO, VO> record)` to send a processed record downstream to the next topology node.
* **Metadata Queries**: Access partition index, offset, and stream headers.

#### Periodic Execution: Punctuator Punctuation
A major advantage of the Processor API is the ability to schedule code to run periodically. This is called **Punctuation**.
You register a punctuation task by calling `context.schedule(...)` inside the `init()` method. Punctuation tasks require three parameters:
1. **Interval**: How often to run the task (e.g., `Duration.ofSeconds(10)`).
2. **Punctuation Type**: How time progress is tracked.
3. **Punctuator Callback**: An implementation of the `Punctuator` interface defining the `punctuate(long timestamp)` method.

##### Punctuation Types: Stream Time vs. Wall-Clock Time
Kafka Streams supports two methods of tracking time progression for punctuation:

* **`PunctuationType.STREAM_TIME`**:
  * Driven entirely by the timestamps of the records arriving from Kafka.
  * *Behavior*: If a batch of records arrives with timestamps spanning from 12:00:00 to 12:00:30, stream time progresses by 30 seconds. Punctuation triggers if this progression exceeds the scheduled interval.
  * *Benefit*: Deterministic and reproducible. If you reprocess historical data, the punctuation triggers at identical timestamp intervals.
  * *Drawback*: If no records arrive, stream time stands still, and punctuation will never trigger.

* **`PunctuationType.WALL_CLOCK_TIME`**:
  * Driven by the actual system clock time of the processing machine (real-world time).
  * *Behavior*: Triggers at regular clock intervals, regardless of whether records are arriving or what timestamps they contain.
  * *Benefit*: Guarantees execution even if topics are completely idle.
  * *Drawback*: Non-deterministic. If your system runs slow, or if you replay historical logs, execution points will shift.

---

### Advanced Level: State Store Management & DSL Integration

#### RocksDB Persistent vs. In-Memory State Stores
When choosing a state store for your processor, you have two primary options:
1. **RocksDB Persistent Store** (`Stores.persistentKeyValueStore`):
   * *Mechanism*: Writes data to off-heap native memory buffers and flushes them periodically to local SSDs.
   * *Pros*: Scales beyond JVM heap boundaries; fast local recovery after restarts because data is stored on disk.
   * *Cons*: Requires off-heap memory allocation tuning; slightly slower than raw RAM lookups.
2. **In-Memory Store** (`Stores.inMemoryKeyValueStore`):
   * *Mechanism*: Keeps all records inside the JVM heap.
   * *Pros*: Extremely low lookup latency.
   * *Cons*: Consumes JVM heap space; must rebuild the entire store from the changelog topic upon restart.

#### State Store Tuning: Caching and Logging
To make state stores fault-tolerant and performant, you can configure:
* **Changelog Logging**: Keeps a backup on the Kafka broker. Enabling this ensures that if a server dies, another task can rebuild the state store. (Enabled using `.withLoggingEnabled(Map<String, String> config)`).
* **Caching**: Buffers state updates in memory. It deduplicates updates before writing to disk or sending them downstream. (Enabled using `.withCachingEnabled()`).

#### Data-Driven Aggregations in the Processor API
In the DSL, aggregations are restricted to key-based groupings. In the Processor API, you can design any custom aggregation layout.
For example, you can maintain a rolling record of the highest and lowest prices of all stock symbols in a single state store. When a new trade transaction arrives:
1. Look up the stock symbol in the state store.
2. Compare the new price against the stored high/low prices.
3. Update the state store if a new threshold is met.
4. Use a stream-time Punctuator to check the store every 10 seconds, identify stocks showing significant price movements, and forward those alerts downstream.

#### Integrating Processor API with the DSL
You do not have to write your entire application using manual topologies. Kafka Streams allows you to insert custom low-level processors directly into a high-level DSL stream using the `.process()` operator:

```java
KStream<String, Order> orders = builder.stream("orders-topic");
KStream<String, Alert> alerts = orders.process(
    new ProcessorSupplier<String, Order, String, Alert>() {
        @Override
        public Processor<String, Order, String, Alert> get() {
            return new CustomAlertProcessor();
        }
    },
    "my-state-store" // State stores must be attached explicitly
);
```

##### A Note on Deprecated Patterns
In older versions of Kafka Streams, you might see code using `.transform()` or `.transformValues()`. These patterns are **deprecated** in newer versions. They have been fully consolidated into the unified `.process()` and `.processValues()` methods, which use the standard `Processor` interface.

---

## 2. Theory & Production Best Practices

### DSL vs. Processor API Comparison

| Feature | High-Level DSL | Low-Level Processor API |
| :--- | :--- | :--- |
| **Development Effort** | Low (declarative functions) | Medium to High (manual state management) |
| **Topology Construction** | Automatic via `StreamsBuilder` | Manual via `Topology` |
| **State Store Access** | Implicit (created by DSL operators) | Explicit (registered and retrieved manually) |
| **Time-Driven Execution** | Limited (windowing limits) | High (custom Punctuator intervals) |
| **Record Forwarding** | Automatic downstream flow | Manual forwarding via `context.forward()` |

### Punctuation Types Trade-offs

| Punctuation Type | Trigger Trigger | Idle Topic Behavior | Determinism | Best Used For |
| :--- | :--- | :--- | :--- | :--- |
| **STREAM_TIME** | Progress of record timestamps | Starves (stops executing) | Highly deterministic | Reprocessing historical logs, session timeout logic. |
| **WALL_CLOCK_TIME**| Machine system clock | Triggers regularly | Non-deterministic | Real-time dashboards, health status heartbeats. |

### State Store Configurations

| Configuration | Performance Impact | Fault Tolerance | Recovery Speed |
| :--- | :--- | :--- | :--- |
| **Persistent (RocksDB)** | Medium | High | High (local disk recovery) |
| **In-Memory** | High | High | Low (full broker restore) |
| **Caching Enabled** | Reduces disk and network IO | High | High |
| **Changelog Disabled** | Eliminates broker writes | None (data lost on disk crash) | None |

---

## 3. Common Errors & Troubleshooting

### 1. `TopologyException: StateStore is not added`
* **Symptom**: Startup failure with `TopologyException: StateStore X is not added to the topology`.
* **Root Cause**: You tried to retrieve a state store inside a custom Processor, but you did not register the store in the topology, or did not associate it with the processor node.
* **Fix**: Ensure the store is added and connected to the processor name:
  ```java
  topology.addStateStore(storeBuilder, "my-processor-node");
  ```

### 2. `ClassCastException` in State Store Retrieval
* **Symptom**: Runtime crash when calling `context.getStateStore(...)`.
* **Root Cause**: Deserialization Serdes mismatch. For example, your store is configured to store JSON objects, but you try to read it using standard String Serdes.
* **Fix**: Verify that the Serdes registered in your `StoreBuilder` match the generic types used in your Processor class.

### 3. Punctuator Blocks Task Thread
* **Symptom**: Application throughput drops to zero, and the broker detects consumer heartbeats timeouts.
* **Root Cause**: The `punctuate()` callback runs on the main stream task thread. If your punctuator loops through a large state store containing millions of records, it blocks processing and offsets commits.
* **Fix**: Keep punctuators short. Avoid full-table scans. If you must scan the database, partition the scan or utilize RocksDB indexes to query a subset of records.

---

## 4. Socratic Review Questions

### Question 1
*How does Kafka Streams guarantee thread safety for a custom `Processor` instance if a single application instance runs across multiple task threads?*
* **Answer**: Kafka Streams requires you to supply a `ProcessorSupplier` instead of a single instance of `Processor`. The `ProcessorSupplier.get()` method is called once by each task thread. This generates a separate, isolated instance of the `Processor` for each stream task, ensuring no variables or state stores are shared across threads.

### Question 2
*If an input topic partition becomes completely idle, what happens to a punctuator scheduled with `PunctuationType.STREAM_TIME`?*
* **Answer**: The punctuator stops running. Since stream time only progresses when new records with advanced timestamps arrive on partition inputs, an idle topic stalls the task's stream time. The scheduled interval cannot be met, so the punctuator will not trigger until new data arrives.

### Question 3
*What is the difference between `ProcessorContext.forward()` and returning a value in a DSL mapper?*
* **Answer**: A DSL mapper must return exactly one record for each input record (or zero for filter). `ProcessorContext.forward()` allows a processor to emit zero, one, or multiple records at any time. It can even forward records during a `punctuate()` invocation when no input record is currently being processed.

### Question 4
*Why is it highly recommended to use RocksDB persistent state stores instead of In-Memory stores for large databases?*
* **Answer**: RocksDB stores write data to local disk directories off-heap, which prevents JVM Garbage Collection (GC) pauses and avoids OutOfMemoryErrors when databases grow large. Furthermore, when a task restarts, it can read directly from the local disk directory instead of spending hours downloading the entire history from the broker changelog topic.

### Question 5
*How can you access record headers inside the modern `Processor` interface?*
* **Answer**: The modern `process(Record<K, V> record)` method receives a `Record` wrapper. You can access record headers directly by calling `record.headers()`. This allows you to read or modify metadata without polluting the record key or value.

---

## 5. Hands-on Labs

### Models for Stock Tracking

#### StockTransaction Model Class
Create the file [StockTransaction.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/StockTransaction.java) with the following content:

```java
package com.kafkastreams.course.labs;

import java.io.Serializable;

public class StockTransaction implements Serializable {
    private static final long serialVersionUID = 1L;

    private String symbol;
    private double price;
    private long timestamp;

    public StockTransaction() {}

    public StockTransaction(String symbol, double price, long timestamp) {
        this.symbol = symbol;
        this.price = price;
        this.timestamp = timestamp;
    }

    public String getSymbol() { return symbol; }
    public void setSymbol(String symbol) { this.symbol = symbol; }

    public double getPrice() { return price; }
    public void setPrice(double price) { this.price = price; }

    public long getTimestamp() { return timestamp; }
    public void setTimestamp(long timestamp) { this.timestamp = timestamp; }

    @Override
    public String toString() {
        return "StockTransaction{" +
                "symbol='" + symbol + ''' +
                ", price=" + price +
                ", timestamp=" + timestamp +
                '}';
    }
}
```

#### StockPerformance Model Class
Create the file [StockPerformance.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/StockPerformance.java) with the following content:

```java
package com.kafkastreams.course.labs;

import java.io.Serializable;

public class StockPerformance implements Serializable {
    private static final long serialVersionUID = 1L;

    private String symbol;
    private double currentPrice;
    private double minPrice;
    private double maxPrice;
    private boolean significantChange;

    public StockPerformance() {
        this.minPrice = Double.MAX_VALUE;
        this.maxPrice = Double.MIN_VALUE;
        this.significantChange = false;
    }

    public void update(StockTransaction transaction) {
        this.symbol = transaction.getSymbol();
        this.currentPrice = transaction.getPrice();
        
        if (currentPrice < minPrice) {
            minPrice = currentPrice;
        }
        if (currentPrice > maxPrice) {
            maxPrice = currentPrice;
        }

        // Flag as significant if current price is more than 5% away from min/max average
        double average = (minPrice + maxPrice) / 2.0;
        double shift = Math.abs(currentPrice - average) / average;
        this.significantChange = (shift > 0.05);
    }

    public String getSymbol() { return symbol; }
    public double getCurrentPrice() { return currentPrice; }
    public double getMinPrice() { return minPrice; }
    public double getMaxPrice() { return maxPrice; }
    public boolean isSignificant() { return significantChange; }

    @Override
    public String toString() {
        return "StockPerformance{" +
                "symbol='" + symbol + ''' +
                ", currentPrice=" + currentPrice +
                ", minPrice=" + minPrice +
                ", maxPrice=" + maxPrice +
                ", significant=" + significantChange +
                '}';
    }
}
```

---

### Lab 10.1 — Stock analysis processor: track high/low prices

#### Scenario
We will create a custom processor named `StockPerformanceProcessor` implementing the lifecycle of the low-level `Processor` interface. The processor will update a RocksDB state store with incoming stock transactions and use a stream-time Punctuator scheduled for every 10 seconds of stream time to forward stock records that meet our threshold.

#### Complete Processor Java Code
Create the file [StockPerformanceProcessor.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/StockPerformanceProcessor.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.streams.KeyValue;
import org.apache.kafka.streams.processor.api.Processor;
import org.apache.kafka.streams.processor.api.ProcessorContext;
import org.apache.kafka.streams.processor.api.Record;
import org.apache.kafka.streams.state.KeyValueIterator;
import org.apache.kafka.streams.state.KeyValueStore;
import org.apache.kafka.streams.processor.PunctuationType;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;

public class StockPerformanceProcessor
    implements Processor<String, StockTransaction, String, StockPerformance> {
    
    private static final Logger log = LoggerFactory.getLogger(StockPerformanceProcessor.class);

    private KeyValueStore<String, StockPerformance> store;
    private ProcessorContext<String, StockPerformance> context;

    @Override
    public void init(ProcessorContext<String, StockPerformance> context) {
        this.context = context;
        // Retrieve the state store registered in the topology
        this.store = context.getStateStore("stock-performance-store");
        
        // Schedule a punctuator every 10 seconds of stream time
        context.schedule(Duration.ofSeconds(10), PunctuationType.STREAM_TIME, this::punctuate);
        log.info("Stock Performance Processor initialized. Punctuation scheduled.");
    }

    @Override
    public void process(Record<String, StockTransaction> record) {
        String symbol = record.key();
        StockTransaction transaction = record.value();

        if (symbol == null || transaction == null) {
            return;
        }

        // Fetch current performance state from store, initialize if absent
        StockPerformance performance = store.get(symbol);
        if (performance == null) {
            performance = new StockPerformance();
        }

        // Update tracking statistics
        performance.update(transaction);
        store.put(symbol, performance);
    }

    private void punctuate(long timestamp) {
        log.info("Punctuation triggered at Stream Time: {}. Analyzing stock anomalies...", timestamp);
        
        try (KeyValueIterator<String, StockPerformance> iter = store.all()) {
            while (iter.hasNext()) {
                KeyValue<String, StockPerformance> entry = iter.next();
                StockPerformance perf = entry.value;

                // Only forward stock entries showing significant volatility
                if (perf != null && perf.isSignificant()) {
                    log.info("Volatility threshold breached for Symbol: {}! Forwarding alert.", entry.key);
                    context.forward(new Record<>(entry.key, perf, timestamp));
                }
            }
        }
    }

    @Override
    public void close() {
        log.info("Shutting down Stock Performance Processor...");
        // Cleanup store reference
        this.store = null;
    }
}
```

#### Step-by-Step Code Walkthrough

##### Initialization (`init`)
1. The method saves a reference to `ProcessorContext` inside class variables.
2. It calls `context.getStateStore(...)` to fetch a handle to the database named `"stock-performance-store"`.
3. It registers a timer by calling `context.schedule()`. The parameters specify that the `punctuate` method should run every 10 seconds based on **Stream Time** progression.

##### Record Processing (`process`)
1. For every stock transaction record that arrives, the processor reads the stock symbol (key) and the transaction details (value).
2. It queries the local store using `store.get(symbol)`. If the symbol has not been processed before, it creates a new `StockPerformance` tracker.
3. It calls `performance.update(transaction)` to recalculate high and low price thresholds.
4. It saves the updated tracker back into the state store using `store.put(symbol, performance)`. No output is forwarded downstream during this step.

##### Periodical Evaluation (`punctuate`)
1. The method is triggered when record timestamps progress by 10 seconds of stream time.
2. It opens an iterator over the entire local database using `store.all()`.
3. It loops through each stock symbol tracker, checking if `perf.isSignificant()` returns true.
4. If a stock exceeds volatility thresholds, it creates a new output record container `Record<>(symbol, perf, timestamp)` and calls `context.forward(...)` to send it downstream.
5. It safely closes the database iterator inside a try-with-resources block.

---

### Lab 10.2 — Wire the topology manually

#### Scenario
We will create the main entry application that maps out the execution flow using a `Topology` instance, adds the input source topic, attaches the custom processor, materializes the RocksDB state store, and outputs results to a sink topic.

#### Complete Application Java Code
Create the file [StockPerformanceTopologyApp.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/kafka-streams-in-action/modules/src/main/java/com/kafkastreams/course/labs/StockPerformanceTopologyApp.java) with the following content:

```java
package com.kafkastreams.course.labs;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.state.Stores;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;

public class StockPerformanceTopologyApp {
    private static final Logger log = LoggerFactory.getLogger(StockPerformanceTopologyApp.class);

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "stock-performance-topology-group");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, JsonSerde.class.getName());
        return props;
    }

    public static void main(String[] args) {
        log.info("Configuring Stock Performance Topology...");

        Topology topology = new Topology();
        JsonSerde<StockTransaction> transactionSerde = new JsonSerde<>();
        JsonSerde<StockPerformance> performanceSerde = new JsonSerde<>();

        // 1. Add Source node to read from stock-transactions topic
        topology.addSource("stock-source", "stock-transactions");

        // 2. Add custom Processor node as child of source node
        topology.addProcessor(
            "stock-processor",
            StockPerformanceProcessor::new,
            "stock-source"
        );

        // 3. Define and register RocksDB persistent key-value store in the topology
        topology.addStateStore(
            Stores.keyValueStoreBuilder(
                Stores.persistentKeyValueStore("stock-performance-store"),
                Serdes.String(),
                performanceSerde
            ),
            "stock-processor" // Associate store with our custom processor node
        );

        // 4. Add Sink node as child of processor node to write to stock-performance output topic
        topology.addSink(
            "stock-sink",
            "stock-performance",
            "stock-processor"
        );

        log.info("Topology wired successfully. Topology Description:
{}", topology.describe());

        KafkaStreams streams = new KafkaStreams(topology, getConfig());

        streams.cleanUp();
        streams.start();
        log.info("Stock Performance App is active!");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Shutting down stock topology app...");
            streams.close();
            log.info("Topology app stopped.");
        }));
    }
}
```

#### Step-by-Step Configuration and Wire-up Walkthrough

##### Topology Construction
1. We create a blank canvas using `new Topology()`.
2. **`addSource`**: We register an entry point named `"stock-source"`. This node reads raw message streams from the Kafka topic `"stock-transactions"`.
3. **`addProcessor`**: We register our processor logic node named `"stock-processor"`. We pass the constructor reference `StockPerformanceProcessor::new` as our supplier factory, and specify that its parent is the `"stock-source"` node.
4. **`addStateStore`**: We build a state store using `Stores.keyValueStoreBuilder(...)`. We define a RocksDB persistent store named `"stock-performance-store"` using String key serialization and our custom `StockPerformance` JSON serialization. We explicitly pass `"stock-processor"` as the target node authorized to access this store.
5. **`addSink`**: We define an exit node named `"stock-sink"` that outputs records to the Kafka topic `"stock-performance"`. We specify that its parent is the `"stock-processor"` node.

#### Configuration Details
The following table explains what each line of the configuration properties does:

| Property Name | Value | Purpose |
| :--- | :--- | :--- |
| `StreamsConfig.APPLICATION_ID_CONFIG` | `"stock-performance-topology-group"` | Serves as the consumer group coordination namespace and sets local RocksDB directory targets. |
| `StreamsConfig.BOOTSTRAP_SERVERS_CONFIG` | `"localhost:9092"` | Locates the Kafka cluster bootstrap brokers. |
| `StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG` | `Serdes.String()...` | Registers String as the default key serialization. |
| `StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG`| `JsonSerde.class...` | Configures default value de/serialization to use our custom JSON serializer. |
