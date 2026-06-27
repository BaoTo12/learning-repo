# Module 01: Introduction and Overview

Database management systems (**DBMS**) serve different purposes:

- **Temporary hot data**: Some databases are used primarily for fast, short-term data.
- **Long-lived cold storage**: Others serve as durable, long-term archives.
- **Complex analytical queries**: Some support deep data analysis.
- **Key-value access**: Some only allow accessing values by a single key.
- **Time-series data**: Others are optimized for storing time-stamped sequences.
- **Large blobs**: Some are designed to store large binary objects efficiently.

To understand the differences and make clear distinctions, we start with a short classification and overview. This helps us understand the scope of our later discussions.

Terminology can sometimes be **unclear** and hard to understand without a complete context. For example, the differences between **column stores** and **wide column stores** (which have little or nothing to do with each other), or how **clustered** and **nonclustered indexes** relate to **index-organized tables**. This module aims to **clarify** these terms and provide their precise definitions.

We start with an overview of **database management system (DBMS) architecture**, discussing system components and their responsibilities. Then, we discuss the differences among databases in terms of:

- ==**Storage medium**==: In-memory versus disk-based systems.
- ==**Data layout**==: Column-oriented versus row-oriented systems.

These two groups do not represent a full classification of databases, and there are many other ways to classify them. For example, some sources group **DBMSs** into three major categories:

- **Online Transaction Processing (OLTP) Databases**: These handle a large number of user-facing requests and transactions. Queries are usually predefined and short-lived.
- **Online Analytical Processing (OLAP) Databases**: These handle complex aggregations. They are used for analytics and data warehousing, and can run complex, long-running, unplanned (**ad hoc**) queries.
- **Hybrid Transactional and Analytical Processing (HTAP)**: These databases combine the properties of both **OLTP** and **OLAP** stores.

> ### 💡 Beginner's Corner: OLTP vs. OLAP
>
> - **Core Architectural Difference**:
>     - **OLTP (Online Transaction Processing)**: Optimized for operational workloads. These systems handle thousands of concurrent read and write operations. The operations are small, touch only a few rows at a time (e.g., retrieving a single user profile or updating a balance), and must complete in milliseconds.
>     - **OLAP (Online Analytical Processing)**: Optimized for decision-support and reporting. These systems handle massive, read-heavy workloads where queries scan millions of rows to compute aggregations, averages, and trends. Queries are highly complex and can take seconds or minutes to run.
> - **Jargon Buster**:
>     - **Ad hoc query**: A one-off, unplanned query created on the spot by a user or analyst (e.g., finding the number of new registrations within a specific hour), as opposed to predefined queries pre-programmed into the application.

There are many other terms and classifications: **key-value stores**, **relational databases**, **document-oriented stores**, and **graph databases**. We assume the reader has a high-level understanding of their functionality. Because the concepts we discuss are widely used in most of these stores, a complete classification is not necessary for our discussions.

Since Part I of this course focuses on storage and indexing structures, we must understand high-level data organization and the relationship between ==**data files** and **index files**==.

Finally, we discuss three techniques widely used to build efficient storage structures, and how these techniques affect their design and implementation:

- ==**Buffering**==
- ==**Immutability**==
- ==**Ordering**==

---

## DBMS Architecture

> **Key Takeaway**: There is no single, standard blueprint for **DBMS** design. Every database is built differently, and component boundaries are often blurred in practice. Even if boundaries are clear on paper, the actual code may couple independent components for performance optimizations, edge-case handling, or architectural reasons.

Databases use a **client/server model**:

- **Database instances (nodes)** act as **servers**.
- **Application instances** act as **clients**.

### The Query Lifecycle

When a client sends a request, it flows through the following subsystems:

1.  **Transport Subsystem**:
    - Receives client requests in the form of queries (usually in a query language).
    - Manages communication with other nodes in the database cluster.
2.  **Query Processor**:
    - Parses, interprets, and validates the incoming query.
    - Performs access control checks (permissions) once the query is interpreted.
