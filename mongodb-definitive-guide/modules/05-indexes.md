# Module 05: Indexes (Chapter 5)

Welcome class. Today we analyze **Indexes (CS-529)**.

Indexing is the primary mechanism for avoiding resource-heavy collection scans (`COLLSCAN`). When a query filters or sorts by fields without an index, the database engine must load and scan every document in the collection from disk, thrashing memory caches.

Today we study **B-Tree Indexes**, analyzing single-field, compound, and multikey index structures, examining index key prefixes, and validating query execution statistics.

---

## 1. Academic Lecture: Index Search Bounds & Prefix Matches

### 1. B-Tree Compound Indexing
MongoDB uses B-Tree indexes. When you construct a compound index like `db.collection.createIndex({ age: 1, name: 1 })`, the index tree is sorted first by `age` ascending, and then within identical ages by `name` ascending.

### 2. The Equality, Sort, Range (ESR) Rule
To optimize compound index query performance, index fields should be ordered following the **ESR Rule**:
1.  **Equality**: Fields queried with exact matches (e.g. `status: "active"`).
2.  **Sort**: Fields used to order query results (e.g. `sort({ createdAt: -1 })`).
3.  **Range**: Fields queried with range selectors (e.g. `age: { $gte: 21 }`).

```text
[Equality Matches] ───> [Sort Fields] ───> [Range Scans]
(Reduces key bounds)    (Avoids RAM sort)   (Bounds last leaf nodes)
```

---

## 2. Theory vs. Production Trade-offs

Compare index types and key structures:

| Dimension / Metric | Single-Field Index | Compound Index | Multikey Index (Arrays) |
| :--- | :--- | :--- | :--- |
| **Write Penalty** | Low | Moderate | High (Creates key entry per array item) |
| **RAM Footprint** | Low | Moderate | High |
| **RAM Sorting Prevention**| Only for single key matches | Prevents RAM sorts on compound prefix | Prevents RAM sorts on array elements |
| **Prefix Reusability** | None | Yes (Sub-prefixes can resolve queries) | None |
| **Explaining Path** | `IXSCAN` | `IXSCAN` | `IXSCAN` |

---

## 3. How to Use: Analyzing Explain Plans

Let us analyze compound indexes. We compare a sub-optimal index configuration (which forces an in-memory sort stage) with the ESR-compliant compound index pattern.

### A. The Wrong Compound Index Ordering (Anti-Pattern)
Avoid placing range queries before sort keys in compound index fields, which triggers in-memory sorting:

```javascript
// DANGER: Ordering index as { range, sort } forces the database engine to perform 
// an in-memory sort stage (indicated by "SORT" in explain plans) if query matches many records.
db.users.createIndex({ age: 1, username: 1 });
// Query:
db.users.find({ age: { $gte: 30 } }).sort({ username: 1 });
```

### B. The Hardened ESR-Compliant Compound Index (Production Pattern)
Order keys following ESR rules to ensure sorted ranges are traversed without database sorting stages:

```javascript
// Robust Pattern: Index is defined matching equality/sort parameters.
db.users.createIndex({ status: 1, username: 1, age: 1 });
// Query:
db.users.find({ status: "active", age: { $gte: 30 } }).sort({ username: 1 });
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Indexing High-Cardinality Arrays (Explosive Multikey Indexes)
*   **Why it fails**: Creating an index on an array field where each document contains hundreds of values. MongoDB creates index node pointer entries for **every element** in the array. This causes write speeds to drop, and the index size can quickly exceed the available WiredTiger memory cache.
*   **Mitigation**: Avoid indexing array fields that grow without bounds. If index queries on array elements are mandatory, use partial indexes to limit index keys to active documents.

---

## 5. Socratic Review Questions

### Question 1
Why does a query filtering on `{ age: 25 }` reuse the index `{ age: 1, name: 1 }`, but a query filtering on `{ name: "Bob" }` cannot reuse it?

#### Answer
MongoDB compound indexes are sorted from left to right. The index tree is organized starting with the first field (`age`). A query filtering by the second field (`name`) cannot navigate the tree root nodes without an initial `age` parameter. This is known as the **Prefix Rule**: compound indexes can only resolve queries that filter on a left-aligned prefix of indexed keys (e.g. `{ age: 1 }`).

---

## 6. Hands-on Challenge: ESR Index Engineering

### The Challenge
In this challenge, you will implement an index matching the ESR rule.
Your task:
1. Optimize this query: `db.orders.find({ storeId: "ST-88", amount: { $gt: 100 } }).sort({ orderDate: -1 })`.
2. Create the index on the `orders` collection that satisfies the ESR rule.
3. Ensure the explain plan shows zero `SORT` stages (using `executionStats` verification).

Complete the index creation stub below:

```javascript
// TODO: Create the optimal compound index
db.orders.createIndex({
  // Add keys here in correct order
});
```

### Verification Query
Confirm the execution plan states:
```javascript
const stats = db.orders.find({ storeId: "ST-88", amount: { $gt: 100 } })
  .sort({ orderDate: -1 })
  .explain("executionStats");

const hasMemorySort = stats.executionStats.executionStages.stage === "SORT" ||
  JSON.stringify(stats.executionStats).includes('"stage":"SORT"');

if (!hasMemorySort && stats.executionStats.totalKeysExamined > 0) {
  print("Success: Index configured correctly; no in-memory sorting required.");
} else {
  print("Error: Index is sub-optimal; SORT stage detected.");
}
```
