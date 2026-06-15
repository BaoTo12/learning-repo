# Module 02 — Kafka Brokers

In this module, we will dive deep into the internals of the storage engine: the Kafka Broker. We will examine write paths (produce requests), read paths (fetch requests), partition assignments, disk log structures, compaction, tiered storage, and cluster consensus mechanics. Finally, we will configure a partition-scale local topic and write a Java 17 AdminClient program to read broker configurations.

---

## 1. Academic Lecture: Kafka Broker Internals

### Basic Level: Kafka Broker as a Storage Coordinator
At its core, a **Kafka broker** is a server running in a distributed cluster that acts as the durable storage and replication layer for events.

##### Analogy: The Append-Only Journal
> Think of a Kafka partition log like a physical journal. You can write new lines at the bottom of the page (this is called **appending**). However, you are not allowed to erase or edit a line that has already been written. The lines are written in the order they happen, and they stay there forever. This makes writes extremely fast because the computer doesn't need to look up or update existing files; it just adds bytes at the very end of the file.

*   **Agnostic Byte Storage**: Brokers handle key-value records as raw binary byte arrays. The broker does not deserialize or inspect payloads, avoiding CPU overhead and allowing maximum transmission speeds.
*   **Topics and Partitions**: A **topic** is a logical stream namespace (e.g., `zmart-orders`). The physical storage unit is a **partition**. Topics are split into partitions and distributed across brokers in the cluster to support parallel processing and scaling.

##### Analogy: Grocery Store Checkout Lines
> Imagine a grocery store with only one cashier. If many customers arrive, the checkout line gets very long and slow. 
> To solve this, the store opens 3 cashier lines. Customers split up and check out in parallel. This is exactly how **partitions** work. By splitting a topic into multiple partitions, different consumers can read from different cashiers (brokers) at the same time, multiplying the system's processing speed. 
>
> If you purchase items and want to make sure your orders are checked out in sequence, you always go to cashier line 1. In Kafka, we hash the **key** to make sure all events with the same key always go to the same partition (line), preserving their order.

*   **Offsets**: Within a partition, each record is assigned a sequential ID called an offset. Offsets track consumer positions linearly.

---

### Intermediate Level: Log Segment Internals & Retention Policies

#### Log Directory Structure
On the broker's filesystem, each partition has its own directory. Inside that directory, the log is broken down into physical **segments**:
- `.log`: The actual binary segment file containing data records.
- `.index`: A memory-mapped file containing offsets mapped to physical byte positions in the `.log` file. The broker uses binary search in the index file to locate records quickly.
- `.timeindex`: A memory-mapped file containing timestamps mapped to offsets, enabling timestamp-based seek queries.

##### Analogy: Archive Cabinet Folders
> If you write in a journal every day, the book eventually gets too heavy. 
> To make it easy to manage, you start a new notebook every time the current one reaches 100 pages. In Kafka, these notebooks are called **log segments**.
> *   The `.log` file is the pages where you write.
> *   The `.index` file is like the table of contents at the front of the book, showing you exactly which page has offset 50 so you don't have to read every page to find it.

#### Segment Rolling
Logs roll (close the active segment file and create a new one) based on:
- Size limit: When the active `.log` file reaches 1 GB (`log.segment.bytes`).
- Age limit: When the segment age exceeds 7 days (`log.roll.hours`).

#### Data Retention Policies (`log.cleanup.policy`)
- **Delete policy (`delete`)**: Retains segments for a set period (`log.retention.hours`) or until total partition size exceeds a threshold (`log.retention.bytes`), after which older segments are deleted.
- **Compaction policy (`compact`)**: Retains the latest record value for each key. A background cleaner thread scans segments and removes duplicate keys, retaining only the latest record state.

##### Analogy: Address Book Cleanup
> Think of log compaction like an address book. If John moves three times, your journal will have three entries: John: Address A, John: Address B, and John: Address C. 
> In a compacted topic, the cleaner scans the book and erases the old addresses A and B, leaving only John: Address C. This saves space while keeping the latest state for every key.
>
> To delete John completely, you write a **tombstone** (John: null). The cleaner removes the previous entries, and eventually removes the tombstone after a delay (`delete.retention.ms`).

