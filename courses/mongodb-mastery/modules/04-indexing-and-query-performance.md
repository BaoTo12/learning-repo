# Module 04: Indexing & Query Planner Internals

## 1. What Problem This Module Solves
In production systems, missing or poorly designed indexes cause query slowdowns, high disk IOPS, and CPU saturation due to Collection Scans (`COLLSCAN`). 

A senior engineer must understand the internal B-Tree mechanics of WiredTiger indexes, index compression, the query planner's scoring phase, the ESR (Equality, Sort, Range) rule, in-memory sorting limits, and how to safely build or rebuild indexes in active environments. Failing to model indexes correctly leads to index page swaps (swapping index pages between memory and disk), high query latencies, and transaction timeouts.

---

## 2. Why This Topic Matters
Indexes must fit entirely into RAM (the Working Set) to be effective. If your indexes are too large, the database must swap pages to disk, causing query latency spikes. Furthermore, deploying a heavy index build in production without understanding lock requirements can block write traffic, leading to service outages.

Understanding how the query planner evaluates candidate plans, selects a winning index, and caches the result allows developers to write highly optimized queries and design indexes that avoid in-memory sorting bottlenecks.

---

## 3. Core Concepts & Internals

### 3.1 B-Tree Indexes & WiredTiger Page Sizing
WiredTiger organizes indexes in B-Trees.
*   **WiredTiger Pages**: Indexes are stored in pages (default 16KB leaf page size). Each page contains sorted keys and pointers to Record IDs in the collection.
*   **Prefix Compression**: WiredTiger compresses keys on disk and in memory by storing only the difference between consecutive keys. For example, if consecutive keys are `"customer_1001"` and `"customer_1002"`, WiredTiger stores `"customer_1001"` and `"+2"`. This reduces the RAM footprint of the index.

---

### 3.2 Index Types: Advanced Mechanics

#### Multikey Indexes
Automatically created when you index an array field.
*   **Index Entry Explosion**: If a document has an array with 100 elements, MongoDB generates **100 distinct index entries** in the B-Tree for that document.
*   **Cartesian Product Restriction**: You cannot create a compound index where *more than one* field is an array. For example, indexing `{ tags: 1, categories: 1 }` where both are arrays is blocked because it would require $M \times N$ index entries per document, exhausting memory resources.

#### Partial Indexes
Indexes only documents matching a `$type` or query expression (using `partialFilterExpression`).
*   *Advantage*: Much smaller index footprint.
*   *Performance Gotcha*: The query planner will only use the partial index if the query filter explicitly includes the partial expression keys.

#### Wildcard Indexes
Created using `{ "fields.$**": 1 }`. Internally, MongoDB creates a virtual compound index covering all sub-paths and values inside the target document, which is useful for highly dynamic attributes.

#### Hidden Indexes
Allows you to hide an index from the query planner (`db.collection.hideIndex()`). This lets you test the performance impact of removing an index before actually dropping it, preventing risky database changes.

---

### 3.3 The ESR (Equality, Sort, Range) Rule
For compound indexes, follow this order:
1.  **Equality**: Fields queried with exact matches (e.g. `status: "ACTIVE"`).
2.  **Sort**: Fields used to sort results (e.g. `createdAt: -1`).
3.  **Range**: Fields queried with range operators (e.g. `age: { $gt: 25 }`).

#### Why Range Breaks Sort:
If you define an index as `{ age: 1, status: 1 }` (Range before Equality/Sort), the index organizes entries by age first. For documents sharing the same age, it sorts them by status. If your query asks to sort by status, the index order is broken because it is grouped by age first, forcing MongoDB to execute an in-memory `SORT` stage (which is slow and limited to 32MB).

---

## 4. Query Planner Phases & Scoring System

When a query is executed and has no cached plan, the query planner runs a multi-candidate race.

```
       [Query Input]
             │
      (Check Plan Cache)
             ├──────────────────────────┐
             ▼ (Hit)                    ▼ (Miss)
    [Execute Cached Plan]     [Generate Index Candidates]
                                        │
                                        ▼
                              [Execute Trial Runs]
                              (Parallel Execution)
                                        │
                                        ▼
                               [Evaluate Scores]
                                        │
                                        ▼
                              [Cache Winning Plan]
```

### 4.1 Step-by-Step Trial Run Scoring Analysis
The query planner runs each candidate plan concurrently, interleaving execution steps. The plan that first reads **101 documents** (or completes its execution) wins. The planner evaluates plans based on the following metrics:
*   `works`: The number of internal execution steps performed (lower is better).
*   `keysExamined`: The number of index entries scanned (lower is better).
*   `docsExamined`: The number of documents fetched from disk (lower is better).
*   `nReturned`: The number of documents returned.

