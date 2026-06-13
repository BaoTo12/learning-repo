# Module 18: Application Diagnostics (Chapter 18)

Welcome class. Today we analyze **Application Diagnostics (CS-529)**.

In production environments, database queries can occasionally lock collections, exhaust connection pools, or query without indexes, degrading application throughput. Administrators must detect and terminate these operations.

Today we study **Database Operation Diagnostics**, analyzing system operations, `currentOp` queries, operation terminations (`killOp`), and profiler adjustments in Java.

---

## 1. Academic Lecture: Operation States & Profiler Controls

### 1. Analyzing Active Operations (`currentOp`)
The `currentOp` command returns a document listing all active operations running on the database server. It provides details such as:
*   `opid`: The operation ID (used to terminate the thread).
*   `secs_running`: How long the operation has been executing.
*   `ns`: The target namespace (database and collection).
*   `query`: The raw filter document of the query.

### 2. Query Profiler Configurations
The MongoDB query profiler writes performance logs to the `system.profile` capped collection. We configure three profiling levels:
*   `0`: Profiler disabled.
*   `1`: Logs operations slower than a specified threshold (e.g. `slowms: 100`).
*   `2`: Logs all operations (Warning: high write overhead).

```text
[Client Query] ──> [Database Engine (Evaluated against slowms)]
                            │
                            ├── (If duration > slowms) ──> Log to system.profile
                            └── (Otherwise) ──────────────> Complete silently
```

---

## 2. Theory vs. Production Trade-offs

Compare query diagnostic options:

| Dimension / Metric | Explain Plan Analysis (`explain`) | Database Profiler Level 1 | System Log Parsing |
| :--- | :--- | :--- | :--- |
| **Performance Cost** | Low (Single query evaluation) | Low (Only logs slow queries) | Very Low (Async filesystem logs) |
| **Real-time Evaluation** | Manual testing only | Continuous (Active capture) | Offline analysis |
| **Storage Overhead** | None | Low (Capped collection) | High (Log rotations needed) |
| **Best Use Case** | Query construction optimization | Production performance audits | Deep systems audits |

---

## 3. How to Use: Inspecting Database Operations in Java

Let us inspect active database threads. We contrast a blind application loop with a diagnostic controller that monitors and terminates slow queries using Java.

### A. The Blocked Application Thread (Anti-Pattern)
Avoid executing unconstrained operations that block database threads:

```java
// DANGER: An unindexed query on a collection with millions of documents 
// will consume high CPU and lock collections, slowing down other client writes.
collection.find(Filters.eq("notes", "unindexed search term")).first();
```

### B. The Operational Diagnostic Controller (Production Pattern)
Query `currentOp` to identify slow-running tasks, and terminate them programmatically:

```java
import com.mongodb.client.MongoDatabase;
import org.bson.Document;
import java.util.List;

public class DiagnosticService {

    public void killLongRunningQueries(MongoDatabase adminDb, int maxDurationSecs) {
        // 1. Query currentOp to find user operations running longer than threshold
        Document filter = new Document("active", true)
                .append("secs_running", new Document("$gt", maxDurationSecs))
                .append("op", new Document("$ne", "none")); // Exclude background system tasks

        Document currentOpResult = adminDb.runCommand(new Document("currentOp", filter));
        List<Document> inprogress = currentOpResult.getList("inprog", Document.class);

        if (inprogress != null) {
            for (Document op : inprogress) {
                int opId = op.getInteger("opid");
                System.out.printf("Killing Operation: %d | Namespace: %s | Duration: %d s%n",
                        opId, op.getString("ns"), op.getInteger("secs_running")
                );
                
                // 2. Kill the operation using killOp
                adminDb.runCommand(new Document("killOp", 1).append("op", opId));
            }
        }
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Leaving Profiler Level at 2 in Production
*   **Why it fails**: Running the database with profiler level `2` (log all operations). This forces the database to write metadata to `system.profile` for every write and read operation, creating a write-amplification bottleneck.
*   **Mitigation**: Use level `1` with a conservative `slowms` limit (e.g. 100ms or 200ms) in production. Use level `2` only in staging or test environments.

---

## 5. Socratic Review Questions

### Question 1
Why does calling `killOp` on a long-running write operation occasionally fail to terminate the operation immediately?

#### Answer
The `killOp` command acts as an asynchronous interrupt flag. The target operation must yield its thread (for example, during index key processing or data block transitions) to detect the interrupt flag. If the write is blocked in disk I/O wait states or processing an complex WiredTiger write transaction lock, the operation may persist for several seconds before terminating.

---

## 6. Hands-on Challenge: Slow Operation Terminating Worker

### The Challenge
In this challenge, you will implement a diagnostic manager in Java.
Your task:
1. Complete `findSlowOperations` in `DiagnosticManager`.
2. Run `currentOp` on the admin database.
3. Filter active operations running on the collection namespace `"prod.transactions"` that have been running for more than `10` seconds.
4. Extract and return a List of their integer operation IDs (`opid`).

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoDatabase;
import java.util.List;

public class DiagnosticManager {

    public List<Integer> findSlowOperations(MongoDatabase adminDatabase) {
        // TODO: Query currentOp with filters active=true, ns="prod.transactions", secs_running > 10,
        // extract opid integers from the "inprog" array list, and return them.
        return null;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoDatabase;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class DiagnosticManagerTest {

    @Test
    void testFindSlowOperations() {
        MongoDatabase adminDb = mock(MongoDatabase.class);
        
        // Mock currentOp response
        Document op1 = new Document("opid", 9921)
                .append("active", true)
                .append("ns", "prod.transactions")
                .append("secs_running", 15);

        Document currentOpResponse = new Document("inprog", List.of(op1));
        
        when(adminDb.runCommand(any(Document.class))).thenReturn(currentOpResponse);

        DiagnosticManager manager = new DiagnosticManager();
        List<Integer> slowIds = manager.findSlowOperations(adminDb);

        assertNotNull(slowIds);
        assertEquals(1, slowIds.size());
        assertEquals(9921, slowIds.get(0));
    }
}
```
