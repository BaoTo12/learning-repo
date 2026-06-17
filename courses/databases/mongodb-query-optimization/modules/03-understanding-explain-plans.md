# Module 03: Understanding Explain Plans

**Difficulty:** Intermediate
**Estimated Study Time:** 5 hours
**Prerequisites:** Modules 01–02

---

## Learning Objectives

By the end of this module you will be able to:
- Choose the correct `explain()` verbosity mode for a given diagnostic task
- Read and interpret every major field in an explain output
- Recognize the most common execution stage trees and know what each implies
- Diagnose inefficient queries from explain output alone
- Calculate ratios that reveal index efficiency
- Recommend specific index or query changes from an explain output

---

## 3.1 The Three Explain Modes

### `queryPlanner` (Fastest, No Execution)

```javascript
db.orders.find({ status: "pending" }).explain("queryPlanner")
// or simply:
db.orders.find({ status: "pending" }).explain()
```

**What it returns:**
- The winning plan MongoDB *would* use
- All rejected plans
- Index names selected
- Stage tree (IXSCAN, COLLSCAN, SORT, etc.)

**What it does NOT return:**
- Actual document or key counts
- Actual execution time
- Actual number of results

**When to use it:**
- Quickly verify that the correct index is being selected
- Check if a query would use COLLSCAN without actually running a scan

---

### `executionStats` (Most Useful for Optimization)

```javascript
db.orders.find({ status: "pending" }).explain("executionStats")
```

**What it returns:** Everything in `queryPlanner` PLUS:
- Actual `executionTimeMillis`
- Actual `nReturned`
- Actual `totalDocsExamined`
- Actual `totalKeysExamined`
- Stage-level statistics (how many docs each stage processed)

**When to use it:**
- Diagnosing slow queries
- Measuring index effectiveness
- Calculating examination ratios

> ⚠️ **Important:** `executionStats` actually runs the query. For slow queries or large collections, this blocks and takes time.

---

### `allPlansExecution` (Deepest, Shows Rejected Plans)

```javascript
db.orders.find({ status: "pending" }).explain("allPlansExecution")
```

**What it returns:** Everything in `executionStats` PLUS:
- Execution statistics for each *rejected* plan during the multi-plan race
- How many documents/keys each rejected plan examined before being eliminated

**When to use it:**
- Understanding why MongoDB chose one index over another
- Diagnosing plan cache instability
- Verifying that the best plan actually won

---

## 3.2 Anatomy of an Explain Output

Let us walk through a complete `executionStats` output field by field.

### Setup for Examples

```javascript
use optimization_lab;

// Insert 100,000 sample orders
const statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"];
for (let i = 0; i < 100000; i++) {
  db.orders.insertOne({
    orderId: `ORD-${i}`,
    customerId: `CUST-${Math.floor(Math.random() * 1000)}`,
    status: statuses[Math.floor(Math.random() * statuses.length)],
    amount: parseFloat((Math.random() * 500 + 5).toFixed(2)),
    createdAt: new Date(Date.now() - Math.random() * 365 * 24 * 3600 * 1000),
    region: ["us-east", "us-west", "eu-central"][Math.floor(Math.random() * 3)]
  });
}

// Create an index for the example
db.orders.createIndex({ customerId: 1, status: 1 });
```

### Running and Reading the Explain

```javascript
db.orders.find(
  { customerId: "CUST-42", status: "pending" }
).explain("executionStats")
```

**Annotated Output:**

