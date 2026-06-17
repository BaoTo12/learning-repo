# Module 02: MongoDB Query Execution Internals

**Difficulty:** Beginner–Intermediate
**Estimated Study Time:** 5 hours
**Prerequisites:** Module 01

---

## Learning Objectives

By the end of this module, you will be able to:
- Trace the full lifecycle of a MongoDB query from client submission to result delivery
- Explain why MongoDB generates multiple candidate plans and how it selects a winner
- Describe how the plan cache works and when it can hurt performance
- Distinguish the classic execution engine from the Slot-Based Execution Engine (SBE)
- Predict query execution behavior from first principles

---

## 2.1 The Query Lifecycle: End to End

### Layer 1: Intuition

When you type `db.orders.find({ status: "pending" })` in the shell, you see results appear in milliseconds. What happens between pressing Enter and seeing results is one of the most important things a performance engineer must understand deeply.

Think of a query as a package being shipped:
1. It is **labeled and sorted** (parsing + canonicalization)
2. A **delivery route is planned** (query planning)
3. The **fastest route is selected** from alternatives (plan selection)
4. The route is **remembered for future packages** (plan cache)
5. The package is **physically delivered** (execution)
6. You **receive and open it** (result delivery)

Understanding each stage tells you where delays can occur and how to eliminate them.

### Layer 2: Internal Mechanics

```
Client
  │
  ▼
┌──────────────────────────────────────────────────────────────────┐
│                    mongod Process                                │
│                                                                  │
│  ①  Wire Protocol  →  Command Parsing (BSON deserialization)    │
│                                                                  │
│  ②  Command Dispatcher  →  Identifies: find/aggregate/update... │
│                                                                  │
│  ③  Canonicalization  →  Normalizes query shape                 │
│        • Sorts filter fields lexicographically                   │
│        • Removes $and wrappers with one child                    │
│        • Converts { a: { $eq: 1 } } → { a: 1 }                  │
│        • Produces canonical query shape (used as cache key)      │
│                                                                  │
│  ④  Plan Cache Lookup  →  Is there a cached plan?               │
│        • If YES (cache hit): skip to ⑧                          │
│        • If NO (cache miss): continue to ⑤                      │
│                                                                  │
│  ⑤  Candidate Plan Generation                                   │
│        • Identifies all relevant indexes                         │
│        • Generates one plan per candidate index                  │
│        • Generates one COLLSCAN plan (always considered)         │
│                                                                  │
│  ⑥  Plan Evaluation (Multi-Plan Race)                           │
│        • Runs all candidate plans simultaneously                 │
│        • Each plan executes until: 101 docs returned OR          │
│          examined 10,000 docs OR 10x more docs than winner       │
│        • The plan that returns results fastest wins              │
│                                                                  │
│  ⑦  Cache Winning Plan                                          │
│        • Stores plan in plan cache keyed by query shape          │
│        • Cache entry invalidated by: index creation/drop,        │
│          enough new data written to collection                   │
│                                                                  │
│  ⑧  Plan Execution  →  Execute via query engine                 │
│        • Classic Engine (older MongoDB versions)                 │
│        • Slot-Based Execution Engine / SBE (MongoDB 5.1+)        │
│                                                                  │
│  ⑨  Result Assembly  →  Apply projection, batch cursor          │
│                                                                  │
│  ⑩  Wire Protocol  →  Return BSON results to client             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
  │
  ▼
Client receives results
```

Let us examine each stage that has significant performance implications.

---

## 2.2 Parsing and Canonicalization

### What Happens

When a query arrives, MongoDB first deserializes the BSON bytes into an internal query representation. It then *canonicalizes* the query — transforming it into a standard normal form.

**Why canonicalization matters:** The canonical form is used as the plan cache key. If two queries that are logically equivalent produce different canonical forms, they will have separate cache entries, doubling planning overhead. If they produce the same canonical form, they share a cache entry — one plan serves both.

### Examples of Canonicalization

