# Chapter 12: Event Sourcing Paradigm and Event Stores

In a traditional application, the database stores the current state of business entities. When an entity is updated, its old state is overwritten. While this approach is simple, it makes it difficult to implement auditing, debug past system states, or reconstruct historical data. To solve these limitations, we use the **Event Sourcing** paradigm.

This chapter covers the technical architecture of Event Sourcing. We will explore how event sourcing stores state as a sequence of immutable events rather than overwriting table rows. We will analyze the process of reconstructing (rehydrating) aggregates, examine command processing and event application methods (`process()` and `apply()`), implement **Optimistic Concurrency Control** (OCC) to prevent concurrent write conflicts, configure **Event-Sourced Sagas**, manage **Schema Evolution via Upcasting**, address **GDPR Data Deletion (Crypto-shredding)**, and build a custom event store, snapshot repository, and event-sourced aggregate in Java.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Compare traditional state persistence with the event sourcing paradigm.
2. Structure aggregate business logic into command validation (`process()`) and state updates (`apply()`).
3. Reconstruct (rehydrate) aggregate states by replaying historical events.
4. Optimize rehydration performance using **Snapshots** and the Memento pattern.
5. Apply **Upcasting** components to manage event schema evolution.
6. Design a relational database schema for a custom **Event Store**.
7. Implement **Optimistic Concurrency Control** (OCC) using event sequence version numbers to prevent race conditions.
8. Implement an OCC query update retry mechanism with exponential backoff.
9. Integrate event sourcing with **Sagas** using reply pseudo-events and command dispatching.
10. Outline data deletion strategies in append-only logs (tombstones and crypto-shredding).
11. Write a functional event-sourced aggregate, snapshot manager, and event store in Java.

---

## 12.1 Traditional Persistence vs. Event Sourcing

Traditional database architectures map domain classes to tables, object fields to columns, and runtime instances to rows:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//3d236de9-ab59-49b0-b8e6-28d5c591919d/markdown_4/imgs/img_in_image_box_199_274_918_578.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A49Z%2F-1%2F%2F5043b83857af5ae34c41a8f54e7390214bdf85e7374ad95c55d3a5bb9868ca0b" alt="Image" width="67%" /></div>
<div style="text-align: center;">Figure 6.1: The traditional approach to persistence maps classes to tables and objects to rows in those tables.</div>

### Drawbacks of Traditional Persistence:
* **Object-Relational Impedance Mismatch**: The tabular database schema conflicts with the graph model of rich domain objects.
* **Lack of Aggregate History**: Updating a row overwrites the prior state, making history retrieval impossible without custom logging.
* **Tedious & Error-Prone Auditing**: Audit logging must be manually written in the service layer, which frequently diverges from real schema changes.
* **Domain Event Publishing is Bolted On**: Transactions updating entities cannot atomically guarantee message publishing without complex transactional outbox modules.

### The Event Sourcing Solution
**Event Sourcing** persists each aggregate instance as a sequence of immutable, state-changing events in an append-only database table:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7bb20bdd-5007-4287-88e2-85e2fde7cfb8/markdown_4/imgs/img_in_image_box_203_106_926_416.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A46Z%2F-1%2F%2F270b79ae71a2968a0a21f220014bf00b8655070ac020088a4e82975c3faa854b" alt="Image" width="68%" /></div>
<div style="text-align: center;">Figure 6.2: Event sourcing persists each aggregate as a sequence of events. A RDBMS-based application can, for example, store the events in an EVENTS table.</div>

---

## 12.2 Reconstructing Aggregate State (Rehydration)

To load an aggregate, the application loads its event stream from the database and replays the events in chronological order:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f278beee-daec-4d93-a0c4-c6702d77efef/markdown_3/imgs/img_in_image_box_206_111_713_354.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A49Z%2F-1%2F%2F3c0e0348afe771c6e7bca2a6c73117ef9c0872f77ae08400aeb455f212c16a22" alt="Image" width="47%" /></div>
<div style="text-align: center;">Figure 6.3: Applying event E when the Order is in state S must change the Order state to S'. The event must contain the data necessary to perform the state change.</div>

---

