# Module 05: Aggregation Pipeline Optimization

## 1. What Problem This Module Solves
While aggregation pipelines are highly flexible, complex data transformations can run slowly if stages are ordered inefficiently. Placing stages in the wrong order can bypass indexes, exceed the 100MB RAM limit per stage, and trigger disk spooling. 

A senior engineer must understand the aggregation optimizer's internal rewrite rules, memory management, how to optimize joins (`$lookup`), how to design parallel queries (`$facet`), and how to analyze execution explain plans. Neglecting these details can result in query latency spikes, high CPU usage, and out-of-memory errors in high-throughput production environments.

---

## 2. Why This Topic Matters
A poorly designed aggregation pipeline can lock database threads and exhaust memory resources. For example, sorting documents after a projection stage forces an in-memory sort because the index is lost. Similarly, using `$lookup` on large unindexed collections can degrade database performance to a crawl.

Understanding optimization mechanics, such as projection pushdown, stage coalescence, and how to analyze aggregation explain plans, helps engineers design performant, memory-efficient data processing systems that run efficiently at scale.

---

## 3. Core Concepts & Internals

### 3.1 The Aggregation Optimizer Engine & Optimization Rewrites
Before executing a pipeline, MongoDB's optimizer rewrites it to improve execution efficiency.

```
       [User Pipeline Input]
                 │
                 ▼
       [Optimizer Analysis]
                 ├───────────────────────────────┐
                 ▼ (Stage Coalescence)           ▼ (Match Pushdown)
       [Combine Sort + Limit]          [Push Match before Project]
                 │                               │
                 ├───────────────────────────────┘
                 ▼ (Lookup + Unwind Coalescence)
       [Fuse Lookup and Unwind]
                 │
                 ▼ (Projection Pushdown)
       [Exclude Unused Fields]
                 │
                 ▼
                     [Optimized Execution Plan]
```

#### Optimization Rules:
*   **`$match` Coalescence**: Multiple consecutive `$match` stages are combined into a single `$match` stage using `$and` operators.
*   **`$match` Pushdown**: If a `$match` follows a `$project` stage, the optimizer pushes the `$match` *before* the `$project` stage. This allows the query engine to filter documents using indexes. Note that this only works if the `$match` does not filter on fields computed in the `$project` stage.
*   **`$sort` + `$limit` Coalescence**: If a `$limit` stage follows a `$sort`, the optimizer combines them into a single Top-N sort stage. Rather than sorting the entire dataset in memory, it maintains only the top $N$ elements in memory, reducing the RAM footprint.
*   **`$lookup` and `$unwind` Coalescence**: If an `$unwind` stage immediately follows a `$lookup` on the joined field, the optimizer fuses them together. Instead of building a temporary array of joined documents in memory and then flattening them, the `$lookup` streams documents directly to the output, saving memory allocation overhead.
*   **Projection Pushdown**: The optimizer analyzes the fields needed in later stages (e.g. `$group`, `$sort`) and automatically projects *only* those fields from disk. This reduces the size of documents processed in memory and minimizes disk read overhead.

---

### 3.2 Stage-by-Stage Memory Management & Spooling
*   **100MB RAM Constraint**: By default, each stage in an aggregation pipeline is limited to **100 megabytes** of RAM. If a stage exceeds this limit, the query aborts and throws an exception.
*   **`allowDiskUse: true`**: When enabled, memory-intensive stages (such as `$group` or `$sort`) can write temporary files to the `_tmp` directory on disk.
    *   *Performance Cost*: Writing to disk is up to **100x slower** than running in RAM. Avoid relying on `allowDiskUse` for active online API routes; reserve it for offline batch ETL processes.
*   **Pipeline Streaming**: Pipeline stages that process documents one-by-one (like `$match`, `$project`, or `$unwind`) stream documents continuously without buffering the entire dataset in memory, meaning they do not count against the 100MB stage limit. Blocking stages (like `$sort` or `$group`) must buffer documents in memory, making them the primary source of memory violations.

---

