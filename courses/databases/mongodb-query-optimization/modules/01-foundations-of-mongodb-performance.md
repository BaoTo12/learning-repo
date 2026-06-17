# Module 01: Foundations of MongoDB Performance

**Difficulty:** Beginner
**Estimated Study Time:** 4 hours
**Prerequisites:** Basic MongoDB CRUD operations

---

## Learning Objectives

By the end of this module, you will be able to:
- Explain why performance optimization is a first-class engineering concern
- Distinguish latency from throughput and explain why both matter
- Identify the four hardware bottlenecks: CPU, memory, disk I/O, and network
- Define the working set and explain its relationship to RAM
- Explain how document databases differ from relational databases regarding optimization
- Classify workloads as read-heavy, write-heavy, mixed, OLTP, or analytical — and explain how each classification changes optimization strategy

---

## 1.1 Why Performance Optimization Matters: The Real Cost of Slow Queries

### Layer 1: Intuition

Imagine a busy restaurant. The kitchen can prepare 200 meals per hour. If a chef suddenly needs to search through all 10,000 refrigerator items by opening every drawer to find one ingredient, the entire kitchen grinds to a halt. Other orders back up. Customers wait. Revenue drops.

A MongoDB collection scan works exactly like that chef searching every drawer. One slow query in a high-throughput system does not just affect the user who triggered it — it consumes CPU, memory, and disk I/O that would otherwise serve hundreds of other requests.

This is the fundamental problem query optimization solves: **resource consumption at scale**.

### Layer 2: Internal Mechanics

When MongoDB executes a query, it consumes resources from four hardware subsystems:

```
┌─────────────────────────────────────────────────────────┐
│                    MongoDB Query Engine                  │
│                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │   CPU    │   │   RAM    │   │  Disk I/O│            │
│  │(planning)│   │ (caching)│   │(document │            │
│  │(sorting) │   │(working  │   │ fetching)│            │
│  │(hashing) │   │  set)    │   │          │            │
│  └──────────┘   └──────────┘   └──────────┘            │
│         ↑               ↑              ↑                │
│         └───────────────┴──────────────┘                │
│                         │                               │
│                    ┌──────────┐                         │
│                    │ Network  │                         │
│                    │(result   │                         │
│                    │ transfer)│                         │
│                    └──────────┘                         │
└─────────────────────────────────────────────────────────┘
```

**CPU** is consumed by:
- Query parsing and canonicalization
- Plan selection (evaluating candidate plans)
- Expression evaluation (regex, `$where`, JavaScript)
- In-memory sorting (`$sort` without index support)
- Hash operations (`$group`, `$lookup` hash joins)

**RAM** is consumed by:
- The WiredTiger cache holding hot data and index pages
- Sort buffers (up to 100MB per sort operation before spill-to-disk)
- Aggregation pipeline intermediate result sets
- Connection overhead (~1MB per active connection)

**Disk I/O** is consumed by:
- Reading documents not present in the WiredTiger cache
- Index traversal when index pages are cold
- Spill-to-disk during memory-exhausting sorts and aggregations
- Journal writes (write durability)

**Network** is consumed by:
- Transferring result documents to the application
- Transferring documents to/from secondaries during replication
- `mongos` → shard communication in sharded clusters

### Layer 3: Concrete Examples

**The Cost of One Bad Query in Production**

Consider a collection of 10 million user documents. A developer writes:

```javascript
// Bad: Full collection scan
db.users.find({ last_name: "Smith" })
```

Without an index on `last_name`, MongoDB must examine all 10 million documents. If each document is 1KB, that is 10GB of data to scan. Assuming SSD throughput of 500MB/s:

```
Scan time ≈ 10,000 MB / 500 MB/s = 20 seconds
```

During those 20 seconds:
- WiredTiger reads 10GB through its cache, evicting hot data for other users
- CPU is saturated executing document-by-document comparisons
- Other queries waiting for the same disk I/O experience dramatically elevated latency
- Thread pool connections are held open, reducing available concurrency

