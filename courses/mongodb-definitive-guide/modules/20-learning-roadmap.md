# Module 20: Learning Roadmap

Welcome, student. Today we outline the **MongoDB with Java Study Plan (CS-529)**.

---

## 1. What problem does this solve?
Learning a massive framework without a structured timeline leads to knowledge gaps. 

We solve this using a **4-week study plan** with weekly milestones and exercises.

---

## 2. Why does MongoDB provide this feature?
Structured roadmaps optimize learning timelines.

---

## 3. How does it work internally or conceptually?
The curriculum is organized dynamically to transition learners from basics (Module 1-5) to advanced performance and production scaling (Module 16-20).

---

## 4. How do we use it in Java?
Weeks combine reading lessons, executing stubs, and writing JUnit 5 verification tests.

---

## 5. What are the trade-offs?
*   **Pros**: Ensures complete topic coverage.
*   **Cons**: Requires structured study discipline.

---

## 6. Common Mistakes
*   Skipping testing chapters. Tests are critical to proving database logic.
*   Focusing only on Spring Data without understanding the underlying native Java driver mechanics.

---

## 7. When should we use it?
*   Use this roadmap to guide your learning over the next 4 weeks.

---

## 8. When should we avoid it?
*   Do not rush; complete the weekly hands-on challenges before moving to the next week.

---

## 9. Roadmap Curriculum

### Week 1: Core Fundamentals & CRUD
*   *Topics*: Document models, connection pooling, basic inserts, updates, deletions, and query filters.
*   *Tasks*: Create a local sandbox, connect a Java application, and complete Module 1–4 exercises.

### Week 2: Design Patterns & Indexing
*   *Topics*: Embedding vs referencing, design patterns (Bucket, Subset), indexing models, ESR rules, explain plans.
*   *Tasks*: Configure compound unique indexes and run covered queries.

### Week 3: Aggregations, Validation & Transactions
*   *Topics*: Pipeline aggregation stages (`$group`, `$lookup`, `$unwind`), JSON Schema validation, multi-document ACID transactions.
*   *Tasks*: Implement transaction blocks with auto-retry handlers.

### Week 4: Production Scaling, Security & Testing
*   *Topics*: Replica sets, failovers, sharded clusters, TLS/SSL, Testcontainers, and capstone project assembly.
*   *Tasks*: Assemble the E-Commerce API and run integration test suites.

---

## 10. Hands-on Exercises

### The Challenge
Implement a validator method `isRoadmapComplete` that evaluates if a week list is not null and has a size of exactly 4.

Complete the implementation stub:

```java
package com.mongodb.systems;

import java.util.List;

public class RoadmapValidator {

    public static boolean isRoadmapComplete(List<String> weeks) {
        // TODO: Return true if weeks is not null and has exactly 4 items
        return weeks != null && weeks.size() == 4;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class RoadmapValidatorTest {

    @Test
    void testRoadmapValidation() {
        assertTrue(RoadmapValidator.isRoadmapComplete(List.of("W1", "W2", "W3", "W4")));
        assertFalse(RoadmapValidator.isRoadmapComplete(List.of("W1", "W2")));
        assertFalse(RoadmapValidator.isRoadmapComplete(null));
    }
}
```
