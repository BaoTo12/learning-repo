# Module 15: System Design with MongoDB

## 1. What Problem This Module Solves
When designing large-scale software systems, selecting the appropriate database and mapping data models is a critical architectural decision. Relational databases (SQL) and document databases (MongoDB) have fundamentally different storage engines, scaling mechanics, and consistency models. 

A senior engineer must understand how to design and compare system architectures for real-time chat platforms, e-commerce catalogs, financial ledgers, and multi-tenant SaaS applications. Making the wrong database choice or applying relational modeling habits to MongoDB results in query latency bottlenecks, high operational costs, and data consistency issues at scale.

---

## 2. Why This Topic Matters
System design requires selecting the right tool for the job based on query patterns, write throughput, and consistency requirements. For example, using a relational database with Entity-Attribute-Value (EAV) tables for a dynamic product catalog introduces complex, slow joins. Conversely, using MongoDB for a financial ledger without enforcing database validation rules and retryable transactions risks data corruption.

This module provides the comparative analysis and structural designs required to architect production systems using MongoDB, detailing trade-offs and layout patterns for high-scale applications.

---

## 3. System Design Comparisons: SQL vs. MongoDB

This section models and compares database architectures across four real-world production domains.

---

### 3.1 Real-Time Chat & Messaging Application
A messaging system must support high-frequency writes, real-time read delivery, and historical search queries across millions of conversations.

#### 1. SQL Relational Model:
*   **Schema**:
    ```sql
    CREATE TABLE conversations (
        id UUID PRIMARY KEY,
        created_at TIMESTAMP
    );

    CREATE TABLE messages (
        id UUID PRIMARY KEY,
        conversation_id UUID REFERENCES conversations(id),
        sender_id UUID,
        body TEXT,
        created_at TIMESTAMP
    );
    ```
*   *Performance gotcha*: Querying chat history requires joining `messages` and `conversations`. As the tables grow, index scans (`IXSCAN`) on `conversation_id` must load separate disk pages, causing query slowdowns due to random IO operations.

#### 2. MongoDB Bucket Document Model:
*   **Schema**:
    ```json
    {
      "_id": ObjectId("6487c6b90000000000000000"),
      "conversationId": UUID("123e4567-e89b-12d3-a456-426614174000"),
      "bucketId": 1, // Incremented as messages grow
      "messageCount": 100,
      "messages": [
        {
          "senderId": UUID("987f6543-e89b-12d3-a456-426614174000"),
          "body": "Hello world!",
          "timestamp": ISODate("2026-06-12T07:30:00Z")
        }
      ]
    }
    ```
*   *Optimization*: Messaging history is grouped into buckets of 100 messages. Fetching chat history requires a single sequential read query to retrieve the target bucket document, reducing random disk IO and improving load times.

#### Detailed Message Read/Write Flow:
1.  **Write Path**: When a user sends a message, the server checks the current active bucket document for the conversation (where `messageCount < 100`). The server appends the message to the `messages` array and increments `messageCount` atomically using `$push` and `$inc` in a single `updateOne` operation.
2.  **Read Path**: When a user opens a chat, the client driver fetches the latest bucket document (`bucketId: N`) using the index `{ conversationId: 1, bucketId: -1 }`. If the user scrolls up, the client fetches preceding buckets (`bucketId: N - 1`), loading exactly 100 messages per roundtrip.
3.  **Read Receipts**: Read receipts are managed by updating a `lastReadTime` field for the user inside the main conversation document, avoiding updates to individual message elements.

---

### 3.2 E-Commerce Product Catalog
An e-commerce catalog must store highly polymorphic products (e.g., clothes with size/color, laptops with CPU/RAM) and support fast searches and dynamic filters.

#### 1. SQL Entity-Attribute-Value (EAV) Model:
*   **Schema**:
    ```sql
    CREATE TABLE products (id INT PRIMARY KEY, name VARCHAR(100));
    CREATE TABLE attributes (id INT PRIMARY KEY, key_name VARCHAR(50));
    CREATE TABLE product_attribute_values (
        product_id INT REFERENCES products(id),
        attribute_id INT REFERENCES attributes(id),
        value VARCHAR(255),
        PRIMARY KEY (product_id, attribute_id)
    );
    ```
