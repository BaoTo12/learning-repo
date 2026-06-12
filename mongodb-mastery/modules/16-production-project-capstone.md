# Module 16: Production Project Capstone

## 1. What Problem This Module Solves
To consolidate the advanced concepts learned throughout this course, developers must build a production-grade, end-to-end system. Mocks and small exercise snippets are insufficient to understand the operational challenges of deploying a system that integrates schema validations, index optimization, multi-document transactions, connection pooling, and horizontal sharding.

This capstone module presents the design, code, configurations, and verification steps for an **IoT Sensor Telemetry Processor and Alerting Engine**. This system must accept high-volume sensor metrics, parse and validate BSON payloads, store them efficiently using the Bucket Pattern, run rolling aggregation pipelines to update materialized metrics views, and handle alert states using atomic transactions.

---

## 2. Why This Topic Matters
Building an enterprise-scale data pipeline requires coordinating multiple database features. If you implement an IoT telemetry database without utilizing the Bucket Pattern, the index size will grow rapidly, exhausting RAM and causing query latency spikes. Similarly, running aggregation reports on millions of active records requires structured pipelines that run in background tasks and merge precomputed results to prevent resource contention.

This capstone project provides complete, production-ready source code, configuration files, and deployment descriptors. It serves as a reference architecture for building high-throughput, resilient applications on MongoDB.

---

## 3. Capstone Architecture & Specifications

The system coordinates the following components:
1.  **Ingestion Layer**: A Node.js API that accepts sensor readings, validates them, and writes them using the Bucket Pattern.
2.  **Storage Layer**: A sharded MongoDB cluster configured with schema validation rules.
3.  **Aggregation Engine**: A scheduled processor that runs rolling average metrics and writes them to a materialized view collection.
4.  **Alerting Service**: A Java/Spring Boot service that monitors metric bounds and updates alert states atomically.

---

## 4. Complete Project Code Listings

This section contains all configurations, scripts, and code files required to run the telemetry processor.

---

### 4.1 Deployment: `docker-compose.yml`
This file configures a 3-node replica set with directory volumes, TLS configurations, and administrative tools.

```yaml
version: '3.8'

services:
  mongo-primary:
    image: mongo:6.0
    container_name: mongo_primary
    command: mongod --replSet rs0 --port 27017 --bind_ip_all
    volumes:
      - primary_data:/data/db
    ports:
      - 27017:27017

  mongo-secondary1:
    image: mongo:6.0
    container_name: mongo_secondary1
    command: mongod --replSet rs0 --port 27017 --bind_ip_all
    volumes:
      - secondary1_data:/data/db

  mongo-secondary2:
    image: mongo:6.0
    container_name: mongo_secondary2
    command: mongod --replSet rs0 --port 27017 --bind_ip_all
    volumes:
      - secondary2_data:/data/db

volumes:
  primary_data:
  secondary1_data:
  secondary2_data:
```

---

### 4.2 Replica Set Initialization: `init-replica.sh`
```bash
#!/usr/bin/env bash
# Replica Set Initialization Script

echo "Initializing replica set rs0..."
docker exec -it mongo_primary mongosh --eval '
  rs.initiate({
    _id: "rs0",
    members: [
      { _id: 0, host: "mongo_primary:27017", priority: 2 },
      { _id: 1, host: "mongo_secondary1:27017", priority: 1 },
      { _id: 2, host: "mongo_secondary2:27017", priority: 1 }
    ]
  });
  print("Replica set initialization submitted.");
'
sleep 10
docker exec -it mongo_primary mongosh --eval "rs.status()"
```

---

### 4.3 Database Collections Configuration: `setup-db.js`
This script configures JSON Schema validation rules and indexes for the telemetry collections.

