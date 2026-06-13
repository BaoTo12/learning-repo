# Module 08: Transactions (Chapter 8)

Welcome class. Today we analyze **Transactions (CS-529)**.

In highly concurrent enterprise environments, operations must often maintain ACID compliance across multiple documents or collections. While MongoDB historically promoted single-document atomicity, modern engines support multi-document ACID transactions across replica sets and sharded clusters.

Today we study **Multi-Document ACID Transactions**, mapping database session lifecycles, analyzing read-concern isolation limits, and managing transactional locking bottlenecks.

---

## 1. Academic Lecture: ACID Sessions & Shared Locks

### 1. Transient Transaction Specs
Multi-document transactions in MongoDB execute inside a **Client Session**. All operations in the transaction block are staged on the client driver side and buffered inside the WiredTiger storage engine's transaction table. No writes are visible to other read threads until the commit command executes.

### 2. Lock Contention & Transaction Expiration
To support concurrent isolation, WiredTiger acquires **Intent-Exclusive (IX)** locks at the database and collection levels, and exclusive write locks on modified documents.
*   **The 60-Second Transaction Window**: To prevent blocked threads from exhausting resources, MongoDB limits the execution time of a transaction to **60 seconds** by default (`transactionLifetimeLimitSeconds`). If a session exceeds this threshold, the server aborts the transaction and releases all locks.

```text
[Start Session] ──> [Stage writes in memory] ──> [Acquire Document Locks]
                                                        │
                                                        ├─ If Commit (within 60s) ──> [Persist data]
                                                        └─ If Timeout / Rollback ───> [Discard changes]
```

---

## 2. Theory vs. Production Trade-offs

Compare transactional isolation and consistency boundaries:

| Dimension / Metric | Single-Document Write (Atomic) | Multi-Document Transaction (Standard) | Multi-Document Transaction (`majority` Read) |
| :--- | :--- | :--- | :--- |
| **ACID Scope** | Single document | Multiple docs / collections | Multiple docs / collections |
| **Read Isolation** | Read Committed (default) | Read Committed (local) | Read Majority (guarantees no rollbacks) |
| **Lock Duration** | Microseconds | Held until transaction commits/aborts | Held until transaction commits/aborts |
| **Write Conflict Risk** | Low (Retryable writes) | High (Requires retry-on-conflict logic) | High (Requires retry-on-conflict logic) |
| **Latency Penalty** | Minimal | Moderate | High (Majority replication lag cost) |

---

## 3. How to Use: Resilient Transaction Sessions

Let us write transaction executions. We contrast a volatile transaction sequence (vulnerable to write conflicts) with a robust transaction handler incorporating retry logic.

### A. The Volatile Transaction Sequence (Anti-Pattern)
Avoid executing transaction operations without conflict retry loops:

```javascript
// DANGER: If another write updates any of the staged documents before this block completes,
// WiredTiger raises a WriteConflict error, causing this script to crash.
const session = db.getMongo().startSession();
session.startTransaction();
try {
  session.getDatabase("bank").accounts.updateOne({ name: "Alice" }, { $dec: { balance: 100 } });
  session.getDatabase("bank").accounts.updateOne({ name: "Bob" }, { $inc: { balance: 100 } });
  session.commitTransaction();
} catch (error) {
  session.abortTransaction();
} finally {
  session.endSession();
}
```

### B. The Hardened Transaction Handler with Retries (Production Pattern)
Implement a robust retry loop to handle transient transaction write conflicts:

```javascript
// Robust Pattern: Captures transient WriteConflicts and retries the transaction.
function runTransactionWithRetry(txnFunc, session) {
  while (true) {
    try {
      session.startTransaction({
        readConcern: { level: "majority" },
        writeConcern: { w: "majority" }
      });
      txnFunc(session);
      session.commitTransaction();
      break; // Transaction succeeded
    } catch (error) {
      session.abortTransaction();
      // Test if the error is a transient write conflict that can be retried
      if (error.hasErrorLabel && error.hasErrorLabel("TransientTransactionError")) {
        print("Transient transaction error, retrying write...");
        continue;
      }
      throw error; // Rethrow fatal errors
    }
  }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: DDL Operations Inside Transactions
*   **Why it fails**: Attempting to create collections, indexes, or change collection settings (like capped parameters) inside a transaction session. MongoDB transactions can only perform CRUD operations. DDL operations require catalog modifications that lock system tables, which are prohibited within transactional boundaries.
*   **Mitigation**: Always ensure that target collections and indexes are initialized before beginning transaction sessions.

---

## 5. Socratic Review Questions

### Question 1
Why does setting a read concern of `local` inside a transaction expose the application to dirty reads if the primary replica set node fails immediately after a commit?

#### Answer
A read concern of `local` returns the document's state immediately from the primary's memory, without confirming if the write has been replicated to other nodes. If the primary node crashes before replication completes, a failover occurs, electing a secondary that does not have that write. The committed transaction's data is lost (rolled back), meaning the client read "dirty" un-replicated data.

---

## 6. Hands-on Challenge: Atomic Balance Transfer

### The Challenge
In this challenge, you will implement an atomic balance transfer.
Your task:
1. Complete `executeTransfer` inside a session context.
2. Deduct `amount` from account `fromId` and credit it to account `toId`.
3. Read concern must be `majority`.
4. If a balance drops below 0, throw an error to trigger a rollback.

Complete the implementation stub below:

```javascript
function executeTransfer(session, fromId, toId, amount) {
  const accounts = session.getDatabase("bank").accounts;
  
  // TODO: Implement the transfer:
  // 1. Fetch fromId account.
  // 2. If balance < amount, throw new Error("Insufficient funds").
  // 3. Deduct amount from fromId.
  // 4. Add amount to toId.
}
```

### Verification Query
Validate the transaction rollback:
```javascript
const session = db.getMongo().startSession();
db.accounts.insertOne({ _id: "A", balance: 50 });
db.accounts.insertOne({ _id: "B", balance: 100 });

try {
  runTransactionWithRetry((sess) => {
    executeTransfer(sess, "A", "B", 100);
  }, session);
} catch (e) {
  print("Caught expected rollback error: " + e.message);
}

const accountA = db.accounts.findOne({ _id: "A" });
if (accountA.balance === 50) {
  print("Success: Transaction rolled back; balance integrity preserved.");
} else {
  print("Error: Inconsistent state detected.");
}
session.endSession();
```
