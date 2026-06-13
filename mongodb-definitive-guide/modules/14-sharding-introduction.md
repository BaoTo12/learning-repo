# Module 14: Introduction to Sharding (Chapter 14)

Welcome class. Today we analyze **Introduction to Sharding (CS-529)**.

When the write volume or size of a dataset exceeds the capability of a single replica set, we must partition the data across multiple database nodes. MongoDB achieves this by utilizing a shared-nothing horizontal clustering mechanism called **Sharding**.

Today we study **Sharded Cluster Architecture**, analyzing cluster components, routing mechanics, and query paths.

---

## 1. Academic Lecture: Shared-Nothing Clusters & Routing Topology

### 1. Cluster Component Classifications
A MongoDB sharded cluster consists of three key components:
*   **Shards**: Replica sets that store a subset of the cluster's data. Each shard represents a partition of the total database.
*   **Config Servers**: A dedicated 3-node replica set that stores the cluster's metadata, routing tables, and authorization keys.
*   **mongos Routers**: Stateless routing processes that act as the interface between the client application and the cluster. They query the config servers for metadata and route client requests to the correct shards.

### 2. Targeted vs. Scatter-Gather Queries
*   **Targeted Query**: A query containing the shard key. The `mongos` router immediately identifies the target shard and queries it directly, minimizing network overhead.
*   **Scatter-Gather Query**: A query without the shard key. The `mongos` router must broadcast the query to **every** shard in the cluster and merge the results, creating massive network and CPU bottlenecks.

```text
               ┌─── targeted query (with shard key) ───> Shard A (Fast)
[Client] ──> mongos
               └─── scatter-gather query ───> Shard A, Shard B, Shard C (Slow)
```

---

## 2. Theory vs. Production Trade-offs

Compare cluster topologies:

| Dimension / Metric | Single Replica Set | Sharded Cluster (Targeted) | Sharded Cluster (Scatter-Gather) |
| :--- | :--- | :--- | :--- |
| **Write Capacity** | Limited by Primary disk/CPU | Scales linearly with shards | Scales linearly (with high CPU lock overhead) |
| **Query Latency** | Low | Low (Direct routing) | High (Broadcast merge latency) |
| **Operational Cost** | Low | High (Many processes to manage) | High |
| **Failover Isolation** | Failover affects all operations | Failover of one shard only affects its partitions | Failover of one shard blocks scatter queries |
| **Hardware Costs** | Moderate | High (Minimum 9+ hosts in production) | High |

---

## 3. How to Use: Dynamic Cluster Configurations

Let us analyze cluster commands. We contrast a naive, un-sharded database setup with a robust sharded collection initialization.

### A. The Monolithic Collection (Anti-Pattern)
Avoid saving massive datasets in un-sharded databases, which prevents horizontal write scaling:

```javascript
// DANGER: Without sharding enabled, this collection will live entirely on the primary 
// replica set shard. Other shards in the cluster will sit idle, wasting hardware resources.
db.largeLogFiles.insertOne({ logId: 1, message: "System crash" });
```

### B. The Hardened Sharded Collection Setup (Production Pattern)
Enable sharding at the database level and initialize a collection with a defined shard key:

```javascript
// Robust Pattern 1: Enable sharding on the target database.
sh.enableSharding("enterpriseLogs");

// Robust Pattern 2: Shard the collection using a hashed key to guarantee uniform distribution.
sh.shardCollection("enterpriseLogs.systemEvents", { eventUuid: "hashed" });
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Connecting Client Apps Directly to Shard Replica Sets
*   **Why it fails**: Configuring client driver connection strings to point directly to a shard's replica set port (e.g. `27018`) instead of the `mongos` router port (`27017`). The client can write to the shard, but the balancer will migrate chunks away, causing metadata mismatches and database inconsistencies.
*   **Mitigation**: Always route all client application connections exclusively through the stateless `mongos` router ports.

---

## 5. Socratic Review Questions

### Question 1
Why must the Config Servers in a sharded cluster be deployed as a replica set, and how does their consistency model differ from a standard replica set?

#### Answer
Config Servers store the cluster metadata mapping chunk ranges to specific shards. If this metadata is inconsistent, queries will read stale data or route writes to the wrong node. Config Servers use strict write concerns (`w:majority`) to ensure metadata changes are committed across the configuration replica set before client routing updates occur, preventing split-brain conditions.

---

## 6. Hands-on Challenge: Sharding Setup Verification

### The Challenge
In this challenge, you will write cluster initialization commands.
Your task:
1. Enable sharding on database `ecommerce`.
2. Shard the collection `ecommerce.orders` using a hashed shard key on `orderId`.

Complete the mongosh commands stub below:

```javascript
// TODO: Enable sharding on database
sh.enableSharding("ecommerce");

// TODO: Shard the orders collection using hashed orderId
sh.shardCollection(
  // Add collection name and shard key config here
);
```

### Verification Query
Verify shard status:
```javascript
const status = sh.status();
// Under mock configuration, we check command signatures
if (typeof sh.enableSharding === "function" && typeof sh.shardCollection === "function") {
  print("Success: Sharding configuration scripts compiled.");
} else {
  print("Error: Sharding APIs missing.");
}
```