```javascript
/**
 * Database Setup Script
 * Enforces schema validation and creates optimized ESR indexes.
 */
const conn = new Mongo("mongodb://localhost:27017/?replicaSet=rs0");
const db = conn.getDB("telemetry_db");

// 1. Create telemetry collection with JSON Schema Validation
db.createCollection("sensor_buckets", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["sensorId", "bucketStart", "bucketEnd", "sampleCount", "samples"],
      properties: {
        sensorId: {
          bsonType: "string",
          pattern: "^SNS-[0-9]{5}$",
          description: "Must be a valid sensor ID format: SNS-XXXXX"
        },
        bucketStart: {
          bsonType: "date"
        },
        bucketEnd: {
          bsonType: "date"
        },
        sampleCount: {
          bsonType: "int",
          minimum: 0,
          maximum: 1000
        },
        samples: {
          bsonType: "array",
          minItems: 0,
          maxItems: 1000,
          items: {
            bsonType: "object",
            required: ["timestamp", "value"],
            properties: {
              timestamp: {
                bsonType: "date"
              },
              value: {
                bsonType: "double",
                minimum: -50.0,
                maximum: 150.0
              }
            }
          }
        }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});

// 2. Create optimized compound index for Bucket searches
db.sensor_buckets.createIndex({ sensorId: 1, bucketStart: -1, bucketEnd: -1 });

// 3. Create alerts collection
db.createCollection("alerts", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["sensorId", "alertType", "status", "createdAt"],
      properties: {
        sensorId: { bsonType: "string" },
        alertType: { enum: ["HIGH_TEMP", "LOW_TEMP", "DISCONNECTED"] },
        status: { enum: ["ACTIVE", "ACKNOWLEDGED", "RESOLVED"] },
        createdAt: { bsonType: "date" }
      }
    }
  }
});

db.alerts.createIndex({ sensorId: 1, status: 1, createdAt: -1 });
print("Database schema validation and indexes configured successfully!");
```

---

### 4.4 Telemetry Ingestion Processor: `ingestion-service.js`
This Node.js service accepts sensor readings, validates them, and writes them using the Bucket Pattern to reduce storage overhead.

```javascript
/**
 * High-Throughput Ingestion Service (Bucket Pattern)
 * Packs multiple sensor readings into a single document bucket.
 */
const { MongoClient } = require('mongodb');
const log = require('console');

class IngestionService {
  constructor(uri) {
    // Configure connection pool and retry behaviors
    this.uri = `${uri}&maxPoolSize=50&retryWrites=true`;
    this.client = new MongoClient(this.uri);
  }

  async start() {
    await this.client.connect();
    this.db = this.client.db('telemetry_db');
    this.buckets = this.db.collection('sensor_buckets');
    log.info("Ingestion service successfully connected to MongoDB.");
  }

  async ingestReading(sensorId, value, timestamp = new Date()) {
    const bucketDurationMs = 60 * 60 * 1000; // 1-hour buckets
    const bucketStartTime = new Date(Math.floor(timestamp.getTime() / bucketDurationMs) * bucketDurationMs);

    try {
      const result = await this.buckets.updateOne(
        {
          sensorId: sensorId,
          bucketStart: bucketStartTime,
          sampleCount: { $lt: 60 } // Limit bucket to 60 readings (one per minute)
        },
        {
          $setOnInsert: {
            bucketEnd: new Date(bucketStartTime.getTime() + bucketDurationMs - 1),
            samples: []
          },
          $push: {
            samples: { timestamp: timestamp, value: parseFloat(value) }
          },
          $inc: { sampleCount: 1 }
        },
        { upsert: true }
      );
      
      return result;
    } catch (error) {
      log.error(`Failed to ingest reading for sensor ${sensorId}:`, error.message);
      throw error;
    }
  }

  async close() {
    await this.client.close();
  }
}

module.exports = IngestionService;
```

---

### 4.5 Ingestion Load Simulator: `simulator.js`
To verify the performance of the Bucket Pattern under high write loads, you can run the following load simulator script. It spawns 10 parallel sensors that send data continuously.

