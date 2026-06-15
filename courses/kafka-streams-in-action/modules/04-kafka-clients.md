# Module 04 — Kafka Clients

In this module, we will explore the core client APIs of the Apache Kafka event streaming platform: the **KafkaProducer**, **KafkaConsumer**, and **Admin API**. We will study the decoupling architecture between producers and consumers, analyze the internal client thread models and buffering systems, and detail core client configuration settings like acknowledgments, retries, and batching limits. We will cover message delivery guarantees (at-least-once, at-most-once, and exactly-once), partition assignment strategies (including round-robin, sticky, and key-based hash partitioning), custom partitioner design, and consumer group coordination (rebalance protocols, static membership, and offset commit patterns). Finally, we will dive into exactly-once streaming transactions and complete hands-on labs for standard operations, transactions, and programmatic admin tasks.

---

## 1. Academic Lecture: Kafka Client Architecture & Operations

### Basic Level: Producer/Consumer Decoupling & Thread Internals

#### Producer/Consumer Decoupling
One of the most important concepts in Apache Kafka is the complete decoupling (separation) of producers and consumers. Producers send records to the Kafka cluster without knowing who will read them, how many consumers exist, or when they will read them. Consumers pull records from the cluster without knowing which producer wrote them. 

##### Analogy: The Corporate Mailroom / Outbox Sorting Boxes
> Imagine a corporate mailroom.
> *   The **Producer** is a department secretary writing letters. They do not drop letters directly onto the mail carrier's truck. Instead, they put them in the department's **Outbox Sorting Boxes** (the **RecordAccumulator**).
> *   The **Kafka Broker** is the post office where letters are stored in mailboxes (topics).
> *   The **Consumer** is a worker in another department who periodically walks to the post office to retrieve letters from their mailbox.
> *   The secretary and the worker never talk directly, and they do not need to be online at the same time. The post office holds the letters until they are retrieved.

#### KafkaProducer Internals: RecordAccumulator & Sender Thread
When you call `producer.send()`, the message is not immediately sent over the network. Instead, the process uses a double-buffered architecture:

```text
                  ┌────────────────────────────────────────────────────────┐
                  │                    KafkaProducer                       │
                  │                                                        │
                  │  producer.send()                                       │
                  └──────┬─────────────────────────────────────────────────┘
                         │
                         ▼
                  ┌────────────────────────────────────────────────────────┐
                  │                 RecordAccumulator                      │
                  │   Buffer Pool (e.g., 32 MB memory space)               │
                  │                                                        │
                  │   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
                  │   │ Partition 0  │ │ Partition 1  │ │ Partition 2  │   │
                  │   │  [Batch #1]  │ │  [Batch #1]  │ │  [Batch #1]  │   │
                  │   │  [Batch #2]  │ │              │ │              │   │
                  │   └──────────────┘ └──────────────┘ └──────────────┘   │
                  └──────┬─────────────────────────────────────────────────┘
                         │
                         │ (Sender thread wakes up, scans batches)
                         ▼
                  ┌────────────────────────────────────────────────────────┐
                  │                    Sender Thread                       │
                  │  Sends network requests (ProduceRequests) to brokers   │
                  └────────────────────────────────────────────────────────┘
```

1.  **Application Thread (Fast & Asynchronous)**:
    *   The application thread calls `producer.send(record, callback)`.
    *   The serializer converts the key and value objects into byte arrays.
    *   The partitioner determines which topic-partition the record belongs to.
    *   The record is placed in a memory queue called the **RecordAccumulator**. This accumulator groups records together into **batches** based on their target partitions.
    *   The `send()` method returns immediately with a `Future` object, making it extremely fast.
2.  **Sender Thread (Background I/O)**:
    *   A background thread called the **Sender thread** continuously runs to scan the RecordAccumulator.
    *   It retrieves batches of records that are ready to be sent (either because the batch is full or a timeout has expired) and packages them into socket-level requests.
    *   It sends these requests to the appropriate Kafka brokers over TCP connections and executes the associated callbacks when responses return.

##### Analogy: Outbox Sacks and cargo trucks
> Think of the RecordAccumulator like a set of mail sacks in the office mailroom—one sack for each delivery neighborhood (partition).
> *   When a clerk writes a letter (`send()`), they drop it into the appropriate sack.
> *   The **Sender thread** is the mail truck driver. The driver waits until a mail sack is completely full (reaches `batch.size`), or a timer clock ticks (`linger.ms` expires), before loading the sack onto the truck and driving it to the sorting facility.

