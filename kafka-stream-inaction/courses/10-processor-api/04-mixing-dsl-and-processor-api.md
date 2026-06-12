# Module 04: Mixing DSL & the Processor API

Building an application completely in the high-level DSL or completely in the low-level Processor API is rarely necessary. Real-world stream processing topologies often use the DSL for routing, parsing, and serialization, but drop down to the Processor API for custom business logic, scheduled punctuating, or fine-grained state store lookups.

This module details how to integrate custom processors into a DSL pipeline, explains the modernization of the integration APIs, and provides a production implementation example.

---

## 1. When to Mix the APIs

You should mix the DSL and Processor API when:
* You want to use DSL features like `.filter()`, `.map()`, and Schema Registry integration, but you need a custom processor to schedule punctuators.
* You need to route events dynamically to multiple downstream destinations, or control exactly when records are forwarded downstream (e.g. suppression based on complex custom indicators).
* You want to execute a custom data-driven windowing aggregation that does not fit into Tumbling, Hopping, Session, or Sliding window semantics.

---

## 2. The Modern `KStream.process()` API

In modern Kafka Streams versions (since 3.0.0), the primary integration point is the **`KStream.process()`** method. 

```java
public <KOut, VOut> KStream<KOut, VOut> process(
    ProcessorSupplier<? super K, ? super V, KOut, VOut> processorSupplier,
    String... stateStoreNames
);
```

### Deprecated API Cleanup: `transform()` vs `process()`
Historically, developers had to choose between several different methods to integrate custom logic. These have been deprecated:

* **Deprecated `KStream.transform()` / `KStream.transformValues()`**:
  * These operators returned a new `KStream` value directly but had confusing semantics around state store integration and record context manipulation.
  * They required developers to return values from the `transform()` call rather than using the standard `context().forward()` method for downstream routing.
* **Modern `KStream.process()`**:
  * Unifies the signature. The custom processor can receive any input key-value pair `<K, V>` and emit zero, one, or multiple key-value pairs `<KOut, VOut>` using `context().forward(record)`.
  * Allows you to supply the names of any `StateStore` instances the processor needs to query.

---

## 3. End-to-End Implementation: Mixing DSL and Processor

Here is a complete, production-grade example of a DSL application that incorporates a custom processor to analyze stock price trends.

### Step 1: Define the Stream and Wire the Processor

```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Produced;
import org.apache.kafka.streams.state.KeyValueStore;
import org.apache.kafka.streams.state.StoreBuilder;
import org.apache.kafka.streams.state.Stores;

public class StockPerformanceDslApplication {

    public void buildTopology(StreamsBuilder builder) {
        String inputTopic = "stock-transactions";
        String outputTopic = "stock-performance-alerts";
        String storeName = "stock-performance-store";

        // 1. Declare the state store builder using the Stores utility
        StoreBuilder<KeyValueStore<String, StockPerformance>> storeBuilder =
            Stores.keyValueStoreBuilder(
                Stores.persistentKeyValueStore(storeName),
                Serdes.String(),
                new StockPerformanceSerde()
            );

        // 2. Register the state store builder directly with the StreamsBuilder
        builder.addStateStore(storeBuilder);

        // 3. Construct the DSL pipeline
        KStream<String, StockTransaction> transactionStream = builder.stream(
            inputTopic,
            Consumed.with(Serdes.String(), new StockTransactionSerde())
        );

        // 4. Inject the custom processor, passing the store name
        KStream<String, StockPerformance> alertsStream = transactionStream.process(
            () -> new StockPerformanceProcessor(storeName),
            storeName // Wire access to the store
        );

        // 5. Output downstream
        alertsStream.to(
            outputTopic,
            Produced.with(Serdes.String(), new StockPerformanceSerde())
        );
    }
}
```

### Step 2: Implement the Custom Processor

```java
import org.apache.kafka.streams.processor.api.ContextualProcessor;
import org.apache.kafka.streams.processor.api.ProcessorContext;
import org.apache.kafka.streams.processor.api.Record;
import org.apache.kafka.streams.state.KeyValueStore;

public class StockPerformanceProcessor 
    extends ContextualProcessor<String, StockTransaction, String, StockPerformance> {

    private final String storeName;
    private KeyValueStore<String, StockPerformance> stateStore;

    public StockPerformanceProcessor(String storeName) {
        this.storeName = storeName;
    }

    @Override
    public void init(ProcessorContext<String, StockPerformance> context) {
        super.init(context);
        this.stateStore = context().getStateStore(storeName);
    }

    @Override
    public void process(Record<String, StockTransaction> record) {
        String symbol = record.key();
        StockTransaction tx = record.value();

        StockPerformance stats = stateStore.get(symbol);
        if (stats == null) {
            stats = new StockPerformance();
        }

        // Add transaction details to moving average calculations
        stats.updatePrice(tx.getSharePrice());
        stats.updateVolume(tx.getShares());

        stateStore.put(symbol, stats);

        // Trigger dynamic forwarding based on thresholds
        if (stats.getPriceDifferential() >= 0.02) { // 2% drift
            context().forward(new Record<>(symbol, stats, record.timestamp()));
        }
    }
}
```

---

## 4. Operational Best Practices

### Store Registration Ordering
You must call `builder.addStateStore()` **before** referencing that store name inside `.process()`. Failing to add the store to the builder first will cause an immediate `TopologyException` during builder construction: *"StateStore X is not added to the topology."*

### Re-partitioning Hazards
Inserting a custom processor with `.process()` can alter the message key. 
* **Key Preservation**: If your custom processor mutates the record key and forwards it, Kafka Streams will flag the downstream stream as "key-modified".
* **Auto-Repartitioning**: Any subsequent stateful operations (like windowed aggregations or joins) will automatically trigger the creation of internal re-partition topics to ensure correct routing. If you preserve the key, make sure the processor forwards the record with the original key to avoid unnecessary network hops.
