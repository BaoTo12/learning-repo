# Module 01: Database Performance and Scaling Boundaries

## 1. What Problem This Module Solves
Application scaling strategies for stateless microservices do not apply to stateful relational databases:
*   **The Shared-State Bottleneck**: You cannot scale a relational database by simply adding more instances. Multiple database instances must coordinate locks, disk writes, and cache state, which introduces network coordination overhead.
*   **Thread Context-Switching Storms**: Allocating database connection pools that are too large forces the database server CPU to waste cycles switching contexts between thousands of competing worker threads rather than executing SQL queries.
*   **Replication Lag Anomalies**: Spreading read traffic across read-replicas can cause clients to read stale data if the write replication has not yet propagated (Read-Your-Own-Write anomaly).

This module explains how database engines handle connection resources and presents scaling patterns (replication, sharding) alongside their architectural trade-offs.

---

## 2. Response Time, Throughput, and Physical Boundaries

In performance engineering, the execution of a request is governed by the following relationship:

$$\text{Response Time} = \text{Service Time} + \text{Wait Time}$$

*   **Service Time**: The actual duration the database CPU spends reading disk pages, performing index lookups, or executing joins.
*   **Wait Time**: The duration the request spends in queue waiting for an available execution thread, lock, or disk IO slot.

```
Incoming Queries ───► [ Connection Queue ] ───► [ Active DB Workers (Sized to CPU Cores) ]
                           ▲
                           └─ If workers are saturated, wait times rise exponentially
```

### The Physical Boundaries of a Database Connection
A database connection is not a cheap memory reference; it is a complex physical resource:
1.  **Network Socket**: Consumes an OS file descriptor and a local TCP port on both the client and database hosts.
2.  **Server Process/Thread**: In process-per-connection engines (like PostgreSQL) or thread-per-connection engines (like MySQL), every connection spawns an isolated OS process or thread.
3.  **Private Buffers**: Each database process allocates private memory regions (e.g., sort buffers, join buffers) off-heap. Having too many idle connections wastes gigabytes of RAM.
4.  **CPU Context-Switching**: If a database server with 16 CPU cores hosts 1,000 active connections, the OS scheduler spends more CPU cycles swapping process registers in and out of the CPU cores (context-switching) than executing queries.

---

## 3. Scaling Patterns: Vertical vs Horizontal

| Scaling Strategy | Mechanics | Primary Benefit | Limitation / Trade-off |
| :--- | :--- | :--- | :--- |
| **Scale-Up (Vertical)** | Adding faster CPUs, more RAM, and NVMe SSDs to a single node. | Simple. Zero code changes. Maintains ACID guarantees. | Hard hardware cost ceilings. Single Point of Failure (SPOF). |
| **Master-Slave (Read replicas)** | Routing all write transactions to a Master node; replicating modifications asynchronously to Slave nodes. | Increases read throughput. | Eventual consistency. Replication lag risks. Slave cannot accept writes. |
| **Multi-Master Replication** | Multiple database nodes accept write operations and synchronize. | High availability. Node failure recovery. | Complex conflict resolution. High network coordination latency. Split-brain risks. |
| **Sharding (Horizontal Partitioning)** | Splitting data across independent databases using a partition key (e.g. User ID). | Scales write throughput horizontally. | Cross-shard joins are disabled or slow. Multi-shard transactions require 2PC. |

---

## 4. Common Mistakes and Anti-Patterns
*   **Master-Slave for Write Bottlenecks**: Attempting to solve write latency or thread exhaustion issues by adding read-replicas. Adding replicas increases master CPU load because the master must serialize write logs and transmit them to the slave pool.
*   **Ignoring Replication Lag in Application Code**: Writing user changes to the master, then immediately redirecting the page refresh to a read-replica. The user receives a blank or outdated page because the replica has not yet processed the transaction logs (Read-Your-Own-Write anomaly).
    *   *Correction*: Route critical user-facing reads to the master, or track log sequence numbers (LSN).

---

## 5. Production Architecture: The Read-Your-Own-Write Pattern

In high-scale setups, route write operations to the primary node and read operations to the read-replicas. To prevent users from seeing stale data, route queries to the primary node for a short window after a write.

```
[ Client Write Request ] ───► [ Transaction Router ] ───► [ Primary Database ]
                                      │
                                      ▼ (Sets user session write flag in Cache)
                                 [ Redis Cache ]
                                      ▲
[ Client Read Request ]  ───► [ Router checks flag ]
                                 ├─ (Flag Present: Route to Primary)
                                 └─ (Flag Absent: Route to Read-Replica)
```

