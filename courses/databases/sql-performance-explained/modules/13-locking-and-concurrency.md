# Module 13: Locking, Concurrency, and Transaction Performance (PostgreSQL)

**Difficulty:** Advanced
**Estimated Study Time:** 6 hours
**Database:** PostgreSQL 14+

---

## Learning Objectives

By the end of this module you will be able to:
- Explain how PostgreSQL's MVCC implementation works internally
- Identify the exact lock mode acquired by every common SQL statement
- Diagnose blocking queries and deadlocks using PostgreSQL system views
- Implement optimistic and pessimistic locking patterns correctly in PostgreSQL
- Choose the correct transaction isolation level and explain its MVCC implementation
- Tune autovacuum to prevent table bloat from degrading performance
- Use online DDL techniques to alter large tables without downtime

---

## 13.1 PostgreSQL MVCC Internals

### Layer 1: Intuition

In most locking-based databases, a reader must wait for a writer to release its lock before reading. This is like a single-toilet public bathroom — one person at a time. PostgreSQL's MVCC is like a library: readers and writers work simultaneously because writers create new "editions" of data rather than overwriting the existing copy.

### Layer 2: How PostgreSQL Implements MVCC

Every row in PostgreSQL has four hidden system columns:

```sql
-- Reveal hidden MVCC columns (use tableoid to get real table name):
SELECT 
    xmin,      -- Transaction ID that INSERT'd this row version
    xmax,      -- Transaction ID that DELETE'd/UPDATE'd this row (0 = still alive)
    ctid,      -- Physical location (page_number, slot_number) of this row version
    *
FROM orders
WHERE order_id = 1;

-- Example output:
-- xmin=7823, xmax=0, ctid=(0,1), order_id=1, status='pending', ...
```

**When a row is UPDATEd:**

```sql
-- Original row: xmin=7823, xmax=0, ctid=(0,1), status='pending'

UPDATE orders SET status = 'confirmed' WHERE order_id = 1;
-- (Transaction ID = 8100)

-- PostgreSQL does NOT modify the original row in-place.
-- Instead:
-- Old row: xmin=7823, xmax=8100, ctid=(0,1), status='pending'   ← "dead" (xmax set)
-- New row: xmin=8100, xmax=0,    ctid=(0,5), status='confirmed'  ← "live"
```

**Visibility rules:** When a transaction reads a row, it checks:
- Is `xmin` committed and did it commit before my snapshot? If no → not visible
- Is `xmax` = 0 (or `xmax` not committed, or `xmax` committed after my snapshot)? If yes → visible

```
                Timeline →
T1 starts          T2 updates         T3 starts
(snapshot: @100)   (snapshot: @150)   (snapshot: @200)
                   UPDATE row
                   COMMIT @175

T1 SELECT → sees xmin=50, xmax=175 → T2 committed AFTER T1 started → T1 still sees old version ✓
T3 SELECT → sees xmin=175 → T2 committed BEFORE T3 started → T3 sees new version ✓
```

### Layer 3: The Dead Tuple Problem

Old row versions (xmax set, no longer visible to any transaction) are called **dead tuples**. They are not deleted immediately — they stay in the table page occupying space until `VACUUM` reclaims them.

```sql
-- Observe dead tuples accumulating:
SELECT 
    schemaname,
    tablename,
    n_live_tup,       -- Current live rows
    n_dead_tup,       -- Dead tuples awaiting vacuum
    n_dead_tup::float / NULLIF(n_live_tup, 0) AS dead_ratio,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE tablename = 'orders';

-- dead_ratio > 0.20 (20%) is a concern
-- dead_ratio > 0.50 is serious: performance degradation likely
```

**Performance impact of dead tuples:**
- Sequential scans must skip dead tuples → more pages read than row count implies
- Index scans still point to dead tuples via old ctid → heap page reads that return nothing
- Table and index files grow without bound (table bloat)

```sql
-- Check actual table and index bloat (requires pgstattuple extension):
CREATE EXTENSION IF NOT EXISTS pgstattuple;

SELECT * FROM pgstattuple('orders');
-- Key fields:
-- tuple_count:      live rows
-- dead_tuple_count: dead rows
-- dead_tuple_percent: % of table that is wasted

-- Estimate bloat without extension:
SELECT 
    pg_size_pretty(pg_total_relation_size('orders')) AS total_size,
    pg_size_pretty(pg_relation_size('orders')) AS table_size,
    pg_size_pretty(pg_indexes_size('orders')) AS index_size;
```

---

## 13.2 PostgreSQL Lock Modes

### All 8 Lock Modes

PostgreSQL has 8 table-level lock modes (from least to most restrictive):

