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

To execute multi-document transactions in Java, we allocate a logical session from the database connection pool, initiate a transaction context, and pass the session reference to each collection write operation.

### 4.1 Understanding the Java Transaction API

1. **`com.mongodb.client.MongoClient.startSession()`**:
   Spawns a new logical session (`ClientSession`). Sessions track causal consistency and serve as boundary scopes for transactions. `ClientSession` implements `AutoCloseable` and should be managed inside a `try-with-resources` block to ensure it releases socket descriptors upon completion.

2. **Transaction Lifecycle Controls**:
   *   `session.startTransaction()`: Initiates a new transaction context within the active session. This sets up the snapshot isolation boundary inside the WiredTiger storage engine.
   *   `session.commitTransaction()`: Writes all uncommitted changes from the private memory snapshot to the oplog, makes them visible globally, and releases locks on all modified document blocks.
   *   `session.abortTransaction()`: Aborts the transaction, rolls back all in-flight modifications inside the snapshot, and releases locks.

3. **Binding Operations to Sessions**:
   All database actions (e.g., `updateOne`, `insertOne`) accept the `ClientSession` object as their first parameter. **Note**: If you fail to pass the `session` object, the operation executes immediately outside the transaction block, bypassing the rollback boundary.

### 4.2 Dataset Visualization Example

#### Input Dataset (`orders` Collection):
```json
[
  { "_id": "1", "status": "INACTIVE" },
  { "_id": "2", "status": "PENDING" }
]
```

#### Step-by-Step Transaction Trace:

1. **`session.startTransaction()`**
   * Spawns a transaction snapshot.
2. **`collection.updateOne(session, eq("_id", "1"), set("status", "PROCESSING"))`**
   * *Private Snapshot*: `{ "_id": "1", "status": "PROCESSING" }`
   * *Global DB State*: `{ "_id": "1", "status": "INACTIVE" }` (Other concurrent users do not see this change).
3. **`collection.updateOne(session, eq("_id", "2"), set("status", "COMPLETED"))`**
   * *Private Snapshot*: `{ "_id": "2", "status": "COMPLETED" }`
   * *Global DB State*: `{ "_id": "2", "status": "PENDING" }`

#### Resolution Path:

*   **Path A: Success (`session.commitTransaction()`)**
    * The changes are committed. Global state becomes:
      ```json
      [
        { "_id": "1", "status": "PROCESSING" },
        { "_id": "2", "status": "COMPLETED" }
      ]
      ```
*   **Path B: Failure (`session.abortTransaction()`)**
    * The transaction is aborted and rolled back. Global state remains:
      ```json
      [
        { "_id": "1", "status": "INACTIVE" },
        { "_id": "2", "status": "PENDING" }
      ]
      ```

### 4.3 Java Implementation Code

Below is the implementation using the explicit session controls:

```java
import com.mongodb.client.MongoClient;
import com.mongodb.client.ClientSession;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class BasicTransactionDemo {
    public void executeTransaction(MongoClient client, MongoCollection<Document> collection) {
        // 1. Start a Logical Session using a try-with-resources block to auto-close the session
        try (ClientSession session = client.startSession()) {
            // 2. Start the transaction within the session
            session.startTransaction();
            try {
                // 3. Perform operations passing the active session reference as the first argument
                collection.updateOne(session, Filters.eq("_id", "1"), Updates.set("status", "PROCESSING"));
                collection.updateOne(session, Filters.eq("_id", "2"), Updates.set("status", "COMPLETED"));
                
                // 4. Commit all updates atomically
                session.commitTransaction();
            } catch (Exception e) {
                // 5. Abort and roll back all changes in the snapshot upon any execution failure
                session.abortTransaction();
                throw e; // Propagate the exception to client application
            }
        }
    }
}
```

#### Explaining the Operations and Syntax:
- **`client.startSession()`**: Returns an instance of `ClientSession` representing a logical database session. Logical sessions are a prerequisite for transactions in MongoDB.
- **`session.startTransaction()`**: Instructs the database server to start a transaction. Any following write operations associated with this session will be executed within this transaction context.
- **`collection.updateOne(session, filter, update)`**: The overloaded `updateOne` method accepts a `ClientSession` as its first parameter. Failing to pass this parameter will cause the driver to execute the write outside the transaction scope immediately.
- **`session.commitTransaction()`**: Notifies the server to commit all modifications in this transaction. The server writes the transaction oplog entries and applies the updates globally.
- **`session.abortTransaction()`**: If any error or exception occurs, this rolls back the transaction. The database discards all modification records associated with this transaction ID.

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