#### KafkaConsumer Internals: Poll Loop & Heartbeats
The `KafkaConsumer` client is single-threaded (with a background heartbeat helper thread). It operates using a active polling model:

*   **The Poll Loop (`poll()`)**:
    *   The consumer must call `poll(Duration)` regularly. This call is the engine of the consumer.
    *   It fetches records from the broker partitions.
    *   It triggers group coordinator interactions, such as joining a group or rebalancing.
    *   It handles automatically committing offsets if enabled.
*   **The Heartbeat Thread**:
    *   Behind the scenes, a background thread sends periodic **heartbeats** to the broker acting as the **Group Coordinator** to prove the client is still alive.

---

### Intermediate Level: Configurations, Partitioning Strategies, Timestamps & Rebalancing

#### Producer Configuration Essentials

To ensure messages are delivered reliably and quickly, you must fine-tune these parameters:

*   **`acks`**: Specifies how many replicas must write the record before the producer considers the write successful.
    *   `0`: The producer considers the write successful as soon as it sends the record over the socket. It does not wait for a response. (Lowest safety, highest speed).
    *   `1`: The producer waits for the partition leader broker to write the record to its log. It does not wait for replicas. (Medium safety).
    *   `all` (or `-1`): The producer waits for the leader and all in-sync replicas (ISRs) to write the record. (Highest safety, lowest speed).
*   **`retries`**: The number of times the client will retry sending a batch if it encounters a transient error (e.g., network timeout or leader election). The default is `Integer.MAX_VALUE` (controlled by `delivery.timeout.ms`).
*   **`max.in.flight.requests.per.connection`**: The maximum number of unacknowledged requests the client can send over a single connection before blocking.
    *   *Warning*: If set to > 1 and `retries` > 0, records could end up out of order. For example, if batch 1 fails but batch 2 succeeds, batch 1 will be retried and written after batch 2.
    *   *Solution*: Set it to 1, or enable idempotence (which allows up to 5 in-flight requests safely).
*   **`compression.type`**: Compresses record batches before writing them to network sockets (`gzip`, `snappy`, `lz4`, `zstd`). This saves network bandwidth and disk storage on brokers.
*   **`batch.size`**: The maximum size in bytes of a single batch in the RecordAccumulator.
*   **`linger.ms`**: The time in milliseconds the producer waits before sending a batch if the batch is not yet full. Increasing this allows more batching, improving throughput but increasing latency.

#### Partition Assignment Strategies

When producing a record, Kafka determines which partition inside the topic will store it:

1.  **Explicit Partition**: You specify the exact partition number in the `ProducerRecord` constructor.
2.  **Key-based Hash Partitioning (Default)**: If a key is present but no partition is specified, Kafka calculates a hash of the key (`murmur2` hash) and takes the modulo of the total partitions count:
    $$	ext{Partition} = |	ext{murmur2(key)}| \pmod{	ext{number of partitions}}$$
    This guarantees that all records with the same key always end up in the exact same partition.
3.  **Sticky Partitioner (Default since Kafka 2.4 when no key is present)**:
    *   *Historical Context*: Before 2.4, round-robin was used, where each record went to a different partition sequentially. This resulted in many small, half-empty batches.
    *   *Mechanism*: The sticky partitioner chooses a random partition and writes all records to it until a batch is full or `linger.ms` expires. Then, it chooses a new partition. This dramatically increases batch sizes, reducing CPU overhead and network requests.

##### Analogy: Shopping Cart Loaders
> Imagine loading groceries into delivery trucks.
> *   **Round-robin** is like placing one grocery item in Truck 1, the next in Truck 2, the next in Truck 3, then back to Truck 1. You end up sending three half-empty trucks.
> *   **Sticky partitioning** is like filling Truck 1 completely with grocery bags before you start loading Truck 2. This ensures trucks always leave full, saving fuel and time.