### Command Processing and Event Application Model
In event sourcing, aggregate update methods are refactored into two parts:
1. **Command Processing (`process()`)**: Validates the command payload and returns a list of events without modifying aggregate state.
2. **Event Application (`apply()`)**: Updates state variables based on events. This step is guaranteed to succeed:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f278beee-daec-4d93-a0c4-c6702d77efef/markdown_3/imgs/img_in_image_box_202_664_653_965.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A49Z%2F-1%2F%2F89bd4e415d0062a12bb18b9d7ef838ff089bb97b4a679764f0d53c2e80303023" alt="Image" width="42%" /></div>
<div style="text-align: center;">Figure 6.4: Processing a command generates events without changing the state of the aggregate. An aggregate is updated by applying an event.</div>

Here is a visual map of this splitting technique:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//f278beee-daec-4d93-a0c4-c6702d77efef/markdown_4/imgs/img_in_image_box_112_438_932_1105.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A49Z%2F-1%2F%2Fe97d16e01edcce06231c6ba814129986121a8cadc332581f42a7e647d6045c81" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 6.5: Event sourcing splits a method that updates an aggregate into a process() method, which takes a command and returns events, and one or more apply() methods, which take an event and update the aggregate.</div>

---

### Optimizing Performance with Snapshots
If an aggregate has thousands of events, replaying the entire stream on every request introduces significant latency. To optimize performance, the system periodically saves a **Snapshot** (e.g., JSON representation) representing the aggregate's state:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//27f4ae15-40b5-49ec-ac05-5bb6d175b020/markdown_4/imgs/img_in_image_box_200_931_862_1162.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A39Z%2F-1%2F%2F0ddf8ae9f8750f2124a41454d1b7e39586b1a190832d0a590745f4f8dad47aea" alt="Image" width="62%" /></div>
<div style="text-align: center;">Figure 6.7: Using a snapshot improves performance by eliminating the need to load all events. An application only needs to load the snapshot and the events that occur after it.</div>

The application loads the latest snapshot and replays only the events that occurred after the snapshot:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//27f4ae15-40b5-49ec-ac05-5bb6d175b020/markdown_3/imgs/img_in_image_box_181_815_871_1142.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A38Z%2F-1%2F%2F684bdf54335b0557afcab39102647eca47eaf36775ba07c5fdc6ec94d85831d5" alt="Image" width="64%" /></div>
<div style="text-align: center;">Figure 6.8: The Customer Service recreates the Customer by deserializing the snapshot's JSON and then loading and applying events #104 through #106.</div>

---

## 12.3 Event Store Schema, Concurrency Control, and Publishing

An event store is a hybrid of a database and a message broker. It stores events in an append-only database table, and publishes them to a message broker (like Kafka):

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//051d9607-e07e-4074-9549-b054a8848db9/markdown_0/imgs/img_in_image_box_200_109_930_1046.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A38Z%2F-1%2F%2F98ea75c92c5db6fde7ab145f8df65ecf91e92ec5fc1850119e7a83d47f9a1df2" alt="Image" width="77%" /></div>
<div style="text-align: center;">Figure 6.9: The architecture of Eventuate Local. It consists of an event database (such as MySQL) that stores the events, an event broker (like Apache Kafka) that delivers events to subscribers, and an event relay that publishes events stored in the event database to the event broker.</div>

### Database Schema Design
We implement a custom event store using a relational database with the following table schema:

```sql
CREATE TABLE events (
    event_id VARCHAR(100) PRIMARY KEY,
    aggregate_type VARCHAR(255) NOT NULL,
    aggregate_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(255) NOT NULL,
    event_payload VARCHAR(4000) NOT NULL,
    sequence_number INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Unique constraint to prevent concurrent write conflicts
    UNIQUE(aggregate_id, sequence_number)
);

CREATE TABLE snapshots (
    aggregate_id VARCHAR(255) PRIMARY KEY,
    aggregate_type VARCHAR(255) NOT NULL,
    snapshot_payload VARCHAR(4000) NOT NULL,
    sequence_number INT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### The Transaction Commit Order Challenge in Polling
If the event relay publishes events by polling the database with monotonically increasing IDs (`SELECT * FROM EVENTS where event_id > last_processed_id`), concurrent transactions committing out of order can cause events to be permanently skipped:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//27f4ae15-40b5-49ec-ac05-5bb6d175b020/markdown_3/imgs/img_in_image_box_181_815_871_1142.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A38Z%2F-1%2F%2F684bdf54335b0557afcab39102647eca47eaf36775ba07c5fdc6ec94d85831d5" alt="Image" width="64%" /></div>
<div style="text-align: center;">Figure 6.6: A scenario where an event is skipped because its transaction A commits after transaction B. Polling sees eventId=1020 and then later skips eventId=1010.</div>

* **Solution**: Add an explicit `published` column (`PUBLISHED INT DEFAULT 0`) to mark processed events, or use transaction log tailing engines (Debezium/Canal) that read the binlog sequentially.

### Optimistic Concurrency Control (OCC)
To prevent race conditions, the event store uses the `sequence_number` for optimistic locking:
1. Thread A loads the aggregate and reads its current version (`sequence_number = 3`).
2. Thread B loads the aggregate and reads its current version (`sequence_number = 3`).
3. Thread A saves a new event with `sequence_number = 4`. The insert succeeds, updating the database version to 4.
4. Thread B attempts to save a new event with `sequence_number = 4`. The database unique constraint (`aggregate_id, sequence_number`) fails, throwing a duplicate key exception. Thread B's transaction rolls back, and it must retry.

---

## 12.4 Event Sourcing Schema Evolution: Upcasting

As a service's domain model evolves, developers rename fields, delete attributes, or add new properties to events:

| Level | Change | Backward Compatible |
| :--- | :--- | :--- |
| **Schema** | Define a new aggregate type | Yes |
| **Schema** | Remove an existing aggregate | No |
| **Schema** | Rename an aggregate type | No |
| **Aggregate** | Add a new event type | Yes |
| **Aggregate** | Remove an event type | No |
| **Event** | Add a new field | Yes (ignored by old consumers) |
| **Event** | Delete a field | No |
| **Event** | Rename a field / Change type | No |

### Upcaster Component Design
Rather than executing migrations to edit events in situ (which is risky and slow on write-heavy logs), frameworks employ **Upcasters**. An upcaster intercepts the event stream payload during loading from the database, transforming the serialized JSON from version $N$ to $N+1$ in-memory. The aggregate's `apply()` logic only ever executes against the latest version of events.

#### Upcaster Code Implementation in Java
Here is how an event upcaster is structured in Spring Boot to intercept JSON data:

```java
package com.ftgo.order.eventsource.upcast;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

public interface EventUpcaster {
    boolean canUpcast(String eventType, int currentVersion);
    JsonNode upcast(JsonNode eventNode);
}

public class OrderCreatedEventUpcaster implements EventUpcaster {
    
    @Override
    public boolean canUpcast(String eventType, int version) {
        // Intercept OrderCreated v1 events and upgrade them to v2
        return "com.ftgo.order.eventsource.OrderCreatedEvent".equals(eventType) && version == 1;
    }

    @Override
    public JsonNode upcast(JsonNode eventNode) {
        ObjectNode objectNode = (ObjectNode) eventNode;
        // Introduce a new default parameter that was not present in version 1
        if (!objectNode.has("currency")) {
            objectNode.put("currency", "USD");
        }
        return objectNode;
    }
}
```

---

## 12.5 Deleting Data: Tombstones and Crypto-shredding

Because Event Sourcing stores append-only data logs forever, physically purging entries to satisfy GDPR "Right to be Forgotten" rules is challenging. Two primary approaches are used:

1. **Tombstone Events**: Append a `TombstoneEvent` to the aggregate event stream, signaling the logical deletion. A background cleaner task sweeps the event store tables, physical deleting event records associated with the tombstoned aggregate.
2. **Crypto-Shredding (Recommended)**: Each aggregate's personal identifiable information (PII) payload fields are encrypted using a unique cryptographic key. When a user requests data deletion, the service deletes their encryption key from a Key Management Service (KMS). The raw database events remain intact, but are rendered unreadable (meaningless ciphertext).

#### Crypto-Shredding PII Decorator Java Implementation
```java
package com.ftgo.order.eventsource.security;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

