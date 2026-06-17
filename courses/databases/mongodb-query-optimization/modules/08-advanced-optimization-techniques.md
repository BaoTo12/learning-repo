# Module 08: Advanced Optimization Techniques

**Difficulty:** Advanced
**Estimated Study Time:** 5 hours
**Prerequisites:** Modules 01–07

---

## Learning Objectives

By the end of this module you will be able to:
- Use `$hint` to override plan selection and when NOT to use it
- Manage the plan cache for stability
- Use Query Settings (MongoDB 7.0+) as a production-safe plan control mechanism
- Configure read preferences and read/write concerns for workload-appropriate consistency
- Tune cursor batch size and explain cursor behavior
- Apply projection strategies to systematically reduce data transfer

---

## 8.1 Index Hints: Forcing a Plan

### What `$hint` Does

`$hint` forces MongoDB to use a specific index regardless of the planner's choice:

```javascript
// Force a specific index:
db.orders.find({ customerId: "CUST-1", status: "pending" })
  .hint({ customerId: 1, status: 1 })

// Force a collection scan (useful for benchmarking):
db.orders.find({ customerId: "CUST-1" })
  .hint({ $natural: 1 })

// In aggregation:
db.orders.aggregate(
  [{ $match: { customerId: "CUST-1" } }],
  { hint: "customerId_1" }    // Use index name string
)
```

### Layer 2: When `$hint` Is Justified

**Legitimate use cases:**

1. **Plan cache is serving a stale/incorrect plan:**
   ```javascript
   // The planner cached a bad plan before data distribution changed
   // Temporary fix while you clear the cache or wait for it to age out:
   db.orders.find({ status: "pending" }).hint({ status: 1, createdAt: -1 })
   ```

2. **Benchmarking index effectiveness:**
   ```javascript
   // Compare two indexes for the same query:
   const plan1 = db.orders.find({...}).hint("index_a").explain("executionStats");
   const plan2 = db.orders.find({...}).hint("index_b").explain("executionStats");
   // Choose the better performer
   ```

3. **Query planner makes a consistently wrong choice:**
   ```javascript
   // Rare but documented: planner chooses COLLSCAN over a valid index
   // Happens when a range filter has very low estimated selectivity
   db.orders.find({ amount: { $gt: 100 } }).hint({ amount: 1 })
   ```

### Layer 3: When `$hint` Is Dangerous

**Anti-patterns:**

1. **Hardcoding hints in application code permanently:**
   ```java
   // Anti-pattern in Spring Boot:
   mongoTemplate.find(
     new Query(Criteria.where("status").is("pending")).withHint("status_1"),
     Order.class
   );
   // Problem: If you later drop or rename the index, the hint causes query failure
   // The application crashes instead of gracefully falling back to an alternative plan
   ```

2. **Using hints to avoid fixing bad indexes:**
   ```javascript
   // Bad reasoning: "The planner picks the wrong index, so I'll always hint"
   // Real fix: Design the correct index and the planner will choose it
   ```

3. **Hinting when the query shape changes:**
   ```javascript
   // A hint correct for one data distribution may be wrong for another
   // As data grows and cardinality shifts, hardcoded hints become liabilities
   ```

**Engineering guideline:** Use `$hint` as a diagnostic and temporary stabilization tool. The permanent solution is always better index design or Query Settings (below).

---

## 8.2 Plan Cache Management

### Inspecting the Plan Cache

```javascript
// List all cached plans for a collection
db.orders.getPlanCache().list()

// For each entry, key fields to examine:
// {
//   "queryHash": "ABCD1234",       // Hash of the query shape
//   "planCacheKey": "EFGH5678",    // Hash of the plan (index combination)
//   "isActive": true,              // Currently used
//   "works": 1234,                 // Work units in the winning trial
//   "timeOfCreation": ISODate()    // When this plan was cached
// }
```

### Clearing the Plan Cache

```javascript
// Clear all plans for a collection (forces re-planning):
db.orders.getPlanCache().clear()

// Clear plans for a specific query shape (MongoDB 4.4+):
db.orders.getPlanCache().clearPlansByQuery(
  { customerId: "anything", status: "anything" }  // Representative query
)
```

### Plan Cache Invalidation Events (Review)

The plan cache is invalidated when:
1. An index is created or dropped
2. An index is hidden or unhidden
3. The collection is dropped
4. `mongod` restarts
5. Enough write operations have occurred (threshold-based automatic invalidation)

