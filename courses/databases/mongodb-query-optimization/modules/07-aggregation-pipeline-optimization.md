# Module 07: Aggregation Pipeline Optimization

**Difficulty:** Advanced
**Estimated Study Time:** 7 hours
**Prerequisites:** Modules 01–06

---

## Learning Objectives

By the end of this module you will be able to:
- Trace how MongoDB executes each aggregation pipeline stage internally
- Apply pipeline ordering rules to push computation earlier and reduce data volume
- Design pipelines that leverage indexes via `$match` pushdown
- Control and monitor memory usage in aggregation pipelines
- Recognize expensive anti-patterns in pipelines and rewrite them efficiently
- Optimize `$lookup`, `$unwind`, `$group`, and `$facet` stages specifically

---

## 7.1 How Aggregation Pipelines Execute

### Layer 1: Intuition

An aggregation pipeline is like a factory assembly line. Raw materials (documents) enter at one end. Each station (stage) transforms them. Finished products (results) exit the other end.

The key insight: **minimizing material at each station reduces total work**. If you can cut 90% of documents at the first station, every subsequent station processes 10x fewer documents.

### Layer 2: Pipeline Execution Model

```
Document stream →  [$match] → [$project] → [$group] → [$sort] → [$limit] → Results

Stage 1 ($match):
  Input:  All 1,000,000 documents
  Output: 10,000 documents matching filter

Stage 2 ($project):
  Input:  10,000 documents
  Output: 10,000 documents (smaller — only needed fields)

Stage 3 ($group):
  Input:  10,000 documents
  Output: 50 groups (one per category)

Stage 4 ($sort):
  Input:  50 groups
  Output: 50 sorted groups (tiny sort)

Stage 5 ($limit):
  Input:  50 sorted groups
  Output: 10 groups
```

**Compare to bad ordering:**

```
Document stream →  [$group] → [$match] → [$sort] → [$limit] → Results

Stage 1 ($group):
  Input:  ALL 1,000,000 documents (no early filtering!)
  Output: 50 groups

Stage 2 ($match):
  Input:  50 groups
  Output: 10 groups matching filter

→ Group stage processed 1,000,000 documents unnecessarily
→ All intermediate group data consumed memory (potential disk spill)
```

### Layer 3: The MongoDB Pipeline Optimizer

MongoDB's aggregation optimizer automatically applies some reordering rules:

```javascript
// Original pipeline:
[
  { $sort: { createdAt: -1 } },
  { $match: { status: "pending" } },
  { $limit: 10 }
]

// After automatic optimization:
[
  { $match: { status: "pending" } },  // Moved before $sort
  { $sort: { createdAt: -1 } },
  { $limit: 10 }
]
// Also: $sort + $limit collapse into a "top-K" sort (only keeps K elements)
```

**But do not rely on the optimizer.** Write pipelines in the optimal order yourself. The optimizer handles basic cases; it will not restructure complex pipelines or identify semantic issues.

---

## 7.2 `$match`: The Critical First Stage

### Rule #1: Always `$match` First

```javascript
// ❌ Anti-pattern: $group before $match
db.orders.aggregate([
  { $group: { _id: "$customerId", total: { $sum: "$amount" } } },
  { $match: { total: { $gt: 1000 } } }  // Filter after expensive grouping
])

// ✅ Correct: $match first when the filter applies to raw documents
db.orders.aggregate([
  { $match: { status: "completed" } },    // Remove non-completed orders first
  { $group: { _id: "$customerId", total: { $sum: "$amount" } } },
  { $match: { total: { $gt: 1000 } } }    // Then filter groups by total
])
// Note: The second $match (on accumulated fields) MUST come after $group
// The first $match (on raw document fields) MUST come before
```

### Rule #2: `$match` Can Use Indexes — Make It Happen

When `$match` is the first stage of a pipeline, it behaves like a `find()` filter — it can use indexes:

```javascript
// This $match can use an index on { status: 1, createdAt: 1 }:
db.orders.aggregate([
  { $match: {
    status: "pending",
    createdAt: { $gte: ISODate("2024-01-01") }
  }},
  { $group: { _id: "$region", total: { $sum: "$amount" } } }
])
// explain() will show IXSCAN in the first stage

// Verify:
db.orders.explain("executionStats").aggregate([
  { $match: { status: "pending", createdAt: { $gte: ISODate("2024-01-01") } } },
  { $group: { _id: "$region", total: { $sum: "$amount" } } }
])
// Look for: winningPlan.stage == "IXSCAN" (not COLLSCAN)
```

