# Module 13: Aggregation Framework Fundamentals

In this module, we will explore the foundational concepts of the MongoDB Aggregation Framework using MongoDB Compass. Standard read filters retrieve documents matching static queries, but backend applications frequently require data transformation, multi-stage processing, and numerical calculations (like averages, sums, and groupings). You will learn why aggregation exists, how the pipeline execution model works, its memory constraints, and the architectural trade-offs between database-side and application-side data processing.

---

## 1. Why Aggregation Exists

Standard MQL query filters (such as the Filter bar in MongoDB Compass) are restricted to matching documents and returning either whole records or projected fields. They cannot perform operations like:
*   Calculating the sum or average of values across a collection.
*   Joining tables dynamically (analogous to SQL `LEFT JOIN`).
*   Restructuring BSON documents in multi-stage flows (e.g., unwinding array values into individual documents, calculating averages, and grouping them by category).

The **Aggregation Framework** is a powerful data-processing engine in MongoDB designed to perform complex analytics, transform document shapes, and calculate metrics directly on the database server.

---

## 2. The Aggregation Pipeline Concept

The core model of the Aggregation Framework is the **Pipeline**. An aggregation operation takes documents from a collection and passes them through a sequence of processing blocks called **Stages**.

```
[Input Collection] ➔ [Stage 1: $match] ➔ [Stage 2: $group] ➔ [Stage 3: $sort] ➔ [Output Documents]
```

### Pipelines in MongoDB Compass
In MongoDB Compass, you construct pipelines visually using the **Aggregation** tab.

*   **Stage-by-Stage Builder**: Click **Add Stage** to append a new stage.
*   **Stage Dropdown**: Select the stage operator (e.g. `$match`, `$group`, `$sort`).
*   **Stage Input Box**: Paste only the raw BSON query body for that specific stage.
*   **Live Preview**: Compass automatically executes the stage on a sample of documents and displays the transformed document shapes on the right.
*   **Non-Destructive**: Pipeline execution does not modify the original documents in the collection unless the pipeline ends with a write stage (like `$out` or `$merge`).

---

## 3. Pipeline Execution Model

### A. Stage-Level Execution
Each stage in the pipeline performs a specific transformation:
*   **Filters**: Stages like `$match` reduce the number of documents passing through.
*   **Reshapers**: Stages like `$project` and `$addFields` change the attributes in each document.
*   **Accumulators**: Stages like `$group` gather values from multiple documents and output summarized results.

---

### B. The 100MB Memory Limit Constraint
To prevent aggregation queries from starving the database engine of RAM, MongoDB imposes a strict constraint:

> [!WARNING]
> *   **The 100MB Limit**: If any single aggregation pipeline stage consumes more than **100MB of RAM** during execution, the query will immediately fail and throw a `QueryExceededMemoryLimitNoTailable` or `CommandFailed` error.
> *   **Risk Stages**: This limit is typically exceeded by blocking memory operations like `$sort` (when not backed by an index) and `$group` (when grouping millions of unique keys).

#### Configuring disk usage in MongoDB Compass
To execute large aggregation runs that exceed the 100MB threshold:
*   Click the **settings** (gear) icon in the top right of the Aggregation tab.
*   Check the box for **Allow Disk Use** (this corresponds to passing the options document `{ "allowDiskUse": true }` to the database).
*   **Mechanics**: When `allowDiskUse` is enabled, MongoDB spills temporary sorting and grouping data to files in the `_tmp` directory on disk, bypassing the 100MB RAM check. However, disk I/O significantly slows down execution speed.

---

### C. Pipeline Optimizations (Query Planner)
Before running the pipeline, the MongoDB Query Planner analyzes and optimizes the stage sequence:
*   **Match Pushdown**: If a `$match` stage is declared late in the pipeline, the planner attempts to push it to the very beginning. Filtering documents early reduces the number of records subsequent stages must process.
*   **Index Utilization**: The first stage in a pipeline can use collection indexes (e.g., running `$match` first allows index scans). Once a stage modifies the document structure (such as `$project` or `$group`), subsequent stages **cannot** use indexes on the original fields.
*   **Limit Coalescing**: If a `$sort` stage is followed immediately by a `$limit` stage, the query planner merges them into a top-K sort algorithm, avoiding sorting the entire dataset in memory.

---

## 4. Aggregation vs. Application Processing

When designing backend systems, you must choose whether to aggregate data on the database server or retrieve raw records and aggregate them in application memory (e.g., using Java streams or JavaScript loops).

### Comparison Matrix

| Resource | Database-Side Aggregation (MQL) | Application-Side Aggregation |
| :--- | :--- | :--- |
| **Network Bandwidth** | **Optimal**. Only the calculated summary payload is sent over the wire (e.g. returning a single count integer instead of 1,000,000 documents). | **Poor**. Transports massive BSON datasets from database to app client, saturating network ports. |
| **CPU Utilization** | High database CPU load. Can degrade database performance if queries run frequently. | Offloads CPU work to application servers, which can scale horizontally. |
| **Memory / RAM** | Utilizes database cache and temp files. Subject to the 100MB stage limit. | Consumes application heap space, which can trigger garbage collection (GC) pauses under heavy load. |
| **Index Advantage** | **High**. Pipeline start stages can use index keys to skip document scans entirely. | **None**. Application cannot utilize database indexes for calculations. |

### Architectural Guideline:
*   **Prefer Database Aggregation**: When querying large datasets where the aggregate result is a small fraction of the input size (e.g. sums, counts, averages, report charts).
*   **Prefer Application Aggregation**: When computing complex business rules on small, pre-filtered datasets, or when database CPU is the primary system bottleneck.
