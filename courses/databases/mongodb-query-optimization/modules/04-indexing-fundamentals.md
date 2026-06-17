# Module 04: Indexing Fundamentals

**Difficulty:** Intermediate
**Estimated Study Time:** 6 hours
**Prerequisites:** Modules 01–03

---

## Learning Objectives

By the end of this module you will be able to:
- Explain how a B-tree index is structured and traversed
- Describe why indexes accelerate reads and decelerate writes
- Identify the right index type for each use case
- Explain the trade-offs, limitations, and anti-patterns of each index type
- Calculate index size and its impact on working set

---

## 4.1 B-Tree Index Internals

### Layer 1: Intuition

Imagine a library of one million books, arranged randomly. Finding a book by title requires checking every book — one million comparisons. Now imagine an alphabetical card catalog: you flip to the section for the first letter, then the second, then find the exact card in seconds. That is a B-tree index.

The card catalog has three key properties:
1. **It is sorted** — you can navigate to any key in O(log n) time
2. **It stores a pointer** — the card contains "aisle 7, shelf 3" (the RecordId in MongoDB)
3. **It must stay updated** — when a new book arrives, a new card must be added in the right alphabetical position

### Layer 2: B-Tree Structure

MongoDB uses a **B+-tree** variant. The critical properties:

```
B+-Tree for index { status: 1 }:

               ┌────────────────────┐
               │   ROOT NODE        │
               │ ["confirmed"|"shipped"]  │ ← Internal node (routing keys)
               └──────┬─────────────┘
                      │
          ┌───────────┼──────────────┐
          ▼           ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  LEAF 1  │  │  LEAF 2  │  │  LEAF 3  │
    │"cancelled"│  │"confirmed"│  │"delivered"│
    │ → RecId1 │  │ → RecId5 │  │ → RecId9 │
    │"cancelled"│  │"confirmed"│  │"shipped" │
    │ → RecId2 │  │ → RecId6 │  │ → RecId10│
    │    ...   │  │    ...   │  │"shipped" │
    └──────────┘  └──────────┘  │ → RecId11│
         │              │       └──────────┘
         └──────────────┘
    (leaf nodes linked as doubly-linked list for range scans)
```

**Internal nodes** contain routing keys that guide traversal to the correct leaf.

**Leaf nodes** contain the actual indexed key values and the corresponding RecordIds (disk locations of documents).

**Key B-tree properties for MongoDB:**
- Tree height: `ceil(log_b(N))` where b is branch factor (~512 per WiredTiger page) and N is number of entries
- For 10M entries: height ≈ ceil(log_512(10M)) ≈ 3 levels — 3 I/O reads to find any key
- Leaf nodes linked for efficient range scans (read next leaf without going back to root)
- All data is in leaves (B+ tree) — internal nodes are navigation only

### Layer 3: Index Traversal in Detail

**Point lookup: `{ status: "pending" }`**

```
1. Start at ROOT NODE
   → "pending" < "confirmed"? No. "pending" < "shipped"? No.
   → Navigate to rightmost child (LEAF 3)

2. At LEAF 3 — binary search within leaf:
   → Find first entry "pending"
   → Collect all "pending" RecordIds by scanning right along linked list until key changes

3. For each RecordId → disk lookup to fetch document (FETCH stage)
```

**Range scan: `{ amount: { $gte: 100, $lte: 200 } }`** (index on `amount`)

```
1. Navigate tree to first leaf containing amount ≥ 100 (O(log n))
2. Scan RIGHT along linked leaf list collecting RecordIds until amount > 200
   → Sequential leaf traversal: highly I/O efficient (pages read contiguously)
3. Fetch documents for collected RecordIds
```

### Layer 4: Why Indexes Speed Reads

Without index:
- Access time: O(N) where N = number of documents
- I/O pattern: random (documents on random disk pages)
- Scale: doubles when collection doubles

With index:
- Access time: O(log N) for the B-tree + O(M) to fetch M matching documents
- I/O pattern: O(log N) random I/Os to traverse tree + sequential leaf scan
- Scale: grows logarithmically with collection size

**Concrete numbers:**

| Collection Size | Without Index (docs to examine) | With Index (tree height + docs fetched) |
| :--- | :--- | :--- |
| 1,000 | 1,000 | 2 levels + matching docs |
| 1,000,000 | 1,000,000 | 3 levels + matching docs |
| 1,000,000,000 | 1,000,000,000 | 4 levels + matching docs |

