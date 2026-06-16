# Module 06 — Retry Topics

In this module, we will learn about non-blocking retries using Retry Topics in Spring Kafka. We will explore how non-blocking retries solve the partition head-of-line blocking issue. We will examine the `@RetryableTopic` annotation and study how retry chains work. Next, we will cover how Spring Kafka automatically creates these retry topics on the Kafka brokers. We will detail retry scheduling, container listener polling, and how transaction scopes are managed across retry hops. We will also look at theory, comparison metrics, common troubleshooting scenarios, Socratic review questions, and hands-on labs with complete, compilable Java configurations.

---

## 1. Academic Lecture: Non-Blocking Retries, @RetryableTopic & Topology Generation

### Basic Level: Blocking vs. Non-blocking Retries & @RetryableTopic

#### What is Blocking Retry?
In standard consumer error handling (like the `DefaultErrorHandler` we saw in Module 4), if a message fails to process, the consumer thread retries the message on the spot. While retrying, the consumer thread pauses the offset commit and continues reading the same failed message. 
* **The Problem**: This blocks the entire consumer partition. No other messages in that partition can be processed until this message succeeds or is sent to a Dead Letter Topic (DLT). This is known as **Head-of-Line (HoL) Blocking**.
* **Real-World Impact**: If you have a message that needs to retry for 30 minutes (e.g., due to a temporary database outage), the entire partition is stalled for 30 minutes. All other users whose messages are in the same partition will experience huge delays.

#### What is Non-blocking Retry?
Non-blocking retry solves this problem by moving failed messages to dedicated **Retry Topics** instead of pausing the partition.
1. The consumer reads a message from the main topic.
2. If processing fails, the message is sent to a retry topic (e.g., `main-topic-retry-0`) with a delay duration.
3. The consumer commits the offset of the main topic and immediately continues processing the next messages.
4. A separate consumer listener reads from `main-topic-retry-0` after the delay expires.
5. This pattern prevents a single failing message from blocking other healthy messages.

```text
               +-----------------------+
               |  Primary Main Topic   |
               +-----------+-----------+
                           |
                     (Error Occurs)
                           |
                           v
               +-----------+-----------+
               |   Retry Topic (0)     |  <-- Configured Delay
               +-----------+-----------+
                           |
                     (Error Occurs)
                           |
                           v
               +-----------+-----------+
               |   Retry Topic (1)     |  <-- Increased Delay
               +-----------+-----------+
                           |
                     (Error Occurs)
                           v
               +-----------------------+
               |   Dead Letter Topic   |
               +-----------------------+
```

#### Introducing `@RetryableTopic`
Spring Kafka provides the `@RetryableTopic` annotation to automate non-blocking retries. Simply by adding `@RetryableTopic` to your `@KafkaListener` method, Spring Kafka handles:
* Topic creation on the Kafka broker.
* Message routing from one retry topic to the next.
* Backoff delays and offset management.

---

### Intermediate Level: Retry Chains & Topology Generation

#### How Retry Chains Work
When you use `@RetryableTopic`, Spring Kafka sets up a chain of retry topics. Let's trace a message through a retry chain with `attempts = 3`:
1. **Primary Input**: The message arrives on the main topic `orders`.
2. **First Failure**: The listener throws an exception. Spring Kafka intercepts the failure and publishes the message to `orders-retry-0`. The consumer commits the offset on `orders`.
3. **Second Failure**: A consumer listening to `orders-retry-0` picks up the message after the configured delay. If it fails again, it publishes the message to `orders-retry-1` and commits the offset on `orders-retry-0`.
4. **Third Failure**: The listener on `orders-retry-1` picks up the message after the second delay. If it fails a third time, it has exhausted all attempts. It is then routed to the final Dead Letter Topic `orders-dlt`.

#### Retry Topology Generation
At startup, Spring Kafka scans for methods annotated with `@RetryableTopic`. It calculates the number of retry topics required based on the `attempts` attribute.
* **Auto-Provisioning**: Spring Kafka uses `KafkaAdmin` to automatically create these topics on the Kafka broker.
* **Naming Convention**: By default, it appends `-retry-N` (where N is the retry index) and `-dlt` to the original topic name.
* **Single vs Multi-Topic retry**: You can configure Spring Kafka to use a single retry topic for all retry attempts with a fixed delay, or multiple retry topics for exponential backoff delays.

---

### Advanced Level: Retry Scheduling & Transaction Scopes