```javascript
/**
 * Sensor Data Generator Simulator
 * Generates continuous metrics streams for multiple sensors.
 */
const IngestionService = require('./ingestion-service');
const log = require('console');

const MONGO_URI = "mongodb://localhost:27017/?replicaSet=rs0";
const service = new IngestionService(MONGO_URI);

async function startSimulation() {
  await service.start();
  log.info("Simulator started. Generating data for 10 sensors...");

  const sensors = Array.from({ length: 10 }, (_, i) => `SNS-1000${i}`);

  // Simulate write pings every 5 seconds for each sensor
  setInterval(async () => {
    for (const sensorId of sensors) {
      const value = parseFloat((20.0 + Math.random() * 80.0).toFixed(2));
      try {
        await service.ingestReading(sensorId, value);
      } catch (err) {
        log.error(`Telemetry simulation write failed for ${sensorId}:`, err.message);
      }
    }
  }, 5000);
}

startSimulation().catch(err => log.error("Failed to start simulator:", err));
```

---

### 4.6 Aggregation Engine: `aggregation-worker.js`
This Node.js worker executes aggregation pipelines in background tasks to calculate rolling averages and update materialized metrics views.

```javascript
/**
 * Metrics Aggregation Engine
 * Runs aggregation pipelines and updates the materialized metrics view.
 */
const { MongoClient } = require('mongodb');
const log = require('console');

class AggregationWorker {
  constructor(uri) {
    this.client = new MongoClient(uri);
  }

  async start() {
    await this.client.connect();
    this.db = this.client.db('telemetry_db');
    log.info("Aggregation worker connected to database.");
  }

  async runHourlyMetrics() {
    const buckets = this.db.collection('sensor_buckets');
    log.info("Starting hourly metrics aggregation...");

    try {
      const startTime = Date.now();
      await buckets.aggregate([
        {
          // Deconstruct samples array
          $unwind: "$samples"
        },
        {
          // Group by sensor and hour
          $group: {
            _id: {
              sensorId: "$sensorId",
              hour: {
                $dateTrunc: {
                  date: "$samples.timestamp",
                  unit: "hour"
                }
              }
            },
            averageValue: { $avg: "$samples.value" },
            minValue: { $min: "$samples.value" },
            maxValue: { $max: "$samples.value" },
            readingCount: { $sum: 1 }
          }
        },
        {
          // Project metrics document structure
          $project: {
            _id: 0,
            sensorId: "$_id.sensorId",
            hour: "$_id.hour",
            averageValue: 1,
            minValue: 1,
            maxValue: 1,
            readingCount: 1,
            lastCalculated: new Date()
          }
        },
        {
          // Merge results into the materialized view collection
          $merge: {
            into: "hourly_sensor_metrics",
            on: ["sensorId", "hour"], // Must match a unique index on the destination collection
            whenMatched: "replace",
            whenNotMatched: "insert"
          }
        }
      ]).toArray(); // Force pipeline execution

      const duration = Date.now() - startTime;
      log.info(`Aggregation completed in ${duration}ms.`);

    } catch (error) {
      log.error("Aggregation worker task failed:", error.message);
    }
  }

  async close() {
    await this.client.close();
  }
}

module.exports = AggregationWorker;
```

---

### 4.7 Java Core Alerting Service: `AlertingService.java`
This Spring Boot class monitors metric boundaries and updates alert states atomically.

