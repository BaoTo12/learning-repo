# Module 08: Data Validation

Welcome, student. Today we study database-level schema constraints and validation features in **MongoDB Data Validation (CS-529)** using the official MongoDB Java Sync Driver.

---

## 1. What problem does this solve?
MongoDB's default schema-less nature allows documents in a collection to contain any shape, keys, or types of data. While this flexibility is ideal for rapid development and polymorphic entities, it poses a risk in multi-service production backends. 

If a service writes an invalid document (e.g. missing `userId`, negative `price`, or a string where a number is expected), other JVM services reading this document can fail with serialization errors or runtime crashes.

We solve this by setting **JSON Schema Validation rules** directly on the database collections. Invalid document writes are rejected at the server level, preventing corrupt data from ever entering WiredTiger storage.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides database-level JSON Schema validation to:
*   **Enforce Invariants at the Storage Layer**: Guarantee that all documents in a collection adhere to structural invariants, regardless of which client or language driver inserts them.
*   **Prevent Serialization Failures**: Protect reading client applications from encountering unexpected shapes or types.
*   **Avoid Client-Side Redundancy**: Define validation rules once in the database configuration, eliminating the need to duplicate complex validation logic across multiple microservices.

---

## 3. How does it work internally or conceptually?
*   **The WiredTiger Hook**: When a client sends a write request (insert or update), MongoDB processes it inside the WiredTiger engine memory buffer. Before writing to the journal or committing pages to disk, the engine passes the document through the validation evaluator. If the document violates the validation criteria, the write is aborted, rolled back, and an error is returned to the client.
*   **Validation Actions**:
    *   `error` (Default): MongoDB rejects the write immediately and returns a write error (code 121).
    *   `warn`: MongoDB accepts the write, but writes a warning to the database server log (`mongod.log`) detailing the validation violation. Useful for debugging new rules.
*   **Validation Levels**:
    *   `strict` (Default): Enforces validation rules on all inserts and all updates.
    *   `moderate`: Enforces rules on inserts, and only validates updates on documents that *already* matched the validation criteria prior to the update. This allows updating legacy documents that do not meet the new schema without forcing a full database rewrite.

---

## 4. How do we use it in Java?
We define validation rules using BSON `Document` structures representing a `$jsonSchema` document. We pass this document to a collection using `CreateCollectionOptions` or update it dynamically on an existing collection via the `collMod` admin command.

```java
import com.mongodb.client.MongoDatabase;
import com.mongodb.client.model.CreateCollectionOptions;
import com.mongodb.client.model.ValidationOptions;
import org.bson.Document;
import java.util.List;

public class BasicValidationDemo {
    public void configureValidation(MongoDatabase database) {
        // Build JSON Schema document
        Document jsonSchema = new Document("bsonType", "object")
            .append("required", List.of("sku", "price"))
            .append("properties", new Document()
                .append("sku", new Document("bsonType", "string"))
                .append("price", new Document("bsonType", "double").append("minimum", 0.0))
            );

        // Map BSON JSON Schema to ValidationOptions
        ValidationOptions validationOptions = new ValidationOptions()
            .validator(new Document("$jsonSchema", jsonSchema))
            .validationAction(com.mongodb.client.model.ValidationAction.ERROR);

        CreateCollectionOptions options = new CreateCollectionOptions().validationOptions(validationOptions);
        database.createCollection("products", options);
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**:
    *   **Data Integrity Guarantee**: Rejects corrupt data at the database gate.
    *   **Unified Constraints**: Rules apply to all clients (Java, Node.js, Python, or shell).
    *   **Migration Safeties**: Moderate validation allows gradual schema migrations.
*   **Cons**:
    *   **Server CPU Cost**: Validating complex schemas with regex pattern matches increases CPU usage on high-velocity writes.
    *   **Schema Rigidity**: Adding required fields blocks old client applications from executing writes until their codebase is updated.
    *   **Complex Modification Operations**: Schema rules must be modified via admin commands rather than simple DDL scripts.

---

## 6. Common Mistakes
*   **Type Mismatches between Java and BSON**: BSON distinguishes between float numbers (`double`) and integers (`int`/`long`). Declaring `bsonType: "double"` and passing a raw Java `int` (like `10`) will fail validation because `10` is parsed as an integer type in BSON.
*   **Strict Validation on Legacy Collections**: Enforcing `strict` validation level on a collection containing invalid legacy data. This blocks services from updating *any* fields in old documents unless they also update all other invalid fields. **Always use moderate validation during migration periods.**
*   **Over-relying on Database Validation**: Using database validation to verify temporary user input state. This leads to user validation failures leaking as raw database exceptions, which are slower to parse than application-level rules.

---

## 7. When should we use it?
*   Use to enforce mandatory primary keys (`required`), enum states, number boundaries, and email/UUID string formats.
*   Use database validation as a second line of defense behind application validation (JSR-380).

---

## 8. When should we avoid it?
*   Avoid for high-throughput logging, telemetry, or unstructured scraping collections where schema layouts vary wildly and write throughput is the primary concern.
*   Avoid validation rules that depend on calculations or queries across multiple documents. MongoDB validation only evaluates fields inside the current document.

---

## 9. Code Examples

### A. APPLICATION VS. DATABASE VALIDATION

| Feature | Application Validation (JSR-380 / Spring) | Database Validation ($jsonSchema) |
| :--- | :--- | :--- |
| **Location** | Executes in JVM memory before sending query | Executes in WiredTiger engine on database server |
| **Scope** | Validates API inputs, handles user error messages | Validates storage state, protects database integrity |
| **Scope of Clients**| Only applies to Java applications using that codebase | Applies to all clients (Python scripts, shell, other apps) |
| **Speed** | Extremely fast (microsecond JVM operations) | Incurs a minor database CPU overhead on write |

---

### B. THE `$jsonSchema` CONSTRAINTS

Here is a comprehensive Java class constructing a complete validation schema covering required fields, type checks, enums, numeric bounds, pattern matches, arrays, and nested structures.

```java
import com.mongodb.client.MongoDatabase;
import com.mongodb.client.model.CreateCollectionOptions;
import com.mongodb.client.model.ValidationOptions;
import org.bson.Document;
import java.util.List;

