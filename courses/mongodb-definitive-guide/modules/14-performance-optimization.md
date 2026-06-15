# Module 14: Performance Optimization

Welcome, student. Today we study application-level performance engineering in **MongoDB Performance Tuning (CS-529)**. We will analyze how to write high-performance queries, optimize indexing architectures, configure driver-level resource pools, resolve dynamic query anti-patterns, and interpret query execution plans using diagnostics.

---

## 1. What problem does this solve?

Un-optimized database interaction is the primary source of application latency and resource exhaustion in production environments:
1. **CPU & Memory Bottlenecks**: Database scans (COLLSCAN) force the engine to load millions of documents from disk into RAM, displacing active pages and saturating CPU cores.
2. **Network Saturation**: Querying complete documents when only a few fields are needed wastes bandwidth and increases serialization latency.
3. **Socket Exhaustion**: Creating and tearing down connections on every request consumes system resources and limits throughput.
4. **Consistency vs. Latency Mismatches**: Un-tuned write concerns and read preferences route queries sub-optimally, leading to avoidable latency.

Applying performance engineering principles ensures your application scales efficiently under high load.

---

## 2. Why does MongoDB provide these options?

MongoDB is designed to scale horizontally and handle high throughput. To achieve this, it provides:
*   **Granular Driver Configuration**: Allows developers to optimize socket pooling, client-side batch thresholds, and connection timeouts based on workload requirements.
*   **Flexible Consistency Controls**: Offers read preferences and write concerns to let developers balance read scaling, write durability, and request latency.
*   **Internal Query Engine Diagnostics**: Built-in profilers, slow query logs, and execution plan analysis (`explain()`) enable deep visibility into database operations.

---

## 3. How does it work internally or conceptually?

### Query and Index Optimization
*   **Index Selectivity**: A highly selective index matches a very small percentage of the total documents in a collection. This allows the query engine to pinpoint matching records quickly without scanning unnecessary index keys.
*   **Covered Queries**: If a query's search criteria and requested fields are all present in an index, the query engine returns the results directly from the index in RAM. It bypasses reading the actual documents from disk entirely, resulting in sub-millisecond execution times.
*   **Prefix Matching**: When using compound indexes, query filters must match the index keys from left to right. E.g., an index on `{ a: 1, b: 1 }` can optimize queries filtering on `a` or `a and b`, but cannot optimize queries filtering only on `b`.

### Data Transfer Minimization
*   **Projections**: Limits the fields returned in the query response. This reduces network payload sizes and saves serialization CPU cycles on both the client and server.
*   **Avoiding Large Documents**: The maximum BSON document size in MongoDB is 16MB. Storing large documents increases disk I/O, network latency, and memory usage.
*   **Avoiding Unbounded Arrays**: Appending items to nested arrays (e.g. growing transaction logs inside a user document) causes documents to grow dynamically. When a document outgrows its allocated space, MongoDB must allocate a new contiguous chunk on disk and move the document. This process causes disk fragmentation and slows down subsequent updates.

### Driver Performance Controls

#### Connection Pooling
Reusing open socket connections avoids the high overhead of establishing new TCP handshakes and authenticating on every request.
*   `maxConnectionPoolSize`: The maximum number of parallel connections the driver can open. When reached, new request threads block waiting for a connection to return to the pool.
*   `minConnectionPoolSize`: The minimum number of idle connections maintained in the pool.
*   `maxWaitTime`: The maximum time a thread waits for an available connection from the pool before throwing a timeout exception.

#### Batch Size
The `batchSize` parameter specifies the number of documents returned in a single batch from the database cursor.
*   *Small Batch Size*: Increases network round-trips for large result sets.
*   *Large Batch Size*: Increases server memory usage and network payload sizes, but reduces database-driver round-trips.