```json
{
  "explainVersion": "2",

  // ─────────────────────────────────────────────────────
  // QUERY PLANNER SECTION
  // ─────────────────────────────────────────────────────
  "queryPlanner": {
    "namespace": "optimization_lab.orders",
    
    // The query shape after canonicalization
    "parsedQuery": {
      "$and": [
        { "customerId": { "$eq": "CUST-42" } },
        { "status": { "$eq": "pending" } }
      ]
    },

    // TRUE = MongoDB considered the index + found an index for this query
    "indexFilterSet": false,
    
    // ── THE WINNING PLAN ──────────────────────────────
    "winningPlan": {
      "queryFramework": "sbe",           // Which engine executed this
      "stage": "FETCH",                  // Outermost (last) stage
      "inputStage": {
        "stage": "IXSCAN",               // Index scan stage
        "keyPattern": { "customerId": 1, "status": 1 },
        "indexName": "customerId_1_status_1",
        "isMultiKey": false,             // Not a multikey index (no arrays)
        "multiKeyPaths": { "customerId": [], "status": [] },
        "isUnique": false,
        "isSparse": false,
        "isPartial": false,
        "indexVersion": 2,
        "direction": "forward",          // Traversing index left-to-right
        "indexBounds": {
          // The range of index entries scanned:
          // customerId = "CUST-42" exactly
          "customerId": ["[\"CUST-42\", \"CUST-42\"]"],
          // status = "pending" exactly
          "status": ["[\"pending\", \"pending\"]"]
        }
      }
    },
    
    // ── REJECTED PLANS ────────────────────────────────
    "rejectedPlans": [
      {
        "stage": "SORT",                 // Rejected plan tried to COLLSCAN + SORT
        "inputStage": {
          "stage": "COLLSCAN",
          "filter": { /* entire filter */ }
        }
      }
    ]
  },

  // ─────────────────────────────────────────────────────
  // EXECUTION STATS SECTION
  // ─────────────────────────────────────────────────────
  "executionStats": {
    
    // Wall-clock time from start to finish
    "executionTimeMillis": 2,
    
    // How many documents were returned to the caller
    "nReturned": 8,
    
    // How many index keys were examined (IXSCAN iterations)
    "totalKeysExamined": 8,
    
    // How many documents were loaded from storage
    "totalDocsExamined": 8,
    
    // ── PER-STAGE BREAKDOWN ───────────────────────────
    "executionStages": {
      "stage": "FETCH",
      "nReturned": 8,
      "executionTimeMillisEstimate": 1,
      "works": 9,          // Internal "work units" (each advance = 1 work)
      "advanced": 8,       // Times a document was advanced to parent
      "needTime": 1,       // Times stage needed to do work but produced no result
      "needYield": 0,      // Times stage yielded execution (e.g., waiting for lock)
      "docsExamined": 8,
      "inputStage": {
        "stage": "IXSCAN",
        "nReturned": 8,
        "executionTimeMillisEstimate": 0,
        "works": 9,
        "advanced": 8,
        "needTime": 1,
        "keysExamined": 8,
        "seeks": 1,        // Number of times index cursor was repositioned
        "indexName": "customerId_1_status_1",
        "direction": "forward",
        "indexBounds": {
          "customerId": ["[\"CUST-42\", \"CUST-42\"]"],
          "status": ["[\"pending\", \"pending\"]"]
        }
      }
    }
  }
}
```

---

## 3.3 Critical Ratios and What They Mean

### The Examination Ratio: Your Primary Efficiency Indicator

```
Keys Examined Ratio  =  totalKeysExamined / nReturned
Docs Examined Ratio  =  totalDocsExamined / nReturned
```

| Ratio | Interpretation | Action |
| :--- | :--- | :--- |
| ≈ 1.0 | **Excellent:** Index perfectly matches query | No action needed |
| 1.1 – 10 | **Acceptable:** Minor over-scanning | Consider if workload justifies index refinement |
| 10 – 100 | **Concerning:** Significant waste | Refine index or query |
| > 100 | **Critical:** Major performance problem | Immediate index redesign required |
| totalDocsExamined >> totalKeysExamined | **COLLSCAN or post-filter** | Index not being used effectively |
| totalKeysExamined >> nReturned BUT totalDocsExamined ≈ nReturned | **Index with poor selectivity** | Tighten index or add more fields |

### Worked Example: Diagnosing a Problem

