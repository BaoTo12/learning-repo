# Module 16: Shard Key Selection (Chapter 16)

Welcome class. Today we analyze **Shard Key Selection (CS-529)**.

The single most critical design decision in a sharded cluster is choosing the shard key. A poorly chosen shard key can create write hotspots, uneven storage distribution, and force all queries to scatter-gather, permanently limiting the scalability of the database.

Today we study **Shard Key Distribution & Design**, analyzing cardinality, write hotspots, range vs. hash patterns, and composite key construction in Java.

---

## 1. Academic Lecture: Cardinality and Key Distribution

### 1. Shard Key Attributes
*   **Cardinality**: The number of unique values a shard key can have. Low cardinality keys (like `country` or `gender`) limit the number of chunks that can be created, leading to massive, unsplittable chunks.
*   **Write Distribution (Hotspots)**: A shard key that increases monotonically (like auto-incrementing IDs or dates) routes all new writes to the last chunk on the highest shard. This overwhelms a single host while other shards remain idle.

### 2. Composite and Hashed Keys
To achieve uniform write distribution without losing query efficiency:
*   **Hashed Shard Keys**: MongoDB hashes the key value to distribute writes randomly. However, range queries on hashed keys must scatter-gather.
*   **Composite Shard Keys**: Combining two fields (e.g. `{ companyId: 1, createdAt: 1 }`) ensures high cardinality and keeps data for a specific company grouped together on a single shard.

```text
[Monotonically Increasing Key]
Write 1 (10:01) ──> Shard 3
Write 2 (10:02) ──> Shard 3 (Hotspot: Shards 1 & 2 idle)

[Composite Shard Key: { tenantId, timestamp }]
Write 1 (TenantA, 10:01) ──> Shard 1
Write 2 (TenantB, 10:02) ──> Shard 2 (Balanced distribution)
```

---

## 2. Theory vs. Production Trade-offs

Compare shard key strategies:

| Dimension / Metric | Monotonic Range Key (e.g. `createdAt`) | Hashed Key (e.g. `_id: "hashed"`) | Composite Key (e.g. `{ tenantId: 1, userUuid: 1 }`) |
| :--- | :--- | :--- | :--- |
| **Write Balancing** | Poor (All writes hit one shard) | Excellent (Random distribution) | Excellent (Distributed by prefix) |
| **Targeted Range Reads** | Excellent | Poor (Scatter-gather required) | Excellent (Targeted by prefix) |
| **Jumbo Chunk Risk** | High | Low | Low |
| **Index Overhead** | Low | Low | Moderate |

---

## 3. How to Use: Composite Shard Keys in Java

Let us construct document models for sharding. We contrast a monotonic timestamp key with a robust composite shard key in Java.

### A. The Monotonic Hotspot (Anti-Pattern)
Avoid sharding solely on dates or timestamps:

```java
// DANGER: Sharding the collection on "timestamp" means all incoming inserts
// write to the same max chunk on the primary shard, creating a severe write hotspot.
Document telemetry = new Document("timestamp", new Date())
        .append("deviceId", "DEV-101")
        .append("value", 45.2);
collection.insertOne(telemetry);
```

### B. The Composite Key Pattern (Production Pattern)
Combine a high-cardinality prefix field with the timestamp to distribute writes:

```java
import org.bson.Document;
import java.util.Date;

public class CompositeKeyGenerator {

    public Document createCompositeTelemetry(String tenantId, String deviceId, double value) {
        // Robust Pattern: Constructing a composite shard key: { tenantId: tenantId, deviceId: deviceId }
        // Combined with timestamp, this ensures writes are balanced by tenant/device prefix.
        Document shardKey = new Document("tenantId", tenantId)
                .append("deviceId", deviceId);

        return new Document("_id", shardKey)
                .append("timestamp", new Date())
                .append("value", value);
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Attempting to Update the Shard Key Field
*   **Why it fails**: Executing a write that changes the shard key value of an existing document (e.g. updating `tenantId` from `"tenant-A"` to `"tenant-B"`). In older MongoDB versions, this is blocked; in newer versions, it requires running inside transactions or can trigger complete document migrations.
*   **Mitigation**: Treat shard key fields as immutable. If a value must change, delete the old document and insert a new one.

---

## 5. Socratic Review Questions

### Question 1
Why does a hashed shard key prevent the database from performing targeted range-based queries (e.g., retrieving all records between Date A and Date B)?

#### Answer
MongoDB hashes the shard key value before placing it on a shard. Because hashes are pseudorandom, two contiguous values (like consecutive timestamps) will have very different hashes and reside on different shards. When performing a range query, the router cannot predict which shards hold the data, forcing it to scatter-gather the query across all shards.

---

## 6. Hands-on Challenge: Composite Key Distribution Builder

### The Challenge
In this challenge, you will implement a composite shard key builder in Java.
Your task:
1. Complete `buildShardedTelemetryDoc` in `TelemetryKeyBuilder`.
2. Construct and return a telemetry Document where:
   - The primary key `_id` is a composite Document containing `region` (String) and `deviceType` (String).
   - Add fields `registeredAt` (Date) and `payload` (Document).
   - This composite key ensures data is balanced across shards by region and device type, preventing localized hotspots.

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.Document;
import java.util.Date;

public class TelemetryKeyBuilder {

    public Document buildShardedTelemetryDoc(String region, String deviceType, Date date, Document payload) {
        // TODO: Construct and return the document with composite _id
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
import java.util.Date;
import static org.junit.jupiter.api.Assertions.*;

class TelemetryKeyBuilderTest {

    @Test
    void testBuildShardedTelemetryDoc() {
        TelemetryKeyBuilder builder = new TelemetryKeyBuilder();
        Date now = new Date();
        Document payload = new Document("metric", 88);
        
        Document doc = builder.buildShardedTelemetryDoc("us-east", "sensor-io", now, payload);

        assertNotNull(doc);
        assertEquals(now, doc.getDate("registeredAt"));
        assertEquals(payload, doc.get("payload"));
        
        // Verify composite key
        Document compositeId = doc.get("_id", Document.class);
        assertNotNull(compositeId);
        assertEquals("us-east", compositeId.getString("region"));
        assertEquals("sensor-io", compositeId.getString("deviceType"));
    }
}
```
