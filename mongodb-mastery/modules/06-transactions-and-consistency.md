# Module 06: Transactions & Distributed Consistency

## 1. What Problem This Module Solves
In a distributed database, managing transactions and consistency levels requires balancing write latency, read availability, and global consistency guarantees. 

A senior engineer must understand the internal mechanics of Write Concerns, Read Concerns, Causal Consistency, transaction lock management, deadlock detection, and how WiredTiger uses Multi-Version Concurrency Control (MVCC) to enforce ACID properties without blocking reads. Selecting incorrect settings can lead to dirty reads, data loss during failovers, or thread exhaustion under heavy workloads.

---

## 2. Why This Topic Matters
Using default consistency settings can lead to data loss or integrity issues. For example, reading from eventually consistent secondaries without Causal Consistency can cause "time-travel" reads where updates vanish. Similarly, selecting `linearizable` read concerns for high-frequency APIs can cause performance degradation.

Understanding the timing characteristics of distributed consensus, lock timeouts, and how secondary nodes coordinate logical cluster time enables developers to build highly reliable applications that preserve transactional safety across multiple documents and collections.

---

## 3. Core Concepts & Internals

### 3.1 Write Concern Majority Consensus Timing Analysis
Write concern controls when a write is confirmed to the client driver. Under a `{ w: "majority" }` write concern, the primary node must verify that the write has been written to the oplog of a majority of voting nodes before returning success.

#### Network Timeline of `{ w: "majority" }` Write Concern:
```
[Client]                [Primary Node]             [Secondary Node 1]        [Secondary Node 2]
   │                          │                            │                          │
   │─── 1. Send Write ───────>│                            │                          │
   │    (w: "majority")       │─── 2. Write to local.oplog │                          │
   │                          │    (Mark Dirty Page)       │                          │
   │                          │─── 3. Fetch Oplog (Poll) ─>│                          │
   │                          │                            │── 4. Apply Oplog         │
   │                          │                            │   (Confirm status)       │
   │                          │<── 5. Confirm oplog state ─│                          │
   │                          │─── 6. Fetch Oplog (Poll) ────────────────────────────>│
   │                          │                                                       │── 7. Apply Oplog
   │                          │                                                       │   (Confirm status)
   │                          │<── 8. Confirm oplog state ────────────────────────────│
   │                          │
   │                          │ (Majority threshold met: 2 of 3 nodes confirmed)
   │<── 9. Write Acknowledged │
   │
```

#### What Happens on Secondary Node Network Failures:
*   If a secondary node goes offline and the replica set cannot reach a majority (e.g. 2 nodes are offline in a 3-node set), the primary blocks the write acknowledgment.
*   To prevent the client thread from blocking indefinitely, you should specify a write concern timeout (`wtimeout`).
*   If the `wtimeout` limit is hit, MongoDB returns a write concern error, but **does not roll back** the write on the nodes that already applied it. The write remains on the primary and must be cleaned up or resolved by the application client.

#### Step-by-Step Handling of Write Concern Failures:
1.  **Detect Network Partition**: If the primary loses contact with a majority of nodes, it steps down to secondary mode, closing existing client sockets.
2.  **Election Window**: The remaining nodes hold an election. If a majority is reachable among them, a new primary is elected.
3.  **Rollback Resolution**: When the old primary rejoins, it syncs its oplog with the new primary. Any writes that were acknowledged with `{ w: 1 }` but not replicated to the majority commit point are written to rollback files and removed from the active database.

---

### 3.2 Read Concern Levels & Rollback Mitigation
Read concern controls the visibility and durability of the read data.

*   **`local` / `available`**: Returns the node's current local data. This does not verify if the write has been replicated to other nodes. If the primary node fails, this data can be rolled back.
*   **`majority`**: Returns data that has been written to a majority of nodes and cannot be rolled back.
    *   *Mechanism*: MongoDB maintains a **Majority Commit Point** pointer in memory. A read with `majority` concern queries a snapshot of the database at this commit point, avoiding uncommitted "dirty" data.