The tree height barely changes while the collection grows by orders of magnitude.

### Layer 5: Why Indexes Slow Writes

Every write operation (insert, update, delete) must maintain all indexes. For a document with 5 indexes:

```
insertOne(doc) →
  1. Write document to data files (1 I/O)
  2. Update index 1 → find position in B-tree, insert leaf entry (1–3 I/Os)
  3. Update index 2 → (1–3 I/Os)
  4. Update index 3 → (1–3 I/Os)
  5. Update index 4 → (1–3 I/Os)
  6. Update index 5 → (1–3 I/Os)
  Total: 6–16 I/Os per insert (vs 1 I/O without indexes)
```

Additionally:
- **B-tree page splits:** When a leaf node is full, it must split into two nodes, requiring parent node updates, potentially cascading up the tree
- **Index page caching:** Index pages occupy WiredTiger cache space, potentially evicting hot data pages

**Engineering principle:** Every index is a contract: *"I will pay an extra write cost on every insert/update/delete in exchange for read speed."* Only make this contract when the read benefit justifies the write cost.

---

## 4.2 Single-Field Indexes

### Definition and Creation

```javascript
// Ascending single-field index
db.orders.createIndex({ customerId: 1 })

// Descending single-field index
db.orders.createIndex({ createdAt: -1 })

// Check index created
db.orders.getIndexes()
```

### What Queries It Supports

A single-field index `{ field: 1 }` supports:
- Equality: `{ field: "value" }`
- Range: `{ field: { $gt: x } }`, `{ field: { $lt: x } }`
- Sort (ascending and descending — a single-field index supports both directions)
- `$in`: `{ field: { $in: ["a", "b", "c"] } }` — treated as union of point lookups
- `$exists`: `{ field: { $exists: true } }` (sparse index needed for `$exists: false`)

### What Queries It Does NOT Support Efficiently

- Queries on *other* fields — this index does nothing for `{ amount: { $gt: 100 } }`
- Combined filter + sort when both fields differ: `{ customerId: "C1" }` sorted by `createdAt`
  → The index covers the filter but an in-memory sort is still required

### Anti-Pattern: Too Many Single-Field Indexes

```javascript
// Anti-pattern: covering every possible field with a single-field index
db.orders.createIndex({ customerId: 1 })
db.orders.createIndex({ status: 1 })
db.orders.createIndex({ region: 1 })
db.orders.createIndex({ createdAt: -1 })
db.orders.createIndex({ amount: 1 })
// ... 5 indexes

// Problem: each write updates 5 index B-trees. 
// A query filtering on multiple fields picks ONE index at most.
// Better solution: compound indexes covering common query patterns
```

---

## 4.3 Compound Indexes

Compound indexes are covered in depth in Module 05. Brief introduction here:

```javascript
// Compound index covers filter on customerId AND status
db.orders.createIndex({ customerId: 1, status: 1 })

// This index ALSO covers single-field queries on customerId alone
// (prefix principle — Module 05)
db.orders.find({ customerId: "C1" })  // Uses compound index via prefix
```

**Key rule: Prefer compound indexes over multiple single-field indexes.** One compound index `{ a: 1, b: 1 }` is almost always better than two single-field indexes `{ a: 1 }` and `{ b: 1 }`.

---

## 4.4 Multikey Indexes

### What They Are

When you index a field that contains an array, MongoDB creates a **multikey index** — one index entry per array element.

```javascript
// Document:
{ _id: 1, tags: ["mongodb", "performance", "indexing"] }

// Index: { tags: 1 }
// Creates 3 index entries:
//   "indexing" → RecordId(1)
//   "mongodb"  → RecordId(1)
//   "performance" → RecordId(1)
```

### Query Support

```javascript
db.articles.find({ tags: "mongodb" })         // Matches documents containing "mongodb" in array
db.articles.find({ tags: { $in: ["mongodb", "performance"] } })  // Efficiently uses index
db.articles.find({ tags: { $all: ["a", "b"] } })                 // Index used but less efficient
```

### Critical Limitations

**Limitation 1: Index size amplification**

If the average array has 10 elements and the collection has 1 million documents, the multikey index has 10 million entries — 10x larger than a single-value index. This means 10x more RAM for index pages in the working set.

