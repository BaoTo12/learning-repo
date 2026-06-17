# Module 10: Query Rewriting for Performance

## 1. What Problem This Module Solves

Most SQL performance problems are not index problems — they are **query structure problems**. A developer can have all the right indexes and still write a query the optimizer refuses to push those indexes through. The culprit is query shape: correlated subqueries that re-execute millions of times, `SELECT *` statements that transfer gigabytes of unnecessary data, poorly structured `NOT IN` filters that neutralize all indexes, and aggregations computed too late in the logical pipeline.

This module teaches how to systematically rewrite underperforming SQL queries into semantically equivalent but structurally superior forms that the query optimizer can handle efficiently.

---

## 2. Why This Topic Matters

Query rewrites are **zero-cost optimizations**: they require no schema changes, no new indexes, and no hardware. A query that runs in 60 seconds can often be rewritten to run in 200ms with no infrastructure change. This makes query rewriting the highest-ROI optimization technique available.

---

## 3. Core Technical Concepts & Deep Dives

### 3.1 Correlated Subqueries vs. Derived Tables (JOIN)

A **correlated subquery** is a subquery that references columns from the outer query. It re-executes once for every row of the outer query — effectively turning a single query into N queries.

#### The Anti-Pattern: Correlated Subquery in SELECT

```sql
-- Anti-pattern: Correlated subquery in SELECT
-- Runs: 1 query per order row = O(N) subquery executions
SELECT 
    o.order_id,
    o.order_date,
    (SELECT SUM(oi.quantity * oi.price) 
       FROM order_items oi 
      WHERE oi.order_id = o.order_id) AS order_total
FROM orders o
WHERE o.customer_id = 99;
```

**What happens internally:**
1. The outer query fetches N orders for customer 99 (suppose N = 200).
2. For each of those 200 orders, the database re-executes the `SUM` subquery against `order_items`.
3. Total executions: 1 (outer) + 200 (subquery) = 201 queries.

This is catastrophic at scale. If a customer has 10,000 orders, the subquery runs 10,000 times.

#### The Fix: Derived Table (Pre-Aggregated JOIN)

```sql
-- Correct: Pre-aggregate in derived table, then join once
SELECT 
    o.order_id,
    o.order_date,
    oi_agg.order_total
FROM orders o
JOIN (
    SELECT 
        order_id,
        SUM(quantity * price) AS order_total
    FROM order_items
    GROUP BY order_id
) oi_agg ON o.order_id = oi_agg.order_id
WHERE o.customer_id = 99;
```

**What happens internally:**
1. The derived table `oi_agg` aggregates `order_items` ONCE — scanning the entire table once.
2. The outer query fetches orders for customer 99.
3. A single join merges the two result sets.
4. Total operations: 1 aggregation pass + 1 join.

**Performance improvement:** For 200 orders, this replaces 201 queries with 2 operations — a 100x reduction in database operations.

**PostgreSQL verification:**
```sql
EXPLAIN ANALYZE
SELECT o.order_id, o.order_date, oi_agg.order_total
FROM orders o
JOIN (
    SELECT order_id, SUM(quantity * price) AS order_total
    FROM order_items GROUP BY order_id
) oi_agg ON o.order_id = oi_agg.order_id
WHERE o.customer_id = 99;
-- Expected: HashAggregate + Hash Join — 2 operations, not N+1
```

---

### 3.2 Correlated Subquery in WHERE (EXISTS vs. IN)

#### Anti-Pattern: `NOT IN` with NULL-sensitive semantics

```sql
-- Anti-pattern: NOT IN — fails silently with NULLs
SELECT * FROM orders
WHERE customer_id NOT IN (
    SELECT customer_id FROM blacklisted_customers
);
```

**The hidden NULL bug:** If `blacklisted_customers.customer_id` contains even one `NULL`, the entire `NOT IN` returns no rows. SQL's three-valued logic (`TRUE`, `FALSE`, `UNKNOWN`) causes `NOT IN (NULL)` to evaluate as `UNKNOWN` for every row, excluding all results.

**Performance problem:** `NOT IN` with a subquery can disable index use on the outer table in some databases, forcing a full scan with an in-memory anti-join.

#### The Fix: `NOT EXISTS`

