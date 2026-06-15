# MongoDB: The Definitive Guide - Production Systems Engineering (CS-529)

Welcome to **MongoDB: The Definitive Guide - Production Systems Engineering (CS-529)**. This course is a deep, systems-level dive into MongoDB architectures, query patterns, indexing strategies, replication mechanics, and distributed sharding clusters.

The curriculum is structured directly around **Chapters 1 through 20** of the definitive text *MongoDB: The Definitive Guide (3rd Edition)*. Each chapter corresponds to a dedicated course module. All code examples, architectural configurations, and hands-on laboratory exercises are presented using **Java 21** and the official **MongoDB Java Sync Driver**.

---

## 🛠️ Local Sandbox Environment (Docker)

To write code and test configurations, you need a running MongoDB database. The easiest way to start MongoDB locally is using **Docker**.

### 1. Docker Compose Configuration (`docker-compose.yml`)
Create a `docker-compose.yml` file in your project directory:

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:6.0
    container_name: mongodb-sandbox
    ports:
      - "27017:27017"
    environment:
      - MONGO_INITDB_DATABASE=academic_sandbox
    volumes:
      - mongodb_data:/data/db

volumes:
  mongodb_data:
```

### 2. Basic Commands
*   **Start the container**: `docker compose up -d`
*   **Stop the container**: `docker compose down`

---

## 🚀 Java Practice Environment Setup

To run the hands-on challenges and compile-grade stubs, initialize a standard **Maven** project.

### 1. Maven Dependency Configuration (`pom.xml`)
Add the following dependencies to your project's `pom.xml`:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.mongodb.systems</groupId>
    <artifactId>mongodb-definitive-guide</artifactId>
    <version>1.0.0</version>

    <properties>
        <maven.compiler.source>21</maven.compiler.source>
        <maven.compiler.target>21</maven.compiler.target>
        <mongodb.driver.version>4.11.1</mongodb.driver.version>
        <junit.version>5.10.1</junit.version>
    </properties>

    <dependencies>
        <!-- MongoDB Java Sync Driver -->
        <dependency>
            <groupId>org.mongodb</groupId>
            <artifactId>mongodb-driver-sync</artifactId>
            <version>${mongodb.driver.version}</version>
        </dependency>

        <!-- Logging Framework -->
        <dependency>
            <groupId>ch.qos.logback</groupId>
            <artifactId>logback-classic</artifactId>
            <version>1.4.14</version>
        </dependency>

        <!-- Testing Framework -->
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>${junit.version}</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

### 2. Thread-Safe Connection Management (`MongoConnectionManager.java`)
Create a static manager class to bootstrap and reuse the `MongoClient` connection pool:

```java
package com.mongodb.systems.config;

import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import com.mongodb.WriteConcern;
import com.mongodb.ReadPreference;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoDatabase;
import java.util.concurrent.TimeUnit;

public class MongoConnectionManager {

    private static MongoClient mongoClient = null;

    public static synchronized MongoClient getClient(String connectionStringUri) {
        if (mongoClient == null) {
            ConnectionString connectionString = new ConnectionString(connectionStringUri);
            
            MongoClientSettings settings = MongoClientSettings.builder()
                .applyConnectionString(connectionString)
                // Configure connection pool limits
                .applyToConnectionPoolSettings(builder -> builder
                    .maxSize(100)                      // Maximum open sockets
                    .minSize(10)                       // Minimum idle connections
                    .maxWaitTime(5, TimeUnit.SECONDS)  // Thread checkout timeout
                )
                // Set default write concern and read preference
                .writeConcern(WriteConcern.MAJORITY.withJournal(true))
                .readPreference(ReadPreference.primary())
                .build();
                
            mongoClient = MongoClients.create(settings);
        }
        return mongoClient;
    }

    public static MongoDatabase getDatabase(String uri, String dbName) {
        return getClient(uri).getDatabase(dbName);
    }