*   **`linearizable`**: Guarantees that the read operation returns the result of the most recent write.
    *   *Mechanism*: The primary node must contact a majority of other replica set members *during the read query* to verify it is still the primary. This prevents stale reads if a network split has occurred.
*   **`snapshot`**: Used in multi-document transactions. It provides a point-in-time snapshot of the database at the start of the transaction session.

---

### 3.3 Causal Consistency & Logical Cluster Time (`ClusterTime`)
*   **The Problem**: Reading from secondaries can result in stale reads due to replication lag. A client could write an update to the primary, immediately query a secondary, and fail to see their own change.
*   **The Resolution**: **Causal Consistency Sessions**.

```
           [Primary Node]                            [Secondary Node]
                  │                                         │
 1. Write (Success, returns ClusterTime: T)                 │
                  │                                         │
 2. Oplog Sync (Delayed due to network lag) ───────────────>│ (Lagging at T-1)
                  │                                         │
                  │                                         │
           [Client Driver]                                  │
                  │                                         │
 3. Send Read Request (ClusterTime: T) ────────────────────>│ (Blocks query)
                                                            │
                                                     4. Oplog Catches Up to T
                                                            │
 5. Read Result (Returned to Client) <──────────────────────│
```

#### Detailed Blocking Mechanics:
1.  When a client performs a write, the primary node returns the logical cluster time (`$clusterTime`) representing the transaction position in the oplog.
2.  The client driver captures and tracks this `$clusterTime`.
3.  When the client sends a subsequent read request to a secondary within the same session, the driver attaches the `$clusterTime` parameter.
4.  The secondary node receives the request and evaluates the timestamp. If its local oplog has not replicated up to that timestamp, it blocks the query execution.
5.  The secondary node waits (`afterClusterTime` wait loop) until the oplog applier processes the required updates.
6.  Once the secondary node catches up, it executes the query and returns the results.
7.  *Tuning Tip*: To prevent client threads from hanging during replication lag spikes, configure appropriate **Socket Timeout** (`socketTimeoutMS`) and **Max Time MS** (`maxTimeMS`) settings.

#### Enabling Causal Consistency in Client Drivers:
*   **Node.js**:
    ```javascript
    const session = client.startSession({ causalConsistency: true });
    ```
*   **Java**:
    ```java
    ClientSessionOptions options = ClientSessionOptions.builder().causalConsistency(true).build();
    ClientSession session = client.startSession(options);
    ```

---

### 3.4 Transaction Lock Management & Deadlock Detection
MongoDB transactions acquire locks at the document level.
*   **Exclusive Document Locks (`X`)**: Modified documents are locked exclusively. These locks are held for the entire duration of the transaction.
*   **WiredTiger Snapshot Isolation**: Reads do not acquire locks, allowing concurrent reads to access older versions of the documents without blocking.
*   **Lock Timeout Configuration**: The parameter `maxTransactionLockRequestTimeoutMillis` (default: 5 milliseconds) controls how long an operation inside a transaction waits to acquire a document lock. If a conflict occurs and the lock cannot be acquired within this time, the transaction aborts immediately to prevent blocking other write paths.
*   **Deadlock Detection**: WiredTiger maintains a dependency graph of transaction locks. If a cycle is detected (e.g. Transaction A holds Lock 1 and waits for Lock 2, while Transaction B holds Lock 2 and waits for Lock 1), WiredTiger immediately aborts one of the transactions, breaking the deadlock and throwing a conflict error that the client must retry.

---

## 4. Practical Examples

### Production-Grade Spring Boot Multi-Document Transaction Service
The following Java service class demonstrates how to manage multi-document transactions in a Spring Boot application, complete with custom retry logic for transient write conflicts and commit errors.

