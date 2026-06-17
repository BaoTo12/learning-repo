# Module 08: Index Maintenance and Write Performance

## 1. What Problem This Module Solves
Indexes are the primary tool for speeding up SQL query reads. However, they do not come for free. Every index added to a database table incurs a tax on data modification operations: **`INSERT`**, **`DELETE`**, and **`UPDATE`** statements.

Common database write performance issues include:
*   **Write Amplification**: Inserting a single row can trigger dozens of physical disk writes as the engine synchronizes multiple indexes.
*   **Index Bloat and Page Splits**: Inserting data with non-sequential keys (e.g., random UUIDs) splits B-Tree leaf pages, fragmenting files and degrading performance.
*   **Redundant Index Maintenance Overhead**: Keeping unused, duplicate, or overlapping indexes that waste CPU cycles and storage space during batch updates.

This module details the physical impact of indexes on write performance, explaining B-Tree balancing operations and providing strategies for pruning indexes to balance read and write performance.

---

## 2. Why This Topic Matters
In transactional (OLTP) and financial applications, database latency is bounded by write capacity. If a table has 10 indexes, an `INSERT` statement must write to 11 separate physical structures (the table heap + 10 B-Trees). This increases transactional lock hold times, limits database write throughput, and increases storage space requirements.

Understanding B-Tree write mechanics allows developers to design balanced indexing strategies, selecting key patterns (e.g., auto-incrementing integers vs. random strings) and pruning redundant indexes to optimize write-intensive workloads.

---

## 3. Core Technical Concepts & Deep Dives

### 3.1 Insert Operations & Write Amplification
When executing an `INSERT` statement on a heap table:
1.  **Table Write**: The database engine appends the row to an active table data block. This is a low-cost operation.
2.  **Index Writes**: For *every* index defined on the table, the database must traverse the B-Tree, locate the correct leaf node sorted position, and write the index key and ROWID.

```
                  [INSERT TRANSACTION PIPELINE]
                         ┌─────────────┐
                         │ INSERT Row  │
                         └──────┬──────┘
                                ▼
                   ┌─────────────────────────┐
                   │ Write to Table Storage  │ (1 Block Write)
                   └────────────┬────────────┘
                                ▼
             ┌──────────────────┴──────────────────┐
             ▼                                     ▼
     ┌──────────────┐                      ┌──────────────┐
     │ Write Index 1│                      │ Write Index 2│ (...for every index)
     └──────┬───────┘                      └──────┬───────┘
            ▼                                     ▼
      (B-Tree Seek)                         (B-Tree Seek)
            ▼                                     ▼
     Insert sorted key                     Insert sorted key
```

#### Page Splits and Leaf Fragmentation
If a target B-Tree leaf page is full, the engine cannot write the key. It must perform a **Page Split**:
1.  Allocate a new leaf block page.
2.  Move approximately half of the index keys from the full page to the new page.
3.  Write the new index key to the correct page.
4.  Insert a new routing entry into the parent branch node block. (If the branch page is also full, the split cascades upwards).
Page splits generate random disk write operations, fragment the index layout, and degrade subsequent range scans.

---

### 3.2 Delete Operations
When executing a `DELETE` statement:
1.  The database engine locates the table row and marks it as deleted in the table page.
2.  For every B-Tree index, the database traverses the tree, locates the key, and marks it as deleted (a logical delete).
3.  **Leaf Node Merging**: If deletions cause a B-Tree page's utilization to drop below a threshold (typically 50%), the engine attempts to merge it with a neighboring page, removing routing keys from parent branch blocks.

---

### 3.3 Update Operations
An `UPDATE` statement's performance depends on whether the modified columns are covered by indexes:
*   **Non-Indexed Columns**: If the updated column is not indexed (e.g., updating a description column), the engine updates the value in-place inside the table data page block. This is a fast, single-block write.
*   **Indexed Columns**: If the updated column is indexed, the database must perform two index operations:
    1.  Traverse the B-Tree to find the old key value, and **delete** the entry.
    2.  Traverse the B-Tree to find the new key's sorted location, and **insert** the new entry.

