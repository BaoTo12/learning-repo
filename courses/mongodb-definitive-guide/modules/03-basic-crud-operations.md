# Module 03: Basic CRUD Operations

Welcome, student. Today we study every aspect of **Basic CRUD Operations & modifications (CS-529)** using the official MongoDB Java Sync Driver.

---

## 1. What problem does this solve?
For a database to be useful, applications must be able to insert records, query them, modify them, and delete them. In relational databases, these tasks use structured SQL statements (`INSERT`, `SELECT`, `UPDATE`, `DELETE`). 

MongoDB solves this by executing CRUD operations using BSON objects directly. This maps cleanly to Java classes, avoids parsing text SQL queries, and enables in-place atomic updates. It avoids the Object-Relational Impedance Mismatch by allowing data to be stored in documents that match application entities directly, without mapping tables, foreign keys, and joints.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides document-level CRUD APIs to:
*   **Optimize Network Transfers**: Update modifiers modify fields on disk without downloading or replacing the entire document.
*   **Enable In-place Mutations**: WiredTiger updates fields in memory and writes changes to the journal, preventing document write conflicts.
*   **Support Dynamic Schema**: Field additions, array modifications, and nested object adjustments can be made dynamically on individual documents without executing database-wide schema migration scripts.

---

## 3. How does it work internally or conceptually?
*   **Insertions**: The driver converts Java POJOs or Document maps into raw BSON byte arrays, computes the size, and sends them to the server. The server writes records to memory buffers (WiredTiger Cache), updates index structures (B-Trees), and logs the action to the transaction journal for durability.
*   **Reads**: MongoDB traverses B-Tree index pointers (`IXSCAN`) or performs collection scans (`COLLSCAN`) to load documents into memory. The cursor manages batch sizes (default 101 documents or 16MB), sending documents in groups to prevent client memory spikes.
*   **Updates**: WiredTiger modifies document values directly in memory. If the updated document fits within its allocated storage block, the mutation happens in-place. If the document size increases beyond its allocated page size (document growth), WiredTiger relocates it on disk, updating all index reference pointers.
*   **Deletes**: Document record flags are marked as deleted, and index reference pointers are pruned. The deleted space is reclaimed by the WiredTiger engine internally for future writes, but disk space is not immediately returned to the host OS (a process called table fragmentation).

---

