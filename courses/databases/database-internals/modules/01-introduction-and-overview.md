# Module 01: Introduction and Overview

Database management systems (**DBMS**) serve different purposes:
*   **Temporary hot data**: Some databases are used primarily for fast, short-term data.
*   **Long-lived cold storage**: Others serve as durable, long-term archives.
*   **Complex analytical queries**: Some support deep data analysis.
*   **Key-value access**: Some only allow accessing values by a single key.
*   **Time-series data**: Others are optimized for storing time-stamped sequences.
*   **Large blobs**: Some are designed to store large binary objects efficiently.

> ### 💡 Beginner's Corner: Why do we use a DBMS?
> * **The Problem**: Imagine you are building a simple app. You could save your data by writing it into a simple text file (like a JSON file) on your hard drive. However, as your app grows, you run into serious problems:
>   1. **Concurrency**: What if two users try to update the same data at the exact same microsecond? They might overwrite each other's changes.
>   2. **Size**: What if your file grows to 50 gigabytes? Reading the whole file into memory just to look up one user's email will crash your server.
>   3. **Durability & Crashes**: What if the power cuts out right in the middle of writing to the file? Your data becomes corrupted.
> * **The Solution**: A **Database Management System (DBMS)** is a specialized, highly optimized piece of software designed to solve these exact problems. It acts as an extremely efficient mediator between your application and the physical storage hardware, ensuring your data is safe, organized, and lightning-fast to query.
> * **Jargon Buster**: 
>   * **Hot Data**: Data that is accessed and updated very frequently (e.g., your active shopping cart).
>   * **Cold Storage**: Data that is rarely accessed but must be kept for a long time (e.g., tax records from five years ago).
>   * **Blob (Binary Large Object)**: Large chunks of unstructured data like images, video clips, or PDF files.

To understand the differences and make clear distinctions, we start with a short classification and overview. This helps us understand the scope of our later discussions.

Terminology can sometimes be **unclear** and hard to understand without a complete context. For example, the differences between **column stores** and **wide column stores** (which have little or nothing to do with each other), or how **clustered** and **nonclustered indexes** relate to **index-organized tables**. This module aims to **clarify** these terms and provide their precise definitions.

We start with an overview of **database management system (DBMS) architecture**, discussing system components and their responsibilities. Then, we discuss the differences among databases in terms of:
*   **Storage medium**: In-memory versus disk-based systems.
*   **Data layout**: Column-oriented versus row-oriented systems.

These two groups do not represent a full classification of databases, and there are many other ways to classify them. For example, some sources group **DBMSs** into three major categories:

*   **Online Transaction Processing (OLTP) Databases**: These handle a large number of user-facing requests and transactions. Queries are usually predefined and short-lived.
*   **Online Analytical Processing (OLAP) Databases**: These handle complex aggregations. They are used for analytics and data warehousing, and can run complex, long-running, unplanned (**ad hoc**) queries.
*   **Hybrid Transactional and Analytical Processing (HTAP)**: These databases combine the properties of both **OLTP** and **OLAP** stores.

> ### 💡 Beginner's Corner: OLTP vs. OLAP
> * **Core Architectural Difference**:
>   * **OLTP (Online Transaction Processing)**: Optimized for operational workloads. These systems handle thousands of concurrent read and write operations. The operations are small, touch only a few rows at a time (e.g., retrieving a single user profile or updating a balance), and must complete in milliseconds.
>   * **OLAP (Online Analytical Processing)**: Optimized for decision-support and reporting. These systems handle massive, read-heavy workloads where queries scan millions of rows to compute aggregations, averages, and trends. Queries are highly complex and can take seconds or minutes to run.
> * **Jargon Buster**:
>   * **Ad hoc query**: A one-off, unplanned query created on the spot by a user or analyst (e.g., finding the number of new registrations within a specific hour), as opposed to predefined queries pre-programmed into the application.

There are many other terms and classifications: **key-value stores**, **relational databases**, **document-oriented stores**, and **graph databases**. We assume the reader has a high-level understanding of their functionality. Because the concepts we discuss are widely used in most of these stores, a complete classification is not necessary for our discussions.

Since Part I of this course focuses on storage and indexing structures, we must understand high-level data organization and the relationship between **data files** and **index files**.

Finally, we discuss three techniques widely used to build efficient storage structures, and how these techniques affect their design and implementation:
*   **Buffering**
*   **Immutability**
*   **Ordering**

