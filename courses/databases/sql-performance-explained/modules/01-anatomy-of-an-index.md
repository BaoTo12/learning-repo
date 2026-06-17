# Module 01: Anatomy of a Database Index

## 1. What Problem This Module Solves
SQL is a declarative language (4GL) where developers write *what* data they want (e.g., `SELECT ... WHERE last_name = 'WINAND'`), completely abstracting away *how* the database engine retrieves it. While this abstraction speeds up feature development, it hides hardware realities. Without a clear mental model of how data is physically laid out on disk and indexed in memory, developers treat database engines like black boxes. 

A naive understanding of databases often results in:
*   Assuming "using an index" makes a query instantly fast, leading to confusion when indexed queries stall.
*   Misunderstanding the performance difference between a unique lookup and a range scan.
*   Failing to budget the physical block reads required when traversing the index tree and fetching row data.

This module bridges the declarative abstraction of SQL with physical storage layout realities, establishing the structural basics of B-Tree indexing.

---

## 2. Why This Topic Matters
Database performance is directly constrained by physical I/O boundaries. Accessing data in RAM takes nanoseconds; fetching blocks from disk takes milliseconds (even with modern NVMe storage, random access is orders of magnitude slower than sequential access). 

An index is not a magical performance booster; it is a highly structured, redundant copy of select column data that points back to the primary table. By learning the physical anatomy of an index—how doubly linked list pages are traversed and how the B-Tree isolates data locations—developers can design queries and schema structures that minimize physical block fetches. Furthermore, understanding the division of labor between developers (who know application access paths) and DBAs (who manage storage infrastructure) empowers developers to take ownership of indexing, where performance problems are usually resolved.

---

## 3. Core Technical Concepts & Deep Dives

To optimize SQL queries, we must analyze how databases organize table records and index entries at a block level.

### 3.1 Heap Tables vs. Indexed Leaf Nodes
Relational database engines store primary table rows in a structure called a **Heap Table**.
*   **Heap Table storage**: Rows are stored in data blocks (pages) in an arbitrary physical order. There is no physical sorting. If you insert a new employee, they are appended to whatever block has free space. Data blocks have no physical connection to one another.
*   **Index Leaf Nodes storage**: The database index is a separate, dedicated storage structure. The bottom-most level of a B-Tree index consists of **Leaf Nodes**. These leaf nodes are sorted logically by the indexed column value. Because physical relocation of disk blocks during inserts is too expensive, the logical ordering of index leaf nodes is maintained via a **Doubly Linked List**. Each index leaf node resides on a block and contains pointers to its preceding and succeeding leaf nodes.

```
[INDEX LEAF NODES (Sorted Doubly Linked List)]
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ Key: 'ADAMS'     │      │ Key: 'SMITH'     │      │ Key: 'WINAND'    │
│ ROWID: Page1/Row2│◄────►│ ROWID: Page2/Row1│◄────►│ ROWID: Page1/Row1│
└────────┬─────────┘      └────────┬─────────┘      └────────┬─────────┘
         │                         │                         │
         │ (ROWID Pointers)        │                         │
         ▼                         ▼                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│ [HEAP TABLE STORAGE (Unsorted Pages on Disk)]                       │
│                                                                      │
│ Page 1:                                                              │
│  Row 1: { last_name: 'WINAND', email: 'winand@db.org' } <────────────┘
│  Row 2: { last_name: 'ADAMS', email: 'adams@db.org' }   <────┐
│                                                              │
│ Page 2:                                                      │
│  Row 1: { last_name: 'SMITH', email: 'smith@db.org' }   <────┘
└──────────────────────────────────────────────────────────────────────┘
```

Each index entry in a leaf node contains:
1.  **The Indexed Key**: The value of the column (e.g., `'WINAND'`).
2.  **The ROWID (Row Identifier)**: A physical pointer to the exact file, block, and directory slot on disk where the corresponding table row resides.

### 3.2 The B-Tree Search Structure
While the doubly linked list preserves the sorted order of leaf nodes, scanning it sequentially from the beginning to find a key would result in $O(N)$ time complexity. To speed up the search, databases construct a balanced search tree (B-Tree) on top of the leaf nodes:

```
                      ┌──────────────────┐
                      │    [ROOT NODE]   │ (Top Page)
                      │   Keys: [50, 100]│
                      └─────┬───┬────┬───┘
            ┌───────────────┘   │    └───────────────┐
            ▼                   ▼                    ▼
   ┌─────────────────┐ ┌─────────────────┐  ┌─────────────────┐
   │ [BRANCH NODE 1] │ │ [BRANCH NODE 2] │  │ [BRANCH NODE 3] │ (Intermediate Pages)
   │ Keys: [15, 30]  │ │ Keys: [65, 80]  │  │ Keys: [115, 130]│
   └────┬────┬────┬──┘ └────┬────┬────┬──┘  └────┬────┬────┬──┘
   ┌────┘    │    └────┐    │         │          │         └────┐
   ▼         ▼         ▼    ▼         ▼          ▼              ▼
┌───────┐ ┌───────┐ ┌───────┐                      ┌───────┐ ┌───────┐
│Leaf 1 │─│Leaf 2 │─│Leaf 3 │ .................... │Leaf N │─│Leaf M │ (Doubly Linked List)
│[0-14] │ │[15-29]│ │[30-49]│                      │[115-  │ │[130+  │
└───────┘ └───────┘ └───────┘                      └───────┘ └───────┘
```

