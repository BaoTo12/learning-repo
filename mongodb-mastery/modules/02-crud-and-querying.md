# Module 02: Advanced CRUD & Concurrency

## 1. What Problem This Module Solves
In high-throughput systems, execution path inefficiencies inside database queries can saturate resources. Simple queries run slowly if locks block each other, concurrent updates corrupt nested arrays, and upserts write duplicate records due to race conditions. 

This module addresses these concurrency and throughput bottlenecks. A senior engineer must understand the write path lifecycle, lock compatibility matrices, lock queuing mechanisms, query plan cache internals, upsert safety constraints, and array filtering mechanics. Without this knowledge, developers run the risk of introducing latency spikes, data corruption, and deadlocks under production-level concurrency.

---

## 2. Why This Topic Matters
Failing to configure concurrency and lock behaviors correctly can lead to system outages. For example, if a developer writes an API that does not use atomic operators, concurrent requests will overwrite each other's changes (lost updates). Similarly, running bulk operations without understanding batch size limits can saturate memory and block execution threads. 

Understanding how MongoDB handles locks at the global, database, collection, and document level helps engineers design APIs that scale horizontally and maintain predictable performance.

---

## 3. Core Concepts & Internals

### 3.1 The MongoDB Write Path Lifecycle (Detailed)
When a client application writes to a primary MongoDB node (e.g. executing `updateOne`), the operation passes through several critical internal steps:

```
[Client App] 
     │ (Driver socket connection pool checkout)
     ▼
[mongod Listener Thread]
     │ (Asynchronously multiplexed to Worker Thread)
     ▼
[1. Acquire Lock Hierarchy] ──> DB (IX) -> Collection (IX) -> Document (X)
     │
     ▼
[2. Read Page into WiredTiger Cache] ──> (If not in memory, fetch from disk)
     │
     ▼
[3. Modify BSON in Cache] ──> (Mark Memory Page as "Dirty")
     │
     ├─────────────────────────────────────────────────┐
     ▼ (Immediate log write to buffer)                 ▼ (Background Checkpoint)
[4. Write to local.oplog.rs]                      [6. WiredTiger Checkpoint]
     │                                                 │ (Every 60s or 2GB dirty data)
     ▼                                                 │ (Reconciliation phase)
[5. Flush to Journal on Disk]                          ▼
     │ (Every 100ms or on {j:true})              [Physical Data Files on Disk]
     ▼
[Journal Files on Disk]
```

#### Detailed Execution Walkthrough:
1.  **Connection Management**: The client driver checks out a socket from the connection pool. The request arrives at the `mongod` process, where the listener thread assigns it to a worker thread from the thread pool.
2.  **Lock Acquisition**: The database engine determines the lock requirements. It requests Intent-Exclusive (`IX`) locks at the Global, Database, and Collection levels. Finally, it requests an Exclusive (`X`) lock on the specific document being updated.
3.  **WiredTiger Page Fetch**: WiredTiger looks for the document in its cache. If the page is not in the cache (cache miss), it performs a synchronous read from disk to pull the compressed page (Zstandard or Snappy) into RAM, decompresses it, and caches it.
4.  **In-Memory BSON Modification**: The document is modified in memory. The corresponding cache page is marked as **dirty**. The operations are concurrently appended to the replication oplog buffer (`local.oplog.rs`).
5.  **Journaling (Durability)**: The changes are written to the WiredTiger journal buffer in memory. The journal buffer is flushed to physical disk:
    *   Every **100ms** by default.
    *   Immediately if a write query specifies `{ j: true }` or is part of a write concern that forces journal synchronization.
6.  **Data Checkpointing (Reconciliation)**: Every **60 seconds** (or when the volume of dirty pages exceeds **2GB**), the WiredTiger background threads run a **checkpoint**. The engine reconciles the in-memory dirty pages, compresses them, and writes them to the main physical data files (`.wt` files) on disk in a transactional, crash-safe manner.

---

### 3.2 Lock Hierarchy, Queues & Compatibility Matrix
MongoDB uses a Multi-Granularity Locking (MGL) scheme. This allows the system to balance locking overhead and concurrency by locking only what is necessary.

```
       Global (r/w)
            │
      Database (d) (IS / IX)
            │
     Collection (c) (IS / IX)
            │
     Document (y) (S / X)
```

