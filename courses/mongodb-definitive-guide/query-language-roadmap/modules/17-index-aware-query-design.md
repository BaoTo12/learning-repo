# Module 17: Index-Aware Query Design

In this module, we will study index-aware query design in MongoDB using MongoDB Compass. Standard read operations can become bottlenecked by scanning entire collections. You will learn why indexes matter, how query execution stages are represented in explain plans (`COLLSCAN`, `IXSCAN`, `PROJECTION_COVERED`), how to define indexes visually using the MongoDB Compass Indexes UI, and strategies to optimize queries and avoid index-breaking patterns.

---

## 1. Why Indexes Matter

Without indexes, MongoDB must perform a **Collection Scan** (`COLLSCAN`), loading and reading every document in a collection from disk or memory cache to evaluate match criteria. As datasets grow to millions of rows, search times increase linearly ($O(N)$), saturating database CPU and disk I/O.

MongoDB uses **B-Tree Indexes** to organize and sort field keys. B-Tree structures allow the database engine to search for records in logarithmic time ($O(\log N)$) by navigating sorted nodes. 

### The Write Cost Trade-off:
Indexes dramatically speed up read queries, but they add overhead to write operations. Every insert, update, or delete requires the database to update the corresponding entries in the B-Tree index structure. Avoid indexing every field; configure indexes selectively based on query patterns.

---

## 2. Managing Indexes in MongoDB Compass

MongoDB Compass provides a dedicated **Indexes** tab to create, analyze, and drop indexes.

### Creating an Index:
1.  Navigate to the collection in MongoDB Compass.
2.  Click the **Indexes** tab.
3.  Click the **Create Index** button.
4.  Specify the fields and index type (e.g. `1` for Ascending, `-1` for Descending, or `text`).
5.  (Optional) Expand the options panel to configure advanced settings like `Unique`, `Sparse`, `Partial Filter Expression`, or `Expire after (seconds)` (TTL).
6.  Click **Create Index**.

---

## 3. Query Execution Stages (Explain Plans)

To audit a query's performance, use the **Explain Plan** tab in MongoDB Compass:
1.  Go to the **Documents** tab.
2.  Configure your **Filter**, **Sort**, **Project**, **Limit**, or **Skip** in the query bar.
3.  Switch to the **Explain Plan** tab (located next to the Documents tab).
4.  Click the **Explain** button.
5.  Observe the execution stages:

### A. Collection Scan (`COLLSCAN`)
*   **Description**: The database engine reads every document in the collection.
*   **Visual Stage**: `COLLSCAN`
*   **Systems Impact**: High CPU and high disk read IO. Avoid this in high-traffic production paths.

### B. Index Scan (`IXSCAN`)
*   **Description**: The engine scans the sorted keys inside a B-Tree index to locate document identifiers (RecordIDs).
*   **Visual Stage**: `IXSCAN` followed by a `FETCH` stage to load the matched documents from data pages.
*   **Systems Impact**: Highly efficient. Only a subset of index nodes is read.

### C. Covered Queries (`PROJECTION_COVERED`)
*   **Description**: The index contains all fields requested by both the filter and the projection. The engine returns results directly from the index in RAM without loading documents from disk or cache.
*   **Visual Stage**: `PROJECTION_COVERED` (or `IXSCAN` directly returning fields with `Documents Examined: 0`).
*   **Systems Impact**: The absolute fastest read operation possible.

---

## 4. Advanced Index Reference

### A. Compound Indexes & The ESR Rule
#### Description
An index covering multiple fields. The key ordering is critical. Arrange fields in this order to maximize index selectivity:
1.  **E**quality: Fields checked for exact equality (e.g. `status = "ACTIVE"`).
2.  **S**ort: Fields used to order results (e.g. `sort({ createdAt: -1 })`).
3.  **R**ange: Fields queried with range operators (e.g. `price > 50`).

#### Compass Setup Example
*   **Indexes Tab Setup**: Add fields `"status": 1`, `"age": 1`, and `"score": 1` in order.
*   **Documents Filter**: `{ "status": "ACTIVE", "score": { "$gt": 80 } }`
*   **Documents Sort**: `{ "age": 1 }`

---

### B. Multikey Indexes
#### Description
An index created on a field containing an array. MongoDB indexes each element in the array automatically.