public class ComplexSchemaValidation {
    public void setupValidatedCollection(MongoDatabase database) {
        Document properties = new Document()
            // 1. String with Pattern Validation (Email Regex)
            .append("email", new Document("bsonType", "string")
                .append("pattern", "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\\.[a-zA-Z]{2,}$")
            )
            // 2. Enum Constraint (Fixed set of valid strings)
            .append("role", new Document("bsonType", "string")
                .append("enum", List.of("STUDENT", "INSTRUCTOR", "ADMIN"))
            )
            // 3. Numeric Boundaries (GPA must be between 0.0 and 4.0)
            .append("gpa", new Document("bsonType", "double")
                .append("minimum", 0.0)
                .append("maximum", 4.0)
            )
            // 4. Nested Object Validation
            .append("profile", new Document("bsonType", "object")
                .append("required", List.of("firstName", "lastName"))
                .append("properties", new Document()
                    .append("firstName", new Document("bsonType", "string"))
                    .append("lastName", new Document("bsonType", "string"))
                )
            )
            // 5. Array Validation (List of unique strings)
            .append("skills", new Document("bsonType", "array")
                .append("uniqueItems", true)
                .append("items", new Document("bsonType", "string"))
            );

        Document schema = new Document("bsonType", "object")
            .append("required", List.of("email", "role", "gpa"))
            .append("properties", properties);

        ValidationOptions vOpts = new ValidationOptions()
            .validator(new Document("$jsonSchema", schema))
            .validationAction(com.mongodb.client.model.ValidationAction.ERROR)
            .validationLevel(com.mongodb.client.model.ValidationLevel.STRICT);

        database.createCollection("students", new CreateCollectionOptions().validationOptions(vOpts));
    }
}
```

---

### C. UPDATING SCHEMAS VIA `collMod`
To modify the validation rules of an existing collection, you must issue the `collMod` command directly to the database.

```java
import com.mongodb.client.MongoDatabase;
import org.bson.Document;

