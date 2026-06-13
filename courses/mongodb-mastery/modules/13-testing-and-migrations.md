# Module 13: Testing & Migrations Lab

## 1. What Problem This Module Solves
Deploying code updates without testing index behaviors, transaction safety, and schema changes is a recipe for production failures. Mocking database drivers or using lightweight in-memory databases (like Fongo or embedded H2/Mongo) fails to validate how queries behave under real database constraints.

This module addresses testing and migrations. A senior engineer must understand why mock databases are insufficient, how to use Testcontainers for integration testing, and how to design zero-downtime database migrations. Failing to use real databases during testing leads to queries that fail on syntax errors in production, missing unique constraints, and transaction rollbacks that behave unexpectedly.

---

## 2. Why This Topic Matters
Testing databases requires using the actual database engine. Mock databases do not enforce constraints (like unique indexes), do not support replication transactions, and do not validate aggregation optimizer pipelines.

Furthermore, updating document structures (like renaming fields or changing data types) in a high-volume collection cannot be done using offline migrations. Doing so would lock tables and cause downtime. This module provides the technical details required to test applications using Testcontainers and execute zero-downtime schema migrations.

---

## 3. Core Concepts & Internals

### 3.1 Testing Methodologies: Mocks vs. Testcontainers
Testing database integrations requires choosing the right environment:

| Testing Pattern | Durability & Fidelity | Test Execution Speed | Transaction Support | Cost & Infrastructure | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Driver Mocks** | **Low**: Does not run a database; queries are simulated in memory. | **Ultra-Fast**: Millisecond execution. | **None** | **None** | Simple unit tests, mock controller routing. |
| **Embedded Mongo (Fongo/H2)** | **Medium**: Runs an in-memory database simulation, but does not use WiredTiger. | **Fast**: Runs locally in JVM memory. | **Incomplete**: Does not support replication or transaction states. | **None** | Basic repository test validation. |
| **Testcontainers** | **Maximum**: Spawns a real MongoDB Docker container matching production versions. | **Medium**: Requires container startup overhead (approx. 5-10s). | **Full**: Supports transactions, replica sets, and indexes. | **Medium**: Requires Docker installed on host. | Integration tests, transaction testing. |

#### Why Embedded MongoDB is Dangerous:
*   Embedded databases do not enforce collation, index ordering (like ESR constraints), or transaction rollbacks under write conflicts. A query that succeeds in an embedded test can fail in production due to invalid BSON formatting or syntax errors.

---

### 3.2 Zero-Downtime Schema Migrations
Updating collection schemas in a database containing millions of documents requires a multi-phase migration strategy:

```
  [Phase 1: Read/Write V1] ──> Old schema active.
          │
          ▼
  [Phase 2: Double-Writing] ──> Write V1 & V2, Read V1.
          │
          ▼
  [Phase 3: Online Backfill] ──> Run background migration runner.
          │
          ▼
  [Phase 4: Read/Write V2] ──> Write V1 & V2, Read V2.
          │
          ▼
  [Phase 5: Cleanup V1] ──> Drop old schema code and fields.
```

#### Migration Phases:
1.  **Phase 1: Read/Write V1**: The application code reads and writes using the old schema structure (V1).
2.  **Phase 2: Double-Writing**: The application code is updated to write data in both V1 and V2 formats (duplicating fields or formats on insert/update). The application continues to read from V1.
3.  **Phase 3: Online Backfill**: A background migration runner script reads old documents, converts them to V2, and saves them back to the database in batches, using transactional retry checks to prevent overwriting active writes.
4.  **Phase 4: Read/Write V2**: Once all documents are migrated, the application reads and writes using the V2 structure.
5.  **Phase 5: Cleanup**: Drop V1 code dependencies and remove old V1 fields from collections using background clean tasks.

---