    public static synchronized void close() {
        if (mongoClient != null) {
            mongoClient.close();
            mongoClient = null;
        }
    }
}
```

## 📂 Syllabus Navigation Index

The course consists of **20 modules** mapping core MongoDB concepts to production Java implementation:

*   **[Module 01: MongoDB Fundamentals](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/01-mongodb-fundamentals.md)**: Document db vs RDBMS, BSON vs JSON datatypes, ObjectId internals, embedded data vs arrays.
*   **[Module 02: Setting Up MongoDB with Java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/02-setting-up-mongodb-with-java.md)**: Local/Atlas configs, connection strings, auth controls, and MongoClient connection pools.
*   **[Module 03: Basic CRUD Operations](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/03-basic-crud-operations.md)**: Single document CRUD, update modifiers, array filters, upserts, deletes, and soft deletes.
*   **[Module 04: Querying Deep Dive](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/04-querying-deep-dive.md)**: Query filters, logical operators, projections, array matching, and keyset pagination.
*   **[Module 05: Schema Design in MongoDB](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/05-schema-design-in-mongodb.md)**: Embedding vs referencing, denormalization, 16MB limit, and advanced modeling patterns.
*   **[Module 06: Indexing](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/06-indexing.md)**: Single-field, compound, unique, multikey, partial, TTL indexes, ESR rules, explain plans.
*   **[Module 07: Aggregation Framework](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/07-aggregation-framework.md)**: Pipelines, match/group/lookup/facet stages, allowDiskUse memory configurations.
*   **[Module 08: Data Validation](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/08-data-validation.md)**: JSON Schema validation ($jsonSchema), validation action errors/warns, strict/moderate levels.
*   **[Module 09: Transactions and Consistency](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/09-transactions-and-consistency.md)**: Multi-document ACID transactions, sessions, write concern majority, and read preference routing.
*   **[Module 10: Error Handling and Reliability](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/10-error-handling-and-reliability.md)**: MongoException classes, unique key violations, timeouts, and network retry loops.
*   **[Module 11: Bulk Operations](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/11-bulk-operations.md)**: insertMany vs bulkWrite, ordered vs unordered writes execution models.
*   **[Module 12: Object Mapping in Java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/12-object-mapping-in-java.md)**: Direct Document maps vs POJO registries, CodecRegistry, and mapping nested entities.
*   **[Module 13: Spring Data MongoDB Comparison](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/13-spring-data-mongodb-comparison.md)**: Abstractions comparison, MongoTemplate vs MongoRepository, mapping annotations.
*   **[Module 14: Performance Optimization](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/14-performance-optimization.md)**: Projections, connection pools, cursor batch sizes, and avoiding N+1 query loops.
*   **[Module 15: Security](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/15-security.md)**: SCRAM, x.509 cert validation, TLS/SSL transport security, and regex injection mitigations.
*   **[Module 16: Deployment and Production Practices](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/16-deployment-and-production-practices.md)**: Replica sets setups, elections, failovers, and sharded cluster topologies configurations.
*   **[Module 17: Testing MongoDB Applications](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/17-testing-mongodb-applications.md)**: Integration testing via Testcontainers and database session cleaning.
*   **[Module 18: Real-World Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/18-real-world-project.md)**: End-to-end e-commerce transactional booking API integration.
*   **[Module 19: Interview Preparation](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/19-interview-preparation.md)**: System design and scenario-based Q&A collections.
*   **[Module 20: Learning Roadmap](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/modules/20-learning-roadmap.md)**: A 4-week structured milestone roadmap study plan.

---

## 🎓 Grading & Assessment Criteria

Your final score in this course is based on:
1.  **Socratic Review Assignments (40%)**: Answering the review questions at the end of each module with detailed systems explanations.
2.  **Java Hands-on Challenges (60%)**: Implementing robust, compile-grade Java query classes and passing the JUnit 5 test assertions.
