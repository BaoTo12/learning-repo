# Module 12: Table Partitioning for Performance

## 1. What Problem This Module Solves

When tables grow to hundreds of millions or billions of rows, even perfectly indexed queries begin to slow down. Index B-tree traversal is O(log N) — but as N grows into the billions, the absolute number of I/O operations still increases. The index itself becomes so large that its working pages no longer fit in the buffer pool, causing cache misses on every lookup.

Partitioning addresses this by physically dividing a large table into smaller, manageable sub-tables (partitions) while presenting them as a single logical table to the application. With partitioning, a query that once scanned a 1 billion row table can be redirected to scan only the 10 million rows in the relevant partition — a 100x reduction in I/O.

---

## 2. Core Technical Concepts & Deep Dives

### 2.1 What Is Partitioning?

Table partitioning splits a table's rows across multiple physical storage segments (partitions) based on a **partition key** column. The database automatically routes inserts to the correct partition and queries to only the relevant partition(s).

```
Logical Table: orders

              ┌─────────────────────────────────────────────┐
              │               orders (logical)               │
              └──────────┬────────────┬─────────────────────┘
                         │            │
        ┌────────────────┘            └──────────────────────┐
        │                                                     │
        ▼                                                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│orders_2022    │   │orders_2023    │   │orders_2024    │   │orders_2025    │
│(Physical)     │   │(Physical)     │   │(Physical)     │   │(Physical)     │
│Jan-Dec 2022   │   │Jan-Dec 2023   │   │Jan-Dec 2024   │   │Jan-Dec 2025   │
└───────────────┘   └───────────────┘   └───────────────┘   └───────────────┘
```

---

### 2.2 Partition Pruning: The Core Performance Mechanism

**Partition pruning** occurs when the query optimizer detects that only specific partitions can contain rows matching the WHERE clause, and physically skips all other partitions.

```sql
-- Without partitioning: scans all 1 billion rows
SELECT * FROM orders WHERE order_date >= '2024-01-01' AND order_date < '2025-01-01';

-- With range partitioning on order_date: only scans orders_2024 (100M rows)
-- 10x reduction in I/O with zero application code changes
```

**EXPLAIN to verify pruning (PostgreSQL):**
```sql
EXPLAIN SELECT * FROM orders
WHERE order_date >= '2024-01-01' AND order_date < '2025-01-01';

-- Look for: Partitions removed: 3 out of 4
-- Or: In Append node, only orders_2024 appears
```

---

### 2.3 Range Partitioning

Divides data into partitions based on a range of values — most commonly date/time ranges.

```sql
-- PostgreSQL: Range partitioning on order_date
CREATE TABLE orders (
    order_id    BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    order_date  DATE NOT NULL,
    total       NUMERIC(12,2) NOT NULL,
    status      VARCHAR(20) NOT NULL
) PARTITION BY RANGE (order_date);

-- Create annual partitions
CREATE TABLE orders_2022 PARTITION OF orders
    FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');

CREATE TABLE orders_2023 PARTITION OF orders
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');

CREATE TABLE orders_2024 PARTITION OF orders
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

-- Default partition catches anything outside defined ranges:
CREATE TABLE orders_default PARTITION OF orders DEFAULT;
```

**SQL Server: Range partitioning**
```sql
-- Step 1: Create partition function (defines the boundaries)
CREATE PARTITION FUNCTION pf_orders_date (DATE)
AS RANGE RIGHT FOR VALUES ('2023-01-01', '2024-01-01', '2025-01-01');
-- RANGE RIGHT: boundary value belongs to the right (newer) partition

-- Step 2: Create partition scheme (maps function to filegroups)
CREATE PARTITION SCHEME ps_orders_date
AS PARTITION pf_orders_date
ALL TO ([PRIMARY]);  -- Or to separate filegroups for I/O isolation

-- Step 3: Create partitioned table
CREATE TABLE orders (
    order_id    BIGINT NOT NULL,
    order_date  DATE NOT NULL,
    total       NUMERIC(12,2) NOT NULL
) ON ps_orders_date(order_date);
```

