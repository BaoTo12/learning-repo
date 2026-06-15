# Module 06: Indexing

Welcome, student. Today we study every aspect of **Indexing (CS-529)** using the official MongoDB Java Sync Driver.

---

## 1. What problem does this solve?
As databases grow to contain millions of documents, querying them becomes increasingly slow. Without an index, a query matching a single document forces MongoDB to read every document in the collection from disk. This is known as a **Collection Scan** (`COLLSCAN`) and scales as $O(N)$ linear time.

Indexes solve this by maintaining a sorted copy of a small subset of document fields in a highly optimized **B-Tree** structure. This allows MongoDB to search for matching records in $O(\log N)$ logarithmic time, reducing disk lookups and query latencies from seconds to milliseconds.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides indexing capabilities to:
*   **Optimize Read Queries**: Speed up find operations by traversing B-Tree nodes instead of executing sequential disk scans.
*   **Avoid CPU-heavy Memory Sorts**: Since B-Trees store keys pre-sorted, queries requesting sorting can return results directly from the index without executing a CPU-intensive in-memory sort stage.
*   **Enforce In-place Constraints**: Unique indexes enforce document business constraints directly at the database engine layer.
*   **Support Specialized Data Cleanup**: TTL (Time-To-Live) indexes automate collection archiving and session expiration tasks.

---

## 3. How does it work internally or conceptually?
*   **B-Tree Structures**: MongoDB indexes are implemented as B-Tree structures. Each node in the tree contains sorted key values and pointers. The leaf nodes contain pointers pointing directly to the physical storage blocks on disk (Record IDs) where the actual document BSON resides.
*   **The ESR Rule**: When designing compound indexes (indexes on multiple fields), you must order keys according to the **ESR** priority rule:
    1.  **E**quality fields first (exact matches).
    2.  **S**ort fields second (ordering targets).
    3.  **R**ange fields last (greater/less than filters, in/nin lists).
    *Why?* Placing a range filter before a sort column forces the query planner to split search bounds, preventing index-based sorting and triggering an in-memory sort stage.
*   **Query Planner & Winning Plan**: The query planner evaluates an incoming filter, lists candidate indexes, and generates alternative execution plans. It executes these plans concurrently for a short trial. The plan that yields matches fastest is saved as the **Winning Plan** in the plan cache, while the others are stored as **Rejected Plans**. The cache is evicted if the index changes or the collection statistics are rebuilt.
*   **COLLSCAN vs. IXSCAN**:
    *   `COLLSCAN`: Collection Scan. The engine reads every document block in WiterTiger storage.
    *   `IXSCAN`: Index Scan. The engine traverses B-Tree index nodes in RAM, identifying matching pointers.
*   **Index Selectivity**: Measures how effectively an index narrows down the search space. A selective index points to a tiny percentage of the total collection. If a query scans 10,000 index keys (`keysExamined`) but returns only 5 documents (`nReturned`), the index has poor selectivity.

---

## 4. How do we use it in Java?
We construct indexes programmatically using builders from the `com.mongodb.client.model.Indexes` and `com.mongodb.client.model.IndexOptions` classes.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Indexes;
import com.mongodb.client.model.IndexOptions;
import org.bson.Document;

