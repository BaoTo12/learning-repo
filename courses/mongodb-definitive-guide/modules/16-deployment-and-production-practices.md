# Module 16: Deployment and Production Practices

Welcome, student. Today we study high availability and scale-out configurations in **MongoDB Production Deployments (CS-529)**.

---

## 1. What problem does this solve?
Single-node databases represent single points of failure (SPOF). If the machine crashes, the application experiences downtime, and data on disk can be corrupted. Furthermore, a single machine has limits on disk, CPU, and network throughput.

We solve this using **Replica Sets** for high availability and **Sharding Clusters** for horizontal scaling.

---

## 2. Why does MongoDB provide this feature?
MongoDB provides production scaling features to:
*   **Prevent Downtime**: Node failovers occur in seconds.
*   **Scale Writes Horizontally**: Distributes collections across multiple independent servers (shards) automatically.

---

## 3. How does it work internally or conceptually?
*   **Replica Sets**: A group of replica processes (typically 3) consisting of:
    *   *Primary*: Receives all writes. Writes are logged to the oplog.
    *   *Secondaries*: Replicate the primary's oplog asynchronously to sync their local databases.
*   **Consensus Elections**: Nodes heartbeat check each other every 2 seconds. If the primary goes offline, the secondaries elect a new primary.
*   **Sharding Topologies**:
    *   *mongos*: A query router proxy that clients connect to.
    *   *Config Server*: Stores routing details and partitions mapping maps.
    *   *Shard Key*: Determines how documents are distributed across shards. Range sharding partitions data in blocks; hashed sharding hashes the key to distribute data uniformly.

---

## 4. How do we use it in Java?
We configure replica sets and query routers inside the MongoClient connection string:

```java
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;

public class ClusterConnection {
    public MongoClient connectToCluster() {
        // Pass all cluster nodes to allow the driver to discover active primaries and route queries
        String uri = "mongodb://node1:27017,node2:27017,node3:27017/prod?replicaSet=rs0&retryWrites=true";
        return MongoClients.create(uri);
    }
}
```

---

## 5. What are the trade-offs?
*   **Pros**: Failover takes seconds; sharding allows unlimited horizontal scaling.
*   **Cons**: Replica sets double storage costs; sharding clusters require significant network and monitoring management.

---

## 6. Common Mistakes
*   **Selecting Low-Cardinality Shard Keys**: Sharding by fields with few unique values, causing unbalanced chunks that the balancer thread cannot migrate.
*   **Connecting to a single node directly**: Hardcoding a single replica node's IP in the client instead of using the full cluster seed list, which breaks failover routing.

---

## 7. When should we use it?
*   Use replica sets in all production systems.
*   Use sharding when data storage or write throughput requirements exceed the capacity of a single machine.

---

## 8. When should we avoid it?
*   Avoid sharding during early development phases, as it adds operational complexity and requires careful shard key planning.

---

## 9. Code Examples
Here is a class demonstrating write concern verification and read preference configurations.

```java
package com.mongodb.systems;

import com.mongodb.ReadPreference;
import com.mongodb.WriteConcern;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoDatabase;
import org.bson.Document;

public class ProductionRoutingConfig {

    public MongoCollection<Document> getSecondaryReadableCollection(MongoDatabase db, String colName) {
        // Read preference secondaryPreferred routes analytical reads to secondaries, saving primary CPU
        return db.getCollection(colName)
                .withReadPreference(ReadPreference.secondaryPreferred())
                .withWriteConcern(WriteConcern.MAJORITY.withJournal(true));
    }
}
```

---

## 10. Hands-on Exercises

### The Challenge
Implement a method `verifyReadPreference` that evaluates whether a collection is configured to allow secondary reads. Return `true` if its ReadPreference is not primary.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.ReadPreference;
import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class ReadPreferenceVerifier {

    public static boolean isSecondaryReadingAllowed(MongoCollection<Document> collection) {
        // TODO: Return true if the collection's ReadPreference is set to secondaryPreferred or secondary
        ReadPreference rp = collection.getReadPreference();
        return rp != null && !rp.equals(ReadPreference.primary());
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import com.mongodb.ReadPreference;
import com.mongodb.client.MongoCollection;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class ReadPreferenceVerifierTest {

    @SuppressWarnings("unchecked")
    @Test
    void testReadPreferenceVerification() {
        MongoCollection<Document> mockCol = mock(MongoCollection.class);
        when(mockCol.getReadPreference()).thenReturn(ReadPreference.secondaryPreferred());

        assertTrue(ReadPreferenceVerifier.isSecondaryReadingAllowed(mockCol));
    }
}
```