```java
package com.ecommerce.domain.order;

import com.mongodb.MongoException;
import com.mongodb.MongoTransactionException;
import com.mongodb.WriteConcern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.mongodb.MongoTransactionManager;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Update;
import org.springframework.stereotype.Service;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.TransactionCallbackWithoutResult;
import org.springframework.transaction.support.TransactionTemplate;
import java.time.Instant;

@Service
public class AlertingService {
    private static final Logger log = LoggerFactory.getLogger(AlertingService.class);
    
    private final MongoTemplate mongoTemplate;
    private final TransactionTemplate transactionTemplate;

    public AlertingService(MongoTemplate mongoTemplate, MongoTransactionManager transactionManager) {
        this.mongoTemplate = mongoTemplate;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
    }

    public void processThresholdCheck(String sensorId, double value) {
        double upperLimit = 100.0;
        double lowerLimit = 0.0;

        if (value > upperLimit) {
            triggerAlert(sensorId, "HIGH_TEMP");
        } else if (value < lowerLimit) {
            triggerAlert(sensorId, "LOW_TEMP");
        } else {
            resolveAlerts(sensorId);
        }
    }

    public void triggerAlert(final String sensorId, final String alertType) {
        transactionTemplate.execute(new TransactionCallbackWithoutResult() {
            @Override
            protected void doInTransactionWithoutResult(TransactionStatus status) {
                mongoTemplate.setWriteConcern(WriteConcern.MAJORITY);

                Query query = new Query(Criteria.where("sensorId").is(sensorId)
                                                .and("alertType").is(alertType)
                                                .and("status").is("ACTIVE"));
                
                boolean exists = mongoTemplate.exists(query, "alerts");
                if (!exists) {
                    Alert alert = new Alert();
                    alert.setSensorId(sensorId);
                    alert.setAlertType(alertType);
                    alert.setStatus("ACTIVE");
                    alert.setCreatedAt(Instant.now());
                    
                    mongoTemplate.save(alert, "alerts");
                    log.warn("New alert triggered for sensor: {}, type: {}", sensorId, alertType);
                }
            }
        });
    }

    public void resolveAlerts(final String sensorId) {
        transactionTemplate.execute(new TransactionCallbackWithoutResult() {
            @Override
            protected void doInTransactionWithoutResult(TransactionStatus status) {
                mongoTemplate.setWriteConcern(WriteConcern.MAJORITY);

                Query query = new Query(Criteria.where("sensorId").is(sensorId).and("status").is("ACTIVE"));
                Update update = new Update().set("status", "RESOLVED").set("resolvedAt", Instant.now());
                
                var result = mongoTemplate.updateMany(query, update, "alerts");
                if (result.getModifiedCount() > 0) {
                    log.info("Resolved {} active alerts for sensor: {}", result.getModifiedCount(), sensorId);
                }
            }
        });
    }

    public static class Alert {
        private String id;
        private String sensorId;
        private String alertType;
        private String status;
        private Instant createdAt;
        private Instant resolvedAt;

        // Getters and Setters
        public String getId() { return id; }
        public void setId(String id) { this.id = id; }
        public String getSensorId() { return sensorId; }
        public void setSensorId(String sensorId) { this.sensorId = sensorId; }
        public String getAlertType() { return alertType; }
        public void setAlertType(String type) { this.alertType = type; }
        public String getStatus() { return status; }
        public void setStatus(String status) { this.status = status; }
        public Instant getCreatedAt() { return createdAt; }
        public void setCreatedAt(Instant time) { this.createdAt = time; }
        public Instant getResolvedAt() { return resolvedAt; }
        public void setResolvedAt(Instant time) { this.resolvedAt = time; }
    }
}
```

---

### 4.8 Alerting REST Endpoints: `AlertController.java`
The following Java controller class exposes REST endpoints to retrieve active alerts and trigger manual alert resolutions.

```java
package com.ecommerce.domain.order;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import java.util.List;

@RestController
@RequestMapping("/api/alerts")
public class AlertController {

    private final AlertingService alertingService;
    private final MongoTemplate mongoTemplate;

    public AlertController(AlertingService alertingService, MongoTemplate mongoTemplate) {
        this.alertingService = alertingService;
        this.mongoTemplate = mongoTemplate;
    }

    @GetMapping("/active")
    public ResponseEntity<List<AlertingService.Alert>> getActiveAlerts() {
        Query query = new Query(Criteria.where("status").is("ACTIVE"));
        List<AlertingService.Alert> activeAlerts = mongoTemplate.find(query, AlertingService.Alert.class, "alerts");
        return ResponseEntity.ok(activeAlerts);
    }

    @PostMapping("/resolve/{sensorId}")
    public ResponseEntity<String> resolveSensorAlerts(@PathVariable String sensorId) {
        alertingService.resolveAlerts(sensorId);
        return ResponseEntity.ok("Alerts resolution request processed.");
    }
}
```

