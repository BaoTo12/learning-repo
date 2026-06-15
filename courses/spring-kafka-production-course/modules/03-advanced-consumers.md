# Module 03 — Advanced Consumers

In this module, we will explore advanced consumer patterns in Spring Kafka. We will look at the internal execution loop of `@KafkaListener` and compare single record listeners with batch consumers. We will study how concurrency and partition assignment work under the hood. Next, we will cover manual offset commits and the various Spring `AckMode` configurations. We will examine consumer rebalance listeners and see how to seek offsets programmatically using `ConsumerSeekAware`. Finally, we will cover runtime pause and resume controls. We will close with Socratic review questions, hands-on labs with complete Java code structures, and detailed configuration tables.

---

## 1. Academic Lecture: Listener Boundaries, Manual Commits & Seeking

### Basic Level: Listener Post-Processors, Record vs. Batch & Concurrency

#### `@KafkaListener` Internals
When your Spring Boot application boots, the container framework scans your beans using the **`KafkaListenerAnnotationBeanPostProcessor`**:
1. It identifies all methods annotated with `@KafkaListener`.
2. For each annotated method, it retrieves the configuration properties (such as topic name, group ID, and concurrency).
3. It registers a `MessageListenerContainer` bean inside the Spring context.
4. It wraps your method inside a message listener adapter (`MessagingMessageListenerAdapter`). This adapter executes your method via reflection when records arrive.

#### Record Listeners vs. Batch Listeners
Spring Kafka supports two processing models:
* **Record Listener** (Default): Invokes your annotated method once for each individual `ConsumerRecord` returned in a broker poll.
  ```java
  @KafkaListener(topics = "orders")
  public void listen(String message) {
      process(message);
  }
  ```
* **Batch Listener**: Invokes your method once per `poll()` loop, passing a `List` containing all records retrieved in that batch. This is highly efficient for high-throughput pipelines.
  ```java
  @KafkaListener(topics = "orders", batch = "true")
  public void listenBatch(List<String> messages) {
      processAll(messages);
  }
  ```

#### Consumer Concurrency and Partition Assignment
The `concurrency` property on the container factory controls the number of active consumer threads:
* If a topic has 6 partitions and your container has `concurrency = 3`, Spring Kafka spawns 3 threads. Each thread gets assigned exactly 2 partitions by the broker coordinator.
* If a thread dies, the broker detects the missing heartbeat and triggers a **Rebalance**, reassigning its partitions to the remaining active threads.

---

### Intermediate Level: Acknowledgements, AckMode & Rebalance Listeners

#### Manual Acknowledgement and AckMode
By default, Kafka automatically commits offsets at fixed intervals (`enable.auto.commit = true`). In production, this can lead to data loss: if a consumer polls a batch, auto-commits the offset, and then crashes before processing the records, those messages are lost.
To prevent this, disable auto-commits and use Spring's manual **`AckMode`** options:
* **`MANUAL`**: The framework buffers your offset acknowledgements. It commits them to the broker when the current batch of records returned by `poll()` is completely processed.
* **`MANUAL_IMMEDIATE`**: The framework sends the commit request to the broker immediately when your code calls `.acknowledge()`, without waiting for the rest of the batch to finish.

To call acknowledgements manually, inject the `Acknowledgment` helper into your listener method:

```java
@KafkaListener(topics = "orders")
public void listen(String message, Acknowledgment ack) {
    process(message);
    ack.acknowledge(); // Commits offset manually
}
```

#### Consumer Rebalance Listeners
During group rebalances, partition ownership shifts. If you maintain local memory maps or databases associated with partitions, you must clear them when partitions are revoked.
Spring Kafka allows you to register a custom `ConsumerAwareRebalanceListener`:
* **`onPartitionsRevoked`**: Triggered before the broker takes away your partition assignments. Use this to commit pending offsets or flush memory caches.
* **`onPartitionsAssigned`**: Triggered when new partitions are allocated. Use this to initialize local databases or seek to specific offsets.

---

### Advanced Level: Programmatic Offset Seeking & Pause/Resume Control

