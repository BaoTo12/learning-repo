# Module 05: Compound Index Design (ESR Rule)

**Difficulty:** Intermediate–Advanced
**Estimated Study Time:** 6 hours
**Prerequisites:** Modules 01–04

---

## Learning Objectives

By the end of this module you will be able to:
- Apply the ESR (Equality–Sort–Range) rule to design optimal compound indexes
- Explain *why* the ESR ordering works from B-tree mechanics first principles
- Recognize when ESR must be adapted for specific query patterns
- Design indexes that support covered queries
- Evaluate competing index designs and choose the optimal one
- Explain index selectivity and cardinality and use them in design decisions
- Apply index design to real-world domain problems

---

## 5.1 The Prefix Principle

Before understanding the ESR rule, you must deeply understand the prefix principle. It is the foundational constraint that makes compound index design non-trivial.

### Layer 1: Intuition

A phone book is sorted first by last name, then by first name. To find "Alice Johnson", you can efficiently flip to "Johnson" then find "Alice". But if you want to find all people named "Alice" regardless of last name, the phone book is useless — the first sort key is last name, so Alices are scattered everywhere.

This is the prefix principle. A compound index on `{ lastName: 1, firstName: 1 }` can efficiently support:
- Queries on `lastName` alone ✅
- Queries on `lastName` + `firstName` ✅
- But NOT queries on `firstName` alone ❌

### Layer 2: Mechanics

A compound index `{ a: 1, b: 1, c: 1 }` creates a single B-tree sorted by:
1. First key `a` (primary sort)
2. Then by key `b` within each `a` group (secondary sort)
3. Then by key `c` within each `a, b` group (tertiary sort)

```
Index entries sorted as:
("cat", "large", 100)   → RecordId 1
("cat", "large", 200)   → RecordId 5
("cat", "small", 50)    → RecordId 3
("dog", "large", 150)   → RecordId 2
("dog", "small", 75)    → RecordId 4
("dog", "small", 300)   → RecordId 8
```

**Queries and which prefix they can use:**

```javascript
// Uses full index:
db.products.find({ category: "cat", size: "large" }).sort({ price: 1 })
// B-tree range: [("cat","large",MinKey) → ("cat","large",MaxKey)]

// Uses first prefix { category: 1 }:
db.products.find({ category: "dog" })
// B-tree range: [("dog",MinKey,MinKey) → ("dog",MaxKey,MaxKey)]

// CANNOT use index (skips first key):
db.products.find({ size: "large" })
// MongoDB must do COLLSCAN because there is no index where "size" is the leading field
```

### Layer 3: The Critical Test

**A query can use a compound index if and only if the query's filter fields form a prefix of the index field order.**

| Index | Query Filter | Can Use Index? |
| :--- | :--- | :--- |
| `{ a, b, c }` | `{ a: x }` | ✅ Prefix { a } |
| `{ a, b, c }` | `{ a: x, b: y }` | ✅ Prefix { a, b } |
| `{ a, b, c }` | `{ a: x, b: y, c: z }` | ✅ Full index |
| `{ a, b, c }` | `{ b: y }` | ❌ Not a prefix |
| `{ a, b, c }` | `{ b: y, c: z }` | ❌ Not a prefix |
| `{ a, b, c }` | `{ a: x, c: z }` | ✅ Prefix { a } — `c` cannot be used, filter by `c` done post-scan |

The last row is subtle and important. When you query `{ a: x, c: z }` against index `{ a, b, c }`, MongoDB can use the index to find all entries where `a = x`, but then must filter by `c` during the FETCH stage (because `b` is not constrained, `c` entries are scattered through the index). The index is partially useful.

---

## 5.2 The ESR Rule

### What It Is

ESR stands for **Equality → Sort → Range**. It is the recommended field ordering for compound indexes when a query has a mix of equality filters, sort criteria, and range filters.

```
Compound Index Field Order:
  [Equality fields first] + [Sort fields second] + [Range fields last]
```

### Why This Order Works: A B-Tree Perspective

**Understanding what each clause type does to the index traversal:**

**Equality fields:** Constrain the index to an exact key section. All matching entries are contiguous in the B-tree.

