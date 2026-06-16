# Module 04 — Error Handling

In this module, we will explore error handling patterns in Spring Kafka. We will examine the internal mechanics of the modern `DefaultErrorHandler` and cover how it replaced legacy handlers like `SeekToCurrentErrorHandler`. We will study exception classification, dividing failures into fatal and recoverable categories. We will review the differences between fixed backoff and exponential backoff retry strategies. Finally, we will build custom recovery logic to route records to Dead Letter Queues (DLQs) when retries are exhausted. We will close with Socratic review questions, hands-on labs with complete Java code structures, and detailed configuration tables.

---

## 1. Academic Lecture: Error Handlers, Exception Classification & DLQs

### Basic Level: Handler Evolution, Modern Defaults & Fixed Retries

#### Why Error Handling is Needed in Consumers
When a consumer thread polls a batch of records from Kafka, the records are processed sequentially by your listener code. If record #3 throws a runtime exception (such as a database connection failure or null pointer exception), what happens?
* In raw Kafka, if you catch the exception and log it, the offset progresses, meaning record #3 is skipped and data loss occurs.
* If you do not catch the exception, the thread crashes, stopping consumption and freezing the pipeline.

Spring Kafka solves this by introducing global container error handlers.

#### The Evolution: From `SeekToCurrentErrorHandler` to `DefaultErrorHandler`
In older versions of Spring Kafka, developers had to manage multiple distinct error handler classes depending on the listener type (e.g., `SeekToCurrentErrorHandler` for record listeners, `ContainerAwareErrorHandler` for container errors).
In modern Spring Kafka (version 2.8+), these have been unified into a single, highly configurable class: **`DefaultErrorHandler`**.

##### How it Works Under the Hood
1. Your listener method throws an exception.
2. The `DefaultErrorHandler` intercepts the exception.
3. It performs a **Seek** operation on the consumer, resetting the offset index of the failing partition back to the offset of the failed record.
4. It pauses consumption of other partitions temporarily, sleeps for the duration of the configured backoff delay, and then invokes your listener again with the same record.
5. If the record succeeds on retry, consumption continues normally. If it fails repeatedly and exceeds the maximum retry limit, the handler delegates execution to a **Recoverer** (such as writing to a Dead Letter Queue) and moves to the next record.

---

### Intermediate Level: Exception Classification & Backoff Strategies

#### Exception Classification: Fatal vs. Recoverable
Not all exceptions should be retried. For example, if a record payload is corrupted and fails JSON deserialization, retrying 10 times will not change the result. Retrying in this case only wastes CPU cycles and clogs the pipeline.
Spring Kafka divides exceptions into two categories:

##### 1. Fatal Exceptions (Non-Retriable)
* **Definition**: Structural or logic errors that will fail regardless of how many times they are retried.
* **Examples**: `DeserializationException`, `MessageConversionException`, `MethodArgumentNotValidException`, `NullPointerException`.
* **Action**: Skip retries immediately. Forward the record to the Dead Letter Queue or log a critical error and move to the next message.

##### 2. Recoverable Exceptions (Retriable)
* **Definition**: Transient errors caused by external system states that are expected to resolve over time.
* **Examples**: `JDBCConnectionException`, `HttpClientErrorException` (due to rate limits), resource lock timeouts.
* **Action**: Apply retry loops with backoff delays.

#### Backoff Strategies
When retrying a recoverable exception, you should configure a delay to allow the downstream system time to recover:
* **Fixed Backoff**: Retries the failed record after a static, unchanging delay interval (e.g., wait exactly 2 seconds between every retry).
* **Exponential Backoff**: Dynamically increases the delay interval after each failure. For example, wait 1 second on the first failure, 2 seconds on the second, 4 seconds on the third, up to a maximum limit. This prevents overloading downstream databases during recovery phases.

---

### Advanced Level: Custom Record Recovery & Dead Letter Queues (DLQs)

