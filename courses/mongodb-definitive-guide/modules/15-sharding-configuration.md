# Module 15: Configuring Sharding (Chapter 15)

Welcome class. Today we analyze **Configuring Sharding (CS-529)**.

Deploying a sharded cluster requires carefully configuring system boundaries: initializing config servers, starting query routers, registering shards, and defining chunk allocation parameters.

Today we study **Sharded Cluster Deployment & Configuration**, analyzing config server replica sets, shard activation, and balancer window options in Java.

---

## 1. Academic Lecture: Sharding Commands & Balancer Windows

### 1. Registering Shards and Activating Databases
To build a sharded cluster, we run administration commands on the `admin` database of a `mongos` router:
*   `addShard`: Adds a replica set as a storage shard.
*   `enableSharding`: Enables sharding on a specific database.
*   `shardCollection`: Shards a collection, utilizing a range or hashed key.

### 2. Chunk Splits & The Balancer
Data is partitioned into contiguous ranges called **chunks**. When a chunk exceeds its maximum size (default 64MB), MongoDB splits it. The **Balancer** runs as a background process, migrating chunks from over-allocated shards to under-allocated shards to balance the cluster.

```text
[Chunk A (0-10)] ──(Exceeds 64MB)──> [Chunk A1 (0-5)] & [Chunk A2 (5-10)]
                                            │
                                    (Balancer Migrate)
                                            ▼
                                     [Move to Shard 2]
```

---

## 2. Theory vs. Production Trade-offs

Compare shard key types:

| Dimension / Metric | Ranged Shard Key | Hashed Shard Key |
| :--- | :--- | :--- |
| **Write Distribution** | Concentrated on max chunk (Hotspot risk) | Uniformly distributed (No write hotspots) |
| **Read Routing Performance**| Excellent for range queries | Low for range queries (Scatter-gather required) |
| **Chunk Balancer Load** | High (Writes cause frequent splits/moves) | Low (Data grows uniformly) |
| **Monotonically Increasing Keys**| Dangerous (Creates write hotspot on last shard) | Recommended (Values are scrambled) |

---

## 3. How to Use: Database Sharding Configuration in Java

Let us register shards. We contrast a naive connection deployment (storing unsharded data) with a robust administrative configuration class in Java.

### A. The Unsharded Database (Anti-Pattern)
Storing data without configuring sharding:

```java
// DANGER: If the database is not sharded, all collections are saved 
// to the cluster's primary shard, rendering other shards idle and defeating sharding.
MongoDatabase db = mongoClient.getDatabase("billing");
db.createCollection("transactions");
```

### B. The Production-Grade Sharding Configurator (Production Pattern)
Run administration commands to enable database sharding and configure shard collection keys:

```java
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoDatabase;
import org.bson.Document;

public class ClusterConfigurationService {

    public void configureSharding(MongoClient mongosClient, String dbName, String collectionName, String shardKey) {
        MongoDatabase adminDb = mongosClient.getDatabase("admin");
        
        // 1. Enable sharding on the database
        adminDb.runCommand(new Document("enableSharding", dbName));
        
        // 2. Shard the collection using a hashed key pattern
        Document shardKeys = new Document(shardKey, "hashed");
        Document shardCommand = new Document("shardCollection", dbName + "." + collectionName)
                .append("key", shardKeys);
                
        adminDb.runCommand(shardCommand);
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Balancer Degradation during Peak Write Periods
*   **Why it fails**: The balancer moves chunks between shards during high-traffic write hours. Document migrations consume network bandwidth and CPU, degrading performance.
*   **Mitigation**: Restrict balancer runs to off-peak hours by configuring a balancer window (e.g., from 1:00 AM to 5:00 AM) using administrative commands on the config database.

---

## 5. Socratic Review Questions

### Question 1
Why does MongoDB restrict shard key modifications after a collection has been sharded, and what must you do if you need to change the shard key?

#### Answer
MongoDB relies on the shard key to route operations and distribute data across shards. If a shard key were modified on-the-fly, the database would have to re-evaluate and migrate every chunk in the cluster, causing high write contention and potential data unavailability. To change a shard key, you must create a new sharded collection with the new shard key, migrate the data using an ETL pipeline, and swap the collection names.

---

## 6. Hands-on Challenge: Balancer Configurator Tool

### The Challenge
In this challenge, you will implement a balancer configuration builder in Java.
Your task:
1. Complete `buildBalancerWindowConfig` in `ClusterBalancerService`.
2. Construct and return a Document that configures the balancer window to run between the specified `startHour` and `stopHour`.
3. The configuration document must update the `settings` collection in the `config` database:
   - Target document `_id`: `"balancer"`.
   - Update values: `activeWindow` containing `start` (e.g. `"01:00"`) and `stop` (e.g. `"05:00"`).

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.Document;

public class ClusterBalancerService {

    public Document buildBalancerWindowConfig(String startHour, String stopHour) {
        // TODO: Construct and return the balancer window update configuration document
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

class ClusterBalancerServiceTest {

    @Test
    void testBuildBalancerWindowConfig() {
        ClusterBalancerService service = new ClusterBalancerService();
        Document updateConfig = service.buildBalancerWindowConfig("01:00", "05:00");

        assertNotNull(updateConfig);
        
        Document setBlock = updateConfig.get("$set", Document.class);
        assertNotNull(setBlock);
        
        Document activeWindow = setBlock.get("activeWindow", Document.class);
        assertNotNull(activeWindow);
        assertEquals("01:00", activeWindow.getString("start"));
        assertEquals("05:00", activeWindow.getString("stop"));
    }
}
```
