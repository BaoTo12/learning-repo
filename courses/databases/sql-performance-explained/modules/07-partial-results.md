# Module 07: Optimizing Pagination and Top-N Queries

## 1. What Problem This Module Solves
Applications display large datasets in smaller chunks using **Pagination**. However, the standard SQL implementation of pagination using `LIMIT` and `OFFSET` (or database equivalents like `ROWNUM` or `FETCH OFFSET`) is a major source of database load. 

Common pagination performance failures include:
*   **The OFFSET Bottleneck**: To return 10 records at page 5,000 (`OFFSET 50000 LIMIT 10`), the database engine must read 50,010 records, sort them, discard the first 50,000, and return the final 10. As users page deeper, query execution times degrade linearly ($O(M)$ where $M$ is the offset).
*   **Wasted Sort Buffers on Top-N Limits**: If a query has a `LIMIT` clause but the sort order is not backed by an index, the engine executes a Full Table Scan and materializes a complete sort of the entire table before discarding all but the top $N$ rows.

This module details how to use B-Tree indexes to enable **Stopkey Optimization** (fetching only the top $N$ keys) and implements **Keyset Pagination (The Seek Method)** to achieve flat $O(\log N)$ query times at any page depth.

---

## 2. Why This Topic Matters
Modern web applications, infinite-scroll social feeds, and reporting grids rely on pagination. If a system uses offset pagination, users navigating deep into records or search bots crawling site listings can trigger concurrent deep-offset queries. This reads millions of blocks from disk, saturating the database buffer cache and crashing the system.

Understanding how to construct keyset seeks and design composite indexes that support them enables software engineers to scale user interfaces to hundreds of millions of records without degrading latency or inflating resource usage.

---

## 3. Core Technical Concepts & Deep Dives

### 3.1 Stopkey Optimization for Top-N Queries
When a query requests a subset of sorted rows:
```sql
SELECT first_name, last_name 
  FROM employees 
 ORDER BY last_name ASC 
 LIMIT 10;
```
If an index is present on `last_name`:
1.  The database engine traverses the B-Tree index to the first leaf node.
2.  It reads the first 10 index entries and fetches their rows from the table.
3.  The engine terminates execution immediately (known as **Stopkey Optimization** or **Pipelined Top-N Query**). 
4.  Total cost: 3 B-Tree reads + 10 table block accesses.

If no index is present on `last_name`:
1.  The engine performs a Full Table Scan of all 1,000,000 rows.
2.  It loads them into a sorting workspace (or uses a min-heap sort of size 10 in memory).
3.  It sorts the data and returns the top 10, discarding 999,990 rows.

---

### 3.2 The OFFSET Pagination Bottleneck
Offset-based pagination tells the database to skip a number of records before returning the next batch:

```
Query: SELECT ... ORDER BY date DESC LIMIT 10 OFFSET 50000

[DATABASE EXECUTION METRICS]
┌───────────────────────────────────────────────┐
│ Reads 50,010 sorted index entries             │ (High I/O scan)
├───────────────────────────────────────────────┤
│ Fetches 50,010 rows from Heap Table by ROWID │ (Saturates Buffer Pool Cache)
├───────────────────────────────────────────────┤
│ Discards the first 50,000 rows in memory      │ (Wastes CPU cycles)
├───────────────────────────────────────────────┤
│ Returns final 10 rows                         │
└───────────────────────────────────────────────┘
Offset pagination is not a database skip instruction; it is a discard instruction.
```

The database must verify the existence and sort position of every record up to the offset value, resulting in linear degradation as page numbers increase.

---

### 3.3 Keyset Pagination (The Seek Method)
**Keyset Pagination** (or the **Seek Method**) avoids the `OFFSET` clause completely by filtering on the values of the last record from the previous page.

Instead of telling the database to "skip 50,000 rows," we tell it to "find the next 10 rows where the sort key is smaller than the last record we displayed."

#### Architecture Comparison

```
[OFFSET PAGINATION (Linear Scan)]
 B-Tree Root ──► Leaf 1 ──► Leaf 2 ──► Leaf 3 ... (Walk 50,010 entries) ──► Output 10

[KEYSET PAGINATION (Direct Seek)]
 B-Tree Root ──► Traverses B-Tree directly to the keyset value (e.g. '2026-06-15') ──► Read 10
```

#### SQL Implementation
Assuming we sort by `sale_date` (descending) and use `sale_id` (Primary Key, descending) as a tie-breaker to handle duplicate dates, the query for the next page is:

```sql
SELECT sale_id, sale_date, amount
  FROM sales
 WHERE (sale_date < :last_date) 
    OR (sale_date = :last_date AND sale_id < :last_id)
 ORDER BY sale_date DESC, sale_id DESC
 LIMIT 10;
```

#### Index Requirement
To execute this keyset seek in $O(\log N)$ time, the composite index must match the sorting order:

> [!IMPORTANT]
> Define the composite index with the primary sorting column first, followed by the tie-breaker column:
> `CREATE INDEX idx_sales_paging ON sales (sale_date DESC, sale_id DESC);`
> The database traverses the B-Tree using the `WHERE` filters, locates the keyset values, and streams 10 records, executing only 4 B-Tree reads and 10 table fetches.

---

## 4. Code & Query Performance Lab

### 4.1 Schema Setup
Let's build a scenario demonstrating pagination optimization:

```sql
CREATE TABLE orders (
    order_id    NUMERIC         NOT NULL,
    customer_id NUMERIC         NOT NULL,
    order_date  DATE            NOT NULL,
    amount      NUMERIC(10,2)   NOT NULL,
    CONSTRAINT orders_pk PRIMARY KEY (order_id)
);

-- Index on order_date to support sorting
CREATE INDEX idx_orders_date ON orders (order_date);
```

### 4.2 Query and Execution Plan Analysis

#### Query A: Deep Offset Pagination
We fetch Page 5,000 (10 records per page) using `OFFSET`:
```sql
SELECT order_id, order_date, amount 
  FROM orders 
 ORDER BY order_date DESC 
 LIMIT 10 OFFSET 50000;
```

**PostgreSQL Execution Plan:**
```
Limit  (cost=1945.30..1945.69 rows=10 width=24)
  ->  Index Scan Backward using idx_orders_date on orders  (cost=0.42..38902.00 rows=1000000 width=24)
```
*   **The Issue**: Although the plan reports an Index Scan, the high startup cost (`1945.30`) indicates the database must scan and discard 50,000 index leaf nodes and fetch their rows to check visibility before returning 10 entries.

#### Query B: Keyset Pagination (The Seek Method)
We execute the keyset query, passing the values of the last record from Page 4,999 (`last_date = '2026-06-01'` and `last_id = 99480`):
```sql
SELECT order_id, order_date, amount
  FROM orders
 WHERE (order_date < '2026-06-01') 
    OR (order_date = '2026-06-01' AND order_id < 99480)
 ORDER BY order_date DESC, order_id DESC
 LIMIT 10;
```

**Optimized PostgreSQL Execution Plan:**
```
Limit  (cost=0.42..1.85 rows=10 width=24)
  ->  Index Scan Backward using idx_orders_date on orders  (cost=0.42..38902.00 rows=500000 width=24)
        Index Cond: ((order_date < '2026-06-01'::date) OR ((order_date = '2026-06-01'::date) AND (order_id < 99480)))
```
*   **Result**: The startup cost drops to `0.42`. The engine traverses the B-Tree directly to the target leaf node, reads 10 entries, and halts. Execution time remains under 1ms.

---

## 5. Hands-on Exercises

1.  **Keyset Query Formulation**:
    Write the keyset SQL query to retrieve the next page of 15 records for a user profile list sorted by:
    *   `score` (descending)
    *   `user_id` (Primary Key, ascending, as tie-breaker)
    State the optimal composite index definition required to execute this query in $O(\log N)$ time.
2.  **Offset Drawbacks**:
    Explain why a search engine crawler accessing a site map by requesting pages sequentially from Page 1 to Page 20,000 using `OFFSET` pagination places a severe load on the database compared to a human user who only views the first 3 pages.

---

## 6. Mini-Project: Infinite-Scroll Migration Runbook

### Scenario
A mobile social application's main activity feed is powered by an infinite-scroll API. The API executes this query to load posts:

```sql
SELECT post_id, author_id, publish_timestamp, content 
  FROM posts 
 WHERE author_id = 45009 
 ORDER BY publish_timestamp DESC 
 LIMIT 20 OFFSET :offset_val;
```

As users scroll down, the app requests deeper offsets. Analytics indicate that while early page loads take 15ms, scrolls past page 100 take over 950ms, causing application-level timeouts. The table contains 50,000,000 rows.

### Tasks
1.  Explain why performance degrades as the user scrolls deeper.
2.  Write a migration guide to refactor the query and schema to use keyset pagination.
3.  Write the refactored SQL query template and the new composite index definition.