### 3.3 Lazy Read-Repair Migration
An alternative to running bulk backfill scripts is the **Lazy Read-Repair** pattern. Instead of migrating all documents at once, the schema is upgraded dynamically as documents are accessed by the application.

```
 [Application Read] ──> Fetch Document
                            │
                            ▼
                  [Check schemaVersion]
                            ├──────────────────────────┐
                            ▼ (Matches V2)             ▼ (Matches V1)
                     [Return Document]          [Convert to V2 in Memory]
                                                       │
                                                       ▼
                                                [Write V2 back to DB]
                                                       │
                                                       ▼
                                                [Return upgraded doc]
```

#### Read-Repair Flow:
1.  **Read Query**: The application reads a document from the collection.
2.  **Version Check**: The code checks the `schemaVersion` field. If the version matches the latest schema structure (V2), it returns the document immediately.
3.  **Dynamic Mapping**: If the version matches the old schema (V1), the application mapping layer converts the document fields into the V2 format in memory.
4.  **Write Back (Repair)**: The application writes the upgraded document back to the database asynchronously or inline, saving it with the updated `schemaVersion` so subsequent reads do not trigger the conversion.

---

### 3.4 Production Migration Planning Checklist
Before running any schema migrations in production, the DBA and engineering teams must complete the following checks:
1.  **Disk Space Verification**: Ensure the database disk has at least **2x the collection size** available to accommodate document growth and index rebuild operations.
2.  **Oplog Window Check**: Verify that the replica set oplog window is large enough to handle the write spike generated by background migration scripts without wrapping around and breaking secondary replication.
3.  **Lock State Monitoring**: Configure migration runners to run in small batches (e.g. 500-1,000 documents) and add brief sleep intervals between batches to prevent database thread queuing.
4.  **Rollback Plan**: Write and test a rollback script to convert V2 structures back to V1 in case the application release needs to be reverted.

---

## 4. Practical Examples

### JUnit 5 Integration Test with Testcontainers (Java)
The following JUnit 5 class demonstrates how to set up and run integration tests using a real MongoDB instance managed by Testcontainers.

```java
package com.ecommerce.domain.order;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.MongoDBContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@Testcontainers
class OrderRepositoryIntegrationTest {

    // 1. Configure MongoDB Docker container
    @Container
    static final MongoDBContainer mongoDBContainer = new MongoDBContainer("mongo:6.0");

    @BeforeAll
    static void startContainer() {
        mongoDBContainer.start();
    }

    @AfterAll
    static void stopContainer() {
        mongoDBContainer.stop();
    }

    // 2. Set Spring connection property dynamically from container port
    @DynamicPropertySource
    static void setMongoProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.data.mongodb.uri", mongoDBContainer::getReplicaSetUrl);
    }

    @Autowired
    private OrderRepository orderRepository;

    @Autowired
    private MongoTemplate mongoTemplate;

    @Test
    void testCreateAndFindOrder() {
        // Clear collection
        mongoTemplate.dropCollection(ProductOrder.class);

        ProductOrder order = new ProductOrder();
        order.setOrderReference("REF-1002");
        order.setProductId("PROD-882");
        order.setAmount(250.00);
        order.setStatus("COMPLETED");

        orderRepository.save(order);

        List<ProductOrder> results = orderRepository.findByStatus("COMPLETED");
        assertEquals(1, results.size());
        assertEquals("REF-1002", results.get(0).getOrderReference());
        assertEquals(250.00, results.get(0).getAmount());
    }
}
```

---

### Lazy Read-Repair Implementation (Java)
The following code demonstrates a Java mapping class that intercepts read operations, checks the schema version, and applies read-repairs dynamically.

