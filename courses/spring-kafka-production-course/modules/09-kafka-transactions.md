# Module 09 — Kafka Transactions

In this module, we will explore transactions in Spring Kafka. We will cover Exactly Once Semantics (EOS) and discuss how the Kafka Transaction Coordinator coordinates commits across partitions. We will look at Read Committed isolation levels and how consumer offsets are updated. Finally, we will cover producer fencing (epochs) to block zombie processes, review common troubleshooting cases, answer 5 Socratic questions, and implement three hands-on transaction labs.

---

## 1. Academic Lecture: Exactly Once Semantics, Fencing & Broker Coordinators

### Basic Level: Exactly Once Semantics & Transaction Coordinators

#### The Exactly Once Semantics (EOS) Challenge
In typical messaging architectures, errors can cause duplication:
* **At-Least-Once** (Default): If a consumer processes a message but crashes before committing the offset, the new consumer reads the message again, causing duplicate processing.
* **Exactly-Once Semantics (EOS)**: Guarantees that even if brokers, producers, or consumers crash, message processing results (writes to database and outbound messages) are applied exactly once.

#### The Transaction Coordinator
To enable transactions, Kafka uses a **Transaction Coordinator** (a special broker thread) and a transaction log topic (`__transaction_state`):
1. **Initialize**: The producer registers its unique `transactional.id` with the coordinator.
2. **Register Hops**: When the producer starts a transaction and writes to partitions, the coordinator records these target partitions in the transaction state log.
3. **Commit/Abort**: When the producer calls commit, the coordinator writes a `COMMIT` marker to the transaction log, and then appends commit markers to all topic partitions involved in the transaction.

```text
  [ Producer ] ──(1. Begin Transaction)──► [ Transaction Coordinator ]
        │                                              │
   (2. Writes)                                   (3. Records State)
        │                                              │
        ▼                                              ▼
  [ Target Partitions ] ◄──(4. Appends Markers)─── [ __transaction_state ]
```

---

### Intermediate Level: Read Committed Isolation & Consumers

#### Consumer Isolation Levels
When transactions are enabled on producers, how do consumers read those messages? Kafka consumers define the `isolation.level` configuration:
* **`read_uncommitted`** (Default): The consumer immediately reads all messages as they are published, even if they are part of an uncommitted, ongoing transaction. If a transaction rolls back, the consumer will have read "dirty" data.
* **`read_committed`**: The consumer thread only returns messages from completed, committed transactions. Uncommitted messages or rolled-back messages are filtered out.

#### Last Stable Offset (LSO)
For `read_committed` consumers, Kafka tracks the **Last Stable Offset (LSO)**:
* LSO is the offset of the first active transaction that has not yet completed.
* The consumer cannot read past the LSO. If there is an active transaction at offset 100, the consumer cannot read offset 101, even if offset 101 is already committed, until the transaction at offset 100 commits or aborts.

---

### Advanced Level: Producer Fencing & Spring DB Synchronization

#### Zombie Producer Fencing
What happens if a network partition splits a producer instance from the cluster, causing a timeout?
1. The coordinator assumes the producer is dead and starts a new instance, assigning it the same `transactional.id`.
2. The old producer recovers and tries to commit its active transaction.
3. **Fencing**: The broker tracks a **Producer Epoch** (an incrementing number associated with the `transactional.id`). When the new instance registered, the coordinator bumped the epoch number. When the old instance tries to commit, the broker rejects it with a `ProducerFencedException`, preventing zombie writes from corrupting data.

#### Spring Database Transaction Synchronization
In enterprise applications, we must coordinate Kafka transactions with Database transactions (e.g., JPA/Hibernate):
* **Spring's `KafkaTransactionManager`**: Integrates Kafka transaction boundaries into Spring's platform transaction management.
* **Transaction Synchronization**: When a `@Transactional` listener method executes:
  1. The DB transaction manager begins a database transaction.
  2. The `KafkaTransactionManager` joins the transaction context and starts a Kafka transaction.
  3. If the listener executes successfully, both transactions are committed.
  4. If an exception occurs, both the DB writes and the Kafka message sends are rolled back, and the consumer offset commit is aborted.

---

## 2. Theory & Production Best Practices

### Isolation Levels Comparison

| Feature | read_uncommitted (Default) | read_committed |
| :--- | :--- | :--- |
| **Read Rolled-back Messages?** | Yes (dirty reads) | No (filtered out) |
| **LSO Blocking?** | No | Yes (reads pause if transaction is stuck) |
| **Latency** | Extremely Low | Medium (depends on transaction duration) |
| **Data Consistency** | Low | High |

### Transaction Scope Models

