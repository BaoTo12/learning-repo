# Course 14: Quality Assurance and Testing

Welcome to **Course 14: Quality Assurance and Testing**. Testing distributed event-driven systems can be highly complex due to temporal behaviors, network partitions, and state synchronization. A robust testing strategy comprises unit tests to validate individual business logic rules, topology tests to verify streaming graphs, and end-to-end integration tests using live brokers.

Through this course, you will learn how to mock client interactions, verify stream topologies using the `TopologyTestDriver` harness, and write comprehensive integration tests with Testcontainers.

## Syllabus & Modules

1. **[Module 01: Unit Testing Clients & Mock Objects](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/14-testing/01-unit-testing-clients.md)**
   * Test Kafka producers and consumers using native `MockProducer` and `MockConsumer` classes.
   * Coordinate asynchronous poll loop executions in tests using `schedulePollTask()`.
   * Leverage Mockito to mock Kafka Streams `ProcessorContext` and state stores.
2. **[Module 02: Topology Verification with `TopologyTestDriver`](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/14-testing/02-topology-test-driver.md)**
   * Harness the broker-free `TopologyTestDriver` to test entire DSL and Processor topologies.
   * Define input and output topics using `TestInputTopic` and `TestOutputTopic`.
   * Simulate record timestamps to advance Stream Time and trigger window completions or punctuators.
   * Directly verify the states of internal RockDB stores using `getKeyValueStore()`.
3. **[Module 03: Integration Testing with Testcontainers](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/14-testing/03-integration-testing-testcontainers.md)**
   * Set up live-broker integration tests using Docker containers via Confluent Testcontainers.
   * Manage container lifecycles in JUnit 5 using `@Testcontainers` and static container optimization.
   * Implement automated topic setup and cleanup logic between test suites.
   * Examine Spring Kafka's native `@EmbeddedKafka` as an alternative in-memory broker approach.

## Course Prerequisites
* Completed **Course 4: High-Performance Kafka Clients**, **Course 10: Processor API**, and **Course 12: Enterprise Integration with Spring Kafka**.
* Understanding of unit testing concepts (JUnit 5, AssertJ/Hamcrest).