```sql
-- Correct: NOT EXISTS — NULL-safe, index-friendly
SELECT * FROM orders o
WHERE NOT EXISTS (
    SELECT 1 
    FROM blacklisted_customers bc 
    WHERE bc.customer_id = o.customer_id
);
```

`NOT EXISTS` is NULL-safe by definition — it checks existence, not value equality. Most optimizers also convert `NOT EXISTS` into an efficient **anti-join** operation with index support.

#### `EXISTS` vs. `IN` for positive matches

```sql
-- IN: Materializes the subquery result as a list
SELECT * FROM orders
WHERE customer_id IN (
    SELECT customer_id FROM vip_customers WHERE tier = 'GOLD'
);

-- EXISTS: Short-circuits at first match
SELECT * FROM orders o
WHERE EXISTS (
    SELECT 1 FROM vip_customers vc 
    WHERE vc.customer_id = o.customer_id AND vc.tier = 'GOLD'
);
```

For small subquery result sets: `IN` is fine (the subquery is materialized once).
For large subquery result sets: `EXISTS` can short-circuit, avoiding full subquery evaluation per row.
In practice: modern optimizers often transform `IN` into the same plan as `EXISTS`. Measure with `EXPLAIN`.

---

### 3.3 Avoiding `SELECT *`

```sql
-- Anti-pattern: SELECT *
SELECT * FROM orders JOIN customers ON orders.customer_id = customers.customer_id;
-- Network bytes: entire orders row + entire customers row per match
-- Prevents index-only scans entirely
-- Breaks if columns are added/removed from schema

-- Correct: Explicit projection
SELECT 
    o.order_id, o.order_date, o.status,
    c.name, c.email
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id;
```

**Why `SELECT *` hurts performance:**
1. **Prevents covering index use** — if even one column is not in the index, the optimizer cannot do an Index-Only Scan
2. **Increases network transfer** — unnecessary columns waste bandwidth between database and application
3. **Increases application memory** — deserializing 50 columns when you need 5 wastes RAM
4. **Breaks pagination** — with `SELECT *`, adding a large BLOB column to the table immediately breaks all paginated queries

---

### 3.4 Moving Computation Out of the WHERE Clause

The fundamental rule: **apply functions to literal values, not to indexed columns**.

```sql
-- Anti-pattern: Function on indexed column
-- Cannot use index on sale_date
SELECT * FROM sales
WHERE EXTRACT(YEAR FROM sale_date) = 2024;

-- Correct: Equivalent range that uses the index
SELECT * FROM sales
WHERE sale_date >= '2024-01-01' AND sale_date < '2025-01-01';
```

```sql
-- Anti-pattern: Arithmetic on indexed column
-- Cannot use index on price
SELECT * FROM products
WHERE price * 0.9 < 100;

-- Correct: Rearrange equation to isolate the column
SELECT * FROM products
WHERE price < 100 / 0.9;  -- ≈ 111.11
```

```sql
-- Anti-pattern: String concatenation on indexed column
SELECT * FROM users
WHERE first_name || ' ' || last_name = 'John Smith';

-- Correct: Separate conditions on individually indexed columns
SELECT * FROM users
WHERE first_name = 'John' AND last_name = 'Smith';
```

---

### 3.5 Common Table Expressions (CTEs) — Performance Implications

CTEs (the `WITH` clause) improve readability but have important performance characteristics that vary by database:

```sql
-- CTE syntax
WITH regional_sales AS (
    SELECT region, SUM(amount) AS total_sales
    FROM orders
    WHERE status = 'completed'
    GROUP BY region
)
SELECT region, total_sales
FROM regional_sales
WHERE total_sales > 1000000
ORDER BY total_sales DESC;
```

**PostgreSQL behavior (< 12):** CTEs were "optimization fences" — the database materialized the CTE result into a temporary table, preventing predicate pushdown and index reuse. A filter in the outer query could not be pushed into the CTE.

**PostgreSQL ≥ 12 and Oracle:** CTEs are "inlined" by default — the optimizer treats the CTE as if it were a subquery, allowing predicate pushdown. You can force materialization with `WITH ... AS MATERIALIZED (...)`.

**SQL Server:** CTEs are always inlined — no materialization barrier.

**Performance rule:** For complex multi-step queries, prefer derived tables (inline subqueries) over CTEs if maximum optimizer freedom is needed. Use CTEs for readability when the optimizer version handles inlining.