public class SchemaModificationService {
    public void addRequiredField(MongoDatabase database, String collectionName, Document newJsonSchema) {
        // Construct the collMod administration command document
        Document collModCmd = new Document("collMod", collectionName)
            .append("validator", new Document("$jsonSchema", newJsonSchema))
            .append("validationLevel", "strict")
            .append("validationAction", "error");

        // Execute the command against the admin database context
        Document result = database.runCommand(collModCmd);
        System.out.println("collMod execution result: " + result.toJson());
    }
}
```

---

### D. JAVA EXCEPTION HANDLING
When a write violates schema rules, MongoDB throws a `MongoWriteException`. The error document is caught, and we parse code `121` (DocumentValidationFailure).

```java
import com.mongodb.MongoWriteException;
import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class ValidationErrorHandler {
    public boolean insertDocument(MongoCollection<Document> collection, Document document) {
        try {
            collection.insertOne(document);
            return true;
        } catch (MongoWriteException e) {
            if (e.getError().getCode() == 121) {
                System.err.println("Database Validation Failed: Document violates schema constraints.");
                System.err.println("Violating details: " + e.getMessage());
                return false;
            }
            throw e; // Re-throw other database write exceptions
        }
    }
}
```

---

## 10. Hands-on Exercises

### Challenge 1: Student Validator Document
Implement a factory class that constructs a `$jsonSchema` document for student records.
*   Required fields: `"name"`, `"email"`, `"status"`.
*   `status` must be restricted via an enum to either `"ACTIVE"`, `"PENDING"`, or `"GRADUATED"`.
*   Include a nested `"address"` object containing a required `"zip"` field (string).

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.Document;
import java.util.List;

public class StudentValidatorFactory {

    public static Document buildSchema() {
        // TODO: Build and return the BSON document representing the $jsonSchema constraint.
        Document properties = new Document()
            .append("name", new Document("bsonType", "string"))
            .append("email", new Document("bsonType", "string"))
            .append("status", new Document("bsonType", "string")
                .append("enum", List.of("ACTIVE", "PENDING", "GRADUATED"))
            )
            .append("address", new Document("bsonType", "object")
                .append("required", List.of("zip"))
                .append("properties", new Document()
                    .append("zip", new Document("bsonType", "string"))
                )
            );

        Document schema = new Document("bsonType", "object")
            .append("required", List.of("name", "email", "status"))
            .append("properties", properties);

        return new Document("$jsonSchema", schema);
    }
}
```

### Challenge 2: Dynamic Schema Modification in Java
Implement a service method that updates an existing collection's validation rules using the `collMod` command. You must retrieve the input database reference, set a new validator, and set `validationLevel` to `"moderate"`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoDatabase;
import org.bson.Document;

public class SchemaUpdaterService {

    public void updateToModerateSchema(MongoDatabase database, String collectionName, Document newJsonSchema) {
        // TODO: Build and execute collMod command with moderate validationLevel.
        Document command = new Document("collMod", collectionName)
            .append("validator", new Document("$jsonSchema", newJsonSchema))
            .append("validationLevel", "moderate")
            .append("validationAction", "error");

        database.runCommand(command);
    }
}
```

### Challenge 3: Validation Error Code Interceptor
Implement a repository wrapper method. Attempt to insert a document. If a `MongoWriteException` is thrown, catch it. Return `false` only if the error code matches `121` (validation error). If any other error occurs or a different exception is thrown, rethrow the exception.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.MongoWriteException;
import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class SafeInsertRepository {

    public boolean executeSafeInsert(MongoCollection<Document> collection, Document doc) {
        // TODO: Insert doc, intercept validation errors, rethrow others.
        try {
            collection.insertOne(doc);
            return true;
        } catch (MongoWriteException e) {
            if (e.getError().getCode() == 121) {
                return false;
            }
            throw e;
        }
    }
}
```

### Verification Tests
Verify all three validation challenges using this JUnit 5 verification test suite:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoDatabase;
import com.mongodb.client.MongoCollection;
import com.mongodb.MongoWriteException;
import com.mongodb.MongoWriteConcernException;
import com.mongodb.WriteError;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class ValidationExercisesTest {

    @Test
    void testStudentSchemaValidator() {
        Document validator = StudentValidatorFactory.buildSchema();
        assertNotNull(validator);
        
        Document schema = (Document) validator.get("$jsonSchema");
        assertNotNull(schema);
        
        java.util.List<String> required = (java.util.List<String>) schema.get("required");
        assertTrue(required.contains("name"));
        assertTrue(required.contains("email"));
        assertTrue(required.contains("status"));
    }

    @Test
    void testUpdateToModerateSchema() {
        MongoDatabase mockDb = mock(MongoDatabase.class);
        SchemaUpdaterService service = new SchemaUpdaterService();

        service.updateToModerateSchema(mockDb, "students", new Document("name", "string"));

        verify(mockDb, times(1)).runCommand(any(Document.class));
    }

    @SuppressWarnings("unchecked")
    @Test
    void testSafeInsertValidationFailure() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        WriteError mockError = new WriteError(121, "Validation failed", new Document());
        MongoWriteException exception = new MongoWriteException(mockError, null);
        
        doThrow(exception).when(mockCol).insertOne(any(Document.class));

        SafeInsertRepository repo = new SafeInsertRepository();
        boolean result = repo.executeSafeInsert(mockCol, new Document());

        assertFalse(result);
    }

    @SuppressWarnings("unchecked")
    @Test
    void testSafeInsertOtherFailure() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        WriteError mockError = new WriteError(11000, "Duplicate Key", new Document());
        MongoWriteException exception = new MongoWriteException(mockError, null);
        
        doThrow(exception).when(mockCol).insertOne(any(Document.class));

        SafeInsertRepository repo = new SafeInsertRepository();
        assertThrows(MongoWriteException.class, () -> repo.executeSafeInsert(mockCol, new Document()));
    }
}
```
