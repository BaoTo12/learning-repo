# Module 13: Persistence and Chat History

Real-time messaging is only one half of the user experience. When users open an application, they expect to see their chat history instantly. They want to know which messages are new, who has read their sent messages, and see a consistent order of conversation across all devices.

This module covers the architecture of message persistence and history replay. We will analyze database design strategies (SQL vs. NoSQL), explore Snowflake ID generation for distributed message ordering, design schemas for read receipts and unread counts, and build a Slack-like history service in Spring Boot.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Design database schemas** (SQL and NoSQL) optimized for write-heavy chat message logs.
2. **Implement Snowflake ID generation** to guarantee monotonic message ordering across distributed server nodes.
3. **Model read receipts and unread message counts** in database structures.
4. **Deploy offline synchronization strategies** to replay missed messages when a client reconnects.
5. **Build a paginated chat history repository** using Spring Data JPA.

---

## 1. Database Design for Real-Time Messages

Chat applications present a unique database workload: **extremely write-heavy** with bursts of read queries when users open channels.

### 1. Relational Databases (e.g. PostgreSQL)
- **Advantages**: Strong consistency, robust indexing, and expressive queries for aggregations (like calculating unread counts).
- **Index Design**: To query history quickly, you must define compound indexes:
  $$\text{Index} = \{\text{roomId}, \text{timestamp}\}$$
- **Limitations**: Slower write throughput under extreme concurrency because SQL databases require maintaining transactional indexes on disk.

### 2. NoSQL Document Stores (e.g. MongoDB)
- **Advantages**: High write throughput. Easy to store unstructured metadata (embedded links, rich media).
- **Indexing**: Similar to relational databases, compound indexes are required on `{roomId: 1, timestamp: -1}`.

### 3. Wide-Column Stores (e.g. Apache Cassandra / ScyllaDB)
- **Advantages**: Designed for write-heavy logging. Scales horizontally to handle millions of writes per second.
- **Partition Key Layout**: Partition data by `roomId`, and use `timestamp` as the clustering key:
  ```sql
  PRIMARY KEY (room_id, message_id) WITH CLUSTERING ORDER BY (message_id DESC);
  ```
  This guarantees that messages in the same room are stored contiguously on disk, optimizing history queries.

---

## 2. Strict Message Ordering and Snowflake IDs

In a chat room, displaying messages out of order (e.g. a response arriving before the question) destroys the user experience.

### Why Auto-Increment IDs Fail in Distributed Systems
If your application runs on three server instances:
- Using a relational database's auto-increment ID (`BIGSERIAL`) creates a bottleneck because all three servers must coordinate with the database to fetch the next ID, limiting write throughput.
- Relying on system clocks (e.g., `System.currentTimeMillis()`) is unreliable. System clocks drift, and two messages sent at the same millisecond on different servers can receive identical timestamps, causing ordering conflicts.

### The Twitter Snowflake ID Solution
A **Snowflake ID** is a 64-bit unsigned integer generated locally on each server instance without database coordination. It guarantees uniqueness and monotonic ordering:

```
 1 bit   41 bits (Timestamp)           10 bits (Worker ID)  12 bits (Sequence)
+-----+-------------------------------+--------------------+------------------+
|  0  | 01101011...                   | 0001011010         | 000000000101     |
+-----+-------------------------------+--------------------+------------------+
```

- **Timestamp (41 bits)**: Milliseconds elapsed since a custom epoch, providing $\approx 69$ years of uniqueness.
- **Worker ID (10 bits)**: Unique ID assigned to each server node (allowing up to 1024 servers).
- **Sequence Number (12 bits)**: Local counter incremented if multiple IDs are generated within the same millisecond on the same worker node (allowing 4096 IDs per millisecond).
- *Result*: Because the leading bits represent the timestamp, Snowflake IDs naturally sort chronologically, ensuring strict message ordering.

---

## 3. Read Receipts and Unread Message Counts