```javascript
// Calculate this before creating a multikey index:
db.orders.aggregate([
  { $project: { tagCount: { $size: { $ifNull: ["$tags", []] } } } },
  { $group: { _id: null, avgArraySize: { $avg: "$tagCount" }, maxArraySize: { $max: "$tagCount" } } }
])
```

**Limitation 2: No compound multikey index with two array fields**

```javascript
// This FAILS:
db.posts.createIndex({ tags: 1, categories: 1 })
// Error: cannot index parallel arrays [tags] [categories]
// MongoDB cannot create compound index entries for two array fields simultaneously
// (the cartesian product would be enormous)

// This is FINE (one array, one scalar):
db.posts.createIndex({ tags: 1, authorId: 1 })
```

**Limitation 3: Sort limitations**

A multikey index cannot support a sort. If a query uses a multikey index for filtering and also requests a sort, MongoDB must perform an in-memory sort.

```javascript
// Cannot use index for both filter and sort:
db.posts.find({ tags: "mongodb" }).sort({ publishDate: -1 })
// IXSCAN on tags, then in-memory SORT
// (because tags is multikey, the document may match multiple index entries)
```

### When to Use Multikey Indexes

✅ **Use when:**
- Documents contain arrays of searchable values (tags, categories, roles, permissions)
- Array cardinality is bounded and reasonable (< 100 elements per document)
- Read queries on array elements are frequent

❌ **Avoid when:**
- Arrays can be very large (thousands of elements) — use Bucket Pattern instead
- You need to sort on the same query that uses the multikey index

---

## 4.5 Unique Indexes

```javascript
// Create unique index
db.users.createIndex({ email: 1 }, { unique: true })

// Create unique compound index
db.orders.createIndex({ orderId: 1, vendorId: 1 }, { unique: true })
```

### Internal Behavior

Unique indexes work like regular B-tree indexes but with an additional uniqueness constraint check on every insert and update. Before inserting an index entry, MongoDB checks if that key already exists in the index. If it does, the write is rejected with `DuplicateKeyError (code 11000)`.

### Performance Implications

```javascript
// Duplicate key rejection is FAST (just a B-tree lookup):
// Cost of uniqueness check ≈ O(log n) — same as a read

// But creating unique index on existing data requires a full scan:
db.users.createIndex({ email: 1 }, { unique: true, background: true })
// If duplicates exist, this fails — clean data first
```

### Anti-Pattern: Unique Index as a Deduplication Strategy

Do NOT rely on MongoDB's unique index rejection as your primary deduplication logic. Applications that catch `DuplicateKeyError` and treat it as "record already exists" are creating unnecessary write attempts. Implement idempotency at the application level with `findOneAndUpdate` + `upsert`.

---

## 4.6 Sparse Indexes

### What They Are

A sparse index only includes index entries for documents that **have the indexed field**. Documents where the field is absent (or `null`) are excluded from the index.

```javascript
// Regular index: { deliveredAt: 1 }
// Includes ALL documents, even those where deliveredAt is missing/null
// Missing field stored as null in index — wastes space

// Sparse index: { deliveredAt: 1 } with sparse: true
// Only includes documents where deliveredAt exists and is not null
db.orders.createIndex({ deliveredAt: 1 }, { sparse: true })
```

### When Sparse Indexes Are Valuable

```javascript
// Collection: 10 million orders
// 9.5 million have status "delivered" with deliveredAt date
// 500,000 are still pending — no deliveredAt field

// Without sparse:  10M index entries (500K are null — wasted space)
// With sparse:      9.5M index entries — saves 5% space and memory

// Query that benefits from sparse index:
db.orders.find({ deliveredAt: { $gt: ISODate("2024-01-01") } })
// Only needs the 9.5M non-null entries — sparse is perfect
```

### Critical Limitation: Sparse Index Breaks `{ field: null }` Queries

```javascript
db.orders.find({ deliveredAt: null })
// With sparse index: MongoDB CANNOT use the sparse index for this query
// because the sparse index does NOT contain entries for documents where deliveredAt is absent
// MongoDB falls back to COLLSCAN for this query

// Solution: use Partial Index instead (more flexible)
```

---

## 4.7 Partial Indexes

### What They Are

Partial indexes are sparse indexes' more powerful successor. Instead of including/excluding based on field presence, partial indexes include only documents that match a **filter expression**.

```javascript
// Only index orders that are "pending" — ignore all others
db.orders.createIndex(
  { createdAt: 1 },
  { partialFilterExpression: { status: "pending" } }
)

// Only index premium users
db.users.createIndex(
  { email: 1 },
  { partialFilterExpression: { premium: true } }
)
```

