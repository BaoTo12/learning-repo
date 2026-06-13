# Module 18: Seeing What Your Application Is Doing (Chapter 18)

Welcome class. Today we analyze **Seeing What Your Application Is Doing (CS-529)**.

Maintaining performance in high-throughput database clusters requires monitoring queries in real time. We must identify and terminate slow operations before they consume execution threads and lock up database caches.

Today we study **Database Diagnostics & Profiling**, analyzing query tracking via `currentOp()`, the system profiler, database size audits, and performance tools (`mongostat`/`mongotop`).

---

## 1. Academic Lecture: Real-Time Diagnostics & Profiling

### 1. In-Flight Query Inspections
The database command `db.currentOp()` returns a document describing all active operations running on the database server.
*   **Targeting Slow Queries**: We can filter the output to find operations running longer than a threshold (e.g. 5 seconds) and terminate them using `db.killOp(opId)`.

### 2. The Database Profiler
MongoDB has a built-in **System Profiler** that records slow queries to a capped collection named `system.profile` inside each database:
*   **Level 0**: Profiling is off.
*   **Level 1**: Profiler records operations taking longer than the slow execution threshold (default is 100ms).
*   **Level 2**: Profiler records all database operations.

```text
[Incoming Query] ──> [Database Engine] ──> [Exceeds 100ms?] ──> Yes ──> Write to system.profile
```

---

## 2. Theory vs. Production Trade-offs

Compare profiling levels:

| Dimension / Metric | Profiler Level 0 (Off) | Profiler Level 1 (Slow Queries Only) | Profiler Level 2 (All Queries) |
| :--- | :--- | :--- | :--- |
| **System Overhead** | Zero | Low | Severe (Every read/write incurs a logging write) |
| **Disk Write Cost** | Zero | Low | High |
| **Diagnostic Resolution**| None | Good (Identifies bottleneck queries) | Absolute |
| **WiredTiger Cache Impact**| Zero | Minimal | High (Dirty pages accumulate in cache) |
| **Use Case** | Production Default | Production Diagnostics | Local Development / Debugging |

---

## 3. How to Use: Real-time Query Profiling

Let us configure database diagnostics. We contrast an unmonitored collection deployment (blind to slow queries) with a configured system profiler setup.

### A. The Unmonitored Runtime (Anti-Pattern)
Avoid running applications without slow-query logging, which hides query bottlenecks:

```javascript
// DANGER: Slow un-indexed queries will run indefinitely, occupying WiredTiger read 
// tickets and eventually locking the entire server without any record in diagnostic logs.
```

### B. The Hardened Profiler and Diagnostics Setup (Production Pattern)
Enable Level 1 profiling for queries taking longer than 200ms, and write a cleanop filter script:

```javascript
// Robust Pattern 1: Set database profiling level to 1 (slow queries) with a 200ms threshold.
db.setProfilingLevel(1, { slowms: 200 });

// Robust Pattern 2: Inspect active queries running for more than 5 seconds.
db.currentOp({
  "active": true,
  "secs_running": { $gt: 5 }
});
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Leaving Profiler Level 2 Enabled in Production
*   **Why it fails**: Leaving Level 2 profiling active under high load. Writing every query execution to the `system.profile` capped collection doubles the write load, locks WiredTiger caches, and fills system logs.
*   **Mitigation**: Only use Level 2 during development or test runs. Use Level 1 with a conservative `slowms` (e.g. 100-200ms) in production.

---

## 5. Socratic Review Questions

### Question 1
Why does a query that is terminated using `db.killOp()` sometimes continue to show up in `db.currentOp()` for several seconds?

#### Answer
`db.killOp()` does not kill the thread process at the OS level. Instead, it sets an interrupt flag on the database operation context. The executing database thread checks this flag at designated **safe points** (e.g., between index keys scans or document disk reads). If the query is stuck in a heavy calculation or waiting for a disk page fault, it may take time to hit a safe point and terminate.

---

## 6. Hands-on Challenge: Identifying and Killing Slow Threads

### The Challenge
In this challenge, you will write an administrative maintenance script.
Your task:
1. Write a script to locate and return the operation IDs (`opid`) of all active queries in the `ecommerce` database that have been running for more than `10` seconds.
2. Exclude system helper operations (like replication or internal index builds).

Complete the implementation stub below:

```javascript
function findSlowOpIds() {
  // TODO: Query db.currentOp() for active operations running > 10s
  // Exclude operations where ns matches system collections or config
  return [];
}
```

### Verification Query
Validate the search structure:
```javascript
const ops = findSlowOpIds();
if (Array.isArray(ops)) {
  print("Success: Diagnostic filter ran successfully.");
} else {
  print("Error: Diagnostic filter failed.");
}
```
