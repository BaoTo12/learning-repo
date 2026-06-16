# Module 08: Sharding & Horizontal Scaling

## 1. What Problem This Module Solves
As a database grows, a single machine will eventually hit its limits for storage capacity, memory size, and CPU processing power. While replica sets provide high availability for read operations, they do not scale write operations, as all writes must go to the primary node. 

To scale beyond the limits of a single machine, we must partition data across multiple servers using **Sharding**. A senior engineer must understand chunk splitting mechanics, balance loops, shard key selection criteria, query routing pathways, and how to configure a multi-container sharded cluster. Selecting the wrong shard key can cause uneven data distribution (hot-spotting), chunk migration bottlenecks, and slow "scatter-gather" queries that degrade performance.

---

## 2. Why This Topic Matters
Sharding partitions large datasets across multiple independent replica set shards. However, sharding introduces operational and architectural complexity. If you select a shard key with low cardinality or monotonic distribution, you risk creating **jumbo chunks** that cannot be split or moved, leading to unbalanced storage and CPU hotspots. 

Understanding how the `mongos` query router coordinates metadata from config servers and how to balance write workloads across shards is essential for maintaining predictable performance in large-scale production environments.

---

## 3. Core Concepts & Internals

### 3.1 Chunk Splits & Sharding Balance Loops
In a sharded cluster, MongoDB groups document collections into logical segments called **Chunks**. Chunks are defined by a range of shard key values.

#### Chunk Splits:
*   **Default Chunk Size**: The default chunk size is **64 megabytes**.
*   **Splitting Mechanics**: When writes to a chunk cause it to exceed the size limit, the primary shard splits the chunk into two smaller chunks by updating the metadata range boundaries on the Config Servers. 
*   *Performance Note*: Chunk splits only update metadata range definitions. They do not write or relocate BSON documents on disk.

#### The Balancer & Chunk Migration:
The **Balancer** is a background process that monitors chunk distribution across shards. If the difference in chunk count between shards exceeds the migration threshold, the balancer initiates a chunk migration.

```
 [Source Shard]                                           [Destination Shard]
        │                                                          │
  1. Acquire Balancer Lock ──> (Config Server Metadata Lock)        │
        │                                                          │
  2. Start Migration ── Send Chunk Metadata ──────────────────────>│
        │                                                          │
  3. Clone Phase ────── Clone BSON documents ─────────────────────>│
        │                                                          │
  4. Catch Up Phase ─── Send Oplog updates during clone ──────────>│
        │                                                          │
  5. Commit Phase ───── Update metadata on Config Servers ────────>│
        │                                                          │
  6. Clean Phase ────── Delete migrated documents from source ──────│
```

#### Chunk Migration Phases:
1.  **Balancer Lock**: The balancer acquires a distributed lock on the Config Servers to prevent other balance loops from modifying the metadata.
2.  **Clone Phase**: The source shard sends chunk metadata to the destination shard, which begins copying BSON documents over the network.
3.  **Catch Up Phase**: The source shard records any write operations applied to the migrating chunk during the clone phase and replays them on the destination shard.
4.  **Commit Phase**: The destination shard updates the cluster metadata on the Config Servers, routing subsequent queries for that chunk's range to the new shard.
5.  **Clean Phase**: The source shard deletes the migrated documents from its local databases asynchronously (using range deleter threads).

#### Jumbo Chunks:
*   **What is a Jumbo Chunk?**: If a chunk exceeds the maximum chunk size, but all documents in the chunk share the exact same shard key value, the chunk cannot be split. It is marked as a **Jumbo Chunk**.
*   **The Problem**: The balancer cannot migrate jumbo chunks to other shards because doing so would split the range of a single shard key. This leads to unbalanced storage and CPU hot-spots on the shard holding the jumbo chunk.

---

### 3.2 Shard Key Selection Criteria
Choosing the right shard key is the most critical design decision when building a sharded cluster.

```
                              Data Distribution
                      ┌───────────────────────────────┐
                      │ Analyze Shard Key Selectivity │
                      └───────────────┬───────────────┘
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            ▼ (High Range Queries)                              ▼ (Uniform Write Path)
   [Ranged Shard Key]                                  [Hashed Shard Key]
   • Groups ranges sequentially.                       • Distributes writes evenly.
   • Bounded range queries are fast.                    • Range queries scatter-gather.
   • Monotonic keys cause hotspots.                    • Prevents write hotspots.
```

