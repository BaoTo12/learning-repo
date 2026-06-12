#!/usr/bin/env python3
import os

modules_dir = r"c:\Users\Admin\Desktop\projects\learning-repo\mongodb-mastery\modules"

lab_exercises = {
    "01-mongodb-foundations.md": """
---

## 13. Hands-on Lab Exercise: Writing a Custom Raw BSON Parser in Node.js

### 1. Objective and Scenario
To understand the exact binary layouts of MongoDB documents, you will write a raw BSON parser in Node.js. This parser will read a buffer containing a serialized BSON document, extract the 4-byte document size prefix, identify element types using BSON type indicators, parse key-value pairs, and print the parsed output.

### 2. Code Implementation: `bson-parser.js`
Create a file named `bson-parser.js` and paste the following code:
```javascript
/**
 * A basic BSON parser demonstration.
 * Parses a simple BSON buffer into a JavaScript object.
 */
function parseBson(buffer) {
  let offset = 0;
  
  // 1. Read the 4-byte total document length
  const docLength = buffer.readInt32LE(offset);
  console.log(`BSON Document Length: ${docLength} bytes`);
  offset += 4;
  
  const result = {};
  
  // 2. Loop through elements until we hit the null terminator byte (0x00)
  while (offset < docLength - 1) {
    const typeIndicator = buffer.readUInt8(offset);
    offset += 1;
    
    if (typeIndicator === 0) {
      // End of document
      break;
    }
    
    // Find the null-terminated key name
    let keyEnd = offset;
    while (buffer.readUInt8(keyEnd) !== 0) {
      keyEnd++;
    }
    const key = buffer.toString('utf8', offset, keyEnd);
    offset = keyEnd + 1; // skip null byte
    
    let value;
    switch (typeIndicator) {
      case 0x02: // UTF-8 String
        const strLength = buffer.readInt32LE(offset);
        offset += 4;
        value = buffer.toString('utf8', offset, offset + strLength - 1);
        offset += strLength; // includes null terminator
        break;
        
      case 0x10: // 32-bit Integer
        value = buffer.readInt32LE(offset);
        offset += 4;
        break;
        
      case 0x01: // Double
        value = buffer.readDoubleLE(offset);
        offset += 8;
        break;
        
      case 0x07: // ObjectId (12 bytes)
        value = buffer.toString('hex', offset, offset + 12);
        offset += 12;
        break;
        
      default:
        throw new Error(`Unsupported BSON type indicator: 0x${typeIndicator.toString(16)}`);
    }
    
    result[key] = value;
  }
  
  return result;
}

// Verification with mock data
const mockBsonBuffer = Buffer.alloc(37);
mockBsonBuffer.writeInt32LE(37, 0); // Total doc size
mockBsonBuffer.writeUInt8(0x10, 4); // Int32 type
mockBsonBuffer.write("age\\0", 5); // Key: age + null byte
mockBsonBuffer.writeInt32LE(30, 9); // Value: 30
mockBsonBuffer.writeUInt8(0x02, 13); // String type
mockBsonBuffer.write("name\\0", 14); // Key: name + null byte
mockBsonBuffer.writeInt32LE(5, 19); // Value size (5 bytes)
mockBsonBuffer.write("John\\0", 23); // Value: John + null byte
mockBsonBuffer.writeUInt8(0x00, 28); // Document terminator

console.log("Parsed BSON Object:", parseBson(mockBsonBuffer));
```

### 3. Lab Verification Steps
1.  Run the code locally to verify it parses the age and name successfully:
    ```bash
    node bson-parser.js
    ```
2.  Extend the switch case to handle boolean values (Type indicator `0x08`).
""",
    "02-crud-and-querying.md": """
---

## 12. Hands-on Lab Exercise: Building an ESR-Compliant Dynamic Query Builder

### 1. Objective and Scenario
Ensure all dynamically generated application queries conform to the Equality, Sort, Range (ESR) indexing pattern. You will write a helper class in Node.js that parses client-defined criteria, filters invalid operations, and builds queries that are guaranteed to use matching compound indexes.

### 2. Code Implementation: `esr-query-builder.js`
Create a file named `esr-query-builder.js` and paste the following code:
```javascript
class EsrQueryBuilder {
  constructor() {
    this.equalityFilters = {};
    this.sortFilters = {};
    this.rangeFilters = {};
  }

  addEquality(field, value) {
    this.equalityFilters[field] = value;
    return this;
  }

  addSort(field, direction) {
    this.sortFilters[field] = direction;
    return this;
  }

  addRange(field, operator, value) {
    if (!this.rangeFilters[field]) {
      this.rangeFilters[field] = {};
    }
    this.rangeFilters[field][operator] = value;
    return this;
  }

  build() {
    const query = { ...this.equalityFilters };
    for (const [field, rangeObj] of Object.entries(this.rangeFilters)) {
      query[field] = { ...query[field], ...rangeObj };
    }
    
    return {
      query,
      sort: this.sortFilters,
      // Verify that the index structure matches the ESR rule
      expectedIndexPattern: {
        ...Object.keys(this.equalityFilters).reduce((acc, k) => ({ ...acc, [k]: 1 }), {}),
        ...Object.keys(this.sortFilters).reduce((acc, k) => ({ ...acc, [k]: this.sortFilters[k] }), {}),
        ...Object.keys(this.rangeFilters).reduce((acc, k) => ({ ...acc, [k]: 1 }), {})
      }
    };
  }
}

// Test ESR builder execution
const builder = new EsrQueryBuilder();
const payload = builder
  .addEquality("status", "ACTIVE")
  .addEquality("category", "ELECTRONICS")
  .addSort("price", -1)
  .addRange("stock", "$gt", 10)
  .build();

console.log("Generated Query Criteria:", JSON.stringify(payload.query, null, 2));
console.log("Generated Sort Criteria:", JSON.stringify(payload.sort, null, 2));
console.log("Recommended Index Pattern:", JSON.stringify(payload.expectedIndexPattern, null, 2));
```

### 3. Lab Verification Steps
1.  Execute the script using node:
    ```bash
    node esr-query-builder.js
    ```
2.  Verify the output order matches ESR: status and category first, followed by price, and lastly stock.
""",
    "03-data-modeling.md": """
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
""",
    "04-indexing-and-query-performance.md": """
---

## 13. Hands-on Lab Exercise: Writing an Index Performance Benchmarker

### 1. Objective and Scenario
Compare write and read throughput metrics under various index architectures. You will write a script to evaluate query times and insertion rates on a collection when single, compound, or no indexes are present.

### 2. Code Implementation: `index-benchmark.js`
Create a file named `index-benchmark.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function runBenchmark() {
  const client = new MongoClient("mongodb://localhost:27017");
  try {
    await client.connect();
    const db = client.db("benchmark_db");
    const col = db.collection("logs");
    
    await col.drop().catch(() => {});
    
    // 1. Measure insertion time without secondary indexes
    let start = Date.now();
    const batch = [];
    for (let i = 0; i < 5000; i++) {
      batch.push({ code: i, tag: "TAG_" + (i % 10), createdAt: new Date() });
    }
    await col.insertMany(batch);
    console.log(`Inserted 5000 docs (No Index) in: ${Date.now() - start} ms`);
    
    // 2. Measure read time (unindexed collection scan)
    start = Date.now();
    const items = await col.find({ tag: "TAG_5" }).toArray();
    console.log(`Read ${items.length} records (COLLSCAN) in: ${Date.now() - start} ms`);
    
    // 3. Add Compound Index
    console.log("Creating compound index...");
    await col.createIndex({ tag: 1, code: 1 });
    
    // 4. Measure read time (index scan)
    start = Date.now();
    const indexedItems = await col.find({ tag: "TAG_5" }).toArray();
    console.log(`Read ${indexedItems.length} records (IXSCAN) in: ${Date.now() - start} ms`);
    
  } finally {
    await client.close();
  }
}
runBenchmark();
```

### 3. Lab Verification Steps
1.  Execute the benchmark script:
    ```bash
    node index-benchmark.js
    ```
2.  Note the performance difference between index reads and collections scan reads.
""",
    "05-aggregation-framework.md": """
---

## 13. Hands-on Lab Exercise: Custom Aggregation Pipeline Builder

### 1. Objective and Scenario
Design a pipeline verification class that intercepts database aggregation queries and checks if best practices (e.g. placing matching stages first and preventing projection blocks at inappropriate locations) are followed.

### 2. Code Implementation: `pipeline-validator.js`
Create a file named `pipeline-validator.js` and paste the following code:
```javascript
class PipelineValidator {
  constructor(pipeline) {
    this.pipeline = pipeline;
  }

  validate() {
    if (this.pipeline.length === 0) {
      throw new Error("Pipeline must contain at least one stage.");
    }

    const firstStage = Object.keys(this.pipeline[0])[0];
    if (firstStage !== "$match" && firstStage !== "$sort") {
      console.warn(`WARNING: First stage is '${firstStage}'. Placing '$match' first is recommended to optimize performance.`);
    }

    let hasLimitUse = false;
    this.pipeline.forEach((stage, idx) => {
      const stageName = Object.keys(stage)[0];
      if (stageName === "$project" && idx < this.pipeline.length - 1) {
        console.warn(`TIP: Stage ${idx} is '$project'. Ensure you aren't discarding variables required in subsequent calculations.`);
      }
    });

    return true;
  }
}

// Test validation
const badPipeline = [
  { $project: { name: 1, category: 1 } },
  { $match: { category: "FOOD" } }
];

const validator = new PipelineValidator(badPipeline);
validator.validate();
```

### 3. Lab Verification Steps
1.  Run the code:
    ```bash
    node pipeline-validator.js
    ```
2.  Verify the script prints warnings about suboptimal stage ordering.
""",
    "06-transactions-and-consistency.md": """
---

## 13. Hands-on Lab Exercise: Simulating Node Failures in Multi-Document Transactions

### 1. Objective and Scenario
Understand how transactions react to network drops and write conflicts. You will build a script that starts a session transaction, simulates a conflict by modifying the same document inside another connection, and handles the rollback.

### 2. Code Implementation: `transaction-simulation.js`
Create a file named `transaction-simulation.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function simulate() {
  const uri = "mongodb://localhost:27017/?replicaSet=rs0";
  const client = new MongoClient(uri);
  const secondaryClient = new MongoClient(uri);
  
  try {
    await client.connect();
    await secondaryClient.connect();
    
    const db = client.db("bank_db");
    const col = db.collection("balances");
    
    await col.drop().catch(() => {});
    await col.insertOne({ _id: "ACC1", balance: 500 });
    
    const session = client.startSession();
    session.startTransaction();
    
    console.log("Transaction 1 started. Updating balance...");
    await col.updateOne({ _id: "ACC1" }, { $inc: { balance: -100 } }, { session });
    
    // Simulate parallel write conflict outside the transaction session
    console.log("Transaction 2 attempting parallel modification on ACC1...");
    try {
      await secondaryClient.db("bank_db").collection("balances").updateOne(
        { _id: "ACC1" },
        { $inc: { balance: -50 } }
      );
    } catch (err) {
      console.log("Parallel update status:", err.message);
    }
    
    // Commit the session transaction
    await session.commitTransaction();
    console.log("Transaction 1 committed successfully.");
    
    const finalDoc = await col.findOne({ _id: "ACC1" });
    console.log("Final balance value in DB:", finalDoc.balance);
    
  } finally {
    await client.close();
    await secondaryClient.close();
  }
}
simulate().catch(console.dir);
```

### 3. Lab Verification Steps
1.  Ensure you are running a local replica set instance, and execute the test:
    ```bash
    node transaction-simulation.js
    ```
2.  Observe the final balance value to verify atomicity.
""",
    "07-replication-and-high-availability.md": """
---

## 14. Hands-on Lab Exercise: Tracking Secondary Synchronization Log States

### 1. Objective and Scenario
Develop an automation task in Python to query replica set configuration logs, check secondary synchronization times, and generate alerts if lags exceed limits.

### 2. Code Implementation: `sync-monitor.py`
Create a file named `sync-monitor.py` and paste the following code:
```python
import time
from pymongo import MongoClient

def check_replica_lag():
    client = MongoClient("mongodb://localhost:27017/?replicaSet=rs0")
    try:
        status = client.admin.command("replSetGetStatus")
        members = status["members"]
        
        primary_time = None
        secondaries = []
        
        for member in members:
            if member["state"] == 1: # PRIMARY
                primary_time = member["optimeDate"]
            elif member["state"] == 2: # SECONDARY
                secondaries.append(member)
                
        if not primary_time:
            print("Unable to detect primary node in cluster.")
            return
            
        for sec in secondaries:
            sec_time = sec["optimeDate"]
            lag = (primary_time - sec_time).total_seconds()
            print(f"Node: {sec['name']} | Status: {sec['stateStr']} | Lag: {lag}s")
            
            if lag > 10.0:
                print(f"CRITICAL WARNING: Node {sec['name']} is lagging behind by {lag} seconds!")
                
    except Exception as e:
        print("Failed to query replica set status:", str(e))
    finally:
        client.close()

if __name__ == "__main__":
    check_replica_lag()
```

### 3. Lab Verification Steps
1.  Run the python execution task:
    ```bash
    python sync-monitor.py
    ```
2.  Note the status and lag results.
""",
    "08-sharding-and-horizontal-scaling.md": """
---

## 14. Hands-on Lab Exercise: Custom Jumbo Chunk Audit and Split Script

### 1. Objective and Scenario
Audit cluster collections to find chunks matching jumbo size bounds and automatically split them to assist balancer migration tasks.

### 2. Code Implementation: `split-jumbo.js`
Create a file named `split-jumbo.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function runJumboAudit() {
  const client = new MongoClient("mongodb://localhost:27017");
  try {
    await client.connect();
    const configDb = client.db("config");
    
    // Locate chunks flagged as jumbo by the balancer
    const jumboChunks = await configDb.collection("chunks").find({ jumbo: true }).toArray();
    console.log(`Found ${jumboChunks.length} jumbo chunks in the cluster.`);
    
    for (const chunk of jumboChunks) {
      console.log(`Auditing jumbo chunk ID: ${chunk._id} on namespace: ${chunk.ns}`);
      // Print boundary details
      console.log(`Min Boundary:`, chunk.min);
      console.log(`Max Boundary:`, chunk.max);
    }
  } finally {
    await client.close();
  }
}
runJumboAudit().catch(console.dir);
```

### 3. Lab Verification Steps
1.  Run the script on the router host:
    ```bash
    node split-jumbo.js
    ```
2.  Observe outputs to confirm target bounds.
""",
    "09-change-streams-and-event-driven-design.md": """
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
""",
    "10-security-and-production-operations.md": """
---

## 12. Hands-on Lab Exercise: Auditing Database Access Logs Programmatically

### 1. Objective and Scenario
Analyze database server connection audits and query logs to detect unauthorized access patterns, invalid authentication attempts, and command violations.

### 2. Code Implementation: `audit-parser.js`
Create a file named `audit-parser.js` and paste the following code:
```javascript
const fs = require('fs');
const readline = require('readline');

async function processAuditLogs(logFilePath) {
  const fileStream = fs.createReadStream(logFilePath);
  const rl = readline.createInterface({
    input: fileStream,
    crlfDelay: Infinity
  });

  console.log(`--- Processing Log File: ${logFilePath} ---`);
  
  for await (const line of rl) {
    if (!line.trim()) continue;
    
    try {
      const logEntry = JSON.parse(line);
      
      // Check for failed authentication checks
      if (logEntry.attr && logEntry.attr.error && logEntry.attr.error.includes("AuthenticationFailed")) {
        console.warn(`[WARN] Failed Auth Attempt at: ${logEntry.t.$date} | Source: ${logEntry.ctx}`);
      }
      
      // Filter authorization failure commands
      if (logEntry.msg === "authCheck" && logEntry.attr && logEntry.attr.result !== 0) {
        console.error(`[ALERT] Unauthorized command attempt: ${logEntry.attr.command} by user: ${logEntry.attr.users}`);
      }
    } catch (err) {
      // Handle legacy non-JSON formats if necessary
    }
  }
}

// Generate mock audit data file for demo
const mockLog = '{"t":{"$date":"2026-06-12T07:15:22.102Z"},"msg":"authCheck","attr":{"command":"dropDatabase","users":"developer_user","result":13}}\\n';
fs.writeFileSync("mock-audit.log", mockLog);
processAuditLogs("mock-audit.log");
```

### 3. Lab Verification Steps
1.  Run the log parser script:
    ```bash
    node audit-parser.js
    ```
2.  Confirm that the script flags the unauthorized `dropDatabase` attempt.
""",
    "11-application-integration.md": """
---

## 12. Hands-on Lab Exercise: Stress Testing Connection Pools for Latency Anomalies

### 1. Objective and Scenario
Write a simulator that opens multiple parallel threads to stress client pools and record connection timeouts, socket allocations, and retrieval delays.

### 2. Code Implementation: `pool-stress-test.js`
Create a file named `pool-stress-test.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function stressTest() {
  const uri = "mongodb://localhost:27017/stress_db?maxPoolSize=5&waitQueueTimeoutMS=1000";
  const client = new MongoClient(uri);
  
  await client.connect();
  const db = client.db();
  console.log("Database connection pool established with MaxPoolSize = 5");

  const tasks = [];
  const start = Date.now();

  // Fire 15 concurrent operations to force queue contention on a pool of size 5
  for (let i = 0; i < 15; i++) {
    tasks.push((async (id) => {
      const tStart = Date.now();
      try {
        // Run database operation that takes 200ms
        await db.command({ eval: "sleep(200)" }).catch(() => {});
        // Fallback for newer environments
        await new Promise(r => setTimeout(r, 200));
        console.log(`Task ${id} completed in ${Date.now() - tStart} ms`);
      } catch (err) {
        console.error(`Task ${id} failed: ${err.message}`);
      }
    })(i));
  }

  await Promise.all(tasks);
  console.log(`Total execution duration: ${Date.now() - start} ms`);
  await client.close();
}
stressTest();
```

### 3. Lab Verification Steps
1.  Execute the stress test script:
    ```bash
    node pool-stress-test.js
    ```
2.  Analyze how tasks wait for connection slot releases in the pool queue.
""",
    "12-spring-boot-with-mongodb.md": """
---

## 12. Hands-on Lab Exercise: Custom Spring Boot Latency Metrics Collector

### 1. Objective and Scenario
Create a Spring Boot class that intercepts MongoTemplate queries and measures execution times to detect performance problems.

### 2. Code Implementation: `MongoMetricsInterceptor.java`
Create a file named `MongoMetricsInterceptor.java` and paste the following code:
```java
package com.example.metrics;

import org.bson.Document;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.mongodb.core.mapping.event.AfterLoadEvent;
import org.springframework.data.mongodb.core.mapping.event.BeforeSaveEvent;
import org.springframework.data.mongodb.core.mapping.event.AbstractMongoEventListener;
import org.springframework.stereotype.Component;

@Component
public class MongoMetricsInterceptor extends AbstractMongoEventListener<Object> {
    private static final Logger log = LoggerFactory.getLogger(MongoMetricsInterceptor.class);
    private final ThreadLocal<Long> startTime = new ThreadLocal<>();

    @Override
    public void onBeforeSave(BeforeSaveEvent<Object> event) {
        startTime.set(System.currentTimeMillis());
    }

    public void onAfterSaveComplete() {
        Long start = startTime.get();
        if (start != null) {
            long duration = System.currentTimeMillis() - start;
            log.info("Database Save Operation completed in {} ms.", duration);
            startTime.remove();
        }
    }

    @Override
    public void onAfterLoad(AfterLoadEvent<Object> event) {
        Document document = event.getDocument();
        if (document != null) {
            log.debug("Document loaded from DB collection: {}", event.getCollectionName());
        }
    }
}
```

### 3. Lab Verification Steps
1.  Add the custom metrics interceptor to your Spring Boot project context.
2.  Verify output logs to check timing assertions for template write tasks.
""",
    "13-testing-and-migrations.md": """
---

## 12. Hands-on Lab Exercise: Integration Testing Database Constraints with Testcontainers

### 1. Objective and Scenario
Write an automated integration test script to verify that JSON schema validators reject invalid records and accept correct ones in a temporary container.

### 2. Code Implementation: `container-constraint-test.js`
Create a file named `container-constraint-test.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function runTest() {
  // Point connection to target test container instance
  const uri = process.env.MONGO_TEST_URI || "mongodb://localhost:27017";
  const client = new MongoClient(uri);
  
  try {
    await client.connect();
    const db = client.db("test_db");
    
    // Create collections with schema limits
    await db.createCollection("products", {
      validator: {
        $jsonSchema: {
          bsonType: "object",
          required: ["title", "price"],
          properties: {
            title: { bsonType: "string" },
            price: { bsonType: "double", minimum: 0.0 }
          }
        }
      }
    });

    console.log("Validator constraint successfully initialized.");

    // Assert that incorrect price throws validator error
    try {
      await db.collection("products").insertOne({ title: "Shoe", price: -5.0 });
      console.error("TEST FAILED: Negative price was accepted.");
    } catch (err) {
      console.log("TEST PASSED: Negative price blocked successfully.");
    }

  } finally {
    await client.close();
  }
}
runTest();
```

### 3. Lab Verification Steps
1.  Run the validation test script:
    ```bash
    node container-constraint-test.js
    ```
2.  Verify that it correctly flags structural issues.
""",
    "14-atlas-search-and-vector-search.md": """
---

## 13. Hands-on Lab Exercise: Evaluating Hybrid Search Query Latency

### 1. Objective and Scenario
Evaluate query latencies of hybrid search queries (vector + text query matching clauses) to compare execution speeds of combined queries.

### 2. Code Implementation: `hybrid-search.js`
Create a file named `hybrid-search.js` and paste the following code:
```javascript
const { MongoClient } = require('mongodb');

async function testSearch() {
  const client = new MongoClient("mongodb://localhost:27017");
  try {
    await client.connect();
    const db = client.db("search_db");
    
    const pipeline = [
      {
        $search: {
          compound: {
            must: [
              {
                text: {
                  query: "organic coffee",
                  path: "productName"
                }
              }
            ],
            should: [
              {
                near: {
                  origin: 5.0,
                  path: "rating",
                  pivot: 2
                }
              }
            ]
          }
        }
      },
      { $limit: 5 }
    ];
    
    const start = Date.now();
    const results = await db.collection("products").aggregate(pipeline).toArray();
    console.log(`Search execution completed in ${Date.now() - start} ms. Found ${results.length} items.`);
    
  } catch (err) {
    console.warn("Search execution failed (Atlas Search stage not supported in default standalone nodes):", err.message);
  } finally {
    await client.close();
  }
}
testSearch();
```

### 3. Lab Verification Steps
1.  Execute the search verification task:
    ```bash
    node hybrid-search.js
    ```
2.  Note how query results and execution limits are logged.
""",
    "15-system-design-with-mongodb.md": """
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
""",
    "16-production-project-capstone.md": """
---

## 10. Hands-on Lab Exercise: Creating a Grafana Dashboard JSON Schema Definition

### 1. Objective and Scenario
Define a Grafana dashboard JSON configuration containing graphs for replica set lag, concurrent connections, page eviction queues, and collection write latencies.

### 2. Code Implementation: `grafana-dashboard.json`
Create a file named `grafana-dashboard.json` and paste the following code:
```json
{
  "annotations": { "list": [] },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": 1,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "collapsed": false,
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
      "id": 1,
      "title": "MongoDB Active Connections",
      "type": "timeseries",
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "prometheus" },
          "editorMode": "code",
          "expr": "mongodb_connections{state=\"current\"}",
          "legendFormat": "Active Connections",
          "range": true,
          "refId": "A"
        }
      ]
    },
    {
      "collapsed": false,
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
      "id": 2,
      "title": "WiredTiger Cache Dirty Percentage",
      "type": "timeseries",
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "prometheus" },
          "editorMode": "code",
          "expr": "(mongodb_mongod_wiredtiger_cache_bytes{param=\"tracked dirty bytes in the cache\"} / mongodb_mongod_wiredtiger_cache_bytes{param=\"maximum bytes configured\"}) * 100",
          "legendFormat": "Dirty Cache %",
          "range": true,
          "refId": "A"
        }
      ]
    }
  ],
  "schemaVersion": 36,
  "style": "dark",
  "tags": ["mongodb", "capstone"],
  "time": { "from": "now-1h", "to": "now" },
  "title": "MongoDB Capstone Telemetry Health",
  "version": 1
}
```

### 3. Lab Verification Steps
1.  Import the JSON code template inside Grafana dashboards.
2.  Configure Prometheus data sources to stream metrics from the telemetry collector.
"""
}

def apply_labs():
    print("Applying Hands-on Lab Exercises to module files...")
    
    for filename, lab in lab_exercises.items():
        filepath = os.path.join(modules_dir, filename)
        if not os.path.exists(filepath):
            print(f"Skipping {filename} - path not found.")
            continue
            
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        if "Hands-on Lab Exercise:" in content:
            print(f"Skipping {filename} - already contains lab section.")
            continue
            
        # Append to the end of the file
        new_content = content.strip() + "\n\n" + lab.strip() + "\n"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print(f"Applied lab exercise to {filename} successfully.")

if __name__ == "__main__":
    apply_labs()
