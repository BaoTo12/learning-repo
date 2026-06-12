# Module 07: Replication Internals & High Availability

## 1. What Problem This Module Solves
In modern distributed architectures, a single database node is a single point of failure (SPOF). Hardware failures, network partitions, and datacenter outages are inevitable. High availability requires replication: copying data across multiple physical machines to ensure that if the primary node fails, another node can immediately take over with minimal downtime and zero data loss.

However, replication introduces distributed state coordination challenges. A senior engineer must understand the internal consensus protocols governing elections, write concern confirmation steps, replication oplog mechanics, heartbeats, chained replication trade-offs, and how to recover rolled-back data from physical disk files. Failing to manage these parameters results in replication lag spikes, stale reads, data loss during split-brain partitions, and unstable replica sets.

---

## 2. Why This Topic Matters
Replica sets are the foundation of MongoDB's high availability. Selecting incorrect configurations, such as using database arbiters in multi-datacenter environments or under-sizing the oplog, can lead to replication failures under high write loads. 

Furthermore, when a network split occurs, understanding how MongoDB elects a new primary and how it handles un-replicated writes (rollbacks) is critical for preventing data corruption in financial or user-profile storage systems. This module provides the deep technical understanding required to run, monitor, and recover replica sets in high-throughput production environments.

---

## 3. Core Concepts & Internals

### 3.1 Election Protocols & Raft-based Consensus
MongoDB replica sets use a consensus protocol based on the **Raft Consensus Algorithm** to manage primary node election and membership configurations.

#### The Election Flow:
1.  **Heartbeats**: Every member of a replica set sends a heartbeat ping (ping request) to every other member every **2 seconds** (configured by `heartbeatIntervalMillis`). If a node does not receive a heartbeat response within **10 seconds** (`electionTimeoutMillis`), it marks the target node as unreachable.
2.  **State Transition**: If a secondary node detects that the primary is unreachable, it increments its internal **term** count and transitions to the **candidate** state.
3.  **Vote Solicitation**: The candidate node sends a request to vote (`replSetRequestVotes`) to all other voting members of the replica set.
4.  **Voting Criteria**: A voting member grants its vote to the candidate only if:
    *   The candidate's term is greater than the voting node's current term.
    *   The candidate's oplog is **at least as fresh** as the voting node's oplog (checked via logical timestamps).
    *   The candidate is eligible to become primary (based on node priority and votes configuration).
5.  **Consensus**: A candidate must receive a **majority of all voting members** defined in the replica set configuration to be elected primary. If a majority is met, the node transitions to primary and begins accepting client writes.

```
[Secondary Node A] ──> (Misses heartbeat from Primary for 10s)
        │
        ▼
[State Transition] ──> Increment Term -> Candidate State
        │
        ▼
[replSetRequestVotes] ── Solicitation ──> [Secondary Node B]
                                                 │
                                                 ▼ (Is candidate's oplog as fresh?)
                                             [Vote Granted]
                                                 │
                                                 ▼
[Receive Majority Votes] ── Consensuses ──> [Transition to PRIMARY]
```

#### Node Priority and Voting Weights:
*   **Priority (`priority`)**: A number between `0` and `1000` (Default: `1`). Nodes with higher priority values are preferred as primary nodes. If a secondary node has a higher priority than the current primary, it will trigger an election to step down the primary and take over, provided its oplog is caught up.
*   **Votes (`votes`)**: A binary flag (`0` or `1`) indicating whether the node can vote in elections. A replica set can have a maximum of **50 members**, but only a maximum of **7 members** can have voting rights.

---

### 3.2 Oplog Mechanics & Secondary Synchronization Pipelines
The **Oplog** (operations log) is a capped collection (`local.oplog.rs`) stored on every replica set member. It records all database modifications in an idempotent format.

#### Oplog Structure & Operation Types:
*   `op`: The operation type:
    *   `i`: Insert.
    *   `u`: Update.
    *   `d`: Delete.
    *   `c`: Database commands (e.g., creating collections, index changes).
    *   `n`: No-op (periodic keep-alive writes).
*   `ts`: Timestamp (a hybrid logical clock composed of 4-byte seconds epoch + 4-byte increment counter).
*   `ui`: UUID of the collection.
*   `ns`: Namespace (database and collection name).
*   `o`: The document payload or change descriptor.

