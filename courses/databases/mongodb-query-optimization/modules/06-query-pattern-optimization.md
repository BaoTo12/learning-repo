# Module 06: Query Pattern Optimization

**Difficulty:** Intermediate–Advanced
**Estimated Study Time:** 5 hours
**Prerequisites:** Modules 01–05

---

## Learning Objectives

By the end of this module you will be able to:
- Optimize equality, range, sort, and combined queries using appropriate indexes
- Explain the offset pagination problem and implement cursor-based pagination correctly
- Design covered queries that eliminate document fetches
- Write efficient aggregation queries that leverage push-down optimizations
- Avoid common query anti-patterns that degrade performance at scale

---

## 6.1 Equality Query Optimization

### Layer 1: Intuition

An equality query (`{ field: value }`) is the simplest MongoDB query. With the right index, it should execute in O(log N) time, returning only matching documents. Without an index, it degrades to O(N) — scanning every document.

### Layer 2: Mechanics

```javascript
// Simple equality:
db.users.find({ email: "alice@example.com" })

// Without index: COLLSCAN of all users
// With index { email: 1 }: 
//   1. Navigate B-tree to "alice@example.com" leaf (3-4 I/Os)
//   2. Return RecordId(s) → FETCH document(s)
//   Total: ~5 I/Os regardless of collection size
```

### Layer 3: Multi-Equality Queries

When a query filters on multiple fields with equality, design the compound index with **higher-cardinality (more selective) fields first** (see Module 05):

```javascript
// Query: { region: "us-east", status: "active", plan: "premium" }
// Cardinalities: region=4, status=3, plan=5
// All are low-cardinality — but together they narrow well

// Not ideal (most common first):
db.users.createIndex({ status: 1, region: 1, plan: 1 })
// IXSCAN: first seeks to "active" (50% of users), then filters region/plan

// Better (any order for low-cardinality equalities, but measure!):
db.users.createIndex({ plan: 1, region: 1, status: 1 })

// Validate with explain:
db.users.find({ region: "us-east", status: "active", plan: "premium" }).explain("executionStats")
// Check totalKeysExamined vs nReturned
```

### Layer 4: The `$in` Operator

`$in` is treated as a set of equality checks. MongoDB executes it as multiple point lookups on the index:

```javascript
db.orders.find({ status: { $in: ["pending", "confirmed"] } })
// Index { status: 1 } → two B-tree point lookups, results merged
// For ESR purposes: treat $in as equality
```

**Performance consideration:** Large `$in` arrays (hundreds of values) degrade performance because each value requires a separate B-tree seek. For `$in` with > 50 values, consider whether a range query or aggregation approach is more efficient.

---

## 6.2 Range Query Optimization

### Layer 1: Intuition

Range queries scan a contiguous section of an index. Their performance depends critically on:
1. How much of the index they scan (the "range width")
2. Whether they appear after equality/sort fields in the index (ESR compliance)

### Layer 2: Range Query Examples

```javascript
// Date range (common in time-series):
db.orders.find({ createdAt: { $gte: ISODate("2024-01-01"), $lt: ISODate("2024-02-01") } })
// Index { createdAt: 1 }: efficient range scan of one month

// Numeric range:
db.products.find({ price: { $gte: 50, $lte: 200 } })
// Index { price: 1 }: scans price entries from 50 to 200

// Combined filter and range:
db.orders.find({ status: "pending", createdAt: { $gte: yesterday } })
// ESR-correct index: { status: 1, createdAt: 1 }
// Status = "pending" (equality), then scan dates from yesterday to now
```

### Layer 3: Range Width and Selectivity

A range query's efficiency depends on what fraction of the index it scans:

```javascript
// Highly selective range (good):
db.orders.find({ createdAt: { $gte: ISODate("2024-01-01T00:00:00Z"), 
                               $lt: ISODate("2024-01-01T00:01:00Z") } })
// 1-minute window in a year of data: very few documents, very selective

// Low-selectivity range (problematic):
db.orders.find({ amount: { $gt: 0 } })  // Everything has amount > 0 → COLLSCAN equivalent
// MongoDB might choose COLLSCAN over this index!
```

**Rule:** Range predicates that match > ~20–30% of a collection are often not worth indexing — MongoDB may prefer COLLSCAN which reads documents sequentially without index overhead.

### Layer 4: Compound Ranges

