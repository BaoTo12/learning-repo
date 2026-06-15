# Module 17: Testing MongoDB Applications

Welcome, student. Today we study automated testing strategies in **MongoDB Java Testing (CS-529)**.

---

## 1. What problem does this solve?
Writing integration tests against shared staging or developer databases introduces state collisions. If one test drops a collection, another running test fails, creating flaky builds. 

We solve this using **Docker Testcontainers**, which spin up isolated, clean MongoDB instances in container environments for every test suite run.

---

## 2. Why does MongoDB provide this feature?
MongoDB testing features are supported by the driver and Testcontainers frameworks to:
*   **Enforce Test Isolation**: Runs queries against isolated databases.
*   **Validate Full Configurations**: Validates index creation, transaction boundaries, and validation rules in tests.

---

## 3. How does it work internally or conceptually?
*   **Testcontainers**: Interacts with the host Docker daemon, pulls the official MongoDB image, starts the container on a random port, and updates connection strings.
*   **Cleanups**: We drop database collections between tests to ensure a clean state for every test case.

---

## 4. How do we use it in Java?
We integrate `MongoDBContainer` inside JUnit 5 lifecycle methods:

```java
import org.testcontainers.containers.MongoDBContainer;
import org.testcontainers.utility.DockerImageName;

public class TestSetup {
    private static MongoDBContainer container;

    public static void startContainer() {
        container = new MongoDBContainer(DockerImageName.parse("mongo:6.0"));
        container.start();
        String replicaSetUrl = container.getReplicaSetUrl(); // Connection string
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**: 100% realistic tests; no cross-test database conflicts.
*   **Cons**: Starting containers adds latency to build times; requires running Docker on the host machine.

---

## 6. Common Mistakes
*   **Restarting Containers per Test**: Starting and stopping Docker containers for every single test case, adding minutes to build runs. **Use a static, shared singleton container instead.**
*   **Failing to Clean Up**: Leaving database state behind between tests.

---

## 7. When should we use it?
*   Use Testcontainers for all repository integration testing.

---

## 8. When should we avoid it?
*   Avoid Testcontainers in simple unit tests where mocking database repository interfaces with Mockito is faster.

---

## 9. Code Examples
Here is a base test class using Testcontainers singleton pattern.

```java
package com.mongodb.systems;

import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoCollection;
import org.bson.Document;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.testcontainers.containers.MongoDBContainer;
import org.testcontainers.utility.DockerImageName;

public abstract class BaseMongoIntegrationTest {

    protected static MongoDBContainer mongo = new MongoDBContainer(DockerImageName.parse("mongo:6.0"));
    protected static MongoClient client;

    @BeforeAll
    public static void start() {
        mongo.start();
        client = MongoClients.create(mongo.getReplicaSetUrl());
    }

    @AfterAll
    public static void stop() {
        if (client != null) {
            client.close();
        }
        mongo.stop();
    }
}
```

---

## 10. Hands-on Exercises

### The Challenge
Implement a utility method `cleanCollection` that clears all documents inside a collection before a test runs.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class TestDatabaseCleaner {

    public static void cleanCollection(MongoCollection<Document> collection) {
        // TODO: Delete all documents inside the collection
        collection.deleteMany(new Document());
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;

class TestDatabaseCleanerTest {

    @SuppressWarnings("unchecked")
    @Test
    void testCleanupExecution() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        TestDatabaseCleaner.cleanCollection(mockCol);
        verify(mockCol, times(1)).deleteMany(any(Document.class));
    }
}
```