#### 1. Ranged Sharding:
*   **Mechanics**: Documents are partitioned based on contiguous ranges of the shard key value.
*   *Advantage*: Highly efficient for range queries (e.g. `createdAt: { $gt: Date1, $lt: Date2 }`). The query router can target the specific shards containing that range.
*   *Disadvantage*: Risk of write hot-spotting if the shard key is monotonically increasing (like ObjectId or Auto-Increment IDs). All new inserts will target the shard holding the highest range.

#### 2. Hashed Sharding:
*   **Mechanics**: MongoDB computes an MD5 hash of the shard key value and uses the hash to partition chunks.
*   *Advantage*: Provides uniform write distribution across shards, even if the shard key is monotonically increasing.
*   *Disadvantage*: Range queries must be sent to all shards (scatter-gather), as contiguous ranges are scattered across the cluster.

#### Shard Key Cardinality & Frequency:
*   **Cardinality**: The number of unique values for a field. Low cardinality fields (e.g. status, gender) make poor shard keys because they cannot be split into enough unique ranges to distribute across shards.
*   **Frequency**: The rate at which a specific shard key value occurs in the dataset. High frequency values (e.g., a specific popular product ID in an orders collection) can create jumbo chunks if they exceed chunk size limits.

---

### 3.3 Query Routing Path (mongos & Config Servers)
Clients interact with a sharded cluster through a **`mongos` query router**.

#### The Routing Architecture:
1.  **Metadata Cache**: `mongos` routers do not store data. They cache metadata from the **Config Servers** that defines chunk ranges and their location shards.
2.  **Targeted Queries**: If a query includes the shard key in its filter, the `mongos` router looks up the chunk location in its cache and routes the query directly to the target shard.
3.  **Scatter-Gather Queries**: If a query does not include the shard key, the `mongos` router must send the query to **all shards** in the cluster. Each shard executes the query locally, and the `mongos` router merges and returns the results. Scatter-gather queries consume significant cluster resources and should be avoided for high-frequency operations.

```
 [Client Application]
         │
         ▼
 [mongos Query Router] <── Read Metadata ── [Config Server Replica Set]
         │ (Lookup Chunk Ranges Cache)
         ├──────────────────────────┬──────────────────────────┐
         ▼ (Targeted Query)         ▼ (Scatter-Gather Query)   ▼ (Scatter-Gather Query)
  [Shard Replica Set 1]      [Shard Replica Set 1]      [Shard Replica Set 2]
```

---

### 3.4 Production Shard Config Files
In production environments, daemon parameters must be explicitly set in config files for config servers, routers (`mongos`), and shards.

#### 1. Config Server Config File (`/etc/mongod-config.conf`):
```yaml
sharding:
  clusterRole: configsvr
replication:
  replSetName: configReplSet
net:
  port: 27019
  bindIp: 0.0.0.0
storage:
  dbPath: /var/lib/mongodb-config
```

#### 2. Shard Node Config File (`/etc/mongod-shard.conf`):
```yaml
sharding:
  clusterRole: shardsvr
replication:
  replSetName: shard1ReplSet
net:
  port: 27018
  bindIp: 0.0.0.0
storage:
  dbPath: /var/lib/mongodb-shard
```

#### 3. mongos Router Config File (`/etc/mongos.conf`):
```yaml
sharding:
  configDB: configReplSet/configsvr01:27019,configsvr02:27019
net:
  port: 27017
  bindIp: 0.0.0.0
```

---

### 3.5 Managing and Splitting Jumbo Chunks
When the balancer is blocked by a jumbo chunk, you must manually split and manage it.

#### Identifying Jumbo Chunks:
Run the sharding status with verbose parameters to list jumbo flags:
```javascript
sh.status(true);
```
In the chunks section of the output:
```
{ "customerId" : "cust_1001" } -->> { "customerId" : "cust_1002" } on : shard1ReplSet Timestamp(2, 0) jumbo
```