#### Cursor Management
MongoDB queries return dynamic cursor objects. Cursors are stateful server-side resources that keep memory allocations active until they are exhausted or explicitly closed.
*   **Cursor Leaks**: Failing to close a cursor leaves the server resource open, consuming RAM until it times out.
*   **Timeout Configuration**: By default, idle cursors time out on the server after 10 minutes. If a query requires more than 10 minutes to process a batch, using the `noCursorTimeout` flag prevents timeout exceptions, but requires manual resource cleanup in `finally` blocks.

### Consistency and Routing Options

#### Read Preferences
Controls how read operations are routed to replica set members:
*   `primary`: (Default) Routes all reads to the primary replica node, ensuring strong read consistency.
*   `primaryPreferred`: Reads from the primary if available, falling back to secondaries if the primary is offline.
*   `secondary`: Routes all reads to secondary nodes. Useful for read-heavy analytical workloads that can tolerate eventual consistency.
*   `secondaryPreferred`: Reads from secondaries first, falling back to the primary if secondaries are unavailable.
*   `nearest`: Reads from the replica set member with the lowest network latency.

#### Write Concerns
Specifies the durability guarantees required from MongoDB before acknowledging a write:
*   `w:1`: Acknowledged once written to the primary's memory. Fastest write latency, but data can be lost if the primary crashes before replicating the write.
*   `w:majority`: Acknowledged once written to a majority of replica set members, protecting against data loss during failovers.
*   `j:true`: Forces the write to flush to the server's disk journal before returning, ensuring durability against power failures.

```text
[Client Write] ──> [Primary Node] ─(Journal: j:true)─> [Disk Journal]
                         │
                  (Replication)
                         ▼
                  [Secondary Node]
```

### Query Anti-Patterns

#### N+1 Query Problem
An anti-pattern where an application executes a query to fetch a list of parent IDs, and then executes a separate query inside a loop for each ID to fetch child details.
*   *Solution*: Query all child documents in a single bulk operation using `Filters.in(...)`, mapping the results in application memory.

#### Unnecessary `$lookup` Joins
Run-time aggregation joins (`$lookup`) are memory-intensive and do not scale well.
*   *Solution*: Denormalize low-frequency, static attributes (e.g. storing product categories directly within order documents) to eliminate the need for joins.

### Diagnostics and Monitoring
*   **Slow Query Monitoring**: Log operations taking longer than the configured `slowms` threshold (default 100ms).
*   **Profiling Levels**:
    - `0`: Profiler off.
    - `1`: Profile slow operations (exceeding `slowms`).
    - `2`: Profile all operations (adds high overhead, useful only in staging environments).
*   **explain() Analysis**:
    Using `.explain("executionStats")` exposes key execution metrics:
    - `totalKeysExamined`: Number of index entries scanned.
    - `totalDocsExamined`: Number of documents read from disk.
    - `nReturned`: Number of documents matching the query.
    - *Selectivity Ratio*: `totalKeysExamined / nReturned`. Ideal ratio is `1.0`. High values indicate poor index selectivity.
    - *Stage indicators*: `COLLSCAN` indicates a table scan; `IXSCAN` indicates an index scan; `PROJECTION_COVERED` indicates a covered query.

---

## 4. How do we use it in Java?

Configuring connection pools, read preferences, and write concerns programmatically:

```java
import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import com.mongodb.ReadPreference;
import com.mongodb.WriteConcern;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import java.util.concurrent.TimeUnit;

public class OptimizedClientBootstrap {

    public static MongoClient createOptimizedClient(String connStr) {
        MongoClientSettings settings = MongoClientSettings.builder()
                .applyConnectionString(new ConnectionString(connStr))
                
                // 1. Connection Pool Tuning
                .applyToConnectionPoolSettings(builder -> builder
                        .maxSize(100) // Allow up to 100 parallel socket channels
                        .minSize(10)  // Keep 10 idle connections warm
                        .maxWaitTime(2000, TimeUnit.MILLISECONDS) // Fail fast if wait time exceeds 2 seconds
                )
                
                // 2. Read Preference Routing
                .readPreference(ReadPreference.secondaryPreferred()) // Read from secondaries to scale reads
                
                // 3. Write Concern Tuning
                .writeConcern(WriteConcern.MAJORITY.withJournal(true)) // Ensure durability
                
                .build();

        return MongoClients.create(settings);
    }
}
```