*   *Performance gotcha*: Querying products with dynamic filters (e.g. searching for a laptop with 16GB RAM and Core i7 CPU) requires joining the values table multiple times, resulting in complex queries and high CPU utilization under load.

#### 2. MongoDB Attribute Pattern:
*   **Schema**:
    ```json
    {
      "_id": 998,
      "name": "SuperBook Laptop",
      "attrs": [
        { "k": "ram", "v": "16GB" },
        { "k": "cpu", "v": "Core i7" },
        { "k": "storage", "v": "512GB SSD" }
      ]
    }
    ```
*   *Optimization*: Dynamic fields are standardized into a key-value array. We can index all dynamic properties using a single compound index: `{ "attrs.k": 1, "attrs.v": 1 }`, enabling fast queries for any attribute.

#### Category Hierarchy Modeling Patterns:
When designing category hierarchies (e.g. `Electronics > Computers > Laptops`), choose the pattern that matches your query complexity:
*   **Materialized Paths Pattern**: Store the hierarchical path as a string:
    ```json
    { "_id": "laptops", "name": "Laptops", "path": ",electronics,computers,laptops," }
    ```
    *Index*: `{ path: 1 }`. Query ancestors using regex: `db.categories.find({ path: /^,electronics,computers,/ })`.
*   **Ancestor Array Pattern**: Store the hierarchical path as an array:
    ```json
    { "_id": "laptops", "name": "Laptops", "ancestors": ["electronics", "computers"] }
    ```
    *Index*: `{ ancestors: 1 }`. Query subcategories using array matching: `db.categories.find({ ancestors: "electronics" })`.

---

### 3.3 Financial Ledger System
A ledger system demands strict transactional consistency, auditability, and zero write conflicts during currency transfers.

#### 1. SQL Ledger Model:
*   **Schema**:
    ```sql
    CREATE TABLE accounts (
        id VARCHAR(50) PRIMARY KEY,
        balance NUMERIC(15, 4) CHECK (balance >= 0)
    );
    ```
*   *Advantage*: SQL engines use row-level locking and ACID MVCC transactions, enforcing checks (like `balance >= 0`) at the database engine level to prevent double-spending.

#### 2. MongoDB Ledger Model:
*   **Schema**:
    ```json
    {
      "_id": "ACC-1002",
      "balance": NumberDecimal("10500.50"),
      "version": 42
    }
    ```
*   *Optimization*: We enforce data integrity using database-level JSON Schema validators to block negative balances, combined with multi-document transactions using `writeConcern: majority` and optimistic concurrency version checks.

#### Dual-Entry Booking Transaction Flow:
```
 [Client Request] ──> Start Transaction Session
                          │
                          ▼
                 1. Fetch ACC-A & ACC-B
                          │
                          ▼
                 2. Verify ACC-A Balance >= Amount
                          │
                          ▼
                 3. Deduct from ACC-A (optimistic version match)
                          │
                          ▼
                 4. Credit to ACC-B
                          │
                          ▼
                 5. Insert Transaction Log Document
                          │
                          ▼
                  Commit Transaction ──> Acknowledge Client
```

---

### 3.4 Multi-Tenant SaaS Platform
A software-as-a-service (SaaS) application isolates data across thousands of tenant accounts while maintaining low operational costs and simple backup options.

#### 1. SQL Database-per-Tenant Model:
*   **Schema**: Each tenant is allocated a separate physical schema or database instance.
*   *Advantage*: Complete data isolation and simple tenant backup and restore processes.
*   *Disadvantage*: Managing connection pools and executing schema migrations across thousands of databases is operationally complex and resource-intensive.

#### 2. MongoDB Shared Collection Model:
*   **Schema**:
    ```json
    {
      "_id": ObjectId("6487c6b90000000000000000"),
      "tenantId": "tenant_abc",
      "name": "User Profile Info"
    }
    ```