#### Secondary Replication Process:
1.  **Oplog Polling**: Secondary nodes continuously pull new oplog entries from their sync source (which can be the primary or another secondary) using long-polling `getMore` requests.
2.  **Applier Threads**: To maximize throughput, secondaries partition oplog entries by document ID and apply them in parallel using a pool of writer threads.
3.  **Idempotency**: All oplog entries are designed to be idempotent. For example, if a write query increments a counter, the oplog translates this into a specific value set (`$set: { count: 10 }`). This ensures that applying the same oplog entry multiple times yields the exact same state, which is crucial for crash recovery and secondary synchronization.

```
  [Sync Source Oplog] 
          │
          ▼ (Long-polling getMore)
  [Oplog Fetcher Thread]
          │
          ▼ (Partitioned by Document ID)
  [Writer Thread Pool] ── (Parallel Oplog Application)
          │
          ▼
   [Local Database]
```

#### Chained Replication:
*   By default, secondary nodes can select another secondary node as their sync source rather than the primary. This is called **Chained Replication**.
*   *Advantage*: Reduces the network load and CPU usage on the primary node.
*   *Disadvantage*: Increases replication lag across the replica set, as writes must hop through multiple nodes before reaching all secondaries.
*   *Tuning*: Chained replication can be disabled by setting `chainingAllowed` to `false` in the replica set configuration.

---

### 3.3 Replication Rollback Internals
When a primary node crashes, a secondary node is elected primary. If the old primary had written data that had not yet been replicated to the majority commit point, those writes are now orphaned.

#### The Rollback Lifecycle:
1.  When the old primary re-establishes contact with the replica set, it discovers it is now a secondary and its oplog diverged from the new primary's oplog.
2.  The node searches backward through its oplog to find the **Common Point** where its history matched the new primary's history.
3.  Any writes applied after this common point must be undone to sync with the new primary.
4.  WiredTiger rolls back these modifications. The undone documents are not discarded; they are written to physical **rollback files** on disk:
    *   Path: `<dbpath>/rollback/<collection_uuid>/`
    *   Format: `.bson` files containing the document states before they were rolled back.
5.  After clearing the mismatched writes, the secondary node syncs with the current primary to catch up.

#### Recovering Rollback Data:
To recover data from a rollback, a database administrator must inspect the physical `.bson` files using tools like `bsondump` and re-apply them to the primary:
```bash
# Convert BSON rollback file to readable JSON
bsondump /var/lib/mongodb/rollback/users_uuid/rollback.1.bson > rollback_data.json

# Re-import missing documents to the database
mongorestore --host="mongo-primary:27017" --db="ecommerce" --collection="users" /var/lib/mongodb/rollback/users_uuid/rollback.1.bson
```

---

### 3.4 Monitoring Replication Status
You can check the health and configuration of a replica set using administrative commands in the MongoDB shell.

#### Output of `rs.status()`:
```javascript
db.adminCommand({ replSetGetStatus: 1 });
```

This returns a detailed status document for the replica set:
```json
{
  "set": "rs0",
  "date": ISODate("2026-06-12T07:25:00Z"),
  "myState": 1,
  "term": NumberLong(2),
  "syncSourceHost": "",
  "syncSourceId": -1,
  "heartbeatIntervalMillis": NumberLong(2000),
  "majorityVoteCount": 2,
  "writeMajorityEstimateDate": ISODate("2026-06-12T07:24:59Z"),
  "members": [
    {
      "_id": 0,
      "name": "mongo-primary:27017",
      "health": 1,
      "state": 1,
      "stateStr": "PRIMARY",
      "uptime": 3600,
      "optime": {
        "ts": Timestamp(1718165099, 1),
        "t": NumberLong(2)
      },
      "optimeDate": ISODate("2026-06-12T07:24:59Z"),
      "electionTime": Timestamp(1718165000, 1),
      "electionDate": ISODate("2026-06-12T07:23:20Z"),
      "self": true
    },
    {
      "_id": 1,
      "name": "mongo-secondary1:27017",
      "health": 1,
      "state": 2,
      "stateStr": "SECONDARY",
      "uptime": 3580,
      "optime": {
        "ts": Timestamp(1718165099, 1),
        "t": NumberLong(2)
      },
      "optimeDate": ISODate("2026-06-12T07:24:59Z"),
      "syncSourceHost": "mongo-primary:27017",
      "syncSourceId": 0
    },
    {
      "_id": 2,
      "name": "mongo-secondary2:27017",
      "health": 1,
      "state": 2,
      "stateStr": "SECONDARY",
      "uptime": 3550,
      "optime": {
        "ts": Timestamp(1718165095, 1),
        "t": NumberLong(2)
      },
      "optimeDate": ISODate("2026-06-12T07:24:55Z"),
      "syncSourceHost": "mongo-secondary1:27017",
      "syncSourceId": 1
    }
  ],
  "ok": 1
}
```