#### Splitting a Jumbo Chunk:
If the values within the chunk boundaries are not completely identical (i.e. there are multiple different values between `cust_1001` and `cust_1002`), you can force a split using `sh.splitAt()` or `sh.splitFind()`:
```javascript
// Split the chunk containing a specific key value
sh.splitFind("ecommerce.orders", { customerId: "cust_1001" });

// Split the chunk at a precise boundary value
sh.splitAt("ecommerce.orders", { customerId: "cust_1001_midpoint" });
```

---

## 4. Practical Examples

### Multi-Container Sharded Cluster Setup (Docker Compose)
The following `docker-compose.yml` configures a complete local sharded cluster containing a Config Server replica set, a Shard replica set, and a `mongos` query router.

```yaml
version: '3.8'

services:
  # Config Server Replica Set
  configsvr01:
    image: mongo:6.0
    container_name: configsvr01
    command: mongod --configsvr --replSet configReplSet --port 27019 --dbpath /data/db --bind_ip_all
    volumes:
      - config_data01:/data/db
    ports:
      - 27019:27019

  configsvr02:
    image: mongo:6.0
    container_name: configsvr02
    command: mongod --configsvr --replSet configReplSet --port 27019 --dbpath /data/db --bind_ip_all
    volumes:
      - config_data02:/data/db

  # Shard 1 Replica Set Node 1
  shard1a:
    image: mongo:6.0
    container_name: shard1a
    command: mongod --shardsvr --replSet shard1ReplSet --port 27018 --dbpath /data/db --bind_ip_all
    volumes:
      - shard1_data_a:/data/db
    ports:
      - 27018:27018

  shard1b:
    image: mongo:6.0
    container_name: shard1b
    command: mongod --shardsvr --replSet shard1ReplSet --port 27018 --dbpath /data/db --bind_ip_all
    volumes:
      - shard1_data_b:/data/db

  # Shard 2 Replica Set Node 1
  shard2a:
    image: mongo:6.0
    container_name: shard2a
    command: mongod --shardsvr --replSet shard2ReplSet --port 27018 --dbpath /data/db --bind_ip_all
    volumes:
      - shard2_data_a:/data/db
    ports:
      - 27028:27018

  shard2b:
    image: mongo:6.0
    container_name: shard2b
    command: mongod --shardsvr --replSet shard2ReplSet --port 27018 --dbpath /data/db --bind_ip_all
    volumes:
      - shard2_data_b:/data/db

  # mongos Query Router
  mongos:
    image: mongo:6.0
    container_name: mongos_router
    command: mongos --configdb configReplSet/configsvr01:27019,configsvr02:27019 --port 27017 --bind_ip_all
    ports:
      - 27017:27017
    depends_on:
      - configsvr01
      - configsvr02
      - shard1a
      - shard2a

volumes:
  config_data01:
  config_data02:
  shard1_data_a:
  shard1_data_b:
  shard2_data_a:
  shard2_data_b:
```

---

### Sharded Cluster Initialization Script (Bash)
This script initializes the config servers, configures the shards, and enables sharding for a collection.

```bash
#!/usr/bin/env bash
# Sharded Cluster Initialization Script

echo "1. Initializing Config Server Replica Set..."
docker exec -it configsvr01 mongosh --port 27019 --eval '
  rs.initiate({
    _id: "configReplSet",
    configsvr: true,
    members: [
      { _id: 0, host: "configsvr01:27019" },
      { _id: 1, host: "configsvr02:27019" }
    ]
  })
'

sleep 5

echo "2. Initializing Shard 1 Replica Set..."
docker exec -it shard1a mongosh --port 27018 --eval '
  rs.initiate({
    _id: "shard1ReplSet",
    members: [
      { _id: 0, host: "shard1a:27018" },
      { _id: 1, host: "shard1b:27018" }
    ]
  })
'

echo "3. Initializing Shard 2 Replica Set..."
docker exec -it shard2a mongosh --port 27018 --eval '
  rs.initiate({
    _id: "shard2ReplSet",
    members: [
      { _id: 0, host: "shard2a:27018" },
      { _id: 1, host: "shard2b:27018" }
    ]
  })
'

sleep 5

echo "4. Adding Shards to the mongos router..."
docker exec -it mongos_router mongosh --port 27017 --eval '
  sh.addShard("shard1ReplSet/shard1a:27018,shard1b:27018");
  sh.addShard("shard2ReplSet/shard2a:27018,shard2b:27018");
  
  print("Initializing database sharding...");
  sh.enableSharding("ecommerce");
  
  // Shard orders collection using a hashed shard key
  sh.shardCollection("ecommerce.orders", { "customerId": "hashed" });
  print("Sharding setup completed successfully!");
'
```