3.  **Query Optimizer**:
    - Removes impossible or redundant parts of the query.
    - Finds the most efficient way to run the query using internal statistics (e.g., index cardinality, approximate intersection size) and data placement (which nodes hold the data and their transfer costs).
    - Handles relational operations (represented as a dependency tree) and selects access methods.
    - Generates the **execution plan** (or **query plan**), which is the sequence of operations required to complete the query. The optimizer selects the most efficient plan from the available options.
4.  **Execution Engine**:
    - Executes the selected plan.
    - Collects results from local and remote operations. Remote execution involves reading/writing data to other cluster nodes and handling replication.
5.  **Storage Engine**:
    - Executes local queries. It manages the physical storage, indexing, and transactional guarantees on disk.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c51a439e-41d9-41f1-9c12-e838570d1dad/markdown_4/imgs/img_in_image_box_131_87_1022_1566.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A58Z%2F-1%2F%2F4d70d03dc1d153fd4c44968b2af0e452d36d3d2fdd411179864cb144a1109154" alt="Image" width="74%" /></div>

### Storage Engine Subcomponents

The storage engine consists of several dedicated components:

- **Transaction Manager**: Schedules transactions and guarantees that they do not leave the database in a logically inconsistent state.
- **Lock Manager**: Controls locks on database objects for running transactions, ensuring concurrent operations do not violate physical data integrity.
- **Access Methods (Storage Structures)**: Manage how data is organized and accessed on disk. These include heap files, **B-Trees**, and **LSM Trees**.
- **Buffer Manager**: Caches data pages in memory to reduce disk I/O.
- **Recovery Manager**: Maintains the operation log (write-ahead log) and restores the system state after a crash or failure.

> **Note**: Together, the **Transaction Manager** and **Lock Manager** handle **concurrency control**. They guarantee both logical and physical data integrity while keeping concurrent execution highly efficient.

---

## Memory-Based DBMS Versus Disk-Based DBMS

Database systems store data in memory and on disk:

- **In-Memory DBMS (Main Memory DBMS)**: Store data primarily in **RAM** and use the disk only for recovery, logging, and backups.
- **Disk-Based DBMS**: Hold most of the data on **disk** and use RAM for caching disk contents or as a temporary storage.

Both types of systems use the disk to some extent, but main memory databases store their contents almost exclusively in RAM.

### Architectural Comparison: Memory- vs. Disk-Based DBMS

| Feature             | In-Memory (Main Memory) DBMS                                   | Disk-Based DBMS                                                                   |
| :------------------ | :------------------------------------------------------------- | :-------------------------------------------------------------------------------- |
| **Primary Storage** | **RAM** (almost exclusively)                                   | **Persistent Disk** (SSD / HDD)                                                   |
| **Disk Usage**      | Only for logging, recovery, and backups                        | Primary data storage, using RAM for caching                                       |
| **Performance**     | Extremely fast (memory access is much faster than disk) $ ^{1} | Slower (limited by disk I/O and latency)                                          |
| **Data Structures** | Uses pointers directly; optimized for random memory access     | Uses specialized structures (e.g., wide, short trees) optimized for block storage |
| **Key Constraints** | **RAM Volatility** (data loss risk) and **High Cost**          | Disk latency, but highly durable and cheap                                        |

### Durability in Memory-Based Stores

Because RAM is **volatile** (temporary), main memory databases use persistent backups and logs to prevent data loss:

1.  **Write-Ahead Log (WAL)**: Before a write operation is complete, its results must be written to a sequential log file on disk.
2.  **Checkpointing**: To avoid reading the entire log during startup, in-memory stores maintain a sorted disk-based backup copy. The system periodically applies log records to this backup in batches (decoupled from client requests).
3.  **Discarding Logs**: After a batch of log records is processed, the backup holds a database snapshot for a specific point in time, and log contents up to this point can be discarded. This reduces recovery times without forcing clients to block.

