# Module 09: High Availability: Replication, Sentinel, and Redis Cluster

## 1. What Problem This Module Solves

A single Redis instance is a single point of failure (SPOF) and is limited by a single machine's RAM and CPU core. 
*   **Hardware Failures**: If the physical server hosting Redis crashes, the application loses its cache and database layer.
*   **Capacity Saturation**: High write traffic can saturate a single node's processing capability, and large datasets can exceed server memory.

This module covers how to scale Redis using **Master-Replica Replication**, automate failover using **Sentinel**, and partition data horizontally using **Redis Cluster**.

---

## 2. Why Redis is Used Instead of Alternatives

*   **Over Relational DB Clustering (for horizontal write scaling)**: Relational databases use complex synchronization models (e.g. multi-master replication or distributed lock managers) to maintain ACID guarantees, which limits throughput. Redis Cluster partitions data across independent hash slots, allowing writes to scale horizontally with sub-millisecond latencies.

---

## 3. High Availability Topologies

Redis provides two primary high-availability architectures:

```
[1. Redis Sentinel - HA for Single Master]
      ┌────────────────────────────────┐
      │   Sentinel Nodes (Consensus)   │
      └──────────────┬─────────────────┘
                     ▼ (Monitors & Failovers)
    Master Node (W/R) ◄───(Async Repl)───► Replica Node (R-only)

[2. Redis Cluster - Distributed Sharding]
 Hash Slots: [0 - 5460]     [5461 - 10922]     [10923 - 16383]
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │  Node A (M)  │◄───►│  Node B (M)  │◄───►│  Node C (M)  │  (Gossip Bus)
  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
         ▼                    ▼                    ▼
     Replica A            Replica B            Replica C
```

### 3.1 Replication Loops
Redis replication is asynchronous.
*   **PSYNC (Partial Resynchronization)**: If a replica disconnects briefly, it reconnects and requests a partial sync. It uses its **replication offset** and **master run ID** to read missed commands from the master's replication backlog buffer.
*   **Full Sync**: If the backlog buffer overflows or the replica is new, a full sync is triggered. The master runs a background save to generate an RDB file, writes the file to the replica socket, and streams incremental writes.

### 3.2 Redis Sentinel
Sentinel is a distributed system that monitors master-replica configurations:
1.  **Monitoring**: Sentinels check the health of master and replica nodes.
2.  **Consensus Failover**: If a master drops offline, Sentinels vote using a configured **Quorum** (e.g., 2 out of 3 sentinels agree). If quorum is met, Sentinel promotes a replica to master and reconfigures the other replicas.

### 3.3 Redis Cluster (Sharding)
Redis Cluster partitions data across multiple nodes:
*   **Hash Slots**: The keyspace is divided into **16,384** logical slots. Keys are mapped to slots using a CRC16 hash check:
    
    $$\text{Slot} = \text{CRC16}(\text{Key}) \pmod{16384}$$

*   **Hash Tags**: By default, multi-key operations (like MGET or transaction blocks) fail in a cluster if the keys reside on different nodes. You bypass this using Hash Tags (wrapping key segments in curly braces, e.g. `{user:1001}profile` and `{user:1001}orders`), which forces Redis to calculate the hash slot using only the braced segment, placing related keys on the same node.

---

## 4. Hands-on Exercises

1.  Configure a local 3-node Sentinel setup using Docker and trigger a master failover using `redis-cli DEBUG sleep 30`. Monitor Sentinel log outputs.
2.  Test the behavior of multi-key operations in a clustered environment with and without hash tags.

---

## 5. Mini-Project: Configuring HA Clients in Spring Boot

**Scenario**: You are deploying an application connecting to a high-availability Redis Cluster. You must configure Spring Data Redis to connect to the cluster topology and handle write failures gracefully.

### 1. Spring Cluster Configuration (`config/RedisClusterConfig.java`)
```java
package com.example.redis.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisClusterConfiguration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.lettuce.LettuceClientConfiguration;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import io.lettuce.core.cluster.ClusterClientOptions;
import io.lettuce.core.cluster.ClusterTopologyRefreshOptions;
import java.time.Duration;
import java.util.Arrays;

@Configuration
public class RedisClusterConfig {

    @Bean
    public RedisConnectionFactory redisConnectionFactory() {
        // 1. Declare cluster entry point nodes
        RedisClusterConfiguration clusterConfig = new RedisClusterConfiguration(
            Arrays.asList(
                "127.0.0.1:7000",
                "127.0.0.1:7001",
                "127.0.0.1:7002"
            )
        );

        // 2. Configure topology refresh intervals to detect node failovers automatically
        ClusterTopologyRefreshOptions refreshOptions = ClusterTopologyRefreshOptions.builder()
            .enableAllAdaptiveRefreshTriggers() // Trigger refresh on transitions
            .enablePeriodicRefresh(Duration.ofMinutes(10))
            .build();

        ClusterClientOptions clientOptions = ClusterClientOptions.builder()
            .topologyRefreshOptions(refreshOptions)
            .build();

        LettuceClientConfiguration clientConfig = LettuceClientConfiguration.builder()
            .clientOptions(clientOptions)
            .commandTimeout(Duration.ofSeconds(2))
            .build();

        return new LettuceConnectionFactory(clusterConfig, clientConfig);
    }
}
```

---

## 6. Interview Questions

### Q1: What is a Split-Brain scenario in Redis Sentinel? How do you configure Redis to mitigate it?
**Answer**: Split-brain occurs when network partition isolates the master node from the Sentinels and replicas. The Sentinels detect a master loss, promote a replica to master, and begin serving clients. 
However, the old master is still online and continues accepting writes from clients on its side of the partition. Once the network heals, the old master is demoted to a replica, and its local writes are overwritten, causing data loss.
**Mitigation**: Configure the master to reject writes if it loses its replicas:
```ini
min-replicas-to-write 1
min-replicas-max-lag 10
```

### Q2: How are Hash Slots allocated in Redis Cluster? Why does Redis use 16,384 slots instead of 65,536?
**Answer**: Redis Cluster divides its keyspace into 16,384 hash slots, which are distributed across the master nodes. 
**Why 16,384**:
1.  **Cluster Bus Overhead**: Nodes exchange topology details using gossip messages, which contain a bitmap of the slots they own. A 16,384-slot bitmap takes 2KB of memory. A 65,536-slot bitmap would take 8KB, consuming significant bandwidth.
2.  **Cluster Scale Limits**: Redis Cluster is designed to scale to a maximum of 1,000 master nodes, making 16,384 slots sufficient to ensure even distribution.

### Q3: What is the difference between client redirection codes `MOVED` and `ASK` in Redis Cluster?
**Answer**:
*   `MOVED`: Returned when a key belongs to a hash slot that is owned by a different node. The client must update its slot-to-node mapping cache and route subsequent queries for this slot to the new node.
*   `ASK`: Returned during hash slot migration (when a slot is being moved from Node A to Node B). It indicates that the key is currently on the destination node. The client must target the destination node for this single request without updating its permanent mapping cache.
