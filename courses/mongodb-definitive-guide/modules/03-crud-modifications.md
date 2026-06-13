# Module 03: Creating, Updating, and Deleting Documents (Chapter 3)

Welcome class. Today we analyze **Creating, Updating, and Deleting Documents (CS-529)**.

In MongoDB, document updates are optimized using atomic modifiers to prevent race conditions. Performing updates using raw document replacements overrides concurrent writes. To modify fields, arrays, and nested structures inside BSON trees, we utilize the Java driver's type-safe `Updates` builders and positional array filters.

Today we study **Atomic Write Operators & Array Filters**, learning the updates pipeline in Java, positional operators, and document size relocation bounds.

---

## 1. Academic Lecture: Document Relocation & Atomic Modifiers

### 1. Storage Relocation Penalties
Under the **WiredTiger** storage engine, document bytes are stored in contiguous blocks on disk. If a write operation increases a document's size beyond its allocated space, WiredTiger must copy the entire document to a new block and rewrite all indexes referencing the document's ID. 

### 2. The Updates API & Atomicity
Instead of replacing a document (which leads to dirty updates if concurrent writes collide), the Java Sync Driver provides a type-safe `Updates` factory.
*   `Updates.set()`, `Updates.inc()`, `Updates.push()`, `Updates.pull()`
*   The database engine locks the document at the collection/document level, applying the modification locally. This ensures isolation without transaction overhead.

```text
[Original Document] ────> Update request (Updates.inc("score", 10)) 
                                │
                        (Acquires write lock)
                                ▼
[Modified Document] ────> (Releases lock, writes only changed delta)
```

---

## 2. Theory vs. Production Trade-offs

Compare update strategies inside Java clients:

| Dimension / Metric | Replacement (`replaceOne`) | Atomic Modifiers (`updateOne`) | Bulk Operations (`bulkWrite`) |
| :--- | :--- | :--- | :--- |
| **Concurrency Safety** | Low (Vulnerable to overrides) | High (Atomic field execution) | High |
| **Network Payload** | High (Sends complete Document) | Low (Sends update operators) | Low (Batched updates) |
| **Index Overhead** | High (Rewrites all indexes) | Low (Modifies only altered keys) | Low |
| **Use Case** | Re-structuring documents | Incremental updates | High-throughput imports |

---

## 3. How to Use: Type-Safe Array Filters in Java

Let us write Java update queries. We contrast a naive positional array write with the robust positional filtered update pattern utilizing `arrayFilters`.

### A. The Basic Positional Update (Anti-Pattern)
Avoid the generic `$` operator if you need to match and modify multiple specific elements in an array:

```java
// DANGER: The "$" operator only updates the FIRST matched element in the array.
// Subsequent matching array elements are left unchanged.
collection.updateOne(
    Filters.eq("_id", 1),
    Updates.set("scores.$", "Passed")
);
```

### B. The Hardened Positional Filtered Update (Production Pattern)
Use `UpdateOptions.arrayFilters` to target all matching array items programmatically:

```java
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import com.mongodb.client.model.UpdateOptions;
import org.bson.Document;
import java.util.List;

// Robust Pattern: Modifies status to "Passed" for all nested score objects where grade >= 80.
UpdateOptions options = new UpdateOptions().arrayFilters(List.of(
    Filters.gte("elem.grade", 80)
));

collection.updateOne(
    Filters.eq("_id", 1),
    Updates.set("scores.$[elem].status", "Passed"),
    options
);
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Unbounded Document Size Escalation
*   **Why it fails**: Appending data (like user logs or audit entries) into an embedded array using `Updates.push()` without limit controls. As the array grows, document sizes approach the **16MB limit**. The storage engine must constantly relocate the document on disk, leading to high latency.
*   **Mitigation**: Bounded arrays. Use the `$slice` operator inside updates to keep only the latest N items:
    `Updates.pushEach("logs", logDocs, new PushOptions().slice(-100))`.

---

## 5. Socratic Review Questions

### Question 1
Why does using `Updates.inc()` guarantee consistency under high concurrency compared to reading a document, calculating the new value in Java, and writing it back using `replaceOne()`?

#### Answer
If two threads read the same balance value ($100), increment it locally by $10, and call `replaceOne()`, both will write $110, resulting in a lost update ($10 missing). `Updates.inc()` executes entirely within the database engine's write lock, executing an atomic mathematical operation (`balance = balance + 10`) directly on the storage block.

---

## 6. Hands-on Challenge: Java Array Filter Update

### The Challenge
In this challenge, you will implement a nested array update in Java.
Your task:
1. Complete `deactivateCourseEnrollment` in `StudentService`.
2. The student document contains an array `courses` with elements containing `code` (String) and `enrolled` (Boolean).
3. Set `enrolled` to `false` for all courses where `code` matches the target parameter.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class StudentService {

    public void deactivateCourseEnrollment(MongoCollection<Document> collection, Object studentId, String courseCode) {
        // TODO: Execute updateOne using Updates.set and UpdateOptions with arrayFilters targeting courseCode
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.mockito.Mockito.*;

class StudentServiceTest {

    @SuppressWarnings("unchecked")
    @Test
    void testDeactivateCourseEnrollment() {
        MongoCollection<Document> collection = mock(MongoCollection.class);
        StudentService service = new StudentService();

        service.deactivateCourseEnrollment(collection, 123, "CS-101");

        // Verify that updateOne is invoked with correct filters and updates
        verify(collection, times(1)).updateOne(
            any(), // Filters
            any(), // Updates
            any()  // UpdateOptions
        );
    }
}
```
