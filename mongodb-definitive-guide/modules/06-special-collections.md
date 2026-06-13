# Module 06: Special Index and Collection Types (Chapter 6)

Welcome class. Today we analyze **Special Index and Collection Types (CS-529)**.

Production database architectures frequently require handling data categories that do not fit standard B-Tree indexing rules—such as logging buffers, expiring credentials, geographical geometry matching, and multi-megabyte binary files.

Today we study **Specialized Storage Architectures**, analyzing Geospatial, Text, Capped, TTL indexes, and the binary file slicing mechanics of **GridFS**.

---

## 1. Academic Lecture: Specialized Index Types & GridFS Mechanics

### 1. Geospatial and TTL Indices
*   **2dsphere Geospatial Indexes**: Uses GeoJSON format coordinates to evaluate spherical geometry calculations.
*   **TTL (Time-To-Live) Indexes**: A background thread runs once every 60 seconds, evaluating documents against a specified age field and purging expired records.

### 2. GridFS Chunking Protocol
Documents in MongoDB cannot exceed 16MB. To store large files (like audio recordings or video files), MongoDB uses **GridFS**, which splits files into binary chunks across two collections:
*   `fs.files`: Stores metadata, checksums, and metadata fields.
*   `fs.chunks`: Stores raw binary chunks (default size is 255KB per document chunk).

```text
               ┌─── [chunk 0 (255KB)] ───> fs.chunks
[Large File] ──┼─── [chunk 1 (255KB)] ───> fs.chunks
               └─── [chunk 2 (140KB)] ───> fs.chunks
```

---

## 2. Theory vs. Production Trade-offs

Compare special collections capabilities:

| Dimension / Metric | Capped Collection | TTL Index Collection | GridFS Storage |
| :--- | :--- | :--- | :--- |
| **Write Strategy** | Circular FIFO Queue (O(1) updates) | Standard B-Tree inserts | Sliced chunk streams |
| **Document Deletion**| Prohibited (Auto-evicted on capacity) | Background thread purge | Manual chunk cleanups |
| **Size Constraint** | Hard limit (Bytes or Count) | Unconstrained | Unconstrained |
| **Index Overhead** | Low (Always sorted by insertion order) | Moderate | High (Chunk indexing) |
| **Query Support** | Tailable cursors supported | Standard query parameters | Metadata query only |

---

## 3. How to Use: Configuring TTL and Capped Buffers

Let us configure special indices. We contrast a volatile, unconstrained logging collection with a robust resource-bounded capped buffer and TTL deployment.

### A. The Volatile Log Collector (Anti-Pattern)
Avoid saving infinite log objects without bounds or expiry settings, which causes disk exhaustion:

```javascript
// DANGER: This collection will grow indefinitely, exhausting server disk space 
// and slowing down queries unless manual cron deletion tasks are configured.
db.systemLogs.insertOne({ timestamp: new Date(), message: "Service initiated" });
```

### B. The Hardened Capped & TTL Deployment (Production Pattern)
Define a bounded log collection and set strict document lifecycles:

```javascript
// Robust Pattern 1: Bounded logs to 10MB or max 10,000 documents.
db.createCollection("cappedSystemLogs", { capped: true, size: 10 * 1024 * 1024, max: 10000 });

// Robust Pattern 2: Expire session documents exactly 1 hour (3600 seconds) after createdAt time.
db.userSessions.createIndex({ createdAt: 1 }, { expireAfterSeconds: 3600 });
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Attempting to Resize Capped Collections Directly
*   **Why it fails**: When a capped collection hits capacity, attempting to alter size properties via update commands fails. Capped parameters are locked at storage allocations.
*   **Mitigation**: To resize, you must rename the collection, create a new capped collection with updated dimensions, copy the data over, and drop the legacy collection.

---

## 5. Socratic Review Questions

### Question 1
Why does setting a TTL index field to an array of dates result in unexpected document deletion behaviors?

#### Answer
If the indexed TTL field contains an array of dates, the background expiration thread evaluates all dates within the array. The document is purged when the **earliest** date within the array reaches its expiration threshold. To prevent premature deletions, keep TTL index targets mapped to single ISO Date fields.

---

## 6. Hands-on Challenge: Bounded Auditing Setup

### The Challenge
In this challenge, you will implement a capped audit trail.
Your task:
1. Create a capped collection named `auditTrail` bounded to a maximum of `500,000` bytes.
2. Build a TTL index on `auditTrail` on the `loggedAt` field to expire documents after `86400` seconds (24 hours).

Complete the commands stub below:

```javascript
// TODO: Create the capped collection
db.createCollection("auditTrail", {
  // Add capped params here
});

// TODO: Create the TTL index
db.auditTrail.createIndex(
  // Add field and expireAfterSeconds config here
);
```

### Verification Query
Verify the settings:
```javascript
const collStats = db.auditTrail.stats();
const indexInfo = db.auditTrail.getIndexes();

const isCapped = collStats.capped === true;
const hasTTL = indexInfo.some(idx => idx.hasOwnProperty("expireAfterSeconds") && idx.expireAfterSeconds === 86400);

if (isCapped && hasTTL) {
  print("Success: Bounded capped auditing log and TTL indexes created.");
} else {
  print("Error: Configuration mismatch.");
}
```