```java
package com.ecommerce.domain.user.domain.service;

import com.mongodb.MongoException;
import com.mongodb.MongoTransactionException;
import com.mongodb.WriteConcern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.mongodb.MongoTransactionManager;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Update;
import org.springframework.stereotype.Service;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.TransactionCallbackWithoutResult;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class TransactionalLedgerService {
    private static final Logger log = LoggerFactory.getLogger(TransactionalLedgerService.class);
    
    private final MongoTemplate mongoTemplate;
    private final TransactionTemplate transactionTemplate;

    public TransactionalLedgerService(MongoTemplate mongoTemplate, MongoTransactionManager transactionManager) {
        this.mongoTemplate = mongoTemplate;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
    }

    public void transferBalanceWithRetry(final String fromAccountId, final String toAccountId, final double amount) {
        int maxAttempts = 3;
        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                executeTransfer(fromAccountId, toAccountId, amount);
                log.info("Ledger balance transfer committed successfully on attempt {}", attempt);
                return; // Success
            } catch (MongoTransactionException | MongoException ex) {
                if ((ex.hasErrorLabel(MongoException.TRANSIENT_TRANSACTION_ERROR_LABEL) || 
                     ex.hasErrorLabel(MongoException.UNKNOWN_TRANSACTION_COMMIT_RESULT_LABEL)) && attempt < maxAttempts) {
                    log.warn("Transient transaction failure. Retrying transfer... Attempt {} of {}", attempt, maxAttempts);
                    try {
                        Thread.sleep(100 * attempt); // Exponential backoff
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw new RuntimeException("Transaction retry interrupted", ie);
                    }
                    continue;
                }
                log.error("Permanent transaction error encountered during ledger transfer.");
                throw ex; // Reraise permanent exception
            }
        }
    }

    private void executeTransfer(final String fromAccountId, final String toAccountId, final double amount) {
        transactionTemplate.execute(new TransactionCallbackWithoutResult() {
            @Override
            protected void doInTransactionWithoutResult(TransactionStatus status) {
                mongoTemplate.setWriteConcern(WriteConcern.MAJORITY);

                Query senderQuery = new Query(Criteria.where("_id").is(fromAccountId));
                Account sender = mongoTemplate.findOne(senderQuery, Account.class, "accounts");
                if (sender == null || sender.getBalance() < amount) {
                    throw new IllegalArgumentException("Insufficient funds or account not found: " + fromAccountId);
                }

                Query deductQuery = new Query(Criteria.where("_id").is(fromAccountId).and("balance").is(sender.getBalance()));
                Update deductUpdate = new Update().inc("balance", -amount);
                var deductResult = mongoTemplate.updateFirst(deductQuery, deductUpdate, "accounts");
                
                if (deductResult.getModifiedCount() == 0) {
                    throw new MongoTransactionException("Conflict detected on sender account balance. Aborting.");
                }

                Query creditQuery = new Query(Criteria.where("_id").is(toAccountId));
                Update creditUpdate = new Update().inc("balance", amount);
                mongoTemplate.updateFirst(creditQuery, creditUpdate, "accounts");
            }
        });
    }

    public static class Account {
        private String id;
        private double balance;

        public String getId() { return id; }
        public void setId(String id) { this.id = id; }
        public double getBalance() { return balance; }
        public void setBalance(double balance) { this.balance = balance; }
    }
}
```

---

## 5. Trade-offs & Alternatives

Distributed consistency parameters involve trade-offs between performance and durability:

| Consistency Configuration | Latency Cost | Rollback Risk | Write Throughput | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **`{w: 1, j: false}`** | **None**: The driver receives success as soon as the memory buffer is updated. | **High**: Data can be lost if the node crashes before flushing or replicating. | **Maximum** | Logs, clickstream tracking, non-critical metrics. |
| **`{w: majority, j: true}`** | **Medium**: Requires network roundtrips to secondaries and disk flushes. | **None**: Data is written to disk across a majority of nodes. | **Medium** | User accounts, configuration changes, payments. |
| **Linearizable Read Concern** | **High**: The primary node must contact a majority of nodes during every read query. | **None**: Stale reads are impossible. | **High (Reads affected)** | High-value operations, real-time security clearances. |
| **Multi-document Transactions** | **High**: Acquires exclusive locks on all modified documents. | **Low**: Handled by the transaction engine. | **Low** | Banking transfers, inventory reconciliation. |