**The automatic invalidation threshold** is approximately 10% of the collection's document count written since the plan was cached. This prevents the cache from serving stale plans as data distribution changes.

### Query Settings: Production Plan Stabilization (MongoDB 7.0+)

Query Settings are a server-side configuration that pins a specific index to a specific query shape. Unlike `$hint` (client-side, per-request), Query Settings are stored in the cluster configuration and survive restarts.

```javascript
// Create a Query Setting (MongoDB 7.0+)
db.adminCommand({
  setQuerySettings: {
    find: "orders",           // Collection name
    filter: { customerId: 1, status: 1 },  // Query shape (literal values don't matter)
    $db: "myapp"
  },
  settings: {
    indexHints: [{
      ns: { db: "myapp", coll: "orders" },
      allowedIndexes: ["customerId_1_status_1"]  // Index name to use
    }]
  }
})

// View all active Query Settings
db.adminCommand({ showQuerySettings: 1 })

// Remove a Query Setting
db.adminCommand({
  removeQuerySettings: {
    find: "orders",
    filter: { customerId: 1, status: 1 },
    $db: "myapp"
  }
})
```

**When to use Query Settings over `$hint`:**
- Production systems where plan stability is critical
- After a confirmed plan regression that the planner cannot self-correct
- Long-term index pinning without modifying application code

---

## 8.3 Read Preferences

### The Five Read Preference Modes

```javascript
// primary (default): All reads to primary
db.orders.find({}).readPref("primary")

// primaryPreferred: Read from primary; fall back to secondary if primary unavailable
db.orders.find({}).readPref("primaryPreferred")

// secondary: All reads to secondaries (round-robin)
db.orders.find({}).readPref("secondary")

// secondaryPreferred: Read from secondary; fall back to primary if no secondaries
db.orders.find({}).readPref("secondaryPreferred")

// nearest: Read from the replica with lowest network latency (primary or secondary)
db.orders.find({}).readPref("nearest")
```

### Performance Implications

**Why use secondary reads?**

```
Primary node:
  ├─ Write operations (100% of writes)
  ├─ Read operations (100% of reads if no secondary reads)
  └─ Replication (continuous)

With secondary reads:
  Primary:
    ├─ Write operations (100% of writes)
    ├─ Read operations for critical/consistent reads
    └─ Replication (continuous)
  Secondary 1:
    ├─ Reporting queries (can be stale)
    └─ Replication
  Secondary 2:
    ├─ Analytics pipelines
    └─ Replication
```

Secondary reads can effectively double or triple read throughput for read-heavy workloads.

**Secondary read lag and stale data:**

```javascript
// Replication lag: time between primary write and secondary application
// Typically: milliseconds in healthy replica sets
// Under heavy write load or network issues: can be seconds or minutes

// Checking replication lag:
rs.printReplicationInfo()
rs.printSlaveReplicationInfo()  // From secondary: shows how far behind

// In production, monitor replication lag as a KPI
// Alert if lag > 10 seconds
```

**Workload mapping:**

| Query Type | Recommended Read Preference | Reason |
| :--- | :--- | :--- |
| User dashboard (own data) | `primary` | Read-your-writes consistency |
| Financial balance | `primary` | Absolute consistency required |
| Product catalog (browse) | `secondaryPreferred` | Slight staleness acceptable |
| Analytics / reports | `secondary` | Consistency not critical |
| Background jobs | `secondary` | Offload primary |
| Search/autocomplete | `nearest` | Minimize latency |

---

## 8.4 Read and Write Concerns

### Read Concerns

Read concerns control which data is visible to a read operation:

```javascript
// local (default): Returns data from the queried instance, may not be durable
db.orders.find({}).readConcern("local")

// majority: Returns only data acknowledged by majority of replica set
// (Prevents reading data that will be rolled back in a failover)
db.orders.find({}).readConcern("majority")

// linearizable: Reads data that reflects all acknowledged writes as of the
// read's start time (highest consistency, highest latency)
db.orders.find({}).readConcern("linearizable")

// snapshot: Reads data from a consistent snapshot of the database
// Required for multi-document transactions
db.orders.find({}).readConcern("snapshot")
```

**Performance impact of read concerns:**