---

## 5. Trade-offs & Alternatives

Choosing a partitioning strategy requires aligning complexity, write performance, and query speeds:

| Scaling Strategy | Cost | Write Performance | Range Query Performance | Operational Complexity | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Vertical Scaling (Scale Up)** | **High**: High-end CPU, RAM, and storage arrays become expensive. | **Medium**: Limited by hardware processing capacity. | **Maximum**: All data resides on a single node; zero network latency. | **None** | Low to medium scale systems where operational complexity must be avoided. |
| **Ranged Sharded Cluster** | **Medium**: Requires multiple nodes for config servers and shards. | **Medium**: Risk of write hotspots if shard keys are monotonically increasing. | **Excellent**: Target queries directly to the specific shard holding the range. | **High**: Balancer and chunk migrations must be managed. | Auditing logs, time-series data, regional queries. |
| **Hashed Sharded Cluster** | **Medium**: Requires multiple nodes for config servers and shards. | **Maximum**: Inserts are distributed uniformly across all shards. | **Poor**: Range queries must be broadcast to all shards (scatter-gather). | **High**: Balancer and chunk migrations must be managed. | High-frequency write systems, user accounts. |

---

## 6. Common Mistakes & Anti-patterns
*   **Selecting a Monotonically Increasing Shard Key in Ranged Sharding**: Sharding on fields like `createdAt` or `_id` in a ranged cluster. All new documents will target the shard holding the highest range boundary, creating a write hotspot and rendering the other shards idle.
*   **Selecting Low-Cardinality Shard Keys**: Sharding on fields like `status` or `country`. The database cannot create enough unique ranges to distribute chunks across shards, leading to unbalanced storage and jumbo chunks.
*   **Running Queries without Shard Keys**: Running high-frequency queries that do not include the shard key in the filter. This forces the `mongos` router to query every shard (scatter-gather), consuming cluster resources and degrading performance.

---

## 7. Hands-on Exercises
1.  Configure a local sharded cluster using the Docker Compose configuration from Section 4.
2.  Enable sharding for a database and shard a collection using a hashed shard key on a `userId` field.
3.  Insert 50,000 mock documents and run `sh.status()` to verify that documents are distributed across both shards.
4.  Run a query that filters by `userId` and inspect its explain plan. Verify that the query is targeted to a single shard. Rerun the query filtering on a different field and verify it triggers a scatter-gather query.

---

## 8. Mini-Project: Shard Key Trade-off Analysis
**Scenario**: Design a sharding strategy for an e-commerce platform's orders collection.

1.  Compare the performance of two different sharding strategies:
    *   **Strategy A**: Shard on `{ orderDate: 1 }` (Ranged sharding).
    *   **Strategy B**: Shard on `{ customerId: "hashed" }` (Hashed sharding).
2.  Analyze how each strategy handles the following workloads:
    *   Inserting 10,000 new orders per minute.
    *   Querying order history for a specific customer.
    *   Generating daily sales reports for the last 30 days.
3.  Write a design document detailing the trade-offs of each strategy and recommending the best option for the platform.

---

## 9. Interview Questions

### Q1: What is a jumbo chunk, how does it occur, and how do you resolve it?
**Answer**: A jumbo chunk is a chunk that has exceeded the maximum chunk size (default 64MB) but cannot be split because all documents in the chunk share the exact same shard key value. It occurs when the selected shard key has low cardinality or high frequency. 
You resolve it by:
1.  Refining the shard key by adding a secondary field to create a compound shard key, which increases cardinality.
2.  Manually splitting the chunk if the values differ, or using the `mergeJumbo` command if supported.
3.  In modern MongoDB versions, the balancer can migrate jumbo chunks if configured, but refining the shard key is the best long-term solution.