```java
package com.ecommerce.domain.order;

import org.bson.Document;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.stereotype.Component;

@Component
public class LazyReadRepairService {

    private final MongoTemplate mongoTemplate;

    public LazyReadRepairService(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    public Document readAndRepairUser(String userId) {
        Document userDoc = mongoTemplate.findById(userId, Document.class, "users");
        if (userDoc == null) {
            return null;
        }

        Integer version = userDoc.getInteger("schemaVersion");
        if (version == null || version < 2) {
            // Document requires upgrade to V2
            upgradeToV2(userDoc);
            
            // Write repaired document back asynchronously or inline
            mongoTemplate.save(userDoc, "users");
        }
        return userDoc;
    }

    private void upgradeToV2(Document doc) {
        Object addressStr = doc.get("addressStr");
        if (addressStr instanceof String) {
            String[] parts = ((String) addressStr).split(",");
            if (parts.length >= 3) {
                Document addressDetail = new Document();
                addressDetail.put("street", parts[0].trim());
                addressDetail.put("city", parts[1].trim());
                addressDetail.put("zipCode", parts[2].trim());

                doc.put("address", addressDetail);
                doc.remove("addressStr");
            }
        }
        doc.put("schemaVersion", 2);
    }
}
```

---

### Zero-Downtime Migration Runner Script (Java / Spring Batch Concept)
The following Java runner class reads documents in batches, migrates a legacy string representation of an address to an embedded subdocument format, and writes them back with optimistic concurrency retry checks.

```java
package com.ecommerce.domain.order;

import org.bson.Document;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.stereotype.Component;
import java.util.List;

@Component
public class AddressMigrationRunner {
    private static final Logger log = LoggerFactory.getLogger(AddressMigrationRunner.class);
    private final MongoTemplate mongoTemplate;

    public AddressMigrationRunner(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    public void executeMigration(int batchSize) {
        log.info("Starting online address schema migration to V2...");
        
        // Find documents with legacy address string (V1 format)
        Query query = new Query(Criteria.where("addressStr").exists(true))
                            .limit(batchSize);
                            
        boolean hasMore = true;
        int migratedCount = 0;

        while (hasMore) {
            // Fetch batch of raw documents to avoid conversion errors on old format
            List<Document> batch = mongoTemplate.find(query, Document.class, "users");
            
            if (batch.isEmpty()) {
                hasMore = false;
                continue;
            }

            for (Document doc : batch) {
                try {
                    migrateSingleDocument(doc);
                    migratedCount++;
                } catch (Exception ex) {
                    log.error("Failed to migrate document _id: {}", doc.get("_id"), ex);
                }
            }
            log.info("Batch migration progress: {} documents processed.", migratedCount);
        }
        log.info("Schema migration completed. Total processed: {} documents.", migratedCount);
    }

    private void migrateSingleDocument(Document doc) {
        Object addressObj = doc.get("addressStr");
        if (addressObj instanceof String) {
            String addressStr = (String) addressObj;
            
            // Parse V1 address string: "Street, City, Zip"
            String[] parts = addressStr.split(",");
            if (parts.length >= 3) {
                Document addressDetail = new Document();
                addressDetail.put("street", parts[0].trim());
                addressDetail.put("city", parts[1].trim());
                addressDetail.put("zipCode", parts[2].trim());

                // Update document structure to V2
                doc.put("address", addressDetail);
                doc.remove("addressStr"); // Remove legacy field

                // Write document back to database
                mongoTemplate.save(doc, "users");
            }
        }
    }
}
```

---

## 5. Trade-offs & Alternatives

Choosing a schema migration approach requires aligning risks and operational constraints:

| Migration Strategy | Rollback Complexity | Database Load | Application Performance | Operational Risk | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Offline Batch Script** | **Low**: Simple to write and run during database downtime. | **High**: Can saturate CPU and disk IOPS. | **None**: System is offline. | **High (Downtime)** | Small systems where planned downtime is acceptable. |
| **Lazy Read-Repair** | **High**: Application must map both schemas dynamically. | **Low**: Updates documents one-by-one as they are read. | **Low**: Minor overhead during read queries. | **Low** | Massive collections where bulk migrations are too costly. |
| **Online Double-Writing** | **Medium**: Requires deploying code updates in phases. | **Low**: Migrations are run in background batches. | **Low**: Minor overhead during write paths. | **Minimum** | Enterprise microservices, high-volume production databases. |