| Lock Mode | SQL Command | Conflicts With |
| :--- | :--- | :--- |
| `ACCESS SHARE` | `SELECT` | `ACCESS EXCLUSIVE` only |
| `ROW SHARE` | `SELECT FOR UPDATE/SHARE` | `EXCLUSIVE`, `ACCESS EXCLUSIVE` |
| `ROW EXCLUSIVE` | `INSERT`, `UPDATE`, `DELETE` | `SHARE`, `SHARE ROW EXCLUSIVE`, `EXCLUSIVE`, `ACCESS EXCLUSIVE` |
| `SHARE UPDATE EXCLUSIVE` | `VACUUM`, `CREATE INDEX CONCURRENTLY` | `SHARE UPDATE EXCLUSIVE` and above |
| `SHARE` | `CREATE INDEX` (non-concurrent) | `ROW EXCLUSIVE` and above |
| `SHARE ROW EXCLUSIVE` | `CREATE TRIGGER` | `ROW EXCLUSIVE` and above |
| `EXCLUSIVE` | Rare, explicit | `ROW SHARE` and above |
| `ACCESS EXCLUSIVE` | `ALTER TABLE`, `DROP TABLE`, `VACUUM FULL` | **ALL** — blocks even SELECTs |

**The key insight:** A regular `SELECT` only takes `ACCESS SHARE`, which conflicts with nothing except `ACCESS EXCLUSIVE` (DDL). This is why reads are almost never blocked in PostgreSQL.

### What Acquires What Lock

```sql
-- View all current table-level locks:
SELECT 
    pid,
    relation::regclass AS table_name,
    mode,
    granted,
    pg_stat_activity.query,
    pg_stat_activity.state
FROM pg_locks
JOIN pg_stat_activity USING (pid)
WHERE relation IS NOT NULL
ORDER BY granted DESC, mode;
```

**Practical lock acquisition examples:**

```sql
-- ACCESS SHARE (SELECT):
BEGIN;
SELECT * FROM orders WHERE order_id = 1;
-- Holds: ACCESS SHARE on orders table
-- Row-level: no table-level row lock for plain SELECT
COMMIT;

-- ROW EXCLUSIVE (UPDATE/DELETE/INSERT):
BEGIN;
UPDATE orders SET status = 'confirmed' WHERE order_id = 1;
-- Table-level: ROW EXCLUSIVE on orders
-- Row-level: EXCLUSIVE on the specific tuple (ctid)
COMMIT;

-- ROW SHARE (SELECT FOR UPDATE):
BEGIN;
SELECT * FROM orders WHERE order_id = 1 FOR UPDATE;
-- Table-level: ROW SHARE on orders
-- Row-level: EXCLUSIVE on the specific tuple
-- Effect: other transactions trying to UPDATE/DELETE/SELECT FOR UPDATE this row WAIT
COMMIT;

-- ACCESS EXCLUSIVE (ALTER TABLE):
ALTER TABLE orders ADD COLUMN priority INTEGER DEFAULT 0;
-- Holds ACCESS EXCLUSIVE — blocks ALL concurrent operations including SELECT!
-- On a large table during peak hours, this is a production incident.
```

### Row-Level Locks

