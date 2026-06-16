# Module 10: Observability, Micrometer, and Production Operations

## 1. What Problem This Module Solves

Redis is single-threaded at its core, meaning any slow execution blocks the entire database. If a database issue arises—such as memory fragmentation, connection exhaustion, slow operations, or high eviction rates—identifying the cause requires real-time metrics and tracing. 

Without automated observability, diagnosing connection pool exhaustion, memory saturation (Out of Memory), or sudden latency spikes is impossible. This module covers how to monitor Redis using **Spring Boot Actuator**, **Micrometer**, and native diagnostic commands.

---

## 2. Why Redis is Used Instead of Alternatives

*   **Low-Overhead Metrics**: Redis keeps operational statistics inside memory arrays. Running diagnostic commands like `INFO` or `SLOWLOG` consumes minimal CPU cycles, allowing you to monitor metrics under high load without degrading performance.

---

## 3. Core Redis Metrics to Monitor

When monitoring Redis in production, track these key metrics:

```
                          ┌──────────────────────────┐
                          │    Redis Metrics Engine  │
                          └────────────┬─────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
   [Memory Metrics]            [Connection Metrics]           [Keyspace Metrics]
   - used_memory               - connected_clients            - evicted_keys
   - mem_fragmentation_ratio   - blocked_clients              - expired_keys
   - active_defrag             - instantaneous_ops/sec        - hit/miss ratio
```

### 3.1 Memory Metrics
*   **`used_memory`**: The total number of bytes allocated by Redis using its memory allocator (typically Jemalloc).
*   **`used_memory_rss`**: Resident Set Size. The total number of bytes allocated by the operating system kernel to the Redis process.
*   **`mem_fragmentation_ratio`**: Calculated as:
    
    $$\text{Fragmentation Ratio} = \frac{\text{used\_memory\_rss}}{\text{used\_memory}}$$

    *   *Interpretation*: 
        *   A ratio $> 1.5$ indicates high memory fragmentation. The operating system has allocated memory blocks that are sparse, wasting RAM.
        *   A ratio $< 1.0$ indicates that the system is running out of physical RAM and has started swapping memory to disk, causing high latency.
    *   *Mitigation*: Enable active defragmentation in `redis.conf`:
        ```ini
        activedefrag yes
        active-defrag-ignore-bytes 100mb
        active-defrag-threshold-lower 10
        ```

### 3.2 Connection & Traffic Metrics
*   **`connected_clients`**: The number of active client socket connections. Connection spikes can indicate connection leaks in client applications.
*   **`blocked_clients`**: The number of clients blocked waiting on blocking operations (e.g. `BLPOP`, `BRPOP`, `bzpopmin`).
*   **`instantaneous_ops_per_sec`**: The number of commands processed per second.

### 3.3 Keyspace & Eviction Metrics
*   **`evicted_keys`**: The number of keys evicted due to memory limits (`maxmemory`). High eviction rates indicate that your memory allocation is too small for the dataset.
*   **`keyspace_hits` & `keyspace_misses`**: Track the cache hit ratio:
    
    $$\text{Hit Ratio} = \frac{\text{keyspace\_hits}}{\text{keyspace\_hits} + \text{keyspace\_misses}}$$

    A low hit ratio indicates stale cache keys, incorrect TTL configurations, or cache penetration.

---

## 4. Spring Boot Actuator & Micrometer Integration

Micrometer integrates with Spring Boot Actuator to collect and export Redis metrics to monitoring backends (like Prometheus).

### 4.1 Dependency Setup (`pom.xml`)
```xml
<dependencies>
    <!-- Core Actuator -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-actuator</artifactId>
    </dependency>
    <!-- Micrometer Prometheus Exporter -->
    <dependency>
        <groupId>io.micrometer</groupId>
        <artifactId>micrometer-registry-prometheus</artifactId>
    </dependency>
</dependencies>
```

### 4.2 Application Configuration (`application.properties`)
```properties
# Enable Actuator endpoints
management.endpoints.web.exposure.include=health,info,metrics,prometheus
management.endpoint.health.show-details=always

# Enable Micrometer to collect Lettuce driver connection metrics
management.metrics.enable.lettuce=true
```

### 4.3 Custom Cache Hit/Miss Telemetry Service
You can write custom telemetry code to log cache hits and misses:

```java
package com.example.redis.observability;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Service;

@Service
public class MetricTrackerService {

    private final Counter cacheHitCounter;
    private final Counter cacheMissCounter;

    public MetricTrackerService(MeterRegistry registry) {
        // Initialize Micrometer counters
        this.cacheHitCounter = Counter.builder("cache.operations")
            .tag("status", "hit")
            .description("Total number of cache hits")
            .register(registry);

        this.cacheMissCounter = Counter.builder("cache.operations")
            .tag("status", "miss")
            .description("Total number of cache misses")
            .register(registry);
    }

    public void recordHit() {
        cacheHitCounter.increment();
    }

    public void recordMiss() {
        cacheMissCounter.increment();
    }
}
```

---

## 5. Memory Management & Eviction Policies

