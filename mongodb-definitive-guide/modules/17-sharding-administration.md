# Module 17: Sharding Administration (Chapter 17)

Welcome class. Today we analyze **Sharding Administration (CS-529)**.

Administrative maintenance of a sharded cluster requires monitoring cluster status, managing chunk splits, diagnosing jumbo chunks, and regulating balancer locks to avoid resource exhaustion.

Today we study **Sharded Cluster Administration**, analyzing diagnostics tools (`sh.status()`), connection pool sizing, and chunk migration tuning.

---

## 1. Academic Lecture: Cluster Status & Jumbo Chunk Mitigation

### 1. Diagnosing Cluster Status
The command `sh.status()` returns the cluster's topology mapping, database sharding states, shard keys, and chunk distributions. An imbalance in chunk distribution indicates a stalled balancer.

### 2. Jumbo Chunks
When a chunk exceeds the maximum size limit (64MB) but cannot be split because all documents in it share the exact same shard key value, it is flagged as a **Jumbo Chunk**.
*   **The Problem**: The balancer cannot migrate jumbo chunks because their size exceeds transmission safety limits. The host shard becomes overloaded.
*   **Mitigation**: Split the chunk manually using `sh.splitFind()` or refine the shard key by adding a secondary field (shard key refinement).

```text
[Jumbo Chunk (120MB - Same Shard Key)] ──> Balancer rejects migration
                                                  │
                                                  ▼
                 [Refine Shard Key / Manual Split on Sub-Key]
                                                  │
                                                  ▼
[Split into 2 Chunks (60MB)] ──> Balancer migrates successfully
```

---

## 2. Theory vs. Production Trade-offs

Compare cluster maintenance strategies:

| Dimension / Metric | Automated Balancing | Manual Chunk Splitting | Shard Key Refinement |
| :--- | :--- | :--- | :--- |
| **Operational Effort** | None | High | Moderate |
| **System Resource Cost**| High (Constant checks) | Low | Low |
| **Permanent Resolution**| No (Symptoms only) | No | Yes (Solves root cardinality limits) |
| **Service Downtime** | Zero | Zero | Zero (Online operation in modern engines) |
| **Applicability** | General maintenance | Urgent hot-fix | System restructuring |

---

## 3. How to Use: Resolving Jumbo Chunks

Let us write administrative commands. We contrast an unmonitored cluster setup with a diagnostic sequence that identifies and splits jumbo chunks.

### A. The Unmonitored Cluster State (Anti-Pattern)
Avoid neglecting jumbo chunk warnings, which leads to skewed disk allocation:

```javascript
// DANGER: Letting jumbo chunks accumulate will lock data distribution,
// eventually running out of disk space on hot shards.
```

### B. The Hardened Diagnostic and Split Sequence (Production Pattern)
Locate the target collection and split the chunk range manually at a boundary:

```javascript
// Robust Pattern 1: Output cluster status details.
sh.status(true); // Verbose mode displays chunk details

// Robust Pattern 2: Manually split a jumbo chunk on a specific value.
sh.splitFind("enterprise.transactions", { userId: "USER-992", txnId: ObjectId("60c72b2f9b1d8b2c8c8b4567") });
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Executing Raw Collection Drops on Sharded Clusters
*   **Why it fails**: Running `db.collection.drop()` on a sharded collection directly through a shard connection, bypassing the `mongos` router. The collection is deleted on the shard, but the config servers still hold its chunk metadata. Future writes to that collection will route to dead ends, throwing execution errors.
*   **Mitigation**: Always execute collection drop commands through a connection to the `mongos` router.

---

## 5. Socratic Review Questions

### Question 1
Why does a sharded cluster require setting connection limits (`maxPoolSize`) on both the client application driver and the `mongos` routers?

#### Answer
Each `mongos` router routes client queries to shards, maintaining connection pools to every shard replica set node. If 10 client app servers open 100 connections each to `mongos`, the routers can spawn thousands of sockets to the shards, exhausting the shards' file descriptors. Restricting connection pool limits prevents resource starvation under load.

---

## 6. Hands-on Challenge: Diagnosing Chunk Distribution

### The Challenge
In this challenge, you will write a diagnostics script.
Your task:
1. Complete a function `findJumboChunks` that checks the config database.
2. Query the `config.chunks` collection where `jumbo` is `true`.
3. Output the collections that contain jumbo chunks.

Complete the implementation stub below:

```javascript
function getCollectionsWithJumboChunks() {
  const configDb = db.getSiblingDB("config");
  // TODO: Query configDb.chunks for jumbo: true
  // Return list of unique collection namespaces
  return [];
}
```

### Verification Query
Validate the config search:
```javascript
const list = getCollectionsWithJumboChunks();
if (Array.isArray(list)) {
  print("Success: Config databases scanned successfully.");
} else {
  print("Error: Query execution failed.");
}
```
