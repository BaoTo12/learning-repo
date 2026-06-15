# Module 09: Transactions and Consistency

Welcome, student. Today we study every aspect of **Transactions and Consistency (CS-529)** using the official MongoDB Java Sync Driver.

---

## 1. What problem does this solve?
In complex business workflows, multiple database changes must be executed as a single unit of work. For example, when transferring money from Account A to Account B, or checking out an e-commerce shopping cart, the system must update balances and insert audit logs together. 

If one update succeeds but a subsequent update fails, the database is left in a corrupted, inconsistent state.

Transactions solve this by guaranteeing **ACID** (Atomicity, Consistency, Isolation, Durability) compliance across multiple documents and collections, ensuring that either all changes are written permanently, or the entire set of changes is rolled back.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides session-bound multi-document transactions to:
*   **Enforce ACID Guarantees**: Provide the same transaction guarantees as traditional relational databases (SQL) when modifying multiple records.
*   **Ensure Data Consistency in Replica Sets**: Sync transaction oplogs across primary and secondary nodes using write concerns, preventing dirty reads of uncommitted data.
*   **Support Complex Enterprise Applications**: Enable applications to handle complex workflows (like double-entry bookkeeping) natively without custom application-level rollback algorithms.

---

## 3. How does it work internally or conceptually?
*   **Single-Document Atomicity (Default)**: In MongoDB, all write operations on a single document (even nested updates inside arrays or subdocuments) are **always atomic** without using transactions. This is because WiredTiger locks the document record block during modification, preventing concurrent writes from interleaving.
*   **Multi-Document Transactions**: When updating multiple documents across collections, MongoDB uses **Logical Sessions** (`ClientSession`). 
*   **Storage Engine Execution**: WiredTiger executes transaction writes inside a private memory snapshot. Modified documents are locked. Oplog entries are generated but marked as uncommitted. Once the client issues a commit, WiredTiger writes the transaction records to the oplog, makes the changes visible globally, and releases document locks.
*   **ACID in MongoDB**:
    *   *Atomicity*: All writes inside a session succeed or fail together.
    *   *Consistency*: Transactions cannot bypass database validation rules.
    *   *Isolation*: Uses Snapshot Isolation. Read concern majority prevents dirty reads.
    *   *Durability*: Oplog writes are synced to disk based on the write concern.

---

## 4. How do we use it in Java?
We start a session using `client.startSession()` and execute write statements by passing this `ClientSession` reference as the first argument to our collection methods.

```java
import com.mongodb.client.MongoClient;
import com.mongodb.client.ClientSession;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class BasicTransactionDemo {
    public void executeTransaction(MongoClient client, MongoCollection<Document> collection) {
        try (ClientSession session = client.startSession()) {
            session.startTransaction();
            try {
                collection.updateOne(session, Filters.eq("_id", "1"), Updates.set("status", "PROCESSING"));
                collection.updateOne(session, Filters.eq("_id", "2"), Updates.set("status", "COMPLETED"));
                session.commitTransaction();
            } catch (Exception e) {
                session.abortTransaction();
                throw e;
            }
        }
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**:
    *   **Full ACID Guarantees**: Safe updates across multiple collections.
    *   **Familiar SQL Patterns**: Simplifies migration of relational logic.
    *   **Snapshot Isolation**: Guarantees read consistency during execution.
*   **Cons**:
    *   **Performance Latency Cost**: Locking documents during a transaction limits database write throughput.
    *   **RAM Cache Limits**: WiredTiger caches uncommitted transaction data in memory. Large transactions can exhaust the cache.
    *   **Replica Set Constraint**: Transactions are not supported on standalone database processes. They require replica set metadata.

---

## 6. Common Mistakes
*   **Executing Slow Operations Inside Transactions**: Making external HTTP requests or running complex file I/O operations inside a transaction block. This keeps document locks open, causing other database requests to queue and time out.
*   **Missing Session Parameter**: Forgetting to pass the `session` reference as the first parameter to a driver operation. The operation will execute outside the transaction scope immediately, bypassing rollback safety.
*   **Overusing Transactions**: Using transactions where a simple nested document update would suffice. Single-document writes are already atomic and much faster.

---

## 7. When should we use it?
*   Use for bank transfers, reservation checkouts, or when updating multiple independent collections (like updating an inventory stock level and creating an order receipt).
*   Use when transactional safety is worth the minor write latency penalty.

---

## 8. When should we avoid it?
*   Do not use transactions when you can achieve the same atomicity by redesigning your schema to embed related data inside a single document.
*   Avoid for high-throughput batch imports or logging collections.

---

## 9. Code Examples

### A. SQL VS. MONGODB TRANSACTIONS

| Feature | Relational Database (SQL) | MongoDB |
| :--- | :--- | :--- |
| **Default Atomicity** | Atomic at row level | Atomic at single-document level (includes nested arrays) |
| **Concurrency Lock** | Row-level locks | Document-level locks (WiredTiger Record IDs) |
| **Scalability** | Standard on single node | Sharded transactions supported via two-phase commit |
| **Oplog Durability** | Redo/Undo transaction logs | Oplog synchronization with replica set write concerns |

---

### B. CONSISTENCY CONFIGURATIONS

#### 1. Write Concern & Retryable Writes
*   **Write Concern**: Controls write durability confirmations:
    *   `w:1` (Default): Returns success as soon as the primary replica node writes to memory.
    *   `w:majority`: Returns success only after a majority of replica nodes confirm the write.
    *   `j:true`: Guarantees the write is flushed to the journal on disk before returning success.
*   **Retryable Writes**: Configures the driver to automatically retry a write operation once if a connection failure occurs during transmission.

```java
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.MongoClientSettings;
import com.mongodb.WriteConcern;
import com.mongodb.ConnectionString;

