# Module 05: Offset Commit Management & Pipelining

To ensure that progress is preserved across worker failures and restarts, a Kafka consumer must periodically write its read offset positions to the cluster. In Kafka, this progress tracking is called **Committing Offsets**. This module compares automatic commits against manual synchronous and asynchronous commit API patterns, and demonstrates how to implement an asynchronous processing pipeline that tracks and commits offsets safely.

---

## 1. Offsets and Commit Modes

The consumer tracks the logical position of the next record it wants to read from a partition. Committing an offset writes this value to the internal, compacted Kafka topic **`__consumer_offsets`**.

```
Read batch: [0] [1] [2] [3] [4]  ───►  Commit position: Offset 5 (Last read offset + 1)
```

---

### 1.1 Automatic Commits (The Risky Default)
When `enable.auto.commit=true`, the consumer periodically commits the latest offset returned by `poll()` at intervals defined by `auto.commit.interval.ms`.
*   **The Risk**: The commit occurs automatically *before* the application finishes processing the record batch. If a consumer pulls records 0–499, passes them to a background worker pool, and returns to the poll loop, the offsets are committed. If the background workers crash while processing record 100, the data from 101 to 499 is lost because the restarted consumer will resume reading from offset 500.

---

### 1.2 Manual Commit APIs
To prevent premature commits, configure:
```java
props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);
```

You can then trigger commits manually using two methods:
1.  **`commitSync()`**: Blocks the calling thread until the broker acknowledges the write. It retries automatically on transient errors but increases latency.
2.  **`commitAsync()`**: Non-blocking. It sends the request to the coordinator and returns immediately.
    *   **Race Condition Risk**: If you trigger `commitAsync(offset=10)` followed immediately by `commitAsync(offset=20)` due to rapid batch processing, a network delay could cause the commit for offset 20 to arrive *before* offset 10. If offset 20 succeeds but offset 10 retries and eventually succeeds, the committed offset will roll back to 10, causing duplicate processing.

---

## 2. Implementing an Asynchronous Pipelined Consumer

To process records at high throughput, you can separate the polling thread from the worker thread. However, doing so requires tracking which offsets have actually been processed to prevent out-of-order commits.

Below is an implementation of a **Pipelining Consumer** that polls records, hands them off to an asynchronous processor, and commits only successfully processed offsets:

### 2.1 The Pipelined Consumer Client
```java
package bbejeck.chapter_4.pipelining;

import bbejeck.chapter_4.sales.ProductTransaction;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.consumer.OffsetAndMetadata;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;
import io.confluent.kafka.serializers.KafkaAvroDeserializer;

import java.time.Duration;
import java.util.Collections;
import java.util.Map;
import java.util.Properties;

public class PipeliningConsumerClient {

    private volatile boolean keepConsuming = true;
    private final ConcurrentRecordProcessor recordProcessor = new ConcurrentRecordProcessor();

    public void run(Properties baseConfigs, String topic) {
        Properties props = new Properties();
        props.putAll(baseConfigs);
        // Turn off auto-commits
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "false");
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, KafkaAvroDeserializer.class.getName());

        try (KafkaConsumer<String, ProductTransaction> consumer = new KafkaConsumer<>(props)) {
            consumer.subscribe(Collections.singletonList(topic));

            while (keepConsuming) {
                // Poll records
                ConsumerRecords<String, ProductTransaction> records = consumer.poll(Duration.ofSeconds(5));
                
                if (!records.isEmpty()) {
                    // Hand off records to async worker threads
                    recordProcessor.processRecords(records);
                }

                // Check for successfully processed offsets to commit
                Map<TopicPartition, OffsetAndMetadata> completedOffsets = recordProcessor.getCompletedOffsets();
                if (completedOffsets != null && !completedOffsets.isEmpty()) {
                    // Commit processed offsets synchronously
                    consumer.commitSync(completedOffsets);
                }
            }
        }
    }
}
```

### 2.2 The Concurrent Record Processor
This class processes records on separate threads and populates a queue with completed offsets:

```java
package bbejeck.chapter_4.pipelining;

import bbejeck.chapter_4.sales.ProductTransaction;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.OffsetAndMetadata;
import org.apache.kafka.common.TopicPartition;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.*;

public class ConcurrentRecordProcessor {
    private static final Logger LOG = LoggerFactory.getLogger(ConcurrentRecordProcessor.class);
    
    // Executor pool for async workers
    private final ExecutorService executor = Executors.newFixedThreadPool(4);
    // Queue tracking completed offsets ready for commit
    private final BlockingQueue<Map<TopicPartition, OffsetAndMetadata>> offsetQueue = new LinkedBlockingQueue<>();

    public void processRecords(ConsumerRecords<String, ProductTransaction> consumerRecords) {
        executor.submit(() -> {
            Map<TopicPartition, OffsetAndMetadata> offsetsToCommit = new HashMap<>();

            // Group records by partition to resolve offsets sequentially
            for (TopicPartition partition : consumerRecords.partitions()) {
                List<ConsumerRecord<String, ProductTransaction>> partitionRecords = consumerRecords.records(partition);
                
                for (ConsumerRecord<String, ProductTransaction> record : partitionRecords) {
                    doWork(record);
                }

                // Get the offset of the last record in this partition batch
                long lastOffset = partitionRecords.get(partitionRecords.size() - 1).offset();
                
                // Commit position is last offset + 1
                offsetsToCommit.put(partition, new OffsetAndMetadata(lastOffset + 1));
            }
            offsetQueue.offer(offsetsToCommit);
        });
    }

    public Map<TopicPartition, OffsetAndMetadata> getCompletedOffsets() {
        // Poll non-blockingly from the completed offsets queue
        return offsetQueue.poll();
    }

    private void doWork(ConsumerRecord<String, ProductTransaction> record) {
        // Simulate database writes or business validations
        LOG.info("Successfully processed transaction for customer: {} offset: {}", 
                 record.key(), record.offset());
    }

    public void shutdown() {
        executor.shutdown();
    }
}
```
