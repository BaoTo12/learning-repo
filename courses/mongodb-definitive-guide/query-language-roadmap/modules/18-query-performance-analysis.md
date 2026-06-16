# Module 18: Query Performance Analysis

In this module, we will explore query performance tuning in MongoDB using MongoDB Compass. High-performance backend applications must monitor, analyze, and optimize database read and write latency. You will learn how to generate and read Explain Plans visually, interpret query planner caching, analyze low-level execution statistics fields (`works`, `advanced`, `needTime`, `needYield`), audit slow queries using the Database Profiler, and apply systems-level optimizations to aggregation pipelines.

---

## 1. Explain Plans & Planner Mechanics in MongoDB Compass

MongoDB Compass provides an **Explain Plan** tab to inspect how the query planner processes a query.

### A. How to Generate an Explain Plan
1.  Navigate to the **Documents** tab and enter your **Filter**, **Sort**, **Project**, **Limit**, or **Skip** parameters.
2.  Switch to the **Explain Plan** tab.
3.  Click the **Explain** button.
4.  To inspect the detailed JSON response (including raw stats), toggle the **Raw JSON** view switch in the top right of the explain panel.

---

### B. The Plan Cache Mechanics

To avoid the CPU overhead of evaluating execution plans for every single query, MongoDB utilizes the **Plan Cache**:

1.  **Plan Selection Phase**: When a query occurs that does not have a cached plan, the query planner compiles a list of candidate indexes. It runs these candidate plans in parallel for a trial period (a specific number of iteration works).
2.  **Winning Plan Selection**: The plan that performs the trial work fastest is selected as the **Winning Plan** and saved in the Plan Cache, mapped to the query's shape (the set of fields queried). Other candidate plans are saved as **Rejected Plans**.
3.  **Cache Reuse**: Subsequent queries of the same shape bypass the selection phase and reuse the winning plan directly.
4.  **Rebuild Triggers**: The planner evicts cached plans and rebuilds the plan cache when:
    *   An index is created or dropped.
    *   The database is restarted.
    *   10 write operations occur on the collection (which could significantly alter index selectivity).

---

## 2. Low-Level Execution Statistics Reference

When viewing the **Raw JSON** of an Explain Plan in Compass, the `"executionStats"` document contains nested BSON counters. Understanding these internal metrics is essential for diagnosing low-level driver bottlenecks.

### Core Execution Counter Metrics:
*   **`works`**: The total number of internal query execution units performed by the stage. A work unit represents a single cycle of the query engine (e.g. evaluating a key, checking a filter, or fetching a document).
*   **`advanced`**: The number of documents or index keys returned (advanced) by this stage to its parent stage in the execution tree.
*   **`needTime`**: The number of work cycles spent performing internal processing where no document was advanced (e.g. scanning an index key that is discarded by filter bounds).
*   **`needYield`**: The number of times this stage suspended its execution to yield its storage locks, allowing other write operations to execute.
*   **`saveState` / `restoreState`**: The number of times the stage saved its execution position before yielding locks, and restored its position afterward.
*   **`isEOF`**: Indicates whether the stage has reached the end of the matching stream (`1` for true, `0` for false).

---

## 3. Query Execution Stages

The output of an explain plan is organized as an execution tree of stages:

| Stage Name | Description | Performance Recommendation |
| :--- | :--- | :--- |
| **`COLLSCAN`** | Collection Scan. Reads every document in the collection from storage. | **Critical Warning**. Always create indexes to avoid COLLSCAN in production. |
| **`IXSCAN`** | Index Scan. Scans the sorted B-Tree index keys. | Optimal. Ensure range scans match selective indexes. |
| **`FETCH`** | Loads document payloads from storage files using RecordIDs from an `IXSCAN`. | Expected when returning fields not covered by the index. |
| **`PROJECTION_COVERED`** | Covered Query. The query was satisfied entirely from index keys. | Maximum performance. totalDocsExamined must be `0`. |
| **`SORT`** | Performs in-memory sorting of documents. | **High Risk**. Subject to the 100MB aggregation / 32MB read limit. Index the sort fields. |
| **`SORT_KEY_GENERATOR`** | Computes sorting keys for documents prior to running a `SORT` stage. | Indicates an in-memory sort is occurring. |
| **`LIMIT`** | Restricts the number of documents returned. | Improves performance when placed directly after `$sort`. |
| **`SKIP`** | Bypasses the first N matching documents. | High overhead for deep skips. Avoid offset pagination. |
| **`OR`** | Combines index range scans from multiple `$or` clauses. | Ensure all clauses in the `$or` filter are indexed. |
| **`AND_ENTRIES`** | Performs index intersection to combine multiple index scans. | Usually slower than compound indexes. Prefer compound index design. |

---

## 4. Tracing Slow Queries: Database Profiler

To audit queries executing in production, configure the **Database Profiler** to write operations to the `system.profile` capped collection.

### Profiling Levels:
*   `0`: Profiling is disabled (off).
*   `1`: Logs operations that exceed the `slowms` execution threshold.
*   `2`: Logs all operations. **Warning**: Writing every query to disk adds severe CPU overhead and will degrade database performance under heavy loads. Never use level 2 in production.

### Configuration Command
To configure database profiling via the embedded MongoDB Shell at the bottom of the Compass window, run:
```json
{
  "profile": 1,
  "slowms": 50,
  "sampleRate": 0.5
}
```

#### Querying the Profile Collection in Compass
Open the `system.profile` collection under your database and configure the query options:
*   **Filter**: `{ "millis": { "$gt": 100 } }`
*   **Sort**: `{ "ts": -1 }`
*   **Limit**: `5`

---

## 5. Aggregation Pipeline Optimizations

Before running an aggregation pipeline, the query optimizer restructures the stages to maximize execution speed:

### A. Match Pushdown Optimization
If a `$match` stage is declared after a projection, the query planner attempts to push it to the very beginning of the pipeline:
```
// Original Pipeline:
[ $project ] ➔ [ $match ]

// Optimized Execution:
[ $match ] ➔ [ $project ]
```
*   *Systems Benefit*: Reduces the number of BSON documents that need to be parsed and transformed in memory.

### B. Projection Pruning (Field Exclusion)
The query planner scans subsequent stages and automatically drops fields from the document stream as early as possible if they are not referenced in downstream stages:
*   *Systems Benefit*: Minimizes the memory footprint of documents in transit.

### C. Sort + Limit Coalescing
If a `$sort` stage is followed directly by a `$limit` stage, the query planner merges them:
*   *Systems Benefit*: Instead of sorting the entire dataset in memory, the engine runs a top-K heap sort algorithm, keeping only the top N elements in memory, which avoids memory overhead.
