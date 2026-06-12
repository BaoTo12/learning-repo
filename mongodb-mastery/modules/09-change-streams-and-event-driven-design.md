# Module 09: Change Streams & Event-Driven Design

## 1. What Problem This Module Solves
In modern event-driven architectures, system components must react to database changes in real time. For example, updating search indexes, sending notification emails, or clearing cache entries must happen immediately when a write occurs. Polling the database for updates is slow, consumes substantial CPU resources, and creates query latency.

MongoDB provides **Change Streams** to stream database modifications directly to application services in real time. A senior engineer must understand change stream resume tokens, performance considerations when storing pre- and post-images, early-stage aggregation filtering, and how to integrate change streams with message brokers like Apache Kafka. Failing to manage change streams correctly can lead to missed events, duplicate processing, and high network bandwidth consumption.

---

## 2. Why This Topic Matters
Change streams allow applications to stream database updates without polling. However, change streams rely on the replication oplog. If your change stream consumer goes offline and the oplog rolls over before the consumer recovers, the stream cannot resume, resulting in lost events.

Understanding how to decode and cache **Resume Tokens**, configure pre- and post-images for document state comparison, and implement dead-letter queue (DLQ) retry mechanisms in consumers is essential for building resilient, event-driven microservices.

---

## 3. Core Concepts & Internals

### 3.1 Resume Tokens: Decoded Structure & Resumability
MongoDB change streams are resumable. If a client disconnects, it can resume streaming from the exact failure point without missing or duplicating events. This is managed using a **Resume Token** (`_id` field in the change stream event).

#### Resume Token Composition:
The resume token is a BSON binary object. If converted to hex, it reveals three metadata blocks:
1.  **Timestamp (`ts`)**: A 64-bit value representing when the write occurred (4-byte seconds epoch + 4-byte increment).
2.  **UUID**: The unique identifier of the collection being watched.
3.  **Document Key**: The `_id` of the document that was modified.

```
       Resume Token (_id) Binary Representation
 ┌─────────────────┬─────────────────┬─────────────────┐
 │   Timestamp     │ Collection UUID │  Document Key   │
 │   (ts: 8 bytes) │   (16 bytes)    │   (ObjectId)    │
 └─────────────────┴─────────────────┴─────────────────┘
```

#### Resuming a Stream:
When initializing a change stream, you can pass the resume token using `resumeAfter` or `startAfter` parameters:
*   `resumeAfter`: Resumes the stream after the event specified by the token.
*   `startAfter`: Similar to `resumeAfter`, but allows resuming after an invalidate event (e.g. if the watched collection was dropped).
*   *Replication Oplog Dependency*: Change streams read from the replication oplog (`local.oplog.rs`). If a consumer goes offline longer than the oplog window, the resume token's timestamp will be overwritten, and the change stream will fail to resume. In this case, the application must perform a full recovery.

---

### 3.2 Performance Optimization: Pre- and Post-Images
By default, change stream update events only return the delta of the modified fields. If the application needs to compare the document state before and after the update, you must enable **Pre- and Post-Images**.

#### Database Overhead:
*   **Pre-Image**: The state of the document before the update.
*   **Post-Image**: The state of the document after the update.
*   *Performance Impact*: When pre- or post-images are enabled on a collection (`changeStreamPreAndPostImages`), MongoDB writes the full document states to the replication oplog during updates. This increases write latency, consumes more disk space, and accelerates oplog rollover. Enable pre/post-images only when necessary.

---

### 3.3 Early Filtering with Aggregation Pipelines
Change streams can take an optional aggregation pipeline to filter and shape events before they are sent over the network to the client driver.

#### Why Filter Early?
If you watch a collection with high write volume, streaming every event consumes network bandwidth and CPU cycles. You should apply filtering stages (like `$match` or `$project`) early in your pipeline so the database engine discards irrelevant events before sending them to the client.

```
 [Replica Oplog] ──> [Filter Early: $match] ──> [Filter Early: $project] ──> [Network Socket]
  (All Writes)        (Discard non-updates)       (Project required fields)    (Only matching events)
```

---