## 4. How do we use it in Java?
We connect to a `MongoCollection<Document>` and execute statements using the static helper builders from `Filters` and `Updates`.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class SampleCrud {
    public void run(MongoCollection<Document> collection) {
        // Create
        collection.insertOne(new Document("_id", "1").append("name", "Alice"));
        
        // Read
        Document doc = collection.find(Filters.eq("name", "Alice")).first();
        
        // Update
        collection.updateOne(Filters.eq("_id", "1"), Updates.set("age", 21));
        
        // Delete
        collection.deleteOne(Filters.eq("_id", "1"));
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**:
    *   **Atomic Updates**: Modifying a document is atomic at the single-document level.
    *   **Reduced Network Payload**: Modifier operators allow client applications to send only small instruction sets (like `$inc` or `$set`) instead of the entire document.
    *   **Flexible Structure**: Documents in the same collection do not need to share the same fields.
*   **Cons**:
    *   **No Referential Integrity**: Relational constraints (e.g. `FOREIGN KEY`) must be enforced at the application level.
    *   **Unbounded Array Growth**: Appending elements to arrays can lead to documents exceeding the 16MB limit.
    *   **Complex Nested Array Mutations**: Updating deeply nested arrays requires verbose positional operators and `arrayFilters`.

---

## 6. Common Mistakes
*   **Overwriting with `replaceOne`**: Using `replaceOne` to change a single property, which accidentally deletes other unmentioned fields in the document and can overwrite concurrent updates from other worker threads. **Always prefer updateOne with $set.**
*   **Unbounded Deletes**: Calling `deleteMany` with an empty filter document, which deletes all data in the collection.
*   **Array Replacement via Set**: Using `Updates.set("tags", "new-tag")` instead of `Updates.push("tags", "new-tag")` to add an element to an array, which overwrites the entire array with a string value.

---

## 7. When should we use it?
*   Use for all primary database entity interactions, batch data imports, and state modifications.
*   Use atomic operators (`$inc`, `$push`, `$set`) whenever multiple processes might update the same document concurrently.

---

## 8. When should we avoid it?
*   Do not perform massive operations inside a synchronous web request thread. Use background tasks or queue systems.
*   Do not use simple CRUD operations when complex multi-document transactional guarantees are needed across dozens of collections. Instead, use Multi-Document Transactions (see Module 9).

---

## 9. Code Examples

### A. CREATE OPERATIONS

#### 1. `insertOne` & `insertMany`
Inserts a single document or multiple documents into a collection.

```java
import com.mongodb.client.MongoCollection;
import org.bson.Document;
import java.util.List;
import java.util.Arrays;

public class CreateOperationsDemo {
    public void run(MongoCollection<Document> collection) {
        // insertOne: Creates a single document
        Document student = new Document("name", "John Doe")
                            .append("email", "john.doe@university.edu")
                            .append("status", "ACTIVE");
        collection.insertOne(student);

        // insertMany: Inserts multiple documents in one network call
        Document student1 = new Document("name", "Alice Smith").append("status", "ACTIVE");
        Document student2 = new Document("name", "Bob Jones").append("status", "PENDING");
        
        List<Document> list = Arrays.asList(student1, student2);
        collection.insertMany(list);
    }
}
```

#### 2. Ordered vs. Unordered Inserts
*   **Ordered Inserts (Default)**: MongoDB executes inserts sequentially. If one document fails (e.g. due to duplicate key), execution stops immediately, and the remaining documents are **not** inserted.
*   **Unordered Inserts**: MongoDB parallelizes writes. If one fails, the database continues processing the remaining documents.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.InsertManyOptions;
import org.bson.Document;
import java.util.List;

public class OrderInsertsDemo {
    public void run(MongoCollection<Document> collection, List<Document> documents) {
        // Ordered insert
        collection.insertMany(documents, new InsertManyOptions().ordered(true));

        // Unordered insert - will process all documents even if some fail
        collection.insertMany(documents, new InsertManyOptions().ordered(false));
    }
}
```

#### 3. Batch Insert (Splitting Large Collections)
When inserting huge datasets, you should batch them (e.g., 500 or 1000 records at a time) to avoid memory starvation and respect the maximum BSON size limit.

```java
import com.mongodb.client.MongoCollection;
import org.bson.Document;
import java.util.ArrayList;
import java.util.List;

public class BatchInsertDemo {
    public void insertInBatches(MongoCollection<Document> collection, List<Document> largeDataset, int batchSize) {
        List<Document> batch = new ArrayList<>();
        for (Document doc : largeDataset) {
            batch.add(doc);
            if (batch.size() == batchSize) {
                collection.insertMany(batch);
                batch.clear();
            }
        }
        if (!batch.isEmpty()) {
            collection.insertMany(batch);
        }
    }
}
```

#### 4. Duplicate Key Errors
If you attempt to insert a duplicate value for a unique index (like the default `_id` field), a `MongoWriteException` is thrown. We catch this, inspect the error code, and resolve it defensively.

```java
import com.mongodb.MongoWriteException;
import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class DuplicateKeyHandler {
    public boolean insertSafe(MongoCollection<Document> collection, Document doc) {
        try {
            collection.insertOne(doc);
            return true;
        } catch (MongoWriteException e) {
            // Error code 11000 indicates duplicate key violation
            if (e.getError().getCode() == 11000) {
                System.err.println("Write failed: Duplicate primary key found. Message: " + e.getMessage());
                return false;
            }
            throw e; // Re-throw other write exceptions
        }
    }
}
```

#### 5. Custom `_id` vs. Generated `_id`
*   **Generated `_id`**: If the `_id` field is omitted from a document, the driver automatically generates and attaches a unique 12-byte `org.bson.types.ObjectId`.
*   **Custom `_id`**: You can explicitly assign custom primary keys (like UUIDs, natural strings, or sequential numbers).

```java
import com.mongodb.client.MongoCollection;
import org.bson.Document;
import java.util.UUID;

public class IdCustomizationDemo {
    public void run(MongoCollection<Document> collection) {
        // Generated: Driver automatically generates an ObjectId
        Document doc1 = new Document("name", "Jane");
        collection.insertOne(doc1);
        System.out.println("Generated ID: " + doc1.get("_id")); // Will print an ObjectId

        // Custom: Primary key specified manually
        String customId = "STUDENT-" + UUID.randomUUID().toString().substring(0, 8);
        Document doc2 = new Document("_id", customId).append("name", "Mark");
        collection.insertOne(doc2);
        System.out.println("Custom ID: " + doc2.get("_id")); // Will print the custom string
    }
}
```

#### 6. `InsertOneResult` & `InsertManyResult`
These classes let you retrieve the database-assigned identifiers after a write operation.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.result.InsertOneResult;
import com.mongodb.client.result.InsertManyResult;
import org.bson.Document;
import org.bson.BsonValue;
import java.util.List;
import java.util.Map;

public class InsertResultDemo {
    public void run(MongoCollection<Document> collection) {
        // Retrieve single insert ID
        InsertOneResult resultOne = collection.insertOne(new Document("name", "Tom"));
        BsonValue insertedId = resultOne.getInsertedId();
        System.out.println("Inserted Single ID: " + insertedId.asObjectId().getValue());

        // Retrieve bulk insert IDs
        List<Document> docs = List.of(new Document("name", "Jerry"), new Document("name", "Spike"));
        InsertManyResult resultMany = collection.insertMany(docs);
        Map<Integer, BsonValue> insertedIds = resultMany.getInsertedIds();
        insertedIds.forEach((index, id) -> {
            System.out.println("Doc at index " + index + " got ID: " + id);
        });
    }
}
```

---

### B. READ OPERATIONS

#### 1. `find`, Find First Document, and Iterate All
Querying database records using cursors.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoCursor;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import java.util.ArrayList;
import java.util.List;

public class FindBasicDemo {
    public void run(MongoCollection<Document> collection) {
        // Find first document matching filter
        Document firstMatch = collection.find(Filters.eq("status", "ACTIVE")).first();

        // Iterate and fetch all matching documents (Try-with-resources avoids cursor leaks)
        List<Document> activeUsers = new ArrayList<>();
        try (MongoCursor<Document> cursor = collection.find(Filters.eq("status", "ACTIVE")).iterator()) {
            while (cursor.hasNext()) {
                activeUsers.add(cursor.next());
            }
        }

        // Direct ingestion into list using .into()
        List<Document> allUsers = collection.find().into(new ArrayList<>());
    }
}
```

#### 2. Query Filters Builder (`Filters`)
Comprehensive use of comparison, logical, element, and regex operators.

```java
import com.mongodb.client.model.Filters;
import org.bson.conversions.Bson;
import java.util.List;

public class QueryFiltersDemo {
    public void buildFilters() {
        // Comparison Filters
        Bson eq  = Filters.eq("role", "ADMIN");                     // Equal
        Bson ne  = Filters.ne("role", "GUEST");                     // Not Equal
        Bson gt  = Filters.gt("score", 75);                         // Greater Than
        Bson gte = Filters.gte("score", 75);                        // Greater Than or Equal
        Bson lt  = Filters.lt("age", 18);                           // Less Than
        Bson lte = Filters.lte("age", 18);                          // Less Than or Equal
        Bson in  = Filters.in("department", "CS", "EE", "MATH");    // Matches any in list
        Bson nin = Filters.nin("department", "ART", "MUSIC");       // Matches none in list

        // Logical Filters
        Bson andFilter = Filters.and(Filters.eq("status", "ACTIVE"), Filters.gt("age", 21));
        Bson orFilter  = Filters.or(Filters.eq("status", "PENDING"), Filters.lt("balance", 0.0));
        Bson notFilter = Filters.not(Filters.eq("role", "ADMIN"));  // Inverts query logic

        // Element Filters
        Bson existsFilter = Filters.exists("graduationDate", true); // Field existence check
        
        // Regex Filters (Pattern matching)
        Bson regexFilter = Filters.regex("email", "@university\\.edu$", "i"); // Case-insensitive
    }
}
```

#### 3. Querying Nested Fields & Arrays (`Filters.elemMatch`)
MongoDB supports dot notation to traverse subdocuments and query primitive or document arrays.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import java.util.ArrayList;
import java.util.List;

public class ComplexReadDemo {
    public void run(MongoCollection<Document> collection) {
        // 1. Querying Nested Fields (Dot Notation)
        Bson nestedFilter = Filters.eq("profile.address.city", "Chicago");
        List<Document> chicagoans = collection.find(nestedFilter).into(new ArrayList<>());

        // 2. Querying Arrays (Primitive values)
        // Matches if "java" is an element in the tags array
        Bson tagFilter = Filters.eq("tags", "java");
        
        // Exact match: Matches if array is exactly [java, spring] in this order
        Bson exactArrayFilter = Filters.eq("tags", List.of("java", "spring"));

        // Match all elements: Matches if tags contains both "java" and "spring" in any order
        Bson allTagsFilter = Filters.all("tags", List.of("java", "spring"));

        // Array size filter: Matches if array contains exactly 3 items
        Bson sizeFilter = Filters.size("tags", 3);

        // 3. Querying Array of Subdocuments (elemMatch)
        // Matches if at least one subdocument in enrollments has courseCode "MATH" AND score >= 90
        Bson subdocArrayFilter = Filters.elemMatch("enrollments", Filters.and(
            Filters.eq("courseCode", "MATH"),
            Filters.gte("score", 90.0)
        ));
        
        List<Document> mathHonorStudents = collection.find(subdocArrayFilter).into(new ArrayList<>());
    }
}
```

#### 4. Projections, Sorting, Limit, and Skip
To reduce memory consumption, we should restrict which fields are fetched. We can sort and slice results directly.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Projections;
import com.mongodb.client.model.Sorts;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.ArrayList;
import java.util.List;

public class QueryModificationsDemo {
    public void run(MongoCollection<Document> collection) {
        // Projection: include only "name" and "email", exclude "_id"
        Bson projection = Projections.fields(
            Projections.include("name", "email"),
            Projections.excludeId()
        );

        // Sorting: descending order of score, then ascending order of name
        Bson sort = Sorts.compoundSort(
            Sorts.descending("score"),
            Sorts.ascending("name")
        );

        // Limit & Skip
        List<Document> results = collection.find(Filters.eq("status", "ACTIVE"))
                                           .projection(projection)
                                           .sort(sort)
                                           .skip(10)  // Skip first 10 documents
                                           .limit(5)  // Retrieve next 5 documents
                                           .into(new ArrayList<>());
    }
}
```

#### 5. Pagination: Offset vs. Keyset
*   **Offset-based Pagination (Skip & Limit)**: Simple to implement, but suffers from O(N) performance degradation as skip count increases because MongoDB must fetch and discard records.
*   **Keyset / Cursor-based Pagination**: Uses the unique value from the last document of the previous page to search for the next batch. Highly scalable and O(1) if indexed.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Sorts;
import org.bson.Document;
import org.bson.types.ObjectId;
import java.util.ArrayList;
import java.util.List;

public class PaginationStrategies {
    // Offset Pagination (Slow for high page numbers)
    public List<Document> getPageOffset(MongoCollection<Document> collection, int pageNum, int pageSize) {
        return collection.find()
                         .sort(Sorts.descending("createdAt"))
                         .skip(pageNum * pageSize)
                         .limit(pageSize)
                         .into(new ArrayList<>());
    }

    // Keyset Pagination (Fast O(1) pagination)
    public List<Document> getPageKeyset(MongoCollection<Document> collection, ObjectId lastSeenId, int pageSize) {
        // If first page, filter is empty. Otherwise, find documents with ID greater than last seen ID
        var filter = (lastSeenId == null) ? new Document() : Filters.gt("_id", lastSeenId);
        return collection.find(filter)
                         .sort(Sorts.ascending("_id"))
                         .limit(pageSize)
                         .into(new ArrayList<>());
    }
}
```

---

### C. UPDATE OPERATIONS

#### 1. `updateOne`, `updateMany`, and `replaceOne`
Understand the structural differences between modifications and total document replacement.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class UpdateBasicsDemo {
    public void run(MongoCollection<Document> collection) {
        // updateOne: Modifies first document matching the query filter
        collection.updateOne(
            Filters.eq("email", "john@example.com"),
            Updates.set("status", "VERIFIED")
        );

        // updateMany: Modifies all documents matching the query filter
        collection.updateMany(
            Filters.eq("status", "PENDING"),
            Updates.set("status", "EXPIRED")
        );

        // replaceOne: Replaces the entire document structure (retains original _id)
        Document replacement = new Document("name", "Bob Spencer")
                                    .append("status", "ACTIVE")
                                    .append("notes", "Replaced whole record");
        collection.replaceOne(
            Filters.eq("_id", "STUDENT-102"),
            replacement
        );
    }
}
```

| Feature | `updateOne` / `updateMany` | `replaceOne` |
| :--- | :--- | :--- |
| **Destructiveness** | Non-destructive. Modifies only targets. | Destructive. Replaces the entire document. |
| **Concurrency Risk**| Minimal. Different threads can modify different fields. | High. Can overwrite concurrent updates. |
| **Network Payload** | Very low. Only updates sent. | High. Entire document sent. |

#### 2. Update Modifiers Builder (`Updates`)
All standard modification operators in Java:

```java
import com.mongodb.client.model.Updates;
import org.bson.conversions.Bson;
import java.util.Date;
import java.util.List;

public class UpdatesBuilderDemo {
    public void buildUpdates() {
        Bson set = Updates.set("name", "Robert");                     // Sets value
        Bson unset = Updates.unset("deprecatedField");                // Deletes field
        Bson inc = Updates.inc("points", 10);                         // Increments numeric value
        Bson mul = Updates.mul("price", 1.15);                        // Multiplies numeric value
        Bson rename = Updates.rename("nickname", "alias");            // Renames field key name
        Bson currDate = Updates.currentDate("lastModified");          // Sets to current datetime
        
        // Array Modifiers
        Bson push = Updates.push("logins", new Date());               // Appends to array
        Bson addToSet = Updates.addToSet("tags", "java");             // Appends value uniquely
        Bson pull = Updates.pull("tags", "c++");                      // Removes matching value
        Bson popFirst = Updates.popFirst("tags");                     // Removes first element
        Bson popLast = Updates.popLast("tags");                       // Removes last element
    }
}
```

#### 3. Positional Array Updates & `arrayFilters`
Modifying nested arrays dynamically.
*   **Positional Operator (`$`)**: Modifies the **first** array element matching the query filter. The array must be part of the initial filter query.
*   **Filtered Positional Operator (`$[identifier]`)**: Modifies elements matching criteria defined within `arrayFilters` list, bypassing the query filter constraint.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import com.mongodb.client.model.UpdateOptions;
import org.bson.Document;
import java.util.List;

public class ArrayUpdatesDemo {
    public void run(MongoCollection<Document> collection) {
        // 1. Basic Positional Operator ($)
        // Query must target the array element we want to modify.
        var queryFilter = Filters.and(
            Filters.eq("_id", "STD-402"),
            Filters.eq("enrollments.courseCode", "MATH")
        );
        var updateOperation = Updates.set("enrollments.$.status", "COMPLETED");
        collection.updateOne(queryFilter, updateOperation);

        // 2. Filtered Positional Operator ($[identifier]) & arrayFilters
        // Allows updating multiple elements or elements without query filter matching.
        var filter = Filters.eq("_id", "STD-402");
        var update = Updates.set("enrollments.$[elem].score", 100.0);

        // Define which array elements match "elem" identifier
        List<Document> arrayFilters = List.of(
            new Document("elem.courseCode", "MATH").append("elem.score", new Document("$lt", 100.0))
        );
        UpdateOptions options = new UpdateOptions().arrayFilters(arrayFilters);

        collection.updateOne(filter, update, options);
    }
}
```

#### 4. Upsert Configurations
Upsert inserts a new document if no matching document is found.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import com.mongodb.client.model.UpdateOptions;
import com.mongodb.client.result.UpdateResult;
import org.bson.Document;

public class UpsertDemo {
    public void run(MongoCollection<Document> collection) {
        var filter = Filters.eq("sku", "PROD-X-99");
        var update = Updates.combine(
            Updates.set("price", 49.99),
            Updates.inc("stock", 5)
        );

        UpdateOptions options = new UpdateOptions().upsert(true);
        UpdateResult result = collection.updateOne(filter, update, options);

        System.out.println("Matched: " + result.getMatchedCount());
        System.out.println("Modified: " + result.getModifiedCount());
        if (result.getUpsertedId() != null) {
            System.out.println("Inserted brand new document with ID: " + result.getUpsertedId());
        }
    }
}
```

---

### D. DELETE OPERATIONS

#### 1. `deleteOne` & `deleteMany`
Performs deletion of documents matching a query filter.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.result.DeleteResult;
import org.bson.Document;

public class DeleteOperationsDemo {
    public void run(MongoCollection<Document> collection) {
        // deleteOne: Removes the first matching document
        DeleteResult deleteOneResult = collection.deleteOne(Filters.eq("_id", "STD-001"));
        System.out.println("Deleted count: " + deleteOneResult.getDeletedCount());

        // deleteMany: Removes all matching documents
        DeleteResult deleteManyResult = collection.deleteMany(Filters.eq("status", "INACTIVE"));
        System.out.println("Deleted multiple count: " + deleteManyResult.getDeletedCount());
    }
}
```

#### 2. Soft Delete vs. Hard Delete
*   **Hard Delete**: Removes the document from disk directly. Reclaiming disk space can cause fragmentation and performance degradation during disk cleanups.
*   **Soft Delete**: Sets a boolean flag (e.g. `isDeleted = true`) or a timestamp (`deletedAt = now`), preserving the document for audit logging and restoring capabilities.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;
import java.util.Date;

public class SoftDeleteDemo {
    public void softDelete(MongoCollection<Document> collection, String docId) {
        collection.updateOne(
            Filters.eq("_id", docId),
            Updates.combine(
                Updates.set("status", "DELETED"),
                Updates.set("deletedAt", new Date()),
                Updates.set("isDeleted", true)
            )
        );
    }
}
```

#### 3. Safe Delete Patterns
*   **Prevent Unbounded Deletes**: Always validate user input parameters before passing them to a delete query. Do not pass empty filters.
*   **TTL Indexes for Automatic Eviction**: Use MongoDB's Time-To-Live index to automatically delete records after a certain period of time.
*   **Eviction limits**: When doing batch cleanups, run `deleteMany` inside loop buckets limiting count, or clean by date partitions to avoid locking resources.

---

## 10. Hands-on Exercises

### Challenge 1: E-Commerce Product Upsert & Increment
Implement a Product Service. When registering stock arrivals, you must upsert a product document by its `sku`. 
*   If the product exists: update the `price` to the new arrival price and increment the `stock` count by the arrived quantity.
*   If the product does not exist: insert the `sku`, set `price` to the arrival price, and initialize `stock` to the arrived quantity.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import com.mongodb.client.model.UpdateOptions;
import org.bson.Document;

public class InventoryService {

    public void registerArrival(MongoCollection<Document> collection, String sku, double price, int quantity) {
        // TODO: Build your update operation and use Upsert Option.
        var filter = Filters.eq("sku", sku);
        var update = Updates.combine(
            Updates.set("price", price),
            Updates.inc("stock", quantity)
        );
        UpdateOptions options = new UpdateOptions().upsert(true);
        collection.updateOne(filter, update, options);
    }
}
```

### Challenge 2: Student Enrollment Course Grade Update
Implement a grade management service. The method must update a student's course grade in their nested `grades` array. The grade score must be updated *only* if the student's status is `"ACTIVE"` and the current score is less than `50.0`. You must use `arrayFilters`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import com.mongodb.client.model.UpdateOptions;
import org.bson.Document;
import java.util.List;

public class GradeService {

    public void passFailingStudent(MongoCollection<Document> collection, String studentId, String courseCode, double passingScore) {
        // TODO: Perform updateOne with arrayFilters
        // Filter student by ID and active status.
        // Update grade score where courseCode matches and current score is < 50.0
        var filter = Filters.and(
            Filters.eq("_id", studentId),
            Filters.eq("status", "ACTIVE")
        );

        var update = Updates.set("grades.$[g].score", passingScore);

        List<Document> arrayFilters = List.of(
            new Document("g.courseCode", courseCode)
                .append("g.score", new Document("$lt", 50.0))
        );
        UpdateOptions options = new UpdateOptions().arrayFilters(arrayFilters);

        collection.updateOne(filter, update, options);
    }
}
```

### Challenge 3: Keyset Pagination Search
Implement a paginated customer search. Return a list of customer documents sorted by `_id` in ascending order. You must accept a page size and a last seen string `_id` parameter to execute high-performance cursor pagination.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Sorts;
import org.bson.Document;
import org.bson.types.ObjectId;
import java.util.ArrayList;
import java.util.List;

public class CustomerSearchService {

    public List<Document> fetchPage(MongoCollection<Document> collection, String lastSeenId, int pageSize) {
        // TODO: Build Keysets Pagination Query
        var filter = (lastSeenId == null) ? new Document() : Filters.gt("_id", new ObjectId(lastSeenId));
        return collection.find(filter)
                         .sort(Sorts.ascending("_id"))
                         .limit(pageSize)
                         .into(new ArrayList<>());
    }
}
```

### Verification Tests
Verify all three challenge solutions using this Junit 5 mock-based test suite:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.FindIterable;
import com.mongodb.client.model.UpdateOptions;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class CRUDExercisesTest {

    @SuppressWarnings("unchecked")
    @Test
    void testRegisterArrival() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        InventoryService service = new InventoryService();

        service.registerArrival(mockCol, "PROD-12", 29.99, 10);

        verify(mockCol, times(1)).updateOne(any(), any(), any(UpdateOptions.class));
    }

    @SuppressWarnings("unchecked")
    @Test
    void testPassFailingStudent() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        GradeService service = new GradeService();

        service.passFailingStudent(mockCol, "STD-01", "MATH", 50.0);

        verify(mockCol, times(1)).updateOne(any(), any(), any(UpdateOptions.class));
    }

    @SuppressWarnings("unchecked")
    @Test
    void testFetchPage() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        FindIterable<Document> mockFind = mock(FindIterable.class);
        
        when(mockCol.find(any(Document.class))).thenReturn(mockFind);
        when(mockFind.sort(any())).thenReturn(mockFind);
        when(mockFind.limit(anyInt())).thenReturn(mockFind);
        when(mockFind.into(any())).thenReturn(List.of(new Document("name", "Alice")));

        CustomerSearchService service = new CustomerSearchService();
        List<Document> result = service.fetchPage(mockCol, null, 10);

        assertNotNull(result);
        assertEquals(1, result.size());
    }
}
```
