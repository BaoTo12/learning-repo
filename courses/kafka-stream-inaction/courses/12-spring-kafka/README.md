# Course 12: Enterprise Integration with Spring Kafka

Welcome to **Course 12: Enterprise Integration with Spring Kafka**. This course covers how to integrate Apache Kafka and Kafka Streams with the Spring and Spring Boot frameworks. You will explore dependency injection, automatic configuration, consuming and producing messages via standard annotations, error-handling topologies with non-blocking retries and Dead Letter Queues (DLQs), and managing the lifecycle of Kafka Streams applications in an enterprise context.

## Syllabus & Modules

1. **[Module 01: Spring Consumers & Producers](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/12-spring-kafka/01-spring-listeners-producers.md)**
   * Understand Spring Boot auto-configuration for Kafka clients.
   * Build message-driven POJOs using `@KafkaListener` at method and class levels.
   * Send messages asynchronously using `KafkaTemplate` and handle send callbacks.
   * Scale consumers using concurrency levels and partition-per-thread matching.
2. **[Module 02: Dead Letter Topics & Non-Blocking Retries](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/12-spring-kafka/02-retries-dead-letter-topics.md)**
   * Design resilient error-handling strategies.
   * Differentiate between blocking retry policies and non-blocking retry topics.
   * Configure Dead Letter Topics (DLQs) using `@RetryableTopic` and `DefaultErrorHandler`.
3. **[Module 03: Spring Kafka Streams Lifecycle Management](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/12-spring-kafka/03-spring-kafka-streams-lifecycle.md)**
   * Wire and inject `StreamsBuilderFactoryBean` using `@EnableKafkaStreams`.
   * Configure the default configuration bean named `defaultKafkaStreamsConfig`.
   * Customize the underlying `KafkaStreams` instance using `KafkaStreamsCustomizer` and `StreamsBuilderFactoryBeanCustomizer`.
   * Implement a manual lifecycle manager using custom lifecycle wrappers (`@PostConstruct`, `@PreDestroy`).

## Course Prerequisites
* Completed **Course 4: High-Performance Kafka Clients** and **Course 6: Developing Streams**.
* Solid understanding of the Spring Boot framework (Dependency Injection, Beans, Configurations).