---

## DBMS Architecture

> **Key Takeaway**: There is no single, standard blueprint for **DBMS** design. Every database is built differently, and component boundaries are often blurred in practice. Even if boundaries are clear on paper, the actual code may couple independent components for performance optimizations, edge-case handling, or architectural reasons.

Databases use a **client/server model**:
*   **Database instances (nodes)** act as **servers**.
*   **Application instances** act as **clients**.

> ### 💡 Beginner's Corner: The Client/Server Model
> * **How it Works**:
>   * The **Client** is the application code (e.g., a web server running Node.js or Python). It initiates connection requests and sends queries to the database over a network socket.
>   * The **Server** is the database process (e.g., MySQL or PostgreSQL) running on a machine. It listens for incoming connections, receives queries, processes them by reading/writing files on its storage drive, and sends the results back over the network.

### The Query Lifecycle

When a client sends a request, it flows through the following subsystems:

1.  **Transport Subsystem**:
    *   Receives client requests in the form of queries (usually in a query language).
    *   Manages communication with other nodes in the database cluster.
2.  **Query Processor**:
    *   Parses, interprets, and validates the incoming query.
    *   Performs access control checks (permissions) once the query is interpreted.
3.  **Query Optimizer**:
    *   Removes impossible or redundant parts of the query.
    *   Finds the most efficient way to run the query using internal statistics (e.g., index cardinality, approximate intersection size) and data placement (which nodes hold the data and their transfer costs).
    *   Handles relational operations (represented as a dependency tree) and selects access methods.
    *   Generates the **execution plan** (or **query plan**), which is the sequence of operations required to complete the query. The optimizer selects the most efficient plan from the available options.
4.  **Execution Engine**:
    *   Executes the selected plan.
    *   Collects results from local and remote operations. Remote execution involves reading/writing data to other cluster nodes and handling replication.
5.  **Storage Engine**:
    *   Executes local queries. It manages the physical storage, indexing, and transactional guarantees on disk.

> ### 🚶‍♂️ Step-by-Step Breakdown: The Journey of a SQL Query
> Let's trace what happens when you run `SELECT name FROM users WHERE id = 42;`
> 1. **Step 1: Arrival (Transport Subsystem)**: Your application sends the SQL text over the network. The transport layer receives the raw bytes and hands them to the Query Processor.
> 2. **Step 2: Parsing & Checking (Query Processor)**: The database parses the text to ensure it's valid SQL syntax (e.g., checking that you didn't write `SELEKT`). It also checks if you actually have permission to read the `users` table.
> 3. **Step 3: Planning & Optimization (Query Optimizer)**: The database figures out the fastest way to get the data. It asks: *"Should I scan the entire table of 1 million users, or should I use the 'id' index to jump straight to row 42?"* It decides that using the index is much faster and generates a step-by-step recipe called an **Execution Plan**.
> 4. **Step 4: Driving the Plan (Execution Engine)**: The engine reads the recipe. It sees: *"Step 1: Ask the storage engine to look up key 42 in the B-Tree index."*
> 5. **Step 5: Retrieving the Bytes (Storage Engine)**: The storage engine goes to the physical disk (or memory cache), locates the exact block of bytes containing the record for user 42, reads the name, and hands it back up.
> 6. **Step 6: Return**: The Execution Engine packages the name and sends it back to the Transport layer, which sends it across the network to your app.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//c51a439e-41d9-41f1-9c12-e838570d1dad/markdown_4/imgs/img_in_image_box_131_87_1022_1566.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A58Z%2F-1%2F%2F4d70d03dc1d153fd4c44968b2af0e452d36d3d2fdd411179864cb144a1109154" alt="Image" width="74%" /></div>

### Storage Engine Subcomponents

The storage engine consists of several dedicated components:

*   **Transaction Manager**: Schedules transactions and guarantees that they do not leave the database in a logically inconsistent state.
*   **Lock Manager**: Controls locks on database objects for running transactions, ensuring concurrent operations do not violate physical data integrity.
*   **Access Methods (Storage Structures)**: Manage how data is organized and accessed on disk. These include heap files, **B-Trees**, and **LSM Trees**.
*   **Buffer Manager**: Caches data pages in memory to reduce disk I/O.
*   **Recovery Manager**: Maintains the operation log (write-ahead log) and restores the system state after a crash or failure.

