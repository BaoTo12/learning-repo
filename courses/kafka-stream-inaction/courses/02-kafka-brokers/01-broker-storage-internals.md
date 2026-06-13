# Module 01: Broker Storage Internals

At its core, a Kafka broker is a highly optimized storage engine designed for sequential append operations. It leverages filesystem storage, OS-level page caches, and memory-mapped indexes to deliver high throughput and low-latency reads and writes. This module examines the filesystem layout of topics, the internal structure of segment files, and the binary search lookup algorithms used for event retrieval.

---

## 1. Filesystem Directory Layout

Kafka organizes stored data hierarchically under the path specified by the `log.dirs` configuration in the broker's configuration file (e.g., `/var/lib/kafka/data`).

### Topics, Partitions, and Directories
A **Topic** is a logical concept. Physically, a topic is split into one or more **Partitions**. Each partition is assigned to a specific directory on disk, named according to the format:

$$\text{Directory Name} = \langle \text{topic\_name} \rangle - \langle \text{partition\_id} \rangle$$

For example, a topic named `purchases` with three partitions creates three distinct directories:
```
/var/lib/kafka/data/
├── purchases-0/
├── purchases-1/
└── purchases-2/
```

Inside each topic-partition directory, Kafka maintains the segment files and metadata checkpoints:
```
purchases-0/
├── 00000000000000000000.log
├── 00000000000000000000.index
├── 00000000000000000000.timeindex
├── 00000000000000125430.log
├── 00000000000000125430.index
├── 00000000000000125430.timeindex
├── leader-epoch-checkpoint
└── partition.metadata
```

*   **`leader-epoch-checkpoint`**: A state checkpoint tracking the mapping of leader epochs to the first offset appended by the leader of that epoch. Used for partition state reconciliation during leader failover to prevent data truncation anomalies.
*   **`partition.metadata`**: Stores metadata unique to the partition (e.g., the topic UUID).

---

## 2. Anatomy of a Log Segment

To prevent partition directories from growing into huge monolithic files, Kafka divides the log partition into **segments**. A segment is a logical grouping of three physical files sharing the same base name:

1.  **`.log` file**: The raw binary file containing the serialized Kafka records appended sequentially.
2.  **`.index` file**: A memory-mapped index file mapping relative offsets to physical byte positions in the `.log` file.
3.  **`.timeindex` file**: A memory-mapped index file mapping Unix timestamps to relative offsets.

### Segment Naming Convention
The 20-character name of each segment file corresponds to its **base offset**—the first offset written to that segment. 
*   The first segment in a partition starts at offset zero and is named `00000000000000000000.log`.
*   If the first segment rolls over when the next offset to write is `125430`, the broker creates a new segment group named `00000000000000125430.log`.

---

## 3. Physical Storage and Serialization Formats

### 3.1 The `.log` File Format
Each `.log` file is structured as a sequence of **Record Batches** containing individual records. Storing records in batches allows Kafka to write blocks of data together, compress payloads effectively (e.g., using Snappy, Gzip, Lz4, or Zstd), and use Zero-Copy transfers efficiently.

The binary layout of a Record Batch contains:
*   **Base Offset** (8 bytes): The offset of the first record in the batch.
*   **Batch Length** (4 bytes): The total size of the batch in bytes.
*   **Partition Leader Epoch** (4 bytes): Tracks the leader epoch at execution time.
*   **Magic Value** (1 byte): Format version indicator (v2 since Kafka 0.11.0).
*   **CRC32C** (4 bytes): Cyclical Redundancy Check to validate batch integrity.
*   **Attributes** (2 bytes): Compression codec, timestamp type, transactional flags.
*   **Last Offset Delta** (4 bytes): The difference between the last offset and the base offset.
*   **First Timestamp** (8 bytes): Epoch millisecond timestamp of the first record.
*   **Max Timestamp** (8 bytes): Maximum timestamp inside the batch.
*   **Producer ID** and **Producer Epoch** (10 bytes total): Used for idempotent/transactional write validation.
*   **Records Array**: The serialized payload elements.

### 3.2 The `.index` File (Offset-to-Position Index)
To read a record at offset $N$, Kafka does not scan the raw `.log` file sequentially. Instead, it queries the memory-mapped `.index` file.

To optimize space, the `.index` file stores **Relative Offsets** instead of absolute offsets. The relative offset is the delta between the target offset and the base offset of the segment:

$$\text{Relative Offset} = \text{Target Offset} - \text{Base Offset}$$

Each index entry is exactly 8 bytes, split into two 4-byte fields:

```
┌───────────────────────────┬───────────────────────────┐
│  Relative Offset (4 Bytes)│ Physical Position (4 Bytes)│
└───────────────────────────┴───────────────────────────┘
```

*   **Relative Offset**: Delta from base offset. Since a single segment rarely exceeds $2^{32}$ records, a 4-byte integer is sufficient.
*   **Physical Position**: The byte position from the start of the `.log` file where the record batch begins.

#### Index Density (`index.interval.bytes`)
Kafka does not write an entry to the `.index` file for every single record produced. That would make the index files massive. Instead, it writes entries at intervals of size defined by the `index.interval.bytes` configuration (default is 4096 bytes / 4 KB). This creates a **sparse index**.

---

## 4. Query Retrieval Mechanics and Binary Search

When a consumer sends a fetch request for a topic partition starting at offset $M$, the broker executes the following retrieval lookup:

```
Step 1: Identify the Segment
Scan the partition directory's segment base offsets.
Find the segment where: Base Offset <= Target Offset M < Next Segment Base Offset.

Step 2: Binary Search the Sparse Offset Index
Perform a binary search on the memory-mapped `.index` file of that segment.
Locate the index entry with the largest offset that is <= target offset M.

Step 3: Read Log File Sequentially
Jump to the physical byte position returned from the index entry in the `.log` file.
Scan sequentially through the records from that position until offset M is matched.
```

### Retrieval Example Visualized
*   Target Offset: `125432`
*   Segment Base Offset: `125430`
*   Target Relative Offset: `125432 - 125430 = 2`

```
.index File (Base Offset: 125430)
┌───────────┬──────────┐
│ RelOffset │ Position │
├───────────┼──────────┤
│     0     │    0     │
│     2     │   151    │  <-- Matches Relative Offset 2 (Exact Position 151)
│     4     │   300    │
└───────────┴──────────┘
                  │
                  ▼
.log File
┌──────────────────────────────────────────────┐
│ Position 0-150   │ Position 151-299          │
│ Record 125430/31 │ Record 125432 (Target)    │
└──────────────────────────────────────────────┘
```

---

## 5. Timestamp Lookups and the `.timeindex` File

For time-based consumer offsets lookups (e.g., replaying data from 8:00 AM yesterday) and time-based segment deletions, the broker uses the `.timeindex` file.

Each `.timeindex` entry is 12 bytes:
```
┌───────────────────────────────────────┬───────────────────────────┐
│          Timestamp (8 Bytes)          │  Relative Offset (4 Bytes)│
└───────────────────────────────────────┴───────────────────────────┘
```

*   **Timestamp**: Epoch millisecond timestamp of the record batch.
*   **Relative Offset**: Delta from base offset.

### Lookup Pipeline
1.  The broker identifies which segment covers the target timestamp $T$ by comparing it with the maximum timestamp of each segment.
2.  It binary searches the `.timeindex` file of the matching segment to locate the relative offset mapped to the largest timestamp less than or equal to $T$.
3.  Once the relative offset is retrieved, it queries the `.index` file to resolve the physical byte position in the `.log` file.
4.  It begins streaming records from that position.
