# Module 17 — Testing

In this module, we will explore Testing in Spring Kafka applications. We will cover testing patterns for producers, consumers, and Kafka Streams topologies. We will discuss the difference between Embedded Kafka (`@EmbeddedKafka`) and Docker-based testing using Testcontainers. Finally, we will cover troubleshooting, answer 5 Socratic questions, and implement hands-on labs with complete code structures.

---

## 1. Academic Lecture: Embedded Kafka, Testcontainers & TopologyTestDriver

### Basic Level: Test Categories & Mocks

#### Testing Philosophy
When building event-driven pipelines, tests must cover different levels:
* **Unit Testing**: Testing single methods or classes (e.g. mapping JSON payload to POJO) by mocking dependencies.
* **Integration Testing**: Testing client interaction with a real Kafka broker (e.g. verifying headers are set and retry logic triggers).
* **End-to-End (E2E) Testing**: Testing the entire system (e.g. database commits, REST queries, and Kafka event routing) in a production-like environment.

---

### Intermediate Level: Embedded Kafka vs. Testcontainers

For integration and integration testing, we need a Kafka broker. We have two main approaches:

#### 1. Embedded Kafka (`@EmbeddedKafka`)
Spring provides an embedded broker implementation that runs directly inside the JVM process alongside your test runner.
* *Pros*: Fast startup; no local Docker installation required.
* *Cons*: Not a real Kafka broker. It lacks advanced features like transaction coordinators or schema registries. Port conflicts are common in parallel pipelines.

#### 2. Testcontainers Kafka (`Testcontainers`)
Testcontainers is a library that spins up docker containers for testing. It allows you to run a real Kafka container (e.g., Confluent Kafka, Zookeeper, Schema Registry) dynamically during tests.
* *Pros*: Runs a real production broker; supports Transactions and Schema Registry; isolation between tests.
* *Cons*: Slow startup; requires a running Docker daemon on the host machine.

---

### Advanced Level: Kafka Streams TopologyTestDriver

#### Kafka Streams Testing
Testing Kafka Streams topologies using real brokers is slow and complex. To solve this, Kafka Streams provides the **`TopologyTestDriver`**:
* **How it works**: It is a test driver that simulates broker input/output in memory. It does not spin up any threads or network sockets.
* **Benefits**: You can feed mock records into your topology and assert the outputs instantly. It executes in milliseconds, making it perfect for unit testing complex join and windowed aggregation logic.

```text
  [ Mock Input Topic ] ──► [ TopologyTestDriver ] ──► [ Assert Mock Output Topic ]
```

---

## 2. Theory & Production Best Practices

### Embedded Kafka vs. Testcontainers

| Feature | Embedded Kafka (`@EmbeddedKafka`) | Testcontainers (`KafkaContainer`) |
| :--- | :--- | :--- |
| **Broker Type** | Embedded Java (in-memory mock) | Real Docker broker container |
| **Startup Speed** | Fast (milliseconds) | Slow (seconds) |
| **Docker Required?** | No | Yes |
| **Transaction Support** | Limited / Buggy | Full |
| **Best Use Case** | Fast local integration tests | CI/CD pipeline validation |

### Mocks vs. Real Containers in CI/CD

| Strategy | Speed | Reliability | CI Complexity |
| :--- | :--- | :--- | :--- |
| **Mockito Mocks** | Extremely Fast | Low (does not verify serialization) | Low |
| **Embedded Kafka** | Fast | Medium (verifies local serialization) | Low |
| **Testcontainers** | Slow | High (verifies full network integration) | Medium (requires Docker-in-Docker)|

---

## 3. Common Errors & Troubleshooting

### 1. Port Collision Failures in Parallel Builds
* **Symptom**: Parallel Maven/Gradle builds fail with `BindException: Address already in use`.
* **Root Cause**: Multiple integration tests are trying to start `@EmbeddedKafka` on the same static port (e.g. `9092`).
* **Fix**: Configure Embedded Kafka to use a dynamic port (`controlledShutdown = true`, port `0`), and inject the dynamic address using `${spring.embedded.kafka.brokers}`.

### 2. Testcontainers Startup Timeout
* **Symptom**: Test runner fails with `ContainerLaunchException: Timed out waiting for container to start`.
* **Root Cause**: The host Docker daemon is slow, or downloading the Kafka image took longer than the timeout limit.
* **Fix**: Increase the start timeout limit programmatically: `container.withStartupTimeout(Duration.ofMinutes(3))`.

