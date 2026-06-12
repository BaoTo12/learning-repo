# Module 01: Spring Data Redis Fundamentals & Serialization

## 1. What Problem This Module Solves

Spring applications require a thread-safe, connection-pooled, and structured framework to interact with Redis. Raw database driver clients (like Lettuce or Jedis) require manual socket management, low-level byte array encoding, and manual thread synchronization. 

Spring Data Redis solves this by introducing high-level template abstractions (`RedisTemplate` and `StringRedisTemplate`) and mapping annotations (`@RedisHash`). This module establishes a strong architectural foundation by explaining driver execution paths, detailing serialization trade-offs, and providing a clean strategy for schema namespacing and TTL management.

---

## 2. Why Redis is Used Instead of Alternatives

In Spring applications, Redis is chosen over alternative datastores for specific reasons:

```
[Local JVM Memory (Caffeine/Map)]     [Memcached]                    [Redis]
┌──────────────────────────────┐     ┌────────────────────────┐     ┌────────────────────────┐
│ High Speed (No network hop)  │     │ Distributed Key-Value  │     │ Distributed Key-Value  │
│ Lacks cluster synchronization│     │ No native collections  │     │ Rich Data Structures   │
│ Limits scale to single JVM   │     │ No persistence         │     │ Persistence & Repl     │
└──────────────────────────────┘     └────────────────────────┘     └────────────────────────┘
```

*   **Over Local Memory (e.g., Caffeine, ConcurrentHashMap)**: Local memory is limited to a single JVM instance. In clustered Spring applications, local caches will drift, causing consistency issues. Redis provides a centralized, shared cache layer that ensures all instances read the same state.
*   **Over Memcached**: While Memcached is a fast key-value store, it is limited to simple string values and lacks native data structures (like Hashes, Sets, or Sorted Sets). Redis allows processing complex structures directly on the database engine, avoiding network read-modify-write loops. Additionally, Redis supports persistence, master-slave replication, and high-availability clustering.

---

## 3. Trade-offs and Limitations

*   **Cost & Memory Limits**: Redis is entirely memory-bound. RAM is significantly more expensive than SSD storage. Storing cold, historical datasets in Redis is an expensive anti-pattern.
*   **Single-Threaded Core**: Redis's main event execution loop is single-threaded. Running complex or blocking operations (such as the `KEYS` command or heavy Lua scripts) blocks the entire server, halting all incoming requests.
*   **Asynchronous Replication Data Loss**: Master-slave synchronization is asynchronous. If the master node crashes immediately after acknowledging a write but before replicating it to slaves, that write is lost, violating strict consistency guarantees.

---

## 4. Common Mistakes and Anti-patterns

*   **Using Default JDK Serialization**: Spring Data Redis's default serializer is `JdkSerializationRedisSerializer`. This serializer writes the fully qualified Java class name and metadata into every key/value. This bloats memory usage by up to 5-10x and makes the database inaccessible to non-Java applications.
*   **No TTL Policy**: Setting keys without a Time-To-Live (TTL) or eviction policy will eventually saturate memory, causing Redis to reject writes (out-of-memory errors).
*   **Executing Blocking Commands**: Running `KEYS *` in production to search for namespace keys triggers an $O(N)$ scan across all records. In large databases, this stalls execution for seconds, triggering connection timeouts in client applications.

---

## 5. When NOT to Use Redis

*   **Relational Querying**: If your application queries data using complex, multi-table joins or requires dynamic ad-hoc filtering on multiple attributes, use a relational database (like PostgreSQL).
*   **ACID Compliance**: If your domain requires strict multi-document ACID transactions across decoupled tables (such as ledger booking double-entry accounting), use a transactional database (PostgreSQL or MongoDB).
*   **Archiving Cold Data**: For large, low-access datasets (e.g. audit logs), use cheap block storage (S3) or a document store (MongoDB).

---

## 6. Spring Data Redis Template Architecture