> **Future Outlook**: **Non-Volatile Memory (NVM)** technologies are closing the gap. NVM storage reduces or completely removes the difference between read and write latencies, improves performance, and allows byte-addressable access.

### Key Architectural Differences

- **Cache vs. In-Memory**: It is not accurate to say that an in-memory database is the equivalent of a disk-based database with a huge page cache. Disk-based databases carry serialization and page-layout overheads that prevent them from matching the optimizations of pure in-memory designs.
- **Access Granularity**: In memory, following pointers is fast, allowing a wider variety of complex data structures. On disk, data must be accessed in blocks, forcing the use of block-optimized structures like B-Trees. Variable-sized data in memory is easily managed with pointers, whereas on disk it requires complex layout schemes.

---

## Column-Oriented DBMS Versus Row-Oriented DBMS

Most databases store tables consisting of columns and rows:

- **Field**: The intersection of a column and a row, representing a single value. Fields in the same column share the same data type.
- **Row**: A collection of values that logically belong to the same record, usually identified by a unique key.

Databases are classified by their physical layout on disk:

- **Row-Oriented (Horizontal Partitioning)**: Stores all values belonging to the same row together.
- **Column-Oriented (Vertical Partitioning)**: Stores all values belonging to the same column together.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//793d4e45-2762-467a-8b37-f53fe47ddea0/markdown_1/imgs/img_in_image_box_139_806_1050_1008.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A57Z%2F-1%2F%2Ffaf7a078a52c1c480e6fad25cdd4754c0ae8ab853c9060303ed22ddc1aa1f819" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 1-2. Data layout in column- and row-oriented stores</div>

### Row-Oriented Data Layout

- **Examples**: `MySQL`, `PostgreSQL`, and most traditional relational databases.
- **Layout**: Stores entire records together. For example:

| ID  | Name  | Birth Date  | Phone Number   |
| --- | ----- | ----------- | -------------- |
| 10  | John  | 01 Aug 1981 | +1 111 222 333 |
| 20  | Sam   | 14 Sep 1988 | +1 555 888 999 |
| 30  | Keith | 07 Jan 1984 | +1 333 444 555 |

- **Best Use Case**: Highly effective when entire records must be accessed or written together (e.g., OLTP workloads like user registration or point lookups).
- **Trade-offs**:
    - **Pros**: Excellent **spatial locality** $ ^{2} $ for row-based access. Since disks are read in blocks, a single block read loads the entire record.
    - **Cons**: Queries that only need a single column (e.g., retrieving only phone numbers) are slower and more expensive because the system must read and discard all other columns in the block.

### Column-Oriented Data Layout

- **Examples**: `MonetDB`, `C-Store` (the predecessor to `Vertica`), `Apache Parquet`, `Apache ORC`, `ClickHouse`.
- **Layout**: Partitions data vertically. Values for the same column are stored contiguously on disk.
- **Best Use Case**: Ideal for analytical workloads (**OLAP**) that compute aggregates (e.g., averages, trends) over millions of rows but only look at a few columns.

#### Logical vs. Physical Columnar Layout

**Logical View**:
| ID | Symbol | Date | Price |
|---|---|---|---|
| 1 | DOW | 08 Aug 2018 | 24,314.65 |
| 2 | DOW | 09 Aug 2018 | 24,136.16 |
| 3 | S&P | 08 Aug 2018 | 2,414.45 |
| 4 | S&P | 09 Aug 2018 | 2,232.32 |

**Physical Layout on Disk**:

- `Symbol`: `1:DOW; 2:DOW; 3:S&P; 4:S&P`
- `Date`: `1:08 Aug 2018; 2:09 Aug 2018; 3:08 Aug 2018; 4:09 Aug 2018`
- `Price`: `1:24,314.65; 2:24,136.16; 3:2,414.45; 4:2,232.32`

> **Note**: To reconstruct rows (tuples) for operations like joins or filtering, the system must map values across columns. To avoid the massive duplication of storing row keys with every value, column stores use **implicit identifiers (virtual IDs)** based on the position (offset) of the value in the file.

