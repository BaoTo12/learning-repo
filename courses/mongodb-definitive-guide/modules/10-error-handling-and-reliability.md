# Module 10: Error Handling and Reliability

Welcome, student. Today we study every aspect of **Error Handling and Reliability (CS-529)** using the official MongoDB Java Sync Driver.

---

## 1. What problem does this solve?
In production environments, database queries can fail due to a wide variety of issues. These include transient network drops, replica set leader elections, duplicate primary keys, schema validation failures, and database lock timeouts.

If an application does not handle these failures gracefully, JVM threads will crash, operations will be left half-completed, and clients will receive unhandled error responses.

We write robust error handling blocks, design idempotent database operations, and implement safe retry mechanisms to guarantee that our application remains resilient during database hiccups.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides a detailed exception hierarchy and driver settings to:
*   **Isolate Root Causes**: Help applications distinguish between transient connection errors (which can be retried) and permanent constraint violations (which should never be retried).
*   **Enable Automated Failovers**: Support automatic retry of reads and writes via driver configuration during replica set elections.
*   **Ensure Write Safeties**: Report exactly which document failed in a bulk write, allowing applications to recover and process successful operations.

---

## 3. How does it work internally or conceptually?
*   **Exception Hierarchy**: The root class is `com.mongodb.MongoException`. It has two main branches:
    *   `com.mongodb.MongoClientException`: Client-side exceptions (e.g. invalid configurations).
    *   `com.mongodb.MongoServerException`: Server-side exceptions (e.g. unique constraint violations, execution timeouts).
*   **Heartbeats & Elections**: In a replica set, nodes exchange heartbeats every 2 seconds. If the primary node fails, an election is triggered, taking up to 10 seconds. During this window, the driver cannot write. 
*   **Retryable Writes**: When `retryWrites=true` is enabled, the driver intercepts transient network exceptions during a write. If the write fails, the driver checks replica set heartbeats, locates the newly elected primary node, and retries the write operation once.
*   **Idempotency (Crucial Concept)**: An operation is **idempotent** if running it multiple times yields the exact same database state as running it once.
    *   *Idempotent Update*: `Updates.set("status", "PAID")` or `Updates.inc("views", 1)` (if wrapped with a unique transaction key check).
    *   *Non-idempotent Update*: `Updates.push("history", "Login Event")`. If a network glitch causes the driver to retry this write, the string may be pushed twice.
*   **Bulk Write Error Maps**: During a `bulkWrite`, MongoDB executes operations in order or out of order. If any operations fail, it throws a `MongoBulkWriteException` containing a list of `BulkWriteError` objects, each referencing the index of the failing request.

---

## 4. How do we use it in Java?
We wrap driver calls in try-catch blocks targeting specific exceptions, and parse BSON error codes to decide whether to retry, log, or abort.

```java
import com.mongodb.MongoWriteException;
import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class SaveHandler {
    public boolean insertSafe(MongoCollection<Document> collection, Document doc) {
        try {
            collection.insertOne(doc);
            return true;
        } catch (MongoWriteException e) {
            // Code 11000 is Duplicate Key, Code 121 is Validation Failure
            int code = e.getError().getCode();
            System.err.println("Write failed on server. Error Code: " + code);
            return false;
        }
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**:
    *   **Graceful Recovery**: Resolves transient network glitches automatically.
    *   **Data Consistency**: Bulk write error maps prevent silent write losses.
    *   **System Stability**: Try-catch blocks prevent unhandled thread crashes.
*   **Cons**:
    *   **Thundering Herd Risk**: Unconstrained retry loops can overload a struggling database server, worsening outages.
    *   **Code Complexity**: Implementing exponential backoff and idempotency checks requires additional application logic.
    *   **Memory Cost**: Large bulk write error maps consume heap space.

---

## 6. Common Mistakes
*   **Retrying Non-Idempotent Operations**: Automatically retrying operations that push elements to arrays (`$push`) or increment values (`$inc`) without checking if the write succeeded on the first attempt.
*   **Catching broad Exceptions**: Catching `java.lang.Exception` everywhere instead of targeting specific MongoDB errors, which hides application bugs.
*   **Retrying Permanent Failures**: Retrying writes that failed due to duplicate key errors (code 11000) or validation failures (code 121). These will always fail.

---

## 7. When should we use it?
*   Use try-catch blocks for duplicate key violations on all unique indexes (e.g. emails, usernames).
*   Implement custom retry loops with exponential backoff and jitter when executing critical business writes.
*   Ensure all retried writes are designed to be idempotent.

---

## 8. When should we avoid it?
*   Do not implement custom retry loops for read queries. The driver already handles read retries natively via `retryReads=true`.
*   Do not retry low-priority logs or metrics writes. If they fail, log a warning and discard them to save resources.

---

## 9. Code Examples

### A. THE EXCEPTION HIERARCHY

Here is a Java service mapping MongoDB server exceptions to business-level responses:

```java
package com.mongodb.systems;