---

## 6. Common Mistakes & Anti-patterns
*   **Running Migrations without Batches**: Running a migration query that updates millions of documents in a single transaction. This locks the collection, fills the transaction journal, and can cause write timeouts or service outages.
*   **Testing against Mock Interfaces**: Relying on mock drivers or JVM in-memory database simulations. This fails to validate real BSON serialization rules, transaction behaviors, and index performance, allowing bugs to reach production.
*   **Neglecting Optimistic Concurrency during Backfills**: Running background backfill runners that overwrite documents without checking versions. This can overwrite active writes from application servers, leading to data loss.

---

## 7. Hands-on Exercises
1.  Configure a Java project and add the Testcontainers dependencies.
2.  Write an integration test that checks database transaction rollbacks using Testcontainers.
3.  Simulate a zero-downtime migration by executing the Double-Writing pattern on a local collection.
4.  Run the migration runner script from Section 4. Verify that old documents are converted to V2 and legacy fields are removed successfully.

---

## 8. Mini-Project: Integration Test Suite Build
**Scenario**: Build an integration test suite for an e-commerce platform.

1.  Configure Testcontainers MongoDB.
2.  Write tests to verify:
    *   Unique index constraints throw expected duplicate key exceptions on conflict.
    *   Multi-document transactions rollback successfully on exceptions.
    *   Positional array update queries modify correct elements.
3.  Ensure the tests run during the CI/CD pipeline build phase.

---

## 9. Interview Questions

### Q1: Why is a real database engine required to test MongoDB integrations, rather than an in-memory JVM simulation?
**Answer**: In-memory JVM simulations (like Fongo) do not use the WiredTiger storage engine. They do not enforce collation rules, B-Tree index structures, transaction boundaries, or lock hierarchies. A query that succeeds in a simulation can fail in production due to invalid BSON formatting, unique constraint violations, or transaction write conflicts. Testcontainers provides a real MongoDB instance, validating queries against the actual database engine.

### Q2: What is the risk of using an offline script to migrate schemas in production?
**Answer**: An offline migration script reads and updates all documents in a collection. On large collections, this consumes significant CPU and disk IOPS, locking the database and causing write timeouts. This forces database downtime. For high-volume production systems, zero-downtime double-writing is required to migrate schemas without service interruption.

### Q3: How do you handle write conflicts during background backfills?
**Answer**: Background backfills must use optimistic concurrency control. The migration script must include the document version in its update query filter: `{ _id: docId, version: docVersion }`. If an application server updates the document during the backfill, the version increments. The backfill update will fail to match the document, preventing it from overwriting the newer data. The script must catch this exception and skip or retry the migration.

---

---

---

## 10. Production Runbook & Deployment Guidelines

### 1. CI/CD Integration Test Automation
Automate Testcontainers execution in pipeline runner scripts (e.g. Jenkins, GitHub Actions):
```yaml
# GitHub Actions Test Step configuration
- name: Run Integration Tests
  run: mvn clean test -Dspring.profiles.active=test
```
Ensure Docker daemon access is enabled on the runner host.

### 2. Rollback Verification Checklist
Always write and test rollback scripts for all schema migrations. Verify that V2 structures can be converted back to V1 without data loss before executing the production release.

## 11. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Port Binding Conflicts in Testcontainers
*   **Failure Mode**: Hardcoding ports in Testcontainers configurations causes test execution failures if those ports are already active.
*   **Resolution**: Use dynamic port bindings in Testcontainers, and configure Spring connection properties dynamically from container ports.

### 2. Online Double-Write Deadlocks
*   **Failure Mode**: Concurrent updates during double-writing migrations trigger database deadlocks.
*   **Resolution**: Run background migration runners in small batches and add sleep intervals to prevent thread queuing.