```
Index { status: 1, ... }  with  status = "pending"
→ All "pending" entries are a contiguous block in the B-tree leaf pages
→ Single seek to start of block, read to end of block
```

**Range fields:** Constrain the index to a contiguous key range. But within that range, other fields are unconstrained and thus not sorted.

```
Index { amount: 1, ... }  with  amount > 100 and amount < 500
→ All entries from 100 to 500 are contiguous
→ But if there are subsequent fields, they are not meaningfully ordered
→ A sort on a subsequent field requires loading all matching docs and sorting in memory
```

**Sort fields:** Enable the index traversal to match the query's sort order, eliminating the SORT stage. But this only works if the documents appear in sorted order in the index traversal path.

### The Critical Insight: Sort Must Come After Equality But Before Range

```
Index: { status: 1, createdAt: -1, amount: 1 }
Query: { status: "pending", amount: { $gt: 100 } }  .sort({ createdAt: -1 })

ESR components:
  Equality:  status = "pending"       → goes first
  Sort:      createdAt descending     → goes second
  Range:     amount > 100             → goes last

Why this works in the B-tree:
1. MongoDB seeks to the contiguous block of "pending" entries
2. Within "pending", entries are sorted by createdAt descending
3. MongoDB reads entries in createdAt order (satisfying sort without in-memory sort)
4. Within each (status, createdAt) combination, entries are sorted by amount
5. MongoDB can apply the amount > 100 range filter as it scans
```

**What happens if range comes before sort:**

```
Index: { status: 1, amount: 1, createdAt: -1 }  (WRONG ORDER!)
Query: { status: "pending", amount: { $gt: 100 } }.sort({ createdAt: -1 })

1. MongoDB seeks to "pending" entries
2. Within "pending", entries are sorted by amount
3. amount > 100 is a range: MongoDB scans entries from amount=100 to MaxKey
4. Within this amount range, createdAt is NOT sorted (it varies randomly per entry)
5. MongoDB CANNOT use the index ordering to satisfy the sort
6. A SORT stage is required — potentially expensive for large result sets
```

### Layer 3: Worked Examples

**Example 1: E-Commerce Order Query**

```javascript
// Query:
db.orders.find({
  customerId: "CUST-123",        // equality
  status: { $in: ["pending", "confirmed"] },  // equality ($in treated as equality)
  createdAt: { $gte: ISODate("2024-01-01") }  // range
}).sort({ amount: -1 })          // sort
```

**Applying ESR:**
- Equality: `customerId`, `status` (note: `$in` is treated as equality for ESR purposes)
- Sort: `amount`
- Range: `createdAt`

```javascript
// Optimal index:
db.orders.createIndex({ customerId: 1, status: 1, amount: -1, createdAt: 1 })
//                       [EQUALITY]            [SORT]          [RANGE]
```

**Verify with explain:**
```javascript
db.orders.find({
  customerId: "CUST-123",
  status: { $in: ["pending", "confirmed"] },
  createdAt: { $gte: ISODate("2024-01-01") }
}).sort({ amount: -1 }).explain("executionStats")
// Expected: IXSCAN with no SORT stage, minimal keysExamined/nReturned ratio
```

---

**Example 2: Blog Post Query**

```javascript
// Query: Find published posts in a specific category, sorted by popularity, filtered by date range
db.posts.find({
  category: "technology",           // equality
  published: true,                  // equality
  publishedAt: { $gte: ISODate("2024-01-01"), $lte: ISODate("2024-12-31") }  // range
}).sort({ views: -1 }).limit(20)    // sort
```

**Applying ESR:**
- Equality: `category`, `published`
- Sort: `views`
- Range: `publishedAt`

```javascript
// Optimal index:
db.posts.createIndex({ category: 1, published: 1, views: -1, publishedAt: 1 })
```

**What makes this a good index:**
1. `category` and `published` narrow the scan to only technology posts that are published
2. Within that set, documents are sorted by `views` descending — no SORT stage for the limit
3. `publishedAt` range is applied as an additional filter during the scan

**Comparing to naive alternatives:**

