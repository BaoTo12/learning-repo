# Module 01 — Spring Kafka Architecture

In this module, we will explore the internal architecture of Spring Kafka. We will look at how Spring Boot auto-configuration operates under the hood, and how to take manual control of the configuration. We will study the `ProducerFactory` and `ConsumerFactory` classes, and how they manage resource lifecycles. We will review the threading model of `ConcurrentMessageListenerContainer` and the template mechanics of `KafkaTemplate`. Finally, we will cover topic management via `KafkaAdmin` and look at bean lifecycle phases. We will close with Socratic review questions, hands-on labs with complete Java code structures, and detailed configuration tables.

---

## 1. Academic Lecture: Auto-Configuration, Factory Chains & Listener Containers

### Basic Level: Spring Wrappers, Auto-Config & Factory Roles

#### Spring Kafka Internals vs. Raw Kafka Clients
In the raw Java client API, you must write manual poll loops, manage thread boundaries, handle serialization/deserialization explicitly, and construct connection client lifecycles manually.
**Spring Kafka** acts as a wrapper layer on top of the raw clients. It integrates the client API into the Spring ecosystem, providing:
* **Dependency Injection**: Injecting templates and listener containers directly into your service beans.
* **Declarative Listening**: Using annotations like `@KafkaListener` to map method handlers to Kafka topics.
* **Automatic Resource Management**: Automatically opening and closing socket connections when the Spring application context starts and stops.

#### Spring Boot Auto-Configuration
When you add the `spring-kafka` dependency to your Spring Boot project, the auto-configuration engine (`KafkaAutoConfiguration.class`) runs automatically at boot time:
1. It scans your `application.properties` or `application.yml` file for keys prefixed with `spring.kafka`.
2. It registers a default `ProducerFactory`, `ConsumerFactory`, and `KafkaTemplate` inside the Spring application context.
3. It initializes a default `ConcurrentKafkaListenerContainerFactory` to manage `@KafkaListener` annotations.

#### The Role of Factories: `ProducerFactory` and `ConsumerFactory`
Raw Kafka clients are not thread-safe. A `KafkaProducer` is thread-safe but costly to instantiate, while a `KafkaConsumer` is **not** thread-safe and must be confined to a single processing thread.
To manage this, Spring Kafka introduces factory interfaces:
* **`ProducerFactory<K, V>`**: A thread-safe factory that acts as a singleton cache. It creates and caches raw `KafkaProducer` instances. If multiple threads call the template to send messages, they reuse the cached producer instances, preventing connection storms.
* **`ConsumerFactory<K, V>`**: A factory responsible for spawning new raw `KafkaConsumer` instances whenever a listener container thread boots up.

---

### Intermediate Level: KafkaTemplate, Threading Containers & KafkaAdmin

#### `KafkaTemplate` Lifecycle and Thread Safety
The **`KafkaTemplate`** is the primary high-level wrapper used to publish messages to Kafka.
* **Thread Safety**: `KafkaTemplate` is fully thread-safe and can be injected as a singleton bean into multiple controllers or services.
* **Asynchronous Execution**: The `.send(...)` methods are non-blocking. They return a Java `CompletableFuture` (or `ListenableFuture` in older versions). You can register callbacks on this future to handle broker delivery confirmations or routing errors asynchronously:

```java
CompletableFuture<SendResult<String, String>> future = kafkaTemplate.send("my-topic", "key", "value");
future.whenComplete((result, ex) -> {
    if (ex == null) {
        log.info("Message sent successfully to offset: {}", result.getRecordMetadata().offset());
    } else {
        log.error("Failed to deliver message", ex);
    }
});
```

#### Listener Containers
A listener container is the engine that pulls records from Kafka and feeds them to your annotated methods. Spring Kafka provides two core container models:

##### 1. `KafkaMessageListenerContainer`
* **Threading**: Single-threaded container. It manages a single raw `KafkaConsumer` instance inside a single execution thread loop.
* **Limitations**: Can only consume from assigned partitions sequentially. Cannot scale processing parallel threads internally.

##### 2. `ConcurrentMessageListenerContainer`
* **Threading**: Multi-threaded container wrapper. It aggregates multiple `KafkaMessageListenerContainer` instances (called tasks or threads) in parallel.
* **Concurrency Scaling**: You set the `concurrency` property (e.g., `concurrency = 3`). Spring Kafka will automatically spin up 3 separate consumer thread tasks, allowing you to process records from 3 partitions simultaneously.

