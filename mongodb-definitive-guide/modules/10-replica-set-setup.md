# Module 10: Setting Up a Replica Set (Chapter 10)

Welcome class. Today we analyze **Setting Up a Replica Set (CS-529)**.

High availability is mandatory in enterprise databases. A single database node represents a single point of failure (SPOF). MongoDB solves this by using **Replica Sets**—groups of database processes that synchronize the same dataset, providing automatic failover and read/write separations.

Today we study **Replica Set Cluster Topology**, analyzing member node classifications, election priorities, and network routing configurations.

---

## 1. Academic Lecture: High Availability & Cluster Topologies

### 1. Replica Set Primary and Secondary Members
A standard replica set consists of a group of nodes that coordinate state:
*   **The Primary**: The single node that accepts all write operations. It records its writes to its Oplog (operations log).
*   **The Secondaries**: Multiple nodes that replicate the primary's oplog and apply the operations to their datasets. Secondaries cannot accept writes.

### 2. Node Variations
*   **Hidden Members**: Replicate data and vote in elections, but are invisible to client drivers. Used for analytical reports or backups.
*   **Arbiters**: Do not replicate data; they only exist to vote in elections when the number of members is even, preventing split-brain scenarios.

```text
                  ┌───────────────┐
                  │ Primary Node  │ (Accepts Writes)
                  └──────┬────────┘
                         │ (Oplog Sync)
            ┌────────────┴────────────┐
            ▼                         ▼
    ┌───────────────┐         ┌───────────────┐
    │ Secondary 1   │         │ Hidden Sec    │ (Priority: 0, Hidden: true)
    └───────────────┘         └───────────────┘
```

---

## 2. Theory vs. Production Trade-offs

Compare member configurations within a replica set:

| Dimension / Metric | Standard Secondary | Hidden Secondary | Election Arbiter |
| :--- | :--- | :--- | :--- |
| **Holds Dataset** | Yes | Yes | No |
| **Can Become Primary**| Yes (If priority > 0) | No (Priority is locked to 0) | No |
| **Votes in Elections**| Yes | Yes | Yes |
| **Driver Visibility** | Visible (Can handle reads) | Invisible | Invisible |
| **System Resource Cost**| High (Full storage/CPU) | High (Full storage/CPU) | Very Low (No data storage) |

---

## 3. How to Use: Replica Set Configuration Document

Let us define replica set configurations. We contrast a naive replica set configuration (vulnerable to network splits) with a robust multi-region hidden member configuration.

### A. The Even-Member Set Configuration (Anti-Pattern)
Avoid configuring replica sets with an even number of voting nodes without an arbiter:

```javascript
// DANGER: With exactly 2 voting nodes, if a network partition occurs,
// neither node can establish a majority vote (>50%). No primary can be elected,
// locking the database in read-only mode.
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo1:27017" },
    { _id: 1, host: "mongo2:27017" }
  ]
});
```

### B. The Hardened Voting Set Configuration (Production Pattern)
Define an odd number of voting nodes, using priority limits to protect analytical nodes:

```javascript
// Robust Pattern: Odd number of voting members (3 nodes).
// Node 2 is a dedicated analytical backup node that can never become primary.
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo1:27017", priority: 2 },
    { _id: 1, host: "mongo2:27017", priority: 1 },
    { _id: 2, host: "mongo3:27017", priority: 0, hidden: true }
  ]
});
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Deploying Arbiters on the Same Host as Data Nodes
*   **Why it fails**: Deploying an Arbiter process on the same VM host machine as a secondary node to "save money". If that physical host goes offline, the replica set loses **two** members simultaneously. This can crash the voting majority, causing the remaining node to step down to secondary.
*   **Mitigation**: Always place arbiters on independent, isolated hosts.

---

## 5. Socratic Review Questions

### Question 1
Why does a secondary member node configuration require its priority setting to be `0` in order to be marked as `hidden: true`?

#### Answer
If a member is hidden, it is hidden from client application drivers, meaning it cannot receive read traffic. If a hidden member had `priority > 0`, it could be elected as the cluster primary. If a hidden member became the primary, client drivers would be unable to find or connect to it, locking all write operations across the application.

---

## 6. Hands-on Challenge: Configuring a Multi-Tier Replica Set

### The Challenge
In this challenge, you will write a replica set configuration.
Your task:
1. Define a configuration document `reconfig.json` for an existing replica set named `production-set`.
2. Members list must contain:
   - Member 0: `prod-node1:27017` (priority: 2)
   - Member 1: `prod-node2:27017` (priority: 1)
   - Member 2: `backup-node:27017` (analytical backup node: must never become primary, must be hidden).

Complete the implementation stub below:

```javascript
// TODO: Define the replica set config object
const config = {
  _id: "production-set",
  members: [
    // Add member configs here
  ]
};
```

### Verification Query
Verify the configuration fields:
```javascript
const member2 = config.members.find(m => m.host === "backup-node:27017");

if (member2 && member2.priority === 0 && member2.hidden === true) {
  print("Success: Analytical backup node isolated via priority and hidden rules.");
} else {
  print("Error: Config structure violation.");
}
```