```javascript
// Problematic query — no index on status alone:
db.orders.find({ status: "delivered" }).explain("executionStats")
```

```json
{
  "executionStats": {
    "nReturned": 19823,
    "totalDocsExamined": 100000,
    "totalKeysExamined": 0,
    "executionTimeMillis": 245
  }
}
```

**Diagnosis:**
- `totalKeysExamined = 0` → no index used (COLLSCAN)
- `totalDocsExamined = 100000` → entire collection scanned
- Ratio: 100000 / 19823 ≈ 5:1 — not terrible by ratio alone, but the absolute scan count is the problem
- **Fix:** Create `{ status: 1 }` index (or better: compound index if other filters are common)

---

## 3.4 Execution Stage Reference

### COLLSCAN — Collection Scan

```json
{ "stage": "COLLSCAN", "docsExamined": 100000 }
```

**What it means:** MongoDB reads every document in the collection sequentially.

**When it appears:**
- No usable index exists for the filter
- The planner determined a collection scan is cheaper than available indexes (very rare)
- The query is `{}` (return all documents) — in this case, COLLSCAN is correct

**When it is acceptable:**
- Small collections (< ~1,000 documents) where index overhead exceeds scan cost
- Batch jobs that intentionally process all documents
- During initial data exploration

**When it is a problem:**
- Any production query on a large collection expected to run frequently

---

### IXSCAN — Index Scan

```json
{
  "stage": "IXSCAN",
  "indexName": "customerId_1_status_1",
  "indexBounds": {
    "customerId": ["[\"CUST-42\", \"CUST-42\"]"],
    "status": ["[\"pending\", \"pending\"]"]
  },
  "direction": "forward",
  "keysExamined": 8
}
```

**What it means:** MongoDB traverses the B-tree index within the specified bounds.

**Key fields to examine:**
- `indexBounds`: What range of the index is being scanned. Point lookups (`["[x, x]"]`) are most efficient; ranges (`["[x, MaxKey]"`) scan more entries.
- `direction`: `"forward"` = ascending; `"backward"` = descending (matching a descending sort)
- `keysExamined`: Total index entries read — compare to `nReturned`

---

### FETCH — Document Fetch

```json
{
  "stage": "FETCH",
  "docsExamined": 8,
  "inputStage": { "stage": "IXSCAN", ... }
}
```

**What it means:** Using RecordIds from the IXSCAN, MongoDB loads full documents from storage (WiredTiger data files).

**This stage adds I/O:** Each RecordId requires a lookup in the data files. If those document pages are not in the WiredTiger cache, disk reads occur.

**The goal:** Eliminate FETCH entirely by creating **covered indexes** (Module 06). If a query only needs fields that are all present in the index, MongoDB can satisfy it from index data alone without loading documents.

---

### SORT — In-Memory Sort

```json
{
  "stage": "SORT",
  "sortPattern": { "createdAt": -1 },
  "memLimit": 104857600,
  "totalDataSizeSorted": 24576,
  "usedDisk": false,
  "inputStage": { ... }
}
```

**What it means:** MongoDB loaded documents into memory and sorted them using a comparison sort algorithm.

**Key fields:**
- `memLimit`: Maximum memory allowed before spilling to disk (100MB default)
- `totalDataSizeSorted`: Total bytes sorted (if this approaches memLimit, disk spill is imminent)
- `usedDisk`: **RED ALERT** — the sort exceeded memory and spilled to disk. This is catastrophically slow.

**How to eliminate SORT:** Create an index with fields matching the sort pattern. If the index is also used for filtering (via IXSCAN), the documents come out pre-sorted — no SORT stage needed.

---

### LIMIT — Limit Stage

```json
{ "stage": "LIMIT", "limitAmount": 10, "inputStage": { ... } }
```

**What it means:** After N documents are collected, processing stops.