#### Winning Plan Scoring Formula:
$$\text{Score} = \frac{\text{nReturned}}{\text{works}} - \text{Penalty}$$

*Penalties* are applied for unoptimized operations:
*   **In-Memory Sort Penalty**: If the plan requires an in-memory sort stage (`SORT`), it is heavily penalized.
*   **Unindexed Fetch Penalty**: If the plan does a `COLLSCAN` or has a high `keysExamined` to `nReturned` ratio.

---

### 4.2 Annotated Explain Plan Trace Log
Below is an annotated excerpt of the candidate evaluation stage from an `explain("allPlansExecution")` call:

```json
{
  "queryPlanner": {
    "plannerVersion": 1,
    "namespace": "ecommerce.orders",
    "indexFilterSet": false,
    "parsedQuery": {
      "status": { "$eq": "COMPLETED" },
      "amount": { "$gt": 100 }
    },
    "winningPlan": {
      "stage": "FETCH",
      "inputStage": {
        "stage": "IXSCAN",
        "keyPattern": { "status": 1, "amount": 1, "orderDate": -1 },
        "indexName": "status_1_amount_1_orderDate_-1"
      }
    },
    "rejectedPlans": [
      {
        "stage": "SORT",
        "sortPattern": { "orderDate": -1 },
        "inputStage": {
          "stage": "FETCH",
          "inputStage": {
            "stage": "IXSCAN",
            "keyPattern": { "status": 1 },
            "indexName": "status_1"
          }
        }
      }
    ]
  },
  "executionStats": {
    "executionSuccess": true,
    "nReturned": 100,
    "executionTimeMillis": 4,
    "totalKeysExamined": 100,
    "totalDocsExamined": 100,
    "allPlansExecution": [
      {
        "nReturned": 100,
        "executionStages": {
          "stage": "FETCH",
          "nReturned": 100,
          "executionTimeMillisEstimate": 1,
          "works": 101,
          "advanced": 100,
          "needTime": 1,
          "docsExamined": 100,
          "inputStage": {
            "stage": "IXSCAN",
            "nReturned": 100,
            "works": 101,
            "keysExamined": 100
          }
        }
      }
    ]
  }
}
```
*   `works: 101`: The winning plan performed 101 execution cycles to return 100 documents, meaning it had almost zero overhead.
*   `keysExamined: 100` and `docsExamined: 100` matched `nReturned: 100`. This is the ideal **Index Selectivity Ratio (1:1:1)**.
*   `rejectedPlans`: The planner rejected the plan using index `status_1` because it lacked the `orderDate` sort field, which forced a `SORT` stage (in-memory sort).

---

### 4.3 In-Memory Sort Execution Trace Analysis
If the query planner cannot find an index that matches the requested sort order, it must perform an **in-memory sort** (`SORT` stage).

```
               [Fetch Documents from Disk]
                           │
                           ▼
              [Allocate Memory Buffer (RAM)]
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼ (Exceeds 32MB limit)
  [Document Fits in RAM]       [Operation Aborted]
   (Sorted in memory)      (Throws error code 292)
```

#### The 32MB RAM Sorting Limit:
*   **Mechanics**: MongoDB allocates an in-memory buffer to sort documents. This buffer is strictly limited to **32 megabytes** of RAM per query.
*   **The Error**: If the accumulated size of documents entering the `SORT` stage exceeds 32MB before sorting is complete, the query aborts and throws an exception:
    `Executor error during find command :: caused by :: WriteConflictException` or `Executor error during find command :: caused by :: Sort operation used more than the maximum 33554432 bytes of RAM.`
*   **The Workaround (and its cost)**: You can allow the query engine to use temporary files on disk by specifying `allowDiskUse` on the query cursor. However, sorting on disk is up to **100x slower** due to disk IO overhead.
*   **The Correct Fix**: Create a compound index matching the query filters and sort patterns using the **ESR rule**.

---

## 5. Practical Examples

### Creating and Analyzing ESR Compound Indexes
```javascript
// Correct ESR Compound Index
db.orders.createIndex({ status: 1, orderDate: -1, amount: 1 });

// Run explain plan to verify index usage
db.orders.find({
  status: "COMPLETED",
  amount: { $gt: 50.00 }
}).sort({ orderDate: -1 }).explain("executionStats");
```