Spring Data Redis abstracts driver connections using the `RedisConnectionFactory` interface, with **Lettuce** as the default driver. It exposes two primary template abstractions:

1.  **`RedisTemplate<K, V>`**: A generic helper class that handles serialization and deserialization of arbitrary Java objects.
2.  **`StringRedisTemplate`**: A specialized subclass of `RedisTemplate` that simplifies string-to-string operations, enforcing UTF-8 `StringRedisSerializer` codecs for keys and values.

---

## 7. Serialization Mechanisms & Strategies

The choice of serializer directly controls memory footprint, CPU overhead, and language compatibility.

| Serializer Strategy | Memory Footprint | CPU Overhead | Language Interoperability |
| :--- | :--- | :--- | :--- |
| **JDK Serializer** | Extremely High (contains class metadata). | Moderate. | Zero (Java only). |
| **Jackson JSON** | Moderate (keys and values in plaintext JSON). | High (requires heavy JSON parsing). | High (supported by all languages). |
| **String Serializer** | Low (raw bytes). | Minimal. | High. |
| **Protobuf / MessagePack**| Very Low (compact binary serialization). | Low. | High. |

### 7.1 Custom RedisTemplate Configuration

The following Spring configuration class replaces the default JDK serializer with a custom Jackson JSON serializer:

```java
package com.example.redis.config;

import com.fasterxml.jackson.annotation.JsonAutoDetect;
import com.fasterxml.jackson.annotation.PropertyAccessor;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.jsontype.impl.LaissezFaireSubTypeValidator;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.serializer.Jackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.StringRedisSerializer;

@Configuration
public class RedisConfig {

    @Bean
    public RedisTemplate<String, Object> redisTemplate(RedisConnectionFactory connectionFactory) {
        RedisTemplate<String, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(connectionFactory);

        // 1. Configure Jackson Object Mapper
        ObjectMapper om = new ObjectMapper();
        om.setVisibility(PropertyAccessor.ALL, JsonAutoDetect.Visibility.ANY);
        // Enable default typing to preserve type information in JSON
        om.activateDefaultTyping(LaissezFaireSubTypeValidator.instance, ObjectMapper.DefaultTyping.NON_FINAL);

        Jackson2JsonRedisSerializer<Object> jacksonSerializer = new Jackson2JsonRedisSerializer<>(om, Object.class);

        // 2. Enforce UTF-8 String Serializer for keys to keep them readable in CLI
        StringRedisSerializer stringSerializer = new StringRedisSerializer();

        template.setKeySerializer(stringSerializer);
        template.setHashKeySerializer(stringSerializer);

        // 3. Apply Jackson serialization for values
        template.setValueSerializer(jacksonSerializer);
        template.setHashValueSerializer(jacksonSerializer);

        template.afterPropertiesSet();
        return template;
    }
}
```

---

## 8. Key Design Strategies & Repository Abstraction

### 8.1 Key Namespacing & Versioning

To organize keys and prevent collisions, enforce a structured naming pattern:

$$\text{Format}: \text{app\_name} : \text{domain} : \text{schema\_version} : \text{unique\_id} : \text{property}$$
$$\text{Example}: \text{billing} : \text{invoice} : \text{v1} : \text{INV-998877} : \text{status}$$

Including a schema version (e.g. `v1` or `v2`) allows you to modify entity models without corrupting existing cache records.

### 8.2 Repository Abstraction (`@RedisHash`)

Spring Data Redis supports a repository abstraction mapping objects to Redis Hashes:

```java
package com.example.redis.repository;

import org.springframework.data.annotation.Id;
import org.springframework.data.redis.core.RedisHash;
import org.springframework.data.redis.core.TimeToLive;
import org.springframework.data.repository.CrudRepository;
import java.io.Serializable;

@RedisHash(value = "billing:invoice:v1")
public class Invoice implements Serializable {

    @Id
    private String id;
    
    private Double amount;
    private String status;

    @TimeToLive
    private Long ttlSeconds; // Dynamically sets TTL on save

    // Getters and Setters
}
```