When filtering on multiple ranges simultaneously, only one range can use the index efficiently. The second range becomes a post-filter:

```javascript
// Query: Find orders between two dates AND within a price range
db.orders.find({ 
  createdAt: { $gte: start, $lt: end },
  amount: { $gte: 100, $lte: 500 }
})

// Index { createdAt: 1, amount: 1 }:
// - IXSCAN on createdAt range (contiguous scan of date range)
// - Within that range, entries are sorted by amount
// - amount filter is applied as a post-scan filter (not a range scan)
// - Only the first range field is used as the primary range scan

// If most orders are in the date range but only 5% have the right amount:
// → Amount filter works reasonably as post-scan
// If most orders have the right amount but only 5% are in the date range:
// → Date filter should be primary (comes first in index)

// Optimize by measuring actual filter selectivities in production
```

---

## 6.3 Sort Optimization

### Without Index Support: In-Memory SORT Stage

```javascript
// No index covering the sort:
db.orders.find({ region: "us-east" }).sort({ createdAt: -1 })
// Plan: IXSCAN(region) → FETCH → SORT(createdAt DESC)
// Problem: SORT must collect all matching documents, then sort them all in memory
// Memory limit: 100MB per sort operation
```

**The 100MB sort limit problem:**

```javascript
// If matched documents total > 100MB:
db.orders.find({ region: "us-east" }).sort({ createdAt: -1 }).explain("executionStats")
// executionStages.usedDisk: true  ← CRITICAL: sort spilled to disk
// Performance: 10-100x slower than in-memory sort
```

### With Index Support: Eliminating the SORT Stage

```javascript
// Create index that covers both filter and sort (ESR rule):
db.orders.createIndex({ region: 1, createdAt: -1 })

// Query:
db.orders.find({ region: "us-east" }).sort({ createdAt: -1 })
// Plan: IXSCAN(region=us-east, createdAt DESC) → FETCH
// No SORT stage! Documents come out of the IXSCAN pre-sorted.
```

**The LIMIT optimization:**

When LIMIT is combined with an index-based sort, MongoDB can stop IXSCAN as soon as LIMIT documents are returned:

```javascript
db.orders.find({ region: "us-east" }).sort({ createdAt: -1 }).limit(10)
// Without index sort: collect ALL us-east orders, sort all, take 10
// With index sort: take first 10 from IXSCAN → DONE
// For a collection with 1M orders in us-east:
//   Without: examines 1M documents
//   With:    examines 10 documents
```

---

## 6.4 Pagination Optimization

### The Offset Pagination Problem

Most developers start with offset-based pagination:

```javascript
// Page 1:
db.orders.find({ status: "pending" }).sort({ createdAt: -1 }).skip(0).limit(20)
// Page 2:
db.orders.find({ status: "pending" }).sort({ createdAt: -1 }).skip(20).limit(20)
// Page 100:
db.orders.find({ status: "pending" }).sort({ createdAt: -1 }).skip(1980).limit(20)
```

**The fatal flaw of `skip()`:**

```
skip(1980) means:
  1. Process first 1980 documents (sort them, then discard them)
  2. Return the next 20

As page number increases:
  skip(0)    → 0 documents discarded
  skip(200)  → 200 documents discarded
  skip(2000) → 2000 documents discarded
  skip(20000) → 20000 documents discarded ← Prohibitively expensive
```

This is the **deep pagination problem**. Performance degrades linearly as users page deeper. Page 1000 is 1000x more expensive than page 1.

### Cursor-Based Pagination (Keyset Pagination)

Instead of skipping records, cursor-based pagination uses a WHERE clause to start from the last seen document:

```javascript
// First page:
db.orders.find({ status: "pending" })
  .sort({ createdAt: -1, _id: -1 })  // _id as tiebreaker for stable ordering
  .limit(20)
// Returns 20 documents. Record the last document's values:
const lastDoc = results[results.length - 1];
const cursor = { createdAt: lastDoc.createdAt, _id: lastDoc._id };

// Next page — no SKIP!
db.orders.find({
  status: "pending",
  $or: [
    { createdAt: { $lt: cursor.createdAt } },
    { createdAt: cursor.createdAt, _id: { $lt: cursor._id } }
  ]
}).sort({ createdAt: -1, _id: -1 }).limit(20)
```

**Why this is efficient:**

