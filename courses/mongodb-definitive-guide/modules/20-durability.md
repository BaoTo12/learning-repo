# Module 20: Durability and Write Performance (Chapter 20)

Welcome class. Today we analyze **Durability and Write Performance (CS-529)**.

A database must guarantee durability—surviving power failures or system crashes without losing committed writes. MongoDB achieves this by using WiredTiger's write-ahead logging (journaling) and multi-node read/write concerns.

Today we study **WiredTiger Durability Mechanics**, analyzing checkpoints, journaling write concerns, read concerns, and client replication contracts in Java.

---

## 1. Academic Lecture: WiredTiger Checkpoints & Journaling

### 1. Checkpoints and the Journal
*   **WiredTiger Checkpoints**: Every 60 seconds (or when 2GB of data is written), WiredTiger creates a checkpoint, flushing all in-memory changes to data files on disk.
*   **The Journal**: A write-ahead log. Writes are appended to the journal in-memory and flushed to disk every 100ms. If the server crashes, MongoDB replays the journal to recover modifications made since the last checkpoint.

```text
[Write Operation] ──> [In-Memory Cache (Dirty Pages)]
                             ├── (Flush every 100ms) ────> [Journal on Disk]
                             └── (Checkpoint every 60s) ──> [Data Files on Disk]
```

### 2. Read and Write Concerns
*   **Write Concerns**:
    *   `w:1`: Confirms the write is in the primary's memory cache.
    *   `w:majority`: Confirms the write is committed to a majority of replica set members.
    *   `j:true`: Confirms the write is flushed to the node's disk journal.
*   **Read Concerns**:
    *   `local` / `available`: Returns the node's local data (vulnerable to rollbacks).
    *   `majority`: Returns data that has been confirmed by a majority of replica set nodes (rollback-proof).
    *   `linearizable`: Directs the primary to perform a quorum check before responding, guaranteeing it is still the primary.

---

## 2. Theory vs. Production Trade-offs

Compare durability levels:

| Configuration Settings | Durability Guarantee | Write Latency | Read Consistency | Rollback Resiliency |
| :--- | :--- | :--- | :--- | :--- |
| `w:1`, `j:false`, Read: `local` | Very Low | Minimal | Weak (Stale / Phantom reads) | None |
| `w:1`, `j:true`, Read: `local` | Moderate (Single node crash safe)| Moderate | Weak (Stale / Phantom reads) | None |
| `w:majority`, `j:true`, Read: `majority` | Maximum | High | High (Rollback-proof reads) | 100% |

---

## 3. How to Use: Durability Configurations in Java

Let us construct write concern settings. We contrast a volatile, un-journaled write with a robust, rollback-proof write and read sequence in Java.

### A. The Volatile Write (Anti-Pattern)
Avoid using un-acknowledged or un-journaled writes for financial transactions:

```java
// DANGER: If the server VM experiences a sudden power loss before the 
// next 100ms journal flush or 60s checkpoint, this write is lost forever.
collection.withWriteConcern(WriteConcern.UNACKNOWLEDGED)
        .insertOne(new Document("accountId", "A").append("deposit", 1000));
```

### B. The Production-Grade Durability Configuration (Production Pattern)
Define write concerns with journaling active, and query using majority read concern to prevent reading rolled-back data:

```java
import com.mongodb.WriteConcern;
import com.mongodb.ReadConcern;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;

public class FinancialService {

    public void secureLedgerWrite(MongoCollection<Document> collection, String txId, double amount) {
        // Robust Pattern: Write concern majority + journal=true
        WriteConcern safeWriteConcern = WriteConcern.MAJORITY.withJournal(true);

        Document ledger = new Document("_id", txId)
                .append("amount", amount)
                .append("status", "COMMITTED");

        collection.withWriteConcern(safeWriteConcern).insertOne(ledger);
    }

    public Document readCommittedLedger(MongoCollection<Document> collection, String txId) {
        // Robust Pattern: Read concern majority guarantees data has been persisted across a majority of nodes
        return collection.withReadConcern(ReadConcern.MAJORITY)
                .find(Filters.eq("_id", txId))
                .first();
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Read Concern `majority` on Standalone Nodes
*   **Why it fails**: Executing a query with `ReadConcern.MAJORITY` against a standalone database node (not running as a replica set member). The query planner raises an exception because a single node has no peers to establish majority consensus.
*   **Mitigation**: Configure read concern majority only when connecting to replica sets or sharded clusters.

---

## 5. Socratic Review Questions

### Question 1
What is the performance consequence of setting `j:true` on every write operation, and how do client write batch sizes mitigate this?

#### Answer
Setting `j:true` forces WiredTiger to perform a synchronous disk write flush for that operation, bypasses the default 100ms journal buffering. This increases write latency to match the disk's physical seek/write speed, limiting single-threaded write throughput. Batching multiple inserts or updates inside a single write operation allows the disk to flush all changes in a single write cycle, improving throughput.

---

## 6. Hands-on Challenge: Zero Data Loss Transaction Engine

### The Challenge
In this challenge, you will implement a durability config helper in Java.
Your task:
1. Complete `executeDurabilityTransaction` in `DurabilityEngine`.
2. Apply the safe Write Concern: write concern `majority` and journal flag `true`.
3. Apply the safe Read Concern: read concern `majority`.
4. Insert `writeDocument` into `collection` using the configured safe write concern.
5. Retrieve the inserted document using the configured safe read concern, filtering by `_id`, and return it.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class DurabilityEngine {

    public Document executeDurabilityTransaction(MongoCollection<Document> collection, Document writeDocument) {
        // TODO: Configure collection with safe write concern (majority, j:true), execute insertOne,
        // then configure collection with majority read concern, retrieve the document by its _id, and return it.
        return null;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.WriteConcern;
import com.mongodb.ReadConcern;
import com.mongodb.client.FindIterable;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class DurabilityEngineTest {

    @SuppressWarnings("unchecked")
    @Test
    void testExecuteDurabilityTransaction() {
        MongoCollection<Document> baseCollection = mock(MongoCollection.class);
        MongoCollection<Document> writeCollection = mock(MongoCollection.class);
        MongoCollection<Document> readCollection = mock(MongoCollection.class);
        FindIterable<Document> findIterable = mock(FindIterable.class);

        Document doc = new Document("_id", "T1").append("value", 500);

        // Mock fluent withWriteConcern and withReadConcern chains
        when(baseCollection.withWriteConcern(any(WriteConcern.class))).thenReturn(writeCollection);
        when(writeCollection.withReadConcern(any(ReadConcern.class))).thenReturn(readCollection);
        when(readCollection.find(any(Document.class))).thenReturn(findIterable);
        when(findIterable.first()).thenReturn(doc);

        DurabilityEngine engine = new DurabilityEngine();
        Document result = engine.executeDurabilityTransaction(baseCollection, doc);

        assertNotNull(result);
        assertEquals("T1", result.getString("_id"));
        
        // Verify correct write concern configuration was requested
        verify(baseCollection).withWriteConcern(argThat(wc -> 
            "majority".equals(wc.getWObject()) && Boolean.TRUE.equals(wc.getJournal())
        ));
        
        // Verify correct read concern configuration was requested
        verify(writeCollection).withReadConcern(ReadConcern.MAJORITY);
    }
}
```
