# Module 01: MongoDB Fundamentals

Welcome, student. Today we analyze the foundational concepts of **MongoDB (CS-529)** from the perspective of a senior systems engineer.

---

## 1. What problem does this solve?
Relational databases (RDBMS) enforce a strict, flat schema. When representing rich, hierarchical application domains (like a user profile with multiple email addresses, active login histories, and security settings) in SQL, we must normalize the data. This breaks the object into separate rows across multiple tables (`users`, `user_emails`, `user_logins`), requiring complex, high-latency multi-table joins to retrieve a single profile. This is known as the **object-relational impedance mismatch**. 

MongoDB solves this by storing data as self-contained **BSON documents**, allowing rich, nested data structures to be saved and retrieved in a single, fast disk operation.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides the document model to:
*   **Align with Code**: JSON and BSON structures align naturally with Object-Oriented programming objects (like Java classes with maps and lists).
*   **Scale Horizontally**: By keeping related data nested inside a single document, MongoDB can partition (shard) collections across machines easily. Since joins are rarely needed, database queries can run isolated on individual cluster nodes.

---

## 3. How does it work internally or conceptually?

### Concept Mapping
*   **Database**: A container for physical collections on disk.
*   **Collection**: A group of BSON documents (equivalent to an RDBMS Table, but without rigid schema enforcement).
*   **Document**: A set of key-value pairs represented in BSON (equivalent to an RDBMS Row).

### BSON vs JSON
JSON (JavaScript Object Notation) is a human-readable text format. Text parsing is CPU-intensive and lacks support for advanced types (like date formats or binary records).
BSON (Binary JSON) is a binary serialization format used to store documents. 
*   *Why BSON?* It includes length prefixes for strings and arrays, allowing the query engine to skip sub-documents without parsing them.
*   *Extended Types*: BSON natively supports `Date` objects, `Double`, `Int32`, `Int64`, `Binary Data`, and `ObjectId`.

### ObjectId Internals
Every MongoDB document requires an `_id` primary key. By default, MongoDB assigns an `ObjectId`, which is a 12-byte binary value structured as:
1.  **4-byte timestamp**: Unix epoch seconds, providing natural chronological sorting.
2.  **5-byte random value**: Unique to the host machine and process.
3.  **3-byte incrementing counter**: Initialized to a random value.

```text
 12-Byte ObjectId Structure:
┌─────────────────────────┬─────────────────────────┬──────────────┐
│  Timestamp (4 Bytes)    │  Random Val (5 Bytes)   │ Counter (3B) │
├─────────────────────────┼─────────────────────────┼──────────────┤
│ 0x64 0x7F 0x1A 0x2B     │ 0xA1 0xB2 0xC3 0xD4 0xE5│ 0x00 0x01 0x02│
└─────────────────────────┴─────────────────────────┴──────────────┘
```

---

## 4. How do we use it in Java?
The official MongoDB Java driver represents BSON documents using the `org.bson.Document` class, which implements `Map<String, Object>`:

```java
import org.bson.Document;
import org.bson.types.ObjectId;
import java.util.List;
import java.util.Date;

public class FundamentalsDemo {
    public static void run() {
        // Constructing a nested document in Java
        Document user = new Document("_id", new ObjectId())
                .append("username", "developer_x")
                .append("createdAt", new Date())
                .append("roles", List.of("DEVELOPER", "ADMIN"))
                .append("profile", new Document("firstName", "Alice").append("lastName", "Smith"));

        // Extracting nested values
        String username = user.getString("username");
        Document profile = (Document) user.get("profile");
        String firstName = profile.getString("firstName");
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**: Dynamic schema allows rapid schema updates; no join latency; reads/writes are extremely fast.
*   **Cons**: Data duplication (denormalization) wastes disk space; database cannot enforce foreign keys (referential integrity must be managed in Java code); documents are capped at **16MB** size limit.

---

## 6. What are common mistakes?
*   **Polymorphic Field Clashes**: Saving different types under the same field name across documents (e.g., `age: "25"` as String in one document and `age: 25` as Int32 in another). This breaks query sorting and numeric index logic.
*   **Unbounded Arrays**: Appending values to a document's array indefinitely (e.g., storing millions of log events inside a user document). This pushes the document past the 16MB limit, degrading WiredTiger performance.

---

## 7. When should we use it?
*   Highly polymorphic data catalogs (e.g. e-commerce products with different attributes).
*   Real-time analytics and event tracking feeds.
*   Content management, customer profiles, and hierarchical configurations.

---

## 8. When should we avoid it?
*   System architectures requiring highly normalized tables with continuous multi-row updates.
*   Systems that require strict relational foreign-key referential integrity checks at the database engine level.

---

## 9. Code Examples
Here is a complete Java class modeling a nested blog post using BSON `Document`.

```java
package com.mongodb.systems;

import org.bson.Document;
import org.bson.types.ObjectId;
import java.util.Date;
import java.util.List;

public class BlogPostFactory {

    public static Document createPost(String title, String content, String author, List<String> tags) {
        return new Document("_id", new ObjectId())
                .append("title", title)
                .append("content", content)
                .append("author", author)
                .append("tags", tags)
                .append("likes", 0)
                .append("comments", List.of()) // Empty comments array
                .append("createdAt", new Date());
    }
}
```

---

## 10. Hands-on Exercises

### The Challenge
Implement a method `buildAccountDocument` that builds a bank account document containing:
1. `_id` (ObjectId).
2. `accountNumber` (String).
3. `owner` (nested Document with `firstName` and `lastName`).
4. `tags` (List of strings).
5. `balance` (Double).

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.Document;
import org.bson.types.ObjectId;
import java.util.List;

public class AccountFactory {

    public static Document buildAccountDocument(String accNumber, String firstName, String lastName, List<String> tags, double balance) {
        // TODO: Construct and return the nested document
        return new Document("_id", new ObjectId())
                .append("accountNumber", accNumber)
                .append("owner", new Document("firstName", firstName).append("lastName", lastName))
                .append("tags", tags)
                .append("balance", balance);
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

class AccountFactoryTest {

    @Test
    void testAccountDocumentBuilding() {
        Document doc = AccountFactory.buildAccountDocument("ACC123", "John", "Doe", List.of("checking"), 1500.50);
        
        assertNotNull(doc);
        assertNotNull(doc.getObjectId("_id"));
        assertEquals("ACC123", doc.getString("accountNumber"));
        assertEquals(1500.50, doc.getDouble("balance"));
        
        Document owner = (Document) doc.get("owner");
        assertNotNull(owner);
        assertEquals("John", owner.getString("firstName"));
        assertEquals("Doe", owner.getString("lastName"));
    }
}
```
