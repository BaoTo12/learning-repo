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

### 4.1 Visual Dataset & Duplicate Key Error Trace

#### Existing Database State (`users` Collection):
```json
[
  { "_id": "USR-10", "email": "alice@gmail.com" }
]
```

#### Step-by-Step Duplicate Insert Execution Path:

1. **Client Sends Insert Operation**:
   * Request: `collection.insertOne(new Document("_id", "USR-11").append("email", "alice@gmail.com"));`
2. **Server Evaluates Unique Constraints**:
   * MongoDB tries to write the document. It scans the unique index index on the `email` field.
   * A match is found: `"alice@gmail.com"` already exists on document `"USR-10"`.
3. **Server Aborts Write**:
   * The database rolls back memory modifications, stops logging to journal, and replies with code `11000` (Duplicate Key Error).
4. **Driver Converts Response**:
   * The Java driver catches the network response, parses the BSON payload, and throws a `com.mongodb.MongoWriteException`.
5. **Application Error Recovery**:
   * The application's `try-catch` block catches the exception, checks `.getCode()`, detects `11000`, and handles it gracefully (e.g. prompt user that email is taken) instead of crashing.

```java
import com.mongodb.MongoWriteException;
import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class SaveHandler {
    public boolean insertSafe(MongoCollection<Document> collection, Document doc) {
        try {
            // Attempt to insert document directly into MongoDB
            collection.insertOne(doc);
            return true;
        } catch (MongoWriteException e) {
            // com.mongodb.MongoWriteException wraps server-side errors during write queries.
            // BSON Code 11000 indicates unique index key constraint violations.
            // BSON Code 121 indicates schema jsonSchema validation rules were violated.
            int code = e.getError().getCode();
            System.err.println("Write failed on server. Error Code: " + code + " | Message: " + e.getError().getMessage());
            return false;
        }
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`collection.insertOne(doc)`**: Performs a single document insert. Throws a runtime exception if any server-side write restrictions are violated.
- **`e.getError().getCode()`**: Accesses the underlying `com.mongodb.WriteError` details, extracting the numeric database server error code.
- **`code == 11000` / `code == 121`**: Identifies specific database engine blocks, allowing localized routing for client corrections.

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

##### Exception Mapping and Failover Trace:

###### Network Partition Scenario:
1. **Application Executes Write**:
   * `collection.insertOne(doc)` is called.
2. **Connection Breakage**:
   * The network link between the Java client host and the replica set primary is cut midway.
3. **Socket Timeout / Acquire Failures**:
   * The driver fails to establish a socket stream or times out while waiting for a response, generating a connection exception.
4. **Exception Mapping**:
   * `MongoSocketOpenException`: Thrown if the host is unreachable.
   * `MongoSocketReadTimeoutException` / `MongoTimeoutException`: Thrown if the socket is alive but the query times out or the connection pool exhausts.
   * The diagnostic block maps these specific scenarios to clean enumerations like `NETWORK_FAILURE` or `TIMEOUT`, bypassing runtime crash risks.

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
            // Attempt inserting document
            collection.insertOne(doc);
            return ErrorStatus.SUCCESS;
        } catch (MongoWriteException e) {
            // Intercept server-side database constraint errors
            int code = e.getError().getCode();
            if (code == 11000) {
                return ErrorStatus.DUPLICATE_KEY;
            } else if (code == 121) {
                return ErrorStatus.VALIDATION_FAILURE;
            }
            return ErrorStatus.UNKNOWN_ERROR;
        } catch (MongoSocketReadTimeoutException | MongoTimeoutException e) {
            // MongoSocketReadTimeoutException: query response timeout
            // MongoTimeoutException: connection pool connection checkout timeout
            return ErrorStatus.TIMEOUT;
        } catch (MongoSocketOpenException e) {
            // MongoSocketOpenException: physical TCP connection failure to the nodes
            return ErrorStatus.NETWORK_FAILURE;
        } catch (MongoException e) {
            // Catch-all for other driver exceptions (e.g. MongoCommandException, client configuration errors)
            System.err.println("Generic database failure: " + e.getMessage());
            return ErrorStatus.UNKNOWN_ERROR;
        }
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`MongoSocketOpenException`**: Subclass of `MongoException` that signals failures during socket opening. It usually indicates that the database server process is offline or blocked.
- **`MongoSocketReadTimeoutException`**: Occurs if the server accepts the socket connection but fails to send response packages back within the configured socket read timeout.
- **`MongoTimeoutException`**: Signals connection pool exhaustion or target election failover delays that exceed client query timeouts.

---

### B. IDEMPOTENCY IN WRITES

#### Non-Idempotent Pattern (Danger)
If the connection drops after the server executes the write but before the client receives confirmation, the client retries the push, resulting in duplicate logs.

##### Non-Idempotent execution trace path:
*   Initial State: `{ "_id": "USR-1", "loginHistory": [] }`
*   Client Issues: `updateOne(eq("_id", "USR-1"), push("loginHistory", "Log-A"))`
*   Server applies push. State becomes: `{ "_id": "USR-1", "loginHistory": ["Log-A"] }`
*   Network drop: Acknowledgment package is lost.
*   Client retries operation.
*   Server applies push again. Final State: `{ "_id": "USR-1", "loginHistory": ["Log-A", "Log-A"] }` (Data duplication occurred).

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class UnsafeArrayPush {
    public void addLog(MongoCollection<Document> collection, String userId, String log) {
        // Danger: If retried, this adds the log element twice since $push is not idempotent.
        collection.updateOne(Filters.eq("_id", userId), Updates.push("loginHistory", log));
    }
}
```

