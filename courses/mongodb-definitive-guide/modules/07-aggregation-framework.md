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

- **Keep Calculations Close to Data**: Process millions of records in place at the database engine level (data locality), minimizing CPU and network transfer overhead.
- **Provide a Declarative Pipeline**: Express complex multi-stage transformations (filtering, grouping, reshaping, sorting) as an array of BSON documents.
- **Enable Collection Joins**: Execute left-outer joins (`$lookup`) and merge results directly into target collections.
- **Replace Map-Reduce**: Provide an optimized C++ implementation for aggregations that executes far faster than older Javascript-based Map-Reduce functions.

---

## 3. How does it work internally or conceptually?

- **The Pipeline Concept**: The framework functions like an assembly line. Input documents from a collection pass through sequential stages. Each stage receives a stream of BSON documents, executes a specific operation (e.g. filters out records, groups elements, or adds new properties), and streams the mutated BSON outputs to the next stage.
- **Memory Usage & RAM Limits**: By default, each stage in an aggregation pipeline is restricted to **100MB of RAM**. If a stage (like `$group` or `$sort`) exceeds this limit, MongoDB throws a memory execution error.
- **Disk Spooling**: To prevent RAM crashes on large datasets, you can set `allowDiskUse(true)`. This allows MongoDB to write temporary buffer blocks to disk if a pipeline stage exceeds the 100MB RAM threshold.
- **Pipeline Optimizations**: The query optimizer analyzes the pipeline and reorders stages to maximize index efficiency. For instance, it automatically pushes `$match` and `$sort` stages to the beginning of the pipeline if they can utilize indexes.

---

## 4. How do we use it in Java?

We construct aggregation stages programmatically using builders from the `com.mongodb.client.model.Aggregates` and `com.mongodb.client.model.Accumulators` classes. We pass these stages as a `List<Bson>` to the collection's `.aggregate()` method.

### 4.1 Understanding the Java Driver Helpers

To build BSON pipeline stages without typing verbose nested JSON syntax programmatically, MongoDB provides two main factory classes in its Java Driver.

#### A. com.mongodb.client.model.Aggregates

The `Aggregates` class contains static factory methods that output individual pipeline stages as `Bson` document objects.

Key methods include:

- **`Aggregates.match(Bson filter)`**:
    - _Purpose_: Filters documents to pass only those matching the query filter. Equivalent to `$match`.
    - _Example_: `Aggregates.match(Filters.eq("status", "ACTIVE"))` translates to:
        ```json
        { "$match": { "status": "ACTIVE" } }
        ```
- **`Aggregates.group(Object id, BsonField... accumulators)`**:
    - _Purpose_: Groups incoming documents by a key and aggregates values. Equivalent to `$group`.
    - _Example_: `Aggregates.group("$department", Accumulators.sum("total", 1))` translates to:
        ```json
        { "$group": { "_id": "$department", "total": { "$sum": 1 } } }
        ```
- **`Aggregates.project(Bson projection)`**:
    - _Purpose_: Filters the fields of output documents (includes, excludes, or renames). Equivalent to `$project`.
    - _Example_: `Aggregates.project(Projections.fields(Projections.include("name"), Projections.excludeId()))` translates to:
        ```json
        { "$project": { "name": 1, "_id": 0 } }
        ```
- **`Aggregates.unwind(String fieldName)`**:
    - _Purpose_: Deconstructs an array field, outputting a document for each element. Equivalent to `$unwind`. Aggregates.lookup(String from, String localField, String foreignField, String as) → xử lý array bên trong document.
    - _Example_: `Aggregates.unwind("$grades")` translates to:
        ```json
        { "$unwind": "$grades" }
        ```
- **`Aggregates.lookup(String from, String localField, String foreignField, String as)`**:
    - _Purpose_: Left outer joins another collection. Equivalent to `$lookup`. → "join" dữ liệu giữa các collections.
    - _Example_: `Aggregates.lookup("courses", "enrolledCode", "code", "courseDetail")` translates to:
        ```json
        {
            "$lookup": {
                "from": "courses",
                "localField": "enrolledCode",
                "foreignField": "code",
                "as": "courseDetail"
            }
        }
        ```

#### B. com.mongodb.client.model.Accumulators