#### Custom Partitioner Design
You can write a custom partitioner class by implementing the `org.apache.kafka.clients.producer.Partitioner` interface. This allows you to route records based on custom rules (e.g., routing a premium customer's events to a dedicated partition).

#### Record Timestamps: CreateTime vs. LogAppendTime
Every Kafka record contains a timestamp. The meaning of this timestamp is configured on a per-topic basis via `message.timestamp.type`:

*   **`CreateTime` (Default)**: The timestamp is set by the producer when the record is created.
*   **`LogAppendTime`**: The timestamp is overwritten by the broker with its system clock time when the record is written to the log partition.

#### Consumer Group Coordinator & Rebalancing Protocols
A **consumer group** is a collaborative unit of consumers with the same `group.id` who divide topic partition ownership among themselves. The broker assigned to monitor the group is called the **Group Coordinator**. When a consumer joins or leaves the group, or fails to send heartbeats, a **rebalance** is triggered.

There are two major rebalance protocols:

##### 1. Eager Rebalance (Stop-the-World)
During an eager rebalance, all consumers in the group must stop processing and give up their current partition assignments. They send a `JoinGroup` request to the coordinator, which assigns partitions from scratch. 
*   *Downside*: This creates a **synchronization barrier** where no records are processed by any consumer until the rebalance is complete.

##### 2. Incremental Cooperative Rebalance
Introduced in Kafka 2.4, this protocol avoids stopping all consumers. 
*   *Mechanism*: The group coordinator and leader identify only the specific partitions that need to migrate from one consumer to another. Consumers only give up ownership of the revoked partitions. Unaffected consumers keep processing their assigned partitions without interruption.

##### Analogy: Eager vs. Cooperative Assignment
> Imagine a team of three clerks sorting physical folders.
> *   **Eager**: A new clerk joins the room. The manager screams "Stop!", snatches all folders from everyone, shuffles them, and redistributes them. While this is happening, no work is done.
> *   **Cooperative**: A new clerk joins. The manager tells them to wait. The manager taps Clerk A on the shoulder and asks them to hand one of their folders to the new clerk. Clerk B and C never stop working.

#### Static Membership
In modern environments like Kubernetes, container restarts or rolling updates occur frequently. Normally, shutting down a consumer to update it triggers a rebalance. When it restarts, it triggers another.

To avoid these transient rebalances, you can set `group.instance.id` to configure **static membership**. The Group Coordinator registers this ID. If the consumer restarts, as long as it rejoins within `session.timeout.ms`, it receives its original partitions back without triggering a rebalance.

---

### Advanced Level: Exactly-Once Semantics, Transaction States & Pipelining

#### Exactly-Once Semantics (EOS) Mechanics
Exactly-Once Semantics guarantees that even if a producer retries due to network failure, or a consumer restarts after processing, the system acts as if the record was delivered exactly once. This is achieved by combining three elements:

##### 1. Idempotent Producer
You enable idempotence by setting `enable.idempotence=true`. The producer is assigned a unique **Producer ID (PID)** by the broker. For each partition, the producer assigns a monotonically increasing **Sequence Number** starting at 0 to every batch.

```text
Producer (PID: 1042)                                        Broker (Partition 0)
────────────────────                                        ────────────────────
Send Batch (Seq: 0)  ─────────(Network Good)────────►       Written! (Expected Seq: 0)
                                                            Next Expected: 1

Send Batch (Seq: 1)  ──x (Broker writes, ACK lost) ──►      Written! (Expected Seq: 1)
                                                            Next Expected: 2

Retry Batch (Seq: 1) ─────────(Retry request)────────►      Duplicate Detected! (Seq 1 < 2)
                                                            Discard batch, return success ACK.
```

*   The broker tracks the next expected sequence number in memory.
*   If the broker receives a sequence number that it has already written, it discards the duplicate write and sends back a success acknowledgment.
*   If it receives a sequence number greater than expected, it throws an `OutOfOrderSequenceException` (which triggers a producer rollback/retry).

##### 2. Transactional Producer
To write to multiple partitions and topics atomically, you set `transactional.id`. This involves a broker-side helper called the **Transaction Coordinator** and a compacted topic `__transaction_state` to store transaction logs.

The steps are:
1.  **`initTransactions()`**: The producer registers its `transactional.id` with the Transaction Coordinator. The coordinator increments the **Producer Epoch** (bumping old instances out to prevent "zombie" writes).
2.  **`beginTransaction()`**: Marks the start of a local transaction block.
3.  **`send()`**: Writes messages to partitions.
4.  **`sendOffsetsToTransaction()`**: Writes consumer offsets directly to the transaction, linking offset commits to the success of the transaction.
5.  **`commitTransaction()`** or **`abortTransaction()`**: The coordinator writes a commit or abort marker to all partition logs.

##### 3. Read-Committed Consumers
To ensure consumers do not read dirty data, they must configure `isolation.level = read_committed`. 

*   **Last Stable Offset (LSO)**: The point in the log where all records below it are decided (either committed or not part of a transaction).
*   **High Watermark (HW)**: The point in the log successfully written to all replicas.
*   A `read_committed` consumer can only read up to the **LSO**, while a `read_uncommitted` consumer can read up to the **HW**, exposed to uncommitted data.

#### Pipelining with Manual Commits
If a consumer processes records using asynchronous helper threads to increase throughput, you must disable auto-commits (`enable.auto.commit = false`). Otherwise, the consumer poll loop will commit offsets of records that are still queueing in the helper threads. If a crash occurs, those records are lost (at-most-once delivery).

To implement safe pipelining, you must manually collect the offsets of successfully completed items and commit them using `commitSync(Map<TopicPartition, OffsetAndMetadata>)`.

#### Handling Multiple Event Types on a Single Topic
To preserve the sequence of related events (e.g., a customer's `LogInEvent`, `SearchEvent`, and `PurchaseEvent`), you should write them to a single topic partition. You can structure this in two ways:

1.  **Google Protobuf `oneof` Strategy**:
    *   Create a wrapper schema `Events.proto` containing a `oneof` field that includes all possible event types.
    *   *Consumer code*: Use `Events.getTypeCase()` to switch and handle concrete event types.
2.  **Apache Avro Union Strategy**:
    *   Define a top-level union type array in Avro: `["LoginEvent", "SearchEvent", "PurchaseEvent"]`.
    *   **CRITICAL CONFIGURATION**:
        *   Producers must set `auto.register.schemas = false` and `use.latest.version = true`.
        *   *Why*: If not, the producer will register a single event's schema directly under the topic subject, destroying the union registration and breaking other events.
        *   Consumers must specify the generic value type `SpecificRecord` as the value deserializer class target.

---

## 2. Theory vs. Production Trade-offs

### Producer Acknowledgments (`acks`) Comparison

| setting | data durability | throughput | latency | potential failure scenarios |
| :--- | :--- | :--- | :--- | :--- |
| **`acks=0`** | None | Extremely High | Extremely Low | Message lost if broker crashes immediately after socket write. |
| **`acks=1`** | Medium | High | Low | Message lost if leader crashes before replica fetches data. |
| **`acks=all`** | Maximum | Moderate | Higher | Write fails if insufficient replicas are available (`NotEnoughReplicasException`). |

### Commit Methods Comparison

| method | delivery guarantee | latency impact | implementation complexity | ideal use case |
| :--- | :--- | :--- | :--- | :--- |
| **`Auto-commit`** | At-least-once (default) | None | Zero | Simple pipelines where duplicate processing is acceptable. |
| **`commitSync()`** | At-least-once / At-most-once | High (Blocks poll thread) | Low | Low-throughput jobs where strict processing order is needed. |
| **`commitAsync()`** | At-least-once | Low (Non-blocking) | Medium (Must handle callbacks) | High-throughput systems where async logging is acceptable. |
| **`Transactional`**| Exactly-once (EOS) | Higher (Transaction markers) | High | Financial transactions, inventory updates, balance sheets. |

### Rebalance Protocols Comparison

| protocol | rebalance latency | active partition processing | synchronization barrier | ideal usecase |
| :--- | :--- | :--- | :--- | :--- |
| **`Eager`** | High | Stopped entirely | Large (Stop-the-World barrier) | Legacy systems (pre-Kafka 2.4). |
| **`Cooperative`** | Low | Continues for unmoved partitions | Tiny (incremental changes only) | Modern cloud-native microservices. |

---

## 3. Common Errors & Pitfalls

### Pitfall 1: `RecordTooLargeException`
*   **Why it fails**: The producer attempts to send a batch or record larger than configured client limits or broker limits.
*   **Default configurations**:
    *   Producer: `max.request.size = 1048576` (1 MB)
    *   Broker: `message.max.bytes = 1048588` (1 MB)
*   **How to fix**:
    *   Increase the broker parameter `message.max.bytes` and topic parameter `max.message.bytes`.
    *   Increase the producer parameter `max.request.size`.
    *   *Crucial*: Always keep these limits aligned across clients, topics, and brokers to avoid silent drops.

### Pitfall 2: `CommitFailedException`
*   **Why it fails**: The consumer poll loop takes too long to process a batch of records, exceeding `max.poll.interval.ms` (default: 5 minutes). The Group Coordinator assumes the consumer is dead, removes it from the group, and triggers a rebalance. When the consumer finally attempts to commit, it fails because it no longer owns the partition.
*   **How to fix**:
    *   Optimize the processing code.
    *   Decrease `max.poll.records` (default: 500) to fetch fewer records per loop.
    *   Increase `max.poll.interval.ms` to give your code more time.

### Pitfall 3: `ProducerFencedException`
*   **Why it fails**: A transactional producer with a specific `transactional.id` is blocked (e.g., due to a garbage collection pause or network timeout) and fails to write within `transaction.timeout.ms`. The Transaction Coordinator aborts the transaction and bumps the producer epoch. When the blocked producer resumes and attempts to commit, it is blocked (fenced) because its epoch is outdated.
*   **How to fix**:
    *   Ensure network connections are stable.
    *   Set `transaction.timeout.ms` to a larger value to accommodate temporary GC stalls.
    *   Catch the exception, close the producer, and instantiate a new client instance.

---

## 4. Socratic Review Questions

### Question 1
Why does enabling Kafka transactions automatically turn on the idempotent producer configuration?

#### Answer
A transaction requires absolute guarantee of in-order, duplicate-free writes to the partition log. If messages could be duplicated or written out of order during retries, the Transaction Coordinator would not be able to guarantee atomic commitments. Therefore, idempotence (`enable.idempotence=true`) is a strict prerequisite for transactions.

### Question 2
When using static membership (`group.instance.id`), if a consumer instance crashes permanently, why doesn't its partition assignment failover immediately? What is the architectural trade-off?

#### Answer
When a static member shuts down, it does not send a "leave group" request to the coordinator. The coordinator waits for the consumer to return. The partitions remain assigned to the dead consumer until the `session.timeout.ms` expires. 
*   **Trade-off**: The benefit is that transient updates do not cause rebalances. The cost is that if a consumer crashes permanently, processing for its partitions stops entirely for the duration of the session timeout before failover occurs.

### Question 3
Explain why a `read_committed` consumer might experience latency spikes if a transactional producer crashes mid-transaction.

#### Answer
A `read_committed` consumer can only fetch records up to the Last Stable Offset (LSO). The LSO is blocked by the first open active transaction. If a producer starts a transaction but crashes before committing or aborting, the LSO remains blocked. The consumer will not be able to read any subsequent records—even from completed transactions—until the Transaction Coordinator times out the hung transaction (default: 1 minute) and writes an abort marker, which advances the LSO.

---

## 5. Hands-on Labs: Producer, Consumer, Transactions, and Admin API

### Lab 4.1 — Basic Avro Producer
Create the directory structure `src/main/java/com/kafkastreams/course/producer/` and save the class as `BasicPurchaseProducer.java`.

This client generates a mock `Purchase` event (defined in Module 3) and sends it asynchronously to the `purchases` topic with a callback.

```java
package com.kafkastreams.course.producer;

import com.kafkastreams.course.Purchase;
import io.confluent.kafka.serializers.KafkaAvroSerializer;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;
import java.time.Instant;
import java.util.Properties;

public class BasicPurchaseProducer {
    public static void main(String[] args) {
        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, KafkaAvroSerializer.class.getName());
        props.put("schema.registry.url", "http://localhost:8081");

        try (KafkaProducer<String, Purchase> producer = new KafkaProducer<>(props)) {
            Purchase purchase = Purchase.newBuilder()
                    .setCustomerId("customer-001")
                    .setItemPurchased("Kafka Streams in Action Book")
                    .setQuantity(1)
                    .setPrice(49.99)
                    .setPurchaseDate(Instant.now().toEpochMilli())
                    .build();

            ProducerRecord<String, Purchase> record =
                    new ProducerRecord<>("purchases", purchase.getCustomerId(), purchase);

            System.out.println("Sending record to Kafka...");
            producer.send(record, (metadata, exception) -> {
                if (exception == null) {
                    System.out.printf("Successfully sent! Topic: %s, Partition: %d, Offset: %d%n",
                            metadata.topic(), metadata.partition(), metadata.offset());
                } else {
                    System.err.println("Error producing message to broker:");
                    exception.printStackTrace();
                }
            });
            
            // Flush to ensure the record is sent before exiting try block
            producer.flush();
        }
    }
}
```

---

### Lab 4.2 — Consumer with Manual Offset Commit
Create `src/main/java/com/kafkastreams/course/consumer/ManualCommitConsumer.java`.

This client reads records from the `purchases` topic, processes them, and manually commits the offsets synchronously to ensure at-least-once processing.

```java
package com.kafkastreams.course.consumer;

import com.kafkastreams.course.Purchase;
import io.confluent.kafka.serializers.KafkaAvroDeserializer;
import io.confluent.kafka.serializers.KafkaAvroDeserializerConfig;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.serialization.StringDeserializer;
import java.time.Duration;
import java.util.Collections;
import java.util.Properties;

public class ManualCommitConsumer {
    public static void main(String[] args) {
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "manual-commit-group");
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "false");
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, KafkaAvroDeserializer.class.getName());
        props.put("schema.registry.url", "http://localhost:8081");
        props.put(KafkaAvroDeserializerConfig.SPECIFIC_AVRO_READER_CONFIG, "true");

        try (KafkaConsumer<String, Purchase> consumer = new KafkaConsumer<>(props)) {
            consumer.subscribe(Collections.singletonList("purchases"));
            System.out.println("Subscribed and polling...");

            int emptyPollCount = 0;
            while (emptyPollCount < 10) { // Limit run loop for demonstration
                ConsumerRecords<String, Purchase> records = consumer.poll(Duration.ofSeconds(2));
                if (records.isEmpty()) {
                    emptyPollCount++;
                    continue;
                }
                
                emptyPollCount = 0;
                for (ConsumerRecord<String, Purchase> record : records) {
                    Purchase purchase = record.value();
                    System.out.printf("Received Purchase - Cust: %s, Item: %s, Qty: %d, Price: %.2f (Offset: %d)%n",
                            purchase.getCustomerId(),
                            purchase.getItemPurchased(),
                            purchase.getQuantity(),
                            purchase.getPrice(),
                            record.offset());
                }

                try {
                    // Sync commit blocks until coordinator acknowledges
                    consumer.commitSync();
                    System.out.println("Offset committed successfully.");
                } catch (Exception e) {
                    System.err.println("Commit failed:");
                    e.printStackTrace();
                }
            }
        }
    }
}
```

---

### Lab 4.3 — Idempotent Producer Setup
Create `src/main/java/com/kafkastreams/course/producer/IdempotentProducer.java`.

This client demonstrates how to safely configure the producer to prevent duplication and ordering errors.

```java
package com.kafkastreams.course.producer;

import com.kafkastreams.course.Purchase;
import io.confluent.kafka.serializers.KafkaAvroSerializer;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;
import java.time.Instant;
import java.util.Properties;

public class IdempotentProducer {
    public static void main(String[] args) {
        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, KafkaAvroSerializer.class.getName());
        props.put("schema.registry.url", "http://localhost:8081");

        // Idempotency requirements
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, "true");
        props.put(ProducerConfig.ACKS_CONFIG, "all");
        props.put(ProducerConfig.RETRIES_CONFIG, String.valueOf(Integer.MAX_VALUE));
        props.put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, "5");

        try (KafkaProducer<String, Purchase> producer = new KafkaProducer<>(props)) {
            Purchase purchase = Purchase.newBuilder()
                    .setCustomerId("customer-idempotent-9")
                    .setItemPurchased("Guaranteed Delivery Notebook")
                    .setQuantity(2)
                    .setPrice(15.50)
                    .setPurchaseDate(Instant.now().toEpochMilli())
                    .build();

            ProducerRecord<String, Purchase> record =
                    new ProducerRecord<>("purchases", purchase.getCustomerId(), purchase);

            System.out.println("Sending idempotent record...");
            producer.send(record, (metadata, exception) -> {
                if (exception == null) {
                    System.out.printf("Sent to partition %d, offset %d%n",
                            metadata.partition(), metadata.offset());
                } else {
                    exception.printStackTrace();
                }
            });
            producer.flush();
        }
    }
}
```

---

### Lab 4.4 — Transactional Producer: Produce-Consume-Produce in a Transaction
Create `src/main/java/com/kafkastreams/course/transaction/TransactionalPipeline.java`.

This client demonstrates a full transaction loop: consuming from `purchases`, filtering or processing, writing to `processed-purchases`, and committing the offsets in a single atomic transaction.

```java
package com.kafkastreams.course.transaction;

import com.kafkastreams.course.Purchase;
import io.confluent.kafka.serializers.KafkaAvroDeserializer;
import io.confluent.kafka.serializers.KafkaAvroDeserializerConfig;
import io.confluent.kafka.serializers.KafkaAvroSerializer;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.KafkaException;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.errors.AuthorizationException;
import org.apache.kafka.common.errors.OutOfOrderSequenceException;
import org.apache.kafka.common.errors.ProducerFencedException;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import java.time.Duration;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;

public class TransactionalPipeline {
    public static void main(String[] args) {
        String inputTopic = "purchases";
        String outputTopic = "processed-purchases";

        // Consumer configs
        Properties consumerProps = new Properties();
        consumerProps.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        consumerProps.put(ConsumerConfig.GROUP_ID_CONFIG, "tx-pipeline-group");
        consumerProps.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "false");
        consumerProps.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        consumerProps.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG, "read_committed");
        consumerProps.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, KafkaAvroDeserializer.class.getName());
        consumerProps.put("schema.registry.url", "http://localhost:8081");
        consumerProps.put(KafkaAvroDeserializerConfig.SPECIFIC_AVRO_READER_CONFIG, "true");

        // Producer configs
        Properties producerProps = new Properties();
        producerProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        producerProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, KafkaAvroSerializer.class.getName());
        producerProps.put("schema.registry.url", "http://localhost:8081");
        producerProps.put(ProducerConfig.TRANSACTIONAL_ID_CONFIG, "tx-retail-pipeline-01");

        try (KafkaConsumer<String, Purchase> consumer = new KafkaConsumer<>(consumerProps);
             KafkaProducer<String, Purchase> producer = new KafkaProducer<>(producerProps)) {

            // Register transactional.id with coordinator
            producer.initTransactions();
            consumer.subscribe(Collections.singletonList(inputTopic));
            System.out.println("Transactional Pipeline started...");

            int emptyPolls = 0;
            while (emptyPolls < 5) {
                ConsumerRecords<String, Purchase> records = consumer.poll(Duration.ofSeconds(2));
                if (records.isEmpty()) {
                    emptyPolls++;
                    continue;
                }
                
                emptyPolls = 0;
                try {
                    producer.beginTransaction();
                    Map<TopicPartition, OffsetAndMetadata> offsets = new HashMap<>();

                    for (TopicPartition partition : records.partitions()) {
                        List<ConsumerRecord<String, Purchase>> partitionRecords = records.records(partition);
                        for (ConsumerRecord<String, Purchase> record : partitionRecords) {
                            Purchase purchase = record.value();
                            
                            // Simple processing: double the quantity for VIP VIP customers
                            if (purchase.getCustomerId().startsWith("customer")) {
                                purchase.setQuantity(purchase.getQuantity() * 2);
                            }

                            producer.send(new ProducerRecord<>(outputTopic, record.key(), purchase));
                        }

                        // Save next expected offset (highest offset in batch + 1)
                        long lastOffset = partitionRecords.get(partitionRecords.size() - 1).offset();
                        offsets.put(partition, new OffsetAndMetadata(lastOffset + 1));
                    }

                    // Commit offsets inside the transaction boundary
                    producer.sendOffsetsToTransaction(offsets, consumer.groupMetadata());
                    producer.commitTransaction();
                    System.out.println("Transaction committed successfully.");

                } catch (ProducerFencedException | OutOfOrderSequenceException | AuthorizationException e) {
                    System.err.println("Fatal transactional error. Closing producer.");
                    throw new RuntimeException("Fatal client error, closing...", e);
                } catch (KafkaException e) {
                    System.err.println("Transient transaction error. Aborting transaction...");
                    producer.abortTransaction();
                }
            }
        }
    }
}
```

---

### Lab 4.5 — Admin API Programmatic Topic Management
Create `src/main/java/com/kafkastreams/course/admin/AdminTopicManager.java`.

This client demonstrates how to create, list (describe), and delete topics programmatically.

```java
package com.kafkastreams.course.admin;

import org.apache.kafka.clients.admin.Admin;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.clients.admin.TopicDescription;
import java.util.Collections;
import java.util.Map;
import java.util.Properties;
import java.util.Set;

public class AdminTopicManager {
    public static void main(String[] args) {
        String testTopicName = "temp-admin-topic";
        Properties props = new Properties();
        props.put(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");

        try (Admin admin = Admin.create(props)) {
            // 1. Create a Topic
            System.out.printf("Creating topic '%s'...%n", testTopicName);
            NewTopic newTopic = new NewTopic(testTopicName, 2, (short) 1);
            admin.createTopics(Collections.singletonList(newTopic)).all().get();
            System.out.println("Topic created successfully.");

            // 2. Describe Topic (Check metadata)
            System.out.println("Describing topics...");
            Map<String, TopicDescription> descriptions = admin.describeTopics(Collections.singletonList(testTopicName)).all().get();
            TopicDescription desc = descriptions.get(testTopicName);
            System.out.printf("Topic: %s, Partitions Count: %d, Internal: %b%n",
                    desc.name(), desc.partitions().size(), desc.isInternal());

            // 3. List Topics
            System.out.println("Listing all topics...");
            Set<String> topicNames = admin.listTopics().names().get();
            System.out.println("Topic list: " + topicNames);

            // 4. Delete Topic
            System.out.printf("Deleting topic '%s'...%n", testTopicName);
            admin.deleteTopics(Collections.singletonList(testTopicName)).all().get();
            System.out.println("Topic deleted successfully.");
        } catch (Exception e) {
            System.err.println("Admin Client action failed:");
            e.printStackTrace();
        }
    }
}
```

---

## 6. Detailed Breakdown of Configurations

Here is what each key in the client configuration maps used in the labs actually does in plain English:

### Producer Configurations

| Property Key | Example Value | Description |
| :--- | :--- | :--- |
| `bootstrap.servers` | `"localhost:9092"` | A list of broker addresses (host:port) that the producer uses to establish its initial connection. |
| `key.serializer` | `StringSerializer.class` | The utility class used to convert the Java String key object into a raw byte array. |
| `value.serializer` | `KafkaAvroSerializer.class` | The Confluent utility class used to convert Avro-generated record objects into the wire byte format. |
| `schema.registry.url` | `"http://localhost:8081"` | The network URL where Schema Registry is listening. Used by serializers to check and register Avro schemas. |
| `enable.idempotence` | `"true"` | When true, assigns unique sequence IDs to batches to prevent duplicate writes and logs on broker retries. |
| `acks` | `"all"` | Tells the producer to wait for all in-sync replicas to confirm receipt before marking the write as successful. |
| `retries` | `Integer.MAX_VALUE` | The maximum retry counts for sending a failed batch before reporting failure. |
| `max.in.flight.requests.per.connection` | `"5"` | The number of unacknowledged record batches that the client can push concurrently over a single TCP connection. |
| `transactional.id` | `"tx-retail-pipeline-01"` | A unique identifier configured for transactional producers, mapping the epoch state to recover from crashes. |

### Consumer Configurations

| Property Key | Example Value | Description |
| :--- | :--- | :--- |
| `bootstrap.servers` | `"localhost:9092"` | The addresses of brokers to establish the initial network handshake. |
| `group.id` | `"tx-pipeline-group"` | A string label grouping multiple consumer instances into a cooperative pool. |
| `enable.auto.commit` | `"false"` | When set to false, disables automatic offset commits, requiring explicit code commits. |
| `auto.offset.reset` | `"earliest"` | Specifies where to begin reading records if no offset commits are found (from the beginning). |
| `isolation.level` | `"read_committed"` | Configures the consumer to hide/ignore aborted transaction records, reading only up to the LSO. |
| `key.deserializer` | `StringDeserializer.class` | The class used to deserialize the raw key bytes back into a Java String. |
| `value.deserializer` | `KafkaAvroDeserializer.class` | The class used to deserialize record value bytes back into strongly typed Java structures using Schema Registry. |
| `schema.registry.url` | `"http://localhost:8081"` | The url of Schema Registry to pull schema identifiers. |
| `specific.avro.reader` | `"true"` | Instructs the deserializer to map Avro payloads into strongly typed classes (e.g. `Purchase`) rather than generic `GenericRecord` structures. |

### Admin Client Configurations

| Property Key | Example Value | Description |
| :--- | :--- | :--- |
| `bootstrap.servers` | `"localhost:9092"` | The addresses of brokers for programmatic resource management operations. |

---

## 7. Verification Command
To compile and package the clients module after setting up:

```bash
mvn clean compile
```
