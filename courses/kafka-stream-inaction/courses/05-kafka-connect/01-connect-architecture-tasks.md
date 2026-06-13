# Module 01: Connect Architecture, Workers, and Tasks

To integrate external datastores with Apache Kafka, engineers often face the challenge of writing custom ingestion (producers) and egress (consumers) applications. Doing this repeatedly introduces duplicate boilerplate code, inconsistent error handling, and manual scaling setups. **Kafka Connect** is a centralized, production-ready framework built specifically to standardize and simplify this integration.

---

## 1. What Problem Does Kafka Connect Solve?

Historically, connecting databases, document stores, indexes, and cloud storage to Kafka required writing dedicated applications for each connector. This approach creates several difficulties:
*   **Duplicate Handling**: Write logic for offset checkpointing, backpressure, rate-limiting, and error recovery must be rewritten for every system.
*   **Scale and Fault Tolerance**: Coordinating multiple instances of consumers/producers for partition rebalancing, parallel execution, and node failures requires complex cluster coordination logic.
*   **Operational Burden**: Tracking client health, schemas, and configurations across different deployments is difficult to maintain.

Kafka Connect resolves these problems by providing a standardized runtime (the **Worker Cluster**) and a plugin architecture (**Connectors** and **Tasks**). 
*   **Decoupled & Centralized**: External systems plug into Kafka via ready-to-use plugins.
*   **No Code Deployment**: Deploying an existing connector requires only a JSON configuration sent to a REST API.
*   **Declarative Formats**: Standardized converters allow any connector to write data in Avro, Protobuf, JSON, or plain text without altering the connector's source code.

---

## 2. Standalone vs. Distributed Operations

Kafka Connect can run in two modes: **Standalone** and **Distributed**.

### 2.1 Standalone Mode
*   **Architecture**: Runs as a single JVM process. Connectors and task configurations are specified in local properties files on the local filesystem.
*   **State Management**: Connector states and offsets are saved to local files.
*   **Use Cases**: Excellent for development, local testing, prototyping, or lightweight file-based pipelines (e.g., streaming local log files).
*   **Drawbacks**: Single point of failure. No scale-out, automatic failover, or REST API configurations.

### 2.2 Distributed Mode (Production Standard)
*   **Architecture**: Runs as a cluster of worker nodes. Workers automatically coordinate using a shared group ID.
*   **State Management**: State, offsets, and configurations are stored directly in internal compacted Kafka topics. These topics are:
    *   `connect-configs`: Stores connector configurations (1 partition, compacted).
    *   `connect-offsets`: Stores source connector offsets (highly partitioned, compacted).
    *   `connect-status`: Stores runtime status of connectors and tasks (highly partitioned, compacted).
*   **Scale & Resiliency**: Adding a worker node automatically triggers a rebalance, distributing tasks across the new node. If a worker node crashes, its running tasks are automatically rescheduled onto the surviving worker nodes.

#### Worker Failover and Rebalancing Lifecycle

```
       [ REST Request ] ──► Worker 1 (Leader)
                               │ (Coordinates partition reassignments)
                               ▼
        ┌──────────────────────────────────────────────┐
        │                 KAFKA CLUSTER                │
        │  Stores state in internal topics:            │
        │  - connect-configs                           │
        │  - connect-offsets                           │
        │  - connect-status                            │
        └──────────────────────┬───────────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
    │   Worker 1    │  │   Worker 2    │  │   Worker 3    │
    │  Connector A  │  │  Task A-2     │  │  Task B-1     │
    │  Task A-1     │  │  Connector B  │  │               │
    └───────┬───────┘  └───────────────┘  └───────────────┘
            │
      [ CRASHED ]
            │
            ▼
    ┌─────────────────────────────────────────────────────┐
    │  Rebalance Triggered: Tasks migrated to healthy     │
    │  workers without data loss.                         │
    │                                                     │
    │  Worker 2: Task A-2, Connector B, Task A-1 [NEW]    │
    │  Worker 3: Task B-1, Connector A [NEW]              │
    └─────────────────────────────────────────────────────┘
```

---

## 3. The Connect Internal Topology

Kafka Connect divides responsibility among four core concepts: **Workers**, **Connectors**, **Tasks**, and **Converters**.

```
    ┌──────────────────────────────────────────────────────────────┐
    │                         WORKER (JVM)                         │
    │                                                              │
    │  ┌───────────────────────┐       ┌────────────────────────┐  │
    │  │  Connector Instance   │ ────► │     Task Instances     │  │
    │  │                       │       │                        │  │
    │  │  - Parses configs     │       │  - SourceTask/SinkTask │  │
    │  │  - Partitions workload│       │  - Pulls/Pushes data   │  │
    │  │  - Generates Task     │       │  - Multithreaded       │  │
    │  │    configurations     │       │                        │  │
    │  └───────────────────────┘       └───────────┬────────────┘  │
    └──────────────────────────────────────────────│───────────────┘
                                                   │ (Internal Struct)
                                                   ▼
                                       ┌────────────────────────┐
                                       │       Converter        │
                                       │                        │
                                       │  - Serializes to raw   │
                                       │    bytes for Kafka     │
                                       └───────────┬────────────┘
                                                   │
                                                   ▼
                                             [ Kafka Topic ]
```

