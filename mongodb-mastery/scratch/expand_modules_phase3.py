#!/usr/bin/env python3
import os

modules_dir = r"c:\Users\Admin\Desktop\projects\learning-repo\mongodb-mastery\modules"

runbooks = {
    "01-mongodb-foundations.md": """
---

## 10. Production Runbook & Deployment Guidelines

### 1. Dynamic Cache Size Allocation
To optimize database performance dynamically under memory pressure without restarting the `mongod` process, you can configure the WiredTiger cache size dynamically using the administration command interface:
```javascript
db.adminCommand({
  setParameter: 1,
  "wiredTigerEngineRuntimeConfig": "cache_size=12G"
});
```
Ensure you leave at least 20-30% of system RAM free for the operating system page cache, which caches compressed data blocks and manages filesystem metadata.

### 2. Monitoring Thread Multiplexing
Monitor active connection worker threads and connection queues in real-time to identify bottleneck patterns:
```bash
# Check current connection metrics
mongosh --eval "db.serverStatus().connections"
```
Ensure `current` does not exceed 80% of `available` connections. If the ratio is high, increase connection pool limits or deploy additional routers.
""",
    "02-crud-and-querying.md": """
---

## 10. Production Runbook & Deployment Guidelines

### 1. Diagnosing Slow Write Operations
When update queries experience performance drops, you must analyze the lock duration and wait queues. Check current lock statistics by running:
```javascript
db.serverStatus().locks;
```
Verify the `acquireWaitCount` and `acquireTimeMicros` values. If the wait times are high, identify long-running operations using:
```javascript
db.currentOp({ "secs_running": { "$gt": 5 } });
```
Kill stuck write operations using their operation ID:
```javascript
db.killOp(opId);
```

### 2. Clearing Query Plan Cache
If a query plan behaves suboptimally, you can clear the plan cache manually for the collection:
```javascript
db.products.clearQueryPlanCache();
```
This forces the query planner to run parallel trial evaluations and cache a new winning plan on the next query execution.
""",
    "03-data-modeling.md": """
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
""",
    "04-indexing-and-query-performance.md": """
---

## 10. Production Runbook & Deployment Guidelines

### 1. Rolling Index Creation Runbook
Never run foreground index builds on active production replica sets. Instead, execute the rolling index build sequence:
1. Identify target node as secondary: `rs.status()`
2. Restart secondary in standalone mode on port 27018.
3. Build the index on standalone: `db.orders.createIndex({ status: 1, orderDate: -1 })`
4. Restart node back into replica set mode.
5. Repeat for remaining secondaries.
6. Step down the primary node, wait for election, and rebuild the index on the old primary.

### 2. Verifying Index Memory Usage
Check if the indexes fit entirely in RAM to prevent disk swapping:
```javascript
db.orders.stats().indexSizes;
```
Compare the total index size to the allocated WiredTiger cache size. If index sizes exceed 60% of the cache, scale memory resources or drop unused indexes.
""",
    "05-aggregation-framework.md": """
---

## 11. Production Runbook & Deployment Guidelines

### 1. Aggregation Memory Allocations Tuning
If analytics reports throw memory errors, enable disk utilization for the pipeline:
```javascript
db.orders.aggregate(pipeline, { allowDiskUse: true });
```
*Warning*: Disk spooling is up to 100x slower. Optimize memory usage by:
* Placing `$match` and `$sort` stages at the very beginning of the pipeline.
* Using `$project` to exclude unused fields early in the stream, minimizing document sizes.

### 2. Monitoring Materialized View Refresh Jobs
Ensure materialized view merge operations complete successfully:
```javascript
db.getSiblingDB("config").changelog.find({ what: "merge" }).sort({ time: -1 }).limit(10);
```
""",
    "06-transactions-and-consistency.md": """
---

## 10. Production Runbook & Deployment Guidelines

### 1. Transaction Lock Timeout Configurations
To prevent transactions from holding locks indefinitely during write conflicts, configure the lock request timeout dynamically:
```javascript
db.adminCommand({
  setParameter: 1,
  maxTransactionLockRequestTimeoutMillis: 5 // Terminate lock wait after 5ms
});
```

### 2. Monitoring Stale Read Operations
Verify replica lag states to prevent stale read operations on secondaries:
```javascript
rs.printSecondaryReplicationInfo();
```
If lag exceeds 5 seconds, route critical read operations to the primary node using read preference `{ readPreference: { mode: "primary" } }`.
""",
    "07-replication-and-high-availability.md": """
---

## 11. Production Runbook & Deployment Guidelines

### 1. Oplog Window Capacity Sizing
Ensure the oplog window is large enough to prevent secondaries from falling out of sync during maintenance:
```javascript
db.getReplicationInfo();
```
If the oplog window is less than 24 hours, increase the oplog size dynamically without restarting the daemon:
```javascript
db.adminCommand({
  replSetResizeOplog: 1,
  size: 102400 // Resize oplog to 100GB
});
```

### 2. Step-Down Safety Runbook
Before executing database maintenance on the primary node, force it to step down safely:
```javascript
rs.stepDown(120); // Keep primary as secondary for 120 seconds
```
This allows other voting nodes to elect a new primary without client connection drops.
""",
    "08-sharding-and-horizontal-scaling.md": """
---

## 11. Production Runbook & Deployment Guidelines

### 1. Balancer Window Scheduling
To prevent chunk migrations from impacting performance during peak business hours, schedule the balancer to run only during off-peak hours:
```javascript
db.getSiblingDB("config").settings.updateOne(
  { _id: "balancer" },
  { $set: { activeWindow: { start: "02:00", stop: "06:00" } } },
  { upsert: true }
);
```

### 2. Monitoring Balancer State
Verify that chunk migrations are executing correctly:
```javascript
sh.isBalancerRunning();
sh.getBalancerWindow();
```
""",
    "09-change-streams-and-event-driven-design.md": """
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
""",
    "10-security-and-production-operations.md": """
---

## 10. Production Runbook & Deployment Guidelines

### 1. Secure Certificate Rotation Runbook
To rotate mTLS certificates in production without database downtime:
1. Deploy the new CA and client certificates to the server hosts.
2. Restart the secondaries one-by-one using the updated certificate files.
3. Step down the primary, wait for election, and restart the old primary.
4. Verify that client drivers connect successfully using the new certificates.

### 2. Auditing User Connections
Regularly monitor access logs and query audits for unauthorized command executions:
```bash
grep "authCheck" /var/log/mongodb/audit.json | grep "result\": 13" # Filter auth failures
```
""",
    "11-application-integration.md": """
---

## 10. Production Runbook & Deployment Guidelines

### 1. Pool Size Calibration
Determine the optimal `maxPoolSize` based on estimated concurrent client requests:
$$\text{maxPoolSize} = \frac{\text{Concurrent Thread Count} \times 1.5}{\text{Number of Application Servers}}$$
Monitor connection check-out times and log alerts if check-out takes longer than 200ms.

### 2. Server Selection Timeout Configurations
Ensure applications fail fast during network drops:
* Set `serverSelectionTimeoutMS` to 5000ms.
* Set `socketTimeoutMS` to 30000ms.
""",
    "12-spring-boot-with-mongodb.md": """
---

## 10. Production Runbook & Deployment Guidelines

### 1. Connection Pool Sizing in Spring Boot
Configure the connection pool properties inside `application.yml` dynamically:
```yaml
spring:
  data:
    mongodb:
      uri: mongodb://localhost:27017/shop_db?maxPoolSize=50&retryWrites=true
```

### 2. Monitoring Spring Transaction Execution
Enable transaction execution logs in Spring to debug rollback states:
```yaml
logging:
  level:
    org.springframework.transaction: DEBUG
    org.springframework.data.mongodb.core.MongoTemplate: DEBUG
```
""",
    "13-testing-and-migrations.md": """
---

## 10. Production Runbook & Deployment Guidelines

### 1. CI/CD Integration Test Automation
Automate Testcontainers execution in pipeline runner scripts (e.g. Jenkins, GitHub Actions):
```yaml
# GitHub Actions Test Step configuration
- name: Run Integration Tests
  run: mvn clean test -Dspring.profiles.active=test
```
Ensure Docker daemon access is enabled on the runner host.

### 2. Rollback Verification Checklist
Always write and test rollback scripts for all schema migrations. Verify that V2 structures can be converted back to V1 without data loss before executing the production release.
""",
    "14-atlas-search-and-vector-search.md": """
---

## 11. Production Runbook & Deployment Guidelines

### 1. Vector Index Build Operations
Before deploying vector search indexes, check the dimension counts and similarity configurations. Changing vector properties requires dropping and rebuilding the index from scratch.

### 2. Monitoring Search Execution Latency
Check Atlas Search query times inside the console or using query logs:
```json
{ "query": { "$search": { ... } } }
```
If search query latency exceeds 200ms, configure explicit field mappings to optimize Lucene indexes.
""",
    "15-system-design-with-mongodb.md": """
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
""",
    "16-production-project-capstone.md": """
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
"""
}