### Why Partial Indexes Are Powerful

**Scenario:** You have 10 million orders. Only 50,000 are currently "pending". You frequently query pending orders by creation date.

Without partial index: Full index on `createdAt` stores 10M entries.
With partial index on `{ status: "pending" }`: Only 50,000 entries — 200x smaller index.

Result:
- 200x less RAM consumed by this index
- 200x faster index creation
- 200x less write overhead for non-pending status changes

```javascript
// The partial index will ONLY be used when the query includes the filter condition:
db.orders.find({ status: "pending", createdAt: { $gte: ISODate("2024-01-01") } })
// ✅ Uses partial index — query satisfies { status: "pending" } filter expression

db.orders.find({ createdAt: { $gte: ISODate("2024-01-01") } })
// ❌ Does NOT use partial index — query doesn't guarantee status = "pending"
//    MongoDB cannot use an index that excludes data the query might need to see
```

### Partial Unique Indexes — The Conditional Uniqueness Pattern

```javascript
// Unique active usernames, but allow multiple "deleted" users to share a username
db.users.createIndex(
  { username: 1 },
  { unique: true, partialFilterExpression: { active: true } }
)
// Two users with username "john" both with active: false → allowed
// Two users with username "john" both with active: true → rejected
```

---

## 4.8 TTL Indexes

### What They Are

TTL (Time-To-Live) indexes are single-field indexes on a `Date` type field that automatically delete documents after a specified number of seconds.

```javascript
// Delete documents 7 days (604800 seconds) after the createdAt date
db.sessions.createIndex({ createdAt: 1 }, { expireAfterSeconds: 604800 })

// Delete documents at the exact date stored in the expiresAt field
db.sessions.createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 })
```

### Internal Mechanism

A background thread (the TTL Monitor) runs every 60 seconds. It scans TTL indexes, identifies documents past their expiry, and deletes them in batches.

**Important nuances:**
- **60-second precision:** Deletion is not instantaneous. Documents may survive up to 60 seconds beyond their expiry.
- **No partial field support:** TTL field must be a BSON Date, not a string or number.
- **Performance:** TTL deletions consume I/O and can affect write performance during peak deletion periods. Schedule large TTL expirations during low-traffic windows if possible.
- **Cannot be compound:** TTL indexes cannot be compound indexes.

### When to Use TTL Indexes

✅ **Excellent for:**
- Session stores (auto-expire inactive sessions)
- Event logs (retain only last N days)
- OTP tokens (expire after N minutes)
- Rate limiting counters (expire hourly windows)
- IoT telemetry (retain only recent data)

❌ **Avoid for:**
- Data that needs fine-grained expiry control (use application-level deletion instead)
- Data that must be archived (not just deleted) before expiry — TTL just deletes

---

## 4.9 Hidden Indexes

### What They Are (MongoDB 4.4+)

A hidden index is an existing index that MongoDB excludes from query planning. The index is still maintained on writes, but the planner never considers it.

```javascript
// Hide an index
db.orders.hideIndex("customerId_1")

// Unhide an index
db.orders.unhideIndex("customerId_1")

// Check if an index is hidden
db.orders.getIndexes()
// "hidden": true will appear in the index document
```

### The Key Use Case: Safe Index Removal

**Problem:** You want to remove an index you believe is unused, but you are afraid removing it will break a query you overlooked.

**Traditional approach (risky):** Drop the index → monitor for slow queries → if something breaks, rebuild the index (which can take hours on large collections).

**Better approach with hidden indexes:**
1. `db.orders.hideIndex("customerId_1")` — index is hidden from planner (instant)
2. Monitor for 24–72 hours — if any query suddenly becomes slow, `unhideIndex` instantly restores it
3. If no problems: `db.orders.dropIndex("customerId_1")` — confident removal

### Trade-Off

Hidden indexes still consume write overhead and RAM for page caching. They are not a permanent solution — they are a *temporary testing mechanism* for safe removal.

---

## 4.10 Text Indexes

```javascript
// Create a text index on one or more fields
db.articles.createIndex({ title: "text", body: "text" })

// Query text index
db.articles.find({ $text: { $search: "mongodb performance optimization" } })

// Sort by text relevance score
db.articles.find(
  { $text: { $search: "mongodb performance" } },
  { score: { $meta: "textScore" } }
).sort({ score: { $meta: "textScore" } })
```