#### Compass Setup Example
*   **Indexes Tab Setup**: Add field `"tags": 1`.
*   **Write Amplification**: If an array has 500 items, inserting a document creates 500 separate index entries in the B-Tree index, which slows down write operations.
*   **Compound Restriction**: You cannot create a compound index where **more than one** field is an array (e.g. indexing `{ "tags": 1, "colors": 1 }` is blocked if both are arrays).

---

### C. Text Indexes
#### Description
A tokenized index that supports full-text search strings, ignoring stop-words and applying stemming.

#### Compass Setup Example
*   **Indexes Tab Setup**: Add field `"title": "text"`, and optional `"description": "text"`.
*   **Limit**: Max of one text index per collection.
*   **Storage Cost**: Highly intensive, consuming significant disk space and RAM.

---

### D. Sparse Indexes
#### Description
Indexes only documents that contain the indexed field. Documents missing the field are completely omitted from the index structure.

#### Compass Setup Example
*   **Indexes Tab Setup**: Add field `"graduationDate": 1`.
*   **Options Checkbox**: Check **Sparse**.
*   **Negation Limitation**: Queries looking for missing fields (`{ "graduationDate": { "$exists": false } }`) **cannot** use the sparse index and fall back to collection scans.

---

### E. Partial Indexes
#### Description
Indexes only documents that match a specified filter condition (`partialFilterExpression`). This is a modern, more powerful replacement for sparse indexes.

#### Compass Setup Example
*   **Indexes Tab Setup**: Add field `"email": 1`.
*   **Options JSON**: Paste into **Partial Filter Expression**:
    ```json
    { "status": "ACTIVE" }
    ```
*   **Query Compatibility**: To use the partial index, the query filter **must include** the partial filter condition (or a subset of it):
    *   *Index Used Filter*: `{ "email": "a@a.com", "status": "ACTIVE" }`
    *   *COLLSCAN Forced Filter*: `{ "email": "a@a.com" }` (because the planner cannot guarantee non-active records are excluded).

---

### F. TTL (Time-To-Live) Indexes
#### Description
Automatically expires and deletes documents from a collection after a specified number of seconds or at a specific date.

#### Compass Setup Example
*   **Indexes Tab Setup**: Add field `"createdAt": 1`.
*   **Options Field**: Enter `3600` in **Expire after (seconds)**.
*   **Behavior & Mechanics**: A background thread runs once every 60 seconds to locate and delete expired documents. Deletions are not real-time. The indexed field must contain a BSON Date or an array of Dates.

---

## 5. Query Analysis: Index Usage vs. Index Breaking

### A. Queries that USE Indexes:
*   **Prefix Regex Searches**: Regexes starting with a caret anchor (`/^admin/`) perform range scans.
*   **Equality / Range Comparisons**: `$eq`, `$gt`, `$gte`, `$lt`, `$lte`, `$in` queries.
*   **Aligned Compound Sorts**: Sorting directions that match the index key order (or its exact reverse).

---

### B. Queries that BREAK Index Usage (Forcing COLLSCAN):
1.  **Negations (`$ne`, `$nin`, `$nor`)**: Standard indexes index values, not their absence. Negating matches requires scanning the inverse of the target set.
2.  **Leading Wildcard Regexes (`/.*admin/` or `/admin/`)**: Substring matches cannot determine B-Tree search boundaries, forcing full index scans or collection scans.
3.  **Unindexed `$or` Clauses**: If a query contains `{ "$or": [ { "indexedField": 1 }, { "unindexedField": 2 } ] }`, MongoDB cannot use the index for the unindexed clause and runs a collection scan for the entire query.
4.  **Field Evaluations (`$expr`)**: Comparing two fields in the same document (e.g. `{ "$expr": { "$eq": ["$price", "$salePrice"] } }`) generally bypasses standard indexes and scans all documents.
5.  **Type Mismatches**: Querying a field with a different BSON type than what is stored in the index (e.g. querying `{ "age": "30" }` when the field is stored as an integer) blocks index scanning.

---

## 6. Query Optimization Strategies

*   **Align compound indexes with the ESR rule**: Place equality fields first, sort fields second, and range fields last in compound indexes.
*   **Verify with Explain plans**: Always run queries through the **Explain Plan** tab in Compass to verify that they perform index scans (`IXSCAN`) and that the ratio of **Documents Returned** to **Keys Examined** is close to `1`.
*   **Prune unused indexes**: Unused indexes slow down write operations and consume RAM. Navigate to the Indexes tab to review index size and drop unused ones.
