# Module 02: Redis as a Cache Layer & Consistency

## 1. What Problem This Module Solves

High-throughput applications struggle with relational database latency and read limits under peak load. Storing pre-computed queries in a fast memory layer reduces database load. 

However, caching introduces a major systems engineering challenge: **Data Consistency**. If the database changes and the cache is not updated, clients receive stale data. Additionally, caching systems are vulnerable to systemic failures:
*   **Cache Stampede**: Multiple clients query the database on a cache miss concurrently.
*   **Cache Avalanche**: Massive key expirations flood the database.
*   **Cache Penetration**: Non-existent keys hit the database directly.

This module details how to design consistent, resilient caching architectures using Spring Boot.

---

## 2. Why Redis is Used Instead of Alternatives

*   **Over Local JVM Cache (Caffeine/Ehcache)**: While local cache is faster (avoiding network hops), it cannot synchronize state across multiple server nodes. In a multi-node cluster, local caches will drift, serving different data from different servers. Redis provides a centralized, shared cache layer.
*   **Over Disk-Based Datastores**: Disk read I/O introduces millisecond-level latency. Redis, running in memory, resolves operations in sub-milliseconds, supporting tens of thousands of operations per second per node.

---

## 3. Caching Design Patterns

Different system requirements demand different caching patterns:

```
[1. Cache-Aside (Lazy Load)]
Client ───► Read Cache ───(Hit)───► Return Data
Client ───► Read Cache ───(Miss)──► Query DB ──► Write Cache ──► Return

[2. Write-Behind (Write-Back)]
Client ───► Write Cache (Immediate Ack) ──► Queue ──(Asynchronous Flush)──► DB
```

1.  **Cache-Aside (Lazy Loading)**: The application queries the cache. On a miss, it queries the database, writes the result to the cache, and returns it.
    *   *Trade-offs*: Low memory usage (keys cached only when requested), but misses incur a three-step latency penalty (query cache $\rightarrow$ query DB $\rightarrow$ write cache).
2.  **Read-Through**: The application delegates reads to a cache provider. On a miss, the cache provider loads data from the database, writes it to the cache, and returns it.
3.  **Write-Through**: The application writes to the cache. The cache synchronously writes to the database before acknowledging success.
    *   *Trade-offs*: High data consistency, but writes suffer from double-write latency.
4.  **Write-Behind (Write-Back)**: The application writes to the cache, which acknowledges immediately. The cache then flushes the write to the database asynchronously.
    *   *Trade-offs*: High write throughput, but node failures can lose data before it is flushed to the database.
5.  **Refresh-Ahead**: The cache asynchronously reloads active keys before their TTL expires, preventing cache misses.

---

## 4. Spring Cache Abstraction

Spring Boot provides declarative caching annotations that intercept method calls using Spring AOP.

*   `@Cacheable`: Checks the cache before executing the method. On a miss, it runs the method and caches the result.
*   `@CachePut`: Always executes the method and updates the cache with the result.
*   `@CacheEvict`: Removes entries from the cache (e.g. on updates).

### 4.1 Configuring RedisCacheManager

To configure serialization and custom TTLs for different cache regions:

```java
package com.example.redis.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.serializer.Jackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;
import org.springframework.data.redis.serializer.StringRedisSerializer;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

@Configuration
public class CacheConfig {

    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory connectionFactory) {
        // Default cache configuration: 1 hour TTL
        RedisCacheConfiguration defaultCacheConfig = RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofHours(1))
            .disableCachingNullValues()
            .serializeKeysWith(RedisSerializationContext.SerializationPair.fromSerializer(new StringRedisSerializer()))
            .serializeValuesWith(RedisSerializationContext.SerializationPair.fromSerializer(new Jackson2JsonRedisSerializer<>(Object.class)));

        // Custom TTL mappings for specific cache regions
        Map<String, RedisCacheConfiguration> customConfigs = new HashMap<>();
        customConfigs.put("users", defaultCacheConfig.entryTtl(Duration.ofMinutes(15)));
        customConfigs.put("products", defaultCacheConfig.entryTtl(Duration.ofDays(1)));

        return RedisCacheManager.builder(connectionFactory)
            .cacheDefaults(defaultCacheConfig)
            .withInitialCacheConfigurations(customConfigs)
            .build();
    }
}
```

---

## 5. Solving Caching Operational Failures

Under production load, simple caching systems can fail catastrophically:

### 5.1 Cache Stampede (Thundering Herd)
*   **Problem**: A highly requested key (e.g. home page config) expires. Hundreds of concurrent client threads read the miss and query the database at the same time, overloading the database.
*   **Solution**: Implement mutual exclusion locking (using Redis locks) so only a single thread can query the database and reload the cache, while other threads wait or return stale data.

### 5.2 Cache Avalanche
*   **Problem**: A batch of keys is initialized at the same time with the same TTL. They expire simultaneously, sending a wave of read requests to the database.
*   **Solution**: Add a random jitter (e.g., random duration between 1 and 5 minutes) to the TTL of every key on creation.

