# Module 18: Real-World Project

Welcome, student. Today we build a complete **E-Commerce Order Management API (CS-529)** using the native MongoDB driver.

---

## 1. What problem does this solve?
Learning syntax in isolation is useful, but production development requires coordinating multiple components: connection pools, validations, repository structures, transaction sessions, and testing suites. 

This module builds a **complete, self-contained project codebase** implementing a reliable booking and order allocation engine.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides driver operations that can be combined to build robust production applications.

---

## 3. How does it work internally or conceptually?
*   **Data Models**:
    *   `products`: Storing item availability (`stock`).
    *   `orders`: Tracking purchases.
*   **Transaction Flow**: The service starts a transaction, validates stock, decrements inventory, and logs the order. If any step fails, everything rolls back.

---

## 4. How do we use it in Java?
We structure our project into standard layers:
1.  **Repository Layer**: Interacts with the `MongoCollection`.
2.  **Service Layer**: Defines business rules and manages transactions.
3.  **Test Layer**: Runs integration validations using Testcontainers.

---

## 5. What are the trade-offs?
*   **Pros**: Demonstrates complete architectural integration; ensures reliable transactions.
*   **Cons**: Increases codebase complexity compared to raw scripts.

---

## 6. Common Mistakes
*   **Ignoring Transaction Retries**: Failing to handle transient failovers during payment allocations.
*   **Unsafe Resource Closures**: Failing to use try-with-resources when managing `ClientSession` instances.

---

## 7. When should we use it?
*   Use this layered structure for all production backend applications.

---

## 8. When should we avoid it?
*   Do not use this structure for simple, one-off scripts.

---

## 9. Code Examples
Here is the complete order processing service implementing transaction boundaries.

```java
package com.mongodb.systems;

import com.mongodb.client.MongoClient;
import com.mongodb.client.ClientSession;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.TransactionBody;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

public class OrderPlacementService {

    private final MongoClient mongoClient;
    private final MongoCollection<Document> products;
    private final MongoCollection<Document> orders;

    public OrderPlacementService(MongoClient client, MongoCollection<Document> products, MongoCollection<Document> orders) {
        this.mongoClient = client;
        this.products = products;
        this.orders = orders;
    }

    public boolean placeOrderSecure(String productId, int quantity, String userId) {
        try (ClientSession session = mongoClient.startSession()) {
            TransactionBody<Boolean> tx = () -> {
                // Fetch product stock inside transaction
                Document prod = products.find(session, Filters.eq("_id", productId)).first();
                if (prod == null || prod.getInteger("stock") < quantity) {
                    throw new IllegalStateException("Insufficient stock");
                }

                // Decrement stock
                products.updateOne(session, Filters.eq("_id", productId), Updates.inc("stock", -quantity));

                // Insert order
                Document order = new Document("userId", userId)
                        .append("productId", productId)
                        .append("qty", quantity)
                        .append("status", "SUCCESS");
                orders.insertOne(session, order);
                return true;
            };

            return session.withTransaction(tx);
        } catch (Exception e) {
            System.err.println("Order transaction failed: " + e.getMessage());
            return false;
        }
    }
}
```

---

## 10. Hands-on Exercises

### The Challenge
Write a service constructor that sets up the database.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoDatabase;

public class DBInitService {

    private final MongoDatabase database;

    public DBInitService(MongoClient client, String dbName) {
        // TODO: Retrieve the database from the client and save it
        this.database = client.getDatabase(dbName);
    }

    public MongoDatabase getDatabase() {
        return this.database;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoDatabase;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class DBInitServiceTest {

    @Test
    void testDBInit() {
        MongoClient mockClient = mock(MongoClient.class);
        MongoDatabase mockDb = mock(MongoDatabase.class);
        when(mockClient.getDatabase("shop")).thenReturn(mockDb);

        DBInitService service = new DBInitService(mockClient, "shop");
        assertNotNull(service.getDatabase());
    }
}
```