#### Explaining the Write Durability API:
*   **`com.mongodb.WriteConcern`**: Configures the level of write verification requested from the database replica set before returning success to the driver:
    *   `WriteConcern.W1` (`w:1`): Responds as soon as the local primary node commits the write in memory. Fast, but vulnerable if the primary node crashes before syncing.
    *   `WriteConcern.MAJORITY` (`w:majority`): Responds only after a majority of replica set nodes write the change. Protects against failover data loss.
    *   `.withJournal(true)` (`j:true`): Forces the node to write to the physical on-disk journal file before returning success, ensuring database durability.
*   **`retryWrites(true)`**: Passed to `MongoClientSettings.builder()`. Transparently intercepts transient network exceptions and automatically retries the failed write statement once, preventing transient database failure leaks to application code.

##### Dataset and Replication Failover Trace:

###### Replica Set Topology:
*   **Primary (P)**: Active writer.
*   **Secondary 1 (S1)**: Active replicator.
*   **Secondary 2 (S2)**: Active replicator (lagging).

###### Step-by-Step Execution Path with `WriteConcern.MAJORITY` and `retryWrites(true)`:

1. **Driver Issues Write Query**:
   * Statement: `collection.insertOne(new Document("_id", "ORD-99").append("total", 49.9));`
2. **Primary Node Receives and Processes**:
   * P logs the insert to its journal file and memory cache.
3. **Primary Replicates to Secondaries**:
   * P streams the oplog entry to S1 and S2.
   * S1 applies the write and replies with an acknowledgement (ACK).
   * S2 is slow/lagging and has not replied yet.
4. **Majority Check**:
   * Primary (P) has: 1 local ACK + 1 remote ACK (from S1) = 2 ACKs out of 3 total nodes. This meets the **MAJORITY** requirement.
5. **Primary Node Crashes or Network Partition Occurs**:
   * Before P can send the success acknowledgment response back to the Java client driver, the network connection is dropped or P goes offline.
6. **Driver Intercepts Error and Coordinates Retry**:
   * The Java driver encounters a socket exception. Because `retryWrites(true)` is set, the driver does not throw an exception immediately.
   * Instead, the driver queries the replica set to locate the new Primary. Meanwhile, S1 is elected as the new Primary.
   * the driver retries the insertion query on the new Primary (S1) using the same unique query transaction identifier.
7. **Idempotent Application**:
   * S1 checks its database logs, notices that the document with `_id: "ORD-99"` was already committed during step 3, and returns a successful response to the driver without executing a duplicate insert.

