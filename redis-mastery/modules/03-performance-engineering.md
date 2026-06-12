# Module 03: Performance Engineering: Pipelining, Transactions, and Lua

## 1. What Problem This Module Solves

Redis is fast, resolving operations in microseconds. However, network Round-Trip Time (RTT) between the application and the Redis server is typically in milliseconds. Sending commands sequentially forces the application to wait for network round-trips, introducing latency.

Additionally, executing multiple dependent commands is vulnerable to race conditions: another client can modify a key between command runs. This module explains how to optimize network and database engine performance using **Pipelining**, **Transactions**, and **Lua Scripting**.

---

## 2. Why Redis is Used Instead of Alternatives

*   **Over Relational DB Stored Procedures**: Relational databases (like PostgreSQL) support PL/pgSQL procedures, but they run on heavy disk-based structures with complex locking models. Redis's single-threaded event loop executes Lua scripts in memory, ensuring rapid, non-blocking execution.
*   **Over Client-Side Synchronization (JVM locks)**: JVM-level locks only synchronize threads within a single JVM instance. They cannot protect shared resources in clustered applications. Redis transactions and Lua scripts provide atomic primitives across clustered application nodes.

---

## 3. Performance Features & Optimization

### 3.1 Pipelining
Pipelining allows the client to write multiple commands to the socket without waiting for replies. The server processes all commands sequentially and returns the combined response block, reducing RTT overhead.

```
[Sequential Commands - 4 RTTs]
Client ───(Command 1)───► Server (Processes) ◄───(Reply 1)─── Client
Client ───(Command 2)───► Server (Processes) ◄───(Reply 2)─── Client

[Pipelined Commands - 1 RTT]
Client ───(Write Cmd 1, Cmd 2, Cmd 3)───► Server (Processes all)
Client ◄──(Combined Reply 1, 2, 3)────── Server
```

### 3.2 Transactions (`MULTI`/`EXEC`)
Redis supports basic transaction blocks:
1.  `MULTI`: Marks the start of a transaction block. Subsequent commands are queued.
2.  `EXEC`: Executes all queued commands sequentially.
3.  `WATCH`: Provides optimistic locking. Monitors keys for changes. If a watched key is modified by another client before `EXEC` runs, the transaction fails and returns null.

*Crucial Limitation*: Redis transactions do not support rollbacks. If a command fails during execution (e.g. key type mismatch), the other queued commands will still execute and commit.

### 3.3 Lua Scripting
For complex operations that require conditional logic or atomic execution, use Lua scripts. The Redis engine executes the script atomically, blocking all other commands during execution to prevent race conditions.

---

## 4. Memory Optimizations & Big Keys

### 4.1 Internal Memory Representations
Redis uses memory-efficient structures under the hood:
*   **ZipList**: A compact, doubly linked list representation optimized for small collections (hashes, lists, sorted sets). It stores elements contiguously in memory, avoiding pointer overhead.
*   **Hashtable/SkipList**: Redis automatically upgrades a ZipList to a standard Hashtable or SkipList once the collection size exceeds limits (e.g., `hash-max-ziplist-entries` defaults to 512). Upgraded structures consume significantly more RAM due to pointer allocations.

### 4.2 Big Keys Detection and Resolution
A **Big Key** is a key containing large payloads (e.g., String keys over 1MB, or Hashes/Sets containing over 10,000 elements).
*   *Risks*: Reading big keys consumes significant network bandwidth. Deleting big keys using the `DEL` command blocks Redis's main thread, stalling the database.
*   *Solution*: Scan for big keys using `redis-cli --bigkeys`. Use `UNLINK` instead of `DEL` to delete big keys. `UNLINK` removes the key from the keyspace immediately and reclaims memory asynchronously in a background thread.

---

## 5. Hands-on Exercises

1.  Benchmark the performance difference between sending 5,000 sequential `SET` commands versus a pipelined batch.
2.  Write a Lua script that increments a user's login counter and updates their last login timestamp, ensuring both operations run atomically.

---

## 6. Mini-Project: Atomic Inventory Allocator via Lua

**Scenario**: You are building a flash sale service. You must allocate stock to users atomically. The system must:
1.  Check if the stock key exists and contains sufficient quantity.
2.  If yes, decrement the stock and record the user's ID in an allocation set.
3.  If no, return an error code.
This must run atomically to prevent overselling.

### 1. Lua Allocation Script (`src/main/resources/allocate.lua`)
```lua
local stockKey = KEYS[1]
local allocSet = KEYS[2]
local userId = ARGV[1]
local quantity = tonumber(ARGV[2])

-- 1. Read current stock
local currentStock = redis.call('GET', stockKey)
if not currentStock then
    return -1 -- Stock key does not exist
end

currentStock = tonumber(currentStock)
if currentStock < quantity then
    return 0 -- Insufficient stock
end

-- 2. Decrement stock and record allocation
redis.call('DECRBY', stockKey, quantity)
redis.call('SADD', allocSet, userId)

return 1 -- Success
```

### 2. Spring Service Implementation (`src/main/java/com/example/redis/StockService.java`)
```java
package com.example.redis;

import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.scripting.support.ResourceScriptSource;
import org.springframework.stereotype.Service;
import java.util.Arrays;
import java.util.List;

@Service
public class StockService {

    private final StringRedisTemplate redisTemplate;
    private final DefaultRedisScript<Long> script;

    public StockService(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
        
        // Load and compile the Lua script
        this.script = new DefaultRedisScript<>();
        this.script.setScriptSource(new ResourceScriptSource(new ClassPathResource("allocate.lua")));
        this.script.setResultType(Long.class);
    }

    public boolean allocateStock(String sku, String userId, int qty) {
        String stockKey = "stock:" + sku;
        String allocSet = "allocations:" + sku;

        List<String> keys = Arrays.asList(stockKey, allocSet);
        
        // Execute Lua script atomically on Redis server
        Long result = redisTemplate.execute(script, keys, userId, String.valueOf(qty));

        if (result == null) {
            return false;
        }

        if (result == -1) {
            throw new IllegalArgumentException("Product stock tracker does not exist");
        }

        return result == 1; // Return true if allocation succeeded
    }
}
```

---

## 7. Interview Questions

### Q1: Why doesn't Redis support standard ACID transactions with rollback capabilities?
**Answer**: Redis prioritizes performance and simplicity. Supporting rollbacks requires complex lock management, transaction state tracking, and recovery logs (write-ahead logs), which would increase CPU overhead and latency. Since most transaction failures are caused by syntax or type mismatches that can be caught during development, Redis queues commands and executes them without rollback checks.

### Q2: What is the difference between DEL and UNLINK? When should you use one over the other?
**Answer**:
*   `DEL`: Removes the key and immediately reclaims the allocated memory. If the key is large (e.g. a Set with 1 million elements), reclaiming memory blocks the single-threaded event loop, stalling other commands.
*   `UNLINK`: Removes the key from the keyspace namespace immediately, but reclaims the allocated memory asynchronously in a background thread, preventing thread stalls.
**Rule**: Use `DEL` for small keys. Use `UNLINK` for large keys.

### Q3: Why is running Lua scripts on Redis considered atomic? What is the risk of executing slow Lua scripts?
**Answer**: Because Redis uses a single-threaded event execution loop, once a Lua script starts running, Redis blocks all other incoming commands until the script completes, guaranteeing atomic execution.
**Risk**: If a Lua script runs slow (e.g., containing complex loops or parsing large collections), it blocks all other requests to the Redis instance, causing connection timeouts in client applications.
