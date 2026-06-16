# Module 10 — Transactional Outbox Pattern

In this module, we will discuss the Transactional Outbox Pattern. We will study the dual-write problem and explain how the Transactional Outbox Pattern provides eventual consistency in decoupled architectures. We will cover Change Data Capture (CDC) and how Debezium integrates with databases (MySQL/PostgreSQL) to read transaction logs and stream outbox records to Kafka topics. Finally, we will cover troubleshooting, answer 5 Socratic questions, and implement hands-on labs with complete code structures.

---

## 1. Academic Lecture: Dual Writes, Outbox Architectures & CDC

### Basic Level: The Dual-Write Problem & Outbox Architecture

#### The Dual-Write Problem
In microservices, a business transaction often requires two writes:
1. Update the local microservice database (e.g., insert an `Order` record).
2. Publish an event to Kafka (e.g., publish an `OrderCreated` event).

* **The Failure Scenario**: If you write to the database successfully but the network fails before you write to Kafka, the database is updated, but other microservices are never notified. If you write to Kafka first but the database transaction rolls back, Kafka contains invalid event details. This is known as the **Dual-Write Problem**.

```text
  [ Client Request ] ──► [ Order Service ]
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
    (1. DB Insert: SUCCESS)           (2. Kafka Send: FAILED)
             │                                 │
             ▼                                 ▼
     [ Database Commit ]              [ Out of Sync State ]
```

#### The Transactional Outbox Pattern
The Outbox Pattern resolves this by storing both writes inside the *same local database* within a single transaction:
1. When you create an `Order`, you write the order record to the `orders` table.
2. In the same transaction, you write a description of the event to a dedicated `outbox` table.
3. Because both inserts run inside a single ACID transaction, they either both succeed or both fail.
4. A separate process (called an **Outbox Publisher**) reads from the `outbox` table and publishes the messages to Kafka.

---

### Intermediate Level: Change Data Capture & Debezium

How do we capture inserts on the `outbox` table and stream them to Kafka?

#### Change Data Capture (CDC)
CDC is a technique that monitors transaction logs of a database (e.g., MySQL binlog or Postgres WAL) and captures inserts, updates, and deletes immediately as they happen.
* **Why tail logs?**: Tailing transaction logs is much faster and less resource-intensive than periodically querying (`SELECT * FROM outbox`) the database. Log tailing has near-zero latency and does not lock table rows.

#### Debezium
Debezium is a popular open-source CDC platform built on top of Kafka Connect. It listens to database transaction logs, translates database inserts into Kafka records, and writes them to target topics automatically.
* **For Outbox**: Debezium captures inserts into the `outbox` table, extracts the event payload, routes it to the correct Kafka topic, and then can be configured to delete the read record to keep the table clean.

---

### Advanced Level: Outbox Cleansing & Deduplication

#### Outbox Table Cleansing
An outbox table must not grow indefinitely. If you insert millions of events, the database disk will fill up.
* **Auto-Delete Pattern**: The Debezium Outbox Event Router transform can be combined with a clean-up database script or transaction hook. Some systems use a scheduled cron job (e.g., delete processed records older than 1 day), while other advanced CDC engines delete the outbox record immediately after it is written to the transaction log.

#### At-Least-Once Delivery & Deduplication
Since CDC engines read transaction logs and push to Kafka, they guarantee **At-Least-Once** delivery. If the connector restarts, it might read the log from the last checkpoint, causing duplicate messages to be written to Kafka.
* **Consumer Deduplication**: Consumers must treat incoming outbox events as idempotent. They should store processed `eventId` values in an internal cache (e.g., Redis) or database unique constraint, and discard incoming duplicates.

---

## 2. Theory & Production Best Practices

### Multi-Writes vs. Transactional Outbox

| Feature | Direct Multi-Writes (No Outbox) | Transactional Outbox + Debezium CDC |
| :--- | :--- | :--- |
| **Consistency Guarantee** | None (risk of out-of-sync states) | Strong Eventual Consistency |
| **Database Lock Overhead** | Low | Low (inserts into outbox table are fast) |
| **Infrastructure Complexity**| Low (no extra components) | High (requires Kafka Connect + Debezium) |
| **Failure Recovery** | Manual reconciliation | Automated (resumes from transaction log offset)|

### CDC Log-Tailing vs. Scheduled SQL Polling

| Metric | Log-Tailing (Debezium CDC) | Scheduled SQL Polling |
| :--- | :--- | :--- |
| **CPU/DB Load** | Low (reads log file, no table scans)| High (constant polling queries) |
| **Real-time Latency** | Milliseconds | Seconds/Minutes (depends on cron interval) |
| **Capture Schema Changes?** | Yes (automatically tracks schema evolution)| No (must rewrite queries manually) |

---