### Q2: How do config servers maintain consistency in a sharded cluster?
**Answer**: Config servers store the metadata that defines chunk ranges and their location shards. To ensure high availability and consistency, config servers are deployed as a replica set. All metadata updates (like chunk splits or migrations) are written using multi-document transactions with write concern `majority`. This guarantees that the metadata is synchronized across config servers before any data routing changes take effect.

### Q3: What is the difference between scatter-gather and targeted queries? How do they affect performance?
**Answer**:
*   **Targeted Queries** include the shard key in the filter. The `mongos` router looks up the chunk location in its cache and routes the query directly to the target shard, minimizing network and resource overhead.
*   **Scatter-Gather Queries** do not include the shard key. The `mongos` router must send the query to every shard in the cluster. Each shard executes the query locally, and the router merges the results. Scatter-gather queries consume significant cluster resources and degrade read throughput.

---

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

## 12. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Stuck Chunk Migration in cloning Phase
*   **Failure Mode**: A chunk migration starts but remains in the `cloning` phase indefinitely, blocking subsequent balancer iterations.
*   **Diagnosis**: Check the migration log using `db.printShardingStatus()`. Run:
    ```javascript
    db.getSiblingDB("config").changelog.find({ what: "moveChunk.commit" }).sort({ time: -1 }).limit(5);
    ```
    If no commit events are returned but `moveChunk.start` is active, the migration is stuck.
*   **Resolution**: This is usually caused by network dropped packets or high replication lag on the destination shard. Resolve replication lag on the target secondary, and restart the `mongos` router to force a config lock release.

### 2. Config Server Metadata Lock Conflicts
*   **Failure Mode**: Multiple concurrent database operations (like manual chunk splits and drops) try to acquire a metadata lock on the config servers, causing split/drop operations to fail with lock conflict errors (Code 158).
*   **Resolution**: Check active metadata locks by running:
    ```javascript
    db.getSiblingDB("config").locks.find({ state: { $ne: 0 } }).pretty();
    ```
    Wait for active operations to complete. If a lock is orphaned due to a config node crash, step down the config primary to force lock reconciliation.

### 3. Jumbo Chunk Balancer Recovery
*   **Failure Mode**: The balancer logs show continuous warnings: `moveChunk failed for chunk ... because it is marked jumbo`.
*   **Resolution**: Run a script to identify, clear, and split all jumbo chunks in the collection:
    ```javascript
    db.getSiblingDB("config").chunks.find({ jumbo: true }).forEach(function(chunk) {
      print("Splitting jumbo chunk: " + chunk._id);
      try {
        sh.splitFind(chunk.ns, chunk.min);
      } catch (e) {
        print("Failed to split chunk: " + e.message);
      }
    });
    ```

---

## 13. Summary
Scaling databases horizontally requires understanding sharding mechanics, query routing, and shard key selection. By monitoring chunk splits, using hashed shard keys to distribute writes uniformly, and ensuring queries are targeted, senior engineers build sharded clusters that scale to petabytes of data.

---

## 13. Enterprise Case Study: Hot Shard Exhaustion & Range-based Shard Key Drift

### 1. Scenario Description
An IoT ingestion system tracks millions of sensor devices. The team deployed a sharded cluster and chose `timestamp` as the shard key (a range-based sharding approach). As the system scaled, database writes were routed to a single shard (the "hot shard"), while other shards sat idle. This caused disk exhaustion and CPU spikes on the active shard, while the balancer could not migrate chunks due to lock contention.

### 2. Analytical Diagnostic Investigation
The DBA checked chunk distribution in the config database:
```javascript
sh.status();
```
They audited the write distribution across shards:
```javascript
db.getSiblingDB("admin").runCommand({ connPoolStats: 1 });
```
**Diagnostic Findings**:
*   Because `timestamp` is monotonically increasing, every new document had a timestamp value higher than the range limit of the last chunk.
*   The router (`mongos`) sent every write operation to the shard holding the max range chunk.
*   The balancer attempted to split and move these chunks, but because writes were constant, the chunks were marked as "jumbo chunks" (too large to migrate safely).