With an index, the same query locates matching documents via B-tree traversal, touching perhaps 1,000 index entries and fetching a few hundred documents. Execution time drops from 20 seconds to single-digit milliseconds.

**The Amplification Effect**

In a system serving 1,000 requests per second, a query that takes 20ms instead of 1ms creates:

```
Additional latency per query:  19ms
Requests per second:           1,000
Additional server load:        1,000 × 19ms = 19 seconds of blocking per second
```

The server is spending 19 seconds worth of work per second — it is overloaded by a 19ms overhead. This is the **amplification effect**: small query inefficiencies multiply catastrophically at scale.

### Layer 4: Trade-Off Analysis

Optimization itself has a cost. Consider these real trade-offs before optimizing anything:

| Decision | Benefit | Cost |
| :--- | :--- | :--- |
| Add an index | Faster reads | Slower writes; disk space; RAM for index pages |
| Denormalize data | Fewer lookups | Larger documents; update complexity |
| Cache query results | Eliminates DB round-trips | Data staleness; cache invalidation complexity |
| Add more RAM | Larger working set fits in memory | Infrastructure cost |
| Shard the cluster | Horizontal read/write scaling | Operational complexity; query routing overhead |

> **Engineering Judgment Rule #1:** Always measure before optimizing. The most dangerous optimization is the one applied to a query that is not actually causing a problem.

---

## 1.2 Latency vs. Throughput: Understanding What You Are Actually Optimizing

### Layer 1: Intuition

These two terms are frequently confused even by experienced engineers:

- **Latency**: How long does it take for *one* operation to complete? (milliseconds per operation)
- **Throughput**: How many operations can the system complete per unit time? (operations per second)

A highway analogy:
- A road with one lane but no traffic lights: **low latency** (no waiting), **low throughput** (few cars simultaneously)
- A 12-lane highway: **similar or higher latency** per car (they still drive the speed limit), but **much higher throughput** (more cars per minute)

MongoDB optimization often forces you to choose between optimizing for one or the other.

### Layer 2: Internal Mechanics

**Latency determinants:**
- Index traversal depth (B-tree height, typically 3–5 levels for millions of documents)
- Number of documents fetched from disk
- Network round-trip time (client ↔ mongod)
- Lock contention (document-level or collection-level)

**Throughput determinants:**
- Degree of query parallelism (MongoDB uses multiple threads)
- WiredTiger cache hit rate (hot data in RAM vs. cold data on disk)
- Index coverage (covered queries require no document fetch — higher parallelism possible)
- Connection pool size (limits concurrent operations)

### Layer 3: Concrete Examples

**Scenario: Batch reporting vs. real-time dashboard**

A batch job that generates nightly reports cares about **throughput**: it needs to process 50 million documents in 2 hours. Optimal strategy: sequential collection scan with streaming, minimal index usage.

A real-time dashboard serving live user queries cares about **latency**: each user-facing query must return in under 100ms. Optimal strategy: precise compound indexes, covered queries where possible.

The same collection, the same data — but completely different optimization strategies because the objectives differ.

```javascript
// Latency-optimized: Pinpoint index for dashboard query
db.orders.find(
  { customerId: "CUST-1234", status: "pending" },
  { _id: 1, orderId: 1, amount: 1 }   // Covered projection
)
// Covered by index on { customerId: 1, status: 1, amount: 1 }
// Target: < 5ms

// Throughput-optimized: Batch analytics job
db.orders.aggregate([
  { $match: { createdAt: { $gte: ISODate("2024-01-01") } } },
  { $group: { _id: "$region", total: { $sum: "$amount" } } }
])
// Intended to run overnight: throughput > latency
```

### Layer 4: Trade-Off Analysis

| Optimization Goal | What You Sacrifice |
| :--- | :--- |
| Minimize latency | May use more memory (indexes, cache warming) |
| Maximize throughput | Individual operation latency may increase |
| Both simultaneously | Requires scaling hardware (more RAM, more shards) |