**Critical rule:** The first `$match` stage in a pipeline can use collection indexes. Stages after `$group`, `$unwind`, or other transformations cannot use collection indexes — they operate on derived intermediate results.

### Rule #3: Split `$match` Across the Pipeline

```javascript
// Document fields available for matching before and after different stages
db.orders.aggregate([
  { $match: { status: "pending" } },          // Uses index — filter on raw docs
  { $lookup: {
    from: "customers",
    localField: "customerId",
    foreignField: "_id",
    as: "customer"
  }},
  { $match: { "customer.country": "US" } },   // Filter on joined customer data
  { $group: { _id: "$region", total: { $sum: "$amount" } } },
  { $match: { total: { $gt: 5000 } } }        // Filter on accumulated data
])
// Three $match stages in different positions, each appropriate to its data context
```

---

## 7.3 `$project` and `$addFields`: Field Management

### Reduce Document Size Early

After `$match`, reduce document size with `$project` to remove fields that subsequent stages don't need:

```javascript
// Without early projection:
db.orders.aggregate([
  { $match: { status: "pending" } },
  // Documents still have all 30 fields including large metadata
  { $group: { _id: "$region", count: { $sum: 1 }, total: { $sum: "$amount" } } }
  // $group only uses region and amount but carries 30 fields through
])

// With early projection:
db.orders.aggregate([
  { $match: { status: "pending" } },
  { $project: { region: 1, amount: 1, _id: 0 } },  // Only 2 fields now
  { $group: { _id: "$region", count: { $sum: 1 }, total: { $sum: "$amount" } } }
])
// Each document flowing into $group is much smaller → less memory consumed
```

**When early projection helps most:**
- Documents are large (> 1KB per document)
- Many stages follow the projection
- `$group` or `$sort` stages are memory-intensive

**When early projection hurts:** If you project aggressively but a later stage needs fields you removed, you will need to re-fetch data (possibly with another `$lookup`) — worse than not projecting.

### `$project` vs. `$addFields` vs. `$set`

```javascript
// $project: explicitly list ALL fields to keep (default: exclude all not listed)
{ $project: { name: 1, email: 1, score: 1 } }

// $addFields ($set is an alias): ADD or OVERWRITE fields, keep everything else
{ $addFields: { totalWithTax: { $multiply: ["$total", 1.1] } } }
// Keeps all original fields and adds totalWithTax

// Use $project when you want to reshape/slim the document
// Use $addFields/$set when you want to augment the document while keeping existing fields
```

---

## 7.4 `$group`: Aggregation and Memory Management

### Layer 2: Internal Mechanics

`$group` maintains an in-memory hash table keyed by the `_id` expression. For each input document:
1. Compute the group key (`_id` expression value)
2. Look up or create the group entry in the hash table
3. Apply accumulator expressions (`$sum`, `$avg`, `$push`, etc.) to update the group entry

**Memory consumption:**
- Number of groups × size per group entry
- `$push` and `$addToSet` accumulate arrays — each element added grows the entry

```javascript
// Memory-safe: Scalar accumulators
{ $group: { _id: "$category", total: { $sum: "$amount" }, count: { $sum: 1 } } }
// Each group entry: { _id: str, total: number, count: number } ≈ small

// Memory-dangerous: $push accumulates entire documents
{ $group: { _id: "$category", allOrders: { $push: "$$ROOT" } } }
// Each group entry grows without bound — can consume gigabytes for large groups!
```

### Memory Limit and Disk Spill

```javascript
// Default: 100MB memory limit for $group stage
// When exceeded, MongoDB can spill to disk (allowDiskUse)

db.orders.aggregate(
  [
    { $group: { _id: "$customerId", orders: { $push: "$$ROOT" } } }
  ],
  { allowDiskUse: true }    // Enable disk spill for large pipelines
)
// Performance with disk spill: 10-100x slower than in-memory
// This is a last resort, not a solution
```

**Preferred approach over `$push` for large collections:**

```javascript
// Anti-pattern: Push all matching documents into an array
{ $group: { _id: "$category", items: { $push: "$$ROOT" } } }

// Alternative 1: Only push needed fields (not $$ROOT)
{ $group: { _id: "$category", skus: { $push: "$sku" } } }

// Alternative 2: Count instead of collect
{ $group: { _id: "$category", count: { $sum: 1 }, totalSales: { $sum: "$amount" } } }

// Alternative 3: If you need all documents per group, process in application
// (query per group separately — "N+1" problem, but controlled)
```