### Internal Mechanics

Text indexes use an inverted index structure (different from B-tree). For each word in the indexed text fields, the index stores the RecordIds of all documents containing that word. The text search query:
1. Tokenizes the search string into words
2. Removes stop words ("the", "a", "is")
3. Applies stemming ("running" → "run")
4. Looks up each stem in the inverted index
5. Computes relevance scores using term frequency (TF) and inverse document frequency (IDF)

### Critical Limitations

- **One text index per collection** — you cannot have two text indexes
- **No compound sort support** — sorting by text score and another field requires an in-memory sort
- **Language-specific** — stemming and stop words are language-dependent (configure with `default_language` option)
- **Performance at scale** — text indexes on large collections with long documents become very large; consider Atlas Search or Elasticsearch for production text search
- **Not suitable for non-English languages without configuration**

---

## 4.11 Hashed Indexes

```javascript
// Create a hashed index
db.users.createIndex({ userId: "hashed" })
```

### What They Do

Instead of storing the actual field value, hashed indexes store a hash of the value. This produces an evenly distributed index regardless of the actual value distribution.

### Primary Use Case: Sharding

Hashed indexes are used as **shard keys** when you want to distribute writes evenly across shards regardless of the monotonic nature of your key.

```javascript
// If you shard by userId with a ranged shard key:
// All new users get sequential IDs → all go to the same shard → hot shard problem

// If you shard by hashed userId:
// Each new userId hash is random → evenly distributed across shards
sh.shardCollection("mydb.users", { userId: "hashed" })
```

### Limitations

- **Only equality queries** — hashed indexes cannot support range queries (`$gt`, `$lt`) or sorting
- **Cannot be unique** — hashed indexes cannot enforce uniqueness
- **Cannot be multikey** — cannot index array fields

---

## 4.12 Wildcard Indexes

```javascript
// Index all fields in a document
db.products.createIndex({ "$**": 1 })

// Index a specific nested path and all its sub-paths
db.products.createIndex({ "attributes.$**": 1 })
```

### What They Are

Wildcard indexes index every field (or every field under a specific path) in a document. They are useful when document schemas are highly dynamic and you cannot predict which fields will be queried.

### When to Consider Them

**Valid use case:** You have a polymorphic collection where each document type has completely different fields, and you need to support ad-hoc queries on any field.

### Why to Be Cautious

```javascript
// The index footprint is enormous:
// If a document has 50 fields, a wildcard index creates 50 index entries per document
// For 1M documents with 50 fields each: 50M index entries

// Also, compound queries are not efficiently supported:
db.products.find({ "attributes.color": "red", "attributes.size": "large" })
// Wildcard index handles this as two separate index scans + intersection
// A specific compound index { "attributes.color": 1, "attributes.size": 1 } is always faster
```

**Engineering guidance:** Use wildcard indexes as a temporary measure or for truly dynamic schemas. As query patterns stabilize, replace with targeted compound indexes.

---

## 4.13 Clustered Indexes (MongoDB 5.3+)

```javascript
// Create a collection with a clustered index on _id
db.createCollection("events", {
  clusteredIndex: { key: { _id: 1 }, unique: true }
})
```

### What They Are

In a standard collection, the `_id` field has a B-tree index, but documents are stored in heap order (approximately insertion order, with gaps). The `_id` index contains RecordIds pointing to the actual document location.

In a **clustered collection**, documents are stored on disk *in the order of the clustered index key*. The `_id` value IS the document location — no separate B-tree indirection is needed.

### Performance Benefits

1. **Range scans on `_id`:** Sequential disk reads for range queries on the clustered key (no random I/O)
2. **No separate `_id` index:** Removes one B-tree from the working set
3. **Better locality:** Documents with similar `_id` values are physically adjacent on disk

### Ideal Use Case

```javascript
// Time-series event data with timestamp-based _id (like ObjectId):
// Documents with nearby ObjectId values were inserted close together in time
// Clustered index ensures range scans by time read sequential disk pages
db.createCollection("iot_readings", {
  clusteredIndex: { key: { _id: 1 }, unique: true }
})
// Then insert with ObjectId-based _id:
db.iot_readings.insertOne({ _id: new ObjectId(), sensorId: "S1", temp: 22.5 })
```

### Limitations