Tracking read status in a group chat with 100 users requires careful schema design to avoid database write fatigue:

- **Bad Practice**: Inserting a read status row for every message and every user (creating $M \times U$ rows).
- **Good Practice (Mark-Point Schema)**:
  - Track only the **last read message ID** (or timestamp) for each user in a room.
  - **Unread Count Query**: Count messages in the room where the message ID is greater than the user's last read message ID:
    ```sql
    SELECT COUNT(*) FROM messages 
    WHERE room_id = :roomId AND message_id > :lastReadMessageId;
    ```

---

## 4. History Replay & Offline Sync Strategies

When a client reconnects after being offline:
1. **Initial History Fetch**: The client sends a subscription request. The server queries the database for the last 20 messages in the room and returns them to populate the client's screen.
2. **Pagination (Infinite Scroll)**: When the user scrolls up, the client requests older messages by passing the oldest message ID in its memory (`message_id < oldest_id`), preventing offset pagination performance issues.
3. **Offline Sync**: If the client was offline for 10 minutes, it passes its `last_seen_message_id` during reconnection. The server queries all messages in the user's active rooms where `message_id > last_seen_message_id` and replays them to catch the client up.

---

## 5. Hands-On Mini Project: Slack-Like History Service

We will build a complete, compilable Spring Boot chat history application.

The project contains:
- **JPA Entities**: `ChatMessageEntity` storing messages with chronological Snowflake IDs, and `ReadReceiptEntity` tracking user read checkpoints.
- **JPA Repositories**: Optimized queries for room history pagination and unread counts.
- **`HistoryService`**: Logic to save messages, retrieve paginated history, mark messages as read, and count unread messages.
- **`HistoryController`**: REST endpoints exposing history queries.

### Code Implementation:

#### 1. Message Database Entity (`ChatMessageEntity.java`)

```java
package com.example.realtime.history.entity;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "chat_messages", indexes = {
    @Index(name = "idx_room_msg", columnList = "roomId, id DESC")
})
public class ChatMessageEntity {

    @Id
    private Long id; // Snowflake ID (Chronological)

    @Column(nullable = false)
    private String roomId;

    @Column(nullable = false)
    private String sender;

    @Column(nullable = false, length = 2000)
    private String content;

    @Column(nullable = false)
    private Instant timestamp;

    public ChatMessageEntity() {
        this.timestamp = Instant.now();
    }

    public ChatMessageEntity(Long id, String roomId, String sender, String content) {
        this.id = id;
        this.roomId = roomId;
        this.sender = sender;
        this.content = content;
        this.timestamp = Instant.now();
    }

    // --- Getters and Setters ---
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getRoomId() { return roomId; }
    public void setRoomId(String roomId) { this.roomId = roomId; }

    public String getSender() { return sender; }
    public void setSender(String sender) { this.sender = sender; }

    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }

    public Instant getTimestamp() { return timestamp; }
    public void setTimestamp(Instant timestamp) { this.timestamp = timestamp; }
}
```

#### 2. Read Receipt Database Entity (`ReadReceiptEntity.java`)

```java
package com.example.realtime.history.entity;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "read_receipts", uniqueConstraints = {
    @UniqueConstraint(columnNames = {"roomId", "username"})
})
public class ReadReceiptEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String roomId;

    @Column(nullable = false)
    private String username;

    @Column(nullable = false)
    private Long lastReadMessageId; // Last read Snowflake ID

    @Column(nullable = false)
    private Instant lastReadTime;

    public ReadReceiptEntity() {
        this.lastReadTime = Instant.now();
    }

    public ReadReceiptEntity(String roomId, String username, Long lastReadMessageId) {
        this.roomId = roomId;
        this.username = username;
        this.lastReadMessageId = lastReadMessageId;
        this.lastReadTime = Instant.now();
    }

    // --- Getters and Setters ---
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getRoomId() { return roomId; }
    public void setRoomId(String roomId) { this.roomId = roomId; }

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public Long getLastReadMessageId() { return lastReadMessageId; }
    public void setLastReadMessageId(Long lastReadMessageId) { this.lastReadMessageId = lastReadMessageId; }

    public Instant getLastReadTime() { return lastReadTime; }
    public void setLastReadTime(Instant lastReadTime) { this.lastReadTime = lastReadTime; }
}
```

