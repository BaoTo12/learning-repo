# Module 11: Bulk Operations

Welcome, student. Today we study every aspect of **Bulk Operations (CS-529)** using the official MongoDB Java Sync Driver.

---

## 1. What problem does this solve?
When applications import large datasets, sync catalogs, or process background updates, executing database operations individually is highly inefficient. 

For example, sending 10,000 separate `updateOne` updates over a network socket forces 10,000 network round-trips. The application spends most of its time waiting for TCP acknowledgments and thread context switches, resulting in poor write throughput.

We solve this using **Bulk Operations (`bulkWrite`)**. The driver packages multiple write operations (inserts, updates, replacements, deletes) into a single BSON command packet and sends it in a single network transmission to the database server.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides bulk write models and execution options to:
*   **Minimize Network Overhead**: Pack multiple mutations into a single network transmission, saving network latency.
*   **Support Mixed Operations**: Execute different types of mutations (e.g. inserting new users, updating active scores, and deleting inactive users) within a single execution block.
*   **Provide Flexible Failure Policies**: Support ordered execution (fail-fast, rollback-like stops) or unordered execution (parallel, continue-on-error).

---

## 3. How does it work internally or conceptually?
*   **BSON Packets Serialization**: The Java driver buffers the list of operations. MongoDB restricts BSON command packets to a maximum size of **48MB** or **100,000 operations** per request. If your bulk request exceeds these limits, the driver automatically splits it into multiple smaller physical batches.
*   **Ordered Bulk Writes (Default)**: MongoDB executes the list of operations sequentially in the order they were added. If an error occurs (e.g. unique key duplicate), execution halts immediately. The database does **not** roll back previously completed operations, but all remaining operations are ignored.
*   **Unordered Bulk Writes**: MongoDB groups operations by write type and parallelizes execution across replica set threads. If one operation fails, the database continues processing the rest. All errors are compiled and returned in the final response.
*   **`insertMany` vs. `bulkWrite`**:
    *   `insertMany`: Highly optimized for a single write type (insertions only).
    *   `bulkWrite`: Supports mixed write models (insert, update, replace, delete).

---

## 4. How do we use it in Java?
We construct lists of `WriteModel<Document>` objects using concrete model classes like `InsertOneModel`, `UpdateOneModel`, `ReplaceOneModel`, and `DeleteOneModel`, then pass the list to the collection's `bulkWrite()` method.

### 4.1 Visual Dataset & Unordered Bulk Write Trace

#### Initial Database State (`users` Collection):
```json
[
  { "_id": "2", "points": 10 },
  { "_id": "3", "status": "EXPIRED" }
]
```

#### Step-by-Step Execution Path (ordered = false):

1. **Client Packages Write Operations**:
   * Request holds 3 mixed instructions:
     1. `InsertOneModel` for `_id: "1"`.
     2. `UpdateOneModel` for `_id: "2"` incrementing points.
     3. `DeleteOneModel` for `_id: "3"`.
2. **Driver Packages and Sends Request**:
   * The driver groups the operations into a single command packet and transmits it over the network to the server node.
3. **Parallel Server Execution**:
   * With `ordered(false)` (unordered execution), MongoDB executes operations in parallel across server threads.
   * *Write Thread A*: Inserts document `_id: "1"`.
   * *Write Thread B*: Finds `_id: "2"` and increments points by `5`.
   * *Write Thread C*: Finds `_id: "3"` and deletes it.
   * If any operation fails (e.g. `_id: "1"` unique constraint), threads B and C continue execution uninterrupted.
4. **Final DB State**:
   ```json
   [
     { "_id": "1", "status": "ACTIVE" },
     { "_id": "2", "points": 15 }
   ]
   ```

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.*;
import org.bson.Document;
import java.util.List;