#### Lock Compatibility Matrix
*   **Intent Shared (IS)**: Indicates intent to read at a lower level of the hierarchy.
*   **Intent Exclusive (IX)**: Indicates intent to write at a lower level of the hierarchy.
*   **Shared (S)**: Read lock on the resource itself.
*   **Exclusive (X)**: Write lock on the resource itself (blocks all reads and writes).

| Requested Mode | IS | IX | S | X |
| :--- | :--- | :--- | :--- | :--- |
| **IS** | Compatible | Compatible | Compatible | Conflict |
| **IX** | Compatible | Compatible | Conflict | Conflict |
| **S** | Compatible | Conflict | Compatible | Conflict |
| **X** | Conflict | Conflict | Conflict | Conflict |

#### Lock Queues & Concurrency Tuning:
*   **Lock Queuing**: When a thread requests a lock that conflicts with an existing lock, it is placed in a **priority-ordered lock queue**. MongoDB prioritizes write requests (`X`, `IX`) over read requests (`S`, `IS`) in the queue to prevent writers from starving.
*   **WiredTiger Ticket Concurrency**: Independent of database-level locks, WiredTiger limits active execution threads using a ticket-based system:
    *   `wiredTiger.concurrentWriteTransactions` (Default: 128)
    *   `wiredTiger.concurrentReadTransactions` (Default: 128)
    If these tickets are exhausted under extreme workloads, operations queue up inside WiredTiger, causing latency to spike even if no collection-level locks are present.

---

### 3.3 Query Plan Cache & Eviction Mechanics
To avoid evaluating every index strategy for every query, MongoDB caches winning plans.

#### How a Plan is Selected and Cached:
1.  **Query Shape Identification**: The Query Planner generates a query shape hash based on the query fields, sort parameters, and projections.
2.  **Trial Execution**: If there is no entry in the cache, the planner spawns multiple candidate index plans and executes them in parallel (using "work units").
3.  **Winning Plan Selection**: The first plan to return 101 documents (or complete scanning) wins. This plan is saved in the Query Plan Cache.
4.  **Plan Eviction**: Cached plans are cleared and rebuilt if:
    *   An index is created, dropped, or modified.
    *   The database service is restarted.
    *   `db.collection.clearQueryPlanCache()` is called.
    *   The query planner detects that the execution performance of the cached plan has degraded (the ratio of `totalKeysExamined` to `nReturned` exceeds the historical baseline).

#### Inspecting the Plan Cache with `planCacheStats`
You can inspect the cached query plans by running:
```javascript
db.collection.aggregate([
  { $planCacheStats: {} }
]).pretty();
```

Here is an annotated mock output from a production collection:
```json
{
  "queryHash": "8B4F3A1D",
  "planCacheKey": "3A2D1F9C",
  "isActive": true,
  "works": NumberLong(145),
  "version": "1",
  "createdFromQuery": {
    "query": { "status": "ACTIVE", "age": { "$gt": 25 } },
    "sort": { "createdAt": -1 },
    "projection": {}
  },
  "cachedPlan": {
    "stage": "FETCH",
    "inputStage": {
      "stage": "IXSCAN",
      "keyPattern": { "status": 1, "createdAt": -1, "age": 1 },
      "indexName": "status_1_createdAt_-1_age_1"
    }
  },
  "creationExecStats": [
    {
      "nReturned": 101,
      "executionTimeMillis": 2,
      "totalKeysExamined": 101,
      "totalDocsExamined": 101
    }
  ]
}
```
*   `queryHash`: A hex string identifying the structural shape of the query filter.
*   `planCacheKey`: A hex string identifying the query shape combined with index configuration details.
*   `isActive`: Boolean indicating if the plan is currently active and used for execution.
*   `works`: The number of internal trial evaluation cycles run before selecting this winning plan.

---

### 3.4 Upsert Concurrency Race Conditions
An `upsert` (update with `{ upsert: true }`) updates a document if found, or inserts a new document if missing.

#### The Concurrency Vulnerability:
1.  **Thread A** executes `updateOne({ email: "user@example.com" }, { ... }, { upsert: true })`. It scans the index and finds no matching document.
2.  **Thread B** concurrently executes the exact same query. It also scans the index and finds no matching document.
3.  **Thread A** proceeds to insert a new document.
4.  **Thread B** also proceeds to insert a new document.
5.  *Result*: Two documents with `{ email: "user@example.com" }` are created, violating logical application rules.

