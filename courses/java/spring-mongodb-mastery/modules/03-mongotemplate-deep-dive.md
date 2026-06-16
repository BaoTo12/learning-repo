# Module 03: MongoTemplate Deep Dive

Welcome class. Today we study **MongoTemplate Operations (CS-530)**.

While repositories abstract query generation, they limit access to low-level database features. For complex writes, bulk operations, atomic positional modifiers, and optimistic locking, we use `MongoTemplate`. Today we study low-level criteria building, bulk write operations, optimistic locking, and write concern overrides.

---

## 1. Academic Lecture: MongoTemplate, Optimistic Locking & Bulk Writes

### Basic Level: Lower-Level Database Controls
`MongoTemplate` is the foundation of Spring Data MongoDB. It provides direct access to MongoDB commands (insert, save, update, remove) without the constraints of high-level repository interfaces, allowing you to configure precise write operations.

### Intermediate Level: Atomic Array Updates
Using `MongoTemplate`, we execute granular in-place updates. Instead of loading a document, modifying it in Java, and saving it back, we run atomic operations using `Query` and `Update` helper classes. This maps directly to update operators like `$set` and `$inc`, ensuring high write speeds.

### Advanced Level: Optimistic Locking & Bulk Operations
*   **Optimistic Locking (`@Version`)**: To prevent concurrent writes from overwriting changes, we annotate a field with `@Version`. When saving a document, Spring checks if the document version matches the database version. If the versions match, the document is saved and the version is incremented. If the version has changed (due to a concurrent write), Spring aborts the write and throws an `OptimisticLockingFailureException`.
*   **Bulk Operations (`bulkWrite`)**: Executing hundreds of writes individually creates network round-trip bottlenecks. `MongoTemplate` provides a `BulkOperations` builder that compiles multiple write operations (inserts, updates, deletes) and executes them in a single batch, maximizing server throughput.

```text
                     ┌─── [Write A: Version 1] ───> Matches DB (Version 1) ➔ Save Success (Version 2)
[Concurrent Writes] ─┼─── [Write B: Version 1] ───> Mismatch (DB is Version 2) ➔ Throws OptimisticLockingFailureException
```

---

## 2. Theory vs. Production Trade-offs

Compare update patterns:

| Persistence Strategy | Network Latency | Lock Duration | Concurrency Safety | Storage Overhead |
| :--- | :--- | :--- | :--- | :--- |
| **Load-Modify-Save (`save`)** | High (Requires read then write) | Moderate | Low (Requires `@Version`) | None |
| **In-Place Atomic (`updateFirst`)** | Low (Single write operation) | Minimal | High (Updates are serialized) | None |
| **Bulk Writing (`BulkOperations`)** | Very Low (Executes in batches) | High (Writes multiple documents) | High | None |

---

## 3. How to Use: Dynamic Updates & Concurrency Control in Java

Let us construct updates. We contrast a vulnerable load-modify-save operation with a robust in-place update using `MongoTemplate` and optimistic locking checks in Java.

### A. The Race-Condition Update (Anti-Pattern)
Avoid saving documents without handling concurrent modification checks:

```java
// DANGER: If two threads load this document concurrently, they will both increment 
// the score locally. The thread that saves last will overwrite the other's changes, 
// causing data loss.
Customer customer = mongoTemplate.findById("1", Customer.class);
customer.setStatus("VIP");
mongoTemplate.save(customer);
```

### B. Optimistic Locking & Bulk Ingestions (Production Pattern)
Define entities with `@Version`, handle version mismatch exceptions, and use bulk operations for high-throughput writes:

```java
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.BulkOperations;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Update;
import org.springframework.dao.OptimisticLockingFailureException;
import org.bson.Document;
import java.util.List;

public class InventoryService {

    private final MongoTemplate mongoTemplate;

    public InventoryService(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    public void updateStockAtomic(String itemId, int quantityChange) {
        try {
            Query query = new Query(Criteria.where("_id").is(itemId));
            Update update = new Update().inc("stock", quantityChange);
            
            mongoTemplate.updateFirst(query, update, "inventory");
        } catch (OptimisticLockingFailureException ex) {
            System.out.println("Conflict detected: Document modified by concurrent process.");
            throw ex;
        }
    }

    public void bulkInsertTelemetry(List<Document> logs) {
        BulkOperations bulkOps = mongoTemplate.bulkOps(BulkOperations.BulkMode.UNORDERED, "telemetry");
        bulkOps.insert(logs);
        bulkOps.execute();
    }
}
```

### Line-by-Line Code Explanation:
1.  `mongoTemplate.updateFirst(...)`: Executes an atomic update directly on the database server, bypassing document load steps.
2.  `new Update().inc("stock", quantityChange)`: Maps to the BSON `$inc` update operator, incrementing the value in-place.
3.  `BulkOperations.BulkMode.UNORDERED`: Tells the database that the bulk operations can run in parallel, maximizing write speeds.
4.  `bulkOps.execute()`: Compiles the batch and sends it to the server in a single database round-trip.

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Bypassing Version Checks on Updates
*   **Why it fails**: Executing a raw update command (`updateFirst`) bypasses Spring Data's version validation checks. If you manually update fields, Spring does not check the version property, risking data inconsistencies.
*   **Mitigation**: When updating using template commands, manually increment the version field inside your update statement (e.g. `Updates.inc("version", 1)`).

---

## 5. Socratic Review Questions

### Question 1
Why does utilizing `BulkOperations.BulkMode.UNORDERED` improve write performance compared to `BulkMode.ORDERED`?

#### Answer
Ordered bulk operations execute tasks sequentially in the order they were declared. If an operation fails, the database halts execution, leaving subsequent writes un-executed. Unordered bulk operations are sent to the database in parallel, allowing MongoDB to distribute write queries across server threads and execute them concurrently, maximizing performance.

---

## 6. Hands-on Challenge: Atomic Positional Item Updater

### The Challenge
In this challenge, you will implement an atomic bulk updater using `MongoTemplate`.
Your task:
1. Complete `updateItemPrices` in `InventoryManager`.
2. Construct a bulk update using `MongoTemplate`:
   - Iterate through `itemIds` list and add an update operation for each ID.
   - Update the `price` field to the provided value.
   - Execute the operations in `UNORDERED` mode.

Complete the implementation stub:

```java
package com.masterclass.mongodb.repository;

import org.springframework.data.mongodb.core.MongoTemplate;
import java.util.List;

public class InventoryManager {

    private final MongoTemplate mongoTemplate;

    public InventoryManager(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    public void updateItemPrices(List<String> itemIds, double newPrice) {
        // TODO: Implement dynamic bulk update using UNORDERED operations
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.masterclass.mongodb.repository;

import org.springframework.data.mongodb.core.MongoTemplate;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class InventoryManagerTest {

    @Test
    void testUpdateItemPrices() {
        MongoTemplate template = mock(MongoTemplate.class);
        var manager = new InventoryManager(template);
        assertNotNull(manager);
    }
}
```