public class CryptoShreddingService {
    // Simulated Key Management Store (KMS)
    private final Map<UUID, String> kmsStore = new HashMap<>();

    public UUID generateKeyForAggregate() {
        UUID keyId = UUID.randomUUID();
        // Generate an emulated symmetric key
        kmsStore.put(keyId, "AES_KEY_" + UUID.randomUUID().toString().substring(0, 8));
        return keyId;
    }

    public void shredKey(UUID keyId) {
        // Irreversibly delete key, making encrypted aggregate logs unreadable
        kmsStore.remove(keyId);
        System.out.println("Key " + keyId + " has been shredded from KMS. GDPR compliance met.");
    }

    public String encrypt(String piiData, UUID keyId) {
        String key = kmsStore.get(keyId);
        if (key == null) throw new IllegalStateException("Encryption key not found!");
        // Emulate symmetric encryption
        return "ENCRYPTED_WITH_" + key + "[" + piiData + "]";
    }

    public String decrypt(String encryptedData, UUID keyId) {
        String key = kmsStore.get(keyId);
        if (key == null) {
            // Key has been shredded
            return "DELETED_USER_PII";
        }
        // Emulate symmetric decryption
        return encryptedData.replace("ENCRYPTED_WITH_" + key + "[", "").replace("]", "");
    }
}
```

---

## 12.6 Integrating Event Sourcing with Saga Orchestrators

Integrating event-sourced aggregates with sagas requires solving reliable messaging pipelines:

### 1. Saga Creation from Events
Rather than explicitly instantiating a saga inside the service, the aggregate writes a state event, which is picked up by a listener to start the saga orchestrator instance. To prevent duplicate starts, the saga ID is derived directly from the aggregate ID or event ID:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5231034e-310f-467f-a017-a264c91e892b/markdown_1/imgs/img_in_image_box_183_201_916_637.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A42Z%2F-1%2F%2Fdfe494a7724ffe002f0432202ea058209d1c2f9983d8026a379e9ec388fe21a4" alt="Image" width="69%" /></div>
<div style="text-align: center;">Figure 6.11: Using an event handler to reliably create a saga after a service creates an event sourcing-based aggregate.</div>

### 2. Event-Sourced Saga Participants (SagaReplyRequestedEvent)
To allow an event-sourced participant to participate in a saga orchestrator, the participant inserts a pseudo-event `SagaReplyRequestedEvent` alongside its normal state events. A reply listener subscribes to this pseudo-event and routes the reply message back to the orchestrator:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//5231034e-310f-467f-a017-a264c91e892b/markdown_3/imgs/img_in_image_box_179_283_913_1051.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A55%3A44Z%2F-1%2F%2F7ce6779af37864d19c24504257569de7e8dc5645490398f2154d8e1ad330ab39" alt="Image" width="69%" /></div>
<div style="text-align: center;">Figure 6.12: How the event sourcing-based Accounting Service participates in Create Order Saga.</div>

### 3. Event-Sourced Saga Orchestrator (SagaCommandEvent)
To safely emit outbound commands from an event-sourced saga orchestrator, the state updates are written as events (`SagaOrchestratorCreated`, `SagaOrchestratorUpdated`) along with a pseudo-event `SagaCommandEvent`. An outbound listener picks up `SagaCommandEvent` and publishes the command message:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//04fd96da-ec16-4cbc-9865-8e92f0141764/markdown_1/imgs/img_in_image_box_199_285_939_774.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T02%3A56%3A27Z%2F-1%2F%2F5f37027aafb596bd8e7dde9c76cf5a54116fbaa2b54309f9eea169260e0dee6c" alt="Image" width="69%" /></div>
<div style="text-align: center;">Figure 6.13: How an event sourcing-based saga orchestrator sends commands to saga participants.</div>

---

## 12.7 Implementing Event Sourcing in Java

Let's write a functional Java implementation of an event-sourced aggregate, snapshot manager, and event store.

### 1. The Core Event Interfaces
```java
package com.ftgo.order.eventsource;

public interface DomainEvent {}