#### Programmatic Offset Seeking via `ConsumerSeekAware`
In standard consumers, reading starts at the earliest or latest offset. However, sometimes you need to reprocess historical logs (such as replaying transactions from yesterday to fix a bug).
Spring Kafka provides the **`ConsumerSeekAware`** interface. By implementing this interface in your listener class, you gain access to offset control methods:
* **`seekToBeginning(TopicPartition)`**: Resets consumption to offset 0.
* **`seekToEnd(TopicPartition)`**: Resets consumption to the newest records.
* **`seekToTimestamp(TopicPartition, long timestamp)`**: Resets consumption to the first offset recorded after a specific epoch timestamp.

```java
public class MySeeker implements ConsumerSeekAware {
    private final ThreadLocal<ConsumerSeekCallback> callbacks = new ThreadLocal<>();

    @Override
    public void registerSeekCallback(ConsumerSeekCallback callback) {
        this.callbacks.set(callback);
    }

    public void replayFromStart(String topic, int partition) {
        callbacks.get().seekToBeginning(topic, partition);
    }
}
```

#### Pausing and Resuming Consumers
If a downstream dependency (such as a remote SQL database or payment gateway API) goes offline, continuing to consume messages will overload your error queues or trigger transaction rollbacks.
To prevent this, you can pause consumer poll loops at runtime:
1. Retrieve the container from the `KafkaListenerEndpointRegistry`.
2. Call `container.pause()`. The consumer will continue to send broker heartbeats to avoid group rebalances, but it stops polling new records.
3. Once the database recovers, call `container.resume()` to resume normal message consumption.

---

## 2. Theory & Production Best Practices

### Record vs. Batch Listeners Comparison

| Feature | Record Listener | Batch Listener |
| :--- | :--- | :--- |
| **Method Invocation** | Once per record | Once per batch pool |
| **Throughput** | Low to Medium | Extremely High (reduced JVM overhead) |
| **Memory Footprint** | Low (single instance in heap) | High (list of records in heap) |
| **Exception Handling** | Simple (fails single record) | Complex (failed batch aborts all) |
| **Commit Control** | Points lookup | Bulk commits |

### Spring Kafka AckMode Options

| AckMode | When Offset is Committed | Best Used For |
| :--- | :--- | :--- |
| **RECORD** | After each record is processed by the listener. | Standard low-volume queues. |
| **BATCH** | When all records returned in the `poll()` are processed. | Default auto-commit replacement. |
| **MANUAL** | Buffered; committed when the batch completes. | Manual control with safety. |
| **MANUAL_IMMEDIATE**| Immediately when `ack.acknowledge()` is called. | Strict data consistency requirements. |

---

## 3. Common Errors & Troubleshooting

### 1. `CommitFailedException` during Rebalance
* **Symptom**: Consumer logs exceptions stating offsets could not be committed because partition ownership changed.
* **Root Cause**: The time spent processing a batch exceeded `max.poll.interval.ms`. The coordinator broker assumed the consumer died, triggered a rebalance, and rejected the late commit request.
* **Fix**: Reduce batch sizes, scale concurrency, or perform manual commits inside `onPartitionsRevoked`.

### 2. Seek Actions Fail silently
* **Symptom**: Calling `seek` does not change the offset index, and no error is logged.
* **Root Cause**: You called `seek` before the partition was fully assigned to the consumer task thread, or called it on a separate thread without saving callbacks in a `ThreadLocal` wrapper.
* **Fix**: Only invoke seek callback operations inside or after the `onPartitionsAssigned` lifecycle callback.

### 3. OutOfMemory (OOM) inside Batch Listeners
* **Symptom**: The JVM crashes with heap space exhaustion under heavy consumer load.
* **Root Cause**: The batch size config `max.poll.records` is too high, and the list of records returned by the broker exceeds the JVM memory limits.
* **Fix**: Restrict batch allocation sizes in properties:
  ```properties
  spring.kafka.consumer.max-poll-records=100
  ```

---

## 4. Socratic Review Questions

### Question 1
*What is the critical difference between Spring's `AckMode.MANUAL` and `AckMode.MANUAL_IMMEDIATE`?*
* **Answer**: In `AckMode.MANUAL`, when you call `ack.acknowledge()`, Spring does not send a network request to the broker immediately. Instead, it buffers the offset index in memory. The actual commit happens on the consumer thread once all records returned by the last `poll()` have been processed. In `AckMode.MANUAL_IMMEDIATE`, calling `ack.acknowledge()` triggers an immediate blocking network commit request to the broker, ensuring synchronization at the cost of higher latency.