> **Note**: Together, the **Transaction Manager** and **Lock Manager** handle **concurrency control**. They guarantee both logical and physical data integrity while keeping concurrent execution highly efficient.

> ### 💡 Beginner's Corner: Storage Subcomponents
> * **Transaction Manager & Lock Manager**: These manage concurrent operations. The **Lock Manager** prevents two operations from modifying the same record at the same time by making one wait until the other finishes. The **Transaction Manager** guarantees that all changes within a transaction are applied completely, or rolled back entirely if a failure occurs, preventing half-completed states.
> * **Buffer Manager**: Coordinates the transfer of data pages between memory (RAM) and persistent storage (disk). It caches frequently accessed pages in RAM to minimize slow disk I/O operations.
> * **Recovery Manager**: Ensures the database remains durable across crashes. It writes a sequential log of all modifications to disk before they are applied to the database files. On system reboot after a crash, it reads this log to restore the database to a consistent state.

---

## Memory- Versus Disk-Based DBMS

Database systems store data in memory and on disk:
*   **In-Memory DBMS (Main Memory DBMS)**: Store data primarily in **RAM** and use the disk only for recovery, logging, and backups.
*   **Disk-Based DBMS**: Hold most of the data on **disk** and use RAM for caching disk contents or as a temporary storage.

Both types of systems use the disk to some extent, but main memory databases store their contents almost exclusively in RAM.

### Architectural Comparison: Memory- vs. Disk-Based DBMS

| Feature | In-Memory (Main Memory) DBMS | Disk-Based DBMS |
| :--- | :--- | :--- |
| **Primary Storage** | **RAM** (almost exclusively) | **Persistent Disk** (SSD / HDD) |
| **Disk Usage** | Only for logging, recovery, and backups | Primary data storage, using RAM for caching |
| **Performance** | Extremely fast (memory access is much faster than disk) $ ^{1} | Slower (limited by disk I/O and latency) |
| **Data Structures** | Uses pointers directly; optimized for random memory access | Uses specialized structures (e.g., wide, short trees) optimized for block storage |
| **Programming Complexity** | **Simpler**: OS abstracts memory; allocates/frees arbitrary chunks | **Higher**: Must manually manage file references, serialization, and fragmentation |
| **Key Constraints** | **RAM Volatility** (data loss risk) and **High Cost** | Disk latency, but highly durable and cheap |

> ### 💡 Beginner's Corner: RAM vs. Disk
> * **Implicit Assumption**: Why are they so different?
>   * **RAM (Random Access Memory)** is **volatile**, meaning it requires electricity to hold data. When you turn off your computer, RAM goes completely blank. However, it is incredibly fast (nanosecond latencies).
>   * **Disk (SSD/HDD)** is **non-volatile**, meaning it retains data even without power. However, it is much slower (microseconds for SSD, milliseconds for HDD) because it involves physical electronics or spinning disks.
> * **Data Structure Design**: Because disk reads are slow, disk-based databases cannot just follow random pointers (which would require jumping to random parts of the disk). Instead, they must read data in large, contiguous blocks (typically 4KB or 8KB **Pages**). This requires completely different, highly specialized algorithms compared to in-memory databases.

### Durability in Memory-Based Stores

Because RAM is **volatile** (temporary), main memory databases use persistent backups and logs to prevent data loss:

1.  **Write-Ahead Log (WAL)**: Before a write operation is complete, its results must be written to a sequential log file on disk.
2.  **Checkpointing**: To avoid reading the entire log during startup, in-memory stores maintain a sorted disk-based backup copy. The system periodically applies log records to this backup in batches (decoupled from client requests).
3.  **Discarding Logs**: After a batch of log records is processed, the backup holds a database snapshot for a specific point in time, and log contents up to this point can be discarded. This reduces recovery times without forcing clients to block.

> ### 💡 Beginner's Corner: Write-Ahead Logging (WAL)
> * **The Problem**: Writing sorted, structured data directly to its final place in database files on disk is slow because it requires random I/O (seeking and updating different file blocks). If the database waits for this to finish before confirming a write, performance degrades. But if it only keeps changes in volatile RAM, a crash will cause data loss.
> * **The Solution**: When a write transaction occurs, the database immediately appends the change to a sequential log file on disk (the **Write-Ahead Log**). Appending to the end of a single file is extremely fast because it uses **sequential I/O** (no disk seeking required). Once this log is flushed to disk, the transaction is safe. The database can then update its complex, sorted data structures in memory and write them to the primary database files later in background batches. If the system crashes, the database replays this sequential log on reboot to reconstruct its state.