### 3.4 Scaling Change Streams & Sharded Clusters
In a sharded cluster, change streams are coordinated across all shards.
*   **Global Change Streams**: A change stream opened on a `mongos` router merges events from all shards, sorting them by their logical cluster time (`$clusterTime`).
*   **Replication Secondaries**: By default, change streams read from the primary node. To offload read traffic, you can configure the stream to read from secondary nodes using read preferences:
    ```javascript
    const changeStream = db.collection.watch(pipeline, { readPreference: { mode: "secondary" } });
    ```
*   *Replication Lag Risk*: If a secondary sync lags behind other nodes, the change stream may delay delivering events until the secondary catches up to the logical cluster time.

---

### 3.5 The Outbox Pattern with Change Streams
In microservice architectures, writing to a database and publishing an event to a message broker must happen atomically. The **Transactional Outbox Pattern** ensures reliable event delivery by writing events to an `outbox` collection within the same database transaction as the primary write.

```
 [Application Write] ──> [Transaction Block] ──> Write Account doc
                             │
                             └── (Same Transaction) ──> Write Outbox event
                                                            │
                                                            ▼
                                                     [MongoDB Oplog]
                                                            │
                                                            ▼ (Watch Outbox Collection)
                                                     [Change Stream Worker]
                                                            │
                                                            ▼
                                                    [Publish to Broker]
```

1.  **Atomic Transaction**: The application writes the primary business document (e.g. order document) and inserts an event record into an `outbox` collection inside the same database transaction.
2.  **Change Stream Listener**: A background change stream worker watches the `outbox` collection.
3.  **Reliable Delivery**: The worker reads events from the stream, publishes them to the message broker, and deletes the outbox records or marks them as processed, guaranteeing at-least-once delivery.

---

## 4. Practical Examples

### Configuring Pre/Post-Images in the Shell
```javascript
// Enable pre- and post-images on the orders collection
db.runCommand({
  collMod: "orders",
  changeStreamPreAndPostImages: { enabled: true }
});
```

---

### Transactional Outbox Publisher Script (Node.js)
The following Node.js script demonstrates how to implement the Outbox Pattern, writing business changes and outbox events within a transaction, alongside a change stream worker that reads and processes these events.

```javascript
/**
 * Transactional Outbox Worker
 * Writes outbox events and processes them via Change Streams.
 */
const { MongoClient } = require('mongodb');
const log = require('console');

class OutboxPublisher {
  constructor(uri) {
    this.client = new MongoClient(uri);
  }

  async start() {
    await this.client.connect();
    this.db = this.client.db('shop_db');
    this.orders = this.db.collection('orders');
    this.outbox = this.db.collection('outbox');
    log.info("Outbox publisher connected.");
  }

  async placeOrder(orderId, customerId, amount) {
    const session = this.client.startSession();
    try {
      await session.withTransaction(async () => {
        // 1. Insert order document
        await this.orders.insertOne(
          { _id: orderId, customerId, amount, status: "PENDING", createdAt: new Date() },
          { session }
        );

        // 2. Insert outbox event in same transaction
        await this.outbox.insertOne(
          {
            aggregateType: "ORDER",
            aggregateId: orderId,
            eventType: "ORDER_CREATED",
            payload: { customerId, amount },
            processed: false,
            createdAt: new Date()
          },
          { session }
        );
      });
      log.info(`Order ${orderId} and outbox event created atomically.`);
    } catch (e) {
      log.error("Failed to place order:", e.message);
    } finally {
      await session.endSession();
    }
  }

  async startOutboxListener() {
    log.info("Starting outbox change stream listener...");
    const pipeline = [
      {
        $match: {
          operationType: "insert",
          "fullDocument.aggregateType": "ORDER"
        }
      }
    ];

    const stream = this.outbox.watch(pipeline, { fullDocument: "updateLookup" });
    stream.on("change", async (change) => {
      const event = change.fullDocument;
      log.info(`Captured outbox event for order ${event.aggregateId}. Publishing to message broker...`);

      // (Simulate broker publish - e.g. RabbitMQ / Kafka)
      const success = true; 

      if (success) {
        // Delete or mark event as processed
        await this.outbox.deleteOne({ _id: event._id });
        log.info(`Outbox event ${event._id} processed and removed.`);
      }
    });
  }

  async close() {
    await this.client.close();
  }
}

module.exports = OutboxPublisher;
```

---