*   **Root Node**: The entry point of the search tree. It holds routing keys pointing to intermediate branch nodes.
*   **Branch Nodes**: Intermediate routing layers. A branch entry records the maximum value stored in its child node page, acting as an index directory.
*   **Balance Property**: The B-Tree is *balanced* because the depth from root to leaf node is identical at every point across the entire database index.
*   **Logarithmic Scalability**: B-Trees have a high branching factor (fan-out ratio). While binary trees have 2 child nodes per parent, a B-Tree page (e.g., 8KB) can hold hundreds of index keys and routing pointers. This ensures that even tables with billions of rows only have B-Tree depths of 4 or 5.

### 3.3 The Three Phases of an Index Lookup
When executing a query utilizing an index, the database engine completes three physical phases:

$$\text{Total Lookup Time} = \text{Tree Traversal (Logarithmic)} + \text{Leaf Chain Scan} + \text{Heap Table Random Access (ROWID)}$$

1.  **Tree Traversal**: The optimizer traverses the B-Tree from root node to the target leaf node. This requires a fixed number of page reads matching the tree depth (usually 3–5 I/O operations).
2.  **Following the Leaf Node Chain**: Once the starting key is located in the leaf node, the engine scans the leaf node page horizontally to retrieve matching entries (for range queries or duplicate keys).
3.  **Table Fetching**: Using the ROWIDs extracted from the index leaf nodes, the engine executes random I/O operations to fetch the actual rows from the heap table pages to obtain non-indexed columns.

---

## 4. Code & Query Performance Lab

We will analyze the physical database operations using standard execution plans.

### 4.1 Schema Setup
Let's initialize a sample database schema:

```sql
CREATE TABLE employees (
    employee_id   NUMERIC         NOT NULL,
    first_name    VARCHAR(100)    NOT NULL,
    last_name     VARCHAR(100)    NOT NULL,
    date_of_birth DATE            NOT NULL,
    phone_number  VARCHAR(50)     NOT NULL,
    CONSTRAINT employees_pk PRIMARY KEY (employee_id)
);

-- Creating a non-unique index on last_name
CREATE INDEX emp_name ON employees (last_name);
```

### 4.2 Execution Plan Verification
Let's analyze two different queries to see how index traversal operations are reported in the execution plan.

#### Scenario A: Unique Key Lookup
```sql
SELECT first_name, last_name 
  FROM employees 
 WHERE employee_id = 123;
```
**Oracle Execution Plan Output:**
```
---------------------------------------------------------------
|Id |Operation                   | Name         | Rows | Cost |
---------------------------------------------------------------
| 0 |SELECT STATEMENT            |              |    1 |    2 |
| 1 | TABLE ACCESS BY INDEX ROWID| EMPLOYEES    |    1 |    2 |
|*2 |  INDEX UNIQUE SCAN         | EMPLOYEES_PK |    1 |    1 |
---------------------------------------------------------------
Predicate Information (identified by operation id):
---------------------------------------------------
   2 - access("EMPLOYEE_ID"=123)
```
*   **`INDEX UNIQUE SCAN`**: The database traverses the B-Tree to find the target `employee_id`. Since a primary key constraint guarantees uniqueness, the database knows only one entry can match. It stops immediately after tree traversal without scanning the leaf chain.

#### Scenario B: Non-Unique Range Scan
```sql
SELECT first_name, last_name 
  FROM employees 
 WHERE last_name = 'WINAND';
```
**Oracle Execution Plan Output:**
```
---------------------------------------------------------------
|Id |Operation                   | Name         | Rows | Cost |
---------------------------------------------------------------
| 0 |SELECT STATEMENT            |              |    1 |    3 |
| 1 | TABLE ACCESS BY INDEX ROWID| EMPLOYEES    |    1 |    3 |
|*2 |  INDEX RANGE SCAN          | EMP_NAME     |    1 |    1 |
---------------------------------------------------------------
Predicate Information (identified by operation id):
---------------------------------------------------
   2 - access("LAST_NAME"='WINAND')
```
*   **`INDEX RANGE SCAN`**: Since the index `emp_name` is non-unique, multiple employees might share the last name `'WINAND'`. The engine traverses the B-Tree to find the first matching key, and then traverses the doubly linked list leaf pages to locate all matching records until a non-matching key is encountered.
*   **`TABLE ACCESS BY INDEX ROWID`**: For every matching index entry, the engine extracts the ROWID and reads the corresponding heap table block to collect `first_name`.

