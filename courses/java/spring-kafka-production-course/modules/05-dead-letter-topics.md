# Module 05 — Dead Letter Topics

In this module, we will explore Dead Letter Topics (DLTs) in Spring Kafka. We will cover the core design of DLT architectures, including how to isolate poison messages. We will study DLT naming strategies and look at the metadata headers injected by `DeadLetterPublishingRecoverer`. Next, we will discuss replay architectures to safely reprocess failed messages after bugs are resolved. Finally, we will cover DLT monitoring and alerting. We will close with Socratic review questions, hands-on labs with complete Java code structures, and detailed configuration tables.

---

## 1. Academic Lecture: DLT Designs, Naming Strategies & Replay Systems

### Basic Level: Poison Pill Isolation, Naming Patterns & Centralization

#### What is a Dead Letter Topic (DLT)?
In stream processing, some records cannot be processed regardless of retry counts.
* **Poison Message (Poison Pill)**: A record that contains corrupt bytes, invalid JSON structures, or values that violate database constraints.
* **The Problem**: If a consumer thread encounters a poison message, standard retries fail. If you block the thread, the partition stalls. If you commit and skip it, the data is lost.
* **The Solution**: Use a **Dead Letter Topic (DLT)**. When all retries fail, the container writes the message to a DLT topic and commits the original offset, isolating the poison pill and keeping the main pipeline active.

#### Naming Strategies
When designing your DLT structure on the Kafka broker, you must choose a naming convention:
* **Dedicated Suffix Naming** (Default): Every input topic gets a dedicated DLT topic (e.g., `payment-transactions` gets `payment-transactions.DLT` or `payment-transactions-dlt`).
  * *Pros*: Isolate errors by domain; consumers of the DLT only deal with one schema.
  * *Cons*: Topic counts double, increasing broker management overhead.
* **Centralized Shared DLT**: A single, shared topic is used to collect failures from all microservices (e.g., `global-errors-dlt`).
  * *Pros*: Easy to monitor; simple topic management.
  * *Cons*: The topic contains multiple schemas, making automated replays difficult.

---

### Intermediate Level: Metadata Headers & Monitoring

#### DLT Metadata Headers
When `DeadLetterPublishingRecoverer` writes a failed record to a DLT, it does not just copy the payload. It automatically injects useful diagnostic **Headers** to help developers troubleshoot the issue:
* **`KafkaHeaders.DLT_EXCEPTION_MESSAGE`**: The string representation of the exception message.
* **`KafkaHeaders.DLT_EXCEPTION_STACKTRACE`**: The full Java stack trace.
* **`KafkaHeaders.DLT_ORIGINAL_TOPIC`**: The topic name where the error occurred.
* **`KafkaHeaders.DLT_ORIGINAL_PARTITION`**: The partition index of the failed message.
* **`KafkaHeaders.DLT_ORIGINAL_OFFSET`**: The offset index of the failed message.

By reading these headers, monitoring tools can group errors by exception type or pinpoint exactly where the transaction failed.

#### DLT Monitoring
A DLT should not be a "data graveyard." If messages enter a DLT, it means your microservice is failing. You must monitor DLTs using these metrics:
* **Consumer Lag**: Check if the DLT itself has an increasing lag, indicating that failures are happening faster than they can be logged or analyzed.
* **Failure Frequencies**: Monitor the rate of incoming messages on `.DLT` topics. If a sudden spike occurs, trigger alerts (such as Slack notifications or PagerDuty pages).

---

### Advanced Level: Replay Architectures & Poison Pill Recovery

#### Replay Architectures
Once a developer identifies a bug, fixes the code, and redeploys the microservice, how do you process the messages that were sent to the DLT during the outage?
You need a **Replay Architecture** to route records from the DLT back into the main input stream.

```text
  [ DLT Topic ] ──► [ Replay Consumer ] ──► (Fix/Adjust Payload) ──► Publish ──► [ Main Topic ]
```

##### Replay Patterns
1. **Manual API Trigger**: Expose a REST endpoint that programmatically spins up a consumer thread, pulls messages from the DLT, writes them back to the main topic, and stops the consumer once the DLT is empty.
2. **Automated Scheduled Replay (Chron)**: A scheduled task runs at night (e.g., 2 AM), reads from the DLT, checks if the downstream database is healthy, replays the messages, and pauses the consumer again.
3. **Poison Pill Filtration**: During replay, you must validate that you have fixed the bug. If a message fails again, make sure it is not sent back to the DLT in an infinite loop. Use retry limits or filter flags.