| Model | Spring Annotation | Java Programmatic API | Use Case |
| :--- | :--- | :--- | :--- |
| **Declarative Listener** | `@Transactional` | None | DB write + Kafka write synchronization. |
| **Programmatic Producer**| None | `KafkaTemplate.executeInTransaction` | Producing to multiple topics outside consumer. |
| **Local Chained** | `@Transactional(ChainedManager)`| None | Spring Boot 2.x legacy sync (deprecated). |

---

## 3. Common Errors & Troubleshooting

### 1. ProducerFencedException
* **Symptom**: Application logs show `org.apache.kafka.common.errors.ProducerFencedException`.
* **Root Cause**: Another instance of the producer was started with the identical `transactional.id`, causing the coordinator to bump the epoch and invalidate the current producer instance.
* **Fix**: Ensure that each running instance of your transactional microservice has a unique `transactional.id` prefix (e.g., appending hostname or pod ID), or use dynamic instance IDs.

### 2. Transaction Timeout Exceptions
* **Symptom**: Transactions are aborted with `TimeoutException: Transaction expired before commit completed`.
* **Root Cause**: The time between transaction initialization and commit exceeded the broker's `transaction.timeout.ms` limit (default is 60 seconds). This can happen if database processing inside the listener takes too long.
* **Fix**:
  * Keep transactions short. Do not call slow external APIs inside transactional methods.
  * Increase the timeout settings on both the broker and the producer configuration.

### 3. Consumer Offset Commits Stalled (LSO Blocked)
* **Symptom**: Consumer lag on `read_committed` groups spikes, and message consumption seems to halt.
* **Root Cause**: A transactional producer crashed mid-transaction, leaving an open transaction on the partition. The LSO is blocked, preventing downstream consumers from reading past it.
* **Fix**: The coordinator will automatically abort the stuck transaction after the timeout period. Set `transaction.max.timeout.ms` on brokers to cap this duration.

---

## 4. Socratic Review Questions

### Question 1
*How does a `read_committed` consumer filter out aborted transaction messages without contacting the Schema Registry or Coordinator?*
* **Answer**: It reads special control records called **markers** (Commit or Abort) that the transaction coordinator appends to the partition logs. The consumer reads the partition linearly but caches uncommitted messages in memory. When it encounters an Abort marker, it discards the cached messages. When it encounters a Commit marker, it returns them to the application.

### Question 2
*Why is it critical to define a unique `transactional.id` for each producer instance?*
* **Answer**: To enforce zombie producer fencing. If multiple instances share the same ID, they will continuously kick each other out of the cluster, causing epoch increments and throwing `ProducerFencedException` errors.

### Question 3
*What is the role of the `__transaction_state` topic?*
* **Answer**: It is an internal topic managed by the Transaction Coordinator. It acts as the write-ahead log for transaction states (e.g., Ongoing, Prepare Commit, Committed, Aborted) and stores metadata about partitions involved in each transaction ID.

### Question 4
*How does Spring Boot 3.x synchronize database transactions with Kafka transactions without using a deprecated ChainedTransactionManager?*
* **Answer**: Spring Boot 3.x uses standard transactional synchronization. It registers a `TransactionSynchronization` callback with the primary database transaction manager. When the DB transaction commits, the callback triggers the commit of the Kafka transaction. If the DB transaction fails, it aborts the Kafka transaction.

### Question 5
*What is the impact of a transaction rollback on consumer offsets?*
* **Answer**: The offset of the input message is not committed to the offset topic. The consumer container will re-read the same message in the next poll loop, allowing the application to retry processing.

---

## 5. Hands-on Labs

### Lab 9.1 — Transactional Producer Factory Configuration

#### Scenario
We will configure a transactional `ProducerFactory` and `KafkaTemplate` in Spring Boot. We will specify a `transactionIdPrefix` to enable transactional capabilities.

#### Application Properties (`application.yml`)
Add the following properties to activate transactional publishing:

```yaml
spring:
  kafka:
    bootstrap-servers: localhost:9092
    producer:
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.apache.kafka.common.serialization.StringSerializer
      # Enabling a transaction ID prefix activates transactional mechanics
      transaction-id-prefix: tx-prod-service-
      properties:
        # Guarantee durability for transactional writes
        acks: all
```