**Production Reality:** Most production systems have mixed workloads with both latency-sensitive and throughput-sensitive paths. The engineering challenge is designing a schema, index set, and read preference strategy that serves both without starving either.

---

## 1.3 The Four Hardware Bottlenecks

### Memory: The Most Important Resource for MongoDB

MongoDB's WiredTiger storage engine uses a cache (default: 50% of (RAM - 1GB)). When your **working set** — the collection of data and indexes that active queries need — fits in the WiredTiger cache, MongoDB operates almost entirely in memory. Queries are fast.

When the working set exceeds available RAM:

```
Working Set > WiredTiger Cache
→ WiredTiger must evict cached pages to make room for new data
→ Evicted pages must be re-read from disk on next access
→ Random I/O increases dramatically
→ Latency spikes; throughput collapses
```

This is called **cache pressure** or **working set overflow** — the most common root cause of MongoDB performance degradation in production.

**How to identify cache pressure:**

```javascript
// Check WiredTiger cache statistics
db.serverStatus().wiredTiger.cache
// Key metrics:
// "bytes currently in the cache" vs "maximum bytes configured"
// "pages read into cache" (rising fast = cache thrashing)
// "unmodified pages evicted" (rising fast = working set overflow)
```

### Disk I/O: The Performance Cliff

The difference between RAM access and disk access is staggering:

| Storage | Access Latency |
| :--- | :--- |
| CPU L1 cache | ~1 nanosecond |
| RAM | ~100 nanoseconds |
| NVMe SSD | ~100 microseconds |
| SATA SSD | ~500 microseconds |
| Hard Disk Drive | ~10 milliseconds |

A query that requires disk I/O instead of serving from RAM is 1,000–100,000x slower. In a system serving 10,000 queries/second, any disk access for a frequently executed query is catastrophic.

**Write amplification:** Writes in MongoDB go through multiple I/O paths:
1. Write to the WiredTiger cache (in-memory)
2. Write to the journal (on-disk, sequential — fast)
3. Eventual checkpoint flush to data files (on-disk, sequential — fast)
4. Index updates for every modified document (one write per index entry, potentially random I/O)

This means a single `updateOne()` with 4 indexes performs at least 5 disk writes (1 data + 4 index updates), each potentially touching a different disk location.

### CPU: Often Underestimated

CPU bottlenecks in MongoDB typically come from:

1. **In-memory sort operations** — `$sort` without an index requires a full document load into memory and a heapsort. For large result sets this is CPU-intensive.
2. **Regex and JavaScript expressions** — `$where` and `$function` execute server-side JavaScript via V8, which is slow and blocks the query thread.
3. **Aggregation pipelines with complex expressions** — `$map`, `$reduce`, `$filter` on large arrays per document is CPU-intensive.
4. **Plan cache misses** — Re-planning queries uses CPU. Frequent plan cache invalidation (due to data distribution changes or index changes) wastes CPU.

**Practical rule:** If `mongotop` shows high CPU usage but normal I/O, look for regex queries, JavaScript operators, or unindexed sorts.

### Network: The Hidden Bottleneck

Network is rarely the primary bottleneck for intra-datacenter deployments but becomes significant when:

1. **Large result sets are returned** — A query returning 500,000 documents, each 5KB, transmits 2.5GB over the network. Even at 10Gbps, that is 2 seconds of network transfer alone.
2. **Projection is missing** — Without projection, MongoDB sends entire documents to the application even when the application only uses 2 of 50 fields.
3. **Sharded clusters** — Queries must travel from application → mongos → multiple shards → mongos → application. Each hop adds latency.

**Practical rule:** Always project only the fields your application uses. The saved bytes across millions of queries translate to meaningful latency and bandwidth cost reductions.

---

## 1.4 The Working Set Concept

### Layer 1: Intuition

Your MongoDB working set is like a chef's mise en place — the ingredients and tools arranged at arm's reach for the current service. If everything needed for tonight's dinner is on the counter, service is fast and smooth. If the chef must walk to the walk-in refrigerator for every ingredient, service collapses.

