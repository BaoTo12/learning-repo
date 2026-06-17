# Module 09: Analyzing and Interpreting Database Execution Plans

## 1. What Problem This Module Solves
When a SQL query runs slowly, developers often try to fix it by guessing. They create indexes on random columns, rewrite the SQL statement, or add database optimizer hints without diagnostic evidence. This often fails or creates redundant indexes that degrade write performance.

The only way to diagnose SQL bottlenecks is to read the **Database Execution Plan**.
Common diagnostic challenges include:
*   **Deciphering execution operator blocks** across different database systems (PostgreSQL, MySQL, SQL Server, and Oracle).
*   **Failing to differentiate between estimated costs and actual runtime execution timings**.
*   **Overlooking the difference between access and filter predicates**, which indicates whether a query uses B-Tree bounds or scans wide ranges of data.

This module details how to retrieve and analyze execution plans across major relational engines, enabling developers to diagnose query bottlenecks.

---

## 2. Why This Topic Matters
Query optimization requires measuring and validating changes. An execution plan is the map of how the query optimizer translates declarative SQL code into physical page reads and joins. 

By learning to read execution plans, developers can locate the exact table scan, join, or sorting operator causing a performance bottleneck, verifying indexing improvements with concrete runtime metrics.

---

## 3. Core Technical Concepts & Deep Dives

### 3.1 What is an Execution Plan?
An execution plan is a tree structure of physical operations. Data flows from the leaf nodes (which scan tables or indexes) up through intermediate nodes (which perform joins, sorting, or aggregation) to the root node (the final result set).

```
                    [ROOT: SELECT STATEMENT] (Output)
                               ▲
                               │
                       [HASH JOIN OPERATOR]
                        ├───► Left Input: [INDEX RANGE SCAN on EMP_NAME]
                        └───► Right Input: [TABLE ACCESS FULL on DEPARTMENTS]
```

---

### 3.2 Retrieving Plans Across Relational Engines

#### A. PostgreSQL
PostgreSQL uses the `EXPLAIN` statement:
*   `EXPLAIN SELECT ...`: Displays the optimizer's estimated plan cost, rows, and width. **It does not execute the query**.
*   `EXPLAIN ANALYZE SELECT ...`: Executes the query and records actual CPU execution times, actual row counts, and memory/buffer block reads.

#### B. MySQL
MySQL uses `EXPLAIN` or `EXPLAIN FORMAT=JSON`:
*   `EXPLAIN SELECT ...`: Outputs a table of join orders, table scan details, keys used, and row estimates.
*   `EXPLAIN ANALYZE SELECT ...`: (Introduced in MySQL 8.0) Executes the query and reports actual block scans and execution times.

#### C. SQL Server
SQL Server displays graphical XML plans or tabular text:
*   `SET SHOWPLAN_ALL ON`: Returns estimated plan cost details without execution.
*   `SET STATISTICS PROFILE ON`: Executes the query and displays the actual row counts and execution statistics.

#### D. Oracle Database
Oracle uses the `EXPLAIN PLAN` command:
1.  Compile the plan: `EXPLAIN PLAN FOR SELECT ...;`
2.  Display the plan: `SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);`

---

### 3.3 Key Execution Plan Operators

#### 1. Data Scan Operations
*   **Full Scan / Seq Scan**: Read all blocks in a table sequentially. (`TABLE ACCESS FULL` in Oracle, `Seq Scan` in PostgreSQL, `Table Scan` in SQL Server).
*   **Index Scan**: Traverse the B-Tree B-Tree and walk the leaf nodes. (`INDEX RANGE SCAN` in Oracle/PostgreSQL/SQL Server).
*   **Index-Only Scan / Covering Index**: Scan the index without fetching data from the table. (`INDEX FAST FULL SCAN` or `INDEX-ONLY SCAN`).

#### 2. Join Operators
*   **Nested Loop**: Iterate through outer rows, searching the inner table using an index.
*   **Hash Join**: Build an in-memory hash table of the smaller table, and probe it with the larger table.
*   **Merge Join**: Sort both tables on join keys, and merge them in a single walk.

#### 3. Aggregation and Sorting Operators
*   **HashAggregate / Hash Match**: Group rows using an in-memory hash table.
*   **GroupAggregate / Stream Aggregate**: Group pre-sorted rows sequentially.
*   **Sort / Sort Order By**: Sort rows in memory (or tempdb if the sort buffer is exceeded).

---

### 3.4 Access vs. Filter Predicates in Plan Diagnostic Output
When analyzing index scans, check the **Predicate Information** section:
*   **Access Predicate (Index Cond)**: Indicates B-Tree traversal boundaries. A targeted access predicate means the database traverses the tree directly to the search key.
*   **Filter Predicate (Filter)**: Indicates that the database scans the index or table blocks and discards non-matching rows. A filter predicate without an access predicate indicates that the index is scanned sequentially rather than traversed.

---

## 4. Code & Query Performance Lab

Let's execute a query and retrieve its plan in **PostgreSQL**.

