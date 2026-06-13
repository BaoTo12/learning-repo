# Module 04: Partition Assignment Protocols

When consumers join or leave a group, partition ownership must be redistributed. The protocol used to handle this redistribution directly impacts the availability and processing latency of your streaming pipelines. This module explains the different partition assignment algorithms and compares the eager "stop-the-world" rebalance protocol with the Incremental Cooperative Rebalance protocol.

---

## 1. Partition Assignor Algorithms

Kafka consumers select their partition mapping strategy using the `partition.assignment.strategy` configuration. The available assignors determine how topic partitions are divided among group members:

---

### 1.1 RangeAssignor (Default)
The RangeAssignor operates on a per-topic basis.
*   **Algorithm**: For each topic, it sorts the partitions in numerical order and the consumers in lexicographical order. It divides the partition count by the consumer count to determine how many partitions to assign to each consumer. If there is a remainder, the first few consumers receive an extra partition.

$$\text{Partitions Per Consumer} = \frac{\text{Partitions}}{\text{Consumers}}$$

*   **Risk of Skew**: If a group subscribes to multiple topics (e.g., 10 topics, each with 3 partitions) and runs 3 consumers, the RangeAssignor will assign partition `0` of *every* topic to Consumer 1, partition `1` to Consumer 2, and partition `2` to Consumer 3. This leads to severe resource imbalance:

```
Consumer 1: 10 Partitions (Partition 0 of all topics)
Consumer 2: 10 Partitions (Partition 1 of all topics)
Consumer 3: 10 Partitions (Partition 2 of all topics)
```

---

### 1.2 RoundRobinAssignor
The RoundRobinAssignor ignores topic boundaries and treats all subscribed partitions collectively.
*   **Algorithm**: It lays out all partitions from all subscribed topics sequentially and distributes them one-by-one to the consumers in a round-robin loop.
*   **Advantage**: Ensures a balanced partition count across all consumers, regardless of how many topics are consumed.

---

### 1.3 StickyAssignor
The StickyAssignor aims to achieve two primary goals:
1.  **Maximum Balance**: Partition distribution is kept as even as possible.
2.  **Minimum Migration**: During a rebalance, it preserves existing partition assignments where possible. If Consumer A drops off, only its partitions are reassigned; Consumer B and C keep their existing assignments.

---

## 2. Rebalancing Protocols: Eager vs. Cooperative Sticky

The rebalance protocol controls *how* the partitions are handed over during changes in group membership.

---

### 2.1 Eager Rebalancing (Stop-the-World)
Eager rebalancing enforces a **Synchronization Barrier** where all processing must halt across the entire group until the rebalance completes.

```
State: Consumer A, B, C processing. Consumer C dies.
Step 1: Rebalance triggered.
Step 2: ALL consumers (A and B) immediately revoke all their partition assignments.
Step 3: Processing HALTS globally.
Step 4: A and B send JoinGroup requests, re-register, and await SyncGroup responses.
Step 5: Assignments received. Processing restarts.
```

*   **Downtime Cost**: During the JoinGroup/SyncGroup round trips, no records are processed. In large-scale deployments, this pause can last from seconds to minutes.

---

### 2.2 Incremental Cooperative Rebalancing
Introduced in Kafka 2.4, this protocol rebalances *incrementally* without revoking unchanged partitions, eliminating the stop-the-world pause for unaffected resources.

```
State: Consumer A (Part 0,1) and Consumer B (Part 2,3) active. Consumer C joins.
Step 1: Rebalance triggered. A and B keep processing their partitions.
Step 2: Group Leader determines that only Partition 1 and 3 need to migrate to C.
Step 3: First Phase: A and B are instructed to revoke ONLY Partition 1 and 3.
        (A keeps processing Part 0; B keeps processing Part 2).
Step 4: Second Phase: A rebalance is triggered to assign Partition 1 and 3 to Consumer C.
```

*   **Key Advantage**: The synchronization barrier is isolated only to the specific partitions undergoing reassignment. Unaffected partitions continue processing data uninterrupted throughout the rebalance.

---

## 3. Configuration

To configure your consumer to use the modern, non-blocking cooperative protocol, assign the `CooperativeStickyAssignor` class:

```java
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.CooperativeStickyAssignor;
import java.util.Properties;

public class CooperativeConsumerApp {
    public static void main(String[] args) {
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "retail-group");
        
        // Enable Incremental Cooperative Sticky Rebalancing
        props.put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG, 
                  CooperativeStickyAssignor.class.getName());
        
        // Build consumer
        // ...
    }
}
```