#### The Solution: Unique Indexes
An upsert operation does **not** hold a collection-level lock during the find-and-insert phase. To guarantee data integrity:
1.  You **must** create a **unique index** on the fields in the query filter (e.g. `{ email: 1 }`).
2.  With the unique index, the second thread's insert will fail at the storage engine level with a **Duplicate Key Error (Code 11000)**.
3.  The application driver or controller must catch this exception and retry the operation, which will now resolve as a standard update instead of an insert.

---

## 4. Practical Examples

### Multi-Level Nested Array Updates
Given a collection representing institutional courses with multi-level nested arrays:
```json
{
  "_id": 101,
  "semesters": [
    {
      "semesterId": "2026-FALL",
      "courses": [
        { "code": "CS-101", "enrolled": 20, "grades": [ 80, 85, 90 ] },
        { "code": "MATH-201", "enrolled": 15, "grades": [ 70, 75 ] }
      ]
    }
  ]
}
```

To update a grade of `85` to `95` for course `"CS-101"` inside semester `"2026-FALL"`, you must use positional nested array filters:
```javascript
db.institutions.updateOne(
  { _id: 101 },
  { $set: { "semesters.$[sem].courses.$[crse].grades.$[grd]": 95 } },
  {
    arrayFilters: [
      { "sem.semesterId": "2026-FALL" },
      { "crse.code": "CS-101" },
      { "grd": 85 }
    ]
  }
);
```

#### Explanation of Positional Identifiers:
*   `$[sem]` matches elements in the `semesters` array that satisfy the filter `sem.semesterId === "2026-FALL"`.
*   `$[crse]` matches elements in the `courses` array nested within the matched semester that satisfy the filter `crse.code === "CS-101"`.
*   `$[grd]` matches the value inside the `grades` array that is exactly equal to `85`.

---

### Concurrency Testing Script (Java / Spring Boot)
The following production-grade Java class demonstrates how to programmatically test for upsert race conditions using concurrent threads and latch-controlled synchronization.

```java
package com.ecommerce.domain.user.domain.service;

import com.mongodb.MongoWriteException;
import com.mongodb.client.result.UpdateResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Update;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

public class ConcurrencyTestService {
    private static final Logger log = LoggerFactory.getLogger(ConcurrencyTestService.class);
    private final MongoTemplate mongoTemplate;

    public ConcurrencyTestService(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    public void runConcurrentUpsertTest(String testEmail) throws InterruptedException {
        int numberOfThreads = 8;
        ExecutorService executor = Executors.newFixedThreadPool(numberOfThreads);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch finishLatch = new CountDownLatch(numberOfThreads);

        AtomicInteger successCount = new AtomicInteger(0);
        AtomicInteger duplicateKeyErrorCount = new AtomicInteger(0);
        AtomicInteger otherErrorCount = new AtomicInteger(0);

        for (int i = 0; i < numberOfThreads; i++) {
            executor.submit(() -> {
                try {
                    // Block until the start latch is released to simulate simultaneous execution
                    startLatch.await();
                    
                    Query query = new Query(Criteria.where("email").is(testEmail));
                    Update update = new Update().set("status", "ACTIVE").setOnInsert("version", 1);
                    
                    UpdateResult result = mongoTemplate.upsert(query, update, "users");
                    successCount.incrementAndGet();
                    log.info("Upsert completed successfully. Matched: {}, UpsertedId: {}", 
                             result.getMatchedCount(), result.getUpsertedId());
                } catch (MongoWriteException ex) {
                    if (ex.getError().getCode() == 11000) {
                        duplicateKeyErrorCount.incrementAndGet();
                        log.warn("Caught expected duplicate key error (11000) on concurrent upsert.");
                    } else {
                        otherErrorCount.incrementAndGet();
                        log.error("Write exception occurred: ", ex);
                    }
                } catch (Exception ex) {
                    otherErrorCount.incrementAndGet();
                    log.error("General error during upsert test: ", ex);
                } finally {
                    finishLatch.countDown();
                }
            });
        }

        // Release the latch to trigger all threads simultaneously
        startLatch.countDown();
        finishLatch.await();
        executor.shutdown();

        log.info("Test results - Successes: {}, Duplicate Key Errors: {}, Other Errors: {}", 
                 successCount.get(), duplicateKeyErrorCount.get(), otherErrorCount.get());
    }
}
```

