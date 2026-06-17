# Module 11: Optimizer Statistics and the Cost-Based Optimizer

## 1. What Problem This Module Solves

The query optimizer is not magic. It is a cost-based estimator that makes mathematical predictions about how expensive different execution plans will be — and those predictions are only as good as the statistics they are based on. When statistics are stale, missing, or misleading, the optimizer makes wrong choices: choosing Nested Loops when it should use Hash Join, picking a full table scan over a perfectly good index, or choosing the wrong driving table in a multi-table join.

Understanding the Cost-Based Optimizer (CBO) is the difference between a developer who guesses at query problems and one who can predict the optimizer's behavior from first principles.

---

## 2. Core Technical Concepts & Deep Dives

### 2.1 What the Cost-Based Optimizer Does

The CBO's job is to enumerate possible execution plans for a SQL query, assign a cost estimate to each, and select the plan with the lowest estimated cost.

```
SQL Query
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│                  QUERY OPTIMIZER PIPELINE                     │
│                                                               │
│  Parser → Semantics Checker → Logical Plan                    │
│                                          │                    │
│                    ┌─────────────────────┘                   │
│                    ▼                                          │
│            Transformation Engine                             │
│        (Rewrite: subquery → join, etc.)                      │
│                    │                                          │
│                    ▼                                          │
│         Candidate Plan Enumeration                           │
│     (Join order permutations, access paths)                  │
│                    │                                          │
│                    ▼                                          │
│          Cost Estimation Model                               │
│  ┌──────────────────────────────────────────────────┐        │
│  │ selectivity_estimate × table_cardinality          │        │
│  │    × I/O_cost_per_block                           │        │
│  │    + CPU_cost_per_row                             │        │
│  └──────────────────────────────────────────────────┘        │
│                    │                                          │
│                    ▼                                          │
│             Winning Plan Selected                            │
└───────────────────────────────────────────────────────────────┘
```

**Key inputs to cost estimation:**
1. **Table cardinality** — How many rows are in the table?
2. **Column statistics (histograms)** — How are values distributed?
3. **Index statistics** — What is the clustering factor?
4. **System statistics** — How fast is disk I/O vs. CPU on this machine?

---

### 2.2 Table and Column Statistics

#### What Gets Collected

```sql
-- PostgreSQL: Collect statistics on a table
ANALYZE employees;

-- Oracle: Gather table statistics
BEGIN
    DBMS_STATS.GATHER_TABLE_STATS(
        ownname   => 'HR',
        tabname   => 'EMPLOYEES',
        cascade   => TRUE    -- Also gather index statistics
    );
END;

-- SQL Server: Update statistics
UPDATE STATISTICS employees;
-- Or: auto-update is configured via database settings

-- MySQL: Analyze table
ANALYZE TABLE employees;
```

**What is stored per column:**
- `n_distinct` — Number of distinct values (cardinality)
- `null_frac` — Fraction of NULL values
- `avg_width` — Average byte size of column values
- `correlation` — Correlation between column order and physical row order (0 = random, 1 = perfectly sorted)
- **Most Common Values (MCV)** — Top-N most frequent values and their frequencies
- **Histogram** — Bucket-based distribution of all values

---

### 2.3 Histograms: The Optimizer's Distribution Map

Without a histogram, the optimizer assumes **uniform distribution**: if there are 100 distinct values and 1 million rows, it estimates each value appears exactly 10,000 times (1% selectivity).

In reality, data is almost never uniformly distributed. An `orders.status` column might have:
- `'completed'`: 85% of rows
- `'pending'`: 10% of rows
- `'cancelled'`: 4% of rows
- `'refunded'`: 1% of rows

Without a histogram, a query `WHERE status = 'refunded'` is estimated at 25% selectivity (1/4 distinct values) — 25x overestimated. The optimizer might choose a full table scan when an index would be far faster.

**Types of histograms:**

```
EQUAL-WIDTH (Equi-Height) Histogram:
  Divides value range into equal-width buckets
  Good for: Uniformly distributed data
  Bad for: Skewed distributions

FREQUENCY Histogram (Most-Common-Values based):
  Explicitly tracks exact frequency of each distinct value
  Good for: Low-cardinality columns (status, country_code)
  PostgreSQL: MCV list + histogram combined

EQUI-DEPTH Histogram:
  Each bucket contains approximately equal number of rows
  Good for: High-cardinality skewed data
  Oracle, SQL Server primarily
```

**Checking histogram data in PostgreSQL:**
```sql
-- View column statistics collected for a table
SELECT 
    attname AS column_name,
    n_distinct,
    null_frac,
    avg_width,
    most_common_vals,
    most_common_freqs,
    histogram_bounds
FROM pg_stats
WHERE tablename = 'orders'
ORDER BY attname;
```

---

### 2.4 Stale Statistics: The Silent Performance Killer

**Scenario: The statistics disaster**

