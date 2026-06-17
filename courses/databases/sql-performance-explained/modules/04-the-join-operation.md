# Module 04: Optimizing SQL Join Operations

## 1. What Problem This Module Solves
In relational databases, data is split across multiple normalized tables. Reassembling this data at query time requires **Join Operations**. Join queries are the most common source of performance degradation in SQL databases. A developer writing a join assumes the database resolves relationships automatically. Without correct indexes, join execution times degrade exponentially.

Common join-related performance failures include:
*   **Nested Loop explosions**, where the engine scans the entire inner table for every row of the outer table.
*   **Memory starvation during Hash Joins**, forcing the database to spill intermediate hash tables to disk (tempdb/workfiles), which degrades query times by $100\times$.
*   **Redundant sorting operations** during Sort Merge joins, consuming excessive CPU and disk space.

This module details the three primary SQL join algorithms—Nested Loops, Hash Joins, and Sort Merge Joins—and explains how to design indexes that match their execution patterns.

---

## 2. Why This Topic Matters
Modern microservices and enterprise applications query data spanning multiple tables. When joining tables with millions of rows, selecting the wrong join algorithm or missing a critical join key index can cause a query to take minutes instead of milliseconds.

Understanding how the Cost-Based Optimizer (CBO) evaluates table statistics to pick a join path allows database engineers to structure schemas and index configurations that support high-throughput, concurrent join transactions without saturating server memory or disk storage.

---

## 3. Core Technical Concepts & Deep Dives

Relational engines use three primary join algorithms. The choice depends on the size of the datasets, the presence of indexes, and the join condition operators.

### 3.1 Nested Loops Join
A **Nested Loops Join** is the most direct join algorithm. It behaves like a nested loop in programming:

```
For each row in Outer_Table:
    For each row in Inner_Table:
        If Outer_Table.Join_Key = Inner_Table.Join_Key:
            Output Combined_Row
```

#### Nested Loops Execution Architecture
```
           [OUTER TABLE]
       (Filtered / Sorted)
                │ (Scanned once)
                ▼
         Row 1: [ID: 100] ──────┐
         Row 2: [ID: 101] ──────┼──────┐
                                │      │ (For each row...)
                                ▼      ▼
                         ┌───────────────────┐
                         │   [INNER TABLE]   │
                         │    B-Tree Index   │
                         │    on Join Key    │
                         └─────────┬─────────┘
                                   │ (INDEX RANGE SCAN / UNIQUE SCAN)
                                   ▼
                             Matching Rows
```

*   **Outer Table (Driving Table)**: Read once. The database filters this table using any `WHERE` clause predicates first.
*   **Inner Table**: Searched once *for every row* returned from the outer table.
*   **Indexing Rule**: 
    > [!IMPORTANT]
    > To prevent a Nested Loops join from executing a Full Table Scan on the inner table for every outer row, **the join columns of the inner table must be indexed**. The outer table does not strictly require an index on the join key (though it may have indexes for its own `WHERE` filters).

---

### 3.2 Hash Join
A **Hash Join** is the preferred algorithm when joining large datasets without indexes, or when a large percentage of rows must be joined.

#### Hash Join Execution Phases
```
[PHASE 1: BUILD PHASE]                          [PHASE 2: PROBE PHASE]
  Small Table (Build Input)                       Large Table (Probe Input)
        │                                               │
        ▼                                               ▼
┌───────────────┐                               ┌───────────────┐
│ Hash Function │                               │ Hash Function │
└───────┬───────┘                               └───────┬───────┘
        ▼                                               ▼
┌───────────────────────┐                               │ (Probes match)
│ In-Memory Hash Table  │ ◄─────────────────────────────┘
│ (Bucket-mapped keys)  │
└───────────────────────┘
```

