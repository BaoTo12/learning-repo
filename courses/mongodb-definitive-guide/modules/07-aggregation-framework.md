# Module 07: Introduction to the Aggregation Framework (Chapter 7)

Welcome class. Today we analyze **Introduction to the Aggregation Framework (CS-529)**.

Running database sorting or calculations in the Java application layer is highly inefficient because it requires downloading large volumes of raw data over the network. MongoDB provides the **Aggregation Framework**—a pipeline-based processing engine running directly inside the database. In Java, this is configured using type-safe stage builders from the `Aggregates` class.

Today we study **Aggregation Pipeline Optimization**, mapping stage configurations, memory limits, and disk write overflows in Java.

---

## 1. Academic Lecture: Aggregation Stages & Pipeline Optimization

### 1. Stage Classifications
An aggregation pipeline passes documents through sequential processing blocks:
*   **Streaming Stages**: Process and output documents one by one (e.g. `Aggregates.match()`, `Aggregates.project()`, `Aggregates.unwind()`). These consume minimal RAM.
*   **Blocking Stages**: Must load and buffer all documents before calculating results (e.g. `Aggregates.group()`, `Aggregates.sort()`).

### 2. The 100MB RAM Limit
To protect server resources, MongoDB limits each aggregation stage to **100 Megabytes of RAM**. If a blocking stage exceeds this limit, the query terminates with an exception. To bypass this, pass the `{ allowDiskUse: true }` option.

```text
[Collection] ──> [ Aggregates.match() ] ──> [ Aggregates.group() (RAM Max: 100MB) ]
                                                   │
                                                   ├── (If < 100MB) ──> [Return Page]
                                                   └── (If > 100MB) ──> [OOM Error / Swap to Disk]
```

---

## 2. Theory vs. Production Trade-offs

Compare aggregation execution options:

| Dimension / Metric | Client-Side Loop Aggregation | Server-Side Aggregation Pipeline | Pipeline with `allowDiskUse(true)` |
| :--- | :--- | :--- | :--- |
| **Network Overhead** | Extreme | Very Low | Very Low |
| **Memory Constraint**| App server constrained | 100MB strict limit per stage | Unlimited (Uses server temp files) |
| **Query Performance**| Low | Very High | Moderate (Disk write swap latency) |
| **Index Utilization** | Direct find queries | Direct index matching on initial stages | Direct index matching on initial stages |

---

## 3. How to Use: Type-Safe Aggregation in Java

Let us construct aggregation pipelines. We contrast a sub-optimal pipeline design (which disables indexes) with a robust, optimized pipeline utilizing index-matched stages.

### A. Sub-Optimal Stage Sequencing (Anti-Pattern)
Avoid projecting fields before match filters, which prevents index scans:

```java
// DANGER: Executing projections ($project) before match filters ($match) prevents 
// the query planner from using indexes on the matched field, triggering a COLLSCAN.
collection.aggregate(List.of(
    Aggregates.project(Projections.fields(Projections.include("storeId", "amount"))),
    Aggregates.match(Filters.eq("storeId", "ST-88"))
));
```

### B. The Hardened Index-Aware Aggregation (Production Pattern)
Place `match` and `sort` stages at the top of the pipeline to leverage index trees:

```java
import com.mongodb.client.model.Accumulators;
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import java.util.List;

// Robust Pattern: Stage matching occurs first, and disk write swaps are enabled for large datasets.
collection.aggregate(List.of(
    Aggregates.match(Filters.eq("storeId", "ST-88")),
    Aggregates.group("$storeId", Accumulators.sum("totalSales", "$amount")),
    Aggregates.project(Projections.fields(
        Projections.computed("store", "$_id"),
        Projections.include("totalSales"),
        Projections.excludeId()
    ))
)).allowDiskUse(true); // Prevents 100MB OOM errors
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Unindexed `$unwind` Array Expansion
*   **Why it fails**: Executing `Aggregates.unwind("items")` on millions of documents before applying a `$match` filter. Unwinding duplicates documents for every element in the array, causing the document count to explode in memory, exceeding the 100MB limit instantly.
*   **Mitigation**: Always match and filter the document count using index stages *before* unwinding arrays.

---

## 5. Socratic Review Questions

### Question 1
Why does placing a `$match` stage after a `$group` stage prevent the database from utilizing collection indexes?

#### Answer
The `$group` stage is a blocking transformation that creates entirely new BSON documents (grouped aggregates). These output documents exist only in-memory (not on disk). Since indexes are bound to the static collection on disk, any downstream stages following a `$group` cannot use collection indexes, forcing complete in-memory scans.

---

## 6. Hands-on Challenge: Java Pipeline Sales Analyst

### The Challenge
In this challenge, you will implement an aggregation pipeline in Java.
Your task:
1. Complete the method `aggregateElectronicsSales` in `SalesAnalyst`.
2. Query the `sales` collection:
   - Match documents where `category` is `"electronics"`.
   - Unwind the `items` array.
   - Group by `items.itemId` and calculate total quantities sold (`totalQty`).
   - Sort by `totalQty` descending, limit to top 3 items, and project `itemId` (from the group key `_id`) and `totalQty`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoIterable;
import org.bson.Document;

public class SalesAnalyst {

    public MongoIterable<Document> aggregateElectronicsSales(MongoCollection<Document> collection) {
        // TODO: Build and return the aggregate pipeline iterable using aggregates stages list
        return null;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import com.mongodb.client.AggregateIterable;
import com.mongodb.client.MongoCollection;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class SalesAnalystTest {

    @SuppressWarnings("unchecked")
    @Test
    void testAggregateElectronicsSales() {
        MongoCollection<Document> collection = mock(MongoCollection.class);
        AggregateIterable<Document> iterable = mock(AggregateIterable.class);
        
        when(collection.aggregate(any())).thenReturn(iterable);
        when(iterable.allowDiskUse(anyBoolean())).thenReturn(iterable);

        SalesAnalyst analyst = new SalesAnalyst();
        var result = analyst.aggregateElectronicsSales(collection);

        assertNotNull(result);
        verify(collection, times(1)).aggregate(any());
    }
}
```