---

## 5. Trade-offs & Alternatives

When handling concurrent operations, choose the strategy that aligns with your consistency and performance requirements:

| Concurrency Pattern | Performance | Consistency | Retry Complexity | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Atomic Operators (`$inc`, `$push`)** | **Ultra-High**: Lock duration is extremely short; executed directly in the database engine. | **Strong**: Operations are atomic at the document level. | **None**: No conflicts to handle at the application level. | Counters, inventory reductions, append-only logs. |
| **Find and Modify (`findOneAndUpdate`)** | **Medium**: Blocks other modifications to the document while the query and write execute. | **Strong**: Returns either the pre-updated or post-updated document atomically. | **Low**: Handled by the database engine, but can queue threads. | Ticket allocations, state machine transitions, claim tasks. |
| **Optimistic Concurrency Control (OCC)** | **High**: Uses versioning fields (e.g. `{ version: 1 }`) in the query filter. No database-level blocking. | **Strong**: Rejects updates if the version has changed. | **High**: The client must intercept failures, reload the document, and retry the update. | Collaborative document editing, profile updates. |
| **Multi-document Transactions** | **Low**: Acquires exclusive locks on all documents in the session; locks are held until commit/abort. | **Strict ACID**: Isolation matches snapshot read levels. | **High**: Transient errors are common; requires client-side retry loops. | Inter-account ledger transfers, multi-collection operations. |

---

## 6. Common Mistakes & Anti-patterns
*   **Executing Unordered Bulk Writes expecting sequence**: Setting `{ ordered: false }` when operation B relies on the success or state change of operation A. Since unordered batches run in parallel, operations can be processed out of order, leading to inconsistent data states.
*   **Querying inside Array Filters**: Putting filters in the `arrayFilters` array that are not present in the primary query filter block. This prevents MongoDB from applying indexes to filter the parent documents first, resulting in a costly collection scan (`COLLSCAN`).
*   **Using `findOneAndUpdate` when `updateOne` is sufficient**: Calling `findOneAndUpdate` just to modify a field without needing the returned document. This causes unnecessary overhead, as the database must serialize the document and send it back to the client over the network.

---

## 7. Hands-on Exercises
1.  Create a replica set environment. Insert a mock collection representing a user's task tracker.
2.  Write an update query using nested `arrayFilters` to modify all active tasks inside a user's `todos` list.
3.  Implement the Java code listed in section 4. Run the script with 10 concurrent threads *without* a unique index on the collection. Inspect the collection for duplicate documents.
4.  Apply a unique index on the field, re-run the script, and observe how the code intercepts the `11000` duplicate key exception to maintain integrity.

---

## 8. Mini-Project: State Machine Transition Engine
**Scenario**: Build a transactional booking engine where ticket reservations must transition through strict state sequences: `PENDING` -> `RESERVED` -> `PAID`.

The system must guarantee that no two threads can update the same booking simultaneously, and a transition from `PENDING` to `RESERVED` can only succeed if the ticket is currently `PENDING`.

```javascript
/**
 * Atomic State Transition Engine
 * Saves data integrity under concurrent requests.
 */
const { MongoClient } = require('mongodb');

async function transitionBookingState(uri, bookingId, targetState) {
  const client = new MongoClient(uri);
  try {
    await client.connect();
    const db = client.db('booking_db');
    const bookings = db.collection('bookings');

    // Define valid state transitions
    const transitionRules = {
      'RESERVED': 'PENDING',
      'PAID': 'RESERVED'
    };

    const expectedPreviousState = transitionRules[targetState];
    if (!expectedPreviousState) {
      throw new Error(`Invalid target state transition: ${targetState}`);
    }

    log.info(`Attempting state transition for booking ${bookingId} to ${targetState}...`);

    // Perform atomic state update
    const result = await bookings.findOneAndUpdate(
      {
        _id: bookingId,
        status: expectedPreviousState
      },
      {
        $set: { status: targetState, updatedAt: new Date() }
      },
      {
        returnDocument: 'after' // Return updated document
      }
    );

    if (!result.value) {
      throw new Error(
        `State transition failed. Booking either does not exist, or status is not '${expectedPreviousState}'`
      );
    }

    log.info(`State transition succeeded! New state: ${result.value.status}`);
    return result.value;

  } catch (error) {
    log.error(`Transaction aborted: ${error.message}`);
    throw error;
  } finally {
    await client.close();
  }
}
```

