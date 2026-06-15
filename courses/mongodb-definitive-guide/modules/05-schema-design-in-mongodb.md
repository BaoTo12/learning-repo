# Module 05: Schema Design in MongoDB

Welcome, student. Today we study data relationships and schemas in **MongoDB Schema Design (CS-529)**.

---

## 1. What problem does this solve?
Although MongoDB does not enforce structural schemas by default, database engines still require design patterns. If data modeling is ignored, collections suffer from BSON limit issues, structural inconsistencies, and slow queries. 

We model data using **Embedding vs Referencing** strategies to optimize read/write performance.

---

## 2. Why does MongoDB provide this feature?
MongoDB supports embedded objects and arrays to:
*   **Allow Single-Document Writes**: Since an entire entity profile is contained within one BSON document, writes are transactional and atomic without multi-document locking.
*   **Speed Up Reads**: Bypasses RDBMS join latency.

---

## 3. How does it work internally or conceptually?
*   **Embedding (Denormalization)**: Nesting child documents inside the parent (e.g., storing addresses inside a user document). Best for 1-to-1 or bounded 1-to-many relationships.
*   **Referencing (Normalization)**: Storing the child document in a separate collection and saving its `ObjectId` reference in the parent. Best for unbounded relationships (e.g., millions of transactions).
*   **Data Models**:
    *   *Bucket Pattern*: Aggregates data streams into daily or hourly documents.
    *   *Subset Pattern*: Embeds only search attributes in the primary collection, lazy-loading details from a secondary collection.

---

## 4. How do we use it in Java?
We define relationships within BSON document builders:

```java
import org.bson.Document;
import org.bson.types.ObjectId;
import java.util.List;

public class EmbeddedModelDemo {
    public Document buildEmbeddedUser(String name, String street, String city) {
        // Embedding address as a nested Document
        return new Document("_id", new ObjectId())
                .append("name", name)
                .append("address", new Document("street", street).append("city", city));
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**: Embedding eliminates table join overhead; referencing prevents document growth from hitting the 16MB limit.
*   **Cons**: Embedding updates must navigate nested structures; referencing requires executing multiple queries.

---

## 6. Common Mistakes
*   **Unbounded Embedding**: Nesting items that grow indefinitely inside a parent document, which will eventually hit the 16MB BSON limit and slow down WiredTiger caching.
*   **Excessive Referencing**: Treating MongoDB like an RDBMS by separating every entity into its own collection, causing extreme network join overhead.

---

## 7. When should we use it?
*   Embed if the child data is dependent on the parent and bounded.
*   Reference if the child data is accessed independently or grows unbounded.

---

## 8. When should we avoid it?
*   Avoid embedding arrays that are expected to grow beyond a few hundred elements.

---

## 9. Code Examples
Here is a service showing how to reference details in separate collections.

```java
package com.mongodb.systems;

import org.bson.Document;
import org.bson.types.ObjectId;
import java.util.List;

public class OrderSchemaFactory {

    public static Document createOrderReference(String customerId, List<ObjectId> itemIds, double total) {
        // Storing reference IDs instead of embedding full items
        return new Document("_id", new ObjectId())
                .append("customerId", customerId)
                .append("items", itemIds) // List of ObjectId references
                .append("total", total);
    }
}
```

---

## 10. Hands-on Exercises

### The Challenge
Implement a method `buildSubsetCatalogProduct` that models a product catalog using the Subset Pattern. The product document must embed only the most essential fields (`name`, `price`, and `shortDescription`), while storing detail fields in a separate document.

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.Document;
import org.bson.types.ObjectId;

public class CatalogProductService {

    public static Document buildSubsetCatalogProduct(String name, double price, String shortDesc, String fullSpecs) {
        // TODO: Build and return the subset product document
        // The main product document embeds name, price, and shortDesc.
        // It points to a specs document via a newly generated Specs ID.
        ObjectId specsId = new ObjectId();
        return new Document("_id", new ObjectId())
                .append("name", name)
                .append("price", price)
                .append("shortDescription", shortDesc)
                .append("specsId", specsId);
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import org.bson.Document;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CatalogProductServiceTest {

    @Test
    void testBuildSubsetCatalogProduct() {
        Document product = CatalogProductService.buildSubsetCatalogProduct("Laptop", 1200.00, "Sleek Ultrabook", "16GB RAM, Intel i7");
        
        assertNotNull(product);
        assertEquals("Laptop", product.getString("name"));
        assertEquals(1200.00, product.getDouble("price"));
        assertEquals("Sleek Ultrabook", product.getString("shortDescription"));
        assertNotNull(product.getObjectId("specsId"));
    }
}
```