#### Tiered Storage (KIP-405)
Separates compute from storage:
*   **Local Tier**: Active and recent segments are stored locally on brokers for low-latency writes and reads.
*   **Remote Tier**: Older, inactive segments are moved to object stores (e.g., AWS S3, Google Cloud Storage), enabling virtually infinite storage capabilities.

---

### Advanced Level: Request Handling Engine & Replication Consensus Quorum

#### Write Path (Produce Requests)
When a producer writes a record:
1. It buffers records locally and sends them in batches to reduce network packet overhead. Batching is controlled by `linger.ms` (wait time) and `batch.size` (max size).
2. The broker receives the request, writes the batch to the active segment (WiredTiger Page Cache / OS Cache), and waits for replication confirmation depending on client `acks` settings:
   - `acks=0`: Acknowledged immediately (risk of loss).
   - `acks=1`: Acknowledged once the leader broker writes it.
   - `acks=all` (or `-1`): Acknowledged only when both the leader and all In-Sync Replicas (ISR) append it.

#### Read Path (Fetch Requests)
When a consumer pulls data:
1. It issues long-polling fetch requests targeting specific offsets. If no data exists, the broker holds the socket open until `fetch.max.wait.ms` expires or new data is appended.
2. The broker reads data from disk using the Linux kernel's page cache and the `sendfile()` system call, performing zero-copy socket transfers directly to avoid JVM memory copying overhead.

#### Replication and KRaft Consensus

##### Analogy: Lead Clerk and Backup Clerks
> Imagine a shop with a Lead Clerk (Leader) and two Backup Clerks (Followers). 
> *   When a customer places an order, they talk only to the Lead Clerk.
> *   The Lead Clerk writes the order in their ledger, and the Backup Clerks copy it into their ledgers (Replication).
> *   If a backup clerk falls behind or goes home, they are removed from the active list of helpers (In-Sync Replicas, or ISR).
> *   If the Lead Clerk gets sick, one of the active Backup Clerks in the ISR is chosen to be the new Lead Clerk.

*   **Leaders and Followers**: Every partition has one leader broker handling all reads and writes, and zero or more followers replicating segments.
*   **In-Sync Replicas (ISR)**: Followers actively caught up with the leader's log (checked via `replica.lag.time.max.ms`). Only ISR brokers can become leaders during failover.
*   **KRaft consensus**: Replaces ZooKeeper. Uses a Raft consensus quorum running on dedicated controller brokers to store cluster metadata in an internal metadata log. This speeds up controller elections and eliminates external dependencies.

---

## 2. Theory vs. Production Trade-offs

### Partition Count Trade-offs

| Configuration | Advantages | Disadvantages | Production Use Case |
| :--- | :--- | :--- | :--- |
| **Low Partitions (e.g., 1–3)** | Low memory overhead, fast startup, simpler client ordering. | Limited parallel throughput (restricted to 1 consumer thread per partition). | Metadata topics, low-volume reference data. |
| **High Partitions (e.g., 10+)** | High read/write parallelism, better scaling across brokers. | High file descriptor usage, increased client memory buffer, slower recovery times. | High-throughput events (e.g., clickstreams, metrics). |

### Replica Synced Write Assurances

| Configuration | Latency | Data Durability | High Availability Risk |
| :--- | :--- | :--- | :--- |
| **`acks=0`** | Lowest (No broker response wait) | Extremely Low (Data lost on network dropout) | High (Silent losses) |
| **`acks=1`** | Low (Leader confirmation only) | Moderate (Data lost if leader crashes before sync) | Low |
| **`acks=all` + `min.insync.replicas=2`** | Higher (Waits for ISR writes) | Highest (No data loss on broker failure) | Moderate (Writes fail if ISR count falls below minimum) |

---

## 3. Common Errors & Pitfalls

### Pitfall 1: Broker Request Handler Starvation (`request-handler-idle-percent < 20%`)
*   **Why it fails**: If brokers spend too much CPU time handling I/O or waiting for disks to write, the request handler threads become saturated, dropping the idle percentage. This leads to client-side timeouts and reconnection loops.
*   **Mitigation**: Scale the thread pool size via `num.io.threads` and `num.network.threads`, optimize disk mount parameters (e.g., use SSDs with `noatime`), and enable compression (`compression.type=lz4`).