---

## 6. Common Mistakes & Anti-patterns
*   **Transactions Running Too Long**: Performing slow, external operations (like calling a payment gateway or sending an email) inside a transaction. This holds locks on the affected documents, blocking other database writes and eventually triggering transaction timeout aborts (default 60 seconds).
*   **Write Concern Misalignment**: Using `{ w: 1 }` writes for critical transactions while using `majority` read concern for reads. The read query may fail to return the updated data until replication completes, breaking consistency.
*   **Ignoring Transaction Limit Restrictions**: Trying to execute DDL operations (like creating indexes or collections) inside a transaction, which is not supported by MongoDB and will cause the transaction to fail.

---

## 7. Hands-on Exercises
1.  Connect to a local replica set.
2.  Perform a write query with write concern `{ w: 3, wtimeout: 1000 }` while one secondary node is offline. Observe the timeout failure.
3.  Write a script that starts a session, executes a transaction, and forces a write conflict by modifying the same document in a separate thread. Verify the conflict is caught.
4.  Configure a causally consistent session in your driver and measure replication lag effects by querying a secondary node.

---

## 8. Mini-Project: Concurrency-Safe Ledger Updates (Node.js API)
The following Node.js script provides a complete implementation of the currency transfer service, executing a safe bank ledger update across multiple account documents with automatic retries for transient transaction errors.

```javascript
const { MongoClient } = require('mongodb');
const log = require('console');

async function executeTransferLedger(uri, fromId, toId, amount) {
  const client = new MongoClient(uri, { maxPoolSize: 10 });
  await client.connect();
  
  const session = client.startSession();
  const accounts = client.db('ledger_db').collection('accounts');
  
  let attempt = 0;
  const maxRetries = 3;

  while (attempt < maxRetries) {
    try {
      attempt++;
      await session.withTransaction(async () => {
        log.info(`Transfer attempt ${attempt} starting...`);
        
        // 1. Fetch sender balance inside transaction
        const sender = await accounts.findOne({ _id: fromId }, { session });
        if (!sender || sender.balance < amount) {
          throw new Error("Insufficient funds or account not found.");
        }

        // 2. Perform optimistic deduction check
        const deductResult = await accounts.updateOne(
          { _id: fromId, balance: sender.balance },
          { $inc: { balance: -amount }, $set: { updatedAt: new Date() } },
          { session }
        );

        if (deductResult.modifiedCount === 0) {
          throw new Error("Write Conflict: Sender account updated by another process.");
        }

        // 3. Credit receiver account
        await accounts.updateOne(
          { _id: toId },
          { $inc: { balance: amount }, $set: { updatedAt: new Date() } },
          { session }
        );

        log.info("Inner transaction commands succeeded.");
      }, {
        readConcern: { level: 'snapshot' },
        writeConcern: { w: 'majority', j: true }
      });

      log.info("Ledger transaction successfully committed.");
      await session.endSession();
      await client.close();
      return;

    } catch (error) {
      log.warn(`Attempt ${attempt} failed: ${error.message}`);
      
      const isTransient = error.hasErrorLabel && 
        (error.hasErrorLabel('TransientTransactionError') || 
         error.hasErrorLabel('UnknownTransactionCommitResult'));
         
      if (isTransient && attempt < maxRetries) {
        log.warn("Retrying transient transaction...");
        await new Promise(res => setTimeout(res, 200 * attempt));
        continue;
      }
      
      await session.endSession();
      await client.close();
      throw error;
    }
  }
}
```

---

## 9. Interview Questions

