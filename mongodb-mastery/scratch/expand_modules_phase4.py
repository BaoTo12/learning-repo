#!/usr/bin/env python3
import os

modules_dir = r"c:\Users\Admin\Desktop\projects\learning-repo\mongodb-mastery\modules"

case_studies = {
    "01-mongodb-foundations.md": """
---

## 12. Enterprise Case Study: WiredTiger Cache Eviction & Connection Exhaustion Under Peak Load

### 1. Scenario Description
During a global promotional event, an e-commerce platform experienced a sudden 15x spike in traffic. Within minutes, the main MongoDB database cluster (running on-premise bare-metal servers) showed CPU usage hitting 100%, and query response times deteriorated from 2ms to over 15,000ms. The application servers began throwing database connection timeout exceptions, and the system became unresponsive.

### 2. Analytical Diagnostic Investigation
The operations team extracted database logs and observed repeating lines indicating that the storage engine was failing to find clean pages to evict, causing active worker threads to stall while waiting for eviction threads to free up memory:
```text
[WT_VERB_EVICT] Eviction server: eviction target not met, cache-size: 11.8GB, clean: 1.2GB, dirty: 10.6GB
[WT_VERB_EVICT] Eviction server: thread-0: eviction target met
[WT_VERB_EVICT] Eviction server: eviction target not met, cache-size: 11.8GB, clean: 0.9GB, dirty: 10.9GB
```
A review of the OS socket parameters showed that the database instance had reached its connection limits:
```bash
# Check socket descriptor allocation in the kernel
sysctl fs.file-max
# Verify ulimit limits for the mongod process user
ulimit -Sn
ulimit -Hn
```
Running `db.serverStatus().wiredTiger.cache` revealed that the dirty cache ratio had exceeded 20%, triggering aggressive thread-blocking eviction (where client write queries are hijacked to do storage engine cleanup).

### 3. Step-by-Step Resolution Runbook
To restore service immediately without restarting the database daemon and losing cache contents, the team executed the following commands:

1.  **Dynamically Increase the WiredTiger Cache Size Limit**:
    Since the node had 32GB of system RAM, and the cache was capped at 12GB, they increased the cache size dynamically to 20GB:
    ```javascript
    db.adminCommand({
      setParameter: 1,
      "wiredTigerEngineRuntimeConfig": "cache_size=20G"
    });
    ```
2.  **Verify the Allocation Change**:
    Ensure the parameter update took effect in the storage engine:
    ```javascript
    db.serverStatus().wiredTiger.cache["maximum bytes configured"];
    ```
3.  **Adjust OS Kernel File Descriptors (Non-disruptively)**:
    They adjusted the open file limits dynamically for the active PID of `mongod`:
    ```bash
    # Locate the mongod process ID
    MONGO_PID=$(pgrep mongod)
    # Write new limits directly to the process limit map
    prlimit --pid=$MONGO_PID --nofile=65536:65536
    ```
4.  **Tune TCP Stack Parameters for Socket Reuse**:
    To prevent connection leakage and TIME_WAIT socket exhaustion, they ran:
    ```bash
    sudo sysctl -w net.ipv4.tcp_tw_reuse=1
    sudo sysctl -w net.ipv4.tcp_fin_timeout=15
    ```
5.  **Implement Client-Side Connection Rate Limits**:
    They throttled the connection pool sizes in the application driver parameters to 50 connections per instance (down from 200) to match the database ticket availability.

### 4. Code Artifact: Automated Cache and Thread Diagnostic Script
Save the following bash script as `/usr/local/bin/mongo-diagnostic.sh` to automatically detect eviction issues and generate notifications:
```bash
#!/usr/bin/env bash
set -euo pipefail

# Connection parameters
MONGO_URI="mongodb://localhost:27017/admin"
LIMIT_DIRTY_PERCENT=15

echo "Starting MongoDB storage engine diagnostics..."

# Fetch cache metrics using mongosh
STATS=$(mongosh "${MONGO_URI}" --quiet --eval '
  const stats = db.serverStatus().wiredTiger.cache;
  const max_bytes = stats["maximum bytes configured"];
  const dirty_bytes = stats["tracked dirty bytes in the cache"];
  const dirty_pct = (dirty_bytes / max_bytes) * 100;
  print(dirty_pct.toFixed(2));
')

echo "Current WiredTiger Cache Dirty Percentage: ${STATS}%"

# Check if dirty percentage exceeds our warning threshold
if (( $(echo "${STATS} > ${LIMIT_DIRTY_PERCENT}" | bc -l) )); then
  echo "WARNING: WiredTiger cache dirty threshold exceeded!"
  echo "Current dirty percentage: ${STATS}% (Limit: ${LIMIT_DIRTY_PERCENT}%)"
  
  # Log recent eviction statistics
  mongosh "${MONGO_URI}" --quiet --eval '
    const cache = db.serverStatus().wiredTiger.cache;
    printjson({
      "bytes_currently_in_cache": cache["bytes currently in the cache"],
      "pages_evicted_by_application_threads": cache["pages selected for eviction written by application threads"],
      "eviction_worker_thread_evictions": cache["pages selected for eviction written by eviction workers"]
    });
  '
else
  echo "Storage engine cache health check: OK"
fi
```

### 5. Architectural Trade-offs & Lessons Learned
*   **WiredTiger Cache Sizing**: Never allocate 100% of RAM to WiredTiger. Leaving 30-40% for the OS page cache is essential because MongoDB depends on the OS page cache for mapping files and caching compressed data.
*   **Thread Safety vs Connection Scaling**: The connection-per-thread model in MongoDB means high connection counts translate directly to high thread scheduling overhead. Forcing clients to use pool size limits reduces scheduling latency.
""",
    "02-crud-and-querying.md": """
---

## 11. Enterprise Case Study: Unindexed Sorting Out-of-Memory & Query Planner Drift

### 1. Scenario Description
A financial analytics platform tracks transaction logs. The dashboard fetches recent transaction entries matching a filter (e.g., status is "APPROVED") and orders them chronologically (`{ createdAt: -1 }`). During high write volume periods, the dashboard began throwing HTTP 500 errors. Database monitoring showed that CPU utilization on the primary replica set member pinned at 100%, and other operations queued behind the sorting queries.

### 2. Analytical Diagnostic Investigation
The engineering team enabled profiling and captured query statistics:
```javascript
db.setProfilingLevel(1, { slowms: 100 });
```
In the diagnostic logs, they found queries terminating with an Out-of-Memory error:
```text
{"t":{"$date":"2026-06-12T07:15:22.102Z"},"s":"E", "c":"QUERY", "id":22345, "ctx":"conn42","msg":"Write conflict or execution error","attr":{"error":"Executor error during find command :: caused by :: Sort operation used more than the maximum 33554432 bytes of RAM. Add an index, or specify a smaller limit."}}
```
They ran the aggregation query with `explain("executionStats")` to inspect the operations performed by the query planner:
```javascript
db.transactions.explain("executionStats").find({ status: "APPROVED" }).sort({ createdAt: -1 });
```
The query plan results revealed the following structure:
```json
{
  "executionStages": {
    "stage": "SORT",
    "nReturned": 15420,
    "executionTimeMillisEstimate": 4820,
    "memLimit": 33554432,
    "usedDisk": false,
    "inputStage": {
      "stage": "COLLSCAN",
      "filter": {
        "status": { "$eq": "APPROVED" }
      },
      "nReturned": 45000
    }
  }
}
```
**Diagnostic Findings**:
*   The query planner was doing a collection scan (`COLLSCAN`) to filter documents matching the status.
*   Because no compound index was present to satisfy the sort, it was attempting to sort 45,000 matched BSON documents in memory.
*   The total size of the documents exceeded 32MB, violating the database limit (`33554432` bytes), causing the query to abort.

### 3. Step-by-Step Resolution Runbook
1.  **Define a Compound Index Satisfying ESR (Equality, Sort, Range)**:
    Since `status` is checked for equality and `createdAt` is sorted, they created the index:
    ```javascript
    db.transactions.createIndex({ status: 1, createdAt: -1 }, { background: true });
    ```
2.  **Clear Query Plan Cache**:
    Force the query engine to invalidate cached execution plans for the collection:
    ```javascript
    db.transactions.clearQueryPlanCache();
    ```
3.  **Create Index Filters to Guarantee Plan Consistency**:
    To prevent the query planner from testing other suboptimal plans, apply an index filter:
    ```javascript
    db.runCommand({
      planCacheSetFilter: "transactions",
      query: { status: "APPROVED" },
      sort: { createdAt: -1 },
      projection: {},
      indexes: [ { status: 1, createdAt: -1 } ]
    });
    ```
4.  **Re-verify execution metrics**:
    Verify that the query now executes as a covered index scan:
    ```javascript
    db.transactions.find({ status: "APPROVED" }).sort({ createdAt: -1 }).explain("executionStats");
    ```
    Ensure the stage is `IXSCAN` and there is no `SORT` stage in memory.

### 4. Code Artifact: Node.js Index Verification Script
Save this script as `verify-indexes.js` to dynamically detect sorting queries running without index backing:
```javascript
const { MongoClient } = require('mongodb');

async function run() {
  const uri = "mongodb://localhost:27017";
  const client = new MongoClient(uri);
  try {
    await client.connect();
    const db = client.db("financial_db");
    
    // Fetch query plan details
    const explanation = await db.collection("transactions")
      .find({ status: "APPROVED" })
      .sort({ createdAt: -1 })
      .explain("executionStats");
      
    const stages = explanation.executionStats.executionStages;
    console.log("Winning Plan Stage:", stages.stage);
    
    if (JSON.stringify(stages).includes("COLLSCAN") || JSON.stringify(stages).includes("SORT_KEY_GENERATOR")) {
      console.error("ALERT: Suboptimal query execution plan detected! Missing compound indexes.");
      process.exit(1);
    } else {
      console.log("Query is fully optimized using index scan.");
    }
  } finally {
    await client.close();
  }
}
run().catch(console.dir);
```

### 5. Architectural Trade-offs & Lessons Learned
*   **The ESR Rule**: Always build compound indexes by ordering matching keys as Equality fields first, Sort fields second, and Range fields last.
*   **Memory Sorting Limits**: If a query must run without an index sort, ensure client-side pagination limits (`limit()`) are explicitly set so the result set stays well below the 32MB limit.
""",
    "03-data-modeling.md": """
---

## 12. Enterprise Case Study: Document Growth & Chunk Migration Latency

### 1. Scenario Description
An enterprise SaaS platform stores user notification items. Initially, notifications were modeled as an embedded array within the user document (the Embedded Array Pattern) for fast retrieval. After two years of operation, high-volume users accumulated tens of thousands of notifications. The document sizes approached the 16MB limit, which triggered disk thrashing during write updates, increased secondary replication lag, and caused shard chunk migrations to fail due to "jumbo document" states.

### 2. Analytical Diagnostic Investigation
The operations team audited the database to find documents close to the limit:
```javascript
db.users.aggregate([
  { $project: { docSize: { $bsonSize: "$$ROOT" }, email: 1 } },
  { $match: { docSize: { $gt: 12000000 } } },
  { $sort: { docSize: -1 } }
]).forEach(doc => {
  print("User ID: " + doc._id + " | Size: " + (doc.docSize / 1024 / 1024).toFixed(2) + " MB");
});
```
The analysis revealed that user documents were exceeding 14MB. WiredTiger writes documents compressed on disk, but when a client requests a document, it must be loaded into memory and uncompressed. A 14MB document expands to 40MB+ of BSON structure in RAM. Modifying a nested array in this document forces the storage engine to re-serialize the entire BSON payload, generating severe heap pressure.

### 3. Step-by-Step Resolution Runbook
To resolve this issue, the engineering team designed a zero-downtime migration to the **Out-of-band Bucketing Pattern**:

1.  **Define the New Schema Structure**:
    Instead of embedding all notifications in the user document, they created a separate collection `user_notifications` with buckets capped at 100 notifications per document:
    ```javascript
    // Sample Bucket Document Schema
    {
      _id: ObjectId(),
      userId: ObjectId("..."),
      bucketId: 1,
      count: 2,
      notifications: [
        { message: "First notification", date: ISODate("...") },
        { message: "Second notification", date: ISODate("...") }
      ]
    }
    ```
2.  **Deploy Schema Validators**:
    Create the validator to enforce constraints on bucket count:
    ```javascript
    db.createCollection("user_notifications", {
      validator: {
        $jsonSchema: {
          bsonType: "object",
          required: ["userId", "bucketId", "count", "notifications"],
          properties: {
            count: { bsonType: "int", maximum: 100 },
            notifications: { bsonType: "array" }
          }
        }
      }
    });
    ```
3.  **Run the Migration Script**:
    Extract legacy arrays and write them to bucket collections. (See Node.js script below).
4.  **Update the Application Persistence Logic**:
    Update the application write path to use the `$push` operator with the `$slice` filter, or query the active bucket and update:
    ```javascript
    db.user_notifications.updateOne(
      { userId: userId, count: { $lt: 100 } },
      {
        $push: { notifications: newNotification },
        $inc: { count: 1 }
      },
      { upsert: true }
    );
    ```

### 4. Code Artifact: Zero-Downtime Migration Script
Save this script as `migrate-notifications.js` to process historical data safely:
```javascript
const { MongoClient } = require('mongodb');

async function migrate() {
  const client = new MongoClient("mongodb://localhost:27017");
  try {
    await client.connect();
    const db = client.db("saas_db");
    const cursor = db.collection("users").find({ "notifications.0": { $exists: true } });
    
    while (await cursor.hasNext()) {
      const user = await cursor.next();
      const notifications = user.notifications;
      
      let bucketId = 1;
      let chunk = [];
      
      for (let i = 0; i < notifications.length; i++) {
        chunk.push(notifications[i]);
        if (chunk.length === 100 || i === notifications.length - 1) {
          await db.collection("user_notifications").insertOne({
            userId: user._id,
            bucketId: bucketId++,
            count: chunk.length,
            notifications: chunk
          });
          chunk = [];
        }
      }
      
      // Unset notifications array from user document to free space
      await db.collection("users").updateOne(
        { _id: user._id },
        { $unset: { notifications: "" } }
      );
      console.log(`Migrated user ${user._id} and removed legacy embedded notification array.`);
    }
  } finally {
    await client.close();
  }
}
migrate().catch(console.dir);
```

### 5. Architectural Trade-offs & Lessons Learned
*   **The 16MB BSON Limit is a Safety Guard**: Do not treat the 16MB document limit as a design target. Design data schemas to keep document sizes below 2MB to ensure cache efficiency and fast replication.
*   **WiredTiger Page Allocations**: Large documents cause leaf pages to exceed allocation bounds, resulting in page splits, disk fragmentation, and high eviction pressures.
""",
    "04-indexing-and-query-performance.md": """
---

## 12. Enterprise Case Study: Multikey Index Explosion & Write Amplification

### 1. Scenario Description
An inventory tracking application records items across multiple warehouses. Each item contains nested arrays for storage locations, product tag values, and batch identifiers. To query items dynamically, the operations team created single and compound indexes on these array fields. During inventory updates, the database write throughput crashed from 8,000 updates/sec to 150 updates/sec, and secondary members fell out of sync due to huge write lag.

### 2. Analytical Diagnostic Investigation
The DBA analyzed the system locks and write metrics:
```javascript
db.serverStatus().metrics.operation;
```
They checked the number of index keys created per document insert. A multikey index creates an index entry for *every single element* inside an indexed array. If a document has:
*   An array of tags (10 elements)
*   An array of locations (20 elements)
*   An array of historical batches (30 elements)

Creating a compound index `{ tags: 1, locations: 1 }` generates:
$$\text{Index Keys} = 10 \times 20 = 200 \text{ index entries}$$
If a write query modifies a location array, the database must write 200 updates to the index B-tree. This index key multiplication is called **Write Amplification**.

They executed `db.inventory.stats()` to analyze index footprints:
```json
{
  "indexSizes": {
    "_id_": 23450000,
    "tags_1_locations_1": 4589000000 // Huge size compared to collection data size!
  }
}
```
The B-tree index was much larger than the actual data, forcing the engine to evict collection data pages from the WiredTiger cache, leading to disk reads during write updates.

### 3. Step-by-Step Resolution Runbook
1.  **Locate and Drop Unnecessary Multikey Indexes**:
    Identify multikey indexes that can be combined or simplified:
    ```javascript
    db.inventory.dropIndex("tags_1_locations_1");
    ```
2.  **Flatten Arrays or Apply Attribute Pattern**:
    Rewrite data models to use flat objects instead of nested arrays where multi-criteria queries are executed.
3.  **Deploy Compound Indexes Safely using Partial Indexes**:
    Limit the size of index structures by indexing only active items:
    ```javascript
    db.inventory.createIndex(
      { status: 1, lastModified: -1 },
      { partialFilterExpression: { status: "ACTIVE" } }
    );
    ```
4.  **Audit Index Key Generation Counts**:
    Use the diagnostic script to measure the index write overhead before launching code to production.

### 4. Code Artifact: Node.js Index Key Amplification Audit Tool
Save the script as `audit-multikey.js` to detect multikey index bloat:
```javascript
const { MongoClient } = require('mongodb');

async function run() {
  const client = new MongoClient("mongodb://localhost:27017");
  try {
    await client.connect();
    const db = client.db("inventory_db");
    
    const collectionName = "inventory";
    const indexes = await db.collection(collectionName).indexes();
    
    console.log("Analyzing index definitions for collection:", collectionName);
    
    for (const index of indexes) {
      console.log(`Index Name: ${index.name}`);
      console.log(`Key Definition:`, index.key);
      
      // Determine if index behaves as multikey
      const stats = await db.collection(collectionName).stats();
      if (stats.indexDetails && stats.indexDetails[index.name]) {
        const detail = stats.indexDetails[index.name];
        console.log(`  Size on disk: ${(detail.uri ? (stats.indexSizes[index.name]/1024/1024).toFixed(2) : 0)} MB`);
      }
    }
  } finally {
    await client.close();
  }
}
run().catch(console.dir);
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Avoid Multiplying Array Fields in Indexes**: MongoDB restricts you from creating compound indexes where more than one field is an array (to prevent exponential index entry generation).
*   **RAM Resident Indexes**: Maintain your index size below 50% of the allocated WiredTiger cache to ensure read operations never trigger disk swaps during B-tree traversals.
""",
    "05-aggregation-framework.md": """
---

## 12. Enterprise Case Study: Aggregation Disk Spooling Overload & Memory Limits

### 1. Scenario Description
A marketing intelligence platform generates daily user engagement summaries. The pipeline processes millions of events using complex `$group`, `$sort`, and `$facet` stages. The pipeline failed with a `QueryExceededMemoryLimitNoDiskUseAllowed` error (the 100MB limit per stage was exceeded). The developer resolved this by setting `{ allowDiskUse: true }`. However, the next pipeline run caused database server disks to run at 100% capacity, blocking real-time transaction updates.

### 2. Analytical Diagnostic Investigation
The DBA checked system statistics during the pipeline run and observed high disk I/O latency:
```bash
# Monitor disk writes in real-time
iostat -x 1 10
```
They extracted the query plan to identify which stages were writing temp files to disk:
```javascript
db.events.explain("executionStats").aggregate(pipeline, { allowDiskUse: true });
```
**Diagnostic Findings**:
*   The pipeline used a `$facet` stage, which branches the stream into multiple sub-pipelines.
*   **Warning**: The `$facet` stage does *not* support disk spooling. The 100MB limit was bypassed by storing items inside sub-pipeline variables, which bloated RAM.
*   The `$sort` and `$group` stages were executing without index backing, forcing the engine to write millions of temporary documents to the filesystem temp directory.

### 3. Step-by-Step Resolution Runbook
1.  **Refactor Pipeline to Filter Data Early**:
    Ensure the `$match` stage is the first step in the pipeline. This reduces the number of documents passed to subsequent stages.
2.  **Optimize Fields Early with `$project`**:
    Discard unused fields immediately so that document footprints are minimal:
    ```javascript
    { $project: { _id: 1, userId: 1, timestamp: 1, type: 1 } }
    ```
3.  **Create Index Backing for Sort Stages**:
    Create a compound index matching the `$match` and `$sort` fields to allow the aggregation engine to use index scan ordering instead of performing a memory sort:
    ```javascript
    db.events.createIndex({ type: 1, timestamp: -1 });
    ```
4.  **Replace `$facet` with Separate Parallel Aggregations**:
    Instead of combining unrelated calculations inside a single resource-heavy `$facet` query, run them as parallel client requests to leverage thread concurrency.

### 4. Code Artifact: Optimized Node.js Stream Pipeline Execution
Save this script as `aggregate-stream.js` to process large aggregation tasks using streams:
```javascript
const { MongoClient } = require('mongodb');

async function run() {
  const client = new MongoClient("mongodb://localhost:27017");
  try {
    await client.connect();
    const db = client.db("analytics_db");
    
    // Aggregation optimized pipeline
    const pipeline = [
      { $match: { type: "CLICK", timestamp: { $gte: new Date("2026-06-01") } } },
      { $project: { userId: 1, amount: 1 } },
      { $group: { _id: "$userId", totalSpend: { $sum: "$amount" } } },
      { $sort: { totalSpend: -1 } }
    ];
    
    const cursor = db.collection("events").aggregate(pipeline, { allowDiskUse: true });
    
    // Process cursor items as stream to avoid loading entire results into Node RAM
    cursor.on('data', (doc) => {
      console.log(`User: ${doc._id} | Spend: ${doc.totalSpend}`);
    });
    
    cursor.on('end', () => {
      console.log("Pipeline processing completed successfully.");
      client.close();
    });
  } catch (err) {
    console.error("Aggregation pipeline failed:", err);
    await client.close();
  }
}
run();
```

### 5. Architectural Trade-offs & Lessons Learned
*   **RAM is 100x Faster than SSD Disk Spooling**: Disk spooling is a fallback, not a solution. If your aggregates require spooling to disk, analyze your index design to eliminate execution sorting.
*   **The Pipeline Optimizer**: MongoDB automatically reorders pipelines (e.g. moving `$match` before `$sort`). However, it cannot optimize stages separated by `$group` or `$project`. Manually optimize stage order.
""",
    "06-transactions-and-consistency.md": """
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
""",
    "07-replication-and-high-availability.md": """
---

## 13. Enterprise Case Study: Oplog Purge & Secondary Desynchronization

### 1. Scenario Description
A large-scale migration was executed on the primary database node, writing 500GB of historical data. The primary node completed the writes quickly. However, the secondary nodes fell behind due to disk I/O bottlenecks. Because the write volume exceeded the capacity of the oplog, the sync offset on the secondary nodes fell off the end of the oplog. The secondaries entered the `FATAL` replication state, showing replication lag of `Infinity`.

### 2. Analytical Diagnostic Investigation
The operations team ran `rs.status()` and observed the replication states of secondaries:
```json
{
  "name": "secondary-node-01:27017",
  "stateStr": "STARTUP2",
  "syncSourceHost": "",
  "lastHeartbeatMessage": "RS102 Oplog loop: client has fallen behind sync source oplog window bounds."
}
```
They checked replication statistics on the primary:
```javascript
db.getReplicationInfo();
```
**Diagnostic Findings**:
*   The Oplog window length had dropped to 1.5 hours because of the high write volume.
*   The secondaries had been lagging by 2 hours due to disk write queues.
*   Because the secondary's last synchronized timestamp was older than the oldest record in the primary's oplog, the secondary could not resume replication and required a full initial sync.

### 3. Step-by-Step Recovery and Tuning Runbook
To recover the secondaries and prevent future synchronization failures, they completed these steps:

1.  **Increase the Oplog Window Capacity Dynamically**:
    On the primary node, they resized the oplog to 150GB to provide a buffer for migrations:
    ```javascript
    db.adminCommand({
      replSetResizeOplog: 1,
      size: 153600 // Resize oplog capacity to 150GB
    });
    ```
2.  **Re-verify Oplog Size Details**:
    ```javascript
    db.getSiblingDB("local").oplog.rs.stats().maxSize;
    ```
3.  **Force Re-Synchronization on the Failed Secondary**:
    On the secondary node host, execute:
    ```bash
    # Stop the mongod service instance
    sudo systemctl stop mongod
    # Delete the data directory files to force a clean initial sync
    sudo rm -rf /var/lib/mongodb/data/*
    # Restart the service
    sudo systemctl start mongod
    ```
    This forces the secondary to pull a fresh snapshot copy from the primary node.
4.  **Tweak Heartbeat and Timeout Values**:
    To prevent network jitter from triggering split-brain elections, they adjusted settings:
    ```javascript
    cfg = rs.conf();
    cfg.settings.electionTimeoutMillis = 15000; // Allow 15 seconds before elections
    rs.reconfig(cfg);
    ```

### 4. Code Artifact: Shell-Based Replication Monitoring Script
Save the script as `/usr/local/bin/monitor-replication.sh` to check replication health:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Querying replica set health details..."

# Fetch replication lag in seconds
LAG_SEC=$(mongosh --quiet --eval '
  const status = rs.status();
  const primaryTime = status.members.find(m => m.state === 1).optimeDate;
  const secondaryTime = status.members.find(m => m.self).optimeDate;
  const lag = (primaryTime - secondaryTime) / 1000;
  print(lag);
')

echo "Current secondary replication lag: ${LAG_SEC} seconds."

# Alert if lag is greater than 1 hour (3600 seconds)
if (( $(echo "${LAG_SEC} > 3600" | bc -l) )); then
  echo "CRITICAL ALERT: Secondary is lagging by more than 1 hour!"
  exit 2
else
  echo "Replication health check: OK"
fi
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Keep Oplog Sizes Large**: Disk space is cheap. Allocate at least 10-20% of your total storage to the oplog to handle batch data operations and maintenance windows without resyncs.
*   **Write Concerns Impact Performance**: Higher write concerns (`{ w: "majority" }`) increase execution latency, but they prevent rollback issues when a primary node fails.
""",
    "08-sharding-and-horizontal-scaling.md": """
---

## 13. Enterprise Case Study: Hot Shard Exhaustion & Range-based Shard Key Drift

### 1. Scenario Description
An IoT ingestion system tracks millions of sensor devices. The team deployed a sharded cluster and chose `timestamp` as the shard key (a range-based sharding approach). As the system scaled, database writes were routed to a single shard (the "hot shard"), while other shards sat idle. This caused disk exhaustion and CPU spikes on the active shard, while the balancer could not migrate chunks due to lock contention.

### 2. Analytical Diagnostic Investigation
The DBA checked chunk distribution in the config database:
```javascript
sh.status();
```
They audited the write distribution across shards:
```javascript
db.getSiblingDB("admin").runCommand({ connPoolStats: 1 });
```
**Diagnostic Findings**:
*   Because `timestamp` is monotonically increasing, every new document had a timestamp value higher than the range limit of the last chunk.
*   The router (`mongos`) sent every write operation to the shard holding the max range chunk.
*   The balancer attempted to split and move these chunks, but because writes were constant, the chunks were marked as "jumbo chunks" (too large to migrate safely).

### 3. Step-by-Step Resolution Runbook
To resolve this imbalance without system downtime, they converted the collection to use a hashed compound shard key:

1.  **Analyze Jumbo Chunks**:
    Locate jumbo chunks that block balancer migration tasks:
    ```javascript
    db.getSiblingDB("config").chunks.find({ jumbo: true });
    ```
2.  **Split Jumbo Chunks Manually**:
    Force a split of the jumbo chunk at its middle point:
    ```javascript
    sh.splitFind("telemetry.sensor_readings", { timestamp: ISODate("2026-06-12T00:00:00Z") });
    ```
3.  **Refine the Shard Key dynamically (Zero-Downtime)**:
    Since MongoDB 4.4+, you can add fields to a shard key to increase cardinality. They refined the key by adding a hashed `sensorId` prefix:
    ```javascript
    sh.refineCollectionShardKey("telemetry.sensor_readings", { sensorId: "hashed", timestamp: 1 });
    ```
4.  **Verify Balancer Progression**:
    Ensure the balancer starts migrating chunks across shards:
    ```javascript
    sh.isBalancerRunning();
    sh.getBalancerWindow();
    ```

### 4. Code Artifact: Shard Balance Diagnostic Script
Save this script as `check-shard-balance.js` to run on the config router:
```javascript
const shardStatus = sh.status();
const configDb = db.getSiblingDB("config");

print("--- Checking Chunk Balances Across Shards ---");
const collections = configDb.collections.find({ dropped: false }).toArray();

collections.forEach(col => {
  print("Collection: " + col._id);
  const chunks = configDb.chunks.find({ ns: col._id }).toArray();
  const distribution = {};
  
  chunks.forEach(chunk => {
    distribution[chunk.shard] = (distribution[chunk.shard] || 0) + 1;
  });
  
  printjson(distribution);
});
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Never Shard on Monotonic Keys**: Range-based sharding on monotonic keys (e.g. auto-increment IDs, timestamps) creates write bottlenecks. Always combine monotonic fields with a high-cardinality field (like a hashed ID) to distribute writes.
*   **Dynamic Shard Key Refinement**: Refinement changes the index configurations. Ensure the compound indexes matching the new refined key are built on all shards before running the command.
""",
    "09-change-streams-and-event-driven-design.md": """
---

## 11. Enterprise Case Study: Change Stream Consumer Dropouts & Resume Token Loss

### 1. Scenario Description
An event-driven billing service processes change streams from an `orders` collection to send invoice notifications. During a network partition, the billing service lost connectivity to MongoDB. The outage lasted for 12 hours. Upon reconnection, the billing service crashed repeatedly, throwing `ChangeStreamHistoryLost` errors. The system could not resume from its last saved state, resulting in missing invoices.

### 2. Analytical Diagnostic Investigation
The developers inspected application logs and found the following stack trace:
```text
com.mongodb.MongoCommandException: Command failed with error 286 (ChangeStreamHistoryLost): 'Resume of change stream was not possible because the resume token was not found in the oplog.'
  at com.mongodb.internal.connection.ProtocolHelper.getCommandFailureException(ProtocolHelper.java:175)
```
**Diagnostic Findings**:
*   The billing service stored the resume token in a database collection after processing each event.
*   Because the downstream outage lasted for 12 hours, the database oplog had rolled over, and the primary node had purged the oplog record associated with the saved resume token.
*   As a result, the client could not resume processing from the token, and starting a new stream risked processing duplicate transactions or missing events.

### 3. Step-by-Step Resolution Runbook
1.  **Determine Current Oplog Window Bounds**:
    Calculate the duration of events stored in the oplog to determine the safe retry window:
    ```javascript
    db.getReplicationInfo();
    ```
2.  **Increase Oplog Retention Window**:
    Increase the oplog size dynamically on the replica set nodes to prevent future rollovers during down times:
    ```javascript
    db.adminCommand({ replSetResizeOplog: 1, size: 81920 }); // Resize to 80GB
    ```
3.  **Deploy a Resilient Fallback Consumption Strategy**:
    If the resume token is lost, the service must perform a fallback query to process missed documents based on timestamp audits before creating a new stream cursor.
4.  **Store Resume Tokens with Reliability**:
    Save tokens in a high-speed, persistent memory store like Redis, and use write concerns to guarantee durability.

### 4. Code Artifact: Java Resilient Change Stream Listener
Save this class as `ResilientStreamListener.java` to manage token failures:
```java
package com.example.event;

import com.mongodb.MongoCommandException;
import com.mongodb.client.ChangeStreamIterable;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoCursor;
import com.mongodb.client.model.changestream.ChangeStreamDocument;
import org.bson.BsonDocument;
import org.bson.Document;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class ResilientStreamListener {
    private static final Logger log = LoggerFactory.getLogger(ResilientStreamListener.class);
    private final MongoCollection<Document> collection;
    private BsonDocument savedResumeToken = null;

    public ResilientStreamListener(MongoCollection<Document> collection) {
        this.collection = collection;
    }

    public void startListening() {
        while (true) {
            try {
                ChangeStreamIterable<Document> stream = collection.watch();
                if (savedResumeToken != null) {
                    log.info("Attempting to resume change stream using token...");
                    stream.resumeAfter(savedResumeToken);
                }
                
                try (MongoCursor<ChangeStreamDocument<Document>> cursor = stream.iterator()) {
                    while (cursor.hasNext()) {
                        ChangeStreamDocument<Document> event = cursor.next();
                        processEvent(event);
                        savedResumeToken = event.getResumeToken();
                    }
                }
            } catch (MongoCommandException e) {
                if (e.getErrorCode() == 286) {
                    log.error("Resume token expired! Performing query fallback before restart...", e);
                    executeFallbackSync();
                    savedResumeToken = null; // Start fresh from current time
                } else {
                    log.error("Fatal database connection exception: ", e);
                    try { Thread.sleep(5000); } catch (InterruptedException ignored) {}
                }
            }
        }
    }

    private void processEvent(ChangeStreamDocument<Document> event) {
        log.info("Processing operation: {}", event.getOperationType());
    }

    private void executeFallbackSync() {
        log.info("Querying for orders modified since last known batch...");
        // Implement query-based synchronization to recover missed data
    }
}
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Oplog Retention Constraints**: Change streams are wrappers around the replica set oplog. If an application falls behind past the oplog window, it *will* miss events. Size the oplog to hold at least 48 hours of write history.
*   **Resume Token Storage**: Always write resume tokens to persistent storage asynchronously. Using a local file or local memory state causes token loss when containers restart.
""",
    "10-security-and-production-operations.md": """
---

## 11. Enterprise Case Study: Mutual TLS Certificate Expiry & Rotation Lockout

### 1. Scenario Description
A financial services cluster enforces strict mutual TLS (mTLS) authentication for all database access. The system administrators scheduled a rolling certificate renewal. During the deployment, the team updated the primary node first. This triggered a cluster disconnection: secondary nodes rejected connections from the primary, and client drivers were locked out from the database, causing a complete system outage.

### 2. Analytical Diagnostic Investigation
The admin team opened log files on the primary node and saw repeating handshake failures:
```text
{"t":{"$date":"2026-06-12T07:15:22.102Z"},"s":"E", "c":"NETWORK", "id":23280, "ctx":"conn42","msg":"SSL handshake failed","attr":{"error":"SSL peer certificate validation failed: Certificate has expired or CA chain mismatch."}}
```
**Diagnostic Findings**:
*   The renewal script updated the CA file, but did not deploy the complete intermediate certificate bundle containing both the old and new root certificates.
*   When the primary restarted with the new certificate, secondaries (which still used the old CA file) could not authenticate the primary's certificate, blocking replication connection attempts.
*   Client drivers also failed to connect because their trust stores lacked the new CA certificate.

### 3. Step-by-Step Certificate Rotation Runbook
To rotate certificates in production without database downtime, you must follow this exact rolling sequence:

1.  **Generate and Distribute Combined CA Certificate Bundle**:
    Combine the old and new root CA certificates into a single `ca.pem` file. This ensures the database will accept certificates signed by either authority:
    ```bash
    cat new_ca.crt old_ca.crt > combined_ca.pem
    ```
2.  **Distribute the Combined CA to All Database Nodes**:
    Deploy `combined_ca.pem` to the TLS directory on all cluster nodes without restarting.
3.  **Perform Rolling Update of Server Certificates**:
    For each secondary node:
    *   Deploy the new server certificate (signed by the new CA).
    *   Configure `mongod.conf` to use the new server certificate and the `combined_ca.pem`.
    *   Restart the node and verify that it rejoins the replica set: `rs.status()`
4.  **Step Down the Primary**:
    Force the primary node to step down to allow a secondary to become the new primary:
    ```javascript
    rs.stepDown(120);
    ```
5.  **Update the Former Primary Node**:
    Deploy the new certificate to the former primary and restart the node.
6.  **Deploy New Client Certificates**:
    Once all database nodes trust both authorities, update client application certificates.
7.  **Clean Up the CA Bundle**:
    Once all nodes and client drivers are updated, remove the old CA from the combined file, leaving only the new root CA for security enforcement.

### 4. Code Artifact: OpenSSL CA and Certificate Generation Script
Save this script as `generate-certs.sh` to build compliant cert configurations:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Generating mTLS Certificate Authority and keys..."

# 1. Create Root CA
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days 365 \
  -subj "/CN=DatabaseCA" -out ca.crt

# 2. Create Server Certificate Request
openssl genrsa -out server.key 2048
openssl req -new -key server.key \
  -subj "/CN=mongodb-server.internal" -out server.csr

# 3. Sign Server Certificate with CA
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 365 -sha256

# 4. Combine key and cert for MongoDB PEM format
cat server.key server.crt > mongodb.pem

echo "Certificates created successfully: mongodb.pem, ca.crt"
```

### 5. Architectural Trade-offs & Lessons Learned
*   **PEM Files Contain Keys and Certs**: MongoDB expects server certificates and private keys to be combined into a single `.pem` file. If they are separated, the service will fail to start.
*   **Verify San Subject Alternative Names**: Ensure server certificates contain valid SANs matching the DNS hosts used in the connection URI to avoid connection rejections.
""",
    "11-application-integration.md": """
---

## 11. Enterprise Case Study: Driver Socket Exhaustion & Connection Leakage

### 1. Scenario Description
A financial analytics API runs on AWS ECS containers. During peak request workloads, the container tasks threw `MongoTimeoutException` and failed health checks. This triggered ECS to restart the tasks, but the replacement containers failed immediately with connection errors, causing an extended API outage.

### 2. Analytical Diagnostic Investigation
The development team verified server connection counts and socket states:
```bash
# Check count of TCP connections on port 27017
netstat -an | grep 27017 | wc -l
```
They reviewed application source code and found that the API was instantiating a new `MongoClient` instance inside every incoming HTTP request handler:
```javascript
// BAD PRACTICE: Client instantiated per request
app.get('/transactions', async (req, res) => {
  const client = new MongoClient("mongodb://localhost:27017");
  await client.connect();
  const db = client.db("api_db");
  const data = await db.collection("logs").find({}).toArray();
  res.json(data);
  // Missing client.close() under error paths!
});
```
**Diagnostic Findings**:
*   Creating a new client for every request bypasses connection pooling.
*   Each client instantiation runs server selection, TCP handshakes, and mTLS handshakes, generating high latency.
*   If an exception occurs before the client is closed, the sockets remain in the `ESTABLISHED` or `TIME_WAIT` state, leading to file descriptor leaks and database connection limit exhaustion.

### 3. Step-by-Step Resolution Runbook
1.  **Refactor Application to Use a Client Singleton**:
    Implement the connection pattern to instantiate the client once and share it across all endpoints (see JavaScript script below).
2.  **Configure Connection Pool Parameters**:
    Optimize driver pool sizes to limit socket allocation on the database server:
    *   Set `maxPoolSize` to 100 connections per container instance.
    *   Set `minPoolSize` to 10 to pre-warm connections.
    *   Set `maxIdleTimeMS` to 30000 to close idle sockets.
3.  **Tweak System Socket Keepalive Settings**:
    Ensure the operating system closes broken TCP connections:
    ```bash
    sudo sysctl -w net.ipv4.tcp_keepalive_time=120
    ```

### 4. Code Artifact: Resilient Node.js MongoClient Wrapper
Save this file as `db-client.js` to manage connection pooling:
```javascript
const { MongoClient } = require('mongodb');

let clientInstance = null;
let dbInstance = null;

async function getDatabase() {
  if (dbInstance) {
    return dbInstance;
  }
  
  const uri = "mongodb://localhost:27017/api_db?maxPoolSize=100&minPoolSize=10&maxIdleTimeMS=30000";
  console.log("Initializing shared MongoDB client connection pool...");
  
  clientInstance = new MongoClient(uri, {
    connectTimeoutMS: 5000,
    socketTimeoutMS: 30000
  });
  
  await clientInstance.connect();
  dbInstance = clientInstance.db();
  
  // Register shutdown handlers
  process.on('SIGTERM', gracefulShutdown);
  process.on('SIGINT', gracefulShutdown);
  
  return dbInstance;
}

async function gracefulShutdown() {
  if (clientInstance) {
    console.log("Closing MongoDB client connection pool...");
    await clientInstance.close();
    process.exit(0);
  }
}

module.exports = { getDatabase };
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Share Client Instances**: Always reuse your database client. The client instance handles connection pooling, node discovery, routing, and handshake caching under the hood.
*   **Serverless Environments**: In serverless functions (like AWS Lambda), instantiate the database client outside the function execution handler. This allows the container to reuse the open sockets across executions.
""",
    "12-spring-boot-with-mongodb.md": """
---

## 11. Enterprise Case Study: Spring Data Mapping Overhead & N+1 Query Cascade

### 1. Scenario Description
An enterprise catalog system uses Spring Boot with Spring Data MongoDB. After a catalog expansion, catalog listing page loads slowed down from 80ms to over 3,000ms. CPU usage on the application server hit 100%, but database CPU usage remained below 10%, indicating a client-side serialization bottleneck.

### 2. Analytical Diagnostic Investigation
The developers ran a thread profiler on the Spring Boot JVM and inspected logging statements:
```yaml
logging:
  level:
    org.springframework.data.mongodb.core.MongoTemplate: DEBUG
```
They observed that querying a single catalog item triggered multiple database requests to load related entities (the N+1 Query Pattern):
```text
DEBUG o.s.d.m.core.MongoTemplate : Finding document for query: { "_id" : 123 } in collection: catalog_items
DEBUG o.s.d.m.core.MongoTemplate : Finding document for query: { "itemId" : 123 } in collection: catalog_images
DEBUG o.s.d.m.core.MongoTemplate : Finding document for query: { "itemId" : 123 } in collection: inventories
DEBUG o.s.d.m.core.MongoTemplate : Finding document for query: { "_id" : 124 } in collection: catalog_items
```
**Diagnostic Findings**:
*   The entity model used `@DBRef` with lazy loading enabled.
*   When iterating through catalog items to build the response DTO, calling getters on child fields triggered database round-trips for each record, degrading response time.
*   Additionally, Spring Data MongoDB's default mapping converts BSON byte buffers to Java objects using reflection, generating massive heap allocations and garbage collection cycles.

### 3. Step-by-Step Resolution Runbook
1.  **Remove `@DBRef` Mappings**:
    Replace lazy reference relations with embedded documents or query-based lookup aggregations.
2.  **Rewrite Catalog Fetch using MongoDB Aggregation**:
    Use `MongoTemplate` to execute an aggregation pipeline that joins the image and inventory collections using `$lookup` stages in a single query.
3.  **Implement Custom Spring Data Converters**:
    Implement custom BSON-to-object converters to bypass reflection mapping rules and speed up response generation.

### 4. Code Artifact: Java Optimized Aggregation Repository
Save this class as `CustomCatalogRepositoryImpl.java` to join related collections efficiently:
```java
package com.example.catalog;

import org.bson.Document;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.Aggregation;
import org.springframework.data.mongodb.core.aggregation.AggregationResults;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class CustomCatalogRepositoryImpl implements CustomCatalogRepository {

    @Autowired
    private MongoTemplate mongoTemplate;

    @Override
    public List<CatalogDto> fetchOptimizedCatalog(String category) {
        Aggregation aggregation = Aggregation.newAggregation(
            Aggregation.match(Criteria.where("category").is(category)),
            // Left outer join to images collection
            Aggregation.lookup("catalog_images", "_id", "itemId", "images"),
            // Left outer join to inventory collection
            Aggregation.lookup("inventories", "_id", "itemId", "inventory"),
            Aggregation.project("name", "price", "images", "inventory")
        );

        AggregationResults<CatalogDto> results = mongoTemplate.aggregate(
            aggregation, "catalog_items", CatalogDto.class
        );
        return results.getMappedResults();
    }
}
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Avoid `@DBRef` in High-Throughput Services**: `@DBRef` forces an application-level query join. Use embedded structures or manual `$lookup` aggregations to minimize database round-trips.
*   **Object Mapping Overhead**: Java serialization of large BSON objects generates heavy heap churn. Select only required fields inside query projection clauses to minimize mapping steps.
""",
    "13-testing-and-migrations.md": """
---

## 11. Enterprise Case Study: Mongock Migration Failure & Database State Desynchronization

### 1. Scenario Description
During a continuous deployment release, a Mongock schema migration failed midway because of a database connection timeout. The deployment runner terminated, but the lock collection on MongoDB remained locked. All future pipeline runs failed with migration lock errors, and the database was left in a partially migrated state, breaking application queries.

### 2. Analytical Diagnostic Investigation
The devops team inspected the pipeline run logs:
```text
io.mongock.api.exception.MongockException: Database lock cannot be acquired because it is currently held by lock owner: runner-instance-042
```
They logged into the database and queried the Mongock tracking collections:
```javascript
// Inspect the migration lock state
db.mongockLock.find().pretty();
// Check which migration stages were applied successfully
db.mongockChangeLog.find().sort({ timestamp: -1 });
```
**Diagnostic Findings**:
*   The migration lock had a timeout value of 3 minutes, but because the runner crashed abruptly, the lock record did not clear.
*   The schema update modified document fields, but because the migration script was not idempotent, running it again would fail with duplicate key or structure mismatch errors.

### 3. Step-by-Step Recovery and Validation Runbook
1.  **Manually Release the Database Lock**:
    Remove the lock record to allow subsequent migration tasks to run:
    ```javascript
    db.mongockLock.deleteMany({ lockKey: "MONGOCK_LOCK" });
    ```
2.  **Rollback Partially Applied Migration Changes**:
    Manually clean up the database state to restore it to the previous version before the failed update.
3.  **Ensure Migration ChangeSets are Idempotent**:
    Modify migration scripts to verify existing conditions before applying writes (e.g. check if field exists before adding it).
4.  **Validate Schema Changes Locally using Testcontainers**:
    Create an automated integration test that runs the migration against a clean local database container before executing production releases (see Java code below).

### 4. Code Artifact: Java Integration Migration Test
Save this class as `MigrationIntegrationTest.java` to test migrations:
```java
package com.example.test;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.testcontainers.containers.MongoDBContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@Testcontainers
public class MigrationIntegrationTest {

    @Container
    static final MongoDBContainer mongoDBContainer = new MongoDBContainer("mongo:6.0.5");

    @Autowired
    private MongoTemplate mongoTemplate;

    @Test
    public void testMigrationSuccess() {
        // Assert container is running
        assertThat(mongoDBContainer.isRunning()).isTrue();
        
        // Assert migration collection changes are logged
        boolean changeLogExists = mongoTemplate.collectionExists("mongockChangeLog");
        assertThat(changeLogExists).isTrue();
        
        long changeSetCount = mongoTemplate.getCollection("mongockChangeLog").countDocuments();
        assertThat(changeSetCount).isGreaterThan(0);
        
        // Ensure new database constraints are working
        boolean userFieldIndexed = mongoTemplate.getCollection("users")
            .listIndexes()
            .toList()
            .stream()
            .anyMatch(doc -> doc.get("name").toString().contains("email"));
        assertThat(userFieldIndexed).isTrue();
    }
}
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Idempotency is Essential**: Every database schema change script must be safe to run multiple times. If a migration is interrupted, executing it again must complete successfully without side effects.
*   **Use Blue-Green Strategy for Schema Changes**: Avoid modifying active production collections directly. Instead, create new collections, replicate writes using change streams, and swap collection aliases when sync completes.
""",
    "14-atlas-search-and-vector-search.md": """
---

## 12. Enterprise Case Study: Atlas Search Sync Lag & Index Size Bloat

### 1. Scenario Description
An international e-commerce portal deployed Atlas Search for product searches and vector recommendations. During peak sales, customers complained that newly added products did not show up in searches, and query response times spiked from 50ms to 4,500ms. MongoDB Atlas consoles showed Search indexing lag metrics exceeding 20 minutes, while search node RAM usage hit 100%.

### 2. Analytical Diagnostic Investigation
The search engineering team profiled search metrics:
*   They checked search replica sync status:
    ```javascript
    db.products.aggregate([{ $searchStatus: {} }]);
    ```
*   They inspected the index mappings. The search index used "Dynamic Mapping", which instructs Lucene to index *every single field* inside all BSON documents.

**Diagnostic Findings**:
*   The dynamic search mapping generated a massive Lucene index structure, exceeding search node RAM.
*   Because Lucene ran out of memory, it began paging to disk, slowing down index update steps.
*   Since Atlas Search consumes changes from the oplog asynchronously, the slow index updates caused search results to lag behind database writes.

### 3. Step-by-Step Resolution Runbook
1.  **Define and Apply Explicit Index Mappings**:
    Disable Dynamic Mapping and define mappings only for queried fields (see config below).
2.  **Optimize Analyzer Allocations**:
    Replace heavy analyzers with specific tokenizers (like standard or edgeGram) to reduce index segment sizes.
3.  **Scale Search Node Capacity**:
    In MongoDB Atlas console, upgrade the Search Node configuration (from M30 to M40) to allocate dedicated search memory.
4.  **Implement Hybrid Query Fallbacks**:
    If search node lag metrics exceed a threshold, configure the client application to query secondary indexes as a fallback.

### 4. Code Artifact: Explicit Search Index Configuration Payload
Save this payload as `search-index-config.json` to define explicit mappings:
```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "productName": {
        "type": "string",
        "analyzer": "lucene.standard",
        "searchAnalyzer": "lucene.standard"
      },
      "description": {
        "type": "string",
        "analyzer": "lucene.english"
      },
      "tags": {
        "type": "string"
      },
      "vectorDescription": {
        "type": "knnVector",
        "dimensions": 1536,
        "similarity": "cosine"
      }
    }
  }
}
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Explicit Mappings for Search**: Never deploy dynamic mappings to production. Define search indexes explicitly to prevent Lucene index size bloat and reduce sync lag.
*   **Oplog Sync Performance**: Lucene index sync is asynchronous. If you need read-after-write consistency, do not query search nodes immediately after database writes.
""",
    "15-system-design-with-mongodb.md": """
---

## 12. Enterprise Case Study: SaaS Multi-Tenant Cross-Contamination & Resource Starvation

### 1. Scenario Description
A SaaS provider stores customer accounting data in a shared MongoDB cluster. They used a shared collection design, separating tenants using a `tenantId` field. During peak tax filing periods, a high-volume tenant executed heavy aggregation queries. This exhausted the database threads, causing queries for all other tenants to time out. Additionally, a bug in a developer's query omitted the `tenantId` filter, resulting in a cross-tenant data leak.

### 2. Analytical Diagnostic Investigation
The DBA checked database operations using `db.currentOp()`:
```javascript
db.currentOp({ "waitingForLock": true, "secs_running": { "$gt": 5 } });
```
**Diagnostic Findings**:
*   A single tenant was executing queries containing unindexed parameters, generating collection scans across millions of documents.
*   WiredTiger resources (read/write tickets) were exhausted by this tenant, leaving no execution slots for other tenants.
*   The code audit showed database queries were built by dynamically appending user parameters, making it easy to forget the tenant scope check.

### 3. Step-by-Step Resolution Runbook
1.  **Deploy Tenant Shard Zones**:
    Migrate to a zoned sharding design. Assign tenant IDs to specific shards to isolate workload resource usage:
    ```javascript
    sh.addShardTag("shard-01", "TenantZoneA");
    sh.addTagRange("saas_db.accounts", { tenantId: "tenant-001" }, { tenantId: "tenant-100" }, "TenantZoneA");
    ```
2.  **Enforce Query Filters at the Application Layer**:
    Implement a database filter interceptor to inject the `tenantId` scope automatically (see Java code below).
3.  **Deploy Rate Limiters**:
    Apply database connection rate limiters per tenant at the API gateway layer to prevent resource starvation.

### 4. Code Artifact: Java Spring Boot MongoDB Tenant Interceptor
Save this class as `TenantInterceptor.java` to enforce tenant scope checks automatically:
```java
package com.example.saas;

import org.bson.Document;
import org.springframework.data.mongodb.core.mapping.event.BeforeConvertCallback;
import org.springframework.data.mongodb.core.mapping.event.BeforeSaveCallback;
import org.springframework.stereotype.Component;

@Component
public class TenantInterceptor implements BeforeConvertCallback<TenantEntity>, BeforeSaveCallback<TenantEntity> {

    @Override
    public TenantEntity onBeforeConvert(TenantEntity entity, String collection) {
        String currentTenant = TenantContext.getCurrentTenantId();
        if (currentTenant == null) {
            throw new IllegalStateException("Authentication context is missing tenant scope ID!");
        }
        entity.setTenantId(currentTenant);
        return entity;
    }

    @Override
    public TenantEntity onBeforeSave(TenantEntity entity, Document document, String collection) {
        document.put("tenantId", TenantContext.getCurrentTenantId());
        return entity;
    }
}
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Database-per-Tenant vs Shared Collection**: Database-per-tenant guarantees isolation but scales poorly due to open file descriptors and collection overhead limits. Shared-collection scales well but requires strict access controls.
*   **Zoned Sharding**: Use zoned sharding to isolate enterprise tenants to dedicated nodes while keeping standard tenants on shared nodes.
""",
    "16-production-project-capstone.md": """
---

## 9. Enterprise Case Study: Capstone Project IoT Telemetry Ingestion Bottleneck

### 1. Scenario Description
During a simulated stress test of the capstone IoT telemetry pipeline, the ingestion system failed to process 500,000 metrics per minute. The ingestion worker container instances threw socket exceptions, write queue lengths increased, and telemetry packets were dropped. CPU utilization on the primary MongoDB instance hit 100%, and the system was unable to persist telemetry events in real time.

### 2. Analytical Diagnostic Investigation
The engineering team audited the MongoDB metrics:
```bash
mongosh --eval "db.serverStatus().wiredTiger.concurrentTransactions"
```
**Diagnostic Findings**:
*   The aggregation worker, which generates hourly sensor rollups, was executing collection scans over raw telemetry data while writes were occurring.
*   The raw write operations competed with the aggregation queries for WiredTiger read/write tickets, causing write queues to build.
*   The bucket document sizes were growing beyond 2MB because the simulator was writing data points in a single, un-partitioned array field.

### 3. Step-by-Step Optimization Runbook
To optimize the capstone project pipeline for high-throughput production workloads, the team performed these steps:

1.  **Optimize the Bucket Design**:
    Configure the ingestion script to partition metrics into buckets of 100 records using the bucket pattern:
    ```javascript
    db.sensor_buckets.updateOne(
      { sensorId: sensorId, count: { $lt: 100 } },
      {
        $push: { readings: { timestamp: new Date(), value: readingValue } },
        $inc: { count: 1 }
      },
      { upsert: true }
    );
    ```
2.  **Separate Ingestion and Aggregation Workloads**:
    Configure the aggregation worker to read from secondary replica set nodes to offload queries from the primary node:
    ```javascript
    const client = new MongoClient("mongodb://localhost:27017/?readPreference=secondary");
    ```
3.  **Tune WiredTiger Thread Concurrency**:
    Configure the database to use more concurrent write tickets under write-heavy loads:
    ```javascript
    db.adminCommand({
      setParameter: 1,
      "wiredTigerEngineRuntimeConfig": "concurrent_write_transactions=128"
    });
    ```
4.  **Validate End-to-End Pipeline Performance**:
    Run a simulation test to confirm that ingestion rates remain stable above 500,000 requests per minute.

### 4. Code Artifact: Ingestion Load Test Validation Script
Save this script as `run-load-test.js` to simulate load on the telemetry database:
```javascript
const { MongoClient } = require('mongodb');

async function simulateLoad() {
  const uri = "mongodb://localhost:27017/telemetry_db?maxPoolSize=200";
  const client = new MongoClient(uri);
  await client.connect();
  const db = client.db();
  
  console.log("Starting high-throughput simulation load test...");
  
  const startTime = Date.now();
  let totalWrites = 0;
  
  const promises = [];
  for (let i = 0; i < 10000; i++) {
    const sensorId = "sensor-" + Math.floor(Math.random() * 500);
    const value = Math.random() * 100;
    
    promises.push(
      db.collection("sensor_buckets").updateOne(
        { sensorId: sensorId, count: { $lt: 100 } },
        {
          $push: { readings: { timestamp: new Date(), value: value } },
          $inc: { count: 1 }
        },
        { upsert: true }
      ).then(() => { totalWrites++; })
    );
  }
  
  await Promise.all(promises);
  const duration = (Date.now() - startTime) / 1000;
  console.log(`Simulation finished. Total Writes: ${totalWrites} in ${duration} seconds.`);
  console.log(`Throughput: ${(totalWrites / duration).toFixed(2)} writes/second.`);
  
  await client.close();
}
simulateLoad().catch(console.dir);
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Offload Heavy Queries**: Never run long-running report or aggregation queries on your primary write database. Route reports to replica set secondaries to keep the primary free for write operations.
*   **The Power of Bucketing**: Using the bucketing pattern for time-series data reduces the index size and index update frequency, improving throughput compared to single-document-per-event designs.
"""
}

def apply_case_studies():
    print("Applying Enterprise Case Studies to module files...")
    
    for filename, study in case_studies.items():
        filepath = os.path.join(modules_dir, filename)
        if not os.path.exists(filepath):
            print(f"Skipping {filename} - path not found.")
            continue
            
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        if "Enterprise Case Study:" in content:
            print(f"Skipping {filename} - already contains case study.")
            continue
            
        # Detect the Appendix section
        # We want to insert the Case Study right BEFORE the Appendix section (or before the Runbook, or at the end).
        # Let's check if there is an Appendix section or Runbook section.
        # To make things extremely safe, clean, and robust, we can append it at the end of the file.
        # However, let's look at the structure. If the file ends with the Appendix, we can append the case study.
        # But wait, does it make sense to put Case Studies as a new section? Yes, it does.
        # Let's just append it to the end of the file. That is 100% safe and doesn't break any existing text.
        new_content = content.strip() + "\n\n" + study.strip() + "\n"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print(f"Applied case study to {filename} successfully.")

if __name__ == "__main__":
    apply_case_studies()