**Oracle: Range partitioning**
```sql
CREATE TABLE orders (
    order_id  NUMBER NOT NULL,
    order_date DATE NOT NULL,
    total      NUMBER(12,2)
)
PARTITION BY RANGE (order_date) (
    PARTITION orders_2022 VALUES LESS THAN (DATE '2023-01-01'),
    PARTITION orders_2023 VALUES LESS THAN (DATE '2024-01-01'),
    PARTITION orders_2024 VALUES LESS THAN (DATE '2025-01-01'),
    PARTITION orders_future VALUES LESS THAN (MAXVALUE)
);
```

---

### 2.4 List Partitioning

Divides data based on discrete values of the partition key.

```sql
-- PostgreSQL: List partitioning on region
CREATE TABLE sales (
    sale_id   BIGINT NOT NULL,
    region    VARCHAR(20) NOT NULL,
    amount    NUMERIC(10,2) NOT NULL
) PARTITION BY LIST (region);

CREATE TABLE sales_north PARTITION OF sales
    FOR VALUES IN ('north', 'northeast', 'northwest');

CREATE TABLE sales_south PARTITION OF sales
    FOR VALUES IN ('south', 'southeast', 'southwest');

CREATE TABLE sales_international PARTITION OF sales
    FOR VALUES IN ('europe', 'asia', 'latam');

-- Query that prunes to a single partition:
SELECT * FROM sales WHERE region = 'north';
-- Only sales_north is scanned
```

---

### 2.5 Hash Partitioning

Distributes rows evenly across partitions using a hash function on the partition key. Used to avoid "hot partition" problems when data has no natural range or list distribution.

```sql
-- PostgreSQL: Hash partitioning on customer_id (for even write distribution)
CREATE TABLE user_events (
    event_id    BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    event_type  VARCHAR(50) NOT NULL,
    event_ts    TIMESTAMP NOT NULL
) PARTITION BY HASH (customer_id);

CREATE TABLE user_events_p0 PARTITION OF user_events
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE user_events_p1 PARTITION OF user_events
    FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE user_events_p2 PARTITION OF user_events
    FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE user_events_p3 PARTITION OF user_events
    FOR VALUES WITH (MODULUS 4, REMAINDER 3);
```

**Hash partitioning trade-off:** Excellent for write distribution and reducing per-partition size, but queries must scan ALL partitions unless the partition key is in the WHERE clause with an exact equality.

---

### 2.6 Composite Partitioning (Sub-Partitioning)

Partitions the data on multiple levels: first by range, then by list within each range partition.

```sql
-- Oracle: Range-Hash composite partitioning
CREATE TABLE transactions (
    txn_id      NUMBER NOT NULL,
    txn_date    DATE NOT NULL,
    account_id  NUMBER NOT NULL,
    amount      NUMBER(15,2) NOT NULL
)
PARTITION BY RANGE (txn_date)
SUBPARTITION BY HASH (account_id) SUBPARTITIONS 8
(
    PARTITION txn_2023 VALUES LESS THAN (DATE '2024-01-01'),
    PARTITION txn_2024 VALUES LESS THAN (DATE '2025-01-01'),
    PARTITION txn_2025 VALUES LESS THAN (DATE '2026-01-01')
);
-- Each year partition is subdivided into 8 hash sub-partitions
-- Query by date range: prunes to 1 year × 8 sub-partitions = 8 physical segments
-- Query by date + account: prunes to 1 year × 1 sub-partition = 1 physical segment
```

---

### 2.7 Partition-Level Index Management

**Local Indexes:** A separate index B-tree exists per partition, containing only entries for rows in that partition.

```sql
-- PostgreSQL: Indexes on partitioned tables are automatically local
CREATE INDEX idx_orders_customer ON orders (customer_id);
-- Creates idx_orders_2022_customer, idx_orders_2023_customer, etc.

-- When querying a specific partition (via partition pruning),
-- only the local index for that partition is used
-- The index B-tree is smaller: proportional to partition size, not full table size
```

**Global Indexes (Oracle, SQL Server):** A single index B-tree spans all partitions.

```sql
-- Oracle: Create a global index (explicit)
CREATE INDEX idx_orders_txn_id ON orders (order_id) GLOBAL;

-- Global indexes are useful for unique constraints across the entire table
-- But: partition DROP/TRUNCATE requires global index maintenance or rebuild!
```

**The critical trade-off:**

