# Module 17: Sharding Administration (Chapter 17)

Welcome class. Today we analyze **Sharding Administration (CS-529)**.

Managing sharded clusters requires active maintenance: inspecting cluster health, analyzing chunk distributions, splits, and resolving the challenge of jumbo chunks.

Today we study **Sharded Cluster Administration**, analyzing shard status command tools, chunk splits, balancer window logs, and jumbo chunk mitigations in Java.

---

## 1. Academic Lecture: Shard Status & Jumbo Chunk Operations

### 1. Diagnostic Commands
To monitor sharding health, we execute commands on the `admin` database:
*   `shardingState`: Confirms if the active connection is a member of a sharded cluster.
*   `balancerStatus`: Reports whether the balancer is active or currently executing migrations.
*   `flushRouterConfig`: Clears the query router's cached routing tables, forcing it to reload metadata from config servers.

### 2. Jumbo Chunks
A chunk becomes a **Jumbo Chunk** when its size exceeds the configured maximum chunk size (default 64MB) but all documents inside have the same shard key. Because MongoDB cannot split a single shard key value across chunks, the balancer cannot migrate it, creating storage imbalances.

```text
[Chunk Size: 70MB]
All records: { shardKey: "BigTenant" } ──> [Cannot Split (Jumbo)] ──> [Balancer Blocks Migration]
```

---

## 2. Theory vs. Production Trade-offs

Compare chunk maintenance strategies:

| Dimension / Metric | Automatic Chunk Splitting | Manual Split Commands | Shard Key Redesign (ETL) |
| :--- | :--- | :--- | :--- |
| **Write Blocking** | Low | Low | High (Migration lock) |
| **System Load** | Low (Background check on writes) | Moderate (Admin execution) | High (Data rewriting) |
| **Jumbo Chunk Resolution** | Cannot resolve jumbo chunks | Can split if key values differ | Resolves jumbo chunks permanently |
| **Implementation Safety**| High | Moderate | Low (Requires app downtime) |

---

## 3. How to Use: Checking Sharding Metadata in Java

Let us inspect cluster status. We contrast a blind client connection with a diagnostic service that reads sharding configurations using Java.

### A. The Blind Client Query (Anti-Pattern)
Avoid operating inside a sharded cluster without checking routing table caches:

```java
// DANGER: If the router has stale metadata, queries target incorrect shards, 
// forcing network redirects. The client is blind to these routing overheads.
MongoCollection<Document> collection = client.getDatabase("prod").getCollection("orders");
collection.insertOne(new Document("storeId", "ST-01").append("amount", 20.5));
```

### B. The Cluster Shard State Checker (Production Pattern)
Verify active connection states and flush routing caches dynamically:

```java
import com.mongodb.client.MongoDatabase;
import org.bson.Document;

public class ShardingAdminService {

    public void checkAndFlushRouter(MongoDatabase adminDb) {
        // 1. Inspect if sharding is enabled on the target node
        Document shardingState = adminDb.runCommand(new Document("shardingState", 1));
        boolean isSharded = shardingState.getBoolean("enabled", false);

        if (isSharded) {
            System.out.println("Node is sharded. Flush routing cache to prevent stale routes.");
            
            // 2. Flush router configuration caches
            adminDb.runCommand(new Document("flushRouterConfig", 1));
        } else {
            System.out.println("Connection targeting standalone / replica set node.");
        }
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Ignoring Balancer Locks
*   **Why it fails**: Attempting to run a manual chunk migration (`moveChunk`) or splitting database chunks while the balancer is actively moving chunks. This can trigger lock collisions, failing both operations and overloading config servers.
*   **Mitigation**: Verify the balancer is inactive (`balancerStatus`) before running manual administrative splits or migrations.

---

## 5. Socratic Review Questions

### Question 1
Why are jumbo chunks problematic for a sharded cluster, and how does selecting a high-cardinality shard key prevent them?

#### Answer
Jumbo chunks are problematic because the balancer cannot migrate them to other shards. Over time, shards holding jumbo chunks accumulate excess data and experience higher write/read traffic, creating performance bottlenecks. A high-cardinality shard key (e.g. `userId`) ensures that individual key values map to small document sizes, allowing chunks to be split cleanly and migrated dynamically.

---

## 6. Hands-on Challenge: Jumbo Chunk Identifier

### The Challenge
In this challenge, you will implement a sharded metadata analyser in Java.
Your task:
1. Complete the method `identifyJumboChunks` in `ShardedClusterMonitor`.
2. Query the `chunks` collection in the `config` database.
3. Iterate through chunk documents and count how many documents have the `jumbo` field set to `true`.
4. Return the total count of jumbo chunks.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoCollection;
import org.bson.Document;

public class ShardedClusterMonitor {

    public long identifyJumboChunks(MongoCollection<Document> chunksCollection) {
        // TODO: Count documents in chunksCollection where the "jumbo" field is true.
        return 0;
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
import static org.junit.jupiter.api.Assertions.*;

class ShardedClusterMonitorTest {

    @SuppressWarnings("unchecked")
    @Test
    void testIdentifyJumboChunks() {
        MongoCollection<Document> chunks = mock(MongoCollection.class);
        
        when(chunks.countDocuments(any(Document.class))).thenReturn(5L);

        ShardedClusterMonitor monitor = new ShardedClusterMonitor();
        long jumboCount = monitor.identifyJumboChunks(chunks);

        assertEquals(5L, jumboCount, "Should count 5 jumbo chunks");
        verify(chunks, times(1)).countDocuments(eq(new Document("jumbo", true)));
    }
}
```