### Pitfall 2: Memory-Mapped Files Exhaustion (OOM or `Too many open files` errors)
*   **Why it fails**: Kafka brokers keep index files (`.index`, `.timeindex`) memory-mapped. If a cluster contains too many partitions and segments, it hits OS limitations on open file handles (`ulimit -n`) or max memory mappings (`vm.max_map_count`), crashing the broker process.
*   **Mitigation**: Set high OS limits (`ulimit -n 65536`), adjust segment sizes to prevent excessive fragmentation, and implement tiered storage.

---

## 4. Socratic Review Questions

### Question 1
How does a broker handle a write request if `acks=all` is configured but the current ISR count is lower than `min.insync.replicas`?

#### Answer
The broker will refuse the write request and return a `NotEnoughReplicasException` or `NotEnoughReplicasAfterAppendException` error to the producer client. This ensures that the data is not written with a lower durability guarantee than expected by the application designer.

### Question 2
Why does log compaction require a configuration parameter like `delete.retention.ms` for tombstone records?

#### Answer
A tombstone record (a record with a null value) must remain in the log long enough for active consumer applications to read it and delete their local state representations. If the tombstone were cleaned immediately, a consumer that was offline during the compaction sweep would never receive the deletion event and would keep the stale key in its state store indefinitely.

---

## Hands-on Lab: Partition Analysis and Java AdminClient

In this lab, we will create a partitioned topic, inspect log directories on disk, configure log compaction, and write a Java 17 program to query broker metadata using the `AdminClient` API.

### 1. Setup the Docker Compose Environment
Use the same `docker-compose.yml` file from Module 1, and run the following command to start it:

```bash
docker-compose up -d
```

### 2. Create a Partitioned Topic
Create a topic named `partition-check` with 3 partitions and a replication factor of 1:

```bash
docker exec -it kafka-broker kafka-topics --create --topic partition-check --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
```

### 3. Produce Keyed Messages to Inspect Routing
Produce messages with defined keys:

```bash
docker exec -it kafka-broker kafka-console-producer --topic partition-check --bootstrap-server localhost:9092 --property parse.key=true --property key.separator=:
```

Paste these lines to verify key hashing routing:

```text
user-1:msg1
user-2:msg2
user-3:msg3
user-1:msg4
user-2:msg5
```

Press `Ctrl+C` to terminate when finished.

### 4. Inspect Partition Directories and Log Segments
List the directory structure inside the broker's storage directory:

```bash
docker exec -it kafka-broker ls -la /var/lib/kafka/data/
```

**Expected Output:**
```text
drwxr-xr-x 1 appuser appuser  4096 Jun 15 00:00 partition-check-0
drwxr-xr-x 1 appuser appuser  4096 Jun 15 00:00 partition-check-1
drwxr-xr-x 1 appuser appuser  4096 Jun 15 00:00 partition-check-2
```

Inspect the files in the `partition-check-0` partition directory:

```bash
docker exec -it kafka-broker ls -la /var/lib/kafka/data/partition-check-0/
```

**Expected Output:**
```text
-rw-r--r-- 1 appuser appuser 10485760 Jun 15 00:00 00000000000000000000.index
-rw-r--r-- 1 appuser appuser       76 Jun 15 00:00 00000000000000000000.log
-rw-r--r-- 1 appuser appuser 10485756 Jun 15 00:00 00000000000000000000.timeindex
```

### 5. Verify Compaction Behavior
Create a compacted topic named `compact-test`:

```bash
docker exec -it kafka-broker kafka-topics --create --topic compact-test --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 --config cleanup.policy=compact --config min.cleanable.dirty.ratio=0.01 --config segment.ms=100
```

Produce updates for the same key:

```bash
docker exec -it kafka-broker kafka-console-producer --topic compact-test --bootstrap-server localhost:9092 --property parse.key=true --property key.separator=:
```

Paste these values:

```text
key-A:value-1
key-A:value-2
key-B:value-1
key-A:value-3
```

Press `Ctrl+C` to terminate.