---

## 5. Hands-on Exercises

1.  **B-Tree Height Calculation**:
    Assuming a B-Tree page can hold 200 index entry key/pointer segments, compute the maximum number of record pointers the tree can support at:
    *   Height 3 (1 root, branch layer, leaf layer)
    *   Height 4
    Compare this to a balanced Binary Search Tree (BST) at the same height.
2.  **Operation Analysis**:
    Explain why replacing a `PRIMARY KEY` unique index lookup with a non-unique index forces the database optimizer to switch from `INDEX UNIQUE SCAN` to `INDEX RANGE SCAN`, and evaluate the performance penalty of this change.

---

## 6. Mini-Project: Index Block I/O Cost Model

### Scenario
An unsorted heap table `employees` contains 1,000,000 rows. The table blocks on disk have an average density of 100 rows per block (totaling 10,000 blocks). 

We have a query:
```sql
SELECT first_name, phone_number FROM employees WHERE last_name = 'SMITH';
```
Assume there is a non-unique index on `last_name` with a B-Tree depth of 3. We are comparing three operational paths.

### Tasks
Calculate the estimated physical block reads required for the following scenarios. Assume no blocks reside in memory cache:
1.  **Path A: Full Table Scan** (No index is used).
2.  **Path B: Indexed Range Scan (Worst Case)**. The query matches 50 rows, and due to random database heap inserts, every matching employee record resides in a different page block on disk.
3.  **Path C: Indexed Range Scan (Best Case)**. The query matches 50 rows, but all matching employee records happen to reside in the same physical page block on disk.

#### Solution Template:
*   *Path A Cost*: 10,000 blocks (Every block in the table must be read).
*   *Path B Cost*: 3 (B-Tree traversal) + 1 (Leaf chain block read) + 50 (50 distinct heap table blocks) = 54 blocks.
*   *Path C Cost*: 3 (B-Tree traversal) + 1 (Leaf chain block read) + 1 (All rows in same heap block) = 5 blocks.

---

## 7. Deep-Dive Interview Questions

### Q1: What makes a B-Tree index balanced, and how does this affect write overhead?
**Answer:** A B-Tree is defined as balanced because all leaf nodes reside at the exact same depth. When new rows are inserted, deleted, or updated, the database must write to the index to keep the leaf nodes sorted. If a leaf node block runs out of free space during an insert, the engine performs a **Page Split**: it allocates a new block, moves half of the entries to the new page, and inserts a new routing key into the parent branch node. If the parent branch is also full, the split cascades upwards. This balancing logic guarantees that lookup times remain consistent, but it introduces disk write overhead during data modification.

### Q2: Why is a B-Tree index preferred over a Binary Search Tree (BST) or Hash Index for disk-based relational tables?
**Answer:** 
*   **BST vs. B-Tree**: Binary search trees have a branching factor of 2, resulting in very deep structures (e.g., a BST storing $10^6$ nodes has a height of $\approx 20$). Since each tree node traversal requires a disk seek, a query would need 20 block reads. A B-Tree page holds hundreds of keys (branching factor of $\geq 100$), keeping height to 3 or 4, which limits block reads to 3 or 4.
*   **Hash Index vs. B-Tree**: Hash indexes use hash tables, which resolve key matches in $O(1)$ time. However, they only support exact match lookups (`WHERE key = 'VAL'`). They do not support range queries (`WHERE key >= 10`), sorted queries (`ORDER BY`), or prefix matching (`LIKE 'A%'`). The B-Tree structure keeps data sorted, supporting both exact lookups and sorted range scans.

### Q3: Under what condition will the cost of a TABLE ACCESS BY INDEX ROWID make an index slower than a Full Table Scan?
**Answer:** The table access phase uses random I/O to fetch rows from heap storage by ROWID. If a query matches a large percentage of the table's rows (e.g., 20% of the entries), accessing the table by index requires fetching thousands of blocks individually via random I/O. In contrast, a Full Table Scan reads blocks sequentially using multi-block read I/O, which reads large physical chunks of disk in a single system call. When the number of matching records exceeds a threshold (typically 10–20% of the table depending on system architecture), the random I/O overhead of ROWID lookups makes the index slower than reading the entire table sequentially.

---

## 8. Summary & Key Takeaways
*   **declarative vs. Procedural**: SQL defines what data is retrieved; the database engine translates it into a physical access path.
*   **B-Tree Layout**: A balanced B-Tree index has root and branch routing directories pointing to sorted, doubly linked leaf nodes.
*   **The ROWID Boundary**: Finding the key in the index B-Tree is fast ($O(\log N)$). The primary performance bottleneck is fetching table columns by ROWID from unsorted heap storage blocks.
*   **Execution Operations**: The unique lookup (`INDEX UNIQUE SCAN`) traverses the B-Tree once, whereas the range lookup (`INDEX RANGE SCAN`) traverses the B-Tree and walks the doubly linked list leaf chain to extract multiple ROWIDs.