#### 3. JPA Message Repositories

```java
package com.example.realtime.history.repository;

import com.example.realtime.history.entity.ChatMessageEntity;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Slice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.util.List;

public interface ChatMessageRepository extends JpaRepository<ChatMessageEntity, Long> {

    /**
     * Retrieves paginated room history.
     * Slice is preferred over Page to avoid executing expensive COUNT queries on large message logs.
     */
    Slice<ChatMessageEntity> findByRoomIdAndIdLessThanOrderByIdDesc(String roomId, Long messageId, Pageable pageable);

    Slice<ChatMessageEntity> findByRoomIdOrderByIdDesc(String roomId, Pageable pageable);

    /**
     * Counts unread messages in a room starting after a specific last read message ID.
     */
    @Query("SELECT COUNT(m) FROM ChatMessageEntity m WHERE m.roomId = :roomId AND m.id > :lastReadId")
    long countUnreadMessages(@Param("roomId") String roomId, @Param("lastReadId") Long lastReadId);
}
```

#### 4. JPA Read Receipt Repositories

```java
package com.example.realtime.history.repository;

import com.example.realtime.history.entity.ReadReceiptEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface ReadReceiptRepository extends JpaRepository<ReadReceiptEntity, Long> {
    Optional<ReadReceiptEntity> findByRoomIdAndUsername(String roomId, String username);
}
```

#### 5. Chat History Coordinator Service

```java
package com.example.realtime.history.service;

import com.example.realtime.history.entity.ChatMessageEntity;
import com.example.realtime.history.entity.ReadReceiptEntity;
import com.example.realtime.history.repository.ChatMessageRepository;
import com.example.realtime.history.repository.ReadReceiptRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Slice;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.Instant;
import java.util.Collections;
import java.util.List;

@Service
public class HistoryService {

    private final ChatMessageRepository messageRepository;
    private final ReadReceiptRepository receiptRepository;

    public HistoryService(ChatMessageRepository messageRepository, ReadReceiptRepository receiptRepository) {
        this.messageRepository = messageRepository;
        this.receiptRepository = receiptRepository;
    }

    /**
     * Saves a new incoming message to the database.
     */
    @Transactional
    public ChatMessageEntity saveMessage(Long snowflakeId, String roomId, String sender, String content) {
        ChatMessageEntity entity = new ChatMessageEntity(snowflakeId, roomId, sender, content);
        return messageRepository.save(entity);
    }

    /**
     * Marks the user's progress in a room by updating their read checkpoint.
     */
    @Transactional
    public void markAsRead(String roomId, String username, Long messageId) {
        ReadReceiptEntity receipt = receiptRepository.findByRoomIdAndUsername(roomId, username)
                .orElse(new ReadReceiptEntity(roomId, username, messageId));
        
        // Update to the latest message ID
        if (messageId > receipt.getLastReadMessageId()) {
            receipt.setLastReadMessageId(messageId);
            receipt.setLastReadTime(Instant.now());
            receiptRepository.save(receipt);
        }
    }

    /**
     * Retrieves unread message counts for a user in a specific room.
     */
    public long getUnreadCount(String roomId, String username) {
        return receiptRepository.findByRoomIdAndUsername(roomId, username)
                .map(receipt -> messageRepository.countUnreadMessages(roomId, receipt.getLastReadMessageId()))
                .orElse(0L); // Assumes 0 if no read receipt exists
    }

    /**
     * Retrieves paginated room history.
     */
    public List<ChatMessageEntity> getRoomHistory(String roomId, Long oldestSeenId, int pageSize) {
        Slice<ChatMessageEntity> slice;
        if (oldestSeenId == null) {
            slice = messageRepository.findByRoomIdOrderByIdDesc(roomId, PageRequest.of(0, pageSize));
        } else {
            slice = messageRepository.findByRoomIdAndIdLessThanOrderByIdDesc(roomId, oldestSeenId, PageRequest.of(0, pageSize));
        }
        
        List<ChatMessageEntity> list = slice.getContent();
        // Reverse content list to restore chronological display order on client
        Collections.reverse(list);
        return list;
    }
}
```