```javascript
// These three queries are logically equivalent AND share a cache entry:
db.orders.find({ status: "pending", customerId: "C1" })
db.orders.find({ customerId: "C1", status: "pending" })       // field order swapped
db.orders.find({ $and: [{ status: "pending" }, { customerId: "C1" }] })

// After canonicalization, all become:
// { customerId: <param>, status: <param> }  (fields sorted lexicographically)

// These do NOT share a cache entry (different operators = different shape):
db.orders.find({ amount: { $gt: 100 } })       // shape: { amount: { $gt: <val> } }
db.orders.find({ amount: { $gte: 100 } })      // shape: { amount: { $gte: <val> } }
```

### Production Implication

If your application generates queries with inconsistent field ordering depending on code paths, each ordering generates separate plan cache entries. This wastes planning cycles and cache space. Use a consistent query builder layer to ensure canonical ordering.

---

## 2.3 Candidate Plan Generation

### Layer 1: Intuition

When planning a route from A to B, you might consider: highway, back roads, or public transit. MongoDB does the same — it considers one query execution strategy per relevant index, plus one strategy without any index (collection scan).

### Layer 2: How MongoDB Identifies Candidate Indexes

MongoDB examines each index in the collection and asks: *"Can this index help satisfy this query's filter, sort, or both?"*

An index is considered a **candidate** if:
1. The query filter references at least the first field(s) of the index (prefix principle — covered in Module 05)
2. OR the query sort uses the index field(s) in the same direction

**Example:**

```javascript
// Query:
db.orders.find({ status: "pending" }).sort({ createdAt: -1 })

// Available indexes:
// A: { status: 1 }           → Candidate: matches filter prefix
// B: { createdAt: -1 }       → Candidate: matches sort
// C: { status: 1, createdAt: -1 } → Candidate: matches both filter + sort
// D: { customerId: 1 }       → NOT a candidate: doesn't help filter or sort
// E: COLLSCAN                → Always a candidate

// Plans generated:
// Plan 1: Use index A for filter, in-memory sort on createdAt
// Plan 2: Use index B for sort, filter applied after fetch
// Plan 3: Use index C for both filter and sort (optimal)
// Plan 4: COLLSCAN, in-memory sort
```

### Layer 3: Multi-Plan Race (Experimental Execution)

This is one of the most elegant and counterintuitive aspects of MongoDB's query planner. Instead of statically analyzing query costs (like traditional RDBMS cost-based optimizers), MongoDB *actually runs* all candidate plans simultaneously for a short trial period and picks the winner by measuring real performance.

```
Time →

Plan 1 (Index A): ─────── (reads index, fetches docs) → 101 docs after 50ms
Plan 2 (Index B): ──── (reads index differently) → 101 docs after 20ms ← WINNER
Plan 3 (Index C): ────────────── (reading both fields) → stalled
Plan 4 (COLLSCAN): ──────────────────────── → not yet 101 docs

Winner: Plan 2, cached for this query shape
```

**Trial run termination conditions (any one triggers end):**
- A plan returns 101 documents
- A plan has examined 10,000 index keys or documents
- One plan has examined 10x more documents than the current leader

**Why this approach?**

Traditional cost-based optimizers require accurate statistics (row counts, cardinality estimates, histogram data). MongoDB's document model makes collecting accurate statistics harder — arrays, nested documents, and flexible schemas make cardinality estimation complex. The multi-plan race sidesteps this by measuring actual performance instead of estimating it.

**The downside:** The trial run consumes real resources. If you have 5 candidate plans and each reads 10,000 documents before termination, that is 50,000 document reads just for planning. For frequently executed queries, this overhead is amortized by the plan cache. For rare queries, it may be significant.

---

## 2.4 The Plan Cache

### Layer 1: Intuition

Remembering a proven route is faster than planning from scratch every trip. MongoDB's plan cache stores the winning execution plan for each query shape. When the same query shape appears again, MongoDB retrieves the cached plan and executes it immediately, skipping the planning phase.

### Layer 2: Cache Mechanics

**Cache Key:** The canonical query shape (filter operator structure + projection structure + sort direction structure), NOT the literal values.

