# Module 04: Querying (Chapter 4)

Welcome class. Today we analyze **Querying (CS-529)**.

Retrieving data from document databases requires matching patterns across nested BSON structures. To prevent reading unnecessary data, Java developers use type-safe query filters, field projections, and key-based cursor pagination.

Today we study **BSON Query Resolution & Pagination**, analyzing search filters, array queries, cursor pagination, and projection optimizations.

---

## 1. Academic Lecture: The Query Engine & Cursor Paging

### 1. Filters & Projection Operators
The MongoDB Java driver uses the `Filters` utility class to compile query queries (`Filters.eq()`, `Filters.and()`, `Filters.elemMatch()`). Projections (`Projections.include()`) instruct the database server to return only specified fields, reducing transport latency.

### 2. Cursor Mechanics & Paging
When a query matches documents, MongoDB does not load all documents into memory. The driver opens a server-side cursor, loading documents in batches (typically 101 documents first).
*   **The Problem of Skip**: Calling `skip(1000)` forces the database to load and evaluate 1,000 documents only to discard them.
*   **The Keyset Solution**: Filtering on unique sorted keys (e.g. `_id: { $gt: lastSeenId }`) allows the index scan to position the cursor directly at the start of the next page.

```text
[Skip-Based Paging]
Skip 10,000 docs ──> [Scan & Parse 10,000 documents in B-Tree] ──> Fetch 10 (Slow)

[Keyset-Based Paging]
Filter _id > LastSeen ──> [Locate LastSeen directly using index] ──> Fetch 10 (Fast)
```

---

## 2. Theory vs. Production Trade-offs

Compare pagination architectures:

| Dimension / Metric | Skip-Based Pagination (`skip` / `limit`) | Keyset-Based Pagination (Range Queries) |
| :--- | :--- | :--- |
| **Execution Performance** | Degrades exponentially as page increases | Stable (O(log N) search cost) |
| **Real-time Resiliency** | Vulnerable (Skips/duplicates data if writes occur) | Consistent |
| **Index Dependency** | Optional | Mandatory |
| **Complexity** | Simple | Moderate (Requires driver to retain state) |
| **Database Server Load** | High (Wasted CPU scans) | Low |

---

## 3. How to Use: Keyset Pagination & Projections in Java

Let us construct query operations. We contrast a performance-weak skip-based pagination query with the robust keyset pagination pattern.

### A. The High-Cost Skip Query (Anti-Pattern)
Avoid using skip offsets for large collections:

```java
// DANGER: Skip forces full scan of skipped keys, leading to COLLSCAN and cache thrashing.
MongoCursor<Document> cursor = collection.find(Filters.eq("status", "ACTIVE"))
        .skip(50000)
        .limit(20)
        .iterator();
```

### B. The Hardened Keyset Range Query (Production Pattern)
Combine filters with keyset values and project only necessary fields:

```java
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Projections;
import com.mongodb.client.model.Sorts;
import com.mongodb.client.MongoCursor;
import org.bson.Document;
import org.bson.types.ObjectId;

// Robust Pattern: Direct pointer navigation using lastSeenId, projecting only name/email.
ObjectId lastSeenId = new ObjectId("60c72b2f9b1d8b2c8c8b4567");

MongoCursor<Document> cursor = collection.find(
    Filters.and(
        Filters.eq("status", "ACTIVE"),
        Filters.gt("_id", lastSeenId)
    ))
    .projection(Projections.fields(
        Projections.include("name", "email"),
        Projections.excludeId()
    ))
    .sort(Sorts.ascending("_id"))
    .limit(20)
    .iterator();
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Loose Array Attribute Queries
*   **Why it fails**: Querying an array of documents without `$elemMatch`. If you call `Filters.eq("grades.score", 90)` and `Filters.eq("grades.type", "exam")`, MongoDB will match documents where ANY grade has score 90, and ANY grade has type exam, even if they are in different array elements.
*   **Mitigation**: Always use `Filters.elemMatch` to target a single nested document within the array.

---

## 5. Socratic Review Questions

### Question 1
Why does a projection query excluding a field (e.g. `Projections.exclude("description")`) still require parsing BSON document headers on the database server before returning the document to the client?

#### Answer
BSON document fields are serialized sequentially. The database engine must parse the document's header size and traverse the field length prefixes to skip the excluded field bytes before writing the projected output to the socket stream. Projections save network bandwidth, but they do not eliminate server-side document parsing costs.

---

## 6. Hands-on Challenge: Java Keyset Pagination Engine

### The Challenge
In this challenge, you will implement a pagination method in Java.
Your task:
1. Complete `getNextPage` in `QueryEngine`.
2. Construct a query to return documents from `orders` where `_id` is greater than `lastId`, sorted by `_id` ascending, limited to `limit`.
3. Project only `orderId` and `total` (excluding the `_id`).

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoIterable;
import org.bson.Document;
import org.bson.types.ObjectId;

public class QueryEngine {

    public MongoIterable<Document> getNextPage(MongoCollection<Document> collection, ObjectId lastId, int limit) {
        // TODO: Construct and return the keyset-paginated, projected iterable
        return null;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import com.mongodb.client.FindIterable;
import com.mongodb.client.MongoCollection;
import org.bson.Document;
import org.bson.types.ObjectId;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class QueryEngineTest {

    @SuppressWarnings("unchecked")
    @Test
    void testGetNextPage() {
        MongoCollection<Document> collection = mock(MongoCollection.class);
        FindIterable<Document> findIterable = mock(FindIterable.class);
        
        when(collection.find(any())).thenReturn(findIterable);
        when(findIterable.projection(any())).thenReturn(findIterable);
        when(findIterable.sort(any())).thenReturn(findIterable);
        when(findIterable.limit(anyInt())).thenReturn(findIterable);

        QueryEngine engine = new QueryEngine();
        ObjectId id = new ObjectId();
        
        var result = engine.getNextPage(collection, id, 10);
        assertNotNull(result);
        
        verify(collection, times(1)).find(any());
        verify(findIterable, times(1)).projection(any());
        verify(findIterable, times(1)).sort(any());
        verify(findIterable, times(1)).limit(10);
    }
}
```
