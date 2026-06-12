# Module 07: Second-Level (L2) Caching

## 1. What Problem This Module Solves
Fetching entities repeatedly from the database introduces latency and database overhead:
*   **Redundant Database Queries**: If multiple concurrent threads fetch the same static entity (e.g. settings configurations, catalog products) by ID, they must execute redundant queries, consuming database CPU.
*   **Stale Data Cache Inconsistencies**: Caching database records in standard application maps (like concurrent hash maps) can lead to data drift if modifications are committed in concurrent transactions.
*   **Cache Stampede Risks**: If a popular entity is evicted from the cache, multiple threads may attempt to query the database concurrently to reload it, overloading database resources.

The Hibernate **Second-Level (L2) Cache** resolves this by providing a transaction-aware, pluggable caching layer that integrates directly with the entity lifecycle.

---

## 2. L2 Cache Architecture

```
[ Application Session (First-Level Cache) ] 
       │
       ▼ (Cache Miss: Check L2 Cache)
[ Pluggable L2 Cache (Ehcache / Redisson) ] 
       │
       ▼ (Cache Miss: Query Database)
[ Database Server ]
```

*   **First-Level Cache**: Bound to the active Session (EntityManager). It is short-lived and thread-confined.
*   **Second-Level Cache**: Shared across all sessions in the JVM. It stores entity properties as disassembled, flat array buffers rather than complete object structures.

---

## 3. Cache Concurrency Strategies

When multiple threads read and write to the same cached entities concurrently, you must select the correct `CacheConcurrencyStrategy`:

### 3.1 `READ_ONLY`
*   *Usage*: For static data that never changes.
*   *Optimization*: Fast, as it requires no transaction synchronization locks. Attempts to update a read-only cached entity will trigger an exception.

### 3.2 `NONSTRICT_READ_WRITE`
*   *Usage*: For data that is rarely updated and where occasional stale reads are acceptable.
*   *Risk*: Does not lock the cache during updates. If a transaction commits a write, it evicts the cache entry. A concurrent transaction can read and cache stale data from a replica before the update propagates, leading to inconsistencies.

### 3.3 `READ_WRITE` (Uses Soft-Locking)
*   *Usage*: For read-heavy data that is updated concurrently, where data consistency is critical.
*   *Soft-Locking Mechanics*: When Transaction A updates an entity, it places a **Soft Lock** on the cache entry. While the soft lock is active, any concurrent transactions attempting to read the entity are forced to bypass the cache and query the database directly. Once Transaction A commits, it removes the soft lock and caches the updated state, preventing read anomalies.

### 3.4 `TRANSACTIONAL`
*   *Usage*: For JTA environments requiring distributed XA transactions (e.g. using JBossTS or Atomikos). It synchronizes cache updates with the distributed transaction manager.

---

## 4. Enabling L2 Caching on Entities

Configure L2 caching on your entities using annotations:

```java
package com.example.jpa.cache;

import jakarta.persistence.*;
import org.hibernate.annotations.Cache;
import org.hibernate.annotations.CacheConcurrencyStrategy;

@Entity
@Table(name = "catalog_products")
@Cacheable
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE, region = "productCache")
public class ProductEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE)
    private Long id;

    private String name;
    private double price;

    public ProductEntity() {}
    public ProductEntity(String name, double price) {
        this.name = name;
        this.price = price;
    }
}
```

---

## 5. The Query Cache and Invalidation Risks

Hibernate's **Query Cache** does not store the returned entity records; it stores the **query parameter hash** mapped to a list of **entity identifiers (IDs)**.

### The Tablespace Invalidation Trap
When you execute a query cache lookup, Hibernate must verify that the underlying tables have not been modified since the query was cached. 
If *any* transaction inserts, updates, or deletes a row in Table X, Hibernate invalidates the entire tablespace cache for Table X. If your tablespace experiences frequent writes, the query cache will be invalidated repeatedly, adding cache management overhead without improving query performance.

> [!WARNING]
> **Performance Caveat**: Enable the query cache only for static tables with high read-to-write ratios (e.g., country codes, configuration lookup states).

---

## 6. Common Mistakes and Anti-Patterns
*   **Using `READ_WRITE` with Read-Only Data**: Configuring read-write cache concurrency strategies on static entities. This adds soft-locking overhead; use `READ_ONLY` instead.
*   **Enabling Query Cache without Entity Cache**: Enabling the query cache for entities that are not cached in the L2 cache. The query cache will return the entity IDs, forcing Hibernate to execute separate queries to fetch the entity properties for each ID, creating an N+1 query problem.

---

## 7. Interview Questions

### Q1: How does the `READ_WRITE` cache concurrency strategy use Soft-Locking to prevent race conditions during concurrent entity updates?
**Answer**: 
When a transaction updates an entity annotated with `READ_WRITE` concurrency:
1.  Before the SQL update is sent to the database, Hibernate inserts a **Soft Lock** value (which contains a unique lock token and transaction timestamp) into the L2 cache for that entity ID.
2.  While the soft lock exists, any concurrent transaction attempting to read that entity is directed to **bypass the L2 cache** and query the database directly.
3.  Once the updating transaction commits successfully, it removes the soft lock and caches the updated entity state. If the transaction rolls back, the soft lock is evicted, ensuring subsequent requests fetch consistent data from the database.

### Q2: Why is the Query Cache generally considered a performance risk for tables that experience frequent updates?
**Answer**: 
The query cache stores query results mapped to entity IDs, and tracks table modification timestamps to ensure data consistency. 
When *any* transaction writes to Table X, Hibernate invalidates all cached query results associated with Table X. If the table experiences continuous writes (even on unrelated rows), the query cache is repeatedly invalidated. This wastes CPU resources on cache updates and lookups without improving query performance.
