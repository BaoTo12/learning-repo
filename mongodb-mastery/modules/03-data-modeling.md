# Module 03: Advanced Data Modeling & Schema Design

## 1. What Problem This Module Solves
In relational databases, normalization rules (1NF, 2NF, 3NF) prevent database anomalies by splitting data into independent tables. In MongoDB, data models must balance query performance, database storage limits, network serialization latency, and write overhead. 

A senior engineer must know how to calculate document storage footprints, design schema validations, manage data consistency in denormalized models, and decide when to embed, reference, or use advanced modeling patterns. Neglecting document size mechanics leads to unbounded array growth, disk fragmentation, and high memory consumption in the WiredTiger cache.

---

## 2. Why This Topic Matters
Poor schema design causes severe performance bottlenecks. For example, allowing arrays to grow unbounded (e.g., storing a post's comments inside the post document) can hit the 16MB document size limit, exhaust WiredTiger cache memory during updates, and increase serialization latency. 

Choosing between embedding and referencing is not a matter of taste; it is a mechanical decision based on data growth rates, join frequencies, and index configurations. Designing data models with precise type structures (like using Binary UUIDs instead of String UUIDs) minimizes storage overhead and ensures the database working set fits comfortably in RAM.

---

## 3. Core Concepts & Internals

### 3.1 Sizing Calculations: Document Sizing Footprint (Detailed)
In MongoDB, a document's BSON size is calculated byte-by-byte. For a collection of $10,000,000$ documents, small sizing inefficiencies can result in gigabytes of wasted RAM.

#### BSON Sizing Formula:
$$\text{Document Size} = 4\text{ bytes (length)} + \sum (\text{Element Overhead}) + 1\text{ byte (terminator)}$$

For each field, the element overhead is calculated as:
$$\text{Element Overhead} = 1\text{ byte (BSON Type)} + \text{Field Name Length} + 1\text{ byte (null terminator)} + \text{Data Size}$$

#### BSON Data Sizes Reference Table:
*   `Double`: 8 bytes
*   `String`: 4 bytes (int32 length) + UTF-8 string bytes + 1 byte (null terminator)
*   `Document` (Embedded): 4 bytes (size) + elements + 1 byte (terminator)
*   `Array`: 4 bytes (size) + elements (where keys are string integers like `"0"`, `"1"`, etc.) + 1 byte (terminator)
*   `Binary (Subtype 4 UUID)`: 4 bytes (length) + 1 byte (subtype) + 16 bytes = 21 bytes
*   `ObjectId`: 12 bytes
*   `Boolean`: 1 byte
*   `Date` (UTC millisecond): 8 bytes
*   `Null`: 0 bytes payload
*   `Int32`: 4 bytes
*   `Int64`: 8 bytes
*   `Decimal128`: 16 bytes (crucial for precise financial transactions)

---

### Step-by-Step Document Sizing Walkthrough:
Let's calculate the exact BSON byte footprint of the following document:
```json
{
  "_id": ObjectId("6487c6b90000000000000000"),
  "user_id": BinData(4, "EjRWeJDzESVFSVFSVVVVVQ=="),
  "meta": {
    "active": true
  },
  "tags": [ "admin", "vip" ],
  "balance": NumberDecimal("100.50")
}
```

#### Byte Allocation Calculation:

1.  **Document Header (Length)**: 
    *   Size: **4 bytes** (int32 indicating total BSON document size).

2.  **Field `_id`**:
    *   Type indicator: 1 byte (`\x07` for ObjectId).
    *   Field name `"_id"`: 3 bytes (`_`, `i`, `d`) + 1 byte (`\x00` null terminator) = 4 bytes.
    *   Data size: **12 bytes** (standard ObjectId size).
    *   Subtotal = $1 + 4 + 12 = \mathbf{17\text{ bytes}}$.

3.  **Field `user_id`**:
    *   Type indicator: 1 byte (`\x05` for Binary).
    *   Field name `"user_id"`: 7 bytes (`u`, `s`, `e`, `r`, `_`, `i`, `d`) + 1 byte (`\x00`) = 8 bytes.
    *   Data size: 4 bytes (length) + 1 byte (subtype) + 16 bytes = **21 bytes**.
    *   Subtotal = $1 + 8 + 21 = \mathbf{30\text{ bytes}}$.

4.  **Field `meta` (Embedded Document)**:
    *   Type indicator: 1 byte (`\x03` for Embedded Document).
    *   Field name `"meta"`: 4 bytes (`m`, `e`, `t`, `a`) + 1 byte (`\x00`) = 5 bytes.
    *   Embedded document data:
        *   Embedded document header: 4 bytes (total subdocument size).
        *   Field `"active"`:
            *   Type indicator: 1 byte (`\x08` for Boolean).
            *   Field name `"active"`: 6 bytes (`a`, `c`, `t`, `i`, `v`, `e`) + 1 byte (`\x00`) = 7 bytes.
            *   Data size: 1 byte (boolean payload).
            *   Subdocument field size = $1 + 7 + 1 = 9$ bytes.
        *   Embedded document terminator: 1 byte (`\x00`).
        *   Embedded document size = $4 + 9 + 1 = 14$ bytes.
    *   Subtotal = $1 + 5 + 14 = \mathbf{20\text{ bytes}}$.

5.  **Field `tags` (Array)**:
    *   Type indicator: 1 byte (`\x04` for Array).
    *   Field name `"tags"`: 4 bytes (`t`, `a`, `g`, `s`) + 1 byte (`\x00`) = 5 bytes.
    *   Array data:
        *   Array document header: 4 bytes (total array document size).
        *   Index element `"0"` (value: `"admin"`):
            *   Type indicator: 1 byte (`\x02` for String).
            *   Index key name `"0"`: 1 byte (`0`) + 1 byte (`\x00`) = 2 bytes.
            *   Data size: 4 bytes (length) + 5 bytes (`admin`) + 1 byte (`\x00`) = 10 bytes.
            *   Element "0" size = $1 + 2 + 10 = 13$ bytes.
        *   Index element `"1"` (value: `"vip"`):
            *   Type indicator: 1 byte (`\x02` for String).
            *   Index key name `"1"`: 1 byte (`1`) + 1 byte (`\x00`) = 2 bytes.
            *   Data size: 4 bytes (length) + 3 bytes (`vip`) + 1 byte (`\x00`) = 8 bytes.
            *   Element "1" size = $1 + 2 + 8 = 11$ bytes.
        *   Array document terminator: 1 byte (`\x00`).
        *   Array size = $4 + 13 + 11 + 1 = 29$ bytes.
    *   Subtotal = $1 + 5 + 29 = \mathbf{35\text{ bytes}}$.

6.  **Field `balance`**:
    *   Type indicator: 1 byte (`\x13` for Decimal128).
    *   Field name `"balance"`: 7 bytes (`b`, `a`, `l`, `a`, `n`, `c`, `e`) + 1 byte (`\x00`) = 8 bytes.
    *   Data size: **16 bytes** (Standard Decimal128 size).
    *   Subtotal = $1 + 8 + 16 = \mathbf{25\text{ bytes}}$.

7.  **Document Terminator**:
    *   Terminator: **1 byte** (`\x00`).

#### Summing Up:
$$\text{Total Document Size} = 4\text{ (Header)} + 17\text{ (_id)} + 30\text{ (user_id)} + 20\text{ (meta)} + 35\text{ (tags)} + 25\text{ (balance)} + 1\text{ (Terminator)} = \mathbf{132\text{ bytes}}$$

*Analysis*: This calculation shows why long field names increase memory footprints. If `"balance"` was renamed `"bal"`, we would save $4\text{ bytes}$ per document. At scale, renaming keys can reclaim gigabytes of cache memory.

---

### 3.2 Embedding vs. Referencing Decision Matrix
Senior designers structure data based on growth characteristics and usage patterns:

```
                  Cardinality & Growth Rate
                  ┌───────────────────────┐
                  │ How does data scale?  │
                  └───────────┬───────────┘
                              │
             ┌────────────────┴────────────────┐
             ▼ (Unbounded/Continuous)          ▼ (Bounded/Fixed)
     [One-to-Many / One-to-Infinite]       [One-to-Few / Monolithic]
             │                                 │
             ▼                                 ▼
   [Store Parent Reference             [Embed Subdocuments
     in Child Collections]               in Single Parent Doc]
```

1.  **One-to-Few (Bounded, e.g. < 100 entries)**: Embed. Retaining addresses in a user document is safe because it is bounded. Reads retrieve the entire entity in one sequential disk IO operation.
2.  **One-to-Many (Bounded, e.g. 100 - 5,000 entries)**: Reference. Storing references in a parent array (e.g. `[ObjectId]`) is acceptable if the array does not grow continuously.
3.  **One-to-Infinite (Unbounded, e.g. Comments, IoT logs)**: Parent-Reference in Child. Store the parent ID inside each child document (e.g., `{ postId: ObjectId(...) }` inside comment documents). This prevents document fragmentation and avoids the 16MB document limit.

---

### 3.3 Dynamic Schema Validation Engine
Although MongoDB is dynamic, production environments require strict rules to enforce data quality and security schema structures.

#### Advanced Validation Configuration
We configure validation using `$jsonSchema` at collection creation:
```javascript
db.createCollection("users", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["email", "status", "schemaVersion", "profile"],
      properties: {
        email: {
          bsonType: "string",
          pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
          description: "Must be a valid email string"
        },
        status: {
          enum: ["ACTIVE", "SUSPENDED", "PENDING"],
          description: "Must be one of the pre-approved enum states"
        },
        schemaVersion: {
          bsonType: "int",
          minimum: 1,
          maximum: 10,
          description: "Tracks active schema structure version"
        },
        profile: {
          bsonType: "object",
          required: ["firstName", "lastName"],
          properties: {
            firstName: {
              bsonType: "string",
              maxLength: 50,
              description: "First name validation"
            },
            lastName: {
              bsonType: "string",
              maxLength: 50,
              description: "Last name validation"
            },
            phone: {
              bsonType: "string",
              pattern: "^\\+?[1-9]\\d{1,14}$",
              description: "E.164 formatted telephone verification string"
            }
          }
        }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});
```

---

## 4. Advanced Modeling Patterns Under the Hood

### 1. Bucket Pattern (IoT & Time-Series Optimization)
*   **Mechanics**: Group data records by time frames (e.g., hour, day) to reduce indexing overhead and avoid document size limits.
*   **Storage Optimization**: Instead of storing 3,600 documents (one per second), store one document containing an array of 3,600 samples, saving BSON key replication space.

### 2. Attribute Pattern (Polymorphic Index Optimization)
*   **Mechanics**: Structure dynamic properties as key-value pairs inside an array.
*   **Index Optimization**: Instead of indexing dozens of dynamic properties, use a single compound index on the key-value array: `{ "attrs.k": 1, "attrs.v": 1 }`.

### 3. Outlier Pattern (Handling Skewed Relationships)
*   **Mechanics**: Model relationships assuming normal distributions. If a document exceeds typical bounds (e.g., a celebrity user with millions of followers), set a boolean flag `"hasOutliers": true` and store additional data in a separate collection.

### 4. Subset Pattern (Capping Memory Payload)
*   **Mechanics**: Keep only the top $N$ items of a large relationship embedded in the main document (e.g. the 10 most recent reviews) and move older history to a separate collection. This keeps the active working set small and fast.

### 5. Computed Pattern
*   **Mechanics**: Precalculate read-heavy metrics (e.g., ratings averages) on write operations and store them in the document, avoiding expensive run-time aggregations.

### 6. Extended Reference Pattern
*   **Mechanics**: Denormalize selected fields from a referenced document into the parent document (e.g., storing the product name and price directly inside an order document) to eliminate `$lookup` joins on read paths.

---

## 5. Practical Examples

### Denormalization Consistency Worker (Node.js Change Stream)
When denormalizing data (using the Extended Reference Pattern), you must ensure updates propagate across the database. The following production-ready Node.js worker reads changes from a `users` collection and uses transactions to update denormalized user data in an `orders` collection safely.

```javascript
const { MongoClient } = require('mongodb');
const log = require('console');

class DenormalizationWorker {
  constructor(uri) {
    this.client = new MongoClient(uri, { maxPoolSize: 10 });
  }

  async start() {
    await this.client.connect();
    const db = this.client.db('ecommerce_db');
    const usersCollection = db.collection('users');
    const ordersCollection = db.collection('orders');

    log.info("Starting Change Stream worker on 'users' collection...");

    // Watch for updates to the name or email fields
    const pipeline = [
      {
        $match: {
          operationType: 'update',
          $or: [
            { 'updateDescription.updatedFields.name': { $exists: true } },
            { 'updateDescription.updatedFields.email': { $exists: true } }
          ]
        }
      }
    ];

    const changeStream = usersCollection.watch(pipeline, { fullDocument: 'updateLookup' });

    changeStream.on('change', async (change) => {
      const userId = change.documentKey._id;
      const updatedFields = change.updateDescription.updatedFields;

      // Extract new details
      const updatePayload = {};
      if (updatedFields.name) updatePayload['customerDetails.name'] = updatedFields.name;
      if (updatedFields.email) updatePayload['customerDetails.email'] = updatedFields.email;

      log.info(`Propagating updates for user ${userId}:`, updatePayload);

      // Run update within a retryable transaction
      await this.runTransactionWithRetry(async (session) => {
        await ordersCollection.updateMany(
          { 'customerDetails.userId': userId },
          { $set: updatePayload },
          { session }
        );
      });
    });
  }

  async runTransactionWithRetry(txnFunc) {
    const session = this.client.startSession();
    try {
      await session.withTransaction(async () => {
        await txnFunc(session);
      });
      log.info("Denormalization transaction committed successfully.");
    } catch (error) {
      log.error("Denormalization transaction failed:", error.message);
    } finally {
      await session.endSession();
    }
  }

  async close() {
    await this.client.close();
  }
}

module.exports = DenormalizationWorker;
```

---

## 6. Trade-offs & Alternatives

Multi-tenant SaaS architectures require choosing the right database separation strategy:

| Partitioning Strategy | Resource Efficiency | Performance Isolation | Schema Flexibility | Backup & Restore Complexity |
| :--- | :--- | :--- | :--- | :--- |
| **Shared Collection** (Tenant ID field) | **Excellent**: Collections and indexes are shared, minimizing system overhead. | **Poor**: High-traffic tenants can saturate the cache and affect others (noisy neighbor). | **Low**: A single schema validator is shared across all tenants. | **High**: Restoring data for a single tenant requires extracting and merging documents. |
| **Database-per-Tenant** | **Medium**: Creates unique collections and indexes per database; incurs metadata overhead. | **Medium**: Some cache segregation, but resources are shared on the same host. | **High**: Each database can run its own collection schemas. | **Easy**: Databases can be backed up and restored independently. |
| **Cluster-per-Tenant** | **Low**: Each tenant runs on dedicated hardware, increasing costs. | **Excellent**: Complete physical isolation from other workloads. | **Unlimited**: Complete operational and versioning independence. | **Excellent**: Standard backup processes run on dedicated nodes. |

---

## 7. Common Mistakes & Anti-patterns
*   **The Unbounded Array**: Appending items to arrays indefinitely (e.g. logs or chat history). This forces WiredTiger to continually relocate the document on disk, degrading performance and eventually hitting the 16MB document limit.
*   **Excessive Referencing**: Normalizing every relationship and relying on multiple `$lookup` operations, which degrades read performance and negates the benefits of a document database.
*   **Storing Binary Data Directly as BSON**: Embedding large binary files (e.g., PDFs, images) directly in documents. This pollutes the WiredTiger page cache. Use GridFS or external object storage (e.g. S3) with references in MongoDB instead.

---

## 8. Hands-on Exercises
1.  Implement a validated collection in MongoDB using the JSON Schema from Section 3.3.
2.  Attempt to insert documents with invalid emails or missing profile fields. Capture and analyze the BSON validation exception output.
3.  Write a script to compute the exact BSON byte size of a document and compare it to its JSON representation size.
4.  Implement the Change Stream worker from Section 5 in your local development environment. Verify that updating a user document automatically updates denormalized fields in the orders collection.

---

## 9. Interview Questions

### Q1: How does MongoDB's 16MB document size limit affect database internals and schema design?
**Answer**: The 16MB limit is a safeguard to prevent documents from consuming excessive WiredTiger memory and network bandwidth. If a document grows too large, reading it saturates network connections and degrades WiredTiger cache efficiency. Appending to large documents also causes disk fragmentation because the engine must relocate the document to a new block on disk. A senior engineer designs around this limit by:
1.  Using the Subset Pattern to cap embedded arrays.
2.  Referencing child documents instead of embedding them when relationships are unbounded.
3.  Using the Bucket Pattern to group chronological data.

### Q2: What are the trade-offs of storing denormalized data in MongoDB? How do you maintain consistency?
**Answer**: Denormalization improves read performance by eliminating `$lookup` operations, but it increases write overhead and storage space because duplicate data must be updated in multiple places. Consistency is managed using:
1.  **Database Transactions**: Multi-document sessions to update all copies of the data atomically.
2.  **Eventual Consistency**: Using Change Streams or message brokers (like Kafka) to trigger background updates when the source of truth changes.
3.  **Accepting Eventual Consistency**: Only denormalizing fields that rarely change (e.g. product names) or where absolute real-time consistency is not required.

### Q3: When is the Schema Versioning Pattern preferred over running offline migrations?
**Answer**: The Schema Versioning Pattern is preferred when you have massive collections where running an offline migration script would saturate disk IOPS, lock tables, or cause downtime. By storing a `schemaVersion` field in each document, the application can read and map both formats dynamically. Outdated documents can be updated lazily as they are read-repaired, avoiding the resource spikes associated with offline batch migrations.

---

---

---

## 10. Production Runbook & Deployment Guidelines

### 1. Automated Document Size Audits
To identify and mitigate document size growth before hitting the 16MB threshold, run regular background checks to identify documents approaching the limit:
```javascript
db.users.aggregate([
  { $project: { docSize: { $bsonSize: "$$ROOT" } } },
  { $match: { docSize: { $gt: 12000000 } } }, // Flags docs larger than 12MB
  { $limit: 10 }
]).pretty();
```
Flagged documents should be refactored by moving embedded arrays to separate collections using references.

### 2. Deploying Schema Validators Safely
When applying validation rules to a collection with existing documents, configure the validation level to `moderate` to prevent writes on legacy documents from failing:
```javascript
db.runCommand({
  collMod: "users",
  validator: { $jsonSchema: { ... } },
  validationLevel: "moderate",
  validationAction: "warn" // Log warnings before enforcing errors
});
```

## 11. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Unbounded Array Growth (Document Relocation Page Splits)
*   **Failure Mode**: Storing history or logs directly inside document arrays causes documents to grow continuously, forcing WiredTiger to perform frequent page splits and document relocations.
*   **Resolution**: Shift to a parent-reference schema model where child documents store references to the parent document.

### 2. Schema Validation Latency Spikes
*   **Failure Mode**: Highly complex JSON Schema validation structures with recursive object checks and multiple regex expressions increase write latency.
*   **Resolution**: Keep validation schemas focused on key fields, and avoid using complex regex checks on high-throughput collections.

### 3. EAV (Entity-Attribute-Value) Index Bloat
*   **Failure Mode**: Dynamic property models generate massive indexes that exhaust WiredTiger cache memory.
*   **Resolution**: Apply the Attribute Pattern to group dynamic properties into key-value pairs inside a single array, and use a single compound index.

---

## 12. Summary
Data modeling in MongoDB is a balance of storage layout, relationship cardinality, and write constraints. By calculating BSON footprints, designing validation rules, and applying patterns like Bucketing or Subset arrays, senior engineers design databases optimized for performance and scalability.

---

## 12. Enterprise Case Study: Document Growth & Chunk Migration Latency

### 1. Scenario Description
An enterprise SaaS platform stores user notification items. Initially, notifications were modeled as an embedded array within the user document (the Embedded Array Pattern) for fast retrieval. After two years of operation, high-volume users accumulated tens of thousands of notifications. The document sizes approached the 16MB limit, which triggered disk thrashing during write updates, increased secondary replication lag, and caused shard chunk migrations to fail due to "jumbo document" states.

### 2. Analytical Diagnostic Investigation
The operations team audited the database to find documents close to the limit:
```javascript
db.users.aggregate([
  { $project: { docSize: { $bsonSize: "$$ROOT" }, email: 1 } },
  { $match: { docSize: { $gt: 12000000 } } },
  { $sort: { docSize: -1 } }
]).forEach(doc => {
  print("User ID: " + doc._id + " | Size: " + (doc.docSize / 1024 / 1024).toFixed(2) + " MB");
});
```
The analysis revealed that user documents were exceeding 14MB. WiredTiger writes documents compressed on disk, but when a client requests a document, it must be loaded into memory and uncompressed. A 14MB document expands to 40MB+ of BSON structure in RAM. Modifying a nested array in this document forces the storage engine to re-serialize the entire BSON payload, generating severe heap pressure.

### 3. Step-by-Step Resolution Runbook
To resolve this issue, the engineering team designed a zero-downtime migration to the **Out-of-band Bucketing Pattern**:

1.  **Define the New Schema Structure**:
    Instead of embedding all notifications in the user document, they created a separate collection `user_notifications` with buckets capped at 100 notifications per document:
    ```javascript
    // Sample Bucket Document Schema
    {
      _id: ObjectId(),
      userId: ObjectId("..."),
      bucketId: 1,
      count: 2,
      notifications: [
        { message: "First notification", date: ISODate("...") },
        { message: "Second notification", date: ISODate("...") }
      ]
    }
    ```
2.  **Deploy Schema Validators**:
    Create the validator to enforce constraints on bucket count:
    ```javascript
    db.createCollection("user_notifications", {
      validator: {
        $jsonSchema: {
          bsonType: "object",
          required: ["userId", "bucketId", "count", "notifications"],
          properties: {
            count: { bsonType: "int", maximum: 100 },
            notifications: { bsonType: "array" }
          }
        }
      }
    });
    ```
3.  **Run the Migration Script**:
    Extract legacy arrays and write them to bucket collections. (See Node.js script below).
4.  **Update the Application Persistence Logic**:
    Update the application write path to use the `$push` operator with the `$slice` filter, or query the active bucket and update:
    ```javascript
    db.user_notifications.updateOne(
      { userId: userId, count: { $lt: 100 } },
      {
        $push: { notifications: newNotification },
        $inc: { count: 1 }
      },
      { upsert: true }
    );
    ```

### 4. Code Artifact: Zero-Downtime Migration Script
Save this script as `migrate-notifications.js` to process historical data safely:
```javascript
const { MongoClient } = require('mongodb');

async function migrate() {
  const client = new MongoClient("mongodb://localhost:27017");
  try {
    await client.connect();
    const db = client.db("saas_db");
    const cursor = db.collection("users").find({ "notifications.0": { $exists: true } });
    
    while (await cursor.hasNext()) {
      const user = await cursor.next();
      const notifications = user.notifications;
      
      let bucketId = 1;
      let chunk = [];
      
      for (let i = 0; i < notifications.length; i++) {
        chunk.push(notifications[i]);
        if (chunk.length === 100 || i === notifications.length - 1) {
          await db.collection("user_notifications").insertOne({
            userId: user._id,
            bucketId: bucketId++,
            count: chunk.length,
            notifications: chunk
          });
          chunk = [];
        }
      }
      
      // Unset notifications array from user document to free space
      await db.collection("users").updateOne(
        { _id: user._id },
        { $unset: { notifications: "" } }
      );
      console.log(`Migrated user ${user._id} and removed legacy embedded notification array.`);
    }
  } finally {
    await client.close();
  }
}
migrate().catch(console.dir);
```

### 5. Architectural Trade-offs & Lessons Learned
*   **The 16MB BSON Limit is a Safety Guard**: Do not treat the 16MB document limit as a design target. Design data schemas to keep document sizes below 2MB to ensure cache efficiency and fast replication.
*   **WiredTiger Page Allocations**: Large documents cause leaf pages to exceed allocation bounds, resulting in page splits, disk fragmentation, and high eviction pressures.

---

## 13. Hands-on Lab Exercise: Schema Validator & Data Integrity Guard

### 1. Objective and Scenario
Deploy structural validators to verify document parameters before insertions. You will write a Node.js script to create a collection with validation boundaries that enforce data types and object hierarchies.

### 2. Code Implementation: `setup-validators.js`
Create a file named `setup-validators.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function main() {
  const client = new MongoClient("mongodb://localhost:27017");
  try {
    await client.connect();
    const db = client.db("schema_db");
    
    // Drop collection if it already exists
    try { await db.collection("customers").drop(); } catch (e) {}

    // Create collection with strict validation
    await db.createCollection("customers", {
      validator: {
        $jsonSchema: {
          bsonType: "object",
          required: ["name", "email", "status"],
          properties: {
            name: {
              bsonType: "string",
              description: "Must be a string and is required"
            },
            email: {
              bsonType: "string",
              pattern: "^.+@.+$",
              description: "Must be a valid email address string"
            },
            status: {
              enum: ["ACTIVE", "INACTIVE", "SUSPENDED"],
              description: "Must be one of the pre-defined states"
            }
          }
        }
      }
    });

    console.log("Collection 'customers' created with JSON schema validation.");

    // Test inserting valid document
    await db.collection("customers").insertOne({
      name: "Alice Smith",
      email: "alice@example.com",
      status: "ACTIVE"
    });
    console.log("Valid document inserted successfully.");

    // Test inserting invalid document
    try {
      await db.collection("customers").insertOne({
        name: "Bob Jones",
        email: "invalid-email",
        status: "PENDING"
      });
    } catch (err) {
      console.log("Invalid document blocked correctly by database validator:", err.message);
    }
  } finally {
    await client.close();
  }
}
main();
```

### 3. Lab Verification Steps
1.  Run the validation validator script:
    ```bash
    node setup-validators.js
    ```
2.  Observe the output to verify the error response when trying to insert invalid fields.

---

## 14. Document Schema Governance & Lifecycle Reference

### 1. Key Schema Validation Settings
Apply these configurations inside `collMod` commands to enforce document properties:
*   `validationLevel`: Controls how strictly validation rules are applied to existing documents (`off`, `strict`, or `moderate`).
*   `validationAction`: Determines whether validation errors reject write requests (`error`) or log warnings (`warn`).

### 2. Operational Diagnostic Commands
Verify validation rules and document integrity metrics:
```javascript
// Query collection metadata to inspect JSON schema configurations
db.getCollectionInfos({ name: "users" });

// Validate collection structure and check for document corruption
db.users.validate({ full: true });
```

### 3. Senior Engineer's Production Checklist
*   [ ] Deploy schema validation rules using `validationLevel: "moderate"` and `validationAction: "warn"` first to check legacy records without write failures.
*   [ ] Set up automated crontabs running `$bsonSize` queries to flag documents approaching 12MB.
*   [ ] Verify that large arrays are converted to separate reference collections using bucketing patterns before BSON limits are reached.

---

## 15. Advanced Cardinality & High-Scale Relationship Modeling

### 1. Normalization vs. Denormalization Decision Matrix
When structuring data models, balance read and write performance using these metrics:

| Criteria | Normalization (References) | Denormalization (Embedding) |
| :--- | :--- | :--- |
| **Document Size** | Small, fixed size | Grows as child items expand |
| **Write Operations** | High speed, updates write to single target | Slower, updates modify multiple arrays |
| **Consistency** | Immediate consistency (ACID joins) | Eventual consistency acceptable |
| **Working Set** | Focuses on active fields | Embeds static fields, using cache RAM |

### 2. High-Cardinality Relationships (Friends & Followers)
When modeling user sub-networks (followers), a 1-to-N relationship can scale beyond BSON limits. If a celebrity (producer) accumulates millions of followers, embedding the follower list in a single document fails.

#### Design Pattern Option: Subs Collection with Outliers
For high-volume celebrity nodes, use the Outlier Pattern with "to-be-continued" (`tbc`) continuation documents to handle growth:
```javascript
// Producer Document
{
  "_id": ObjectId("51252871d86041c7dca8191a"),
  "username": "wil_wheaton",
  "email": "wil@example.com",
  "tbc": [
    ObjectId("512528ced86041c7dca8191e")
  ],
  "followers": [
    ObjectId("512528a0d86041c7dca8191b"),
    ObjectId("512528a2d86041c7dca8191c")
  ]
}

// Continuation Document
{
  "_id": ObjectId("512528ced86041c7dca8191e"),
  "followers": [
    ObjectId("512528f1d86041c7dca8191f"),
    ObjectId("512528f6d86041c7dca81920")
  ]
}
```
Update the application logic to check the `tbc` array and load continuation documents sequentially during subscriber lists retrieval.
