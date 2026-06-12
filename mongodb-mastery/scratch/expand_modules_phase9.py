#!/usr/bin/env python3
import os

modules_dir = r"c:\Users\Admin\Desktop\projects\learning-repo\mongodb-mastery\modules"

book_sections = {
    "01-mongodb-foundations.md": """
---

## 15. Advanced Production Host Settings & Systems Architecture

### 1. NUMA (Non-Uniform Memory Access) Node Interleaving
When running MongoDB on modern multi-socket hardware, CPU scheduling and memory allocation defaults can degrade database operations. NUMA binds RAM to specific CPU sockets. By default, a process running on CPU 1 prefers local memory nodes. When CPU 1's local memory is full, the OS kernel starts evicting cached database pages to swap space, even if CPU 2 has free memory. This leads to disk swapping and high page fault rates.

To disable NUMA memory zones behavior on Linux, configure a memory interleave policy before starting the `mongod` daemon:
```bash
# 1. Disable zone reclaim in the sysctl configuration
echo 0 | sudo tee /proc/sys/vm/zone_reclaim_mode
sudo sysctl -w vm.zone_reclaim_mode=0

# 2. Start the database instance interleaved across all memory nodes
numactl --interleave=all mongod --config /etc/mongod.conf
```
*Note*: On Windows, memory interleaving must be enabled through the hardware BIOS settings.

### 2. Disabling Transparent Huge Pages (THP)
Transparent Huge Pages (THP) allocates memory in 2MB to 256MB pages instead of the standard x86 4KB page size. While large pages benefit sequential memory allocations, they degrade MongoDB's random memory access profiles. Reading or writing a small document forces the OS to page-in and page-out huge memory chunks, inflating memory consumption, triggering disk thrashing, and slowing down WiredTiger dirty page flushes.

Check if THP is active and disable it:
```bash
# Check current THP status
cat /sys/kernel/mm/transparent_hugepage/enabled

# Disable THP dynamically
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
```
Ensure these commands run on system startup by appending them to `/etc/rc.local`.

### 3. Readahead (RA) Calibration for SSDs
Operating system readahead instructs the block manager to load extra sectors from disk into memory on the assumption that disk access is sequential. For random read/write workloads (like MongoDB database instances), high readahead settings (e.g. 128KB or 256KB) read unnecessary blocks into memory, causing disk I/O write bottlenecks. Set readahead to between 8 and 32 blocks (4KB - 16KB) for WiredTiger on SSDs:
```bash
# Set block device readahead size
sudo blockdev --setra 16 /dev/sda
```
""",
    "03-data-modeling.md": """
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
""",
    "04-indexing-and-query-performance.md": """
---

## 15. Special Collections & Advanced Storage Engines (Capped & GridFS)

### 1. Capped Collections and Cursors
Capped collections are fixed-size, circular queues that overwrite the oldest document when they run out of space.
*   **Restricted Writes**: Documents cannot be deleted, and updates that increase the BSON document size are rejected.
*   **Creation syntax**:
    ```javascript
    db.createCollection("audit_logs", { capped: true, size: 5242880, max: 10000 });
    ```
*   **Tailable Cursors**: Keep a cursor open after query execution ends. As new documents are written, the cursor consumes them. Use `cursorType: TAILABLE_AWAIT` to listen for events in queueing applications.

### 2. GridFS Binary Data Storage Architecture
When storing binaries exceeding the 16MB limit, GridFS splits files into chunks (default 255KB) and stores them in two collections:
*   `fs.files`: Groups file metadata:
    ```javascript
    {
      "_id": ObjectId("..."),
      "length": NumberLong(12589000),
      "chunkSize": 261120, // 255KB
      "uploadDate": ISODate("2026-06-12T07:15:00Z"),
      "filename": "manual.pdf",
      "md5": "e2c3b88..."
    }
    ```
*   `fs.chunks`: Stores binary pieces linked by `files_id`:
    ```javascript
    {
      "_id": ObjectId("..."),
      "files_id": ObjectId("..."), // References fs.files._id
      "n": 0,                      // Sequence sequence offset
      "data": BinData(0, "...")    // Binary payload
    }
    ```
GridFS uses two secondary indexes to optimize reads: `{ files_id: 1, n: 1 }` on `fs.chunks` and `{ filename: 1, uploadDate: 1 }` on `fs.files`.

### 3. TTL (Time-To-Live) Index Execution
TTL indexes age out documents after a duration. A background thread runs every 60 seconds to delete expired documents:
```javascript
db.sessions.createIndex({ lastUpdated: 1 }, { expireAfterSeconds: 86400 });
```
*   **Limits**: TTL indexes cannot be compound, and they cannot be built on capped collections.
""",
    "06-transactions-and-consistency.md": """
---

## 15. Cluster-wide Logical Clock & Causal Consistency Sessions

### 1. Causal Consistency and logical Sessions
Logical sessions track the time and sequencing of database operations. A causally consistent client session guarantees that read and write operations maintain order across secondary nodes, preventing stale reads. Under the hood, MongoDB uses a global logical clock. Read and write operations exchange logical time tokens (`$clusterTime`) signed by cryptographic keys to establish causality:
```json
{
  "$clusterTime": {
    "clusterTime": Timestamp(1541450091, 2),
    "signature": { "hash": BinData(0, "abc..."), "keyId": NumberLong(12) }
  }
}
```

### 2. Core API vs. Callback API Transactions
*   **Core API**: The developer manually initiates logical sessions, starts transactions, handles rollbacks, and writes error-handling loops for `TransientTransactionError` and `UnknownTransactionCommitResult`.
*   **Callback API**: Automatically starts transactions, processes callback operations, commits transactions, and handles transient errors.
```python
# Python Callback API Transaction example
with client.start_session() as session:
    def callback(my_session):
        orders = my_session.client.webshop.orders
        inventory = my_session.client.webshop.inventory
        orders.insert_one({"sku": "abc123", "qty": 100}, session=my_session)
        inventory.update_one({"sku": "abc123", "qty": {"$gte": 100}},
                             {"$inc": {"qty": -100}}, session=my_session)
    session.with_transaction(callback)
```

### 3. Read Concerns and wtimeout
*   `linearizable`: Reads wait for majority verification, blocking if a network partition occurs.
*   `snapshot`: Reads data from a point-in-time snapshot, guaranteeing isolation within transactions.
*   `wtimeout`: Limit write concern blocks when replication consensus fails.
""",
    "07-replication-and-high-availability.md": """
---

## 16. Replication Internals: Initial Sync & Rollback BSON Recovery

### 1. Five Phases of Initial Synchronization
When a new node joins the replica set with an empty data folder, it performs an initial sync:
1.  **Drop Existing Data**: The sync node drops all databases (except the local database).
2.  **Clone Collections**: Copies collections in parallel from the sync source while fetching any oplog writes generated during the clone.
3.  **Build Indexes**: Creates secondary indexes on all cloned collections to match the sync source.
4.  **Apply Oplog Modifications**: Applies oplog modifications captured during cloning to bring the node up to date.
5.  **Replication Transition**: Joins the secondary sync queue to apply ongoing changes.

### 2. Sync Source Latency Selection
Secondaries monitor ping latency to select their synchronization source dynamically, preferring nodes with ping times within 15ms of the nearest member. Chaining allows nodes to sync from other secondaries, reducing bandwidth on the primary. Disable chaining if required:
```javascript
cfg = rs.conf();
cfg.settings.chainingAllowed = false;
rs.reconfig(cfg);
```

### 3. Rollback BSON Recovery
If a primary receives writes but crashes before they replicate to the majority, the newly elected primary will diverge. When the old node reconnects as a secondary, it must roll back its uncommitted writes. MongoDB saves these rolled-back writes to physical `.bson` files in the `<dbpath>/rollback/<collectionName>.<timestamp>.bson` directory.

To recover and merge these rolled-back records:
1.  **Import to a Staging Collection**:
    ```bash
    mongorestore --db staging_db --collection rollback_data /var/lib/mongodb/rollback/saas.orders.2026-06-12T07.bson
    ```
2.  **Examine and Merge Documents**:
    Write a script to compare and merge records into the production collection:
    ```javascript
    db.getSiblingDB("staging_db").rollback_data.find().forEach(function(doc) {
      db.getSiblingDB("saas").orders.updateOne(
        { _id: doc._id },
        { $setOnInsert: doc },
        { upsert: true }
      );
    });
    ```
""",
    "08-sharding-and-horizontal-scaling.md": """
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
"""
}

def apply_book_knowledge():
    print("Applying MongoDB: The Definitive Guide knowledge to modules...")
    
    for filename, section in book_sections.items():
        filepath = os.path.join(modules_dir, filename)
        if not os.path.exists(filepath):
            print(f"Skipping {filename} - path not found.")
            continue
            
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        if "Advanced Production Host Settings & Systems Architecture" in content or "Advanced Cardinality & High-Scale Relationship Modeling" in content or "Special Collections & Advanced Storage Engines" in content or "Cluster-wide Logical Clock & Causal Consistency" in content or "Replication Internals: Initial Sync & Rollback BSON Recovery" in content or "Shard Key Engineering: Jumbo Chunks & Capacity Distribution" in content:
            print(f"Skipping {filename} - already contains book knowledge.")
            continue
            
        new_content = content.strip() + "\n\n" + section.strip() + "\n"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print(f"Applied book knowledge to {filename} successfully.")

if __name__ == "__main__":
    apply_book_knowledge()