### 4.1 Schema Setup
```sql
CREATE TABLE departments (
    department_id   NUMERIC PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL
);

CREATE TABLE employees (
    employee_id   NUMERIC PRIMARY KEY,
    department_id NUMERIC NOT NULL,
    last_name     VARCHAR(100) NOT NULL,
    salary        NUMERIC(10,2) NOT NULL
);

CREATE INDEX idx_emp_dept ON employees (department_id);
```

### 4.2 Query and Execution Plan Analysis
We join the tables and filter by department:
```sql
SELECT e.last_name, e.salary, d.department_name
  FROM employees e
  JOIN departments d ON e.department_id = d.department_id
 WHERE e.department_id = 10;
```

#### PostgreSQL Plan Output:
We run `EXPLAIN (ANALYZE, BUFFERS)` to capture execution metrics and memory page hits:
```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT e.last_name, e.salary, d.department_name
  FROM employees e
  JOIN departments d ON e.department_id = d.department_id
 WHERE e.department_id = 10;
```

**Plan Output:**
```
Nested Loop  (cost=0.30..22.45 rows=5 width=48) (actual time=0.018..0.085 loops=1)
  Buffers: shared hit=8
  ->  Index Scan using departments_pkey on departments d  (cost=0.15..8.17 rows=1 width=32) (actual time=0.008..0.009 loops=1)
        Index Cond: (department_id = 10)
        Buffers: shared hit=2
  ->  Index Scan using idx_emp_dept on employees e  (cost=0.15..14.23 rows=5 width=48) (actual time=0.008..0.072 loops=1)
        Index Cond: (department_id = 10)
        Buffers: shared hit=6
```

#### Diagnostic Breakdown:
1.  **Shared Hit Buffers**: The query read 8 physical blocks from memory (`shared hit=8`). Bypassing disk I/O resulted in a fast execution time of 0.085ms.
2.  **Driving Step**: The optimizer performed an `Index Scan` on `departments` using its primary key B-Tree (`departments_pkey`) to verify department 10 exists (reading 2 blocks).
3.  **Inner Step**: The optimizer performed an `Index Scan` on `employees` using `idx_emp_dept` to retrieve the 5 employees assigned to department 10 (reading 6 blocks).
4.  **Join**: The rows were combined using a `Nested Loop` operator.

---

## 5. Hands-on Exercises

1.  **Operator Diagnosis**:
    Identify the performance bottleneck operator in the following PostgreSQL execution plan and propose the index optimization needed to resolve it:
    ```
    Hash Join  (cost=35.50..4720.00 rows=500 width=64) (actual time=1.120..95.402 loops=1)
      Hash Cond: (e.manager_id = m.employee_id)
      ->  Seq Scan on employees e  (cost=0.00..4120.00 rows=100000 width=32) (actual time=0.010..42.200 loops=1)
      ->  Hash  (cost=30.00..30.00 rows=100 width=32) (actual time=0.100..0.100 loops=1)
            ->  Index Scan using employees_pkey on employees m  (cost=0.15..30.00 rows=100 width=32)
    ```
2.  **Filter vs. Cond Evaluation**:
    Explain the performance difference reported in an index scan when a condition is listed under `Index Cond` compared to when it is listed under `Filter` in PostgreSQL.

---

## 6. Mini-Project: Diagnosing a Query Timeout

### Scenario
An OLTP report query is timing out on a PostgreSQL database. The query searches for high-value client transactions:

```sql
SELECT t.transaction_id, c.client_name, t.amount, t.transaction_date
  FROM transactions t
  JOIN clients c ON t.client_id = c.client_id
 WHERE c.country_code = 'US' AND t.amount > 10000.00
 ORDER BY t.transaction_date DESC
 LIMIT 10;
```

### Table Specifications
*   `clients` PK: `client_id`. Contains 50,000 rows. US clients count: 10,000.
*   `transactions` PK: `transaction_id`. Contains 10,000,000 rows. Transactions with amount > 10,000.00: 50,000.
*   `idx_txn_client` on `transactions(client_id)`.

### Execution Plan (Retrieved via EXPLAIN ANALYZE)
```
Limit  (cost=42501.20..42501.23 rows=10 width=56) (actual time=1450.200..1450.205 loops=1)
  ->  Sort  (cost=42501.20..42503.20 rows=800 width=56) (actual time=1450.198..1450.200 loops=1)
        Sort Key: t.transaction_date DESC
        Sort Method: quicksort  Memory: 95kB
        ->  Nested Loop  (cost=0.42..42463.00 rows=800 width=56) (actual time=0.120..1425.400 loops=1)
              ->  Seq Scan on clients c  (cost=0.00..1200.00 rows=10000 width=32) (actual time=0.012..18.200 loops=1)
                    Filter: (country_code = 'US'::text)
                    Rows Removed by Filter: 40000
              ->  Index Scan using idx_txn_client on transactions t  (cost=0.42..4.11 rows=1 width=32) (actual time=0.080..0.138 loops=10000)
                    Index Cond: (client_id = c.client_id)
                    Filter: (amount > 10000.00)
                    Rows Removed by Filter: 190
```