```sql
-- Force CTE materialization (PostgreSQL 12+ ONLY when you WANT a temp table):
WITH MATERIALIZED expensive_calc AS (
    SELECT customer_id, complex_calculation() AS result
    FROM orders
)
SELECT * FROM expensive_calc WHERE result > 100;
-- Useful when the CTE is referenced multiple times and re-computation is expensive
```

---

### 3.6 Window Functions vs. Self-Joins

Window functions (OVER PARTITION) are dramatically more efficient than self-join equivalents:

```sql
-- Anti-pattern: Self-join to compute running totals
SELECT 
    a.order_date,
    a.amount,
    SUM(b.amount) AS running_total
FROM orders a
JOIN orders b ON b.order_date <= a.order_date
GROUP BY a.order_date, a.amount;
-- Complexity: O(N²) — for N=100,000 rows: 10 billion comparisons!

-- Correct: Window function — O(N log N) sort + O(N) accumulation
SELECT 
    order_date,
    amount,
    SUM(amount) OVER (ORDER BY order_date 
                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
FROM orders;
```

**Common window function optimizations:**

```sql
-- Get the most recent order per customer (anti-pattern: correlated subquery)
SELECT * FROM orders o1
WHERE order_date = (
    SELECT MAX(o2.order_date) FROM orders o2 WHERE o2.customer_id = o1.customer_id
);
-- Cost: O(N) subquery executions

-- Correct: ROW_NUMBER() window function
SELECT * FROM (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) AS rn
    FROM orders
) ranked
WHERE rn = 1;
-- Cost: O(N log N) single pass
```

---

### 3.7 The HAVING Clause Optimization

`HAVING` filters apply after aggregation. `WHERE` filters apply before aggregation. Always push filters to `WHERE` when they apply to individual rows:

```sql
-- Anti-pattern: Filtering in HAVING when WHERE would work
SELECT customer_id, COUNT(*) AS order_count
FROM orders
GROUP BY customer_id
HAVING customer_id > 1000;  -- This runs AFTER grouping all customers

-- Correct: Filter before grouping
SELECT customer_id, COUNT(*) AS order_count
FROM orders
WHERE customer_id > 1000  -- Eliminates rows BEFORE expensive GROUP BY
GROUP BY customer_id;
```

The correct version groups far fewer rows if `customer_id > 1000` eliminates most records.

---

## 4. Code & Query Performance Lab

### 4.1 Schema Setup
```sql
CREATE TABLE customers (
    customer_id   BIGINT PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    email         VARCHAR(200) NOT NULL,
    country_code  CHAR(2) NOT NULL,
    tier          VARCHAR(20) NOT NULL DEFAULT 'standard',
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
    order_id      BIGINT PRIMARY KEY,
    customer_id   BIGINT NOT NULL REFERENCES customers(customer_id),
    status        VARCHAR(20) NOT NULL,
    total_amount  NUMERIC(12,2) NOT NULL,
    order_date    DATE NOT NULL
);

CREATE TABLE order_items (
    item_id       BIGINT PRIMARY KEY,
    order_id      BIGINT NOT NULL REFERENCES orders(order_id),
    product_id    BIGINT NOT NULL,
    quantity      INTEGER NOT NULL,
    unit_price    NUMERIC(10,2) NOT NULL
);

CREATE INDEX idx_orders_customer ON orders (customer_id);
CREATE INDEX idx_orders_date ON orders (order_date);
CREATE INDEX idx_items_order ON order_items (order_id);
```

### 4.2 Optimization Challenge: Five Slow Queries

**Query 1 — Correlated Subquery in SELECT (Rewrite with JOIN)**
```sql
-- Original (slow):
SELECT 
    c.name,
    (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.customer_id) AS total_orders,
    (SELECT SUM(o.total_amount) FROM orders o WHERE o.customer_id = c.customer_id) AS lifetime_value
FROM customers c
WHERE c.country_code = 'US';

-- Optimized (run EXPLAIN ANALYZE to compare):
SELECT 
    c.name,
    COALESCE(o_agg.total_orders, 0) AS total_orders,
    COALESCE(o_agg.lifetime_value, 0) AS lifetime_value
FROM customers c
LEFT JOIN (
    SELECT customer_id, COUNT(*) AS total_orders, SUM(total_amount) AS lifetime_value
    FROM orders
    GROUP BY customer_id
) o_agg ON c.customer_id = o_agg.customer_id
WHERE c.country_code = 'US';
```

