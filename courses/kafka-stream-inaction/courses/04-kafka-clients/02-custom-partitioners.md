# Module 02: Partition Routing & Custom Partitioners

In Apache Kafka, partitions are the primary unit of scalability and parallelism. How records are distributed across partitions determines client throughput, broker balancing, and downstream order guarantees. This module explores default routing mechanics (key-based hashing vs. sticky batch partition assignment) and walks through the implementation and configuration of a custom partitioner in Java.

---

## 1. Default Partitioning Algorithms

When building a `ProducerRecord` in Java, you can construct it with or without a key:

```java
// Option A: Key-less record
ProducerRecord<String, String> record = new ProducerRecord<>("topic-name", "value");

// Option B: Keyed record
ProducerRecord<String, String> record = new ProducerRecord<>("topic-name", "order-123", "value");
```

The default partitioner (`DefaultPartitioner`) handles these records using different routing strategies:

### 1.1 Key-Based Hashing (Deterministic Routing)
If a record contains a non-null key, the default partitioner generates the destination partition using a hashing formula:

$$\text{Partition ID} = \text{toPositive}(\text{murmur2}(\text{serializedKeyBytes})) \pmod{\text{Total Partitions}}$$

*   **Order Guarantee**: Because the formula is deterministic, all records sharing the exact same key bytes will always route to the exact same partition. This ensures strict, chronological order guarantees within that partition.

### 1.2 Sticky Partitioning (Key-less Routing)
Historically, if a record was sent without a key, Kafka used a Round-Robin algorithm (alternating partitions for every single record). This created many tiny, half-empty batches across all partition buffers, causing high network overhead and broker write latency.

Modern Kafka versions use **Sticky Partitioning**:
1.  When a key-less record is sent, the partitioner selects a target partition at random.
2.  All subsequent key-less records are pinned ("stuck") to that same partition batch buffer until the batch is either full (`batch.size` reached) or rolled over (`linger.ms` elapsed).
3.  Once the batch is sent to the broker, the partitioner selects a new partition at random and repeats the process.
4.  This strategy maximizes batch sizes and throughput while ensuring an even distribution of keys over time.

---

## 2. Implementing a Custom Partitioner in Java

Suppose your business domain has a special case: orders associated with a testing account or VIP client (`CUSTOM`) must always be isolated to a single partition (`0`) to undergo processing or validation. All other standard client transactions must be evenly distributed across partitions `1` to $N-1$ using standard hashing.

To achieve this, implement the `org.apache.kafka.clients.producer.Partitioner` interface:

```java
package bbejeck.chapter_4.sales;

import org.apache.kafka.clients.producer.Partitioner;
import org.apache.kafka.common.Cluster;
import org.apache.kafka.common.PartitionInfo;
import org.apache.kafka.common.utils.Utils;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * A custom partitioner that isolates the "CUSTOM" key to partition 0
 * and hashes all other keys across the remaining partitions.
 */
public class CustomOrderPartitioner implements Partitioner {

    @Override
    public void configure(Map<String, ?> configs) {
        // Retrieve custom configurations if needed. Called during client bootstrap.
    }

    @Override
    public int partition(String topic, Object key, byte[] keyBytes, Object value, byte[] valueBytes, Cluster cluster) {
        Objects.requireNonNull(key, "Record key must not be null when using CustomOrderPartitioner");
        
        // Resolve partition count for the topic
        int numPartitions = cluster.partitionCountForTopic(topic);
        
        // Throw an exception if configuration requires multiple partitions but only one exists
        if (numPartitions < 2) {
            throw new IllegalArgumentException("CustomOrderPartitioner requires a minimum of 2 topic partitions");
        }
        
        String stringKey = (String) key;
        int targetPartition;

        if ("CUSTOM".equalsIgnoreCase(stringKey)) {
            // Force special key to partition 0
            targetPartition = 0;
        } else {
            // Distribute other keys across partitions [1, numPartitions - 1]
            // Standard murmur2 hash calculation
            int murmurHash = Utils.toPositive(Utils.murmur2(keyBytes));
            
            // Map modulo to range [0, numPartitions - 2] and shift by +1
            targetPartition = (murmurHash % (numPartitions - 1)) + 1;
        }

        return targetPartition;
    }

    @Override
    public void close() {
        // Cleanup resources
    }
}
```

---

## 3. Configuring the Producer to Use a Custom Partitioner

To bind the custom partitioner class, add the configuration key `partitioner.class` to your producer properties:

```java
import org.apache.kafka.clients.producer.ProducerConfig;
import bbejeck.chapter_4.sales.CustomOrderPartitioner;
import java.util.Properties;

public class CustomPartitionerApp {
    public static void main(String[] args) {
        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringSerializer");
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringSerializer");
        
        // Bind the Custom Partitioner
        props.put(ProducerConfig.PARTITIONER_CLASS_CONFIG, CustomOrderPartitioner.class.getName());
        
        // Build producer
        // ...
    }
}
```
