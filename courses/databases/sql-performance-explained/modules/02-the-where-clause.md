# Module 02: Indexing and the WHERE Clause

## 1. What Problem This Module Solves
Writing a query that retrieves data correctly is easy; writing a query that executes efficiently is much harder. The `WHERE` clause defines the search conditions for SQL statements. If structured carelessly, the query optimizer will fail to use the index and resort to a **Full Table Scan (FTS)**. 

Common indexing failures in the `WHERE` clause include:
*   **Wrong column order in composite indexes**, rendering the index tree traversal useless.
*   **Wrapping indexed columns in functions** (e.g., `UPPER(last_name)`), which acts as a "black box" to the database optimizer.
*   **Incorrect date and numeric formatting**, forcing implicit type conversions that hide columns from the index.
*   **Poorly structured range queries and LIKE wildcards** that scan much wider index segments than necessary.
*   **Dynamic logic and math operations** executed directly on columns (e.g., `WHERE age - 1 = 20` instead of `WHERE age = 21`).

This module explains how different SQL operators and structures affect index usage, providing a step-by-step methodology for designing high-performance search queries.

---

## 2. Why This Topic Matters
In a small development environment, even a poorly written `WHERE` clause executes fast because the entire table fits in memory cache. However, when deployed to production, tables scale to millions of rows. A query requiring a Full Table Scan will read every single data block from disk, consuming CPU cycles and disk I/O, leading to database lockups.

Understanding how the database query optimizer parses SQL filters and maps them to physical index trees enables developers to build schema designs that execute in milliseconds. It saves storage space and database write overhead by maximizing the utility of a single index across multiple queries.

---

## 3. Core Technical Concepts & Deep Dives

### 3.1 Concatenated (Composite) Indexes
A **Concatenated Index** (or composite/composite index) is a single index structure built across multiple columns. Column order is critical because the database sorts the index entries hierarchically using the defined columns from left to right.

#### The Telephone Directory Analogy
Think of a concatenated index `(last_name, first_name)` like a printed telephone directory:
1.  Entries are sorted primarily by `last_name`.
2.  If two entries share the same `last_name` (e.g., `'SMITH'`), they are sorted secondarily by `first_name`.

```
Index Definition: ON employees (last_name, first_name)

Index Leaf Layout:
------------------------------------------
| LAST_NAME (Primary) | FIRST_NAME       |
|---------------------|------------------|
| ADAMS               | JOHN             |
| SMITH               | ALBERT           | <── Cluster starts
| SMITH               | JOHN             |
| SMITH               | ZACHARY          | <── Cluster ends
| WINAND              | MARKUS           |
------------------------------------------
```

*   **Usable Queries**:
    *   `WHERE last_name = 'SMITH'` (The database traverses the B-Tree to find the `'SMITH'` cluster and reads entries).
    *   `WHERE last_name = 'SMITH' AND first_name = 'JOHN'` (The B-Tree locates the exact entry).
*   **Unusable Queries**:
    *   `WHERE first_name = 'JOHN'` (Since the directory is sorted by last name, first names are scattered throughout. The index tree is useless; a Full Table Scan is required).

#### Key Principle:
> [!IMPORTANT]
> A concatenated index can only support searches that filter on its leading (leftmost) columns. If an index is defined on `(A, B, C)`, it supports queries on `(A)`, `(A, B)`, and `(A, B, C)`. It does *not* support queries on `(B)` or `(C)` alone.

---

### 3.2 The Optimizer Black Box and Function-Based Indexes
When a database compiles an SQL query, the query optimizer translates declarative clauses into execution plans. If a column is wrapped inside a function, the optimizer cannot resolve the mathematical relationship between the raw column values and the function's output.

```
Query: WHERE UPPER(last_name) = 'WINAND'

Optimizer's Perspective:
┌─────────────────────────┐      ┌─────────────┐
│  UPPER(last_name)       │ ───► │  BLACKBOX   │
│  (Indexed on raw data)  │      │  (...)= 'W' │
└─────────────────────────┘      └─────────────┘
The index B-Tree is sorted by raw last names ('Winand'). It is not sorted by 'WINAND'.
Therefore, the database cannot use the B-Tree to find the value; it runs a Full Table Scan.
```