**Query 2 — Function on Indexed Column (Rewrite with Range)**
```sql
-- Original (slow — disables index on order_date):
SELECT order_id, total_amount
FROM orders
WHERE DATE_TRUNC('month', order_date) = '2024-06-01';

-- Optimized:
SELECT order_id, total_amount
FROM orders
WHERE order_date >= '2024-06-01' AND order_date < '2024-07-01';
```

**Query 3 — NOT IN with potential NULLs (Rewrite with NOT EXISTS)**
```sql
-- Original (slow + NULL bug):
SELECT order_id FROM orders
WHERE customer_id NOT IN (SELECT customer_id FROM suspended_customers);

-- Optimized:
SELECT o.order_id FROM orders o
WHERE NOT EXISTS (
    SELECT 1 FROM suspended_customers sc WHERE sc.customer_id = o.customer_id
);
```

**Query 4 — Self-Join for Ranking (Rewrite with Window Function)**
```sql
-- Original (slow — O(N²)):
SELECT DISTINCT o1.customer_id, o1.order_id, o1.order_date
FROM orders o1
WHERE o1.order_date = (
    SELECT MAX(o2.order_date)
    FROM orders o2
    WHERE o2.customer_id = o1.customer_id
);

-- Optimized:
SELECT customer_id, order_id, order_date
FROM (
    SELECT customer_id, order_id, order_date,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) AS rn
    FROM orders
) ranked
WHERE rn = 1;
```

**Query 5 — HAVING where WHERE works (Rewrite)**
```sql
-- Original:
SELECT customer_id, SUM(total_amount) AS revenue
FROM orders
GROUP BY customer_id
HAVING customer_id IS NOT NULL AND SUM(total_amount) > 500;

-- Optimized:
SELECT customer_id, SUM(total_amount) AS revenue
FROM orders
WHERE customer_id IS NOT NULL       -- Move non-aggregate filter here
GROUP BY customer_id
HAVING SUM(total_amount) > 500;    -- Aggregate filter stays in HAVING
```

---

## 5. Hands-on Exercises

1. **Rewrite Drill:** Rewrite the following without a correlated subquery:
   ```sql
   SELECT department_id, department_name,
     (SELECT AVG(salary) FROM employees e WHERE e.department_id = d.department_id) AS avg_salary
   FROM departments d;
   ```

2. **NULL Trap Identification:** Given a `products` table and a `discontinued_products` table where `discontinued_products.product_id` can be NULL, explain what `WHERE product_id NOT IN (SELECT product_id FROM discontinued_products)` actually returns. Write the correct version.

3. **Window Function Conversion:** Rewrite this self-join using window functions:
   ```sql
   SELECT a.sale_date, a.amount,
     (SELECT SUM(b.amount) FROM daily_sales b WHERE b.sale_date <= a.sale_date) AS cumulative
   FROM daily_sales a
   ORDER BY a.sale_date;
   ```

---

## 6. Mini-Project: The Monthly Report Overhaul

### Scenario
A monthly reporting query has been flagging in slow query logs at 45 seconds. It generates a sales summary:

```sql
SELECT 
    c.name,
    c.tier,
    EXTRACT(MONTH FROM o.order_date) AS month,
    EXTRACT(YEAR FROM o.order_date) AS year,
    (SELECT COUNT(*) FROM order_items oi WHERE oi.order_id = o.order_id) AS item_count,
    (SELECT SUM(oi.quantity * oi.unit_price) FROM order_items oi WHERE oi.order_id = o.order_id) AS computed_total
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE c.tier IN ('gold', 'platinum')
  AND EXTRACT(YEAR FROM o.order_date) = 2024
GROUP BY c.name, c.tier, month, year, o.order_id
ORDER BY year, month, computed_total DESC;
```

### Tasks
1. Identify every performance problem in this query (at least 4).
2. Rewrite it to eliminate all anti-patterns.
3. Write the optimal index definitions needed to support the rewritten query.
4. Estimate the expected improvement in execution time and justify your estimate.

