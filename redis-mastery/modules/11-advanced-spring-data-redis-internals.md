# Module 11: Connection Factories, Lettuce Internals, and Reactive Redis

## 1. What Problem This Module Solves

Standard blocking database drivers assign a dedicated thread to every database connection socket. Under heavy traffic, this process-per-thread model leads to thread context lock contention and socket buffer limits. 

Additionally, reactive Spring WebFlux applications require a fully non-blocking, reactive database driver to prevent blocking execution threads. This module details the difference between **Lettuce** and **Jedis**, explains how Lettuce uses **Netty** event loops, and covers how to write reactive pipelines using `ReactiveRedisTemplate`.

---

## 2. Why Redis is Used Instead of Alternatives

*   **Native Non-blocking Protocols**: Redis's simple, binary protocol (RESP) is easy to parse, allowing client libraries to implement highly optimized, non-blocking multiplexing architectures using Netty.

---

## 3. ConnectionFactory Architecture: Lettuce vs. Jedis

Spring Data Redis supports two Java client drivers: **Lettuce** and **Jedis**.

```
[Jedis Thread Model - Thread-Unsafe / Blocked]
Thread A ───► [ Connection Pool Node ] ───(Locked Conn)───► Redis Server
Thread B ───► [ Connection Pool Node ] ───(Blocked waiting for Conn)

[Lettuce Thread Model - Multiplexed / Non-blocking (Netty)]
Thread A ──┐
Thread B ──┼───► [ Single Shareable Connection ] ───(Netty Event Loop)───► Redis
Thread C ──┘
```

### 3.1 Jedis Driver Architecture
*   *Design*: Thread-unsafe. Individual Jedis instances cannot be shared between multiple threads.
*   *Pooling*: Requires a dedicated connection pool (`GenericObjectPool` from Apache Commons Pool). Under high traffic, threads spend significant CPU cycles waiting to acquire connections from the pool, creating a bottleneck.

### 3.2 Lettuce Driver Architecture (Default)
*   *Design*: Thread-safe and fully non-blocking. It is built on top of the **Netty** network framework.
*   *Connection Sharing*: Multiple application threads share a single Lettuce connection for standard operations (like GET, SET, HASH reads). Lettuce serializes commands and writes them to the TCP socket asynchronously, avoiding connection pooling overhead.
*   *When Pooling is Needed*: Lettuce only requires connection pooling for blocking operations (e.g. `BLPOP`) or transaction blocks (`MULTI`/`EXEC`), which require exclusive use of a connection socket.

---

## 4. Lettuce Internals & Netty Event Loops

Lettuce uses Netty event loops to manage network sockets.
1.  **Netty Channel**: Encapsulates the socket connection.
2.  **EventLoopGroup**: A pool of threads that handle read/write socket events asynchronously. By default, Lettuce allocates a thread pool size equal to the number of CPU cores.
3.  **Command Pipelining**: Lettuce automatically pipelines commands from separate application threads into Netty's outbound write buffers. This reduces the number of system calls and optimizes TCP throughput.

---

## 5. Reactive Redis Programming

Spring WebFlux applications require reactive drivers to maintain non-blocking execution. Spring Data Redis supports this using `ReactiveRedisTemplate`.

### 5.1 Spring Config for Reactive Redis

```java
package com.example.redis.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.ReactiveRedisConnectionFactory;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.ReactiveRedisTemplate;
import org.springframework.data.redis.serializer.Jackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;
import org.springframework.data.redis.serializer.StringRedisSerializer;

@Configuration
public class ReactiveRedisConfig {

    @Bean
    public ReactiveRedisConnectionFactory reactiveRedisConnectionFactory() {
        return new LettuceConnectionFactory("127.0.0.1", 6379);
    }

    @Bean
    public ReactiveRedisTemplate<String, Object> reactiveRedisTemplate(
            ReactiveRedisConnectionFactory factory) {

        StringRedisSerializer keySerializer = new StringRedisSerializer();
        Jackson2JsonRedisSerializer<Object> valueSerializer = new Jackson2JsonRedisSerializer<>(Object.class);

        // Define serialization context for reactive operations
        RedisSerializationContext<String, Object> serializationContext = 
            RedisSerializationContext.<String, Object>newSerializationContext(keySerializer)
                .value(valueSerializer)
                .hashKey(keySerializer)
                .hashValue(valueSerializer)
                .build();

        return new ReactiveRedisTemplate<>(factory, serializationContext);
    }
}
```

---

## 6. Hands-on Exercises

1.  Compare the thread consumption profiles of a Spring application executing 10,000 queries using a Jedis connection pool versus Lettuce connection sharing.
2.  Write a reactive Spring WebFlux handler that uses `ReactiveRedisTemplate` to read a user profile and returns a `Mono<User>`.

---

## 7. Mini-Project: Reactive User Event Stream Processing

**Scenario**: You are building a real-time event pipeline. User click stream data is written to a Redis list. You must write a reactive Spring component that reads the list asynchronously as a stream, processes the events, and publishes metrics without blocking execution threads.

```java
package com.example.redis.reactive;

import org.springframework.data.redis.core.ReactiveRedisTemplate;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import java.time.Duration;

@Service
public class ReactiveStreamService {

    private final ReactiveRedisTemplate<String, Object> reactiveTemplate;
    private static final String EVENT_LIST_KEY = "user:clicks:list";

    public ReactiveStreamService(ReactiveRedisTemplate<String, Object> reactiveTemplate) {
        this.reactiveTemplate = reactiveTemplate;
    }

    // Write event asynchronously (Non-blocking)
    public Mono<Long> publishEvent(String clickEventJson) {
        return reactiveTemplate.opsForList().leftPush(EVENT_LIST_KEY, clickEventJson);
    }

    // Stream and process events reactively (Reactive Pull)
    public Flux<String> consumeEventStream() {
        // Repeatedly pop elements from the list asynchronously
        return Flux.interval(Duration.ofMillis(100))
            .flatMap(tick -> reactiveTemplate.opsForList().rightPop(EVENT_LIST_KEY))
            .cast(String.class)
            .doOnNext(event -> {
                // Execute processing
                System.out.printf("Processed Event Reactively: %s on thread %s\n", 
                    event, Thread.currentThread().getName());
            });
    }
}
```

---

## 8. Interview Questions

### Q1: Why can Lettuce share a single connection socket across multiple threads, while Jedis cannot?
**Answer**: 
*   **Jedis**: Uses a blocking I/O model (standard socket streams). Once a thread writes a command, it must block the socket and wait for the response, meaning connections cannot be shared concurrently.
*   **Lettuce**: Built on Netty, which uses non-blocking I/O multiplexing. Lettuce assigns a unique ID to every command and writes them to the socket asynchronously. When responses arrive on the Netty thread, Lettuce uses the command IDs to resolve the futures and return values to the correct caller threads, allowing a single socket to be shared safely.

### Q2: Under what conditions should you configure connection pooling in Lettuce?
**Answer**: Lettuce only requires connection pooling for:
1.  **Blocking Commands**: Operations like `BLPOP` or `BRPOP` block the connection socket until data is available, preventing other commands from sharing it.
2.  **Transaction Blocks**: Commands like `MULTI`/`EXEC` require an exclusive connection to queue commands sequentially without interference.

### Q3: What is the risk of not managing backpressure when using ReactiveRedisTemplate?
**Answer**: If a publisher generates write commands faster than the Lettuce driver can send them over the network TCP socket, Netty's outbound write queue will accumulate commands. If backpressure is not managed, this queue can grow indefinitely, consuming JVM memory and eventually triggering OutOfMemory errors.
