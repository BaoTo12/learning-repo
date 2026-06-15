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

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.*;
import org.bson.Document;
import java.util.List;

public class BasicBulkDemo {
    public void executeBulk(MongoCollection<Document> collection) {
        List<WriteModel<Document>> operations = List.of(
            new InsertOneModel<>(new Document("_id", "1").append("status", "ACTIVE")),
            new UpdateOneModel<>(Filters.eq("_id", "2"), Updates.inc("points", 5)),
            new DeleteOneModel<>(Filters.eq("_id", "3"))
        );

        collection.bulkWrite(operations, new BulkWriteOptions().ordered(false));
    }
}
```

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

```java
import com.mongodb.client.model.*;
import org.bson.Document;
import org.bson.conversions.Bson;

public class WriteModelsBuilder {
    public WriteModel<Document> getInsert(Document doc) {
        return new InsertOneModel<>(doc);
    }

    public WriteModel<Document> getUpdateOne(Bson filter, Bson update) {
        return new UpdateOneModel<>(filter, update);
    }

    public WriteModel<Document> getUpdateMany(Bson filter, Bson update) {
        return new UpdateManyModel<>(filter, update);
    }

    public WriteModel<Document> getReplace(Bson filter, Document replacement) {
        return new ReplaceOneModel<>(filter, replacement);
    }

    public WriteModel<Document> getDeleteOne(Bson filter) {
        return new DeleteOneModel<>(filter);
    }

    public WriteModel<Document> getDeleteMany(Bson filter) {
        return new DeleteManyModel<>(filter);
    }
}
```

---

### B. PARSING BULK WRITES RESULTS & EXCEPTIONS

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
            BulkWriteResult result = collection.bulkWrite(operations);
            
            System.out.println("Bulk write completed successfully.");
            System.out.println("Inserted: " + result.getInsertedCount());
            System.out.println("Matched: " + result.getMatchedCount());
            System.out.println("Modified: " + result.getModifiedCount());
            System.out.println("Deleted: " + result.getDeletedCount());
            System.out.println("Upserted Count: " + result.getUpserts().size());
        } catch (MongoBulkWriteException e) {
            System.err.println("Bulk write encountered errors.");
            
            // Print successful write statistics
            BulkWriteResult result = e.getWriteResult();
            System.err.println("Inserted: " + result.getInsertedCount());
            System.err.println("Modified: " + result.getModifiedCount());

            // Process each individual failure
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

---

## 10. Hands-on Exercises

### Challenge 1: Mixed Inventory Sync
Implement a warehouse sync service. Given a list of active arrivals and deleted items, construct a mixed `List<WriteModel<Document>>` and execute it as an **unordered** bulk write.
*   For each active arrival: construct an `UpdateOneModel` using `Filters.eq("sku", sku)` to increment `stock` by quantity and set `status = "ACTIVE"`, with `upsert(true)`.
*   For each deleted SKU: construct a `DeleteOneModel` using `Filters.eq("sku", sku)`.

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
        // TODO: Build operations list, call bulkWrite with ordered(false) options.
        List<WriteModel<Document>> operations = new ArrayList<>();

        for (Document arrival : arrivals) {
            String sku = arrival.getString("sku");
            int qty = arrival.getInteger("quantity", 0);
            operations.add(new UpdateOneModel<>(
                Filters.eq("sku", sku),
                Updates.combine(
                    Updates.inc("stock", qty),
                    Updates.set("status", "ACTIVE")
                ),
                new UpdateOptions().upsert(true)
            ));
        }

        for (String sku : deletedSkus) {
            operations.add(new DeleteOneModel<>(Filters.eq("sku", sku)));
        }

        if (!operations.isEmpty()) {
            collection.bulkWrite(operations, new BulkWriteOptions().ordered(false));
        }
    }
}
```

### Challenge 2: Partitioned Bulk Loader
When importing very large datasets (e.g. 50,000 records), you must partition the data to avoid memory spikes. Implement a service that splits a list of documents into batches of size `1,000`, wraps them inside `InsertOneModel` wrappers, and executes a `bulkWrite` for each batch.

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
        // TODO: Partition dataset list into chunks of batchSize. Execute bulkWrite for each partition.
        // Return total inserted documents count.
        int totalInserted = 0;
        List<WriteModel<Document>> batch = new ArrayList<>();

        for (Document doc : dataset) {
            batch.add(new InsertOneModel<>(doc));
            if (batch.size() == batchSize) {
                var result = collection.bulkWrite(batch);
                totalInserted += result.getInsertedCount();
                batch.clear();
            }
        }

        if (!batch.isEmpty()) {
            var result = collection.bulkWrite(batch);
            totalInserted += result.getInsertedCount();
        }

        return totalInserted;
    }
}
```

### Verification Tests
Verify both challenges using this JUnit 5 verification test suite:

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
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        WarehouseSyncService service = new WarehouseSyncService();

        List<Document> arrivals = List.of(new Document("sku", "PROD-1").append("quantity", 5));
        List<String> deletes = List.of("PROD-OLD");

        service.syncWarehouse(mockCol, arrivals, deletes);

        verify(mockCol, times(1)).bulkWrite(anyList(), any(BulkWriteOptions.class));
    }

    @SuppressWarnings("unchecked")
    @Test
    void testPartitionedBulkLoader() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        BulkWriteResult mockResult = mock(BulkWriteResult.class);
        
        when(mockCol.bulkWrite(anyList())).thenReturn(mockResult);
        when(mockResult.getInsertedCount()).thenReturn(2);

        BulkDatasetLoader loader = new BulkDatasetLoader();
        List<Document> dataset = List.of(new Document("id", 1), new Document("id", 2));
        
        int result = loader.loadDataset(mockCol, dataset, 2);

        assertEquals(2, result);
        verify(mockCol, times(1)).bulkWrite(anyList());
    }
}
```
