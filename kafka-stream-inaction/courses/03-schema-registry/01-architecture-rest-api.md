# Module 01: Schema Registry Architecture & REST API

In an enterprise event-driven microservices architecture, data schemas represent the formal interface contract between independent teams. Decoupled applications require a centralized coordinator to store schemas, version data models, and validate compatibility. This module details the architecture of Confluent Schema Registry, primary-secondary replication dynamics, local caching optimizations, and REST API commands.

---

## 1. Decentralized Serialization & Schema Registry Caching

Producers and consumers need schemas to serialize and deserialize messages. However, making an external network HTTP call to a database or registry service for every single message during production loops would cause unacceptable latency.

Schema Registry solves this bottleneck using a **decentralized validation pattern** combined with **local client-side caches**.

```
┌──────────────┐                  HTTP GET /id/1                  ┌─────────────────┐
│   CONSUMER   ├─────────────────────────────────────────────────►│ SCHEMA REGISTRY │
│ (KafkaClient)│◄─────────────────────────────────────────────────┤     SERVERS     │
└──────┬───────┘                 Schema Definition                └────────┬────────┘
       │                                                                   │
       │ Reads Bytes                                                       │ Writes Schema
       ▼                                                                   ▼
┌──────────────┐                                                  ┌─────────────────┐
│ KAFKA BROKER │◄─────────────────────────────────────────────────┤    _schemas     │
│ (Log Segment)│                  Produce / Compact               │  (Compacted)    │
└──────────────┘                                                  └─────────────────┘
```

### 1.1 The Message Binary Layout
When a Schema Registry-aware serializer converts a Java object into bytes, it does not embed the entire schema in the message payload. That would create massive, redundant overhead. Instead, it prepends a **5-byte Magic Byte Header**:

```
┌──────────────┬────────────────────────────┬──────────────────────────────────────┐
│ Magic Byte   │     Schema ID (4 Bytes)    │        Serialized Data Payload       │
│   (1 Byte)   │ (Monotonically Increasing) │           (Avro/Protobuf/JSON)       │
└──────────────┴────────────────────────────┴──────────────────────────────────────┘
```

*   **Magic Byte** (1 Byte): Always set to `0x00` to indicate the Confluent serialization format.
*   **Schema ID** (4 Bytes): The unique identifier assigned to the schema version by Schema Registry.
*   **Data Payload**: The raw serialized object bytes.

### 1.2 Local Cache Mechanics
1.  **First Message Ingestion**: When a producer serializes a record, or a consumer receives a record with a new Schema ID, the client-side serializer/deserializer intercepts the 4-byte Schema ID.
2.  **HTTP Lookup**: The client makes an HTTP GET request to the Schema Registry REST endpoint to fetch the matching schema definition.
3.  **Local Caching**: The client stores the mapping (ID $\leftrightarrow$ Schema Object) in an in-memory local cache.
4.  **Production Hot Path**: For all subsequent messages of the same type, the client looks up the schema from its local cache, reducing the lookup latency to microseconds. The HTTP call occurs only once per schema lifetime per client instance.

---

## 2. Replication and Storage Architecture (`_schemas` Topic)

Schema Registry is designed as a distributed, stateless application that offloads its persistence layer back onto Apache Kafka.

### 2.1 The Compacted `_schemas` Topic
Schema Registry stores all registered schemas and version details in an internal Kafka topic named **`_schemas`** (with double underscores indicating internal status).
*   **Partitioning**: The topic is configured with a **single partition** to guarantee absolute global ordering of schema registration events.
*   **Cleanup Policy**: Configured as `cleanup.policy=compact`. As new schemas are added, only the latest metadata for each subject is retained in the log cleaner tail, preventing the metadata storage from growing indefinitely.
*   **Local Materialized Cache**: Each Schema Registry server runs a consumer thread that reads the `_schemas` partition sequentially, materializing all registered schemas into a local, high-speed memory cache.

### 2.2 Primary-Secondary Replication
In a multi-node Schema Registry cluster, nodes coordinate using a primary-secondary model:
1.  **Primary Election**: Using ZooKeeper or KRaft metadata coordination, one Schema Registry node is elected the **Primary** node. The remaining nodes act as **Secondaries**.
2.  **Read Path**: All Schema Registry nodes (both Primary and Secondaries) can serve HTTP GET requests directly from their local caches, allowing horizontal scalability for read traffic.
3.  **Write Path (Registration)**: Secondary nodes do not write to the `_schemas` topic. If a client sends an HTTP POST request to register a new schema to a Secondary node, the Secondary node proxies the request via forwarding to the Primary node. The Primary node writes the new schema record to the `_schemas` partition, validates compatibility, assigns a unique schema ID, and returns the response.

---

## 3. Operations: Communicating with the REST API

Administrators and build pipelines interact with the Schema Registry using its HTTP/REST interface. Below are the most common commands:

### 3.1 Listing Registered Subjects
Subjects represent the namespace scope of schemas.
```bash
curl -s "http://localhost:8081/subjects" | jq
```
*Response*:
```json
[
  "avro-avengers-value"
]
```

### 3.2 Retrieving Schema Versions
To list all versions registered under a specific subject:
```bash
curl -s "http://localhost:8081/subjects/avro-avengers-value/versions" | jq
```
*Response*:
```json
[
  1,
  2
]
```

### 3.3 Fetching a Specific Schema Version
To fetch a specific version (e.g., version 1):
```bash
curl -s "http://localhost:8081/subjects/avro-avengers-value/versions/1" | jq
```
*Response*:
```json
{
  "subject": "avro-avengers-value",
  "version": 1,
  "id": 1,
  "schema": "{\"type\":\"record\",\"name\":\"Avenger\",\"namespace\":\"bbejeck.chapter_3\",\"fields\":[{\"name\":\"name\",\"type\":\"string\"},{\"name\":\"real_name\",\"type\":\"string\"}]}"
}
```

### 3.4 Fetching the Latest Version
To fetch the latest version of a schema directly:
```bash
curl -s "http://localhost:8081/subjects/avro-avengers-value/versions/latest" | jq
```