> **Future Outlook**: **Non-Volatile Memory (NVM)** technologies are closing the gap. NVM storage reduces or completely removes the difference between read and write latencies, improves performance, and allows byte-addressable access.

### Key Architectural Differences

*   **Cache vs. In-Memory**: It is not accurate to say that an in-memory database is the equivalent of a disk-based database with a huge page cache. Disk-based databases carry serialization and page-layout overheads that prevent them from matching the optimizations of pure in-memory designs.
*   **Access Granularity**: In memory, following pointers is fast, allowing a wider variety of complex data structures. On disk, data must be accessed in blocks, forcing the use of block-optimized structures like B-Trees. Variable-sized data in memory is easily managed with pointers, whereas on disk it requires complex layout schemes.

---

## Column- Versus Row-Oriented DBMS

Most databases store tables consisting of columns and rows:
*   **Field**: The intersection of a column and a row, representing a single value. Fields in the same column share the same data type.
*   **Row**: A collection of values that logically belong to the same record, usually identified by a unique key.

Databases are classified by their physical layout on disk:
*   **Row-Oriented (Horizontal Partitioning)**: Stores all values belonging to the same row together.
*   **Column-Oriented (Vertical Partitioning)**: Stores all values belonging to the same column together.

> ### 💡 Beginner's Corner: Physical Layout on Disk
> * **Row-Oriented**: The database stores all column values of a single record contiguously on disk. For example, a single block on disk contains: `[ID 1, John, 30, 555-111]`.
>   * **Best For**: Transactional workloads (OLTP) where you frequently read or write an entire record (e.g., retrieving a user profile).
> * **Column-Oriented**: The database stores all values of a single column contiguously on disk, separate from other columns. For example, one block contains the names `[John, Alice, Bob]`, another block contains the ages `[30, 25, 40]`.
>   * **Best For**: Analytical workloads (OLAP) where you query specific columns across millions of rows (e.g., calculating the average age of all users). The database only needs to read the blocks containing ages, skipping all names and phone numbers, which drastically reduces disk I/O.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//793d4e45-2762-467a-8b37-f53fe47ddea0/markdown_1/imgs/img_in_image_box_139_806_1050_1008.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A57Z%2F-1%2F%2Ffaf7a078a52c1c480e6fad25cdd4754c0ae8ab853c9060303ed22ddc1aa1f819" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 1-2. Data layout in column- and row-oriented stores</div>

### Row-Oriented Data Layout

*   **Examples**: `MySQL`, `PostgreSQL`, and most traditional relational databases.
*   **Layout**: Stores entire records together. For example:

| ID | Name | Birth Date | Phone Number |
|---|---|---|---|
| 10 | John | 01 Aug 1981 | +1 111 222 333 |
| 20 | Sam | 14 Sep 1988 | +1 555 888 999 |
| 30 | Keith | 07 Jan 1984 | +1 333 444 555 |

*   **Best Use Case**: Highly effective when entire records must be accessed or written together (e.g., OLTP workloads like user registration or point lookups).
*   **Trade-offs**:
    *   **Pros**: Excellent **spatial locality** $ ^{2} $ for row-based access. Since disks are read in blocks, a single block read loads the entire record.
    *   **Cons**: Queries that only need a single column (e.g., retrieving only phone numbers) are slower and more expensive because the system must read and discard all other columns in the block.

### Column-Oriented Data Layout

*   **Examples**: `MonetDB`, `C-Store` (the predecessor to `Vertica`), `Apache Parquet`, `Apache ORC`, `ClickHouse`.
*   **Layout**: Partitions data vertically. Values for the same column are stored contiguously on disk.
*   **Best Use Case**: Ideal for analytical workloads (**OLAP**) that compute aggregates (e.g., averages, trends) over millions of rows but only look at a few columns.

#### Logical vs. Physical Columnar Layout

**Logical View**:
| ID | Symbol | Date | Price |
|---|---|---|---|
| 1 | DOW | 08 Aug 2018 | 24,314.65 |
| 2 | DOW | 09 Aug 2018 | 24,136.16 |
| 3 | S&P | 08 Aug 2018 | 2,414.45 |
| 4 | S&P | 09 Aug 2018 | 2,232.32 |