### Index-Backed Optimization with `$group`

For certain `$group` patterns, MongoDB can use a `DISTINCT_SCAN` instead of a full COLLSCAN/IXSCAN:

```javascript
// If you just want distinct values of a field:
db.orders.aggregate([
  { $group: { _id: "$status" } }
])
// With index { status: 1 }, MongoDB uses DISTINCT_SCAN:
// → Jumps between distinct status values in the index
// → Reads only one entry per distinct value (instead of all matching documents)
// → Extremely fast for low-cardinality fields

// Verify:
db.orders.explain().aggregate([{ $group: { _id: "$status" } }])
// Look for: "stage": "DISTINCT_SCAN"
```

---

## 7.5 `$sort`: Index and Memory

### Sort with Index (Optimal)

If `$sort` immediately follows `$match` in the pipeline, and there is an index on the sort fields, MongoDB can use the index order:

```javascript
// Pipeline:
db.orders.aggregate([
  { $match: { region: "us-east" } },
  { $sort: { createdAt: -1 } },
  { $limit: 20 }
])

// Index { region: 1, createdAt: -1 }:
// → $match → $sort uses index order → $limit short-circuits after 20 docs
// No in-memory sort! Extremely efficient.
```

### Sort Cascade Optimization

`$sort` followed by `$limit` is automatically optimized into a "top-K" algorithm:

```javascript
// Original:
{ $sort: { score: -1 } },
{ $limit: 10 }

// Internally: MongoDB maintains a min-heap of size K=10.
// As documents arrive, if they are in the top-K, they replace the minimum.
// Result: O(N log K) instead of O(N log N) for a full sort.
// For K=10 and N=1,000,000: 10M log 10 ≈ 33M ops vs 20M log 1M ≈ 400M ops
```

**The critical optimization: Apply `$limit` immediately after `$sort` in your pipeline.**

```javascript
// ❌ Bad: $limit far from $sort
db.posts.aggregate([
  { $sort: { views: -1 } },
  { $addFields: { rank: { $rank: {} } } },  // Some transformation
  { $limit: 10 }

// ✅ Good: $limit immediately after $sort
db.posts.aggregate([
  { $sort: { views: -1 } },
  { $limit: 10 },
  { $addFields: { rank: { $rank: {} } } }
])
// Sort only 10 documents through subsequent stages
```

---

## 7.6 `$lookup`: The Most Expensive Stage

### Layer 1: Intuition

`$lookup` is MongoDB's JOIN operator. Every JOIN is expensive in any database because it must correlate data from two collections. Unlike SQL optimizers that automatically choose join strategies, MongoDB's `$lookup` places the join burden directly on the developer.

### Layer 2: How `$lookup` Executes Internally

**For each document in the pipeline stream:**
1. Read the local join field value from the current document
2. Query the foreign collection for matching documents
3. Attach the matched documents as an array field

This is a **nested loop join** — the default and most naive join strategy.

**Time complexity: O(N × M)** where N = pipeline documents, M = foreign collection size (without index on foreign field)

**With index on the foreign join field:** O(N × log M) — each foreign lookup is an indexed point query.

```javascript
// Always ensure the foreign field is indexed!
db.orders.aggregate([
  { $match: { status: "pending" } },
  { $lookup: {
    from: "customers",
    localField: "customerId",      // local field
    foreignField: "_id",           // MUST be indexed on the "customers" collection
    as: "customerInfo"
  }}
])

// Verify customers has an index on _id (it always does — it's the primary key)
// For non-_id foreign fields:
db.orders.createIndex({ customerId: 1 })   // For the reverse direction
db.customers.createIndex({ email: 1 })    // If joining on email
```

### Layer 3: Pipeline `$lookup` (More Efficient)

The pipeline form of `$lookup` allows pushing a `$match` into the lookup subquery — enabling index use in the foreign collection and reducing matched documents:

```javascript
// Standard form (no filtering in lookup):
{ $lookup: {
  from: "orders",
  localField: "_id",
  foreignField: "customerId",
  as: "orders"
}}
// Fetches ALL orders for each customer — potentially thousands per customer!

// Pipeline form with filtering:
{ $lookup: {
  from: "orders",
  let: { custId: "$_id" },
  pipeline: [
    { $match: {
      $expr: { $eq: ["$customerId", "$$custId"] },  // Join condition
      status: "pending"                              // Additional filter!
    }},
    { $project: { amount: 1, createdAt: 1, _id: 0 } }  // Minimize returned fields
  ],
  as: "pendingOrders"
}}
// Only fetches pending orders and only selected fields — much less data
```