---

## 2. Theory & Production Best Practices

### Dedicated DLTs vs. Centralized Shared DLTs

| Feature | Dedicated Suffix (`topic.DLT`) | Centralized Shared (`global-dlt`) |
| :--- | :--- | :--- |
| **Topic Counts** | High (doubles topic footprint) | Low (exactly 1 topic) |
| **Schema Validation** | Easy (matching input schema) | Hard (mixed schemas in one topic) |
| **Alert Routing** | Easy (route by domain topic) | Complex (must parse headers to route) |
| **Replay Complexity** | Low (direct return to main) | High (requires content-based routing) |

### Replay Patterns Comparison

| Replay Pattern | Implementation Effort | Downstream Risk | Use Case |
| :--- | :--- | :--- | :--- |
| **Manual Script** | Low | Low (controlled execution) | Occasional errors, simple pipeline. |
| **Programmatic API REST** | Medium | Medium (could overload API) | Standard business operational replays. |
| **Scheduled Chron** | High | High (automated loop risk) | High-volume queues, self-healing setups. |

---

## 3. Common Errors & Troubleshooting

### 1. The Infinite Replay Loop (Tombstone Loop)
* **Symptom**: Messages loop between the main topic and the DLT forever, causing CPU spikes.
* **Root Cause**: You replayed a poison message from the DLT back to the main topic, but the underlying code bug was not fixed. The main topic consumer rejected it again, sending it back to the DLT.
* **Fix**:
  * Track replay counts in record headers (e.g., `replay-attempts`).
  * If the count exceeds 2, discard the message or route it to a secondary quarantine topic.

### 2. Tracing Context (traceparent) Lost during DLT Write
* **Symptom**: Distributed tracing charts (such as Jaeger or Zipkin) break when messages enter the DLT.
* **Root Cause**: The `DeadLetterPublishingRecoverer` copied the record headers but did not update or propagate the active parent tracing context span.
* **Fix**: Configure the recoverer's headers customization callback to inject the current tracing span ID into the DLT record headers.

### 3. DLT Topic Partition Count Mismatch
* **Symptom**: Publishing to DLT fails with `KafkaException: Partition does not exist`.
* **Root Cause**: The original topic has 12 partitions, but the automatically created `.DLT` topic was initialized with only 1 partition. The recoverer tried to preserve partition index (writing to partition 5 of the DLT), which does not exist.
* **Fix**: Set `retainPartitionBoundary = false` in your `DeadLetterPublishingRecoverer` configuration, or pre-create the DLT topics with matching partition counts.

---

## 4. Socratic Review Questions

### Question 1
*Why is it highly recommended to set `retainPartitionBoundary = false` in `DeadLetterPublishingRecoverer` when deploying to production clusters?*
* **Answer**: By default, the recoverer tries to write the failed record to the identical partition index on the DLT (e.g., if the failure occurred on partition 7 of the main topic, it writes to partition 7 of the DLT). If the DLT topic is created with fewer partitions than the main topic, this write will throw a `PartitionDoesNotExistsException` and crash the consumer. Setting `retainPartitionBoundary = false` allows the Kafka producer to calculate the target partition using standard key hashing, preventing crashes.

### Question 2
*How does Spring Kafka prevent a message that fails DLT writing from causing a partition commit block?*
* **Answer**: If the DLT publishing fails (e.g., the broker is offline), the exception is thrown back to the container factory. The default error handler will catch this, pause the consumer thread, log a critical error, and retry the DLT write in the next poll loop. It will not commit the offset of the main topic until the DLT write succeeds or a fallback skip mechanism is executed, ensuring no message is lost.

### Question 3
*What headers should a custom consumer look for to determine why a message ended up in a `.DLT` topic?*
* **Answer**: The consumer should inspect the `KafkaHeaders.DLT_EXCEPTION_MESSAGE` (for the exception reason) and `KafkaHeaders.DLT_EXCEPTION_STACKTRACE` (for the full Java stack trace) headers. These are injected as byte arrays by the recoverer.