### Question 2
*Why does pausing a container using `container.pause()` prevent partition rebalances, whereas stopping it with `container.stop()` triggers a rebalance?*
* **Answer**: `container.stop()` closes the underlying consumer. The broker immediately detects the connection loss and reassigns its partitions. `container.pause()` keeps the consumer open and running. The consumer continue to send background heartbeats to the broker coordinator, which prevents rebalances. However, it pauses the polling of new records, stopping incoming message processing safely.

### Question 3
*How does `ConsumerSeekAware` handle multi-threaded concurrency if a listener class is a Spring singleton bean?*
* **Answer**: Because a singleton bean has only one instance shared across all thread containers, injecting a single `ConsumerSeekCallback` instance would cause race conditions. `ConsumerSeekAware` provides thread-local callbacks. You must store these callbacks in a `ThreadLocal` map keyed by thread ID or `TopicPartition` to execute seek actions safely on the correct consumer task thread.

### Question 4
*What happens if an exception is thrown inside a Batch Listener containing 100 records?*
* **Answer**: By default, if the batch listener throws an exception, the entire batch fails. The offsets for all 100 records are not committed, and the consumer will poll the identical 100 records again in the next loop, potentially creating an infinite crash loop. You must catch exceptions manually inside the batch loop, or register a custom `BatchErrorHandler` to process failed rows.

### Question 5
*Why must `autoStartup` be set to `false` on a container if you intend to seek offsets to a specific timestamp during startup?*
* **Answer**: If `autoStartup` is true, the consumer immediately joins the group and starts polling from the default offset. If you want to force consumption from a specific timestamp, you must keep the container paused, set the seek target, and then start the container. This ensures it begins polling from the correct timestamp index.

---

## 5. Hands-on Labs

### Lab 3.1 — Batch Consumer with Manual Commit

#### Scenario
We will create a high-throughput batch consumer named `BatchManualCommitConsumer` that processes a list of transactions, writes them to a console log, and commits the batch offset manually.

#### Complete Consumer Java Code
Create the file [BatchManualCommitConsumer.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/consumer/BatchManualCommitConsumer.java) with the following content:

```java
package com.springkafka.course.consumer;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;

@Service
public class BatchManualCommitConsumer {
    private static final Logger log = LoggerFactory.getLogger(BatchManualCommitConsumer.class);

    // 1. Configure listener for batch consumption and attach custom factory bean
    @KafkaListener(
            id = "batch-consumer-id",
            topics = "payment-transactions",
            containerFactory = "customKafkaListenerContainerFactory"
    )
    public void consumeBatch(List<String> messages, Acknowledgment ack) {
        log.info("Received transaction batch. Batch size: {}", messages.size());

        try {
            // 2. Loop and process the transaction records
            for (String message : messages) {
                log.info("Processing transaction record: {}", message);
            }
            
            // 3. Commit offsets manual once processing is complete
            ack.acknowledge();
            log.info("Batch offset committed successfully.");
            
        } catch (Exception e) {
            log.error("Failed to process transaction batch", e);
            // Abort commit. The batch will be re-delivered on next poll
        }
    }
}
```

---

### Lab 3.2 — Custom Rebalance Listener

#### Scenario
We will create a custom consumer configuration class that registers a `ConsumerAwareRebalanceListener` to log partition assignments and revocation events.

#### Complete Configuration Java Code
Create the file [CustomRebalanceListener.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/consumer/CustomRebalanceListener.java) with the following content:

```java
package com.springkafka.course.consumer;

import org.apache.kafka.common.TopicPartition;
import org.springframework.kafka.listener.ConsumerAwareRebalanceListener;
import org.apache.kafka.clients.consumer.Consumer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.Collection;

@Component
public class CustomRebalanceListener implements ConsumerAwareRebalanceListener {
    private static final Logger log = LoggerFactory.getLogger(CustomRebalanceListener.class);

    @Override
    public void onPartitionsRevokedBeforeCommit(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.info("Rebalance triggered! Revoking partitions before commit: {}", partitions);
    }

    @Override
    public void onPartitionsRevokedAfterCommit(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.info("Partitions revoked and committed: {}", partitions);
    }

    @Override
    public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.info("New partition assignments completed: {}", partitions);
        for (TopicPartition partition : partitions) {
            log.info("Consumer Thread: {} is now processing Partition: {}", 
                     Thread.currentThread().getName(), partition.partition());
        }
    }
}
```