### Q1: How does MongoDB's `readConcern: "majority"` prevent dirty reads during replica set failovers?
**Answer**: If a write is executed with `{ w: 1 }`, it is only written to the primary node. If the primary node crashes before replicating this write, a secondary is elected primary. The new primary does not have this write, and the old primary will roll it back when it recovers. A client reading with `readConcern: "local"` would have read this rolled-back data (a dirty read). A read with `readConcern: "majority"` queries the database snapshot at the **Majority Commit Point**—the point where writes have been confirmed by a majority of nodes. Since the un-replicated write never reached this point, the query does not see it, preventing dirty reads.

### Q2: What is the difference between Causal Consistency and Linearizability?
**Answer**: Causal Consistency guarantees that operations that are causally related are seen in the same order by all nodes (e.g. read-your-own-writes, monotonic reads/writes). It does not enforce a global time order across unrelated operations. Linearizability guarantees that *all* operations are seen in a single, global real-time order. Linearizability is stronger but requires the primary node to contact a majority of replica nodes during every read query to confirm its status, which increases latency compared to Causal Consistency.

### Q3: What is logical cluster time (`ClusterTime`) and how is it used to coordinate causally consistent sessions?
**Answer**: Logical cluster time (`ClusterTime`) is a hybrid logical clock timestamp that MongoDB uses to order operations across the replica set. When a write is performed, MongoDB returns the current logical cluster time. The application driver saves this value. When executing subsequent reads on secondary nodes, the driver passes the saved cluster time. The secondary node checks its local replication state; if its logical time lags behind the driver's timestamp, it blocks the query until it replicates the required updates, ensuring the client reads their own writes.

---

---

---

## 10. Production Runbook & Deployment Guidelines

### 1. Transaction Lock Timeout Configurations
To prevent transactions from holding locks indefinitely during write conflicts, configure the lock request timeout dynamically:
```javascript
db.adminCommand({
  setParameter: 1,
  maxTransactionLockRequestTimeoutMillis: 5 // Terminate lock wait after 5ms
});
```

### 2. Monitoring Stale Read Operations
Verify replica lag states to prevent stale read operations on secondaries:
```javascript
rs.printSecondaryReplicationInfo();
```
If lag exceeds 5 seconds, route critical read operations to the primary node using read preference `{ readPreference: { mode: "primary" } }`.

## 11. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Transaction Timeout Aborts (Code 251)
*   **Failure Mode**: Transactions running longer than **60 seconds** are aborted automatically, releasing locks.
*   **Resolution**: Keep transactions short, and avoid making external network calls or slow operations inside the transaction block.

### 2. Write Concern Timeout Errors (wtimeout)
*   **Failure Mode**: Writes using `{ w: "majority" }` fail with timeout errors if secondary replication lags behind the limit.
*   **Resolution**: Configure write timeouts (`wtimeout`) in client drivers, and monitor replication lag spikes using automated alerting scripts.

### 3. Causal Consistency Logical Clock Drift
*   **Failure Mode**: Stale secondary nodes block subsequent reads indefinitely if replication lag prevents them from catching up to the client session cluster time.
*   **Resolution**: Set read timeouts on client sessions to prevent threads from hanging when nodes are down.

---

## 12. Summary
Managing distributed consistency requires aligning read concerns, write concerns, and transaction boundaries. By leveraging WiredTiger's lock-free MVCC snapshots, using causally consistent sessions to offload reads safely, and implementing transaction retry loops, senior database developers build high-throughput, consistent distributed applications.

---

## 12. Enterprise Case Study: Ledger Deadlocks & Write Conflicts in Financial Microservices

### 1. Scenario Description
A ledger service manages customer balance transfers across accounts. During peak system workloads, transactions failed with `WriteConflictException` and transaction lock request timeouts. These failures cascaded: client pools exhausted connection timeout limits, and database operations queued, causing double-spend bugs when retry logic was applied incorrectly.

### 2. Analytical Diagnostic Investigation
The DBA checked database lock metrics:
```javascript
db.serverStatus().locks;
db.currentOp({ "type": "op", "waitingForLock": true });
```
They observed that transactions were updating account records in inconsistent sequences. For example:
*   Transaction 1 locks Account A and attempts to lock Account B.
*   Transaction 2 locks Account B and attempts to lock Account A.