| Index Type | Query Performance | Partition Drop Cost | Index Size |
| :--- | :--- | :--- | :--- |
| Local | Fast (small B-tree per partition) | Cheap (drop partition's local index) | Small per partition |
| Global | Fast for cross-partition lookups | **Expensive** (must rebuild or maintain) | Large (full table) |

**Engineering rule:** Prefer local indexes. Use global indexes only for uniqueness constraints that must span partitions.

---

### 2.8 Partition Maintenance: The Sliding Window Pattern

Range-partitioned time-series data typically follows a **sliding window** maintenance pattern: add a new partition for the incoming period, and archive or drop the oldest partition.

```sql
-- PostgreSQL: Monthly partition rotation

-- Add next month's partition (done via scheduled job, monthly):
CREATE TABLE orders_2025_02 PARTITION OF orders
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

-- Archive old partition by detaching it from the parent table:
ALTER TABLE orders DETACH PARTITION orders_2022;
-- Now orders_2022 exists as a standalone table — archive to cold storage
-- Detach is INSTANT (just updates catalog metadata — no data movement!)

-- Drop old partition entirely (irreversible!):
DROP TABLE orders_2022;
-- Also INSTANT — one catalog operation, no row-by-row DELETE
```

**Why this matters:** Deleting 100 million old rows with `DELETE WHERE order_date < '2022-01-01'` generates 100 million undo log entries, massive I/O, and takes hours. Dropping a partition is an O(1) catalog operation that takes milliseconds.

---

### 2.9 When NOT to Partition

Partitioning is not universally beneficial:

❌ **Small to medium tables (< 10 million rows):** The overhead of partition routing, catalog lookups, and index management exceeds the benefit. A well-indexed non-partitioned table is almost always faster below 10M rows.

❌ **OLTP point lookups:** If your primary query pattern is `WHERE order_id = 12345` (a unique lookup), partitioning provides no benefit — the B-tree traversal to find `order_id = 12345` is already O(log N), and the partition must be identified first via an additional lookup.

❌ **When the partition key is not in most queries:** If you partition by `order_date` but most queries filter on `customer_id` (no date filter), every query scans all partitions (full table scan across all partitions — worse than no partitioning).

❌ **Cross-partition aggregations without pruning:** `SELECT COUNT(*) FROM orders` with no WHERE clause still scans all partitions — no benefit over a non-partitioned table.

---

## 3. Code & Query Performance Lab

### 3.1 Partition Pruning Verification

```sql
-- Create partitioned test table
CREATE TABLE events (
    event_id    BIGINT GENERATED ALWAYS AS IDENTITY,
    event_date  DATE NOT NULL,
    event_type  VARCHAR(50) NOT NULL,
    user_id     BIGINT NOT NULL,
    payload     TEXT
) PARTITION BY RANGE (event_date);

CREATE TABLE events_q1_2024 PARTITION OF events
    FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE events_q2_2024 PARTITION OF events
    FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE events_q3_2024 PARTITION OF events
    FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE events_q4_2024 PARTITION OF events
    FOR VALUES FROM ('2024-10-01') TO ('2025-01-01');

CREATE INDEX ON events (event_date);
CREATE INDEX ON events (user_id);

-- Insert test data
INSERT INTO events (event_date, event_type, user_id, payload)
SELECT 
    DATE '2024-01-01' + (n % 365),
    CASE n % 3 WHEN 0 THEN 'login' WHEN 1 THEN 'purchase' ELSE 'view' END,
    (n % 10000) + 1,
    'payload_' || n
FROM generate_series(1, 1000000) n;

-- Verify pruning:
EXPLAIN SELECT * FROM events
WHERE event_date >= '2024-04-01' AND event_date < '2024-07-01';
-- Should show: only events_q2_2024 scanned

EXPLAIN SELECT * FROM events
WHERE user_id = 42;
-- Should show: ALL partitions scanned (no pruning — user_id is not partition key)
-- This is a case where partitioning by event_date hurts user_id queries!
```

### 3.2 Sliding Window Partition Management

```sql
-- Simulate monthly partition management:

-- Add next quarter partition:
CREATE TABLE events_q1_2025 PARTITION OF events
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

-- Detach oldest partition for archiving:
ALTER TABLE events DETACH PARTITION events_q1_2024;
-- events_q1_2024 now exists as a standalone table

-- Verify that the main table no longer includes Q1 2024 data:
SELECT COUNT(*) FROM events WHERE event_date = '2024-01-15';
-- Should return 0 (data is in detached table)

-- The detached table still exists independently:
SELECT COUNT(*) FROM events_q1_2024;
-- Still has all Q1 2024 data for archiving
```

---

## 4. Hands-on Exercises

1. **Pruning Analysis:** Create a list-partitioned table on `country_code` with 5 partitions (US, EU, APAC, LATAM, OTHER). Insert 500,000 rows. Run `EXPLAIN ANALYZE` for queries with and without the `country_code` filter. Measure the difference in rows examined.

2. **Maintenance Operation Comparison:** Insert 1 million rows into a non-partitioned table. Time how long it takes to `DELETE` all rows from a specific year. Then create a partitioned equivalent and time how long `DETACH PARTITION` takes. Record the difference.

3. **Index Design for Partitioned Tables:** For a range-partitioned `transactions` table partitioned by `transaction_date`, design the optimal local index strategy for these three query patterns:
   - `WHERE account_id = 123 AND transaction_date >= last_month`
   - `WHERE transaction_date >= yesterday AND amount > 10000`
   - `WHERE transaction_id = 99999999` (primary key lookup)

---

## 5. Deep-Dive Interview Questions

### Q1: When would you choose hash partitioning over range partitioning for a time-series events table?

**Answer:** Hash partitioning is preferable when the write workload is the primary concern and most queries include the partition key with equality (not range). If a time-series table has one extremely active recent partition receiving all new inserts (hot partition), I/O contention is concentrated on that partition. Hash partitioning distributes writes evenly. However, the trade-off is critical: range queries (`WHERE event_date BETWEEN x AND y`) must scan ALL hash partitions because the hash function does not preserve date ordering — there is no pruning for date ranges. The right choice depends on whether the primary workload is: (a) high-concurrency inserts (hash wins), or (b) range-based time-series queries (range partitioning wins).

### Q2: What happens to a global index in Oracle when you drop a partition, and how do you handle this in production?

**Answer:** When a partition is dropped in Oracle, all global indexes become **unusable** (marked as invalid) because their entries point to rows that no longer exist. Any subsequent query using a global index will fail with `ORA-01502: index is in unusable state`. Solutions: (1) Include `UPDATE GLOBAL INDEXES` in the `DROP PARTITION` statement — Oracle rebuilds the global indexes synchronously during the drop, which can be slow for large indexes. (2) Use `INVALIDATE` (default) and schedule an `ALTER INDEX ... REBUILD` during a maintenance window. (3) Prefer local indexes over global indexes for partitioned tables, eliminating the problem entirely. (4) Use the `PARTITION EXCHANGE` pattern instead of `DROP PARTITION` — exchange the partition with an empty staging table (preserving global indexes) before dropping the empty staging table.

### Q3: A partitioned table uses `event_date` as the partition key. A query runs `WHERE user_id = 42` with no date filter. How does this query perform compared to the same query on a non-partitioned table?

**Answer:** It performs the same or worse. Partition pruning only works when the partition key column appears in the WHERE clause with a filter that allows the optimizer to identify which partitions are relevant. A query filtering only on `user_id` cannot prune any partitions — the optimizer must scan all partitions, which is functionally equivalent to a full table scan on the original table. With a local index on `user_id`, the optimizer must scan the `user_id` local index across ALL partitions (N index lookups for N partitions) versus a single global B-tree lookup on a non-partitioned table. The correct fix: if `user_id` queries are important, ensure `user_id` is part of the index on each partition, or reconsider whether the partition key choice is appropriate for the actual query workload.

---

## 6. Summary & Key Takeaways

- **Partition pruning** is the core performance mechanism. It only works when the partition key is in the WHERE clause, enabling the optimizer to skip irrelevant partitions.
- **Range partitioning** is ideal for time-series data with date-range queries and rolling window data management.
- **List partitioning** is ideal for categorical data (region, country, status) with discrete value distributions.
- **Hash partitioning** is ideal for high-concurrency write distribution but sacrifices range query pruning.
- **Local indexes** (one B-tree per partition) are the best practice — they are smaller, cheaper to maintain, and not invalidated by partition drops.
- **Partition maintenance** (DETACH/DROP) is orders of magnitude faster than row-by-row DELETE for large data lifecycle management.
- **Partition key selection is architectural** — the partition key must align with the dominant query pattern. A mismatch causes every query to scan all partitions, negating all benefits.