To resolve this, databases offer two strategies:
1.  **Function-Based Indexes (FBI)**: An index built directly on the expression (e.g., `CREATE INDEX idx ON employees (UPPER(last_name))`). The database computes the output of the function for every insert/update and stores the sorted result in the B-Tree leaf nodes.
2.  **Computed/Generated Columns**: (Used in SQL Server and MariaDB/MySQL). You define a virtual column `last_name_up AS UPPER(last_name)` and build a standard B-Tree index on that column.

#### Deterministic vs. Non-Deterministic Functions
You can only index **deterministic** functions—functions that return the exact same output for a given input.
*   *Deterministic (Indexable)*: `UPPER(col)`, `ROUND(col)`, `A + B`.
*   *Non-Deterministic (Non-Indexable)*: `SYSDATE`, `CURRENT_TIMESTAMP`, `RAND()`, or custom functions querying other tables. The database cannot store these in a static index leaf node because the values drift over time without update operations.

---

### 3.3 Range Queries and Composite Index Design
Range operators (`<`, `>`, `BETWEEN`, `LIKE 'prefix%'`) alter how the database scans leaf nodes. In a composite index, a range filter ends the B-Tree search capability for any columns defined to its right.

Consider an index `ON employees (date_of_birth, subsidiary_id)` for the query:
```sql
WHERE date_of_birth >= '1980-01-01' AND subsidiary_id = 30;
```
1.  The database uses the B-Tree to find the first entry where `date_of_birth` is `'1980-01-01'`.
2.  From that point, it must scan *all* subsequent leaf nodes because the dates are sorted, but the `subsidiary_id` values within those dates are not ordered as a single cluster. The database must filter out rows where `subsidiary_id != 30` manually (an index filter predicate).

```
Index definition: (date_of_birth, subsidiary_id)
Leaf scan starts at 1980-01-01. It must read every subsequent leaf entry to check subsidiary_id.
1980-01-01 [Sub: 10] (Skip) ──► 1980-01-02 [Sub: 30] (Match) ──► 1980-01-03 [Sub: 15] (Skip)...
```

#### The Rule of Range Indexing:
> [!TIP]
> Always place equality columns first, and range columns last in your composite index definition.
> For the query above, the optimal index definition is `ON employees (subsidiary_id, date_of_birth)`. The B-Tree isolates the `subsidiary_id = 30` cluster, and then reads a sorted, contiguous range of dates.

---

### 3.4 LIKE Wildcards
*   **Prefix Search (`LIKE 'WIN%'`)**: The search key is bounded. The database executes an `INDEX RANGE SCAN`, traversing the tree to find the first index entry starting with `'WIN'` and scanning until keys no longer start with `'WIN'`.
*   **Suffix Search (`LIKE '%NAN'`)**: The B-Tree cannot locate a starting position because the sorting order is determined from left to right. The database must perform a Full Table Scan.

---

### 3.5 Implicit Type Conversions
Relational engines execute implicit type conversion when comparing mismatched data types. One data type has higher precedence, and the database wraps the lower precedence column in an implicit type cast function.

#### Scenario: Numeric Column compared with String Parameter
If `employee_id` is a `NUMERIC` column, and you query:
```sql
WHERE employee_id = '123';
```
Since numeric has higher precedence than string, the database casts the string to numeric: `employee_id = 123`. The index is **usable**.

#### Scenario: String Column compared with Numeric Parameter
If `phone_number` is a `VARCHAR` column, and you query:
```sql
WHERE phone_number = 12345;
```
Since numeric has higher precedence, the database casts the database column: `TO_NUMBER(phone_number) = 12345`. This wraps the indexed column in a function, **disabling the index** and triggering a Full Table Scan.

---

## 4. Code & Query Performance Lab

### 4.1 Schema Definition
Let's build a scenario demonstrating composite index performance tuning:

```sql
CREATE TABLE employees (
    employee_id   NUMERIC         NOT NULL,
    first_name    VARCHAR(100)    NOT NULL,
    last_name     VARCHAR(100)    NOT NULL,
    subsidiary_id NUMERIC         NOT NULL,
    date_of_birth DATE            NOT NULL,
    phone_number  VARCHAR(50)     NOT NULL,
    CONSTRAINT employees_pk PRIMARY KEY (employee_id)
);

-- Index defined with subsidiary_id second
CREATE INDEX emp_wrong_order ON employees (employee_id, subsidiary_id);
```

### 4.2 Query Optimization Analysis

#### Query 1: Filtering on second column only
```sql
SELECT first_name, last_name FROM employees WHERE subsidiary_id = 20;
```
Because the leading column `employee_id` is not present in the query filter, the database is forced to run a Full Table Scan:

**PostgreSQL Execution Plan:**
```
EXPLAIN ANALYZE SELECT first_name, last_name FROM employees WHERE subsidiary_id = 20;

Seq Scan on employees  (cost=0.00..478.00 rows=106 width=32) (actual time=0.021..14.502 loops=1)
  Filter: (subsidiary_id = 20)
  Rows Removed by Filter: 99894
```

#### Optimization Step:
We re-index, placing `subsidiary_id` first:
```sql
CREATE INDEX emp_right_order ON employees (subsidiary_id, employee_id);
DROP INDEX emp_wrong_order;
```

**Optimized PostgreSQL Execution Plan:**
```
EXPLAIN ANALYZE SELECT first_name, last_name FROM employees WHERE subsidiary_id = 20;

Index Scan using emp_right_order on employees  (cost=0.29..75.00 rows=106 width=32) (actual time=0.012..0.124 loops=1)
  Index Cond: (subsidiary_id = 20)
```
The query execution time drops from 14.5ms to 0.12ms, reducing disk block reads.

---

## 5. Hands-on Exercises

1.  **Refactoring Poor SQL Queries**:
    Rewrite the following queries to ensure the database can use standard indexes:
    *   *Query A*: `SELECT * FROM sales WHERE EXTRACT(YEAR FROM sale_date) = 2026;`
    *   *Query B*: `SELECT * FROM inventory WHERE price * 0.9 < 100.00;`
    *   *Query C*: `SELECT * FROM users WHERE registration_code || '-X' = 'CODE99-X';`
2.  **Implicit Conversion Diagnosis**:
    Assuming `account_id` is defined as a `VARCHAR(50)` column in Oracle Database, explain why the query `SELECT * FROM accounts WHERE account_id = 100998877;` will trigger a Full Table Scan, and fix the query statement.

---

## 6. Mini-Project: The SQL Optimization Challenge

### Scenario
An online logistics application has a tracking log table `shipment_logs` with 5,000,000 rows. The table has three indexes:
*   `idx_log_id` on `log_id` (Primary Key)
*   `idx_status` on `status` (Nullable VARCHAR)
*   `idx_shipment_date` on `shipment_date` (Timestamp)

The following three queries are running concurrently and causing database CPU spikes.

```sql
-- Query 1: Retrieve delivered shipments for a client
SELECT * FROM shipment_logs 
 WHERE status = 'DELIVERED' AND client_id = 4556;

-- Query 2: Retrieve shipping transactions processed last week
SELECT * FROM shipment_logs 
 WHERE shipment_date BETWEEN '2026-06-10 00:00:00' AND '2026-06-17 00:00:00' 
   AND status = 'PENDING';

-- Query 3: Search clients by partial business code
SELECT * FROM shipment_logs 
 WHERE UPPER(business_code) LIKE 'EXP%';
```

### Tasks
1.  Explain why each of the three queries fails to run optimally with the current index structure.
2.  Propose the exact composite or function-based index definitions needed to optimize all three queries.
3.  Write the refactored SQL code where necessary.