| Read Concern | Consistency | Latency | Use Case |
| :--- | :--- | :--- | :--- |
| `local` | Lowest (may see un-replicated data) | Fastest | General reads, analytics |
| `majority` | High (safe data) | Moderate (waits for majority ack) | Financial reads, user operations |
| `linearizable` | Highest (serially consistent) | High (blocking) | Rarely needed (use transactions instead) |
| `snapshot` | Transaction-level | High | Multi-document transactions |

### Write Concerns

Write concerns control when MongoDB acknowledges a write as complete:

```javascript
// w: 0 — Fire and forget (no acknowledgment)
db.logs.insertOne(doc, { writeConcern: { w: 0 } })
// Fastest. Data may be lost if mongod crashes before writing to journal.
// Use only for truly disposable data (telemetry, debug logs)

// w: 1 (default) — Acknowledged by primary
db.orders.insertOne(doc, { writeConcern: { w: 1 } })
// Standard for most applications

// w: "majority" — Acknowledged by majority of voting members
db.payments.insertOne(doc, { writeConcern: { w: "majority" } })
// Guarantees data survives primary failure without data loss
// Additional latency: typically 1–5ms for a healthy 3-node replica set

// w: 2 — Acknowledged by at least 2 members
db.critical.insertOne(doc, { writeConcern: { w: 2 } })

// j: true — Wait for journal flush (disk durability) before acknowledging
db.payments.insertOne(doc, { writeConcern: { w: "majority", j: true } })
// Guarantees data is on disk before application receives acknowledgment
```

**Performance trade-off matrix:**

```
          Write Speed
          ↑ Fast    ↓ Slow
w:0   ─── fastest (no ack) ──────────────────── highest risk (data loss)
w:1   ─── fast (primary ack) ─────────────────── primary crash → data loss possible
w:2   ─── moderate ───────────────────────────── two-node failure required for loss
majority── moderate (cross-network) ───────────── highest durability
j:true ─── slower (disk sync) ─────────────────── guaranteed disk persistence
```

**Engineering guideline:**
- Transactional data (payments, orders): `{ w: "majority", j: true }`
- User-facing operations: `{ w: "majority" }` (j: true is usually overkill)
- Analytics ingest, bulk loading: `{ w: 1 }` or `{ w: 0 }` for max speed
- Audit logs: `{ w: "majority", j: true }` — must not be lost

---

## 8.5 Cursor Batch Size Tuning

### How MongoDB Returns Results

Results are not returned all at once. MongoDB uses a cursor with batches:

```
Client requests:  db.orders.find().batchSize(1000)

Batch 1: Server sends 1000 documents → Client processes
Batch 2: Server sends 1000 documents → Client processes
...
Final batch: Server sends remaining documents → Cursor closed
```

**Default batch size:**
- `find()` results: First batch = 101 documents or 16MB, subsequent batches = 16MB
- `aggregate()` results: First batch = 101 documents, subsequent = 16MB

### Tuning Batch Size

```javascript
// Increase batch size for large result sets (reduces round trips):
db.orders.find({ status: "completed" }).batchSize(5000)
// Better for: Batch export jobs, analytics scripts fetching millions of rows

// Decrease batch size for large documents (prevent memory spikes):
db.orders.find({}).batchSize(20)
// Better for: When each document is large (10KB+) and processing is slow

// Aggregation batch size:
db.orders.aggregate([...], { batchSize: 200 })
```

**When batch size matters:**
- Large exports: Large batches reduce TCP round trips, improving throughput
- Streaming pipelines: Smaller batches reduce client-side memory pressure
- Long-running cursors: Server-side cursor timeout (10 minutes by default) — large batches mean fewer cursor lifetime issues

**Cursor timeout:**
```javascript
// For long-running cursor operations (batch jobs):
db.orders.find({}).noCursorTimeout()
// WARNING: noCursorTimeout cursors must be explicitly closed
// or they persist forever (memory leak)
```

---

## 8.6 The `$sample` Operator

```javascript
// Get a random sample of 100 documents
db.users.aggregate([{ $sample: { size: 100 } }])
```

**Internals:** `$sample` uses one of two strategies:
1. **Pseudo-random cursor** (when N < 5% of collection and collection is not sharded): O(N) random reads — fast
2. **Sort with `$rand()`** (when N ≥ 5% or other conditions): Full sort — O(N log N) — slow

**When to use `$sample`:**
- Data exploration and profiling
- Creating test datasets from production data
- A/B experiment sampling