---

## 9. Interview Questions

### Q1: How does MongoDB's query plan cache evaluate query shapes? How do you force plan recompilation?
**Answer**: MongoDB evaluates query shapes by parsing the query filter, sort parameters, and projections into a structural representation (ignoring literal values). If no plan exists in the cache, the planner runs candidate indexes in parallel. The fastest index strategy is stored in the cache. 
You can force plan recompilation by:
1. Creating, dropping, or modifying an index.
2. Running `db.collection.clearQueryPlanCache()`.
3. Restarting the `mongod` daemon.
4. Calling `planCacheStats` and deleting a specific key.

### Q2: Why is a unique index required to guarantee upsert safety?
**Answer**: An `upsert` is not an atomic single-lock operation. It executes a query to check for document existence, relaxes its lock, and then performs either an insert or an update. Under high concurrency, two operations can check for existence at the same time, find no document, and both attempt to insert. A unique index enforces constraint validation at the storage engine level, rejecting the second insert with a duplicate key error (Code 11000), which allows the application to retry the operation as an update.

### Q3: What is the difference between ordered and unordered bulk writes?
**Answer**:
*   **Ordered Bulk Writes (`{ ordered: true }`)**: MongoDB executes operations sequentially. If any single write fails, execution stops immediately, and the remaining operations are skipped.
*   **Unordered Bulk Writes (`{ ordered: false }`)**: MongoDB executes operations in parallel. If an operation fails, execution continues, processing all remaining writes, and returns an aggregate report listing all successes and failures.

---

---

---

## 10. Production Runbook & Deployment Guidelines

### 1. Diagnosing Slow Write Operations
When update queries experience performance drops, you must analyze the lock duration and wait queues. Check current lock statistics by running:
```javascript
db.serverStatus().locks;
```
Verify the `acquireWaitCount` and `acquireTimeMicros` values. If the wait times are high, identify long-running operations using:
```javascript
db.currentOp({ "secs_running": { "$gt": 5 } });
```
Kill stuck write operations using their operation ID:
```javascript
db.killOp(opId);
```

### 2. Clearing Query Plan Cache
If a query plan behaves suboptimally, you can clear the plan cache manually for the collection:
```javascript
db.products.clearQueryPlanCache();
```
This forces the query planner to run parallel trial evaluations and cache a new winning plan on the next query execution.

## 11. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Lock Queue Bottlenecks (Ticket Exhaustion)
*   **Failure Mode**: High concurrent write requests exhaust the available WiredTiger concurrent write tickets (default 128), causing threads to queue up and API latency to spike.
*   **Diagnosis**: Check active tickets using:
    ```javascript
    db.serverStatus().wiredTiger.concurrentTransactions;
    ```
*   **Resolution**: Optimize query performance to return connections faster, or implement rate limiting in the application tier.

### 2. Query Plan Cache Bloat
*   **Failure Mode**: Having too many unique query shapes (e.g. dynamic queries generated by ORMs without bind parameters) consumes substantial memory and causes plan cache lookups to slow down.
*   **Resolution**: Standardize query formats in the application layer and limit the maximum size of the plan cache using parameter settings.

### 3. Duplicate Key Errors (Code 11000) on Concurrent Upserts
*   **Failure Mode**: Concurrently executing upserts on identical query filters results in duplicate inserts before the unique index is built.
*   **Resolution**: Always build unique indexes on filter fields before executing concurrent upserts, and catch and retry code 11000 exceptions.

---

## 12. Summary
Advanced CRUD operations require understanding concurrency constraints. By using positional array operators, designing atomic query structures, mitigating upsert race conditions with unique indexes, and monitoring query plan caching, senior engineers ensure high performance under load.

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

---

## 12. Hands-on Lab Exercise: Building an ESR-Compliant Dynamic Query Builder