1.  **Build Phase**: The database reads the smaller of the two tables (the **Build Input**), applies a hash function to the join key, and constructs a hash table in memory.
2.  **Probe Phase**: The database reads the larger table (the **Probe Input**), hashes its join key, and probes the in-memory hash table for matches.
3.  **Memory Constraints**: Hash tables are stored in memory pools (e.g., Oracle's PGA, PostgreSQL's `work_mem`, SQL Server's Query Workspace). If the build input exceeds this memory limit, the engine must partition the data and **spill to disk** (TempDB / Worktables), causing high I/O latency.
4.  **Join Conditions**: Hash joins only support equality conditions (`ON a.id = b.id`). They cannot execute inequality joins (`ON a.id > b.id`).

---

### 3.3 Sort Merge Join
A **Sort Merge Join** is used when joining large datasets, particularly when the join keys are already sorted by indexes, or when inequality conditions are used.

#### Sort Merge Execution Phases
1.  **Sort Phase**: Both datasets are sorted on the join key columns (unless they are already retrieved in sorted order from index B-Trees).
2.  **Merge Phase**: Two pointers walk through both sorted datasets in a single pass. If the keys match, the rows are joined. If one key is smaller, its pointer advances.

```
Sorted Dataset A: [10, 12, 15, 20, 25]
                   ▲ (Pointer A)
Sorted Dataset B: [10, 11, 15, 18, 20]
                   ▲ (Pointer B)
Pointer A and B match on 10 -> Join. Pointer B advances to 11.
Pointer A (12) is larger than Pointer B (11) -> Pointer B advances to 15...
```

*   **Index Utility**: If both tables have B-Tree indexes on the join keys, the database bypasses the sorting phase completely, scanning the index leaf nodes directly to merge the data.

---

### 3.4 Optimizer Join Decision Matrix

| Metric | Nested Loops | Hash Join | Sort Merge Join |
| :--- | :--- | :--- | :--- |
| **Best Dataset Sizes** | Small Outer, Any Inner | Large Outer, Large Inner | Large Outer, Large Inner |
| **Indexing Required** | **Critical on Inner Join Key** | None (Indexes are ignored) | Helpful (Bypasses sort phase) |
| **Memory Footprint** | Low (Row-by-row streaming) | High (Stores Build Table in RAM) | Medium (Sort buffers) |
| **Join Operators** | All (`=`, `<`, `>`, `!=`) | **Equality Only** (`=`) | All (`=`, `<`, `>`, `!=`) |

---

## 4. Code & Query Performance Lab

### 4.1 Schema Setup
Let's define a classic parent-child database relationship:

```sql
CREATE TABLE orders (
    order_id    NUMERIC         NOT NULL,
    customer_id NUMERIC         NOT NULL,
    order_date  DATE            NOT NULL,
    status      VARCHAR(20)     NOT NULL,
    CONSTRAINT orders_pk PRIMARY KEY (order_id)
);

CREATE TABLE order_items (
    item_id     NUMERIC         NOT NULL,
    order_id    NUMERIC         NOT NULL,
    product_id  NUMERIC         NOT NULL,
    quantity    NUMERIC         NOT NULL,
    price       NUMERIC(10,2)   NOT NULL,
    CONSTRAINT order_items_pk PRIMARY KEY (item_id)
);

-- We explicitly omit the index on order_items.order_id to demonstrate the FTS nested loop issue
```

### 4.2 Query and Execution Plan Analysis

We execute a query joining both tables for a specific customer:
```sql
SELECT o.order_id, oi.product_id, oi.price 
  FROM orders o 
  JOIN order_items oi ON o.order_id = oi.order_id
 WHERE o.customer_id = 99;
```

#### Execution Plan A: Missing Index (Hash Join Fallback)
Since `order_items.order_id` is not indexed, a Nested Loops join would require a Full Table Scan on `order_items` for every order returned by `customer_id = 99`. The optimizer bypasses Nested Loops and defaults to a Hash Join:

**PostgreSQL Execution Plan:**
```
Hash Join  (cost=15.40..345.50 rows=45 width=24)
  Hash Cond: (oi.order_id = o.order_id)
  ->  Seq Scan on order_items oi  (cost=0.00..280.00 rows=15000 width=20)
  ->  Hash  (cost=15.30..15.30 rows=8 width=8)
        ->  Seq Scan on orders o  (cost=0.00..15.30 rows=8 width=8)
              Filter: (customer_id = 99)
```
*   **The Issue**: The database must scan the entire `order_items` table (15,000 rows) using a sequential scan (`Seq Scan`) to build or probe the hash table, even though we only want items for a single customer.

#### Execution Plan B: Optimized (Nested Loops Join)
We add the index on the inner table join key:
```sql
CREATE INDEX idx_items_order ON order_items (order_id);
```

**Optimized PostgreSQL Execution Plan:**
```
Nested Loop  (cost=0.29..32.40 rows=45 width=24)
  ->  Index Scan using idx_orders_customer on orders o  (cost=0.15..12.30 rows=8 width=8)
        Index Cond: (customer_id = 99)
  ->  Index Scan using idx_items_order on order_items oi  (cost=0.14..2.45 rows=6 width=20)
        Index Cond: (order_id = o.order_id)
```
*   **Result**: The database reads the 8 orders matching `customer_id = 99` using an index, and for each order, performs a fast index lookup on `order_items` using `idx_items_order`. Total physical reads drop to a few blocks.

---

## 5. Hands-on Exercises

1.  **Join Strategy Identification**:
    Determine which join algorithm (Nested Loops, Hash Join, or Sort Merge Join) the database optimizer is most likely to choose for the following queries, and justify your answer:
    *   *Query A*: Joining a small `countries` table (200 rows) with a large `cities` table (50,000 rows) where `cities.country_id` has a B-Tree index.
    *   *Query B*: Joining two massive tables `web_traffic` (50,000,000 rows) and `user_profiles` (10,000,000 rows) on `user_id` where neither table has indexes on the join key.
    *   *Query C*: Joining `employees` and `departments` on `employees.salary > departments.max_budget`.
2.  **Plan Diagnosis**:
    Reviewing an execution plan, you notice a Hash Join where the "Build Input" size is 50GB, and the database server only has 8GB of RAM. Describe the physical behavior of the database under this workload.

---

## 6. Mini-Project: E-Commerce Report Optimization

### Scenario
An e-commerce reporting dashboard query is timing out. The query compiles sales data for corporate clients:

```sql
SELECT c.company_name, o.order_date, p.product_name, oi.quantity * oi.price as line_total
  FROM companies c
  JOIN orders o ON c.company_id = o.company_id
  JOIN order_items oi ON o.order_id = oi.order_id
  JOIN products p ON oi.product_id = p.product_id
 WHERE c.region = 'NORTH_AMERICA';
```

### Table Specifications
*   `companies`: 5,000 rows. Region `'NORTH_AMERICA'` matches 100 companies.
*   `orders`: 1,000,000 rows. Average orders per company is 200.
*   `order_items`: 5,000,000 rows. Average items per order is 5.
*   `products`: 10,000 rows.

### Current Indexes
*   Primary Key indexes exist on `companies(company_id)`, `orders(order_id)`, `order_items(item_id)`, and `products(product_id)`.
*   There are **no foreign key indexes** on join columns.

### Tasks
1.  Map the logical Nested Loops query execution path, detailing how many index lookups or table scans are performed at each join level if the database runs a Nested Loops join using the current index setup.
2.  Propose the exact indexes needed to convert the execution plan into an optimized chain of index-based joins.
3.  Calculate the theoretical number of block lookups before and after your indexing improvements.

#### Solution Model:
1.  *Current Path Analysis*:
    *   Find companies with region = 'NORTH_AMERICA': FTS on `companies` (5,000 rows scanned) -> Returns 100 companies.
    *   Join `orders` on `company_id`: Since `company_id` is not indexed in `orders`, the database must run a FTS on `orders` (1,000,000 rows) for *each* of the 100 companies. This requires 100,000,000 rows to be scanned! (The optimizer will fail over to a Hash Join to prevent this, but it will consume substantial memory).
    *   Join `order_items` on `order_id`: Since `order_id` is not indexed in `order_items`, it would FTS `order_items` (5,000,000 rows) for every matching order.
2.  *Optimal Indexing Layout*:
    *   Create index `idx_companies_region` on `companies(region)`.
    *   Create index `idx_orders_company` on `orders(company_id)`.
    *   Create index `idx_items_order` on `order_items(order_id)`.
    *   `products` join key `product_id` is already covered by its Primary Key index.
3.  *Optimized Lookup Count*:
    *   Retrieve 100 companies using `idx_companies_region` -> 1 B-Tree scan + table fetches (low cost).
    *   For 100 companies, lookup orders using `idx_orders_company` -> 100 index lookups (each retrieving ~200 orders, totaling 20,000 orders).
    *   For 20,000 orders, lookup order items using `idx_items_order` -> 20,000 index lookups (each retrieving ~5 items, totaling 100,000 order items).
    *   For 100,000 items, lookup products using `products_pk` -> 100,000 index lookups.
    *   *Total cost*: Highly targeted index key seek operations, avoiding full table scans.

---

## 7. Deep-Dive Interview Questions

### Q1: In a Nested Loops Join, does it matter which table is chosen as the "driving" (outer) table? Why?
**Answer:** Yes, it is critical. The driving table is scanned once, and for every row it returns, the database performs a lookup on the inner table.
*   If Table A has 10 rows and Table B has 1,000,000 rows, and both are indexed:
    *   *A driving*: The database performs 10 lookups on Table B's index. (Fast: ~30 block reads).
    *   *B driving*: The database performs 1,000,000 lookups on Table A's index. (Slow: millions of block reads).
The Cost-Based Optimizer analyzes table statistics and always selects the dataset that returns the **smallest number of filtered rows** as the driving (outer) table.

### Q2: What is the difference between a "One-Pass" and "Two-Pass" Hash Join, and how do they impact disk performance?
**Answer:**
*   **In-Memory / Classic Hash Join**: The build input fits entirely in the database memory allocation. The hash table is built in RAM, probed once, and discarded.
*   **One-Pass Hash Join (Disk Spill)**: If the build input exceeds the memory allocation, the database splits both the build and probe datasets into matching partitions on disk. It loads one partition of the build table into memory at a time, probes it with the corresponding probe partition from disk, and repeats this for all partitions. Each partition is read/written to disk once.
*   **Two-Pass Hash Join (Deep Disk Spill)**: If a single partition is still too large to fit in memory, the database must recursively partition the data, writing and reading blocks to disk multiple times. This causes severe disk thrashing and query slowdowns.

### Q3: Why is a Hash Join unable to execute joins with inequality conditions (e.g., `ON a.id > b.id`)?
**Answer:** Hash functions map data keys to specific, deterministic buckets (e.g., `Hash(10) -> Bucket 4`, `Hash(11) -> Bucket 9`). When probing the hash table, the engine hashes the probe key and looks in that exact bucket.
Inequality conditions (e.g., `a.id > b.id`) mean that a key of `10` matches all keys smaller than `10` (e.g., `9, 8, 7`). Since the hashed values of `9`, `8`, and `7` map to completely different buckets, the engine cannot locate them with a single bucket probe. It would have to scan the entire hash table for every row, which defeats the purpose of the hash table. For inequality conditions, the engine must use a **Nested Loops Join** or a **Sort Merge Join**.

---

## 8. Summary & Key Takeaways
*   **Nested Loops indexing**: In a Nested Loops join, the inner table's join columns must have an index. The outer table is scanned, and its keys drive index searches on the inner table.
*   **Hash Join matching**: Hash Joins construct an in-memory hash table of the smaller dataset and probe it with the larger dataset. They do not use B-Tree indexes, only support equality (`=`) conditions, and can spill to disk if memory boundaries are exceeded.
*   **Sort Merge joins**: Sort Merge Joins sort both datasets on join keys and merge them in a single walk. They benefit from B-Tree indexes because the sorted leaf nodes allow the database to skip the sorting phase.
*   **Join Optimization**: To optimize database joins, analyze execution plans to identify sequential scans on inner tables, and create indexes on those join keys to enable fast Nested Loops.
