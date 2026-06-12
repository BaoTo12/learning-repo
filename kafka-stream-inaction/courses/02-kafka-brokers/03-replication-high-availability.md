# Module 03: Replication, High Watermarks & Data Durability

Apache Kafka ensures data availability and partition durability in the face of broker failures through its replication protocol. This module details the roles of leaders and followers, explains the lifecycle of the In-Sync Replicas (ISR) list, defines the relationships between High Watermarks and Log End Offsets, and analyzes the synergy between producer client configurations (`acks`) and broker-side settings (`min.insync.replicas`).

---

## 1. The Partition Replication Protocol

When creating a topic, you specify a **Replication Factor** (e.g., 3). This tells the cluster controller to allocate three replicas for each partition of the topic, distributed across different physical brokers to prevent single-point-of-failure issues.

```
                  ┌───────────────────────────────┐
                  │           PRODUCER            │
                  └──────────────┬────────────────┘
                                 │
                   Produce Request (acks=all)
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                          KAFKA CLUSTER                          │
│                                                                 │
│   ┌──────────────────┐  Fetch   ┌──────────────────┐            │
│   │     BROKER 1     │◄─────────┤     BROKER 2     │            │
│   │ (Leader Part 0)  │          │(Follower Part 0) │            │
│   └────────┬─────────┘          └──────────────────┘            │
│            ▲                                                    │
│            │ Fetch                                              │
│   ┌────────┴─────────┐                                          │
│   │     BROKER 3     │                                          │
│   │(Follower Part 0) │                                          │
│   └──────────────────┘                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 1.1 Leaders and Followers
For each partition, the cluster assigns brokers distinct replica roles:
*   **Leader**: The single broker responsible for handling all produce write requests and fetch read requests for the partition.
*   **Followers**: Passive replicas. They do not accept client writes. Instead, they act as consumers, issuing continuous `Fetch` requests to the partition leader to copy the log segments sequentially to their local disks.

---

## 2. In-Sync Replicas (ISR) and Lag Tracking

To ensure high availability without blocking writes indefinitely, Kafka maintains a subset of replicas called the **In-Sync Replicas (ISR)**. The ISR list contains the leader replica and all follower replicas that are caught up with the leader's log.

### 2.1 Determining Lag (`replica.lag.time.max.ms`)
A follower replica is considered "In-Sync" if it satisfies either of the following conditions:
1.  It is caught up to the leader’s Log End Offset (LEO).
2.  It has actively issued a `Fetch` request to the leader within the time window configured by **`replica.lag.time.max.ms`** (default: 30,000 ms / 30 seconds).

If a follower replica suffers a network partition, disk failure, or GC pause and fails to fetch or catch up within this window, the partition leader removes it from the ISR list. When the follower recovers and catches up, it is re-added to the ISR.

---

## 3. High Watermarks vs. Log End Offsets

To maintain consistency across replicas during failovers, Kafka uses two offset positions within each partition log:

```
Leader Partition Log:
┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
│ 0 │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │ 8 │ 9 │
└───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
                            ▲           ▲
                            │           │
                     High Watermark    Log End Offset (LEO)
                     (Last replica-    (Next offset to write)
                      committed offset)
```

1.  **Log End Offset (LEO)**: The offset of the next record to be written to the local log partition. Each replica tracks its own LEO.
2.  **High Watermark (HW)**: The offset of the last record that has been successfully replicated to **all** replicas in the ISR list.
    *   **Consumer Isolation**: Consumers can only read records up to the High Watermark. Even if the leader has accepted records 8 and 9 locally, consumers cannot fetch them until they are replicated to the followers and the High Watermark advances. This prevents consumers from reading "dirty" data that could be lost if the leader crashes before replication.

---

## 4. The Durability Matrix: `acks` vs. `min.insync.replicas`

Data durability is a shared responsibility between the producer client and the broker cluster.

### 4.1 Producer `acks` Configuration
When producing records, the client specifies the `acks` configuration to trade off throughput for write safety:
*   `acks=0`: The producer returns success as soon as the record is sent over the network. It does not wait for any broker write confirmation. High throughput, maximum risk of data loss.
*   `acks=1`: The producer waits for the partition leader to write the record to its local log. It does not wait for follower replication. Medium safety, low latency.
*   `acks=all` (or `acks=-1`): The producer waits for the record to be committed by **all** replicas currently in the ISR list. High safety, higher latency.

### 4.2 Broker `min.insync.replicas` Configuration
The broker-side configuration **`min.insync.replicas`** (default: 1) enforces the minimum size of the ISR list required to accept a write when a producer uses `acks=all`.

#### Scenario A: Default Setup (`min.insync.replicas=1`, `acks=all`)
*   If two follower brokers crash, they are removed from the ISR, leaving only the leader in the ISR list.
*   Because `min.insync.replicas=1`, the leader accepts the write and acknowledges the producer.
*   **Risk**: If the leader broker now suffers a hardware failure, the data is lost because it was never replicated.

#### Scenario B: Production Hardening (`min.insync.replicas=2`, `acks=all`)
*   With a replication factor of 3 and `min.insync.replicas=2`, the leader checks if at least two replicas (the leader + one follower) are active in the ISR.
*   If two followers crash, the ISR size drops to 1.
*   The leader rejects new produce requests with a **`NotEnoughReplicasException`**. The producer client catches this error and retries.
*   This ensures that no write is confirmed as successful unless it has been written to at least two physical brokers.

| Cluster Configuration | Active ISR Count | Produce Result (`acks=all`) | Durability Guarantee |
| :--- | :---: | :--- | :--- |
| `min.insync.replicas=1` | 3 | Success (ACK from all 3) | Excellent (Replicated across 3 brokers) |
| `min.insync.replicas=1` | 1 | Success (ACK from leader only) | Risky (Single point of failure) |
| `min.insync.replicas=2` | 3 | Success (ACK from all 3) | Excellent (Replicated across 3 brokers) |
| `min.insync.replicas=2` | 1 | **Fail (`NotEnoughReplicasException`)** | Hardened (Prevents single-point-of-failure writes) |
| `min.insync.replicas=3` | 2 | **Fail (`NotEnoughReplicasException`)** | Maximum Safety (Requires absolute cluster sync) |