### Reviewing explain() output:
*   Verify `stage` is `IXSCAN` followed by `FETCH`.
*   Ensure there is no `SORT` or `COLLSCAN` stage in the output.

---

### Production Operations: Rolling Index Rebuild Script
Building or rebuilding large indexes on collections with millions of records can saturate disk IOPS and CPU, degrading performance. The following Bash script demonstrates how to execute a rolling index rebuild across a 3-node replica set.

```bash
#!/usr/bin/env bash
# Production Rolling Index Rebuild Script
# Warning: Ensure backup and validation before running.

MONGO_HOSTS=("mongo-secondary1.prod:27017" "mongo-secondary2.prod:27017" "mongo-primary.prod:27017")
DB_NAME="ecommerce"
COLL_NAME="orders"
INDEX_NAME="status_1_orderDate_-1_amount_1"
INDEX_SPEC='{ "status": 1, "orderDate": -1, "amount": 1 }'

rebuild_index_standalone() {
  local node=$1
  echo "====== Rebuilding index on Node: $node ======"

  # 1. Connect and check status
  echo "Checking replica set node state..."
  local is_master=$(mongosh --host "$node" --quiet --eval "db.isMaster().ismaster")
  
  if [ "$is_master" = "true" ]; then
    echo "ERROR: Node $node is the current PRIMARY. Step down first!"
    exit 1
  fi

  # 2. Restart mongod in Standalone Mode
  echo "Stopping mongod service on $node..."
  # (Simulated OS commands for reference - systemctl stop mongod)
  
  echo "Starting mongod as standalone on port 27018..."
  # (mongod --port 27018 --dbpath /var/lib/mongodb)

  # 3. Drop and recreate index in standalone mode
  echo "Dropping and recreating index..."
  mongosh --port 27018 "$DB_NAME" --eval "
    db.${COLL_NAME}.dropIndex('${INDEX_NAME}');
    db.${COLL_NAME}.createIndex(${INDEX_SPEC});
  "

  # 4. Restart node in Replica Set Mode
  echo "Restarting mongod back into replica set mode on port 27017..."
  # (systemctl start mongod)

  echo "Waiting for node to catch up and state to show SECONDARY..."
  # Poll rs.status() until node returns to SECONDARY state
}

# Run on secondaries first
rebuild_index_standalone "${MONGO_HOSTS[0]}"
rebuild_index_standalone "${MONGO_HOSTS[1]}"

# Finally, step down primary and run on the old primary
echo "====== Stepping down Primary ======"
mongosh --host "${MONGO_HOSTS[2]}" "$DB_NAME" --eval "rs.stepDown(60)"

# Wait for a secondary to be elected primary
sleep 15

# Rebuild index on the old primary (now secondary)
rebuild_index_standalone "${MONGO_HOSTS[2]}"

echo "Rolling index rebuild complete across all nodes!"
```

---

## 6. Trade-offs & Alternatives

| Index Type | Read Performance | Write Overhead | Memory Footprint | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Single-Field Index** | **High**: Fast searches on a single property. | **Low**: Minor overhead during document updates. | **Small**: Minimal B-Tree footprint. | Simple lookup queries. |
| **Compound Index** | **Maximum**: Fast search and sorting on multiple fields. | **Medium**: Requires updates when any indexed field changes. | **Medium**: Larger footprint, key compression helps. | Multi-field filters and sorted queries. |
| **Multikey Index (Array)** | **High**: Fast searches within arrays. | **High**: Generates index entries for every array element. | **Large**: B-Tree footprint increases with array size. | Searching tags, category arrays. |
| **Wildcard Index** | **Medium**: Flexible index matching. | **Very High**: MongoDB must index all dynamic subfields. | **Large**: Virtual compound index footprint. | Dynamic user attribute fields, custom forms. |

---

## 7. Common Mistakes & Anti-patterns
*   **Index Intersection Fallacy**: Relying on the query planner to combine two separate indexes (e.g., `{ status: 1 }` and `{ userId: 1 }`). A compound index `{ userId: 1, status: 1 }` is almost always faster because it avoids the overhead of merging index pointer lists in memory.
*   **Over-indexing**: Indexing every field in a collection. This increases write latency, consumes WiredTiger cache memory, and can lead to index page swapping if the total index size exceeds available RAM.
*   **Wrong Sort Key Order**: Ordering compound index keys as `{ sortField: 1, equalityField: 1 }`, which violates the ESR rule and forces in-memory sorting.

---