### Question 4
*What is the main risk of using a single centralized DLT topic to collect failures from 50 different microservices?*
* **Answer**: The main risk is schema deserialization complexity. Since 50 services write different JSON schemas to the same topic, building an automated replay engine is difficult because the engine cannot use a single specific Avro class or JSON parser. It must parse records as generic raw byte objects and route them based on the `x-original-topic` header, which increases coding effort and risk.

### Question 5
*How can you track the execution duration of transactions that went through a DLT?*
* **Answer**: You read the `x-original-timestamp` header injected by the recoverer (which shows when the record was originally published to Kafka) and compare it against the current system time when the replayed transaction successfully completes. The difference represents the total latency duration.

---

## 5. Hands-on Labs

### Lab 5.1 — DLT Implementation with Custom Naming and Headers

#### Scenario
We will configure a `DeadLetterPublishingRecoverer` that appends `-failures` instead of `.DLT` to the target topic name, and injects a custom trace header.

#### Complete Configuration Java Code
Create the file [DltNamingConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/DltNamingConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.apache.kafka.common.TopicPartition;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.FixedBackOff;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;

@Configuration
public class DltNamingConfig {
    private static final Logger log = LoggerFactory.getLogger(DltNamingConfig.class);

    // 1. Configure custom DeadLetterPublishingRecoverer
    @Bean
    public DeadLetterPublishingRecoverer customDltRecoverer(KafkaTemplate<String, String> template) {
        log.info("Configuring DeadLetterPublishingRecoverer with custom naming strategy...");
        
        DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(template,
            // Custom naming callback: appends "-failures" suffix to original topic name
            (record, exception) -> {
                String dltTopic = record.topic() + "-failures";
                log.warn("Failed record from Topic: {} will be routed to DLT: {}", record.topic(), dltTopic);
                return new TopicPartition(dltTopic, record.partition());
            });

        // 2. Set partition boundary retention to false to allow key hashing on the DLT
        recoverer.setRetainPartitionBoundary(false);

        // 3. Inject custom tracking headers during recovery
        recoverer.setHeadersFunction((record, exception) -> {
            var headers = DeadLetterPublishingRecoverer.defaultHeaders(record, exception);
            headers.add("recovered-by", "spring-dlt-framework".getBytes(StandardCharsets.UTF_8));
            return headers;
        });

        return recoverer;
    }

    // 4. Instantiate DefaultErrorHandler linking our custom recoverer
    @Bean
    public DefaultErrorHandler customDltErrorHandler(DeadLetterPublishingRecoverer customDltRecoverer) {
        log.info("Linking custom DLT recoverer to DefaultErrorHandler...");
        // Retry 3 times with a 1-second delay, then write to DLT
        return new DefaultErrorHandler(customDltRecoverer, new FixedBackOff(1000L, 2L));
    }
}
```

---

### Lab 5.2 — Programmatic DLT Replay Service and Controller

#### Scenario
We will create an administrative service class named `MessageReplayService` and a REST Controller named `DltReplayController` that allows administrators to programmatically consume failed messages from `payment-transactions-failures`, strip the error headers, and publish them back to the main topic.

#### Complete Replay Controller Java Code
Create the file [DltReplayController.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/controller/DltReplayController.java) with the following content:

```java
package com.springkafka.course.controller;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.Collections;

@RestController
@RequestMapping("/api/dlt")
public class DltReplayController {
    private static final Logger log = LoggerFactory.getLogger(DltReplayController.class);

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ConsumerFactory<String, String> consumerFactory;

    public DltReplayController(KafkaTemplate<String, String> kafkaTemplate, ConsumerFactory<String, String> consumerFactory) {
        this.kafkaTemplate = kafkaTemplate;
        this.consumerFactory = consumerFactory;
    }

    @PostMapping("/replay")
    public String replayMessages(@RequestParam String sourceDltTopic, @RequestParam String targetTopic) {
        log.info("Initiating manual DLT replay from topic: {} to target: {}", sourceDltTopic, targetTopic);

        // 1. Instantiate a temporary, dedicated consumer to pull from DLT
        try (Consumer<String, String> consumer = consumerFactory.createConsumer("replay-temp-group", "")) {
            consumer.subscribe(Collections.singletonList(sourceDltTopic));

            // Poll the DLT topic with a 5-second timeout
            ConsumerRecords<String, String> records = consumer.poll(Duration.ofSeconds(5));
            int replayedCount = 0;

            for (ConsumerRecord<String, String> record : records) {
                // 2. Build a clean ProducerRecord without the DLT exception headers
                ProducerRecord<String, String> replayRecord = new ProducerRecord<>(targetTopic, record.key(), record.value());
                
                // Copy original non-exception headers if present
                record.headers().forEach(header -> {
                    if (!header.key().startsWith("x-dlt-") && !header.key().startsWith("recovered-")) {
                        replayRecord.headers().add(header);
                    }
                });

                // 3. Publish back to the primary topic
                kafkaTemplate.send(replayRecord);
                replayedCount++;
            }

            // Commit offsets on DLT so we don't replay them again
            consumer.commitSync();
            log.info("Manual DLT replay completed. Replayed {} messages.", replayedCount);
            return String.format("Replay complete. Replayed %d records.", replayedCount);
        } catch (Exception e) {
            log.error("Failed to execute DLT replay loop", e);
            return "Replay failed: " + e.getMessage();
        }
    }
}
```

---

### Lab 5.3 — DLT Monitoring Service

#### Scenario
We will create a service class named `DltMonitorService` that consumes from the DLT topic, checks the exceptions, and logs metrics.

#### Complete Service Java Code
Create the file [DltMonitorService.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/consumer/DltMonitorService.java) with the following content:

```java
package com.springkafka.course.consumer;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;

@Service
public class DltMonitorService {
    private static final Logger log = LoggerFactory.getLogger(DltMonitorService.class);

    // 1. Register listener for the DLT topic
    @KafkaListener(id = "dlt-monitor-id", topics = "payment-transactions-failures")
    public void monitorDlt(ConsumerRecord<String, String> record) {
        log.warn("ALERT -> New failed transaction received in DLT!");
        
        // 2. Extract exception diagnostics from headers
        var reasonHeader = record.headers().lastHeader("x-dlt-exception-message");
        var originalTopicHeader = record.headers().lastHeader("x-dlt-original-topic");

        String reason = reasonHeader != null ? new String(reasonHeader.value(), StandardCharsets.UTF_8) : "Unknown reason";
        String originalTopic = originalTopicHeader != null ? new String(originalTopicHeader.value(), StandardCharsets.UTF_8) : "Unknown topic";

        // 3. Log metrics to console
        log.error("DLT Alert Details -> Failed Key: {} | Source Topic: {} | Reason: {}",
                record.key(), originalTopic, reason);
        
        // In a real-world system, you would export these metrics to Micrometer/Prometheus here
    }
}
```

#### Step-by-Step Code Walkthrough

##### Configuration Class Walkthrough
1. **`customDltRecoverer`**: We define a custom recoverer. We supply a naming function that routes failed messages to a topic suffixed with `-failures`.
2. **`setRetainPartitionBoundary(false)`**: We disable partition boundary retention. This ensures that if the destination `-failures` topic has fewer partitions than the original, the producer will hashing keys dynamically across available partitions instead of throwing errors.
3. **`setHeadersFunction`**: We append a custom header `"recovered-by"` to the default DLT headers during recovery.

##### Replay Controller Walkthrough
1. **`createConsumer`**: The controller instantiates a temporary consumer using the `ConsumerFactory`.
2. **`poll`**: We pull records from the `-failures` topic.
3. **`ProducerRecord` Construction**: For each failed record, we build a new `ProducerRecord` targeting the main topic. We loop through the original headers, copying them over while excluding DLT exception headers (`x-dlt-`) to keep the payload clean.
4. **`kafkaTemplate.send()`**: We publish the cleaned records back to the main topic. We then commit the DLT consumer offsets.

##### Monitoring Service Walkthrough
1. **`@KafkaListener`**: The monitor service listens continuously to the `payment-transactions-failures` topic.
2. **Header Parsing**: When a failed record is received, it extracts the `x-dlt-exception-message` and `x-dlt-original-topic` headers and logs the diagnostics to help developers troubleshoot the issue.