#### Dead Letter Publishing Recoverer (DLQ)
When a record exceeds its maximum retry attempts, you must handle the failure without stopping the application. The standard pattern is to write the failed record to a **Dead Letter Queue (DLQ)** topic.
Spring Kafka provides the **`DeadLetterPublishingRecoverer`** to automate this:
1. It creates a new `ProducerRecord` using the failed record's key and value.
2. By default, it appends `.DLT` (Dead Letter Topic) to the original topic name.
3. It injects diagnostic headers into the record (including the exception message, the stack trace, the original topic, the original partition, and the offset where the failure occurred).
4. It publishes the record to the broker DLT topic using a `KafkaTemplate`.

```text
  [ Input Record ] ──► [ Process fails ] ──► [ Retry 3 times ] ──► [ Exhausted ] ──► [ DeadLetterPublishingRecoverer ] ──► [ topic.DLT ]
```

#### Custom Error Handler Registration
To activate custom error handling, you instantiate a `DefaultErrorHandler` bean and register it in your `ConcurrentKafkaListenerContainerFactory` bean:

```java
@Bean
public ConcurrentKafkaListenerContainerFactory<String, String> kafkaListenerContainerFactory(
        DefaultErrorHandler errorHandler) {
    var factory = new ConcurrentKafkaListenerContainerFactory<String, String>();
    factory.setCommonErrorHandler(errorHandler); // Register the handler
    return factory;
}
```

---

## 2. Theory & Production Best Practices

### Exception Classifications Comparison

| Exception Class | Category | Retries Attempted? | Production Action |
| :--- | :--- | :--- | :--- |
| `DeserializationException` | Fatal | No | Send to DLQ immediately; alert developers of schema mismatch. |
| `MethodArgumentTypeMismatch` | Fatal | No | Discard or route to invalid-payload store. |
| `SQLTransientConnectionException` | Recoverable | Yes | Apply exponential backoff; block consumer until DB recovers. |
| `SocketTimeoutException` | Recoverable | Yes | Retry with short backoff delay. |

### Backoff Strategies Comparison

| Backoff Type | Complexity | downstream Protection | Primary Use Case |
| :--- | :--- | :--- | :--- |
| **None** (Retry Immediately) | Low | None (causes connection storms) | Unit testing. |
| **Fixed Backoff** | Low | Low (static rate) | Simple microservices, predictable recovery. |
| **Exponential Backoff** | Medium | High (reduces rate over time) | Production APIs, database-connected systems. |
| **Custom Backoff** | High | Maximum | Complex workflows requiring dynamic SLA checks. |

---

## 3. Common Errors & Troubleshooting

### 1. Poison Pill causes Infinite Retry Loop
* **Symptom**: A single corrupted record stops all consumption on a partition. The consumer logs show the same offset being processed forever.
* **Root Cause**: A fatal exception (such as a parsing error) was not registered in the fatal exception map of the `DefaultErrorHandler`, causing the handler to retry the message indefinitely.
* **Fix**: Register the exception as fatal:
  ```java
  errorHandler.addNotRetryableExceptions(MyJsonParseException.class);
  ```

### 2. DLQ Write Fails, Crashing the Consumer
* **Symptom**: The error handler exhausts all retries, tries to write to the `.DLT` topic, but crashes.
* **Root Cause**: The `.DLT` topic does not exist on the broker, and broker auto-creation is disabled, or the `KafkaTemplate` used by the recoverer failed to send the record.
* **Fix**: Programmatically declare the `.DLT` topic using `NewTopic` beans, or configure the recoverer to log the failure if the broker is unreachable.

### 3. Commit Failed Exception during Long Retries
* **Symptom**: Exception logs show offset commit failures after a retry loop completes.
* **Root Cause**: The total time spent waiting during backoff delays exceeded the broker's `max.poll.interval.ms` limit.
* **Fix**: Ensure that the sum of all backoff delays (e.g., 3 retries $	imes$ 5 seconds = 15 seconds) is well below your `max.poll.interval.ms` value (default 300 seconds).

---

## 4. Socratic Review Questions

