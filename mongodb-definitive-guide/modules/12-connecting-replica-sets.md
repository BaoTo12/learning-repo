# Module 12: Connecting to a Replica Set from Your Application (Chapter 12)

Welcome class. Today we analyze **Connecting to a Replica Set from Your Application (CS-529)**.

A database cluster is only as resilient as the application client driver connecting to it. Client drivers must dynamically discover replica set topologies, handle node failures without throwing errors, route reads/writes to correct nodes, and enforce consistency guarantees.

Today we study **Driver Topology Connection Mechanics**, mapping connection strings, analyzing write concerns (`w`), and evaluating read preference parameters.

---

## 1. Academic Lecture: Driver Topology Discovery & Consistency

### 1. Replica Set Discovery & Seed Lists
When an application connects to a replica set, it uses a connection string containing a seed list of nodes:
`mongodb://node1:27017,node2:27017/?replicaSet=rs0`.
1.  The driver connects to any seed node and executes the `isMaster` command.
2.  The node returns the current primary and list of all members.
3.  The driver connects to all members and updates its internal topology map.

### 2. Write Concern (`w`) and Read Preference
*   **Write Concern (`w:majority`)**: The primary blocks response until the write is written to the primary's journal AND replicated to a majority of voting members' journals.
*   **Read Preference (`secondaryPreferred`)**: Routes read queries to secondaries to offload the primary, falling back to the primary if secondaries are offline.

```text
[App Driver] ────────── Write (w:majority) ──────────> [Primary Node]
                                                            │
                                                     (Syncs to Node B)
                                                            ▼
[App Driver] <────── Ack (Replication Done) ────────── [Primary Node]
```

---

## 2. Theory vs. Production Trade-offs

Compare read preference routing strategies:

| Read Preference | Primary Target | Read Latency | Consistency Guarantee | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **primary** | Primary only | Moderate | Strict (Always reads latest writes) | Transactional operations |
| **primaryPreferred** | Primary first | Moderate | Strict (Unless primary is offline) | Core user profiles |
| **secondary** | Secondaries only | Low | Eventual (Subject to replication lag) | Heavy report generation |
| **secondaryPreferred** | Secondaries first | Low | Eventual | Catalogs and search |
| **nearest** | Lowest network ping node | Very Low | Eventual | Multi-region deployments |

---

## 3. How to Use: Resilient Connection Setup

Let us configure client options. We contrast a type-weak connection configuration (vulnerable to write rollbacks) with a robust write concern configuration.

### A. The Fire-and-Forget Write Config (Anti-Pattern)
Avoid using low write concerns for critical application data:

```javascript
// DANGER: w:1 only waits for primary acknowledgment. If the primary crashes before 
// replication completes, this write is lost (rolled back), causing data loss.
const dbConnection = db.getMongo();
db.getSiblingDB("finance").orders.insertOne(
  { sku: "SKU-99", qty: 1 },
  { writeConcern: { w: 1, j: false } }
);
```

### B. The Hardened Majority Write Config (Production Pattern)
Enforce majority write concerns and set strict timeouts to prevent connection hangs:

```javascript
// Robust Pattern: Acknowledged by majority, journal persisted, with a 5-second timeout.
db.getSiblingDB("finance").orders.insertOne(
  { sku: "SKU-99", qty: 1 },
  { writeConcern: { w: "majority", j: true, wtimeout: 5000 } }
);
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Infinite Client Waits on WAN Partitions
*   **Why it fails**: Using `w:majority` without specifying a `wtimeout`. If a network partition cuts off the primary from secondaries, the primary cannot achieve majority validation. The write operation blocks indefinitely, consuming connection threads on the application server until the server runs out of memory.
*   **Mitigation**: Always declare a `wtimeout` (e.g. 5000ms) alongside `w:majority`.

---

## 5. Socratic Review Questions

### Question 1
Why does reading from a secondary using `readPreference: "secondary"` lead to monotonic read consistency violations (reading a value, then subsequently reading an older value)?

#### Answer
Secondaries pull writes independently from the primary's oplog, meaning their sync timelines differ. If secondary A is synchronized up to time T1, and secondary B is lagging at time T0, a client driver routing consecutive reads to "secondary" will query A first (reading data at T1) and then B (reading older data at T0), causing a consistency regression.

---

## 6. Hands-on Challenge: Configured Client Connection Routing

### The Challenge
In this challenge, you will implement client write concerns.
Your task:
1. Write a script to insert a document to `payments`.
2. The transaction must use a write concern requiring majority confirmation, journal replication, and a strict timeout limit of 3 seconds.

Complete the insertion stub below:

```javascript
// TODO: Write payment insertion query with strict writeConcern
db.payments.insertOne(
  { txnId: "TX-9001", amount: 450.00 },
  // Add writeConcern object here
);
```

### Verification Query
Verify the write concern settings:
```javascript
// We check if the execution fails gracefully under mock constraints
try {
  db.payments.insertOne(
    { txnId: "TX-TEST", amount: 1.00 },
    { writeConcern: { w: "majority", j: true, wtimeout: 3000 } }
  );
  print("Success: Query executed with majority journaling write concerns.");
} catch (e) {
  print("Error: Invaliding configuration.");
}
```