```javascript
// These share a cache entry (same shape, different values):
db.orders.find({ status: "pending", customerId: "CUST-1" })
db.orders.find({ status: "shipped", customerId: "CUST-99" })

// Cache key: { status: <string>, customerId: <string> }
```

**Cache Entry States:**
1. `"missing"` — no cached plan for this shape
2. `"inactive"` — plan was cached but needs re-evaluation
3. `"active"` — plan is ready and will be used immediately

**Cache Invalidation Triggers:**
- An index is created or dropped on the collection
- The collection is dropped
- The `mongod` process is restarted
- **Data cardinality changes significantly** (more on this below)

### Layer 3: Inspecting the Plan Cache

```javascript
// List all cached plans
db.orders.getPlanCache().list()

// Clear the plan cache for a collection (use with caution!)
db.orders.getPlanCache().clear()

// Clear a specific plan from cache (MongoDB 4.4+)
db.orders.getPlanCache().clearPlansByQuery(
  { status: "pending", customerId: "CUST-1" }
)
```

### Layer 4: When the Plan Cache Hurts Performance

This is one of the most subtle and dangerous aspects of MongoDB performance.

**The Scenario: Plan Cache Staleness**

1. Your `orders` collection is new. 95% of orders have `status: "pending"`.
2. MongoDB selects a plan using `{ status: 1 }` index → works well (few matching docs).
3. Six months later: 95% of orders have `status: "delivered"`. Only 0.1% are still "pending".
4. The cached plan still uses the `{ status: 1 }` index, but now the index has poor selectivity for "delivered".
5. A new index `{ status: 1, createdAt: -1 }` was added for a different feature — it would be perfect — but the cache is serving the old plan.

**Detection:**

```javascript
// Look for cache entries with poor performance
db.orders.getPlanCache().list()
// If "timeOfCreation" is months ago and the collection has grown significantly,
// stale cache entries may be causing suboptimal plans.

// Force re-planning a specific query shape
db.orders.getPlanCache().clearPlansByQuery({ status: "delivered" })
```

**Prevention strategies:**
- After significant data distribution changes (end of month, migrations), clear relevant plan cache entries.
- Use `$hint` to force a specific index when you know the optimal plan and the cache is selecting wrong.
- In MongoDB 7.0+, use Query Settings to pin a specific plan for a query shape.

### Layer 5: Production Reality — Plan Cache Storms

A plan cache storm occurs when:
1. Multiple cache entries are simultaneously invalidated (e.g., index rebuild)
2. Many concurrent queries arrive for shapes without cached plans
3. MongoDB runs multi-plan races for all of them simultaneously
4. The server becomes overwhelmed with planning overhead

**Symptoms:** CPU spike, latency spike, no obvious I/O increase. If index maintenance triggered the storm, it resolves once plans are re-cached.

**Mitigation:**
- Schedule index creation during low-traffic periods
- Use rolling index builds on secondaries to avoid primary plan cache invalidation
- In critical systems, use `$hint` on known-good queries to bypass the cache

---

## 2.5 The Execution Engines

### Classic Execution Engine

The traditional MongoDB query execution model used a tree of "cursor" objects. Each stage of query execution (IXSCAN, FETCH, SORT, etc.) was a cursor that pulled documents from its child cursor on demand. This is a **pull model** or **iterator model**.

```
SORT cursor.getNext() calls:
  → FETCH cursor.getNext() calls:
    → IXSCAN cursor.getNext() reads next index entry
    ← Returns (docId, doc)
  ← Returns fetched doc
← Returns sorted doc to caller
```

**Characteristics:**
- Simple conceptually; each stage operates independently
- Poor CPU efficiency: each `getNext()` call has overhead; tight loops are interrupted by function call boundaries
- Poor vectorization: processes one document at a time, preventing SIMD CPU optimization
- High function call stack depth for complex pipelines

### Slot-Based Execution Engine (SBE)

