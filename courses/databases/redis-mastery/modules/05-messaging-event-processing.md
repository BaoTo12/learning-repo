# Module 05: Messaging and Event Processing: Streams & Pub/Sub

## 1. What Problem This Module Solves

Microservices need to communicate asynchronously to decouple dependencies and scale processing.
*   **Broadcasting Events**: Dispatches updates to multiple services concurrently.
*   **Durable Message Queuing**: Distributes tasks to worker pools reliably, ensuring messages are not lost if a worker fails.

Redis provides two distinct messaging models: **Pub/Sub** and **Streams**. This module explains how they work, how to implement consumer groups, and compares them with Kafka and RabbitMQ.

---

## 2. Why Redis is Used Instead of Alternatives

*   **Over Kafka/RabbitMQ (for simple messaging)**: Deploying and managing Kafka or RabbitMQ clusters requires substantial infrastructure overhead. If your system already uses Redis for caching, leveraging Redis Pub/Sub or Streams provides a lightweight messaging option with sub-millisecond delivery latency.

---

## 3. Redis Pub/Sub vs. Redis Streams

Redis provides two messaging features with different design goals:

```
[Redis Pub/Sub (Fire-and-Forget)]
Publisher ───► Redis Channel ───► Subscriber A (Online - Receives)
                             ───► Subscriber B (Offline - Misses Message)

[Redis Streams (Append-Only Log + Consumer Groups)]
Producer ───► Stream Log ───► Consumer Group
                                 ├── Worker 1 (Pulls Msg 1, sends ACK)
                                 └── Worker 2 (Pulls Msg 2, crashes before ACK)
                                        └─► Reclaimed by Worker 1 via XCLAIM
```

### 3.1 Redis Pub/Sub (Fire-and-Forget)
*   *Mechanics*: A publisher sends messages to a channel. Active subscribers receive them.
*   *Limitations*: Fire-and-forget. Redis does not persist Pub/Sub messages. If a subscriber is offline during transmission, it misses the message.

### 3.2 Redis Streams (Append-Only Log)
*   *Mechanics*: An append-only log structure. Messages are assigned unique IDs (e.g. `1686574200000-0`).
*   *Durability*: Messages are persisted based on Redis persistence settings.
*   *Consumer Groups*: Allows multiple workers to share the processing load. Each message is delivered to only one worker in the group.
*   *Reliability*: Workers must explicitly acknowledge (`XACK`) message receipt. Unacknowledged messages are tracked in a **Pending Entries List (PEL)** and can be claimed by other workers if a consumer crashes.

---

## 4. Architectural Comparison: Streams vs. Kafka vs. RabbitMQ

| Dimension | Redis Streams | Apache Kafka | RabbitMQ |
| :--- | :--- | :--- | :--- |
| **Storage Model** | In-Memory (Optional RDB/AOF persistence). | Disk-based Commit Log. | Queue-based (RAM/Disk). |
| **Message Retention** | Capped stream size (using `MAXLEN`). | Time-based or size-based retention policies. | Removed from queue immediately after ACK. |
| **Routing Patterns** | Basic stream name routing. | Topic-partition routing. | Flexible routing keys (Direct, Fanout, Topic exchanges). |
| **Throughput & Scale** | Extremely High QPS (limited by single-node RAM). | High (horizontal scaling via partitions). | Moderate (limited by queue synchronization). |

---

## 5. Hands-on Exercises

1.  Write a script to monitor unacknowledged messages in a Redis Stream using the `XPENDING` command.
2.  Trigger a worker crash during stream processing and use the `XCLAIM` command to reclaim the pending messages.

---

## 6. Mini-Project: Reliable Event Consumer Group

**Scenario**: You are building an order processing system. When an order is placed, an event is written to a Redis Stream. You must implement a Spring worker pool that:
1.  Pulls events from a Consumer Group.
2.  Processes the event and sends an acknowledgement (`XACK`).
3.  Runs a background scheduler to scan for stalled messages using `XPENDING` and reclaim them using `XCLAIM`.

