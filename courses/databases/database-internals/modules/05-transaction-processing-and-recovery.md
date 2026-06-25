# Module 05: Transaction Processing and Recovery

We take a bottom-up approach to database system concepts: we first learned about storage structures. Now, we are ready to move to the higher-level components responsible for **buffer management**, **lock management**, and **recovery**, which are the requirements for understanding database transactions.

## Understanding Transactions (ACID)

A **transaction** is a single, unbreakable logical unit of work in a database management system, allowing you to run multiple operations as a single step. Operations executed by transactions include reading and writing database records. 

A database transaction must maintain four key properties, commonly referred to as **ACID**:

*   **Atomicity**: Transaction steps are unbreakable. Either all steps associated with the transaction execute successfully, or none of them do. Transactions are never applied partially. A transaction can either **commit** (making all written changes visible) or **abort** (rolling back all side effects). Commit is a final operation; after an abort, the transaction can be retried.
*   **Consistency**: An application-specific guarantee. A transaction must only bring the database from one valid state to another, maintaining all database invariants (such as unique constraints and referential integrity). 
*   **Isolation**: Multiple concurrently executing transactions must run without interference, as if each were the only transaction running. Isolation defines when and how changes to the database state become visible to other concurrent transactions. 
*   **Durability**: Once a transaction commits, all its database modifications must be permanently written to disk. These changes must survive power outages, system failures, and crashes.

### Local Node Transaction Subsystems
To implement transactions, several components on a single database node must work together:
*   **Transaction Manager**: Coordinates, schedules, and tracks transactions and their individual execution steps.
*   **Lock Manager**: Controls access to database resources and prevents concurrent operations that would violate data integrity. If a transaction requests a lock, the lock manager checks if another transaction holds a conflicting lock. Since exclusive locks are held by at most one transaction, others must wait until the lock is released or abort and retry.
*   **Page Cache (Buffer Pool)**: Acts as an intermediary between persistent storage (disk) and the storage engine. It stages state changes in RAM and caches recently read pages. All database state changes are first applied to cached pages in memory.
*   **Log Manager**: Maintains a sequential history of operations (log entries) applied to cached pages but not yet written to disk, ensuring they are not lost in a crash. The log is used to reapply operations during startup (recovery) or to undo changes from aborted transactions.

> **Note**: Distributed (multi-partition) transactions require additional coordination and remote execution protocols, which we discuss in **Module 13**.

---

## Buffer Management

To bridge the speed gap between slower persistent storage (disk) and faster main memory (RAM), databases cache pages in memory. When the storage layer requests a page, the page cache returns its cached copy if available, avoiding a slow disk read.

> **Terminology**: This caching layer is referred to as the **page cache** or **buffer pool**. Historically, Rudolf Bayer referred to this approach as a **virtual disk** because physical disk reads are bypassed if a copy of the page is already in RAM. 

*   **Page-In**: Loading an uncached page from disk into memory.
*   **Dirty Page**: A cached page in memory that has been modified but has not yet been written (flushed) back to disk.
*   **Eviction**: When the page cache is full, it must choose an existing page to remove (evict) to make room for a new page. If the evicted page is dirty, it must be flushed to disk first.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//98e4579a-c8b9-48e2-91da-370fbd713fd8/markdown_0/imgs/img_in_image_box_155_133_1030_449.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F3a1047fbfbccca8c8470ca5166c2e8495eb905afb317bdd220be2a0a40d6d1fb" alt="Image" width="73%" /></div>
<div style="text-align: center;">Figure 5-1. Page cache mapping (out-of-order loading)</div>

### Primary Functions of a Page Cache
*   Keeps recently accessed page contents in RAM.
*   Allows multiple updates to the same page to be buffered together in memory.
*   Fetches requested pages from disk if they are not present in RAM (paging in).
*   Evicts pages and flushes dirty contents to disk when the cache reaches capacity.

> ### Bypassing the Kernel Page Cache
> Many databases open files using the `O_DIRECT` flag. This flag bypasses the operating system's kernel page cache, allowing the database to access the disk directly and manage its own buffers. 
> 
> *   **Criticism**: Bypassing the kernel removes automatic OS features like asynchronous read-ahead.
> *   **Justification**: Database engines understand their own access patterns (e.g., B-Tree traversals, sequential scans) much better than a general-purpose OS kernel can. Using custom buffer pools gives the database precise control over page eviction and flushing, which is critical for transactional correctness.

### Caching Semantics

Because the database has exclusive control over the data file, synchronization is a one-way process: from memory to disk. The page cache decouples logical write operations (updating a record in memory) from physical write operations (writing pages to disk).

