# Module 20: Durability (Chapter 20)

Welcome class. Today we analyze **Durability (CS-529)**.

A database must guarantee that committed transactions survive server crashes. MongoDB's **WiredTiger** storage engine achieves this by coordinating write buffers in memory, transaction journaling, and replica set write concerns.

Today we study **Database Durability Mechanics**, analyzing WiredTiger journaling, write concern thresholds, read concerns, and data corruption verification.

---

## 1. Academic Lecture: Journaling & Read Concerns

### 1. WiredTiger Journaling
WiredTiger caches modifications in memory. To ensure durability before cache pages are flushed to data files on disk (which occurs once every 60 seconds), MongoDB writes operations to an append-only **Journal** file on disk.
*   The journal is flushed to disk every **100 milliseconds** by default (`commitIntervalMs`). If the server crashes, MongoDB replays the journal on startup to restore memory state.

### 2. Read Concerns
*   **local / available**: Returns the node's local data immediately; does not guarantee that the read data was replicated.
*   **majority**: Returns data committed by a majority of replica set members. This protects against dirty reads from nodes that are later rolled back.
*   **linearizable**: Guarantees that the read returns the latest completed write, verifying that the node is still the primary by querying other members.

```text
[Write Client] ──> [Primary Memory] ──> [Journal Flush (100ms)]
                        │
                  (Sync to Node B)
                        ▼
[Read Client]  <─── Read (majority) ─── [Consistent Data]
```

---

## 2. Theory vs. Production Trade-offs

Compare write and read concern configurations:

| Dimension / Metric | `{ w: 1, j: false }` | `{ w: "majority", j: true }` | `{ w: "majority", j: false }` |
| :--- | :--- | :--- | :--- |
| **Write Latency** | Low | High | Moderate |
| **Crash Durability** | Vulnerable (Lost if crash < 100ms) | Absolute (Persisted to journal) | Vulnerable to power losses |
| **Rollback Safety** | None | Guaranteed | Guaranteed |
| **RAM Cache Burden** | Low | Low | High |
| **throughput** | High | Low | Moderate |

---

## 3. How to Use: Durability Configurations

Let us write durability queries. We contrast a volatile, un-journaled write configuration with a robust, durable write pattern.

### A. The Non-Journaled Write (Anti-Pattern)
Avoid saving transactions with journaling disabled on critical systems:

```javascript
// DANGER: j:false tells the engine to acknowledge the write before it is flushed 
// to disk. A sudden power loss in the next 100ms will result in data loss.
db.accounts.updateOne(
  { name: "Alice" },
  { $set: { balance: 500 } },
  { writeConcern: { w: 1, j: false } }
);
```

### B. The Hardened Durable Write (Production Pattern)
Enforce majority replication and journal persistence for transaction queries:

```javascript
// Robust Pattern: Acknowledged by majority and written to journal before returning.
db.accounts.updateOne(
  { name: "Alice" },
  { $set: { balance: 500 } },
  { writeConcern: { w: "majority", j: true, wtimeout: 5000 } }
);
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Read Majority Failing Due to Replication Lag
*   **Why it fails**: When you query with `readConcern: { level: "majority" }`, the database engine reads from a snapshot of majority-committed data. If replication lag is high, the majority snapshot can fall behind. Queries will return stale data until secondaries catch up.
*   **Mitigation**: Monitor replication lag and set alerts. Avoid reading from secondaries if lag thresholds are exceeded.

---

## 5. Socratic Review Questions

### Question 1
What is the difference between WiredTiger data checkpoints and journal flushes, and how do they work together to restore database state after a crash?

#### Answer
WiredTiger flushes its entire memory cache to database files on disk once every 60 seconds, creating a consistent **Checkpoint** on disk. Journal flushes occur every 100ms, logging changes since the last checkpoint. If the server crashes, MongoDB loads the database from the last checkpoint and replays the journal logs to recover operations committed in the last 60 seconds.

---

## 6. Hands-on Challenge: Durable Query Verification

### The Challenge
In this challenge, you will write a durable transaction query.
Your task:
1. Write a script to update `inventory` records.
2. The query must use strict durability options: require majority write acknowledgment, force immediate journal sync, and set a timeout of 2 seconds.

Complete the query stub below:

```javascript
// TODO: Write durable update query
db.inventory.updateOne(
  { sku: "SKU-9921" },
  { $inc: { quantity: -5 } },
  // Add strict writeConcern here
);
```

### Verification Query
Confirm write concern syntax:
```javascript
try {
  db.inventory.updateOne(
    { sku: "SKU-9921" },
    { $inc: { quantity: -5 } },
    { writeConcern: { w: "majority", j: true, wtimeout: 2000 } }
  );
  print("Success: Update verified with strict durability settings.");
} catch (e) {
  print("Error: Durability settings invalid.");
}
```
