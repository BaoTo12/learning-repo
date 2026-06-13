# Module 10: Setting Up a Replica Set (Chapter 10)

Welcome class. Today we analyze **Setting Up a Replica Set (CS-529)**.

A single database server represents a single point of failure (SPOF). MongoDB solves this by using **Replica Sets**—groups of database nodes that synchronize datasets, providing automatic failover and read/write separations.

Today we study **Replica Set Cluster Topologies**, analyzing node classifications, elections, arbiters, and member configurations.

---

## 1. Academic Lecture: High Availability & Voting Members

### 1. Replica Set Members
A replica set consists of a group of nodes that coordinate state:
*   **Primary**: The single node that accepts writes and records them in its Oplog (operations log).
*   **Secondaries**: Nodes that replicate the primary's oplog. Secondaries are read-only.

### 2. Node Configurations
*   **Hidden Members**: Replicate data and vote in elections, but are invisible to client drivers. Used for analytical reports or backups.
*   **Arbiters**: Do not replicate data; they only exist to vote in elections when the number of members is even, preventing tie votes.

```text
                  ┌───────────────┐
                  │ Primary Node  │ (Accepts Writes)
                  └──────┬────────┘
                         │ (Oplog Sync)
            ┌────────────┴────────────┐
            ▼                         ▼
    ┌───────────────┐         ┌───────────────┐
    │ Secondary 1   │         │ Hidden Sec    │ (Priority: 0, Hidden: true)
    └───────────────┘         └───────────────┘
```

---

## 2. Theory vs. Production Trade-offs

Compare replica set member configurations:

| Dimension / Metric | Standard Secondary | Hidden Secondary | Election Arbiter |
| :--- | :--- | :--- | :--- |
| **Data Replication** | Yes | Yes | No |
| **Priority Range** | 1 to 1000 (can become primary) | Locked to 0 (cannot become primary) | Locked to 0 |
| **Votes in Elections**| Yes | Yes | Yes |
| **Client Visibility** | Visible (Can handle reads) | Invisible (Protected from reads) | Invisible |
| **Host System Costs** | High (Storage, CPU, RAM) | High (Storage, CPU, RAM) | Very Low (No data storage) |

---

## 3. How to Use: Replica Configuration in Java

Let us construct replica set configurations. We contrast a naive replica set configuration (vulnerable to network splits) with a robust multi-region hidden member configuration defined in Java.

### A. The Even-Member Configuration (Anti-Pattern)
Avoid configuring replica sets with an even number of voting members without an arbiter:

```java
// DANGER: If a network split occurs, neither partition can achieve a majority vote (>50%).
// The replica set will fail to elect a primary, locking the cluster in read-only mode.
Document config = new Document("_id", "rs0")
    .append("members", List.of(
        new Document("_id", 0).append("host", "mongo1:27017"),
        new Document("_id", 1).append("host", "mongo2:27017")
    ));
```

### B. The Hardened Odd-Member Configuration (Production Pattern)
Configure an odd number of voting nodes, assigning priority 0 to hidden backup nodes:

```java
import org.bson.Document;
import java.util.List;

// Robust Pattern: Odd number of voting members (3 nodes).
// Node 2 is a dedicated hidden backup node that cannot become primary.
Document config = new Document("_id", "rs0")
    .append("members", List.of(
        new Document("_id", 0).append("host", "mongo-primary:27017").append("priority", 2),
        new Document("_id", 1).append("host", "mongo-secondary:27017").append("priority", 1),
        new Document("_id", 2).append("host", "mongo-backup:27017")
                .append("priority", 0)
                .append("hidden", true)
    ));
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Placing Arbiters on the Same Host as Data Nodes
*   **Why it fails**: Deploying an Arbiter on the same physical server VM as a secondary node. If that physical host crashes, you lose **two** members of the replica set at the same time. This can cause the remaining nodes to lose their voting majority, forcing the primary to step down to secondary.
*   **Mitigation**: Always place arbiters on independent, isolated hosts.

---

## 5. Socratic Review Questions

### Question 1
Why does a hidden replica set member require its election priority setting to be explicitly configured as `priority: 0`?

#### Answer
If a hidden member had `priority > 0`, it could be elected as the cluster primary. If a hidden member became the primary, client drivers would be unable to find or connect to it, locking all write operations across the application.

---

## 6. Hands-on Challenge: Java Configuration Builder

### The Challenge
In this challenge, you will implement a replica set configuration builder in Java.
Your task:
1. Complete `buildReplicaSetConfig` in `ReplicaSetService`.
2. Construct and return a configuration Document for a replica set named `rs-prod`.
3. Members must include:
   - Node 0: `mongo1:27017` (priority: 2)
   - Node 1: `mongo2:27017` (priority: 1)
   - Node 2: `mongo3:27017` (hidden analytical node, priority: 0)

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.Document;

public class ReplicaSetService {

    public Document buildReplicaSetConfig(String replicaSetName, String host1, String host2, String host3) {
        // TODO: Construct and return the replica set config document
        return null;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test:

```java
package com.mongodb.systems;

import org.bson.Document;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class ReplicaSetServiceTest {

    @Test
    void testBuildReplicaSetConfig() {
        ReplicaSetService service = new ReplicaSetService();
        Document config = service.buildReplicaSetConfig("rs-prod", "m1:27017", "m2:27017", "m3:27017");

        assertNotNull(config);
        assertEquals("rs-prod", config.getString("_id"));
        
        List<Document> members = config.getList("members", Document.class);
        assertEquals(3, members.size());
        
        Document m3 = members.get(2);
        assertEquals(0, m3.getInteger("priority"));
        assertTrue(m3.getBoolean("hidden"));
    }
}
```