---

## 6. Common Mistakes & Debugging Scenarios

### Scenario A: Slow History Queries (Database CPU Exhaustion)
* **The Problem**: As chat logs grow to millions of rows, loading history in a room takes several seconds, causing high database CPU utilization.
* **Why it happens**: The database is executing full table scans because it lacks a compound index. If the query filters by `roomId` and sorts by `id DESC` (or timestamp), but only has single-column indexes on `roomId`, the database must fetch all rows matching the room ID and sort them in memory.
* **The Fix**: Define a compound database index combining the partition query column and the sort column:
  `CREATE INDEX idx_room_msg ON chat_messages (room_id, id DESC);`

### Scenario B: Count Query Performance Bottlenecks
* **The Problem**: A developer uses Spring Data's `Page<T>` return type to load message history. The API response times degrade as the room message count increases.
* **Why it happens**: Returning a `Page<T>` forces Spring Data JPA to run an expensive `SELECT COUNT(*)` query alongside the select query to calculate total pages. This is inefficient for large message logs.
* **The Fix**: Switch the repository return type from `Page<T>` to `Slice<T>`. A `Slice` only queries `pageSize + 1` rows to check if a next page exists, eliminating the need to run count queries.

---

## 7. Technical Interview Questions

### Question 1: SQL vs. Wide-Column Stores for Chat
*Why are wide-column stores (like Apache Cassandra) preferred over relational databases for scaling chat logs to millions of active users?*

**Answer**:
Relational databases write data to B-Tree indexes on disk, which requires random disk I/O operations and lock synchronization to maintain constraints under high concurrency. 

Wide-column stores like Cassandra utilize Log-Structured Merge (LSM) Trees. They write incoming data sequentially to an in-memory buffer (Memtable) and flush it sequentially to disk (SSTables) without updating existing blocks. This enables extremely high write throughput. 

Additionally, Cassandra partition keys allow storing a room's messages contiguously on disk sorted by clustering keys, optimizing history range queries.

---

### Question 2: Snowflake IDs in Distributed Systems
*How does a Snowflake ID guarantee unique, chronological message ordering across a cluster of server nodes without using database locks?*

**Answer**:
A Snowflake ID is a 64-bit unsigned integer generated locally on each server node:
- The leading **41 bits** represent the current timestamp in milliseconds. Because the time component is at the front, IDs generated later are naturally larger, guaranteeing chronological sorting.
- The next **10 bits** represent a unique Worker ID assigned to the server node, preventing two different servers from generating identical IDs at the same millisecond.
- The final **12 bits** represent a local sequence counter that increments if multiple IDs are generated within the same millisecond on the same worker node, preventing duplicates.
This structure enables servers to generate unique, chronologically ordered IDs locally with zero network coordination.

---

## Summary
- **Message Persistence** requires indexing strategies: relational databases require compound indexes on `{roomId, id DESC}`, while Cassandra utilizes partition and clustering keys.
- **Distributed Ordering** is resolved using **Snowflake IDs**, which pack timestamps, worker IDs, and sequence counters into unique 64-bit integers.
- **Read status tracking** is optimized using a **Mark-Point Schema** (tracking only the last read message ID per user) to minimize database write traffic.
- **History Queries** should return a `Slice<T>` instead of `Page<T>` to avoid executing expensive `COUNT` queries on large tables.
- **Replay Strategies** use keyset pagination (`id < oldestSeenId`) to fetch older messages efficiently during infinite scrolling.