```
Page 1:  IXSCAN 20 entries → FETCH 20 documents → Return
Page 2:  IXSCAN 20 entries from cursor position → FETCH 20 → Return
Page 100: IXSCAN 20 entries from cursor position → FETCH 20 → Return
```

Every page costs exactly the same regardless of depth. No documents are discarded.

**Required index:** The sort fields must form a compound index:

```javascript
// For sort { createdAt: -1, _id: -1 }:
db.orders.createIndex({ status: 1, createdAt: -1, _id: -1 })
// ESR: status (equality), createdAt (sort/range boundary), _id (tiebreaker)
```

### Limitations of Cursor-Based Pagination

1. **Cannot jump to arbitrary pages** — you cannot say "give me page 50" without traversing pages 1–49
2. **Cursor invalidation** — if documents are inserted or deleted between pages, the cursor boundary may skip or duplicate items
3. **Sorting** — the sort field must be in the cursor (and thus the index); changing sort requires a new cursor

**When to use which pagination:**

| Scenario | Approach |
| :--- | :--- |
| Sequential browsing (infinite scroll, next/previous) | Cursor-based |
| Arbitrary page jumps (search results) | Offset-based with depth limit |
| Admin reporting (few pages, not performance-critical) | Offset-based |
| Massive datasets (millions of records, deep pages) | Cursor-based (mandatory) |

### Adding a Total Count (Performance Trap)

```javascript
// Anti-pattern: counting for pagination display
const total = db.orders.countDocuments({ status: "pending" });
// This is a SEPARATE full collection scan!

// Better: Use a cached count updated by triggers or change streams
// Or: Use estimated count (approximate, fast):
db.orders.estimatedDocumentCount()  // Uses collection metadata, not a full scan

// Or: Accept that "showing results 1-20 of ~50,000" is good enough
```

---

## 6.5 Projection Optimization

### Why Projection Matters

By default, MongoDB returns entire documents. In a collection where documents average 10KB but the application only needs 3 fields (0.5KB), **95% of the data transferred is wasted**.

At 1,000 requests/second:
- Without projection: 10MB/s of wasted bandwidth
- At 10,000 requests/second: 100MB/s of wasted bandwidth

### How to Use Projection

```javascript
// Inclusion projection — specify fields to include:
db.users.find({}, { name: 1, email: 1, _id: 0 })
// Returns only name and email (no _id)

// Exclusion projection — specify fields to exclude:
db.users.find({}, { password: 0, secretToken: 0 })
// Returns everything EXCEPT password and secretToken
// Note: Cannot mix inclusions and exclusions (except _id)

// Projection on nested fields:
db.users.find({}, { "address.city": 1, "address.country": 1, _id: 0 })
```

### Designing for Covered Queries

A covered query eliminates the FETCH stage entirely. Design your index to include the projected fields:

```javascript
// Query:
db.orders.find(
  { customerId: "C1", status: "pending" },
  { orderId: 1, amount: 1, createdAt: 1, _id: 0 }
)

// Covered index (must include ALL projected fields):
db.orders.createIndex({ customerId: 1, status: 1, orderId: 1, amount: 1, createdAt: 1 })
// Filter fields: customerId, status (ESR equality)
// Projected fields: orderId, amount, createdAt (included in index)

// Verify: expect totalDocsExamined = 0 in explain
```

### Common Projection Mistakes

```javascript
// ❌ Mistake: Forgetting _id exclusion breaks coverage
db.orders.find(
  { customerId: "C1" },
  { orderId: 1, amount: 1 }  // _id is included by default!
)
// _id is NOT in our index above → forces FETCH to get _id → coverage broken
// Fix: add _id: 0 to projection OR include _id in the index

// ❌ Mistake: Projection on array elements requires full document
db.orders.find({}, { "items.sku": 1 })
// If items is an embedded array, MongoDB must FETCH the full document to project an array element
// Coverage is impossible for array field projections

// ❌ Mistake: Returning entire embedded documents when you need one field
db.users.find({}, { address: 1 })  // Returns full address subdocument (potentially large)
db.users.find({}, { "address.city": 1 })  // Better: return only city
```

---

## 6.6 Regex Query Optimization

### When Regex Uses an Index

