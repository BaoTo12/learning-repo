# Course 1: Welcome to the Kafka Event Streaming Platform

Welcome to Course 1 of the Apache Kafka and Kafka Streams curriculum. This course lays the foundational architectural concepts of event streaming, compares stream processing to traditional queuing, reviews the components of the Confluent/Apache Kafka ecosystem, and walks through a real-world enterprise retail case study.

## Course Syllabus

*   [Module 01: Event Streaming vs Message Queuing](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/01-welcome-to-kafka/01-event-streaming-vs-queuing.md)
    *   Deconstructing event streams and the "Event Trinity" (Key, Value, Timestamp).
    *   Structural comparison: ActiveMQ/RabbitMQ vs. Apache Kafka.
    *   Tactical vs. strategic messaging semantics.
    *   When *not* to use event streaming.
*   [Module 02: Kafka Ecosystem Architectural Overview](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/01-welcome-to-kafka/02-kafka-ecosystem-overview.md)
    *   Anatomy of the platform: Brokers, Schema Registry, Clients, Connect, Streams, and ksqlDB.
    *   Decoupling mechanics and client-broker agnosticism.
*   [Module 03: Real-World Case Study: ZMart Retail Pipeline](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/01-welcome-to-kafka/03-real-world-case-study.md)
    *   Analysis of ZMart's online clickstream and point-of-sale (POS) pipeline.
    *   Data security (masking credit cards via SMTs), real-time marketing campaigns, sales trend analytics dashboards, and inventory coordination.

---

## Local Sandbox Environment

To run the hands-on labs throughout this curriculum, we will use a local multi-container Docker Compose sandbox running Kafka in KRaft mode, Schema Registry, Kafka Connect, and ksqlDB.

Create a `docker-compose.yml` file in your workspace directory:

```yaml
version: '3.8'
services:
  broker:
    image: confluentinc/cp-kafka:7.4.0
    hostname: broker
    container_name: broker
    ports:
      - "9092:9092"
      - "9101:9101"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://broker:29092,PLAINTEXT_HOST://localhost:9092'
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REREPLICATION_FACTOR: 1
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_LIVENESS_TARGET_BUSY_PERCENTAGE: 0.90
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@broker:29093'
      KAFKA_LISTENERS: 'PLAINTEXT://0.0.0.0:29092,CONTROLLER://0.0.0.0:29093,PLAINTEXT_HOST://0.0.0.0:9092'
      KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_LOG_DIRS: '/tmp/kraft-combined-logs'
      CLUSTER_ID: 'MkU3OEVBNTcwNTJENDM2Qk'

  schema-registry:
    image: confluentinc/cp-schema-registry:7.4.0
    hostname: schema-registry
    container_name: schema-registry
    depends_on:
      - broker
    ports:
      - "8081:8081"
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: 'broker:29092'
      SCHEMA_REGISTRY_LISTENERS: http://0.0.0.0:8081

  connect:
    image: confluentinc/cp-kafka-connect:7.4.0
    hostname: connect
    container_name: connect
    depends_on:
      - broker
      - schema-registry
    ports:
      - "8083:8083"
    environment:
      CONNECT_BOOTSTRAP_SERVERS: 'broker:29092'
      CONNECT_REST_ADVERTISED_HOST_NAME: connect
      CONNECT_REST_PORT: 8083
      CONNECT_GROUP_ID: compose-connect-group
      CONNECT_CONFIG_STORAGE_TOPIC: docker-connect-configs
      CONNECT_CONFIG_STORAGE_REPLICATION_FACTOR: 1
      CONNECT_OFFSET_STORAGE_TOPIC: docker-connect-offsets
      CONNECT_OFFSET_STORAGE_REPLICATION_FACTOR: 1
      CONNECT_STATUS_STORAGE_TOPIC: docker-connect-status
      CONNECT_STATUS_STORAGE_REPLICATION_FACTOR: 1
      CONNECT_KEY_CONVERTER: org.apache.kafka.connect.storage.StringConverter
      CONNECT_VALUE_CONVERTER: io.confluent.connect.avro.AvroConverter
      CONNECT_VALUE_CONVERTER_SCHEMA_REGISTRY_URL: http://schema-registry:8081
      CONNECT_PLUGIN_PATH: "/usr/share/java,/usr/share/filestream-connectors"

  ksqldb-server:
    image: confluentinc/cp-ksqldb-server:7.4.0
    hostname: ksqldb-server
    container_name: ksqldb-server
    depends_on:
      - broker
      - schema-registry
    ports:
      - "8088:8088"
    environment:
      KSQL_CONFIG_DIR: "/etc/ksqldb"
      KSQL_BOOTSTRAP_SERVERS: "broker:29092"
      KSQL_HOST_NAME: ksqldb-server
      KSQL_LISTENERS: "http://0.0.0.0:8088"
      KSQL_KSQL_SCHEMA_REGISTRY_URL: "http://schema-registry:8081"

  ksqldb-cli:
    image: confluentinc/cp-ksqldb-cli:7.4.0
    container_name: ksqldb-cli
    depends_on:
      - ksqldb-server
    entrypoint: /bin/sh
    tty: true
```

### Starting the Sandbox

Run the following command in the directory containing the file:
```bash
docker compose up -d
```
To verify the services are healthy:
```bash
docker compose ps
```