```javascript
// Alternative A: { category: 1, publishedAt: 1, published: 1, views: -1 }
// Problem: Range (publishedAt) comes before Sort (views)
// Result: SORT stage required, examines all matching docs before taking limit(20)

// Alternative B: { views: -1, category: 1, published: 1, publishedAt: 1 }
// Problem: Sort (views) comes before Equality (category, published)
// Result: Index scans from highest views → low, then filters by category
// Very inefficient: most popular posts are not necessarily in "technology"
```

---

**Example 3: Complex Multi-Equality**

```javascript
// Query:
db.events.find({
  tenantId: "T-001",              // equality — high selectivity
  eventType: "purchase",          // equality — medium selectivity
  userId: "U-8877",               // equality — high selectivity
  timestamp: { $gte: yesterday }  // range
}).sort({ value: -1 }).limit(10)  // sort
```

**Question: Which equality field should come first?**

The ESR rule tells you to put equalities before sort before range, but it does NOT specify the order *among* equality fields. This is where **selectivity** matters.

---

## 5.3 Index Selectivity and Cardinality

### Layer 1: Intuition

If you are looking for a book in a library with 100,000 books:
- "Books by J.K. Rowling" narrows to ~10 books (high selectivity — good first criterion)
- "Books in English" narrows to 80,000 books (low selectivity — poor first criterion)

Put high-selectivity criteria first to eliminate the most documents earliest.

### Layer 2: Cardinality and Selectivity Defined

**Cardinality** = number of distinct values for a field.

**Selectivity** = fraction of documents matching a filter. A *high* selectivity filter matches *few* documents.

```javascript
// Measure cardinality:
db.orders.distinct("status").length          // e.g., 5 values — LOW cardinality
db.orders.distinct("customerId").length      // e.g., 50,000 values — HIGH cardinality
db.orders.distinct("orderId").length         // e.g., 1,000,000 — UNIQUE
```

### Layer 3: Ordering Equality Fields by Selectivity

For multiple equality fields, order them from **highest cardinality (most selective) to lowest cardinality (least selective)**:

```javascript
// Query: { tenantId: "T-001", eventType: "purchase", userId: "U-8877" }
// Cardinalities:
//   tenantId:   5 distinct values  → each value matches 20% of docs — LOW selectivity
//   eventType:  15 distinct values → each value matches ~7% — MEDIUM
//   userId:     500,000 distinct   → each value matches 0.0002% — HIGH selectivity

// Optimal equality order: userId first (most selective), then eventType, then tenantId
db.events.createIndex({ userId: 1, eventType: 1, tenantId: 1, timestamp: 1, value: -1 })
//                        [HIGH]     [MEDIUM]    [LOW]        [RANGE]       [SORT]
```

**Important caveat:** This principle applies when your cardinality distribution is relatively uniform. In multi-tenant systems, tenantId is often queried *first* even if it has low cardinality, because the cardinality within a tenant context may be high, and putting it first respects the shard key structure. Always validate with actual `explain()` output.

---

## 5.4 Covered Queries

### What They Are

A **covered query** is one where all fields in the query (filter, sort, AND projection) are present in an index. MongoDB can satisfy the entire query from index data alone — no FETCH stage, no document reads.

### Why They Are The Performance Gold Standard

Without covered query:
```
IXSCAN → RecordId → FETCH (disk I/O) → PROJECTION → Return
```

With covered query:
```
IXSCAN (all fields in index) → PROJECTION_COVERED → Return
```

The elimination of FETCH means:
- No document I/O (even if documents are cold/on disk)
- Dramatically reduced WiredTiger cache pressure
- Much higher query throughput

### How to Design a Covered Index

```javascript
// Query:
db.orders.find(
  { customerId: "CUST-1", status: "pending" },  // filter fields
  { orderId: 1, amount: 1, createdAt: 1, _id: 0 }  // projection fields
)
// Note: _id: 0 is required — by default _id is included and forces a FETCH

// Covered index must include ALL fields: filter + projection:
db.orders.createIndex({
  customerId: 1,
  status: 1,
  orderId: 1,   // ← from projection
  amount: 1,    // ← from projection
  createdAt: 1  // ← from projection
})
```

