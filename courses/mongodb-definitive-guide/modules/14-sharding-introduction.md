# Module 14: Introduction to Sharding (Chapter 14)

Welcome class. Today we analyze **Introduction to Sharding (CS-529)**.

No single host system can scale indefinitely. When write volumes or storage footprints exceed the physical capacity of a replica set, we must partition the dataset horizontally. MongoDB implements this through **Sharding**.

Today we study **Sharded Cluster Architecture**, analyzing query routing mechanics, config servers, targeted queries, and scatter-gather operations in Java.

---

## 1. Academic Lecture: Sharding Topology & Query Execution Plans

### 1. Cluster Architecture
A sharded cluster consists of three main components:
*   **Shards**: Replica sets that store a partition of the cluster's data.
*   **Config Servers**: Replica sets that store the cluster's metadata, directory mappings, and routing tables.
*   **mongos Routers**: Query routers that intercept client calls, retrieve routing targets from config servers, and direct queries to the appropriate shards.

```text
[Java Application]
        │
        ▼ (Reads/Writes)
   [mongos Router]
     ├── (Metadata cache query) ──> [Config Servers]
     ▼ (Direct Routes)
┌──────────────┐      ┌──────────────┐
│  Shard Set A │      │  Shard Set B │
└──────────────┘      └──────────────┘
```

### 2. Query Routing Mechanics
*   **Targeted Queries**: The query contains the shard key. The `mongos` router inspects its routing table and sends the request *only* to the single shard holding that key range.
*   **Scatter-Gather Queries**: The query does not contain the shard key. The `mongos` must broadcast the request to *all* shards, collect the results, and merge them in-memory before returning them.

---

## 2. Theory vs. Production Trade-offs

Compare query routing patterns:

| Metric / Dimension | Shard-Key Targeted Query | Scatter-Gather Broadcast Query |
| :--- | :--- | :--- |
| **Execution Latency** | Low | High (Latency bound by slowest shard) |
| **Shard Resource Load** | Single shard active | All cluster shards active |
| **Network Overhead** | Low | High (Multi-node result sorting) |
| **Optimal Access Pattern** | Single-record fetches / Updates | Analytics / Batch reports |
| **Index Dependencies** | Shard key index utilization | Shard collection indexes on all shards |

---

## 3. How to Use: Analyzing Query Routing in Java

Let us analyze query execution plans. We contrast a scatter-gather query with an optimized targeted query.

### A. The Scatter-Gather Broadcast (Anti-Pattern)
Avoid executing updates or high-frequency lookups without specifying the shard key:

```java
// DANGER: Without specifying the shard key (e.g. storeId), this query 
// forces mongos to broadcast the query to all shards in the cluster, 
// causing massive network and CPU load.
MongoCollection<Document> collection = database.getCollection("orders");
Document order = collection.find(Filters.eq("orderUuid", "9823-1123")).first();
```

### B. The Targeted Query Execution (Production Pattern)
Include the shard key in the filter to direct the query directly to the correct shard:

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;

public class TargetedQueryService {

    public Document findOrder(MongoCollection<Document> collection, String storeId, String orderUuid) {
        // Robust Pattern: Including the shard key (storeId) targets the query to one shard
        return collection.find(
                Filters.and(
                        Filters.eq("storeId", storeId),       // Shard Key
                        Filters.eq("orderUuid", orderUuid)
                )
        ).first();
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Unique Constraint Violations
*   **Why it fails**: Creating a unique index on a non-shard-key field in a sharded collection. Shards only index their local datasets. To enforce unique constraints globally, the index *must* begin with the shard key, or MongoDB will reject index creation.
*   **Mitigation**: Create unique constraints only on the shard key itself, or manage unique indexes in application validation layers.

---

## 5. Socratic Review Questions

### Question 1
Why does a scatter-gather query scale poorly as the number of shards in a cluster increases?

#### Answer
In a scatter-gather query, the `mongos` router broadcasts the request to every shard. As the number of shards grows, the probability of encountering a slow or degraded node increases. Furthermore, sorting and merging large datasets from dozens of shards consumes substantial CPU and memory on the `mongos` instance. This creates a performance bottleneck.

---

## 6. Hands-on Challenge: Explain Plan Routing Analyzer

### The Challenge
In this challenge, you will implement a query plan routing analyzer in Java.
Your task:
1. Complete the method `isScatterGatherQuery` in `QueryPlanAnalyzer`.
2. Given a mock query explain document, evaluate its execution stages.
3. In a sharded cluster, the explain plan contains a `shards` or `executionStages` block. If the stages show that the query was sent to multiple shards (indicated by multiple keys under the `shards` document or `executionStages.stage` equal to `"SHARD_MERGE"`), return `true`. If the query was targeted to a single shard, return `false`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.Document;

public class QueryPlanAnalyzer {

    public boolean isScatterGatherQuery(Document explainDocument) {
        // TODO: Parse the explain document structure to identify if multiple shards were queried
        return false;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import org.bson.Document;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class QueryPlanAnalyzerTest {

    @Test
    void testIsScatterGatherQuery() {
        // Mock a scatter-gather explain document (has SHARD_MERGE stage)
        Document stage = new Document("stage", "SHARD_MERGE");
        Document queryPlanner = new Document("winningPlan", stage);
        Document mockExplain = new Document("queryPlanner", queryPlanner);

        QueryPlanAnalyzer analyzer = new QueryPlanAnalyzer();
        assertTrue(analyzer.isScatterGatherQuery(mockExplain));
    }
}
```
