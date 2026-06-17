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

### 4.1 Visual Setup Flow & Port Allocation Trace

```text
[ JUnit Runner ] ──( 1. start() )──> [ Testcontainers Engine ]
                                               │
                                               ▼ ( 2. Query Docker Socket )
                                     [ Local Docker Daemon ]
                                               │
                                               ▼ ( 3. Pull & Run Image )
                                     [ MongoDB Container ] 
                                     - Internal Port: 27017
                                     - External Port: 32768 (Randomized)
                                               │
                                               ▼ ( 4. getReplicaSetUrl() )
[ MongoClient ]  <──( Connection String )──────┘
  e.g., "mongodb://localhost:32768"
```

#### Step-by-Step Container Bootstrap Path:

1. **JVM Class Init**:
   * JUnit suite initializes `MongoDBContainer` with image `mongo:6.0`.
2. **Docker Check**:
   * Testcontainers locates Docker daemon socket (`unix:///var/run/docker.sock` on Linux/macOS or `npipe:////./pipe/docker_engine` on Windows).
3. **Pull & Start Image**:
   * If `mongo:6.0` image is missing in the local repository cache, it pulls it from Docker Hub.
   * Spawns container instance, dynamically mapping the internal BSON listener port `27017` to a randomized external port (e.g. `32768`).
4. **Replica Set Configuration**:
   * Configures replica set metadata inside container.
5. **URL Mapping**:
   * `container.getReplicaSetUrl()` returns the standard connection URI mapping to the randomized exposed port (e.g. `mongodb://localhost:32768/?uuidRepresentation=STANDARD`). This avoids port allocation collision.

```java
import org.testcontainers.containers.MongoDBContainer;
import org.testcontainers.utility.DockerImageName;

public class TestSetup {
    private static MongoDBContainer container;

    public static void startContainer() {
        // Construct the container using parsed Docker coordinate coordinates
        container = new MongoDBContainer(DockerImageName.parse("mongo:6.0"));
        // Starts container and blocks thread until replica set is fully active
        container.start();
        // Retrieves the mapped connection string containing randomize ports
        String replicaSetUrl = container.getReplicaSetUrl(); 
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`MongoDBContainer`**: Utility class in `org.testcontainers.containers` library that handles starting and stopping standard MongoDB database instances inside Docker.
- **`DockerImageName.parse("mongo:6.0")`**: Parses Docker Hub coordinates string.
- **`container.getReplicaSetUrl()`**: Dynamically returns the JDBC/MongoDB connection string, configuring proper standard UUID mappings.

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

##### Visual Test Lifecycle Execution Timeline:

```text
[Suite Boot] ──> @BeforeAll (starts container & MongoClient)
                   │
                   ├──> Test Case 1 (inserts documents)
                   ├──> @BeforeEach (calls deleteMany to clear collections)
                   │
                   ├──> Test Case 2 (runs in a completely clean database)
                   │
                 @AfterAll (closes client connection & stops container)
```

1. **Suite Startup**:
   * JUnit runner loads test suite class extending `BaseMongoIntegrationTest`.
2. **Initialization Hook**:
   * `@BeforeAll` executes once. Spawns the static Docker container instance and initiates the `MongoClient` connection pool.
3. **Clean Slate execution between test cases**:
   * `@BeforeEach` can be used to execute database cleans, guaranteeing tests run in isolation and do not leak state.
4. **Shutdown Hook**:
   * `@AfterAll` executes once. Closes socket streams and terminates the Docker container.

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

    // Define the MongoDB container using static singleton scope to avoid restarts per test method
    protected static final MongoDBContainer mongo = new MongoDBContainer(DockerImageName.parse("mongo:6.0"));
    protected static MongoClient client;

    @BeforeAll
    public static void start() {
        // Start the Docker container process
        mongo.start();
        // Connect pool using dynamic Testcontainers replica set url
        client = MongoClients.create(mongo.getReplicaSetUrl());
    }

    @AfterAll
    public static void stop() {
        // Ensure MongoClient connection pool is closed to avoid socket leaks
        if (client != null) {
            client.close();
        }
        // Stop container and destroy Docker container processes
        mongo.stop();
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`protected static final MongoDBContainer mongo`**: Declaring the container as a static class property shared across tests prevents the container from restarting between individual test runs, saving minutes in build execution times.
- **`@BeforeAll` / `@AfterAll`**: JUnit 5 lifecycle annotations that execute code block once per class. The target methods must be declared `static`.

---

## 10. Hands-on Exercises

### The Challenge
Implement a utility method `cleanCollection` that clears all documents inside a collection before a test runs.

##### Dataset Clean Execution Trace:

###### Collection State before clean (`orders` Collection):
```json
[
  { "_id": "1", "status": "COMPLETED" },
  { "_id": "2", "status": "PENDING" }
]
```

###### Step-by-Step Clean Execution:
1. **Application Invokes**: `TestDatabaseCleaner.cleanCollection(ordersCollection)`.
2. **Execute Query Filter**:
   * Method calls `deleteMany(new Document())`.
   * An empty BSON document `{}` is passed, which matches all records in the collection.
3. **Database Clears Records**:
   * MongoDB drops all documents within WiredTiger data pages.
4. **Final State**:
   ```json
   []
   ```

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class TestDatabaseCleaner {

    public static void cleanCollection(MongoCollection<Document> collection) {
        // Delete all documents inside the collection by passing a blank filter query document
        collection.deleteMany(new Document());
    }
}
```

#### Detailed Operations & Syntax Explanation:
- **`collection.deleteMany(new Document())`**: Standard driver method used to remove documents. Passing an empty `Document()` filter acts as a wildcard, deleting all records.

---

### Verification Test
Verify your code with this JUnit 5 test class:

#### Detailed Testing & Verification Explanation:
*   **`mock(MongoCollection.class)`**: Mocks the MongoDB driver collection interfaces, bypassing connection boots.
*   **`verify(mockCol, times(1)).deleteMany(any(Document.class))`**: Asserts that `deleteMany` was executed exactly once with a BSON document filter class.

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
        // 1. Arrange mock MongoCollection dependencies
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        
        // 2. Act
        TestDatabaseCleaner.cleanCollection(mockCol);
        
        // 3. Assert and Verify
        // Verify deleteMany was called exactly once with any Document filter parameter
        verify(mockCol, times(1)).deleteMany(any(Document.class));
    }
}
```