Introduced experimentally in MongoDB 5.1 and enabled by default for `find` queries in MongoDB 6.0, SBE is a fundamentally different approach inspired by modern relational database engines (similar to DuckDB's vectorized execution).

**Core concept:** Instead of cursors pulling documents one at a time, SBE processes documents in batches and passes values through typed "slots" — named memory locations that hold a column of values.

```
IXSCAN Stage:
  slot[keyVal]  = [ "pending", "pending", "pending", "shipped", ... ]  (1024 values)
  slot[recId]   = [ RecordId(5), RecordId(7), RecordId(12), ...      ]

FETCH Stage:
  Receives: slot[recId] batch
  Outputs: slot[doc] batch (full documents)

FILTER Stage:
  Evaluates: slot[doc.status] == "pending" for each slot element
  Outputs: filtered slot[doc] batch

RETURN Stage:
  Collects: slot[doc] results
```

**Why SBE is faster:**
1. **Batch processing** — amortizes function call overhead across 1024+ documents
2. **Type specialization** — SBE stages know the data type at compile time, enabling type-specific code paths
3. **CPU register usage** — slots fit in CPU cache; classic cursor values do not
4. **Compilation** — SBE plans are compiled into an efficient execution tree at plan time, not evaluated dynamically

**Benchmarks (approximate, workload dependent):**
- Simple `find()` with index: 10–30% faster with SBE
- `find()` with complex expressions: 20–50% faster
- Sort-heavy queries: up to 2x faster
- Aggregation pipelines: SBE support is expanding in MongoDB 6.x and 7.x

### Checking Which Engine Executed Your Query

```javascript
db.orders.find({ status: "pending" }).explain("executionStats")

// In the output, look for:
// "queryFramework": "sbe"    ← Slot-Based Execution Engine used
// "queryFramework": "classic" ← Classic engine used
```

**When SBE is NOT used (as of MongoDB 7.0):**
- Queries using `$text` search
- Queries on views
- Some complex aggregation stages not yet ported
- When explicitly disabled via `internalQueryFrameworkControl` parameter

---

## 2.6 A Complete Query Walk-Through

### Example: A Real Query Traced Through All Stages

**Setup:**

```javascript
// Collection: orders (1,000,000 documents)
// Indexes:
//   { customerId: 1 }
//   { status: 1, createdAt: -1 }

// Query:
db.orders.find(
  { customerId: "CUST-4521", status: "pending" },
  { orderId: 1, amount: 1, createdAt: 1, _id: 0 }
).sort({ createdAt: -1 })
```

**Stage-by-stage trace:**

**① Parsing & Canonicalization:**
```
BSON deserialized → 
Canonical shape: { customerId: <string>, status: <string> }
Sort key: { createdAt: -1 }
Projection: { orderId: 1, amount: 1, createdAt: 1, _id: 0 }
```

**② Plan Cache Lookup:**
```
Cache key: shape{ customerId:<s>, status:<s> } + sort{ createdAt:-1 }
Result: MISS (first time this query runs)
→ Proceed to candidate plan generation
```

**③ Candidate Plan Generation:**
```
Evaluate all indexes:
  Index A: { customerId: 1 }
    → Matches filter prefix (customerId). Sort NOT covered.
    → Plan A: IXSCAN(customerId) → FETCH → SORT(createdAt)
    
  Index B: { status: 1, createdAt: -1 }
    → Matches filter prefix (status). Sort covered.
    → Plan B: IXSCAN(status, createdAt) → FETCH
    → (But customer filter applied post-index: potentially poor selectivity)
    
  COLLSCAN:
    → Plan C: COLLSCAN → SORT → FILTER
```

**④ Multi-Plan Race:**
```
Plan A executes:
  - IXSCAN on customerId="CUST-4521" → finds ~50 RecordIds
  - FETCH 50 documents
  - SORT by createdAt (small sort, in-memory, fast)
  - Returns 50 documents → reaches 101-doc limit? No (only 50 pending for this customer)
  - But finishes fast → WINNER

Plan B executes:
  - IXSCAN on status="pending" → potentially millions of entries
  - Has not reached 101 results before Plan A finishes
  - ELIMINATED

Plan C: never competitive
```

**⑤ Winner Cached:**
```
Plan A (IXSCAN on customerId) cached for query shape
```

**⑥ Execution:**
```
IXSCAN: traverse index { customerId: 1 } for "CUST-4521"
  → Yields RecordIds: [5, 23, 78, 234, ...] (~50 total)
FETCH: load 50 full documents from WiredTiger
SORT: sort 50 documents by createdAt descending (tiny, fast)
PROJECTION: apply { orderId:1, amount:1, createdAt:1, _id:0 }
RETURN: send ~50 results to client
```

**⑦ Execution Stats (via explain):**
```json
{
  "executionTimeMillis": 2,
  "totalKeysExamined": 50,
  "totalDocsExamined": 50,
  "nReturned": 12
}
```

This is an efficient plan: keys examined ≈ docs examined ≈ docs returned.

---

## 2.7 What "Efficient" Looks Like vs. What "Inefficient" Looks Like

| Metric | Efficient | Warning | Inefficient |
| :--- | :--- | :--- | :--- |
| `totalKeysExamined / nReturned` | ≈ 1:1 | < 10:1 | > 100:1 |
| `totalDocsExamined / nReturned` | ≈ 1:1 | < 10:1 | > 100:1 |
| Stage tree | IXSCAN → (FETCH) → LIMIT | IXSCAN → SORT → LIMIT | COLLSCAN → SORT |
| `executionTimeMillis` | < 10ms | 10–100ms | > 100ms (or 1s+) |

---

## 2.8 Exercises

### Exercise 2.1: Plan Prediction
Given these indexes on a `products` collection:
- `{ category: 1 }`
- `{ price: 1 }`
- `{ category: 1, price: 1 }`

Predict which candidate plans MongoDB generates for:
```javascript
db.products.find({ category: "electronics", price: { $lt: 200 } }).sort({ price: 1 })
```
Which plan likely wins the race? Why?

### Exercise 2.2: Cache Key Analysis
Which pairs of queries share a plan cache entry? Explain your reasoning.

```javascript
// A
db.users.find({ age: 25, city: "London" })
// B
db.users.find({ city: "Paris", age: 30 })
// C
db.users.find({ age: { $gt: 25 }, city: "London" })
// D
db.users.find({ $and: [{ city: "London" }, { age: 25 }] })
```

### Exercise 2.3: Engine Identification
Run the following and identify which execution engine was used and why:

```javascript
db.orders.find({ status: "pending" }).explain("executionStats")
```

Look for the `queryFramework` field. If it says "classic", investigate what feature might be preventing SBE adoption. What would you change?

---

## 2.9 Knowledge Check

1. What is query canonicalization and why is it important for the plan cache?
2. What three conditions can terminate the multi-plan race?
3. Name three events that invalidate the plan cache.
4. What is the key architectural difference between the classic engine and SBE?
5. Why might the plan cache hurt performance after significant data distribution changes?

---

## 2.10 Interview-Style Questions

**Q: MongoDB's query planner uses "experimental execution" to select plans instead of a cost-based model. What are the advantages and disadvantages of this approach compared to a traditional cost-based optimizer?**

> Model answer: Advantages — No dependence on accurate statistics, which are hard to maintain in schema-flexible systems; plans are selected based on actual runtime performance rather than estimates; works well even with skewed data distributions. Disadvantages — Planning itself has a real execution cost (wasted I/O); rare queries are always re-planned; statistics-based optimizers can explore more plan combinations theoretically; large numbers of candidate indexes increase planning overhead linearly.

**Q: You notice in production that a query is running slowly even though it has a cached plan. The `explain()` output shows it is using the right index. What might be happening?**

> Model answer: Data distribution may have changed since the plan was cached. The index may have been optimal when the plan was stored but is now scanning many more entries. Other possibilities: lock contention causing waits not visible in explain; WiredTiger cache pressure causing index pages to be read from disk; a background index rebuild invalidated the cache and the new winning plan is suboptimal. The solution is to check `executionStats` for high `keysExamined/nReturned` ratio, examine `$currentOp` for lock waits, and monitor WiredTiger cache metrics.

---

*Next: [Module 03: Understanding Explain Plans →](03-understanding-explain-plans.md)*
