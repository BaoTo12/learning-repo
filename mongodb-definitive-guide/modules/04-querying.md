# Module 04: Querying (Chapter 4)

Welcome class. Today we analyze **Querying (CS-529)**.

Designing efficient query paths in document databases requires matching nested records without traversing unnecessary paths. Because MongoDB documents represent data trees, queries can target flat fields, arrays, or deep nested subdocuments.

Today we study **BSON Query Resolution**, analyzing search operators, array query limits, cursor paginations, and projection mechanics.

---

## 1. Academic Lecture: The Query Engine & Cursor Paging

### 1. Element Matching and Projections
When MongoDB resolves a query, it filters documents and passes them to the **Projection** engine. Projections (`{ name: 1, _id: 0 }`) reduce network and memory overhead by preventing the database from sending unused fields back to the client application.

### 2. Cursor Mechanics & Batching
*   **The Cursor**: When a query returns matches, MongoDB does not load all documents into memory. Instead, it opens a server-side cursor.
*   **Batch Fetching**: The driver client pulls records in batches (typically 101 documents in the first batch, then 4MB batches). If a cursor is held open on the server without activity for more than 10 minutes, the server terminates it to release thread resources.

```text
[Client App] ────────── Query ───────────> [MongoDB Engine]
             <───── First 101 Docs ──────  (Open Cursor)
[Process Docs]
             ────────── getMore ─────────> [Cursor fetch next batch]
```

---

## 2. Theory vs. Production Trade-offs

Compare retrieval strategies for large datasets:

| Dimension / Metric | Offset-Based Paging (`skip` / `limit`) | Keyset-Based Paging (Range Queries) |
| :--- | :--- | :--- |
| **Execution Performance** | Declines under high skip pages | Stable (O(log N) index boundary search) |
| **Index Dependency** | High (Requires index to avoid colscan) | High (Requires sorted index field) |
| **Real-time Safety** | Vulnerable to duplicate/skipped elements | Resilient (Pagination tied to fixed key value) |
| **Query Complexity** | Simple (`.skip(1000).limit(50)`) | Moderate (Requires passing last key state) |
| **Resource Footprint** | High (Server scans skipped documents) | Low (Direct cursor positioning) |

---

## 3. How to Use: Strict Array Matching

Let us write complex array queries. We contrast standard array queries (which match elements loosely across array elements) with the strict `$elemMatch` constraint.

### A. The Loose Array Query (Anti-Pattern)
Avoid querying arrays without `$elemMatch` if you need multiple criteria to be satisfied by the **same** array element:

```javascript
// DANGER: This query matches documents where ANY subdocument has score >= 90
// AND ANY subdocument (not necessarily the same one) has type == "exam".
db.registrations.find({
  "grades.score": { $gte: 90 },
  "grades.type": "exam"
});
```

### B. The Strict Element Match Query (Production Pattern)
Use `$elemMatch` to guarantee that a single array element satisfies all conditions:

```javascript
// Robust Pattern: Asserts that at least one array element contains BOTH exam and score >= 90.
db.registrations.find({
  grades: {
    $elemMatch: { type: "exam", score: { $gte: 90 } }
  }
});
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Skip-Based Performance Degradation
*   **Why it fails**: Using `.skip(10000).limit(10)` to paginate search results. To skip 10,000 documents, the database must retrieve them from disk and count them, parsing their BSON headers. This creates high CPU utilization.
*   **Mitigation**: Implement Keyset Paging. Filter on a unique sorted ID (e.g. `_id: { $gt: lastSeenId }`) and limit the query.

---

## 5. Socratic Review Questions

### Question 1
Why does querying an array of documents using an exact subdocument match (e.g., `db.users.find({ address: { street: "Main", zip: 123 } })`) depend on the key order of the subdocument?

#### Answer
BSON is a binary byte format. When you perform an exact subdocument match, MongoDB does byte-for-byte comparison of the serialized BSON subdocument. Since BSON maps dictionary entries in order, `{ street: "Main", zip: 123 }` generates different bytes than `{ zip: 123, street: "Main" }`. To avoid this, always query specific fields using dot notation: `db.users.find({ "address.street": "Main", "address.zip": 123 })`.

---

## 6. Hands-on Challenge: Cursor Paging Query Implementation

### The Challenge
In this challenge, you will implement keyset paging.
Your task:
1. Write a query function `fetchNextPage` in JavaScript.
2. The function takes `lastId` (ObjectId) and `pageSize` (number).
3. Query the `orders` collection, returning documents where `_id` is greater than `lastId`, sorted by `_id` ascending, limited to `pageSize`.
4. Restrict the projection to exclude `internalMetadata`.

Complete the implementation stub below:

```javascript
function fetchNextPage(lastId, pageSize) {
  // TODO: Implement keyset query page
  return db.orders.find(
    // query, projection, sort, limit
  );
}
```

### Verification Query
Run page transition check:
```javascript
const cursor = fetchNextPage(ObjectId("60c72b2f9b1d8b2c8c8b4567"), 5);
const resultList = cursor.toArray();

if (resultList.length <= 5 && resultList.every(doc => !doc.hasOwnProperty("internalMetadata"))) {
  print("Success: Keyset page resolved with correct limits and projections.");
} else {
  print("Error: Keyset page formatting failed.");
}
```