- Only one clustered index per collection
- The clustered key must be `_id`
- Not suitable for collections where `_id` does not reflect the primary query access pattern

---

## 4.14 Index Size Analysis and Management

### Measuring Index Sizes

```javascript
// Detailed index statistics
db.orders.stats({ indexDetails: true })

// Quick index sizes
db.orders.aggregate([{ $indexStats: {} }])

// Total index size for the collection
const stats = db.orders.stats({ scale: 1024 * 1024 }); // MB
print(`Total index size: ${stats.totalIndexSize} MB`);
print(`Index sizes:`);
Object.entries(stats.indexSizes).forEach(([name, size]) => {
  print(`  ${name}: ${size} MB`);
});
```

### Identifying Unused Indexes

```javascript
// Check index access statistics (resets on mongod restart)
db.orders.aggregate([{ $indexStats: {} }])
// Look for indexes with "ops": { "accesses": { "since": <long time ago>, "ops": 0 } }
// These are candidates for removal (but verify with hidden index first)
```

### Index Naming Strategy

```javascript
// MongoDB default naming: field1_direction_field2_direction...
// { customerId: 1, status: 1 } → "customerId_1_status_1"

// Custom name (useful for long compound indexes):
db.orders.createIndex(
  { customerId: 1, status: 1, createdAt: -1, region: 1 },
  { name: "customer_status_time_region" }
)
```

---

## 4.15 Exercises

### Exercise 4.1: Index Type Selection
For each scenario, choose the most appropriate index type and justify your decision:

1. You need to automatically delete user sessions 30 minutes after creation.
2. You have a product catalog where each product has a dynamic set of attributes stored as a subdocument, and you need to support ad-hoc queries on any attribute.
3. You want to enforce that each email address is unique, but only for active user accounts (inactive accounts can share emails with other inactive accounts).
4. You have a large collection where 95% of documents have `premiumUntil: null` and you frequently query for documents where `premiumUntil` is in the future.
5. You are building a full-text search feature for blog articles.

### Exercise 4.2: Write Cost Analysis
A collection has 7 indexes. An insert operation triggers a write. Estimate the minimum and maximum number of I/O operations for this insert, and explain what determines the range.

### Exercise 4.3: Multikey Index Impact Assessment
A `posts` collection has 2 million documents. Each document has a `tags` array with an average of 8 tags and a maximum of 150 tags. 

1. Calculate the approximate number of index entries if you create `{ tags: 1 }`.
2. Estimate the index size assuming each entry is ~50 bytes.
3. Propose an alternative approach if the large index size is a concern.

---

## 4.16 Knowledge Check

1. What is the difference between a B-tree and a B+-tree, and why does MongoDB use the latter?
2. Why does a single-field index not help a query that sorts on a different field?
3. What is the key difference between a sparse index and a partial index?
4. Why can't you create a compound index with two array (multikey) fields?
5. When should you use a hashed index and when should you avoid it?
6. A hidden index still consumes write I/O — true or false? Why?

---

## 4.17 Interview-Style Questions

**Q: A team member wants to add an index on every frequently queried field. There are 12 different fields queried in the application. They want 12 single-field indexes. How do you advise them?**

> Model answer: Twelve single-field indexes is almost certainly excessive and counterproductive. First, identify which field *combinations* appear together in the most common, most latency-sensitive queries. A compound index on `{ field1: 1, field2: 1 }` can support queries on field1 alone (via prefix), field1 + field2 together, and sort operations — replacing two single-field indexes. Additionally, 12 indexes means every write must maintain 12 B-trees — significant write amplification. Start with 3–5 carefully designed compound indexes covering the critical query patterns. Use `$indexStats` to identify which indexes are actually used. Use hidden index testing before adding or removing any index.

**Q: You have a TTL index set to 86400 seconds (1 day). A user's session expires, but 2 minutes later they can still log in with it. Why?**

> Model answer: TTL Monitor runs every 60 seconds, not continuously. After a document's TTL expires, it may take up to 60 seconds for the background thread to identify and delete it. Additionally, if the mongod is under heavy load, the TTL Monitor may be delayed further. This is by design — TTL provides "eventual expiry" not "exact expiry." For security-critical session expiry (like OAuth tokens), do not rely on TTL alone. Check expiry at the application layer by storing `expiresAt` in the document and validating it in your session lookup code.

---

*Next: [Module 05: Compound Index Design (ESR Rule) →](05-compound-index-design.md)*