**The pipeline `$lookup` is almost always preferable** because you can:
- Add `$match` to filter before returning (index usage on foreign collection)
- Add `$project` to reduce field sizes
- Add `$limit` to cap results per lookup
- Add `$sort` to order results

### Layer 4: `$lookup` Performance Anti-Patterns

**Anti-pattern 1: Large $lookup without limit**

```javascript
// Customer with 50,000 orders → $lookup returns 50,000-element array per customer
{ $lookup: { from: "orders", localField: "_id", foreignField: "customerId", as: "orders" } }
// If 1,000 customers × 50,000 orders = 50 million document loads
// NEVER do unbounded lookups on large collections
```

**Anti-pattern 2: $lookup after expensive processing**

```javascript
// Anti-pattern: Join after group
db.orders.aggregate([
  { $group: { _id: "$customerId", total: { $sum: "$amount" } } },
  { $lookup: { from: "customers", localField: "_id", foreignField: "_id", as: "customer" } }
])
// $group produces N groups, then $lookup queries for each group
// Better: Join before group when possible, or minimize group output first
```

**Anti-pattern 3: Correlated $lookup in $facet**

```javascript
// $facet runs multiple sub-pipelines — each sub-pipeline gets the same input documents
// If each sub-pipeline has a $lookup, the lookup runs once per facet branch
// Keep $facet stages cheap (counts, ranges) not expensive (joins)
```

### Alternative: `$graphLookup` for Recursive Joins

```javascript
// Traverse organizational hierarchy:
db.employees.aggregate([
  { $match: { _id: "CEO" } },
  { $graphLookup: {
    from: "employees",
    startWith: "$_id",
    connectFromField: "_id",
    connectToField: "managerId",
    as: "subordinates",
    maxDepth: 5,              // ALWAYS set a maxDepth to prevent infinite traversal
    depthField: "level"
  }}
])
```

**Performance:** `$graphLookup` is expensive by nature. Every level of traversal requires additional queries to the foreign collection. Always:
1. Set `maxDepth`
2. Use an index on `connectToField`
3. Limit the starting set with `$match` before `$graphLookup`

---

## 7.7 `$unwind`: Arrays Become Rows

### What `$unwind` Does

`$unwind` decomposes an array field, creating one output document per array element:

```javascript
// Input document:
{ orderId: "ORD-1", items: [{ sku: "A", qty: 2 }, { sku: "B", qty: 1 }] }

// After $unwind: { path: "$items" }:
{ orderId: "ORD-1", items: { sku: "A", qty: 2 } }
{ orderId: "ORD-1", items: { sku: "B", qty: 1 } }
// One document per item
```

### Performance Implications

`$unwind` multiplies the number of documents by the average array size:

```
1M orders × avg 5 items per order → 5M documents after $unwind
```

**This dramatically increases the data volume flowing through subsequent stages.** Place `$unwind` as late as possible, and follow it immediately with `$match` or `$group` to reduce the document count again:

```javascript
// ❌ Bad order: unwind then filter
db.orders.aggregate([
  { $unwind: "$items" },           // 5M documents
  { $match: { "items.sku": "SKU-001" } }  // Now filter: expensive
])

// ✅ Better: filter before unwind when possible
db.orders.aggregate([
  { $match: { "items.sku": "SKU-001" } },  // Match orders containing this SKU (using multikey index)
  { $unwind: "$items" },                    // Unwind only matching orders
  { $match: { "items.sku": "SKU-001" } }   // Filter to only the matching item
])
// Note: First $match filters at order level (multikey), second $match filters at item level
```

### `preserveNullAndEmptyArrays`

```javascript
{ $unwind: { path: "$items", preserveNullAndEmptyArrays: true } }
// Without this option, documents with null/missing/empty items array are DROPPED
// With this option, they are kept with items: null
// Performance implication: keeping these documents adds to the output stream
```

---

## 7.8 `$facet`: Parallel Sub-Pipelines

### What `$facet` Does

`$facet` executes multiple aggregation sub-pipelines on the same input documents, returning their results as a single output document. This is used for building faceted search results (e.g., "Showing 150 results — Filter by: Category [Electronics 45, Clothing 32...], Price [$0-$50: 20, $50-$100: 45...]").