This creates a **Deadlock**. MongoDB automatically breaks deadlocks by aborting one of the transactions, which throws a `WriteConflict` exception. If the application does not catch this exception and retry, the database transaction fails.

Additionally, they checked `transactionLifetimeLimitSeconds` (default: 60 seconds). Long-running transactions held locks on account records, blocking other transaction tasks and causing connection pooling exhaustion.

### 3. Step-by-Step Resolution Runbook
1.  **Configure Transaction Execution Lock Timeouts**:
    Reduce the amount of time transactions wait for locks to prevent system lockouts:
    ```javascript
    db.adminCommand({
      setParameter: 1,
      maxTransactionLockRequestTimeoutMillis: 100
    });
    ```
2.  **Enforce Consistent Account Locking Sequence**:
    Modify the application logic to sort account IDs before executing updates:
    ```javascript
    // Ensure smaller Account ID is locked first
    const accountsToLock = [fromAccountId, toAccountId].sort();
    ```
3.  **Implement Exponential Backoff Retry Loop**:
    Implement robust client retry handlers inside the transaction code blocks (see Java code below).
4.  **Tune System Transaction Expiry Time limits**:
    Ensure transactions expire fast if they get stuck:
    ```javascript
    db.adminCommand({
      setParameter: 1,
      transactionLifetimeLimitSeconds: 15
    });
    ```

### 4. Code Artifact: Java Transaction Execution Helper
Save this class as `TransactionRetryRunner.java` to handle write conflicts:
```java
package com.example.db;

import com.mongodb.MongoCommandException;
import com.mongodb.client.ClientSession;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoDatabase;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class TransactionRetryRunner {
    private static final Logger log = LoggerFactory.getLogger(TransactionRetryRunner.class);
    private final MongoClient mongoClient;

    public TransactionRetryRunner(MongoClient client) {
        this.mongoClient = client;
    }

    public void runWithRetry(Runnable transactionBlock) {
        int attempt = 0;
        int maxAttempts = 5;
        
        while (attempt < maxAttempts) {
            try (ClientSession session = mongoClient.startSession()) {
                session.startTransaction();
                try {
                    transactionBlock.run();
                    session.commitTransaction();
                    log.info("Transaction executed and committed successfully.");
                    break;
                } catch (MongoCommandException e) {
                    session.abortTransaction();
                    if (e.getErrorCode() == 112 || e.getErrorCodeName().contains("WriteConflict")) {
                        attempt++;
                        int backoff = (int) Math.pow(2, attempt) * 50;
                        log.warn("Write conflict detected. Retrying attempt {}/{} after {}ms...", attempt, maxAttempts, backoff);
                        try { Thread.sleep(backoff); } catch (InterruptedException ignored) {}
                    } else {
                        log.error("Transaction failed with non-retryable exception: ", e);
                        throw e;
                    }
                }
            }
        }
    }
}
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Transactions vs Single Document Design**: If your data requires frequent multi-document transactions, verify if you can design the collections differently. Consolidating related entities into a single BSON document removes transaction overhead because single-document operations are atomic.
*   **Keep Transactions Small**: Minimize business logic, HTTP network calls, or other CPU tasks within a active transaction block to release locks as fast as possible.

---

## 13. Hands-on Lab Exercise: Simulating Node Failures in Multi-Document Transactions

### 1. Objective and Scenario
Understand how transactions react to network drops and write conflicts. You will build a script that starts a session transaction, simulates a conflict by modifying the same document inside another connection, and handles the rollback.

### 2. Code Implementation: `transaction-simulation.js`
Create a file named `transaction-simulation.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function simulate() {
  const uri = "mongodb://localhost:27017/?replicaSet=rs0";
  const client = new MongoClient(uri);
  const secondaryClient = new MongoClient(uri);
  
  try {
    await client.connect();
    await secondaryClient.connect();
    
    const db = client.db("bank_db");
    const col = db.collection("balances");
    
    await col.drop().catch(() => {});
    await col.insertOne({ _id: "ACC1", balance: 500 });
    
    const session = client.startSession();
    session.startTransaction();
    
    console.log("Transaction 1 started. Updating balance...");
    await col.updateOne({ _id: "ACC1" }, { $inc: { balance: -100 } }, { session });
    
    // Simulate parallel write conflict outside the transaction session
    console.log("Transaction 2 attempting parallel modification on ACC1...");
    try {
      await secondaryClient.db("bank_db").collection("balances").updateOne(
        { _id: "ACC1" },
        { $inc: { balance: -50 } }
      );
    } catch (err) {
      console.log("Parallel update status:", err.message);
    }
    
    // Commit the session transaction
    await session.commitTransaction();
    console.log("Transaction 1 committed successfully.");
    
    const finalDoc = await col.findOne({ _id: "ACC1" });
    console.log("Final balance value in DB:", finalDoc.balance);
    
  } finally {
    await client.close();
    await secondaryClient.close();
  }
}
simulate().catch(console.dir);
```

### 3. Lab Verification Steps
1.  Ensure you are running a local replica set instance, and execute the test:
    ```bash
    node transaction-simulation.js
    ```
2.  Observe the final balance value to verify atomicity.

---

## 14. Distributed Lock & Consistency Verification Reference

### 1. Key Transaction Configurations
Adjust these parameters to control transaction timeouts:
*   `transactionLifetimeLimitSeconds`: The maximum execution time allowed for active transactions before rollback (Default: 60s).
*   `maxTransactionLockRequestTimeoutMillis`: The duration a transaction blocks waiting to acquire lock resources (Default: 5ms).

### 2. Operational Diagnostic Commands
Verify transaction states:
```javascript
// Inspect running transaction logs and active lock queues
db.adminCommand({
  currentOp: 1,
  "transaction.opcount": { $gt: 0 }
});