### 5.3 Cache Penetration
*   **Problem**: A client queries for non-existent IDs (e.g., randomly generated IDs by an attacker). The request misses the cache and hits the database, which returns "not found", bypassing the cache layer entirely.
*   **Solution**: Cache null values with a short TTL (e.g., 5 minutes) or deploy a **Bloom Filter** before the cache to block queries for non-existent IDs.

### 5.4 Hot Key Problem
*   **Problem**: A specific key (e.g. viral product) receives massive traffic. Because this key belongs to a single Redis shard, it saturates that shard's CPU and network capacity, even if other shards are idle.
*   **Solution**: Use a multi-level cache topology: replicate the key in the application node's local L1 cache (Caffeine) for short intervals, avoiding Redis network hits entirely.

---

## 6. Hands-on Exercises

1.  Simulate a Cache Avalanche: Write a script to insert 5,000 keys with identical TTL values, monitor database read rates when they expire, and rewrite the script to add random TTL jitter.
2.  Implement a Bloom Filter using Redisson to validate user IDs before querying the cache.

---

## 7. Mini-Project: Multi-Level L1/L2 Cache with Pub/Sub Sync

**Scenario**: You are building a high-scale user profile service. To mitigate hot key problems, you must deploy a multi-level cache topology:
1.  **L1 Cache**: Local memory (Caffeine) inside each Spring instance (TTL: 1 minute).
2.  **L2 Cache**: Central Redis cache (TTL: 1 hour).
3.  **Synchronization**: When an instance updates a profile, it must invalidate L2 (Redis) and publish an invalidation event over a Redis Pub/Sub channel to notify other Spring instances to evict the key from their local L1 caches.

### 1. Unified Cache Manager Configuration (`multilevel/CacheSyncManager.java`)
```java
package com.example.redis.multilevel;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import java.time.Duration;

@Service
public class MultiLevelCacheService {

    private final StringRedisTemplate redisTemplate;
    private final Cache<String, String> l1Cache;
    private static final String INVALIDATION_CHANNEL = "cache:invalidate:l1";

    public MultiLevelCacheService(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
        
        // 1. Initialize L1 local cache (Caffeine)
        this.l1Cache = Caffeine.newBuilder()
            .expireAfterWrite(Duration.ofMinutes(1))
            .maximumSize(10000)
            .build();
    }

    // Read flow
    public String get(String key) {
        // 1. Check L1 Cache
        String value = l1Cache.getIfPresent(key);
        if (value != null) {
            return value;
        }

        // 2. Check L2 Cache (Redis)
        value = redisTemplate.opsForValue().get(key);
        if (value != null) {
            l1Cache.put(key, value); // Populate L1
            return value;
        }

        return null; // DB query fallback should trigger externally
    }

    // Write flow (Cache Evict & Invalidation Publish)
    public void update(String key, String value) {
        // 1. Update L2 Cache (Redis)
        redisTemplate.opsForValue().set(key, value, Duration.ofHours(1));

        // 2. Local L1 Evict
        l1Cache.invalidate(key);

        // 3. Broadcast invalidation to all other nodes in the cluster
        redisTemplate.convertAndSend(INVALIDATION_CHANNEL, key);
    }

    public void evictLocal(String key) {
        l1Cache.invalidate(key);
    }
}
```

### 2. Pub/Sub Message Listener for Sync
```java
package com.example.redis.multilevel;

import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.stereotype.Component;

@Component
public class CacheInvalidationListener implements MessageListener {

    private final MultiLevelCacheService cacheService;

    public CacheInvalidationListener(MultiLevelCacheService cacheService) {
        this.cacheService = cacheService;
    }

    @Override
    public void onMessage(Message message, byte[] pattern) {
        String keyToEvict = new String(message.getBody());
        // Evict key from this instance's local L1 cache
        cacheService.evictLocal(keyToEvict);
    }
}
```

---

## 8. Interview Questions

### Q1: How does Cache-Aside mitigate the risk of race conditions during updates? Should you update the cache or evict the key?
**Answer**: During updates, you should **evict (delete)** the key from the cache rather than updating it. 
Updating the cache is vulnerable to race conditions: if Update A writes to the database, and then Update B writes to the database, but network latency causes Update B's cache update to arrive before Update A's cache update, the cache will be left with stale data from Update A. Evicting the key forces the next read operation to query the database and reload the cache, ensuring consistency.

### Q2: What is the XFetch algorithm, and how does it prevent Cache Stampede probabilistic failures?
**Answer**: XFetch is a probabilistic early expiration algorithm. When a key is read near its expiration time, the algorithm computes a probability based on read frequency and database execution latency. 
If the probability check succeeds, a single client thread updates the key in the background *before* it actually expires. Other clients continue to read the existing cached value, preventing cache misses and thundering herds.

### Q3: Why is Caffeine used as L1 local memory cache in Spring Boot instead of standard ConcurrentHashMap?
**Answer**: `ConcurrentHashMap` has no built-in eviction policies or size constraints. It will grow indefinitely, eventually triggering JVM OutOfMemory errors. 
Caffeine provides optimized, high-throughput caching structures with configurable eviction policies (e.g. Least Recently Used, Least Frequently Used), size limits, and TTL parameters, ensuring safe memory utilization.
