# Module 05: High-Performance JPA Batching

## 1. What Problem This Module Solves
Executing bulk modifications inside an ORM without proper configurations leads to significant overhead:
*   **Disabled JDBC Batching**: Hibernate maps objects dynamically. If you save multiple entities, but the underlying identifier uses `GenerationType.IDENTITY`, batching is silently disabled.
*   **Batch Breaking**: If the save sequence alternates between different entity types or SQL commands (e.g. insert Order, insert OrderItem, insert Order, insert OrderItem), Hibernate will execute them sequentially, breaking the JDBC batch.
*   **Out of Memory (OOM) Errors**: Buffering thousands of objects in the persistence context during bulk operations consumes system memory, causing heap exhaustion.

This module details how to configure Hibernate properties, order statements, and execute batch inserts/updates/deletes.

---

## 2. Core Batching Configuration Properties

To enable statement batching in JPA/Hibernate, configure the following properties in your `application.yml` or `hibernate.properties`:

```yaml
spring:
  jpa:
    properties:
      # 1. Set the maximum number of statements to buffer in a single batch
      hibernate.jdbc.batch_size: 50
      
      # 2. Sort insert statements by entity type to prevent batch breaking
      hibernate.order_inserts: true
      
      # 3. Sort update statements by entity type to prevent batch breaking
      hibernate.order_updates: true
      
      # 4. Enable batching for versioned entities (for optimistic locking compatibility)
      hibernate.jdbc.batch_versioned_data: true
```

---

## 3. Why Statement Ordering is Necessary

By default, Hibernate executes SQL statements in the order entities are modified. 

If you persist a hierarchy of entities (e.g. Order and OrderItem):
```
Modification Sequence:
Order A ──► OrderItem A1 ──► Order B ──► OrderItem B1

Without Statement Ordering (Batch size = 50, but Batch Breaks):
- Batch 1: INSERT Order A (Execute batch: size 1)
- Batch 2: INSERT OrderItem A1 (Execute batch: size 1)
- Batch 3: INSERT Order B (Execute batch: size 1)
- Batch 4: INSERT OrderItem B1 (Execute batch: size 1)
* Batching is broken because the statements alternate.

With hibernate.order_inserts = true:
- Batch 1: INSERT Order A, INSERT Order B (Execute batch: size 2)
- Batch 2: INSERT OrderItem A1, INSERT OrderItem B1 (Execute batch: size 2)
* Batching works because Hibernate groups identical statements together.
```

---

## 4. Implementing JPA Batch Updates in Spring Boot

This service demonstrates how to execute batch updates, using sequence generators and clearing the persistence context periodically to control memory usage:

```java
package com.example.jpa.batch;

import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.List;

@Service
public class OrderBatchService {

    @PersistenceContext
    private EntityManager entityManager;

    @Transactional
    public void executeBulkInsert(List<OrderEntity> orders) {
        int batchSize = 50; // Match hibernate.jdbc.batch_size configuration

        for (int i = 0; i < orders.size(); i++) {
            entityManager.persist(orders.get(i));

            // Flush and clear periodically to prevent memory bloat
            if (i > 0 && i % batchSize == 0) {
                entityManager.flush(); // Execute the batched statements
                entityManager.clear(); // Evict managed entities from memory
            }
        }
    }
}
```

---

## 5. Common Mistakes and Anti-Patterns
*   **Alternating Entity Saves**: Executing batch saves without enabling `hibernate.order_inserts`. The batch will break continuously, resulting in row-by-row executions.
*   **Neglecting `hibernate.jdbc.batch_versioned_data`**: Disabling batching for entities that use version fields for optimistic locking. Ensure this property is set to `true` (standard in Hibernate 6).
*   **Leaving Auto-Commit Enabled**: Running batch updates outside transaction boundaries. If auto-commit is enabled, the driver will commit each statement in the batch individually, slowing down execution.

---

## 6. Interview Questions

### Q1: How does the configuration parameter `hibernate.order_inserts` affect statement batching at the JDBC level?
**Answer**: 
During flush, Hibernate iterates through the persistence context changes. If your code alternates between persisting Parent and Child entities, the generated SQL statements alternate (e.g. `INSERT parent`, `INSERT child`, `INSERT parent`). 
Because the JDBC driver can only batch identical SQL statements (using the same prepared statement context), alternating statements breaks the batch, forcing immediate execution. Enabling `hibernate.order_inserts` tells Hibernate to sort the insert actions by entity type before flushing, grouping all parent inserts and child inserts into separate, optimized batch runs.

### Q2: Why will using a sequence generator with an allocation size of 1 (`allocationSize = 1`) degrade batch insert performance in JPA?
**Answer**: 
If the sequence `allocationSize` is set to 1, Hibernate must query the database sequence to retrieve a new ID for every single insert statement.
Even if you set `hibernate.jdbc.batch_size` to 50, saving 50 entities requires executing 50 separate database sequence queries before the batch insert can be sent. This creates network bottlenecks. To optimize batch inserts, configure a sequence generator with a larger allocation size (e.g., `allocationSize = 50`) and use a sequence optimizer.