**Physical Layout on Disk**:
*   `Symbol`: `1:DOW; 2:DOW; 3:S&P; 4:S&P`
*   `Date`: `1:08 Aug 2018; 2:09 Aug 2018; 3:08 Aug 2018; 4:09 Aug 2018`
*   `Price`: `1:24,314.65; 2:24,136.16; 3:2,414.45; 4:2,232.32`

> **Note**: To reconstruct rows (tuples) for operations like joins or filtering, the system must map values across columns. To avoid the massive duplication of storing row keys with every value, column stores use **implicit identifiers (virtual IDs)** based on the position (offset) of the value in the file.

### Columnar Optimizations

Column stores go beyond simple physical layout adjustments by leveraging two key CPU and storage optimizations:

1.  **Vectorized Processing**: Reading contiguous values of the same type improves CPU cache use. Modern CPUs can use **vectorized instructions (SIMD)** to process multiple data points with a single CPU instruction $ ^{3} $.
2.  **High Compression Ratios**: Storing identical data types contiguously (e.g., numbers with numbers, strings with strings) allows the database to achieve much better compression. The database can apply different compression algorithms optimized for specific data types.

> ### 💡 Beginner's Corner: Vectorized Processing & Compression
> * **Vectorized Processing (SIMD)**: Normal CPUs process one item at a time (e.g., *"add A to B"*). **Single Instruction Multiple Data (SIMD)** allows a CPU to load a whole batch of numbers and perform an operation on all of them simultaneously (e.g., *"add this array of 8 ages to that array of 8 ages"*). Because column stores pack numbers of the same type next to each other, the CPU can use SIMD to perform calculations extremely fast.
> * **Compression**: Compression works by finding patterns. In a column of ages, you might see: `[25, 25, 25, 26, 26]`. We can compress this to `"three 25s, two 26s"`. In a row-oriented store, the data looks like: `[John, 25, 555-111, Alice, 25, 555-222]`. There is almost no pattern, so compression ratios are much worse.

#### Decision Rule: Row vs. Column Store
*   Use a **Row-Oriented Store** if:
    *   Workloads consist of point queries and narrow range scans.
    *   Queries read or write complete records (most or all columns at once).
*   Use a **Column-Oriented Store** if:
    *   Workloads consist of large scans spanning millions of rows.
    *   Queries compute aggregates (e.g., sum, average) over a small subset of columns.

### Wide Column Stores

> **Crucial Distinction**: Do not confuse **column-oriented databases** with **wide column stores** (e.g., `Bigtable`, `HBase`). 
> *   In a wide column store, data is represented as a **multidimensional sorted map**.
> *   Columns are grouped into **column families** (which are stored separately on disk).
> *   Inside each column family, the data is stored **row-wise** (keys and values are stored together).

> ### 💡 Beginner's Corner: The Wide Column Store Misconception
> * **Common Misconception**: Beginners often think *"Wide Column Stores"* are column-oriented. They are **not**!
> * **The Reality**: Wide Column Stores are actually **Row-Oriented** databases in disguise, but with a twist. Think of them as a massive two-level map. The outer level splits the table into "Column Families" (like `profile` and `activity`). The database stores each family in a separate file. But *inside* that file, the data is stored row-by-row.
> * **Why do this?** It gives you a middle ground. If you rarely query the user's `activity` but frequently query their `profile`, splitting them into two column families prevents the database from reading massive activity logs during simple profile lookups.

#### Conceptual View of a Wide Column Store (Webtable Example)
A Webtable stores web page snapshots, their attributes, and their link relationships at specific timestamps. It can be conceptually viewed as a nested map:

```json
{
    "com.cnn.www": {
        "contents": {
            "t6": {"html": "<html>..."},
            "t5": {"html": "<html>..."},
            "t3": {"html": "<html>..."}
        },
        "anchor": {
            "t9": {"cnnsi.com": "CNN"},
            "t8": {"my.look.ca": "CNN.com"}
        }
    },
    "com.example.www": {
        "contents": {
            "t5": {"html": "<html>..."}
        },
        "anchor": {}
    }
}
```