*   `term`: The election term. Used to identify when the active primary was elected.
*   `state`: The node's state: `1` for PRIMARY, `2` for SECONDARY.
*   `optime`: The timestamp of the last oplog entry applied by the node.
*   *Replication Lag Calculation*: The difference between the primary's `optimeDate` and a secondary's `optimeDate` is the replication lag for that secondary. In the example above, `mongo-secondary2` has **4 seconds** of replication lag.
*   `syncSourceHost`: Indicates which node this member is syncing from. Here, `mongo-secondary2` is syncing from `mongo-secondary1`, showing chained replication is active.

---

### 3.5 Production Configurations for Replication
When deploying a production-ready replica set, you should configure options in `/etc/mongod.conf` to optimize replication health and resource limits.

```yaml
# /etc/mongod.conf replica set configuration sections
replication:
  oplogSizeMB: 51200          # 50GB Oplog size to guarantee a 48-hour sync window
  replSetName: "prodReplSet"  # Name of the replica set
  enableMajorityReadConcern: true # Enforce majority snapshot isolation

net:
  port: 27017
  bindIp: 0.0.0.0             # Bind to all network adapters
  maxIncomingConnections: 65536

storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true
  wiredTiger:
    engineConfig:
      cacheSizeGB: 16         # Enforce dedicated cache pool allocation
```

#### Configuring Hidden and Delayed Members:
For analytical queries or backup safety, you can configure secondary nodes that do not participate in elections or receive writes directly, and delay replication:
```javascript
// rs.conf() edit sequence
const config = rs.conf();
// Member indices are 0-indexed. Let member at index 2 be hidden and delayed by 1 hour.
config.members[2].priority = 0;      // Cannot become primary
config.members[2].hidden = true;      // Hidden from client driver queries
config.members[2].votes = 1;          // Can still vote in elections
config.members[2].secondaryDelaySecs = 3600; // Delay applying operations by 1 hour
rs.reconfig(config);
```

---

## 4. Practical Examples

### Replication Lag Monitoring Script (Python)
The following Python script connects to a replica set, monitors the replication state, calculates replication lag in seconds, and triggers alerts if lag exceeds a set threshold.

```python
#!/usr/bin/env python3
import sys
import time
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

def monitor_replica_set(uri, max_acceptable_lag=5.0):
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Verify connection
        client.admin.command('ping')
        print(f"Connected to replica set using URI: {uri}")
    except ConnectionFailure as ex:
        print(f"CRITICAL: Failed to connect to MongoDB cluster: {ex}")
        sys.exit(1)

    while True:
        try:
            status = client.admin.command('replSetGetStatus')
            members = status.get('members', [])
            
            # Find the primary node's current optime date
            primary_date = None
            for member in members:
                if member.get('stateStr') == 'PRIMARY':
                    primary_date = member.get('optimeDate')
                    break

            if not primary_date:
                print("WARNING: No PRIMARY node detected in replica set!")
                time.sleep(2)
                continue

            print(f"\n--- Checking Replication Health (Primary Time: {primary_date}) ---")

            for member in members:
                name = member.get('name')
                state = member.get('stateStr')
                health = member.get('health')

                if health == 0:
                    print(f"ALERT: Member {name} is reporting health: OFFLINE!")
                    continue

                if state == 'SECONDARY':
                    secondary_date = member.get('optimeDate')
                    # Calculate difference in seconds
                    lag = (primary_date - secondary_date).total_seconds()
                    
                    print(f"Node: {name:<25} State: {state:<10} Lag: {lag:.2f}s  SyncSource: {member.get('syncSourceHost')}")
                    
                    if lag > max_acceptable_lag:
                        print(f"ALERT: Node {name} replication lag is high ({lag:.2f}s > {max_acceptable_lag}s)!")
                elif state == 'PRIMARY':
                    print(f"Node: {name:<25} State: {state:<10} Lag: 0.00s")

        except OperationFailure as ex:
            print(f"ERROR: Failed to run replSetGetStatus: {ex}")
        except Exception as ex:
            print(f"ERROR: Unexpected error occurred: {ex}")

        time.sleep(5)

if __name__ == '__main__':
    MONGO_URI = "mongodb://mongo-primary:27017,mongo-secondary1:27017,mongo-secondary2:27017/?replicaSet=rs0"
    monitor_replica_set(MONGO_URI)
```