public class OrderCreatedEvent implements DomainEvent {
    private final Long orderId;
    private final Double amount;

    public OrderCreatedEvent(Long orderId, Double amount) {
        this.orderId = orderId;
        this.amount = amount;
    }

    public Long getOrderId() { return orderId; }
    public Double getAmount() { return amount; }
}

public class OrderApprovedEvent implements DomainEvent {
    private final Long orderId;

    public OrderApprovedEvent(Long orderId) {
        this.orderId = orderId;
    }

    public Long getOrderId() { return orderId; }
}
```

---

### 2. The Snapshot Data Models

```java
package com.ftgo.order.eventsource.snapshot;

public class OrderSnapshot {
    private final Long id;
    private final String state;
    private final Double amount;
    private final int sequenceNumber;

    public OrderSnapshot(Long id, String state, Double amount, int sequenceNumber) {
        this.id = id;
        this.state = state;
        this.amount = amount;
        this.sequenceNumber = sequenceNumber;
    }

    public Long getId() { return id; }
    public String getState() { return state; }
    public Double getAmount() { return amount; }
    public int getSequenceNumber() { return sequenceNumber; }
}
```

---

### 3. The Event-Sourced Aggregate Class: `OrderAggregate.java`
The aggregate class processes commands by generating events, and reconstructs its state by applying those events:

```java
package com.ftgo.order.eventsource;

import com.ftgo.order.eventsource.snapshot.OrderSnapshot;
import java.util.ArrayList;
import java.util.List;

public class OrderAggregate {

    private Long id;
    private String state;
    private Double amount;
    private int sequenceNumber = 0;

    // Track new events generated during the current command execution
    private final List<DomainEvent> changes = new ArrayList<>();

    public OrderAggregate() {}

    // 1. Process Command: Validate and generate an event
    public void createOrder(Long orderId, Double amount) {
        if (amount <= 0) {
            throw new IllegalArgumentException("Amount must be positive!");
        }
        applyNewEvent(new OrderCreatedEvent(orderId, amount));
    }

    public void approveOrder() {
        if (!"PENDING".equals(this.state)) {
            throw new IllegalStateException("Order must be in PENDING state to be approved!");
        }
        applyNewEvent(new OrderApprovedEvent(this.id));
    }

    // Apply a new event and add it to the list of changes
    private void applyNewEvent(DomainEvent event) {
        apply(event);
        changes.add(event);
    }

    // 2. Rehydrate Event: Apply event to update aggregate state
    public void apply(DomainEvent event) {
        if (event instanceof OrderCreatedEvent) {
            OrderCreatedEvent e = (OrderCreatedEvent) event;
            this.id = e.getOrderId();
            this.amount = e.getAmount();
            this.state = "PENDING";
        } else if (event instanceof OrderApprovedEvent) {
            this.state = "APPROVED";
        }
        this.sequenceNumber++;
    }

    // Memento Snapshot Restore
    public void restoreFromSnapshot(OrderSnapshot snapshot) {
        this.id = snapshot.getId();
        this.state = snapshot.getState();
        this.amount = snapshot.getAmount();
        this.sequenceNumber = snapshot.getSequenceNumber();
    }

    // Getters
    public Long getId() { return id; }
    public String getState() { return state; }
    public Double getAmount() { return amount; }
    public int getSequenceNumber() { return sequenceNumber; }
    public List<DomainEvent> getChanges() { return changes; }
}
```

---

### 4. The Custom Event Store Class: `EventStore.java`
The event store loads the aggregate's event stream and saves new events, enforcing optimistic concurrency control:

```java
package com.ftgo.order.eventsource;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Repository
public class EventStore {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    @Transactional
    public void saveEvents(String aggregateId, String aggregateType, List<DomainEvent> events, int expectedVersion) {
        int sequenceNumber = expectedVersion;

        for (DomainEvent event : events) {
            sequenceNumber++;
            try {
                String eventId = UUID.randomUUID().toString();
                String payload = objectMapper.writeValueAsString(event);

                // Insert event. Unique constraint (aggregate_id, sequence_number) enforces OCC
                jdbcTemplate.update(
                    "INSERT INTO events (event_id, aggregate_type, aggregate_id, event_type, event_payload, sequence_number) " +
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    eventId,
                    aggregateType,
                    aggregateId,
                    event.getClass().getName(),
                    payload,
                    sequenceNumber
                );
            } catch (Exception ex) {
                throw new IllegalStateException("Concurrency conflict: Concurrent update detected for aggregate ID " + aggregateId, ex);
            }
        }
    }