## 8. Hands-on Exercises
1.  Insert 100,000 documents with random order amounts and statuses.
2.  Run a query that filters by status and sorts by amount, and check the explain plan. Notice the `SORT` stage.
3.  Create an ESR index: `{ status: 1, amount: 1 }` and rerun the query. Verify that the `SORT` stage is replaced by an `IXSCAN` and `FETCH`.
4.  Write a script to trigger the 32MB limit error. Verify the error code, and resolve it by adding a proper compound index.

---

## 9. Interview Questions

### Q1: Why does a range filter on a compound index key prevent subsequent keys in the index from being used for sorting?
**Answer**: A B-Tree index maintains keys in strict sorted order. In a compound index like `{ age: 1, name: 1 }`, the index is sorted by `age` first, and then by `name` *within each specific age group*. If your query requests a range of ages (e.g. `age: { $gt: 20 }`) and sorts by `name`, the index entries for different ages are interleaved. Since the index is not sorted by name globally across different ages, the database cannot use the index to sort the results, forcing an in-memory `SORT` stage.

### Q2: How do you safely build a 10GB index in a production replica set without service interruption?
**Answer**: Even though MongoDB's hybrid index builds are non-blocking, building a 10GB index consumes significant CPU, disk IOPS, and RAM, which can degrade performance. The safest approach is a rolling index build:
1.  Temporarily stop a secondary node, restart it as a standalone instance on a different port, and build the index.
2.  Once complete, restart the node as a replica secondary, allow it to catch up on replication, and repeat for the other secondaries.
3.  Force the primary to step down, wait for a secondary to be elected primary, and build the index on the old primary using the same process.

### Q3: What is index selectivity, and how does it relate to key cardinality?
**Answer**: Index selectivity refers to the index's ability to narrow down the scanned dataset. High cardinality fields (like unique emails or UUIDs) are highly selective because each index search returns a single document. Low cardinality fields (like gender or status) have low selectivity because a search on "ACTIVE" returns thousands of documents, forcing the query engine to scan many index keys. Senior engineers design compound indexes by ordering high-cardinality keys first to minimize the keys scanned.

---

---

---

## 10. Production Runbook & Deployment Guidelines

### 1. Rolling Index Creation Runbook
Never run foreground index builds on active production replica sets. Instead, execute the rolling index build sequence:
1. Identify target node as secondary: `rs.status()`
2. Restart secondary in standalone mode on port 27018.
3. Build the index on standalone: `db.orders.createIndex({ status: 1, orderDate: -1 })`
4. Restart node back into replica set mode.
5. Repeat for remaining secondaries.
6. Step down the primary node, wait for election, and rebuild the index on the old primary.

### 2. Verifying Index Memory Usage
Check if the indexes fit entirely in RAM to prevent disk swapping:
```javascript
db.orders.stats().indexSizes;
```
Compare the total index size to the allocated WiredTiger cache size. If index sizes exceed 60% of the cache, scale memory resources or drop unused indexes.

## 11. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Index Key Size Limit Exceeded (Code 17282)
*   **Failure Mode**: Trying to index fields containing values larger than **1024 bytes** fails, blocking writes.
*   **Resolution**: Hash large values before indexing, or use partial index configurations to filter out large values.

### 2. In-Memory Sort Overflow (Code 292)
*   **Failure Mode**: Queries requesting sorting on unindexed fields throw an exception if the document set exceeds **32MB** in size.
*   **Resolution**: Build a compound index matching the query filters and sort patterns following the ESR rule.

### 3. Index Page Fragmentation
*   **Failure Mode**: High delete volumes leave empty slots in B-Tree leaves, increasing index size and search times.
*   **Resolution**: Execute rolling index rebuilds on secondary nodes during off-peak hours.

---

## 12. Summary
Optimizing query performance requires understanding how B-Trees, page layouts, and the query planner work. By applying the ESR rule, checking explain plans for `IXSCAN` and `totalKeysExamined` metrics, and using rolling index builds, senior engineers ensure low query latency in production environments.

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
$$	ext{Index Keys} = 10 	imes 20 = 200 	ext{ index entries}$$
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

---

## 13. Hands-on Lab Exercise: Writing an Index Performance Benchmarker

### 1. Objective and Scenario
Compare write and read throughput metrics under various index architectures. You will write a script to evaluate query times and insertion rates on a collection when single, compound, or no indexes are present.