### 3. Migration Retry Failures under High Concurrency
*   **Failure Mode**: Backfill scripts overwrite documents without version checks, leading to data loss.
*   **Resolution**: Always use optimistic concurrency version checks in migration runners.

---

## 12. Summary
Testing and migrations require using real database engines and structured migration phases. By leveraging Testcontainers in integration tests, designing zero-downtime double-writing migrations, and implementing version checks during backfills, senior developers update database schemas safely without downtime.

---

## 11. Enterprise Case Study: Mongock Migration Failure & Database State Desynchronization

### 1. Scenario Description
During a continuous deployment release, a Mongock schema migration failed midway because of a database connection timeout. The deployment runner terminated, but the lock collection on MongoDB remained locked. All future pipeline runs failed with migration lock errors, and the database was left in a partially migrated state, breaking application queries.

### 2. Analytical Diagnostic Investigation
The devops team inspected the pipeline run logs:
```text
io.mongock.api.exception.MongockException: Database lock cannot be acquired because it is currently held by lock owner: runner-instance-042
```
They logged into the database and queried the Mongock tracking collections:
```javascript
// Inspect the migration lock state
db.mongockLock.find().pretty();
// Check which migration stages were applied successfully
db.mongockChangeLog.find().sort({ timestamp: -1 });
```
**Diagnostic Findings**:
*   The migration lock had a timeout value of 3 minutes, but because the runner crashed abruptly, the lock record did not clear.
*   The schema update modified document fields, but because the migration script was not idempotent, running it again would fail with duplicate key or structure mismatch errors.

### 3. Step-by-Step Recovery and Validation Runbook
1.  **Manually Release the Database Lock**:
    Remove the lock record to allow subsequent migration tasks to run:
    ```javascript
    db.mongockLock.deleteMany({ lockKey: "MONGOCK_LOCK" });
    ```
2.  **Rollback Partially Applied Migration Changes**:
    Manually clean up the database state to restore it to the previous version before the failed update.
3.  **Ensure Migration ChangeSets are Idempotent**:
    Modify migration scripts to verify existing conditions before applying writes (e.g. check if field exists before adding it).
4.  **Validate Schema Changes Locally using Testcontainers**:
    Create an automated integration test that runs the migration against a clean local database container before executing production releases (see Java code below).