### Production Change Stream Consumer with Kafka & DLQ (Node.js)
The following Node.js script listens to updates on a `users` collection, filters out non-email updates early using an aggregation pipeline, transforms the payload, publishes it to Apache Kafka, and implements a Dead Letter Queue (DLQ) retry mechanism for resilience.

```javascript
/**
 * Event-Driven Change Stream Consumer with Kafka Integration
 * Features Resume Token Caching and Dead-Letter Queue (DLQ) retries.
 */
const { MongoClient } = require('mongodb');
const { Kafka } = require('kafkajs');
const log = require('console');
const fs = require('fs');

const TOKEN_CACHE_PATH = './resume_token.json';

// Initialize Kafka client
const kafka = new Kafka({
  clientId: 'mongodb-consumer',
  brokers: ['localhost:9092']
});
const producer = kafka.producer();

// Read cached resume token
function getCachedToken() {
  if (fs.existsSync(TOKEN_CACHE_PATH)) {
    try {
      const data = fs.readFileSync(TOKEN_CACHE_PATH, 'utf8');
      return JSON.parse(data);
    } catch (e) {
      log.error("Failed to parse cached resume token:", e.message);
    }
  }
  return null;
}

// Cache resume token on disk
function cacheToken(token) {
  fs.writeFileSync(TOKEN_CACHE_PATH, JSON.stringify(token), 'utf8');
}

async function startChangeStream(mongoUri) {
  const client = new MongoClient(mongoUri, { maxPoolSize: 10 });
  await client.connect();
  await producer.connect();

  const db = client.db('ecommerce_db');
  const usersCollection = db.collection('users');
  const dlqCollection = db.collection('users_dlq');

  log.info("Change Stream client initialized. Watching 'users' collection...");

  // Filter early: stream only updates that modify the email field
  const pipeline = [
    {
      $match: {
        operationType: 'update',
        'updateDescription.updatedFields.email': { $exists: true }
      }
    },
    {
      // Project only relevant fields to save network bandwidth
      $project: {
        documentKey: 1,
        updateDescription: 1,
        fullDocument: 1
      }
    }
  ];

  const options = {
    fullDocument: 'updateLookup' // Fetch current state of document
  };

  // Add cached resume token if available
  const cachedToken = getCachedToken();
  if (cachedToken) {
    options.resumeAfter = cachedToken;
    log.info("Resuming Change Stream from cached token...");
  }

  const changeStream = usersCollection.watch(pipeline, options);

  changeStream.on('change', async (event) => {
    const resumeToken = event._id;
    const userId = event.documentKey._id;
    const newEmail = event.updateDescription.updatedFields.email;

    log.info(`Received change event for user ${userId}. Processing...`);

    const payload = {
      userId: userId,
      email: newEmail,
      timestamp: new Date()
    };

    // Attempt to publish event to Kafka
    let attempts = 0;
    const maxAttempts = 3;
    let published = false;

    while (attempts < maxAttempts && !published) {
      try {
        attempts++;
        await producer.send({
          topic: 'user-email-updates',
          messages: [{ value: JSON.stringify(payload) }]
        });
        published = true;
        log.info(`Successfully published event for user ${userId} to Kafka.`);
        // Cache token on success
        cacheToken(resumeToken);
      } catch (err) {
        log.warn(`Kafka publish failed. Attempt ${attempts} of ${maxAttempts}: ${err.message}`);
        if (attempts < maxAttempts) {
          await new Promise(res => setTimeout(res, 500 * attempts)); // Backoff
        }
      }
    }

    // Move to Dead Letter Queue (DLQ) if Kafka is unreachable
    if (!published) {
      log.error(`Failed to publish event for user ${userId} after ${maxAttempts} attempts. Routing to DLQ...`);
      try {
        await dlqCollection.insertOne({
          event: event,
          failedAt: new Date(),
          error: "Kafka unavailable"
        });
        log.info("Event for user routed to DLQ.");
        cacheToken(resumeToken);
      } catch (dlqErr) {
        log.error("CRITICAL: Failed to write to DLQ collection!", dlqErr.message);
      }
    }
  });

  changeStream.on('error', (err) => {
    log.error("Change Stream encountered an error:", err.message);
  });
}

const MONGO_URI = "mongodb://localhost:27017/ecommerce_db?replicaSet=rs0";
startChangeStream(MONGO_URI).catch(err => log.error("Failed to start worker:", err));

---

---

## 10. Production Runbook & Deployment Guidelines

### 1. Monitoring Change Stream Cursor State
Check active change stream cursors on the database server to prevent memory leaks:
```javascript
db.serverStatus().metrics.cursor;
```
Ensure all inactive cursors are closed by client applications using finalizer blocks.

### 2. Resuming Streams After Failover
When a replica set failover occurs, ensure the client driver captures the new primary and resumes the stream automatically using cached tokens.

## 11. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Change Stream Resume Token Truncation (Oplog Rollover)
*   **Failure Mode**: A consumer fails to resume because the token's timestamp is no longer in the oplog (error code 136 or 286).
*   **Resolution**: Monitor the oplog window using `db.getReplicationInfo()`, and increase the oplog size if it rolls over too quickly.

### 2. Pre/Post-Image Collection Mod Latencies
*   **Failure Mode**: Enabling pre- and post-images increases write latency and accelerates oplog rollover.
*   **Resolution**: Enable pre/post-images only when necessary, and monitor storage size changes in oplog collections.

### 3. Kafka / RabbitMQ Broker Connection Exhaustion
*   **Failure Mode**: Microservices watching Change Streams exhaust socket connections to the broker.
*   **Resolution**: Manage and share a single Change Stream connection using RxJS or EventEmitters inside application code.

---

## 11. Enterprise Case Study: Change Stream Consumer Dropouts & Resume Token Loss

### 1. Scenario Description
An event-driven billing service processes change streams from an `orders` collection to send invoice notifications. During a network partition, the billing service lost connectivity to MongoDB. The outage lasted for 12 hours. Upon reconnection, the billing service crashed repeatedly, throwing `ChangeStreamHistoryLost` errors. The system could not resume from its last saved state, resulting in missing invoices.

### 2. Analytical Diagnostic Investigation
The developers inspected application logs and found the following stack trace:
```text
com.mongodb.MongoCommandException: Command failed with error 286 (ChangeStreamHistoryLost): 'Resume of change stream was not possible because the resume token was not found in the oplog.'
  at com.mongodb.internal.connection.ProtocolHelper.getCommandFailureException(ProtocolHelper.java:175)