**Pushdown optimization:** When LIMIT appears *before* SORT in the plan tree (i.e., LIMIT is the parent of SORT), MongoDB must still sort all documents before limiting. This is **inefficient**. When SORT uses an index (so documents come pre-sorted), LIMIT can stop as soon as N documents are returned — this is the goal.

---

### SKIP — Skip Stage

```json
{ "stage": "SKIP", "skipAmount": 1000, "inputStage": { ... } }
```

**What it means:** MongoDB discards the first N documents from the result stream.

**Why SKIP is dangerous:** MongoDB cannot jump to offset 1000 in an arbitrary result set. It must process all 1000 documents before discarding them. For `SKIP: 10000`, MongoDB processes 10,000 documents just to throw them away. This is the **offset pagination problem** covered in Module 06.

---

### PROJECTION — Projection Stage

```json
{ "stage": "PROJECTION_SIMPLE", "transformBy": { "orderId": 1, "_id": 0 } }
```

**Types:**
- `PROJECTION_SIMPLE`: Fast path for simple inclusion/exclusion projections
- `PROJECTION_DEFAULT`: General path for complex expressions
- `PROJECTION_COVERED`: Applied directly to index data — no FETCH needed ✅

When you see `PROJECTION_COVERED`, it means MongoDB served the entire query (including projection) from the index. This is the ideal state — no document I/O.

---

### GROUP — Aggregation Grouping

```json
{
  "stage": "GROUP",
  "nReturned": 5,
  "totalOutputDataSizeBytes": 480,
  "usedDisk": false
}
```

**What it means:** `$group` accumulation stage. All documents that match the `_id` expression are grouped in memory.

`usedDisk: true` here means the group stage exceeded memory limit (100MB) and spilled to disk — a major performance problem.

---

### DISTINCT_SCAN — Optimized Distinct Query

```json
{
  "stage": "DISTINCT_SCAN",
  "indexName": "status_1",
  "keysExamined": 5,
  "nReturned": 5
}
```

**What it means:** MongoDB uses a B-tree index to return distinct values by jumping from one unique key to the next, skipping over duplicates. This is extremely efficient for `distinct()` queries on low-cardinality fields when the right index exists.

**When it appears:** Running `db.collection.distinct("fieldName")` or `$group` with `_id` pointing to an indexed field with no other accumulators.

---

### SHARDING_FILTER — Shard Boundary Filter (Sharded Clusters Only)

```json
{ "stage": "SHARDING_FILTER", "inputStage": { ... } }
```

**What it means:** In a sharded cluster, a shard may receive documents that belong to another shard (due to orphaned documents during migration). The SHARDING_FILTER removes these orphaned documents from results.

If you see this stage frequently in your explain plans, investigate whether chunk migrations are creating orphaned documents and consider running `cleanupOrphaned` if needed.

---

## 3.5 Reading Complex Explain Trees

### Example: Multi-Stage Pipeline

```javascript
db.orders.aggregate([
  { $match: { region: "us-east", status: "pending" } },
  { $sort: { createdAt: -1 } },
  { $limit: 20 }
]).explain("executionStats")
```

**Without index on { region, status, createdAt }:**

```
Winning Plan (read bottom-up):
  LIMIT (20)
    ↑
  SORT (createdAt: -1)        ← Sorting all matched docs = expensive
    ↑
  FETCH                       ← Loading all matched docs
    ↑
  IXSCAN (region: 1, status: 1)   ← Or COLLSCAN if no index
```

**With index `{ region: 1, status: 1, createdAt: -1 }`:**

```
Winning Plan:
  LIMIT (20)
    ↑
  FETCH                       ← Only fetch 20 docs (LIMIT pushed down)
    ↑
  IXSCAN                      ← Traverses index in sorted order
  (region, status, createdAt)  ← No SORT stage needed!
```

The difference:
- Without index: examine *all* matched docs, sort them all, take 20
- With index: traverse 20 index entries in pre-sorted order, fetch 20 docs, done

---

## 3.6 Step-By-Step Explain Diagnostic Workflow

When you receive a slow query to diagnose, follow this process:

