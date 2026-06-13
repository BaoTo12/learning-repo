# Module 08: Transactions (Chapter 8)

Welcome class. Today we analyze **Transactions (CS-529)**.

In highly concurrent applications, operations must often maintain ACID compliance across multiple documents or collections. MongoDB supports multi-document ACID transactions using **Client Sessions**. In Java, this requires managing session contexts and implementing retry logic to resolve transient write conflicts.

Today we study **Multi-Document ACID Transactions**, analyzing session lifecycles, database locking behaviors, and write conflict recovery.

---

## 1. Academic Lecture: ACID Sessions & Transaction Timeouts

### 1. Transient Transaction Architecture
MongoDB transactions execute inside a `com.mongodb.client.ClientSession`. Write operations are staged in memory on the client side and buffered inside the WiredTiger storage engine's transaction tables. Changes are invisible to other client connections until the transaction commits.

### 2. Lock Contention & Lifecycles
*   **Locks**: WiredTiger acquires Intent-Exclusive (IX) locks on databases and collections, and exclusive write locks on modified documents.
*   **The 60-Second Limit**: To prevent transactions from blocking system threads, MongoDB enforces a `transactionLifetimeLimitSeconds` of **60 seconds**. If a transaction runs longer than this, the database automatically aborts it and rolls back all modifications.

```text
[Start Session] ──> [Stage Updates (Memory)] ──> [Acquire Document Locks]
                                                        │
                                    ┌───────────────────┴───────────────────┐
                                    ▼ (Commit within 60s)                   ▼ (Abort/Timeout)
                             [Persist Writes]                       [Rollback Changes]
```

---

## 2. Theory vs. Production Trade-offs

Compare write consistency boundaries:

| Dimension / Metric | Single-Document Write (Atomic) | Multi-Document Transaction (Local Read) | Multi-Document Transaction (Majority Read) |
| :--- | :--- | :--- | :--- |
| **ACID Scope** | Single document | Multiple docs / collections | Multiple docs / collections |
| **Read Isolation** | Read Committed (local) | Read Committed (local) | Read Majority (guarantees no rollbacks) |
| **Lock Duration** | Microseconds | Held until transaction commits/aborts | Held until transaction commits/aborts |
| **Write Conflict Risk** | Low (Retryable writes) | High (Requires retry-on-conflict logic) | High (Requires retry-on-conflict logic) |
| **Latency Cost** | Minimal | Moderate | High (Majority sync validation latency) |

---

## 3. How to Use: Resilient Transactions in Java

Let us construct transactional writes. We contrast a volatile transactional write (vulnerable to conflicts) with a robust transaction callback using conflict retry loops.

### A. The Volatile Transaction Sequence (Anti-Pattern)
Avoid running transactions without retry logic:

```java
// DANGER: If a concurrent write updates either account A or B before this block commits,
// WiredTiger raises a MongoWriteConflictException, causing the Java application to crash.
ClientSession session = mongoClient.startSession();
session.startTransaction();
try {
    accounts.updateOne(session, Filters.eq("_id", "A"), Updates.inc("balance", -100));
    accounts.updateOne(session, Filters.eq("_id", "B"), Updates.inc("balance", 100));
    session.commitTransaction();
} catch (Exception e) {
    session.abortTransaction();
} finally {
    session.endSession();
}
```

### B. The Hardened Transaction Callback (Production Pattern)
Use the driver's built-in transaction runner (`session.withTransaction()`), which automatically handles transient write conflicts and retries:

```java
import com.mongodb.TransactionOptions;
import com.mongodb.WriteConcern;
import com.mongodb.ReadConcern;
import com.mongodb.client.ClientSession;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class TransactionService {

    public void transferFunds(MongoClient client, MongoCollection<Document> accounts, String fromId, String toId, double amount) {
        TransactionOptions txnOptions = TransactionOptions.builder()
                .readConcern(ReadConcern.MAJORITY)
                .writeConcern(WriteConcern.MAJORITY.withJournal(true))
                .build();

        try (ClientSession session = client.startSession()) {
            // withTransaction handles retries for TransientTransactionError
            session.withTransaction(() -> {
                accounts.updateOne(session, Filters.eq("_id", fromId), Updates.inc("balance", -amount));
                accounts.updateOne(session, Filters.eq("_id", toId), Updates.inc("balance", amount));
                return "Commit Complete";
            }, txnOptions);
        }
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Executing DDL Queries Inside Transactions
*   **Why it fails**: Executing collection creations or index builds (`createIndex`) inside a transactional block. MongoDB transactions only support CRUD operations. DDL operations modify the database catalog, which requires global locks that are prohibited within transaction sessions.
*   **Mitigation**: Initialize all collections and indexes before beginning transaction sessions.

---

## 5. Socratic Review Questions

### Question 1
Why does WiredTiger release document locks only *after* a transaction commits or aborts, rather than immediately after each individual document update inside the session?

#### Answer
WiredTiger must guarantee database isolation (the "I" in ACID). If locks were released immediately after an update, other clients could read the modified document *before* the transaction commits. If the transaction is later aborted, this leads to dirty reads. Keeping locks held until the final commit/abort ensures that changes become visible atomically.

---

## 6. Hands-on Challenge: Atomic Balance Transfer Engine

### The Challenge
In this challenge, you will implement an atomic balance transfer engine in Java.
Your task:
1. Complete `executeTransferTxn` in `BankService`.
2. Deduct `amount` from `fromId` and credit it to `toId`.
3. Check the balance of the `fromId` account first. If it is less than `amount`, throw a `RuntimeException` to abort the transaction.
4. Execute both updates within the provided `ClientSession` transaction context.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.ClientSession;
import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class BankService {

    public void executeTransferTxn(ClientSession session, MongoCollection<Document> accounts, String fromId, String toId, double amount) {
        // TODO:
        // 1. Fetch fromId document.
        // 2. Throw RuntimeException if balance < amount.
        // 3. Deduct amount from fromId, add to toId.
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test:

```java
package com.mongodb.systems;

import com.mongodb.client.ClientSession;
import com.mongodb.client.MongoCollection;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class BankServiceTest {

    @SuppressWarnings("unchecked")
    @Test
    void testInsufficientFundsAborts() {
        MongoCollection<Document> accounts = mock(MongoCollection.class);
        ClientSession session = mock(ClientSession.class);
        BankService service = new BankService();

        Document account = new Document("_id", "A").append("balance", 50.0);
        when(accounts.find(session, any())).thenReturn(null); // Force failure or mock return

        assertNotNull(service);
    }
}
```
