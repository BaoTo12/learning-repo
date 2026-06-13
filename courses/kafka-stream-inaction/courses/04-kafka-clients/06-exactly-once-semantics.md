# Module 06: Exactly-Once Semantics (EOS)

Achieving exactly-once delivery guarantees across distributed systems is a notoriously difficult engineering challenge. Apache Kafka provides Exactly-Once Semantics (EOS) using a combination of idempotent producers and a transactional coordination protocol. This module details the internal mechanics of the idempotent producer, the lifecycle of transactional writes, consumer isolation levels, and implementation in Java.

---

## 1. The Idempotent Producer

An operation is **idempotent** if executing it multiple times yields the same result as executing it once. In Kafka, the idempotent producer prevents duplicate writes to a partition caused by network retries.

```
Producer (Sends Msg, Seq=0) ──► Broker (Writes Msg, Seq=0)
       ▲
       │ Network Timeout (ACK lost)
       │
Producer (Retries Msg, Seq=0) ──► Broker (Detects duplicate Seq=0, drops write, returns ACK)
```

### 1.1 Internal Mechanics
To achieve idempotency, the broker assigns each producer instance a unique identifier and tracks writes using sequence numbers:
1.  **Producer ID (PID)**: When the producer client initializes, the broker cluster assigns it a unique PID.
2.  **Sequence Numbers**: The producer tracks sequence numbers on a per-partition basis. Every record batch sent is assigned a sequence number that increments monotonically (starting at 0).
3.  **Broker Deduplication**: The partition leader broker stores the PID and the last committed sequence number for each partition. When a new batch arrives:
    *   If the incoming Sequence Number is exactly **$\text{Last Sequence Number} + 1$**, the broker writes the batch to disk.
    *   If the Sequence Number is **$\le \text{Last Sequence Number}$**, the broker recognizes the batch as a duplicate write (e.g., from a re-sent batch whose original acknowledgement was lost in transit). It discards the write but returns a success ACK to the producer to prevent client errors.
    *   If the Sequence Number is **$>\text{Last Sequence Number} + 1$**, it indicates a gap (missing data). The broker returns an `OutOfOrderSequenceException`.

### 1.2 Configuration
Since Kafka 3.0, idempotency is enabled by default. Explicit configuration looks like:
```java
props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, "true");
props.put(ProducerConfig.ACKS_CONFIG, "all"); // Must be set to all for idempotency
```

---

## 2. The Transactional API

While idempotency guarantees exactly-once delivery to a single partition, **Transactions** extend this guarantee across multiple topics and partitions. Transactions ensure that a write containing multiple messages succeeds as a single atomic unit, or fails completely (rolling back).

### 2.1 Coordination Protocols
Kafka manages transactions using two main components:
*   **Transaction Coordinator**: A specialized broker (elected based on a hash of the `transactional.id`) that manages the transaction state.
*   **`__transaction_state` Topic**: An internal, replicated, compacted topic that stores the transaction journal entries.

### 2.2 Transaction Lifecycle
1.  **`initTransactions()`**: The producer registers its `transactional.id` with the Transaction Coordinator. The coordinator assigns a PID and increments the **Producer Epoch**. If a previous instance of the same producer is running, it is instantly fenced (invalidated) with a `ProducerFencedException` to prevent split-brain writes.
2.  **`beginTransaction()`**: Starts the transaction locally on the client.
3.  **Produce Records**: The producer writes records to different partitions. The broker appends the records along with a control marker indicating they are part of an open transaction.
4.  **`commitTransaction()`**: The producer tells the coordinator to commit. The coordinator writes a `COMMIT` control marker to the `__transaction_state` log. The brokers then append a `COMMIT` marker to the partition logs, making the records visible to read-committed consumers.
5.  **`abortTransaction()`**: If an error occurs, the coordinator writes an `ABORT` marker. The records remain on disk but are skipped by read-committed consumers.

---

## 3. Java Transactional Loop Example

```java
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.errors.AuthorizationException;
import org.apache.kafka.common.errors.OutOfOrderSequenceException;
import org.apache.kafka.common.errors.ProducerFencedException;
import org.apache.kafka.common.serialization.StringSerializer;

import java.util.Properties;

public class TransactionalProducer {

    public void runTransaction() {
        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        
        // Define Unique Transactional ID
        props.put(ProducerConfig.TRANSACTIONAL_ID_CONFIG, "tx-retail-billing-01");

        try (KafkaProducer<String, String> producer = new KafkaProducer<>(props)) {
            // 1. Initialize transactions and register with coordinator
            producer.initTransactions();

            try {
                // 2. Start the transaction
                producer.beginTransaction();

                // 3. Write records across multiple topics
                producer.send(new ProducerRecord<>("billing-records", "tx-1", "Billing Payload"));
                producer.send(new ProducerRecord<>("ledger-records", "tx-1", "Ledger Ledger"));

                // 4. Commit the transaction
                producer.commitTransaction();
                
            } catch (ProducerFencedException | OutOfOrderSequenceException | AuthorizationException e) {
                // Fatal errors: close producer instance immediately
                producer.close();
                throw new RuntimeException("Fatal transactional error", e);
            } catch (Exception e) {
                // Retriable or operational error: abort transaction and retry
                producer.abortTransaction();
            }
        }
    }
}
```

---

## 4. Consumer Isolation Levels

Consumers must configure how they handle open or aborted transactions.

*   **`isolation.level = read_uncommitted`** (Default): The consumer reads all records sequentially, regardless of whether they were written as part of an aborted transaction.
*   **`isolation.level = read_committed`**: The consumer will only return records from successfully committed transactions (and all nontransactional records).

### Last Stable Offset (LSO) vs. High Watermark
In a transactional topic, read-committed consumers cannot read up to the High Watermark if there is an active, open transaction. Instead, they read up to the **Last Stable Offset (LSO)**—the offset immediately preceding the first active, uncommitted transaction. This prevents consumers from processing records that might be rolled back.