#### Key Principle:
> [!IMPORTANT]
> Updating an indexed column is processed as an index delete followed by an index insert. It generates twice the index write overhead of an insert operation.

---

## 4. Code & Query Performance Lab

### 4.1 Index Maintenance Cost Study
Let's analyze the operational disk block writes required to insert 1 row into an `employees` table under three scenarios:

```sql
CREATE TABLE employees (
    employee_id   NUMERIC         PRIMARY KEY,
    first_name    VARCHAR(100)    NOT NULL,
    last_name     VARCHAR(100)    NOT NULL,
    email         VARCHAR(150)    NOT NULL,
    phone_number  VARCHAR(50)     NOT NULL,
    status        VARCHAR(20)     NOT NULL
);
```

#### Scenario A: Minimal Indexes
*   Active Indexes: `PRIMARY KEY` unique index only.
*   *Write Cost*: 1 Table block write + 1 Index block write = **2 block writes**.

#### Scenario B: Heavy Indexes
*   Active Indexes: `PRIMARY KEY`, `idx_emp_names (last_name, first_name)`, `idx_emp_email (email)`, `idx_emp_phone (phone_number)`, and `idx_emp_status (status)`.
*   *Write Cost*: 1 Table block write + 4 B-Tree index block writes = **5 block writes** (assuming no page splits).

#### Scenario C: Over-Indexing with Page Split
*   Active Indexes: Same as Scenario B, but the `idx_emp_email` leaf page is full and splits.
*   *Write Cost*: 1 Table block write + 3 Standard Index writes + 2 Page Split writes (allocating and writing the split page) + 1 Branch update = **7 block writes**.

---

### 4.2 Drop Redundant Composite Indexes
Redundant indexes consume write capacity without providing any read benefits. We can drop indexes that are left-prefixes of other indexes.

```sql
-- REDUNDANT INDEX LAYOUT:
CREATE INDEX idx_emp_last ON employees (last_name);
CREATE INDEX idx_emp_last_first ON employees (last_name, first_name);

-- OPTIMIZATION:
-- Since idx_emp_last_first can satisfy queries filtering on last_name alone,
-- idx_emp_last is redundant and should be dropped.
DROP INDEX idx_emp_last;
```

---

## 5. Hands-on Exercises

1.  **Write Amplification Audit**:
    A table has 6 indexes. An update query updates two columns: `status` (which is indexed) and `salary` (which is not indexed).
    Compute the number of B-Tree index adjustments the database must perform to execute this update for a single row.
2.  **Primary Key Selection Mechanics**:
    Explain why using a sequentially incrementing integer (`IDENTITY` or `AUTO_INCREMENT`) as the Primary Key on a Clustered Index table (such as MySQL InnoDB) minimizes page splits compared to using a randomly generated UUID string.

---

## 6. Mini-Project: Index Pruning & Performance Audit

### Scenario
An OLTP billing database table `invoices` (5,000,000 rows) is experiencing transaction timeouts during peak hours. The table receives 300 `INSERT` and 500 `UPDATE` queries per second. 

An inspection of the schema reveals the following index layout:
*   `PK_invoices` on `invoice_id` (Primary Key)
*   `idx_inv_client` on `client_id`
*   `idx_inv_client_date` on `client_id, invoice_date`
*   `idx_inv_date` on `invoice_date`
*   `idx_inv_status` on `status`
*   `idx_inv_client_status` on `client_id, status`
*   `idx_inv_date_status` on `invoice_date, status`

### Tasks
1.  Identify all redundant or overlapping indexes that can be safely dropped without affecting read performance.
2.  Provide the SQL drop statements.
3.  Calculate the write reduction (block writes saved per second) achieved by pruning these indexes.

#### Solution Guide:
1.  *Redundancy Analysis*:
    *   `idx_inv_client` `(client_id)` is a left-prefix of `idx_inv_client_date` `(client_id, invoice_date)` and `idx_inv_client_status` `(client_id, status)`. It is redundant.
    *   `idx_inv_date` `(invoice_date)` is a left-prefix of `idx_inv_date_status` `(invoice_date, status)`. It is redundant.
    *   `idx_inv_status` `(status)` is a single-column index. If `status` has low cardinality (e.g., only `'PAID'`, `'UNPAID'`), a range scan on `status` alone is inefficient. In most queries, it is paired with `client_id` or `invoice_date`. If a query filters on `status` alone, we can keep it, but it might be overlapping.