---

### Step-Down and Sync Source Management Script (Bash / mongosh)
This shell script shows how to force a primary node to step down and how to manually configure sync sources on secondaries.

```bash
#!/usr/bin/env bash
# Replica Set Management Automation

PRIMARY_HOST="mongo-primary.prod:27017"
SECONDARY_HOST="mongo-secondary2.prod:27017"
SYNC_TARGET="mongo-secondary1.prod:27017"

# 1. Force primary node to step down for maintenance (seconds to stay secondary)
echo "Forcing Primary at $PRIMARY_HOST to step down for 60 seconds..."
mongosh --host "$PRIMARY_HOST" --quiet --eval "
  try {
    rs.stepDown(60);
    print('Primary successfully stepped down.');
  } catch(e) {
    print('Error stepping down primary: ' + e.message);
  }
"

# Wait for election to stabilize
sleep 5

# 2. Manually change secondary node sync source
echo "Configuring sync source for $SECONDARY_HOST to $SYNC_TARGET..."
mongosh --host "$SECONDARY_HOST" --quiet --eval "
  db.adminCommand({ replSetSyncFrom: '$SYNC_TARGET' });
  print('Sync source set to $SYNC_TARGET');
"
```

---

## 5. Trade-offs & Alternatives

Replica set topologies require aligning durability, network limits, and costs:

| Topology Configuration | Read Scaling | Write Durability | Network Traffic | Cost Impact | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **3-Node Replica Set** (1 Pri, 2 Sec) | **Low**: Reads can be offloaded to 2 secondaries, but lag must be managed. | **Standard**: `{ w: majority }` writes require acknowledgment from 2 nodes. | **Minimal**: Light synchronization traffic. | **Standard**: Needs 3 nodes/instances. | Standard web applications, test environments. |
| **5-Node Replica Set** (1 Pri, 4 Sec) | **High**: Offloads reads to 4 secondaries across different availability zones. | **High**: Acknowledged by 3 nodes, meaning it can survive 2 node outages. | **Medium**: Multi-node heartbeat and sync traffic. | **High**: Operational and instance costs for 5 nodes. | Enterprise databases, high-availability critical apps. |
| **Geographically Distributed Set** (Multi-region) | **Excellent**: Low read latency for regional users using local read preferences. | **Low**: Syncing writes across regions increases latency. | **High**: Cross-region data transfer costs. | **Maximum**: Multi-region hosting and bandwidth costs. | Global multi-user platforms. |
| **Arbiter Topologies** (1 Pri, 1 Sec, 1 Arbiter) | **Minimal**: Read traffic can only be offloaded to a single secondary. | **Risky**: If the secondary fails, the arbiter cannot hold data, leaving the set in read-only mode. | **Low**: Arbiter only exchanges heartbeats. | **Low**: Arbiters require minimal CPU and RAM. | Budget-constrained systems (not recommended for production). |

---

## 6. Common Mistakes & Anti-patterns
*   **Using Arbiters in Production**: Deploying arbiters to save instance costs. While arbiters help elect a primary by breaking ties, they do not hold data. If a node fails, the arbiter cannot help with recovery, leaving the database vulnerable to data loss if another node goes offline.
*   **Replica Sets with Even Member Counts**: Setting up a 4-node replica set. An election requires a majority of all voting members. A 4-node set needs **3 votes** for a majority. If a network split divides the set into 2 nodes on each side, neither side can elect a primary. A 3-node set also needs 2 votes, but it can still elect a primary if a single node fails.
*   **Under-sizing the Oplog**: Under-sizing the oplog on high-write systems. If the write volume is high, the oplog will wrap around quickly. If a secondary node goes offline for maintenance and stays down longer than the oplog window, it will miss entries that have already been overwritten, forcing a full resync from scratch.