**When NOT to use `$sample`:**
- Precise statistical sampling (results are not truly random — cursor-based sampling has distribution bias)
- High-frequency operations (full sort for large N is expensive)

---

## 8.7 Combining Techniques: The Optimization Hierarchy

When optimizing a query or pipeline, apply techniques in this order:

```
Priority 1: Schema Design (Module 09)
  → Embedding vs. referencing determines whether $lookup exists at all
  → Document size affects working set and cache efficiency
  → Array cardinality affects multikey index behavior

Priority 2: Index Design (Modules 04–05)
  → Right index type, right field order (ESR), right covered fields
  → Compound index vs. multiple single-field indexes
  → Partial/sparse indexes to reduce index size

Priority 3: Query/Pipeline Structure (Modules 06–07)
  → $match first, projection early, $limit after $sort
  → Cursor-based pagination over offset pagination
  → $lookup with pipeline form and filtered subqueries

Priority 4: Advanced Controls (This Module)
  → Read preferences for workload distribution
  → Write concerns for consistency/performance balance
  → Batch size tuning for throughput
  → Hints and Query Settings for plan stability

Priority 5: Infrastructure (Module 10–11)
  → Sharding for horizontal scale
  → WiredTiger cache tuning (RAM)
  → Connection pool sizing
  → Hardware (SSD vs. HDD, RAM capacity)
```

> **Never jump to Priority 5 when the problem is actually Priority 1 or 2.** Adding RAM solves a cache miss problem temporarily; fixing the index solves it permanently and for free.

---

## 8.8 Exercises

### Exercise 8.1: Read Preference Selection

For each scenario, choose the correct read preference and explain your reasoning:

1. A user clicks "View my account balance" on a banking app.
2. A nightly job generates a usage report for the previous day.
3. A search-as-you-type autocomplete feature needs minimum latency.
4. An admin dashboard shows real-time active session count.
5. A background job exports all user data to S3 once per week.

### Exercise 8.2: Write Concern Trade-Off Analysis

You are building a financial payment processing system that processes 500 transactions/second. The business requires:
- No payment can be lost (even in a primary node crash)
- P99 latency must be < 50ms

Given a 3-node replica set where each primary→secondary replication takes ~3ms, design the write concern strategy and estimate whether the latency requirement is achievable.

### Exercise 8.3: Plan Cache Debugging

Your monitoring shows a query that was running in 5ms is now taking 2,000ms. You checked and the index exists. Walk through the steps to diagnose and fix the issue, including which tools you would use.

---

## 8.9 Knowledge Check

1. What is the difference between `$hint` and Query Settings, and when would you use each?
2. Name the five read preference modes and describe a production use case for each.
3. What is the difference between `w: 1` and `w: "majority"` write concerns?
4. What is cursor batch size and when would you increase or decrease it?
5. In what order should you apply optimization techniques (schema → indexes → queries → infrastructure)?

---

## 8.10 Interview-Style Questions

**Q: A critical payment microservice is losing some payments during database failovers. What write concern setting would you recommend and what are the trade-offs?**

> Model answer: Use `{ w: "majority", j: true }`. This ensures the write is acknowledged by a majority of the replica set with journal persistence, meaning even if the primary crashes immediately after acknowledgment, the data is preserved on enough secondaries to survive election. Trade-offs: latency increases by the replication round-trip time (typically 2–5ms in healthy replica sets) plus journal flush time. For a payment system, this is absolutely worth it. Additionally, implement idempotency in the write logic — if the application retries on timeout, a duplicate payment attempt should be detected and rejected using an idempotency key (unique compound index on `{ paymentId: 1, idempotencyKey: 1 }` with `unique: true`).

**Q: You use `$hint` to force an index, and it works great. Your colleague says you should remove it and let MongoDB decide. Who is right?**

> Model answer: Your colleague is generally right as a principle. `$hint` should be temporary, not permanent. If the planner consistently chooses a worse index, the root cause is either (1) the better index does not exist yet — fix it, (2) the index exists but the data distribution has made it appear non-selective to the planner — clear the plan cache and let re-planning occur, (3) a genuine planner bug/limitation — in this case, use Query Settings (MongoDB 7.0+) instead of application-level `$hint` for a maintainable, code-independent solution. Hardcoded hints in application code create operational risk: dropping or renaming the hinted index causes application crashes, and the hint may become suboptimal as data evolves.

---

*Next: [Module 09: Schema Design and Query Performance →](09-schema-design-and-query-performance.md)*