```text
  [ ConcurrentMessageListenerContainer (Concurrency: 3) ]
           ├──► [ Thread 1: KafkaMessageListenerContainer ] ──► Consumer 1 (Partition 0)
           ├──► [ Thread 2: KafkaMessageListenerContainer ] ──► Consumer 2 (Partition 1)
           └──► [ Thread 3: KafkaMessageListenerContainer ] ──► Consumer 3 (Partition 2)
```

#### Topic Management via `KafkaAdmin`
In production, you should not rely on the broker's auto-creation of topics (`auto.create.topics.enable=true`), as this creates topics with default partitions and replication factors that are not suitable for production workloads.
Spring Kafka provides **`KafkaAdmin`** to automate topic provisioning. When you register `KafkaAdmin` and declare `NewTopic` beans, the context automatically checks the broker at startup and creates the topics with your exact specifications if they do not exist:

```java
@Bean
public NewTopic myTopic() {
    return TopicBuilder.name("my-topic")
        .partitions(6)
        .replicas(3)
        .build();
}
```

---

### Advanced Level: Bean Lifecycle Hooks & Spring Kafka Thread Model

#### Bean Lifecycle Phases and Container Control
Listener containers implement Spring's `SmartLifecycle` interface. This controls exactly when the consumer poll loops start and stop:
* **Auto-Startup**: By default, containers start automatically when the Spring context finishes booting (`autoStartup = true`).
* **Startup Phase**: Containers are assigned a phase index (default `Integer.MAX_VALUE`). This ensures they boot up *after* other backend database connection pools and REST APIs are fully active.
* **Programmatic Control**: You can retrieve the `KafkaListenerEndpointRegistry` bean to start or stop specific listener containers programmatically in response to application health checks or maintenance states:

```java
@Autowired
private KafkaListenerEndpointRegistry registry;

public void stopConsumers() {
    registry.getListenerContainer("my-listener-id").stop();
}
```

#### The Spring Kafka Thread Model
Understanding the threading boundaries is critical for tuning performance:
1. **The Poll Loop**: For each concurrency unit, a dedicated thread executes a loop:
   ```java
   while (isRunning()) {
       ConsumerRecords<K, V> records = consumer.poll(pollTimeout);
       invokeListener(records);
       commitOffsets();
   }
   ```
2. **Listener Invocation**: By default, your listener method (e.g., `@KafkaListener`) is invoked on the **same thread** that called `consumer.poll()`.
3. **Blocking Pitfalls**: If your listener method performs blocking calls (such as query databases or calling slow external APIs), the poll loop stands still. If the processing duration exceeds the broker's `max.poll.interval.ms` threshold, the broker assumes the consumer is dead, kicks it out of the group, and triggers a rebalance.
4. **Resolution**: If processing is slow, scale up the container's concurrency, reduce `max.poll.records`, or hand off processing tasks to an internal worker thread pool (using Spring `@Async`).

---

## 2. Theory & Production Best Practices

### Auto-Configuration vs. Custom Manual Configuration

| Metric | Boot Auto-Configuration | Custom Manual Configuration |
| :--- | :--- | :--- |
| **Setup Speed** | Instant (just define properties) | Low (requires boilerplate beans) |
| **Multi-Broker Support** | Hard (requires prefix hacks) | Easy (register separate factories) |
| **Interceptor Registration** | Limited configuration hooks | Full programmatic flexibility |
| **Control Over Serialization**| Declarative values in configuration | Explicit instances registered in beans |

### Listener Container Models Comparison

| Metric | `KafkaMessageListenerContainer` | `ConcurrentMessageListenerContainer` |
| :--- | :--- | :--- |
| **Internal Consumers** | Exactly 1 | $N$ (where $N = concurrency$) |
| **Partition Scaling** | Manual instantiation per partition | Automatic task allocation |
| **Thread Management** | Simple single loop | Complex coordinator thread pool |
| **Use Case** | Single partition control, debug | Production high-throughput microservices |

---

## 3. Common Errors & Troubleshooting

### 1. `BeanCurrentlyInCreationException` (Circular Dependency)
* **Symptom**: Spring Boot application crashes during startup.
* **Root Cause**: You tried to autowire the `KafkaTemplate` inside a custom class that is also injected during the creation of the `ProducerFactory` or custom serializer.
* **Fix**: Separate your custom serializers and factories from your primary business service layer, or use lazy initialization (`@Lazy`).

