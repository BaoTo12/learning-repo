# Module 16 — Performance Tuning

In this module, we will explore Performance Tuning in Spring Kafka. We will cover producer tuning configurations (`batch.size`, `linger.ms`, `compression.type`, `buffer.memory`) and consumer tuning parameters (`max.poll.records`, `fetch.min.bytes`, `concurrency`). We will study the trade-offs between throughput optimization and latency optimization,Concurrency tuning, and Batch tuning. Finally, we will cover troubleshooting, answer 5 Socratic questions, and implement hands-on labs with complete code structures.

---

## 1. Academic Lecture: Throughput, Latency, Concurrency & Batch Tuning

### Basic Level: Producer Tuning & Batching Parameters

#### High Throughput vs. Low Latency
When tuning Kafka clients, there is a fundamental trade-off:
* **Throughput Optimization**: Sending messages in large blocks to maximize bytes per second (saves network overhead, but increases the time individual messages wait before being sent).
* **Latency Optimization**: Sending messages immediately (reduces latency, but increases CPU and network overhead due to tiny packet headers).

#### Producer Batching parameters
To optimize throughput, configure the producer parameters:
* **`batch.size`**: The maximum size in bytes of a single partition batch. Once a batch fills up to this size, it is immediately sent to the broker.
* **`linger.ms`**: The time to wait (in milliseconds) to let more messages accumulate in the batch before sending. If `linger.ms = 50`, the producer waits up to 50ms for more records. This drastically increases throughput under load.
* **`buffer.memory`**: The total memory pool size in bytes the producer can use to buffer records waiting to be sent to the broker.

---

### Intermediate Level: Consumer Batching & Thread Concurrency

#### Consumer Batching
On the consumer side, reading in batches decreases database transaction locks and network overhead.
* **`max.poll.records`**: The maximum number of records returned in a single poll call. Setting this to `500` or `1000` allows batch consumers to bulk-process records.
* **`fetch.min.bytes`**: The minimum amount of data the broker should return for a fetch request. If set to `1024` (1KB), the broker waits until 1KB of data is ready, reducing polling network chats.

#### Concurrency Tuning
The `concurrency` property of Spring listener containers scales consumer performance:
* **`concurrency = N`**: Instructs Spring to spin up `N` parallel Kafka consumer threads within the single container.
* **Concurrency Rules**: The number of threads should not exceed the partition count of the topic. If topic `orders` has 12 partitions, setting `concurrency = 12` assigns exactly 1 thread per partition, maximizing consumer performance. Any thread beyond 12 will remain idle.

---

### Advanced Level: Compression Algorithms & Socket Buffers

#### Compression Type
Compressing messages reduces both disk utilization on the brokers and network bandwidth. The available algorithms are:
* **Snappy**: Default standard developed by Google. Excellent balance of CPU usage and compression ratio.
* **zstd** (Zstandard): Developed by Facebook. Extremely high compression ratio, but higher CPU utilization.
* **LZ4**: Very fast compression/decompression speed; good for low-latency pipelines.
* **GZIP**: High compression ratio, but very slow CPU overhead. Avoid in high-volume real-time messaging.

#### Memory Management
Tuning socket buffers protects microservices from system bottlenecks:
* **`send.buffer.bytes` / `receive.buffer.bytes`**: The size of the TCP send/receive buffers. In high-bandwidth WAN connections (e.g. crossing data centers), increasing this to 1MB ensures the network pipe stays full.

---

## 2. Theory & Production Best Practices

### High Throughput vs. Low Latency Configurations

| Param | High Throughput Profile | Low Latency Profile (Default) |
| :--- | :--- | :--- |
| **`acks`** | `1` (or `all` with batching) | `1` (or `0` for fire-and-forget) |
| **`linger.ms`** | `50` to `100` milliseconds | `0` (send immediately) |
| **`batch.size`** | `65536` (64 KB) to `131072` (128 KB) | `16384` (16 KB) |
| **`compression.type`**| `snappy` or `zstd` | `none` (or `lz4`) |
| **`max.in.flight`** | `5` (enables pipelining) | `1` (strict ordering) |

### Compression Algorithms Comparison

| Algorithm | Compression Ratio | CPU Usage (Compress) | CPU Usage (Decompress) | Best Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **none** | 1.0 (No Compression) | None | None | Ultra-low latency LAN. |
| **LZ4** | Good | Extremely Low | Extremely Low | Standard low-latency pipeline.|
| **Snappy** | Very Good | Low | Low | Default recommendation. |
| **zstd** | Best | Medium | Low | High volume, archiving logs. |
| **GZIP** | Best | Extremely High | High | Legacy systems only. |

---

## 3. Common Errors & Troubleshooting

