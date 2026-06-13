# Module 11: Components of a Replica Set (Chapter 11)

Welcome class. Today we analyze **Components of a Replica Set (CS-529)**.

Behind a replica set's high availability lies a distributed state machine. Nodes must constantly coordinate data synchronization, evaluate node health, run leader elections, and resolve data divergence (rollbacks) without manual intervention.

Today we study **Replica Set Synchronization & Elections**, analyzing Oplog syncing mechanics, heartbeat checks, Raft-like election protocols, and rollback resolution boundaries.

---

## 1. Academic Lecture: Oplog Syncing & Rollback Boundaries

### 1. Synchronization Mechanics
*   **Initial Sync**: When a secondary node joins a cluster, it drops its databases, copies all data from a source node, and replays all oplog operations generated during the copy.
*   **Replication Sync**: Secondaries continuously tail the oplog of their sync source (which can be the primary or another secondary using chaining).

### 2. Elections & Rollback Files
*   **Elections**: Nodes exchange heartbeats once every 2 seconds. If a primary fails to respond for 10 seconds, secondaries initiate an election. A node must receive votes from a majority of the replica set's total voting members to become the primary.
*   **Rollbacks**: If a primary commits writes to its local storage but crashes before they replicate to secondaries, the new primary will have divergent data. When the old primary recovers, it must **rollback** its un-replicated writes, saving them to a `.bson` rollback file in the `rollback/` directory.

```text
[Node A (Primary crashes)] ──> Write "Data X" (un-replicated)
[Node B elected Primary] ───> Write "Data Y"
[Node A recovers] ──────────> Detects mismatch ──> Rollback "Data X" to file ──> Syncs "Data Y"
```

---

## 2. Theory vs. Production Trade-offs

Compare replication sync parameters:

| Dimension / Metric | Direct Primary Syncing | Chained Syncing (Secondary-to-Secondary) |
| :--- | :--- | :--- |
| **Primary CPU Load** | High (All nodes tail primary) | Low (Secondaries tail other secondaries) |
| **Network Replication Lag**| Minimal | Higher (Cascading sync delay) |
| **Sync Source Resiliency**| High | Vulnerable to transit hop outages |
| **Inter-Data Center Cost** | High (Cross-WAN traffic from all nodes) | Low (One node pulls cross-WAN, others sync locally) |
| **Execution Complexity** | Low | High (Requires dynamic sync graph adjustments) |

---

## 3. How to Use: Analyzing Election States

Let us monitor replica set status. We compare a naive deployment (blind to replication lag) with a monitoring check that identifies lag bottlenecks.

### A. The Blind Connection (Anti-Pattern)
Avoid reading from secondaries without checking node synchronization health:

```javascript
// DANGER: This connection reads from secondaries without verifying lag.
// If secondary sync is delayed by minutes, the client will read stale data.
db.getMongo().setReadPref("secondary");
const staleDoc = db.users.findOne({ _id: 1 });
```

### B. The Hardened Sync Status Check (Production Pattern)
Run administrative checks to monitor replication lag and sync source hierarchies:

```javascript
// Robust Pattern: Inspect replication health status.
const status = rs.status();
status.members.forEach(member => {
  if (member.stateStr === "SECONDARY") {
    // Calculate synchronization lag against the primary's oplog state
    const lag = status.members[0].optimeDate - member.optimeDate;
    print(`Member: ${member.name} | State: SECONDARY | Lag: ${lag / 1000}s`);
  }
});
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Oplog Size Saturation (Oplog Overrun)
*   **Why it fails**: If a replica set secondary goes offline for maintenance, and the primary processes a high volume of writes, the primary's Oplog can roll over (exceed its max size), overwriting historical logs. When the secondary recovers, its sync point is gone, forcing it to undergo a costly **Initial Sync**.
*   **Mitigation**: Size Oplogs conservatively. Oplogs should hold at least 24–48 hours of write volume. Use `rs.printReplicationInfo()` to check Oplog window times.

---

## 5. Socratic Review Questions

### Question 1
Why does a replica set election fail if a network partition splits a 5-node cluster into a 2-node group and a 3-node group?

#### Answer
MongoDB requires a vote from a absolute majority of the replica set's total configured members to elect a primary. For a 5-node cluster, the majority threshold is 3. In the 2-node partition, no primary can be elected. In the 3-node partition, the nodes can establish a majority (3 votes) and elect a primary. This guarantees that only one partition can write, preventing split-brain conflicts.

---

## 6. Hands-on Challenge: Evaluating Rollback Risks

### The Challenge
In this challenge, you will implement a replica set status check.
Your task:
1. Write a script `check_health.js` that checks replica set members.
2. The script must scan `rs.status().members` and raise an alarm (return false) if any secondary member has replication lag exceeding 10 seconds compared to the primary.

Complete the implementation stub below:

```javascript
function verifyReplicationLag() {
  const status = rs.status();
  const primaryMember = status.members.find(m => m.state === 1);
  if (!primaryMember) return false;
  
  // TODO: Loop through members and check lag
  // Return false if any secondary lag > 10000ms
  return true;
}
```

### Verification Query
Verify the output structure:
```javascript
const healthy = verifyReplicationLag();
if (typeof healthy === "boolean") {
  print("Success: Replication lag validator executed.");
} else {
  print("Error: Validator did not return boolean status.");
}
```