```
Step 1: Run explain("executionStats")

Step 2: Locate the TOP-LEVEL stage
  ├─ COLLSCAN? → No index is being used → identify filter fields → design index → GOTO Step 1
  ├─ IXSCAN?   → An index is used → continue to Step 3
  └─ SORT (top)? → SORT is the final stage → in-memory sort is happening → check Step 5

Step 3: Check totalKeysExamined / nReturned ratio
  ├─ Ratio > 100? → Index is not selective enough
  │    → Add more fields to index to narrow the scan
  └─ Ratio ≈ 1?  → Index is well matched → check totalDocsExamined

Step 4: Check totalDocsExamined / nReturned ratio
  ├─ Ratio >> 1 even though IXSCAN is good?
  │    → A post-filter is rejecting many fetched docs
  │    → Consider adding the filter field to the index
  └─ Ratio ≈ 1? → Proceed to Step 5

Step 5: Is there a SORT stage in the tree?
  ├─ YES with usedDisk: true? → CRITICAL: sort exceeded memory → add index for sort
  ├─ YES with usedDisk: false? → Check totalDataSizeSorted / memLimit ratio
  └─ NO? → Sort is index-covered (optimal)

Step 6: Is there a FETCH stage?
  ├─ YES? → Can this query be covered by adding projected fields to the index?
  └─ NO (PROJECTION_COVERED)? → Query is fully covered → optimal

Step 7: Check executionTimeMillis
  ├─ Higher than expected even with good ratios?
  │    → Look for lock contention (needYield values), WiredTiger pressure, or network latency
  └─ Within acceptable range? → Optimization complete
```

---

## 3.7 Production Example: Diagnosing a Real Slow Query

**Scenario:** Engineering receives an alert that the "order history" API endpoint is taking 2+ seconds. The query is:

```javascript
db.orders.find(
  { customerId: "CUST-8819", status: { $in: ["pending", "confirmed"] } }
).sort({ createdAt: -1 }).limit(50)
```

**Step 1: Run explain**

```javascript
db.orders.find(
  { customerId: "CUST-8819", status: { $in: ["pending", "confirmed"] } }
).sort({ createdAt: -1 }).limit(50).explain("executionStats")
```

**Output (summarized):**

```json
{
  "queryPlanner": {
    "winningPlan": {
      "stage": "SORT",
      "sortPattern": { "createdAt": -1 },
      "inputStage": {
        "stage": "FETCH",
        "inputStage": {
          "stage": "IXSCAN",
          "indexName": "customerId_1",
          "indexBounds": {
            "customerId": ["[\"CUST-8819\", \"CUST-8819\"]"]
          }
        }
      }
    }
  },
  "executionStats": {
    "executionTimeMillis": 2180,
    "nReturned": 50,
    "totalKeysExamined": 3421,
    "totalDocsExamined": 3421,
    "executionStages": {
      "stage": "SORT",
      "usedDisk": true,
      "totalDataSizeSorted": 120549183
    }
  }
}
```

**Diagnosis:**

1. **SORT at top with `usedDisk: true`** → 115MB of data sorted to disk — catastrophic
2. **3421 docs examined for 50 returned** → ratio 68:1 — the `status $in` filter is applied post-IXSCAN on all of CUST-8819's orders (3421 total), then they are all sorted, then 50 taken
3. **Index `customerId_1` only** → does not cover the `status` filter or the `createdAt` sort

**Root Cause:** The existing index `{ customerId: 1 }` finds all orders for the customer (3421), but does not help filter by status or sort by date. MongoDB must fetch all 3421 documents, apply the status filter in memory, sort them all, then take 50.

**Fix:**

```javascript
db.orders.createIndex({ customerId: 1, status: 1, createdAt: -1 })
```

**Re-run explain after index creation:**