**Verify it is covered:**
```javascript
db.orders.find(
  { customerId: "CUST-1", status: "pending" },
  { orderId: 1, amount: 1, createdAt: 1, _id: 0 }
).explain("executionStats")
// Expected:
// "totalDocsExamined": 0   ← No documents fetched
// Stage: PROJECTION_COVERED (not FETCH)
```

### When Covered Queries Are NOT Worth It

Adding many extra fields to an index to enable covered queries makes the index larger. If the "extra" fields are large (long strings, arrays), the index overhead may exceed the performance benefit of eliminating FETCH.

**Rule of thumb:** Covered queries make the most sense when:
1. The query is extremely frequent (thousands per second)
2. The projected fields are small (IDs, short strings, numbers)
3. Documents are large (many fields) making FETCH expensive

---

## 5.5 Index Intersection vs. Compound Indexes

### What Is Index Intersection?

MongoDB can sometimes use *two* separate indexes simultaneously to answer a query, combining their results via an AND or OR operation. This is called index intersection.

```javascript
// Indexes:
db.orders.createIndex({ customerId: 1 })
db.orders.createIndex({ status: 1 })

// Query:
db.orders.find({ customerId: "CUST-1", status: "pending" })
// MongoDB might use AND_SORTED or AND_HASH to intersect results from both indexes
```

### Why You Should Prefer Compound Indexes

Index intersection sounds convenient — just create single-field indexes and let MongoDB combine them. The reality is disappointing:

**Performance of intersection:**
1. IXSCAN on index A → produces set of RecordIds {A}
2. IXSCAN on index B → produces set of RecordIds {B}
3. AND_HASH or AND_SORTED operation: join {A} ∩ {B} in memory
4. FETCH documents for intersection result

**Problems:**
- Step 1 and 2 examine *all* documents matching each individual condition
- The intersection must be computed in memory (additional CPU and RAM)
- Cannot eliminate the SORT stage (neither index alone provides sort order)
- MongoDB rarely chooses intersection even when possible — it often prefers COLLSCAN

**Compound index performance:**
1. IXSCAN on `{ customerId: 1, status: 1 }` → directly yields RecordIds for exact match
2. FETCH documents for those RecordIds only

**Conclusion:** Almost always prefer a compound index over relying on index intersection. The compound index is faster, uses less memory, can support sort elimination, and is more predictable.

---

## 5.6 Sort Support Edge Cases

### Sort Direction Matching

A compound index supports a sort if the sort direction either exactly matches or exactly reverses the index direction.

```javascript
// Index: { status: 1, createdAt: -1 }

// Supported sorts:
db.orders.find({status:"pending"}).sort({ createdAt: -1 })      // ✅ Matches index direction
db.orders.find({status:"pending"}).sort({ createdAt: 1 })       // ✅ Reverse (backward scan)
db.orders.find({status:"pending"}).sort({ status:1, createdAt:-1 }) // ✅ Exact match
db.orders.find({status:"pending"}).sort({ status:-1, createdAt:1 }) // ✅ Full reverse

// NOT supported (mixed directions):
db.orders.find({status:"pending"}).sort({ status: 1, createdAt: 1 })  // ❌ Mixed: forward/forward
// Would need index { status: 1, createdAt: 1 } to support this sort
```

### Multi-Field Sort with Equality

```javascript
// Query with equality on a, sort on b and c:
db.events.find({ a: "x" }).sort({ b: 1, c: -1 })

// Index { a: 1, b: 1, c: -1 } supports this:
// a= "x" → seek, then within "x" entries, b ascending, c descending

// Index { a: 1, b: -1, c: 1 } does NOT support this sort (wrong direction)
// Would need to either add another index or sort in memory
```

---

## 5.7 Mini Project: Design Indexes for Four Domains

### Part 1: E-Commerce Catalog and Orders

**Schema:**
```javascript
// products collection
{ _id, sku, name, category, brand, price, inStock, ratings: { avg, count }, tags: [] }

// orders collection
{ _id, orderId, customerId, status, items: [{sku, qty, price}], total, createdAt, deliveredAt, region }
```