---

## 5. Verification Plan

Verify the capstone deployment and data pipeline health by executing the following steps.

---

### Step 1: Deploy and Verify Cluster Nodes
1.  Deploy the replica set containers:
    ```bash
    docker-compose up -d
    ```
2.  Initialize the replica set configuration using the initialization script:
    ```bash
    ./init-replica.sh
    ```
3.  Verify that all nodes are online and reporting correct states:
    ```bash
    docker exec -it mongo_primary mongosh --eval "rs.status().members.forEach(m => print(m.name + ' - ' + m.stateStr))"
    ```
    *Expected Output*:
    ```
    mongo_primary:27017 - PRIMARY
    mongo_secondary1:27017 - SECONDARY
    mongo_secondary2:27017 - SECONDARY
    ```

---

### Step 2: Configure Collections and Indexes
1.  Run the collection configuration script:
    ```bash
    mongosh --host "localhost" --port 27017 setup-db.js
    ```
2.  Verify collections are created with schema validation rules:
    ```bash
    mongosh --host "localhost" --port 27017 --eval "db.getSiblingDB('telemetry_db').getCollectionInfos()"
    ```
3.  Confirm index patterns:
    ```bash
    mongosh --host "localhost" --port 27017 --eval "db.getSiblingDB('telemetry_db').sensor_buckets.getIndexes()"
    ```

---

### Step 3: Run Ingestion and Aggregation Pipelines
1.  Write a script to load mock data and run the ingestion service:
    ```javascript
    const IngestionService = require('./ingestion-service');
    const service = new IngestionService("mongodb://localhost:27017/?replicaSet=rs0");
    
    async function loadMockData() {
      await service.start();
      for (let i = 0; i < 60; i++) {
        await service.ingestReading("SNS-10001", 22.4 + (Math.random() * 2), new Date(Date.now() - (i * 60 * 1000)));
      }
      await service.close();
      console.log("Mock data loaded.");
    }
    loadMockData();
    ```
2.  Run the aggregation worker to update materialized metrics:
    ```javascript
    const AggregationWorker = require('./aggregation-worker');
    const worker = new AggregationWorker("mongodb://localhost:27017/telemetry_db?replicaSet=rs0");
    
    async function runAnalytics() {
      await worker.start();
      await worker.db.collection('hourly_sensor_metrics').createIndex({ sensorId: 1, hour: 1 }, { unique: true });
      await worker.runHourlyMetrics();
      await worker.close();
    }
    runAnalytics();
    ```
3.  Query and verify that metrics are precomputed and merged into the destination collection:
    ```bash
    mongosh --host "localhost" --port 27017 --eval "db.getSiblingDB('telemetry_db').hourly_sensor_metrics.find().pretty()"
    ```

---

## 6. Project Architecture Diagram

The diagram below shows the flow of sensor data through the ingestion, storage, aggregation, and alerting layers.

```
 [Physical Sensors]
        │
        ▼ (Ingests metrics)
 [Ingestion Service] ──> [Sensor Buckets Collection] (WiredTiger Storage Engine)
                                │
                                ├───────────────────────────────┐
                                ▼ (Aggregates hourly)           ▼ (Threshold Trigger)
                       [Aggregation Worker]             [Java Alerting Service]
                                │                               │
                                ▼                               ▼
                  [Hourly Metrics Collection]          [Alerts Collection]
                       (Materialized View)              (Active Alerts Log)
```

---

## 7. Capstone Troubleshooting Guide

When running the capstone deployment, utilize these troubleshooting procedures to resolve common execution failures:

#### 1. Thrown: `DocumentFailedValidation` (Error Code 121)
*   **The Issue**: The BSON payload failed database validation rules configured in `setup-db.js`.
*   **Resolution**: Run `db.sensor_buckets.find({ "$expr": { "$eq": [ { "$type": "$sensorId" }, "missing" ] } })` or check value bounds. Ensure `sensorId` matches regex pattern `"^SNS-[0-9]{5}$"` and value is a double.

