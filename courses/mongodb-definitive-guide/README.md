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

---

## 📂 Syllabus Navigation Index

The course consists of **21 modules** (a Beginner's Primer plus 20 modules mapping directly to Chapters 1–20 of the textbook):

### Part I: Introduction
*   **[Module 00: Beginner's Primer to NoSQL & Java-MongoDB](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/00-beginners-primer.md)**
    *   *Core concepts*: SQL vs NoSQL comparisons, BSON/JSON, and a fully runnable Java CRUD operations walkthrough.
*   **[Module 01: Introduction to MongoDB](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/01-introduction.md)**
    *   *Core concepts*: Document database design philosophies, scale-out versus scale-up models, SQL vs. Java object-mapping comparisons.
*   **[Module 02: Getting Started with MongoDB](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/02-getting-started.md)**
    *   *Core concepts*: BSON serialization, document mapping in Java using `Document`, BSON datatypes, and running simple inserts.
*   **[Module 03: Creating, Updating, and Deleting Documents](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/03-crud-modifications.md)**
    *   *Core concepts*: Java CRUD operations, atomic update operators (`$set`, `$inc`, `$push`, `$pull`), array positionals, and `arrayFilters`.
*   **[Module 04: Querying](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/04-querying.md)**
    *   *Core concepts*: Find collections, conditional logical operators (`Filters`), cursor paging using `FindIterable`, limits, and projections.

### Part II: Designing Your Application
*   **[Module 05: Indexes](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/05-indexes.md)**
    *   *Core concepts*: Creating indexes in Java (`Indexes`), single/compound sorting directions, explain document parsing, and collision mitigations.
*   **[Module 06: Special Index and Collection Types](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/06-special-collections.md)**
    *   *Core concepts*: Geospatial query scopes, Text searching, Capped collections, TTL (Time-To-Live) index setups, and GridFS bucket streams.
*   **[Module 07: Introduction to the Aggregation Framework](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/07-aggregation-framework.md)**
    *   *Core concepts*: Building pipelines using Java `Aggregates` factory stages (`match`, `unwind`, `group`, `project`, `facet`), memory limits, and disk swaps.
*   **[Module 08: Transactions](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/08-transactions.md)**
    *   *Core concepts*: ACID transactions in Java, `ClientSession` management, lock timeouts, and transient write-conflict auto-retries.
*   **[Module 09: Application Design](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/09-application-design.md)**
    *   *Core concepts*: Schema design patterns (Bucket, Polymorphic, Subset), cardinality references, and data migrations in Java.

### Part III: Replication
*   **[Module 10: Setting Up a Replica Set](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/10-replica-set-setup.md)**
    *   *Core concepts*: High availability topologies, hidden nodes, arbiters, voting priority configurations, and configuration documents.
*   **[Module 11: Components of a Replica Set](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/11-replica-set-components.md)**
    *   *Core concepts*: Oplog syncing mechanics, heartbeat checks, election state routing, rollback files, and partition recovery.
*   **[Module 12: Connecting to a Replica Set from Your Application](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/12-connecting-replica-sets.md)**
    *   *Core concepts*: Connection strings, write concerns (`WriteConcern.MAJORITY`), read preferences, and connection pool tuning in Java.
*   **[Module 13: Replica Set Administration](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/13-replica-set-administration.md)**
    *   *Core concepts*: Dynamic oplog resizing commands, secondary index builds in standalone modes, and lag monitoring.

### Part IV: Sharding
*   **[Module 14: Introduction to Sharding](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/14-sharding-introduction.md)**
    *   *Core concepts*: Scaling limits, sharded cluster topologies (Config servers, mongos routing, shards), and query routing.
*   **[Module 15: Configuring Sharding](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/15-sharding-configuration.md)**
    *   *Core concepts*: Balancer scheduling, chunk range splitting, adding shards from replica sets, and collection-level activations.
*   **[Module 16: Choosing a Shard Key](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/16-shard-key-selection.md)**
    *   *Core concepts*: Key selection distributions (ranged vs. hashed), composite key routing, cardinality limitations, and split safety.
*   **[Module 17: Sharding Administration](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/17-sharding-administration.md)**
    *   *Core concepts*: Running status checks, tracing router network pools, split finds, and resolving jumbo chunks.

### Part V: Application Administration
*   **[Module 18: Seeing What Your Application Is Doing](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/18-application-diagnostics.md)**
    *   *Core concepts*: Current operations tracking (`currentOp`), killing hanging threads (`killOp`), profiler levels, and size calculations.
*   **[Module 19: An Introduction to MongoDB Security](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/19-security.md)**
    *   *Core concepts*: RBAC database roles, SCRAM authentication, TLS/SSL configurations, and x.509 client certificate handshakes in Java.
*   **[Module 20: Durability](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/20-durability.md)**
    *   *Core concepts*: WiredTiger journaling, read concern levels (`local`, `majority`, `linearizable`), commit guarantees, and database checks.

---

## 🎓 Grading & Assessment Criteria

Your final score in this course is based on:
1.  **Socratic Review Assignments (40%)**: Answering the review questions at the end of each module with detailed systems explanations.
2.  **Java Hands-on Challenges (60%)**: Implementing robust, compile-grade Java query classes and passing the JUnit 5 test assertions.
