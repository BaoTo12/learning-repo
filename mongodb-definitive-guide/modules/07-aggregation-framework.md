# Module 07: Introduction to the Aggregation Framework (Chapter 7)

Welcome class. Today we analyze **Introduction to the Aggregation Framework (CS-529)**.

When applications require data transformations, executing operations inside the client application is highly inefficient due to network transmission overhead. MongoDB's **Aggregation Framework** provides a declarative, multi-stage data processing pipeline running directly inside the storage engine, utilizing server-side index optimizations.

Today we study **Aggregation Pipeline Optimization**, mapping pipeline stages, analyzing memory constraint boundaries, and writing aggregation outputs to collections.

---

## 1. Academic Lecture: Aggregation Stages & Pipeline Optimization

### 1. Pipeline Stages & Streaming Execution
Aggregation runs documents through a sequence of processing blocks. Pipeline stages can be divided into:
*   **Streaming Stages**: Operators that process and output documents one by one (e.g. `$match`, `$project`, `$unwind`). These consume minimal memory.
*   **Blocking Stages**: Operators that must buffer all documents in memory before outputting results (e.g. `$sort`, `$group`). These have high memory footprints.

### 2. The 100MB RAM Boundary
To prevent runaway queries from crashing the database server, MongoDB restricts each aggregation stage execution memory limit to **100 Megabytes**. If a blocking stage (like `$group`) exceeds this limit, the query fails with a memory boundary exception.

```text
[Collection] ──> [ $match (Index) ] ──> [ $group (RAM Limit: 100MB) ] ──> [Output]
                                              │
                                              ▼ (If limit exceeded)
                                     [ OOM Error / Fallback to Disk ]
```

---

## 2. Theory vs. Production Trade-offs

Compare aggregation pipeline design options:

| Dimension / Metric | Client-Side Aggregation | Aggregation Pipeline (Standard) | Aggregation Pipeline (`allowDiskUse: true`) |
| :--- | :--- | :--- | :--- |
| **Network Overhead** | Extreme (All raw docs sent) | Low (Only aggregated results sent) | Low |
| **Memory Footprint** | App-server constrained | 100MB strict limit per stage | Unlimited (Uses external temp files) |
| **Database Server Load** | Very Low | Moderate | High (Requires disk I/O swapping) |
| **Index Execution** | Driver-side queries | Direct query planner index reuse | Direct query planner index reuse |
| **Latency Profile** | High | Low | Moderate to High (Disk swap delay) |

---

## 3. How to Use: Structuring Optimized Pipelines

Let us write aggregation queries. We contrast a sub-optimal pipeline design (which disables index usage by projecting fields too early) with the robust optimized aggregation pattern.

### A. Early Projection Optimization Bypass (Anti-Pattern)
Avoid executing `$project` before `$match` or `$sort`, which prevents the query engine from utilizing index structures:

```javascript
// DANGER: Placing $project before $match prevents the query planner from using 
// indexes on the matched field, forcing a full collection scan (COLLSCAN).
db.orders.aggregate([
  { $project: { storeId: 1, amount: 1 } },
  { $match: { storeId: "ST-88" } }
]);
```

### B. The Hardened Index-Aware Pipeline (Production Pattern)
Always position `$match` and `$sort` at the start of the pipeline stages to leverage index optimization:

```javascript
// Robust Pattern: Stage matching filters elements before projections happen.
db.orders.aggregate([
  { $match: { storeId: "ST-88" } },
  { $group: { _id: "$storeId", totalSales: { $sum: "$amount" } } }
]);
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Memory Limits on Unindexed `$group` Queries
*   **Why it fails**: Executing a `$group` on millions of documents with a high-cardinality key (e.g. grouping sales by customer email). If the grouped payload exceeds 100MB, the database raises an error.
*   **Mitigation**: Enable temporary disk write swaps by passing `{ allowDiskUse: true }` inside the aggregation options document parameters:
    `db.orders.aggregate([...], { allowDiskUse: true })`.

---

## 5. Socratic Review Questions

### Question 1
Why does placing a `$sort` stage immediately after a `$match` stage allow index reuse, but placing `$sort` after a `$project` stage forces an in-memory sort?

#### Answer
The database engine's query planner can match the `{ $match: ..., $sort: ... }` sequence directly to a compound index prefix structure, bypassing in-memory sorting entirely. Once a `$project` stage is executed, it transforms document fields and outputs new BSON streams. B-Tree indexes are linked to the raw collection, not the projected stream, rendering index structures unusable for downstream sorting stages.

---

## 6. Hands-on Challenge: High-Throughput Sales Analysis Pipeline

### The Challenge
In this challenge, you will implement an aggregation pipeline.
Your task:
1. Complete the pipeline to process the `sales` collection.
2. Steps:
   - Match sales where `category` is `"electronics"`.
   - Unwind the `items` array.
   - Group by `items.itemId` and calculate total quantities sold (`totalQty`).
   - Project results to contain only `itemId` and `totalQty`.
   - Limit outputs to the top 3 items.

Complete the implementation stub below:

```javascript
// TODO: Write aggregate query stages
db.sales.aggregate([
  // Add stages here
]);
```

### Verification Query
Validate the aggregation output format:
```javascript
const sampleResult = db.sales.aggregate([
  { $match: { category: "electronics" } },
  { $unwind: "$items" },
  { $group: { _id: "$items.itemId", totalQty: { $sum: "$items.qty" } } },
  { $project: { itemId: "$_id", totalQty: 1, _id: 0 } },
  { $sort: { totalQty: -1 } },
  { $limit: 3 }
]).toArray();

if (sampleResult.length <= 3 && sampleResult.every(r => r.hasOwnProperty("itemId") && r.hasOwnProperty("totalQty"))) {
  print("Success: Aggregation pipeline executed with correct transformations.");
} else {
  print("Error: Pipeline format execution error.");
}
```