---

## 7. Hands-on Exercises
1.  Configure a local 3-node replica set using Docker Compose.
2.  Use `mongosh` to view replica set configuration and verify heartbeats using `rs.status()`.
3.  Simulate a primary node crash by stopping the primary container. Monitor the replica set state to observe the election and verify that a secondary node is promoted to primary.
4.  Restart the old primary container. Find the divergence point and check if any rollback files were created on disk under `/data/db/rollback/`.

---

## 8. Mini-Project: Replica Failover Recovery Test
**Scenario**: Test the failover behavior and data integrity of your replica set under write loads.

1.  Write a script to continuously insert documents into a replica set with write concern `{ w: 1 }`.
2.  Stop the primary node container while the script is running.
3.  Observe the election time and verify that write operations fail until a new primary is elected.
4.  Measure the number of failed writes during the election window.
5.  Restart the old primary, locate the rollback `.bson` files generated, convert them to JSON, and verify if any writes were rolled back.

---

## 9. Interview Questions

### Q1: What is the difference between replication lag and heartbeat timeout? How do they affect client applications?
**Answer**:
*   **Replication Lag** is the time difference between when an operation is written to the primary's oplog and when it is applied to a secondary node. High replication lag causes stale reads on client applications that read from secondaries.
*   **Heartbeat Timeout** is the time limit a node waits for a response to a heartbeat ping from another node. If heartbeats fail for longer than this limit (default 10s), it triggers an election. Client applications will experience brief write failures (10-15s) until the election completes.

### Q2: Why is a majority of all voting members in a replica set required to elect a primary, rather than just a majority of online nodes?
**Answer**: Requiring a majority of *all* voting members prevents split-brain scenarios during network partitions. If a replica set is partitioned into two isolated groups, only the side that contains a majority of the original members can elect a primary. The minority side cannot reach a majority of all voting members, preventing it from electing a primary. If elections only required a majority of online nodes, both sides could elect a primary, leading to divergent datasets and data corruption.

### Q3: What is the risk of enabling chained replication, and how do you disable it?
**Answer**: Chained replication allows secondary nodes to sync from other secondaries rather than directly from the primary. While this reduces the CPU and network load on the primary, it increases replication lag across the replica set because updates must hop through multiple nodes. You can disable chained replication by updating the replica set configuration settings:
```javascript
const cfg = rs.conf();
cfg.settings.chainingAllowed = false;
rs.reconfig(cfg);
```

---

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

## 12. Appendix: Advanced Troubleshooting & Operational Failure Modes

### 1. Synchronization Loop Deadlocks
*   **Failure Mode**: In rare instances under chained replication, secondary nodes can form a synchronization loop (e.g. Node A syncs from Node B, and Node B syncs from Node A), stalling all replication.
*   **Diagnosis**: Run `rs.status()` and check the `syncSourceHost` values. If nodes are referencing each other in a circle, replication lag will increase continuously.
*   **Resolution**: Force a specific node to sync directly from the primary:
    ```javascript
    db.adminCommand({ replSetSyncFrom: "mongo-primary.prod:27017" });
    ```

### 2. Oplog Rollover Recovery (OutOfSync Error)
*   **Failure Mode**: A secondary node goes offline for maintenance and stays down longer than the oplog window. When it rejoins, the sync source has already overwritten the required oplog entries, causing replication to fail with an `rsFatal` or `OplogStartMissing` error (Code 94).
*   **Resolution**: The secondary must perform a **Initial Sync** to pull the entire dataset from scratch.
    1. Stop the secondary daemon: `systemctl stop mongod`.
    2. Empty the data directory: `rm -rf /var/lib/mongodb/*`.
    3. Restart the secondary daemon: `systemctl start mongod`. The node will detect the empty database and automatically trigger an initial sync from the primary.

### 3. Split-Brain Partitions & Rollback Files Inspections
*   **Failure Mode**: A network partition splits a 3-node replica set into a 2-node side and a 1-node side. The 2-node side elects a primary and continues to accept writes. The isolated node (old primary) continues to accept writes from client drivers that do not use majority write concerns.
*   **Resolution**: When the network recovers, the isolated node steps down, finds the divergence point, and writes the un-replicated documents to `.bson` rollback files on disk. Administrator must manually restore them:
    ```bash
    # Extract BSON documents for review
    bsondump /var/lib/mongodb/rollback/orders/rollback.2026-06-12.bson
    ```