public class ClientDurabilityConfig {
    public MongoClient createMongoClient(String connectionString) {
        MongoClientSettings settings = MongoClientSettings.builder()
            .applyConnectionString(new ConnectionString(connectionString))
            .writeConcern(WriteConcern.MAJORITY.withJournal(true)) // Ensure durability
            .retryWrites(true)                                      // Enable auto-retry
            .build();
        return MongoClients.create(settings);
    }
}
```

#### 2. Read Concern & Read Preference
*   **Read Concern**: Controls the isolation level of read queries:
    *   `local`: Returns the node's local data, vulnerable to rollbacks.
    *   `majority`: Returns data committed by a majority of replica nodes, preventing dirty reads.
    *   `linearizable`: Reads wait for majority confirmation, guaranteeing real-time consistency.
    *   `snapshot`: Used inside transactions to guarantee reads see a consistent snapshot of the data.
*   **Read Preference**: Directs queries to specific replica set nodes (e.g. `secondary` to offload reporting reads, or `primary` for consistency).

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.ReadConcern;
import com.mongodb.ReadPreference;
import org.bson.Document;

public class ReadConsistencyConfig {
    public MongoCollection<Document> configureReadBehavior(MongoCollection<Document> collection) {
        return collection
            .withReadConcern(ReadConcern.MAJORITY)
            .withReadPreference(ReadPreference.secondaryPreferred());
    }
}
```

---

### C. TRANSACTIONS IN JAVA

#### 1. Transaction Body Callback (Recommended)
Using the `.withTransaction()` wrapper is the recommended approach. It automatically retries the transaction if a transient network exception or election failure occurs.

```java
import com.mongodb.client.MongoClient;
import com.mongodb.client.ClientSession;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.TransactionBody;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class TransactionCallbackDemo {
    public boolean executeSafeTransfer(MongoClient client, MongoCollection<Document> accounts, String fromId, String toId, double amount) {
        try (ClientSession session = client.startSession()) {
            TransactionBody<Boolean> txnBody = () -> {
                // Deduct funds
                accounts.updateOne(session, Filters.eq("_id", fromId), Updates.inc("balance", -amount));
                
                // Add funds
                accounts.updateOne(session, Filters.eq("_id", toId), Updates.inc("balance", amount));
                return true;
            };

            // Runs the transaction and automatically retries on transient errors
            return session.withTransaction(txnBody);
        } catch (Exception e) {
            System.err.println("Transaction failed: " + e.getMessage());
            return false;
        }
    }
}
```

---

## 10. Hands-on Exercises