The WiredTiger cache is your mise en place. If the data and indexes your most frequent queries need are in the cache, MongoDB is fast. If they are not — if they must be fetched from disk — performance degrades significantly.

### Layer 2: Internal Mechanics

The working set consists of:
1. **Index pages** in active use — B-tree pages for indexes on frequently queried fields
2. **Data pages** containing frequently accessed documents
3. **Internal metadata** — collection catalog, validation rules, etc.

WiredTiger uses an **LRU (Least Recently Used) eviction policy** with some additional heuristics. When the cache approaches its maximum:
1. WiredTiger's eviction threads begin evicting clean (unmodified) pages
2. If clean eviction cannot keep up, dirty (modified) pages are checkpointed to disk and evicted
3. If eviction threads cannot keep up with application demand, **application threads are stalled** to perform eviction — this causes latency spikes

**Critical insight:** The working set is NOT just the data your query matches. It is every index page and data page touched during the query path. A query on 10% of documents might touch 100% of an index's leaf pages if the filter has low selectivity.

### Layer 3: Concrete Examples

**Working set calculation for a typical application:**

```
Collection: orders
Documents:  10,000,000
Avg size:   2KB per document
Total data: 20GB

Indexes:
  { customerId: 1, status: 1 } → ~800MB
  { createdAt: -1 }            → ~300MB
  { sku: 1 }                   → ~200MB

Total index size: ~1.3GB

Hot data (accessed in last hour): ~5% of documents = 1GB

Effective working set:
  Hot data:   1GB
  All indexes: 1.3GB
  ─────────────────
  Total:      2.3GB

If WiredTiger cache = 4GB → Working set fits comfortably → Fast queries
If WiredTiger cache = 1.5GB → Working set overflows → Performance degradation
```

**How to observe working set size:**

```javascript
// Check collection + index sizes
db.orders.stats({ scale: 1024 * 1024 }) // sizes in MB
// storageSize: data on disk
// totalIndexSize: all indexes

// Check WiredTiger cache usage
db.serverStatus().wiredTiger.cache["bytes currently in the cache"]
```

### Layer 4: Trade-Off Analysis

| Decision | Effect on Working Set |
| :--- | :--- |
| Add a new index | Increases working set size by index size |
| Increase document size | Increases working set size |
| Add projection to queries | Does NOT reduce working set (indexes still loaded) |
| Increase WiredTiger cache | Directly expands working set capacity |
| Partition data (sharding) | Reduces working set *per shard* |
| Archive old data | Reduces working set by removing cold documents |

> **Common Misconception:** "Adding projection to queries reduces memory usage." Projection reduces network transfer size and application memory, but it does **not** reduce WiredTiger cache consumption. The full document is still loaded into cache before projection is applied.

---

## 1.5 Document Databases vs. Relational Databases: Different Optimization Challenges

### Layer 1: Intuition

A relational database is like a normalized spreadsheet — data is split across many small tables, and queries join them together. Optimization focuses on join order, join strategy, and table statistics.

A document database is like a filing cabinet with folders — each folder (document) contains related information together. Optimization focuses on the shape of the documents, how data is grouped, and how indexes traverse nested structures.

The optimization *problems* are different, not just the syntax.

### Layer 2: Key Differences

| Aspect | Relational (PostgreSQL, MySQL) | Document (MongoDB) |
| :--- | :--- | :--- |
| **Schema** | Fixed at table definition; enforced | Flexible; enforced by application or JSON schema |
| **Join optimization** | Query planner selects join order and strategy | `$lookup` is explicit; order is controlled by the developer |
| **Normalization** | First normal form to BCNF; optimizer handles joins | Developer chooses embedding vs. referencing |
| **Index structures** | B-tree primary; also GiST, GIN, BRIN | B-tree primary; also multikey, text, geo, hashed |
| **Statistics** | Automatic column statistics collection | Limited; MongoDB uses plan evaluation instead |
| **Nested data** | Joins; no native nesting | Native subdocuments and arrays; multikey indexes |
| **Update patterns** | Row-level in-place updates; MVCC | Document-level MVCC; in-place vs. full document rewrite |