// View lock status for all database partitions
db.serverStatus().locks;
```

### 3. Senior Engineer's Production Checklist
*   [ ] Enforce consistent order of document lock acquisition across operations to prevent deadlocks.
*   [ ] Set `transactionLifetimeLimitSeconds` to 15 seconds to release database locks quickly.
*   [ ] Set read concern to `majority` and write concern to `w: "majority"` to prevent rollback issues when executing transactions.

---

## 15. Cluster-wide Logical Clock & Causal Consistency Sessions

### 1. Causal Consistency and logical Sessions
Logical sessions track the time and sequencing of database operations. A causally consistent client session guarantees that read and write operations maintain order across secondary nodes, preventing stale reads. Under the hood, MongoDB uses a global logical clock. Read and write operations exchange logical time tokens (`$clusterTime`) signed by cryptographic keys to establish causality:
```json
{
  "$clusterTime": {
    "clusterTime": Timestamp(1541450091, 2),
    "signature": { "hash": BinData(0, "abc..."), "keyId": NumberLong(12) }
  }
}
```

### 2. Core API vs. Callback API Transactions
*   **Core API**: The developer manually initiates logical sessions, starts transactions, handles rollbacks, and writes error-handling loops for `TransientTransactionError` and `UnknownTransactionCommitResult`.
*   **Callback API**: Automatically starts transactions, processes callback operations, commits transactions, and handles transient errors.
```python
# Python Callback API Transaction example
with client.start_session() as session:
    def callback(my_session):
        orders = my_session.client.webshop.orders
        inventory = my_session.client.webshop.inventory
        orders.insert_one({"sku": "abc123", "qty": 100}, session=my_session)
        inventory.update_one({"sku": "abc123", "qty": {"$gte": 100}},
                             {"$inc": {"qty": -100}}, session=my_session)
    session.with_transaction(callback)
```

### 3. Read Concerns and wtimeout
*   `linearizable`: Reads wait for majority verification, blocking if a network partition occurs.
*   `snapshot`: Reads data from a point-in-time snapshot, guaranteeing isolation within transactions.
*   `wtimeout`: Limit write concern blocks when replication consensus fails.