---

## 13. Summary
Managing replication and high availability requires balancing write consistency, election timeouts, and sync sources. By leveraging Raft-based consensus, sizing the oplog correctly, avoiding arbiters in production, and monitoring lag, senior database administrators build highly resilient database clusters.

---

## 13. Enterprise Case Study: Oplog Purge & Secondary Desynchronization

### 1. Scenario Description
A large-scale migration was executed on the primary database node, writing 500GB of historical data. The primary node completed the writes quickly. However, the secondary nodes fell behind due to disk I/O bottlenecks. Because the write volume exceeded the capacity of the oplog, the sync offset on the secondary nodes fell off the end of the oplog. The secondaries entered the `FATAL` replication state, showing replication lag of `Infinity`.

### 2. Analytical Diagnostic Investigation
The operations team ran `rs.status()` and observed the replication states of secondaries:
```json
{
  "name": "secondary-node-01:27017",
  "stateStr": "STARTUP2",
  "syncSourceHost": "",
  "lastHeartbeatMessage": "RS102 Oplog loop: client has fallen behind sync source oplog window bounds."
}
```
They checked replication statistics on the primary:
```javascript
db.getReplicationInfo();
```
**Diagnostic Findings**:
*   The Oplog window length had dropped to 1.5 hours because of the high write volume.
*   The secondaries had been lagging by 2 hours due to disk write queues.
*   Because the secondary's last synchronized timestamp was older than the oldest record in the primary's oplog, the secondary could not resume replication and required a full initial sync.

### 3. Step-by-Step Recovery and Tuning Runbook
To recover the secondaries and prevent future synchronization failures, they completed these steps:

1.  **Increase the Oplog Window Capacity Dynamically**:
    On the primary node, they resized the oplog to 150GB to provide a buffer for migrations:
    ```javascript
    db.adminCommand({
      replSetResizeOplog: 1,
      size: 153600 // Resize oplog capacity to 150GB
    });
    ```
2.  **Re-verify Oplog Size Details**:
    ```javascript
    db.getSiblingDB("local").oplog.rs.stats().maxSize;
    ```
3.  **Force Re-Synchronization on the Failed Secondary**:
    On the secondary node host, execute:
    ```bash
    # Stop the mongod service instance
    sudo systemctl stop mongod
    # Delete the data directory files to force a clean initial sync
    sudo rm -rf /var/lib/mongodb/data/*
    # Restart the service
    sudo systemctl start mongod
    ```
    This forces the secondary to pull a fresh snapshot copy from the primary node.
4.  **Tweak Heartbeat and Timeout Values**:
    To prevent network jitter from triggering split-brain elections, they adjusted settings:
    ```javascript
    cfg = rs.conf();
    cfg.settings.electionTimeoutMillis = 15000; // Allow 15 seconds before elections
    rs.reconfig(cfg);
    ```

### 4. Code Artifact: Shell-Based Replication Monitoring Script
Save the script as `/usr/local/bin/monitor-replication.sh` to check replication health:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Querying replica set health details..."

# Fetch replication lag in seconds
LAG_SEC=$(mongosh --quiet --eval '
  const status = rs.status();
  const primaryTime = status.members.find(m => m.state === 1).optimeDate;
  const secondaryTime = status.members.find(m => m.self).optimeDate;
  const lag = (primaryTime - secondaryTime) / 1000;
  print(lag);
')

echo "Current secondary replication lag: ${LAG_SEC} seconds."

# Alert if lag is greater than 1 hour (3600 seconds)
if (( $(echo "${LAG_SEC} > 3600" | bc -l) )); then
  echo "CRITICAL ALERT: Secondary is lagging by more than 1 hour!"
  exit 2
else
  echo "Replication health check: OK"
fi
```

### 5. Architectural Trade-offs & Lessons Learned
*   **Keep Oplog Sizes Large**: Disk space is cheap. Allocate at least 10-20% of your total storage to the oplog to handle batch data operations and maintenance windows without resyncs.
*   **Write Concerns Impact Performance**: Higher write concerns (`{ w: "majority" }`) increase execution latency, but they prevent rollback issues when a primary node fails.

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
