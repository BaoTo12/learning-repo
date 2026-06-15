# Module 07: Aggregation Framework

Welcome, student. Today we study every aspect of the **Aggregation Framework (CS-529)** using the official MongoDB Java Sync Driver.

---

## 1. What problem does this solve?
While basic CRUD operations allow fetching and modifying individual documents, business applications require complex analytical data processing, such as calculating averages, grouping statistics, joining collections, and building reports.

In relational databases, these tasks are written via SQL using functions like `GROUP BY`, `SUM`, `AVG`, and `JOIN`. Doing this on client applications is highly inefficient, as it requires downloading millions of raw records over the network to calculate a single value.

MongoDB solves this using the **Aggregation Framework**, which provides a multi-stage data processing pipeline. Data transformations are executed directly on the database server, returning only the final calculated aggregate outputs to the client application.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides the Aggregation Framework to:
*   **Keep Calculations Close to Data**: Process millions of records in place at the database engine level (data locality), minimizing CPU and network transfer overhead.
*   **Provide a Declarative Pipeline**: Express complex multi-stage transformations (filtering, grouping, reshaping, sorting) as an array of BSON documents.
*   **Enable Collection Joins**: Execute left-outer joins (`$lookup`) and merge results directly into target collections.
*   **Replace Map-Reduce**: Provide an optimized C++ implementation for aggregations that executes far faster than older Javascript-based Map-Reduce functions.

---

## 3. How does it work internally or conceptually?
*   **The Pipeline Concept**: The framework functions like an assembly line. Input documents from a collection pass through sequential stages. Each stage receives a stream of BSON documents, executes a specific operation (e.g. filters out records, groups elements, or adds new properties), and streams the mutated BSON outputs to the next stage.
*   **Memory Usage & RAM Limits**: By default, each stage in an aggregation pipeline is restricted to **100MB of RAM**. If a stage (like `$group` or `$sort`) exceeds this limit, MongoDB throws a memory execution error. 
*   **Disk Spooling**: To prevent RAM crashes on large datasets, you can set `allowDiskUse(true)`. This allows MongoDB to write temporary buffer blocks to disk if a pipeline stage exceeds the 100MB RAM threshold.
*   **Pipeline Optimizations**: The query optimizer analyzes the pipeline and reorders stages to maximize index efficiency. For instance, it automatically pushes `$match` and `$sort` stages to the beginning of the pipeline if they can utilize indexes.

---

## 4. How do we use it in Java?
We construct aggregation stages programmatically using builders from the `com.mongodb.client.model.Aggregates` and `com.mongodb.client.model.Accumulators` classes. We pass these stages as a `List<Bson>` to the collection's `.aggregate()` method.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Accumulators;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.List;