2.  *Pruning SQL*:
    ```sql
    DROP INDEX idx_inv_client;
    DROP INDEX idx_inv_date;
    ```
3.  *Write Savings*:
    *   We dropped 2 indexes.
    *   Current write load: 300 inserts + 500 updates = 800 modifications per second.
    *   *For Inserts*: Each insert saved 2 B-Tree writes. $300 \times 2 = 600$ writes saved/sec.
    *   *For Updates*: If updates modify `client_id` or `invoice_date` (rare for invoice logs, but assuming standard modifications), updates to those columns save delete + insert overhead. If updates modify other columns, they are unaffected, but we save significant overhead during page splits. Dropping these indexes reduces write amplification and frees up memory cache space.

---

## 7. Deep-Dive Interview Questions

### Q1: Explain the difference between a page split on sequential keys (right-page split) vs. random keys (50/50 split) in a B-Tree index.
**Answer:**
*   **Random Keys Split (50/50 split)**: When inserting random keys (e.g., UUID hashes), the insertion point lands in a random leaf page. When a page is full, the engine splits it by allocating a new page and moving 50% of the keys. This leaves both pages 50% empty. This results in index bloat and fragmented storage, requiring $2\times$ disk space.
*   **Sequential Keys Split (Right-Page Split / 90/10 split)**: When inserting ascending sequential keys (e.g., auto-incrementing IDs), the insert point is always at the right-most edge of the index B-Tree. When the right-most page is full, the database knows no values smaller than the current max will be inserted. It allocates a new page, moves only the last entry (or none), and keeps the original page 100% full. This prevents index bloat and achieves close to 100% space efficiency.

### Q2: What is the PostgreSQL HOT (Heap-Only Tuple) optimization, and how does it optimize write performance?
**Answer:** In PostgreSQL, an `UPDATE` write operation writes a new version of the row (tuple) to the table block. Under standard behavior, this requires updating all B-Tree indexes to point to the new tuple's ROWID, even if the indexed columns were not modified.
The **HOT (Heap-Only Tuple) optimization** bypasses index updates if two conditions are met:
1.  No indexed columns are modified by the `UPDATE` statement.
2.  The new row version (tuple) can fit in the **same physical table block** as the old version.
*   *Mechanics*: The database creates a redirect pointer (chained line) inside the table block from the old tuple to the new tuple. The B-Tree indexes continue to point to the old tuple's ROWID, and the query engine follows the redirect link to find the updated row version. This eliminates B-Tree index writes.

### Q3: Why does having too many indexes degrade database buffer cache efficiency?
**Answer:** The database buffer cache (e.g., InnoDB Buffer Pool) stores table and index pages in memory to prevent slow disk reads.
*   **Cache Contention**: Every index on a table has its own B-Tree pages. When data is inserted or updated, the database must load the target index branch and leaf pages into the buffer cache to perform the write.
*   **Eviction Pressure**: Having many indexes forces the database to load more index pages into memory. This evicts active table data pages and other index pages from the buffer cache. This increases page faults, forcing subsequent read queries to fetch pages from disk, degrading overall system performance.

---

## 8. Summary & Key Takeaways
*   **Write Tax**: Indexes speed up reads but tax writes. Every `INSERT`, `DELETE`, and `UPDATE` on indexed columns must update corresponding B-Tree keys.
*   **Page Splits**: Inserting random keys triggers 50/50 page splits, leaving pages half-empty. This fragments storage and degrades range scans. Sequential keys trigger right-page splits, preserving index density.
*   **Update Dual-Phase**: Updating an indexed column is processed as a B-Tree delete followed by a B-Tree insert, generating double the write overhead.
*   **Index Pruning**: Periodically review table index configurations and drop redundant, unused, or left-prefix duplicate indexes to maximize write capacity.