### Question 1
*How does `DefaultErrorHandler` reset the consumer offset to retry a failed message without affecting other partitions assigned to the same consumer thread?*
* **Answer**: The error handler calls the raw consumer's `.seek(TopicPartition, offset)` method. It specifies the exact `TopicPartition` and offset index of the failed record. While this resets the read cursor for that specific partition, the cursors for other partitions remain unchanged, allowing the consumer thread to resume processing correctly.

### Question 2
*Why is it critical to configure the `KafkaTemplate` used by `DeadLetterPublishingRecoverer` with a different transaction manager than the template used in your main business code?*
* **Answer**: If the main business template throws an exception, the current transaction is rolled back, aborting all writes. If the `DeadLetterPublishingRecoverer` uses the same transaction context, the write to the `.DLT` topic will also be rolled back, preventing the failed message from being saved. The recoverer must run in a separate transaction context or write without transaction wrappers.

### Question 3
*What is the difference between adding an exception to `addNotRetryableExceptions()` vs. catching the exception in the listener method?*
* **Answer**: Catching the exception in the listener method handles the error locally. The framework assumes processing completed successfully and commits the offset. Adding the exception to `addNotRetryableExceptions()` allows the exception to bubble up to the container. The `DefaultErrorHandler` intercepts it, bypasses retry loops, executes the recovery handler (like writing to the DLQ), and commits the offset safely.

### Question 4
*How can you calculate the maximum duration a consumer thread will block during an exponential backoff retry loop?*
* **Answer**: The duration is calculated using the initial interval, multiplier, and max attempts. For example, with an initial interval of 1 second, a multiplier of 2, and 4 max attempts, the delays will be 1s, 2s, and 4s. The total block duration is the sum of these delays (7 seconds).

### Question 5
*What happens to record offsets if a fatal deserialization exception occurs inside the Spring Kafka record converter layer before your listener method is invoked?*
* **Answer**: The record converter throws a `DeserializationException`. Since this exception occurs within the Spring container framework, it bubbles up to the `DefaultErrorHandler`. The handler classifies it as a fatal exception, skips retries, forwards the corrupted payload metadata to the DLQ, and commits the offset to move past the poison pill.

---

## 5. Hands-on Labs

### Lab 4.1 — Standard Retry Configuration

#### Scenario
We will configure a manual `DefaultErrorHandler` bean that applies a fixed backoff retry strategy. The handler will retry any recoverable exception 3 times with a 2-second delay between attempts.

#### Complete Configuration Java Code
Create the file [FixedRetryConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/FixedRetryConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.FixedBackOff;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;

@Configuration
public class FixedRetryConfig {
    private static final Logger log = LoggerFactory.getLogger(FixedRetryConfig.class);

    // 1. Define the DefaultErrorHandler bean with FixedBackOff
    @Bean
    public DefaultErrorHandler fixedBackoffErrorHandler() {
        log.info("Configuring DefaultErrorHandler with 3 attempts and 2-second fixed delay...");
        
        // Retry 3 times (1 initial attempt + 2 retries) with a 2000ms delay
        FixedBackOff backOff = new FixedBackOff(2000L, 2L);
        
        DefaultErrorHandler errorHandler = new DefaultErrorHandler(backOff);
        
        // 2. Classify IOException as a retriable exception
        errorHandler.addRetryableExceptions(IOException.class);
        
        return errorHandler;
    }

    // 3. Register the error handler in the container factory
    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, String> retryContainerFactory(
            ConsumerFactory<String, String> consumerFactory,
            DefaultErrorHandler fixedBackoffErrorHandler) {
        
        ConcurrentKafkaListenerContainerFactory<String, String> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory);
        factory.setCommonErrorHandler(fixedBackoffErrorHandler);
        return factory;
    }
}
```

---

### Lab 4.2 — Exponential Backoff

#### Scenario
We will configure a `DefaultErrorHandler` bean that applies an exponential backoff retry strategy. The delay will start at 1 second, double after each failure, and top out at a maximum delay of 10 seconds.

#### Complete Configuration Java Code
Create the file [ExponentialBackoffConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/ExponentialBackoffConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.ExponentialBackOff;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.SQLException;

@Configuration
public class ExponentialBackoffConfig {
    private static final Logger log = LoggerFactory.getLogger(ExponentialBackoffConfig.class);

    @Bean
    public DefaultErrorHandler exponentialErrorHandler() {
        log.info("Configuring DefaultErrorHandler with exponential backoff...");

        // Start at 1000ms, multiply by 2.0 after each failure, max delay of 10000ms
        ExponentialBackOff backOff = new ExponentialBackOff(1000L, 2.0);
        backOff.setMaxInterval(10000L);
        // Set maximum attempts (includes initial attempt)
        
        DefaultErrorHandler errorHandler = new DefaultErrorHandler(
            (record, exception) -> log.warn("Record recovery fallback triggered for Key: {}", record.key()), 
            backOff
        );

        // Add transient database connection exceptions as retriable
        errorHandler.addRetryableExceptions(SQLException.class);
        
        return errorHandler;
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, String> exponentialContainerFactory(
            ConsumerFactory<String, String> consumerFactory,
            DefaultErrorHandler exponentialErrorHandler) {
        
        ConcurrentKafkaListenerContainerFactory<String, String> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory);
        factory.setCommonErrorHandler(exponentialErrorHandler);
        return factory;
    }
}
```