```
Day 1: orders table has 10,000 rows.
       ANALYZE runs. Statistics: 10,000 rows, status distribution: 50% pending, 50% completed.
       Optimizer estimates a query for status='pending' returns 5,000 rows → chooses Hash Join.

Day 180: 3,000,000 rows imported via batch loading.
         ANALYZE was NOT run after the batch load.
         Actual row count: 3,010,000. Pending: 500 rows (0.02%).
         Optimizer STILL thinks there are 10,000 rows, 50% pending → 5,000 rows.
         Optimizer STILL chooses Hash Join — but should choose Nested Loop with index.
         Result: 3 second query that should take 5ms.
```

**Detecting stale statistics:**

```sql
-- PostgreSQL: Check when statistics were last collected
SELECT 
    schemaname,
    tablename,
    last_analyze,
    last_autoanalyze,
    n_live_tup,    -- Current live row estimate
    n_dead_tup,    -- Dead rows (not vacuumed yet)
    analyze_count
FROM pg_stat_user_tables
ORDER BY last_analyze ASC NULLS FIRST;

-- Tables with NULL last_analyze or very old dates need immediate ANALYZE
```

**Forcing statistics rebuild after large data changes:**
```sql
-- PostgreSQL: After bulk load of 5M rows
ANALYZE orders;  -- Fast: samples the table

-- For extremely critical tables, increase statistics target (default: 100):
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 500;
ANALYZE orders;
-- More histogram buckets = more accurate estimates for this column
```

---

### 2.5 The Join Order Problem

For a query joining N tables, the optimizer must evaluate `N!` possible join orderings. For N=5 tables: 120 orderings. For N=10: 3,628,800 orderings.

**Practical example with 4 tables:**

```sql
SELECT * FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE c.country_code = 'US' AND p.category = 'Electronics';
```

The optimizer estimates result sizes at each join step. Starting with the most selective table minimizes intermediate result sizes:

```
Option 1 (Optimal): customers (US filter: 10K rows) 
  → orders (10K × avg 5 orders = 50K rows)
  → order_items (50K × avg 5 items = 250K rows)
  → products (filter to Electronics: 50K rows)
  Intermediate peak: 250K rows

Option 2 (Suboptimal): products 
  → order_items (all 5M rows match all products)
  → orders (5M rows)
  → customers (filter US: 100K rows)
  Intermediate peak: 5M rows
```

The optimizer selects Option 1 because it minimizes peak intermediate result size.

**When the optimizer gets it wrong:** With stale statistics, `customers` might be estimated at 500,000 rows instead of 10,000. The optimizer then ranks it as a large table and chooses a different join order, creating larger intermediates.

---

### 2.6 Cardinality Estimation Failures and Fixes

**Parameter Sniffing / Bind Variable Peeking:**

```sql
-- This plan is compiled once and cached:
SELECT * FROM orders WHERE status = :status_param;

-- First execution: status = 'cancelled' (100 rows) → Nested Loop chosen
-- Plan cached for shape "status = ?"

-- Second execution: status = 'completed' (2,000,000 rows) → Nested Loop is catastrophic
-- But the cached plan is used without re-optimization
```

**Database-specific fixes:**

```sql
-- PostgreSQL: Force re-planning by clearing plan cache
-- (Plans are NOT cached across sessions in PostgreSQL by default)
-- PostgreSQL re-plans on each new connection for non-prepared statements

-- SQL Server: Trace flag to force recompile per execution (use sparingly)
SELECT * FROM orders WHERE status = @status_param
OPTION (RECOMPILE);

-- Oracle: Adaptive Cursor Sharing
-- Oracle detects when bind variable values produce different selectivities
-- and creates child cursors with different plans for different value ranges
```

---

### 2.7 Statistics Target Tuning (PostgreSQL)

```sql
-- Default statistics target (100 histogram buckets):
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 100;

-- For highly skewed columns with many distinct values, increase to 500+:
ALTER TABLE orders ALTER COLUMN customer_id SET STATISTICS 500;
ANALYZE orders;

-- View current targets:
SELECT attname, attstattarget 
FROM pg_attribute 
WHERE attrelid = 'orders'::regclass AND attstattarget != 0;

-- Check if estimates are now closer to actuals:
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 12345;
-- Compare "rows=X" (estimate) with "actual rows=Y" — should be within 2x
```

---

## 3. Code & Query Performance Lab

### 3.1 Simulating a Statistics Problem

```sql
-- Create and populate test table
CREATE TABLE stat_demo (
    id SERIAL PRIMARY KEY,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Insert highly skewed data
INSERT INTO stat_demo (status, created_at)
SELECT 
    CASE 
        WHEN random() < 0.95 THEN 'active'
        WHEN random() < 0.99 THEN 'suspended'
        ELSE 'deleted'
    END,
    NOW() - (random() * INTERVAL '365 days')
FROM generate_series(1, 100000);

CREATE INDEX idx_stat_demo_status ON stat_demo (status);

-- Run ANALYZE with default settings
ANALYZE stat_demo;

-- Check what the optimizer estimates for 'deleted' (only ~500 rows):
EXPLAIN SELECT * FROM stat_demo WHERE status = 'deleted';
-- Compare estimated rows vs actual (run EXPLAIN ANALYZE to see actual)
EXPLAIN ANALYZE SELECT * FROM stat_demo WHERE status = 'deleted';

-- Increase statistics for this column:
ALTER TABLE stat_demo ALTER COLUMN status SET STATISTICS 500;
ANALYZE stat_demo;

-- Check again — estimates should be more accurate now
EXPLAIN ANALYZE SELECT * FROM stat_demo WHERE status = 'deleted';
```

