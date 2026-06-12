# High-Performance JPA and Hibernate

Welcome to the **High-Performance JPA and Hibernate** course. This repository contains a comprehensive, production-focused syllabus designed for senior software engineers, platform architects, and Java developers who build, tune, and operate microservices using JPA/Hibernate.

This course is based on Part II of Vlad Mihalcea's *High-Performance Java Persistence*. It covers connection monitoring, custom mapping types, identifier generation optimizers, bidirectional association tuning, dirty checking enhancement, batch inserts/updates/deletes, N+1 resolution, Second-Level (L2) cache concurrency strategies, and concurrency control using explicit database lock modes.

---

## 🎯 Course Objectives

By the end of this course, you will be able to:
1. **Monitor Connections**: Track JPA connection lease allocations, configure parameters logging via DataSource-proxy, and analyze execution times.
2. **Optimize Identifiers**: Implement pooled and pooled-lo identifier generators to reduce sequence query network round-trips.
3. **Map Relationships Efficiently**: Correctly configure unidirectional and bidirectional associations, avoiding common memory leaks in ordered lists.
4. **Tune Hibernate Flushing**: Configure `FlushMode` to prevent write latency issues and control persistence context sizes.
5. **Optimize Dirty Checking**: Configure dirty tracking bytecode enhancement to bypass reflection-based checking.
6. **Implement Batching**: Write high-performance batch updates, inserts, and deletes, resolving JDBC batching limits.
7. **Solve the N+1 Query Problem**: Profile and eliminate the N+1 query problem, write clean DTO projections, and avoid Open Session in View (OSIV) anti-patterns.
8. **Enforce L2 Caching**: Configure Redis or Ehcache with read-write soft locking and transactional caching strategies, avoiding stale data.
9. **Control Concurrency**: Implement optimistic (implicit and versionless) and pessimistic lock modes (timeouts, scopes).

---

## 📚 Structured Syllabus & Modules

The curriculum consists of 8 comprehensive, technical modules:

| Module | Topic | File Link |
| :--- | :--- | :--- |
| **01** | Connection Management and Monitoring | [01-connection-monitoring.md](./modules/01-connection-monitoring.md) |
| **02** | Mapping Types and Identifier Optimizers | [02-types-identifiers.md](./modules/02-types-identifiers.md) |
| **03** | Relationships Mapping & Inheritance | [03-relationships-inheritance.md](./modules/03-relationships-inheritance.md) |
| **04** | Flushing Mechanics & Dirty Checking | [04-flushing-dirty-checking.md](./modules/04-flushing-dirty-checking.md) |
| **05** | High-Performance JPA Batching | [05-jpa-batching.md](./modules/05-jpa-batching.md) |
| **06** | Fetching Strategies & N+1 Resolution | [06-fetching-strategies.md](./modules/06-fetching-strategies.md) |
| **07** | Second-Level (L2) Caching | [07-second-level-caching.md](./modules/07-second-level-caching.md) |
| **08** | JPA Concurrency & Explicit Locking | [08-concurrency-locking.md](./modules/08-concurrency-locking.md) |

---

## 🛠️ Local Sandbox Infrastructure Setup

To run the labs, compile test stubs, and practice cache concurrency validation, you will need PostgreSQL and a Redis container (for L2 cache integration).

Save the following configuration block as `docker-compose.yml` in your working directory:

```yaml
version: '3.8'

services:
  # Database Storage
  postgres:
    image: postgres:15-alpine
    container_name: jpa-postgres
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=jpa_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    networks:
      - jpa-net

  # Second-Level Cache Store (Redisson / Redis Cache)
  redis:
    image: redis:7.0-alpine
    container_name: jpa-redis
    ports:
      - "6379:6379"
    networks:
      - jpa-net

networks:
  jpa-net:
    driver: bridge
```

---

## 📈 Graduation & System Assessment Rubrics

Assessments will evaluate projects across four dimensions:

### 1. Identifier & Mapping Design (25% Weight)
*   **Optimizer Sizing**: Correct configuration of sequences with pooled/pooled-lo identifier optimizers.
*   **Relationship Mapping**: Correct entity mappings avoiding unidirectional list overheads.

### 2. Batch Performance & Action Queues (25% Weight)
*   **Batch Configuration**: Proper configuration of statement sorting (`order_inserts`, `order_updates`) to ensure JDBC batch execution.
*   **Session Management**: Flushing controls to manage persistence context memory footprint.

### 3. Fetching Efficiency & Projections (25% Weight)
*   **Lazy Association Management**: Correct use of `FetchType.LAZY` and resolving the N+1 problem using fetch joins or entity graphs.
*   **DTO Projection**: Sizing transaction data outputs using DTO projections rather than returning managed entities.

### 4. Cache Concurrency & Concurrency Locks (25% Weight)
*   **L2 Concurrency Strategies**: Proper use of `READ_WRITE` vs `NONSTRICT_READ_WRITE` caching based on business consistency rules.
*   **Concurrency Locking**: Correct use of pessimistic and optimistic lock modes under high-concurrency contention.