*   **Row Key**: The reversed URL (e.g., `com.cnn.www`), which indexes each row.
*   **Column Families**: Grouped columns (e.g., `contents` and `anchor`) stored separately on disk.
*   **Column Key**: A combination of the column family and a qualifier (e.g., `contents:html`, `anchor:cnnsi.com`).
*   **Version Control**: Column families store multiple versions of data, versioned by **timestamps** (e.g., `t3`, `t5`).

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
*   **Storage Efficiency**: Formats are designed to minimize storage overhead for every record.
*   **Access Efficiency**: Data structures are optimized so records can be found in the fewest possible disk operations.
*   **Update Efficiency**: Updates are written in ways that minimize the physical changes required on disk.

> ### 💡 Beginner's Corner: Why not just use CSV or JSON?
> * **The Problem**: A CSV or JSON file is stored as plain text. If you want to find row number 500,000, the operating system has to scan through the entire file character-by-character from the beginning to count the newline characters (this is $ O(N) $ time). Also, if you want to update user 5's name from "Bob" to "Robert", you have to push all subsequent bytes in the file forward, which requires rewriting the entire file.
> * **The Solution**: Databases use binary, block-structured formats. They divide the file into fixed-size blocks (pages). They store offset tables at the start of each page, allowing them to jump directly to any record in $ O(1) $ time. They also leave empty space inside pages to allow records to grow without shifting the rest of the file.

### File and Index Organization
*   **Data Files**: Store the actual data records. Each table is usually stored in its own file.
*   **Index Files**: Store record metadata to help locate records in the data files without performing slow, full-table scans. Index files are much smaller than data files.
*   **Pages**: Files are split into fixed-size **pages** (usually matching the size of one or more disk blocks). Pages can be organized as simple record sequences or as **slotted pages**.
*   **Tombstones (Deletion Markers)**: Modern storage systems rarely delete data from pages immediately. Instead, they write a **tombstone** (deletion marker) containing the key and a timestamp.
*   **Garbage Collection (Compaction)**: Space occupied by old (shadowed) records or deleted records is reclaimed during garbage collection. This process reads the active pages, copies live records to a new location, and discards the old ones.

> ### 💡 Beginner's Corner: The Index Analogy
> * **Mental Model**: Think of the **Data File** as a massive **textbook** of 1,000 pages.
>   * If you want to find where the book discusses "Write-Ahead Logging", and you don't have an index, you have to read the book page-by-page from the start (a **Full Table Scan**).
>   * The **Index File** is the alphabetical index at the very back of the book. It is much smaller (only 5 pages) and contains alphabetical terms with page numbers: `Write-Ahead Logging -> page 104`. 
>   * You quickly scan the tiny index, find `page 104`, and immediately jump to page 104 in the textbook. This requires only two steps, regardless of how large the textbook is!

### Data Files

Data files (sometimes called primary files) can be organized in three primary ways:

1.  **Heap-Organized Tables (Heap Files)**:
    *   Records are placed in no particular order, usually in the order they were written.
    *   New writes require no reorganization; they are simply appended.
    *   **Requires a separate index** containing pointers to the records to make them searchable.
2.  **Hash-Organized Tables (Hashed Files)**:
    *   Records are grouped into **buckets** based on the hash value of their key.
    *   Inside each bucket, records are stored either in append order or sorted by key for faster lookups.
3.  **Index-Organized Tables (IOTs)**:
    *   Data records are stored directly inside the index itself, sorted by key.
    *   Traversing the index locates both the key and the actual record, saving at least one disk seek.
    *   Range scans are highly efficient because the data is already stored sequentially in key order.

#### Locating Records on Disk
*   If data is in a **separate file**: The index stores **data entries** containing the primary key and a pointer to the record (such as a **file offset/row locator** or a bucket ID).
*   If data is in an **Index-Organized Table**: The index entries store the actual data records directly.

### Index Files

An **index** maps search keys to their physical locations in data files.

*   **Primary Index**: Built on the table's primary key. It typically holds unique entries (one per search key).
*   **Secondary Index**: Built on other columns to allow query filtering by non-primary attributes. A secondary index can contain multiple entries per search key. It can point:
    *   Directly to the data record using a file offset.
    *   Indirectly by storing the record's primary key.