public class BasicIndexDemo {
    public void configureIndex(MongoCollection<Document> collection) {
        // Create an ascending single-field index on the "email" field
        collection.createIndex(
            Indexes.ascending("email"),
            new IndexOptions().name("idx_email").unique(true)
        );
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**:
    *   **Sub-millisecond Read Performance**: Speeds up lookups significantly.
    *   **RAM-efficient sorting**: Pre-sorted keys avoid memory-limited sorting errors.
    *   **Disk savings via covered queries**: Reduces I/O latency.
*   **Cons**:
    *   **Write Speed Cost**: Every insert, update, or delete must mutate the matching B-Tree nodes.
    *   **Memory Cache Footprint**: Indexes must fit entirely within the system's RAM (WiredTiger Cache). If indexes exceed RAM capacity, the system thrashing triggers continuous page swapping on disk.
    *   **Storage Overhead**: Large compound and multikey indexes consume significant disk space.

---

## 6. Common Mistakes
*   **Compound Index Sort Mismatches**: Creating a compound index on `{ a: 1, b: -1 }` but querying with a sort on `{ a: 1, b: 1 }`. The database cannot traverse the index backwards on both keys concurrently, triggering an in-memory sort.
*   **Multikey Index Key Explosion**: Creating a compound index on two separate array fields (e.g. `Indexes.compoundIndex(ascending("tags"), ascending("roles"))`). MongoDB prevents this because it would force a Cartesian product of keys, leading to massive index sizes.
*   **The "Too Many Indexes" Problem**: Indexing every field to support different query formats. This slows database writes to a crawl and fills memory with redundant indexes.

---

## 7. When should we use it?
*   Use single-field indexes on selective keys that are searched frequently (e.g. UUIDs, emails, SKUs).
*   Use compound indexes for queries that filter on multiple properties or combine filters with sorting.
*   Use partial indexes when queries only target a specific subset of documents, saving memory.

---

## 8. When should we avoid it?
*   Do not create indexes on low-cardinality fields (e.g. booleans like `isDeleted` or status codes with few states) unless they are part of a compound index.
*   Do not index large text fields (like descriptions) with standard B-Trees. Use text indexes or external search servers.

---

## 9. Code Examples

### A. INDEX CONFIGURATIONS

#### 1. Single-Field, Unique, and Compound Indexes
Configuring standard index layouts.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Indexes;
import com.mongodb.client.model.IndexOptions;
import org.bson.Document;

public class CoreIndexesDemo {
    public void run(MongoCollection<Document> collection) {
        // 1. Single Field Index
        collection.createIndex(Indexes.ascending("username"));

        // 2. Unique Index (Forces database-level uniqueness)
        collection.createIndex(
            Indexes.ascending("email"),
            new IndexOptions().name("idx_unique_email").unique(true)
        );

        // 3. Compound Index (Multi-key fields with sorting directives)
        // Order: department (ascending) -> age (descending)
        collection.createIndex(
            Indexes.compoundIndex(
                Indexes.ascending("department"),
                Indexes.descending("age")
            ),
            new IndexOptions().name("idx_dept_age")
        );
    }
}
```

#### 2. Multikey, Text, and Hashed Indexes
Handling arrays, search scoring, and sharding distribution.
*   **Multikey Index**: Automatically created when you index a field containing an array. It creates an index entry for every element in the array.
*   **Text Index**: Indexes string content for full-text search. A collection can have at most one text index.
*   **Hashed Index**: Computes a MD5 hash of the field value. Used to partition data uniformly across shard clusters.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Indexes;
import com.mongodb.client.model.IndexOptions;
import org.bson.Document;

public class SpecialIndexesDemo {
    public void run(MongoCollection<Document> collection) {
        // 1. Multikey Index: Indexing primitive array "tags"
        collection.createIndex(Indexes.ascending("tags"));

        // 2. Text Index: Support text search on fields "title" and "description"
        collection.createIndex(
            Indexes.compoundIndex(
                Indexes.text("title"),
                Indexes.text("description")
            ),
            new IndexOptions().name("idx_text_search")
        );

        // 3. Hashed Index: Computes hashes for sharding partition uniformity
        collection.createIndex(Indexes.hashed("userId"));
    }
}
```

#### 3. Sparse, Partial, and TTL Indexes
*   **Sparse Index**: Only contains entries for documents that actually have the indexed field. Saves space when many documents lack the field.
*   **Partial Index**: Indexes only documents that match a filter expression. Highly efficient for targeted queries.
*   **TTL Index**: Automatically deletes documents after a specified time. Field must be a BSON Date type.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Indexes;
import com.mongodb.client.model.IndexOptions;
import org.bson.Document;
import java.util.concurrent.TimeUnit;

public class ConditionalIndexesDemo {
    public void run(MongoCollection<Document> collection) {
        // 1. Sparse Index
        collection.createIndex(
            Indexes.ascending("twitterHandle"),
            new IndexOptions().sparse(true)
        );

        // 2. Partial Index: Index SKU only for active catalog items
        Document filter = new Document("status", "ACTIVE");
        collection.createIndex(
            Indexes.ascending("sku"),
            new IndexOptions().partialFilterExpression(filter).name("idx_active_sku")
        );

        // 3. TTL Index: Auto-expire sessions 3600 seconds (1 hour) after "loginTime"
        collection.createIndex(
            Indexes.ascending("loginTime"),
            new IndexOptions().expireAfter(3600L, TimeUnit.SECONDS).name("idx_session_timeout")
        );
    }
}
```

#### 4. Indexing Nested Fields & Arrays
Traversing embedded properties for B-Tree construction.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Indexes;
import org.bson.Document;

public class NestedIndexDemo {
    public void run(MongoCollection<Document> collection) {
        // Indexing nested object properties (Dot Notation)
        collection.createIndex(Indexes.ascending("profile.address.zipCode"));

        // Indexing array of subdocuments
        // Indexes the "score" field inside all documents within the "grades" array
        collection.createIndex(Indexes.ascending("grades.score"));
    }
}
```

---

### B. ADVANCED OPTIMIZATIONS

#### 1. Compound Index Order (ESR Rule)
To maximize compound index performance, follow the **ESR Rule** (Equality, Sort, Range):
*   **Equality**: Exact matches (`eq`, `in`) must be placed first. They prune the dataset to the smallest candidate list.
*   **Sort**: Sorting fields must come next. This allows the index tree to provide sorted records directly.
*   **Range**: Range queries (`gt`, `lt`, `regex`) split the index bounds. They must be placed last.

**Example scenario**: Query: `find(status = "ACTIVE", price > 50).sort(createdAt: -1)`
*   **ESR Index structure**: `{ status: 1, createdAt: -1, price: 1 }`
*   Equality (`status`) ➔ Sort (`createdAt`) ➔ Range (`price`).

#### 2. Covered Queries
A query is **covered** if MongoDB can satisfy the filter, sorting, and projection criteria using only index keys in memory, without loading the actual documents from disk.
To cover a query, you must explicitly project out the default `_id` field unless it is part of the index.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Projections;
import com.mongodb.client.model.Indexes;
import org.bson.Document;
import org.bson.conversions.Bson;

public class CoveredQueryDemo {
    public void executeCoveredQuery(MongoCollection<Document> collection) {
        // Setup index: { department: 1, email: 1 }
        collection.createIndex(Indexes.compoundIndex(Indexes.ascending("department"), Indexes.ascending("email")));

        // Query criteria covers only indexed fields
        Bson filter = Filters.eq("department", "COMPUTER_SCIENCE");
        Bson projection = Projections.fields(
            Projections.include("email"),
            Projections.excludeId() // EXCLUDE id to ensure the query is covered
        );

        // This query runs entirely in memory without loading documents from disk
        collection.find(filter).projection(projection).forEach(doc -> {
            System.out.println("Email: " + doc.getString("email"));
        });
    }
}
```

---

### C. DIAGNOSTICS & EXPLAIN OPERATIONS

To verify that your query is executing efficiently, use the `.explain()` method to retrieve the execution plan.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.ExplainVerbosity;
import org.bson.Document;

public class ExplainDiagnosticsDemo {
    public void analyzeQuery(MongoCollection<Document> collection) {
        // Run explain on query matching active items
        Document explainResult = collection.find(Filters.eq("sku", "PROD-99"))
                                           .explain(ExplainVerbosity.EXECUTION_STATS);

        System.out.println(explainResult.toJson());
    }
}
```

#### Key Explain Document Fields to Monitor:
1.  **`stage`**:
    *   `IXSCAN`: Index scan. Indicates index usage.
    *   `COLLSCAN`: Collection scan. Indicates poor performance.
    *   `FETCH`: Retrieval of physical documents from disk.
    *   `PROJECTION_COVERED`: Confirms the query is a covered query.
2.  **`executionStats`**:
    *   `nReturned`: Number of documents returned to the client.
    *   `keysExamined`: Number of B-Tree index keys scanned.
    *   `docsExamined`: Number of physical documents loaded from disk.
    *   *Optimal Selectivity Ratio*: `keysExamined` should match `nReturned`. If `docsExamined` is high compared to `nReturned`, the query is scanning too many documents.

---

## 10. Hands-on Exercises

### Challenge 1: Compound Index Builder (ESR Rule)
Implement a service method that constructs a compound index for an active orders collection.
The queries targeting this collection filter by `customerId` (Equality) and `orderDate` (Range), while sorting results by `amount` in descending order. Follow the **ESR rule** to design and create the index.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Indexes;
import com.mongodb.client.model.IndexOptions;
import org.bson.Document;
import org.bson.conversions.Bson;

public class OrderIndexService {

    public void createOptimizedOrderIndex(MongoCollection<Document> collection) {
        // TODO: Build compound index following ESR:
        // Equality: customerId (ascending)
        // Sort: amount (descending)
        // Range: orderDate (ascending)
        Bson index = Indexes.compoundIndex(
            Indexes.ascending("customerId"),
            Indexes.descending("amount"),
            Indexes.ascending("orderDate")
        );
        IndexOptions options = new IndexOptions().name("idx_customer_amount_date");
        collection.createIndex(index, options);
    }
}
```

### Challenge 2: Partial TTL Index Setup
Implement a session management service. You must construct an index on the `expiredAt` Date field that automatically deletes documents. To save index space, configure a **partial filter expression** that only indexes documents with the status `"INACTIVE"`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Indexes;
import com.mongodb.client.model.IndexOptions;
import org.bson.Document;
import java.util.concurrent.TimeUnit;

public class SessionIndexService {

    public void createPartialTtlIndex(MongoCollection<Document> collection) {
        // TODO: Create a TTL index on "expiredAt" (ascending) that expires immediately (0 seconds after date).
        // Configure a partialFilterExpression to index only documents where status = "INACTIVE".
        var index = Indexes.ascending("expiredAt");
        Document filter = new Document("status", "INACTIVE");
        IndexOptions options = new IndexOptions()
            .name("idx_inactive_sessions_ttl")
            .expireAfter(0L, TimeUnit.SECONDS)
            .partialFilterExpression(filter);

        collection.createIndex(index, options);
    }
}
```

### Challenge 3: Explain Plan selectivity verification
Implement a query diagnostic parser. The method accepts a raw explain JSON `Document` containing execution stats. You must parse the metrics and return `true` if the query is performing an Index Scan (`IXSCAN`) and matches an index selectivity ratio of `keysExamined / nReturned <= 2.0`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.Document;

public class ExplainAnalyzerService {

    public boolean isQueryOptimized(Document explainDoc) {
        // TODO: Retrieve executionStats.
        // Check if executionStats exists and parse:
        // - totalKeysExamined
        // - nReturned
        // Verify stage contains IXSCAN. Return true if keysExamined / nReturned <= 2.0
        Document executionStats = (Document) explainDoc.get("executionStats");
        if (executionStats == null) {
            return false;
        }

        int keysExamined = executionStats.getInteger("totalKeysExamined", 0);
        int nReturned = executionStats.getInteger("nReturned", 0);

        // Check winning plan stage
        Document queryPlanner = (Document) explainDoc.get("queryPlanner");
        if (queryPlanner == null) {
            return false;
        }
        Document winningPlan = (Document) queryPlanner.get("winningPlan");
        if (winningPlan == null) {
            return false;
        }

        String stage = winningPlan.getString("stage");
        if (stage == null || (!stage.contains("IXSCAN") && !stage.contains("FETCH"))) {
            // Check nested inputStage
            Document inputStage = (Document) winningPlan.get("inputStage");
            if (inputStage != null) {
                stage = inputStage.getString("stage");
            }
        }

        if (stage == null || !stage.contains("IXSCAN")) {
            return false;
        }

        if (nReturned == 0) {
            return keysExamined <= 2; // avoid division by zero
        }

        double ratio = (double) keysExamined / nReturned;
        return ratio <= 2.0;
    }
}
```

### Verification Tests
Verify all three indexing challenges using this JUnit 5 verification test suite:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.IndexOptions;
import org.bson.Document;
import org.bson.conversions.Bson;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class IndexingExercisesTest {

    @SuppressWarnings("unchecked")
    @Test
    void testCreateOptimizedOrderIndex() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        OrderIndexService service = new OrderIndexService();

        service.createOptimizedOrderIndex(mockCol);

        verify(mockCol, times(1)).createIndex(any(Bson.class), any(IndexOptions.class));
    }

    @SuppressWarnings("unchecked")
    @Test
    void testCreatePartialTtlIndex() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        SessionIndexService service = new SessionIndexService();

        service.createPartialTtlIndex(mockCol);

        verify(mockCol, times(1)).createIndex(any(Bson.class), any(IndexOptions.class));
    }

    @Test
    void testExplainAnalyzerOptimized() {
        // Construct a mock explain result document
        Document winningPlan = new Document("stage", "IXSCAN");
        Document queryPlanner = new Document("winningPlan", winningPlan);
        
        Document executionStats = new Document("totalKeysExamined", 10)
                                      .append("nReturned", 8);
        
        Document explainDoc = new Document("queryPlanner", queryPlanner)
                                  .append("executionStats", executionStats);

        ExplainAnalyzerService service = new ExplainAnalyzerService();
        boolean result = service.isQueryOptimized(explainDoc);

        assertTrue(result);
    }

    @Test
    void testExplainAnalyzerPoorSelectivity() {
        Document winningPlan = new Document("stage", "IXSCAN");
        Document queryPlanner = new Document("winningPlan", winningPlan);
        
        // scanned 100 keys to return 5 results
        Document executionStats = new Document("totalKeysExamined", 100)
                                      .append("nReturned", 5);
        
        Document explainDoc = new Document("queryPlanner", queryPlanner)
                                  .append("executionStats", executionStats);

        ExplainAnalyzerService service = new ExplainAnalyzerService();
        boolean result = service.isQueryOptimized(explainDoc);

        assertFalse(result);
    }
}
```