import com.mongodb.MongoException;
import com.mongodb.MongoSocketReadTimeoutException;
import com.mongodb.MongoSocketOpenException;
import com.mongodb.MongoTimeoutException;
import com.mongodb.MongoWriteException;
import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class ExceptionDiagnosticsService {
    
    public enum ErrorStatus {
        SUCCESS, DUPLICATE_KEY, VALIDATION_FAILURE, TIMEOUT, NETWORK_FAILURE, UNKNOWN_ERROR
    }

    public ErrorStatus writeRecord(MongoCollection<Document> collection, Document doc) {
        try {
            collection.insertOne(doc);
            return ErrorStatus.SUCCESS;
        } catch (MongoWriteException e) {
            int code = e.getError().getCode();
            if (code == 11000) {
                return ErrorStatus.DUPLICATE_KEY;
            } else if (code == 121) {
                return ErrorStatus.VALIDATION_FAILURE;
            }
            return ErrorStatus.UNKNOWN_ERROR;
        } catch (MongoSocketReadTimeoutException | MongoTimeoutException e) {
            return ErrorStatus.TIMEOUT;
        } catch (MongoSocketOpenException e) {
            return ErrorStatus.NETWORK_FAILURE;
        } catch (MongoException e) {
            System.err.println("Generic database failure: " + e.getMessage());
            return ErrorStatus.UNKNOWN_ERROR;
        }
    }
}
```

---

### B. IDEMPOTENCY IN WRITES

#### Non-Idempotent Pattern (Danger)
If the connection drops after the server executes the write but before the client receives confirmation, the client retries the push, resulting in duplicate logs.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class UnsafeArrayPush {
    public void addLog(MongoCollection<Document> collection, String userId, String log) {
        // Danger: If retried, this adds the log element twice
        collection.updateOne(Filters.eq("_id", userId), Updates.push("loginHistory", log));
    }
}
```

#### Idempotent Pattern (Safe)
Use `$addToSet` (which only appends unique values) or check a unique transaction token before pushing.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class SafeIdempotentWrite {
    public void addLogSafe(MongoCollection<Document> collection, String userId, String log) {
        // Safe: $addToSet guarantees uniqueness in the array
        collection.updateOne(Filters.eq("_id", userId), Updates.addToSet("loginHistory", log));
    }

    public boolean addPurchaseWithToken(MongoCollection<Document> collection, String userId, Document purchase, String transactionToken) {
        // Safe: Match document only if the transactionToken has not already been processed
        var filter = Filters.and(
            Filters.eq("_id", userId),
            Filters.ne("processedTokens", transactionToken)
        );

        var update = Updates.combine(
            Updates.push("purchases", purchase),
            Updates.push("processedTokens", transactionToken)
        );

        var result = collection.updateOne(filter, update);
        return result.getModifiedCount() > 0;
    }
}
```

---

### C. HANDLING BULK WRITE ERRORS

When executing bulk writes, we must parse the `MongoBulkWriteException` to identify exactly which documents failed and which succeeded.

```java
import com.mongodb.MongoBulkWriteException;
import com.mongodb.bulk.BulkWriteError;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.WriteModel;
import org.bson.Document;
import java.util.List;

public class BulkErrorHandler {
    public void executeBulk(MongoCollection<Document> collection, List<WriteModel<Document>> operations) {
        try {
            collection.bulkWrite(operations);
            System.out.println("Bulk write completed successfully.");
        } catch (MongoBulkWriteException e) {
            System.err.println("Bulk write encountered failures.");
            System.err.println("Successful writes count: " + e.getWriteResult().getInsertedCount());
            
            // Iterate over errors to pinpoint issues
            for (BulkWriteError error : e.getWriteErrors()) {
                System.err.println("Error at operation index " + error.getIndex() 
                    + " | Code: " + error.getCode() 
                    + " | Message: " + error.getMessage());
            }
        }
    }
}
```

---

## 10. Hands-on Exercises

### Challenge 1: Idempotent Payment Processor
Implement a payment processing service method. To prevent double-charging users, you must make the write operation idempotent using a `paymentToken` string.
*   Query the user account.
*   Only deduct the `amount` from the `balance` if the `paymentToken` is not present in the user's `processedPayments` array.
*   If the update succeeds, append the `paymentToken` to the `processedPayments` array.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import com.mongodb.client.result.UpdateResult;
import org.bson.Document;

public class IdempotentPaymentService {

    public boolean processPayment(MongoCollection<Document> collection, String accountId, double amount, String paymentToken) {
        // TODO: Build idempotent update filter and updates
        var filter = Filters.and(
            Filters.eq("_id", accountId),
            Filters.ne("processedPayments", paymentToken)
        );

        var update = Updates.combine(
            Updates.inc("balance", -amount),
            Updates.push("processedPayments", paymentToken)
        );

        UpdateResult result = collection.updateOne(filter, update);
        return result.getModifiedCount() > 0;
    }
}
```