### Solution Guide
**Problems identified:**
1. `EXTRACT(YEAR FROM o.order_date) = 2024` — function on indexed column, disables `idx_orders_date`
2. Correlated subquery for `item_count` — runs once per order row
3. Correlated subquery for `computed_total` — runs once per order row (2 correlated queries per row!)
4. `GROUP BY o.order_id` is redundant — `order_id` is unique; grouping by it does nothing useful
5. `ORDER BY computed_total DESC` — ordering by a correlated subquery alias requires computing it first for all rows before sorting

**Optimized query:**
```sql
SELECT 
    c.name,
    c.tier,
    EXTRACT(MONTH FROM o.order_date) AS month,
    EXTRACT(YEAR FROM o.order_date) AS year,
    oi_agg.item_count,
    oi_agg.computed_total
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN (
    SELECT 
        order_id,
        COUNT(*) AS item_count,
        SUM(quantity * unit_price) AS computed_total
    FROM order_items
    GROUP BY order_id
) oi_agg ON o.order_id = oi_agg.order_id
WHERE c.tier IN ('gold', 'platinum')
  AND o.order_date >= '2024-01-01' AND o.order_date < '2025-01-01'
ORDER BY year, month, oi_agg.computed_total DESC;
```

**Required indexes:**
```sql
CREATE INDEX idx_customers_tier ON customers (tier, customer_id);
CREATE INDEX idx_orders_date_customer ON orders (order_date, customer_id) INCLUDE (order_id);
-- order_items already indexed on order_id
```

---

## 7. Deep-Dive Interview Questions

### Q1: When would you use a CTE over a derived table, and when does that choice affect performance?

**Answer:** CTEs improve readability for complex multi-step logic, especially when a result set is referenced multiple times in the same query. A derived table (inline subquery) is semantically equivalent but requires repeating the definition. The performance difference depends on the database version: in PostgreSQL < 12, CTEs were optimization fences — predicates from the outer query could not push into the CTE, causing it to always materialize. In PostgreSQL ≥ 12, Oracle, and SQL Server, CTEs are inlined by default, making the performance equivalent. The key rule: if you're using PostgreSQL < 12, use derived tables for queries where filter pushdown is needed. On modern versions, choose CTE for readability when referenced multiple times, and force `WITH MATERIALIZED` only when re-computation prevention is explicitly desired.

### Q2: A query using `NOT IN (subquery)` suddenly returns zero rows after a data migration. What happened and how do you fix it?

**Answer:** The subquery result set contains at least one NULL value after the migration. SQL's three-valued logic makes `x NOT IN (NULL, 1, 2)` always evaluate to UNKNOWN (not FALSE), because `x != NULL` is UNKNOWN by definition. Every row in the outer query is excluded because UNKNOWN is treated as non-matching. The fix is to replace `NOT IN` with `NOT EXISTS`, which evaluates row existence rather than value equality, making it inherently NULL-safe. Alternatively, add `WHERE subquery_col IS NOT NULL` inside the subquery, but `NOT EXISTS` is the canonical solution.

### Q3: Explain why a window function like `ROW_NUMBER() OVER (PARTITION BY ...)` is typically more efficient than a correlated subquery returning `MAX()`.

**Answer:** A correlated `MAX()` subquery executes once per row of the outer query. For N outer rows, it produces N passes over the inner dataset — O(N²) total work. A window function executes in a single pass: the database sorts the data (O(N log N)) or leverages an index, then computes the window function in one linear scan (O(N)), assigning row numbers. The window function's total cost is O(N log N) versus the correlated subquery's O(N²). For N=100,000 rows, this is the difference between 1.7 billion operations and 100,000. Furthermore, window functions maintain a running partition state in memory, while correlated subqueries must re-access disk or buffer pool for each invocation.

---

## 8. Summary & Key Takeaways

- **Correlated subqueries in SELECT or WHERE** execute once per outer row. Always rewrite with JOINs to pre-aggregated derived tables.
- **`NOT IN` with nullable subqueries** is a silent correctness bug and a performance trap. Use `NOT EXISTS`.
- **Functions on indexed columns in WHERE** disable index B-Tree traversal. Rearrange conditions to apply functions to literal values.
- **`SELECT *`** prevents covering index scans, inflates network transfer, and breaks future optimizations.
- **Window functions** replace O(N²) self-joins with O(N log N) operations — always prefer them for ranking, cumulative sums, and lead/lag patterns.
- **HAVING vs. WHERE**: Push non-aggregate filters to WHERE to reduce the number of rows entering the GROUP BY phase.