```javascript
// ✅ Prefix regex: anchored at the start with no options
db.products.find({ sku: /^SKU-/ })
// Index { sku: 1 } can efficiently find all entries starting with "SKU-"
// This is equivalent to a range query: [SKU-, SKU-\uffff)

// ❌ Infix regex: contains pattern anywhere in string
db.products.find({ name: /performance/ })
// Cannot use B-tree index efficiently — must scan all entries

// ❌ Case-insensitive regex:
db.products.find({ name: /performance/i })
// Case-insensitive requires examining all entries regardless of anchor
```

**Rule:** Only anchored prefix regex (`/^prefix/`) can efficiently use a B-tree index. All other regex patterns trigger index scans or collection scans.

**Alternative for full-text search:** Use a text index with `$text` operator, or Atlas Search for production-grade full-text capabilities.

---

## 6.7 The `$or` Query Pattern

### How `$or` Uses Indexes

```javascript
// Each $or branch can use its own index:
db.orders.find({
  $or: [
    { customerId: "C1" },           // Can use { customerId: 1 } index
    { orderId: "ORD-12345" }        // Can use { orderId: 1 } index
  ]
})
// Plan: SUBPLAN (each branch evaluated separately, results merged)
```

### The `$or` Performance Trap

`$or` is expensive because:
1. Each branch requires a separate IXSCAN + FETCH
2. Results must be de-duplicated (a document matching both branches should appear once)
3. Sorting across merged result sets requires an in-memory sort

**Anti-pattern:**

```javascript
// Developer wants to find "important" customers:
db.users.find({
  $or: [
    { plan: "enterprise" },
    { plan: "premium" },
    { totalSpend: { $gt: 10000 } }
  ]
})
// Three separate index scans, de-duplication, then filter — expensive

// Better: Use $in for same-field cases:
db.users.find({ plan: { $in: ["enterprise", "premium"] } })
// Single IXSCAN on { plan: 1 } with two point lookups

// Cannot easily replace the $or that spans different fields
// Consider: materialized "tier" field updated asynchronously
// db.users.find({ tier: "high-value" })
// Supported by: db.users.createIndex({ tier: 1 })
```

---

## 6.8 `$exists` and `$type` Query Optimization

### `$exists` Performance

```javascript
// $exists: true with a regular index:
db.orders.find({ deliveredAt: { $exists: true } })
// Regular index includes null values for documents where deliveredAt is absent
// MongoDB must check which entries are null vs. actual dates

// $exists: true with a SPARSE index:
db.orders.createIndex({ deliveredAt: 1 }, { sparse: true })
// Sparse index ONLY includes non-null entries
// $exists: true efficiently uses the sparse index (all entries match)
// BUT $exists: false CANNOT use the sparse index (missing docs not in index)

// Best approach for $exists patterns: Partial index
db.orders.createIndex(
  { deliveredAt: 1 },
  { partialFilterExpression: { deliveredAt: { $exists: true } } }
)
```

---

## 6.9 Read Preference and Query Distribution

### Using Secondaries for Reads

In a replica set, all writes go to the primary. Reads can be directed to secondaries to distribute load:

```javascript
// Direct reads to secondary nodes (read from secondary):
db.orders.find({ status: "pending" }).readPref("secondaryPreferred")

// Spring Boot configuration:
spring:
  data:
    mongodb:
      uri: mongodb://host1,host2,host3/db?readPreference=secondaryPreferred
```

**Trade-off:** Secondary reads may return slightly stale data (replication lag). For analytics queries and reporting this is acceptable. For user-facing operations requiring immediate consistency, use primary reads.

**When to use secondary reads:**
- Analytics, reporting, dashboards (stale data acceptable)
- Offloading read load from primary during write-heavy periods
- Background jobs and batch processing

**When NOT to use secondary reads:**
- After a write that must be immediately visible to the same user (read-your-writes concern)
- Financial balance queries
- Any query where stale data causes incorrect business logic

---

## 6.10 Query Profiling Workflow

### Using the Profiler

```javascript
// Enable profiler for slow queries (> 50ms)
db.setProfilingLevel(1, { slowms: 50 })

// Run your application workload for a few minutes, then:
db.system.profile.find().sort({ millis: -1 }).limit(10)
// Shows the 10 slowest operations

// For specific analysis:
db.system.profile.find({ millis: { $gt: 100 }, ns: "mydb.orders" })
  .sort({ ts: -1 })
  .limit(20)
```

**Important profiler fields:**