---

## 5. What are the trade-offs?

| Optimization | Pros | Cons / Risks |
| :--- | :--- | :--- |
| **Index Projections (Covered Queries)** | Extremely fast, zero disk I/O. | Increased RAM usage for larger index sizes. |
| **Secondary Read Preferences** | Scales read throughput, offloads primary. | eventual consistency (clients may read stale data). |
| **Write Concern `w:majority`** | Guarantees durability, prevents rollbacks. | Higher write latency, requires replica sets. |
| **Connection Pooling** | Reuses sockets, reduces latency spikes. | Consumes server descriptors, increases database load. |
| **Denormalization** | Eliminates runtime joins ($lookup). | Complex updates, risk of inconsistent data. |

---

## 6. Common Mistakes

1. **Querying Without Projections**
   Fetching large fields (like nested images or PDFs) that the application doesn't use wastes network bandwidth and memory.
   *Fix*: Always apply `.projection(Projections.include("id", "name"))` to return only required attributes.

2. **Unbounded Array Growth**
   Storing unbounded arrays (like comments or log lines) in a single document causes document size bloat and performance degradation as the document grows.
   *Fix*: Move the array items to a separate collection and reference them by ID, or use the bucket pattern.

3. **Running `$lookup` on Un-indexed Fields**
   Executing an aggregation join on an un-indexed foreign field causes a full collection scan on the target collection for every input document.
   *Fix*: Ensure target fields inside lookup aggregations have matching indexes.

4. **Forgetting to Close Cursors**
   Failing to close cursor streams leaves resources open on the database server, leading to memory leaks and connection degradation over time.
   *Fix*: Use try-with-resources statements when iterating over cursors.

---

## 7. When should we use it?
*   Implement query projections and indexing strategies from the start of development for core application tables.
*   Configure connection pools, write concerns, and read preferences based on application throughput and consistency requirements.

---

## 8. When should we avoid it?
*   Avoid routing reads to secondaries (`ReadPreference.secondary()`) if the application requires immediate consistency (e.g. checking user balances after deposits).
*   Avoid adding indexes to low-cardinality fields (like booleans) where selectivity is low, as the query planner will fall back to table scans.

---

## 9. Code Examples

### 9.1 Resolving the N+1 Query Problem in Java
Here is an example demonstrating the N+1 query problem, followed by the optimized bulk fetch pattern:

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import java.util.ArrayList;
import java.util.List;

public class QueryPatternOptimizer {

    // ANTI-PATTERN: N+1 Queries
    public List<Document> fetchUserOrdersUnoptimized(MongoCollection<Document> users, MongoCollection<Document> orders) {
        List<Document> allOrders = new ArrayList<>();
        
        // Query 1: Fetch users
        for (Document user : users.find()) {
            String userId = user.getString("userId");
            
            // Queries N: Fetch orders for each user ID
            for (Document order : orders.find(Filters.eq("user_id", userId))) {
                allOrders.add(order);
            }
        }
        return allOrders;
    }

    // OPTIMIZED PATTERN: Single Bulk Query
    public List<Document> fetchUserOrdersOptimized(MongoCollection<Document> users, MongoCollection<Document> orders) {
        List<String> userIds = new ArrayList<>();
        
        // Query 1: Fetch user IDs
        for (Document user : users.find().projection(new Document("userId", 1))) {
            userIds.add(user.getString("userId"));
        }

        // Query 2: Fetch all matching orders in a single bulk round-trip
        List<Document> allOrders = new ArrayList<>();
        orders.find(Filters.in("user_id", userIds)).into(allOrders);
        
        return allOrders;
    }
}
```

---

### 9.2 Programmatic Projection Filter
Applying projections to reduce data transfer payloads:

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Projections;
import org.bson.Document;

public class ProjectionQuery {

    public static Document findProductShortDetails(MongoCollection<Document> collection, String productId) {
        return collection.find(Filters.eq("_id", productId))
                .projection(Projections.fields(
                        Projections.include("name", "price", "sku"),
                        Projections.excludeId()
                ))
                .first();
    }
}
```