### 1. Producer Buffer Exhaustion / Timeout Exception
* **Symptom**: Publisher throws `TimeoutException: Failed to allocate memory within the configured max block time`.
* **Root Cause**: The producer is generating messages faster than the broker can acknowledge them. The `buffer.memory` pool (default 32MB) is full, and the thread blocks for `max.block.ms` before timing out.
* **Fix**:
  * Check broker performance (disk I/O bottlenecks).
  * Increase `buffer.memory` or decrease client thread write rate.

### 2. Consumer Rebalance Due to Batch Processing Starvation
* **Symptom**: Consumer group keeps rebalancing, logging `CommitFailedException` or group coordinator timeouts.
* **Root Cause**: The consumer fetched a large batch of records (`max.poll.records = 1000`). Processing the 1000 records took longer than `max.poll.interval.ms` (default 5 minutes). The broker assumed the consumer thread died and triggered a rebalance.
* **Fix**:
  * Decrease `max.poll.records` (e.g. to `100`).
  * Increase `max.poll.interval.ms` in the consumer properties.
  * Optimize processing logic (use parallel processing or bulk DB writes).

### 3. Idle Consumer Threads
* **Symptom**: Half of your microservice container replica consumer threads are idle, reading 0 messages.
* **Root Cause**: The total container concurrency count (replicas * concurrency setting) is greater than the partition count of the topic.
* **Fix**: Ensure that the total thread count matches the partition count. If the topic has 6 partitions, run 2 replicas with `concurrency = 3` (6 threads total).

---

## 4. Socratic Review Questions

### Question 1
*How does setting `linger.ms > 0` improve overall throughput while increasing latency?*
* **Answer**: It forces the producer client to pause for a few milliseconds before sending. This delay allows other threads to add their messages to the active partition batch. Sending one large network socket write containing 100 messages is significantly faster and consumes less CPU than sending 100 separate network requests.

### Question 2
*Why is zstd compression preferred for high-volume logs, while LZ4 is preferred for real-time transactional APIs?*
* **Answer**: zstd provides the highest compression ratio (saving massive disk and bandwidth storage space) but requires significant CPU compression cycles. LZ4 has a slightly lower compression ratio but is extremely fast to compress and decompress, minimizing processing latency.

### Question 3
*What is the relationship between `concurrency` setting in Spring and partition allocation in Kafka?*
* **Answer**: Spring spins up `concurrency` number of consumer threads. Each thread registers as an independent consumer within the same group ID. Kafka assigns partitions among these threads. If concurrency is higher than partition count, the excess threads receive no partition assignments and remain idle.

### Question 4
*What happens if `max.poll.records` is set to 2000, but the database batch insert limit is capped at 100?*
* **Answer**: The application will perform 20 sequential database calls of size 100 inside the consumer loop, which is slow. To optimize performance, match the consumer batch size to the database insert batch size, or process database inserts concurrently.

### Question 5
*How can you prevent a slow downstream database from triggering consumer group eviction rebalances?*
* **Answer**: By configuring a lower `max.poll.records` limit to ensure the poll loop returns quickly, or by increasing `max.poll.interval.ms` to give the consumer thread enough time to complete processing before the coordinator logs a timeout.

---

## 5. Hands-on Labs

### Lab 16.1 — High-Throughput Producer Configuration

#### Scenario
We will configure a Spring Kafka Producer for high-throughput batching, enable Snappy compression, and write a Java benchmark class to measure publish speed.

#### Application Properties (`application.yml`)
Add these performance properties to the producer configurations:

```yaml
spring:
  kafka:
    producer:
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.apache.kafka.common.serialization.StringSerializer
      properties:
        # High Throughput Settings
        linger.ms: 100 # Wait up to 100ms for batches to fill
        batch.size: 65536 # Increase batch size to 64KB
        compression.type: snappy # Snappy compression balances CPU and ratio
        buffer.memory: 67108864 # Increase memory buffer to 64MB
        max.block.ms: 30000 # Timeout after 30 seconds if buffer is full
```

#### Complete Producer Benchmark Java Code
Create the file [ProducerBenchmark.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/producer/ProducerBenchmark.java) with the following content:

```java
package com.springkafka.course.producer;

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.UUID;
import java.util.concurrent.CountDownLatch;

@Service
public class ProducerBenchmark {
    private static final Logger log = LoggerFactory.getLogger(ProducerBenchmark.class);

    private final KafkaTemplate<String, String> kafkaTemplate;

    public ProducerBenchmark(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    public void runBenchmark(int messageCount) throws InterruptedException {
        log.info("Starting producer benchmark test for {} messages...", messageCount);
        long startTime = System.currentTimeMillis();

        CountDownLatch latch = new CountDownLatch(messageCount);

        for (int i = 0; i < messageCount; i++) {
            String key = "key-" + i;
            String payload = "payload-data-" + UUID.randomUUID().toString();

            // Publish asynchronously
            kafkaTemplate.send("benchmark-topic", key, payload)
                .whenComplete((result, exception) -> {
                    latch.countDown();
                    if (exception != null) {
                        log.error("Publish error during benchmark", exception);
                    }
                });
        }

        latch.await(); // Wait for all messages to receive broker ACK
        long duration = System.currentTimeMillis() - startTime;
        double throughput = (messageCount / (duration / 1000.0));

        log.info("Benchmark Complete! Duration: {} ms | Throughput: {} messages/second", duration, throughput);
    }
}
```