The `Accumulators` class contains static helper methods used exclusively inside the `$group` stage (specifically as arguments to `Aggregates.group`) to define how values are aggregated across grouped documents.

Key methods include:

- **`Accumulators.sum(String fieldName, Object expression)`**:
    - _Purpose_: Sums numeric values or counts entries.
    - _Example_: `Accumulators.sum("totalRevenue", "$revenue")` translates to:
        ```json
        { "totalRevenue": { "$sum": "$revenue" } }
        ```
    - _Example (Count)_: `Accumulators.sum("count", 1)` translates to:
        ```json
        { "count": { "$sum": 1 } }
        ```
- **`Accumulators.avg(String fieldName, Object expression)`**:
    - _Purpose_: Calculates the average of numeric values.
    - _Example_: `Accumulators.avg("averageAge", "$age")` translates to:
        ```json
        { "averageAge": { "$avg": "$age" } }
        ```
- **`Accumulators.first(String fieldName, Object expression)`**:
    - _Purpose_: Returns the value of the first document in the group (typically useful after a `$sort` stage).
    - _Example_: `Accumulators.first("firstOrder", "$orderId")` translates to:
        ```json
        { "firstOrder": { "$first": "$orderId" } }
        ```
- **`Accumulators.push(String fieldName, Object expression)`**:
    - _Purpose_: Appends all values from the grouped documents into an array.
    - _Example_: `Accumulators.push("allScores", "$score")` translates to:
        ```json
        { "allScores": { "$push": "$score" } }
        ```
- **`Accumulators.addToSet(String fieldName, Object expression)`**:
    - _Purpose_: Appends values into a set, automatically filtering out duplicate entries.
    - _Example_: `Accumulators.addToSet("uniqueDepartments", "$dept")` translates to:
        ```json
        { "uniqueDepartments": { "$addToSet": "$dept" } }
        ```

### 4.2 Dataset Visualization Example

#### Input Dataset (`users` Collection):

```json
[
    {
        "_id": 1,
        "name": "Alice",
        "status": "ACTIVE",
        "department": "HR",
        "age": 30
    },
    {
        "_id": 2,
        "name": "Bob",
        "status": "ACTIVE",
        "department": "Engineering",
        "age": 40
    },
    {
        "_id": 3,
        "name": "Charlie",
        "status": "INACTIVE",
        "department": "HR",
        "age": 50
    },
    {
        "_id": 4,
        "name": "David",
        "status": "ACTIVE",
        "department": "HR",
        "age": 20
    }
]
```

#### Step-by-Step Pipeline Trace:

1. **Stage 1: `$match` (Filter Active Users)**
   Documents are evaluated against the filter `status == "ACTIVE"`.
    - Document 3 (`Charlie`) is discarded.
    - Passed to next stage:
        ```json
        [
            {
                "_id": 1,
                "name": "Alice",
                "status": "ACTIVE",
                "department": "HR",
                "age": 30
            },
            {
                "_id": 2,
                "name": "Bob",
                "status": "ACTIVE",
                "department": "Engineering",
                "age": 40
            },
            {
                "_id": 4,
                "name": "David",
                "status": "ACTIVE",
                "department": "HR",
                "age": 20
            }
        ]
        ```

2. **Stage 2: `$group` (Group by department, average age)**
   The remaining documents are grouped by the value of the `department` field:
    - Group `HR`: Alice (30) and David (20). Average age: $\frac{30 + 20}{2} = 25.0$.
    - Group `Engineering`: Bob (40). Average age: $\frac{40}{1} = 40.0$.

#### Final Output Dataset:

```json
[
    { "_id": "HR", "averageAge": 25.0 },
    { "_id": "Engineering", "averageAge": 40.0 }
]
```

### 4.3 Java Implementation Code

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

- **Pros**:
    - **Data Locality**: Heavy processing happens on the server.
    - **High Performance**: Native C++ execution plans bypass client serializations.
    - **Flexible Output**: Outputs can be written to disk (`$merge`, `$out`), formatted as facets, or returned as cursors.
- **Cons**:
    - **RAM Limits**: Operations can crash if disk spooling is not enabled.
    - **Index Limits**: Only the early stages (before grouping/unwinding) can utilize indexes.
    - **Verbose Syntax**: Deep nested pipeline definitions can be harder to debug than SQL queries.

---

## 6. Common Mistakes