---

## 6. Hands-on Exercises
1.  Use `sysbench` or a custom Java execution loop to run parallel queries against a PostgreSQL database. Measure latency changes as you increase thread concurrency beyond the CPU core count.
2.  Configure a master-slave replication group in Docker Compose and measure the replication lag (in bytes/time) during high-throughput bulk inserts.

---

## 7. Mini-Project: Concurrency Latency Analyzer in Java
Write a raw Java program that executes concurrent database tasks over a varying thread pool, measuring throughput and database wait times to demonstrate the impact of thread count on query latency.

### Implementation Code (`ConcurrencyAnalyzer.java`)
```java
package com.example.jdbc.performance;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;

public class ConcurrencyAnalyzer {

    private static final String DB_URL = "jdbc:postgresql://localhost:5432/jdbc_db";
    private static final String DB_USER = "postgres";
    private static final String DB_PASS = "postgres";

    public static void runTest(int poolSize, int totalRequests) throws Exception {
        ExecutorService executor = Executors.newFixedThreadPool(poolSize);
        List<Callable<Long>> tasks = new ArrayList<>();

        for (int i = 0; i < totalRequests; i++) {
            tasks.add(() -> {
                long start = System.nanoTime();
                // Connect and run dummy PG query that sleeps to simulate DB processing
                try (Connection conn = DriverManager.getConnection(DB_URL, DB_USER, DB_PASS);
                     Statement stmt = conn.createStatement()) {
                    
                    // Force the database engine to sleep for 20ms to simulate disk IO
                    stmt.execute("SELECT pg_sleep(0.02);");
                }
                return System.nanoTime() - start;
            });
        }

        long testStart = System.currentTimeMillis();
        List<Future<Long>> results = executor.invokeAll(tasks);
        long testDuration = System.currentTimeMillis() - testStart;

        long totalLatencyNs = 0;
        for (Future<Long> res : results) {
            totalLatencyNs += res.get();
        }

        double averageLatencyMs = (totalLatencyNs / (double) totalRequests) / 1_000_000.0;
        double throughput = (totalRequests / (double) testDuration) * 1000.0;

        System.out.printf("Threads: %d | Throughput: %.2f req/sec | Average Latency: %.2f ms | Test Duration: %d ms\n",
            poolSize, throughput, averageLatencyMs, testDuration);

        executor.shutdown();
    }

    public static void main(String[] args) throws Exception {
        // Pre-run warm up
        System.out.println("Starting concurrency test simulations...");
        
        // Sizing threads. As thread count increases beyond the database execution capabilities,
        // context switching and waiting times increase, hurting performance.
        runTest(4, 40);
        runTest(16, 40);
        runTest(64, 40);
    }
}
```

---

## 8. Interview Questions

### Q1: Why does adding database connections beyond a certain threshold degrade transaction throughput, even if the application servers have CPU capacity?
**Answer**: 
Adding connections beyond a threshold (which is typically governed by: $\text{DB CPU Cores} \times 2$) degrades performance because of **resource contention** at the database kernel level:
1.  **CPU Context-Switching**: If a database server with 8 cores has 200 active query threads, the OS scheduler continuously swaps thread contexts, wasting CPU cycles on context switches instead of executing SQL logic.
2.  **Lock Contention**: More active threads increase concurrent access to shared data structures (page locks, row locks, transaction table latches). Threads block waiting for locks, driving up average wait time.
3.  **Disk I/O Thrashing**: Too many concurrent worker threads performing disk lookups saturate disk queue capacities, causing disk head thrashing and degrading throughput.

### Q2: What is the "Split-Brain" problem in Multi-Master replication databases? How do consensus algorithms prevent it?
**Answer**: 
*   **Split-Brain**: Occurs when a network partition isolates database nodes into two or more groups. If nodes in both isolated sub-networks continue to accept write transactions independently, their data states will drift. When the partition heals, resolving these conflicting writes is extremely difficult, often resulting in data loss.
*   **Prevention via Consensus**: Modern distributed databases enforce consensus algorithms (like Raft or Paxos) to prevent this. To accept write transactions, a partitioned group of nodes must obtain confirmation from a **strict majority (quorum)** of all nodes in the cluster (e.g. 3 out of 5 nodes). The minority partition will refuse writes, preventing data drift.