### Tasks
1.  Identify the two main performance bottlenecks in the execution plan.
2.  Explain why `idx_txn_client` is performing poorly in this plan (pay attention to `loops` and `Filter` metrics).
3.  Design the index changes needed to optimize the query and write the SQL statements to deploy them.

#### Solution Guide:
1.  *Bottleneck Analysis*:
    *   **Bottleneck 1: Loop lookup with Filter**. The `Nested Loop` performs 10,000 lookups on `idx_txn_client`. For each lookup, it fetches the row and discards entries where `amount <= 10000.00` (`Rows Removed by Filter: 190` per loop, totaling 1,900,000 rows scanned). This is a slow, high-I/O operation.
    *   **Bottleneck 2: Sorting**. The database executes a `Sort` operation at the end to order the output by `transaction_date`, which blocks pipelined stopkey execution.
2.  *Index Assessment*: The index `idx_txn_client` does not cover `amount`. The database must look up the row and check the amount column value, generating random I/O.
3.  *Optimization Strategy*:
    *   Create a composite index on `transactions` that includes the client, the filter column, and the sort column: `(client_id, amount, transaction_date, transaction_id)`.
    *   Create a index on `clients` covering the search filter: `(country_code, client_id)`.
    *   *Optimized Plan Flow*: The database uses `idx_clients` to find US clients. For each US client, it performs a targeted index seek on the composite transaction index using the conditions `client_id = c.client_id` and `amount > 10000.00`. The index entries are already sorted by `transaction_date`, allowing the database to merge and stream the top 10 records without a separate sort phase.

---

## 7. Deep-Dive Interview Questions

### Q1: What is the risk of executing `EXPLAIN ANALYZE` on data-modifying queries (like `UPDATE` or `DELETE`), and how do we execute it safely?
**Answer:** The `EXPLAIN ANALYZE` statement executes the query to record actual runtime metrics. If run on a write query:
```sql
EXPLAIN ANALYZE DELETE FROM sessions WHERE expiry_date < NOW();
```
The database will delete the rows, modifying the data on disk.
To execute it safely, wrap the query in a **Transaction Block** and run a rollback:
```sql
BEGIN;
EXPLAIN ANALYZE DELETE FROM sessions WHERE expiry_date < NOW();
ROLLBACK;
```
This records the performance metrics but rolls back the data modifications at the end of the transaction.

### Q2: What does a large mismatch between "Estimated Rows" and "Actual Rows" in an execution plan indicate? How does this impact performance?
**Answer:** A mismatch indicates that the database's **Optimizer Statistics** are stale, corrupted, or missing.
*   **Performance Impact**: The query optimizer uses cardinality (row count) estimates to evaluate plan costs and select join algorithms, join orders, and index access paths. If the optimizer estimates a step will return 5 rows, it will choose a Nested Loops join. If that step actually returns 500,000 rows, the Nested Loops join will execute 500,000 index lookups, degrading query performance.
*   **Resolution**: Update the table statistics:
    *   *PostgreSQL*: `ANALYZE table_name;`
    *   *Oracle*: `DBMS_STATS.GATHER_TABLE_STATS(ownname => 'schema', tabname => 'table');`
    *   *SQL Server*: `UPDATE STATISTICS table_name;`

### Q3: In SQL Server, what is a "Key Lookup" (or "RID Lookup") operation in an execution plan? Why is it considered a tuning opportunity?
**Answer:**
*   **Key Lookup / RID Lookup**: This operation occurs when a query uses a non-clustered index to locate records, but the index does not cover all columns requested in the `SELECT` list. The database must look up the clustered primary key (Key Lookup) or the physical row ID (RID Lookup) in the primary table page to retrieve the missing columns.
*   **Tuning Opportunity**: Lookups generate random I/O reads. If the lookup count is high, it degrades query performance. We can resolve this by adding the missing columns to the index definition using the `INCLUDE` clause:
    ```sql
    CREATE INDEX idx_emp_names ON employees (last_name) INCLUDE (first_name, email);
    ```
    This stores `first_name` and `email` in the B-Tree leaf pages without sorting on them, converting Key Lookups into fast Index-Only Scans.

---

## 8. Summary & Key Takeaways
*   **Read the Plan**: Tuning queries requires analyzing the execution plan to locate bottlenecks rather than guessing.
*   **Explain vs. Analyze**: `EXPLAIN` returns estimated costs. `EXPLAIN ANALYZE` executes the query to record actual execution times, memory usage, and page reads.
*   **Filter vs. Access**: Access conditions represent B-Tree boundaries; filter conditions are evaluated during sequential scans. Always design indexes to convert filters into access conditions.
*   **Plan Operators**: Scans (`Seq Scan`, `Index Scan`), joins (`Nested Loop`, `Hash Join`), and aggregates (`Hash Match`, `Stream Aggregate`) are the building blocks of database execution.
*   **Maintain Statistics**: Ensure table statistics are kept up-to-date so the query optimizer has accurate estimates to select the best execution path.