#### Complete Configuration Java Code
Create the file [KafkaTransactionConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/KafkaTransactionConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTransactionManager;
import org.springframework.kafka.core.ProducerFactory;

@Configuration
public class KafkaTransactionConfig {

    // 1. Define KafkaTransactionManager linked to the producer factory
    @Bean
    public KafkaTransactionManager<String, String> kafkaTransactionManager(
            ProducerFactory<String, String> producerFactory) {
        
        // Ensure the factory supports transactions (has transactional ID prefix set)
        if (producerFactory.transactionCapable()) {
            return new KafkaTransactionManager<>(producerFactory);
        }
        throw new IllegalStateException("ProducerFactory is not configured for transactions!");
    }
}
```

---

### Lab 9.2 — Transactional Listeners & Programmatic Execution

#### Scenario
We will write a consumer listener that uses `@Transactional` to coordinate a read-process-write pipeline, and a service that runs transactions programmatically.

#### Complete Listener and Service Java Code
Create the file [TransactionalService.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/service/TransactionalService.java) with the following content:

```java
package com.springkafka.course.service;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class TransactionalService {
    private static final Logger log = LoggerFactory.getLogger(TransactionalService.class);

    private final KafkaTemplate<String, String> kafkaTemplate;

    public TransactionalService(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    // 1. Declarative transaction inside consumer listener (read-process-write)
    @KafkaListener(id = "tx-process-group", topics = "input-orders")
    @Transactional("kafkaTransactionManager")
    public void listenAndProcess(String orderJson) {
        log.info("Starting transactional processing for input message: {}", orderJson);
        
        // Publish to outbound topics within same transaction boundary
        kafkaTemplate.send("billing-topic", "key", "Billing data for " + orderJson);
        kafkaTemplate.send("shipping-topic", "key", "Shipping details for " + orderJson);
        
        log.info("Transaction ready for commit.");
    }

    // 2. Programmatic transaction execution
    public void executeProgrammaticTransaction(String key, String value) {
        log.info("Executing programmatic transaction block...");
        
        kafkaTemplate.executeInTransaction(operations -> {
            operations.send("audit-topic", key, "Audit: " + value);
            operations.send("alerts-topic", key, "Alert: " + value);
            return true; // Commits automatically on return
        });
    }
}
```

---

### Lab 9.3 — Database & Kafka Rollback Synchronization

#### Scenario
We will simulate database writes and outbound Kafka events running in a unified transaction, demonstrating that a database write exception causes the outbound Kafka messages to roll back.

#### Complete Service Java Code
Create the file [DbKafkaSyncService.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/service/DbKafkaSyncService.java) with the following content:

```java
package com.springkafka.course.service;

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class DbKafkaSyncService {
    private static final Logger log = LoggerFactory.getLogger(DbKafkaSyncService.class);

    private final KafkaTemplate<String, String> kafkaTemplate;

    public DbKafkaSyncService(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    // 1. Transaction synchronized with database transaction manager
    @Transactional("transactionManager") // Primary Database transaction manager
    public void registerUserAndAlert(String userId, String username) {
        log.info("DB Transaction started. Registering user ID: {}", userId);
        
        // Simulate database write
        mockDatabaseInsert(userId, username);

        // Publish event to Kafka (joins active transaction context)
        log.info("Publishing outbound event to Kafka...");
        kafkaTemplate.send("user-notifications", userId, "Welcome event for " + username);

        // Simulate database exception to test rollback behavior
        if (username.contains("ERROR")) {
            log.error("Simulated database failure! Throwing exception to trigger rollback...");
            throw new RuntimeException("Database constraint violation!");
        }

        log.info("DB and Kafka transaction successfully committed.");
    }

    private void mockDatabaseInsert(String userId, String username) {
        log.info("Inserted into DB: user_id={}, name={}", userId, username);
    }
}
```

---

### Step-by-Step Code Walkthrough & Parameter Configuration Tables

#### Step-by-Step Code Walkthrough

##### Lab 9.1 Walkthrough
1. **`transaction-id-prefix`**: Activates transactions in `DefaultKafkaProducerFactory`. Spring uses this prefix to generate unique transaction IDs.
2. **`acks=all`**: Recommended for transactional writing to ensure that all partition replicas acknowledge the records before a transaction is marked as committed.

##### Lab 9.2 Walkthrough
1. **`@Transactional("kafkaTransactionManager")`**: Configures the listener thread to execute within a transaction boundary. Spring wraps the listener call, begins the transaction, runs your publishes, and commits them. If an exception occurs, the transaction aborts and offsets are not committed.
2. **`executeInTransaction`**: Provides programmatic transactional execution, guaranteeing that all operations inside the lambda succeed or fail together.

##### Lab 9.3 Walkthrough
1. **`@Transactional("transactionManager")`**: Targets the primary database transaction manager. When a Kafka write is executed within this method, Spring Kafka registers database synchronization callbacks, aligning the Kafka commit with the DB transaction commit.

---

### Configuration Parameter Tables

#### Spring Boot Kafka Transaction Configurations

| Property Key | Expected Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `transaction-id-prefix` | `String` | None | Enables transactions on the producer and specifies the ID prefix used by the coordinator. |
| `isolation-level` | `String` | `read_uncommitted`| Sets the consumer isolation level. Options are `read_uncommitted` and `read_committed`. |
| `transaction.timeout.ms` | `Integer` | `60000` (1 min) | The maximum transaction duration allowed by the broker coordinator before aborting. |
| `acks` | `String` | `"1"` | Set to `"all"` to ensure high durability guarantees for transactional operations. |
