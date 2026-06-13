# Module 11: Components of a Replica Set (Chapter 11)

Welcome class. Today we analyze **Components of a Replica Set (CS-529)**.

Behind a replica set's high availability lies a distributed state machine. Nodes must constantly coordinate data synchronization, evaluate node health, run leader elections, and resolve data divergence (rollbacks) without manual intervention.

Today we study **Replica Set Synchronization & Elections**, analyzing Oplog syncing mechanics, heartbeat checks, Raft-like election protocols, and rollback resolution boundaries in Java.

---

## 1. Academic Lecture: Oplog Syncing & Rollback Boundaries

### 1. Synchronization Mechanics
*   **Initial Sync**: When a secondary node joins a cluster, it drops its databases, copies all data from a source node, and replays all oplog operations generated during the copy.
*   **Replication Sync**: Secondaries continuously tail the oplog of their sync source (which can be the primary or another secondary using chaining).

### 2. Elections & Rollback Files
*   **Elections**: Nodes exchange heartbeats once every 2 seconds. If a primary fails to respond for 10 seconds, secondaries initiate an election. A node must receive votes from a majority of the replica set's total voting members to become the primary.
*   **Rollbacks**: If a primary commits writes to its local storage but crashes before they replicate to secondaries, the new primary will have divergent data. When the old primary recovers, it must **rollback** its un-replicated writes, saving them to a `.bson` rollback file in the `rollback/` directory.

```text
[Node A (Primary crashes)] ──> Write "Data X" (un-replicated)
[Node B elected Primary] ───> Write "Data Y"
[Node A recovers] ──────────> Detects mismatch ──> Rollback "Data X" to file ──> Syncs "Data Y"
```

---

## 2. Theory vs. Production Trade-offs

Compare replication sync parameters:

| Dimension / Metric | Direct Primary Syncing | Chained Syncing (Secondary-to-Secondary) |
| :--- | :--- | :--- |
| **Primary CPU Load** | High (All nodes tail primary) | Low (Secondaries tail other secondaries) |
| **Network Replication Lag**| Minimal | Higher (Cascading sync delay) |
| **Sync Source Resiliency**| High | Vulnerable to transit hop outages |
| **Inter-Data Center Cost** | High (Cross-WAN traffic from all nodes) | Low (One node pulls cross-WAN, others sync locally) |
| **Execution Complexity** | Low | High (Requires dynamic sync graph adjustments) |

---

## 3. How to Use: Analyzing Election States in Java

Let us monitor replica set status. We compare a naive deployment (blind to replication lag) with a monitoring check that identifies lag bottlenecks using Java.

### A. The Blind Connection (Anti-Pattern)
Avoid reading from secondaries without checking node synchronization health:

```java
// DANGER: This connection reads from secondaries without verifying lag.
// If secondary sync is delayed by minutes, the client will read stale data.
MongoClient mongoClient = MongoClients.create("mongodb://localhost:27017/?readPreference=secondary");
MongoDatabase db = mongoClient.getDatabase("prod");
Document user = db.getCollection("users").find(Filters.eq("_id", 1)).first();
```

### B. The Hardened Sync Status Check (Production Pattern)
Run administrative checks to monitor replication lag and sync source hierarchies:

```java
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoDatabase;
import org.bson.Document;
import java.util.Date;
import java.util.List;

public class ReplicaSetMonitor {

    public void inspectReplicationLag(MongoClient mongoClient) {
        MongoDatabase adminDb = mongoClient.getDatabase("admin");
        Document status = adminDb.runCommand(new Document("replSetGetStatus", 1));
        
        List<Document> members = status.getList("members", Document.class);
        Document primary = members.stream()
                .filter(m -> m.getInteger("state") == 1) // 1 = PRIMARY
                .findFirst()
                .orElse(null);

        if (primary == null) {
            System.out.println("Warning: Primary node not found.");
            return;
        }

        Date primaryOptime = primary.getDate("optimeDate");

        for (Document member : members) {
            if (member.getInteger("state") == 2) { // 2 = SECONDARY
                Date secondaryOptime = member.getDate("optimeDate");
                long lagMs = primaryOptime.getTime() - secondaryOptime.getTime();
                System.out.printf("Node: %s | Lag: %d ms | Sync Source: %s%n",
                        member.getString("name"),
                        lagMs,
                        member.getString("syncingTo")
                );
            }
        }
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Oplog Size Saturation (Oplog Overrun)
*   **Why it fails**: If a replica set secondary goes offline for maintenance, and the primary processes a high volume of writes, the primary's Oplog can roll over (exceed its max size), overwriting historical logs. When the secondary recovers, its sync point is gone, forcing it to undergo a costly **Initial Sync**.
*   **Mitigation**: Size Oplogs conservatively. Oplogs should hold at least 24–48 hours of write volume. Use the `replSetGetStatus` command in Java to inspect oplog windows.

---

## 5. Socratic Review Questions

### Question 1
Why does a replica set election fail if a network partition splits a 5-node cluster into a 2-node group and a 3-node group?

#### Answer
MongoDB requires a vote from an absolute majority of the replica set's total configured members to elect a primary. For a 5-node cluster, the majority threshold is 3. In the 2-node partition, no primary can be elected. In the 3-node partition, the nodes can establish a majority (3 votes) and elect a primary. This guarantees that only one partition can write, preventing split-brain conflicts.

---

## 6. Hands-on Challenge: Evaluating Rollback Risks

### The Challenge
In this challenge, you will implement a replica set status check.
Your task:
1. Complete the method `checkReplicationLag` in `ReplicaSetLagEvaluator`.
2. The method must run `replSetGetStatus` command on the admin database.
3. Compute the replication lag for each member in milliseconds compared to the primary's `optimeDate`.
4. If any secondary member has replication lag exceeding 10,000 milliseconds, return `false` (alert condition); otherwise, return `true`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoDatabase;
import org.bson.Document;

public class ReplicaSetLagEvaluator {

    public boolean checkReplicationLag(MongoDatabase adminDatabase) {
        // TODO: Run replSetGetStatus command, extract members list, locate Primary,
        // calculate lag for each Secondary, and return false if lag > 10000ms.
        return true;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoDatabase;
import org.bson.Document;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Date;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class ReplicaSetLagEvaluatorTest {

    @Test
    void testReplicationLagCheck() {
        MongoDatabase adminDb = mock(MongoDatabase.class);
        
        // Mock replica set status response
        Date now = new Date();
        Date staleDate = new Date(now.getTime() - 15000); // 15 seconds lag

        Document memberPrimary = new Document("name", "node1:27017")
                .append("state", 1) // PRIMARY
                .append("optimeDate", now);

        Document memberSecondary = new Document("name", "node2:27017")
                .append("state", 2) // SECONDARY
                .append("optimeDate", staleDate);

        Document replStatus = new Document("members", List.of(memberPrimary, memberSecondary));
        
        when(adminDb.runCommand(any(Document.class))).thenReturn(replStatus);

        ReplicaSetLagEvaluator evaluator = new ReplicaSetLagEvaluator();
        boolean isHealthy = evaluator.checkReplicationLag(adminDb);

        assertFalse(isHealthy, "Should return false because replication lag is 15 seconds (> 10s)");
    }
}
```
