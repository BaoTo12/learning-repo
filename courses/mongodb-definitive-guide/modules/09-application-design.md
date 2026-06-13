# Module 09: Application Design (Chapter 9)

Welcome class. Today we analyze **Application Design (CS-529)**.

In document database architectures, database joins do not scale. Schema design is driven by access patterns—minimizing read latency by embedding nested objects or splitting records dynamically.

Today we study **Document Schema Engineering**, analyzing cardinality mappings, normalization vs. denormalization, and design patterns (Bucket, Subset, Extended Reference) in Java.

---

## 1. Academic Lecture: Schema Design Patterns & Working Sets

### 1. Cardinality Modeling in Java
*   **One-to-Few (1:Few)**: Embed as subdocuments (e.g. user address list).
*   **One-to-Many (1:N)**: If bounded (e.g., product variations), embed. If unbounded (e.g., transaction records), use parent referencing.
*   **One-to-Squillions (1:10^6)**: Always use parent referencing. Never store millions of references inside an array on a parent document to avoid exceeding the 16MB limit.

### 2. Advanced Design Patterns
*   **The Bucket Pattern**: Instead of storing unbounded arrays, group logs into documents representing discrete buckets (e.g., 100 entries per document).
*   **The Subset Pattern**: If documents contain rarely accessed fields (e.g., 500 product reviews), store only the top 5 reviews in the main product document, and move the rest to a separate `reviews` collection to optimize the WiredTiger RAM cache.

```text
[Standard Unbounded Array]
User Document { logs: [0, 1, 2, ... 1,000,000] } (exceeds 16MB, slow indices)

[Bucket Pattern]
Bucket Document 1 { userId, count: 100, logs: [...] }
Bucket Document 2 { userId, count: 100, logs: [...] } (Bounded size, fast search)
```

---

## 2. Theory vs. Production Trade-offs

Compare relationship modeling patterns:

| Modeling Strategy | Read Performance | Write Performance | Data Consistency | Working Set Size |
| :--- | :--- | :--- | :--- | :--- |
| **Normalized References** | Low (Requires parent queries) | High (Writes are isolated) | Strict (Single point of truth) | Low |
| **Denormalized (Embedded)**| Excellent (Single fetch reads) | Low (Rewriting large arrays) | Low (Data duplicates) | High |
| **Subset Pattern** | High | High | Strict | Very Low (Optimized RAM cache) |
| **Bucket Pattern** | High | High | Strict | Low |

---

## 3. How to Use: Implementing the Bucket Pattern in Java

Let us construct schema modifications. We contrast an unbounded array logging scheme with the robust Bucket Pattern implemented in Java.

### A. The Unbounded Array Logging (Anti-Pattern)
Avoid appending unlimited entries to a single document array:

```java
// DANGER: The array will grow indefinitely. When the document approaches 16MB, 
// WiredTiger must allocate new blocks and copy the entire document, causing high write latency.
collection.updateOne(
    Filters.eq("deviceId", "DEV-101"),
    Updates.push("history", new Document("timestamp", new Date()).append("status", "OK"))
);
```

### B. The Bounded Bucket Pattern (Production Pattern)
Limit document counts dynamically by upserting into buckets:

```java
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import com.mongodb.client.model.UpdateOptions;
import org.bson.Document;
import java.util.Date;

// Robust Pattern: Appends to a bucket document only if it contains fewer than 100 logs.
UpdateOptions options = new UpdateOptions().upsert(true);

collection.updateOne(
    Filters.and(
        Filters.eq("deviceId", "DEV-101"),
        Filters.lt("count", 100)
    ),
    Updates.combine(
        Updates.push("history", new Document("timestamp", new Date()).append("status", "OK")),
        Updates.inc("count", 1),
        Updates.setOnInsert("start", new Date())
    ),
    options
);
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Denormalizing Volatile Fields
*   **Why it fails**: Duplicating a product's price or stock count into every transaction document. Because prices and stock change constantly, updating thousands of orders or active carts every time a value shifts creates high write lock contention.
*   **Mitigation**: Only denormalize static or rarely changed fields (e.g. product names, category tags). Keep volatile fields normalized.

---

## 5. Socratic Review Questions

### Question 1
How does the "Extended Reference Pattern" improve database read performance, and what operational cost does it introduce?

#### Answer
The Extended Reference Pattern copies high-frequency fields from a referenced document directly into the primary document (e.g., storing `customerName` in an `Order` document instead of just `customerId`). This eliminates database joins on reads, reducing latency. The operational cost is eventual consistency management: if the customer updates their name, the application must run a background worker to update all orders containing that name.

---

## 6. Hands-on Challenge: Java Telemetry Bucket Builder

### The Challenge
In this challenge, you will implement the Bucket Pattern in Java.
Your task:
1. Complete `appendTelemetryLog` in `TelemetryService`.
2. Add a telemetry log document to a device's log bucket in `device_telemetry`.
3. A bucket is defined by `deviceId` and must hold at most `50` logs.
4. Increment the `count` field by 1 on each append. Use `Updates.combine` and enable `upsert(true)`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class TelemetryService {

    public void appendTelemetryLog(MongoCollection<Document> collection, String deviceId, Document logEntry) {
        // TODO: Execute updateOne with filter (deviceId and count < 50), updates (push log, inc count, setOnInsert start date), and upsert option
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class TelemetryServiceTest {

    @SuppressWarnings("unchecked")
    @Test
    void testAppendTelemetryLog() {
        MongoCollection<Document> collection = mock(MongoCollection.class);
        TelemetryService service = new TelemetryService();
        Document entry = new Document("temp", 22.5);

        service.appendTelemetryLog(collection, "D-101", entry);

        // Verify updateOne was called
        verify(collection, times(1)).updateOne(any(), any(), any());
    }
}
```