```javascript
{
  "op": "query",              // Operation type
  "ns": "mydb.orders",       // Namespace (db.collection)
  "command": { /* query */ },
  "millis": 250,              // Execution time in milliseconds
  "planSummary": "IXSCAN { customerId: 1 }",  // Quick plan summary
  "keysExamined": 5000,      // Index keys examined
  "docsExamined": 5000,      // Documents examined
  "nreturned": 25,           // Documents returned
  "ts": ISODate("...")        // When the operation ran
}
```

### Optimization Workflow

```
1. Enable profiler at threshold (50ms or less for production)
2. Collect 30 minutes of query data
3. Sort by millis DESC to find worst offenders
4. For each slow query:
   a. Run explain("executionStats")
   b. Check keysExamined / nReturned ratio
   c. Look for COLLSCAN, SORT with usedDisk, high skip values
   d. Design and create appropriate index
   e. Re-run explain to verify improvement
5. Disable profiler or raise threshold after investigation
```

---

## 6.11 Exercises

### Exercise 6.1: Pagination Implementation

```javascript
// Given: A collection of 5 million blog posts
// Query: Get published posts, sorted by publishedAt DESC, 20 per page
// The post list page needs to support "Load More" (infinite scroll)
```

1. Implement the first page query.
2. Implement the subsequent page query given a cursor.
3. Design the required index (ESR compliant).
4. Explain why offset-based pagination would be problematic at page 500.

### Exercise 6.2: Anti-Pattern Identification

Identify all performance problems in this code:

```javascript
// Get user's recent order history for display:
function getUserOrders(userId, page) {
  const skip = (page - 1) * 20;
  const orders = db.orders
    .find({ userId: userId })
    .sort({ createdAt: -1 })
    .skip(skip)
    .limit(20)
    .toArray();
    
  const total = db.orders.countDocuments({ userId: userId });
  
  return { orders, total, page };
}
```

List all problems and provide the corrected implementation.

### Exercise 6.3: Covered Query Design

Design an index that makes the following query covered (no document fetch):

```javascript
db.products.find(
  { 
    category: "electronics",
    inStock: true,
    price: { $lte: 500 }
  },
  { 
    name: 1,
    price: 1,
    sku: 1,
    brand: 1,
    _id: 0
  }
).sort({ price: 1 })
```

---

## 6.12 Knowledge Check

1. What is the primary performance problem with `skip()` and why does it worsen with page depth?
2. What additional field should always be added to a sort to ensure stable cursor-based pagination?
3. When does a regex query efficiently use a B-tree index?
4. What is a covered query and what condition must the projection satisfy for it to be covered?
5. What are the downsides of `$or` queries compared to `$in`?
6. When would you use `readPreference: "secondaryPreferred"` and when would you avoid it?

---

## 6.13 Interview-Style Questions

**Q: A team is building a product catalog page with filtering by category, price range, and brand, with sorting by price and pagination. What is the ideal MongoDB index design?**

> Model answer: Apply ESR rule: equality fields first (category, brand), sort field next (price), range field last (price range). Since price is both the sort key and a range filter, we need to think carefully — if filtering by specific brand and category, those equalities go first, then price serves as both sort and range scan. Index: `{ category: 1, brand: 1, price: 1 }`. Pagination should be cursor-based using `price` and `_id` as the cursor key to avoid deep skip performance degradation. Verify with `explain("executionStats")` that there is no SORT stage and `totalDocsExamined ≈ nReturned`.

**Q: You are reviewing a query that uses `$or` with 10 conditions spanning 5 different fields. What concerns do you have and what alternatives exist?**

> Model answer: A 10-condition `$or` requires 10 separate IXSCAN operations plus result set intersection/union. Performance is roughly proportional to the sum of all individual IXSCAN costs. Concerns: (1) De-duplication overhead if documents match multiple branches, (2) No efficient sort across merged results, (3) Plan cache entry may use a suboptimal combination. Alternatives: if multiple conditions are on the same field, use `$in` instead. If the conditions represent a business concept ("high-value customer"), materialize a computed field (`{ tier: "high-value" }`) via change streams or application logic, then query that single field. If the `$or` is for full-text-style search, use Atlas Search or text indexes.

---

*Next: [Module 07: Aggregation Pipeline Optimization →](07-aggregation-pipeline-optimization.md)*