*   *Optimization*: All tenants store data in a single shared collection, partitioned using a `tenantId` index. This maximizes resource utilization, but requires careful application-level checks to prevent cross-tenant data access.

#### Tenant Isolation and Pool Sizing:
If you choose the **Database-per-Tenant** strategy in MongoDB:
*   **Connection Pool Consumption**: Each database instantiation consumes connection sockets. If you have 1,000 tenants and a connection pool size of 10, the application can open up to **10,000 socket connections** to the database host.
*   **WiredTiger Metadata Exhaustion**: WiredTiger allocates cache space for every open collection and index. Running thousands of databases with distinct collections can exhaust metadata memory, degrading cache performance. Use the **Shared Collection** strategy with tenant IDs to ensure resource efficiency.

---

## 4. Architectural Trade-offs & Comparisons

The following matrix compares SQL and MongoDB across key architectural dimensions:

| Architectural Dimension | SQL Database (e.g. PostgreSQL) | MongoDB (Document Store) |
| :--- | :--- | :--- |
| **Write Throughput** | **Medium**: Limited by row locking, WAL writes, and single-primary bottlenecks. | **High**: Fast in-memory writes on WiredTiger, easily scaled using hashed sharding. |
| **Schema Flexibility** | **Rigid**: Schema-on-write. Migrations require table locks or online migration tools. | **Flexible**: Schema-on-read. Supports polymorphic structures and dynamic attributes. |
| **Complex Joins** | **High**: Native index nested-loop and merge joins executed at the engine level. | **Low**: Join queries (`$lookup`) are executed as nested loops, which can be slow. |
| **Read Scaling** | **Medium**: Requires read-replicas; writes cannot be sharded easily. | **High**: Scale reads using replication secondaries and horizontal sharding. |
| **Transactional Latency** | **Low**: Optimized lock hierarchies and row-level concurrency. | **Medium**: Multi-document transactions require distributed locks across shards. |

---

## 5. System Architecture Design Diagrams

### E-Commerce Product Catalog Architecture
The diagram below shows how an e-commerce platform coordinates search, cache, and database writes using the Computed Pattern.

```
 [User API Request] ──> [API Gateway Router]
                             │
                             ├── Read path ──> [Redis Cache]
                             │                     │
                             │                  (Miss)
                             │                     ▼
                             │                 [MongoDB Secondary Shard]
                             │
                             └── Write path ──> [MongoDB Primary Shard]
                                                    │
                                                    ▼ (Change Stream Event)
                                               [Computed Worker Engine]
                                                    │
                                                    ▼
                                               [Update Redis Cache]
```

#### Architecture Components:
*   **Redis Cache**: Caches precomputed catalog pages, offloading read traffic from the database.
*   **MongoDB Shards**: Partition product data using a hashed shard key on `productId` to distribute writes uniformly.
*   **Change Stream Worker**: Listens to updates on the product collection and automatically updates the Redis cache, ensuring cache consistency.

---

## 6. Shared Collection Tenant Backup Script (Bash)
In a shared-collection multi-tenant SaaS application, backing up individual tenant data requires exporting filtered documents rather than raw databases. The following script shows how to execute and pack a specific tenant's data safely using `mongodump` and queries.

```bash
#!/usr/bin/env bash
# Shared Collection Single Tenant Backup Runner

TENANT_ID="tenant_abc"
DB_NAME="saas_db"
OUTPUT_DIR="./backups/$TENANT_ID"
MONGO_URI="mongodb://localhost:27017/?replicaSet=rs0"

echo "====== Starting backup for Tenant: $TENANT_ID ======"

# 1. Run mongodump with query filter on tenantId
mongodump --uri="$MONGO_URI" \
          --db="$DB_NAME" \
          --collection="user_profiles" \
          --query="{\"tenantId\": \"$TENANT_ID\"}" \
          --out="$OUTPUT_DIR"

# 2. Package output files
if [ $? -eq 0 ]; then
  echo "Data exported successfully. Compressing backup files..."
  tar -czf "./backups/backup_${TENANT_ID}_$(date +%F).tar.gz" -C "$OUTPUT_DIR" .
  # Clean up temp folder
  rm -rf "$OUTPUT_DIR"
  echo "Backup completed successfully!"
else
  echo "ERROR: Backup failed during export."
  exit 1
fi
```