---

### Lab 16.2 — Batch Consumer Listener Configuration

#### Scenario
We will configure a Spring Kafka consumer to read records in batches, enabling batch processing and configuring batch acknowledgements.

#### Application Properties (`application.yml`)
Add these performance properties to the consumer configurations:

```yaml
spring:
  kafka:
    listener:
      type: batch # Enable batch listener mode
      ack-mode: batch # Commit offsets after the entire batch is processed
    consumer:
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      max-poll-records: 500 # Fetch up to 500 records per poll call
      properties:
        fetch.min.bytes: 1024 # Wait for at least 1KB of data
        fetch.max.wait.ms: 500 # Wait up to 500ms if data size is below min bytes
```

#### Complete Batch Listener Java Code
Create the file [BatchOrderConsumer.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/consumer/BatchOrderConsumer.java) with the following content:

```java
package com.springkafka.course.consumer;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;

@Service
public class BatchOrderConsumer {
    private static final Logger log = LoggerFactory.getLogger(BatchOrderConsumer.class);

    // 1. Map list parameters to capture batch records
    @KafkaListener(id = "batch-order-listener", topics = "benchmark-topic")
    public void consumeBatch(List<String> payloads) {
        log.info("BATCH CONSUMER -> Fetched batch of {} records. Processing...", payloads.size());
        
        long startTime = System.currentTimeMillis();

        // Simulate database batch insert
        mockDatabaseBatchInsert(payloads);

        long duration = System.currentTimeMillis() - startTime;
        log.info("BATCH CONSUMER -> Processed batch of size {} in {} ms.", payloads.size(), duration);
    }

    private void mockDatabaseBatchInsert(List<String> records) {
        // In production, you would perform a batch JPA insert here
        try {
            Thread.sleep(50); // Simulate database insert duration
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
```

---

### Lab 16.3 — Dynamic Concurrency Configuration

#### Scenario
We will write a configuration class that adjusts consumer container concurrency dynamically based on the number of partitions of the target topic.

#### Complete Dynamic Concurrency Config Java Code
Create the file [DynamicConcurrencyConfig.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/config/DynamicConcurrencyConfig.java) with the following content:

```java
package com.springkafka.course.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Configuration
public class DynamicConcurrencyConfig {
    private static final Logger log = LoggerFactory.getLogger(DynamicConcurrencyConfig.class);

    // Inject partition count configuration (defaulting to 3 if not set)
    @Value("${app.kafka.orders-partitions:3}")
    private int ordersPartitionsCount;

    // Configure Concurrent factory mapping concurrency to partition count
    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, String> dynamicKafkaListenerContainerFactory(
            ConsumerFactory<String, String> consumerFactory) {
        
        ConcurrentKafkaListenerContainerFactory<String, String> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory);

        // Map concurrency exactly to partition count
        log.info("Scaling concurrency dynamically to match partition count: {}", ordersPartitionsCount);
        factory.setConcurrency(ordersPartitionsCount);

        return factory;
    }
}
```

---

### Step-by-Step Code Walkthrough & Parameter Configuration Tables

#### Step-by-Step Code Walkthrough

##### Lab 16.1 Walkthrough
1. **`linger.ms=100`**: Pauses publisher requests slightly, letting records combine.
2. **`CountDownLatch`**: Counts callbacks asynchronously to track benchmark completion.

##### Lab 16.2 Walkthrough
1. **`listener.type: batch`**: Configures container factory to output a List wrapper to listener parameters.
2. **`max-poll-records`**: Limits maximum batch sizes to prevent rebalance timeouts.

##### Lab 16.3 Walkthrough
1. **`setConcurrency`**: Spins up worker threads matching the partition count dynamically.

---

### Configuration Parameter Tables

#### Spring Boot Kafka Performance Properties

| Property Key | Expected Type | Description |
| :--- | :--- | :--- |
| `linger.ms` | `Long` | The duration in milliseconds the producer waits to batch records. |
| `batch.size` | `Integer` | The maximum size in bytes of a partition batch before sending. |
| `max-poll-records` | `Integer` | The maximum number of records returned in a single poll call. |
| `concurrency` | `Integer` | The number of consumer threads to spin up in the listener container. |