```json
{
  "queryPlanner": {
    "winningPlan": {
      "stage": "FETCH",
      "inputStage": {
        "stage": "IXSCAN",
        "indexName": "customerId_1_status_1_createdAt_-1",
        "indexBounds": {
          "customerId": ["[\"CUST-8819\", \"CUST-8819\"]"],
          "status": ["[\"confirmed\", \"confirmed\"]", "[\"pending\", \"pending\"]"],
          "createdAt": ["[MaxKey, MinKey]"]
        }
      }
    }
  },
  "executionStats": {
    "executionTimeMillis": 3,
    "nReturned": 50,
    "totalKeysExamined": 50,
    "totalDocsExamined": 50
  }
}
```

**Result:**
- Execution time: 2180ms → 3ms (727x improvement)
- Keys examined: 3421 → 50 (ratio 1.0:1)
- No SORT stage (documents come pre-sorted from index)
- No disk spill

---

## 3.8 Exercises

### Exercise 3.1: Explain Interpretation
Analyze the following explain output and answer: What is wrong? What index would fix it?

```json
{
  "winningPlan": {
    "stage": "SORT",
    "inputStage": {
      "stage": "FETCH",
      "docsExamined": 85000,
      "inputStage": {
        "stage": "IXSCAN",
        "indexName": "region_1",
        "keysExamined": 85000
      }
    }
  },
  "executionStats": {
    "nReturned": 25,
    "totalKeysExamined": 85000,
    "totalDocsExamined": 85000,
    "executionTimeMillis": 890
  }
}
```

### Exercise 3.2: Stage Prediction
Without running the query, predict the execution stage tree for:

```javascript
db.users.find(
  { country: "US", premium: true },
  { name: 1, email: 1, _id: 0 }
).sort({ joinDate: -1 }).limit(10)
```

Available indexes: `{ country: 1 }`, `{ premium: 1 }`, `{ joinDate: -1 }`

What is the optimal index? Would it produce a covered query?

### Exercise 3.3: Covered Query Design
Design an index that makes this query fully covered (no FETCH stage):

```javascript
db.products.find(
  { category: "electronics", inStock: true },
  { name: 1, price: 1, sku: 1, _id: 0 }
)
```

---

## 3.9 Knowledge Check

1. What additional information does `executionStats` provide over `queryPlanner`?
2. A query has `totalKeysExamined: 50000` and `nReturned: 10`. What does this tell you?
3. What does `usedDisk: true` in a SORT stage indicate and why is it critical?
4. When does a PROJECTION become a `PROJECTION_COVERED`?
5. What is the `indexBounds` field and how do you interpret a range vs. a point lookup?

---

## 3.10 Interview-Style Questions

**Q: In an explain output, you see COLLSCAN even though an index exists on the filter field. Why might MongoDB choose COLLSCAN over IXSCAN?**

> Model answer: MongoDB's planner chose COLLSCAN because it estimated the index would be less efficient than a full scan. This typically happens when the index has very low selectivity — for example, a `{ status: 1 }` index on a field where 95% of documents have the same value. In this case, an IXSCAN would examine almost all index entries, then fetch almost all documents. A COLLSCAN has less overhead because it avoids the index B-tree traversal and reads documents sequentially (sequential reads are faster than random reads from IXSCAN). The fix is to improve index selectivity (use more fields in a compound index) rather than forcing an index with `$hint`.

**Q: You run `explain("executionStats")` and the query looks fast (3ms). Your users are complaining the API is slow (500ms). Where is the difference?**

> Model answer: `explain("executionStats")` measures pure query execution time on the database server. The 497ms gap is likely in: (1) network latency between application and database server; (2) application-side document deserialization from BSON to language objects; (3) connection acquisition time from the connection pool if the pool is exhausted; (4) application-side processing after the query returns; (5) waterfall effect if the API makes multiple sequential queries. The fix depends on diagnosis: use distributed tracing (OpenTelemetry, Datadog APM) to identify which layer is consuming the 497ms.

---

*Next: [Module 04: Indexing Fundamentals →](04-indexing-fundamentals.md)*