```javascript
db.products.aggregate([
  { $match: { inStock: true } },     // Common filter applied once
  { $facet: {
    "byCategory": [
      { $group: { _id: "$category", count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ],
    "byPriceRange": [
      { $bucket: { groupBy: "$price", boundaries: [0, 50, 100, 200, 500], default: "Other" } }
    ],
    "total": [
      { $count: "totalCount" }
    ]
  }}
])
```

### Performance Considerations

- The input to `$facet` is computed ONCE (the `$match` result)
- Each sub-pipeline processes the same input independently
- Total memory = sum of all sub-pipeline memory usage
- `$facet` cannot use indexes internally — it operates on the pipeline's intermediate results

**Keep `$facet` sub-pipelines lightweight:**

```javascript
// ❌ Expensive facet: joining data inside a facet branch
{ $facet: {
  "withDetails": [
    { $lookup: { from: "categories", ... } }  // Join inside facet = inefficient
  ]
}}

// ✅ Efficient facet: only counting and bucketing
{ $facet: {
  "byCategory": [{ $group: { _id: "$category", count: { $sum: 1 } } }],
  "byPrice": [{ $bucket: { ... } }]
}}
```

---

## 7.9 `$merge` and `$out`: Writing Pipeline Results

### `$out`: Atomic Replace

```javascript
// Writes pipeline results to a new collection, replacing it atomically
db.orders.aggregate([
  { $match: { status: "completed" } },
  { $group: { _id: "$region", revenue: { $sum: "$amount" } } },
  { $out: "regional_revenue_summary" }  // Replace the entire collection
])
// Use case: nightly report materialization
// Limitation: Drops and replaces the target collection atomically
```

### `$merge`: Flexible Upsert (MongoDB 4.2+)

```javascript
// Merges results into an existing collection
db.orders.aggregate([
  { $match: { createdAt: { $gte: today } } },
  { $group: { _id: "$region", todayRevenue: { $sum: "$amount" } } },
  { $merge: {
    into: "regional_revenue_summary",
    on: "_id",                      // Match key
    whenMatched: "merge",           // Update existing: merge fields
    whenNotMatched: "insert"        // Insert new
  }}
])
// Use case: incremental updates to summary collections
// Much better than $out for real-time rollup patterns
```

---

## 7.10 Pipeline Optimization Checklist

Apply these checks to every pipeline you write:

```
□ 1. Does $match come first? Can it use an index? (verify with explain)
□ 2. Are there unnecessary fields flowing through stages? Add $project after $match
□ 3. Is $unwind followed immediately by $match or $group to reduce document count?
□ 4. Is $sort followed immediately by $limit?
□ 5. Does $lookup have an index on the foreign field?
□ 6. Is the $lookup pipeline form used to add filtering/projection to the subquery?
□ 7. Does any $group stage use $push or $addToSet without bound? (memory risk)
□ 8. Is allowDiskUse: true required? If so, is that acceptable (it's slow)?
□ 9. Are $facet sub-pipelines cheap (no joins, no sorts on large sets)?
□ 10. Has the pipeline been validated with explain("executionStats") for the first stage?
```

---

## 7.11 Production Example: Optimizing a Slow Analytics Pipeline

**Original slow pipeline (3 seconds):**

```javascript
db.events.aggregate([
  { $lookup: {
    from: "users",
    localField: "userId",
    foreignField: "_id",
    as: "user"
  }},
  { $unwind: "$user" },
  { $match: {
    "user.country": "US",
    eventType: "purchase",
    timestamp: { $gte: ISODate("2024-01-01") }
  }},
  { $group: {
    _id: { month: { $month: "$timestamp" }, product: "$productId" },
    revenue: { $sum: "$amount" },
    buyers: { $addToSet: "$userId" }
  }},
  { $sort: { revenue: -1 } },
  { $limit: 20 }
])
```

**Problems identified:**
1. `$lookup` is the first stage — joins ALL events with ALL users before filtering
2. `$match` comes after `$unwind` and `$lookup` — cannot use indexes
3. `$addToSet: "$userId"` accumulates all buyer IDs per group — memory danger
4. No `$limit` between `$sort` and preceding stages

**Optimized pipeline:**

