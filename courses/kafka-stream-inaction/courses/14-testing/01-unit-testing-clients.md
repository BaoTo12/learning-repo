# Module 01: Unit Testing Clients & Mock Objects

To keep unit tests fast and repeatable, you must be able to test your producers, consumers, and stream processors without connecting to a live Kafka cluster. Apache Kafka and mocking libraries like Mockito provide classes to isolate your code and verify logic in sub-second test runs.

This module details how to use native mocks for consumer and producer clients, manage consumer polling tasks, and mock internal stream dependencies.

---

## 1. Unit Testing Clients with `MockConsumer` and `MockProducer`

Using interfaces like `Consumer<K, V>` and `Producer<K, V>` (rather than the concrete implementations `KafkaConsumer` and `KafkaProducer`) allows you to inject mocks during testing. Kafka provides built-in testing mocks for this purpose:
* `org.apache.kafka.clients.consumer.MockConsumer`
* `org.apache.kafka.clients.producer.MockProducer`

---

## 2. Managing the Consumer Poll Loop (`schedulePollTask`)

A standard Kafka consumer client runs in an infinite `while(true)` poll loop. When writing a unit test, calling this loop blocks the thread, preventing you from injecting new records or calling `close()`.

The `MockConsumer` resolves this by providing **`schedulePollTask(Runnable)`**. It schedules tasks in an internal queue that execute sequentially every time the client calls `.poll(...)`.

Here is a complete Junit 5 test verifying a currency exchange consumer/producer loop:

```java
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.MockConsumer;
import org.apache.kafka.clients.consumer.OffsetResetStrategy;
import org.apache.kafka.clients.producer.MockProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringSerializer;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;

public class CurrencyExchangeClientTest {

    private MockConsumer<String, CurrencyTransaction> mockConsumer;
    private MockProducer<String, CurrencyTransaction> mockProducer;
    private CurrencyExchangeClient client;

    @BeforeEach
    public void setUp() {
        mockConsumer = new MockConsumer<>(OffsetResetStrategy.EARLIEST);
        mockProducer = new MockProducer<>(true, new StringSerializer(), new CurrencyTransactionSerializer());
        
        client = new CurrencyExchangeClient(
            mockConsumer,
            mockProducer,
            "exchange-input",
            "exchange-output"
        );
    }

    @Test
    public void testRunExchangeLoop() {
        TopicPartition partition = new TopicPartition("exchange-input", 0);

        // 1. Schedule Task 1: Rebalance and assign partition
        mockConsumer.schedulePollTask(() -> {
            mockConsumer.rebalance(Collections.singletonList(partition));
            Map<TopicPartition, Long> beginningOffsets = new HashMap<>();
            beginningOffsets.put(partition, 0L);
            mockConsumer.updateBeginningOffsets(beginningOffsets);
        });

        // 2. Schedule Task 2: Inject test records into the partition
        mockConsumer.schedulePollTask(() -> {
            mockConsumer.addRecord(new ConsumerRecord<>(
                "exchange-input", 0, 0L, "key-1", 
                new CurrencyTransaction(100.00, "EUR")
            ));
        });

        // 3. Schedule Task 3: Trigger client shutdown
        mockConsumer.schedulePollTask(client::close);

        // 4. Execute the client loop
        client.runExchange();

        // 5. Verify results in MockProducer's history
        List<ProducerRecord<String, CurrencyTransaction>> history = mockProducer.history();
        assertThat(history.size(), equalTo(1));
        
        CurrencyTransaction outputTx = history.get(0).value();
        assertThat(outputTx.getCurrency(), equalTo("USD"));
        assertThat(outputTx.getAmount(), equalTo(110.00)); // Evaluated at 1.10 rate
    }
}
```

---

## 3. Mocking Stream Collaborators with Mockito

Custom Kafka Streams operators (like `Processor` or `Punctuator`) rely on internal interfaces like `ProcessorContext` or `KeyValueStore`. Rather than instantiating the entire streaming engine, you can use Mockito to mock these interfaces.

Here is a test for a custom `StockPerformancePunctuator` verifying record forwarding:

```java
import org.apache.kafka.streams.KeyValue;
import org.apache.kafka.streams.processor.api.ProcessorContext;
import org.apache.kafka.streams.processor.api.Record;
import org.apache.kafka.streams.state.KeyValueIterator;
import org.apache.kafka.streams.state.KeyValueStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import java.util.Collections;
import static org.mockito.Mockito.*;

public class StockPerformancePunctuatorTest {

    private ProcessorContext<String, StockPerformance> mockContext;
    private KeyValueStore<String, StockPerformance> mockStore;
    private StockPerformancePunctuator punctuator;

    @BeforeEach
    public void setUp() {
        mockContext = mock(ProcessorContext.class);
        mockStore = mock(KeyValueStore.class);
        
        punctuator = new StockPerformancePunctuator(0.02, mockContext, mockStore);
    }

    @Test
    public void testPunctuationThreshold() {
        long timestamp = 1000L;
        String symbol = "CFLT";
        
        StockPerformance performance = new StockPerformance();
        performance.setPriceDifferential(0.03); // Crosses the 2% (0.02) threshold

        // Create a mock iterator to return our test data
        KeyValueIterator<String, StockPerformance> mockIterator = mock(KeyValueIterator.class);
        when(mockIterator.hasNext()).thenReturn(true, false);
        when(mockIterator.next()).thenReturn(new KeyValue<>(symbol, performance));

        // Stub out the store to return our mock iterator
        when(mockStore.all()).thenReturn(mockIterator);

        // Run the punctuator
        punctuator.punctuate(timestamp);

        // Verify that the record was forwarded exactly once
        Record<String, StockPerformance> expectedRecord = new Record<>(symbol, performance, timestamp);
        verify(mockContext, times(1)).forward(expectedRecord);
    }
}
```

---

## 4. Production Unit Testing Guidelines

### Injecting Interfaces
Always design your class constructors to receive the abstract types:
* Prefer `Consumer<K, V>` over `KafkaConsumer<K, V>`.
* Prefer `Producer<K, V>` over `KafkaProducer<K, V>`.
Failing to do this makes subclass mock injection impossible, forcing you to spin up real client threads.

### Resetting Mock States
Mockito mocks retain stubbing and invocation history for the lifecycle of the test class. If you share mocks across multiple tests, invoke `Mockito.reset(mock)` in your `@AfterEach` method or setup fresh mock instances for each test to prevent test cross-contamination.