When a page is requested:
1.  The engine checks if the page is already in the cache. If so, it returns the cached version.
2.  If not, the cache translates the logical page number to a physical file offset, reads the page from disk into a cache slot, and returns it.
3.  Once returned, the page is said to be **referenced** (or pinned in memory). The storage engine must release or dereference the page when it is done.
4.  If a page is modified, it is marked as **dirty**, signaling that it must be flushed to disk to guarantee durability.

### Cache Eviction

Because cache capacity is limited, clean, unreferenced pages are evicted directly to free up slots. Dirty pages must be flushed to disk before eviction, and currently referenced pages cannot be evicted.

To balance performance and durability, databases manage several conflicting objectives:
*   Delay flushes to buffer multiple writes together, reducing disk I/O.
*   Preemptively flush dirty pages in the background so that slots can be evicted quickly when needed.
*   Select the optimal order in which to evict and flush pages.
*   Keep the total cache size within memory limits.
*   Prevent data loss by coordinating flushes with the write-ahead log.

> **Background Writers**: To avoid blocking queries during eviction, some databases run a background process (e.g., `PostgreSQL`'s background writer) that continuously cycles through dirty pages and flushes them to disk in the background.

### Locking Pages in Cache (Pinning)

Because a B-Tree narrows toward the top, the root node and upper-level internal nodes are accessed by almost every query. Locking these highly accessed pages in memory is called **pinning**. 

*   **Benefit**: Pinning the root and upper levels permanently in RAM reduces the number of disk accesses for a query from $h$ (the tree height) to just 1 or 2 reads at the un-cached leaf level.
*   **Write Buffering**: Structural changes (splits/merges) in a subtree can also be buffered in memory, allowing conflicting operations (such as a delete merge followed immediately by an insert split) to cancel each other out before writing to disk.

> **Prefetching & Immediate Eviction**: The database can optimize cache use by pre-loading pages before they are accessed (e.g., loading the next leaf page during a sequential range scan) or immediately evicting pages used for one-off maintenance tasks that are unlikely to be accessed again.

### Page Replacement Policies

When the cache is full, the **eviction policy** (or **page-replacement policy**) decides which page to remove. A poor policy results in pages being evicted and immediately paged back in, causing high I/O overhead.

> **Bélády's Anomaly**: Increasing cache size can actually *increase* the number of page evictions if the page-replacement algorithm is not optimal (e.g., FIFO). Pages start competing for space, degrading performance.

#### 1. First-In, First-Out (FIFO)
*   Maintains a queue of pages in the order they were loaded. The oldest page is evicted first.
*   **Drawback**: Highly impractical. The root and upper B-Tree pages are loaded first, so FIFO makes them the first candidates for eviction, even though they are accessed constantly.

#### 2. Least-Recently Used (LRU)
*   Maintains a queue of pages, but moves a page back to the tail (making it "new" again) whenever it is accessed.
*   **Drawback**: Relinking queue nodes on every single read is highly expensive due to thread lock contention in concurrent environments.
*   **Variants**:
    *   **2Q (Two-Queue)**: Uses two queues. New pages enter a tentative queue; if they are accessed a second time, they are promoted to a "hot" queue, separating recently accessed pages from frequently accessed ones.
    *   **LRU-K**: Tracks the timestamps of the last $K$ accesses to estimate the inter-arrival time of page requests, improving eviction accuracy.

#### 3. CLOCK Sweep
A compact, concurrent, and cache-friendly alternative to LRU that avoids queue relinking overhead.

##### The CLOCK Sweep Workflow:
1.  Pages are organized in a circular buffer (representing the face of a clock) with a moving "clock hand" pointer.
2.  Each page has an **access bit** (set to `1` when the page is read or written).
3.  When eviction is triggered, the clock hand sweeps the buffer:
    *   If the access bit is `1` and the page is unreferenced, the hand clears the bit to `0` and moves to the next page.
    *   If the access bit is `0`, the page is selected as an eviction candidate.
    *   If a page is currently in use (referenced), it is skipped.
4.  Because the hand and bits can be updated using atomic **compare-and-swap (CAS)** instructions, the CLOCK algorithm avoids heavy lock synchronization.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b074479c-7ec1-4175-9efa-312297c94f61/markdown_3/imgs/img_in_image_box_141_138_1052_1040.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A00Z%2F-1%2F%2F5a4ef4d0c9273542f2acd0889309279696f8b0269bf28249a60e6de88885fa7e" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 5-2. CLOCK-sweep circular buffer</div>

#### 4. Least-Frequently Used (LFU) & TinyLFU
Under heavy database workloads, access recency (how recently a page was touched) is often a poor predictor of future use compared to frequency (how often it is touched).

*   **TinyLFU**: A frequency-based policy that orders pages by access frequency using a compact **frequency histogram** (to save memory).
*   **Queues**: TinyLFU manages three queues:
    *   **Admission**: Newly added elements managed by an LRU policy.
    *   **Probation**: Holds candidate pages most likely to be evicted.
    *   **Protected**: Holds hot elements retained for a long time.
*   **Promotion**: When an item is evicted from admission, it competes with the victim in probation. It is only admitted to probation if its access frequency is higher than the victim's. On subsequent hits, items move from probation to the protected queue.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//196065d1-b2ed-4fd9-a24d-48784ed68c97/markdown_0/imgs/img_in_image_box_139_162_1044_387.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A21%3A59Z%2F-1%2F%2F336dde93fc8ba08844aa01ec6ee89f479d791423b2d4c3e08051424db0c7d641" alt="Image" width="75%" /></div>
<div style="text-align: center;">Figure 5-3. TinyLFU queue layout</div>

---

## Recovery

Because hardware and software can fail, databases must ensure that committed data is safe and uncommitted data can be cleanly rolled back.

The **Write-Ahead Log (WAL)** (or **commit log**) is an append-only, disk-resident structure used for crash and transaction recovery. While the page cache buffers page modifications in RAM, the WAL serves as the durable record of these modifications on disk.

### Key Functions of a WAL
*   Allows the page cache to buffer updates in RAM while guaranteeing durability.
*   Persists all modifications sequentially on disk before the dirty page contents are allowed to be overwritten on disk.
*   Allows the database to reconstruct lost in-memory changes from the log after a crash.

### Log Semantics

The WAL is append-only, meaning its contents are immutable and all writes are sequential. The log writer appends records to the log tail, while readers can safely scan the log up to the latest flushed threshold.

*   **Log Sequence Number (LSN)**: Every log record has a unique, monotonically increasing LSN (usually a counter or timestamp).
*   **Log Buffer**: Log records are buffered in memory and flushed to disk in a **force** operation when the buffer fills, or when requested by the transaction manager. Log records must be written in LSN order.
*   **Commit Invariant**: A transaction is not considered committed until its commit log record has been successfully forced to disk.
*   **Compensation Log Records (CLRs)**: Used during rollbacks to log the undoing of an operation, ensuring the database can recover even if it crashes midway through a rollback.

> ### The PostgreSQL fsync() Dilemma
> Databases use the `fsync()` system call to force dirty OS kernel pages to disk. 
> *   **The Bug**: In Linux and other kernels, if `fsync()` fails due to an I/O error (e.g., a temporary disk disconnect), the kernel clears the dirty flag on those pages anyway. Subsequent `fsync()` calls on the same file descriptors might return success, even though the data was never written to disk.
> *   **The Risk**: If a database checkpointer closes and reopens file descriptors, it can miss these error notifications, assuming data is safe on disk when it is actually lost, leading to silent database corruption.
> *   **Takeaway**: Recovery systems must be designed with extra care, considering OS-level quirks and thoroughly testing edge-case hardware failures.

### Checkpoints

To prevent the WAL from growing indefinitely and to speed up crash recovery, the database uses **checkpoints**. A checkpoint tells the recovery manager that all log records prior to the checkpoint LSN have been successfully flushed to the primary data files, so those log segments can be safely deleted or recycled.

*   **Sync Checkpoint**: Pauses all transactions and forces all dirty pages to disk. This is simple but causes severe write-stalls and latency spikes in production.
*   **Fuzzy Checkpoint**: Runs asynchronously without pausing transactions:
    1.  Writes a `begin_checkpoint` record to the log.
    2.  Collects metadata about active transactions and dirty pages into an `end_checkpoint` record.
    3.  Flushes the listed dirty pages asynchronously.
    4.  Once all pages are flushed, the database updates its log header pointer to the LSN of `begin_checkpoint`. If a crash occurs, recovery starts from this LSN.

### Operation Versus Data Log

There are two main ways to record changes in a log:
*   **Physical Logging**: Records the exact state of the pages, saving before-images (pre-state) and after-images (post-state) of byte-level modifications. 
    *   *Pros*: Fast recovery during redo.
    *   *Cons*: Large log sizes since entire page states must be recorded.
*   **Logical Logging**: Records the logical operations to be performed (e.g., "Insert key Y into table X") and its corresponding inverse operation (e.g., "Delete key Y from table X").
    *   *Pros*: Compact log sizes.
    *   *Cons*: Slower recovery; requires pages to be in a highly specific state before applying.
*   **Physiological Logging**: A hybrid approach. It uses physical logging for redo operations (to speed up recovery) and logical logging for undo operations (to improve concurrency).

> **Shadow Paging**: An alternative to WAL-based recovery (used in historical engines like `System R`). It uses a copy-on-write technique: updates are written to a new "shadow" page on disk. The transaction commits atomically by flipping a parent pointer from the old page to the new shadow page.

### Steal and Force Policies

To coordinate how the page cache and recovery manager interact, databases define **steal/no-steal** and **force/no-force** policies:

*   **Steal Policy**: Allows the page cache to evict and flush a dirty page modified by an *uncommitted* transaction to make room for other pages. 
    *   *Requirement*: The WAL must contain **undo** information so that if the transaction aborts later, the uncommitted changes on disk can be rolled back.
*   **No-Steal Policy**: Prevents the page cache from flushing any page modified by an uncommitted transaction.
    *   *Benefit*: Simplifies recovery because disk pages never contain uncommitted data (no undo log is needed).
*   **Force Policy**: Requires all pages modified by a transaction to be flushed to disk *before* the transaction is allowed to commit.
    *   *Benefit*: Simplifies recovery because committed changes are guaranteed to be on disk (no redo log is needed).
    *   *Drawback*: High write latency due to blocking I/O during commit.
*   **No-Force Policy**: Allows a transaction to commit even if some of its modified pages are still dirty in RAM.
    *   *Requirement*: The WAL must contain **redo** information so that if the system crashes, committed changes can be replayed and restored.

#### Policy Trade-off Matrix

| Policy Configuration | Undo Info Needed? | Redo Info Needed? | Commit Latency | Memory Overhead |
| :--- | :---: | :---: | :--- | :--- |
| **Steal / Force** | **Yes** | **No** | High (forces page writes) | Low |
| **Steal / No-Force** | **Yes** | **Yes** | **Low** (only forces WAL writes) | High (buffers dirty pages) |
| **No-Steal / Force** | **No** | **No** | Very High | Very High (must keep all transaction pages in RAM) |
| **No-Steal / No-Force** | **No** | **Yes** | Moderate | Very High |

Modern high-performance databases almost universally use a **Steal / No-Force** configuration (e.g., ARIES) because it provides the lowest write latency by deferring heavy page flushes.

> ### 💡 Beginner's Corner: Buffer Pool Steal and Force Policies
> * **The Problem (Decoupling RAM and Disk)**: To maximize write performance, the database page cache buffers dirty pages in RAM. However, the database must coordinate when these dirty pages are physically written to disk to ensure durability and allow transaction aborts. This coordination is defined by two policies:
> * **Steal vs. No-Steal Policy (Managing Memory Capacity)**:
>   * **Steal**: The page cache is allowed to evict a dirty page modified by an *uncommitted* transaction and write it to disk to free up RAM for other pages.
>     * *Why it is used*: Prevents the database from running out of memory when transactions modify more pages than can fit in RAM.
>     * *Underlying Mechanism*: Because uncommitted data is written to disk, the database must write **Undo information** to the WAL *before* the page is flushed. If the transaction aborts, the database reads the Undo log to revert the uncommitted changes on disk.
>   * **No-Steal**: The page cache is forbidden from flushing dirty pages of uncommitted transactions to disk.
>     * *Why it is used*: Simplifies recovery because disk pages never contain uncommitted data, removing the need for Undo logs. However, it severely limits transaction sizes to the available RAM.
> * **Force vs. No-Force Policy (Managing Commit Latency)**:
>   * **Force**: Requires all pages modified by a transaction to be flushed to disk *before* the transaction is allowed to commit.
>     * *Why it is used*: Guarantees durability immediately on commit, removing the need for Redo logs during recovery.
>     * *Drawback*: Causes high commit latency because the transaction must block while performing slow, random disk writes for every modified page.
>   * **No-Force**: Allows a transaction to commit as soon as its changes are written to the sequential WAL, leaving the actual database pages dirty in RAM to be flushed later in background batches.
>     * *Why it is used*: Drastically reduces write latency by replacing slow random page writes with fast sequential log appends.
>     * *Underlying Mechanism*: Because committed changes may only exist in volatile RAM, the database must write **Redo information** to the WAL. If the system crashes, the database replays the Redo log on reboot to reconstruct those changes.
> * **Jargon Buster**:
>   * **Idempotency**: A property of an operation where executing it multiple times yields the exact same result as executing it once. In database recovery, log replay must be **idempotent** because if the system crashes midway through recovery, the subsequent reboot will replay the same log records again; replaying a record twice must not corrupt the state (e.g., re-applying an increment operation must not double-increment the value).

---

## ARIES Recovery Algorithm

**ARIES** (Algorithm for Recovery and Isolation Exploiting Semantics) is a state-of-the-art **steal/no-force** recovery algorithm. It uses physical redo for speed and logical undo to maximize concurrency during normal operations.

When the database restarts after a crash, ARIES executes three distinct recovery phases:

1.  **Analysis Phase**:
    *   Scans the WAL forward from the last checkpoint to identify all active transactions (which were in progress during the crash) and dirty pages in the cache.
    *   Identifies the oldest LSN in the **Dirty Page Table (DPT)** to set the starting point for the Redo phase.
2.  **Redo Phase (Repeating History)**:
    *   Replays all logged operations forward from the oldest dirty page LSN up to the point of the crash.
    *   This restores the database state exactly to its pre-crash condition, including uncommitted changes and committed changes that had not yet been flushed.
3.  **Undo Phase**:
    *   Walks backward through the WAL, rolling back all operations executed by active (uncommitted) transactions.
    *   Each undone operation is logged using a **Compensation Log Record (CLR)** to ensure that if the database crashes again during recovery, the system will not repeat the undo operation.

> ### 🚶‍♂️ Step-by-Step Breakdown: The ARIES Recovery Protocol
> When the database restarts after a crash under a Steal/No-Force policy, ARIES executes three sequential phases to restore consistency:
> 1. **Step 1: The Analysis Phase**: 
>    * **Goal**: Reconstruct the state of the system at the exact moment of the crash.
>    * **Mechanism**: The database scans the WAL forward starting from the last known checkpoint. It rebuilds two key in-memory tables: the **Transaction Table** (identifying all active transactions that never committed before the crash) and the **Dirty Page Table (DPT)** (identifying all pages that were modified in RAM but never flushed to disk, along with the oldest log sequence number (`recLSN`) that modified each page).
> 2. **Step 2: The Redo Phase ("Repeating History")**:
>    * **Goal**: Reapply all modifications to restore the database to its exact pre-crash state.
>    * **Mechanism**: Starting from the smallest `recLSN` found in the DPT, the database scans the WAL forward and reapplies *every logged operation*, including changes from transactions that were subsequently aborted or left uncommitted. For each page, the database compares the log record's LSN with the page's on-disk `pageLSN`. If the `pageLSN` is smaller than the log record LSN, the change is reapplied in memory and the `pageLSN` is updated, ensuring the page matches the log.
> 3. **Step 3: The Undo Phase**:
>    * **Goal**: Roll back all changes made by transactions that were active (uncommitted) at the time of the crash.
>    * **Mechanism**: The database scans the WAL backward, starting from the end of the log. It processes the operations of all active transactions in reverse chronological order, undoing each change. For every undo operation, the database writes a **Compensation Log Record (CLR)** to the WAL containing a pointer (`UndoNextLSN`) to the next log record to be undone for that transaction. If the system crashes during this phase, the CLRs prevent the database from re-undoing already reverted changes during the next recovery attempt, guaranteeing idempotency.

---

## Concurrency Control

**Concurrency control** is the set of techniques used to manage simultaneous transaction executions, preventing data corruption while maximizing throughput. These techniques fall into three categories:

### 1. Optimistic Concurrency Control (OCC)
OCC assumes that transaction conflicts are rare. Transactions execute without blocking or acquiring locks:

1.  **Read Phase**: The transaction runs its operations in a private, isolated workspace. It records all accessed data in a **read set** and all modified data in a **write set**.
2.  **Validation Phase**: Before committing, the database checks if the transaction's read or write sets conflict with concurrent transactions. If a conflict is found (e.g., another transaction modified data this transaction read), this transaction is aborted and restarted.
3.  **Write Phase**: If validation succeeds, the transaction commits, writing its private write set permanently to the database.

> **Validation Strategies**:
> *   **Backward-Oriented**: Validates against transactions that have already committed.
> *   **Forward-Oriented**: Validates against transactions currently in their validation phase.
> *   OCC is highly efficient under read-heavy workloads where conflicts are rare, but suffers under high write contention due to frequent aborts and retries.

### 2. Multiversion Concurrency Control (MVCC)
MVCC provides transactional consistency by keeping multiple timestamped versions of a record on disk:
*   **Non-blocking Reads**: Read operations do not acquire locks and do not block write operations. Instead, a read transaction simply reads a consistent snapshot of the data matching its starting timestamp.
*   **Active Writes**: Write operations create a new version of the record with a newer timestamp instead of overwriting the old version in-place.
*   **Garbage Collection**: Older record versions are removed once no active transaction can see them.

> ### 💡 Beginner's Corner: The Underlying Mechanism of MVCC
> * **The Problem (Read-Write Lock Contention)**: In lock-based concurrency control (2PL), reader threads acquire shared locks and writer threads acquire exclusive locks. Because shared and exclusive locks conflict, readers block writers and writers block readers. Under heavy concurrent workloads, this locking causes significant latency spikes.
> * **The Solution (Snapshot Isolation)**: MVCC eliminates read-write blocking by ensuring that readers and writers operate on different versions of the same logical record.
> * **The Underlying Mechanism**:
>   1. **Version Chains**: When a row is updated, the database does not overwrite the existing data in-place. Instead, it allocates space for a new version of the row on disk and links it to the previous version using a pointer, creating a **version chain**.
>   2. **Transaction Timestamps**: Every transaction is assigned a unique read timestamp ($T_{read}$) when it begins.
>   3. **Visibility Rules**: When a transaction reads a row, the database traverses its version chain and returns the newest version whose creation timestamp is less than or equal to the transaction's $T_{read}$. This is called a **consistent snapshot**.
>   4. **Non-blocking Execution**: Because readers only read historical versions that are guaranteed to be immutable, they do not acquire any locks. Writers append new versions to the end of the chain without modifying the historical versions, allowing reads and writes to proceed concurrently without blocking.
>   5. **Garbage Collection**: A background process continuously scans version chains and purges old, unreachable versions once their timestamps are older than the oldest active transaction's read timestamp.

### 3. Pessimistic Concurrency Control (PCC)
PCC assumes conflicts are highly likely. It blocks or aborts transactions as soon as a potential conflict is detected:
*   **Timestamp Ordering**: Each transaction is assigned a timestamp. The database maintains `max_read_timestamp` and `max_write_timestamp` for each record.
    *   A read is aborted if it attempts to read a record newer than the transaction's timestamp.
    *   A write is aborted if it conflicts with a newer read. Under the **Thomas Write Rule**, a write is allowed to proceed if it is older than the record's write timestamp because the write can be safely ignored (shadowed by the newer write).
*   **Lock-Based Concurrency Control**: Transactions must acquire explicit locks on database objects before accessing them, blocking other transactions.

### Two-Phase Locking (2PL)

To guarantee that concurrent transactions are **serializable**, lock-based systems use **Two-Phase Locking (2PL)**. 2PL splits lock management into two distinct phases:

1.  **Growing Phase (Expanding)**: The transaction acquires locks as needed but is **not allowed to release any locks**.
2.  **Shrinking Phase**: The transaction releases its acquired locks but is **not allowed to acquire any new locks**.

> ### WARNING: Two-Phase Locking vs. Two-Phase Commit
> Do not confuse **Two-Phase Locking (2PL)** with **Two-Phase Commit (2PC)**:
> *   **2PL** is a local concurrency control protocol used to guarantee transaction serializability.
> *   **2PC** is a distributed consensus protocol used to coordinate commits across multiple physical nodes.

#### Deadlocks
Because pessimistic locking causes transactions to block, two or more transactions can end up waiting for each other to release locks, creating a **deadlock**.

*   **Detection (Waits-For Graph)**: The database maintains a directed graph where nodes represent transactions and edges represent "waits-for" relationships. If a cycle is detected, a deadlock exists. The database breaks the cycle by aborting one of the transactions (typically the youngest).
*   **Prevention (Timestamps)**: Transactions are assigned priorities based on their start times (older transactions have higher priority). When transaction $T_1$ requests a lock held by $T_2$:
    *   **Wait-Die**: If $T_1$ is older, it is allowed to wait. If $T_1$ is younger, it "dies" (aborts and restarts).
    *   **Wound-Wait**: If $T_1$ is older, it "wounds" $T_2$ (forcing $T_2$ to abort). If $T_1$ is younger, it is allowed to wait.

### Locks vs. Latches

In database systems, there is a strict distinction between the mechanisms that protect logical data integrity (transactions) and those that protect physical data structures (in-memory pages and indexes):

| Feature | Locks | Latches |
| :--- | :--- | :--- |
| **Protected Entity** | **Logical data** (records, keys, ranges) | **Physical data structures** (in-memory pages, B-Tree nodes) |
| **Granularity** | Keys, tables, or database objects | Pages or physical memory blocks |
| **Duration** | Held for the **entire transaction** | Held only for the **duration of the page operation** (microseconds) |
| **User Visibility** | Visible to the user (via SQL isolation/locks) | Completely hidden from the user |
| **Deadlock Handling** | Managed by the lock manager (waits-for graphs, timeouts) | Prevented by code design and latch ordering (no graph checks) |
| **Implementation** | Heavyweight (lock tables, transaction contexts) | Lightweight (mutexes, spinlocks, read-write locks) |

### Readers-Writer Locks

To allow concurrent reads on a page while isolating writes, databases use **Readers-Writer (RW) locks** as latches:
*   **Shared Mode (S)**: Multiple reader threads can hold a shared latch on a page concurrently.
*   **Exclusive Mode (X)**: A writer thread must acquire exclusive access, blocking all other readers and writers.

| Latch Request | Reader (Shared) | Writer (Exclusive) |
| :--- | :---: | :---: |
| **Reader (Shared)** | **Compatible** (Shared access) | Conflict (Exclusive block) |
| **Writer (Exclusive)** | Conflict (Exclusive block) | Conflict (Exclusive block) |

*Figure 5-7. Readers-writer lock compatibility table*

*   **Busy-Wait (Spinlocks)**: For very short page operations, threads spin in a loop using atomic compare-and-swap (CAS) instructions rather than yielding control to the OS scheduler, reducing thread context-switch overhead.

### Latch Crabbing (Latch Coupling)

To traverse a B-Tree without locking the entire index (which would block all other threads), databases use **latch crabbing**:

1.  Acquire a latch on the **parent node**.
2.  Locate the correct child node and acquire a latch on the **child node**.
3.  Evaluate if the parent is "safe":
    *   *On Read*: The parent is immediately safe. Release the parent latch.
    *   *On Insert*: The parent is safe if the child node is not full (an insert will not trigger a split). Release the parent latch.
    *   *On Delete*: The parent is safe if the child has more than the minimum number of elements (will not trigger a merge). Release the parent latch.
4.  Repeat the process descending the tree.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//3b8589e7-7c50-47af-adf4-415c64f8234b/markdown_4/imgs/img_in_image_box_140_135_1052_1213.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-25T02%3A22%3A01Z%2F-1%2F%2Fe46854ae89abba207e575b51e90f8f20c69bc0c6bcab078ee96af68ae66715cd" alt="Image" width="76%" /></div>
<div style="text-align: center;">Figure 5-9. Latch crabbing during insert</div>

> **Optimistic Latches**: Since splits and merges are rare, write operations can descend acquiring only **shared (read) latches** on the upper levels. Only the target leaf is locked in exclusive mode. If a split is triggered, the transaction releases its latches and restarts, upgrading to exclusive latches along the path.

### $B_{link}$-Trees Concurrency

$B_{link}$-Trees simplify concurrent access by adding a **sibling pointer** and a **high key** to every node.

*   **Half-Split State**: A node can be split concurrently. The new node is linked via the sibling pointer, but its parent pointer is not yet written.
*   **Traversal**: If a reader accesses the splitting node and finds the search key exceeds the node's **high key**, the reader knows a concurrent split occurred. Instead of aborting, it simply follows the **sibling link** to the new node on the same level.
*   **Benefit**: Eliminates the need to hold parent write locks during splits. Pointers are updated lazily, preventing deadlocks and allowing concurrent reads during B-Tree structural changes.

---

## Transaction Isolation

Concurrently executing transactions can overlap, causing several **read and write anomalies**:

### Read Anomalies
*   > **Dirty Read**: A transaction reads uncommitted changes made by another transaction. If the writing transaction aborts later, the reading transaction has accessed data that logically never existed.
*   > **Non-Repeatable Read (Fuzzy Read)**: A transaction reads the same record twice but gets different values because a concurrent transaction modified and committed the record in between.
*   > **Phantom Read**: A transaction runs a range query twice but receives a different set of rows because a concurrent transaction inserted or deleted rows in that range and committed.

### Write Anomalies
*   **Lost Update**: Two transactions read value $V$. Both calculate a new value and write it back. Whichever commits last overwrites the other's update without realizing it, losing the first update.
*   **Dirty Write**: A transaction writes a value based on uncommitted changes read from another transaction (a write based on a dirty read).
*   **Write Skew**: Two transactions read overlapping data, verify that their individual changes maintain a database constraint, and commit. However, the combination of their writes violates the constraint (e.g., withdrawing money from two separate accounts, driving the joint balance negative).

> ### 💡 Beginner's Corner: Transaction Read and Write Anomalies
> * **Dirty Read (Read Anomaly)**: Occurs when Transaction A modifies a row, and Transaction B reads this modified row before Transaction A commits. If Transaction A subsequently aborts and rolls back its changes, Transaction B has operated on data that logically never existed in the database.
> * **Write Skew (Write Anomaly)**: Occurs under isolation levels like Snapshot Isolation. Suppose the database has an integrity constraint that requires $X + Y \geq 0$. Currently, $X = 50$ and $Y = 50$. Transaction A reads $X$ and $Y$, and decides to subtract 80 from $X$ (making $X = -30$), verifying that $X + Y = 20 \geq 0$. Concurrently, Transaction B reads $X$ and $Y$, and decides to subtract 80 from $Y$ (making $Y = -30$), verifying that $X + Y = 20 \geq 0$. Both transactions commit. The final state is $X = -30$ and $Y = -30$, which results in $X + Y = -60$, violating the constraint. Individually, each transaction's check was valid, but because they ran concurrently without locking the shared state, they committed a write skew.

### SQL Standard Isolation Levels

To control which anomalies are allowed, SQL databases support four standard isolation levels:

| Isolation Level | Dirty Read | Non-Repeatable Read | Phantom Read |
| :--- | :---: | :---: | :---: |
| **Read Uncommitted** | Allowed | Allowed | Allowed |
| **Read Committed** | - | Allowed | Allowed |
| **Repeatable Read** | - | - | Allowed |
| **Serializable** | - | - | - |

*Figure 5-5. SQL Isolation levels and allowed anomalies*

> **Snapshot Isolation**: Under snapshot isolation, a transaction reads a consistent snapshot of the database taken when the transaction started. It commits only if the records it modified have not been changed by any other transaction in the meantime; otherwise, it aborts. This prevents lost updates, but **write skew is still possible** because transactions write to independent records.

---

## Summary

*   **ACID Properties**: Transactions guarantee **Atomicity** (all-or-nothing), **Consistency** (valid states), **Isolation** (no interference), and **Durability** (permanently written).
*   **Page Cache (Buffer Pool)**: Caches data pages in RAM, decoupling logical writes from physical disk flushes. Uses eviction policies like **CLOCK Sweep** or **TinyLFU** to manage memory capacity.
*   **Recovery & WAL**: The write-ahead log sequentially records all modifications before pages are updated on disk. Guided by **Steal / No-Force** policies, it allows rebuilding committed changes (**redo**) and rolling back uncommitted ones (**undo**).
*   **ARIES**: A robust steal/no-force recovery protocol executing in three phases: **Analysis** (finds active transactions/dirty pages), **Redo** (repeats history), and **Undo** (rolls back active transactions).
*   **Concurrency CC**: Handled via **OCC** (validation-based), **MVCC** (non-blocking snapshot reads), or **PCC** (locking/timestamps).
*   **Locks vs. Latches**: Locks protect logical records for transaction duration. Latches protect physical page layouts for thread operation duration.
*   **Latch Crabbing**: Speeds up B-Tree traversal by releasing parent locks as soon as the child is confirmed safe from structural splits/merges.

---

## Further Reading

### Transaction Processing and Recovery
*   Weikum, Gerhard, and Gottfried Vossen. 2001. *Transactional Information Systems: Theory, Algorithms, and the Practice of Concurrency Control and Recovery*. San Francisco: Morgan Kaufmann Publishers Inc.
*   Bernstein, Philip A. and Eric Newcomer. 2009. *Principles of Transaction Processing*. San Francisco: Morgan Kaufmann.
*   Graefe, Goetz, Guy, Wey & Sauer, Caetano. 2016. “Instant Recovery with Write-Ahead Logging: Page Repair, System Restart, Media Restore, and System Failover, (2nd Ed.)” in *Synthesis Lectures on Data Management* 8, 1-113.
*   Mohan, C., Don Haderle, Bruce Lindsay, Hamid Pirahesh, and Peter Schwarz. 1992. "ARIES: a transaction recovery method supporting fine-granularity locking and partial rollbacks using write-ahead logging." *ACM Transactions on Database Systems* 17, no. 1.

### B-Tree Concurrency
*   Wang, Paul. 1991. "An In-Depth Analysis of Concurrent B-Tree Algorithms." *MIT Technical Report*.
*   Graefe, Goetz. 2010. "A survey of B-tree locking techniques." *ACM Transactions on Database Systems* 35, 3.

### Parallel and Concurrent Systems
*   McKenney, Paul E. 2012. “Is Parallel Programming Hard, And, If So, What Can You Do About It?”
*   Herlihy, Maurice and Nir Shavit. 2012. *The Art of Multiprocessor Programming, Revised Reprint* (1st Ed.). San Francisco: Morgan Kaufmann.

### Modern Database Engines
*   Diaconu, Cristian et al. 2013. “Hekaton: SQL Server’s Memory-Optimized OLTP Engine.” *SIGMOD '13*.
*   Kimura, Hideaki. 2015. “FOEDUS: OLTP Engine for a Thousand Cores and NVRAM.” *SIGMOD '15*.
*   Yu, Xiangyao et al. 2016. “TicToc: Time Traveling Optimistic Concurrency Control.” *SIGMOD '16*.
*   Kim, Kangnyeon et al. 2016. “ERMIA: Fast Memory-Optimized Database System for Heterogeneous Workloads.” *SIGMOD '16*.
*   Lim, Hyeontaek et al. 2017. “Cicada: Dependably Fast Multi-Core In-Memory Transactions.” *SIGMOD '17*.