- **Incorrect Match Placement**: Placing the `$match` filter stage _after_ a `$group` or `$unwind` stage. This forces MongoDB to process every single document, completely bypassing index scan capabilities. **Always place $match at the start of the pipeline.**
- **Unbounded Unwinds**: Unwinding large arrays (`$unwind`) without filtering first. This creates a massive number of temporary documents in memory, leading to RAM saturation.
- **Forgetting to Project Out Unneeded Fields**: Carrying large, unused fields through multiple stages of the pipeline, which wastes database buffer pool memory.

---

## 7. When should we use it?

- Use for building reporting dashboards, calculating averages, executing complex analytics, and transforming datasets.
- Use when joining related collections (`$lookup`) on read request boundaries.

---

## 8. When should we avoid it?

- Do not use aggregations for simple single-document lookups. Standard `find` queries are faster and use fewer server resources.
- Do not execute massive multi-stage aggregations in real-time inside high-traffic user requests. Run them asynchronously in background workers, cache results in Redis, or write them to reporting collections via `$merge`.

---

## 9. Code Examples

### A. COMPARISON: FIND VS. AGGREGATE

| Feature             | Find Query (`find`)                      | Aggregation Pipeline (`aggregate`)                    |
| :------------------ | :--------------------------------------- | :---------------------------------------------------- |
| **Primary Purpose** | Fetching and slicing raw documents       | Analyzing, grouping, and transforming documents       |
| **Execution Model** | Single stage (filter -> sort -> project) | Multi-stage pipeline flow                             |
| **Computations**    | Cannot perform math calculations         | Supports accumulators, arithmetic, and string parsing |
| **Joins**           | Does not support joins                   | Supports left-outer joins via `$lookup`               |

---

### B. THE PIPELINE STAGES

#### 1. `$match`, `$project`, and `$addFields`

- `$match`: Filters documents using standard query syntax.
- `$addFields`: Adds new fields to documents. The syntax is `{"$addFields": { "newFieldName": <expression> }}`.
- `$project`: Filters the output document shape by including (`1`) or excluding (`0`) fields.

##### Dataset Visualization Example

###### Input Dataset (`students` Collection):

```json
[
    {
        "_id": 1,
        "name": "Alice",
        "status": "ACTIVE",
        "homeworkScore": 80,
        "examScore": 90
    },
    {
        "_id": 2,
        "name": "Bob",
        "status": "INACTIVE",
        "homeworkScore": 70,
        "examScore": 75
    },
    {
        "_id": 3,
        "name": "Charlie",
        "status": "ACTIVE",
        "homeworkScore": 95,
        "examScore": 95
    }
]
```

###### Step-by-Step Pipeline Trace:

1. **Stage 1: `$match` (Filter active)**
    - Alice and Charlie are kept. Bob is discarded.
2. **Stage 2: `$addFields` (Calculate `totalScore`)**
    - Computes `homeworkScore` + `examScore` using `$add`.
    - Intermediate document shape:
        ```json
        {
            "_id": 1,
            "name": "Alice",
            "status": "ACTIVE",
            "homeworkScore": 80,
            "examScore": 90,
            "totalScore": 170
        }
        ```
3. **Stage 3: `$project` (Shape document output)**
    - Includes `name` and `totalScore`. Excludes `_id` explicitly.
    - Discards all other fields.

###### Final Output Dataset:

```json
[
    { "name": "Alice", "totalScore": 170 },
    { "name": "Charlie", "totalScore": 190 }
]
```

##### Java Implementation Code:

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

---

#### 2. `$group`, `$sort`, `$limit`, and `$skip`

- `$group`: Aggregates documents by a key and calculates totals using accumulator operators like `$sum` and `$avg`.
- `$sort`: Sorts documents by columns in ascending (`1`) or descending (`-1`) order.
- `$limit`: Restricts the output to the first $N$ documents.

##### Dataset Visualization Example

###### Input Dataset (`sales` Collection):

```json
[
    { "_id": 1, "category": "Electronics", "revenue": 1000, "price": 500 },
    { "_id": 2, "category": "Books", "revenue": 150, "price": 15 },
    { "_id": 3, "category": "Electronics", "revenue": 2000, "price": 1000 },
    { "_id": 4, "category": "Books", "revenue": 300, "price": 30 },
    { "_id": 5, "category": "Home", "revenue": 800, "price": 400 }
]
```