## 3. Common Errors & Troubleshooting

### 1. Debezium Log Offsets Lost
* **Symptom**: Debezium starts consuming from the beginning of the database binlog, sending millions of duplicate events to Kafka.
* **Root Cause**: The storage offset topic used by Kafka Connect was deleted, or the connector name was renamed, causing Debezium to lose its log index coordinates.
* **Fix**: Pre-configure Connect offsets to write to highly durable, replicated topics (`cleanup.policy=compact`), and avoid renaming active connectors without restoring offsets.

### 2. Database Log Retention Expiration
* **Symptom**: Debezium crashes with `binlog purged` or `WAL segment missing` errors.
* **Root Cause**: Debezium was offline (e.g. for maintenance) longer than the database log retention period. The database purged the logs Debezium needed to read.
* **Fix**: Set database binlog/WAL retention to at least 3-7 days, providing enough headroom for service recovery during extended outages.

### 3. Outbox Storage Space Exhaustion
* **Symptom**: Database crashes with "disk full" error.
* **Root Cause**: Outbox events are inserted faster than they are deleted, causing the table size to consume all disk space.
* **Fix**: Ensure a clean-up strategy is active. For example, run a scheduled SQL delete script: `DELETE FROM outbox_events WHERE created_at < NOW() - INTERVAL 12 HOUR`.

---

## 4. Socratic Review Questions

### Question 1
*Why is direct asynchronous publishing to Kafka inside a Spring `@Transactional` database method still vulnerable to the dual-write problem?*
* **Answer**: Because database commit happens *after* the Java method execution completes successfully. If `kafkaTemplate.send()` completes but the database commit fails immediately afterward due to a database constraint error, Kafka contains a message for a transaction that never existed.

### Question 5
*How does Debezium read transaction logs without causing performance locks on the active database tables?*
* **Answer**: It behaves like a replica instance. Databases write all commits to sequential log files (binlog/WAL) on disk. Debezium reads these log files sequentially in memory instead of executing queries or scanning table rows, preventing locks and minimizing overhead.

### Question 3
*What metadata attributes must be present in the Outbox Table schema to allow Debezium to route events to different topics?*
* **Answer**: The schema must contain `aggregate_type` (defines the destination topic name, e.g. `order` routes to `order-topic`), `aggregate_id` (serves as the partition key), and `payload` (holds the JSON event payload).

### Question 4
*How does a consumer handle duplicate outbox messages caused by a Debezium connector crash and restart?*
* **Answer**: By implementing an idempotent receiver. The consumer extracts the unique `eventId` from the message metadata and checks it against a unique database table or Redis cache. If the ID is already present, it skips processing.

### Question 5
*Can the Transactional Outbox Pattern preserve message ordering across different database tables?*
* **Answer**: Yes. Since all events are recorded in the single `outbox_events` table within serial transactions, they are written to the database transaction log in order. Debezium reads that log sequentially, preserving order across topics.

---

## 5. Hands-on Labs

### Lab 10.1 — Outbox Table Schema & JPA Entity

#### Scenario
We will define the database structure for our outbox pattern. We will write a SQL DDL script and a JPA Hibernate entity class representation.

#### SQL DDL Schema Definition
Execute this script on your local relational database:

```sql
CREATE TABLE outbox_event (
    event_id VARCHAR(36) PRIMARY KEY,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

#### Complete JPA Entity Java Code
Create the file [OutboxEvent.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/model/OutboxEvent.java) with the following content:

```java
package com.springkafka.course.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

@Entity
@Table(name = "outbox_event")
public class OutboxEvent {

    @Id
    @Column(name = "event_id", length = 36)
    private String eventId;

    @Column(name = "aggregate_type", nullable = false, length = 50)
    private String aggregateType;

    @Column(name = "aggregate_id", nullable = false, length = 50)
    private String aggregateId;

    @Column(name = "event_type", nullable = false, length = 100)
    private String eventType;

    // Mapping payload as a raw JSON string
    @Column(name = "payload", nullable = false, columnDefinition = "json")
    private String payload;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    public OutboxEvent() {}

    public OutboxEvent(String eventId, String aggregateType, String aggregateId, String eventType, String payload) {
        this.eventId = eventId;
        this.aggregateType = aggregateType;
        this.aggregateId = aggregateId;
        this.eventType = eventType;
        this.payload = payload;
        this.createdAt = LocalDateTime.now();
    }

