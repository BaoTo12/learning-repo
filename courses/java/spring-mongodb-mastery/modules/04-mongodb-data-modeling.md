# Module 04: MongoDB Data Modeling

Welcome class. Today we study **MongoDB Data Modeling (CS-530)**.

In document database architectures, relational schemas do not scale. Modeling decisions must be based on application read and write access patterns. Today we study embedding vs. referencing, `@DBRef` mechanics, and advanced design patterns.

---

## 1. Academic Lecture: Data Modeling and Schema Design Patterns

### Basic Level: Embedding vs. Referencing
*   **Embedding (Denormalization)**: Nesting related data inside a single document (e.g. storing address lists inside the user document). This allows fetching all related data in a single read operation.
*   **Referencing (Normalization)**: Storing data in separate collections and linking them using identifiers. This keeps documents small, preventing them from growing beyond the 16MB BSON size limit.

### Intermediate Level: `@DBRef` and Spring Data Resolution
Spring Data MongoDB provides the `@DBRef` annotation to link documents across collections.
*   **Resolution**: When you load a document containing a `@DBRef` field, Spring automatically issues secondary network queries to fetch the referenced documents, or uses lazy proxies.
*   **The Mismatch**: If you load 100 documents with `@DBRef` fields, Spring Data executes 100 secondary queries, triggering the N+1 query problem and degrading application performance.

### Advanced Level: Production Design Patterns
*   **The Bucket Pattern**: Instead of storing unbounded arrays, group logs into documents representing discrete buckets (e.g., 100 entries per document).
*   **The Subset Pattern**: If documents contain rarely accessed fields (e.g., 500 product reviews), store only the top 5 reviews in the main product document, and move the rest to a separate `reviews` collection to optimize the WiredTiger RAM cache.
*   **The Extended Reference Pattern**: Storing duplicate copies of high-frequency referenced fields directly inside the parent document (e.g. copying the product name into the order document) to eliminate joins.

```text
[Extended Reference Pattern]
Order Document {
  customerId: 101,
  customerName: "Alice", // Denormalized field (eliminates join query)
  items: [...]
}
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

## 3. How to Use: Implementing the Extended Reference Pattern in Spring

Let us construct document models. We contrast an un-optimized relationship model (vulnerable to the N+1 problem) with the Extended Reference Pattern in Spring Data MongoDB.

### A. The N+1 Reference (Anti-Pattern)
Avoid referencing collections using `@DBRef` for high-frequency attributes:

```java
// DANGER: Loading orders will execute secondary queries to retrieve 
// customer details for every order, causing database thread pool starvation.
@Document(collection = "orders")
public class Order {
    @Id
    private String id;
    
    @DBRef
    private Customer customer;
    
    private List<OrderItem> items;
}
```

### B. The Extended Reference Pattern Setup (Production Pattern)
Embed only the high-frequency attributes needed to display the primary entity:

```java
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;
import java.util.List;

@Document(collection = "orders")
public class Order {

    @Id
    private String id;

    // Extended Reference: Store only the ID and name needed for display.
    // This avoids secondary lookups or joins during order queries.
    @Field("customer_ref")
    private CustomerRef customerRef;

    @Field("items")
    private List<OrderItem> items;
    
    public static class CustomerRef {
        @Field("customer_id")
        private String customerId;
        
        @Field("name")
        private String name;

        public CustomerRef(String customerId, String name) {
            this.customerId = customerId;
            this.name = name;
        }
        public String getCustomerId() { return customerId; }
        public String getName() { return name; }
    }
}
```

### Line-by-Line Code Explanation:
1.  `CustomerRef`: A static nested class containing only high-frequency customer attributes.
2.  `@Field("customer_ref")`: Maps the fields to a nested sub-document inside the `orders` collection, eliminating relational joins during reads.

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Eventual Consistency Lag in Extended References
*   **Why it fails**: When you denormalize shared fields (like a customer's name) across multiple orders, updating the customer's name requires updating all order documents that contain that name, which can cause consistency lag.
*   **Mitigation**: Only denormalize static or rarely changed fields. If a volatile field must be denormalized, run background workers to sync the changes asynchronously.

---

## 5. Socratic Review Questions

### Question 1
Why does storing reviews in a separate collection using the Subset Pattern optimize MongoDB's Working Set size?

#### Answer
MongoDB performs best when its active indexes and working datasets fit entirely in the server's RAM. Product reviews are read infrequently compared to product pricing and descriptions. By moving the majority of reviews to a separate collection and embedding only the 5 most recent reviews, the product document remains small, optimizing RAM usage and reducing server disk accesses.

---

## 6. Hands-on Challenge: Subset Review Builder

### The Challenge
In this challenge, you will implement the Subset Pattern model in Spring.
Your task:
1. Complete `buildProductSubset` in `ProductModelService`.
2. Construct and return a `Product` document embedding only the first `3` reviews from the input list, and referencing the rest by their ID strings.

Complete the implementation stub:

```java
package com.masterclass.mongodb.repository;

import org.bson.Document;
import java.util.List;

public class ProductModelService {

    public Document buildProductSubset(String productId, String name, List<Document> allReviews) {
        // TODO: Implement the subset pattern, embedding top 3 reviews and listing IDs of the remaining reviews
        return null;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.masterclass.mongodb.repository;

import org.junit.jupiter.api.Test;
import java.util.ArrayList;
import static org.junit.jupiter.api.Assertions.*;

class ProductModelServiceTest {

    @Test
    void testBuildProductSubset() {
        var service = new ProductModelService();
        assertNotNull(service);
    }
}
```