*Limitations of `@RedisHash`*: Spring Data Repositories create secondary index sets to track entities. This can generate significant write amplification (creating multiple keys and sets under the hood for a single save operation), increasing memory consumption and network overhead.

---

## 9. Interview Questions

### Q1: Why is JdkSerializationRedisSerializer considered an anti-pattern for production caches?
**Answer**: JDK serialization writes the fully qualified Java class names, package structures, and serialization headers into every key-value byte array. This metadata often dwarfs the actual business payload, wasting memory. Furthermore, JDK serialization is insecure (vulnerable to deserialization attacks) and makes the keys unreadable to non-Java applications, preventing interoperability.

### Q2: What is the difference between RedisTemplate and StringRedisTemplate?
**Answer**: `RedisTemplate` is a generic helper class that uses `JdkSerializationRedisSerializer` by default for both keys and values. 
`StringRedisTemplate` is a specialized subclass configured to use `StringRedisSerializer` (UTF-8) for both keys and values. It is cleaner and more readable for key-value string operations.

### Q3: How does Spring Data Redis's @TimeToLive annotation work? Is its accuracy guaranteed?
**Answer**: When you save an entity annotated with `@RedisHash`, Spring reads the field annotated with `@TimeToLive` and runs an explicit `EXPIRE` command on the primary hash key.
The accuracy is **not** guaranteed for application-level lifecycle listeners (like `@EventListener`). Spring tracks expirations by subscribing to Redis Keyspace Events. Because Redis keyspace notifications are delivered over Pub/Sub, they are fire-and-forget: if the Spring application is offline or restarting when a key expires, it will miss the event, leading to stale references in secondary indexes.

---

## 10. Hands-on Exercises

1.  Inspect a key saved by the default `@RedisHash` repository in the Redis CLI using `HGETALL` and describe the fields created by Spring Data Redis.
2.  Write a custom serializer using **MessagePack** and configure a `RedisTemplate` to use it.

---

## 11. Mini-Project: Serialization Performance Benchmarker

**Scenario**: You must evaluate different serialization strategies (JDK, JSON, and custom String formats) to optimize memory footprint and serialization times.

Implement a Spring Boot benchmark controller:

```java
package com.example.redis.project;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.bind.annotation.*;
import java.io.Serializable;
import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/benchmark")
public class BenchmarkController {

    @Autowired
    private RedisTemplate<String, Object> jsonRedisTemplate;

    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    public static class SamplePayload implements Serializable {
        public String userId = "usr-1200389";
        public String name = "Johnathan Doe";
        public double balance = 150000.45;
        public long timestamp = System.currentTimeMillis();
    }

    @PostMapping("/run")
    public Map<String, Object> runBenchmark() {
        SamplePayload payload = new SamplePayload();
        int iterations = 1000;

        // 1. Benchmark Jackson JSON template
        Instant startJson = Instant.now();
        for (int i = 0; i < iterations; i++) {
            jsonRedisTemplate.opsForValue().set("bench:json:" + i, payload, Duration.ofMinutes(5));
        }
        long durationJson = Duration.between(startJson, Instant.now()).toMillis();

        // 2. Benchmark Raw String serialization
        Instant startRaw = Instant.now();
        for (int i = 0; i < iterations; i++) {
            String value = String.format("userId=%s,name=%s,balance=%.2f,ts=%d", 
                payload.userId, payload.name, payload.balance, payload.timestamp);
            stringRedisTemplate.opsForValue().set("bench:string:" + i, value, Duration.ofMinutes(5));
        }
        long durationRaw = Duration.between(startRaw, Instant.now()).toMillis();

        Map<String, Object> results = new HashMap<>();
        results.put("Jackson JSON time (ms)", durationJson);
        results.put("Raw String serialization time (ms)", durationRaw);
        return results;
    }
}
```
