# Module 02: Contextual Processors & State Stores

State stores are key to building analytical or transactional processing logic in stream systems. In the Processor API, you must explicitly construct, register, and bind these state stores to the processors that need to access them.

This module covers the lifecycle of state stores, how to declare and bind stores to your topology, and how to interact with them inside a `ContextualProcessor`.

---

## 1. Instantiating State Stores

In the Processor API, you instantiate stores using the `org.apache.kafka.streams.state.Stores` utility class. This class provides builders for different storage backends:

```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.state.KeyValueBytesStoreSupplier;
import org.apache.kafka.streams.state.StoreBuilder;
import org.apache.kafka.streams.state.Stores;

// Create an in-memory key-value store supplier
KeyValueBytesStoreSupplier inMemoryStoreSupplier = 
    Stores.inMemoryKeyValueStore("sensor-state-store");

// Create a persistent (RocksDB) key-value store supplier
KeyValueBytesStoreSupplier persistentStoreSupplier = 
    Stores.persistentKeyValueStore("sensor-state-store");

// Wrap the supplier in a StoreBuilder
StoreBuilder<KeyValueStore<String, SensorAggregation>> storeBuilder =
    Stores.keyValueStoreBuilder(
        persistentStoreSupplier,
        Serdes.String(),
        new SensorAggregationSerde()
    );
```

---

## 2. Binding State Stores to Processors

A processor cannot access a state store unless it has been explicitly wired to it in the topology. There are two primary patterns for doing this:

### Pattern A: Auto-Binding via `ProcessorSupplier` (Recommended)
You can override the `stores()` method in your `ProcessorSupplier` implementation. Kafka Streams will automatically add these stores to the topology and bind them to the processor returned by `get()`:

```java
import org.apache.kafka.streams.processor.api.Processor;
import org.apache.kafka.streams.processor.api.ProcessorSupplier;
import org.apache.kafka.streams.state.StoreBuilder;
import java.util.Collections;
import java.util.Set;

public class SensorProcessorSupplier implements ProcessorSupplier<String, Sensor, String, SensorAggregation> {

    private final StoreBuilder<KeyValueStore<String, SensorAggregation>> storeBuilder;

    public SensorProcessorSupplier(StoreBuilder<KeyValueStore<String, SensorAggregation>> storeBuilder) {
        this.storeBuilder = storeBuilder;
    }

    @Override
    public Processor<String, Sensor, String, SensorAggregation> get() {
        return new SensorProcessor(storeBuilder.name());
    }

    @Override
    public Set<StoreBuilder<?>> stores() {
        // Automatically wires the state store to the topology and processor
        return Collections.singleton(storeBuilder);
    }
}
```

### Pattern B: Manual Topology Registration
If you build the supplier as a raw lambda, you must register the state store and associate it manually:

```java
Topology topology = new Topology();

topology.addSource("source", ...)
        .addProcessor("processor", () -> new CustomProcessor(), "source");

// Register the store
topology.addStateStore(storeBuilder);

// Explicitly connect the store to the processor
topology.connectProcessorAndStateStores("processor", "sensor-state-store");
```

---

## 3. Implementing the Stateful Processor

To interact with the store, extend the `org.apache.kafka.streams.processor.api.ContextualProcessor` class. This class manages the `ProcessorContext` lifecycle for you. You retrieve the store in the `init()` method:

```java
import org.apache.kafka.streams.processor.api.ContextualProcessor;
import org.apache.kafka.streams.processor.api.ProcessorContext;
import org.apache.kafka.streams.processor.api.Record;
import org.apache.kafka.streams.state.KeyValueStore;

public class SensorProcessor extends ContextualProcessor<String, Sensor, String, SensorAggregation> {

    private final String storeName;
    private KeyValueStore<String, SensorAggregation> stateStore;

    public SensorProcessor(String storeName) {
        this.storeName = storeName;
    }

    @Override
    public void init(ProcessorContext<String, SensorAggregation> context) {
        // Always invoke the super method to initialize the ContextualProcessor
        super.init(context);
        
        // Retrieve the state store from the context
        this.stateStore = context().getStateStore(storeName);
    }

    @Override
    public void process(Record<String, Sensor> record) {
        String key = record.key();
        Sensor value = record.value();

        // 1. Fetch current aggregated value
        SensorAggregation currentAgg = stateStore.get(key);

        if (currentAgg == null) {
            currentAgg = new SensorAggregation(value.getId(), 0.0, 0);
        }

        // 2. Update state calculations
        double newAvg = ((currentAgg.getAverage() * currentAgg.getCount()) + value.getReading()) 
                        / (currentAgg.getCount() + 1);
        int newCount = currentAgg.getCount() + 1;

        SensorAggregation updatedAgg = new SensorAggregation(value.getId(), newAvg, newCount);

        // 3. Persist the updated state back to the store
        stateStore.put(key, updatedAgg);

        // 4. Optionally forward a record downstream
        context().forward(new Record<>(key, updatedAgg, record.timestamp()));
    }

    @Override
    public void close() {
        // Release any local resources. No need to close the stateStore; 
        // Kafka Streams handles that lifecycle.
    }
}
```

---

## 4. Production Architectural Guidelines

### rocksdb JNI Local Directory Layout
When using persistent state stores, Kafka Streams leverages RocksDB. Each task maintains its local DB partitions under the directory configured by `state.dir` (defaults to `/var/lib/kafka-streams/`). 
* **Warning**: Never run multiple active instances of the same application pointing to the exact same local path on a shared drive. RocksDB acquires a filesystem lock on the DB directory; a second thread attempting to acquire the lock will throw an unrecoverable `RocksDBException`.

### Changelog Topics (State Backup)
Under the hood, Kafka Streams automatically configures a **changelog topic** for every state store to back up local states in case a broker or node crashes.
* **Tuning Compaction**: Ensure your changelog topics are configured with `cleanup.policy=compact`. If cleanup is set to `delete`, old records will expire, leading to data loss when rebuilding the local RocksDB state during task migration.
