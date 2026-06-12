# Module 02: Log Compaction, Retention & Tiered Storage

To prevent physical disks on brokers from filling up, Kafka provides automated log cleanup strategies. This module details the configurations governing time- and size-based data retention, the mechanics of key-based Log Compaction, the role of tombstone markers, and the architecture of Tiered Storage (KIP-405) for separating compute from storage.

---

## 1. Log Retention Policies: Time- and Size-Based Deletion

Kafka brokers use a coarse-grained segment deletion approach to clean up old files. When a segment's contents exceed configured limits, the broker marks the segment for deletion and subsequently deletes the files from disk.

### 1.1 Time-Based Retention
Time-based retention triggers segment deletion based on the age of the records. The broker evaluates retention using the maximum timestamp of records within each segment, *not* the modification time of the file on disk.

There are three time retention settings, listed in order of priority:
1.  **`log.retention.ms`**: How long to keep a segment in milliseconds. (Highest priority)
2.  **`log.retention.minutes`**: How long to keep a segment in minutes.
3.  **`log.retention.hours`**: How long to keep a segment in hours. (Default: 168 hours / 7 days)

If a segment's maximum record timestamp is older than the configured limit, the segment is eligible for deletion.

### 1.2 Size-Based Retention
Size-based retention deletes the oldest segments when the total physical size of a partition directory exceeds the configured threshold.
*   **`log.retention.bytes`**: The maximum allowed size of a partition's log directory (Default: `-1` / Unlimited). 

If you configure both time- and size-based thresholds, the broker deletes segments as soon as *either* limit is reached.

---

## 2. Log Compaction Mechanics

For topics containing key-value updates—where only the latest value for a specific key is necessary for system state initialization (e.g., database changelogs, cache stores)—Kafka provides **Log Compaction**.

To enable compaction on a topic, configure:
```bash
log.cleanup.policy=compact
```

```
Log Compaction Pipeline (Before vs After)

Before:
┌──────────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┐
│ Offset   │  10   │  11   │  12   │  13   │  14   │  15   │  16   │
├──────────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┤
│ Key      │  K1   │  K2   │  K1   │  K3   │  K2   │  K4   │  K1   │
├──────────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┤
│ Value    │  A    │  B    │  C    │  D    │  E    │  F    │  G    │
└──────────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┘
                                 │
                                 ▼ (Log Cleaner deduplicates)
After:
┌──────────┬───────┬───────┬───────┬───────┐
│ Offset   │  13   │  14   │  15   │  16   │
├──────────┼───────┼───────┼───────┼───────┤
│ Key      │  K3   │  K2   │  K4   │  K1   │
├──────────┼───────┼───────┼───────┼───────┤
│ Value    │  D    │  E    │  F    │  G    │
└──────────┴───────┴───────┴───────┴───────┘
```

### 2.1 The Log Cleaner Thread Pool
The broker manages log compaction via a background pool of **Log Cleaner** threads. The compaction process splits the log segments into two parts:
1.  **Clean Log (Active head/tail)**: The compacted segment file section containing only one record per key.
2.  **Dirty Log**: The uncompacted section containing updates and duplicate keys.

```
┌───────────────────────────────┬───────────────────────────────┐
│           CLEAN LOG           │           DIRTY LOG           │
│  (Only latest value per key)  │       (Contains updates)      │
└───────────────────────────────┴───────────────────────────────┘
                                ▲
                          Cleaner Point
```

#### Compaction Step-by-Step
1.  **Identify Dirty Segments**: The cleaner thread selects the partition with the highest dirty ratio (configured via `log.cleaner.min.cleanable.ratio`, defaulting to `0.5` / 50%).
2.  **Build Offset Map**: The cleaner reads the dirty log segment sequentially and populates an in-memory hash table (the **Skimpy Offset Map**). The map keys are the hash of the record keys, and the values are their physical offsets. As duplicates are read, the offset is updated to the latest offset.
3.  **Recopy Segments**: The thread reads the clean segments and dirty segments, writing only records whose offsets match the highest offset stored in the Skimpy Offset Map back into new, compacted segments.
4.  **Swap Segments**: The broker swaps the active segments with the newly created compacted segments and deletes the old ones.

### 2.2 Tombstones: How Deletions Occur in Compacted Topics
In a compacted topic, sending a new write to an existing key overwrites the old value. To physically **delete** a key from the log, the producer client must write a record with the target key and a `null` value. This record is called a **tombstone marker**.

#### Tombstone Lifecycle
1.  **Write**: The tombstone is appended to the active segment log.
2.  **Compaction**: During compaction, the log cleaner removes all prior records associated with that key, but preserves the tombstone marker.
3.  **Removal**: The tombstone marker remains in the log to allow downstream consumers to read it and delete the key from their local caches/state stores. The tombstone is physically deleted during a subsequent compaction pass after `delete.retention.ms` (default: 24 hours) has elapsed.

---

## 3. Tiered Storage Architecture (KIP-405)

Historically, increasing Kafka's storage capacity required adding more brokers to the cluster. This coupled computation power (CPU/Memory) with storage capacity (Disks), leading to high costs and slow broker rebalancing times when data had to be replicated over the network.

**Tiered Storage** separates computation from storage by introducing a two-tiered system:

```
┌───────────────────────────────────────────────────────────────┐
│                         KAFKA BROKER                          │
├───────────────────────────────┬───────────────────────────────┤
│         LOCAL STORAGE         │        REMOTE STORAGE         │
│          "Hot" Data           │        "Warm & Cold"          │
│   Active/Recent Segments      │      Completed Segments       │
│        (Fast SSD/NVMe)        │    (S3 / GCS / Azure Blob)    │
└───────────────────────────────┴───────────────────────────────┘
```

### 1. Local Tier (Hot Data)
*   **Role**: Consists of local physical disks (SSDs/NVMe) attached to the brokers.
*   **Data**: Stores the active segments currently being written to, and recent segments being fetched by real-time consumers.
*   **Retention**: Configured via local retention parameters (e.g., `log.local.retention.bytes` or `log.local.retention.ms`). Typically configured for a few hours.

### 2. Remote Tier (Warm/Cold Data)
*   **Role**: Object storage systems like Amazon S3, Google Cloud Storage, or Azure Blob storage.
*   **Data**: As local segments roll over and exceed the local retention period, the broker uploads them to the remote storage tier.
*   **Read Path**: When a historical consumer requests an old offset, the broker intercepts the request, streams the segment data from object storage, and serves it to the consumer client over TCP. The client application is unaware that the data was retrieved from the cloud storage tier rather than local disk.

### Benefits of Tiered Storage
*   **Storage Cost Reduction**: Object storage is significantly cheaper than provisioning high-performance SSDs on brokers.
*   **Instant Rebalancing**: When a new broker joins a cluster, it only needs to replicate the small active local segments. Warm/Cold historical segments remain in object storage and do not need to be transferred over the network.
*   **Virtually Infinite Retention**: Enables Kafka topics to act as a system of record for long-term historical audits.
