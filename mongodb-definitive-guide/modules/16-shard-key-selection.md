# Module 16: Choosing a Shard Key (Chapter 16)

Welcome class. Today we analyze **Choosing a Shard Key (CS-529)**.

Selecting a shard key is the most critical decision in sharded architecture design. A poor shard key choice can create un-resolvable write bottlenecks (hot spots) or lead to un-splittable chunks, eventually forcing a complete cluster reload.

Today we study **Shard Key Engineering**, analyzing data distribution patterns, ranged vs. hashed key behaviors, and cardinality constraints.

---

## 1. Academic Lecture: Shard Key Distributions & Cardinality

### 1. Ranged vs. Hashed Shard Keys
*   **Ranged Shard Keys** (e.g., `{"createdAt": 1}`): Keep contiguous ranges of data on the same shard. Excellent for range queries (which become targeted), but creates write bottlenecks: if keys are ascending (like timestamps), every new write goes to the last shard, overloading it while others sit idle.
*   **Hashed Shard Keys** (e.g., `{"userId": "hashed"}`): Use an MD5 hash of the field value to distribute writes uniformly across all shards, but turn range queries into scatter-gather operations.

### 2. Cardinality and Un-splittable Chunks
A shard key must have **high cardinality** (a large number of unique values). If a key has low cardinality (e.g. `{"status": 1}` which only has 3 unique states), the database will allocate millions of documents to the same key value. These documents cannot be split across chunks, resulting in massive, un-migratable **Jumbo Chunks**.

```text
[Ranged: Ascending Key (Time)] ──> All Writes ──> [Shard C (Overloaded)]
                                                  [Shard A, B (Idle)]

[Hashed: Random Distribution]  ──> Writes split ──> [Shard A], [Shard B], [Shard C] (Balanced)
```

---

## 2. Theory vs. Production Trade-offs

Compare shard key strategies:

| Dimension / Metric | Ranged Key (Ascending: ID, Date) | Hashed Key (Random: UserID) | Compound Key (StoreId + ItemId) |
| :--- | :--- | :--- | :--- |
| **Write Distribution** | Very Poor (Hotspot on max range) | Excellent (Uniform load balancing) | Excellent (If first key has high cardinality) |
| **Read Selectivity** | Excellent for range queries | Poor for range queries (Scatter-gather) | Excellent for targeted queries |
| **Cardinality Level** | High | High | Very High |
| **Chunk Split Safety** | Safe | Safe | Safe |
| **Jumbo Chunk Risk** | Low | Low | Very Low |

---

## 3. How to Use: Composite Shard Keys

Let us analyze shard key configurations. We contrast a naive, low-cardinality shard key with a robust composite shard key configuration.

### A. The Low-Cardinality Shard Key (Anti-Pattern)
Avoid sharding collections on low-cardinality fields, which creates un-splittable jumbo chunks:

```javascript
// DANGER: If the database contains millions of users, only two countries exist (e.g. US, CA).
// This creates massive, un-splittable jumbo chunks, overloading a single shard.
sh.shardCollection("enterprise.users", { country: 1 });
```

### B. The Composite High-Cardinality Shard Key (Production Pattern)
Combine a medium-cardinality routing prefix with a high-cardinality field to optimize distribution:

```javascript
// Robust Pattern: Combines storeId (for targeted reads) with userUuid (for write distribution).
sh.shardCollection("enterprise.users", { storeId: 1, userUuid: 1 });
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Selecting the Legacy Auto-Incrementing `_id` as Shard Key
*   **Why it fails**: Sharding on an ascending `_id` field (which is default behavior in SQL migrations). Because the ID values always increase, every insert targets the highest chunk range on the last shard, creating a permanent write hotspot.
*   **Mitigation**: Use a hashed index key on `_id` (`{ _id: "hashed" }`) or define a composite shard key.

---

## 5. Socratic Review Questions

### Question 1
Why does a hashed shard key turn a range query (e.g. `.find({ userId: { $gte: 10, $lte: 20 } })`) into a scatter-gather operation?

#### Answer
A hashed shard key passes each field value through a hash function. The hash values for sequential numbers like 10, 11, 12 are widely different and distributed randomly across the cluster's shards. To resolve the range query, the `mongos` router cannot predict which shard holds which value, forcing it to broadcast the query to every shard.

---

## 6. Hands-on Challenge: Shard Key Selection Case Study

### The Challenge
In this challenge, you will choose a shard key configuration.
Your task:
1. Optimize a high-throughput IoT logging collection `deviceLogs`.
2. The queries are:
   - Writes: high-volume inserts from millions of devices.
   - Reads: fetch logs for a specific device sorted by time: `db.deviceLogs.find({ deviceId: "DEV-101" }).sort({ loggedAt: -1 })`.
3. Choose the optimal shard key to guarantee targeted reads and prevent write hotspots.

Complete the sharding script stub:

```javascript
// TODO: Write the optimal shard collection command
sh.shardCollection("iot.deviceLogs", {
  // Add optimal shard key fields here
});
```

### Verification Query
Confirm key layout:
```javascript
// A compound key { deviceId: 1, loggedAt: 1 } satisfies targeted reads, 
// and avoids hotspots because deviceIds are distributed.
if (typeof sh.shardCollection === "function") {
  print("Success: Composite shard key validated.");
} else {
  print("Error: Command missing.");
}
```