#### Solution Guide:
1.  *Query 1*: Has a filter on `status` and `client_id`. Currently, it uses `idx_status` and does a table lookup for `client_id`, which scans a large volume of data if 'DELIVERED' is common. *Solution*: Create composite index `(client_id, status)` or `(status, client_id)`. Since both are equality checks, placing the more selective column first is a best practice.
2.  *Query 2*: Uses a range on `shipment_date` and equality on `status`. Currently, it uses `idx_shipment_date` range scan, checking `status` during table access. *Solution*: Define composite index `(status, shipment_date)`. Place equality column `status` first, followed by the range column.
3.  *Query 3*: Wraps `business_code` in `UPPER()`, disabling any index on `business_code`. *Solution*: Create a Function-Based Index: `CREATE INDEX idx_fbi_buscode ON shipment_logs (UPPER(business_code))`. The prefix search `LIKE 'EXP%'` is bounded, so it will utilize this FBI range scan.

---

## 7. Deep-Dive Interview Questions

### Q1: What are bind parameters, and how do they interact with the database Query Optimizer and Column Histograms?
**Answer:** Bind parameters (or dynamic parameters) use placeholders (e.g., `?` or `:id`) instead of injecting values directly into SQL strings. 
*   **Plan Caching**: Bind parameters allow the database to compile the query once and cache the execution plan, reuse it for subsequent executions with different parameters, and save parser CPU overhead.
*   **The Optimizer Trade-off**: If a column has an uneven data distribution, the database uses a **Column Histogram** to estimate selectivity. For example, a query for `subsidiary_id = 9` might return 2 rows (best with index scan), while `subsidiary_id = 30` returns 1,000,000 rows (best with full table scan). When using a bind parameter (`subsidiary_id = :id`), the optimizer cannot see the value at compile time. It must bypass the histogram, assume a uniform data distribution, and generate a generic plan. This can lead to suboptimal performance if the actual parameters vary widely in frequency.

### Q2: Why does Oracle database treat NULL values differently in index entries compared to other databases like PostgreSQL, and how does this affect indexing?
**Answer:**
*   **Oracle Database**: Oracle B-Tree indexes do not store index entries where all key columns are `NULL`. If a query filters `WHERE nullable_column IS NULL`, Oracle cannot use a standard index on `nullable_column` and is forced to perform a Full Table Scan. To make nulls indexable in Oracle, you must define a composite index that contains at least one column guaranteed to be `NOT NULL` (e.g., `(nullable_column, 0)` or `(nullable_column, primary_key)`).
*   **PostgreSQL / SQL Server**: These databases include `NULL` values in their indexes. Queries filtering `WHERE nullable_column IS NULL` can utilize an `INDEX RANGE SCAN` to locate all null entries directly.

### Q3: Explain index merge operations (Bitmap Index Merge), and why a single composite index is generally preferred over two single-column indexes.
**Answer:** When a query filters on two columns, each having a single-column index (e.g., `WHERE status = 'A' AND client_id = 12`), the database can run an **Index Merge**. It performs range scans on both indexes, extracts their ROWIDs, and performs a bitmap `AND` or `OR` operation to find intersecting records before fetching data from the table.
While this allows the database to utilize separate indexes, it is less efficient than a single composite index `(client_id, status)`. An index merge requires scanning two B-Trees, running bitmap intersections in memory, and sorting ROWIDs. A composite index allows the engine to locate the exact intersecting records in a single B-Tree traversal, saving CPU and memory cycles.

---

## 8. Summary & Key Takeaways
*   **Composite Order**: A composite index is sorted hierarchically from left to right. The leading column must be filtered in the `WHERE` clause for the index B-Tree to be usable.
*   **Function Wrappers**: Wrapping columns in functions (e.g., `UPPER`, `DATE_TRUNC`, or mathematical expressions) disables standard B-Tree indexing. Use Function-Based Indexes (FBI) or computed columns to optimize.
*   **Equality-First Rule**: For queries containing both equality filters and range filters, define composite indexes with equality columns first and range columns last.
*   **Implicit Cast Trap**: Comparing mismatched data types triggers implicit type conversion. If the database column has lower precedence than the parameter, it is wrapped in an implicit cast function, disabling the index. Always align query data types with schema column definitions.