---

## 7. Common Mistakes & Anti-patterns
*   **Using MongoDB as a Relational Database**: Normalizing all collections and executing multiple `$lookup` joins on read paths. This degrades performance and negates the benefits of a document database.
*   **Selecting the Wrong Shard Key**: Using monotonically increasing fields (like `createdAt`) in a ranged cluster, which creates write hotspots.
*   **Using Embedded Documents for Unbounded Relationships**: Storing unbounded arrays (like user logs or chat history) inside a single document, which eventually hits the 16MB document size limit.

---

## 8. Hands-on Exercises
1.  Draw a system architecture diagram for a multi-tenant SaaS application using MongoDB.
2.  Implement the Attribute Pattern for a dynamic product collection. Verify that queries use a single compound index.
3.  Simulate a high-frequency write workload on a replica set. Compare write throughput with and without sharding.
4.  Write a script to measure query execution times for a `$lookup` join across unindexed collections. Apply indexes and compare the results.

---

## 9. Mini-Project: E-Commerce Catalog Design
**Scenario**: Design a database architecture for an e-commerce catalog containing 5,000,000 products with dynamic attributes.

1.  Create the collection schema using the Attribute Pattern.
2.  Configure JSON Schema validation rules to enforce product types, category boundaries, and required fields.
3.  Define the index configuration to support fast searches and dynamic filters.
4.  Write a design document detailing the architecture, index choices, and scalability options.

---

## 10. Interview Questions

### Q1: How do you choose between embedding and referencing when designing a MongoDB schema?
**Answer**: Choosing between embedding and referencing is based on data growth rates and query patterns:
1.  **Embed** when the relationship is bounded (e.g. one-to-few, < 100 entries) and the data is queried together. This retrieves all data in a single sequential disk read.
2.  **Reference** when the relationship is unbounded (e.g. one-to-many or one-to-infinite) or the data is queried independently. This prevents document fragmentation and avoids the 16MB document size limit.

### Q2: What is the impact of executing a `$lookup` join across sharded collections?
**Answer**: Executing a `$lookup` join across sharded collections is complex. The query router (`mongos`) must coordinate data lookup across multiple shards, sending requests to the shards holding the target ranges. If the join keys are not indexed, this forces a collection scan on all shards, degrading cluster performance. Avoid `$lookup` joins on high-frequency API read paths; use the Extended Reference Pattern to denormalize fields instead.

### Q3: Why is the Attribute Pattern preferred over standard dynamic properties for polymorphic documents?
**Answer**: The Attribute Pattern standardizes dynamic fields into a key-value array format. This allows you to index all dynamic attributes using a single compound index: `{ "attrs.k": 1, "attrs.v": 1 }`. If you store dynamic fields as standard properties (e.g. `{ ram: "16GB", cpu: "i7" }`), you must create a separate index for every possible property, which increases write latency and index memory footprint.

---

---

---

## 11. Production Runbook & Deployment Guidelines

### 1. Multi-Tenant Database Separations
If using a shared collection model, enforce tenant-level filtering inside application repositories:
```java
// Spring Data Mongo Repository Custom Interface
public interface TenantRepository<T> {
    List<T> findAllByTenantId(String tenantId);
}
```

### 2. Monitoring Shared Collections Size
Check collection statistics regularly to verify tenant data distribution and prevent storage imbalances.

## 12. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Chat System Bucket Overflow
*   **Failure Mode**: Failing to limit bucket sizes causes documents to exceed the 16MB limit, blocking subsequent messages.
*   **Resolution**: Check bucket counts, and create new bucket documents when `messageCount` reaches the limit.

### 2. Category Path Index Bloat
*   **Failure Mode**: Storing long path strings in Materialized Path category collections results in large index footprints.
*   **Resolution**: Hash path ranges, or use Ancestor Arrays instead of string paths.