### Columnar Optimizations

Column stores go beyond simple physical layout adjustments by leveraging two key CPU and storage optimizations:

1.  **Vectorized Processing**: Reading contiguous values of the same type improves CPU cache use. Modern CPUs can use **vectorized instructions (SIMD)** to process multiple data points with a single CPU instruction $ ^{3} $.
2.  **High Compression Ratios**: Storing identical data types contiguously (e.g., numbers with numbers, strings with strings) allows the database to achieve much better compression. The database can apply different compression algorithms optimized for specific data types.

#### Decision Rule: Row vs. Column Store

- Use a **Row-Oriented Store** if:
    - Workloads consist of point queries and narrow range scans.
    - Queries read or write complete records (most or all columns at once).
- Use a **Column-Oriented Store** if:
    - Workloads consist of large scans spanning millions of rows.
    - Queries compute aggregates (e.g., sum, average) over a small subset of columns.

### Wide Column Stores

> **Crucial Distinction**: Do not confuse **column-oriented databases** with **wide column stores** (e.g., `Bigtable`, `HBase`).
>
> - In a wide column store, data is represented as a **multidimensional sorted map**.
> - Columns are grouped into **column families** (which are stored separately on disk).
> - Inside each column family, the data is stored **row-wise** (keys and values are stored together).

#### Conceptual View of a Wide Column Store (Webtable Example)

A Webtable stores web page snapshots, their attributes, and their link relationships at specific timestamps. It can be conceptually viewed as a nested map:

```json
{
    "com.cnn.www": {
        "contents": {
            "t6": { "html": "<html>..." },
            "t5": { "html": "<html>..." },
            "t3": { "html": "<html>..." }
        },
        "anchor": {
            "t9": { "cnnsi.com": "CNN" },
            "t8": { "my.look.ca": "CNN.com" }
        }
    },
    "com.example.www": {
        "contents": {
            "t5": { "html": "<html>..." }
        },
        "anchor": {}
    }
}
```

- **Row Key**: The reversed URL (e.g., `com.cnn.www`), which indexes each row.
- **Column Families**: Grouped columns (e.g., `contents` and `anchor`) stored separately on disk.
- **Column Key**: A combination of the column family and a qualifier (e.g., `contents:html`, `anchor:cnnsi.com`).
- **Version Control**: Column families store multiple versions of data, versioned by **timestamps** (e.g., `t3`, `t5`).

#### Physical Layout of a Wide Column Store

Physically, column families are stored in separate files on disk. Inside each column family file, data belonging to the same row key is kept together, sorted by key and timestamp:

**Column Family: `contents`**
| Row Key | Timestamp | Qualifier | Value |
| :--- | :--- | :--- | :--- |
| `com.cnn.www` | `t3` | `html` | `"<html>..."` |
| `com.cnn.www` | `t5` | `html` | `"<html>..."` |
| `com.cnn.www` | `t6` | `html` | `"<html>..."` |
| `com.example.www` | `t5` | `html` | `"<html>..."` |

**Column Family: `anchor`**
| Row Key | Timestamp | Qualifier | Value |
| :--- | :--- | :--- | :--- |
| `com.cnn.www` | `t8` | `cnnsi.com` | `"CNN"` |
| `com.cnn.www` | `t5` | `my.look.ca` | `"CNN.com"` |

---

## Data Files and Index Files

Rather than relying on the standard filesystem directories and files, databases organize data inside files using custom, highly specialized formats.

### Why Databases Use Specialized File Formats

- **Storage Efficiency**: Formats are designed to minimize storage overhead for every record.
- **Access Efficiency**: Data structures are optimized so records can be found in the fewest possible disk operations.
- **Update Efficiency**: Updates are written in ways that minimize the physical changes required on disk.

### File and Index Organization