**Query workload:**
1. Find available products in a category under a given price, sorted by rating
2. Get a customer's pending orders sorted by creation date (newest first)
3. Find all orders placed in a region in the last 30 days
4. Get top 10 best-selling products in a category

**Design indexes and explain your reasoning for each.**

---

### Part 2: Social Media Feed

**Schema:**
```javascript
// posts collection
{ _id, authorId, content, visibility: "public"|"followers", likes, createdAt, tags: [] }

// follows collection  
{ _id, followerId, followedId, createdAt }
```

**Query workload:**
1. Get all posts by a specific author, sorted by date (user profile page)
2. Get the 20 most recent public posts (global feed)
3. Get posts by all people the current user follows (home feed — complex)
4. Find trending posts in the last 24 hours with at least 100 likes

**Design indexes and identify which queries cannot be efficiently served by indexes alone (requiring aggregation or denormalization).**

---

### Part 3: Financial Ledger

**Schema:**
```javascript
// transactions collection
{ _id, transactionId, accountId, type: "debit"|"credit", amount, currency, status, createdAt, reference }
```

**Query workload:**
1. Get account balance (sum of all transactions for an account)
2. Get all transactions for an account in a date range, sorted by date
3. Find all failed transactions in the last hour across all accounts
4. Get monthly summary per account

**Important constraint: This is a write-heavy workload (financial system). Minimize index count while ensuring query performance.**

---

### Part 4: Logging System

**Schema:**
```javascript
// logs collection
{ _id, service, level: "info"|"warn"|"error", message, metadata: {}, timestamp }
```

**Query workload:**
1. Find all errors in the last 15 minutes across all services
2. Find all logs for a specific service in a time range
3. Find error logs containing a specific error code (field: `metadata.errorCode`)
4. Count log entries by level per service for the last hour

**Special constraint: 50,000 logs per minute are written. Index write overhead is a critical concern.**

---

## 5.8 Knowledge Check

1. What is the prefix principle and how does it constrain compound index design?
2. Explain in B-tree terms why range fields should come after sort fields in the ESR ordering.
3. What does `$in` mean for the ESR rule? Is it treated as equality or range?
4. What additional fields must be included in an index to create a covered query?
5. When would MongoDB choose a COLLSCAN over using an available index?
6. A compound index `{ a: 1, b: 1 }` exists. Does `db.collection.find({ b: 5 })` use this index? Explain.

---

## 5.9 Interview-Style Questions

**Q: A colleague says "we have compound indexes on everything, our queries are slow, and we should just add more indexes." What questions do you ask before agreeing?**

> Model answer: First, examine `explain("executionStats")` for the slow queries — are they using indexes? If yes, what is the `keysExamined/nReturned` ratio? If indexes are being used but ratios are high, the indexes exist but are not well-designed (wrong field order, wrong fields). More indexes won't help — better indexes will. If the system is write-heavy, adding more indexes will worsen write performance further. Check `db.collection.aggregate([{$indexStats:{}}])` to identify unused indexes — candidates for removal to reduce write amplification. The solution may be *fewer better indexes*, not more indexes.

**Q: Explain why the ESR rule says Sort comes before Range. Give a concrete example from first principles.**

> Model answer: Consider index `{ status: 1, createdAt: -1, amount: 1 }` for query `{ status: "pending", amount: { $gt: 100 } }.sort({ createdAt: -1 })`. Within all "pending" entries (equality), the index is sorted by `createdAt` descending. MongoDB can traverse these entries in order, examining only the amount filter as it scans. After reading the first N documents that match `amount > 100` in `createdAt` order, it can stop (when paired with LIMIT). If instead we use `{ status: 1, amount: 1, createdAt: -1 }`, the "pending" entries are sorted by amount first. To satisfy `amount > 100`, MongoDB reads all entries from amount=100 to MaxKey — but within this range, `createdAt` is completely unsorted (a customer might pay small or large amounts at any time). MongoDB cannot traverse in createdAt order, so it must collect ALL matching docs and sort them in memory. The in-memory sort cannot be short-circuited by LIMIT. This is why Sort must come before Range.

---

*Next: [Module 06: Query Pattern Optimization →](06-query-pattern-optimization.md)*