#### 2. Thrown: `WriteConflict` on `$merge`
*   **The Issue**: The aggregation background worker failed during `$merge` because another process updated the same range.
*   **Resolution**: Wrap the aggregation task execution in a retryable function with exponential backoff, or decrease the frequency of execution to minimize write conflicts.

#### 3. Heartbeats Fail (Replica Set Unstable)
*   **The Issue**: Secondary containers cannot reach the primary node, preventing election majorities.
*   **Resolution**: Check docker logs (`docker logs mongo_primary`) and verify that all containers reside in the same Docker network. Update host names inside `init-replica.sh` to match container host names.

---

---

---

## 8. Production Runbook & Deployment Guidelines

### 1. Deploying the Telemetry Pipeline
Deploy and start the IoT telemetry services in sequence:
1. Start the Docker containers: `docker-compose up -d`
2. Initialize the replica set: `./init-replica.sh`
3. Load database collection schemas and validations: `setup-db.js`
4. Start the ingestion simulator: `node simulator.js`
5. Run the metrics aggregation worker: `node aggregation-worker.js`

### 2. Monitoring Pipeline Performance
Check collection sizes and index statistics:
```bash
mongosh --eval "db.getSiblingDB('telemetry_db').sensor_buckets.stats()"
```
Verify that the average bucket document size remains below 200KB.

## 11. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Ingestion Pipeline Thread Saturation
*   **Failure Mode**: High-volume telemetry pings saturate ingestion threads, causing connection checkout timeouts.
*   **Resolution**: Adjust driver pool sizes (`maxPoolSize`), and implement backpressure queues in ingestion layers.

### 2. Aggregation Worker Out-of-Memory
*   **Failure Mode**: Background aggregation tasks run out of memory when processing large buckets.
*   **Resolution**: Split aggregations into smaller time windows, and use `allowDiskUse: true` for large tasks.

### 3. Container Network Partitions during Elections
*   **Failure Mode**: Network splits prevent replica nodes from electing a primary, stalling ingestion.
*   **Resolution**: Ensure nodes are deployed on robust networks, and use write concerns with appropriate timeouts.

---

## 12. Summary
Deploying high-volume, transactional architectures requires coordinating database features. By using the Bucket Pattern to organize time-series data, writing background aggregation workers to precompute metrics, enforcing database-level schemas, and coordinating write pings using replica sets, senior database engineers build scalable, reliable data pipelines.

---

## 9. Enterprise Case Study: Capstone Project IoT Telemetry Ingestion Bottleneck

### 1. Scenario Description
During a simulated stress test of the capstone IoT telemetry pipeline, the ingestion system failed to process 500,000 metrics per minute. The ingestion worker container instances threw socket exceptions, write queue lengths increased, and telemetry packets were dropped. CPU utilization on the primary MongoDB instance hit 100%, and the system was unable to persist telemetry events in real time.

### 2. Analytical Diagnostic Investigation
The engineering team audited the MongoDB metrics:
```bash
mongosh --eval "db.serverStatus().wiredTiger.concurrentTransactions"
```
**Diagnostic Findings**:
*   The aggregation worker, which generates hourly sensor rollups, was executing collection scans over raw telemetry data while writes were occurring.
*   The raw write operations competed with the aggregation queries for WiredTiger read/write tickets, causing write queues to build.
*   The bucket document sizes were growing beyond 2MB because the simulator was writing data points in a single, un-partitioned array field.

### 3. Step-by-Step Optimization Runbook
To optimize the capstone project pipeline for high-throughput production workloads, the team performed these steps:

1.  **Optimize the Bucket Design**:
    Configure the ingestion script to partition metrics into buckets of 100 records using the bucket pattern:
    ```javascript
    db.sensor_buckets.updateOne(
      { sensorId: sensorId, count: { $lt: 100 } },
      {
        $push: { readings: { timestamp: new Date(), value: readingValue } },
        $inc: { count: 1 }
      },
      { upsert: true }
    );
    ```
