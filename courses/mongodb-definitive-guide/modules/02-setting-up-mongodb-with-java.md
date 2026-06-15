# Module 02: Setting Up MongoDB with Java

Welcome, student. Today we analyze connection topologies and driver setup in **MongoDB with Java (CS-529)**.

---

## 1. What problem does this solve?
Before executing database queries, applications must establish a network connection. Connecting manually for every request is slow, as socket handshakes, TLS certificates, and authentication checks add high latency. 

We solve this using a **MongoClient connection pool**, which maintains a set of open, authenticated TCP connections that are reused across application threads.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides the client driver with built-in connection pool features to:
*   **Maximize Throughput**: Minimizes connection creation overhead.
*   **Balance Load**: Automatically routes read and write requests across multiple nodes in replica sets.

---

## 3. How does it work internally or conceptually?
*   **MongoClient**: The entry point. It manages the connection pool. It is thread-safe and should be registered as a singleton bean.
*   **MongoDatabase**: Binds to a specific database name.
*   **MongoCollection**: Represents a target collection of documents.
*   **Connection String URI**: Formatted as `mongodb://username:password@host:port/database?options`. Includes replication details and connection pool constraints.

```text
                    ┌─── [Thread 1] ───> [Checkout Socket] ──┐
[MongoClient Pool]  ┼─── [Thread 2] ───> [Checkout Socket] ──┼───> [MongoDB Cluster]
                    └─── [Thread 3] ───> [Checkout Socket] ──┘
```

---

## 4. How do we use it in Java?
We connect using `MongoClients.create()` and set configurations via `MongoClientSettings`:

```java
import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoDatabase;
import java.util.concurrent.TimeUnit;

public class MongoConnector {
    public static MongoClient createClient(String uri) {
        MongoClientSettings settings = MongoClientSettings.builder()
                .applyConnectionString(new ConnectionString(uri))
                .applyToConnectionPoolSettings(builder -> builder
                        .maxSize(50) // Allow up to 50 active socket connections
                        .maxWaitTime(5000, TimeUnit.MILLISECONDS)
                ).build();
        return MongoClients.create(settings);
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**: Reuses connection threads, minimizing database overhead; thread-safe operations.
*   **Cons**: Keeping connection pools open consumes JVM memory and database sockets; pool starvation can occur if the database is overloaded.

---

## 6. What are common mistakes?
*   **Instantiating MongoClient per request**: Creating a new client for every query. This exhausts database connections and crashes performance. **Always reuse a single MongoClient instance.**
*   **Hardcoding Passwords**: Placing raw credentials in source code. Always pull connection strings from environment variables.

---

## 7. When should we use it?
*   Always use a single connection pool singleton in backend applications communicating with MongoDB.

---

## 8. When should we avoid it?
*   Do not instantiate MongoClient connection pools in ephemeral serverless functions (like AWS Lambda) without using an external proxy or connection limit constraints.

---

## 9. Code Examples
Here is a complete thread-safe helper class pulling connection settings from environment variables.

```java
package com.mongodb.systems;

import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoDatabase;
import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class DatabaseRegistry {

    private static MongoClient mongoClient = null;

    public static synchronized MongoClient getClient() {
        if (mongoClient == null) {
            String uri = System.getenv("MONGODB_URI");
            if (uri == null) {
                uri = "mongodb://localhost:27017"; // Local fallback
            }
            mongoClient = MongoClients.create(uri);
        }
        return mongoClient;
    }

    public static MongoCollection<Document> getCollection(String dbName, String colName) {
        return getClient().getDatabase(dbName).getCollection(colName);
    }
}
```

---

## 10. Hands-on Exercises

### The Challenge
Implement a method `checkConnection` that attempts to retrieve the database name from a collection object. If it succeeds, return `true`; if it throws a network exception, catch it and return `false`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class ConnectionTester {

    public static boolean checkConnection(MongoCollection<Document> collection) {
        try {
            // TODO: Extract database name from collection namespace
            return collection.getNamespace().getDatabaseName() != null;
        } catch (Exception e) {
            return false;
        }
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import com.mongodb.MongoNamespace;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class ConnectionTesterTest {

    @SuppressWarnings("unchecked")
    @Test
    void testConnectionVerification() {
        MongoCollection<Document> mockCollection = mock(MongoCollection.class);
        MongoNamespace namespace = new MongoNamespace("test_db", "test_collection");
        when(mockCollection.getNamespace()).thenReturn(namespace);

        assertTrue(ConnectionTester.checkConnection(mockCollection));
    }
}
```