- **Data Files**: Store the actual data records. Each table is usually stored in its own file.
- **Index Files**: Store record metadata to help locate records in the data files without performing slow, full-table scans. Index files are much smaller than data files.
- **Pages**: Files are split into fixed-size **pages** (usually matching the size of one or more disk blocks). Pages can be organized as simple record sequences or as **slotted pages**.
- **Tombstones (Deletion Markers)**: Modern storage systems rarely delete data from pages immediately. Instead, they write a **tombstone** (deletion marker) containing the key and a timestamp.
- **Garbage Collection (Compaction)**: Space occupied by old (shadowed) records or deleted records is reclaimed during garbage collection. This process reads the active pages, copies live records to a new location, and discards the old ones.

### Data Files

Data files (sometimes called primary files) can be organized in three primary ways:

1.  **Heap-Organized Tables (Heap Files)**:
    - Records are placed in no particular order, usually in the order they were written.
    - New writes require no reorganization; they are simply appended.
    - **Requires a separate index** containing pointers to the records to make them searchable.
2.  **Hash-Organized Tables (Hashed Files)**:
    - Records are grouped into **buckets** based on the hash value of their key.
    - Inside each bucket, records are stored either in append order or sorted by key for faster lookups.
3.  **Index-Organized Tables (IOTs)**:
    - Data records are stored directly inside the index itself, sorted by key.
    - Traversing the index locates both the key and the actual record, saving at least one disk seek.
    - Range scans are highly efficient because the data is already stored sequentially in key order.

#### Locating Records on Disk

- If data is in a **separate file**: The index stores **data entries** containing the primary key and a pointer to the record (such as a **file offset/row locator** or a bucket ID).
- If data is in an **Index-Organized Table**: The index entries store the actual data records directly.

### Index Files

An **index** maps search keys to their physical locations in data files.

- **Primary Index**: Built on the table's primary key. It typically holds unique entries (one per search key).
- **Secondary Index**: Built on other columns to allow query filtering by non-primary attributes. A secondary index can contain multiple entries per search key. It can point:
    - Directly to the data record using a file offset.
    - Indirectly by storing the record's primary key.

#### Clustered vs. Nonclustered Indexes

- **Clustered Index**: The physical order of the records in the data file matches the logical order of the index keys. A table can have only one clustered index (and is clustered by definition in index-organized tables).
- **Nonclustered Index**: The physical order of the records on disk does not match the index key order. The index contains pointers (offsets) to the records stored out-of-order in a separate data file.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e3a5f91f-ca5f-485b-b6b9-2b8fd335444a/markdown_3/imgs/img_in_image_box_147_143_581_346.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F5504089ab49d3b61994e018cd3b1e7d2bd673862ce26dc3eb1d6d392093462af" alt="Image" width="36%" /></div>
<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e3a5f91f-ca5f-485b-b6b9-2b8fd335444a/markdown_3/imgs/img_in_image_box_610_145_1044_364.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F54abc891db024e2999b77776c8cfcb8d2e029f1b1db183d65a43eed8ea4ed088" alt="Image" width="36%" /></div>
<div style="text-align: center;">Figure 1-5. Storing data records in an index file versus storing offsets to the data file (index segments shown in white; segments holding data records shown in gray)</div>

> **Note**: Primary keys uniquely identify records. If a table is created without a primary key, the storage engine often generates an **implicit primary key** automatically (e.g., `MySQL InnoDB` adds an internal auto-increment column).

### Primary Index as an Indirection

When secondary indexes need to locate a data record, databases choose between two primary reference models:

#### 1. Direct Reference (File Offsets)

- The secondary index stores the direct physical file offset (row locator) of the record.
- **Pros**: Fast reads; saves disk seeks because the database immediately goes to the file offset.
- **Cons**: Expensive writes and maintenance; if a record is updated, moved, or rescheduled during compaction, the database must update all secondary indexes pointing to it.

#### 2. Indirect Reference (Primary Key Indirection)