#### How Retry Scheduling Works Without Blocking
How does a consumer listener wait for a specific delay (e.g., 10 seconds) on a retry topic without blocking other partitions?
* **Kafka's Poll Cycle**: A Kafka consumer must poll the broker regularly. If the consumer thread sleeps for 10 seconds to create a delay, Kafka might assume the consumer is dead and trigger a group rebalance.
* **Spring's Non-Blocking Backoff**: Instead of sleeping, the consumer continues to poll. When it receives a message from `orders-retry-0`, it checks the timestamp in the message header:
  * If the delay has **not expired**, the consumer pauses partition consumption for that specific topic and resumes it later, or it performs a short sleep if the delay is very small.
  * If the delay has **expired**, the message is processed immediately.
  * This ensures that polling is maintained, preventing unwanted consumer rebalances while enforcing accurate delay intervals.

#### Transactions and Commit Scopes in Retry Hops
When moving messages through the retry chain, transactions must be handled carefully:
* **Scope of a Hop**: Each hop in the retry chain (from `orders` to `orders-retry-0`) is a separate transaction context.
* **Commit Sequence**:
  1. The transaction on the primary topic consumer is rolled back or committed based on whether you want to retry.
  2. Spring Kafka publishes the message to the next retry topic as part of a new transaction.
  3. The consumer commits the offset of the primary topic message.
* **Broker Transactions**: If you use container-managed transactions (`ChainedKafkaTransactionManager`), the publish to the retry topic and the offset commit of the original message are grouped into a single atomic transaction. If the publish to `orders-retry-0` fails, the offset on `orders` is not committed, ensuring no message loss.

---

## 2. Theory & Production Best Practices

### Blocking vs. Non-Blocking (Retry Topics) Error Handling

| Feature | Blocking Retry (`DefaultErrorHandler`) | Non-Blocking Retry (`@RetryableTopic`) |
| :--- | :--- | :--- |
| **Partition Blocked?** | Yes. Head-of-line blocking occurs. | No. Failed messages are offloaded. |
| **Message Ordering** | Maintained. Messages are processed in strict offset order. | Broken. Failed messages are processed later, out of order. |
| **Broker Resource Usage** | Very low. No extra topics needed. | High. Multiplies topic counts and partition numbers. |
| **Use Case** | Transient, very short errors (e.g., brief database lock). | Longer, business-level failures (e.g., downstream API down). |
| **Database Load** | High. Constant retries block resources. | Low. Delayed retries spread the load. |

### Retry Backoff Types

| Backoff Type | Delay Pattern | Pros | Cons | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Fixed Backoff** | Constant delay (e.g., 5s, 5s, 5s) | Simple to configure and predict. | Can overload database if many messages fail. | Simple internal systems. |
| **Exponential** | Multiplied delay (e.g., 2s, 4s, 8s, 16s) | Gives downstream services time to recover. | Harder to debug timings. | Production APIs and databases. |
| **Fibonacci** | Fibonacci sequence (e.g., 1s, 2s, 3s, 5s, 8s) | More gradual delay increase. | Rare built-in support; complex math. | Advanced custom scheduler logic. |

---

## 3. Common Errors & Troubleshooting

### 1. Consumer Group Rebalances Caused by Long Backoffs
* **Symptom**: Consumer groups keep rebalancing, causing latency and double processing.
* **Root Cause**: The backoff delay between retries is longer than the consumer's `max.poll.interval.ms` configuration. The consumer halts polling to wait out the delay, causing the broker to think it is dead.
* **Fix**:
  * Keep backoff delays small, or use a single retry topic with custom scheduling.
  * Increase `max.poll.interval.ms` in your consumer configuration.

### 2. Message Ordering Broken due to Retry Hops
* **Symptom**: Out-of-order execution causes data corruption (e.g., an "Update Account" message fails and goes to retry, while a later "Delete Account" message succeeds first).
* **Root Cause**: Non-blocking retries route messages to separate topics. This breaks the strict partition key ordering guarantees of Kafka.
* **Fix**:
  * Do not use `@RetryableTopic` for ordering-sensitive pipelines. Use blocking retry (`DefaultErrorHandler`) instead.
  * Use a Saga pattern or check database timestamps before applying updates.