### 3. Step-by-Step Resolution Runbook
To resolve this imbalance without system downtime, they converted the collection to use a hashed compound shard key:

1.  **Analyze Jumbo Chunks**:
    Locate jumbo chunks that block balancer migration tasks:
    ```javascript
    db.getSiblingDB("config").chunks.find({ jumbo: true });
    ```
2.  **Split Jumbo Chunks Manually**:
    Force a split of the jumbo chunk at its middle point:
    ```javascript
    sh.splitFind("telemetry.sensor_readings", { timestamp: ISODate("2026-06-12T00:00:00Z") });
    ```
3.  **Refine the Shard Key dynamically (Zero-Downtime)**:
    Since MongoDB 4.4+, you can add fields to a shard key to increase cardinality. They refined the key by adding a hashed `sensorId` prefix:
    ```javascript
    sh.refineCollectionShardKey("telemetry.sensor_readings", { sensorId: "hashed", timestamp: 1 });
    ```
4.  **Verify Balancer Progression**:
    Ensure the balancer starts migrating chunks across shards:
    ```javascript
    sh.isBalancerRunning();
    sh.getBalancerWindow();
    ```

### 4. Code Artifact: Shard Balance Diagnostic Script
Save this script as `check-shard-balance.js` to run on the config router:
```javascript
const shardStatus = sh.status();
const configDb = db.getSiblingDB("config");

print("--- Checking Chunk Balances Across Shards ---");
const collections = configDb.collections.find({ dropped: false }).toArray();

collections.forEach(col => {
  print("Collection: " + col._id);
  const chunks = configDb.chunks.find({ ns: col._id }).toArray();
  const distribution = {};
  
  chunks.forEach(chunk => {
    distribution[chunk.shard] = (distribution[chunk.shard] || 0) + 1;
  });
  
  printjson(distribution);
});
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Never Shard on Monotonic Keys**: Range-based sharding on monotonic keys (e.g. auto-increment IDs, timestamps) creates write bottlenecks. Always combine monotonic fields with a high-cardinality field (like a hashed ID) to distribute writes.
*   **Dynamic Shard Key Refinement**: Refinement changes the index configurations. Ensure the compound indexes matching the new refined key are built on all shards before running the command.

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

---

## 16. Shard Key Engineering: Jumbo Chunks & Capacity Distribution

### 1. Shard Key Selection tradeoffs
*   **Ascending Shard Key**: Writes hit the maximum range chunk on the hot shard. This provides fast range reads but creates write bottlenecks.
*   **Hashed Shard Key**: Disperses writes evenly across shards. This provides fast write throughput but makes range queries slow because the query router must query every shard.
*   **Location-Based (Zoned)**: Routes data chunks to shards tagged with specific regions (e.g. `US`, `EU`) to meet data residency compliance requirements.

### 2. The Firehose Strategy
The Firehose Strategy routes all ingestion writes to a single shard with high-performance SSD disks. The balancer then migrates chunks asynchronously to shards with cost-effective SATA disks, isolating write workloads.

### 3. Jumbo Chunk Resolution Runbook
Jumbo chunks exceed the maximum chunk size limit (default 64MB) and cannot be split because all documents share the same shard key value. The balancer ignores jumbo chunks, resulting in uneven storage distribution.

1.  **Temporarily Increase Chunk Size**:
    ```javascript
    use config
    db.settings.updateOne({ _id: "chunksize" }, { $set: { value: 10000 } });
    ```
2.  **Split the Chunk Manually**:
    Force a split of the jumbo chunk at its middle point:
    ```javascript
    sh.splitFind("acme.analytics", { customerId: 1042 });
    ```
3.  **Move the Chunk**:
    ```javascript
    sh.moveChunk("acme.analytics", { customerId: 1042 }, "shard-02");
    ```
4.  **Restore Original Chunk Size**:
    ```javascript
    db.settings.updateOne({ _id: "chunksize" }, { $set: { value: 64 } });
    ```
5.  **Refine Shard Key**:
    To prevent future jumbo chunks, refine the shard key dynamically to add cardinality (e.g., adding `timestamp` to `customerId`):
    ```javascript
    sh.refineCollectionShardKey("acme.analytics", { customerId: 1, timestamp: 1 });
    ```