---

## 10. Hands-on Exercises

### Exercise 1: Connection Pool & Driver Customizer
Complete the builder implementation class to return a `MongoClientSettings` instance configured with the specified connection pool limits, write concern, read preference, and default batch size.

#### Implementation Stub
Complete the helper configuration class:

```java
package com.mongodb.systems;

import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import com.mongodb.ReadPreference;
import com.mongodb.WriteConcern;
import java.util.concurrent.TimeUnit;

public class DriverConfigurator {

    /**
     * Creates MongoClientSettings configured with:
     * - Connection pool maximum size: maxPoolLimit
     * - Read preference: ReadPreference.secondaryPreferred()
     * - Write concern: WriteConcern.MAJORITY
     * - Connection wait timeout: 3000 ms
     */
    public static MongoClientSettings buildCustomSettings(String connectionStr, int maxPoolLimit) {
        // TODO: Build and return settings with pool and consistency controls
        return MongoClientSettings.builder()
                .applyConnectionString(new ConnectionString(connectionStr))
                .applyToConnectionPoolSettings(builder -> builder
                        .maxSize(maxPoolLimit)
                        .maxWaitTime(3000, TimeUnit.MILLISECONDS)
                )
                .readPreference(ReadPreference.secondaryPreferred())
                .writeConcern(WriteConcern.MAJORITY)
                .build();
    }
}
```

#### Verification Test
Run the JUnit 5 test class to verify configuration accuracy:

```java
package com.mongodb.systems;

import static org.junit.jupiter.api.Assertions.*;

import com.mongodb.MongoClientSettings;
import com.mongodb.ReadPreference;
import com.mongodb.WriteConcern;
import org.junit.jupiter.api.Test;

class DriverConfiguratorTest {

    @Test
    void testClientSettingsBuildParameters() {
        String mockUri = "mongodb://localhost:27017/test_db";
        MongoClientSettings settings = DriverConfigurator.buildCustomSettings(mockUri, 75);

        assertNotNull(settings);
        assertEquals(75, settings.getConnectionPoolSettings().getMaxSize());
        assertEquals(3000, settings.getConnectionPoolSettings().getMaxWaitTime(java.util.concurrent.TimeUnit.MILLISECONDS));
        assertEquals(ReadPreference.secondaryPreferred(), settings.getReadPreference());
        assertEquals(WriteConcern.MAJORITY, settings.getWriteConcern());
    }
}
```

---

### Exercise 2: Resolving N+1 Query Anti-Pattern
Complete the customer address lookup utility. The unoptimized implementation queries secondary addresses in a loop, causing N+1 queries. Rewrite the method to execute a single bulk read matching all customer IDs.

#### Implementation Stub
Complete the missing bulk query conversion logic:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import java.util.ArrayList;
import java.util.List;

public class QueryOptimizer {

    /**
     * Resolves N+1 query patterns. Reads customer IDs from customerDocs, 
     * and fetches all matching addresses from addressesCollection in a single bulk call.
     */
    public static List<Document> bulkFetchAddresses(
            List<Document> customerDocs, 
            MongoCollection<Document> addressesCollection
    ) {
        List<String> customerIds = new ArrayList<>();
        
        // 1. Collect all target customerIds
        for (Document cust : customerDocs) {
            String cid = cust.getString("customer_id");
            if (cid != null) {
                customerIds.add(cid);
            }
        }

        // 2. TODO: Query matching addresses in a single collection fetch using Filters.in
        List<Document> results = new ArrayList<>();
        addressesCollection.find(Filters.in("owner_id", customerIds)).into(results);

        return results;
    }
}
```

#### Verification Test
Run this validation test to assert your queries are executed efficiently:

```java
package com.mongodb.systems;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.mongodb.client.FindIterable;
import com.mongodb.client.MongoCollection;
import org.bson.Document;
import org.bson.conversions.Bson;
import org.junit.jupiter.api.Test;
import java.util.Arrays;
import java.util.List;

