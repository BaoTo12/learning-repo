# Module 01: Introduction to MongoDB (Chapter 1)

Welcome class. Today we analyze **Introduction to MongoDB (CS-529)**.

In Java enterprise architectures, relational databases (RDBMS) coupled with Object-Relational Mapping (ORM) tools like Hibernate/JPA have been the default choice. However, ORM engines introduce substantial performance overhead due to impedance mismatch—translating nested Java objects into flat SQL tables. Furthermore, scaling these tables horizontally across multiple database nodes requires complex clustering configurations that degrade write performance.

Today we study **Document-Oriented Database Architectures**, mapping the core design philosophies of MongoDB, contrasting scaling paradigms, and analyzing SQL-to-Java mapping bottlenecks.

---

## 1. Academic Lecture: Document Databases & Scaling Paradigms

### 1. Document-Oriented vs. Relational Models in Java
A document-oriented database replaces tabular rows with a flexible structure: the BSON document. In Java, this maps naturally to domain objects:
*   **Impedance Mismatch Mitigation**: Instead of mapping a `User` class to separate tables (e.g. `USER`, `ADDRESS`) and joining them on read, a single BSON document embeds these elements in a single record.
*   **Dynamic Schemas**: Java applications can persist polymorphic data structures without needing migrations, since MongoDB does not enforce column schemas at the storage layer.

### 2. Scaling Up vs. Scaling Out
*   **Scaling Up (Vertical)**: Upgrading server CPU, RAM, or disk speed. It is expensive and hit physical limits.
*   **Scaling Out (Horizontal)**: Native sharding. MongoDB partitions collection documents across replica set nodes, dynamically balancing the database without altering the Java application's configuration.

```text
[Tabular Normalization (SQL)]
Users Table ────(Foreign Key Join)────> Addresses Table (Impedance Mismatch)

[Document Embedding (MongoDB)]
User Document { _id, name, addresses: [{ street, city }] } (Direct mapping to Java Object)
```

---

## 2. Theory vs. Production Trade-offs

Compare operational characteristics of SQL/JPA and MongoDB Java clients:

| Dimension / Metric | JPA / Hibernate (SQL) | MongoDB Java Driver (BSON) |
| :--- | :--- | :--- |
| **Object Mapping** | High (Dirty checks, proxy joins) | Low (Direct BSON-to-Document mapping) |
| **Schema Flexibility** | Rigid (Alter-table migrations) | Dynamic (Polymorphic records permitted) |
| **Query Latency** | High (Table joins overhead) | Low (Single fetch reads) |
| **Scaling Strategy** | Scale-Up (Vertical) | Scale-Out (Horizontal sharding) |
| **Relationship Modeling**| Join tables / Foreign keys | Embedding (Nested Document) / References |

---

## 3. How to Use: Client Object Setup

Let us explore BSON document structures in Java. We contrast a naive relational mapping approach with the robust embedded document representation.

### A. The Relational Normalization (Anti-Pattern in Java)
Avoid writing separate collection calls to resolve nested relationships:

```java
// DANGER: Querying two separate collections to build a single Java entity 
// replicates RDBMS joins, causing redundant database socket round-trips.
Document user = new Document("_id", 1).append("name", "Alice");
usersCollection.insertOne(user);

Document address = new Document("userId", 1).append("street", "123 Main St");
addressesCollection.insertOne(address);
```

### B. The Embedded Document Pattern (Production Pattern)
Embed nested structures directly inside the main document using lists of sub-documents:

```java
import org.bson.Document;
import java.util.List;

// Robust Pattern: A single BSON document represents the entire Java domain model.
Document address1 = new Document("type", "home").append("street", "123 Main St");
Document address2 = new Document("type", "work").append("street", "456 Market St");

Document user = new Document("_id", 1)
        .append("name", "Alice")
        .append("addresses", List.of(address1, address2));

usersCollection.insertOne(user);
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Over-Normalization in Document DBs
*   **Why it fails**: When migrating from SQL, Java developers often store only the `id` of related entities, querying them manually. In MongoDB, this triggers the "N+1 query problem" inside client application loops, overloading the database connection pool.
*   **Mitigation**: Embed components that are read together. Only reference independent collections (e.g. log streams or giant lists of reviews).

---

## 5. Socratic Review Questions

### Question 1
Why does mapping relationships as embedded documents in MongoDB improve write performance compared to traditional database table transactions?

#### Answer
In relational databases, writing a single entity with nested elements (e.g., an Order with Items) requires executing multiple SQL insert statements across different tables. This forces the database to write to different sections of the disk, update multiple indexes, and lock multiple tables. MongoDB writes the entire embedded document in a single write operation, modifying only one database block and one index.

---

## 6. Hands-on Challenge: Java BSON Schema Migration

### The Challenge
In this challenge, you will implement a schema migration function in Java.
Your task:
1. Complete the method `createEmbeddedOrder` in `OrderMigration`.
2. Map a flat order structure and a list of order items into a single, nested `org.bson.Document`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.Document;
import java.util.List;

public class OrderMigration {

    public Document createEmbeddedOrder(String orderId, String status, List<Document> items) {
        // TODO: Construct and return the nested order document containing orderId, status, and items list
        return null;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import org.bson.Document;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class OrderMigrationTest {

    @Test
    void testCreateEmbeddedOrder() {
        OrderMigration migration = new OrderMigration();
        Document item1 = new Document("productId", "P1").append("qty", 2);
        Document item2 = new Document("productId", "P2").append("qty", 1);

        Document order = migration.createEmbeddedOrder("ORD-100", "SHIPPED", List.of(item1, item2));

        assertNotNull(order);
        assertEquals("ORD-100", order.getString("orderId"));
        assertEquals("SHIPPED", order.getString("status"));
        
        List<Document> embeddedItems = order.getList("items", Document.class);
        assertNotNull(embeddedItems);
        assertEquals(2, embeddedItems.size());
        assertEquals("P1", embeddedItems.get(0).getString("productId"));
    }
}
```