public class BasicBulkDemo {
    public void executeBulk(MongoCollection<Document> collection) {
        // Compile a list of mixed write models
        List<WriteModel<Document>> operations = List.of(
            new InsertOneModel<>(new Document("_id", "1").append("status", "ACTIVE")),
            new UpdateOneModel<>(Filters.eq("_id", "2"), Updates.inc("points", 5)),
            new DeleteOneModel<>(Filters.eq("_id", "3"))
        );

        // Execute bulk write on the collection.
        // BulkWriteOptions().ordered(false) disables ordered execution to allow parallel runs
        // and bypass fail-fast abort logic if any single item fails.
        collection.bulkWrite(operations, new BulkWriteOptions().ordered(false));
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`List<WriteModel<Document>>`**: List array storing mixed write models. All operations must share the collection's generic document class type bounds.
- **`BulkWriteOptions().ordered(false)`**: Configures execution order. Set this parameter to `false` (unordered) to maximize server execution parallelization.

---

## 5. What are the trade-offs?
*   **Pros**:
    *   **Maximum Write Throughput**: Drastically reduces execution time.
    *   **Batch Isolation**: Unordered writes maximize database server thread utilization.
    *   **Detailed Diagnostic Metrics**: Returns exact error counts and successful write indicators.
*   **Cons**:
    *   **No Rollback Guarantee**: Unlike transactions, a failed bulk write does not roll back successfully completed operations.
    *   **Server Lock Contention**: Writing thousands of documents inside a single request can block other threads from reading or writing.
    *   **RAM/Socket Exhaustion**: Large batches can lead to network buffers allocation timeouts.

---

## 6. Common Mistakes
*   **Using Ordered Writes for Independent Operations**: Defaulting to ordered execution when operations do not depend on each other, which prevents parallelization.
*   **Sending Single Massive Batches**: Passing a list of 500,000 documents to `bulkWrite` at once, which increases client memory footprint and forces the driver to execute multiple internal splits. **Always slice massive loads into smaller manual batches (e.g., 1,000 documents).**
*   **Mixed Model Type Bloat**: Mixing too many different types of operations inside an ordered bulk write. MongoDB must split the payload into separate command batches for each type change (e.g. switching from insert to delete), increasing network roundtrips.

---

## 7. When should we use it?
*   Use for background ETL sync tasks, nightly product catalog updates, batch imports, and data migrations.
*   Use unordered bulk writes whenever processing independent events.

---

## 8. When should we avoid it?
*   Do not use bulk writes when you need complete transactional consistency (e.g. money transfers). If one step fails, you cannot easily roll back the completed steps. Use Multi-Document Transactions instead.

---

## 9. Code Examples

### A. CONCRETE WRITE MODELS

Here is a Java class configuring and compiling a list of mixed write models.

#### Explaining the Write Model Selection API:
*   **`InsertOneModel`**: Takes a document to insert.
*   **`UpdateOneModel`**: Updates the first matching document based on a query filter. Accepts `UpdateOptions` (e.g. `upsert`).
*   **`UpdateManyModel`**: Updates all matching documents matching the filter conditions.
*   **`ReplaceOneModel`**: Replaces the entire content of the first matching document. The replacement document cannot contain update operators like `$set`.
*   **`DeleteOneModel`**: Removes the first matching document.
*   **`DeleteManyModel`**: Removes all matching documents.

##### Mixed models execution dataset trace:
*   **Starting State**:
    ```json
    [
      { "_id": "ITEM-1", "category": "A", "price": 10.0 }
    ]
    ```
*   **Execution Models sequence**:
    1. `InsertOneModel({ "_id": "ITEM-2", "category": "A", "price": 15.0 })`
    2. `UpdateOneModel(eq("_id", "ITEM-1"), inc("price", 2.0))`
    3. `ReplaceOneModel(eq("_id", "ITEM-2"), { "_id": "ITEM-2", "category": "B", "price": 20.0 })`
*   **Final Output Dataset state**:
    ```json
    [
      { "_id": "ITEM-1", "category": "A", "price": 12.0 },
      { "_id": "ITEM-2", "category": "B", "price": 20.0 }
    ]
    ```

```java
import com.mongodb.client.model.*;
import org.bson.Document;
import org.bson.conversions.Bson;

public class WriteModelsBuilder {
    // 1. Insert Model
    public WriteModel<Document> getInsert(Document doc) {
        return new InsertOneModel<>(doc);
    }

    // 2. Single Update Model
    public WriteModel<Document> getUpdateOne(Bson filter, Bson update) {
        return new UpdateOneModel<>(filter, update);
    }

    // 3. Multi Update Model
    public WriteModel<Document> getUpdateMany(Bson filter, Bson update) {
        return new UpdateManyModel<>(filter, update);
    }

    // 4. Single Document Replacement Model (Requires raw replacement document, no operators)
    public WriteModel<Document> getReplace(Bson filter, Document replacement) {
        return new ReplaceOneModel<>(filter, replacement);
    }

    // 5. Single Document Deletion Model
    public WriteModel<Document> getDeleteOne(Bson filter) {
        return new DeleteOneModel<>(filter);
    }

    // 6. Multi Document Deletion Model
    public WriteModel<Document> getDeleteMany(Bson filter) {
        return new DeleteManyModel<>(filter);
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`ReplaceOneModel`**: Differs from `UpdateOneModel` because it completely replaces the matching document with the provided replacement document. It is useful when syncing complete entity states.
- **`UpdateManyModel` / `DeleteManyModel`**: Affect all records that match the query filter in the batch, unlike the `One` variations which only target the first matched record.

---

### B. PARSING BULK WRITES RESULTS & EXCEPTIONS

#### Explaining the Results Parsing API:
*   **`BulkWriteResult`**: Class containing counts of matched, modified, inserted, and deleted records:
    *   `getInsertedCount()`: Count of successful inserts.
    *   `getMatchedCount()`: Count of updates/replacements matching filters.
    *   `getModifiedCount()`: Count of documents updated or replaced.
    *   `getDeletedCount()`: Count of successfully deleted documents.
    *   `getUpserts()`: Returns a list of `BulkWriteUpsert` objects mapping upsert records.

##### Mixed Bulk Result Execution Trace:

###### Input List:
1. `UpdateOneModel(eq("sku", "S1"), inc("stock", 2))` -> Matches, increases stock.
2. `InsertOneModel({ "sku", "S2" })` -> Successful insert.
3. `UpdateOneModel(eq("sku", "S3"), inc("stock", 1))` (Upsert = true) -> No match, creates S3.

###### Output Metric Parse:
*   `result.getInsertedCount()` = 1
*   `result.getMatchedCount()` = 1
*   `result.getModifiedCount()` = 1
*   `result.getUpserts().size()` = 1

```java
import com.mongodb.MongoBulkWriteException;
import com.mongodb.bulk.BulkWriteResult;
import com.mongodb.bulk.BulkWriteError;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.WriteModel;
import org.bson.Document;
import java.util.List;

public class BulkResultParser {
    public void executeBulkOperations(MongoCollection<Document> collection, List<WriteModel<Document>> operations) {
        try {
            // Execute the bulk operations
            BulkWriteResult result = collection.bulkWrite(operations);
            
            System.out.println("Bulk write completed successfully.");
            System.out.println("Inserted: " + result.getInsertedCount());
            System.out.println("Matched: " + result.getMatchedCount());
            System.out.println("Modified: " + result.getModifiedCount());
            System.out.println("Deleted: " + result.getDeletedCount());
            System.out.println("Upserted Count: " + result.getUpserts().size());
        } catch (MongoBulkWriteException e) {
            // Parse partial failure details from exception payload
            System.err.println("Bulk write encountered errors.");
            
            // e.getWriteResult() retrieves successfully applied updates metrics
            BulkWriteResult result = e.getWriteResult();
            System.err.println("Inserted: " + result.getInsertedCount());
            System.err.println("Modified: " + result.getModifiedCount());

            // Process each individual failure mapped to the failing write models list indexes
            List<BulkWriteError> errors = e.getWriteErrors();
            for (BulkWriteError error : errors) {
                System.err.println("Failure at operation index: " + error.getIndex()
                    + " | Error Code: " + error.getCode()
                    + " | Message: " + error.getMessage());
            }
        }
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`result.getUpserts()`**: Returns a list of `BulkWriteUpsert` items, which hold the generated object IDs (`_id`) for any upserts.
- **`e.getWriteResult()`**: Used to verify which portion of the bulk write succeeded before the exception was thrown.

---

## 10. Hands-on Exercises

### Challenge 1: Mixed Inventory Sync
Implement a warehouse sync service. Given a list of active arrivals and deleted items, construct a mixed `List<WriteModel<Document>>` and execute it as an **unordered** bulk write.
*   For each active arrival: construct an `UpdateOneModel` using `Filters.eq("sku", sku)` to increment `stock` by quantity and set `status = "ACTIVE"`, with `upsert(true)`.
*   For each deleted SKU: construct a `DeleteOneModel` using `Filters.eq("sku", sku)`.

##### Dataset and execution Trace:

###### Input datasets:
*   `inventory` Collection initial state:
    ```json
    [
      { "sku": "S1", "stock": 10, "status": "ACTIVE" },
      { "sku": "S3", "stock": 5, "status": "ACTIVE" }
    ]
    ```
*   `arrivals` List:
    ```json
    [
      { "sku": "S1", "quantity": 5 },
      { "sku": "S2", "quantity": 20 }
    ]
    ```
*   `deletedSkus` List:
    ```json
    ["S3"]
    ```

###### Trace:
1. ** arrivals loop**:
   * Creates `UpdateOneModel` on S1: filter `sku = "S1"`, updates: increment stock by 5 and status to "ACTIVE".
   * Creates `UpdateOneModel` on S2: filter `sku = "S2"`, updates: increment stock by 20 and status to "ACTIVE" with `upsert(true)`.
2. **deletedSkus loop**:
   * Creates `DeleteOneModel` on S3: filter `sku = "S3"`.
3. **Execute bulkWrite (unordered)**:
   * Thread executes updates on S1 and S2, and deletion of S3 in parallel.
   * S1 stock is updated to 15.
   * S2 is created with stock 20 and status "ACTIVE" (since it did not exist and `upsert` was set to `true`).
   * S3 is removed.
4. **Final DB State**:
   ```json
   [
     { "sku": "S1", "stock": 15, "status": "ACTIVE" },
     { "sku": "S2", "stock": 20, "status": "ACTIVE" }
   ]
   ```

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.*;
import org.bson.Document;
import java.util.ArrayList;
import java.util.List;

public class WarehouseSyncService {

    public void syncWarehouse(MongoCollection<Document> collection, List<Document> arrivals, List<String> deletedSkus) {
        List<WriteModel<Document>> operations = new ArrayList<>();

        // Loop arrivals list and build UpdateOneModel for each item
        for (Document arrival : arrivals) {
            String sku = arrival.getString("sku");
            int qty = arrival.getInteger("quantity", 0);
            operations.add(new UpdateOneModel<>(
                Filters.eq("sku", sku),
                Updates.combine(
                    Updates.inc("stock", qty),
                    Updates.set("status", "ACTIVE")
                ),
                // Configure upsert true to create document if SKU does not exist
                new UpdateOptions().upsert(true)
            ));
        }

        // Loop deleted SKUs list and build DeleteOneModel for each item
        for (String sku : deletedSkus) {
            operations.add(new DeleteOneModel<>(Filters.eq("sku", sku)));
        }

        // Execute bulkWrite using unordered settings if operations list is not empty
        if (!operations.isEmpty()) {
            collection.bulkWrite(operations, new BulkWriteOptions().ordered(false));
        }
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`Updates.combine`**: Merges `$inc` and `$set` operators so that both values are applied together to the matching document in a single update operation.
- **`new UpdateOptions().upsert(true)`**: Passed to the `UpdateOneModel` constructor, enabling dynamic document creation when the SKU filter finds no database records.

---

### Challenge 2: Partitioned Bulk Loader
When importing very large datasets (e.g. 50,000 records), you must partition the data to avoid memory spikes. Implement a service that splits a list of documents into batches of size `1,000`, wraps them inside `InsertOneModel` wrappers, and executes a `bulkWrite` for each batch.

##### Dataset and Execution Partitioning Trace:
*   Dataset size = 2500 documents. Batch size = 1000.
*   **Iteration 1**:
    *   Loops first 1000 documents, wraps in `InsertOneModel`.
    *   Calls `bulkWrite(batch)` -> 1000 documents written. Clears batch list.
*   **Iteration 2**:
    *   Loops next 1000 documents.
    *   Calls `bulkWrite(batch)` -> 1000 documents written. Clears batch list.
*   **Final Batch Cleanup**:
    *   Loops remaining 500 documents.
    *   Out of loop, calls `bulkWrite(batch)` on the remaining 500 documents.
*   **Result**: 2500 documents written using 3 requests instead of 2500 individual insertions, minimizing network overhead.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.InsertOneModel;
import com.mongodb.client.model.WriteModel;
import org.bson.Document;
import java.util.ArrayList;
import java.util.List;

public class BulkDatasetLoader {

    public int loadDataset(MongoCollection<Document> collection, List<Document> dataset, int batchSize) {
        int totalInserted = 0;
        List<WriteModel<Document>> batch = new ArrayList<>();

        for (Document doc : dataset) {
            // Wrap document in InsertOneModel and add to batch
            batch.add(new InsertOneModel<>(doc));
            
            // If batch size matches requested batchSize threshold, execute write and clear list
            if (batch.size() == batchSize) {
                var result = collection.bulkWrite(batch);
                totalInserted += result.getInsertedCount();
                batch.clear();
            }
        }

        // Write any remaining trailing documents not captured inside loop threshold check
        if (!batch.isEmpty()) {
            var result = collection.bulkWrite(batch);
            totalInserted += result.getInsertedCount();
        }

        return totalInserted;
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`batch.clear()`**: Essential step to release references to already committed write models and reuse the array list memory pool, avoiding JVM Heap allocation inflation.
- **`result.getInsertedCount()`**: Accumulates successful inserts counts returned from the driver.

---

### Verification Tests

Below is the JUnit 5 verification test suite. It uses Mockito to mock MongoDB collections, stub results, and verify that the bulk operations execute with the expected sizes and configurations.

#### Detailed Testing & Verification Explanation:
*   **`verify(mockCol, times(1)).bulkWrite(anyList(), any(BulkWriteOptions.class))`**: Checks that `syncWarehouse` executed a single unordered bulk request.
*   **`verify(mockCol, times(1)).bulkWrite(anyList())`**: Asserts that `loadDataset` executed exactly one bulk request when batch sizes equaled dataset sizes.

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.BulkWriteOptions;
import com.mongodb.bulk.BulkWriteResult;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class BulkOperationsTest {

    @SuppressWarnings("unchecked")
    @Test
    void testSyncWarehouse() {
        // 1. Arrange mock objects
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        WarehouseSyncService service = new WarehouseSyncService();

        List<Document> arrivals = List.of(new Document("sku", "PROD-1").append("quantity", 5));
        List<String> deletes = List.of("PROD-OLD");

        // 2. Act
        service.syncWarehouse(mockCol, arrivals, deletes);

        // 3. Assert and Verify
        verify(mockCol, times(1)).bulkWrite(anyList(), any(BulkWriteOptions.class)); // Asserts write was bundled
    }

    @SuppressWarnings("unchecked")
    @Test
    void testPartitionedBulkLoader() {
        // 1. Arrange mock objects
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        BulkWriteResult mockResult = mock(BulkWriteResult.class);
        
        // 2. Configure mock actions
        when(mockCol.bulkWrite(anyList())).thenReturn(mockResult);
        when(mockResult.getInsertedCount()).thenReturn(2);

        // 3. Act
        BulkDatasetLoader loader = new BulkDatasetLoader();
        List<Document> dataset = List.of(new Document("id", 1), new Document("id", 2));
        int result = loader.loadDataset(mockCol, dataset, 2);

        // 4. Assert and Verify
        assertEquals(2, result); // Asserts successful insertions match count
        verify(mockCol, times(1)).bulkWrite(anyList()); // Asserts it executed as a single batch
    }
}
```