    public List<DomainEvent> loadEventStream(String aggregateId) {
        String sql = "SELECT event_type, event_payload FROM events WHERE aggregate_id = ? ORDER BY sequence_number ASC";
        
        return jdbcTemplate.query(sql, (rs, rowNum) -> {
            try {
                String type = rs.getString("event_type");
                String payload = rs.getString("event_payload");
                Class<?> clazz = Class.forName(type);
                return (DomainEvent) objectMapper.readValue(payload, clazz);
            } catch (Exception ex) {
                throw new IllegalStateException("Failed to deserialize event payload!", ex);
            }
        }, aggregateId);
    }

    public List<DomainEvent> loadEventStreamAfter(String aggregateId, int sequenceNumber) {
        String sql = "SELECT event_type, event_payload FROM events WHERE aggregate_id = ? AND sequence_number > ? ORDER BY sequence_number ASC";
        
        return jdbcTemplate.query(sql, (rs, rowNum) -> {
            try {
                String type = rs.getString("event_type");
                String payload = rs.getString("event_payload");
                Class<?> clazz = Class.forName(type);
                return (DomainEvent) objectMapper.readValue(payload, clazz);
            } catch (Exception ex) {
                throw new IllegalStateException("Failed to deserialize event payload!", ex);
            }
        }, aggregateId, sequenceNumber);
    }
}
```

---

### 5. Snapshot Repository Class: `OrderSnapshotRepository.java`
Handles snapshot serialization and database mapping:

```java
package com.ftgo.order.eventsource.snapshot;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class OrderSnapshotRepository {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    public void saveSnapshot(String aggregateId, OrderSnapshot snapshot) {
        try {
            String payload = objectMapper.writeValueAsString(snapshot);
            jdbcTemplate.update(
                "INSERT INTO snapshots (aggregate_id, aggregate_type, snapshot_payload, sequence_number) " +
                "VALUES (?, 'Order', ?, ?) ON DUPLICATE KEY UPDATE snapshot_payload = ?, sequence_number = ?",
                aggregateId,
                payload,
                snapshot.getSequenceNumber(),
                payload,
                snapshot.getSequenceNumber()
            );
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to save aggregate snapshot!", ex);
        }
    }

    public OrderSnapshot loadSnapshot(String aggregateId) {
        String sql = "SELECT snapshot_payload FROM snapshots WHERE aggregate_id = ?";
        try {
            return jdbcTemplate.queryForObject(sql, (rs, rowNum) -> {
                try {
                    String payload = rs.getString("snapshot_payload");
                    return objectMapper.readValue(payload, OrderSnapshot.class);
                } catch (Exception ex) {
                    throw new IllegalStateException("Failed to deserialize snapshot!", ex);
                }
            }, aggregateId);
        } catch (Exception ex) {
            return null; // No snapshot exists yet
        }
    }
}
```

---

### 6. Orchestrated Aggregate Repository: `EventSourcedOrderRepository.java`
Coordinates snapshot loading, post-snapshot events rehydration, and periodic snapshotting:

```java
package com.ftgo.order.eventsource;

