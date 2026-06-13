# Course 2: Deep-Dive Kafka Brokers & Clustering

This course explores the architecture and storage engine of the Apache Kafka broker, covering log segments, compaction, tiered storage, consensus protocols (ZooKeeper vs. KRaft), replication, and broker-level observability.

## Course Syllabus

*   [Module 01: Broker Storage Internals](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/02-kafka-brokers/01-broker-storage-internals.md)
    *   Filesystem storage layout, partitions as the storage unit, log directory structures, and segment files (`.log`, `.index`, `.timeindex`).
    *   Memory-mapped files and binary search mechanics for record retrieval.
*   [Module 02: Log Compaction & Retention Policies](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/02-kafka-brokers/02-log-compaction-retention.md)
    *   Log retention settings (time vs. size limits).
    *   Log compaction: cleaner threads, updates by key, tombstone markers.
    *   Tiered Storage (KIP-405) architecture: hot local vs. cold remote storage.
*   [Module 03: Replication & High Availability](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/02-kafka-brokers/03-replication-high-availability.md)
    *   Replication protocol: Leaders, Followers, ISRs (In-Sync Replicas).
    *   Lag tracking (`replica.lag.time.max.ms`), High Watermarks, Log End Offset (LEO).
    *   Acks configuration vs. `min.insync.replicas` data safety policies.
*   [Module 04: Cluster Metadata Management: KRaft vs. ZooKeeper](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/02-kafka-brokers/04-metadata-kraft-zookeeper.md)
    *   Metadata role: cluster membership, topic configurations, controller election, ACLs.
    *   ZooKeeper dependency drawbacks.
    *   KRaft (KIP-500) consensus protocol and active controller metadata log.
*   [Module 05: Health & Observability Metrics](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/02-kafka-brokers/05-health-observability-metrics.md)
    *   JMX instrumentation.
    *   Analyzing Request Handler Idle (`RequestHandlerAvgIdlePercent`), Network Processor Idle, and Under-Replicated Partitions.

---

## Hands-On: Multi-Broker KRaft Cluster Setup

To test replication and failover, create a 3-broker KRaft cluster environment using the following `docker-compose-multi.yml` configuration:

```yaml
version: '3.8'
services:
  broker-1:
    image: confluentinc/cp-kafka:7.4.0
    hostname: broker-1
    container_name: broker-1
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://broker-1:29092,PLAINTEXT_HOST://localhost:9092'
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 2
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 3
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@broker-1:29093,2@broker-2:29093,3@broker-3:29093'
      KAFKA_LISTENERS: 'PLAINTEXT://0.0.0.0:29092,CONTROLLER://0.0.0.0:29093,PLAINTEXT_HOST://0.0.0.0:9092'
      KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_LOG_DIRS: '/tmp/kraft-combined-logs'
      CLUSTER_ID: 'MkU3OEVBNTcwNTJENDM2Qk'

  broker-2:
    image: confluentinc/cp-kafka:7.4.0
    hostname: broker-2
    container_name: broker-2
    ports:
      - "9093:9093"
    environment:
      KAFKA_NODE_ID: 2
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://broker-2:29092,PLAINTEXT_HOST://localhost:9093'
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 2
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 3
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@broker-1:29093,2@broker-2:29093,3@broker-3:29093'
      KAFKA_LISTENERS: 'PLAINTEXT://0.0.0.0:29092,CONTROLLER://0.0.0.0:29093,PLAINTEXT_HOST://0.0.0.0:9093'
      KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_LOG_DIRS: '/tmp/kraft-combined-logs'
      CLUSTER_ID: 'MkU3OEVBNTcwNTJENDM2Qk'

  broker-3:
    image: confluentinc/cp-kafka:7.4.0
    hostname: broker-3
    container_name: broker-3
    ports:
      - "9094:9094"
    environment:
      KAFKA_NODE_ID: 3
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://broker-3:29092,PLAINTEXT_HOST://localhost:9094'
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 2
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 3
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@broker-1:29093,2@broker-2:29093,3@broker-3:29093'
      KAFKA_LISTENERS: 'PLAINTEXT://0.0.0.0:29092,CONTROLLER://0.0.0.0:29093,PLAINTEXT_HOST://0.0.0.0:9094'
      KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_LOG_DIRS: '/tmp/kraft-combined-logs'
      CLUSTER_ID: 'MkU3OEVBNTcwNTJENDM2Qk'
```

Launch the cluster:
```bash
docker compose -f docker-compose-multi.yml up -d
```
Verify all brokers are up:
```bash
docker compose -f docker-compose-multi.yml ps
```