### 1. Objective and Scenario
Ensure all dynamically generated application queries conform to the Equality, Sort, Range (ESR) indexing pattern. You will write a helper class in Node.js that parses client-defined criteria, filters invalid operations, and builds queries that are guaranteed to use matching compound indexes.

### 2. Code Implementation: `esr-query-builder.js`
Create a file named `esr-query-builder.js` and paste the following code:
```javascript
class EsrQueryBuilder {
  constructor() {
    this.equalityFilters = {};
    this.sortFilters = {};
    this.rangeFilters = {};
  }

  addEquality(field, value) {
    this.equalityFilters[field] = value;
    return this;
  }

  addSort(field, direction) {
    this.sortFilters[field] = direction;
    return this;
  }

  addRange(field, operator, value) {
    if (!this.rangeFilters[field]) {
      this.rangeFilters[field] = {};
    }
    this.rangeFilters[field][operator] = value;
    return this;
  }

  build() {
    const query = { ...this.equalityFilters };
    for (const [field, rangeObj] of Object.entries(this.rangeFilters)) {
      query[field] = { ...query[field], ...rangeObj };
    }
    
    return {
      query,
      sort: this.sortFilters,
      // Verify that the index structure matches the ESR rule
      expectedIndexPattern: {
        ...Object.keys(this.equalityFilters).reduce((acc, k) => ({ ...acc, [k]: 1 }), {}),
        ...Object.keys(this.sortFilters).reduce((acc, k) => ({ ...acc, [k]: this.sortFilters[k] }), {}),
        ...Object.keys(this.rangeFilters).reduce((acc, k) => ({ ...acc, [k]: 1 }), {})
      }
    };
  }
}

// Test ESR builder execution
const builder = new EsrQueryBuilder();
const payload = builder
  .addEquality("status", "ACTIVE")
  .addEquality("category", "ELECTRONICS")
  .addSort("price", -1)
  .addRange("stock", "$gt", 10)
  .build();

console.log("Generated Query Criteria:", JSON.stringify(payload.query, null, 2));
console.log("Generated Sort Criteria:", JSON.stringify(payload.sort, null, 2));
console.log("Recommended Index Pattern:", JSON.stringify(payload.expectedIndexPattern, null, 2));
```

### 3. Lab Verification Steps
1.  Execute the script using node:
    ```bash
    node esr-query-builder.js
    ```
2.  Verify the output order matches ESR: status and category first, followed by price, and lastly stock.

---

## 13. Query Execution & Index Selection Reference

### 1. Key Query Planner Parameters
Tweak these system variables to optimize query plan evaluation times:
*   `internalQueryPlannerMaxIndexedSolutions`: Limits the maximum indexed plans evaluated (Default: 64).
*   `internalQueryExecMaxBlockingSortBytes`: The maximum memory allocation allowed for execution sort operations (Default: 33,554,432 bytes).

### 2. Operational Diagnostic Commands
Verify execution statistics and investigate slow queries using these scripts:
```javascript
// Explain winning and rejected plan details for a specific query
db.collection.find({ status: "ACTIVE" }).sort({ score: -1 }).explain("allPlansExecution");

// List all cached execution plans for a collection
db.collection.getPlanCache().list();
```

### 3. Senior Engineer's Production Checklist
*   [ ] Run `explain("executionStats")` on all application queries to ensure winning plans utilize `IXSCAN` and avoid `COLLSCAN` stages.
*   [ ] Add explicit `.limit()` constraints to sorting queries to prevent memory overflow errors.
*   [ ] Set database profiling thresholds (`db.setProfilingLevel(1, 100)`) to log queries taking longer than 100ms.\n\n---

## 15. Advanced Query Formulation Reference Guide

### 1. Complex Array Filtering and Element Projections
When querying documents containing nested array structures, standard projection filters retrieve the *entire* array. To isolate only the specific array elements matching a criteria, you must use either the `$elemMatch` projection operator or modern aggregation projections.