2.  **Separate Ingestion and Aggregation Workloads**:
    Configure the aggregation worker to read from secondary replica set nodes to offload queries from the primary node:
    ```javascript
    const client = new MongoClient("mongodb://localhost:27017/?readPreference=secondary");
    ```
3.  **Tune WiredTiger Thread Concurrency**:
    Configure the database to use more concurrent write tickets under write-heavy loads:
    ```javascript
    db.adminCommand({
      setParameter: 1,
      "wiredTigerEngineRuntimeConfig": "concurrent_write_transactions=128"
    });
    ```
4.  **Validate End-to-End Pipeline Performance**:
    Run a simulation test to confirm that ingestion rates remain stable above 500,000 requests per minute.

### 4. Code Artifact: Ingestion Load Test Validation Script
Save this script as `run-load-test.js` to simulate load on the telemetry database:
```javascript
const { MongoClient } = require('mongodb');

async function simulateLoad() {
  const uri = "mongodb://localhost:27017/telemetry_db?maxPoolSize=200";
  const client = new MongoClient(uri);
  await client.connect();
  const db = client.db();
  
  console.log("Starting high-throughput simulation load test...");
  
  const startTime = Date.now();
  let totalWrites = 0;
  
  const promises = [];
  for (let i = 0; i < 10000; i++) {
    const sensorId = "sensor-" + Math.floor(Math.random() * 500);
    const value = Math.random() * 100;
    
    promises.push(
      db.collection("sensor_buckets").updateOne(
        { sensorId: sensorId, count: { $lt: 100 } },
        {
          $push: { readings: { timestamp: new Date(), value: value } },
          $inc: { count: 1 }
        },
        { upsert: true }
      ).then(() => { totalWrites++; })
    );
  }
  
  await Promise.all(promises);
  const duration = (Date.now() - startTime) / 1000;
  console.log(`Simulation finished. Total Writes: ${totalWrites} in ${duration} seconds.`);
  console.log(`Throughput: ${(totalWrites / duration).toFixed(2)} writes/second.`);
  
  await client.close();
}
simulateLoad().catch(console.dir);
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Offload Heavy Queries**: Never run long-running report or aggregation queries on your primary write database. Route reports to replica set secondaries to keep the primary free for write operations.
*   **The Power of Bucketing**: Using the bucketing pattern for time-series data reduces the index size and index update frequency, improving throughput compared to single-document-per-event designs.

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
          "expr": "mongodb_connections{state="current"}",
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
          "expr": "(mongodb_mongod_wiredtiger_cache_bytes{param="tracked dirty bytes in the cache"} / mongodb_mongod_wiredtiger_cache_bytes{param="maximum bytes configured"}) * 100",
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

---

## 11. Project Monitoring & Alerting Metric Reference

### 1. Key Metrics for Telemetry Alerting
Configure Prometheus alerts based on these threshold targets:
*   `mongodb_connections{state="current"}`: Alert if active connection counts exceed 80% of system limits.
*   `mongodb_mongod_wiredtiger_cache_bytes{param="tracked dirty bytes in the cache"}`: Trigger alert if dirty bytes exceed 15% of cache capacity.
*   `mongodb_mongod_oplog_lag`: Alert if replication lag on secondaries exceeds 10 seconds.

### 2. Operational Diagnostic Commands
Run post-deployment checks:
```bash
# Verify ingestion telemetry database collection stats
mongosh --eval "db.getSiblingDB('telemetry_db').sensor_buckets.stats()"

# Monitor active client operations queue lengths
mongosh --eval "db.serverStatus().globalLock.currentQueue"
```

### 3. Senior Engineer's Production Checklist
*   [ ] Verify telemetry data points are bucketed correctly to prevent document growth.
*   [ ] Route analytics reporting queries to secondaries using connection read preferences.
*   [ ] Run stress tests to confirm ingestion pipelines process workloads without socket starvation.