When Redis memory usage reaches the `maxmemory` limit, it evicts keys based on the configured **Eviction Policy**:

| Policy Name | Description | Best Used For |
| :--- | :--- | :--- |
| **`noeviction`** | Default. Rejects all write commands, returning out-of-memory errors. Reads continue to work. | Transactional databases where data loss is unacceptable. |
| **`allkeys-lru`** | Evicts the Least Recently Used (LRU) keys across the entire database. | Standard web application caches. |
| **`volatile-lru`** | Evicts the Least Recently Used (LRU) keys among keys configured with a TTL. | Hybrid databases containing both persistent and cached keys. |
| **`allkeys-lfu`** | Evicts the Least Frequently Used (LFU) keys across the entire database. | Caching systems where key popularity changes slowly. |
| **`volatile-ttl`** | Evicts keys with the shortest remaining TTL. | Caches where key lifetime dictates importance. |

---

## 6. Dynamic Diagnostics & Slow Logs

### 6.1 Diagnostic Commands
*   `INFO`: Returns comprehensive server statistics (memory, CPU, connections, cluster state).
*   `MONITOR`: Real-time stream of every command processed by the server. **Warning**: Do not run `MONITOR` in busy production environments, as logging every command can degrade performance by up to 50%.
*   `CLIENT LIST`: Lists all connected client sockets with details on idle times, buffers, and flags.

### 6.2 Slow Log Configuration
Redis logs commands that exceed execution limits:
*   `slowlog-log-slower-than 10000`: Logs commands taking longer than 10,000 microseconds (10 milliseconds).
*   `slowlog-max-len 128`: The maximum number of entries kept in the slow log queue.

Query the slow log using the CLI:
```bash
# Get the 10 slowest commands
SLOWLOG GET 10
```

---

## 7. Hands-on Exercises

1.  Write a script to parse the output of the `INFO memory` command and calculate the memory fragmentation ratio.
2.  Simulate a memory saturation event and monitor eviction metrics using Grafana or the command line.

---

## 8. Mini-Project: Prometheus Metrics Exporter & Alerting Engine

**Scenario**: You must monitor a production Redis instance. You will write a Spring Boot component that:
1.  Connects to the database and collects memory and connection metrics.
2.  Publishes alerts if memory usage exceeds 85% of `maxmemory` or if the fragmentation ratio exceeds 1.8.

```java
package com.example.redis.observability;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import java.util.Properties;

@Component
public class RedisAlertEngine {

    private final StringRedisTemplate redisTemplate;

    public RedisAlertEngine(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    @Scheduled(fixedDelay = 15000) // Run checks every 15 seconds
    public void monitorMetrics() {
        // Fetch INFO command output
        Properties info = redisTemplate.getConnectionFactory()
            .getConnection()
            .info("memory");

        if (info == null) {
            return;
        }

        long maxMemory = Long.parseLong(info.getProperty("maxmemory", "0"));
        long usedMemory = Long.parseLong(info.getProperty("used_memory", "0"));
        double fragmentation = Double.parseDouble(info.getProperty("mem_fragmentation_ratio", "1.0"));

        // 1. Check Memory Thresholds
        if (maxMemory > 0) {
            double memoryUsagePct = ((double) usedMemory / maxMemory) * 100;
            if (memoryUsagePct > 85.0) {
                System.err.printf("ALERT: Redis memory usage is critical: %.2f%% (%d of %d bytes)\n",
                    memoryUsagePct, usedMemory, maxMemory);
            }
        }

        // 2. Check Memory Fragmentation
        if (fragmentation > 1.8) {
            System.err.printf("ALERT: High Redis memory fragmentation: %.2f. Consider running Active Defrag.\n",
                fragmentation);
        }
    }
}
```

---

## 9. Interview Questions

### Q1: What is memory fragmentation? Why does it occur in Redis, and how do you resolve it?
**Answer**: Memory fragmentation occurs when the memory allocator (Jemalloc) allocates sparse memory blocks that contain gaps of unused bytes. It occurs because Redis keys are created and deleted dynamically, leaving empty holes in page allocations that Jemalloc cannot release back to the operating system easily.
**Resolution**: Enable active defragmentation (`activedefrag yes`). This forces Redis to scan memory, copy active objects to contiguous pages, and release the fragmented pages back to the operating system.

### Q2: Why is the MONITOR command dangerous to run in a busy production environment?
**Answer**: The `MONITOR` command streams every command processed by the Redis server to the client socket. 
Because writing to the socket is blocking, the single-threaded event loop must block to write command details to the socket buffer, which can degrade Redis throughput by up to 50% under heavy traffic.

### Q3: What happens to writes when Redis memory usage hits maxmemory and the eviction policy is set to volatile-lru, but all keys have no TTL?
**Answer**: If the eviction policy is set to `volatile-lru` (which only evicts keys configured with a TTL) and all keys have no TTL, Redis cannot find any keys to evict. Under this condition, it behaves like the `noeviction` policy: it rejects all write commands, returning out-of-memory errors (`OOM command not allowed when used memory > 'maxmemory'`).