class QueryOptimizerTest {

    @Test
    @SuppressWarnings("unchecked")
    void testBulkFetchAddressesQueryInCriteria() {
        MongoCollection<Document> mockCollection = mock(MongoCollection.class);
        FindIterable<Document> mockFind = mock(FindIterable.class);

        when(mockCollection.find(any(Bson.class))).thenReturn(mockFind);

        List<Document> customers = Arrays.asList(
                new Document("customer_id", "C100"),
                new Document("customer_id", "C101")
        );

        QueryOptimizer.bulkFetchAddresses(customers, mockCollection);

        // Verify find is called once with an in criteria filter instead of a loop
        verify(mockCollection, times(1)).find(any(Bson.class));
    }
}
```

---

### Exercise 3: explain() Result Analyzer Service
Write a diagnostic tool that parses a MongoDB query `explain()` BSON report. The analyzer must return whether the execution performed a table scan (`COLLSCAN`) or used an index (`IXSCAN`), and calculate the query's index selectivity ratio.

#### Implementation Stub
Complete the explain report analyzer method logic:

```java
package com.mongodb.systems;

import org.bson.Document;

public class ExplainPlanAnalyzer {

    public static class MetricsReport {
        private final boolean indexUsed;
        private final double selectivityRatio;

        public MetricsReport(boolean indexUsed, double selectivityRatio) {
            this.indexUsed = indexUsed;
            this.selectivityRatio = selectivityRatio;
        }

        public boolean isIndexUsed() { return indexUsed; }
        public double getSelectivityRatio() { return selectivityRatio; }
    }

    /**
     * Parses the explain stats document:
     * - Checks if the executionStages.stage equals "IXSCAN" or contains "IXSCAN" (indexUsed = true)
     * - Returns true for indexUsed if "COLLSCAN" is not present in the stage
     * - Calculates selectivityRatio = totalKeysExamined / nReturned
     */
    public static MetricsReport analyzeStats(Document explainResult) {
        Document execStats = (Document) explainResult.get("executionStats");
        if (execStats == null) {
            throw new IllegalArgumentException("Missing executionStats in report");
        }

        int nReturned = execStats.getInteger("nReturned", 0);
        int totalKeys = execStats.getInteger("totalKeysExamined", 0);

        Document stages = (Document) execStats.get("executionStages");
        String stageName = stages != null ? stages.getString("stage") : "";
        boolean indexUsed = stageName != null && !stageName.equals("COLLSCAN");

        double ratio = nReturned > 0 ? (double) totalKeys / nReturned : 0.0;

        return new MetricsReport(indexUsed, ratio);
    }
}
```

#### Verification Test
Run the JUnit 5 test class to verify report parsing:

```java
package com.mongodb.systems;

import static org.junit.jupiter.api.Assertions.*;

import org.bson.Document;
import org.junit.jupiter.api.Test;

class ExplainPlanAnalyzerTest {

    @Test
    void testExplainReportParsingCollscan() {
        Document explain = new Document("executionStats", new Document()
                .append("nReturned", 100)
                .append("totalKeysExamined", 0)
                .append("executionStages", new Document("stage", "COLLSCAN"))
        );

        ExplainPlanAnalyzer.MetricsReport report = ExplainPlanAnalyzer.analyzeStats(explain);
        assertNotNull(report);
        assertFalse(report.isIndexUsed());
        assertEquals(0.0, report.getSelectivityRatio());
    }

    @Test
    void testExplainReportParsingIxscan() {
        Document explain = new Document("executionStats", new Document()
                .append("nReturned", 50)
                .append("totalKeysExamined", 50)
                .append("executionStages", new Document("stage", "IXSCAN"))
        );

        ExplainPlanAnalyzer.MetricsReport report = ExplainPlanAnalyzer.analyzeStats(explain);
        assertNotNull(report);
        assertTrue(report.isIndexUsed());
        assertEquals(1.0, report.getSelectivityRatio());
    }
}
```
