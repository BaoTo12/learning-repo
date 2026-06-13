# Module 05: Broker Health & Observability Metrics

Distributed systems must be monitored using key telemetry indicators to preempt failures, bottlenecks, and network issues. Apache Kafka exposes internal state indicators via JMX (Java Management Extensions). This module outlines the most critical production broker health metrics: Request Handler Idle, Network Processor Idle, and Under-Replicated Partitions.

---

## 1. Kafka JMX Instrumentation Overview

Each Kafka broker exposes hundreds of metrics via JMX. In a production cluster, these metrics are typically scraped by collector agents (e.g., Prometheus JMX Exporter or Datadog Agent) and visualized in monitoring dashboards.

### The Request Lifecycle and Thread Pools
Understanding broker health metrics requires understanding the request pipeline:

```
Client Requests
     │
     ▼ (Network Socket)
┌───────────────────────────────────────────────────────────────┐
│                        KAFKA BROKER                           │
│                                                               │
│  ┌───────────────────────┐                                    │
│  │   Network Thread      │ (Accepts connections, reads/writes)│
│  └──────────┬────────────┘                                    │
│             │ Queue Request                                   │
│             ▼                                                 │
│  ┌───────────────────────┐                                    │
│  │    Request Queue      │                                    │
│  └──────────┬────────────┘                                    │
│             │ Pulls Request                                   │
│             ▼                                                 │
│  ┌───────────────────────┐                                    │
│  │ Request Handler Thread│ (Processes: appends log to disk,  │
│  │       (IO Thread)     │  reads segment data, etc.)         │
│  └──────────┬────────────┘                                    │
│             │ Queue Response                                  │
│             ▼                                                 │
│  ┌───────────────────────┐                                    │
│  │    Response Queue     │                                    │
│  └──────────┬────────────┘                                    │
│             │ Pulls Response                                  │
│             ▼                                                 │
│  ┌───────────────────────┐                                    │
│  │   Network Thread      │ (Sends binary packet to client)   │
│  └───────────────────────┘                                    │
└───────────────────────────────────────────────────────────────┘
```

---

## 2. Key Telemetry Metrics

### 2.1 Request Handler Idle Percentage
This metric measures the average fraction of time the I/O request handler threads are idle (not processing incoming requests).

*   **JMX Object Name**:
    ```
    kafka.server:type=KafkaRequestHandlerPool,name=RequestHandlerAvgIdlePercent
    ```
*   **Metric Type**: Gauge (Value between `0.0` and `1.0` representing idle ratio).
*   **Target Threshold**: Under normal operations, this value should stay between **`0.7` and `0.9`** (70% to 90% idle).
*   **Interpretation & Production Alerts**:
    *   If the idle percentage falls below **`0.3` (30%)**, it indicates that the broker is under heavy I/O pressure.
    *   If the value hits **`0` (0% idle)**, the request handler threads are fully saturated. Incoming produce/fetch requests will stack up in the Request Queue, causing client-side latency spikes, socket timeouts, and client retries.
*   **Mitigation Actions**:
    *   Increase the number of request handler threads by tuning `num.io.threads` (default matches number of CPU cores).
    *   Identify slow disks or high disk write latency (e.g., IOPS limits reached on EBS volumes).
    *   Tune disk flush intervals or scale out the cluster to distribute the log write load.

### 2.2 Network Processor Idle Percentage
This metric measures the average idle percentage of the network processor threads that accept network connections and serialize/deserialize request envelopes.

*   **JMX Object Name**:
    ```
    kafka.network:type=RequestMetrics,name=NetworkProcessorAvgIdlePercent
    ```
*   **Metric Type**: Gauge (Value between `0.0` and `1.0`).
*   **Target Threshold**: Ideally should stay above **`0.5`** (50% idle).
*   **Interpretation & Alerts**:
    *   Values consistently below **`0.5`** indicate network handler congestion, often caused by a massive number of concurrent client connections, large batch payloads, or slow client networks.
*   **Mitigation Actions**:
    *   Increase the number of network processor threads by increasing `num.network.threads` in broker configurations.
    *   Tune JVM socket buffers and optimize network layout.

### 2.3 Under-Replicated Partitions
This metric tracks the absolute count of partition replicas assigned to the broker that are currently out of sync with their partition leader.

*   **JMX Object Name**:
    ```
    kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions
    ```
*   **Metric Type**: Gauge (Integer).
*   **Target Threshold**: **`0`** (Must remain zero at all times).
*   **Interpretation & Alerts**:
    *   A value **greater than zero** indicates that one or more follower replicas are lagging behind the leader and have been removed from the ISR list.
    *   This represents degraded data safety; if the partition leader broker crashes while a partition is under-replicated, data loss could occur.
*   **Mitigation Actions**:
    *   Check for broker hardware failures, bad sector disks, or memory limits.
    *   Examine network throughput between brokers (especially across availability zones).
    *   Investigate if a broker is overloaded (GC pauses or CPU starvation hindering follower fetch loops).