```javascript
db.events.aggregate([
  // Stage 1: Filter events FIRST (uses index { eventType: 1, timestamp: 1 })
  { $match: {
    eventType: "purchase",
    timestamp: { $gte: ISODate("2024-01-01") }
  }},

  // Stage 2: Project only needed fields to reduce document size
  { $project: {
    userId: 1,
    productId: 1,
    amount: 1,
    timestamp: 1,
    _id: 0
  }},

  // Stage 3: Lookup only for matched events (now a much smaller set)
  { $lookup: {
    from: "users",
    let: { uid: "$userId" },
    pipeline: [
      { $match: { $expr: { $eq: ["$_id", "$$uid"] } } },
      { $project: { country: 1, _id: 0 } }  // Only need country
    ],
    as: "user"
  }},
  { $unwind: "$user" },

  // Stage 4: Filter by user country AFTER lookup (no alternative)
  { $match: { "user.country": "US" } },

  // Stage 5: Group — use $sum instead of $addToSet for buyer count
  { $group: {
    _id: { month: { $month: "$timestamp" }, product: "$productId" },
    revenue: { $sum: "$amount" },
    buyerCount: { $sum: 1 }  // Count instead of collecting IDs
    // If unique buyer count is required: consider $accumulator or pre-deduplicated data
  }},

  { $sort: { revenue: -1 } },
  { $limit: 20 }
])
```

**Expected improvement:** 3s → ~150ms (20x improvement from early filtering and projection)

---

## 7.12 Exercises

### Exercise 7.1: Pipeline Reordering

Reorder this pipeline for maximum efficiency and explain each change:

```javascript
db.orders.aggregate([
  { $project: { customerId: 1, amount: 1, region: 1, status: 1 } },
  { $sort: { amount: -1 } },
  { $group: { _id: "$region", topOrders: { $push: "$$ROOT" } } },
  { $match: { status: "completed" } },
  { $limit: 5 }
])
```

### Exercise 7.2: $lookup Optimization

The following pipeline runs in 8 seconds. Identify the performance problem and rewrite it:

```javascript
db.posts.aggregate([
  { $lookup: {
    from: "comments",
    localField: "_id",
    foreignField: "postId",
    as: "comments"
  }},
  { $addFields: { commentCount: { $size: "$comments" } } },
  { $match: { commentCount: { $gt: 10 }, category: "technology" } },
  { $sort: { commentCount: -1 } },
  { $limit: 10 }
])
```

### Exercise 7.3: Memory Management

This pipeline fails with "exceeded memory limit" on a 5M document collection:

```javascript
db.purchases.aggregate([
  { $group: {
    _id: "$productId",
    buyers: { $push: "$customerId" }
  }},
  { $project: {
    productId: "$_id",
    uniqueBuyerCount: { $size: { $setUnion: ["$buyers", []] } }
  }}
])
```

Rewrite it to eliminate memory issues while still computing unique buyer counts.

---

## 7.13 Knowledge Check

1. Why should `$match` appear as the first stage in most pipelines?
2. What is the difference between `$project` and `$addFields`?
3. What optimization does MongoDB apply when `$sort` is followed by `$limit`?
4. How does `$lookup` execute internally? Why must the foreign field be indexed?
5. What does `$unwind` do to document count? Why is that a performance concern?
6. What is the `allowDiskUse` option and when should it be used?

---

## 7.14 Interview-Style Questions

**Q: Your analytics pipeline runs in 45 seconds. The first step tells you it is spending most time in a `$group` stage with `$push`. How do you approach this?**

> Model answer: `$push` accumulates entire documents (or sub-documents) per group, consuming memory proportional to all matched documents × their size. At scale this almost certainly causes disk spill. First, check `allowDiskUse` — if set to true, spill is happening. Solutions in order of preference: (1) Replace `$push: "$$ROOT"` with `$push` of only the needed fields, reducing per-element size. (2) Replace `$push` with scalar accumulators (`$sum`, `$avg`, `$count`) if you can compute what you need without collecting all documents. (3) If you genuinely need all documents per group (rare), consider running one query per group at the application level rather than accumulating them all. (4) Pre-aggregate into summary collections with `$merge` so the pipeline starts from smaller summary documents rather than raw events.

**Q: When would you choose schema denormalization over a `$lookup` join for a frequently-accessed user profile display?**

> Model answer: When `$lookup` is too expensive. If the user profile page is served to 10,000 users/second and each page requires joining user → subscription plan → company profile (3 collections), each request triggers 2–3 `$lookup` operations. Even with indexes, 20,000–30,000 index lookups per second is significant load. If the joined data is relatively stable (company name, subscription tier), denormalize it into the user document. Accept the update complexity: when the company name changes, run an `updateMany` to propagate the change. This trades write complexity for read simplicity. The decision depends on the read/write ratio — if reads are 1000:1 to writes, denormalization wins almost always.

---

*Next: [Module 08: Advanced Optimization Techniques →](08-advanced-optimization-techniques.md)*