#### Idempotent Pattern (Safe)
Use `$addToSet` (which only appends unique values) or check a unique transaction token before pushing.

##### Idempotent trace path:
*   Initial State: `{ "_id": "USR-1", "purchases": [], "processedTokens": [] }`
*   Client Issues Update: `filter = eq("_id", "USR-1") AND ne("processedTokens", "TX-100")`
*   Updates applied: `push("purchases", purchase)` and `push("processedTokens", "TX-100")`
*   First run succeeds. Global State: `{ "_id": "USR-1", "purchases": [purchase], "processedTokens": ["TX-100"] }`
*   Network drop: Acknowledgment is lost.
*   Client retries operation.
*   Evaluation: `ne("processedTokens", "TX-100")` check **fails** because `"TX-100"` already exists in the array.
*   Server skips update. modifiedCount is `0`. Data is kept safe from duplicates.

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class SafeIdempotentWrite {
    public void addLogSafe(MongoCollection<Document> collection, String userId, String log) {
        // Safe: $addToSet guarantees uniqueness in the array. Retrying this is safe.
        collection.updateOne(Filters.eq("_id", userId), Updates.addToSet("loginHistory", log));
    }

    public boolean addPurchaseWithToken(MongoCollection<Document> collection, String userId, Document purchase, String transactionToken) {
        // Safe: Match document only if the transactionToken has not already been processed.
        // Filters.ne ensures the transactionToken does not exist in the processedTokens list.
        var filter = Filters.and(
            Filters.eq("_id", userId),
            Filters.ne("processedTokens", transactionToken)
        );

        // Updates.combine wraps both pushes into a single write operation.
        var update = Updates.combine(
            Updates.push("purchases", purchase),
            Updates.push("processedTokens", transactionToken)
        );

        var result = collection.updateOne(filter, update);
        // Returns true if modifiedCount > 0, indicating the update was applied.
        // Returns false if 0, indicating a retry that was ignored due to duplicate token.
        return result.getModifiedCount() > 0;
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`Updates.addToSet("fieldName", value)`**: Adds a value to an array unless it's already present. Useful for building idempotent logs/lists.
- **`Filters.ne("fieldName", value)`**: Tests inequality. Inside arrays, it checks that *no* element matches the value.
- **`result.getModifiedCount()`**: Checks the count of updated documents. If the count is 0 in the idempotent check, the calling service knows the operation was already processed during a previous attempt.

---

### C. HANDLING BULK WRITE ERRORS

When executing bulk writes, we must parse the `MongoBulkWriteException` to identify exactly which documents failed and which succeeded.

##### Bulk Write Error Visualization:

###### Input Operations List:
1. `InsertOneModel({ "_id": "A" })`
2. `InsertOneModel({ "_id": "B" })` (Duplicate Key, already exists)
3. `InsertOneModel({ "_id": "C" })`

###### Execution Processing Trace (Ordered = true):
*   **Operation 0**: Successful insert of "A".
*   **Operation 1**: Fails with Duplicate Key Error.
*   **Ordered Failure**: Since the execution is ordered, execution halts. Operation 2 is skipped.
*   **Exception Throw**: `MongoBulkWriteException` is thrown:
    *   `insertedCount` = 1
    *   `writeErrors` = `[BulkWriteError(index=1, code=11000, message="Duplicate Key")]`

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
            // Execute the bulk operations.
            collection.bulkWrite(operations);
            System.out.println("Bulk write completed successfully.");
        } catch (MongoBulkWriteException e) {
            // MongoBulkWriteException is thrown if any of the operations in the list fail.
            System.err.println("Bulk write encountered failures.");
            // e.getWriteResult() holds results of successful changes before the abort occurred
            System.err.println("Successful writes count: " + e.getWriteResult().getInsertedCount());
            
            // Iterate over errors to pinpoint issues.
            // e.getWriteErrors() returns individual BulkWriteError records mapping to the failed requests.
            for (BulkWriteError error : e.getWriteErrors()) {
                System.err.println("Error at operation index " + error.getIndex() 
                    + " | Code: " + error.getCode() 
                    + " | Message: " + error.getMessage());
            }
        }
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`collection.bulkWrite(List<WriteModel>)`**: Combines multiple inserts, updates, and deletes into a single request payload to minimize connection socket rounds.
- **`BulkWriteError.getIndex()`**: Returns the 0-indexed position of the write model request that failed inside the original operations list passed to `bulkWrite()`.
- **`BulkWriteError.getCode()`**: Server BSON error code indicating the root cause of that specific failed operation.

---

## 10. Hands-on Exercises

### Challenge 1: Idempotent Payment Processor
Implement a payment processing service method. To prevent double-charging users, you must make the write operation idempotent using a `paymentToken` string.
*   Query the user account.
*   Only deduct the `amount` from the `balance` if the `paymentToken` is not present in the user's `processedPayments` array.
*   If the update succeeds, append the `paymentToken` to the `processedPayments` array.

##### Dataset and Execution Trace:

###### Input Dataset (`accounts` Collection):
```json
[
  { "_id": "ACCT-99", "balance": 500.0, "processedPayments": [] }
]
```

###### Scenario A: First attempt processing payment of 100.0:
1. **Apply Filter**: Match document with `_id: "ACCT-99"` AND `processedPayments != "TOKEN-P1"`. Match is found.
2. **Apply Update**: Decrements balance by `100.0` (new balance: `400.0`) and appends `"TOKEN-P1"` to `processedPayments`.
3. **Outcome**: Update completes, `result.getModifiedCount()` is `1`. Returns `true`.
4. **Final State**:
   ```json
   { "_id": "ACCT-99", "balance": 400.0, "processedPayments": ["TOKEN-P1"] }
   ```

###### Scenario B: Retry attempt of the same payment (TOKEN-P1):
1. **Apply Filter**: Match document with `_id: "ACCT-99"` AND `processedPayments != "TOKEN-P1"`.
2. **Outcome**: No document matches because `"TOKEN-P1"` is already in `processedPayments`.
3. **Execution Skip**: Skip balance deduction. `result.getModifiedCount()` is `0`. Returns `false`. Prevents duplicate charge.

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
        // Build idempotent update filter targeting active user without duplicate paymentToken
        var filter = Filters.and(
            Filters.eq("_id", accountId),
            Filters.ne("processedPayments", paymentToken)
        );

        // Perform balance deduction and paymentToken registry in a single write operation
        var update = Updates.combine(
            Updates.inc("balance", -amount),
            Updates.push("processedPayments", paymentToken)
        );

        UpdateResult result = collection.updateOne(filter, update);
        // Returns true if document was updated (first run), false if ignored (duplicate retry)
        return result.getModifiedCount() > 0;
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`Filters.ne("processedPayments", paymentToken)`**: Ensures that the update will not match the document if the unique payment token is already registered, acting as a concurrency and duplicate guard.
- **`Updates.combine(Updates.inc(...), Updates.push(...))`**: Chains multiple update instructions to run atomically together on the matching document.

---

### Challenge 2: Bulk Write Failure Report Service
Implement a bulk write service. Attempt to execute bulk writes. If a `MongoBulkWriteException` is caught:
*   Collect the count of successful writes.
*   Check if any error codes match `11000` (Duplicate Key). If a duplicate key error is found, increment a duplicate count.
*   Return a custom result document summary in format: `{"successCount": X, "duplicateErrorsCount": Y}`.

##### Dataset and Execution Trace:

###### Input Operations List:
1. `InsertOneModel({ "_id": "USR-1" })`
2. `InsertOneModel({ "_id": "USR-2" })` (Duplicate Key Error - already exists)
3. `InsertOneModel({ "_id": "USR-3" })` (Duplicate Key Error - already exists)

###### Outcome Diagnostic Document:
```json
{
  "successCount": 1,
  "duplicateErrorsCount": 2
}
```

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
        try {
            // Attempt executing the bulk write operations
            var result = collection.bulkWrite(operations);
            // If all operations succeed without error:
            return new Document("successCount", result.getInsertedCount() + result.getModifiedCount())
                .append("duplicateErrorsCount", 0);
        } catch (MongoBulkWriteException e) {
            // Catch bulk write exceptions, extracting successful write counts and error mappings
            int successCount = e.getWriteResult().getInsertedCount() + e.getWriteResult().getModifiedCount();
            int duplicates = 0;
            
            // Loop through all individual write errors to find duplicate keys (code 11000)
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

#### Detailed Operations & Syntax Explanation:
- **`e.getWriteResult()`**: Accesses the partial write result object inside the bulk exception payload.
- **`err.getCode() == 11000`**: Explicitly matches against the server-side BSON duplicate error code to distinguish key clashes from schema validation failures.

---

### Challenge 3: Exponential Backoff Retry Loop
Implement a write retry runner. Attempt to insert a document. If a `com.mongodb.MongoSocketOpenException` (transient network failure) is thrown:
*   Retry the operation up to 3 times.
*   Implement exponential backoff: sleep `attempt * 100` milliseconds between retries.
*   If all 3 retries fail, return `false`.

##### Step-by-Step Backoff Execution Timeline:
*   **Attempt 1**: `collection.insertOne(doc)` is called -> `MongoSocketOpenException` caught.
    *   Action: Backoff sleeps `1 * 100 = 100ms`.
*   **Attempt 2**: `collection.insertOne(doc)` is called -> `MongoSocketOpenException` caught.
    *   Action: Backoff sleeps `2 * 100 = 200ms`.
*   **Attempt 3**: `collection.insertOne(doc)` is called -> Success. Returns `true`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.MongoSocketOpenException;
import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class BackoffRetryService {

    public boolean insertWithBackoff(MongoCollection<Document> collection, Document doc) {
        int maxAttempts = 3;
        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                // Attempt to insert the document
                collection.insertOne(doc);
                return true; // Return success immediately if insert is successful
            } catch (MongoSocketOpenException e) {
                // Catch transient socket connection open issues.
                // If maximum attempts are exhausted, fail the operation permanently.
                if (attempt == maxAttempts) {
                    return false;
                }
                try {
                    // Sleep for attempt * 100 milliseconds (Exponential Backoff)
                    Thread.sleep(attempt * 100L);
                } catch (InterruptedException ie) {
                    // Restore interrupt thread status and abort immediately
                    Thread.currentThread().interrupt();
                    return false;
                }
            }
        }
        return false;
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`MongoSocketOpenException`**: Represents a transient networking fault when attempting to open a TCP socket channel to the node endpoints.
- **`Thread.sleep(attempt * 100L)`**: Introduces a short cooldown period that gets progressively longer with subsequent retries, giving the database time to recover.

---

### Verification Tests

Below is the JUnit 5 verification test suite. It uses Mockito to mock MongoDB collection calls and stub socket exception behavior to verify the backoff retry timings.

#### Detailed Testing & Verification Explanation:
*   **`doThrow(Exception).doNothing().when(mockCol).insertOne(...)`**: Configures Mockito to throw an exception on the first call, and succeed on the second.
*   **`verify(mockCol, times(2)).insertOne(...)`**: Asserts that the collection method was called exactly twice, validating the retry behavior.

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
        // 1. Arrange mock objects
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        UpdateResult mockResult = mock(UpdateResult.class);
        
        // 2. Configure mock actions
        when(mockCol.updateOne(any(), any())).thenReturn(mockResult);
        when(mockResult.getModifiedCount()).thenReturn(1L);

        // 3. Act
        IdempotentPaymentService service = new IdempotentPaymentService();
        boolean success = service.processPayment(mockCol, "ACCT-1", 100.00, "TOKEN-XYZ");

        // 4. Assert
        assertTrue(success);
    }

    @SuppressWarnings("unchecked")
    @Test
    void testBackoffRetryLoopSuccess() {
        // 1. Arrange mock objects
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        BackoffRetryService service = new BackoffRetryService();

        // Configure mock to throw socket exception on first run and succeed on second
        doThrow(new MongoSocketOpenException("Network error", new ServerAddress()))
            .doNothing()
            .when(mockCol).insertOne(any(Document.class));

        // 2. Act
        boolean success = service.insertWithBackoff(mockCol, new Document());
        
        // 3. Assert and Verify
        assertTrue(success);
        verify(mockCol, times(2)).insertOne(any(Document.class)); // Asserts retry succeeded on second attempt
    }

    @SuppressWarnings("unchecked")
    @Test
    void testBackoffRetryLoopExhausted() {
        // 1. Arrange mock objects
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        BackoffRetryService service = new BackoffRetryService();

        // Configure mock to persistently fail with socket exceptions
        doThrow(new MongoSocketOpenException("Network error", new ServerAddress()))
            .when(mockCol).insertOne(any(Document.class));

        // 2. Act
        boolean success = service.insertWithBackoff(mockCol, new Document());
        
        // 3. Assert and Verify
        assertFalse(success); // Loop should fail after exhausting all attempts
        verify(mockCol, times(3)).insertOne(any(Document.class)); // Asserts three attempts were executed
    }
}
```