### 3. State Store NullPointer in TopologyTestDriver
* **Symptom**: Topology tests fail with `NullPointerException` during state store lookup.
* **Root Cause**: The test driver was not initialized correctly, or the state store name in the topology does not match the name referenced in the query.
* **Fix**: Ensure `topologyTestDriver.getKeyValueStore("store-name")` matches the exact string defined in your `Materialized.as()` topology.

---

## 4. Socratic Review Questions

### Question 1
*Why is `@EmbeddedKafka` preferred for local developer loops, while Testcontainers is preferred for CI/CD pipelines?*
* **Answer**: Because developers value fast feedback loops. `@EmbeddedKafka` starts in milliseconds, whereas Testcontainers requires pulling Docker images and waiting for container startup. In CI/CD pipelines, reliability is paramount, and running a real Kafka container ensures that network, security, and transaction behaviors behave exactly as they will in production.

### Question 2
*How does `DynamicPropertySource` enable Spring Boot 3.x to resolve dynamic Testcontainers broker addresses?*
* **Answer**: Since Testcontainers maps the internal container port 9092 to a random available host port at startup (e.g., 32456), the broker address is not known beforehand. `@DynamicPropertySource` allows tests to intercept Spring properties at runtime and inject the dynamic address (`bootstrap-servers = container.getBootstrapServers()`).

### Question 3
*What is the main benefit of testing Kafka Streams using `TopologyTestDriver` over an embedded broker?*
* **Answer**: Execution speed and determinism. `TopologyTestDriver` runs synchronously in a single thread, eliminating partition timing and network latency issues, and runs in milliseconds.

### Question 4
*How can you assert that a consumer listener successfully committed an offset during an integration test?*
* **Answer**: Use a spy on the consumer factory or check partition logs. Alternatively, send a test message, wait for processing, stop the container, and assert that the consumer group's committed offset is incremented.

### Question 5
*Why must you call `topologyTestDriver.close()` after each test method runs?*
* **Answer**: To release local RocksDB memory and lock resources. If left open, subsequent tests might fail to initialize their state stores due to file access conflicts.

---

## 5. Hands-on Labs

### Lab 17.1 — Embedded Kafka Integration Test

#### Scenario
We will write a JUnit 5 integration test using `@EmbeddedKafka` to verify that our Spring listener consumes messages published to a test topic.

#### Complete Test Java Code
Create the file [EmbeddedKafkaTest.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/test/java/com/springkafka/course/EmbeddedKafkaTest.java) with the following content:

```java
package com.springkafka.course;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.test.context.EmbeddedKafka;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
@EmbeddedKafka(partitions = 1, topics = { "test-topic" })
public class EmbeddedKafkaTest {

    private static final Logger log = LoggerFactory.getLogger(EmbeddedKafkaTest.class);
    private static final CountDownLatch latch = new CountDownLatch(1);

    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;

    @Test
    public void testListenerConsumesMessage() throws InterruptedException {
        log.info("Sending message to embedded broker...");
        kafkaTemplate.send("test-topic", "key", "Test payload data");

        // Wait up to 5 seconds for consumer thread to count down
        boolean messageReceived = latch.await(5, TimeUnit.SECONDS);
        assertTrue(messageReceived, "Consumer did not receive the message in time!");
    }

    // Temporary consumer component inside test scope
    @Component
    public static class TestConsumer {
        @KafkaListener(id = "test-consumer-id", topics = "test-topic")
        public void consume(String message) {
            log.info("Test consumer received message: {}", message);
            latch.countDown();
        }
    }
}
```

---

### Lab 17.2 — Testcontainers Kafka E2E Test

#### Scenario
We will write an integration test using Testcontainers to spin up a real Kafka docker container and map dynamic boot properties.

#### Complete Testcontainers Test Java Code
Create the file [TestcontainersKafkaTest.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/test/java/com/springkafka/course/TestcontainersKafkaTest.java) with the following content:

```java
package com.springkafka.course;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.KafkaContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
@Testcontainers // Activates Testcontainers lifecycle
public class TestcontainersKafkaTest {

    // 1. Define real Kafka docker container
    @Container
    public static KafkaContainer kafkaContainer = new KafkaContainer(
            DockerImageName.parse("confluentinc/cp-kafka:7.4.0")
    );

    // 2. Map dynamic container port to Spring bootstrap server properties
    @DynamicPropertySource
    public static void registerProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.kafka.bootstrap-servers", kafkaContainer::getBootstrapServers);
    }

    private static final CountDownLatch latch = new CountDownLatch(1);

    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;

    @Test
    public void testE2ePipeline() throws InterruptedException {
        kafkaTemplate.send("e2e-topic", "key", "Testcontainers integration");

        boolean received = latch.await(10, TimeUnit.SECONDS);
        assertTrue(received, "E2E consumer did not receive message from Docker broker!");
    }

    @Component
    public static class E2eConsumer {
        @KafkaListener(id = "e2e-consumer-id", topics = "e2e-topic")
        public void consume(String payload) {
            latch.countDown();
        }
    }
}
```

---

### Lab 17.3 — Kafka Streams TopologyTestDriver Test

#### Scenario
We will use `TopologyTestDriver` to unit test a Kafka Streams topology class without running any broker instance.

#### Complete TopologyTestDriver Java Code
Create the file [StreamsTopologyTest.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/test/java/com/springkafka/course/StreamsTopologyTest.java) with the following content:

```java
package com.springkafka.course;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.TopologyTestDriver;
import org.apache.kafka.streams.TestInputTopic;
import org.apache.kafka.streams.TestOutputTopic;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KStream;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Properties;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class StreamsTopologyTest {

    private TopologyTestDriver testDriver;
    private TestInputTopic<String, String> inputTopic;
    private TestOutputTopic<String, String> outputTopic;

    @BeforeEach
    public void setup() {
        // 1. Build simple topology
        StreamsBuilder builder = new StreamsBuilder();
        KStream<String, String> sourceStream = builder.stream("input-topic", Consumed.with(Serdes.String(), Serdes.String()));
        
        // Convert input payload to uppercase
        sourceStream.mapValues(value -> value.toUpperCase()).to("output-topic");
        
        Topology topology = builder.build();

        // 2. Initialize test driver properties
        Properties props = new Properties();
        props.setProperty("application.id", "test-streams-app");
        props.setProperty("bootstrap.servers", "mock:1234");

        testDriver = new TopologyTestDriver(topology, props);

        // 3. Setup mock input and output topics
        inputTopic = testDriver.createInputTopic(
            "input-topic", 
            Serdes.String().serializer(), 
            Serdes.String().serializer()
        );
        outputTopic = testDriver.createOutputTopic(
            "output-topic", 
            Serdes.String().deserializer(), 
            Serdes.String().deserializer()
        );
    }

    @AfterEach
    public void tearDown() {
        if (testDriver != null) {
            testDriver.close(); // Release locks and memory
        }
    }

    @Test
    public void testUpperCaseTopology() {
        // 4. Pipe mock record and verify response instantly
        inputTopic.pipeInput("key-123", "hello world");
        
        String outputValue = outputTopic.readValue();
        assertEquals("HELLO WORLD", outputValue);
    }
}
```

---

### Step-by-Step Code Walkthrough & Parameter Configuration Tables

#### Step-by-Step Code Walkthrough

##### Lab 17.1 Walkthrough
1. **`@EmbeddedKafka`**: Instructs JUnit to spin up an in-memory broker instance at startup.
2. **`CountDownLatch`**: Blends asynchronous listener consumption with synchronous assertion execution.

##### Lab 17.2 Walkthrough
1. **`@Container`**: Starts a real Confluent Docker broker instance.
2. **`@DynamicPropertySource`**: Modifies the `spring.kafka.bootstrap-servers` configuration at test startup.

##### Lab 17.3 Walkthrough
1. **`TopologyTestDriver`**: Runs stream topologies in memory.
2. **`pipeInput`**: Feeds mock data into the stream pipeline.
3. **`readValue`**: Reads final state changes from the mock destination topic.

---

### Configuration Parameter Tables

#### Embedded Kafka `@EmbeddedKafka` Annotation Attributes

| Attribute Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `partitions` | `int` | `2` | The partition count initialized for each generated test topic. |
| `topics` | `String[]` | `{}` | The list of topic names to pre-create on the embedded broker at boot. |
| `brokerProperties` | `String[]`| `{}` | Custom broker property settings overrides (e.g. `transaction.state.log.min.isr=1`). |