public class BasicAggregationDemo {
    public void calculateStats(MongoCollection<Document> collection) {
        List<Bson> pipeline = List.of(
            // Stage 1: Filter active users
            Aggregates.match(Filters.eq("status", "ACTIVE")),
            // Stage 2: Group by department and compute average age
            Aggregates.group("$department", Accumulators.avg("averageAge", "$age"))
        );

        collection.aggregate(pipeline).forEach(doc -> System.out.println(doc.toJson()));
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**:
    *   **Data Locality**: Heavy processing happens on the server.
    *   **High Performance**: Native C++ execution plans bypass client serializations.
    *   **Flexible Output**: Outputs can be written to disk (`$merge`, `$out`), formatted as facets, or returned as cursors.
*   **Cons**:
    *   **RAM Limits**: Operations can crash if disk spooling is not enabled.
    *   **Index Limits**: Only the early stages (before grouping/unwinding) can utilize indexes.
    *   **Verbose Syntax**: Deep nested pipeline definitions can be harder to debug than SQL queries.

---

## 6. Common Mistakes
*   **Incorrect Match Placement**: Placing the `$match` filter stage *after* a `$group` or `$unwind` stage. This forces MongoDB to process every single document, completely bypassing index scan capabilities. **Always place $match at the start of the pipeline.**
*   **Unbounded Unwinds**: Unwinding large arrays (`$unwind`) without filtering first. This creates a massive number of temporary documents in memory, leading to RAM saturation.
*   **Forgetting to Project Out Unneeded Fields**: Carrying large, unused fields through multiple stages of the pipeline, which wastes database buffer pool memory.

---

## 7. When should we use it?
*   Use for building reporting dashboards, calculating averages, executing complex analytics, and transforming datasets.
*   Use when joining related collections (`$lookup`) on read request boundaries.

---

## 8. When should we avoid it?
*   Do not use aggregations for simple single-document lookups. Standard `find` queries are faster and use fewer server resources.
*   Do not execute massive multi-stage aggregations in real-time inside high-traffic user requests. Run them asynchronously in background workers, cache results in Redis, or write them to reporting collections via `$merge`.

---

## 9. Code Examples

### A. COMPARISON: FIND VS. AGGREGATE

| Feature | Find Query (`find`) | Aggregation Pipeline (`aggregate`) |
| :--- | :--- | :--- |
| **Primary Purpose** | Fetching and slicing raw documents | Analyzing, grouping, and transforming documents |
| **Execution Model** | Single stage (filter -> sort -> project) | Multi-stage pipeline flow |
| **Computations** | Cannot perform math calculations | Supports accumulators, arithmetic, and string parsing |
| **Joins** | Does not support joins | Supports left-outer joins via `$lookup` |

---

### B. THE PIPELINE STAGES

#### 1. `$match`, `$project`, and `$addFields`
Reshaping documents and adding properties:
*   `$match`: Filters documents (identical to query filters).
*   `$project`: Includes, excludes, or renames fields.
*   `$addFields`: Appends new fields or computes expressions without overwriting existing document shapes.

```java
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Projections;
import org.bson.conversions.Bson;
import org.bson.Document;
import java.util.List;

public class ReshapingStages {
    public List<Bson> buildPipeline() {
        Bson match = Aggregates.match(Filters.eq("status", "ACTIVE"));
        
        // Add a field calculating total score (homework + exam)
        Bson addFields = Aggregates.addFields(List.of(
            new org.bson.Document("totalScore", 
                new org.bson.Document("$add", List.of("$homeworkScore", "$examScore"))
            )
        ));

        // Project: Include specific fields, exclude _id
        Bson project = Aggregates.project(Projections.fields(
            Projections.include("name", "totalScore"),
            Projections.excludeId()
        ));

        return List.of(match, addFields, project);
    }
}
```

#### 2. `$group`, `$sort`, `$limit`, and `$skip`
Aggregating, ordering, and chunking results:
*   `$group`: Collapses documents by a group key (`_id`) and applies accumulator expressions.
*   `$sort`, `$limit`, `$skip`: Orders and paginate records inside the pipeline.

```java
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.Accumulators;
import com.mongodb.client.model.Sorts;
import org.bson.conversions.Bson;
import java.util.List;

public class GroupingStages {
    public List<Bson> buildPipeline() {
        // Group by category, calculate sum of revenue and avg price
        Bson group = Aggregates.group("$category", 
            Accumulators.sum("totalRevenue", "$revenue"),
            Accumulators.avg("averagePrice", "$price")
        );

        // Sort by totalRevenue descending
        Bson sort = Aggregates.sort(Sorts.descending("totalRevenue"));

        // Limit results to top 10 categories
        Bson limit = Aggregates.limit(10);

        return List.of(group, sort, limit);
    }
}
```

#### 3. `$unwind` & `$lookup`
Handling arrays and linking collections:
*   `$unwind`: Splits a document containing an array of size $N$ into $N$ separate documents, copying the rest of the fields.
*   `$lookup`: Joins documents from an external collection.

```java
import com.mongodb.client.model.Aggregates;
import org.bson.conversions.Bson;
import java.util.List;

public class JoinStages {
    public List<Bson> buildPipeline() {
        // Unwind: Split grades array
        Bson unwind = Aggregates.unwind("$grades");

        // Lookup: Left outer join with "courses" collection
        // localField "grades.courseId" matches foreignField "_id" in courses collection
        // Joins matching course documents into a new field "courseDetails"
        Bson lookup = Aggregates.lookup(
            "courses",              // Target collection
            "grades.courseId",      // Local field
            "_id",                  // Foreign field
            "courseDetails"         // Output array field
        );

        return List.of(unwind, lookup);
    }
}
```

#### 4. `$count`, `$facet`, and `$bucket`
Multi-dimensional analysis:
*   `$count`: Counts the number of documents passing through the stage.
*   `$facet`: Runs multiple independent pipeline trees on the same input documents.
*   `$bucket`: Groups documents into price/age boundaries (buckets).

```java
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.BucketOptions;
import org.bson.conversions.Bson;
import org.bson.Document;
import java.util.List;

public class AdvancedAnalysisStages {
    public List<Bson> buildPipeline() {
        // Bucket: Group products by price ranges [0-50], [50-100], [100-200]
        BucketOptions options = new BucketOptions()
            .defaultBucket("expensive")
            .output(List.of(
                new Document("count", new Document("$sum", 1))
            ));
            
        Bson bucket = Aggregates.bucket(
            "$price", 
            List.of(0.0, 50.0, 100.0, 200.0), 
            options
        );

        // Facet: Execute multiple pipeline branches concurrently
        Bson facet = Aggregates.facet(
            new com.mongodb.client.model.Facet("priceBuckets", bucket),
            new com.mongodb.client.model.Facet("countOnly", Aggregates.count())
        );

        return List.of(facet);
    }
}
```

#### 5. `$replaceRoot`, `$merge`, and `$out`
Outputting and reshaping contexts:
*   `$replaceRoot`: Promotes a nested sub-document to be the new top-level root document.
*   `$merge`: Writes pipeline results into a target collection, matching documents and updating fields in-place.
*   `$out`: Overwrites a target collection with the pipeline's output documents.

```java
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.MergeOptions;
import org.bson.conversions.Bson;
import org.bson.Document;
import java.util.List;

public class OutputStages {
    public List<Bson> buildPipeline() {
        // Promote nested subdocument "profile" to root level
        Bson replaceRoot = Aggregates.replaceRoot("$profile");

        // Merge: Upsert pipeline results into the "dashboard_stats" collection
        MergeOptions mergeOptions = new MergeOptions()
            .uniqueIdentifier(List.of("_id"))
            .whenMatched(MergeOptions.WhenMatched.REPLACE)
            .whenNotMatched(MergeOptions.WhenNotMatched.INSERT);
            
        Bson merge = Aggregates.merge("dashboard_stats", mergeOptions);

        return List.of(replaceRoot, merge);
    }
}
```

---

### C. FIVE REAL-WORLD EXAMPLES IN JAVA

Here is an implementation of five standard analytical business queries using the sync driver:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Accumulators;
import com.mongodb.client.model.Sorts;
import com.mongodb.client.model.Projections;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class AggregationQueryService {

    // 1. Count students by course
    public List<Document> countStudentsByCourse(MongoCollection<Document> collection) {
        List<Bson> pipeline = List.of(
            Aggregates.unwind("$enrollments"),
            Aggregates.group("$enrollments.courseCode", Accumulators.sum("studentCount", 1)),
            Aggregates.sort(Sorts.descending("studentCount"))
        );
        return collection.aggregate(pipeline).into(new ArrayList<>());
    }

    // 2. Calculate average score per course
    public List<Document> calculateAverageScore(MongoCollection<Document> collection) {
        List<Bson> pipeline = List.of(
            Aggregates.unwind("$grades"),
            Aggregates.group("$grades.courseCode", Accumulators.avg("averageScore", "$grades.score")),
            Aggregates.sort(Sorts.descending("averageScore"))
        );
        return collection.aggregate(pipeline).into(new ArrayList<>());
    }

    // 3. Get top-selling products (by total revenue)
    public List<Document> getTopSellingProducts(MongoCollection<Document> collection, int limit) {
        List<Bson> pipeline = List.of(
            Aggregates.match(Filters.eq("status", "COMPLETED")),
            Aggregates.unwind("$items"),
            Aggregates.group("$items.productId", 
                Accumulators.sum("unitsSold", "$items.quantity"),
                Accumulators.sum("totalRevenue", new Document("$multiply", List.of("$items.quantity", "$items.price")))
            ),
            Aggregates.sort(Sorts.descending("totalRevenue")),
            Aggregates.limit(limit)
        );
        return collection.aggregate(pipeline).into(new ArrayList<>());
    }

    // 4. Join orders with users (lookup join)
    public List<Document> joinOrdersWithUsers(MongoCollection<Document> ordersCol) {
        List<Bson> pipeline = List.of(
            Aggregates.lookup(
                "users",           // Target collection
                "userId",          // Local field
                "_id",             // Foreign field
                "userDetails"      // Output field array
            ),
            Aggregates.unwind("$userDetails"),
            Aggregates.project(Projections.fields(
                Projections.include("orderId", "amount", "userDetails.username", "userDetails.email"),
                Projections.excludeId()
            ))
        );
        return ordersCol.aggregate(pipeline).into(new ArrayList<>());
    }

    // 5. Build dashboard statistics (Overall metrics)
    public Document buildDashboardStatistics(MongoCollection<Document> ordersCol) {
        List<Bson> pipeline = List.of(
            Aggregates.group(null, // Group all matching documents together
                Accumulators.sum("totalSales", "$amount"),
                Accumulators.avg("avgOrderValue", "$amount"),
                Accumulators.sum("totalOrdersCount", 1)
            )
        );
        return ordersCol.aggregate(pipeline).first();
    }
}
```

---

## 10. Hands-on Exercises

### Challenge 1: Monthly Sales Revenue Aggregation
Implement a billing reporter service. You must compute the monthly sales revenue.
*   Filter for orders with a status of `"PAID"`.
*   Group by the `month` field, calculating the total sum of `revenue`.
*   Sort by `totalRevenue` in descending order.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Accumulators;
import com.mongodb.client.model.Sorts;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class MonthlySalesReportService {

    public List<Document> generateMonthlyReport(MongoCollection<Document> collection) {
        // TODO: Build and run the aggregate pipeline:
        // Match paid orders. Group by month. Sum revenue. Sort descending.
        List<Bson> pipeline = List.of(
            Aggregates.match(Filters.eq("status", "PAID")),
            Aggregates.group("$month", Accumulators.sum("totalRevenue", "$revenue")),
            Aggregates.sort(Sorts.descending("totalRevenue"))
        );
        return collection.aggregate(pipeline).into(new ArrayList<>());
    }
}
```

### Challenge 2: Lookup Student Course Detail Join
Implement a join query service. Given a student enrollment collection, join each student document with their matching course record in the `"courses"` collection.
*   Local field: `"enrolledCourseCode"`
*   Foreign field: `"code"`
*   Output array name: `"courseDetails"`
*   Unwind the output array `"courseDetails"` so it behaves as an embedded document.
*   Exclude the database `_id` field from the final projection.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.Projections;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class StudentCourseJoinService {

    public List<Document> joinStudentsWithCourses(MongoCollection<Document> studentsCol) {
        // TODO: Run lookup join, unwind, project out _id
        List<Bson> pipeline = List.of(
            Aggregates.lookup("courses", "enrolledCourseCode", "code", "courseDetails"),
            Aggregates.unwind("$courseDetails"),
            Aggregates.project(Projections.fields(
                Projections.include("studentName", "enrolledCourseCode", "courseDetails.name"),
                Projections.excludeId()
            ))
        );
        return studentsCol.aggregate(pipeline).into(new ArrayList<>());
    }
}
```

### Challenge 3: Product Price Range Buckets
Implement a catalog analytics service. Group products into price range buckets using the `$bucket` stage.
*   Boundaries: `0.0, 25.0, 75.0, 150.0`
*   Default bucket key name: `"premium"`
*   Output accumulator details: count the number of items inside each bucket.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.BucketOptions;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class ProductBucketAnalytics {

    public List<Document> categorizeProductsByPrice(MongoCollection<Document> collection) {
        // TODO: Build bucket stage and run pipeline
        BucketOptions options = new BucketOptions()
            .defaultBucket("premium")
            .output(List.of(
                new Document("count", new Document("$sum", 1))
            ));

        Bson bucket = Aggregates.bucket("$price", List.of(0.0, 25.0, 75.0, 150.0), options);
        return collection.aggregate(List.of(bucket)).into(new ArrayList<>());
    }
}
```

### Verification Tests
Verify all three aggregation challenges using this JUnit 5 verification test suite:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.AggregateIterable;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class AggregationExercisesTest {

    @SuppressWarnings("unchecked")
    @Test
    void testGenerateMonthlyReport() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        AggregateIterable<Document> mockIterable = mock(AggregateIterable.class);

        when(mockCol.aggregate(any())).thenReturn(mockIterable);
        when(mockIterable.into(any())).thenReturn(List.of(new Document("month", "JAN").append("totalRevenue", 5000.0)));

        MonthlySalesReportService service = new MonthlySalesReportService();
        List<Document> result = service.generateMonthlyReport(mockCol);

        assertNotNull(result);
        assertEquals(1, result.size());
        assertEquals("JAN", result.get(0).getString("month"));
    }

    @SuppressWarnings("unchecked")
    @Test
    void testJoinStudentsWithCourses() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        AggregateIterable<Document> mockIterable = mock(AggregateIterable.class);

        when(mockCol.aggregate(any())).thenReturn(mockIterable);
        when(mockIterable.into(any())).thenReturn(List.of(new Document("studentName", "Bob")));

        StudentCourseJoinService service = new StudentCourseJoinService();
        List<Document> result = service.joinStudentsWithCourses(mockCol);

        assertNotNull(result);
        assertEquals(1, result.size());
    }

    @SuppressWarnings("unchecked")
    @Test
    void testCategorizeProductsByPrice() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        AggregateIterable<Document> mockIterable = mock(AggregateIterable.class);

        when(mockCol.aggregate(any())).thenReturn(mockIterable);
        when(mockIterable.into(any())).thenReturn(List.of(new Document("_id", 0.0).append("count", 15)));

        ProductBucketAnalytics service = new ProductBucketAnalytics();
        List<Document> result = service.categorizeProductsByPrice(mockCol);

        assertNotNull(result);
        assertEquals(1, result.size());
    }
}
```
