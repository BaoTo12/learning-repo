# Module 03: Creating, Updating, and Deleting Documents (Chapter 3)

Welcome class. Today we analyze **Creating, Updating, and Deleting Documents (CS-529)**.

In document-oriented storage engines, updates are not merely tabular replacements. Since records can contain arrays and nested documents, updates can mutate document sizes, causing the storage engine to relocate documents on disk.

Today we study **Atomic Data Modifications**, mapping the update operations of MongoDB, analyzing atomic updates, array operators, positional identifiers, and write performance boundaries.

---

## 1. Academic Lecture: Document Relocation & Atomic Updates

### 1. The Cost of Document Growth
When a document's size exceeds its allocated block size in storage (due to pushing elements into an array or adding fields), the **WiredTiger** engine must write the updated document to a new disk block and update all indexing pointers. This is a heavy write penalty.

### 2. Atomic Modifiers vs. Replacement Updates
*   **Replacement Update**: Rewriting the entire document. This raises concurrency issues (race conditions) if multiple processes update different fields at the same time.
*   **Atomic Modifiers**: Targeting specific key paths (`$set`, `$inc`, `$push`, `$pull`). MongoDB locks the document and executes the operation atomically, preventing write conflicts.

```text
               ┌─── [Client A: $set: { status: "Active" }] ───┐
               │                                              ▼
[Original Document] ───> [Atomic Lock & Modification] ───> [Updated Document]
               ▲                                              ▲
               └─── [Client B: $inc: { loginCount: 1 }] ──────┘
```

---

## 2. Theory vs. Production Trade-offs

Compare update patterns inside the database engine:

| Dimension / Metric | Replacement Update (`replaceOne`) | Atomic Modifier (`updateOne` with `$set`) |
| :--- | :--- | :--- |
| **Concurrency Safety** | Low (Vulnerable to dirty overrides) | High (Atomic modification on field-level) |
| **Network Payload** | High (Entire document sent) | Low (Only modification payload sent) |
| **Disk Write Overhead** | High (Complete block write) | Variable (Only updates modified fields) |
| **Index Updates** | Re-builds index keys | Re-builds only modified index keys |
| **Upsert Capability** | Replaces default object | Appends dynamic modifiers |

---

## 3. How to Use: Advanced Array Operations

Let us write BSON array update operations. We contrast a naive positional update (which only updates the first matched item) with the robust positional filtered array update syntax.

### A. The Naive First-Match Positional Update (Anti-Pattern)
Avoid using the basic `$` positional operator when you need to match and update multiple specific nested items in an array:

```javascript
// DANGER: The "$" positional operator only updates the FIRST matched element in the array.
// Subsequent matching elements are left unchanged.
db.grades.updateOne(
  { _id: 1, "scores.grade": 80 },
  { $set: { "scores.$.status": "Passed" } }
);
```

### B. The Hardened Positional Filtered Update (Production Pattern)
Use `arrayFilters` to target and modify specific array elements matching precise criteria:

```javascript
// Robust Pattern: $[elem] matches all elements satisfying scoresFiltered filter.
db.grades.updateOne(
  { _id: 1 },
  { $set: { "scores.$[elem].status": "Passed" } },
  { arrayFilters: [{ "elem.grade": { $gte: 80 } }] }
);
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Unbounded Array Growth
*   **Why it fails**: Appending data endlessly to a document array (e.g. logging user activity clicks inside a `User` document using `$push`). Documents have a hard limit of **16 Megabytes**. As the array grows to thousands of elements, query speeds decay, eventually raising a document size validation error.
*   **Mitigation**: Use the "Bucket Pattern" to split arrays across documents when they exceed a threshold, or store logs in a separate collection.

---

## 5. Socratic Review Questions

### Question 1
What is the difference in locking behavior between `db.collection.updateMany()` and multiple single `db.collection.updateOne()` operations?

#### Answer
`updateMany()` executes within a single database operation context, acquiring locks on affected documents as it processes them, but yielding periodically to allow other read/write clients to execute. Spawning multiple separate `updateOne()` queries from client drivers incurs network transport latency between writes, increasing the risk of phantom reads and data inconsistencies.

---

## 6. Hands-on Challenge: Positional Nested Array Update

### The Challenge
In this challenge, you will implement a nested array update.
Your task:
1. Write a query to update `students` collection.
2. The collection document schema has a nested array `courses` which contains `{ code: "CS-101", enrolled: true }`.
3. Set `enrolled` to `false` for all courses where `code` is `"CS-101"`.

Complete the implementation stub below:

```javascript
// TODO: Write the updateMany query with arrayFilters
db.students.updateMany(
  {},
  // Add update modifier and arrayFilters here
);
```

### Verification Query
Run the check script:
```javascript
const doc = db.students.findOne({ "courses.code": "CS-101" });
const allCS101Unenrolled = doc.courses
  .filter(c => c.code === "CS-101")
  .every(c => c.enrolled === false);

if (allCS101Unenrolled) {
  print("Success: Filtered nested array elements modified correctly.");
} else {
  print("Error: Positional update failed.");
}
```