#### Clustered vs. Nonclustered Indexes
*   **Clustered Index**: The physical order of the records in the data file matches the logical order of the index keys. A table can have only one clustered index (and is clustered by definition in index-organized tables).
*   **Nonclustered Index**: The physical order of the records on disk does not match the index key order. The index contains pointers (offsets) to the records stored out-of-order in a separate data file.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e3a5f91f-ca5f-485b-b6b9-2b8fd335444a/markdown_3/imgs/img_in_image_box_147_143_581_346.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F5504089ab49d3b61994e018cd3b1e7d2bd673862ce26dc3eb1d6d392093462af" alt="Image" width="36%" /></div>
<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//e3a5f91f-ca5f-485b-b6b9-2b8fd335444a/markdown_3/imgs/img_in_image_box_610_145_1044_364.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F54abc891db024e2999b77776c8cfcb8d2e029f1b1db183d65a43eed8ea4ed088" alt="Image" width="36%" /></div>
<div style="text-align: center;">Figure 1-5. Storing data records in an index file versus storing offsets to the data file (index segments shown in white; segments holding data records shown in gray)</div>

> **Note**: Primary keys uniquely identify records. If a table is created without a primary key, the storage engine often generates an **implicit primary key** automatically (e.g., `MySQL InnoDB` adds an internal auto-increment column).

### Primary Index as an Indirection

When secondary indexes need to locate a data record, databases choose between two primary reference models:

#### 1. Direct Reference (File Offsets)
*   The secondary index stores the direct physical file offset (row locator) of the record.
*   **Pros**: Fast reads; saves disk seeks because the database immediately goes to the file offset.
*   **Cons**: Expensive writes and maintenance; if a record is updated, moved, or rescheduled during compaction, the database must update all secondary indexes pointing to it.

#### 2. Indirect Reference (Primary Key Indirection)
*   The secondary index stores the record's primary key instead of its physical offset. Finding the record requires a two-step lookup: first in the secondary index, then in the primary index.
*   **Pros**: Cheaper writes; moving or updating a record only requires updating the primary index pointer. Secondary indexes remain unchanged.
*   **Cons**: Slower reads; every query using a secondary index must perform an extra primary index lookup (e.g., `MySQL InnoDB`).

| Reference Strategy | Read Path Cost | Write Path Cost (On Record Move) | Secondary Index Size |
| :--- | :--- | :--- | :--- |
| **Direct (File Offset)** | **Low** (1 hop) | **High** (Must update all indexes) | Small (integer offset) |
| **Indirect (Primary Key)** | **High** (2 hops) | **Low** (Only update primary index) | Larger (stores primary key) |

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fea32fbb-8229-4916-b6f8-bb95eed68416/markdown_0/imgs/img_in_image_box_139_161_561_493.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A57Z%2F-1%2F%2F35b3229e7773d004e16d081924780b946e234cbfd3ffdbe7eecdd41318c73d84" alt="Image" width="35%" /></div>
<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//fea32fbb-8229-4916-b6f8-bb95eed68416/markdown_0/imgs/img_in_image_box_621_163_1046_510.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A57Z%2F-1%2F%2F699f84ad6a861c55d2a2b2d37dbf9b34930f6778a88704564a3d777d36e632b2" alt="Image" width="35%" /></div>
<div style="text-align: center;">Figure 1-6. Referencing data tuples directly (a) versus using a primary index as indirection (b)</div>

> ### 💡 Beginner's Corner: Direct vs. Indirect References
> * **Direct Reference (Mental Model)**: Think of it like booking a **hotel room**. The front desk gives you a card key with the exact room number: `Room 304`. You walk directly to Room 304. However, if the hotel decides to move you to a different room, they have to physically find you and update all your friends who have your room number written down.
> * **Indirect Reference (Mental Model)**: The front desk tells your friends: *"He is registered under the name John Doe."* Your friends must first ask the front desk: *"What room is John Doe in?"*, get the room number, and then go there (a two-step lookup). If the hotel moves you to Room 502, the front desk updates their central computer. Your friends still ask for *"John Doe"* and get the new room number automatically. None of your friends' address books need to be updated!

> **Hybrid Approach**: Some systems store both the physical file offset and the primary key. The database first attempts to read directly using the offset. If the offset is invalid (the record moved), it falls back to a primary key lookup and updates the secondary index with the new offset.

---

## Buffering, Immutability, and Ordering

While storage engines are built on top of core data structures, they must implement caching, crash recovery, transactions, and durability. To optimize these, storage structures tune three primary variables:

### 1. Buffering
*   **Definition**: Whether the storage structure collects writes in memory before flushing them to disk.
*   **Purpose**: Amortizes disk I/O costs. While all engines buffer to write full blocks, some implement custom buffering layers.
*   **Examples**: Adding in-memory buffers to **B-Tree** nodes (**Lazy B-Trees**) or buffering all writes in memory before flushing sorted runs to disk (**LSM Trees**).