### Layer 3: The Schema-Flexibility Trap

> **"MongoDB is schema-less" does NOT mean performance considerations disappear.**

This is one of the most common misconceptions among developers new to MongoDB. In fact, schema design has *more* performance impact in MongoDB than in relational databases, because:

1. **The developer controls join strategy** — by choosing to embed or reference, you pre-decide whether data retrieval requires one query or two.
2. **Document size affects cache efficiency** — a 500KB document takes 250x more cache space than a 2KB document, even if you only access one field.
3. **Array indexing (multikey) has multiplicative effects** — an array of 100 elements in a document creates 100 index entries. Scale this to millions of documents and the index becomes enormous.
4. **There are no SQL query plan hints about join selectivity** — MongoDB cannot re-order an explicit pipeline the way a SQL planner can re-order joins.

**Example:**

```javascript
// Schema Design A: Embed order items in the order document
{
  _id: "ORD-001",
  customerId: "CUST-123",
  items: [
    { sku: "A1", qty: 2, price: 9.99 },
    { sku: "B2", qty: 1, price: 19.99 },
    // ... potentially hundreds of items
  ]
}

// Schema Design B: Separate order_items collection
// orders document:
{ _id: "ORD-001", customerId: "CUST-123" }
// order_items documents:
{ orderId: "ORD-001", sku: "A1", qty: 2, price: 9.99 }
{ orderId: "ORD-001", sku: "B2", qty: 1, price: 19.99 }
```

**Design A Performance Characteristics:**
- ✅ Retrieving an order with all its items: 1 query, 1 document fetch
- ❌ Finding all orders containing a specific SKU: requires multikey index, potentially large result scan
- ❌ If items array grows unbounded: document growth, page splits, cache bloat

**Design B Performance Characteristics:**
- ✅ Finding all orders containing a specific SKU: simple indexed query on `order_items`
- ✅ Large item sets don't bloat the order document
- ❌ Retrieving order + items: 2 queries or `$lookup` (with its own performance cost)

The "correct" choice depends on your *query workload* — not on abstract normalization theory.

---

## 1.6 Workload Classification

Before optimizing anything, classify your workload. The right strategy depends entirely on it.

### Read-Heavy Workloads (R:W > 10:1)

**Characteristics:**
- Many concurrent reads, infrequent writes
- Examples: product catalog, content delivery, user profile reads, reporting

**Optimization priorities:**
1. Maximize index coverage (covered queries)
2. Tune WiredTiger cache size
3. Use secondary reads (`ReadPreference.secondaryPreferred()`)
4. Consider read replicas or Atlas global reads
5. Denormalize to reduce join operations

**Indexes:** Multiple covering indexes are acceptable; write performance hit is manageable

### Write-Heavy Workloads (W:R > 5:1)

**Characteristics:**
- High write volume, moderate reads
- Examples: IoT telemetry, event logging, real-time tracking, financial ledgers

**Optimization priorities:**
1. Minimize index count (every index is updated on write)
2. Use bulk writes (`insertMany`, `BulkWrite`)
3. Consider time-series collections (MongoDB 5.0+)
4. Tune write concern for durability vs. throughput trade-off
5. Consider bounded arrays (Bucket Pattern)

**Indexes:** Keep indexes minimal; prefer compound over multiple single-field indexes

### Mixed Workloads

**Characteristics:**
- Balanced read and write traffic
- Examples: e-commerce platforms, social media, SaaS applications

**Optimization priorities:**
1. Identify the critical path (user-facing queries) and optimize those first
2. Move non-critical analytical queries to secondary nodes or Atlas Data Federation
3. Separate OLTP indexes from analytical indexes using secondary index strategies
4. Consider CQRS (Command Query Responsibility Segregation) patterns

### OLTP vs. Analytical Workloads

