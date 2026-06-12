#!/usr/bin/env python3
import os

modules_dir = r"c:\Users\Admin\Desktop\projects\learning-repo\mongodb-mastery\modules"

tuning_references = {
    "01-mongodb-foundations.md": """
---

## 14. Storage Engine & Memory Optimization Reference

### 1. Key WiredTiger Cache Settings
Configure these parameters in `mongod.conf` under the `storage.wiredTiger.engineConfig` block or modify them dynamically:
*   `cacheSizeGB`: Limits the maximum RAM utilized by WiredTiger for document pages.
*   `eviction_target`: The percentage of cache dirty bytes at which background eviction threads start processing (Default: 80%).
*   `eviction_trigger`: The percentage of cache dirty bytes at which client threads are forced to run eviction tasks (Default: 95%).

### 2. Operational Diagnostic Commands
Verify cache eviction rates and page state metrics using `mongosh`:
```javascript
// Get detailed cache usage statistics
db.serverStatus().wiredTiger.cache;

// Inspect the page sweep and block manager operations
db.serverStatus().wiredTiger["block-manager"];
```

### 3. Senior Engineer's Production Checklist
*   [ ] Verify system page cache size. Ensure at least 30% of system RAM is unallocated to host files and compressed leaf pages.
*   [ ] Mount data directories using XFS filesystem with the `noatime` option to prevent write IOPS on read operations.
*   [ ] Set system file descriptor limits (`ulimit -n`) to 64000 to prevent connection issues under high traffic workloads.
""",
    "02-crud-and-querying.md": """
---

## 13. Query Execution & Index Selection Reference

### 1. Key Query Planner Parameters
Tweak these system variables to optimize query plan evaluation times:
*   `internalQueryPlannerMaxIndexedSolutions`: Limits the maximum indexed plans evaluated (Default: 64).
*   `internalQueryExecMaxBlockingSortBytes`: The maximum memory allocation allowed for execution sort operations (Default: 33,554,432 bytes).

### 2. Operational Diagnostic Commands
Verify execution statistics and investigate slow queries using these scripts:
```javascript
// Explain winning and rejected plan details for a specific query
db.collection.find({ status: "ACTIVE" }).sort({ score: -1 }).explain("allPlansExecution");

// List all cached execution plans for a collection
db.collection.getPlanCache().list();
```

### 3. Senior Engineer's Production Checklist
*   [ ] Run `explain("executionStats")` on all application queries to ensure winning plans utilize `IXSCAN` and avoid `COLLSCAN` stages.
*   [ ] Add explicit `.limit()` constraints to sorting queries to prevent memory overflow errors.
*   [ ] Set database profiling thresholds (`db.setProfilingLevel(1, 100)`) to log queries taking longer than 100ms.
""",
    "03-data-modeling.md": """
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
""",
    "04-indexing-and-query-performance.md": """
---

## 14. Index Maintenance & Performance Tuning Reference

### 1. Key Index Configurations
Manage index settings to reduce storage footprint:
*   `background`: Builds the index in the background to prevent blocking database operations (deprecated since version 4.2).
*   `partialFilterExpression`: Indexes documents matching specific criteria to optimize space.
*   `expireAfterSeconds`: Configures TTL indexes to automatically delete documents after a duration.

### 2. Operational Diagnostic Commands
Audit index utilization statistics:
```javascript
// Retrieve usage frequencies for all indexes on a collection
db.collection.aggregate([{ $indexStats: {} }]);

// Retrieve disk usage sizes for indexes
db.collection.stats().indexSizes;
```

### 3. Senior Engineer's Production Checklist
*   [ ] Drop unused indexes identified using `$indexStats` to reduce write amplification and reclaim memory.
*   [ ] Create partial indexes on sparse fields to optimize index size.
*   [ ] Ensure index sizes fit entirely within the allocated WiredTiger cache.
""",
    "05-aggregation-framework.md": """
---

## 14. Pipeline Profiling & Memory Management Reference

### 1. Key Aggregation Variables
Configure these limits to manage resources during complex computations:
*   `internalQueryExecMaxBlockingSortBytes`: Caps memory allocations during sort operations in aggregation pipelines (Default: 32MB).
*   `allowDiskUse`: Enables database stages to write temporary BSON files to disk when memory limits are exceeded.

### 2. Operational Diagnostic Commands
Inspect aggregation metrics:
```javascript
// Run explain plans on aggregation tasks to evaluate stages
db.orders.explain("executionStats").aggregate(pipeline);

// Check current aggregation workers running on the instance
db.currentOp({ "command.aggregate": { $exists: true } });
```

### 3. Senior Engineer's Production Checklist
*   [ ] Ensure `$match` and `$sort` stages are placed at the very beginning of the pipeline to leverage indexes.
*   [ ] Minimize BSON document footprint early in pipelines using `$project` blocks to select only required fields.
*   [ ] Avoid `$facet` stages on large collections because it executes in-memory and does not support disk spooling.
""",
    "06-transactions-and-consistency.md": """
---

## 14. Distributed Lock & Consistency Verification Reference

### 1. Key Transaction Configurations
Adjust these parameters to control transaction timeouts:
*   `transactionLifetimeLimitSeconds`: The maximum execution time allowed for active transactions before rollback (Default: 60s).
*   `maxTransactionLockRequestTimeoutMillis`: The duration a transaction blocks waiting to acquire lock resources (Default: 5ms).

### 2. Operational Diagnostic Commands
Verify transaction states:
```javascript
// Inspect running transaction logs and active lock queues
db.adminCommand({
  currentOp: 1,
  "transaction.opcount": { $gt: 0 }
});

// View lock status for all database partitions
db.serverStatus().locks;
```

### 3. Senior Engineer's Production Checklist
*   [ ] Enforce consistent order of document lock acquisition across operations to prevent deadlocks.
*   [ ] Set `transactionLifetimeLimitSeconds` to 15 seconds to release database locks quickly.
*   [ ] Set read concern to `majority` and write concern to `w: "majority"` to prevent rollback issues when executing transactions.
""",
    "07-replication-and-high-availability.md": """
---

## 15. Replication Lag & Election Monitoring Reference

### 1. Key Replica Set Parameters
Adjust these values to fine-tune elections and sync sources:
*   `electionTimeoutMillis`: The timeout duration before secondary nodes trigger elections if the primary is unreachable (Default: 10,000ms).
*   `heartbeatIntervalMillis`: The duration between node status checks (Default: 2000ms).
*   `settings.chainingAllowed`: Enables secondaries to synchronize data from other secondaries.

### 2. Operational Diagnostic Commands
Check replication health status:
```javascript
// Output detailed replication lag and sync source metrics
rs.printReplicationInfo();
rs.printSecondaryReplicationInfo();

// Get replica set status structure
rs.status();
```

### 3. Senior Engineer's Production Checklist
*   [ ] Keep election timeout at 10-15 seconds to prevent network anomalies from triggering split-brain elections.
*   [ ] Resize the oplog window dynamically during data imports to prevent synchronization failures on secondaries.
*   [ ] Deploy replica set members across separate physical zones to guarantee high availability.
""",
    "08-sharding-and-horizontal-scaling.md": """
---

## 15. Shard Chunk Balance & Router Operations Reference

### 1. Key Shard Balancer Settings
Configure chunk parameters to manage cluster balance:
*   `balancer.activeWindow`: Schedules the balancer execution window to prevent migration tasks during peak hours.
*   `chunkSize`: The maximum size (in megabytes) of a chunk before a split is triggered (Default: 64MB).

### 2. Operational Diagnostic Commands
Check cluster balance:
```javascript
// Print cluster sharding configuration details
sh.status(true);

// Verify if the balancer is active on the cluster
sh.isBalancerRunning();
```

### 3. Senior Engineer's Production Checklist
*   [ ] Choose a high-cardinality compound or hashed shard key to ensure even write distribution across shards.
*   [ ] Split and migrate jumbo chunks manually when balancer migrations fail.
*   [ ] Schedule the balancer window during low-traffic periods to avoid performance impacts.
""",
    "09-change-streams-and-event-driven-design.md": """
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
""",
    "10-security-and-production-operations.md": """
---

## 13. Security Auditing & RBAC Configuration Reference

### 1. Key Security Settings
Configure these settings in `mongod.conf` to secure the database cluster:
*   `security.authorization`: Enables role-based access control (RBAC) (Default: `disabled`).
*   `security.keyFile`: Configures the keyfile path for node-to-node authentication in replica sets.
*   `net.tls.mode`: Enforces TLS encrypted connections (`requireTLS`).

### 2. Operational Diagnostic Commands
Verify security credentials and run audits:
```javascript
// List details of all custom roles in the database
db.getRoles({ showPrivileges: true });

// Check current user credentials and privilege levels
db.runCommand({ connectionStatus: 1 });
```

### 3. Senior Engineer's Production Checklist
*   [ ] Enable IP whitelisting in configurations to restrict access to trusted hosts.
*   [ ] Audit configuration parameters using security scanning tools prior to database deployment.
*   [ ] Rotate TLS certificates annually using rolling restart methods to maintain access.
""",
    "11-application-integration.md": """
---

## 13. Connection Lifecycle & Pool Diagnostic Reference

### 1. Key Connection Pool Parameters
Configure client settings to manage pool resources:
*   `maxPoolSize`: The maximum connections allowed in the pool (Default: 100).
*   `minPoolSize`: The minimum pre-warmed connection count (Default: 0).
*   `maxIdleTimeMS`: Sockets idle longer than this limit are closed (Default: 0 - no limit).

### 2. Operational Diagnostic Commands
Verify socket usage:
```javascript
// Query the active database connection metrics
db.serverStatus().connections;

// Track driver operations queued waiting for connection slots
db.serverStatus().metrics.operation;
```

### 3. Senior Engineer's Production Checklist
*   [ ] Instantiate a single, shared `MongoClient` connection pool per application process.
*   [ ] Size connection pools dynamically using concurrency formulas to match backend limits.
*   [ ] Configure driver socket timeouts (`socketTimeoutMS`) to terminate stalled queries.
""",
    "12-spring-boot-with-mongodb.md": """
---

## 13. Spring Data Configuration & Logging Reference

### 1. Key Spring Connection Properties
Configure database connection parameters in `application.properties`:
*   `spring.data.mongodb.auto-index-creation`: Enables automatic index generation on startup (Default: `true`).
*   `spring.data.mongodb.uuid-representation`: Standardizes UUID binary representation type (`standard`).

### 2. Operational Diagnostic Commands
Trace database template execution:
```yaml
# Enable logging for Template operations in application.yml
logging:
  level:
    org.springframework.data.mongodb.core.MongoTemplate: DEBUG
```

### 3. Senior Engineer's Production Checklist
*   [ ] Disable `auto-index-creation` in production configurations to prevent deployment timeouts during index builds.
*   [ ] Define custom converters to handle non-standard Java classes like `ZonedDateTime`.
*   [ ] Use projections in MongoTemplate queries to select only required fields and reduce object serialization overhead.
""",
    "13-testing-and-migrations.md": """
---

## 13. CI/CD Integration Test & Mocking Reference

### 1. Key Testcontainers Variables
Configure docker parameters to run local containers in integration tests:
*   `MONGO_TEST_URI`: Custom connection string pointing to local testing containers.
*   `testcontainers.reuse.enable`: Enables reusing existing database test containers to speed up tests.

### 2. Operational Diagnostic Commands
Verify test outcomes:
```bash
# Run integration tests in clean profiles
mvn clean test -Dspring.profiles.active=test

# Inspect docker container logs running database tasks
docker logs <mongo_test_container_id>
```

### 3. Senior Engineer's Production Checklist
*   [ ] Test database migrations against a mock container database in local environments prior to deployment.
*   [ ] Write idempotent migration scripts to ensure failed deployments can be retried safely.
*   [ ] Verify database index structures automatically inside integration testing suites.
""",
    "14-atlas-search-and-vector-search.md": """
---

## 14. Search Index Mappings & Latency Tuning Reference

### 1. Key Atlas Search Mappings
Configure search properties to manage index sizes:
*   `dynamic`: Disables automatic indexing of all fields to prevent index bloat (`false`).
*   `analyzer`: The Lucene tokenizer configuration utilized for text searches (`lucene.standard`).

### 2. Operational Diagnostic Commands
Verify search status:
```javascript
// Query search status metadata for a collection
db.collection.aggregate([{ $searchStatus: {} }]);

// Inspect query performance for Lucene clauses
db.collection.aggregate([{ $searchMeta: { count: { type: "total" } } }]);
```

### 3. Senior Engineer's Production Checklist
*   [ ] Define explicit index mappings for all search properties to optimize RAM usage.
*   [ ] Set dimension parameters matching model outputs when constructing vector search indexes.
*   [ ] Monitor search lag metrics inside Atlas configurations to detect indexing bottlenecks.
""",
    "15-system-design-with-mongodb.md": """
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
""",
    "16-production-project-capstone.md": """
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
"""
}

def apply_tuning():
    print("Applying Performance Tuning References to module files...")
    
    for filename, ref in tuning_references.items():
        filepath = os.path.join(modules_dir, filename)
        if not os.path.exists(filepath):
            print(f"Skipping {filename} - path not found.")
            continue
            
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        if "Performance Tuning & Verification Commands" in content or "Storage Engine & Memory Optimization Reference" in content:
            print(f"Skipping {filename} - already contains tuning section.")
            continue
            
        # Append to the end of the file
        new_content = content.strip() + "\n\n" + ref.strip() + "\n"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print(f"Applied tuning reference to {filename} successfully.")

if __name__ == "__main__":
    apply_tuning()