### 3. Multi-Tenant Database Exhaustion
*   **Failure Mode**: Creating separate databases for thousands of tenants exhausts WiredTiger cache metadata capacity.
*   **Resolution**: Shift to a shared collection design with tenant IDs to optimize resource utilization.

---

## 13. Summary
System design with MongoDB requires aligning database choices, scaling strategies, and relationship mappings. By understanding the trade-offs of embedding vs. referencing, applying patterns like the Attribute Pattern, and using change streams to maintain cache consistency, senior engineers design scalable, high-performance database architectures.

---

## 12. Enterprise Case Study: SaaS Multi-Tenant Cross-Contamination & Resource Starvation

### 1. Scenario Description
A SaaS provider stores customer accounting data in a shared MongoDB cluster. They used a shared collection design, separating tenants using a `tenantId` field. During peak tax filing periods, a high-volume tenant executed heavy aggregation queries. This exhausted the database threads, causing queries for all other tenants to time out. Additionally, a bug in a developer's query omitted the `tenantId` filter, resulting in a cross-tenant data leak.

### 2. Analytical Diagnostic Investigation
The DBA checked database operations using `db.currentOp()`:
```javascript
db.currentOp({ "waitingForLock": true, "secs_running": { "$gt": 5 } });
```
**Diagnostic Findings**:
*   A single tenant was executing queries containing unindexed parameters, generating collection scans across millions of documents.
*   WiredTiger resources (read/write tickets) were exhausted by this tenant, leaving no execution slots for other tenants.
*   The code audit showed database queries were built by dynamically appending user parameters, making it easy to forget the tenant scope check.

### 3. Step-by-Step Resolution Runbook
1.  **Deploy Tenant Shard Zones**:
    Migrate to a zoned sharding design. Assign tenant IDs to specific shards to isolate workload resource usage:
    ```javascript
    sh.addShardTag("shard-01", "TenantZoneA");
    sh.addTagRange("saas_db.accounts", { tenantId: "tenant-001" }, { tenantId: "tenant-100" }, "TenantZoneA");
    ```
2.  **Enforce Query Filters at the Application Layer**:
    Implement a database filter interceptor to inject the `tenantId` scope automatically (see Java code below).
3.  **Deploy Rate Limiters**:
    Apply database connection rate limiters per tenant at the API gateway layer to prevent resource starvation.

