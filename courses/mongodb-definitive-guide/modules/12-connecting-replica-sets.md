# Module 12: Connecting to a Replica Set (Chapter 12)

Welcome class. Today we analyze **Connecting to a Replica Set (CS-529)**.

In production environments, a Java application does not communicate with a single database server; it connects to a dynamic replica set cluster. The Java driver must handle auto-discovery of nodes, routing read requests to appropriate secondaries, and executing writes with majority consensus.

Today we study **Replica Set Client Connections**, analyzing replica set connection strings, read preferences, write concerns, and rollback resilience in Java.

---

## 1. Academic Lecture: Driver Discovery & Connection Options

### 1. Auto-Discovery & Seed Lists
When establishing a connection, the Java driver receives a connection string containing a **seed list** of hosts. The driver initiates connection checks with the seeds, issues an `isMaster` (or `hello`) command to identify the cluster primary, and discovers the addresses of all other cluster members dynamically.

### 2. Read Preference & Write Concern
*   **Write Concern**: Controls write validation rules. `w:majority` waits until a write is persisted to a majority of voting members.
*   **Read Preference**: Directs query routes:
    *   `primary`: (Default) Always routes queries to the primary.
    *   `secondaryPreferred`: Routes queries to secondaries if available, falling back to primary.
    *   `nearest`: Routes queries to the node with the lowest network latency.

```text
               ┌─── [Write Request] ───> Primary (Write Concern: majority)
[Java Driver] ─┼─── [Read Request] ────> Secondary (Read Preference: secondaryPreferred)
               └─── [Read Request] ────> Lowest Latency Node (Read Preference: nearest)
```

---

## 2. Theory vs. Production Trade-offs

Compare read and write safety profiles:

| Configuration Parameter | Write Speed | Read Consistency | Rollback Resiliency | WAN Network Load |
| :--- | :--- | :--- | :--- | :--- |
| `w:1` (Acknowledge Local) | Excellent | Primary-read Consistent | Very Low | Minimal |
| `w:majority` (Consensus) | Moderate | Primary-read Consistent | 100% Guaranteed | High (Requires intra-cluster ACK) |
| ReadPref: `primary` | Moderate | Strict Consistency | High | Moderate |
| ReadPref: `secondary` | Moderate | Eventual Consistency (Lag) | Low (Stale read risks) | High (Cross-DC queries) |

---

## 3. How to Use: Configuring Connection Security in Java

Let us look at connection builders. We contrast a volatile, un-monitored connection setup with a robust, production-grade connection manager configured for durability.

### A. The Volatile Local Connection (Anti-Pattern)
Avoid executing updates with weak write concerns:

```java
// DANGER: Writes are acknowledged by the local node only. If the primary crashes 
// before replicating the write, the data is lost and rolled back, corrupting states.
MongoClient client = MongoClients.create("mongodb://localhost:27017");
MongoCollection<Document> collection = client.getDatabase("prod").getCollection("orders");
collection.withWriteConcern(WriteConcern.W1).insertOne(new Document("orderId", "123"));
```

### B. The Production-Grade Client Settings Setup (Production Pattern)
Define client configurations targeting write majority confirmations and secondary query routing:

```java
import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import com.mongodb.WriteConcern;
import com.mongodb.ReadPreference;
import com.mongodb.ReadConcern;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import java.util.concurrent.TimeUnit;

public class ConnectionSettingsFactory {

    public static MongoClient createSecureClient(String seedListUri) {
        MongoClientSettings settings = MongoClientSettings.builder()
                .applyConnectionString(new ConnectionString(seedListUri))
                .writeConcern(WriteConcern.MAJORITY.withWTimeout(5000, TimeUnit.MILLISECONDS))
                .readConcern(ReadConcern.MAJORITY)
                .readPreference(ReadPreference.secondaryPreferred())
                .applyToConnectionPoolSettings(builder -> builder
                        .maxSize(100)
                        .minSize(10)
                        .maxConnectionIdleTime(60, TimeUnit.SECONDS)
                )
                .build();

        return MongoClients.create(settings);
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Omitted `wtimeout` on Write Concern Majority
*   **Why it fails**: Setting `WriteConcern.MAJORITY` without configuring a `wtimeout` limit. If a network partition isolates the primary, the write cannot reach a majority. Without a timeout, the driver's write threads will block indefinitely, exhausting application threads.
*   **Mitigation**: Always specify `withWTimeout(timeout, TimeUnit.MILLISECONDS)` when configuring write majority limits.

---

## 5. Socratic Review Questions

### Question 1
Why does reading from a secondary using `ReadPreference.secondary()` with `ReadConcern.LOCAL` risk returning data that is subsequently rolled back?

#### Answer
`ReadConcern.LOCAL` allows a node to return its local copy of data, regardless of whether that data has been replicated to a majority of nodes. If a primary writes to its local collection, replicates it to a secondary, and then crashes before achieving majority confirmation, the cluster will elect a new primary that does not contain that write. When the old primary/secondary reconnect, they roll back the write. The client has thus read stale, phantom data.

---

## 6. Hands-on Challenge: Resilient Client Configuration Builder

### The Challenge
In this challenge, you will implement a resilient MongoClient configuration builder in Java.
Your task:
1. Complete `buildMongoClientSettings` in `MongoClientConfigurationBuilder`.
2. Construct and return `MongoClientSettings` matching the requirements:
   - Target the provided connection string URI.
   - Configure write concern to `majority` with a timeout of `3000` milliseconds.
   - Configure read preference to `secondaryPreferred`.
   - Configure read concern to `majority`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.MongoClientSettings;

public class MongoClientConfigurationBuilder {

    public MongoClientSettings buildMongoClientSettings(String connectionStringUri) {
        // TODO: Build and return MongoClientSettings matching the requirements
        return null;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test:

```java
package com.mongodb.systems;

import com.mongodb.MongoClientSettings;
import com.mongodb.WriteConcern;
import com.mongodb.ReadPreference;
import com.mongodb.ReadConcern;
import org.junit.jupiter.api.Test;
import java.util.concurrent.TimeUnit;
import static org.junit.jupiter.api.Assertions.*;

class MongoClientConfigurationBuilderTest {

    @Test
    void testConfigurationBuilder() {
        MongoClientConfigurationBuilder builder = new MongoClientConfigurationBuilder();
        String uri = "mongodb://host1:27017,host2:27017/?replicaSet=prodRS";
        
        MongoClientSettings settings = builder.buildMongoClientSettings(uri);

        assertNotNull(settings, "Settings should not be null");
        assertEquals(ReadPreference.secondaryPreferred(), settings.getReadPreference());
        assertEquals(ReadConcern.MAJORITY, settings.getReadConcern());
        
        WriteConcern wc = settings.getWriteConcern();
        assertNotNull(wc);
        assertTrue(wc.getWObject() instanceof String);
        assertEquals("majority", wc.getWObject());
        assertEquals(3000, wc.getWTimeout(TimeUnit.MILLISECONDS));
    }
}
```