def apply_runbooks():
    print("Applying Production Runbooks to module files...")
    
    for filename, runbook in runbooks.items():
        filepath = os.path.join(modules_dir, filename)
        if not os.path.exists(filepath):
            print(f"Skipping {filename} - path not found.")
            continue
            
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Check if the runbook is already in the file
        if "Production Runbook & Deployment" in content:
            print(f"Skipping {filename} - already contains runbook section.")
            continue
            
        # Detect the Appendix section (or where we want to insert)
        # We want to insert the Runbook RIGHT BEFORE the Appendix section.
        # Let's look for "## 11. Appendix" or "## 12. Appendix" or "## 9. Appendix" or "## 10. Appendix"
        appendix_headers = ["## 11. Appendix", "## 12. Appendix", "## 9. Appendix", "## 10. Appendix"]
        appendix_header_found = None
        for ah in appendix_headers:
            if ah in content:
                appendix_header_found = ah
                break
                
        if appendix_header_found:
            parts = content.split(appendix_header_found)
            before_appendix = parts[0]
            appendix_content = appendix_header_found + parts[1]
            
            # The renumbered appendix header should be renumbered:
            # Let's calculate the new appendix number.
            # If the runbook starts with "## 10. Production Runbook", then the appendix should be "## 11. Appendix".
            new_appendix_num = "11"
            if "## 11. Production Runbook" in runbook:
                new_appendix_num = "12"
            elif "## 12. Production Runbook" in runbook:
                new_appendix_num = "13"
            elif "## 9. Production Runbook" in runbook:
                new_appendix_num = "10"
                
            new_appendix_header = f"## {new_appendix_num}. Appendix"
            
            # Replace the old appendix header with the new one
            appendix_content = appendix_content.replace(appendix_header_found, new_appendix_header)
            
            # We also need to check if the summary is after the appendix and update its numbering.
            # Usually the summary is the very last section. Let's see:
            # The script will update the summary header too!
            # Let's find summary headers inside appendix_content:
            summary_headers = ["## 11. Summary", "## 12. Summary", "## 13. Summary", "## 10. Summary", "## 9. Summary"]
            for sh in summary_headers:
                if sh in appendix_content:
                    # Let's say if appendix is renumbered to new_appendix_num, summary should be new_appendix_num + 1.
                    new_summary_num = str(int(new_appendix_num) + 1)
                    new_summary_header = f"## {new_summary_num}. Summary"
                    appendix_content = appendix_content.replace(sh, new_summary_header)
                    break
                    
            new_content = before_appendix + runbook.strip() + "\n\n" + appendix_content
        else:
            new_content = content.strip() + "\n\n" + runbook.strip()
            
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print(f"Applied runbook to {filename} successfully.")

if __name__ == "__main__":
    apply_runbooks()