### 3.1 Workers
The **Worker** is the runtime JVM process. It hosts the REST API, coordinates partition assignments, loads plugins onto the classpath, and monitors running connectors and tasks.

### 3.2 Connectors
A **Connector** does not perform data movement. It is responsible for defining the configuration schema, checking credentials, interacting with the target system to discover data structures (e.g., tables or partitions), and dividing that workload into configurations for its tasks.

### 3.3 Tasks
A **Task** is the actual execution unit. It runs in its own thread within a worker. 
*   **`SourceTask`**: Queries data from an external datastore, creates `SourceRecord` objects containing schemas and offsets, and publishes them to the Kafka producer.
*   **`SinkTask`**: Consumes `ConsumerRecord` bytes from Kafka topics, converts them, and writes them in batches to the external system.
*   **Max Tasks Configuration**: Defined using `"tasks.max"` in the connector JSON configuration. If a database has 10 tables, and `"tasks.max"` is set to 3, the connector splits the 10 tables across 3 task configurations.

### 3.4 Converters
Connectors operate on an internal data model (`org.apache.kafka.connect.data.Struct` and `org.apache.kafka.connect.data.Schema`). Converters translate this internal structure into serialized bytes to write to Kafka (for sources) or deserialize bytes into the internal structures (for sinks).
*   **Configuring Converters**: You configure key and value converters independently on the worker level or override them per connector:
    ```json
    "key.converter": "org.apache.kafka.connect.storage.StringConverter",
    "value.converter": "org.apache.kafka.connect.json.JsonConverter",
    "value.converter.schemas.enable": "false"
    ```

> [!WARNING]
> Setting `"value.converter.schemas.enable": "true"` with the standard `JsonConverter` embeds the full schema structure into **every single JSON message**. This incurs significant network bandwidth and storage overhead. For production pipelines, use a Schema Registry converter (e.g., `AvroConverter` or `ProtobufConverter`), which registers the schema once and references it via a compact 5-byte header in the record.

---

## 4. Sink Delivery Resilience & Dead Letter Queues (DLQ)

Because sink connectors integrate with external systems, records will occasionally fail to write due to:
1.  **Serialization Issues**: Bad bytes in Kafka that the converter cannot deserialize.
2.  **Transformation Failures**: A Single Message Transform (SMT) trying to access a missing field.
3.  **Target API Writes**: Database constraint violations, format mismatches, or target system rejections.

To handle these gracefully, Kafka Connect provides configurable error-handling behaviors.

### 4.1 Error Tolerance Modes
The **`errors.tolerance`** setting controls how a sink task responds to a record write failure:
*   **`none`** (Default): Any error causes the task to transition to the `FAILED` state immediately. Data processing halts. This ensures **strict data consistency** (no silent drops), but requires manual operator intervention to resolve and restart.
*   **`all`**: Errors are ignored. The bad record is skipped, and the consumer offset is committed. Processing continues. This ensures **high availability**, but risks silent data loss unless coupled with logging and Dead Letter Queues.

### 4.2 Dead Letter Queues (DLQ)
When `errors.tolerance` is set to `all`, you can route skipped records to a specialized Kafka topic, called a **Dead Letter Queue (DLQ)**. This allows operators to isolate and reprocess bad records later.

```json
"errors.tolerance": "all",
"errors.deadletterqueue.topic.name": "orientation_student_dlq",
"errors.deadletterqueue.topic.replication.factor": "3",
"errors.deadletterqueue.context.headers.enable": "true"
```

> [!NOTE]
> Dead Letter Queues are **only applicable to Sink Connectors**. Source connectors cannot write to a DLQ because a failure inside a source task occurs *before* data is formatted or sent to Kafka; the source task is responsible for handling connections to its own external origin and can retry natively.

### 4.3 Appending Diagnostic Context
By enabling `"errors.deadletterqueue.context.headers.enable": "true"`, Kafka Connect appends metadata to the headers of the skipped record in the DLQ. This metadata includes:
*   `__connect.errors.topic`: Origin topic.
*   `__connect.errors.partition`: Origin partition.
*   `__connect.errors.offset`: Origin offset.
*   `__connect.errors.connector.name`: Connector that threw the error.
*   `__connect.errors.task.id`: Task index.
*   `__connect.errors.exception.class.name`: Class name of the exception.
*   `__connect.errors.exception.message`: Precise failure cause (e.g. database connection timeout, JSON parsing error).

#### Production Best Practice
> [!TIP]
> Never route records to a DLQ without active alerting. Run a dedicated consumer on the DLQ topics, or configure Prometheus alerts on the JMX metrics `errant-record-failures` and `errant-record-errors` to notify your team when the rate of rejected records increases.