---

### Lab 3.3 — Pause and Resume Consumers at Runtime

#### Scenario
We will build a REST Controller named `ConsumerPauseResumeController` that uses Spring's `KafkaListenerEndpointRegistry` to pause and resume message consumption programmatically.

#### Complete Controller Java Code
Create the file [ConsumerPauseResumeController.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/controller/ConsumerPauseResumeController.java) with the following content:

```java
package com.springkafka.course.controller;

import org.springframework.kafka.config.KafkaListenerEndpointRegistry;
import org.springframework.kafka.listener.MessageListenerContainer;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@RestController
@RequestMapping("/api/consumers")
public class ConsumerPauseResumeController {
    private static final Logger log = LoggerFactory.getLogger(ConsumerPauseResumeController.class);

    private final KafkaListenerEndpointRegistry registry;

    public ConsumerPauseResumeController(KafkaListenerEndpointRegistry registry) {
        this.registry = registry;
    }

    @PostMapping("/pause")
    public String pauseConsumer() {
        log.info("REST request received to pause batch consumer...");
        
        // 1. Retrieve the container using its listener ID
        MessageListenerContainer container = registry.getListenerContainer("batch-consumer-id");
        
        if (container != null) {
            // 2. Pause consumption
            container.pause();
            log.info("Batch consumer container paused successfully.");
            return "Consumer paused.";
        }
        return "Container not found.";
    }

    @PostMapping("/resume")
    public String resumeConsumer() {
        log.info("REST request received to resume batch consumer...");
        
        MessageListenerContainer container = registry.getListenerContainer("batch-consumer-id");
        
        if (container != null) {
            // 3. Resume consumption
            container.resume();
            log.info("Batch consumer container resumed successfully.");
            return "Consumer resumed.";
        }
        return "Container not found.";
    }
}
```

---

### Lab 3.4 — Replay Messages using ConsumerSeekAware

#### Scenario
We will create a service class named `MessageReplayService` that implements `ConsumerSeekAware`. It will save seek callbacks in a thread-local variable and expose a method to reset the consumer's offset back to the beginning of a partition, allowing us to replay historical messages.

#### Complete Service Java Code
Create the file [MessageReplayService.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/consumer/MessageReplayService.java) with the following content:

```java
package com.springkafka.course.consumer;

import org.apache.kafka.common.TopicPartition;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.listener.ConsumerSeekAware;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class MessageReplayService implements ConsumerSeekAware {
    private static final Logger log = LoggerFactory.getLogger(MessageReplayService.class);

    // Thread-safe map to store seek callbacks for each assigned partition
    private final Map<TopicPartition, ConsumerSeekCallback> callbacks = new ConcurrentHashMap<>();

    @Override
    public void registerSeekCallback(ConsumerSeekCallback callback) {
        // Not used in partition-specific seek implementations
    }

    @Override
    public void onPartitionsAssigned(Map<TopicPartition, ConsumerSeekCallback> callbacks, ConsumerSeekCallback initialCallbacks) {
        log.info("Saving seek callbacks for assigned partitions...");
        // Save the callback objects for each partition
        this.callbacks.putAll(callbacks);
    }

    @Override
    public void onIdleContainer(Map<TopicPartition, ConsumerSeekCallback> callbacks, ConsumerSeekCallback initialCallbacks) {
        // Not used
    }

    // Programmatic method to reset offsets to the beginning
    public void replayFromBeginning(String topic, int partition) {
        TopicPartition topicPartition = new TopicPartition(topic, partition);
        ConsumerSeekCallback callback = callbacks.get(topicPartition);

        if (callback != null) {
            log.info("Executing seek target -> Resetting topic: {} | partition: {} to beginning.", topic, partition);
            // 1. Reset consumer offset index
            callback.seekToBeginning(topic, partition);
        } else {
            log.warn("Seek callback not found for TopicPartition: {}", topicPartition);
        }
    }

    @KafkaListener(id = "replay-listener-id", topics = "payment-transactions")
    public void listen(String message) {
        log.info("Replay Listener received record -> Content: {}", message);
    }
}
```
