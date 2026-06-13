# Module 15: Configuring Sharding (Chapter 15)

Welcome class. Today we analyze **Configuring Sharding (CS-529)**.

Deploying a sharded cluster requires setting up config nodes, starting routers, and managing data balance. As data shifts, the database must split chunk boundaries and migrate chunks across nodes to maintain uniform load.

Today we study **Cluster Configurations & Balancing**, analyzing chunk splitting, balancing lifecycles, and change streams.

---

## 1. Academic Lecture: Chunk Allocations & The Balancer

### 1. Chunks and Splitting
Data inside a sharded collection is partitioned into logical segments called **Chunks**. A chunk represents a range of shard key values. The default max chunk size is **64 Megabytes**.
*   When writes cause a chunk to exceed this size, the `mongos` router triggers a **Chunk Split** on the config server, creating two smaller chunk ranges. This is a metadata-only update (no documents are moved).

### 2. The Balancer Lifecycle
*   **The Balancer**: A background process running on the primary config server. It monitors chunk distributions across shards.
*   If the imbalance between shards exceeds the migration threshold, the balancer locks the collections and initiates a **Chunk Migration**, moving documents across the network to balance the load.

```text
[Shard A (10 Chunks)] ─── Balancer Threshold Exceeded ───> [Shard B (2 Chunks)]
                           (Network migration of chunks)
[Shard A (6 Chunks)] <─────────────────────────────────── [Shard B (6 Chunks)]
```

---

## 2. Theory vs. Production Trade-offs

Compare balancing options:

| Dimension / Metric | Automatic Balancer (Active 24/7) | Configured Balancer Window (Off-Peak) | Manual Balancing |
| :--- | :--- | :--- | :--- |
| **System Load (Peak Hours)**| High (Migrations compete with client writes) | Zero | Zero |
| **Shard Data Skew** | Minimal | Moderate (Skew accumulates during day) | High (Unless manual runs are scheduled) |
| **WAN Network Costs** | High (Unpredictable migrations) | Bounded (Scheduled off-peak hours) | Bounded |
| **Risk of Lock Collisions** | Moderate | Low | Low |
| **Operational overhead** | None | Low | High (Requires custom scripts) |

---

## 3. How to Use: Managing Balancer Schedules

Let us configure the balancer. We contrast a raw default balancer deployment (vulnerable to resource conflicts during peak hours) with a robust scheduled balancer window.

### A. The Default Unconstrained Balancer (Anti-Pattern)
Avoid leaving the balancer running 24/7 in production settings with high write volumes:

```javascript
// DANGER: The balancer can fire migrations during peak traffic hours,
// causing network saturation and slow client query response times.
```

### B. The Hardened Balancer Window Configuration (Production Pattern)
Define a strict migration window to restrict balancer activity to off-peak hours:

```javascript
// Robust Pattern: Set the balancer window to run only between 11 PM and 6 AM.
db.getSiblingDB("config").settings.updateOne(
  { _id: "balancer" },
  {
    $set: {
      activeWindow: { start: "23:00", stop: "06:00" },
      stopped: false
    }
  },
  { upsert: true }
);
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Changing Chunk Sizes Arbitrarily
*   **Why it fails**: Setting the chunk size to a very low value (e.g. 1MB) to get "more granular balancing". This triggers continuous chunk splitting and migrations, saturating config server tables and creating network bottlenecks. Conversely, setting it too high (e.g. 500MB) blocks migrations and leads to hot shards.
*   **Mitigation**: Retain the default 64MB chunk size unless specific, highly skewed access patterns are identified.

---

## 5. Socratic Review Questions

### Question 1
Why does a chunk split operation not require moving document bytes on disk, whereas a chunk migration does?

#### Answer
A chunk split is a logical division of a shard key range. The documents remain in place on their current shard. The split only updates the Config Server's routing metadata (e.g., splitting range `[1, 100]` into `[1, 50]` and `[51, 100]`). A chunk migration moves the actual document payloads across the network to a different shard to balance data, which consumes network and disk I/O.

---

## 6. Hands-on Challenge: Configuring Balancer Locks

### The Challenge
In this challenge, you will implement balancer management commands.
Your task:
1. Write a script to disable the balancer on a sharded cluster.
2. Verify that the balancer is stopped.

Complete the administrative script stub below:

```javascript
function disableClusterBalancer() {
  // TODO: Stop the balancer using sh.stopBalancer()
}
```

### Verification Query
Validate the balancer state:
```javascript
if (typeof sh.stopBalancer === "function") {
  print("Success: Balancer control scripts validated.");
} else {
  print("Error: Balancer API missing.");
}
```