    // Getters and Setters
    public String getEventId() { return eventId; }
    public String getAggregateType() { return aggregateType; }
    public String getAggregateId() { return aggregateId; }
    public String getEventType() { return eventType; }
    public String getPayload() { return payload; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
```

---

### Lab 10.2 — Atomic Transactional Publisher

#### Scenario
We will write a service class that processes orders. It will save the order entity and insert the event record into the outbox table inside a single database transaction.

#### Complete JPA Order Service Java Code
Create the file [OrderService.java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/java/com/springkafka/course/service/OrderService.java) with the following content:

```java
package com.springkafka.course.service;

import com.springkafka.course.model.OutboxEvent;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import jakarta.persistence.EntityManager;
import java.util.UUID;

@Service
public class OrderService {

    private final EntityManager entityManager;

    public OrderService(EntityManager entityManager) {
        this.entityManager = entityManager;
    }

    // 1. Process order and record outbox event inside unified transaction
    @Transactional
    public void createOrder(String customerId, double amount) {
        String orderId = UUID.randomUUID().toString();
        
        // Mock business operation: persist Order
        logBusinessOrder(orderId, customerId, amount);

        // Define event payload details in JSON
        String eventPayload = String.format(
            "{\"orderId\":\"%s\",\"customerId\":\"%s\",\"amount\":%.2f}",
            orderId, customerId, amount
        );

        // 2. Instantiate OutboxEvent
        OutboxEvent outboxEvent = new OutboxEvent(
            UUID.randomUUID().toString(),
            "order", // Aggregate type helps Debezium route to "order" topic
            orderId, // Partition key matches Order ID to preserve ordering
            "OrderCreated",
            eventPayload
        );

        // 3. Persist the outbox record
        entityManager.persist(outboxEvent);
        
        // Both database and outbox records will commit atomically here
    }

    private void logBusinessOrder(String orderId, String customerId, double amount) {
        // In production, you would persist an actual Order Entity here
        System.out.println("Persisted business order -> ID: " + orderId + " | Customer: " + customerId);
    }
}
```

---

### Lab 10.3 — Debezium Connector Configuration

#### Scenario
We will configure Debezium MySQL Connector to monitor the `outbox_event` table and stream inserts to Kafka.

#### Complete JSON Configuration (Debezium MySQL Connector)
Create the file [debezium-outbox-mysql.json](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/src/main/resources/debezium-outbox-mysql.json) with the following content:

```json
{
  "name": "mysql-outbox-connector",
  "config": {
    "connector.class": "io.debezium.connector.mysql.MySqlConnector",
    "tasks.max": "1",
    "database.hostname": "localhost",
    "database.port": "3306",
    "database.user": "debezium",
    "database.password": "dbz_pass",
    "database.server.id": "184054",
    "database.server.name": "mysql_server",
    
    // Whitelist outbox table specifically
    "table.whitelist": "inventory_db.outbox_event",
    
    // Transform parameters to route payload data directly
    "transforms": "outbox",
    "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
    "transforms.outbox.route.by.field": "aggregate_type",
    "transforms.outbox.key.field": "aggregate_id",
    "transforms.outbox.value.field": "payload",
    
    // Database schema changes behavior
    "database.history.kafka.topic": "schema-changes.mysql_server",
    "database.history.kafka.bootstrap.servers": "localhost:9092"
  }
}
```

---

### Step-by-Step Code Walkthrough & Parameter Configuration Tables

#### Step-by-Step Code Walkthrough

##### Lab 10.1 Walkthrough
1. **Outbox Schema**: Table contains fields to capture event identifiers, payload context in JSON format, and aggregate details.
2. **`OutboxEvent` JPA Entity**: Defines table metadata mapping.

##### Lab 10.2 Walkthrough
1. **`@Transactional`**: Coordinates database commits. If persistence throws exceptions, both inserts (Order and OutboxEvent) rollback, leaving the database consistent.
2. **`aggregateType`**: Handled by Debezium Event Router transform to define topic targets dynamically.

##### Lab 10.3 Walkthrough
1. **`MySqlConnector`**: Connector tails MySQL binary log updates.
2. **`transforms.outbox.type`**: Activates Debezium Outbox router. It extracts the raw JSON payload and maps it directly as the Kafka record value, discarding database log wraps.
3. **`route.by.field`**: Directs records to topics matching the field value (e.g. `aggregate_type` value `"order"` routes message to topic `"order"`).

---

### Configuration Parameter Tables

#### Debezium Connector JSON Configuration Properties

| Property Key | Expected Type | Description |
| :--- | :--- | :--- |
| `connector.class` | `String` | Fully qualified class path of the target database connector. |
| `table.whitelist` | `String` | Comma-separated list specifying the database and tables to monitor. |
| `transforms.outbox.type` | `Class` | The Debezium Outbox event routing class path. |
| `transforms.outbox.route.by.field`| `String` | Database column name holding aggregate type info to route topic names. |
| `transforms.outbox.key.field` | `String` | Database column name holding entity IDs to assign Kafka partition keys. |
| `transforms.outbox.value.field` | `String` | Database column name containing JSON payloads to assign Kafka record values. |

