# Spring Data Redis & Advanced Redis Mastery

Welcome to the **Spring Data Redis & Advanced Redis Mastery** course. This repository contains a comprehensive, production-grade syllabus designed for senior software engineers, platform architects, and distributed systems specialists. 

This course moves past basic CRUD operations to focus on low-level serialization mechanics, cache consistency topologies, distributed locking algorithms, pub/sub stream structures, and operations at high scale.

---

## 🎯 Course Objectives

By the end of this course, you will be able to:
1. **Master Spring Data Redis Internals**: Understand how Lettuce multiplexes connections, manage pipeline buffers, and utilize `RedisTemplate` serialization structures.
2. **Design Highly-Consistent Caching Layers**: Solve Cache Stampede, Avalanche, Penetration, and Hot Key problems using multi-level topologies (Redis + local Caffeine).
3. **Write Performant Lua Scripts**: Execute atomic transactions, evaluate custom scripts, and optimize memory allocations (ZipLists, Bitmaps).
4. **Enforce Distributed Coordination**: Implement Redlock algorithms, lock renewals, sliding window rate limiters, and leader election engines.
5. **Architect Real-Time Stream Pipelines**: Manage Redis Streams consumer groups, process acknowledgement frames, and evaluate Kafka/RabbitMQ alternatives.
6. **Implement Secure Distributed Sessions**: Configure session clustering via Spring Session and build high-performance JWT blacklists.
7. **Model Complex Data Relationships**: Design sorted sets leaderboards, secondary indexes, geospatial maps, and time-series pipelines.
8. **Calibrate Persistence & HA Topologies**: Optimize RDB/AOF sync cycles, configure Sentinel quorums, and balance partitions across Redis Cluster shards.
9. **Observe and Operations at Scale**: Monitor slow logs, track memory fragmentation, trace Netty connection pools, and run load testing benchmarks.

---

## 📚 Structured Syllabus & Modules

The curriculum consists of 12 comprehensive, technical modules:

| Module | Topic | File Link |
| :--- | :--- | :--- |
| **01** | Spring Data Redis Fundamentals & Serialization | [01-spring-data-redis-fundamentals.md](./modules/01-spring-data-redis-fundamentals.md) |
| **02** | Redis as a Cache Layer & Consistency | [02-redis-cache-layer.md](./modules/02-redis-cache-layer.md) |
| **03** | Performance Engineering: Pipelining, Transactions, and Lua | [03-performance-engineering.md](./modules/03-performance-engineering.md) |
| **04** | Distributed Systems Patterns: Locking, Rate Limiting, and Coordination | [04-distributed-systems-patterns.md](./modules/04-distributed-systems-patterns.md) |
| **05** | Messaging and Event Processing: Streams & Pub/Sub | [05-messaging-event-processing.md](./modules/05-messaging-event-processing.md) |
| **06** | Spring Session, Authentication, and Token Management | [06-spring-session-authentication.md](./modules/06-spring-session-authentication.md) |
| **07** | Advanced Data Modeling, Leaderboards, and Time-Series | [07-data-modeling-redis.md](./modules/07-data-modeling-redis.md) |
| **08** | Persistence, Durability, and Data Recovery | [08-redis-persistence-reliability.md](./modules/08-redis-persistence-reliability.md) |
| **09** | High Availability: Replication, Sentinel, and Redis Cluster | [09-high-availability.md](./modules/09-high-availability.md) |
| **10** | Observability, Micrometer, and Production Operations | [10-observability-operations.md](./modules/10-observability-operations.md) |
| **11** | Connection Factories, Lettuce Internals, and Reactive Redis | [11-advanced-spring-data-redis-internals.md](./modules/11-advanced-spring-data-redis-internals.md) |
| **12** | Real Production Case Studies | [12-real-production-architectures.md](./modules/12-real-production-architectures.md) |

---

## 🛠️ Local Sandbox Infrastructure Setup

To run the labs, exercises, and performance tests, you will need a docker-compose sandbox containing:
- **Redis Sentinel Cluster**: Three nodes (Master + 2 Replicas) monitored by three Sentinel containers.
- **Prometheus & Grafana**: For metrics monitoring and alerts.

### 1. Docker Compose Configuration (`docker-compose.yml`)

Save the following configuration block as `docker-compose.yml` in your working directory:

```yaml
version: '3.8'

services:
  # Master Node
  redis-master:
    image: redis:7.0.11-alpine
    container_name: redis-master
    command: redis-server --protected-mode no
    ports:
      - "6379:6379"
    networks:
      - redis-net

  # Replica Node 1
  redis-replica-1:
    image: redis:7.0.11-alpine
    container_name: redis-replica-1
    command: redis-server --replicaof redis-master 6379 --protected-mode no
    depends_on:
      - redis-master
    ports:
      - "6380:6379"
    networks:
      - redis-net

  # Replica Node 2
  redis-replica-2:
    image: redis:7.0.11-alpine
    container_name: redis-replica-2
    command: redis-server --replicaof redis-master 6379 --protected-mode no
    depends_on:
      - redis-master
    ports:
      - "6381:6379"
    networks:
      - redis-net

  # Sentinel Node 1
  redis-sentinel-1:
    image: redis:7.0.11-alpine
    container_name: redis-sentinel-1
    command: >
      sh -c "echo 'port 26379' > /etc/sentinel.conf &&
             echo 'sentinel monitor mymaster redis-master 6379 2' >> /etc/sentinel.conf &&
             echo 'sentinel down-after-milliseconds mymaster 5000' >> /etc/sentinel.conf &&
             echo 'sentinel failover-timeout mymaster 60000' >> /etc/sentinel.conf &&
             echo 'sentinel parallel-syncs mymaster 1' >> /etc/sentinel.conf &&
             redis-server /etc/sentinel.conf --sentinel"
    depends_on:
      - redis-master
    ports:
      - "26379:26379"
    networks:
      - redis-net

  # Sentinel Node 2
  redis-sentinel-2:
    image: redis:7.0.11-alpine
    container_name: redis-sentinel-2
    command: >
      sh -c "echo 'port 26379' > /etc/sentinel.conf &&
             echo 'sentinel monitor mymaster redis-master 6379 2' >> /etc/sentinel.conf &&
             echo 'sentinel down-after-milliseconds mymaster 5000' >> /etc/sentinel.conf &&
             echo 'sentinel failover-timeout mymaster 60000' >> /etc/sentinel.conf &&
             echo 'sentinel parallel-syncs mymaster 1' >> /etc/sentinel.conf &&
             redis-server /etc/sentinel.conf --sentinel"
    depends_on:
      - redis-master
    ports:
      - "26380:26379"
    networks:
      - redis-net

  # Sentinel Node 3
  redis-sentinel-3:
    image: redis:7.0.11-alpine
    container_name: redis-sentinel-3
    command: >
      sh -c "echo 'port 26379' > /etc/sentinel.conf &&
             echo 'sentinel monitor mymaster redis-master 6379 2' >> /etc/sentinel.conf &&
             echo 'sentinel down-after-milliseconds mymaster 5000' >> /etc/sentinel.conf &&
             echo 'sentinel failover-timeout mymaster 60000' >> /etc/sentinel.conf &&
             echo 'sentinel parallel-syncs mymaster 1' >> /etc/sentinel.conf &&
             redis-server /etc/sentinel.conf --sentinel"
    depends_on:
      - redis-master
    ports:
      - "26381:26379"
    networks:
      - redis-net

  # Prometheus exporter
  redis-exporter:
    image: oliver006/redis_exporter:v1.51.0-alpine
    container_name: redis-exporter
    environment:
      - REDIS_ADDR=redis://redis-master:6379
    ports:
      - "9121:9121"
    networks:
      - redis-net

networks:
  redis-net:
    driver: bridge
```

---

## 📈 Graduation & System Assessment Rubrics

Course projects are evaluated against four core systems criteria:

### 1. Data Integrity & Cache Consistency (25% Weight)
*   **Optimal Patterns**: Correct use of cache patterns. Implementations must successfully mitigate cache stampede, avalanche, and penetration risks.
*   **Consistency Control**: Proper use of read/write transactions or Lua script synchronization.
*   **Key Design Layout**: Keys must feature logical namespaces, version descriptors, and appropriate TTL configurations.

### 2. Serialization & Driver Efficiency (25% Weight)
*   **Low Allocation Footprint**: Custom serializers must prioritize memory efficiency, avoiding slow reflection arrays.
*   **Connection Tuning**: Leverage Lettuce's reactive non-blocking execution models. Correct setup of thread pools and event loop groups.
*   **No Blocking Operations**: Prevent execution of blocking commands (e.g. `KEYS`) on the main Redis thread loop.

### 3. Distributed Architecture & Coordination (25% Weight)
*   **Reliable Locking**: Implementing locking mechanisms using Redisson, handling watchdog auto-renewals and release leases.
*   **Rate Limiting Accuracy**: Token bucket or sliding window limiters must execute atomically (via Lua scripts), preventing race conditions under high concurrent loads.
*   **Stream Processing Hygiene**: Streams must run under consumer group controls, processing failures, and resolving pending un-ACKed messages.

### 4. Operations & Observability (25% Weight)
*   **Actuator Integration**: Metrics exposed through Spring Boot Actuator/Micrometer configurations.
*   **Capacity Modeling**: Proper choice of eviction policies (e.g., volatile-lru, allkeys-lru) based on memory footprints.
*   **Troubleshooting Capability**: Logs must capture slow queries, memory fragmentation, and database error states.

---

## 📚 Recommended Background Reading

For deeper study of Redis internals and Spring bindings:
*   [Spring Data Redis Reference Guide](https://docs.spring.io/spring-data/redis/docs/current/reference/html/)
*   [Redis Command Reference Documentation](https://redis.io/commands/)
*   [Distributed Systems Patterns: Redlock Spec](https://redis.io/docs/manual/patterns/distributed-locks/)

Let's begin! Access [Module 01: Spring Data Redis Fundamentals & Serialization](./modules/01-spring-data-redis-fundamentals.md) to start your learning journey.