```java
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.MongoClientSettings;
import com.mongodb.WriteConcern;
import com.mongodb.ConnectionString;

public class ClientDurabilityConfig {
    public MongoClient createMongoClient(String connectionString) {
        // 1. Build client settings using the MongoClientSettings builder API
        MongoClientSettings settings = MongoClientSettings.builder()
            // 2. Set connection URI string
            .applyConnectionString(new ConnectionString(connectionString))
            // 3. Require write confirmations from a majority of nodes and sync to disk journal
            .writeConcern(WriteConcern.MAJORITY.withJournal(true)) 
            // 4. Automatically retry failed writes due to temporary network drops/elections
            .retryWrites(true)                                      
            .build();
        
        // 5. Build and return the client instance
        return MongoClients.create(settings);
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`WriteConcern.MAJORITY`**: Ensures that a write propagates to a majority of replica set members before the application receives a success. This guards against rolling back changes if the primary node goes offline.
- **`.withJournal(true)`**: In conjunction with `WriteConcern`, this forces the MongoDB server to commit the transaction data to the physical write-ahead log (journal) on disk.
- **`retryWrites(true)`**: Tells the MongoDB driver to retry single-document writes (like `insertOne`, `updateOne`, `deleteOne`) automatically once if the connection is lost during execution, making replica set elections transparent to the client.

---

#### 2. Read Concern & Read Preference

#### Explaining the Read Consistency API:
*   **`com.mongodb.ReadConcern`**: Specifies the isolation and consistency characteristics of query reads:
    *   `ReadConcern.LOCAL`: Reads the local node's data. Fast, but data is uncommitted globally and prone to rollback.
    *   `ReadConcern.MAJORITY`: Reads only data verified by a majority of replica set members. Prevents dirty/phantom reads of uncommitted changes.
    *   `ReadConcern.SNAPSHOT`: Enforces Snapshot Isolation inside transaction sessions. Ensures all operations within the transaction read a consistent view of committed data.
*   **`com.mongodb.ReadPreference`**: Controls which physical replica set node the query driver targets:
    *   `ReadPreference.primary()`: Directs all reads to the primary replica node (guarantees real-time read-after-write consistency).
    *   `ReadPreference.secondaryPreferred()`: Offloads query reads to secondary nodes to scale read capacity, falling back to the primary node only if secondaries are offline.

##### Dataset and Replication Lag Trace:

###### Database Node States:
*   **Primary (P)**: Has uncommitted or local-only updates: `{ "_id": "ITEM-1", "stock": 5 }`.
*   **Secondary 1 (S1)**: Replicated majority-committed data: `{ "_id": "ITEM-1", "stock": 10 }`.
*   **Secondary 2 (S2)**: Replicated majority-committed data: `{ "_id": "ITEM-1", "stock": 10 }`.

###### Step-by-Step Read Request Trace:

1. **Client Performs Read Request**:
   * Query: `collection.find(Filters.eq("_id", "ITEM-1")).first();`
   * Configuration: `ReadConcern.MAJORITY` and `ReadPreference.secondaryPreferred()`.
2. **Driver Routes Query**:
   * The driver targets secondary node **S1** to offload read traffic from the Primary.
3. **Data Filtering**:
   * S1 receives the query. Although the Primary has a local uncommitted state where `stock` is `5`, this update has not been replicated to the majority yet.
   * S1 filters out any uncommitted data block and returns the last majority-acknowledged state: `{ "_id": "ITEM-1", "stock": 10 }`.
   * This guarantees that the reading application does not see uncommitted data that could be rolled back if the Primary node fails (prevents "dirty reads").

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.ReadConcern;
import com.mongodb.ReadPreference;
import org.bson.Document;

public class ReadConsistencyConfig {
    public MongoCollection<Document> configureReadBehavior(MongoCollection<Document> collection) {
        // withReadConcern() and withReadPreference() return new instances of MongoCollection
        // with the specified read concern and read preference configurations.
        return collection
            .withReadConcern(ReadConcern.MAJORITY)
            .withReadPreference(ReadPreference.secondaryPreferred());
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`collection.withReadConcern(ReadConcern.MAJORITY)`**: Configures the returned collection instance to use the `MAJORITY` read concern. This prevents reading data that might be rolled back due to primary node failure.
- **`collection.withReadPreference(ReadPreference.secondaryPreferred())`**: Instructs the driver to target secondary nodes when executing query reads. This scales read operations across the replica set, though read data might be slightly stale compared to the primary node.

---

### C. TRANSACTIONS IN JAVA

#### 1. Transaction Body Callback (Recommended)

Using the `.withTransaction()` wrapper is the recommended transaction execution pattern. Instead of writing custom try-catch blocks to handle database rollbacks and election retry attempts manually, we define a callback block using the functional interface `com.mongodb.client.TransactionBody<T>`.

#### Explaining the Transaction Callback retry Logic:
The `.withTransaction(TransactionBody)` API automatically intercepts database exceptions and manages:
1.  **TransientTransactionError**: If a network failure occurs or a replica set election changes the primary node while executing the callback block, the driver automatically re-runs the *entire* callback block from the beginning.
2.  **UnknownTransactionCommitResult**: If a network failure occurs during the commit phase (so the client doesn't know if the transaction succeeded), the driver automatically retries the `commitTransaction` call.

##### Dataset Visualization Example

###### Input Dataset (`accounts` Collection):
```json
[
  { "_id": "ACCT-1", "balance": 100.0 },
  { "_id": "ACCT-2", "balance": 50.0 }
]
```

###### Step-by-Step Transaction Callback execution:
1.  **Callback execution begins**. The driver starts a new transaction session context.
2.  **Deduct Funds**: `accounts.updateOne(session, eq("_id", "ACCT-1"), inc("balance", -30.0))`
    * *Snapshot State*: ACCT-1 balance is 70.0.
    * *Global DB State*: ACCT-1 balance is still 100.0 (Uncommitted, isolated).
3.  **Add Funds**: `accounts.updateOne(session, eq("_id", "ACCT-2"), inc("balance", 30.0))`
    * *Snapshot State*: ACCT-2 balance is 80.0.
    * *Global DB State*: ACCT-2 balance is still 50.0.
4.  **Callback returns `true`**.
5.  **Commit Phase**: The driver commits the transaction automatically. If commit fails with transient errors, the driver retries.

###### Final Output Dataset (Commited State):
```json
[
  { "_id": "ACCT-1", "balance": 70.0 },
  { "_id": "ACCT-2", "balance": 80.0 }
]
```

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
        // 1. Open a Logical Session using a try-with-resources statement
        try (ClientSession session = client.startSession()) {
            
            // 2. Define the callback implementation block using the TransactionBody functional interface
            TransactionBody<Boolean> txnBody = () -> {
                // Deduct funds from the sender's account. Updates.inc decreases balance when amount is positive.
                accounts.updateOne(session, Filters.eq("_id", fromId), Updates.inc("balance", -amount));
                
                // Add funds to the receiver's account
                accounts.updateOne(session, Filters.eq("_id", toId), Updates.inc("balance", amount));
                
                // Return transaction status result (true indicates successful execution of operations)
                return true;
            };

            // 3. Execute the transaction body block.
            // Under the hood, withTransaction automatically starts a transaction, executes the callback,
            // catches TransientTransactionErrors to retry execution, and commits the transaction.
            return session.withTransaction(txnBody);
        } catch (Exception e) {
            // 4. Handle persistent transaction failures
            System.err.println("Transaction failed permanently: " + e.getMessage());
            return false;
        }
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`TransactionBody<T>`**: A functional interface containing a single method `T execute()`. Code inside this interface represents the operations that must succeed or fail as a single atomic unit.
- **`session.withTransaction(txnBody)`**: The primary high-level API for transaction execution. It manages the transaction lifecycle, executing `startTransaction()` and calling the lambda.
  - If the callback returns a value or exits without throwing, `withTransaction()` commits the transaction.
  - If the callback throws an exception, it rolls back by calling `abortTransaction()`.
  - It automatically retries on transient errors (`TransientTransactionError`) by re-running the lambda expression, and retries the commit if the commit status is unclear.

---

## 10. Hands-on Exercises

### Challenge 1: Bank Fund Transfer
Implement a bank ledger service. You must execute a money transfer between two accounts using explicit session management (`startTransaction`, `commitTransaction`, `abortTransaction`).
*   Verify the sender has a balance greater than or equal to the transfer amount.
*   If the sender balance is insufficient, throw an `IllegalStateException` to trigger a rollback.
*   Deduct `amount` from the sender and add `amount` to the receiver.

##### Dataset and execution Trace:

###### Input Dataset (`accounts` Collection):
```json
[
  { "_id": "ACCT-1", "balance": 150.0 },
  { "_id": "ACCT-2", "balance": 50.0 }
]
```

###### Scenario A: Successful Transfer of 100.0:
1. **Transaction Starts**: `session.startTransaction()`.
2. **Find Sender**: `accounts.find(session, Filters.eq("_id", "ACCT-1")).first()` fetches `{ "_id": "ACCT-1", "balance": 150.0 }`.
3. **Validate Balance**: Balance `150.0 >= 100.0` check passes.
4. **Update Sender**: Deducts `100.0` from `ACCT-1`. Snapshot balance becomes `50.0`.
5. **Update Receiver**: Adds `100.0` to `ACCT-2`. Snapshot balance becomes `150.0`.
6. **Commit**: `session.commitTransaction()` executes. Changes are written globally.
7. **Final State**:
   ```json
   [
     { "_id": "ACCT-1", "balance": 50.0 },
     { "_id": "ACCT-2", "balance": 150.0 }
   ]
   ```

###### Scenario B: Insufficient Balance (Attempt to transfer 200.0):
1. **Transaction Starts**: `session.startTransaction()`.
2. **Find Sender**: `accounts.find(session, Filters.eq("_id", "ACCT-1")).first()` fetches `{ "_id": "ACCT-1", "balance": 150.0 }`.
3. **Validate Balance**: Balance `150.0 < 200.0`. An `IllegalStateException("Insufficient funds")` is thrown.
4. **Catch Block**: The catch block intercepts the exception and executes `session.abortTransaction()`.
5. **Aborted State**: The transaction snapshot is discarded. Global balances remain unchanged (`150.0` and `50.0`).

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
                // Find the sender document within the active transaction snapshot
                Document sender = accounts.find(session, Filters.eq("_id", fromId)).first();
                
                // If sender does not exist or has insufficient balance, throw an exception to abort
                if (sender == null || sender.getDouble("balance") < amount) {
                    throw new IllegalStateException("Insufficient funds");
                }

                // Deduct amount from sender and add amount to receiver
                accounts.updateOne(session, Filters.eq("_id", fromId), Updates.inc("balance", -amount));
                accounts.updateOne(session, Filters.eq("_id", toId), Updates.inc("balance", amount));

                // Commit the updates atomically
                session.commitTransaction();
                return true;
            } catch (Exception e) {
                // Roll back any changes if any exception is encountered
                session.abortTransaction();
                return false;
            }
        }
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`accounts.find(session, Filters.eq("_id", fromId)).first()`**: Retrieves the sender document. By passing `session`, the read is bound to the transaction snapshot.
- **`Updates.inc("balance", -amount)`**: Atomically decreases the balance. The minus sign is used since `inc` adds the specified value.
- **`session.abortTransaction()`**: Essential in the `catch` block to unlock any locked documents in WiredTiger and abort the current transaction session.

---

### Challenge 2: E-Commerce Order Reservation Callback
Implement a checkout booking service. Use the recommended `session.withTransaction()` method callback to perform atomic cart processing.
*   Retrieve the item document by its `productId` in the inventory collection.
*   Verify the `stock` is greater than or equal to the requested checkout `quantity`. If stock is insufficient, throw a `RuntimeException` to roll back the write.
*   Deduct `quantity` from the inventory stock, and insert a new order document in the orders collection.

##### Dataset and Execution Trace:

###### Input Datasets:
*   `inventory` Collection:
    ```json
    [
      { "_id": "PROD-10", "name": "Wireless Mouse", "stock": 10 }
    ]
    ```
*   `orders` Collection:
    ```json
    []
    ```

###### Scenario A: Checkout of 3 Units:
1. **Callback Executes**: The driver manages `ClientSession` and starts the transaction.
2. **Retrieve Product**: `inventory.find(session, Filters.eq("_id", "PROD-10")).first()` returns mouse document.
3. **Verify Stock**: Stock `10 >= 3` check passes.
4. **Update Stock**: Decrements `PROD-10` stock by `3` inside the snapshot. Snapshot stock becomes `7`.
5. **Insert Order**: Inserts `{ "userId": "USER-5", "productId": "PROD-10", "quantity": 3 }` into the `orders` collection snapshot.
6. **Return `true`**: Callback successfully completes. The driver commits transaction.
7. **Final State**:
   * `inventory` Collection:
     ```json
     [
       { "_id": "PROD-10", "name": "Wireless Mouse", "stock": 7 }
     ]
     ```
   * `orders` Collection:
     ```json
     [
       { "_id": "...", "userId": "USER-5", "productId": "PROD-10", "quantity": 3 }
     ]
     ```

###### Scenario B: Checkout of 12 Units (Insufficient Stock):
1. **Callback Executes**: Transaction session starts.
2. **Verify Stock**: Product stock `10 < 12`. A `RuntimeException("Insufficient stock")` is thrown.
3. **Abort & Rollback**: The thrown exception causes `withTransaction` to abort the transaction.
4. **Outcome**: No changes committed. Inventory stock remains `10`, no order is inserted.

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
            // Define the transactional callback body
            TransactionBody<Boolean> checkoutTx = () -> {
                // Find product within transaction session context
                Document product = inventory.find(session, Filters.eq("_id", productId)).first();
                
                // If product is not found or has insufficient stock, throw exception to abort transaction
                if (product == null || product.getInteger("stock", 0) < quantity) {
                    throw new RuntimeException("Insufficient stock");
                }

                // Decrement inventory stock count
                inventory.updateOne(session, Filters.eq("_id", productId), Updates.inc("stock", -quantity));
                
                // Insert a new order record into orders collection
                orders.insertOne(session, new Document("userId", userId)
                    .append("productId", productId)
                    .append("quantity", quantity));
                
                return true;
            };
            
            // Execute callback with automatic commit and error retry logic
            return session.withTransaction(checkoutTx);
        } catch (Exception e) {
            // Return false if transaction failed permanently
            return false;
        }
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`inventory.find(session, Filters.eq("_id", productId)).first()`**: Retrieves the inventory document inside the snapshot context using the passed session.
- **`inventory.updateOne(session, Filters.eq("_id", productId), Updates.inc("stock", -quantity))`**: Atomically decreases the stock. Note that `Updates.inc` takes a negative value to decrement.
- **`orders.insertOne(session, ...)`**: Inserts a new order document. By passing `session`, this operation is isolated from other clients until the transaction is committed.

---

### Verification Tests

Below is the JUnit 5 verification test suite. It uses Mockito to mock database dependencies and verify the transaction lifecycle commands under different paths.

#### Detailed Testing & Verification Explanation:
*   **`mock(MongoClient.class)`**: Spawns mock instances of MongoDB driver clients.
*   **`when(mockClient.startSession()).thenReturn(mockSession)`**: Sets up the mock client to return a mock session when `startSession` is called.
*   **`when(mockCol.find(...)).thenReturn(mockFind)`**: Mocks the query builder chain.
*   **`verify(mockSession, times(1)).abortTransaction()`**: Asserts that `abortTransaction()` was called exactly once on the mock session when `IllegalStateException` was triggered, confirming that rollback logic was executed.

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
        // 1. Arrange mock objects
        MongoClient mockClient = mock(MongoClient.class);
        ClientSession mockSession = mock(ClientSession.class);
        MongoCollection<Document> mockCol = mock(MongoCollection.class);

        // 2. Configure mock client behaviors
        when(mockClient.startSession()).thenReturn(mockSession);
        
        // Mock finding the sender with insufficient funds (10.0 balance is less than 50.0 transfer amount)
        Document senderDoc = new Document("_id", "ACCT-1").append("balance", 10.0);
        var mockFind = mock(com.mongodb.client.FindIterable.class);
        when(mockCol.find(eq(mockSession), any(org.bson.conversions.Bson.class))).thenReturn(mockFind);
        when(mockFind.first()).thenReturn(senderDoc);

        // 3. Act
        BankTransferService service = new BankTransferService();
        boolean result = service.executeTransfer(mockClient, mockCol, "ACCT-1", "ACCT-2", 50.0);

        // 4. Assert and Verify
        assertFalse(result); // The transfer should fail
        verify(mockSession, times(1)).abortTransaction(); // Verify rollback was triggered
    }

    @SuppressWarnings("unchecked")
    @Test
    void testCheckoutCartFailure() {
        // 1. Arrange mock objects
        MongoClient mockClient = mock(MongoClient.class);
        ClientSession mockSession = mock(ClientSession.class);
        MongoCollection<Document> inventory = mock(MongoCollection.class);
        MongoCollection<Document> orders = mock(MongoCollection.class);

        // 2. Configure mock client behaviors
        when(mockClient.startSession()).thenReturn(mockSession);

        // 3. Act
        OrderCheckoutService service = new OrderCheckoutService();
        boolean result = service.checkoutCart(mockClient, inventory, orders, "PROD-99", 5, "USER-1");

        // 4. Assert
        assertFalse(result); // The transaction should fail since inventory returns null (insufficient stock)
    }
}
```
