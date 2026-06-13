# Module 03: Punctuation & Scheduling

Punctuation is the mechanism by which Kafka Streams schedules periodic execution of logic inside custom processors. Rather than running tasks inside external cron jobs or background executor pools, you can schedule a callback directly within the processor context.

This module details how to register and implement a `Punctuator`, compares the two types of scheduling triggers, and covers the thread-safety guarantees of punctuation.

---

## 1. Defining and Registering a `Punctuator`

A `Punctuator` is a callback interface containing a single method: `void punctuate(long timestamp)`. You register it inside the `init()` method of your processor using the `ProcessorContext.schedule()` method:

```java
import org.apache.kafka.streams.processor.api.ContextualProcessor;
import org.apache.kafka.streams.processor.api.ProcessorContext;
import org.apache.kafka.streams.processor.api.Record;
import org.apache.kafka.streams.processor.PunctuationType;
import org.apache.kafka.streams.processor.Punctuator;
import org.apache.kafka.streams.state.KeyValueStore;
import org.apache.kafka.streams.state.KeyValueIterator;
import org.apache.kafka.streams.KeyValue;
import java.time.Duration;

public class StockPerformanceProcessor extends ContextualProcessor<String, StockTransaction, String, StockPerformance> {

    private KeyValueStore<String, StockPerformance> stateStore;

    @Override
    public void init(ProcessorContext<String, StockPerformance> context) {
        super.init(context);
        this.stateStore = context().getStateStore("stock-performance-store");

        // Schedule a Punctuator callback to execute every 10 seconds (Stream Time)
        context().schedule(
            Duration.ofSeconds(10),
            PunctuationType.STREAM_TIME,
            new StockPerformancePunctuator(context(), stateStore)
        );
    }

    @Override
    public void process(Record<String, StockTransaction> record) {
        // Logic to update stats in stateStore
    }
}
```

---

## 2. Punctuation Types: Stream Time vs. Wallclock Time

You must specify the trigger mechanic by selecting a `PunctuationType`:

### A. `PunctuationType.STREAM_TIME`
* **Mechanic**: Driven exclusively by record timestamps extracted from consumed records.
* **Trigger Condition**: Punctuation fires when the system advances its task-level Stream Time past the scheduled threshold. If `lastPunctuateTime + interval <= currentStreamTime`, the punctuator runs.
* **Key Characteristic**: If data consumption stalls or stops completely, Stream Time freezes, and **STREAM_TIME punctuations will never fire**.
* **Use Case**: Financial metrics, computing sliding session windows, or reporting metrics tied strictly to business events.

### B. `PunctuationType.WALL_CLOCK_TIME`
* **Mechanic**: Driven by the physical system clock of the JVM machine running the application.
* **Trigger Condition**: Punctuation fires when the physical wallclock time elapsed exceeds the interval.
* **Key Characteristic**: Fires regardless of whether the application is actively consuming messages. It runs during the polling loop cycle of the stream thread.
* **Use Case**: Clearing stale aggregations, periodically dumping cache records to an external API, or diagnostic heartbeats.

---

## 3. Implementing the Punctuator Callback

The `punctuate` method has access to the state store and can forward records downstream. Here is a production implementation of a punctuator that scans a store and emits records that cross a trending threshold:

```java
import org.apache.kafka.streams.KeyValue;
import org.apache.kafka.streams.processor.Punctuator;
import org.apache.kafka.streams.processor.api.ProcessorContext;
import org.apache.kafka.streams.processor.api.Record;
import org.apache.kafka.streams.state.KeyValueIterator;
import org.apache.kafka.streams.state.KeyValueStore;

public class StockPerformancePunctuator implements Punctuator {

    private final ProcessorContext<String, StockPerformance> context;
    private final KeyValueStore<String, StockPerformance> stateStore;
    private final double differentialThreshold = 0.02; // 2% threshold

    public StockPerformancePunctuator(ProcessorContext<String, StockPerformance> context,
                                     KeyValueStore<String, StockPerformance> stateStore) {
        this.context = context;
        this.stateStore = stateStore;
    }

    @Override
    public void punctuate(long timestamp) {
        // 1. Query the state store
        try (KeyValueIterator<String, StockPerformance> iterator = stateStore.all()) {
            while (iterator.hasNext()) {
                KeyValue<String, StockPerformance> entry = iterator.next();
                StockPerformance performance = entry.value;

                if (performance != null) {
                    double priceDiff = performance.getPriceDifferential();
                    double volDiff = performance.getShareDifferential();

                    // 2. Evaluate business logic
                    if (priceDiff >= differentialThreshold || volDiff >= differentialThreshold) {
                        // 3. Forward record downstream using the context
                        context.forward(new Record<>(entry.key, performance, timestamp));
                    }
                }
            }
        }
    }
}
```

---

## 4. Single-Threaded Execution Guarantees & Thread Safety

A common point of concern is whether `process()` and `punctuate()` can access state stores or mutate local fields concurrently. 

* **No Concurrent Execution**: Kafka Streams guarantees that **`Processor.process()` and `Punctuator.punctuate()` are executed sequentially by the same parent `StreamThread`**.
* **Thread Safety**: Because a task's operations are completely bound to a single thread:
  1. You do not need to use `synchronized` blocks, lock variables, or thread-safe atomic data structures (like `AtomicLong`) to coordinate state changes between `process()` and `punctuate()`.
  2. The thread processes a record fully (calling `process()`), checks if any punctuations are eligible, runs eligible `punctuate()` callbacks, and only then fetches the next batch of records from the broker.

### Punctuation Best Practices

#### Do Not Block
Because punctuation runs on the critical stream processing thread, **blocking operations (like synchronous HTTP requests or slow database transactions) inside `punctuate()` will block the entire task consumption loop**. This causes consumer lag to spike and heartbeat timeouts to fail, forcing group rebalances.

#### Clean Up
If you schedule a punctuator that is temporary, capture the returned `Cancellable` instance from `schedule()` and call `cancel()` when it is no longer required:

```java
import org.apache.kafka.streams.processor.Cancellable;

Cancellable cancellable = context().schedule(Duration.ofMinutes(1), PunctuationType.WALL_CLOCK_TIME, callback);
// Later...
cancellable.cancel();
```
