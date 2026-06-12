# Module 04: Distributed Systems Patterns: Locking, Rate Limiting, and Coordination

## 1. What Problem This Module Solves

In distributed systems, microservice nodes must coordinate operations without a single database bottleneck. 
*   **Race Conditions**: Multiple instances processing the same order must ensure that only one instance handles it at a time. Local JVM locks cannot coordinate across processes.
*   **API Flooding**: Applications must limit the rate of incoming requests per user to prevent resource exhaustion and denial-of-service (DoS) attacks.
*   **Duplicate Submissions**: Networks retry failed requests. Servers must deduplicate incoming actions to prevent double charges.

This module details how to implement robust distributed coordination patterns using Redis.

---

## 2. Why Redis is Used Instead of Alternatives

*   **Over Relational DB Advisory Locks**: While relational databases support advisory locks, acquiring and releasing locks requires heavy disk write transactions, limiting performance. Redis, operating in memory, processes lock operations in sub-milliseconds.
*   **Over ZooKeeper**: ZooKeeper provides strong consistency for locking (using ephemeral nodes), but it has lower throughput and higher deployment complexity compared to Redis. Redis provides high-throughput locking and flexible coordination patterns.

---

## 3. Distributed Locking with Redisson

A naive Redis lock can be implemented using the `SET key value NX PX max_lock_time` command. However, this naive approach is vulnerable to failures: if Client A's processing takes longer than the lock TTL, the lock expires. Client B then acquires the lock. Once Client A finishes, it runs `DEL` and deletes Client B's lock, causing race conditions.

**Redisson** resolves this by introducing the **Watchdog** thread:

```
[Redisson Lock Lifecycle]
Client A ───► Acquires Lock (default lease: 30s) ───► Runs business logic
                 │
                 ▼ (Watchdog Thread)
                 Spawns background task to renew lock 
                 by extending TTL by 30s every 10s.
                 │
Client A ───► Completes logic ───► Releases Lock ───► Stops Watchdog
```

*   **Watchdog Mechanism**: If the client does not specify a lease time, Redisson sets a default lock lease time (30 seconds) and spawns a background thread (the watchdog) to renew the lock every 10 seconds. If the client JVM crashes, the watchdog stops, and the lock expires naturally, preventing deadlocks.

### 3.1 The Redlock Algorithm and Criticisms
The Redlock algorithm secures locks across multiple independent Redis master nodes (e.g. 5 nodes). The client must acquire locks on at least 3 nodes to succeed.
*   *Criticisms (Martin Kleppmann)*: Redlock depends on system clock synchronization. If a node's system clock drifts or experiences a long JVM garbage collection (GC) pause, the lock can be released prematurely, violating safety guarantees.
*   *Design Rule*: Use Redisson's standard locking models for performance. Use Redlock only if you can tolerate clock drift risks and require multi-master redundancy.

---

## 4. Rate Limiting Algorithms

gRPC or HTTP APIs protect resources using rate limiters:

1.  **Token Bucket**: A bucket is filled with tokens at a constant rate. Requests consume tokens. If the bucket is empty, the request is rejected.
2.  **Sliding Window Log**: Stores request timestamps in a Sorted Set (ZSET). It evicts timestamps older than the sliding window, counting the remaining entries to enforce limits.

---

## 5. Hands-on Exercises

1.  Configure a Redisson client lock in a local Spring Boot application and simulate a thread crash to verify that the watchdog stops and the lock is released.
2.  Write a sliding window rate limiter script using Redis CLI and verify throughput limits under load.

---

## 6. Mini-Project: Sliding Window Rate Limiter Middleware

**Scenario**: You are securing an API gateway. You must implement a sliding window rate limiter that limits users to 10 requests per minute. You will write a Lua script to ensure atomic check-and-increment operations, and expose it via a Spring Boot interceptor.

### 1. Rate Limiting Lua Script (`src/main/resources/rate_limit.lua`)
```lua
local rateKey = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local maxLimit = tonumber(ARGV[3])

local clearBefore = now - window

-- 1. Remove timestamps older than the sliding window boundary
redis.call('ZREMRANGEBYSCORE', rateKey, 0, clearBefore)

-- 2. Count active requests within the window
local currentRequests = redis.call('ZCARD', rateKey)

if currentRequests < maxLimit then
    -- 3. Record the current request timestamp
    redis.call('ZADD', rateKey, now, now)
    -- Extend key TTL to keep set active
    redis.call('EXPIRE', rateKey, window / 1000)
    return 1 -- Request allowed
else
    return 0 -- Rate limit exceeded
end
```

### 2. Spring Rate Limiter Service (`src/main/java/com/example/redis/RateLimiterService.java`)
```java
package com.example.redis;

import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.scripting.support.ResourceScriptSource;
import org.springframework.stereotype.Service;
import java.util.Collections;

@Service
public class RateLimiterService {

    private final StringRedisTemplate redisTemplate;
    private final DefaultRedisScript<Long> script;

    public RateLimiterService(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
        
        this.script = new DefaultRedisScript<>();
        this.script.setScriptSource(new ResourceScriptSource(new ClassPathResource("rate_limit.lua")));
        this.script.setResultType(Long.class);
    }

    public boolean isAllowed(String userId, int maxRequests, long windowMillis) {
        String key = "ratelimit:" + userId;
        long now = System.currentTimeMillis();

        Long result = redisTemplate.execute(
            script,
            Collections.singletonList(key),
            String.valueOf(now),
            String.valueOf(windowMillis),
            String.valueOf(maxRequests)
        );

        return result != null && result == 1;
    }
}
```

---

## 7. Interview Questions

### Q1: What is the purpose of Redisson's Lock Watchdog? What problem does it solve?
**Answer**: The Lock Watchdog solves the lock expiry problem. If a client acquires a lock with a fixed TTL, and its business processing takes longer than the TTL (e.g. due to slow DB responses or GC pauses), the lock will expire, allowing other clients to acquire it and causing race conditions. 
The watchdog runs a background thread that periodically renews the lock's expiration lease as long as the client remains active. If the client crashes, the watchdog stops, and the lock expires naturally to prevent deadlocks.

### Q2: Why is the Sliding Window Log rate limiter more accurate than the Fixed Window algorithm?
**Answer**: The Fixed Window algorithm resets counters at fixed time boundaries (e.g., at the start of every minute). An attacker can send their entire rate limit at the end of Minute 1 and another burst at the start of Minute 2, doubling the allowed rate within a short window.
The Sliding Window Log stores individual request timestamps, allowing it to calculate the exact rate dynamically across a moving window (e.g., trailing 60 seconds), preventing burst limit bypasses.

### Q3: What is the main system resource cost of using Redis Sorted Sets (ZSET) for Sliding Window rate limiting? How do you optimize it?
**Answer**: ZSETs are memory-intensive. Storing 64-bit timestamps for millions of requests can quickly saturate Redis memory. 
**Optimization**: Ensure you run `ZREMRANGEBYSCORE` on every write to evict old timestamps, keep the set size small, and set an expiration TTL on the ZSET key so it is deleted when the user is inactive.