### 4. Code Artifact: Java Spring Boot MongoDB Tenant Interceptor
Save this class as `TenantInterceptor.java` to enforce tenant scope checks automatically:
```java
package com.example.saas;

import org.bson.Document;
import org.springframework.data.mongodb.core.mapping.event.BeforeConvertCallback;
import org.springframework.data.mongodb.core.mapping.event.BeforeSaveCallback;
import org.springframework.stereotype.Component;

@Component
public class TenantInterceptor implements BeforeConvertCallback<TenantEntity>, BeforeSaveCallback<TenantEntity> {

    @Override
    public TenantEntity onBeforeConvert(TenantEntity entity, String collection) {
        String currentTenant = TenantContext.getCurrentTenantId();
        if (currentTenant == null) {
            throw new IllegalStateException("Authentication context is missing tenant scope ID!");
        }
        entity.setTenantId(currentTenant);
        return entity;
    }

    @Override
    public TenantEntity onBeforeSave(TenantEntity entity, Document document, String collection) {
        document.put("tenantId", TenantContext.getCurrentTenantId());
        return entity;
    }
}
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Database-per-Tenant vs Shared Collection**: Database-per-tenant guarantees isolation but scales poorly due to open file descriptors and collection overhead limits. Shared-collection scales well but requires strict access controls.
*   **Zoned Sharding**: Use zoned sharding to isolate enterprise tenants to dedicated nodes while keeping standard tenants on shared nodes.

---

## 13. Hands-on Lab Exercise: Creating an Automated Cold Data Archiver

### 1. Objective and Scenario
Build an automated background process in Node.js to scan collections for documents older than 90 days, archive them to a secondary system, and purge them from the primary collection.

### 2. Code Implementation: `cold-archiver.js`
Create a file named `cold-archiver.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function archiveOldData() {
  const client = new MongoClient("mongodb://localhost:27017");
  try {
    await client.connect();
    const db = client.db("saas_db");
    
    const cutOffDate = new Date();
    cutOffDate.setDate(cutOffDate.getDate() - 90);
    
    console.log(`Searching for records created before: ${cutOffDate.toISOString()}`);
    
    const oldRecords = await db.collection("transactions")
      .find({ createdAt: { $lt: cutOffDate } })
      .toArray();
      
    console.log(`Found ${oldRecords.length} records ready for archiving.`);
    
    if (oldRecords.length > 0) {
      // Write to archive collection
      await db.collection("transactions_archive").insertMany(oldRecords);
      console.log("Archived documents successfully written to transactions_archive.");
      
      // Delete from active collection
      const deleteResult = await db.collection("transactions")
        .deleteMany({ createdAt: { $lt: cutOffDate } });
      console.log(`Purged ${deleteResult.deletedCount} records from active transactions collection.`);
    }
  } finally {
    await client.close();
  }
}
archiveOldData().catch(console.dir);
```

### 3. Lab Verification Steps
1.  Run the archiver script:
    ```bash
    node cold-archiver.js
    ```
2.  Verify the count in both target collections.

---

## 14. SaaS Multi-Tenancy & Data Isolation Reference

### 1. Key Isolation Configurations
Design models to enforce tenant safety boundaries:
*   `tenantId`: The database field utilized to scope documents in shared collections.
*   `shardKey`: Incorporates tenant scope variables to distribute client workloads.

### 2. Operational Diagnostic Commands
Audit isolation constraints:
```javascript
// Retrieve collection storage details split by tenant criteria
db.collection.aggregate([
  { $group: { _id: "$tenantId", totalStorageBytes: { $sum: { $bsonSize: "$$ROOT" } } } }
]);
```

### 3. Senior Engineer's Production Checklist
*   [ ] Implement query filter interceptors to inject tenant scope filters automatically.
*   [ ] Deploy database rate-limiters at the API layer to prevent resource starvation.
*   [ ] Use zoned sharding to isolate high-throughput tenants to dedicated hardware nodes.

---

## 15. Advanced Operational Diagnostic Playbook: Cold Storage Archiving with Atlas Data Federation

### 1. Cold Data Isolation and Tiering Strategy
For high-volume SaaS applications, keeping historical data in active collections slows down database queries and increases storage costs. A senior architect must implement a cold storage archiving policy. By transitioning records older than 90 days from primary replica nodes to AWS S3 buckets (cold storage), you keep active indexes small and memory-resident. You can use Atlas Data Federation to query active and archived collections simultaneously using unified aggregation queries.

### 2. Unified Query Implementation Script
Save the following aggregation query block as `federated-query.js`. It performs a unified query across the active MongoDB collection and the archived S3 files:
```javascript
// Perform a federated query across active database and S3 cold files
db.getSiblingDB("saas_db").transactions.aggregate([
  {
    $lookup: {
      from: "s3_archive_collection",
      localField: "tenantId",
      foreignField: "tenantId",
      as: "historicalRecords"
    }
  },
  {
    $project: {
      tenantId: 1,
      currentBalance: "$balance",
      archivedBalanceSum: { $sum: "$historicalRecords.amount" }
    }
  }
]);
```

### 3. Step-by-Step Resolution Runbook
1.  **Establish Data Federation Storage Mappings**:
    Define data stores in the Atlas Data Federation console, mapping active database collections and targets in the S3 bucket.
2.  **Configure Cold Storage Partitioning**:
    Ensure archived BSON files are structured in S3 using partitioned paths (e.g. `/year=YYYY/month=MM/tenantId=ID/`) to allow query engines to perform partition pruning.
3.  **Run Scheduled Retention Scripts**:
    Deploy background execution cron tasks to transfer data and verify delete completion logs regularly.