### 4. Code Artifact: Java Integration Migration Test
Save this class as `MigrationIntegrationTest.java` to test migrations:
```java
package com.example.test;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.testcontainers.containers.MongoDBContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@Testcontainers
public class MigrationIntegrationTest {

    @Container
    static final MongoDBContainer mongoDBContainer = new MongoDBContainer("mongo:6.0.5");

    @Autowired
    private MongoTemplate mongoTemplate;

    @Test
    public void testMigrationSuccess() {
        // Assert container is running
        assertThat(mongoDBContainer.isRunning()).isTrue();
        
        // Assert migration collection changes are logged
        boolean changeLogExists = mongoTemplate.collectionExists("mongockChangeLog");
        assertThat(changeLogExists).isTrue();
        
        long changeSetCount = mongoTemplate.getCollection("mongockChangeLog").countDocuments();
        assertThat(changeSetCount).isGreaterThan(0);
        
        // Ensure new database constraints are working
        boolean userFieldIndexed = mongoTemplate.getCollection("users")
            .listIndexes()
            .toList()
            .stream()
            .anyMatch(doc -> doc.get("name").toString().contains("email"));
        assertThat(userFieldIndexed).isTrue();
    }
}
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Idempotency is Essential**: Every database schema change script must be safe to run multiple times. If a migration is interrupted, executing it again must complete successfully without side effects.
*   **Use Blue-Green Strategy for Schema Changes**: Avoid modifying active production collections directly. Instead, create new collections, replicate writes using change streams, and swap collection aliases when sync completes.

---

## 12. Hands-on Lab Exercise: Integration Testing Database Constraints with Testcontainers

### 1. Objective and Scenario
Write an automated integration test script to verify that JSON schema validators reject invalid records and accept correct ones in a temporary container.

### 2. Code Implementation: `container-constraint-test.js`
Create a file named `container-constraint-test.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function runTest() {
  // Point connection to target test container instance
  const uri = process.env.MONGO_TEST_URI || "mongodb://localhost:27017";
  const client = new MongoClient(uri);
  
  try {
    await client.connect();
    const db = client.db("test_db");
    
    // Create collections with schema limits
    await db.createCollection("products", {
      validator: {
        $jsonSchema: {
          bsonType: "object",
          required: ["title", "price"],
          properties: {
            title: { bsonType: "string" },
            price: { bsonType: "double", minimum: 0.0 }
          }
        }
      }
    });

    console.log("Validator constraint successfully initialized.");

    // Assert that incorrect price throws validator error
    try {
      await db.collection("products").insertOne({ title: "Shoe", price: -5.0 });
      console.error("TEST FAILED: Negative price was accepted.");
    } catch (err) {
      console.log("TEST PASSED: Negative price blocked successfully.");
    }

  } finally {
    await client.close();
  }
}
runTest();
```

### 3. Lab Verification Steps
1.  Run the validation test script:
    ```bash
    node container-constraint-test.js
    ```
2.  Verify that it correctly flags structural issues.

---

## 13. CI/CD Integration Test & Mocking Reference

### 1. Key Testcontainers Variables
Configure docker parameters to run local containers in integration tests:
*   `MONGO_TEST_URI`: Custom connection string pointing to local testing containers.
*   `testcontainers.reuse.enable`: Enables reusing existing database test containers to speed up tests.

### 2. Operational Diagnostic Commands
Verify test outcomes:
```bash
# Run integration tests in clean profiles
mvn clean test -Dspring.profiles.active=test

# Inspect docker container logs running database tasks
docker logs <mongo_test_container_id>
```

### 3. Senior Engineer's Production Checklist
*   [ ] Test database migrations against a mock container database in local environments prior to deployment.
*   [ ] Write idempotent migration scripts to ensure failed deployments can be retried safely.
*   [ ] Verify database index structures automatically inside integration testing suites.

---

## 14. Advanced Operational Diagnostic Playbook: Pipeline CI/CD Data Migration Tests

### 1. Migration Testing in Automated Environments
To deploy schema changes without risks, you must automate migration tests in your CI/CD pipelines (e.g. Jenkins or GitHub Actions). The build step must deploy a local test replica set container, apply the migrations, verify database constraints, test the rollback paths, and clean up resources before production deployment.

### 2. Pipeline Configuration Block
Save the following configuration block as `.github/workflows/migration-test.yml` to define automated testing:
```yaml
name: Database Migration Test

on: [push]

jobs:
  test-migrations:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v3

      - name: Start MongoDB Test Container
        run: |
          docker run -d --name test-mongo -p 27017:27017 mongo:6.0.5

      - name: Set up JDK Environment
        uses: actions/setup-java@v3
        with:
          java-version: '17'
          distribution: 'temurin'

      - name: Run Schema Migration Tests
        run: |
          mvn clean test -Dtest=MigrationIntegrationTest -Dspring.profiles.active=test

      - name: Stop and Clean Test Containers
        run: |
          docker stop test-mongo
          docker rm test-mongo
```

### 3. Step-by-Step Resolution Runbook
1.  **Assert Clean States**:
    Configure test runners to deploy clean container volumes for each execution to ensure isolation.
2.  **Verify Rollback Scenarios**:
    Ensure the test suite runs the rollback steps and asserts that constraints return to previous states.
3.  **Integrate Audit Tracking**:
    Export test execution logs and store them in build artifacts for debugging purposes.