### 3.2 Validating Estimate Accuracy

```sql
-- A useful diagnostic query: estimate accuracy ratio
-- Run this after any query optimization to validate statistics quality

EXPLAIN (ANALYZE, FORMAT JSON) 
SELECT status, COUNT(*) FROM stat_demo GROUP BY status;
-- In the JSON output, find each node's:
--   "Plan Rows" (estimate) vs "Actual Rows" (truth)
-- Ratio > 10x or < 0.1x indicates stale/insufficient statistics
```

---

## 4. Hands-on Exercises

1. **Stale Statistics Simulation:**
   Create a table with 10,000 rows, run `ANALYZE`, then insert 1,000,000 more rows WITHOUT running `ANALYZE`. Compare the `EXPLAIN` estimate vs. the actual count for a simple WHERE query. Then re-run `ANALYZE` and verify the estimate improves.

2. **Histogram Inspection:**
   Using the `pg_stats` view, query the histogram data for the `status` column of any existing table. Calculate the expected selectivity for each status value and compare it to the actual distribution using a `GROUP BY` count.

3. **Statistics Target Experiment:**
   For a column with 50 distinct values, set `STATISTICS` to 10 (very low) and observe how the optimizer estimate changes for rare values. Then set it to 1000 and observe the improvement.

---

## 5. Deep-Dive Interview Questions

### Q1: What is "parameter sniffing" and when does it become a problem in SQL Server?

**Answer:** Parameter sniffing is SQL Server's behavior of "peeking" at the literal value of a parameter during query compilation and using that value to estimate selectivity and build the execution plan. The problem arises when the compiled plan is cached and reused for subsequent executions with very different parameter values. For example, if the first execution uses `status = 'deleted'` (100 rows → Nested Loop chosen and cached), and the next execution uses `status = 'active'` (500,000 rows → should use Hash Join), the cached Nested Loop plan runs catastrophically slowly. Solutions include: `OPTION (RECOMPILE)` to force per-execution compilation, plan guides to pin specific plans, `OPTIMIZE FOR UNKNOWN` hint to use average selectivity, or using local variables (which SQL Server does not sniff).

### Q2: How does PostgreSQL's auto-vacuum affect optimizer statistics, and what happens when it falls behind?

**Answer:** PostgreSQL's autovacuum daemon runs both VACUUM (removes dead row versions created by MVCC) and ANALYZE (collects statistics). By default, autovacuum triggers ANALYZE after 20% of the table's rows have been inserted or updated. If autovacuum is disabled, or the table experiences very high write throughput (inserts faster than autovacuum can process), statistics fall behind. Consequences: optimizer cardinality estimates become stale, causing plan regressions. The `pg_stat_user_tables` view's `n_dead_tup` (dead rows) and `last_autoanalyze` columns detect this. Mitigation: increase `autovacuum_analyze_scale_factor` reduction for large tables, add more autovacuum workers, or run manual `ANALYZE` after large batch operations.

### Q3: Oracle collects "system statistics" in addition to table statistics. What are these and why do they matter?

**Answer:** Oracle's system statistics model the hardware performance characteristics of the specific machine: the speed of random vs. sequential disk I/O (in milliseconds per block read), CPU cycle time (nanoseconds per operation), and I/O throughput (MB/s). The CBO incorporates these into its cost formula: `cost = (disk_io_cost × block_reads) + (cpu_cost × operations)`. On fast NVMe SSDs, random I/O is cheap — the optimizer should prefer index scans even for relatively large ranges. On slow spinning disks, sequential full-table scans are relatively cheaper. If system statistics reflect an old hardware configuration (e.g., gathered on HDDs but now running on NVMe SSDs), the optimizer over-penalizes random I/O costs, preferring table scans when index scans would be faster. `DBMS_STATS.GATHER_SYSTEM_STATS('START')` re-collects these.

---

## 6. Summary & Key Takeaways

- **The CBO uses statistics** — cardinality, histograms, and clustering factors — to estimate plan costs. Wrong statistics = wrong plans.
- **Histograms model data skew.** Without them, the optimizer assumes uniform distribution and severely miscalculates selectivity for skewed columns.
- **Statistics grow stale** after bulk loads, deletes, or major data distribution shifts. Always run `ANALYZE` (or equivalent) after large data operations.
- **Join order matters.** The optimizer orders joins to minimize intermediate result sets. Stale statistics lead to wrong join order and exponentially larger intermediates.
- **Statistics target** controls histogram resolution. Increase it for highly selective, skewed columns used in critical query filters.
- **Parameter sniffing / bind peeking** can cache wrong plans. Use per-execution recompile hints for queries with extreme selectivity variance.
