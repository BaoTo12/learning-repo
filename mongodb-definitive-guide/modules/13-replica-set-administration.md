# Module 13: Replica Set Administration (Chapter 13)

Welcome class. Today we analyze **Replica Set Administration (CS-529)**.

Operational management of replica sets requires performing critical tasks—such as hardware upgrades, index additions, and configuration changes—without causing downtime or losing database consensus.

Today we study **Replica Set Administrative Engineering**, analyzing forced reconfigurations, step-down mechanisms, secondary index building strategies, and live oplog resizing.

---

## 1. Academic Lecture: Forced Reconfigurations & Online Maintenance

### 1. Forced Configurations
If a network partition or hardware disaster takes a majority of voting replica set nodes offline, the remaining nodes cannot elect a primary. To recover, administrators must run a **Forced Reconfiguration** (`force: true`), which bypasses member consensus to initialize a new topology structure.

### 2. Live Oplog Resizing
Historically, changing the primary's Oplog size required restarting processes. Modern MongoDB engines allow dynamic online oplog resizing using administrative command parameters.
*   **Secondary Index Builds**: Building an index is CPU/disk-heavy. To prevent the primary from blocking requests, indexes are built in a rolling fashion:
    1.  Take a secondary offline, start it as standalone.
    2.  Build the index.
    3.  Re-join it to the replica set. Repeat for other secondaries, then step down the primary and repeat.

```text
[Secondary Node] ──> Standalone Mode ──> Build Index ──> Re-join set
                                                              │
[Step down Primary] <─────────────────────────────────────────┘
```

---

## 2. Theory vs. Production Trade-offs

Compare index building strategies on replica sets:

| Dimension / Metric | Foreground Index Build | Background Index Build | Rolling Index Build (Secondary-First) |
| :--- | :--- | :--- | :--- |
| **Primary Database Locks** | Exclusive (Blocks all reads/writes) | Intent (Allows concurrent queries) | None |
| **System Resource Impact**| High (Quick build, high CPU load) | Moderate (Slower build) | None on Primary (Executes on standalones) |
| **Client Query Impact** | Severe (Application hangs) | Minimal (Higher latency) | Zero |
| **Consistency Guarantee** | Same index key across set | Same index key across set | Strict (Index built on all nodes before use) |
| **Operational Effort** | None | None | High (Requires manual node restarts) |

---

## 3. How to Use: Dynamic Oplog Resizing

Let us perform replica set administrative tasks. We contrast a volatile, obsolete oplog resizing routine with the modern dynamic configuration pattern.

### A. The Obsolete Offline Oplog Resize (Anti-Pattern)
Avoid restarting nodes to resize the oplog, which creates unnecessary cluster failovers:

```javascript
// DANGER: Stopping members to adjust parameters in mongod.conf causes database 
// node down times and triggers cluster re-elections.
// Legacy method required offline configuration parameters adjustments.
```

### B. The Hardened Online Oplog Resizing (Production Pattern)
Resize the oplog dynamically using the runtime administrative commands:

```javascript
// Robust Pattern: Resize the Oplog to 50GB (53687091200 bytes) dynamically.
db.adminCommand({
  replSetResizeOplog: 1,
  size: Double(53687091200) // Double cast required for size validation
});
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Force Reconfigurations on False Network Splits
*   **Why it fails**: Executing `rs.reconfig(newConfig, { force: true })` when the primary node is merely slow, not disconnected. If the primary can still talk to a subset of nodes, forcing reconfiguration can split the set, creating **two independent primaries** (split-brain), which leads to silent write divergence.
*   **Mitigation**: Only use `{ force: true }` when a true majority of members are permanently dead.

---

## 5. Socratic Review Questions

### Question 1
Why does building a secondary index in a rolling fashion require starting the target secondary node as a standalone process on a different port?

#### Answer
If you build the index while the node is active in the replica set, the member will process the build task but will still attempt to handle read queries from clients. Since index building consumes heavy CPU and disk I/O, client queries on that secondary will experience high latency. Starting the node as standalone blocks client traffic, allowing the index to build using maximum system resources without affecting the application.

---

## 6. Hands-on Challenge: Rolling Index Maintenance Script

### The Challenge
In this challenge, you will implement an administrative config helper.
Your task:
1. Write a script to check if the current node is the primary.
2. If it is the primary, execute a step-down command to force it to become a secondary, allowing other members to take the primary role.

Complete the administrative script stub below:

```javascript
function stepDownPrimaryIfActive() {
  // TODO: Check replica set state using rs.status()
  // If stateStr is "PRIMARY", execute rs.stepDown(60) (60 seconds stepdown)
}
```

### Verification Query
Verify the command sequence:
```javascript
// Check rs commands are present
if (typeof rs.stepDown === "function") {
  print("Success: Stepdown controller initiated.");
} else {
  print("Error: Admin functions missing.");
}
```
