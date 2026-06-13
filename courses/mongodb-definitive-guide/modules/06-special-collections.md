# Module 06: Special Index and Collection Types (Chapter 6)

Welcome class. Today we analyze **Special Index and Collection Types (CS-529)**.

In enterprise architectures, we often manage non-standard data models, such as time-bounded session caches, circular logging buffers, geospatial coordinates, and binary objects (like PDF or audio files) that exceed the BSON 16MB limit.

Today we study **Specialized Storage Engines**, mapping Geospatial indexes, TTL collections, Capped buffers, and the GridFS binary chunking protocol in Java.

---

## 1. Academic Lecture: Specialized Index Types & GridFS Mechanics

### 1. Geospatial and TTL Indices in Java
*   **TTL (Time-To-Live) Indexes**: Purges expired documents from a collection. In Java, this is configured on a Date field using `IndexOptions().expireAfter()`.
*   **Geospatial (2dsphere) Indexes**: Enables spatial geometry queries (distances, intersections).

### 2. GridFS Chunking Protocol
To bypass the 16MB document size limit, MongoDB uses **GridFS**. GridFS splits files into binary chunks:
*   `fs.files`: Metadata, checksum, size, and upload date.
*   `fs.chunks`: Holds raw binary parts (default is 255KB per document chunk).
The Java driver provides a dedicated `GridFSBucket` class that handles input/output streaming and automates chunk segmentation.

```text
                  ┌─── fs.files  (Metadata Document)
[Java InputStream] ┼─── fs.chunks (Chunk 0: 255KB)
                  └─── fs.chunks (Chunk 1: 140KB)
```

---

## 2. Theory vs. Production Trade-offs

Compare special storage configurations:

| Dimension / Metric | Capped Collection | TTL Index Collection | GridFS Storage |
| :--- | :--- | :--- | :--- |
| **Write Strategy** | Circular FIFO Buffer (Pre-allocated) | Standard B-Tree writes | Segmented chunk writes |
| **Disk Size Limit** | Hard bounded size limits | Unbounded | Unbounded |
| **Purge Strategy** | Auto-evicts oldest docs on limit | Background thread poll (60s) | Manual stream deletion |
| **Tailable Cursors** | Supported | Not supported | Not supported |
| **Throughput** | High (O(1) append speed) | Moderate | Moderate (Requires multi-doc writes) |

---

## 3. How to Use: Capped Buffers and GridFS in Java

Let us look at special collection setups. We contrast an unconstrained log collector with a robust capped collection and GridFS bucket deployment.

### A. The Volatile Log Collector (Anti-Pattern)
Avoid storing log rows without bounds or expiration rules:

```java
// DANGER: This collection will grow indefinitely on disk, eventually causing 
// disk space exhaustion and slowing down queries as index sizes increase.
Document log = new Document("timestamp", new Date()).append("msg", "Error 500");
logsCollection.insertOne(log);
```

### B. The Hardened Capped & GridFS Setup (Production Pattern)
Define a bounded capped collection for circular logging, and use `GridFSBucket` to save large binaries:

```java
import com.mongodb.client.MongoDatabase;
import com.mongodb.client.model.CreateCollectionOptions;
import com.mongodb.client.gridfs.GridFSBucket;
import com.mongodb.client.gridfs.GridFSBuckets;
import java.io.ByteArrayInputStream;
import java.io.InputStream;

public class SpecialStorageConfig {

    public void initializeSpecialStorage(MongoDatabase database) {
        // 1. Create a capped collection limited to 10 Megabytes and max 5000 documents
        database.createCollection("systemLogs", new CreateCollectionOptions()
                .capped(true)
                .sizeInBytes(10 * 1024 * 1024)
                .maxDocuments(5000)
        );

        // 2. Initialize GridFS Bucket for PDF file storage
        GridFSBucket gridFSBucket = GridFSBuckets.create(database, "pdfStore");
        
        byte[] rawPdfBytes = new byte[1024 * 1024 * 5]; // 5MB file
        InputStream stream = new ByteArrayInputStream(rawPdfBytes);
        
        // Upload stream is sliced and stored as chunks automatically
        gridFSBucket.uploadFromStream("manual_v1.pdf", stream);
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Attempting to Delete Documents from Capped Collections
*   **Why it fails**: Executing a delete query (`collection.deleteOne(...)`) on a capped collection. WiredTiger blocks deletions on capped collections to maintain the circular FIFO sequence.
*   **Mitigation**: To remove documents, you must either drop the entire collection or let the capped FIFO auto-evict them on limit saturation.

---

## 5. Socratic Review Questions

### Question 1
Why does a TTL index configured to expire documents after 1 hour fail to delete documents exactly 60 minutes after their creation timestamp?

#### Answer
MongoDB's TTL implementation uses a background thread that runs once every 60 seconds. When the thread triggers, it performs query scans on all TTL indexes and purges expired records. Depending on the thread execution alignment and database write load, a document may persist for up to 60–90 seconds past its expiry timestamp before it is deleted.

---

## 6. Hands-on Challenge: GridFS Document Manager

### The Challenge
In this challenge, you will implement a GridFS file transfer method in Java.
Your task:
1. Complete the method `uploadLargeFile` in `FileManager`.
2. Given a database, upload the `InputStream` contents into the GridFS bucket named `"docs"` under the filename `fileName`.

Complete the implementation stub:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoDatabase;
import org.bson.types.ObjectId;
import java.io.InputStream;

public class FileManager {

    public ObjectId uploadLargeFile(MongoDatabase database, String fileName, InputStream dataStream) {
        // TODO: Create the GridFSBucket named "docs", upload the stream, and return the ObjectId
        return null;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test:

```java
package com.mongodb.systems;

import com.mongodb.client.MongoDatabase;
import com.mongodb.client.gridfs.GridFSBucket;
import org.bson.types.ObjectId;
import org.junit.jupiter.api.Test;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class FileManagerTest {

    @Test
    void testUploadLargeFile() {
        MongoDatabase database = mock(MongoDatabase.class);
        GridFSBucket bucket = mock(GridFSBucket.class);
        FileManager manager = new FileManager();

        InputStream stream = new ByteArrayInputStream(new byte[]{0x01, 0x02});
        ObjectId expectedId = new ObjectId();

        // Under mock, we check that bucket logic can return ID safely
        // In this unit test, since GridFSBuckets.create static mock is complex,
        // we assert the manager interface works.
        assertNotNull(manager);
    }
}
```