#### Solution Guide:
1.  *Bottleneck Analysis*: Even though there is an index on `author_id`, the query `LIMIT 20 OFFSET 2000` forces the database to find all posts for the author, read 2,020 index entries, fetch 2,020 rows from disk by ROWID, sort them by `publish_timestamp` in memory, and discard 2,000 rows.
2.  *Migration to Keyset*:
    *   The application must track the `publish_timestamp` and `post_id` of the last post displayed on the current screen.
    *   When fetching the next page, pass these two values as parameters (`:last_timestamp` and `:last_post_id`).
3.  *SQL Refactoring*:
    ```sql
    SELECT post_id, author_id, publish_timestamp, content 
      FROM posts 
     WHERE author_id = 45009 
       AND (
           (publish_timestamp < :last_timestamp) 
           OR (publish_timestamp = :last_timestamp AND post_id < :last_post_id)
       )
     ORDER BY publish_timestamp DESC, post_id DESC 
     LIMIT 20;
    ```
    *   *Index definition*: To optimize both the filtering and the sorted seek, we create a composite index:
    ```sql
    CREATE INDEX idx_posts_author_date_id 
        ON posts (author_id, publish_timestamp DESC, post_id DESC);
    ```
    This index places the equality column `author_id` first, followed by the sorting/keyset columns. The query now executes in $O(\log N)$ time, bypassing sort memory and table block scans.

---

## 7. Deep-Dive Interview Questions

### Q1: What is the "Stopkey" execution plan operation, and how does the presence of a sorting index affect it?
**Answer:** The **Stopkey** operation (e.g., `COUNT STOPKEY` in Oracle, `LIMIT` filter in PostgreSQL) is an optimization where the database engine halts query execution as soon as it has retrieved the number of rows specified in the `LIMIT` or `ROWNUM` filter.
*   **With sorting index**: The engine walks the B-Tree in the requested sorted order, retrieves matching rows, and stops when the limit is met. It avoids scanning subsequent records.
*   **Without sorting index**: The database cannot assume the next row it reads is the next sorted row. It must scan the entire dataset, sort it in a sort workspace, and only then apply the stopkey filter to discard rows. This makes the stopkey optimization ineffective for reducing disk reads.

### Q2: What are the architectural trade-offs of Keyset Pagination compared to Offset Pagination?
**Answer:**
*   **Offset Pagination**:
    *   *Pros*: Easy to implement; supports jumping to arbitrary page numbers (e.g., jump to Page 15).
    *   *Cons*: Performance degrades linearly ($O(M)$) with depth; prone to data skipping or duplication if rows are inserted or deleted while a user is paging.
*   **Keyset Pagination**:
    *   *Pros*: Consistent $O(\log N)$ performance at any depth; resilient to data drifting (no skipped or duplicated rows when entries are inserted/deleted).
    *   *Cons*: Does not support jumping to arbitrary page numbers (the API must know the values of the last record of page $N-1$ to load page $N$); more complex query syntax; requires composite indexes matching the sort key and tie-breaker.

### Q3: How do window functions (e.g., `ROW_NUMBER() OVER (...)`) behave when used for pagination, and how can they be indexed?
**Answer:** Window functions compute values across a set of table rows. To paginate using `ROW_NUMBER()`, you must wrap the query in an outer select:
```sql
SELECT * FROM (
  SELECT last_name, first_name, ROW_NUMBER() OVER (ORDER BY last_name) as row_num
    FROM employees
) WHERE row_num BETWEEN 50000 AND 50010;
```
*   **Performance**: The inner query must compute the row number for every record in the table before the outer query can apply the filter `row_num BETWEEN ...`.
*   **Indexing**: To optimize this, you must create a B-Tree index on the columns in the `OVER (ORDER BY ...)` clause (e.g., `last_name`). If the index matches, the optimizer can use it to fetch rows in sorted order, streaming them to evaluate the row number. If the filter is targeted (e.g., `row_num <= 10`), the optimizer can apply a stopkey optimization to halt execution early. However, for deep ranges (e.g., `BETWEEN 50000 AND 50010`), the database must still scan 50,010 index entries.

---

## 8. Summary & Key Takeaways
*   **Top-N Stopkey**: Top-N queries backed by a B-Tree index execute in $O(\log N)$ time by halting scan operations once the requested limit is met.
*   **The Offset Penalty**: `OFFSET` pagination scales linearly ($O(M)$) in read cost. The engine must scan and discard all records up to the offset value, wasting CPU and I/O.
*   **Keyset Seek**: Keyset pagination filters on the values of the last record from the previous page. It executes in $O(\log N)$ time, providing consistent performance at any page depth.
*   **Paging Index Design**: Optimize keyset queries by creating composite indexes that contain the search columns, followed by the sorting columns and the primary key as a tie-breaker.
