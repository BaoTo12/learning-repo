# Module 13: Administration of a Replica Set (Chapter 13)

Welcome class. Today we analyze **Administration of a Replica Set (CS-529)**.

Maintaining high-availability database clusters requires routine maintenance, such as updating replica set configurations, resizing oplog boundaries, and building indexes without degrading cluster performance.

Today we study **Replica Set Cluster Administration**, analyzing reconfigurations, oplog adjustments, and rolling index builds in Java.

---

## 1. Academic Lecture: Rolling Configurations & Oplog Resizing

### 1. Administrative Reconfiguration (`replSetReconfig`)
To modify member hostnames, priorities, or hidden states, we execute a `replSetReconfig` command. The primary validates the configuration changes and propagates them across the cluster. If the reconfiguration changes voting weights, it may trigger a brief election.

### 2. Rolling Index Builds
Building an index on a large collection consumes CPU and blocks writes. In production, indexes are built using a **rolling procedure**:
1. Take a secondary offline.
2. Build the index locally as a standalone node.
3. Restart the secondary as a cluster member and let it catch up.
4. Repeat for all secondaries.
5. Force the primary to step down, and repeat the process on the old primary.

```text
[Step 1] Stop Secondary B ──> Restart Standalone ──> Build Index ──> Restart Secondary
[Step 2] Stop Secondary C ──> Restart Standalone ──> Build Index ──> Restart Secondary
[Step 3] Stepdown Primary ──> Standalone Old Prim ─> Build Index ──> Restart as Secondary
```

---

## 2. Theory vs. Production Trade-offs

Compare index construction patterns:

| Index Construction Strategy | Primary Write Blocking | Network Rebuilding Overhead | Execution Cost | Implementation Safety |
| :--- | :--- | :--- | :--- | :--- |
| **Foreground Index Build** | Extreme (Blocks all reads/writes) | Low | Low | Very Low (Crashes production) |
| **Background Index Build** | Low (Deprecated in modern versions)| Low | Low | Low |
| **Rolling Index Build** | None | High (Synchronizing caught-up lag) | High (Manual host stepdowns) | Excellent |

---

## 3. How to Use: Reconfiguring Replica Sets in Java

Let us construct administration actions. We contrast a destructive reconfiguration with a safe, state-aware member configuration update using Java.

### A. The Destructive Reconfig (Anti-Pattern)
Avoid updating member lists directly without validating active states:

```java
// DANGER: Reconfiguring replica sets by overwriting member IDs or changing 
// vote thresholds without fetching active configs will drop nodes from the cluster.
Document badConfig = new Document("_id", "prodRS")
    .append("members", List.of(new Document("_id", 0).append("host", "mongo1:27017")));
adminDb.runCommand(new Document("replSetReconfig", badConfig));
```

### B. The Production-Grade Configuration Adjuster (Production Pattern)
Fetch the existing configuration document, modify the target members array, increment the version counter, and apply the update:

```java
import com.mongodb.client.MongoDatabase;
import org.bson.Document;
import java.util.List;

public class ReplicaSetConfigService {

    public void promoteSecondaryNode(MongoDatabase adminDb, String hostToPromote) {
        // 1. Fetch current config
        Document configResult = adminDb.runCommand(new Document("replSetGetConfig", 1));
        Document config = configResult.get("config", Document.class);
        
        // 2. Increment version number (Required by replSetReconfig)
        int currentVersion = config.getInteger("version");
        config.put("version", currentVersion + 1);
        
        // 3. Locate member and update priority
        List<Document> members = config.getList("members", Document.class);
        for (Document member : members) {
            if (member.getString("host").equals(hostToPromote)) {
                member.put("priority", 10); // Higher priority
            }
        }
        
        // 4. Apply reconfig command
        adminDb.runCommand(new Document("replSetReconfig", config));
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Reconfiguring Over a Degraded Cluster
*   **Why it fails**: Initiating a `replSetReconfig` command when a majority of the replica set members are offline. Since a majority must agree on the new config, the command will block and timeout, occasionally leaving the cluster in an inconsistent administrative state.
*   **Mitigation**: Confirm that a majority of voting members are online and active before executing any reconfiguration commands.

---

## 5. Socratic Review Questions

### Question 1
Why does MongoDB require the replica set configuration version number (`version`) to be strictly incremented on every `replSetReconfig` command execution?

#### Answer
The `version` field acts as an optimistic locking token. If multiple administrators attempt to reconfigure the cluster simultaneously, the version increment checks prevent out-of-order changes from overwriting each other. A member node will reject any configuration package that does not contain a version number higher than its active configuration version.

---

## 6. Hands-on Challenge: Admin Node Configuration Tool

### The Challenge
In this challenge, you will implement a replica set member configuration modifier in Java.
Your task:
1. Complete `addArbitrationMember` in `ReplicaSetAdminService`.
2. Retrieve the active configuration using `replSetGetConfig`.
3. Add a new member document to the `members` array with the provided `arbiterHost` address.
4. Set the new member's `_id` to the next available integer index.
5. Set `arbiterOnly` to `true` and `priority` to `0` for the new member.
6. Increment the configuration's `version` field.
7. Return the modified configuration Document (without executing the final reconfig command, to facilitate unit testing).

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.Document;

public class ReplicaSetAdminService {

    public Document addArbitrationMember(Document configResult, String arbiterHost) {
        // TODO: Extract the "config" subdocument, increment version, append new member with arbiter settings, and return the modified config document.
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
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class ReplicaSetAdminServiceTest {

    @Test
    void testAddArbitrationMember() {
        // Mock configuration input document
        Document member0 = new Document("_id", 0).append("host", "mongo1:27017");
        Document config = new Document("_id", "rs-prod")
                .append("version", 5)
                .append("members", List.of(member0));
        Document configResult = new Document("config", config);

        ReplicaSetAdminService service = new ReplicaSetAdminService();
        Document updatedConfig = service.addArbitrationMember(configResult, "arbiter1:27017");

        assertNotNull(updatedConfig);
        assertEquals(6, updatedConfig.getInteger("version"));
        
        List<Document> members = updatedConfig.getList("members", Document.class);
        assertEquals(2, members.size());
        
        Document addedNode = members.get(1);
        assertEquals(1, addedNode.getInteger("_id"));
        assertEquals("arbiter1:27017", addedNode.getString("host"));
        assertTrue(addedNode.getBoolean("arbiterOnly"));
        assertEquals(0, addedNode.getInteger("priority"));
    }
}
```