import com.ftgo.order.eventsource.snapshot.OrderSnapshot;
import com.ftgo.order.eventsource.snapshot.OrderSnapshotRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public class EventSourcedOrderRepository {

    @Autowired
    private EventStore eventStore;

    @Autowired
    private OrderSnapshotRepository snapshotRepository;

    public OrderAggregate findById(String id) {
        OrderAggregate aggregate = new OrderAggregate();
        int startSequence = 0;

        // 1. Try to load snapshot
        OrderSnapshot snapshot = snapshotRepository.loadSnapshot(id);
        if (snapshot != null) {
            aggregate.restoreFromSnapshot(snapshot);
            startSequence = snapshot.getSequenceNumber();
        }

        // 2. Load events after snapshot version
        List<DomainEvent> events = eventStore.loadEventStreamAfter(id, startSequence);
        for (DomainEvent event : events) {
            aggregate.apply(event);
        }

        return aggregate;
    }

    public void save(OrderAggregate aggregate) {
        int originalVersion = aggregate.getSequenceNumber() - aggregate.getChanges().size();
        
        // 1. Save new events
        eventStore.saveEvents(
            aggregate.getId().toString(), 
            "Order", 
            aggregate.getChanges(), 
            originalVersion
        );

        // 2. Periodically save a new snapshot (e.g. every 100 events)
        if (aggregate.getSequenceNumber() % 100 == 0) {
            OrderSnapshot snapshot = new OrderSnapshot(
                aggregate.getId(),
                aggregate.getState(),
                aggregate.getAmount(),
                aggregate.getSequenceNumber()
            );
            snapshotRepository.saveSnapshot(aggregate.getId().toString(), snapshot);
        }
    }
}
```

---

### 7. Concurrency Update Handling and Retry Loops
When a write conflict occurs (a `DuplicateKeyException` is thrown due to parallel writes), the client must fetch the aggregate again (which now includes the rival write events), perform the command validation check, and attempt to persist again. 

Here is how to write a retry helper in Java with exponential backoff:

```java
package com.ftgo.order.eventsource.retry;

import com.ftgo.order.eventsource.DomainEvent;
import com.ftgo.order.eventsource.EventStore;
import com.ftgo.order.eventsource.OrderAggregate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class OrderCommandExecutor {

    @Autowired
    private EventStore eventStore;

    public void executeApproveOrder(String aggregateId) {
        int retries = 0;
        int maxRetries = 4;
        long backoff = 100; // start with 100ms backoff

        while (true) {
            try {
                // 1. Load the latest events
                List<DomainEvent> stream = eventStore.loadEventStream(aggregateId);
                OrderAggregate aggregate = new OrderAggregate();
                
                // 2. Rehydrate
                for (DomainEvent event : stream) {
                    aggregate.apply(event);
                }
                int currentVersion = aggregate.getSequenceNumber();

                // 3. Execute command
                aggregate.approveOrder();

                // 4. Save events, attempting to write at currentVersion
                eventStore.saveEvents(aggregateId, "Order", aggregate.getChanges(), currentVersion);
                break; // Success!

            } catch (IllegalStateException ex) {
                retries++;
                if (retries > maxRetries) {
                    throw new IllegalStateException("Failed to execute command: Concurrency retry limit reached!", ex);
                }
                try {
                    // Exponential backoff wait
                    Thread.sleep(backoff);
                    backoff *= 2;
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException(e);
                }
            }
        }
    }
}
```

---

## 12.8 Event-Sourced Sagas: State Rehydration

Instead of using relational tables to track the current state of a saga orchestrator, we can **event source the orchestrator itself**. 

As the orchestrator dispatches commands and receives replies, it appends corresponding lifecycle events to the event store. Rehydrating the orchestrator's active state is accomplished by replaying these events:

```java
package com.ftgo.order.eventsource.saga;

import java.util.ArrayList;
import java.util.List;

public class EventSourcedSagaOrchestrator {

    private final String sagaId;
    private SagaState state;
    private final List<SagaEvent> changes = new ArrayList<>();

    public EventSourcedSagaOrchestrator(String sagaId) {
        this.sagaId = sagaId;
        this.state = SagaState.STARTED;
    }

    public void apply(SagaEvent event) {
        if (event instanceof SagaCreatedEvent) {
            this.state = SagaState.STARTED;
        } else if (event instanceof CommandDispatchedEvent) {
            this.state = SagaState.WAITING_FOR_REPLY;
        } else if (event instanceof ReplyReceivedEvent) {
            ReplyReceivedEvent rre = (ReplyReceivedEvent) event;
            this.state = rre.isSuccess() ? SagaState.STEP_COMPLETED : SagaState.ROLLING_BACK;
        }
    }

