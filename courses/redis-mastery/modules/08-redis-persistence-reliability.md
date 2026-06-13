# Module 08: Persistence, Durability, and Data Recovery

## 1. What Problem This Module Solves

Redis is an in-memory database. If the server crashes, experiences a power loss, or restarts, all data in RAM is lost. 

To prevent data loss, Redis provides **Persistence** options to write data to non-volatile disk storage. This module explains how to configure Point-in-Time snapshots (RDB) and Append-Only logs (AOF) to balance performance and durability.

---

## 2. Why Redis is Used Instead of Alternatives

*   **Over Standard Disk Databases (for latency)**: While databases like PostgreSQL write data to disk before acknowledging transactions (strict durability), this limits write speeds. Redis write operations target memory first, utilizing background threads to write data to disk asynchronously. This bypasses disk write bottlenecks, maintaining sub-millisecond latencies.

---

## 3. Redis Persistence Models

Redis supports three persistence options:

```
[1. RDB (Point-in-Time Snapshotting)]
Active Memory ───(fork() child process)───► Copy-on-Write ───► dump.rdb (compact)

[2. AOF (Append-Only File Log)]
Write Command ───► Memory Queue ───(fsync policy)───► appendonly.aof (incremental)
```

### 3.1 RDB (Redis Database Snapshot)
RDB creates compact, point-in-time binary snapshots of the database.
*   *Mechanics*: Redis calls the OS `fork()` command to spawn a child process. The child process reads the memory layout and writes it to a `dump.rdb` file. The main process continues serving client requests using **Copy-on-Write (COW)** page allocations.
*   *Trade-offs*: Fast reloads and minimal runtime overhead. However, if the server crashes between snapshot cycles (e.g. default: 5 minutes), all writes since the last snapshot are lost.

### 3.2 AOF (Append Only File)
AOF logs every write command received by the server to an incremental text file.
*   *fsync Policies*: Governs how often data is flushed to disk:
    1.  `appendfsync always`: fsync on every write command. High durability, but degrades performance due to disk I/O bottlenecks.
    2.  `appendfsync everysec` (Default): fsync once per second. Limits data loss to a maximum of 1 second while maintaining high performance.
    3.  `appendfsync no`: Delegates flushes to the operating system (typically every 30 seconds). High risk of data loss.
*   *AOF Rewrite*: As AOF logs grow, they can consume significant disk space. Redis runs background rewrite cycles to compact the log by reconstructing the minimal command set required to represent the active database state.

### 3.3 Hybrid Persistence (Recommended)
Combines the benefits of both models. The background rewrite writes an RDB snapshot to the start of the AOF file, appending incremental AOF logs. During restarts, Redis loads the RDB preamble quickly, then replays the remaining AOF commands, combining fast load times and minimal data loss.

---

## 4. Hands-on Exercises

1.  Configure a local Redis instance to use hybrid persistence, simulate a crash, and verify data recovery.
2.  Monitor disk I/O write activity and memory consumption on a Redis master node during an AOF rewrite cycle.

---

## 5. Mini-Project: Persistence Configurator & Recovery Script

**Scenario**: You are setting up a production Redis environment. You must configure the persistence parameters in `redis.conf` to use hybrid persistence and write an administrative shell script to verify AOF integrity and repair corruption.

### 1. Production Config Snippet (`redis.conf`)
```ini
# Enable RDB snapshotting schedules
save 900 1
save 300 10
save 60 10000

# Enable Append Only File logging
appendonly yes
appendfilename "appendonly.aof"

# Configure fsync frequency
appendfsync everysec

# Prevent disk write lock blocking during AOF rewrites
no-appendfsync-on-rewrite yes

# Auto-trigger AOF rewrite when size grows by 100% (min size: 64MB)
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Enable Hybrid Persistence
aof-use-rdb-preamble yes
```

### 2. Recovery Shell Script (`verify-recovery.sh`)
```bash
#!/usr/bin/env bash
set -euo pipefail

AOF_FILE="/var/lib/redis/appendonly.aof"

echo "Checking Append-Only File integrity..."

# 1. Run check utility
if redis-check-aof "${AOF_FILE}"; then
    echo "AOF file is healthy."
else
    echo "WARNING: AOF file corruption detected!"
    
    # Create backup copy before attempting repairs
    cp "${AOF_FILE}" "${AOF_FILE}.bak"
    echo "Backup created at ${AOF_FILE}.bak"
    
    # 2. Execute auto-repair (truncates corrupted/incomplete commands at the end)
    echo "Running repair utility..."
    redis-check-aof --fix "${AOF_FILE}"
    
    echo "Repair complete. Please verify database contents after restart."
fi
```

---

## 6. Interview Questions

### Q1: How does the OS copy-on-write (COW) mechanism work during Redis RDB snapshotting? What is its memory overhead?
**Answer**: When Redis calls `fork()`, the operating system creates a child process that shares the same physical memory pages as the parent process. The child process reads the shared pages to write the RDB file. 
If the parent process writes to a memory page during this time, the OS kernel copies that page to a new physical location for the parent, leaving the child's copy untouched. 
**Memory Overhead**: If your application performs heavy writes during a snapshot, the OS will copy many pages, increasing memory consumption by up to 2x.

### Q2: What is the risk of enabling `no-appendfsync-on-rewrite yes` in your Redis configuration?
**Answer**: When an AOF rewrite or RDB snapshot is running, background processes generate heavy disk write I/O. If `no-appendfsync-on-rewrite` is set to `no`, the main Redis thread will attempt to fsync client writes during this time, which can block client requests.
Setting this option to `yes` prevents the main thread from calling fsync during rewrite cycles. However, if the server crashes during a rewrite, you can lose up to 30 seconds of write data (reverting to `appendfsync no` behavior temporarily).

### Q3: Why does AOF loading take longer than RDB loading during database startups?
**Answer**:
*   **RDB**: A compact, binary representation of the database. Redis can read the file and write the data directly to RAM.
*   **AOF**: A text-based log containing individual write commands. To restore state, Redis must run a virtual client to replay every logged command sequentially, which is CPU-intensive and slow for large databases.