#### Scenario: Fetching Specific Active Transactions
Suppose a customer document contains an array of transaction history:
```json
{
  "_id": 1001,
  "customerName": "Acme Corp",
  "transactions": [
    { "txId": "T101", "amount": 500, "status": "APPROVED" },
    { "txId": "T102", "amount": 1200, "status": "PENDING" },
    { "txId": "T103", "amount": 150, "status": "REJECTED" }
  ]
}
```
If you execute a standard query `find({ "transactions.status": "PENDING" })`, MongoDB returns the entire document including the approved and rejected items. To isolate only the pending transaction, use the `$elemMatch` projection block:
```javascript
// Query projection using $elemMatch
db.customers.find(
  { "transactions.status": "PENDING" },
  { "transactions.$": 1, "customerName": 1 }
);
```
*Note*: The positional projection operator `$` returns only the *first* matching element inside the array. If you need to filter and return multiple elements from an array (e.g. all transactions with amount > 200), use the aggregation framework with the `$filter` operator:
```javascript
db.customers.aggregate([
  { $match: { _id: 1001 } },
  {
    $project: {
      customerName: 1,
      filteredTransactions: {
        $filter: {
          input: "$transactions",
          as: "tx",
          cond: { $gt: ["$$tx.amount", 200] }
        }
      }
    }
  }
]);
```

### 2. Deep Array Updates using Filtered Positional Operators
Updating elements inside nested arrays requires precision. MongoDB provides three update operator patterns:
1.  **Positional Operator (`$`)**: Updates the first matching element identified in the query criteria.
2.  **All-Positional Operator (`$[ ]`)**: Updates all elements inside the array unconditionally.
3.  **Filtered Positional Operator (`$[<identifier>]`)**: Updates only the array elements that match a custom filter defined in the `arrayFilters` parameter list.

#### Scenario: Modifying Price in Nested Product Tiers
Suppose you want to apply a 10% discount to all variants of a product whose inventory level is below 15.
```javascript
// Document structure
{
  "_id": "PROD-102",
  "name": "Heavy Duty Boots",
  "variants": [
    { "sku": "BOOT-S", "price": 100, "stock": 5 },
    { "sku": "BOOT-M", "price": 100, "stock": 20 },
    { "sku": "BOOT-L", "price": 110, "stock": 10 }
  ]
}
```
To update the price of only the small and large variants (where stock is < 15), run:
```javascript
db.products.updateOne(
  { _id: "PROD-102" },
  { $mul: { "variants.$[elem].price": 0.90 } },
  {
    arrayFilters: [ { "elem.stock": { $lt: 15 } } ]
  }
);
```
This query modifies only index 0 and index 2 of the `variants` array in a single atomic write execution, leaving index 1 unchanged.

### 3. Bitwise Query Operators for High-Throughput Access Checks
For systems requiring fine-grained role permissions (like CMS access structures), storing permissions as arrays of strings scales poorly. Instead, compress permission profiles using binary bitmasks.

#### Bitwise Operators:
*   `$bitsAllSet`: Matches documents where all specified bit positions are set to 1.
*   `$bitsAnySet`: Matches documents where at least one of the specified bit positions is set to 1.
*   `$bitsAllClear`: Matches documents where all specified bit positions are set to 0.
*   `$bitsAnyClear`: Matches documents where at least one of the specified bit positions is set to 0.

#### Scenario: Evaluating User Security Permissions
Suppose permission bitmasks are mapped as:
*   Bit 0 (value 1): READ
*   Bit 1 (value 2): WRITE
*   Bit 2 (value 4): EXECUTE
*   Bit 3 (value 8): DELETE

A document stores the user's combined permission bitmask integer value:
```json
{ "_id": "usr-92", "name": "Admin User", "permissions": 11 } // Binary: 1011 (READ, WRITE, DELETE)
```
To query for all users who possess both WRITE (bit 1) and DELETE (bit 3) access, execute:
```javascript
db.users.find({
  permissions: { $bitsAllSet: [ 1, 3 ] } // Matches mask value 11
});
```

### 4. Query Planner Diagnostics for Unindexed Operations
Always verify that queries leverage database indexes. Run explain commands to locate suboptimal executions:
```javascript
db.customers.find({ "transactions.status": "PENDING" }).explain("executionStats");
```
*   `COLLSCAN`: The execution scanned all documents in the collection (Unindexed Query - slow).
*   `IXSCAN`: The execution scanned index keys to locate matching documents (Indexed Query - fast).
*   `FETCH`: The execution retrieved documents from storage using index pointers.
*   `PROJECTION_COVERED`: The execution returned results using only the index key data without loading documents from storage (Most optimized).\n