### 3. Transaction Rollbacks causing Infinite Redelivery
* **Symptom**: A message fails, but instead of routing to `retry-0`, it gets processed by the primary listener repeatedly.
* **Root Cause**: The exception thrown by the listener is caught by a transaction manager that rolls back the entire offset commit, overriding the non-blocking retry routing.
* **Fix**: Ensure that the transaction manager is configured to allow Spring Kafka's retry framework to handle exception routing before rolling back, or exclude retry topics from standard transaction rollbacks.

---

## 4. Socratic Review Questions

### Question 1
*How does Spring Kafka determine when a message in `orders-retry-0` is ready to be consumed?*
* **Answer**: Spring Kafka checks the timestamp header injected into the message when it was published to `orders-retry-0`. The listener container calculates the difference between the current time and that timestamp. If the delay has not elapsed, it pauses the partition consumption for a specific duration, allowing the broker poll cycle to continue without processing the record prematurely.

### Question 2
*Why is strict message ordering lost when using `@RetryableTopic`?*
* **Answer**: Because healthy messages behind the failed message in the partition continue to be processed on the primary topic, while the failed message is sent to a separate retry topic to be consumed later. The original sequence of events is therefore altered.

### Question 3
*What happens if a broker is offline when `@RetryableTopic` attempts to publish a failed message to the next retry topic?*
* **Answer**: The write to the retry topic fails, throwing a producer exception. Spring Kafka will fall back to blocking retry behavior for that record. It will keep polling and trying to write to the retry topic until the broker comes back online, preventing message loss.

### Question 4
*Can we use custom backoff multipliers with `@RetryableTopic`, and how does that affect the number of retry topics created?*
* **Answer**: Yes. When using a multiplier (e.g., exponential backoff), Spring Kafka creates a separate retry topic for *each* attempt because each attempt has a different delay duration (e.g., `retry-0` for 1s, `retry-1` for 2s, `retry-2` for 4s). If you use a fixed delay, Spring Kafka can be configured to use a single retry topic for all attempts.

### Question 5
*How can we prevent specific exceptions (like `IllegalArgumentException`) from triggering a retry topic flow?*
* **Answer**: You specify these exceptions as "fatal" or "exclude" in the `@RetryableTopic` annotation or in the configuration builder. When these exceptions are thrown, Spring Kafka will skip all retry topics and send the message directly to the DLT.

---

## 5. Hands-on Labs

### Lab 6.1 — Standard @RetryableTopic Setup

#### Scenario
We will create a standard `@RetryableTopic` configuration using the annotation on a listener. This setup will retry processing 3 times with a 2-second delay using suffix indexes before routing failures to the DLT.

