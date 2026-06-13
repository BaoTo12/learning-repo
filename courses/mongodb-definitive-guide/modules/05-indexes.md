# Module 05: Indexes (Chapter 5)

Welcome class. Today we analyze **Indexes (CS-529)**.

Without index structures, executing queries forces the database engine to load and scan every document in a collection (`COLLSCAN`). To avoid this, MongoDB uses B-Tree indexes. When building compound indexes, the order of the indexed keys is critical to ensure proper query execution.

Today we study **B-Tree Indexing Rules**, analyzing compound structures, key prefixes, and query explain plans.

---

## 1. Academic Lecture: Index Search Bounds & Prefix Matches

### 1. Compound Index Sort Ordering
MongoDB's compound indexes are sorted from left to right. An index defined as `{ age: 1, score: -1 }` sorts keys first by `age` ascending, and then within identical ages by `score` descending.

### 2. The Equality, Sort, Range (ESR) Rule
To optimize compound index queries, order the keys in the index using the **ESR Rule**:
1.  **Equality**: Fields matching exact values (e.g. `status = "active"`).
2.  **Sort**: Fields matching sorting parameters (e.g. `sort(createdAt: -1)`).
3.  **Range**: Fields matching range query filters (e.g. `age > 21`).

```text
[Equality Matches] ────────> [Sort Fields] ────────> [Range Scans]
(Positions scan start)   (Avoids in-memory sort)   (Bounds leaf scan)
```

---

## 2. Theory vs. Production Trade-offs

Compare index patterns inside the JVM runtime:

| Dimension / Metric | Single-Field Index | Compound Index (ESR ordered) | Index Intersection (Two indexes merged) |
| :--- | :--- | :--- | :--- |
| **Write Penalty** | Low | Moderate | High (Multiple updates required) |
| **RAM Footprint** | Low | Moderate | High |
| **RAM Sort Prevention** | Only on indexed key | Yes | No (Often triggers memory sort) |
| **Prefix Reusability** | No | Yes (Left-aligned keys) | No |
| **WiredTiger Sync Cost** | Low | Moderate | High |

---

## 3. How to Use: Compound Index Configurations in Java

Let us construct indexing tasks. We contrast a sub-optimal index setup (which triggers in-memory sorting) with the ESR-compliant compound index pattern.

### A. The Sub-Optimal Index Configuration (Anti-Pattern)
Avoid ordering compound indexes with range keys before sort keys:

```java
// DANGER: Placing the range query "age" before the sort key "username" 
// forces the database engine to perform an in-memory SORT stage, consuming RAM.
collection.createIndex(Indexes.compoundIndex(
    Indexes.ascending("age"),
    Indexes.ascending("username")
));
```

### B. The Hardened ESR-Compliant Index (Production Pattern)
Order index fields strictly matching Equality, Sort, and Range parameters:

```java
import com.mongodb.client.model.Indexes;
import com.mongodb.client.model.IndexOptions;

// Robust Pattern: Index is configured as { status: Equality, username: Sort, age: Range }.
collection.createIndex(
    Indexes.compoundIndex(
        Indexes.ascending("status"),
        Indexes.ascending("username"),
        Indexes.ascending("age")
    ),
    new IndexOptions().name("idx_status_username_age")
);
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Indexing High-Cardinality Arrays (Explosive Multikey Indexes)
*   **Why it fails**: Creating a compound index where multiple fields are arrays. MongoDB generates index key entries for every combination of array elements (Cartesian product). This causes index size to explode and write performance to collapse, triggering cache saturation.
*   **Mitigation**: MongoDB blocks index creation if more than one compound field is an array (to prevent explosive growth). Ensure at most one compound index field targets an array.

---

## 5. Socratic Review Questions

### Question 1
Why does a query filtering on `{ username: "Alice" }` fail to use the compound index `{ status: 1, username: 1 }`?

#### Answer
MongoDB compound indexes can only resolve queries containing the left-aligned prefix of indexed keys. Since `status` is the primary sorting key in the B-Tree, the engine cannot navigate the tree without a `status` filter. Searching for `username` directly forces a full index scan (`IXSCAN` on all leaf nodes) or a full collection scan (`COLLSCAN`).

---

## 6. Hands-on Challenge: ESR Compound Index Design

### The Challenge
In this challenge, you will implement index creation in Java.
Your task:
1. Complete `createOptimalIndex` in `IndexService`.
2. Configure a compound index to optimize this query pattern:
   `collection.find(eq("storeId", "A")).sort(descending("orderDate")).filter(gt("amount", 100))`
3. Follow the ESR rule.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class IndexService {

    public void createOptimalIndex(MongoCollection<Document> collection) {
        // TODO: Build compound index matching the equality, sort, and range rules
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;

class IndexServiceTest {

    @SuppressWarnings("unchecked")
    @Test
    void testCreateOptimalIndex() {
        MongoCollection<Document> collection = mock(MongoCollection.class);
        IndexService service = new IndexService();

        service.createOptimalIndex(collection);

        // Verify index creation was requested
        verify(collection, times(1)).createIndex(any(), any());
    }
}
```