### 2. Mutability vs. Immutability
*   **Mutable (In-Place Updates)**: The engine reads a page, updates its content in memory, and writes it back to the exact same physical location on disk (e.g., standard B-Trees).
*   **Immutable (Append-Only)**: Once written, data files are never modified.
*   **Append-Only**: All new inserts, updates, and deletes are appended to the end of the file (e.g., **LSM Trees**, `Bitcask`).
*   **Copy-on-Write (CoW)**: When a page is modified, the updated page is written to a completely new physical location rather than overwriting the original.
*   **Hybrid**: Structures like **Bw-Trees** combine B-Tree logic with an immutable, log-structured layout.

### 3. Ordering
*   **Ordered**: Records are stored on disk sorted by their keys, ensuring keys that sort closely are placed contiguously.
    *   **Pros**: Highly efficient range scans and sorted sequential reads.
*   **Unordered**: Records are stored out of key order, typically in the order they were inserted.
    *   **Pros**: Highly optimized, high-throughput write paths (e.g., `Bitcask`, `WiscKey` append-only files).
    *   **Cons**: Range scans require sorting or random lookups, making them slow.

> ### 💡 Beginner's Corner: The 3 Core Variables
> * **Buffering**: Instead of saving every letter you type one-by-one to disk, you type them into a memory buffer and hit "Save" to write a whole paragraph at once.
> * **Mutability (In-Place)** vs. **Immutability (Append-Only)**:
>   * **Mutable**: You have a physical paper form with boxes. When someone's address changes, you erase the old address with an eraser and write the new one in the same box.
>   * **Immutable**: You have a notebook. You never erase anything. When an address changes, you turn to the next blank page at the end and write: *"Update: John's new address is X"*. Later, to find John's address, you read the notebook from the back to find the most recent entry.
> * **Ordering**:
>   * **Ordered**: A phone book sorted alphabetically. Finding "Smith" is incredibly fast, and finding all names starting with "S" is easy because they are right next to each other.
>   * **Unordered**: A list of phone numbers in the order people signed up. Writing a new number is instant (just add it to the bottom), but finding "Smith" requires reading the entire list from start to finish.

---

## Summary

In this chapter, we’ve discussed the architecture of a **DBMS** and covered its primary components.
*   To highlight the importance of disk-based structures and their difference from in-memory ones, we discussed memory- and disk-based stores, coming to the conclusion that disk-based structures are important for both types of stores, but are used for different purposes.
*   To understand how access patterns influence database system design, we discussed column- and row-oriented database management systems and the primary factors that set them apart.
*   To start a conversation about how the data is stored, we covered data and index files.
*   Lastly, we introduced three core concepts: **buffering**, **immutability**, and **ordering**. We will use them throughout this book to highlight properties of the storage engines that use them.

---

### Further Reading

If you’d like to learn more about the concepts mentioned in this chapter, you can refer to the following sources:

*   **Database Architecture**:
    *   Hellerstein, Joseph M., Michael Stonebraker, and James Hamilton. 2007. "Architecture of a Database System." Foundations and Trends in Databases 1, no. 2 (February): 141-259. https://doi.org/10.1561/1900000002.
*   **Column-oriented DBMS**:
    *   Abadi, Daniel, Peter Boncz, Stavros Harizopoulos, Stratos Idreaos, and Samuel Madden. 2013. *The Design and Implementation of Modern Column-Oriented Database Systems*. Hanover, MA: Now Publishers Inc.
*   **In-memory DBMS**:
    *   Faerber, Frans, Alfons Kemper, and Per-Åke Alfons. 2017. *Main Memory Database Systems*. Hanover, MA: Now Publishers Inc.

---

### Footnotes

*   $^1$ Accessing memory is several orders of magnitude faster than accessing disk.
*   $^2$ Storing entire rows together improves **spatial locality** (keeping related data close together).
*   $^3$ **Vectorized instructions**, or **Single Instruction Multiple Data (SIMD)**, describes a class of CPU instructions that perform the same operation on multiple data points.
*   $^4$ The original post that has stirred up the discussion was controversial and one-sided, but you can refer to the presentation comparing MySQL and PostgreSQL index and storage formats, which references the original source as well.