### 2. Code Implementation: `index-benchmark.js`
Create a file named `index-benchmark.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function runBenchmark() {
  const client = new MongoClient("mongodb://localhost:27017");
  try {
    await client.connect();
    const db = client.db("benchmark_db");
    const col = db.collection("logs");
    
    await col.drop().catch(() => {});
    
    // 1. Measure insertion time without secondary indexes
    let start = Date.now();
    const batch = [];
    for (let i = 0; i < 5000; i++) {
      batch.push({ code: i, tag: "TAG_" + (i % 10), createdAt: new Date() });
    }
    await col.insertMany(batch);
    console.log(`Inserted 5000 docs (No Index) in: ${Date.now() - start} ms`);
    
    // 2. Measure read time (unindexed collection scan)
    start = Date.now();
    const items = await col.find({ tag: "TAG_5" }).toArray();
    console.log(`Read ${items.length} records (COLLSCAN) in: ${Date.now() - start} ms`);
    
    // 3. Add Compound Index
    console.log("Creating compound index...");
    await col.createIndex({ tag: 1, code: 1 });
    
    // 4. Measure read time (index scan)
    start = Date.now();
    const indexedItems = await col.find({ tag: "TAG_5" }).toArray();
    console.log(`Read ${indexedItems.length} records (IXSCAN) in: ${Date.now() - start} ms`);
    
  } finally {
    await client.close();
  }
}
runBenchmark();
```

### 3. Lab Verification Steps
1.  Execute the benchmark script:
    ```bash
    node index-benchmark.js
    ```
2.  Note the performance difference between index reads and collections scan reads.

---

## 14. Index Maintenance & Performance Tuning Reference

### 1. Key Index Configurations
Manage index settings to reduce storage footprint:
*   `background`: Builds the index in the background to prevent blocking database operations (deprecated since version 4.2).
*   `partialFilterExpression`: Indexes documents matching specific criteria to optimize space.
*   `expireAfterSeconds`: Configures TTL indexes to automatically delete documents after a duration.

### 2. Operational Diagnostic Commands
Audit index utilization statistics:
```javascript
// Retrieve usage frequencies for all indexes on a collection
db.collection.aggregate([{ $indexStats: {} }]);

// Retrieve disk usage sizes for indexes
db.collection.stats().indexSizes;
```

### 3. Senior Engineer's Production Checklist
*   [ ] Drop unused indexes identified using `$indexStats` to reduce write amplification and reclaim memory.
*   [ ] Create partial indexes on sparse fields to optimize index size.
*   [ ] Ensure index sizes fit entirely within the allocated WiredTiger cache.

---

## 15. Special Collections & Advanced Storage Engines (Capped & GridFS)

### 1. Capped Collections and Cursors
Capped collections are fixed-size, circular queues that overwrite the oldest document when they run out of space.
*   **Restricted Writes**: Documents cannot be deleted, and updates that increase the BSON document size are rejected.
*   **Creation syntax**:
    ```javascript
    db.createCollection("audit_logs", { capped: true, size: 5242880, max: 10000 });
    ```
*   **Tailable Cursors**: Keep a cursor open after query execution ends. As new documents are written, the cursor consumes them. Use `cursorType: TAILABLE_AWAIT` to listen for events in queueing applications.

### 2. GridFS Binary Data Storage Architecture
When storing binaries exceeding the 16MB limit, GridFS splits files into chunks (default 255KB) and stores them in two collections:
*   `fs.files`: Groups file metadata:
    ```javascript
    {
      "_id": ObjectId("..."),
      "length": NumberLong(12589000),
      "chunkSize": 261120, // 255KB
      "uploadDate": ISODate("2026-06-12T07:15:00Z"),
      "filename": "manual.pdf",
      "md5": "e2c3b88..."
    }
    ```
*   `fs.chunks`: Stores binary pieces linked by `files_id`:
    ```javascript
    {
      "_id": ObjectId("..."),
      "files_id": ObjectId("..."), // References fs.files._id
      "n": 0,                      // Sequence sequence offset
      "data": BinData(0, "...")    // Binary payload
    }
    ```
GridFS uses two secondary indexes to optimize reads: `{ files_id: 1, n: 1 }` on `fs.chunks` and `{ filename: 1, uploadDate: 1 }` on `fs.files`.

### 3. TTL (Time-To-Live) Index Execution
TTL indexes age out documents after a duration. A background thread runs every 60 seconds to delete expired documents:
```javascript
db.sessions.createIndex({ lastUpdated: 1 }, { expireAfterSeconds: 86400 });
```
*   **Limits**: TTL indexes cannot be compound, and they cannot be built on capped collections.