### Challenge 2: Bulk Write Failure Report Service
Implement a bulk write service. Attempt to execute bulk writes. If a `MongoBulkWriteException` is caught:
*   Collect the count of successful writes.
*   Check if any error codes match `11000` (Duplicate Key). If a duplicate key error is found, increment a duplicate count.
*   Return a custom result document summary in format: `{"successCount": X, "duplicateErrorsCount": Y}`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.MongoBulkWriteException;
import com.mongodb.bulk.BulkWriteError;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.WriteModel;
import org.bson.Document;
import java.util.List;

public class BulkWriteDiagnosticService {

    public Document executeBulkWithDiagnostics(MongoCollection<Document> collection, List<WriteModel<Document>> operations) {
        // TODO: Attempt bulkWrite. Catch MongoBulkWriteException, parse errors and success count.
        try {
            var result = collection.bulkWrite(operations);
            return new Document("successCount", result.getInsertedCount() + result.getModifiedCount())
                .append("duplicateErrorsCount", 0);
        } catch (MongoBulkWriteException e) {
            int successCount = e.getWriteResult().getInsertedCount() + e.getWriteResult().getModifiedCount();
            int duplicates = 0;
            for (BulkWriteError err : e.getWriteErrors()) {
                if (err.getCode() == 11000) {
                    duplicates++;
                }
            }
            return new Document("successCount", successCount)
                .append("duplicateErrorsCount", duplicates);
        }
    }
}
```

### Challenge 3: Exponential Backoff Retry Loop
Implement a write retry runner. Attempt to insert a document. If a `com.mongodb.MongoSocketOpenException` (transient network failure) is thrown:
*   Retry the operation up to 3 times.
*   Implement exponential backoff: sleep `attempt * 100` milliseconds between retries.
*   If all 3 retries fail, return `false`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.MongoSocketOpenException;
import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class BackoffRetryService {

    public boolean insertWithBackoff(MongoCollection<Document> collection, Document doc) {
        // TODO: Loop 3 times. Sleep attempt * 100 ms on MongoSocketOpenException.
        int maxAttempts = 3;
        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                collection.insertOne(doc);
                return true;
            } catch (MongoSocketOpenException e) {
                if (attempt == maxAttempts) {
                    return false;
                }
                try {
                    Thread.sleep(attempt * 100L);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    return false;
                }
            }
        }
        return false;
    }
}
```

### Verification Tests
Verify all three exercises using this JUnit 5 verification test suite:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.result.UpdateResult;
import com.mongodb.MongoSocketOpenException;
import com.mongodb.ServerAddress;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class ErrorHandlingExercisesTest {

    @SuppressWarnings("unchecked")
    @Test
    void testProcessPaymentSuccess() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        UpdateResult mockResult = mock(UpdateResult.class);
        
        when(mockCol.updateOne(any(), any())).thenReturn(mockResult);
        when(mockResult.getModifiedCount()).thenReturn(1L);

        IdempotentPaymentService service = new IdempotentPaymentService();
        boolean success = service.processPayment(mockCol, "ACCT-1", 100.00, "TOKEN-XYZ");

        assertTrue(success);
    }

    @SuppressWarnings("unchecked")
    @Test
    void testBackoffRetryLoopSuccess() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        BackoffRetryService service = new BackoffRetryService();

        // First attempt fails, second succeeds
        doThrow(new MongoSocketOpenException("Network error", new ServerAddress()))
            .doNothing()
            .when(mockCol).insertOne(any(Document.class));

        boolean success = service.insertWithBackoff(mockCol, new Document());
        assertTrue(success);
        verify(mockCol, times(2)).insertOne(any(Document.class));
    }

    @SuppressWarnings("unchecked")
    @Test
    void testBackoffRetryLoopExhausted() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        BackoffRetryService service = new BackoffRetryService();

        doThrow(new MongoSocketOpenException("Network error", new ServerAddress()))
            .when(mockCol).insertOne(any(Document.class));

        boolean success = service.insertWithBackoff(mockCol, new Document());
        assertFalse(success);
        verify(mockCol, times(3)).insertOne(any(Document.class));
    }
}
```