PostgreSQL row-level locks are stored inside the heap page itself (in the row's `xmax` field), not in a separate lock table. This makes row-level locking essentially free in terms of lock table memory.

```sql
-- Four row-level lock modes:

-- FOR UPDATE: Exclusive row lock (prevents all concurrent modifications)
SELECT * FROM orders WHERE order_id = 1 FOR UPDATE;

-- FOR NO KEY UPDATE: Like FOR UPDATE but allows FK-only updates
SELECT * FROM orders WHERE order_id = 1 FOR NO KEY UPDATE;

-- FOR SHARE: Shared row lock (prevents modifications, allows other shared locks)
SELECT * FROM orders WHERE order_id = 1 FOR SHARE;

-- FOR KEY SHARE: Weakest row lock (only prevents DELETE and key-changing UPDATE)
SELECT * FROM orders WHERE order_id = 1 FOR KEY SHARE;
```

**Lock incompatibility at row level:**

```
            FOR KEY SHARE  FOR SHARE  FOR NO KEY UPDATE  FOR UPDATE
FOR KEY SHARE    OK            OK            OK              WAIT
FOR SHARE        OK            OK           WAIT             WAIT
FOR NO KEY UPDATE OK           WAIT          WAIT             WAIT
FOR UPDATE       WAIT          WAIT          WAIT             WAIT
```

---

## 13.3 Diagnosing Lock Contention in PostgreSQL

### Finding Blocking Queries

```sql
-- The essential blocking query: find what is blocking what
SELECT
    blocked.pid                  AS blocked_pid,
    blocked.usename              AS blocked_user,
    blocked.query                AS blocked_query,
    blocked.query_start          AS blocked_since,
    now() - blocked.query_start  AS blocked_duration,
    blocking.pid                 AS blocking_pid,
    blocking.usename             AS blocking_user,
    blocking.query               AS blocking_query,
    blocking.query_start         AS blocking_since
FROM pg_stat_activity AS blocked
JOIN pg_stat_activity AS blocking
    ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE cardinality(pg_blocking_pids(blocked.pid)) > 0
ORDER BY blocked_duration DESC;
```

**Interpreting the output:**

```
blocked_pid | blocked_query                          | blocking_pid | blocking_query                      | blocked_duration
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
8721        | UPDATE orders SET status='shipped'...  | 8645         | UPDATE orders SET status='paid'...  | 00:00:45
9102        | SELECT * FROM orders FOR UPDATE...      | 8645         | UPDATE orders SET status='paid'...  | 00:00:38
```

**Analysis:** PID 8645 has been running an UPDATE for at least 45 seconds and has NOT committed. It is blocking two other sessions. This is the root blocker.

### Full Lock Graph Query

```sql
-- Full lock chain (recursively trace all waiting sessions):
WITH RECURSIVE lock_chain AS (
    -- Base: sessions that are blocked
    SELECT 
        pid AS blocked_pid,
        pg_blocking_pids(pid) AS blocking_pids,
        query AS blocked_query,
        1 AS depth
    FROM pg_stat_activity
    WHERE cardinality(pg_blocking_pids(pid)) > 0
    
    UNION ALL
    
    -- Recursive: find what is blocking the blocker
    SELECT 
        a.pid,
        pg_blocking_pids(a.pid),
        a.query,
        lc.depth + 1
    FROM pg_stat_activity a
    JOIN lock_chain lc ON a.pid = ANY(lc.blocking_pids)
    WHERE depth < 10  -- prevent infinite recursion
)
SELECT DISTINCT * FROM lock_chain ORDER BY depth;
```

### Lock Wait Monitoring Query

```sql
-- Combined view: all active locks with wait state and query text
SELECT
    l.pid,
    l.relation::regclass   AS locked_table,
    l.mode,
    l.granted,
    a.query,
    a.state,
    a.wait_event_type,
    a.wait_event,
    now() - a.query_start  AS query_age
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE l.relation IS NOT NULL
  AND a.state != 'idle'
ORDER BY l.granted, query_age DESC;
```

### Killing a Blocking Session

```sql
-- Step 1: Identify the blocker PID (from queries above, e.g., PID 8645)

-- Step 2: Attempt graceful cancellation (kills current query, keeps connection)
SELECT pg_cancel_backend(8645);
-- Returns: true if signal sent, false if PID not found

-- Step 3: If still blocking, terminate the entire connection
SELECT pg_terminate_backend(8645);
-- Returns: true if connection terminated

-- Important: pg_terminate_backend rolls back the transaction and all its locks
-- Use only when the session is causing widespread blockage
```

---

## 13.4 Advisory Locks

Advisory locks are application-managed locks that do not protect specific rows or tables — they protect any logical resource identified by an integer.

```sql
-- Session-level advisory lock (held until explicitly released or session ends):
SELECT pg_advisory_lock(12345);           -- Exclusive lock on key 12345
SELECT pg_advisory_lock_shared(12345);    -- Shared lock on key 12345
SELECT pg_advisory_unlock(12345);         -- Release

-- Transaction-level advisory lock (released automatically at COMMIT/ROLLBACK):
SELECT pg_advisory_xact_lock(12345);           -- Auto-released at transaction end
SELECT pg_advisory_xact_lock_shared(12345);

-- Non-blocking trylock (returns immediately):
SELECT pg_try_advisory_lock(12345);       -- Returns true if acquired, false if busy
SELECT pg_try_advisory_xact_lock(12345);
```

**Use cases for advisory locks:**

```sql
-- Pattern 1: Distributed cron job — only one server runs a task at a time
DO $$
BEGIN
    -- Try to acquire exclusive lock on application-defined key 999
    IF pg_try_advisory_xact_lock(999) THEN
        -- Only one server acquires this lock — do the work:
        PERFORM process_pending_jobs();
        RAISE NOTICE 'Job executed by this server';
    ELSE
        RAISE NOTICE 'Another server is running this job, skipping';
    END IF;
END $$;
-- Lock auto-released when DO block's transaction ends

-- Pattern 2: Prevent concurrent processing of the same entity
-- When updating a customer's credit limit, prevent duplicate concurrent updates:
DO $$
DECLARE
    v_customer_id BIGINT := 42;
BEGIN
    -- Lock keyed on customer_id (convert to bigint for advisory lock)
    PERFORM pg_advisory_xact_lock(v_customer_id);
    
    -- Safe to read-modify-write: no other session can acquire this lock for customer 42
    UPDATE customers 
    SET credit_limit = credit_limit + 1000
    WHERE customer_id = v_customer_id;
    
    -- Lock released at COMMIT automatically
END $$;
```

---

## 13.5 Isolation Levels in PostgreSQL

### PostgreSQL's MVCC-Based Isolation

PostgreSQL implements ALL isolation levels using MVCC snapshots, not traditional locking. This is fundamentally different from SQL Server's lock-based isolation:

```
SQL Server:                         PostgreSQL:
REPEATABLE READ =                   REPEATABLE READ =
  Hold read locks until commit        Snapshot at transaction START
  → Blocks writers                    → Writers never blocked by readers
```

### READ COMMITTED (Default)

```sql
BEGIN;  -- Default: READ COMMITTED
-- Each statement gets a NEW snapshot of committed data

SELECT amount FROM accounts WHERE id = 1;  -- Sees: 1000 (T2 hasn't committed)

-- T2 commits: UPDATE accounts SET amount = 900 WHERE id = 1;

SELECT amount FROM accounts WHERE id = 1;  -- Now sees: 900 (T2 committed)
-- Non-repeatable read: two reads in the SAME transaction see DIFFERENT values

COMMIT;
```

**When READ COMMITTED is appropriate:** Most OLTP operations — inserting orders, updating user profiles, processing events. Each statement sees the latest committed state, which is correct for isolated CRUD operations.

**When READ COMMITTED is NOT appropriate:** Multi-step financial calculations where you need a consistent view throughout (e.g., computing a balance from multiple reads and then writing a derived value).

### REPEATABLE READ

```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
-- Single snapshot taken at the START of the transaction

SELECT amount FROM accounts WHERE id = 1;  -- Sees: 1000

-- T2 commits: UPDATE accounts SET amount = 900 WHERE id = 1;

SELECT amount FROM accounts WHERE id = 1;  -- Still sees: 1000 (snapshot is fixed)
-- No non-repeatable read!

COMMIT;
```

**PostgreSQL REPEATABLE READ also prevents phantom reads** (unlike SQL standard definition). This is stronger than required by the SQL standard but makes REPEATABLE READ more useful in PostgreSQL.

**When REPEATABLE READ is appropriate:**
- Computing aggregates across multiple statements that must be consistent
- Report generation (ensure report is consistent to a point in time)
- Multi-step reads where consistency matters

### SERIALIZABLE

```sql
BEGIN ISOLATION LEVEL SERIALIZABLE;
-- PostgreSQL uses Serializable Snapshot Isolation (SSI) — not lock-based
-- SSI tracks read/write dependencies and detects serialization conflicts

-- Example: Concurrent write-skew scenario
-- T1 reads all doctors on call (finds 3)
SELECT COUNT(*) FROM on_call_doctors WHERE shift_date = TODAY;  -- Returns 3

-- T2 simultaneously: also reads 3 on-call doctors, decides to remove one
-- T1 simultaneously: also decides to remove one
-- Both T1 and T2 commit → 1 doctor on call (business rule violation: need ≥ 2)

-- Under SERIALIZABLE: one transaction is aborted with:
-- ERROR: could not serialize access due to read/write dependencies among transactions
-- DETAIL: Processes in the serialization graph...
-- SQLSTATE: 40001 (serialization_failure)

COMMIT;
```

**Handling serialization failures:**

```java
// Java application: retry on serialization failure
int maxRetries = 3;
for (int attempt = 0; attempt < maxRetries; attempt++) {
    try (Connection conn = dataSource.getConnection()) {
        conn.setAutoCommit(false);
        conn.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
        
        try {
            // Execute business logic
            performCriticalOperation(conn);
            conn.commit();
            break; // Success
        } catch (SQLException e) {
            conn.rollback();
            if ("40001".equals(e.getSQLState())) {
                // Serialization failure — retry
                if (attempt == maxRetries - 1) throw e;
                Thread.sleep(50 * (attempt + 1)); // Backoff
            } else {
                throw e; // Other error, don't retry
            }
        }
    }
}
```

**When SERIALIZABLE is appropriate:**
- Inventory reservation (prevent overselling)
- Auction bidding (prevent two users winning the same item)
- Account balance checks with conditional writes
- Any "read-modify-write" with a business invariant

**Performance cost of SERIALIZABLE:** SSI tracks read/write dependencies using predicate locks. These consume memory in the lock table and introduce overhead per transaction. For low-conflict workloads: ~10–20% overhead. For high-conflict workloads: significant abort rate → retry loops → net throughput reduction.

### Isolation Level Decision Guide

```
Decision tree:
  ├─ Do you need to prevent dirty reads (read uncommitted data)?
  │   └─ Always YES in PostgreSQL — all levels prevent dirty reads
  │
  ├─ Do multiple reads within the same transaction need to be consistent?
  │   ├─ NO → READ COMMITTED (default, best performance)
  │   └─ YES →
  │       ├─ Is a phantom read acceptable? (new rows inserted between reads)
  │       │   └─ NO or YES → REPEATABLE READ (PostgreSQL prevents phantoms too)
  │       └─ Do you need write serialization (prevent write skew)?
  │           └─ YES → SERIALIZABLE (with retry logic)
```

---

## 13.6 Deadlock Detection and Prevention

### How PostgreSQL Detects Deadlocks

PostgreSQL's deadlock detector runs every `deadlock_timeout` milliseconds (default: 1 second). When a transaction has been waiting for `deadlock_timeout`, the detector runs, examines the wait-for graph, and identifies cycles.

```sql
-- Check current deadlock_timeout:
SHOW deadlock_timeout;  -- Default: '1s'

-- Tune for high-concurrency OLTP (shorter detection = faster resolution):
SET deadlock_timeout = '100ms';  -- Per-session
-- Or in postgresql.conf: deadlock_timeout = 100ms
```

**Deadlock log entry:**
```
ERROR:  deadlock detected
DETAIL: Process 8721 waits for ShareLock on transaction 8645; 
        blocked by process 8645.
        Process 8645 waits for ShareLock on transaction 8721; 
        blocked by process 8721.
HINT:   See server log for query details.
CONTEXT: while updating tuple (0,3) in relation "orders"
```

**PostgreSQL chooses the victim** as the transaction that has done the least work (fewest locks acquired or smallest transaction size).

### Preventing Deadlocks with Consistent Lock Ordering

```sql
-- Schema: Transfer between accounts — deadlock-prone pattern
-- T1: transfers from account 1 to 2
-- T2: transfers from account 2 to 1 (simultaneously)

-- Deadlock-prone (wrong):
-- T1: LOCK account 1, LOCK account 2
-- T2: LOCK account 2, LOCK account 1 → deadlock possible!

-- Deadlock-safe (always lock in ID order):
CREATE OR REPLACE FUNCTION transfer_funds(
    from_account_id BIGINT,
    to_account_id   BIGINT,
    amount          NUMERIC
) RETURNS VOID AS $$
DECLARE
    first_id  BIGINT;
    second_id BIGINT;
BEGIN
    -- Always lock the lower ID first → consistent ordering → no deadlock
    IF from_account_id < to_account_id THEN
        first_id  := from_account_id;
        second_id := to_account_id;
    ELSE
        first_id  := to_account_id;
        second_id := from_account_id;
    END IF;
    
    -- Lock both rows in consistent order
    PERFORM 1 FROM accounts WHERE account_id IN (first_id, second_id)
    ORDER BY account_id   -- Explicit order within the IN clause
    FOR UPDATE;
    
    -- Now safely perform the transfer
    UPDATE accounts SET balance = balance - amount WHERE account_id = from_account_id;
    UPDATE accounts SET balance = balance + amount WHERE account_id = to_account_id;
END;
$$ LANGUAGE plpgsql;
```

### `SKIP LOCKED`: Queue Pattern Without Deadlocks

```sql
-- Job queue table
CREATE TABLE job_queue (
    job_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payload    JSONB NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_job_queue_status ON job_queue (status, created_at)
    WHERE status = 'pending';

-- Worker function: claim one job atomically, skip already-locked jobs
CREATE OR REPLACE FUNCTION claim_next_job()
RETURNS TABLE (job_id BIGINT, payload JSONB) AS $$
BEGIN
    RETURN QUERY
    UPDATE job_queue
    SET status = 'processing'
    WHERE job_id = (
        SELECT jq.job_id
        FROM job_queue jq
        WHERE jq.status = 'pending'
        ORDER BY jq.created_at
        LIMIT 1
        FOR UPDATE SKIP LOCKED   -- ← Key: skip rows locked by other workers
    )
    RETURNING job_queue.job_id, job_queue.payload;
END;
$$ LANGUAGE plpgsql;

-- Multiple workers can call this simultaneously with NO deadlock and NO duplicate claims:
SELECT * FROM claim_next_job();
```

**How `SKIP LOCKED` works:** When a worker tries to acquire a row lock (`FOR UPDATE`) and the row is already locked by another transaction, instead of waiting, it skips to the next available unlocked row. This makes it perfect for work queue processing where any available job is acceptable.

---

## 13.7 Optimistic vs. Pessimistic Locking in PostgreSQL

### Pessimistic Locking with `SELECT FOR UPDATE`

```sql
-- Pattern: Reserve inventory item (pessimistic)
BEGIN;

-- Lock the row immediately — no other transaction can modify this row until we commit
SELECT quantity, reserved
FROM inventory
WHERE product_id = 42
FOR UPDATE;  -- Exclusive row lock

-- Check availability:
-- IF quantity - reserved >= requested_qty THEN
UPDATE inventory
SET reserved = reserved + :requested_qty
WHERE product_id = 42;

COMMIT;
-- Lock released on commit
```

**Lock modes available in PostgreSQL:**
```sql
FOR UPDATE           -- Full exclusive lock (most restrictive)
FOR NO KEY UPDATE    -- Exclusive but allows other transactions to FK-reference this row
FOR SHARE            -- Shared lock: allows other readers to also share-lock, blocks updates
FOR KEY SHARE        -- Weakest: only blocks DELETE and key-changing UPDATE
```

**`NOWAIT` option:** Fail immediately if the row is locked (instead of waiting):
```sql
SELECT * FROM inventory WHERE product_id = 42 FOR UPDATE NOWAIT;
-- If locked: ERROR: could not obtain lock on row in relation "inventory"
-- Application handles this immediately rather than waiting
```

**`SKIP LOCKED` option:** Skip locked rows (covered in queue pattern above)

### Optimistic Locking with Version Columns

```sql
-- Schema with version column:
CREATE TABLE products (
    product_id  BIGINT PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    price       NUMERIC(10,2) NOT NULL,
    stock       INTEGER NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Read (no lock taken):
SELECT product_id, price, stock, version
FROM products
WHERE product_id = 42;
-- Returns: price=29.99, stock=100, version=7

-- Application processes data (no lock held during this time)...

-- Write with version check (atomic compare-and-swap):
UPDATE products
SET 
    stock    = stock - :requested_qty,
    version  = version + 1,
    updated_at = NOW()
WHERE product_id = 42
  AND version = 7;  -- ← Only succeeds if version hasn't changed

-- Check if our update succeeded:
GET DIAGNOSTICS rows_affected = ROW_COUNT;
IF rows_affected = 0 THEN
    -- Version changed: another transaction modified this product
    -- Retry: re-read, re-validate, re-attempt
    RAISE EXCEPTION 'Optimistic lock conflict on product %', 42;
END IF;
```

**Optimistic locking with `RETURNING` (single round-trip):**
```sql
-- Attempt update and get the result back in one statement:
WITH attempt AS (
    UPDATE products
    SET stock = stock - :qty, version = version + 1
    WHERE product_id = 42 AND version = :expected_version
    RETURNING product_id, stock, version
)
SELECT 
    CASE WHEN EXISTS (SELECT 1 FROM attempt) 
         THEN 'success' 
         ELSE 'conflict'
    END AS result;
```

---

## 13.8 Autovacuum: Keeping MVCC Performant

### Why Autovacuum Is Critical

Because MVCC leaves dead tuples in place, autovacuum is essential for:
1. **Reclaiming space** from dead tuples (prevents table bloat)
2. **Preventing transaction ID wraparound** (a catastrophic event that forces `VACUUM FREEZE` on the entire database)
3. **Updating statistics** for the query planner (via `ANALYZE`)

### Autovacuum Configuration

```sql
-- View current autovacuum settings:
SHOW autovacuum_vacuum_scale_factor;   -- Default: 0.2 (20%)
SHOW autovacuum_vacuum_threshold;       -- Default: 50 rows
SHOW autovacuum_analyze_scale_factor;  -- Default: 0.1 (10%)
SHOW autovacuum_analyze_threshold;     -- Default: 50 rows

-- Autovacuum triggers VACUUM when:
-- n_dead_tup > autovacuum_vacuum_threshold + (n_live_tup * autovacuum_vacuum_scale_factor)
-- = 50 + (1,000,000 * 0.20) = 200,050 dead tuples

-- For a 1M row table: vacuum only triggers after 200,000 dead tuples!
-- This means significant table bloat before vacuum runs.
```

**Tuning autovacuum for high-write tables:**

```sql
-- Per-table autovacuum tuning (overrides global settings):
ALTER TABLE orders SET (
    autovacuum_vacuum_scale_factor = 0.01,   -- Trigger at 1% dead tuples (not 20%)
    autovacuum_vacuum_threshold    = 100,    -- Minimum 100 dead tuples (not 50)
    autovacuum_analyze_scale_factor = 0.005, -- Analyze at 0.5% changes
    autovacuum_vacuum_cost_delay   = 2       -- Reduce I/O throttling (ms, default 2)
);

-- For extremely high-write tables (e.g., logging, events):
ALTER TABLE events SET (
    autovacuum_vacuum_scale_factor = 0.001,  -- Trigger at 0.1% dead tuples
    autovacuum_vacuum_threshold    = 1000,
    autovacuum_analyze_scale_factor = 0.001
);
```

### Monitoring Autovacuum

```sql
-- Is autovacuum running right now?
SELECT 
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query,
    state
FROM pg_stat_activity
WHERE query LIKE 'autovacuum:%'
ORDER BY duration DESC;

-- Check autovacuum history and effectiveness:
SELECT
    schemaname,
    tablename,
    n_live_tup,
    n_dead_tup,
    round(n_dead_tup * 100.0 / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_pct,
    last_autovacuum,
    last_autoanalyze,
    vacuum_count,
    autovacuum_count
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 20;

-- Tables with dead_pct > 10% need attention
```

### Manual VACUUM Operations

```sql
-- Standard VACUUM (reclaims dead tuples, does not return space to OS):
VACUUM orders;

-- VACUUM ANALYZE (also refreshes query planner statistics):
VACUUM ANALYZE orders;

-- VACUUM FULL (rewrites table, returns space to OS — REQUIRES ACCESS EXCLUSIVE LOCK!):
-- WARNING: Blocks ALL queries for the duration. Use only in maintenance windows.
VACUUM FULL orders;

-- Better alternative to VACUUM FULL for online reclamation:
-- pg_repack extension (rebuilds table without exclusive lock)
-- pg_repack --table=orders --dbname=mydb
```

---

## 13.9 Online DDL in PostgreSQL

### The Problem: `ALTER TABLE` Takes `ACCESS EXCLUSIVE`

```sql
-- This blocks ALL reads and writes for the entire duration:
ALTER TABLE orders ADD COLUMN notes TEXT;
-- On a 500M row table: could take minutes, causing a production outage
```

### Safe Patterns for Online DDL

**Pattern 1: Add column with NULL default (instant)**
```sql
-- Adding a nullable column is always instant (no table rewrite):
ALTER TABLE orders ADD COLUMN notes TEXT;        -- Instant ✓
ALTER TABLE orders ADD COLUMN priority INTEGER;  -- Instant (NULL default) ✓

-- Backfill later in small batches to avoid long transactions:
DO $$
DECLARE
    batch_size INTEGER := 10000;
    last_id BIGINT := 0;
    max_id BIGINT;
BEGIN
    SELECT MAX(order_id) INTO max_id FROM orders;
    
    WHILE last_id < max_id LOOP
        UPDATE orders
        SET priority = 0
        WHERE order_id > last_id AND order_id <= last_id + batch_size
          AND priority IS NULL;
        
        last_id := last_id + batch_size;
        PERFORM pg_sleep(0.05);  -- Brief pause to reduce I/O pressure
    END LOOP;
END $$;

-- After backfill, add NOT NULL constraint:
ALTER TABLE orders ALTER COLUMN priority SET NOT NULL;  -- Requires full table scan
-- Or use CHECK CONSTRAINT with NOT VALID first (faster):
ALTER TABLE orders ADD CONSTRAINT orders_priority_not_null 
    CHECK (priority IS NOT NULL) NOT VALID;  -- Instant (skips existing rows)
-- Then validate in background:
ALTER TABLE orders VALIDATE CONSTRAINT orders_priority_not_null;  -- Scans table
-- Then convert to NOT NULL:
ALTER TABLE orders ALTER COLUMN priority SET NOT NULL;  -- Instant (constraint verified)
ALTER TABLE orders DROP CONSTRAINT orders_priority_not_null;
```

**Pattern 2: Adding a constant default value (PostgreSQL 11+, instant)**
```sql
-- PostgreSQL 11+: Adding a column with a non-volatile constant default is INSTANT
-- No table rewrite needed — the default is stored in pg_attribute

ALTER TABLE orders ADD COLUMN status_code SMALLINT NOT NULL DEFAULT 0;
-- Instant! Even on a 1 billion row table.
-- PostgreSQL stores the default in catalog; existing rows appear to have value 0
-- Only new rows/updates physically write the column value
```

**Pattern 3: `CREATE INDEX CONCURRENTLY` (no write blocking)**
```sql
-- Regular index creation: takes SHARE lock → blocks writes during build
CREATE INDEX idx_orders_customer ON orders (customer_id);  -- Blocks writes!

-- Concurrent index creation: only takes SHARE UPDATE EXCLUSIVE
-- Other writes can proceed during the build (index build takes longer but is online)
CREATE INDEX CONCURRENTLY idx_orders_customer ON orders (customer_id);

-- Important limitations of CONCURRENTLY:
-- 1. Cannot be done inside a transaction block (must run outside BEGIN/COMMIT)
-- 2. Takes longer (two-pass: reads table twice)
-- 3. If it fails, leaves an INVALID index — must DROP CONCURRENTLY and rebuild

-- Check for invalid indexes:
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'orders'
  AND NOT EXISTS (
      SELECT 1 FROM pg_index i 
      JOIN pg_class c ON i.indexrelid = c.oid
      WHERE c.relname = pg_indexes.indexname
        AND i.indisvalid = true
  );

-- Drop an invalid index:
DROP INDEX CONCURRENTLY idx_orders_customer;
```

**Pattern 4: Rename column (dangerous — requires application coordination)**
```sql
-- Step 1: Add new column
ALTER TABLE orders ADD COLUMN customer_ref_id BIGINT;  -- Instant

-- Step 2: Sync old to new via trigger (application still writes to old column)
CREATE OR REPLACE FUNCTION sync_customer_id()
RETURNS TRIGGER AS $$
BEGIN
    NEW.customer_ref_id := NEW.customer_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_customer_id
    BEFORE INSERT OR UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION sync_customer_id();

-- Step 3: Backfill new column from old
UPDATE orders SET customer_ref_id = customer_id WHERE customer_ref_id IS NULL;

-- Step 4: Deploy application code to read from new column

-- Step 5: Drop trigger and old column (after old column no longer needed)
DROP TRIGGER trg_sync_customer_id ON orders;
ALTER TABLE orders DROP COLUMN customer_id;

-- Step 6: Rename new column
ALTER TABLE orders RENAME COLUMN customer_ref_id TO customer_id;
```

---

## 13.10 Exercises

### Exercise 13.1: Lock Observation Lab

Open three `psql` sessions simultaneously:

**Session 1:** Begin a transaction and lock a row:
```sql
BEGIN;
SELECT * FROM orders WHERE order_id = 1 FOR UPDATE;
-- Do NOT commit yet
```

**Session 2:** Try to update the same row and observe blocking:
```sql
BEGIN;
UPDATE orders SET status = 'confirmed' WHERE order_id = 1;
-- This should block
```

**Session 3:** Monitor the lock situation:
```sql
SELECT 
    blocked.pid AS blocked_pid,
    blocked.query AS blocked_query,
    blocking.pid AS blocking_pid,
    blocking.query AS blocking_query,
    now() - blocked.query_start AS wait_time
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking 
    ON blocking.pid = ANY(pg_blocking_pids(blocked.pid));
```

Then commit Session 1 and observe Session 2 unblock. Record the wait time.

### Exercise 13.2: Deadlock Reproduction and Analysis

**Session 1:**
```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE account_id = 1;
-- Wait 2 seconds, then:
UPDATE accounts SET balance = balance + 100 WHERE account_id = 2;
```

**Session 2 (start 1 second after Session 1):**
```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE account_id = 2;
-- Then immediately:
UPDATE accounts SET balance = balance + 100 WHERE account_id = 1;
```

Observe which session gets the deadlock error. Rewrite using the consistent-ordering function from 13.6 to prevent it.

### Exercise 13.3: Autovacuum Bloat Analysis

1. Create a table and insert 100,000 rows
2. Run `UPDATE` on all rows 10 times (generating 900,000 dead tuples)
3. Check `n_dead_tup` in `pg_stat_user_tables`
4. Run `VACUUM ANALYZE` manually
5. Verify dead tuple count drops to 0
6. Tune `autovacuum_vacuum_scale_factor` to 0.01 and repeat — observe autovacuum running sooner

---

## 13.11 Knowledge Check

1. What are the four hidden MVCC system columns in every PostgreSQL row and what does each store?
2. What lock mode does a plain `SELECT` acquire? What lock mode does `ALTER TABLE` acquire?
3. What is the difference between `FOR UPDATE` and `FOR UPDATE SKIP LOCKED`?
4. Under REPEATABLE READ in PostgreSQL, can a phantom read occur? Why or why not?
5. What happens to dead tuples if autovacuum is disabled? How does this affect performance?
6. Why can `CREATE INDEX CONCURRENTLY` not run inside a transaction block?

---

## 13.12 Interview-Style Questions

**Q: A PostgreSQL UPDATE on a high-write table is running slowly. You `EXPLAIN ANALYZE` and the query plan looks optimal. `pg_stat_user_tables` shows `n_dead_tup = 5,000,000`. What is happening and how do you fix it?**

> Model answer: Severe table bloat. 5M dead tuples indicate autovacuum is not keeping up with the write rate. Dead tuples inflate the table's physical size — sequential scans now read many more 8KB pages than the live row count implies. Index scans also encounter dead tuple ctids, requiring heap page reads that return nothing. Fix: (1) Run `VACUUM ANALYZE tablename` manually to immediately reclaim space. (2) Reduce `autovacuum_vacuum_scale_factor` for this table to 0.01 or lower so autovacuum triggers earlier. (3) Check if autovacuum is being throttled — reduce `autovacuum_vacuum_cost_delay` or increase `autovacuum_vacuum_cost_limit`. (4) If bloat is severe (table is 3x+ expected size), schedule a `pg_repack` run during low-traffic hours to rebuild the table online without `VACUUM FULL`'s exclusive lock.

**Q: You have a `SELECT FOR UPDATE NOWAIT` in production. Under what circumstances would you choose `NOWAIT` over the default waiting behavior, and what must the application handle?**

> Model answer: Use `NOWAIT` when holding up the request while waiting for a lock is worse than failing fast. Example: a user clicks "claim ticket" — if the ticket is already being claimed, showing an immediate error ("ticket no longer available") is better than the user waiting 30 seconds only to get the same error at lock timeout. The application must handle `ERROR: could not obtain lock on row` (SQLSTATE 55P03) gracefully: catch the exception, present an appropriate message to the user, and allow retry at the application level rather than blocking the database thread. If `NOWAIT` is used in a transaction, the transaction must be rolled back after the error before attempting to reuse the connection.

**Q: You need to add a NOT NULL column with a non-constant default to a 2-billion row table in production. The table serves thousands of queries per second. How do you do this without downtime?**

> Model answer: Use the expand-then-constrain pattern. (1) Add the column as nullable with no default — instant, no lock beyond the catalog change. (2) Backfill in small batches (10,000–50,000 rows per transaction) with `pg_sleep(0.1)` between batches to prevent I/O saturation. This takes hours but runs in the background without blocking. (3) Add a `CHECK (col IS NOT NULL) NOT VALID` constraint — instant, existing rows not validated. (4) `VALIDATE CONSTRAINT` — runs a read-only scan of the table to verify all existing rows (takes time but only takes `SHARE UPDATE EXCLUSIVE`, allowing concurrent reads/writes). (5) `ALTER COLUMN SET NOT NULL` — instant because the check constraint already verified all rows. This sequence never takes `ACCESS EXCLUSIVE` for more than a catalog-update millisecond.

---

*End of Module 13*

*See also:*
- *[Module 11: Optimizer Statistics](11-optimizer-statistics.md) — how stale stats interact with lock wait estimates*
- *[Module 12: Table Partitioning](12-table-partitioning.md) — partitioning reduces lock contention scope*
