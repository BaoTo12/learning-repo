# Module 02: Dead Letter Topics & Non-Blocking Retries

When processing streams of events, exceptions are inevitable. Deserialization errors, external service outages, and data validation failures can halt processing. A resilient streaming architecture must handle these failures without losing messages or blocking the processing pipeline.

This module covers blocking retries, non-blocking retry topics, and Dead Letter Topics (DLTs) using Spring Kafka's robust error-handling APIs.

---

## 1. Blocking vs. Non-Blocking Retries

```
[Blocking Retry]
Incoming Record -> [Failed!] -> [Retry 1] -> [Retry 2] -> [Blocked!] (Lag increases)

[Non-Blocking Retry]
Incoming Record -> [Failed!] -> Send to "input-topic-retry-0" -> Commit offset
                                      |
                              (Delay passes)
                                      v
                               Process retry -> [Failed!] -> Send to DLT -> Audit / Manual Triage
```

### A. Blocking Retries
* **Behavior**: The consumer thread pauses and continually retries processing the **same record** without committing its offset.
* **Pro**: Easy to configure. Guarantees message ordering because no subsequent records on that partition are processed until this record succeeds or fails.
* **Con**: If processing fails repeatedly, the consumer thread is blocked, **head-of-line blocking** occurs, and consumer lag increases across the entire partition.
* **Best Use**: Short-lived, transient exceptions (e.g., a database connection pool is temporarily full, retrying for 2 seconds).

### B. Non-Blocking Retries
* **Behavior**: If processing fails, the record is published to a **retry topic**, its offset in the main topic is committed, and the consumer thread immediately moves to the next record. A separate listener processes records from the retry topic after a configured backoff delay.
* **Pro**: Prevents head-of-line blocking. The consumer continues processing healthy records.
* **Con**: Out-of-order execution. Records that fail will be processed out of order relative to the rest of the stream.
* **Best Use**: Business logic failures, long-running downstream outages, or slow HTTP integrations.

---

## 2. Implementing Non-Blocking Retries with `@RetryableTopic`

Spring Kafka simplifies non-blocking retries using the `@RetryableTopic` annotation. When added to a `@KafkaListener`, Spring automatically creates the retry topics (e.g. `topic-retry-0`, `topic-retry-1`) and a Dead Letter Topic (`topic-dlt`).

```java
import org.springframework.kafka.annotation.DltHandler;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.annotation.RetryableTopic;
import org.springframework.kafka.retrytopic.DltStrategy;
import org.springframework.retry.annotation.Backoff;
import org.springframework.stereotype.Component;

@Component
public class ResilientLoanProcessor {

    @RetryableTopic(
        attempts = "3", // 1 initial attempt + 2 retries
        backoff = @Backoff(
            delay = 2000,      // Initial delay: 2 seconds
            multiplier = 2.0,   // Exponential multiplier
            maxDelay = 10000    // Cap delay at 10 seconds
        ),
        dltStrategy = DltStrategy.FAIL_ON_ERROR, // Send to DLT if all attempts fail
        include = {TemporaryOutageException.class} // Only retry on specific errors
    )
    @KafkaListener(topics = "loan-applications", groupId = "resilient-group")
    public void process(LoanApplication application) {
        if (isThirdPartyServiceDown()) {
            throw new TemporaryOutageException("Credit scoring API is down");
        }
        
        System.out.println("Successfully processed loan: " + application.getId());
    }

    // Callback method when the record fails all retries and land in the DLT
    @DltHandler
    public void handleDeadLetter(LoanApplication application, @Header(KafkaHeaders.RECEIVED_TOPIC) String topic) {
        System.err.printf("ALERT: Loan %s sent to DLT: %s. Requires manual audit!%n", 
            application.getId(), topic);
    }
}
```

---

## 3. Configuring programmatic Error Handlers

For general consumer error handling (including handling deserialization errors, which cannot be processed by `@RetryableTopic` because the payload cannot be parsed), configure a `DefaultErrorHandler` bean:

```java
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.FixedBackOff;

@Configuration
public class KafkaErrorHandlerConfig {

    @Bean
    public DefaultErrorHandler errorHandler(KafkaTemplate<Object, Object> template) {
        // 1. Configure the DLT recoverer (sends failed records to <original-topic>.DLT)
        DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(template);

        // 2. Define a BackOff policy (retry 3 times with a 1-second fixed interval)
        FixedBackOff backOff = new FixedBackOff(1000L, 3L);

        // 3. Create the handler
        DefaultErrorHandler errorHandler = new DefaultErrorHandler(recoverer, backOff);

        // 4. Configure specific exceptions to be classified as non-retryable (fail fast to DLT)
        errorHandler.addNotRetryableExceptions(
            org.apache.kafka.common.errors.SerializationException.class,
            org.springframework.kafka.support.serializer.DeserializationException.class
        );

        return errorHandler;
    }
}
```

---

## 4. Production Operational Warnings

### Infinite Loop Danger on Deserialization Errors
If a poison-pill message (a message with invalid JSON/Avro format) arrives, the default deserializer will throw a `SerializationException`. 
* **The Hazard**: If the error handler attempts to retry this record, it will fail infinitely because the payload bytes will never change.
* **The Mitigation**: Always add deserialization exceptions to the `notRetryableExceptions` list in your `DefaultErrorHandler`, or use Spring's `ErrorHandlingDeserializer` which catches deserialization exceptions and passes a wrapped error descriptor to the listener so it can be routed to the DLT immediately.

### Retries vs. Partition Limits
If a retry backoff is long (e.g. 5 minutes) and is executed *blocking* inside a standard consumer loop, the consumer may fail to poll the broker within the time limit defined by `max.poll.interval.ms`.
* **The Hazard**: The coordinator will assume the consumer is dead, kick it out of the group, and trigger a rebalance.
* **The Mitigation**: For delays longer than a few seconds, **always** prefer non-blocking retries (`@RetryableTopic`) over blocking retries.