### 3.3 `$lookup` Join Internals & Optimization
The `$lookup` stage performs a left outer join.
*   **Nested Loop Join**: Under the hood, `$lookup` executes a nested loop. For every document entering the stage, MongoDB runs a query against the target collection.
*   **The Index Requirement**: To prevent $O(N \times M)$ scans, you **must** create an index on the joined collection's matching field (the `foreignField`). Without this index, every join operation triggers a full table scan of the target collection.
*   **Subquery Aggregation Pipelines**: You can run complex joins using variables (`let`) and a sub-pipeline (`pipeline`), allowing you to filter and shape joined documents before returning them.

---

### 3.4 `$facet` Parallel Execution Constraints
The `$facet` stage runs multiple aggregation pipelines in parallel on the same input dataset.
*   **Memory Footprint**: Every pipeline defined inside `$facet` operates on a copy of the input documents in memory.
*   **RAM Gotcha**: `$facet` stages are limited to the 100MB RAM threshold and **cannot** use `allowDiskUse`. If the combined data in your facets exceeds 100MB, the query will fail.

---

## 4. Query Planner explain() Analysis for Aggregations
To understand how the optimizer structures a pipeline, you must run and inspect its explain plan:
```javascript
db.orders.explain("executionStats").aggregate([
  { $match: { status: "PROCESSING" } },
  { $sort: { orderDate: -1 } },
  { $project: { userId: 1, amount: 1 } }
]);
```

### Annotated Explain Output Excerpt:
```json
{
  "stages": [
    {
      "$cursor": {
        "queryPlanner": {
          "plannerVersion": 1,
          "namespace": "ecommerce.orders",
          "winningPlan": {
            "stage": "FETCH",
            "inputStage": {
              "stage": "IXSCAN",
              "keyPattern": { "status": 1, "orderDate": -1 },
              "indexName": "status_1_orderDate_-1"
            }
          }
        },
        "executionStats": {
          "nReturned": 5000,
          "executionTimeMillis": 12,
          "totalKeysExamined": 5000,
          "totalDocsExamined": 5000
        }
      }
    },
    {
      "$project": {
        "userId": true,
        "amount": true,
        "_id": false
      }
    }
  ]
}
```

#### Key Takeaways from the Explain Output:
1.  **Cursor Stage (`$cursor`)**: The optimizer combined the `$match` and `$sort` stages into the initial database read cursor. This allows MongoDB to execute the filter and sort directly in the storage engine using the index (`status_1_orderDate_-1`).
2.  **No Separate Sort Stage**: Since the index matched the sort order, there is no explicit `$sort` stage in the explain output. The sort was handled by the index scan (`IXSCAN`).
3.  **Project Stage (`$project`)**: The `$project` stage runs after the database read cursor, projecting only the `userId` and `amount` fields.

---

## 5. Practical Examples

### Optimized Lookup with Sub-Pipelines & Index Matching
Given `orders` and `products` collections, join them to retrieve only active items costing over $100:
```javascript
db.orders.aggregate([
  { $match: { status: "PROCESSING" } },
  {
    $lookup: {
      from: "products",
      let: { order_item_id: "$productId" }, // Pass variable from orders
      pipeline: [
        {
          $match: {
            $expr: {
              $and: [
                { $eq: ["$_id", "$$order_item_id"] }, // Match variables
                { $eq: ["$status", "ACTIVE"] },
                { $gt: ["$price", 100.00] }
              ]
            }
          }
        },
        // Optimize: project only required fields inside lookup
        { $project: { name: 1, price: 1 } }
      ],
      as: "productDetails"
    }
  }
]);
```
*   *Index Requirement*: Ensure you have a compound index on the `products` collection: `{ _id: 1, status: 1, price: 1 }`.

---

### Window Functions ($setWindowFields) & Boundary Frames
Window functions let you run calculations across a span of documents (a "window") without collapsing them into a single output, unlike `$group`.

