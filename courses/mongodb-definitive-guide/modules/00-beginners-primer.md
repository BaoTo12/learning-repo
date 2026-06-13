# Module 00: Beginner's Primer to NoSQL & Java-MongoDB

Welcome class. Today we introduce the foundation of **NoSQL and Document Databases (CS-529)**.

If you are coming from a relational database background (such as MySQL, PostgreSQL, or Oracle), storing data as documents rather than flat tables requires a shift in how you model relationships and write queries. Today we establish the basic concepts, compare SQL structures to MongoDB collections, and write our first Java program to interact with MongoDB.

---

## 1. Academic Lecture: Relational vs. Document Models

### 1. SQL to NoSQL Mapping
In a relational database, data is normalized across tables and linked together using foreign keys. In MongoDB, data is stored as BSON (Binary JSON) documents. Here is how the terminology maps:

| Relational (SQL) | Document-Oriented (MongoDB) | Description |
| :--- | :--- | :--- |
| **Database** | **Database** | A container for collections. |
| **Table** | **Collection** | A grouping of documents (analogous to a table). |
| **Row** | **Document** | A single record stored in BSON format. |
| **Column** | **Field** | A key-value pair inside a document. |
| **Table Join** | **Embedding / Reference**| Combining data from different sources. |
| **Primary Key** | **Primary Key (`_id`)** | A unique identifier automatically or manually set. |

### 2. What is JSON and BSON?
*   **JSON (JavaScript Object Notation)**: A human-readable text format for representing structured data as key-value pairs.
*   **BSON (Binary JSON)**: A binary serialization format used by MongoDB to store documents on disk and transfer them over the network. BSON extends JSON by adding support for additional data types (such as `Date`, `Decimal128`, and raw binary data) and allows faster parsing.

---

## 2. Theory vs. Production Trade-offs

Compare embedding data vs. referencing data:

| Dimension / Metric | Embedded Schema (Nested Documents) | Referenced Schema (Normalized DBRef) |
| :--- | :--- | :--- |
| **Read Latency** | Excellent (Fetch all related data in one read) | Moderate (Requires secondary query lookups) |
| **Consistency** | High (Atomic updates inside a single document) | Eventual (Requires multi-document updates) |
| **Data Redundancy** | High (Duplicate values across documents) | Low (Data is normalized in one location) |
| **Document Size Limit** | Subject to the 16MB document limit | Bypasses the 16MB limit |

---

## 3. How to Use: Dynamic BSON CRUD Walkthrough in Java

Let us construct our first Java application to manage documents. Below is a fully commented, runnable example demonstrating connection bootstrapping, inserting a document, querying, updating, and deleting records.

```java
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoDatabase;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import org.bson.Document;

import java.util.List;

public class BasicCrudWalkthrough {

    public static void main(String[] args) {
        // 1. Establish connection to the local sandbox database
        // (Assumes a local MongoDB instance is running on port 27017)
        try (MongoClient client = MongoClients.create("mongodb://localhost:27017")) {
            
            // 2. Access a database
            MongoDatabase database = client.getDatabase("academic_sandbox");
            
            // 3. Access a collection
            MongoCollection<Document> users = database.getCollection("students");
            
            // Clear any existing documents for clean demonstration
            users.drop();

            // 4. CREATE: Insert a new student document
            Document newStudent = new Document("_id", "STD-101")
                    .append("fullName", "Jane Doe")
                    .append("enrolled", true)
                    .append("courses", List.of("CS-529", "CS-509"));
            
            users.insertOne(newStudent);
            System.out.println("Document inserted successfully.");

            // 5. READ: Query the student document using Filters
            Document queryResult = users.find(Filters.eq("_id", "STD-101")).first();
            if (queryResult != null) {
                System.out.println("Retrieved Student: " + queryResult.toJson());
            }

            // 6. UPDATE: Add a new course to the courses array using Updates
            users.updateOne(
                    Filters.eq("_id", "STD-101"),
                    Updates.push("courses", "CS-512")
            );
            System.out.println("Document updated successfully.");

            // 7. DELETE: Remove the student document
            users.deleteOne(Filters.eq("_id", "STD-101"));
            System.out.println("Document deleted successfully.");
        }
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Leaking Connection Sockets
*   **Why it fails**: Creating a new `MongoClient` instance for every database query. The `MongoClient` object maintains an internal pool of connection sockets to the database. Re-initializing it repeatedly exhausts system file descriptors and degrades query performance.
*   **Mitigation**: Initialize a single `MongoClient` instance at application startup, share it across your services, and close it when the application shuts down.

---

## 5. Socratic Review Questions

### Question 1
Why is storing data in flat tables with relations (SQL) less scalable horizontally compared to document-oriented storage (MongoDB)?

#### Answer
SQL databases rely on strict constraints and normalized joins to link tables. Splitting these tables across different servers (horizontal sharding) makes performing joins slow and expensive because the database must coordinate data across multiple network connections. MongoDB's document model encourages storing related data together inside a single document (embedding), allowing documents to be distributed across servers and queried independently without needing cross-server joins.

---

## 6. Hands-on Challenge: Java Document Mapper Utility

### The Challenge
In this challenge, you will implement a basic document mapper utility.
Your task:
1. Complete `mapStudentDocument` in `StudentMapper`.
2. Construct and return an `org.bson.Document` containing:
   - `_id` set to the provided `studentId`.
   - `name` set to `studentName`.
   - `gpa` set to `gpa` (double).
   - `status` set to `"ACTIVE"` if the `gpa` is greater than or equal to 2.0; otherwise, set it to `"PROBATION"`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.Document;

public class StudentMapper {

    public Document mapStudentDocument(String studentId, String studentName, double gpa) {
        // TODO: Build and return the document according to the rules above.
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
import static org.junit.jupiter.api.Assertions.*;

class StudentMapperTest {

    @Test
    void testActiveStudentMapping() {
        StudentMapper mapper = new StudentMapper();
        Document activeStudent = mapper.mapStudentDocument("S1", "Alice", 3.8);

        assertNotNull(activeStudent);
        assertEquals("S1", activeStudent.getString("_id"));
        assertEquals("Alice", activeStudent.getString("name"));
        assertEquals(3.8, activeStudent.getDouble("gpa"));
        assertEquals("ACTIVE", activeStudent.getString("status"));
    }

    @Test
    void testProbationStudentMapping() {
        StudentMapper mapper = new StudentMapper();
        Document probationStudent = mapper.mapStudentDocument("S2", "Bob", 1.5);

        assertNotNull(probationStudent);
        assertEquals("S2", probationStudent.getString("_id"));
        assertEquals("Bob", probationStudent.getString("name"));
        assertEquals(1.5, probationStudent.getDouble("gpa"));
        assertEquals("PROBATION", probationStudent.getString("status"));
    }
}
```
