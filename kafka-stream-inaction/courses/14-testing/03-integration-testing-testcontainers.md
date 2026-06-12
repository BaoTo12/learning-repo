# Module 03: Integration Testing with Testcontainers

While mock classes and test drivers are highly effective for validating logic, they cannot simulate real broker scenarios. Network latency, broker-side ACL configurations, consumer partition rebalances, and disk-commit timings require testing against a live Kafka broker.

This module details how to write end-to-end integration tests using **Testcontainers** to spawn Docker-based brokers, manage topic lifecycle utilities, and use Spring's in-memory `@EmbeddedKafka` as an alternative.

---

## 1. End-to-End Integration Testing with Testcontainers

**Testcontainers** is a Java library that supports JUnit tests by instantiating and lifecycle-managing throwaway Docker containers. For Kafka integration tests, Testcontainers runs a real Confluent Platform Kafka image.

### Lifecycle Management
Annotating the test class with `@Testcontainers` tells the JUnit extension to manage container lifecycles. Declaring the `KafkaContainer` field as **`static`** ensures the container starts once before the first test method and stops after all tests are finished, saving substantial CPU overhead.

```java
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.Topology;
import org.junit.jupiter.api.*;
import org.testcontainers.containers.KafkaContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicBoolean;

@Testcontainers
public class StreamsIntegrationTest {

    // 1. Declare the Kafka container as a shared static resource
    @Container
    private static final KafkaContainer KAFKA = new KafkaContainer(
        DockerImageName.parse("confluentinc/cp-kafka:7.5.1")
    );

    private Properties streamsProps;
    private Properties producerProps;

    @BeforeEach
    public void setUp() {
        // 2. Fetch the dynamic broker bootstrap address from the running container
        String bootstrapServers = KAFKA.getBootstrapServers();

        streamsProps = new Properties();
        streamsProps.put(StreamsConfig.APPLICATION_ID_CONFIG, "integration-test-app");
        streamsProps.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        streamsProps.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, org.apache.kafka.common.serialization.Serdes.String().getClass().getName());
        streamsProps.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, org.apache.kafka.common.serialization.Serdes.String().getClass().getName());

        producerProps = new Properties();
        producerProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        producerProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());

        // Create topics (see Section 2)
        createTopics();
    }

    @AfterEach
    public void tearDown() {
        deleteTopics();
    }

    @Test
    public void testTopologyAgainstBroker() throws InterruptedException {
        Topology topology = buildTopology();
        AtomicBoolean streamsRunning = new AtomicBoolean(false);

        try (KafkaStreams kafkaStreams = new KafkaStreams(topology, streamsProps)) {
            // Wait for Streams client to transition to RUNNING before producing data
            kafkaStreams.setStateListener((newState, oldState) -> {
                if (newState == KafkaStreams.State.RUNNING) {
                    streamsRunning.set(true);
                }
            });

            kafkaStreams.start();

            // Block test execution until StreamThread is active
            while (!streamsRunning.get()) {
                Thread.sleep(100);
            }

            // Produce records, consume outputs, and assert results...
            produceInputRecord("input-topic", "key-1", "value-A");
        }
    }

    private void produceInputRecord(String topic, String key, String val) {
        try (KafkaProducer<String, String> producer = new KafkaProducer<>(producerProps)) {
            producer.send(new ProducerRecord<>(topic, key, val));
        }
    }
}
```

---

## 2. Managing Topic Lifecycle Utilities

To ensure test isolation, **always create and delete topics between test runs**. Reusing topics across tests can result in poison-pill records from a previous test method corrupting the consumer offset state in the next test.

```java
import org.apache.kafka.clients.admin.AdminClient;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.NewTopic;
import java.util.Collections;
import java.util.Properties;

public class TopicUtils {

    public static void createTopic(String bootstrapServers, String topicName, int partitions) {
        Properties config = new Properties();
        config.put(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        
        try (AdminClient admin = AdminClient.create(config)) {
            NewTopic newTopic = new NewTopic(topicName, partitions, (short) 1);
            admin.createTopics(Collections.singleton(newTopic)).all().get();
        } catch (Exception e) {
            throw new RuntimeException("Failed to create topic: " + topicName, e);
        }
    }

    public static void deleteTopic(String bootstrapServers, String topicName) {
        Properties config = new Properties();
        config.put(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        
        try (AdminClient admin = AdminClient.create(config)) {
            admin.deleteTopics(Collections.singleton(topicName)).all().get();
        } catch (Exception e) {
            // Ignore if topic does not exist
        }
    }
}
```

---

## 3. Spring Kafka: `@EmbeddedKafka` Alternative

If you do not have Docker running locally or want faster startup times during development, Spring Kafka provides a native, in-memory broker wrapper: **`@EmbeddedKafka`**.

```java
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.kafka.test.EmbeddedKafkaBroker;
import org.springframework.kafka.test.context.EmbeddedKafka;
import org.springframework.test.annotation.DirtiesContext;

@SpringBootTest
@EmbeddedKafka(
    partitions = 1, 
    topics = {"input-topic", "output-topic"},
    bootstrapServersProperty = "spring.kafka.bootstrap-servers" // Bind port dynamically
)
@DirtiesContext
public class EmbeddedBrokerIntegrationTest {

    @Autowired
    private EmbeddedKafkaBroker embeddedKafkaBroker;

    @Test
    public void testWithEmbeddedBroker() {
        String brokerList = embeddedKafkaBroker.getBrokersAsString();
        System.out.println("Embedded Kafka Broker active at: " + brokerList);
        
        // Execute Spring template tests...
    }
}
```

---

## 4. Testcontainers vs. `@EmbeddedKafka`

Choose the integration framework that fits your operational bounds:

| Metric / Aspect | Testcontainers (cp-kafka) | EmbeddedKafka |
|---|---|---|
| **Broker Engine** | Real production Docker container | JVM-embedded Kafka instance wrapper |
| **Port Management** | Dynamic randomized mapping | In-memory loopback or dynamic properties |
| **Docker Required** | **Yes** (Requires Docker Daemon running) | **No** (Runs completely inside JVM memory) |
| **Broker Version** | Matches production image version exactly | Bound to the spring-kafka library dependency |
| **Execution Time** | Moderate (5-15s startup cost) | Fast (1-3s startup cost) |
| **Use Case** | Validating production configurations | Rapid local CI/CD pipelines |