- The secondary index stores the record's primary key instead of its physical offset. Finding the record requires a two-step lookup: first in the secondary index, then in the primary index.
- **Pros**: Cheaper writes; moving or updating a record only requires updating the primary index pointer. Secondary indexes remain unchanged.
- **Cons**: Slower reads; every query using a secondary index must perform an extra primary index lookup (e.g., `MySQL InnoDB`).

| Reference Strategy         | Read Path Cost    | Write Path Cost (On Record Move)    | Secondary Index Size        |
| :------------------------- | :---------------- | :---------------------------------- | :-------------------------- |
| **Direct (File Offset)**   | **Low** (1 hop)   | **High** (Must update all indexes)  | Small (integer offset)      |
| **Indirect (Primary Key)** | **High** (2 hops) | **Low** (Only update primary index) | Larger (stores primary key) |

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fea32fbb-8229-4916-b6f8-bb95eed68416/markdown_0/imgs/img_in_image_box_139_161_561_493.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A57Z%2F-1%2F%2F35b3229e7773d004e16d081924780b946e234cbfd3ffdbe7eecdd41318c73d84" alt="Image" width="35%" /></div>
<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fea32fbb-8229-4916-b6f8-bb95eed68416/markdown_0/imgs/img_in_image_box_621_163_1046_510.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A57Z%2F-1%2F%2F699f84ad6a861c55d2a2b2d37dbf9b34930f6778a88704564a3d777d36e632b2" alt="Image" width="35%" /></div>
<div style="text-align: center;">Figure 1-6. Referencing data tuples directly (a) versus using a primary index as indirection (b)</div>

> **Hybrid Approach**: Some systems store both the physical file offset and the primary key. The database first attempts to read directly using the offset. If the offset is invalid (the record moved), it falls back to a primary key lookup and updates the secondary index with the new offset.

---

## Buffering, Immutability, and Ordering

While storage engines are built on top of core data structures, they must implement caching, crash recovery, transactions, and durability. To optimize these, storage structures tune three primary variables:

### 1. Buffering

- **Definition**: Whether the storage structure collects writes in memory before flushing them to disk.
- **Purpose**: Amortizes disk I/O costs. While all engines buffer to write full blocks, some implement custom buffering layers.
- **Examples**: Adding in-memory buffers to **B-Tree** nodes (**Lazy B-Trees**) or buffering all writes in memory before flushing sorted runs to disk (**LSM Trees**).

### 2. Mutability vs. Immutability

- **Mutable (In-Place Updates)**: The engine reads a page, updates its content in memory, and writes it back to the exact same physical location on disk (e.g., standard B-Trees).
- **Immutable (Append-Only)**: Once written, data files are never modified.
- **Append-Only**: All new inserts, updates, and deletes are appended to the end of the file (e.g., **LSM Trees**, `Bitcask`).
- **Copy-on-Write (CoW)**: When a page is modified, the updated page is written to a completely new physical location rather than overwriting the original.
- **Hybrid**: Structures like **Bw-Trees** combine B-Tree logic with an immutable, log-structured layout.

### 3. Ordering

- **Ordered**: Records are stored on disk sorted by their keys, ensuring keys that sort closely are placed contiguously.
    - **Pros**: Highly efficient range scans and sorted sequential reads.
- **Unordered**: Records are stored out of key order, typically in the order they were inserted.
    - **Pros**: Highly optimized, high-throughput write paths (e.g., `Bitcask`, `WiscKey` append-only files).
    - **Cons**: Range scans require sorting or random lookups, making them slow.

---

## Summary

In this chapter, we’ve discussed the architecture of a **DBMS** and covered its primary components.

- To highlight the importance of disk-based structures and their difference from in-memory ones, we discussed memory- and disk-based stores, coming to the conclusion that disk-based structures are important for both types of stores, but are used for different purposes.
- To understand how access patterns influence database system design, we discussed column- and row-oriented database management systems and the primary factors that set them apart.
- To start a conversation about how the data is stored, we covered data and index files.
- Lastly, we introduced three core concepts: **buffering**, **immutability**, and **ordering**. We will use them throughout this book to highlight properties of the storage engines that use them.
