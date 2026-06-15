# Module 19: Interview Preparation

Welcome, student. Today we review core concepts in this **MongoDB Interview Preparation Guide (CS-529)**.

---

## 1. What problem does this solve?
Navigating backend engineering job interviews requires explaining not only syntax, but also the underlying systems architecture and performance trade-offs under load.

This module provides **scenario-based interview questions and answers** covering indexing, sharding, transactions, and Java integration.

---

## 2. Why does MongoDB provide this feature?
Architectural questions evaluate your systems design competency.

---

## 3. How does it work internally or conceptually?
Questions focus on topics like:
*   B-Tree index traversal structures vs collection scans.
*   WiredTiger lock management and ticket mechanisms.
*   Consensus elections in replica sets.

---

## 4. How do we use it in Java?
Questions focus on MongoClient connection pooling settings and transaction session management.

---

## 5. What are the trade-offs?
*   Relational databases vs document databases consistency trade-offs.

---

## 6. Common Mistakes
*   Explain plan diagnostic errors, over-indexing, and un-anchored regex queries.

---

## 7. When should we use it?
*   Review these scenarios when preparing for systems design or senior backend developer roles.

---

## 8. When should we avoid it?
*   Do not memorize answers; focus on understanding the engineering trade-offs.

---

## 9. Q&A Scenario Sets

### Q1: What is the ESR rule, and why does violating it hurt query performance?
**Answer**:
The ESR rule states that compound index keys must be ordered: **E**quality fields first, **S**ort fields second, and **R**ange fields last.
If a range field is placed before a sort field (e.g. index on `{ age: 1, name: 1 }` with query `{ age: { $gt: 20 } }` sorted by `name`), MongoDB cannot use the index sorting. The query planner must scan the matched index segments and run a CPU-heavy in-memory sort stage (`SORT`).

### Q2: Why are MongoDB multi-document transactions unable to execute on a standalone database process?
**Answer**:
Multi-document transactions require replica set or sharded cluster architectures. Transactions use the cluster's replication oplog to distribute atomic write operations across nodes. A standalone database process does not produce an oplog, making transaction session tracking impossible.

### Q3: Explain the difference in execution plans between a covered query and a normal query scan.
**Answer**:
*   *Covered Query*: All filtered and projected fields exist within the index itself. In the explain plan, we see `IXSCAN` but **no** `FETCH` stage, as the database retrieves data from index keys directly without reading files from disk.
*   *Normal Query*: The database engine runs `IXSCAN` followed by a `FETCH` stage to load the BSON document from disk into memory.

---

## 10. Hands-on Exercises

### The Challenge
Implement a helper method `verifyAnswerFormat` that checks if an answer is non-null and starts with the prefix `"Answer:"`.

Complete the implementation stub:

```java
package com.mongodb.systems;

public class InterviewHelper {

    public static boolean verifyAnswerFormat(String answer) {
        // TODO: Return true if the answer is not null and starts with "Answer:"
        return answer != null && answer.startsWith("Answer:");
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class InterviewHelperTest {

    @Test
    void testAnswerVerification() {
        assertTrue(InterviewHelper.verifyAnswerFormat("Answer: The ESR rule is..."));
        assertFalse(InterviewHelper.verifyAnswerFormat("The ESR rule is..."));
        assertFalse(InterviewHelper.verifyAnswerFormat(null));
    }
}
```