```
                    Input Documents Stream
    ┌─────────────────┬─────────────────┬─────────────────┐
    │  Doc 1 (100.00) │  Doc 2 (150.00) │  Doc 3 (200.00) │
    └────────┬────────┴────────┬────────┴────────┬────────┴
             │                 │                 │
             ▼                 ▼                 ▼
        [Window 1]        [Window 2]        [Window 3]
       (Doc 1 only)     (Doc 1 + Doc 2)   (Doc 2 + Doc 3)
             │                 │                 │
             ▼                 ▼                 ▼
      Avg: 100.00       Avg: 125.00       Avg: 175.00
```

#### Boundary Frame Modes:
1.  **Documents Mode (`documents`)**: Specifies window boundaries relative to the position of the current document in the stream (e.g. the 2 preceding documents to the current document).
2.  **Range Mode (`range`)**: Specifies window boundaries relative to the value of the sorting key in the current document (e.g. transaction dates within 3 days of the current document's date).

#### Example: Rolling Average Sales and Cumulative Totals
```javascript
db.sales.aggregate([
  {
    $setWindowFields: {
      partitionBy: "$storeId",
      sortBy: { date: 1 },
      output: {
        rollingAverageSales: {
          $avg: "$amount",
          window: {
            range: [-3, "current"], // 3 days ago to current document date
            unit: "day"
          }
        },
        cumulativeTotalSales: {
          $sum: "$amount",
          window: {
            documents: ["unbounded", "current"] // From the beginning of partition to the current document
          }
        }
      }
    }
  }
]);
```

#### Performance Considerations:
*   Sorting is required inside `$setWindowFields` to define the document order. Ensure the sort field (`date` in this case) is backed by an index.
*   Memory usage increases with the size of the window frame. Large partitions or using `unbounded` boundaries can consume significant memory, so design your partitions carefully.

---

## 6. Trade-offs & Alternatives

| Approach | Performance | Implementation Complexity | Data Freshness | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **On-the-Fly Aggregation** | **Medium to Low**: Runs calculations on every query; CPU and memory consumption scales with dataset size. | **Low**: Simple to write and deploy. | **Real-time**: Always processes current data. | Ad-hoc reporting, search filters, low-volume analytics. |
| **Materialized Views (`$merge`)** | **High**: Queries read pre-calculated results from a physical collection. | **Medium**: Requires running update jobs on a schedule. | **Eventual Consistency**: Data is updated periodically. | Business intelligence dashboards, complex reports. |
| **On-Demand Computations (Computed Pattern)** | **Maximum**: Precalculates values during write operations and stores them in the document. | **High**: Requires updates to application write logic. | **Real-time**: Fields are kept in sync during writes. | Counters, average reviews, sum of order amounts. |

---

## 7. Common Mistakes & Anti-patterns
*   **Sorting After Grouping on Unindexed Fields**: Placing a `$sort` stage after a `$group` stage on a computed field. Since the computed field is not indexed, this forces an in-memory sort.
*   **Projecting Out Index Keys Before Sorting**: Placing a `$project` stage before a `$sort` stage. This discards the index metadata, preventing MongoDB from using index-based sorting. Always place the `$sort` stage before the `$project` stage.
*   **Unindexed `$lookup`**: Executing joins where the target collection lacks an index on the join key. This forces a full collection scan (`COLLSCAN`) for every document processed, degrading performance.

---

## 8. Hands-on Exercises
1.  Insert 50,000 sales transactions across 5 different stores.
2.  Write an aggregation query that uses `$explain: true` to view the optimized pipeline stages. Observe how the engine rewrites or merges stages.
3.  Write a script to trigger a 100MB memory violation in an aggregation query, then resolve it using `allowDiskUse`.
4.  Design an aggregation pipeline using `$facet` to categorize user data by status and registration year in a single query.

---

## 9. Mini-Project: Real-Time Analytics Materialized Views
**Scenario**: Optimize a dashboard API that loads user engagement metrics.

Instead of recalculating total likes and views on every API request, build an aggregation pipeline that runs every 10 minutes and writes the precomputed results to a `dashboard_metrics` collection using `$merge`.

### Complete Materialized View Scheduler Script (Node.js)
```javascript
/**
 * Production-ready Materialized View Update Worker
 * Schedules and updates aggregated dashboard metrics.
 */
const { MongoClient } = require('mongodb');
const log = require('console');

async function updateMaterializedView(uri) {
  const client = new MongoClient(uri, { maxPoolSize: 5 });
  try {
    await client.connect();
    const db = client.db('ecommerce_db');
    const activities = db.collection('user_activities');

    log.info("Starting materialized view aggregation...");
    const startTime = Date.now();

    await activities.aggregate([
      {
        $group: {
          _id: { userId: "$userId", month: { $month: "$createdAt" } },
          totalLikes: { $sum: "$likes" },
          totalViews: { $sum: "$views" },
          lastActive: { $max: "$createdAt" }
        }
      },
      {
        $project: {
          _id: 0,
          userId: "$_id.userId",
          month: "$_id.month",
          totalLikes: 1,
          totalViews: 1,
          lastActive: 1
        }
      },
      {
        // Merge results into a materialized view collection
        $merge: {
          into: "dashboard_metrics",
          on: ["userId", "month"], // Must match a unique index on dashboard_metrics
          whenMatched: "replace",
          whenNotMatched: "insert"
        }
      }
    ]).toArray(); // Force pipeline execution

    const duration = Date.now() - startTime;
    log.info(`Materialized view successfully updated in ${duration}ms.`);
  } catch (error) {
    log.error(`Materialized view aggregation failed: ${error.message}`);
  } finally {
    await client.close();
  }
}

// Scheduled loop running every 10 minutes
const MONGO_URI = "mongodb://localhost:27017/ecommerce_db";
log.info("Scheduler started. Materialized view updates scheduled for every 10 minutes.");
setInterval(() => {
  updateMaterializedView(MONGO_URI);
}, 10 * 60 * 1000);
```

---

## 10. Interview Questions

### Q1: What optimizations does the MongoDB aggregation engine perform automatically when a pipeline contains `$match`, `$sort`, and `$project` stages?
**Answer**: The engine performs several optimizations:
1.  **Stage Coalescence**: If `$match` stages are consecutive, they are merged. If `$limit` follows `$sort`, they are merged into a top-N sort.
2.  **Match Pushdown**: If a `$match` follows a `$project`, the optimizer pushes the `$match` before the `$project` so it can filter documents using indexes (provided the match does not query computed fields).
3.  **Projection Pushdown**: The optimizer analyzes the fields needed in later stages and projects only those fields from disk, saving memory and disk IOPS.

### Q2: Why is `$lookup` performance sensitive to index designs? How do you resolve this?
**Answer**: Under the hood, `$lookup` executes a nested loop join: for every document entering the stage, MongoDB runs a lookup query against the target collection. If the target collection does not have an index on the join field (the `foreignField`), every document triggers a full collection scan (`COLLSCAN`), causing CPU usage to spike. You resolve this by ensuring a compound index exists on the joined collection covering the join keys and any filter parameters used in the sub-pipeline.

### Q3: What is the risk of using the `$unwind` stage on large arrays in high-concurrency environments?
**Answer**: The `$unwind` stage deconstructs an array field from input documents and outputs a new document for each element in the array. If a document has an array with 10,000 items, `$unwind` generates 10,000 documents in memory. In high-concurrency environments, running `$unwind` on large arrays can quickly consume available RAM, trigger memory allocation delays, and cause the aggregation query to exceed the 100MB stage limit.

---

---

---

## 11. Production Runbook & Deployment Guidelines

### 1. Aggregation Memory Allocations Tuning
If analytics reports throw memory errors, enable disk utilization for the pipeline:
```javascript
db.orders.aggregate(pipeline, { allowDiskUse: true });
```
*Warning*: Disk spooling is up to 100x slower. Optimize memory usage by:
* Placing `$match` and `$sort` stages at the very beginning of the pipeline.
* Using `$project` to exclude unused fields early in the stream, minimizing document sizes.

### 2. Monitoring Materialized View Refresh Jobs
Ensure materialized view merge operations complete successfully:
```javascript
db.getSiblingDB("config").changelog.find({ what: "merge" }).sort({ time: -1 }).limit(10);
```

## 12. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Facet Memory Overflow (Code 40300)
*   **Failure Mode**: Pipelines using `$facet` fail if the combined size of all facets exceeds **100MB**, as `$facet` does not support `allowDiskUse`.
*   **Resolution**: Split complex facets into separate queries, or filter documents early using indexes before the facet stage.

### 2. Unindexed Join Scans during `$lookup`
*   **Failure Mode**: Running a `$lookup` join where the target collection lacks an index on the join key forces a full collection scan (`COLLSCAN`) for every document, causing CPU spikes.
*   **Resolution**: Ensure a compound index exists on the joined collection covering the join keys.

### 3. Merge Phase Write Conflicts
*   **Failure Mode**: Periodic materialized view updates using `$merge` fail due to write conflicts if other write operations modify target ranges concurrently.
*   **Resolution**: Schedule aggregation runs during off-peak hours, or run updates in batches using transaction retry locks.

---

## 13. Summary
Optimizing aggregation pipelines requires understanding engine rewrite rules and memory limits. By filtering early using indexes, placing sorting before projections, and ensuring joins are backed by indexes, senior engineers design performant, memory-efficient data processing systems.

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

---

## 13. Hands-on Lab Exercise: Custom Aggregation Pipeline Builder

### 1. Objective and Scenario
Design a pipeline verification class that intercepts database aggregation queries and checks if best practices (e.g. placing matching stages first and preventing projection blocks at inappropriate locations) are followed.

### 2. Code Implementation: `pipeline-validator.js`
Create a file named `pipeline-validator.js` and paste the following code:
```javascript
class PipelineValidator {
  constructor(pipeline) {
    this.pipeline = pipeline;
  }

  validate() {
    if (this.pipeline.length === 0) {
      throw new Error("Pipeline must contain at least one stage.");
    }

    const firstStage = Object.keys(this.pipeline[0])[0];
    if (firstStage !== "$match" && firstStage !== "$sort") {
      console.warn(`WARNING: First stage is '${firstStage}'. Placing '$match' first is recommended to optimize performance.`);
    }

    let hasLimitUse = false;
    this.pipeline.forEach((stage, idx) => {
      const stageName = Object.keys(stage)[0];
      if (stageName === "$project" && idx < this.pipeline.length - 1) {
        console.warn(`TIP: Stage ${idx} is '$project'. Ensure you aren't discarding variables required in subsequent calculations.`);
      }
    });

    return true;
  }
}

