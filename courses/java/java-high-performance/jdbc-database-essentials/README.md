# High-Performance JDBC and Database Essentials

Welcome to the **High-Performance JDBC and Database Essentials** course. This repository contains a comprehensive, production-focused syllabus designed for senior software engineers, platform architects, and database developers who design and operate high-scale Java data access layers.

This course is based on Part I of Vlad Mihalcea's *High-Performance Java Persistence*. It covers the deep relational and connectivity layers, connection pool optimization, statement batching dynamics, statement caching internals, result set fetching limits, transaction isolation levels, and concurrency control models (MVCC vs 2PL).

---

## 🎯 Course Objectives

By the end of this course, you will be able to:
1. **Analyze Performance Boundaries**: Understand throughput, latency, and physical database connectivity limitations.
2. **Design Scaling Topologies**: Code and configure master-slave replication, multi-master, and sharding layouts.
3. **Configure Connection Pools**: Size and configure HikariCP using queuing theory equations.
4. **Deploy Connection Monitoring**: Monitor metrics (acquisition times, lease times, and thread pools) to prevent connection leaks.
5. **Optimize Batch Operations**: Configure statements and prepared statements batching, and analyze sequence allocation footprints.
6. **Master Statement Caching**: Optimize client-side and server-side statement caches, and debug parameter sniffing.
7. **Control ResultSet Fetching**: Tune driver-specific fetch sizes and implement high-speed keyset pagination.
8. **Analyze Concurrency Controls**: Master Two-Phase Locking (2PL), MVCC mechanics, and database-specific isolation levels.
9. **Trace Transactional Phenomena**: Debug dirty writes, non-repeatable reads, read/write skews, and lost updates.
10. **Implement Read-Write Splitting**: Route write transactions to master databases and read-only transactions to replication replicas dynamically in raw Java.

---

## 📚 Structured Syllabus & Modules

The curriculum consists of 6 comprehensive, technical modules:

| Module | Topic | File Link |
| :--- | :--- | :--- |
| **01** | Database Performance and Scaling Boundaries | [01-performance-scaling.md](./modules/01-performance-scaling.md) |
| **02** | JDBC Connection Management & Pool Sizing | [02-connection-management.md](./modules/02-connection-management.md) |
| **03** | High-Performance Batch Processing | [03-batch-updates.md](./modules/03-batch-updates.md) |
| **04** | Statement Lifecycles & Caching | [04-statement-caching.md](./modules/04-statement-caching.md) |
| **05** | ResultSet Fetching & Pagination | [05-resultset-fetching.md](./modules/05-resultset-fetching.md) |
| **06** | Transactions, Concurrency Control, & Isolation | [06-transactions-concurrency.md](./modules/06-transactions-concurrency.md) |

---

## 🛠️ Local Sandbox Infrastructure Setup

To run the labs and practice read-write splitting and replication lag analysis, you will need a docker-compose environment running a master-slave PostgreSQL replication group.

Save the following configuration block as `docker-compose.yml` in your working directory:

```yaml
version: '3.8'

services:
  # Primary Database (Writes)
  pg-master:
    image: bitnami/postgresql:15
    container_name: pg-master
    ports:
      - "5432:5432"
    environment:
      - POSTGRESQL_USERNAME=postgres
      - POSTGRESQL_PASSWORD=postgres
      - POSTGRESQL_DATABASE=jdbc_db
      - POSTGRESQL_REPLICATION_MODE=master
      - POSTGRESQL_REPLICATION_USER=repl_user
      - POSTGRESQL_REPLICATION_PASSWORD=repl_password
    networks:
      - jdbc-net

  # Replication Database (Read-Only)
  pg-replica:
    image: bitnami/postgresql:15
    container_name: pg-replica
    ports:
      - "5433:5432"
    environment:
      - POSTGRESQL_USERNAME=postgres
      - POSTGRESQL_PASSWORD=postgres
      - POSTGRESQL_DATABASE=jdbc_db
      - POSTGRESQL_REPLICATION_MODE=slave
      - POSTGRESQL_MASTER_HOST=pg-master
      - POSTGRESQL_MASTER_PORT_NUMBER=5432
      - POSTGRESQL_REPLICATION_USER=repl_user
      - POSTGRESQL_REPLICATION_PASSWORD=repl_password
    depends_on:
      - pg-master
    networks:
      - jdbc-net

networks:
  jdbc-net:
    driver: bridge
```

---

## 📈 Graduation & System Assessment Rubrics

Assessments will evaluate projects across four dimensions:

### 1. Connection Pooling & Capacity Sizing (25% Weight)
*   **Queue Sizing**: Correct sizing of connection pools based on target concurrency requirements using Erlang C equations.
*   **Metrics Integration**: Monitoring latency metrics and configuring alerting limits on connection acquisition times.

### 2. Statement Batching & Sequence Layout (25% Weight)
*   **Batch Configuration**: Tuning batch sizes to optimize database round-trips.
*   **ID Allocation footprint**: Proper use of sequence allocation ranges (`allocationSize` / `cache` sizes) to avoid round-trip serialization bottlenecks.

### 3. Execution Plan Analysis (25% Weight)
*   **Plan Validation**: Visualizing and parsing database execution plans to spot full-table scans.
*   **Parameter Optimization**: Correct use of bind parameters to enable statement caching while preventing parameter sniffing anomalies.

### 4. Concurrency & Isolation Design (25% Weight)
*   **Phenomena Prevention**: Correct isolation level mapping and locking models to prevent lost updates and write skew.
*   **Read-Write Routing**: Dynamic transaction routing separating write operations from read-only replications.