###### Step-by-Step Pipeline Trace:

1. **Stage 1: `$group` (Group by category, sum revenue, average price)**
    - Group `Electronics`: Sum revenue ($1000+2000=3000$), Avg price ($\frac{500+1000}{2}=750.0$).
    - Group `Books`: Sum revenue ($150+300=450$), Avg price ($\frac{15+30}{2}=22.5$).
    - Group `Home`: Sum revenue ($800$), Avg price ($400.0$).
    - Intermediate dataset:
        ```json
        [
            {
                "_id": "Electronics",
                "totalRevenue": 3000,
                "averagePrice": 750.0
            },
            { "_id": "Books", "totalRevenue": 450, "averagePrice": 22.5 },
            { "_id": "Home", "totalRevenue": 800, "averagePrice": 400.0 }
        ]
        ```
2. **Stage 2: `$sort` (Sort by totalRevenue descending)**
    - Ordered: `Electronics` (3000) -> `Home` (800) -> `Books` (450).
3. **Stage 3: `$limit` (Limit to top 2 categories)**
    - Only the first 2 documents are kept.

###### Final Output Dataset:

```json
[
    { "_id": "Electronics", "totalRevenue": 3000, "averagePrice": 750.0 },
    { "_id": "Home", "totalRevenue": 800, "averagePrice": 400.0 }
]
```

##### Java Implementation Code:

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

---

#### 3. `$unwind` & `$lookup`

- `$unwind`: Deconstructs an array field from the input documents to output a document for each element.
- `$lookup`: Performs a left outer join to an unsharded collection in the same database.
    - `from`: The collection to join.
    - `localField`: The field in the input documents to match with.
    - `foreignField`: The field in the joined collection.
    - `as`: The name of the output array field to append.

##### Dataset Visualization Example

###### Input Dataset (`students` Collection):

```json
[
    {
        "_id": 1,
        "name": "Alice",
        "grades": [{ "courseId": "CS-101", "score": 90 }]
    }
]
```

###### Input Dataset (`courses` Collection):

```json
[{ "_id": "CS-101", "title": "Intro to Computer Science" }]
```

###### Step-by-Step Pipeline Trace:

1. **Stage 1: `$unwind` (Split grades array)**
    - Decouples the grades array. Output:
        ```json
        {
            "_id": 1,
            "name": "Alice",
            "grades": { "courseId": "CS-101", "score": 90 }
        }
        ```
2. **Stage 2: `$lookup` (Left outer join with courses)**
    - Matches `grades.courseId` (`"CS-101"`) with `_id` in `courses` collection.
    - Appends matching course details into an array named `courseDetails`.

###### Final Output Dataset:

```json
[
    {
        "_id": 1,
        "name": "Alice",
        "grades": { "courseId": "CS-101", "score": 90 },
        "courseDetails": [
            { "_id": "CS-101", "title": "Intro to Computer Science" }
        ]
    }
]
```

##### Java Implementation Code:

```java
import com.mongodb.client.model.Aggregates;
import org.bson.conversions.Bson;
import java.util.List;

public class JoinStages {
    public List<Bson> buildPipeline() {
        // Unwind: Split grades array
        Bson unwind = Aggregates.unwind("$grades");

        // Lookup: Left outer join with "courses" collection
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

---

#### 4. `$count`, `$facet`, and `$bucket`

- `$bucket`: Categorizes incoming documents into groups called buckets, based on a specified expression and boundaries.
- `$facet`: Processes multiple aggregation pipelines in parallel within a single stage on the same set of input documents.

##### Dataset Visualization Example

###### Input Dataset (`products` Collection):

```json
[
    { "_id": 1, "name": "Pen", "price": 10.0 },
    { "_id": 2, "name": "Notebook", "price": 60.0 },
    { "_id": 3, "name": "Backpack", "price": 120.0 },
    { "_id": 4, "name": "Laptop", "price": 1200.0 }
]
```

###### Step-by-Step Pipeline Trace:

1. **Bucket Branch (priceBuckets)**:
    - Boundaries: `[0.0, 50.0]`, `[50.0, 100.0]`, `[100.0, 200.0]`. Everything else goes to `"expensive"`.
    - Pen (price 10.0) -> bucket `0.0`. (Count = 1).
    - Notebook (price 60.0) -> bucket `50.0`. (Count = 1).
    - Backpack (price 120.0) -> bucket `100.0`. (Count = 1).
    - Laptop (price 1200.0) -> bucket `"expensive"`. (Count = 1).
2. **Count Branch (countOnly)**:
    - Counts total incoming products. (Count = 4).
3. **Facet Join**:
    - Combines both outputs into a single object with keys matching the facet branch names.

###### Final Output Dataset:

```json
[
    {
        "priceBuckets": [
            { "_id": 0.0, "count": 1 },
            { "_id": 50.0, "count": 1 },
            { "_id": 100.0, "count": 1 },
            { "_id": "expensive", "count": 1 }
        ],
        "countOnly": [{ "count": 4 }]
    }
]
```

##### Java Implementation Code:

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

---

#### 5. `$replaceRoot`, `$merge`, and `$out`

- `$replaceRoot`: Replaces the input document with the specified embedded document, promoting it to root.
- `$merge`: Writes query output directly into an existing collection. It matches documents based on a unique identifier and updates them.

##### Dataset Visualization Example

###### Input Dataset (`orders` Collection):

```json
[
    {
        "_id": 1,
        "orderNum": "ORD-12",
        "profile": { "_id": "CUST-99", "tier": "GOLD", "loyaltyPoints": 450 }
    }
]
```

###### Step-by-Step Pipeline Trace:

1. **Stage 1: `$replaceRoot` (Promote subdocument)**
    - Extracts `profile` subdocument and discards outer fields.
    - Intermediate document shape:
        ```json
        { "_id": "CUST-99", "tier": "GOLD", "loyaltyPoints": 450 }
        ```
2. **Stage 2: `$merge` (Merge into target collection)**
    - Writes/updates this document into the `"dashboard_stats"` collection based on `_id` (`"CUST-99"`). If it exists, it replaces it; otherwise, it inserts it.

###### Final Output in `"dashboard_stats"` Collection:

```json
{ "_id": "CUST-99", "tier": "GOLD", "loyaltyPoints": 450 }
```

##### Java Implementation Code:

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

Here is the implementation of five standard business reports with their corresponding data formats and trace flows:

#### 1. Count students by course

- **Goal**: Count enrollments for each course across the student collection.

##### Input Dataset (`students` Collection):

```json
[
    {
        "_id": 1,
        "name": "Alice",
        "enrollments": [{ "courseCode": "CS-101" }, { "courseCode": "CS-202" }]
    },
    { "_id": 2, "name": "Bob", "enrollments": [{ "courseCode": "CS-101" }] }
]
```

##### Step-by-Step Pipeline Trace:

1. **`$unwind`**: Splits Alice's enrollments into two separate documents. Output:
    ```json
    { "name": "Alice", "enrollments": { "courseCode": "CS-101" } }
    { "name": "Alice", "enrollments": { "courseCode": "CS-202" } }
    { "name": "Bob", "enrollments": { "courseCode": "CS-101" } }
    ```
2. **`$group`**: Groups by `enrollments.courseCode` and sums occurrences. Output:
    - Group `CS-101`: Alice, Bob (2)
    - Group `CS-202`: Alice (1)
3. **`$sort`**: Orders by `studentCount` descending.

##### Final Output:

```json
[
    { "_id": "CS-101", "studentCount": 2 },
    { "_id": "CS-202", "studentCount": 1 }
]
```

---

#### 2. Calculate average score per course

- **Goal**: Calculate average score by unpacking grade structures.

##### Input Dataset (`students` Collection):

```json
[
    {
        "_id": 1,
        "grades": [
            { "courseCode": "CS-101", "score": 90 },
            { "courseCode": "CS-202", "score": 80 }
        ]
    },
    { "_id": 2, "grades": [{ "courseCode": "CS-101", "score": 100 }] }
]
```

##### Step-by-Step Pipeline Trace:

1. **`$unwind`**: Splits grades arrays.
2. **`$group`**: Groups by `grades.courseCode` and calculates `$avg` on `grades.score`.
    - Group `CS-101`: $\frac{90+100}{2} = 95.0$.
    - Group `CS-202`: $80.0$.
3. **`$sort`**: Sorts by `averageScore` descending.

##### Final Output:

```json
[
    { "_id": "CS-101", "averageScore": 95.0 },
    { "_id": "CS-202", "averageScore": 80.0 }
]
```

---

#### 3. Get top-selling products (by total revenue)

- **Goal**: Compute sales revenue per product for completed orders.

##### Input Dataset (`orders` Collection):

```json
[
    {
        "_id": 1,
        "status": "COMPLETED",
        "items": [{ "productId": "PROD-A", "quantity": 2, "price": 50 }]
    },
    {
        "_id": 2,
        "status": "PENDING",
        "items": [{ "productId": "PROD-A", "quantity": 10, "price": 50 }]
    },
    {
        "_id": 3,
        "status": "COMPLETED",
        "items": [
            { "productId": "PROD-A", "quantity": 1, "price": 50 },
            { "productId": "PROD-B", "quantity": 1, "price": 300 }
        ]
    }
]
```

##### Step-by-Step Pipeline Trace:

1. **`$match`**: Filters status = `COMPLETED`. Order 2 is discarded.
2. **`$unwind`**: Splits item arrays for Order 1 and Order 3.
3. **`$group`**: Groups by product ID.
    - `PROD-A`: Sums quantity ($2 + 1 = 3$), Sums total revenue ($2 \times 50 + 1 \times 50 = 150.0$).
    - `PROD-B`: Sums quantity ($1$), Sums total revenue ($1 \times 300 = 300.0$).
4. **`$sort`**: Sorts by `totalRevenue` descending.
5. **`$limit`**: Restricts output.

##### Final Output:

```json
[
    { "_id": "PROD-B", "unitsSold": 1, "totalRevenue": 300.0 },
    { "_id": "PROD-A", "unitsSold": 3, "totalRevenue": 150.0 }
]
```

---

#### 4. Join orders with users (lookup join)

- **Goal**: De-normalize order documents by pulling user profiles.

##### Input Dataset (`orders` Collection):

```json
[{ "_id": 101, "userId": 1, "amount": 99.0 }]
```

##### Input Dataset (`users` Collection):

```json
[{ "_id": 1, "username": "clara99", "email": "clara@mail.com" }]
```

##### Step-by-Step Pipeline Trace:

1. **`$lookup`**: Joins `users` on `userId`. Appends matching user details as an array `userDetails`.
2. **`$unwind`**: Deconstructs the single-element array to an object:
    ```json
    {
        "_id": 101,
        "userId": 1,
        "amount": 99.0,
        "userDetails": { "username": "clara99", "email": "clara@mail.com" }
    }
    ```
3. **`$project`**: Includes defined fields, discards others, and drops `_id`.

##### Final Output:

```json
[
    {
        "orderId": 101,
        "amount": 99.0,
        "userDetails": { "username": "clara99", "email": "clara@mail.com" }
    }
]
```

---

#### 5. Build dashboard statistics (Overall metrics)

- **Goal**: Calculate database aggregates across the entire collection.

##### Input Dataset (`orders` Collection):

```json
[
    { "_id": 1, "amount": 100.0 },
    { "_id": 2, "amount": 200.0 },
    { "_id": 3, "amount": 300.0 }
]
```

##### Step-by-Step Pipeline Trace:

1. **`$group`**: Groups by `null` (evaluates all input documents together).
    - Calculates sum of amount ($100+200+300 = 600.0$).
    - Calculates avg of amount ($\frac{100+200+300}{3} = 200.0$).
    - Calculates count of documents ($3$).

##### Final Output:

```json
{
    "totalSales": 600.0,
    "avgOrderValue": 200.0,
    "totalOrdersCount": 3
}
```

##### Java Implementation Class (`AggregationQueryService`):

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

- Filter for orders with a status of `"PAID"`.
- Group by the `month` field, calculating the total sum of `revenue`.
- Sort by `totalRevenue` in descending order.

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

- Local field: `"enrolledCourseCode"`
- Foreign field: `"code"`
- Output array name: `"courseDetails"`
- Unwind the output array `"courseDetails"` so it behaves as an embedded document.
- Exclude the database `_id` field from the final projection.

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

- Boundaries: `0.0, 25.0, 75.0, 150.0`
- Default bucket key name: `"premium"`
- Output accumulator details: count the number of items inside each bucket.

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