Run the consumer to verify that only the latest value for `key-A` is retained after log cleaner compaction runs:

```bash
docker exec -it kafka-broker kafka-console-consumer --topic compact-test --bootstrap-server localhost:9092 --from-beginning --property print.key=true --property key.separator=":"
```

**Expected Output:**
```text
key-B:value-1
key-A:value-3
```

---

### 6. Java 17 AdminClient Tool

Create a Java program to query broker configurations and metrics.

#### Maven `pom.xml` Dependency Block
Add these configurations to your Java application:

```xml
<dependencies>
    <dependency>
        <groupId>org.apache.kafka</groupId>
        <artifactId>kafka-clients</artifactId>
        <version>3.6.0</version>
    </dependency>
</dependencies>
```

#### Detailed Breakdown of Maven Dependency Block Properties:
*   `dependencies`: Surrounds the list of all external software packages your app downloads and uses.
*   `dependency`: Marks the start of a single package download configuration.
*   `groupId: org.apache.kafka`: The name of the organization or group that publishes this package.
*   `artifactId: kafka-clients`: The specific library name we want to download (the Kafka core client code).
*   `version: 3.6.0`: The exact version version of the client code we want to fetch.

#### Java Implementation Class
```java
package com.zmart.kafka.admin; // Corrected package namespace

import org.apache.kafka.clients.admin.AdminClient;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.DescribeClusterResult;
import org.apache.kafka.clients.admin.DescribeConfigsResult;
import org.apache.kafka.common.Node;
import org.apache.kafka.common.config.ConfigResource;

import java.util.Collections;
import java.util.Properties;
import java.util.concurrent.ExecutionException;

public class KafkaAdminMetricsTool {

    public static void main(String[] args) {
        // 1. Set up broker connection properties
        Properties config = new Properties();
        
        // AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG tells Java the network address of the broker (localhost:9092)
        config.put(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");

        // 2. Create the AdminClient connection inside a try-with-resources block to auto-close it
        try (AdminClient adminClient = AdminClient.create(config)) {
            System.out.println("Connecting to Kafka cluster...");

            // 3. Describe the Cluster Nodes
            DescribeClusterResult clusterResult = adminClient.describeCluster();
            String clusterId = clusterResult.clusterId().get();
            Node controller = clusterResult.controller().get();

            System.out.println("Cluster ID: " + clusterId);
            System.out.println("Active Controller Node: " + controller.id() + " (" + controller.host() + ":" + controller.port() + ")");

            for (Node node : clusterResult.nodes().get()) {
                System.out.println("Broker Node: " + node.id() + " on " + node.host() + ":" + node.port());
            }

            // 4. Query Specific Broker Configurations (checking cleanup policy and segment size)
            ConfigResource brokerResource = new ConfigResource(ConfigResource.Type.BROKER, String.valueOf(controller.id()));
            DescribeConfigsResult configsResult = adminClient.describeConfigs(Collections.singletonList(brokerResource));

            configsResult.all().get().forEach((resource, cfg) -> {
                System.out.println("\nConfiguration for Broker " + resource.name() + ":");
                cfg.entries().stream()
                        .filter(entry -> entry.name().equals("log.cleanup.policy") 
                                      || entry.name().equals("log.segment.bytes") 
                                      || entry.name().equals("log.retention.hours"))
                        .forEach(entry -> System.out.println(" - " + entry.name() + " = " + entry.value()));
            });

        } catch (InterruptedException | ExecutionException e) {
            System.err.println("Failed to query cluster metadata: " + e.getMessage());
            Thread.currentThread().interrupt();
        }
    }
}
```

#### Program Execution Verification
Make sure the cluster is running. Execute the tool using Java 17:

```bash
java -cp target/kafka-admin-tool-1.0.jar com.zmart.kafka.admin.KafkaAdminMetricsTool
```

**Expected Console Stdout Output:**
```text
Connecting to Kafka cluster...
Cluster ID: MkU3OEVBNTcwNTJENDM2Qk
Active Controller Node: 1 (localhost:9092)
Broker Node: 1 on localhost:9092

Configuration for Broker 1:
 - log.cleanup.policy = [delete]
 - log.segment.bytes = 1073741824
 - log.retention.hours = 168
```