// Test validation
const badPipeline = [
  { $project: { name: 1, category: 1 } },
  { $match: { category: "FOOD" } }
];

const validator = new PipelineValidator(badPipeline);
validator.validate();
```

### 3. Lab Verification Steps
1.  Run the code:
    ```bash
    node pipeline-validator.js
    ```
2.  Verify the script prints warnings about suboptimal stage ordering.

---

## 14. Pipeline Profiling & Memory Management Reference

### 1. Key Aggregation Variables
Configure these limits to manage resources during complex computations:
*   `internalQueryExecMaxBlockingSortBytes`: Caps memory allocations during sort operations in aggregation pipelines (Default: 32MB).
*   `allowDiskUse`: Enables database stages to write temporary BSON files to disk when memory limits are exceeded.

### 2. Operational Diagnostic Commands
Inspect aggregation metrics:
```javascript
// Run explain plans on aggregation tasks to evaluate stages
db.orders.explain("executionStats").aggregate(pipeline);

// Check current aggregation workers running on the instance
db.currentOp({ "command.aggregate": { $exists: true } });
```

### 3. Senior Engineer's Production Checklist
*   [ ] Ensure `$match` and `$sort` stages are placed at the very beginning of the pipeline to leverage indexes.
*   [ ] Minimize BSON document footprint early in pipelines using `$project` blocks to select only required fields.
*   [ ] Avoid `$facet` stages on large collections because it executes in-memory and does not support disk spooling.