### 2. Slow Processing Triggers Consumer Rebalance Loop
* **Symptom**: Broker log logs `CommitFailedException` and consumers repeatedly join and leave the group.
* **Root Cause**: The time spent processing records returned in a single `poll()` exceeded `max.poll.interval.ms` configuration limit.
* **Fix**: 
  * Increase `max.poll.interval.ms` in your consumer config.
  * Reduce the batch size by setting `spring.kafka.consumer.max-poll-records` to a lower value (e.g., 50 instead of 500).

### 3. Container Startup Freezes Muted by Unreachable Broker
* **Symptom**: Application hangs at startup without logging exceptions.
* **Root Cause**: `KafkaAdmin` tries to initialize connection pools and check topics at boot time, blocking the main thread if the broker is unreachable.
* **Fix**: Disable startup blocking or configure short timeout bounds:
  ```java
  kafkaAdmin.setFatalIfBrokerNotAvailable(false);
  ```

---

## 4. Socratic Review Questions

### Question 1
*Why is `KafkaTemplate` considered thread-safe, whereas the raw `KafkaProducer` requires care when used in concurrent architectures?*
* **Answer**: While raw `KafkaProducer` is technically thread-safe, managing transactional states and sharing physical TCP connections requires careful synchronization. `KafkaTemplate` wraps the producer factory logic, managing the synchronization and lifecycle of producer instances automatically. It handles thread-local transactions and future callback registration, allowing safe, concurrent access across multiple singleton beans.

### Question 2
*If you configure a `ConcurrentMessageListenerContainer` with `concurrency = 6` but the target topic only has 4 partitions, what happens to the remaining 2 threads?*
* **Answer**: The remaining 2 thread containers will boot up and create consumers, but since there are more threads than partitions, they will receive no partition assignments from the Kafka broker coordinator. They will sit idle in a poll loop, consuming CPU cycles without processing data, until a partition count upgrade or consumer failure occurs.

### Question 3
*What is the purpose of setting `kafkaAdmin.setFatalIfBrokerNotAvailable(true)` vs `false` in production Spring environments?*
* **Answer**: Setting it to `true` forces the application to fail startup immediately if the broker cluster cannot be reached. This is useful when the application cannot function without verifying database topics. Setting it to `false` allows the application to boot up and serve other non-Kafka endpoints, attempting to connect to the broker in the background once traffic resumes.

### Question 4
*How does Spring Kafka map the `@KafkaListener` method signatures to incoming consumer records under the hood?*
* **Answer**: Spring Kafka uses a message listener adapter (`MessagingMessageListenerAdapter`). When the container poll loop retrieves a `ConsumerRecord`, the adapter uses a converter class to map the record key, value, headers, and metadata to your method parameters, performing automatic conversion (such as JSON parsing) if matching argument types are detected.

### Question 5
*What is the thread relation between the `Consumer.poll()` execution thread and the database transaction thread when using Spring's `@Transactional` annotation with `@KafkaListener`?*
* **Answer**: By default, the transactional logic is bound to the same thread. Spring Kafka's listener container starts a transaction using a `KafkaTransactionManager` on the polling thread before invoking your listener method. The database operations execute on this same thread, committing only if the listener method completes successfully.

---

## 5. Hands-on Labs

### Lab 1.1 — Build Spring Boot Kafka project

#### Scenario
We will configure a Maven project structure with all necessary dependencies to support Spring Kafka, Schema Registry, and JSON processing.

#### Complete `pom.xml` Dependency Block
Create your Spring Boot project's [pom.xml](file:///c:/Users/Admin/Desktop/projects/learning-repo/pom.xml) or check that the dependencies block contains:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
        <relativePath/>
    </parent>

    <groupId>com.springkafka.course</groupId>
    <artifactId>spring-kafka-production</artifactId>
    <version>1.0.0-SNAPSHOT</version>

    <properties>
        <java.version>17</java.version>
    </properties>

    <dependencies>
        <!-- Spring Boot Starter Web for REST endpoints -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>

        <!-- Spring Kafka Core Dependency -->
        <dependency>
            <groupId>org.springframework.kafka</groupId>
            <artifactId>spring-kafka</artifactId>
        </dependency>

        <!-- Jackson for JSON Serialization -->
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
        </dependency>

        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

#### Step-by-Step Dependency Explanation