### Challenge 1: Bank Fund Transfer
Implement a bank ledger service. You must execute a money transfer between two accounts using explicit session management (`startTransaction`, `commitTransaction`, `abortTransaction`).
*   Verify the sender has a balance greater than or equal to the transfer amount.
*   If the sender balance is insufficient, throw an `IllegalStateException` to trigger a rollback.
*   Deduct `amount` from the sender and add `amount` to the receiver.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoClient;
import com.mongodb.client.ClientSession;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class BankTransferService {

    public boolean executeTransfer(MongoClient client, MongoCollection<Document> accounts, String fromId, String toId, double amount) {
        // TODO: Start session, manually manage transaction lifecycle, catch exceptions and abort.
        try (ClientSession session = client.startSession()) {
            session.startTransaction();
            try {
                Document sender = accounts.find(session, Filters.eq("_id", fromId)).first();
                if (sender == null || sender.getDouble("balance") < amount) {
                    throw new IllegalStateException("Insufficient funds");
                }

                accounts.updateOne(session, Filters.eq("_id", fromId), Updates.inc("balance", -amount));
                accounts.updateOne(session, Filters.eq("_id", toId), Updates.inc("balance", amount));

                session.commitTransaction();
                return true;
            } catch (Exception e) {
                session.abortTransaction();
                return false;
            }
        }
    }
}
```

### Challenge 2: E-Commerce Order Reservation Callback
Implement a checkout booking service. Use the recommended `session.withTransaction()` method callback to perform atomic cart processing.
*   Retrieve the item document by its `productId` in the inventory collection.
*   Verify the `stock` is greater than or equal to the requested checkout `quantity`. If stock is insufficient, throw a `RuntimeException` to roll back the write.
*   Deduct `quantity` from the inventory stock, and insert a new order document in the orders collection.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoClient;
import com.mongodb.client.ClientSession;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.TransactionBody;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class OrderCheckoutService {

    public boolean checkoutCart(MongoClient client, MongoCollection<Document> inventory, MongoCollection<Document> orders, String productId, int quantity, String userId) {
        // TODO: Implement transaction using session.withTransaction() callback
        try (ClientSession session = client.startSession()) {
            TransactionBody<Boolean> checkoutTx = () -> {
                Document product = inventory.find(session, Filters.eq("_id", productId)).first();
                if (product == null || product.getInteger("stock", 0) < quantity) {
                    throw new RuntimeException("Insufficient stock");
                }

                inventory.updateOne(session, Filters.eq("_id", productId), Updates.inc("stock", -quantity));
                orders.insertOne(session, new Document("userId", userId).append("productId", productId).append("quantity", quantity));
                return true;
            };
            return session.withTransaction(checkoutTx);
        } catch (Exception e) {
            return false;
        }
    }
}
```

### Verification Tests
Verify both transactional challenges using this JUnit 5 verification test suite:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoClient;
import com.mongodb.client.ClientSession;
import com.mongodb.client.MongoCollection;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class TransactionExercisesTest {

    @SuppressWarnings("unchecked")
    @Test
    void testBankTransferInsufficientFunds() {
        MongoClient mockClient = mock(MongoClient.class);
        ClientSession mockSession = mock(ClientSession.class);
        MongoCollection<Document> mockCol = mock(MongoCollection.class);

        when(mockClient.startSession()).thenReturn(mockSession);
        
        // Mock finding the sender with insufficient funds
        Document senderDoc = new Document("_id", "ACCT-1").append("balance", 10.0);
        var mockFind = mock(com.mongodb.client.FindIterable.class);
        when(mockCol.find(eq(mockSession), any(org.bson.conversions.Bson.class))).thenReturn(mockFind);
        when(mockFind.first()).thenReturn(senderDoc);

        BankTransferService service = new BankTransferService();
        boolean result = service.executeTransfer(mockClient, mockCol, "ACCT-1", "ACCT-2", 50.0);

        assertFalse(result);
        verify(mockSession, times(1)).abortTransaction();
    }

    @SuppressWarnings("unchecked")
    @Test
    void testCheckoutCartFailure() {
        MongoClient mockClient = mock(MongoClient.class);
        ClientSession mockSession = mock(ClientSession.class);
        MongoCollection<Document> inventory = mock(MongoCollection.class);
        MongoCollection<Document> orders = mock(MongoCollection.class);

        when(mockClient.startSession()).thenReturn(mockSession);

        OrderCheckoutService service = new OrderCheckoutService();
        boolean result = service.checkoutCart(mockClient, inventory, orders, "PROD-99", 5, "USER-1");

        assertFalse(result);
    }
}
```