| Dimension | OLTP | Analytical |
| :--- | :--- | :--- |
| **Access pattern** | Point lookups; small result sets | Full or large scans; aggregations |
| **Latency target** | < 10ms | Seconds to minutes acceptable |
| **Concurrency** | Thousands of concurrent users | Few concurrent jobs |
| **Index strategy** | Many precise indexes | Fewer indexes; rely on sequential scans |
| **Schema strategy** | Normalized for update flexibility | Denormalized for scan efficiency |
| **MongoDB feature** | MongoTemplate/Repository with index hints | Aggregation pipelines, `$merge`, Atlas Data Federation |

---

## 1.7 Exercises

### Exercise 1.1: Bottleneck Classification
For each scenario, identify the primary bottleneck (CPU, RAM, disk I/O, or network) and explain your reasoning:

1. A MongoDB instance that is slow on all queries, `mongostat` shows `%pf` (page faults) consistently above 50/second.
2. A query using `{ $where: "this.items.some(i => i.price > 100)" }` is consuming 80% CPU.
3. A reporting query returns 200,000 documents in 3 seconds; the application processes them in 500ms.
4. An aggregation pipeline runs fine locally but is slow in production on a sharded cluster.

### Exercise 1.2: Working Set Analysis
Given:
- Collection: 5 million documents, avg size 3KB
- Indexes: `{ userId: 1 }` (400MB), `{ createdAt: -1 }` (250MB), `{ status: 1, userId: 1 }` (500MB)
- WiredTiger cache: 8GB
- "Hot" data (accessed in last 24 hours): ~10% of collection

Calculate whether the working set fits in the WiredTiger cache and explain the implications.

### Exercise 1.3: Workload Classification and Strategy
A SaaS CRM application has:
- 10,000 concurrent users during business hours
- Users read their own contact records (avg 50 contacts per user): 90% of queries
- Admins run reports across all contacts: 10% of queries (but long-running)
- Data is written when contacts are updated: ~1 write per 20 reads

Classify this workload and propose two different optimization strategies: one that prioritizes user-facing read latency and one that prioritizes admin report throughput.

---

## 1.8 Knowledge Check

1. What is the difference between latency and throughput? Give a database example of each.
2. Why does a collection scan affect *other* queries running simultaneously?
3. What two components make up the MongoDB working set?
4. Why does "MongoDB is schema-less" NOT mean performance is schema-independent?
5. A query uses projection `{ name: 1, email: 1 }`. Does this reduce WiredTiger cache usage? Why or why not?

---

## 1.9 Reflection Questions

- Think of a real application you have worked on or know about. What was its read-to-write ratio? How did that influence its database design choices?
- If you had to explain the working set concept to a junior developer in one sentence, what would you say?
- When would it be acceptable to NOT optimize a slow query?

---

## 1.10 Interview-Style Questions

**Q: Our MongoDB server has 32GB of RAM and our data is 100GB. How do we approach performance optimization?**

> Model answer: Start by understanding which data is *actually accessed frequently* — the working set. Profile slow queries with the profiler to identify the hot query paths. Calculate index sizes for indexes supporting those hot paths. Ensure those indexes fit in the WiredTiger cache (default: 50% of RAM - 1GB = ~15GB in this case). If hot indexes plus hot data exceed ~15GB, either reduce index count, archive cold data, add RAM, or shard the workload. Never assume all 100GB needs to be in cache.

**Q: A developer says "we don't need indexes, MongoDB is fast enough." How do you respond?**

> Model answer: The claim may be true for a collection of 1,000 documents but will fail catastrophically at 1,000,000 or 10,000,000 documents. Without an index, every query performs a collection scan proportional to collection size. At scale, even a 1-second query on a small collection becomes a 100-second query on a large one. Furthermore, collection scans are not isolated — they exhaust I/O and evict hot pages from the WiredTiger cache, degrading *all concurrent queries*. Indexes are not a premature optimization; they are a fundamental correctness requirement for any non-trivial collection.

---

*Next: [Module 02: Query Execution Internals →](02-query-execution-internals.md)*
