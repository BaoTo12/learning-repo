# Module 02: Topology Verification with `TopologyTestDriver`

Testing individual operations in isolation is valuable, but verifying the interaction of the entire streaming pipeline is critical. The **`org.apache.kafka.streams.TopologyTestDriver`** allows you to execute and test complete topologies—including state stores, joins, and windowing rules—locally in-memory without starting a Kafka broker.

This module details how to setup the test driver, model input and output topics, control time advancement, and query internal state stores.

---

## 1. Setting Up the `TopologyTestDriver`

The `TopologyTestDriver` requires the `Topology` object and a set of configuration `Properties`. When running, it intercepts all inputs, pushes them through the topology DAG, updates local RocksDB instances, and routes outputs to in-memory buffers.

```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.TopologyTestDriver;
import org.apache.kafka.streams.TestInputTopic;
import org.apache.kafka.streams.TestOutputTopic;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.Properties;

public class YellingTopologyTest {

    private TopologyTestDriver testDriver;
    private TestInputTopic<String, String> inputTopic;
    private TestOutputTopic<String, String> outputTopic;

    @BeforeEach
    public void setUp() {
        // 1. Build the target topology
        StreamsBuilder builder = new StreamsBuilder();
        builder.stream("src-topic")
               .mapValues(value -> value.toString().toUpperCase())
               .to("out-topic");
        Topology topology = builder.build();

        // 2. Define minimum properties
        Properties props = new Properties();
        props.put("application.id", "yelling-test-app");
        props.put("bootstrap.servers", "mock:9092");

        // 3. Instantiate the driver
        testDriver = new TopologyTestDriver(topology, props);

        // 4. Create in-memory topics matching topology inputs/outputs
        inputTopic = testDriver.createInputTopic(
            "src-topic", Serdes.String().serializer(), Serdes.String().serializer());
        
        outputTopic = testDriver.createOutputTopic(
            "out-topic", Serdes.String().deserializer(), Serdes.String().deserializer());
    }

    @AfterEach
    public void tearDown() {
        // Clean up store files and thread pools
        testDriver.close();
    }

    @Test
    public void testUppercaseTransformation() {
        // Pipe a single record in
        inputTopic.pipeInput("hello world");
        
        // Assert the output
        String result = outputTopic.readValue();
        assert("HELLO WORLD".equals(result));
    }
}
```

---

## 2. Simulating Timestamps & Clocks

For topologies that rely on windowing or punctuators, processing behaviors depend on time advancement. The test driver does not query the host system clock. You must advance time manually:

### A. Advancing Clocks in `TestInputTopic`
You can advance the event time of the input topic. Subsequent records will inherit the updated event time:

```java
// Pipe record at current topic time
inputTopic.pipeInput("key-1", "event-A");

// Advance the input topic time by 15 seconds
inputTopic.advanceTime(Duration.ofSeconds(15));

// This record will be processed with a timestamp 15 seconds in the future
inputTopic.pipeInput("key-1", "event-B");
```

### B. Passing Instants Directly
For precise timestamps, pass `Instant` values inside `pipeInput`:

```java
Instant baseTime = Instant.now();

inputTopic.pipeInput("key-1", "event-A", baseTime);
inputTopic.pipeInput("key-1", "event-B", baseTime.plus(10, ChronoUnit.SECONDS));
```

### C. Advancing Wallclock Clocks (for Punctuators)
If your punctuators use `PunctuationType.WALL_CLOCK_TIME`, they rely on the host system clock. To trigger them, explicitly advance the driver's wallclock:

```java
// Advance the driver's system clock by 10 seconds to trigger wallclock punctuations
testDriver.advanceWallClockTime(Duration.ofSeconds(10));
```

---

## 3. Testing Suppression & Windows

When windowing aggregates are configured with suppression (`.suppress()`), they buffer updates until the window closes. To test these, you must feed events to advance stream time past the window end and grace period:

```java
@Test
public void testSuppressedWindowCount() {
    Instant start = Instant.parse("2026-06-12T12:00:00Z");

    // 1. Pipe 3 records inside the [12:00, 12:01) window
    inputTopic.pipeInput("user-1", "event", start.plusMillis(10));
    inputTopic.pipeInput("user-1", "event", start.plusMillis(20));
    inputTopic.pipeInput("user-1", "event", start.plusMillis(30));

    // Assert: No output has been emitted yet (buffered by suppression)
    assertThat(outputTopic.isEmpty(), is(true));

    // 2. Pipe a record to advance Stream Time past [12:01] (the window boundary)
    // The window has no grace period, so any timestamp >= 12:01:00 closes it.
    inputTopic.pipeInput("user-1", "event", start.plus(75, ChronoUnit.SECONDS));

    // Assert: The final result of 3 is emitted as the window closes
    assertThat(outputTopic.readValue(), is(3L));
}
```

---

## 4. Querying Internal State Stores

You can query the materialized state stores inside `TopologyTestDriver` to verify correct writes and updates:

```java
import org.apache.kafka.streams.state.KeyValueStore;

@Test
public void testStateStoreWrites() {
    inputTopic.pipeInput("Jane", 10.0);
    inputTopic.pipeInput("Jane", 20.0);

    // Fetch the key-value store from the driver by name
    KeyValueStore<String, Double> store = testDriver.getKeyValueStore("user-sum-store");

    // Assert the stored state directly
    Double janeTotal = store.get("Jane");
    assertThat(janeTotal, is(30.0));
}
```
`TopologyTestDriver` provides specialized lookups for all store types:
* `getKeyValueStore(name)`
* `getWindowStore(name)`
* `getSessionStore(name)`
* `getTimestampedKeyValueStore(name)`