```
**Diagnostic Findings**:
*   The billing service stored the resume token in a database collection after processing each event.
*   Because the downstream outage lasted for 12 hours, the database oplog had rolled over, and the primary node had purged the oplog record associated with the saved resume token.
*   As a result, the client could not resume processing from the token, and starting a new stream risked processing duplicate transactions or missing events.

### 3. Step-by-Step Resolution Runbook
1.  **Determine Current Oplog Window Bounds**:
    Calculate the duration of events stored in the oplog to determine the safe retry window:
    ```javascript
    db.getReplicationInfo();
    ```
2.  **Increase Oplog Retention Window**:
    Increase the oplog size dynamically on the replica set nodes to prevent future rollovers during down times:
    ```javascript
    db.adminCommand({ replSetResizeOplog: 1, size: 81920 }); // Resize to 80GB
    ```
3.  **Deploy a Resilient Fallback Consumption Strategy**:
    If the resume token is lost, the service must perform a fallback query to process missed documents based on timestamp audits before creating a new stream cursor.
4.  **Store Resume Tokens with Reliability**:
    Save tokens in a high-speed, persistent memory store like Redis, and use write concerns to guarantee durability.

### 4. Code Artifact: Java Resilient Change Stream Listener
Save this class as `ResilientStreamListener.java` to manage token failures:
```java
package com.example.event;