#### Complete Configuration and Listener Java Code
Create the file [RetryTopicConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/RetryTopicConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.annotation.DltHandler;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.annotation.RetryableTopic;
import org.springframework.kafka.retrytopic.TopicSuffixingStrategy;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.retry.annotation.Backoff;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Configuration
public class RetryTopicConfig {
    private static final Logger log = LoggerFactory.getLogger(RetryTopicConfig.class);

    // 1. Configure non-blocking retries with annotation
    @RetryableTopic(
        attempts = "3",
        backoff = @Backoff(delay = 2000), // Fixed 2-second delay between attempts
        topicSuffixingStrategy = TopicSuffixingStrategy.SUFFIX_WITH_INDEX_VALUE
    )
    @KafkaListener(id = "orders-consumer-group", topics = "orders")
    public void consumeOrder(String orderJson) {
        log.info("Processing order message: {}", orderJson);
        
        // Simulate business rule failure
        if (orderJson.contains("POISON_PILL")) {
            log.error("Failed to process order. Throwing exception to trigger retry topic chain...");
            throw new RuntimeException("Simulated processing error for order");
        }
        
        log.info("Successfully processed order");
    }

    // 2. Define DLT Handler for the retryable topic
    @DltHandler
    public void handleOrdersDlt(String orderJson, @Header(KafkaHeaders.RECEIVED_TOPIC) String topic) {
        log.error("CRITICAL: Order reached DLT handler. Payload: {} | Source Topic: {}", orderJson, topic);
    }
}
```

---

### Lab 6.2 — Customized Backoff and Fatal Exception Configuration

#### Scenario
We will configure non-blocking retries programmatically using a `RetryTopicConfiguration` bean. We will configure an exponential backoff, exclude fatal runtime exceptions, and provide customized configuration properties.

#### Complete Configuration and Listener Java Code
Create the file [ProgrammaticRetryConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/ProgrammaticRetryConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.retrytopic.RetryTopicConfiguration;
import org.springframework.kafka.retrytopic.RetryTopicConfigurationBuilder;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;

@Configuration
public class ProgrammaticRetryConfig {
    private static final Logger log = LoggerFactory.getLogger(ProgrammaticRetryConfig.class);

    // 1. Programmatic configuration builder
    @Bean
    public RetryTopicConfiguration customRetryableTopic(KafkaTemplate<String, String> template) {
        log.info("Configuring programmatic RetryTopicConfiguration with custom backoff and classification...");
        
        return RetryTopicConfigurationBuilder
            .newInstance()
            .maxAttempts(4) // 4 attempts total (1 primary + 3 retries)
            .exponentialBackoff(1000, 2.0, 10000) // Initial 1s, multiplier 2.0, max 10s delay
            .notRetryOn(NullPointerException.class, IllegalArgumentException.class) // Fatal exceptions go straight to DLT
            .retryOn(IOException.class) // Recoverable exceptions
            .listenerFactory("kafkaListenerContainerFactory")
            .create(template);
    }

    // 2. Component listener that uses the programmatic configuration
    @Component
    public static class InventoryConsumer {
        @KafkaListener(id = "inventory-consumer-group", topics = "inventory-updates")
        public void consumeInventory(String message) {
            log.info("Consuming inventory update: {}", message);
            
            if (message.contains("NULL_POINTER")) {
                log.error("Null pointer simulated. Direct to DLT.");
                throw new NullPointerException("Simulated null value error");
            }
            
            if (message.contains("IO_ERROR")) {
                log.warn("IO connection issue simulated. Triggering exponential retry topic flow.");
                throw new RuntimeException(new IOException("Database timed out"));
            }
            
            log.info("Inventory update processed successfully.");
        }
    }
}
```

---

### Lab 6.3 — Custom DLT Routing within Retryable Topics

#### Scenario
We will create a programmatic configuration that customizes the `DeadLetterPublishingRecoverer` used by the retry topic framework. We will route failed messages to a custom DLT name and inject custom tracing headers during recovery hops.

#### Complete Configuration Java Code
Create the file [CustomDltRoutingConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/CustomDltRoutingConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.retrytopic.DeadLetterPublishingRecovererFactory;
import org.springframework.kafka.retrytopic.RetryTopicConfiguration;
import org.springframework.kafka.retrytopic.RetryTopicConfigurationBuilder;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.apache.kafka.common.TopicPartition;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;

@Configuration
public class CustomDltRoutingConfig {
    private static final Logger log = LoggerFactory.getLogger(CustomDltRoutingConfig.class);

    // 1. Override the DeadLetterPublishingRecovererFactory to customize DLT destination and headers
    @Bean
    public DeadLetterPublishingRecovererFactory customRetryTopicRecovererFactory(KafkaTemplate<?, ?> template) {
        log.info("Initializing custom DeadLetterPublishingRecovererFactory for retry infrastructure...");
        
        return new DeadLetterPublishingRecovererFactory(template) {
            @Override
            public DeadLetterPublishingRecoverer create() {
                DeadLetterPublishingRecoverer recoverer = super.create();
                
                // Customize headers function to inject tracking details during retry topic hops
                recoverer.setHeadersFunction((record, exception) -> {
                    var headers = DeadLetterPublishingRecoverer.defaultHeaders(record, exception);
                    headers.add("retry-source", "custom-factory-recoverer".getBytes(StandardCharsets.UTF_8));
                    return headers;
                });
                
                // Retain partition mapping boundary safety
                recoverer.setRetainPartitionBoundary(false);
                return recoverer;
            }
        };
    }

    // 2. Associate programmatic retry topic config with topic 'payments'
    @Bean
    public RetryTopicConfiguration paymentRetryConfig(KafkaTemplate<String, String> template) {
        log.info("Applying custom retry config with customized recoverer factory to 'payments' topic...");
        
        return RetryTopicConfigurationBuilder
            .newInstance()
            .maxAttempts(3)
            .fixedBackOff(3000L) // 3-second delay
            .dltRoutingRules(rules -> rules.dltPublishingMode(RetryTopicConfiguration.DltPublishingMode.ALWAYS))
            .create(template);
    }
}
```

---

### Step-by-Step Code Walkthrough & Parameter Configuration Tables

#### Step-by-Step Code Walkthrough

##### Lab 6.1 Walkthrough
1. **`@RetryableTopic`**: We annotate the listener method to enable non-blocking retries. We specify that we want to retry 3 times (`attempts = "3"`) and use a fixed backoff of 2 seconds.
2. **`TopicSuffixingStrategy.SUFFIX_WITH_INDEX_VALUE`**: Specifies that the generated retry topics should append `-retry-0`, `-retry-1`, etc.
3. **`@DltHandler`**: Indicates the method that will handle the message after all retry attempts are exhausted. The message key, value, and headers can be mapped directly as parameters.

##### Lab 6.2 Walkthrough
1. **`RetryTopicConfigurationBuilder`**: Programmatically defines retry topics. We set `maxAttempts(4)` and use an exponential backoff configuration starting at 1 second, doubling each time up to a maximum of 10 seconds.
2. **`notRetryOn` / `retryOn`**: Dynamically classifies exceptions. `NullPointerException` and `IllegalArgumentException` are marked as fatal and will bypass the retry chain.
3. **`InventoryConsumer`**: A normal Kafka listener that automatically inherits the programmatic retry settings for the configured topic names.

##### Lab 6.3 Walkthrough
1. **`DeadLetterPublishingRecovererFactory`**: We override the bean that creates the recovery publisher for the retry topics. This allows us to customize the recovery behavior, such as adding custom headers during each routing hop.
2. **`dltPublishingMode`**: Configure whether to publish to a DLT. Setting this to `ALWAYS` ensures a DLT is provisioned and used at the end of the retry chain.

---

### Configuration Parameter Tables

The tables below describe every configuration property, retry parameter, and annotation property used in the hands-on configurations.

#### `@RetryableTopic` Annotation Attributes

| Attribute Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `attempts` | `String` | `"3"` | The total number of delivery attempts including the initial delivery. Must be at least 1. |
| `backoff` | `@Backoff` | `@Backoff()` | Configures the backoff strategy (delay, multiplier, max delay) between retry attempts. |
| `topicSuffixingStrategy` | `TopicSuffixingStrategy` | `SUFFIX_WITH_INDEX_VALUE` | Determines whether to append the index value (`-retry-0`, `-retry-1`) or just use a single retry topic name. |
| `include` | `Class<? extends Throwable>[]` | `{}` | Exception classes that should trigger the retry topic flow. If empty, all exceptions trigger retries except those in `exclude`. |
| `exclude` | `Class<? extends Throwable>[]` | `{}` | Exception classes that are fatal and should immediately route to the DLT instead of retrying. |
| `dltStrategy` | `DltStrategy` | `ALWAYS_BUFFERS` | Determines if the DLT should be created and how failures are sent. Options include sending to DLT, skipping DLT, or running DLT handler methods. |

#### `@Backoff` Annotation Attributes

| Attribute Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `delay` | `long` | `1000` | The delay duration in milliseconds between retry attempts. |
| `multiplier` | `double` | `0.0` | The multiplier to apply to the delay to calculate the next delay duration (used for exponential backoffs). |
| `maxDelay` | `long` | `0` | The maximum delay limit in milliseconds. Useful to cap exponential backoffs. |

#### `RetryTopicConfigurationBuilder` Programmatic Methods

| Method Name | Return Type | Description |
| :--- | :--- | :--- |
| `newInstance()` | `RetryTopicConfigurationBuilder` | Creates a new instance of the builder with default configuration settings. |
| `maxAttempts(int attempts)` | `RetryTopicConfigurationBuilder` | Sets the total number of attempts (initial delivery + retries) for the configuration. |
| `fixedBackOff(long delay)` | `RetryTopicConfigurationBuilder` | Configures a fixed delay between all retry attempts. |
| `exponentialBackoff(...)` | `RetryTopicConfigurationBuilder` | Configures exponential backoff delay parameters (initial delay, multiplier, max delay limit). |
| `retryOn(Class<?>... exceptions)` | `RetryTopicConfigurationBuilder` | Adds exceptions that should trigger non-blocking retries. |
| `notRetryOn(Class<?>... exceptions)` | `RetryTopicConfigurationBuilder` | Marks exceptions as fatal, bypassing the retry chain. |
| `listenerFactory(String name)` | `RetryTopicConfigurationBuilder` | Specifies the listener factory bean name used to create the retry container listeners. |
| `create(KafkaTemplate<?,?> template)` | `RetryTopicConfiguration` | Compiles the builder configuration and registers the retry topics infrastructure. |