| Dependency | Purpose |
| :--- | :--- |
| `spring-boot-starter-parent` | Provides default build plugins and versions for all Spring Boot starter libraries. |
| `spring-kafka` | Imports the core Spring wrapper libraries for Kafka clients, templates, and listener containers. |
| `jackson-databind` | Integrates JSON processing support for mapping Java objects to/from topic records. |

---

### Lab 1.2 — Manual configuration without auto-config

#### Scenario
We will create a Spring `@Configuration` class that manually defines our Kafka factories and templates. This completely bypasses Spring Boot's auto-configuration, allowing us to specify custom thread naming, timeout parameters, and server details programmatically.

#### Complete Configuration Java Code
Create the file [ManualKafkaConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/ManualKafkaConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.NewTopic;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.TopicBuilder;
import org.springframework.kafka.core.KafkaAdmin;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;

@Configuration
public class ManualKafkaConfig {
    private static final Logger log = LoggerFactory.getLogger(ManualKafkaConfig.class);

    // 1. Manually configure the KafkaAdmin bean
    @Bean
    public KafkaAdmin kafkaAdmin() {
        log.info("Initializing manual KafkaAdmin configuration...");
        Map<String, Object> configs = new HashMap<>();
        configs.put(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        
        KafkaAdmin admin = new KafkaAdmin(configs);
        // Prevent application startup freeze if broker cluster is offline
        admin.setFatalIfBrokerNotAvailable(false);
        return admin;
    }

    // 2. Declare a topic using TopicBuilder
    @Bean
    public NewTopic transactionsTopic() {
        log.info("Registering topic definition bean for: payment-transactions");
        return TopicBuilder.name("payment-transactions")
                .partitions(6)
                .replicas(1) // Set to 1 for local development
                .build();
    }
}
```

#### Step-by-Step Code Walkthrough
1. **`@Configuration`**: Marks this class as a source of bean definitions for the Spring container context.
2. **`kafkaAdmin()`**: We create our own `KafkaAdmin` bean. We supply a configuration map specifying `bootstrap.servers`. By calling `.setFatalIfBrokerNotAvailable(false)`, we ensure that if local Kafka is down, our service still boots up successfully.
3. **`transactionsTopic()`**: We declare a `NewTopic` bean. The Spring runtime intercepts this, checks the brokers, and automatically runs topic creations with 6 partitions.

---

### Lab 1.3 — Custom ProducerFactory and KafkaTemplate configuration

#### Scenario
We will build a custom configuration class that initializes our own `ProducerFactory` and `KafkaTemplate` with customized batch size, compression types, and serialization rules.

#### Complete Configuration Java Code
Create the file [CustomProducerConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/CustomProducerConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;

@Configuration
public class CustomProducerConfig {
    private static final Logger log = LoggerFactory.getLogger(CustomProducerConfig.class);

    // 1. Define custom configurations map
    private Map<String, Object> producerConfigs() {
        Map<String, Object> props = new HashMap<>();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        
        // High-throughput and reliability settings
        props.put(ProducerConfig.ACKS_CONFIG, "all");
        props.put(ProducerConfig.LINGER_MS_CONFIG, 20); // Wait up to 20ms for batching
        props.put(ProducerConfig.BATCH_SIZE_CONFIG, 32768); // 32KB batch limit
        props.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "snappy");
        return props;
    }

    // 2. Create the custom ProducerFactory bean
    @Bean
    public ProducerFactory<String, String> customProducerFactory() {
        log.info("Creating custom ProducerFactory with high-throughput parameters...");
        return new DefaultKafkaProducerFactory<>(producerConfigs());
    }

    // 3. Instantiate the KafkaTemplate bean passing our custom factory
    @Bean
    public KafkaTemplate<String, String> customKafkaTemplate() {
        log.info("Instantiating custom KafkaTemplate wrapper...");
        return new KafkaTemplate<>(customProducerFactory());
    }
}
```

#### Step-by-Step Code Walkthrough
1. **`producerConfigs()`**: We construct our custom configuration map. We override default properties to optimize high throughput (using `snappy` compression, `32KB` batch sizes, and a `20ms` buffer linger delay) and durability (setting `acks=all`).
2. **`customProducerFactory()`**: We instantiate a `DefaultKafkaProducerFactory` wrapper passing our customized config map.
3. **`customKafkaTemplate()`**: We create a `KafkaTemplate` bean, injecting our custom factory. This template is now ready to be autowired into our business services.

#### Configuration Details
The following table explains what each line of the configuration properties does:

| Property Name | Value | Purpose |
| :--- | :--- | :--- |
| `ProducerConfig.BOOTSTRAP_SERVERS_CONFIG` | `"localhost:9092"` | Locates the Kafka cluster bootstrap brokers. |
| `ProducerConfig.ACKS_CONFIG` | `"all"` | Requires all replica brokers to acknowledge receipt before declaring write success, ensuring high data safety. |
| `ProducerConfig.LINGER_MS_CONFIG` | `20` | Holds back message delivery for up to 20ms to allow more records to group into a single network batch. |
| `ProducerConfig.BATCH_SIZE_CONFIG` | `32768` | Limits maximum network batch memory size to 32KB before flushing data immediately. |
| `ProducerConfig.COMPRESSION_TYPE_CONFIG` | `"snappy"` | Compresses transaction payloads using Snappy algorithm, reducing network and broker disk footprints. |

---

### Lab 1.4 — Custom ConsumerFactory and Container Factory configuration

#### Scenario
We will create a custom configuration class for our consumer flow. We will initialize a custom `ConsumerFactory` and configure a `ConcurrentKafkaListenerContainerFactory` to manage concurrency and thread boundaries manually.

#### Complete Configuration Java Code
Create the file [CustomConsumerConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/CustomConsumerConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.listener.ContainerProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;

@Configuration
public class CustomConsumerConfig {
    private static final Logger log = LoggerFactory.getLogger(CustomConsumerConfig.class);

    // 1. Define custom configurations map for consumers
    private Map<String, Object> consumerConfigs() {
        Map<String, Object> props = new HashMap<>();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "payment-processors-group");
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "latest");
        // Disable auto offset commits to enable manual control
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);
        props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 100); // Process maximum 100 records at a time
        return props;
    }

    // 2. Create the custom ConsumerFactory bean
    @Bean
    public ConsumerFactory<String, String> customConsumerFactory() {
        log.info("Configuring custom ConsumerFactory...");
        return new DefaultKafkaConsumerFactory<>(consumerConfigs());
    }

    // 3. Create the ConcurrentKafkaListenerContainerFactory bean
    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, String> customKafkaListenerContainerFactory() {
        log.info("Initializing ConcurrentKafkaListenerContainerFactory...");
        ConcurrentKafkaListenerContainerFactory<String, String> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        
        factory.setConsumerFactory(customConsumerFactory());
        // Set task thread concurrency limit
        factory.setConcurrency(3);
        
        // Configure manual acknowledgement mode
        factory.getContainerProperties().setAckMode(ContainerProperties.AckMode.MANUAL);
        
        return factory;
    }
}
```

#### Step-by-Step Code Walkthrough
1. **`consumerConfigs()`**: We construct our configurations. We disable auto commits (`enable.auto.commit = false`) and set batch sizes (`max.poll.records = 100`) to guarantee manual offset control.
2. **`customConsumerFactory()`**: We instantiate our `ConsumerFactory` passing the configuration map.
3. **`customKafkaListenerContainerFactory()`**: We create a `ConcurrentKafkaListenerContainerFactory` bean.
   * We attach our custom `ConsumerFactory` to it.
   * **`setConcurrency(3)`**: Tells the factory to spawn 3 container threads for each `@KafkaListener` registered under this factory name.
   * **`setAckMode(MANUAL)`**: Instructs Spring Kafka to wait for our code to call `.acknowledge()` explicitly before recording message completion offsets on the broker.

#### Configuration Details
The following table explains what each line of the configuration properties does:

| Property Name | Value | Purpose |
| :--- | :--- | :--- |
| `ConsumerConfig.GROUP_ID_CONFIG` | `"payment-processors-group"` | Defines the coordination group namespace for partitioning cluster workloads. |
| `ConsumerConfig.AUTO_OFFSET_RESET_CONFIG` | `"latest"` | Tells the consumer to read from the newest logs if no offset check history is found. |
| `ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG` | `false` | Disables automatic broker updates of offsets, shifting responsibility to our application code. |
| `ConsumerConfig.MAX_POLL_RECORDS_CONFIG` | `100` | Restricts the maximum number of rows returned in a single poll loop to prevent thread starvation. |
| `factory.setConcurrency(3)` | `3` | Instantiates three active concurrent thread loops to consume from separate topic partitions simultaneously. |
| `ContainerProperties.AckMode.MANUAL` | `MANUAL` | Requires the listener method handler to acknowledge message processing completion explicitly. |