import com.mongodb.MongoCommandException;
import com.mongodb.client.ChangeStreamIterable;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoCursor;
import com.mongodb.client.model.changestream.ChangeStreamDocument;
import org.bson.BsonDocument;
import org.bson.Document;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class ResilientStreamListener {
    private static final Logger log = LoggerFactory.getLogger(ResilientStreamListener.class);
    private final MongoCollection<Document> collection;
    private BsonDocument savedResumeToken = null;

    public ResilientStreamListener(MongoCollection<Document> collection) {
        this.collection = collection;
    }

    public void startListening() {
        while (true) {
            try {
                ChangeStreamIterable<Document> stream = collection.watch();
                if (savedResumeToken != null) {
                    log.info("Attempting to resume change stream using token...");
                    stream.resumeAfter(savedResumeToken);
                }
                
                try (MongoCursor<ChangeStreamDocument<Document>> cursor = stream.iterator()) {
                    while (cursor.hasNext()) {
                        ChangeStreamDocument<Document> event = cursor.next();
                        processEvent(event);
                        savedResumeToken = event.getResumeToken();
                    }
                }
            } catch (MongoCommandException e) {
                if (e.getErrorCode() == 286) {
                    log.error("Resume token expired! Performing query fallback before restart...", e);
                    executeFallbackSync();
                    savedResumeToken = null; // Start fresh from current time
                } else {
                    log.error("Fatal database connection exception: ", e);
                    try { Thread.sleep(5000); } catch (InterruptedException ignored) {}
                }
            }
        }
    }

    private void processEvent(ChangeStreamDocument<Document> event) {
        log.info("Processing operation: {}", event.getOperationType());
    }

    private void executeFallbackSync() {
        log.info("Querying for orders modified since last known batch...");
        // Implement query-based synchronization to recover missed data
    }
}
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Oplog Retention Constraints**: Change streams are wrappers around the replica set oplog. If an application falls behind past the oplog window, it *will* miss events. Size the oplog to hold at least 48 hours of write history.
*   **Resume Token Storage**: Always write resume tokens to persistent storage asynchronously. Using a local file or local memory state causes token loss when containers restart.

---

## 12. Hands-on Lab Exercise: Creating a Transactional Outbox Event Dispatcher

### 1. Objective and Scenario
Implement the transactional outbox pattern to write operations and broadcast events reliably to external messaging queues without resource losses.

### 2. Code Implementation: `outbox-dispatcher.js`
Create a file named `outbox-dispatcher.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function startOutbox() {
  const client = new MongoClient("mongodb://localhost:27017/?replicaSet=rs0");
  try {
    await client.connect();
    const db = client.db("outbox_db");
    const outboxCol = db.collection("outbox");
    
    console.log("Listening for new outbox events...");
    
    const changeStream = outboxCol.watch([
      { $match: { operationType: "insert" } }
    ]);
    
    changeStream.on("change", async (change) => {
      const event = change.fullDocument;
      console.log(`[DISPATCH] Processing event: ${event.eventType} for Entity: ${event.entityId}`);
      
      // Simulate external queue dispatch
      try {
        await mockQueuePublish(event);
        // Mark as processed in database
        await outboxCol.updateOne({ _id: event._id }, { $set: { processed: true, processedAt: new Date() } });
        console.log(`[SUCCESS] Event ${event._id} successfully marked as processed.`);
      } catch (err) {
        console.error(`[ERROR] Event dispatch failed:`, err.message);
      }
    });
    
  } catch (err) {
    console.error("Change stream failed:", err);
  }
}

function mockQueuePublish(event) {
  return new Promise((resolve) => setTimeout(resolve, 100));
}

startOutbox();
```

### 3. Lab Verification Steps
1.  Run the change stream listener:
    ```bash
    node outbox-dispatcher.js
    ```
2.  In a separate shell, insert documents into `outbox` and verify they are processed.

---

## 13. Event Stream Durability & Scaling Reference

### 1. Key Stream Parameters
Ensure stream stability using these metrics:
*   `maxAwaitTimeMS`: The maximum duration a cursor blocks waiting for database operations before returning an empty batch.
*   `resumeAfter`: The resume token used to restart a change stream from a specific point in the oplog.

### 2. Operational Diagnostic Commands
Check change stream metrics:
```javascript
// Retrieve active stream cursors on the database server
db.serverStatus().metrics.cursor;

// Verify current oplog collection sizes
db.getSiblingDB("local").oplog.rs.stats();
```

### 3. Senior Engineer's Production Checklist
*   [ ] Save the resume token to persistent storage (like Redis) after processing each change stream event.
*   [ ] Implement a fallback query-based sync mechanism to recover events when resume tokens expire from the oplog.
*   [ ] Apply filter stages (like `$match` on specific update fields) directly to the database watch stream to minimize network overhead.