---

### Lab 4.3 — Custom Dead Letter Recovery

#### Scenario
We will build a custom configuration class that initializes a `DeadLetterPublishingRecoverer` to publish failed records to a `.DLT` topic, and customize the destination topic routing logic.

#### Complete Configuration Java Code
Create the file [CustomRecoveryConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/CustomRecoveryConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.apache.kafka.common.TopicPartition;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.FixedBackOff;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Configuration
public class CustomRecoveryConfig {
    private static final Logger log = LoggerFactory.getLogger(CustomRecoveryConfig.class);

    private final KafkaTemplate<String, String> kafkaTemplate;

    public CustomRecoveryConfig(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    // 1. Define the DeadLetterPublishingRecoverer bean
    @Bean
    public DeadLetterPublishingRecoverer dltRecoverer() {
        log.info("Initializing DeadLetterPublishingRecoverer with custom routing...");
        
        return new DeadLetterPublishingRecoverer(kafkaTemplate,
            // Custom topic routing function: sends all failures to a centralized error topic
            (record, exception) -> {
                log.warn("Routing failed message from Topic: {} to centralized DLQ", record.topic());
                return new TopicPartition("central-errors-dlq", record.partition());
            });
    }

    // 2. Define the DefaultErrorHandler bean linking our recoverer
    @Bean
    public DefaultErrorHandler dltErrorHandler(DeadLetterPublishingRecoverer dltRecoverer) {
        log.info("Linking DLT recoverer to DefaultErrorHandler...");
        // Retry 2 times with a 1-second delay, then execute our recoverer
        FixedBackOff backOff = new FixedBackOff(1000L, 2L);
        return new DefaultErrorHandler(dltRecoverer, backOff);
    }

    // 3. Register the handler in the container factory
    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, String> dltContainerFactory(
            ConsumerFactory<String, String> consumerFactory,
            DefaultErrorHandler dltErrorHandler) {
        
        ConcurrentKafkaListenerContainerFactory<String, String> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory);
        factory.setCommonErrorHandler(dltErrorHandler);
        return factory;
    }
}
```

#### Step-by-Step Code Walkthrough
1. **`dltRecoverer()`**: We instantiate the `DeadLetterPublishingRecoverer` by passing our `KafkaTemplate`. Instead of using the default naming strategy (which appends `.DLT` to the original topic name), we supply a custom lambda expression that routes all failed messages from any input topic to a single, centralized error topic named `"central-errors-dlq"`.
2. **`dltErrorHandler()`**: We create the `DefaultErrorHandler` bean. We pass our custom `dltRecoverer` as the first argument, and configure a fixed backoff retry of 2 attempts.
3. **`dltContainerFactory()`**: We register the error handler in our listener container factory. If a listener method registered under this factory throws an unhandled exception, it retries twice and then publishes the record to the `"central-errors-dlq"` topic automatically.