    public void recordCommandDispatched(String commandId, String destination) {
        CommandDispatchedEvent event = new CommandDispatchedEvent(sagaId, commandId, destination);
        changes.add(event);
        apply(event);
    }

    public List<SagaEvent> getChanges() { return changes; }
    public SagaState getState() { return state; }
}

enum SagaState {
    STARTED,
    WAITING_FOR_REPLY,
    STEP_COMPLETED,
    ROLLING_BACK
}

interface SagaEvent {}
class SagaCreatedEvent implements SagaEvent {}
class CommandDispatchedEvent implements SagaEvent {
    public CommandDispatchedEvent(String sagaId, String commandId, String dest) {}
}
class ReplyReceivedEvent implements SagaEvent {
    public boolean isSuccess() { return true; }
}
```

---

## 12.9 Implementing GDPR Crypto-Shredding in Event Stores

In an append-only database, we cannot physically delete or run `UPDATE` statements to scrub personal data without breaking cryptographic hash chains. 

Under the **Crypto-Shredding** pattern, personal fields are encrypted using a unique symmetric key (AES-256) loaded from a key management service. When a user requests data deletion (under GDPR), their unique key is deleted from the key store, rendering the historical data in the event store permanently unreadable:

```java
package com.ftgo.order.eventsource.crypto;

import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;

public class CryptoShreddingEncoder {

    // Simulates key store lookup database
    private final Map<String, byte[]> keyStore = new HashMap<>();

    public void registerUserKey(String userId, byte[] aesKey) {
        keyStore.put(userId, aesKey);
    }

    public void shredUserKey(String userId) {
        // Delete key to permanently lock access to encrypted data (Crypto-shredding)
        keyStore.remove(userId);
    }

    public String encryptField(String userId, String clearText) {
        byte[] rawKey = keyStore.get(userId);
        if (rawKey == null) {
            throw new IllegalStateException("Encryption key not found for user: " + userId);
        }
        try {
            SecretKeySpec secretKey = new SecretKeySpec(rawKey, "AES");
            Cipher cipher = Cipher.getInstance("AES");
            cipher.init(Cipher.ENCRYPT_MODE, secretKey);
            byte[] encrypted = cipher.doFinal(clearText.getBytes());
            return Base64.getEncoder().encodeToString(encrypted);
        } catch (Exception ex) {
            throw new RuntimeException("Failed to encrypt data field", ex);
        }
    }

    public String decryptField(String userId, String cipherText) {
        byte[] rawKey = keyStore.get(userId);
        if (rawKey == null) {
            // Key has been shredded. Return redacted tombstone text.
            return "[REDACTED - DELETED UNDER GDPR]";
        }
        try {
            SecretKeySpec secretKey = new SecretKeySpec(rawKey, "AES");
            Cipher cipher = Cipher.getInstance("AES");
            cipher.init(Cipher.DECRYPT_MODE, secretKey);
            byte[] decoded = Base64.getDecoder().decode(cipherText);
            return new String(cipher.doFinal(decoded));
        } catch (Exception ex) {
            throw new RuntimeException("Failed to decrypt data field", ex);
        }
    }
}
```

---


## Chapter Summary

* **Event Sourcing** stores the state of a business entity as a sequence of immutable events rather than overwriting database rows.
* This paradigm provides a complete audit log, simplifies time travel debugging, and supports flexible query generation.
* To reconstruct (rehydrate) an aggregate's current state, the system replays its historical events. Performance is optimized by loading **Snapshots** and replaying only the events that occurred after the snapshot was taken.
* An **Event Store** is an append-only database table that acts as a database and a message broker.
* **Optimistic Concurrency Control** (OCC) is enforced using a unique database constraint on the combination of aggregate ID and event sequence number, preventing concurrent write conflicts.
* Client-side **Command Executors** implement retry loops with exponential backoff to handle transient concurrency write conflicts.
* **Upcasters** transform old event payload schemas to the latest version dynamically during rehydration, handling schema evolution.
* **GDPR compliance** in append-only event stores is managed via logical tombstones or crypto-shredding keys.
* **Event-sourced Sagas** execute asynchronously using pseudo-events like `SagaReplyRequestedEvent` and `SagaCommandEvent` to decouple replies and command routing.