### 1. Spring Stream Listener & Configuration (`streams/StreamConsumer.java`)
```java
package com.example.redis.streams;

import org.springframework.data.redis.connection.stream.MapRecord;
import org.springframework.data.redis.connection.stream.RecordId;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.stream.StreamListener;
import org.springframework.stereotype.Service;

@Service
public class OrderStreamListener implements StreamListener<String, MapRecord<String, String, String>> {

    private final StringRedisTemplate redisTemplate;
    private static final String STREAM_KEY = "orders:stream";
    private static final String GROUP_NAME = "order-processors";

    public OrderStreamListener(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    @Override
    public void onMessage(MapRecord<String, String, String> message) {
        RecordId id = message.getId();
        String orderId = message.getValue().get("orderId");
        String amount = message.getValue().get("amount");

        try {
            System.out.printf("Processing Order [%s]: ID=%s, Amount=%s\n", id, orderId, amount);
            
            // Simulate processing logic
            
            // 2. Acknowledge message processing completion
            redisTemplate.opsForStream().acknowledge(STREAM_KEY, GROUP_NAME, id);
            
        } catch (Exception e) {
            System.err.printf("Failed to process message %s: %s\n", id, e.getMessage());
            // Do NOT call XACK, letting it remain in the PEL for recovery
        }
    }
}
```

### 2. Backlog Recovery Scheduler (`streams/BacklogRecoveryScheduler.java`)
```java
package com.example.redis.streams;

import org.springframework.data.redis.connection.stream.PendingMessage;
import org.springframework.data.redis.connection.stream.PendingMessages;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.domain.Range;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import java.time.Duration;
import java.util.List;

@Component
public class BacklogRecoveryScheduler {

    private final StringRedisTemplate redisTemplate;
    private static final String STREAM_KEY = "orders:stream";
    private static final String GROUP_NAME = "order-processors";
    private static final String RECOVERER_NAME = "recovery-worker-1";

    public BacklogRecoveryScheduler(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    @Scheduled(fixedDelay = 10000) // Scan backlog every 10 seconds
    public void recoverPendingMessages() {
        // 1. Fetch unacknowledged messages (Pending Entries List - PEL)
        PendingMessages pending = redisTemplate.opsForStream()
            .pending(STREAM_KEY, GROUP_NAME, Range.unbounded(), 10);

        if (pending.isEmpty()) {
            return;
        }

        for (PendingMessage pm : pending) {
            // Check if the message has been pending for over 30 seconds
            if (pm.getElapsedTimeSinceLastDelivery().compareTo(Duration.ofSeconds(30)) > 0) {
                System.out.printf("Reclaiming stalled message [%s] from consumer [%s]\n", 
                    pm.getIdAsString(), pm.getConsumerName());

                // 2. Claim message ownership to process it
                redisTemplate.opsForStream().claim(
                    STREAM_KEY,
                    GROUP_NAME,
                    RECOVERER_NAME,
                    Duration.ofSeconds(30),
                    pm.getId()
                );
            }
        }
    }
}
```

---

## 7. Interview Questions

### Q1: What is the Pending Entries List (PEL) in Redis Streams? How does it ensure reliable processing?
**Answer**: The Pending Entries List (PEL) is an internal Redis metadata structure that tracks messages delivered to consumers but not yet acknowledged (using `XACK`). 
For each pending message, the PEL records its ID, the assigned consumer, and the elapsed time since its last delivery. This ensures reliability: if a consumer crashes mid-processing, the message remains in the PEL and can be identified and reclaimed by other active workers using the `XCLAIM` command.

### Q2: Why is Redis Pub/Sub unsuitable for implementing transactional message queues?
**Answer**: Redis Pub/Sub is a fire-and-forget broadcasting protocol. Messages are not persisted on disk or buffered in memory queues. If a subscriber is offline during transmission, the message is lost. Additionally, Pub/Sub lacks acknowledgement patterns and message recovery features, making it unsuitable for transactional queuing.

### Q3: What is the risk of running capped streams (using MAXLEN) without strict memory budget limits?
**Answer**: Although capped streams limit memory usage, using `MAXLEN` can lead to data loss if the inflow of messages exceeds processing speeds. If the stream fills up, Redis automatically evicts the oldest events.
**Best Practice**: Ensure your stream processing speeds can handle traffic spikes, and set alert thresholds on stream sizes using Actuator metrics.
