# Module 05 — Kafka Connect

In this module, we will explore the scalable, fault-tolerant data integration framework of the Apache Kafka ecosystem: **Kafka Connect**. We will examine the core architecture of Connect, contrasting source connectors (pulling data in) with sink connectors (pushing data out). We will study Connect workers in standalone and distributed modes, analyze how tasks are partitioned and reassigned, and write configurations using Connect's REST API. We will implement Single Message Transforms (SMTs) to clean, mask, or route records on the fly, and write our own custom `SourceConnector` and `SourceTask` to parse CSV files. Finally, we will configure monitoring threads for dynamic task updates and construct custom SMT transformers.

---

## 1. Academic Lecture: Kafka Connect Architecture & Operations

### Basic Level: Data Integration Problem Space & Worker Modes

#### The Data Integration Problem Space
When organizations build modern event streaming platforms, they rarely start with a clean slate. Data is already stored in relational databases (Postgres, Oracle), document stores (MongoDB), caching tiers (Redis), and cloud storage buckets (Amazon S3). To make Kafka the central hub, you must continuously stream data *into* Kafka from these systems, and stream processed results *out* to target applications.

Writing custom producer and consumer scripts for every external system is extremely inefficient. Each system requires complex boilerplate code to handle:
*   Connection pooling, backoff retry limits, and credential handshakes.
*   Fault-tolerant failovers (resuming where you left off after crashes).
*   Dynamic scale-out (splitting work across multiple threads or machines).
*   Data schema conversions and serialization formats.

**Kafka Connect** solves this by offering a standardized, declarative framework for building, running, and managing connectors.

##### Analogy: The Logistics Conveyor Belt System
> Imagine a massive logistics warehouse where packages are constantly moving.
> *   **Kafka** is a central high-speed **Conveyor Belt**.
> *   The **Source Connector** is a robotic arm that continuously unloads items from incoming delivery trucks (relational databases) and places them on the conveyor belt.
> *   The **Sink Connector** is another robotic arm at the other end that grabs items off the conveyor belt and loads them into outgoing delivery vans (Elasticsearch or storage buckets).
> *   The **Connect Workers** are the warehouse floors (servers) running the conveyor systems. You do not need to write new code for every truck; you just plug in a preset robot configuration card (JSON file).

#### Source vs. Sink Connectors
*   **Source Connectors**: Act as Kafka producers. They poll data from external resources, translate it into Connect records, and write it to Kafka topics.
*   **Sink Connectors**: Act as Kafka consumers. They subscribe to Kafka topics, fetch records, translate them, and write them to external target databases or APIs.

```text
  ┌──────────────────┐           ┌───────────────┐           ┌──────────────┐
  │  External Source │ ─────────►│SourceConnector│ ─────────►│ Kafka Broker │
  │(e.g., PostgreSQL)│           └───────────────┘           │   (Topic)    │
  └──────────────────┘                                       └──────┬───────┘
                                                                    │
  ┌──────────────────┐           ┌───────────────┐                  │
  │  External Sink   │◄──────────│ SinkConnector │◄─────────────────┘
  │(e.g.Elasticsearch)           └───────────────┘
  └──────────────────┘
```

#### Connect Workers: Standalone vs. Distributed
Connectors run inside JVM processes called **Workers**. Workers can run in two modes:

*   **Standalone Mode**: A single JVM process runs all connectors and tasks. This is easy to run and is ideal for local development, testing, or processing log files on a single machine.
    *   *Limitation*: No fault tolerance or automatic scaling. If the process crashes, data transfer stops.
*   **Distributed Mode**: A cluster of workers cooperates to execute connectors and tasks. The workers coordinate using Kafka topics to store configuration, offsets, and status.
    *   *Fault Tolerance*: If a worker crashes, the surviving workers automatically detect the failure and reassign the orphaned tasks to themselves (rebalancing), ensuring near-continuous execution.
    *   *Scalability*: You can add workers to the cluster, and Connect will automatically distribute the tasks across the new instances.

##### Workers Synchronization via Internal Topics
In Distributed Mode, Kafka Connect does not rely on ZooKeeper or KRaft for synchronization. Instead, workers use three internal topics in the Kafka cluster to coordinate state:
1.  **`connect-configs`**: A single-partition, compacted topic that stores connector configurations. 
2.  **`connect-offsets`**: A partitioned, compacted topic that stores source task read positions (e.g. database sequence offsets or file line numbers).
3.  **`connect-status`**: A partitioned, compacted topic that tracks task states (RUNNING, FAILED, PAUSED) and worker allocation mappings.

---

### Intermediate Level: REST API Configs, Task Mapping & Single Message Transforms

#### Connector Configuration via REST API
In distributed mode, Kafka Connect is entirely headless. You do not write Java code to deploy a connector; instead, you interact with it using a JSON payload sent to the worker's **REST API** (usually listening on port `8083`).

The main endpoints are:
*   `POST /connectors`: Deploy and start a new connector.
*   `GET /connectors`: List all deployed connectors.
*   `GET /connectors/{name}/status`: Inspect the health and task distribution of a connector.
*   `PUT /connectors/{name}/config`: Update a connector's settings.
*   `POST /connectors/{name}/restart`: Trigger a restart of the connector instance.
*   `POST /connectors/{name}/tasks/{id}/restart`: Restart a specific failed task thread.
*   `DELETE /connectors/{name}`: Tear down a connector.

#### Task Partition Mapping
When you deploy a connector, the Connect framework splits the work into **Tasks**. 
*   The **Connector** object does not move data. Its sole responsibility is to evaluate the source system (e.g., list database tables or directory files) and generate configuration maps for tasks.
*   The **Tasks** do the actual work. They execute in parallel on separate threads across the worker cluster.

For example, if you configure a JDBC Source Connector with `tasks.max = 3` to import 6 database tables, the connector will group the tables and assign 2 tables to each of the 3 tasks. The Connect framework distributes these tasks across the active workers.

#### Single Message Transforms (SMTs)
A **Single Message Transform** is a lightweight filter or manipulator that sits in the record path.
*   For a **Source**: The SMT modifies the record *after* it is generated by the connector task but *before* it is serialized and written to Kafka.
*   For a **Sink**: The SMT modifies the record *after* it is deserialized but *before* it is written to the external database.

##### Analogy: The Conveyor Belt Quality Inspectors
> Think of SMTs as physical inspectors standing next to the conveyor belt. 
> *   As a package passes by, the inspector intercepts it, modifies it, and places it back on the belt.
> *   **ValueToKey**: The inspector copies the customer ID printed on the item inside the box and writes it as a barcode label on the outside of the box (making it the partition key).
> *   **MaskField**: The inspector sees a Social Security Number on the document, pulls out a black marker, and writes `xxx-xx-xxxx` over it to protect privacy.
> *   **InsertField**: The inspector stamps the current timestamp on the box to show when it passed through the warehouse.

##### Built-in SMTs Configured in Chains
You can chain multiple SMTs together in the connector JSON configuration. They are executed in the exact order they are listed.

Here are the standard configurations for built-in SMT classes:

###### 1. ValueToKey and ExtractField
Copies `user_id` from value to key, then extracts the raw string so the key is a plain String, not a Struct:
```json
"transforms": "copyFieldToKey,extractKeyFromStruct",
"transforms.copyFieldToKey.type": "org.apache.kafka.connect.transforms.ValueToKey",
"transforms.copyFieldToKey.fields": "user_id",
"transforms.extractKeyFromStruct.type": "org.apache.kafka.connect.transforms.ExtractField$Key",
"transforms.extractKeyFromStruct.field": "user_id"
```

###### 2. ReplaceField
Drops the `ssn` field entirely and renames `user_name` to `username`:
```json
"transforms": "replaceFields",
"transforms.replaceFields.type": "org.apache.kafka.connect.transforms.ReplaceField$Value",
"transforms.replaceFields.blacklist": "ssn",
"transforms.replaceFields.renames": "user_name:username"
```

###### 3. MaskField
Replaces the `ssn` field with the mask string `xxx-xx-xxxx` (Value) or `0` (Numeric):
```json
"transforms": "maskValue",
"transforms.maskValue.type": "org.apache.kafka.connect.transforms.MaskField$Value",
"transforms.maskValue.fields": "ssn",
"transforms.maskValue.replacement": "xxx-xx-xxxx"
```

###### 4. InsertField
Stamps the active worker connector name and the current timestamp to every processed record value:
```json
"transforms": "insertWorkerMetadata",
"transforms.insertWorkerMetadata.type": "org.apache.kafka.connect.transforms.InsertField$Value",
"transforms.insertWorkerMetadata.timestamp.field": "processed_at",
"transforms.insertWorkerMetadata.static.field": "connector_node",
"transforms.insertWorkerMetadata.static.value": "connect-worker-prod-01"
```

---

### Advanced Level: Dynamic Monitoring, Custom SMTs & DLQ Diagnostics

#### Adding a Monitoring Thread to Make a Connector Dynamic
Source environments are rarely static. Relational databases add tables dynamically, stock tickers add symbols, and file directories receive new feeds. To auto-discover these changes without restarting the connector, we run a background monitoring thread.

Here is the complete Java implementation for a background checking loop that tracks symbols from an external API service:

##### Listing 5.1: `StockTickerSourceConnectorMonitorThread.java`
```java
package com.kafkastreams.course.connect;

import org.apache.kafka.connect.connector.ConnectorContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

public class StockTickerSourceConnectorMonitorThread extends Thread {
    private static final Logger LOG = LoggerFactory.getLogger(StockTickerSourceConnectorMonitorThread.class);

    private final ConnectorContext context;
    private final int checkIntervalMs;
    private final HttpClient httpClient;
    private final String serviceUrl;
    private final CountDownLatch shutdownLatch;
    private List<String> currentSymbols;

    public StockTickerSourceConnectorMonitorThread(
            ConnectorContext context,
            int checkIntervalMs,
            HttpClient httpClient,
            String serviceUrl) {
        this.context = context;
        this.checkIntervalMs = checkIntervalMs;
        this.httpClient = httpClient;
        this.serviceUrl = serviceUrl;
        this.shutdownLatch = new CountDownLatch(1);
        this.currentSymbols = new ArrayList<>();
    }

    @Override
    public void run() {
        LOG.info("Starting stock symbols monitor background thread...");
        while (shutdownLatch.getCount() > 0) {
            try {
                if (checkForSymbolUpdates()) {
                    LOG.info("New symbols detected. Requesting task reconfiguration...");
                    context.requestTaskReconfiguration();
                }
            } catch (Exception e) {
                LOG.error("Error checking for symbol updates in monitor loop", e);
            }

            try {
                boolean shutdownRequested = shutdownLatch.await(checkIntervalMs, TimeUnit.MILLISECONDS);
                if (shutdownRequested) {
                    LOG.info("Shutdown requested. Exiting monitor thread.");
                    return;
                }
            } catch (InterruptedException e) {
                LOG.warn("Monitor thread interrupted", e);
                Thread.currentThread().interrupt();
                return;
            }
        }
    }

    public List<String> symbols() {
        synchronized (this) {
            return new ArrayList<>(currentSymbols);
        }
    }

    public void shutdown() {
        LOG.info("Stopping monitor thread...");
        shutdownLatch.countDown();
    }

    private boolean checkForSymbolUpdates() throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(serviceUrl))
                .GET()
                .headers("Accept", "text/plain")
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) {
            LOG.warn("Failed to fetch symbols from API. Status: {}", response.statusCode());
            return false;
        }

        String body = response.body();
        List<String> newSymbols = parseSymbols(body);
        
        synchronized (this) {
            if (!newSymbols.equals(this.currentSymbols)) {
                this.currentSymbols = newSymbols;
                return true;
            }
        }
        return false;
    }

    private List<String> parseSymbols(String csv) {
        if (csv == null || csv.trim().isEmpty()) {
            return Collections.emptyList();
        }
        String[] parts = csv.split(",");
        List<String> list = new ArrayList<>();
        for (String p : parts) {
            list.add(p.trim());
        }
        Collections.sort(list);
        return list;
    }
}
```

#### Building a Custom SMT (Transformation)
If the built-in SMTs are not sufficient, you can write a custom SMT by implementing the `org.apache.kafka.connect.transforms.Transformation` interface.
An SMT must be able to handle two execution paths depending on the serializer/converter setup:

1.  **Schemaless Mode (e.g., JSON without schemas)**:
    *   The record value is represented as a plain Java `Map<String, Object>`.
    *   The SMT directly manipulates the keys and values in the map.
2.  **With Schema Mode (e.g., Avro, Protobuf, or JSON with schemas enabled)**:
    *   The record value is represented as a Connect `Struct` object, and the schema is a Connect `Schema` object.
    *   The SMT cannot modify a `Struct` in place because its structure is bound to its immutable Schema.
    *   The SMT must programmatically construct a **new Schema**, instantiate a **new Struct** conforming to the new schema, copy the kept fields from the old struct to the new struct, and return the new record.

To avoid rebuilding the updated schema for every single record, SMTs use a **Schema Update Cache** (e.g., a LRU cache) to store and reuse generated schemas.

Here is the complete Java implementation for a custom `MultiFieldExtract` transformer:

##### Listing 5.2: `MultiFieldExtract.java`
```java
package com.kafkastreams.course.transformer;

import org.apache.kafka.common.cache.Cache;
import org.apache.kafka.common.cache.LRUCache;
import org.apache.kafka.common.cache.SynchronizedCache;
import org.apache.kafka.common.config.ConfigDef;
import org.apache.kafka.connect.connector.ConnectRecord;
import org.apache.kafka.connect.data.Field;
import org.apache.kafka.connect.data.Schema;
import org.apache.kafka.connect.data.SchemaBuilder;
import org.apache.kafka.connect.data.Struct;
import org.apache.kafka.connect.transforms.Transformation;
import org.apache.kafka.connect.transforms.util.SimpleConfig;
import java.util.*;

public abstract class MultiFieldExtract<R extends ConnectRecord<R>> implements Transformation<R> {
    public static final String FIELDS_CONFIG = "fields";
    private static final ConfigDef CONFIG_DEF = new ConfigDef()
            .define(FIELDS_CONFIG, ConfigDef.Type.LIST, ConfigDef.Importance.HIGH, "Comma-separated list of field names to keep");

    private static final String PURPOSE = "extracting specified fields from record";
    
    private Set<String> fieldsToExtract;
    private Cache<Schema, Schema> schemaUpdateCache;

    @Override
    public void configure(Map<String, ?> configs) {
        SimpleConfig config = new SimpleConfig(CONFIG_DEF, configs);
        this.fieldsToExtract = new HashSet<>(config.getList(FIELDS_CONFIG));
        this.schemaUpdateCache = new SynchronizedCache<>(new LRUCache<>(16));
    }

    @Override
    public R apply(R record) {
        if (operatingValue(record) == null) {
            return record;
        }

        if (operatingSchema(record) == null) {
            return applySchemaless(record);
        } else {
            return applyWithSchema(record);
        }
    }

    private R applySchemaless(R record) {
        Object rawValue = operatingValue(record);
        if (!(rawValue instanceof Map)) {
            return record; // Cannot transform non-map payloads in schemaless
        }
        
        @SuppressWarnings("unchecked")
        Map<String, Object> valueMap = (Map<String, Object>) rawValue;
        Map<String, Object> updatedValueMap = new LinkedHashMap<>();

        for (Map.Entry<String, Object> entry : valueMap.entrySet()) {
            if (fieldsToExtract.contains(entry.getKey())) {
                updatedValueMap.put(entry.getKey(), entry.getValue());
            }
        }

        return newRecord(record, null, updatedValueMap);
    }

    private R applyWithSchema(R record) {
        Object rawValue = operatingValue(record);
        if (!(rawValue instanceof Struct)) {
            return record;
        }

        Struct struct = (Struct) rawValue;
        Schema originalSchema = struct.schema();
        
        Schema updatedSchema = schemaUpdateCache.get(originalSchema);
        if (updatedSchema == null) {
            updatedSchema = makeUpdatedSchema(originalSchema);
            schemaUpdateCache.put(originalSchema, updatedSchema);
        }

        Struct updatedStruct = new Struct(updatedSchema);
        for (Field field : updatedSchema.fields()) {
            updatedStruct.put(field.name(), struct.get(field.name()));
        }

        return newRecord(record, updatedSchema, updatedStruct);
    }

    private Schema makeUpdatedSchema(Schema originalSchema) {
        SchemaBuilder builder = SchemaBuilder.struct().name(originalSchema.name());
        if (originalSchema.isOptional()) {
            builder.optional();
        }
        
        for (Field field : originalSchema.fields()) {
            if (fieldsToExtract.contains(field.name())) {
                builder.field(field.name(), field.schema());
            }
        }
        return builder.build();
    }

    @Override
    public ConfigDef config() {
        return CONFIG_DEF;
    }

    @Override
    public void close() {
        schemaUpdateCache.values().clear();
    }

    protected abstract Schema operatingSchema(R record);
    protected abstract Object operatingValue(R record);
    protected abstract R newRecord(R record, Schema updatedSchema, Object updatedValue);

    // Inner implementation specifically targeting the Record Key
    public static class Key<R extends ConnectRecord<R>> extends MultiFieldExtract<R> {
        @Override
        protected Schema operatingSchema(R record) {
            return record.keySchema();
        }

        @Override
        protected Object operatingValue(R record) {
            return record.key();
        }

        @Override
        protected R newRecord(R record, Schema updatedSchema, Object updatedValue) {
            return record.newRecord(record.topic(), record.kafkaPartition(), updatedSchema, updatedValue, record.valueSchema(), record.value(), record.timestamp());
        }
    }

    // Inner implementation specifically targeting the Record Value
    public static class Value<R extends ConnectRecord<R>> extends MultiFieldExtract<R> {
        @Override
        protected Schema operatingSchema(R record) {
            return record.valueSchema();
        }

        @Override
        protected Object operatingValue(R record) {
            return record.value();
        }

        @Override
        protected R newRecord(R record, Schema updatedSchema, Object updatedValue) {
            return record.newRecord(record.topic(), record.kafkaPartition(), record.keySchema(), record.key(), updatedSchema, updatedValue, record.timestamp());
        }
    }
}
```

#### Dead Letter Queues (DLQ) & Error Tolerance
In production, a sink connector might encounter "poison pill" records—records containing corrupt bytes, missing fields, or invalid formats that cause the deserializer or sink task to crash.

Kafka Connect offers three levels of error handling:
*   **`errors.tolerance = none` (Default)**: The connector task fails immediately and shuts down. Processing stops. (Safe but requires manual intervention).
*   **`errors.tolerance = all`**: The connector logs the conversion error and continues processing subsequent records. (Dangerous if errors are not monitored).
*   **Dead Letter Queue (DLQ)**: By configuring `errors.deadletterqueue.topic.name`, any record that fails to be processed by a sink connector is routed to a dedicated Kafka topic (the DLQ topic).
    *   *Context Headers*: Setting `errors.deadletterqueue.context.headers.enable = true` writes diagnostic headers to the DLQ record, specifying the target connector name, task ID, raw exception stack trace, and original partition info. This allows operational teams to inspect and debug the failures.

---

## 2. Theory vs. Production Trade-offs

### Connect Worker Modes Comparison

| feature | standalone worker | distributed worker cluster |
| :--- | :--- | :--- |
| **Failover / HA** | None. Worker crash kills all connector tasks. | High Availability. Tasks are automatically migrated if a worker fails. |
| **Scalability** | Scale-up only (increase tasks on the single JVM). | Scale-out. Tasks are distributed dynamically across all cluster nodes. |
| **Configuration** | File-based local properties on startup. | Headless REST API (`POST /connectors`) with JSON payloads. |
| **Use Case** | Local development, testing, standalone agents (e.g. log tailing). | Production data pipelines, databases, search clusters. |

### Error Tolerance and DLQ Strategies

| strategy | data integrity | operational overhead | risk of silent data loss | ideal use case |
| :--- | :--- | :--- | :--- | :--- |
| **`tolerance=none`** | Maximum (processing halts on error) | High (requires manual manual restart/clearing) | Zero | Strict transactional pipelines (billing, audits). |
| **`tolerance=all` (No DLQ)** | Low (bad records are skipped and lost) | Low | High | High-throughput, non-critical logging where loss is acceptable. |
| **`tolerance=all` + DLQ** | High (failed records are preserved for retry) | Medium (requires monitoring the DLQ topic) | Zero | Production pipelines where data quality varies (catalogs, streams). |

### SMT Chaining vs. Kafka Streams Processing

| metric | smt chaining | kafka streams application |
| :--- | :--- | :--- |
| **Operational Complexity** | Low (zero code, declarative configurations). | High (requires writing Java code and running distinct microservices). |
| **Throughput / Latency** | Low Latency (transforms are in-memory on the network edge). | Higher Latency (requires an intermediate hop: read, process, write). |
| **Supported Operations** | Stateless only. Operates on a single record in isolation. | Stateful supported. Joins, windowed aggregations, and session merges. |
| **Routing** | Basic topic mutations only. | Complete dynamic stream split routing and branching. |

### Serializers and Schema Formats in Connect

| converter class | schema registry required | bytes payload footprint | schema evolution support |
| :--- | :--- | :--- | :--- |
| **`StringConverter`** | No | Small | None |
| **`JsonConverter` (Schemas on)** | No | Extremely Large (schema repeated in every message) | Backward / Forward |
| **`JsonConverter` (Schemas off)**| No | Medium | None |
| **`AvroConverter`** | Yes | Tiny (5-byte Confluent header + binary payload) | Backward, Forward, Full, Transitive |
| **`ProtobufConverter`** | Yes | Tiny (5-byte Confluent header + compressed binary) | Backward, Forward, Full |

---

## 3. Common Errors & Pitfalls

### Pitfall 1: `ClassNotFoundException` / Plugin Loading Failure
*   **Why it fails**: You configure a connector class (e.g. `JdbcSourceConnector`) in your JSON payload, but the Connect worker logs a `ClassNotFoundException` and rejects the POST request.
*   **Cause**: The connector JAR files and dependencies are not present on the worker's classpaths or the directory path is missing from `plugin.path`.
*   **How to fix**: 
    1.  Ensure all connector JAR files are extracted to a dedicated subdirectory (e.g., `/usr/share/filestream-connectors/`).
    2.  Configure `plugin.path` in the Connect worker properties to point to the parent directory (e.g., `plugin.path=/usr/share/filestream-connectors/`).
    3.  Restart the worker process to load the plugins on boot.

### Pitfall 2: Payload Size Explosion with `JsonConverter` Schemas
*   **Why it fails**: Your Kafka storage costs spike, and consumer performance slows down.
*   **Cause**: You configured the source connector value converter to use `JsonConverter` but left `schemas.enable = true` (the default). This instructs Connect to embed the full field-by-field schema metadata alongside the actual JSON data in *every single message* payload.
*   **How to fix**:
    *   Set `"value.converter.schemas.enable": "false"` in the connector config to write plain JSON bytes.
    *   *Best Practice*: Use `AvroConverter` or `ProtobufConverter` combined with Confluent Schema Registry. This stores schemas centrally, appending only a tiny 5-byte header to each record.

### Pitfall 3: Task Rebalance Storms in Large Clusters
*   **Why it fails**: Adding or updating a connector causes long pauses across all other active connectors in the cluster.
*   **Cause**: In eager Connect rebalancing, updating a single connector configuration forces *all* tasks across the entire cluster to stop executing, rejoin, and undergo reassignment.
*   **How to fix**: Upgrade to Kafka Connect 2.3+ which supports **Incremental Cooperative Rebalancing**. Ensure the configuration `connect.protocol = cooperative` is configured on all workers.

### Pitfall 4: Offset Persistence Race Conditions in Source Tasks
*   **Why it fails**: If a worker node crashes, the source connector restarts and processes duplicate records, violating transactional limits.
*   **Cause**: Source tasks write data to Kafka immediately, but their offsets are only committed to the internal `connect-offsets` topic asynchronously on an interval (`offset.flush.interval.ms` defaults to 1 minute). 
*   **How to fix**: Set the offset flush interval to a shorter time or design downstream consumers to be idempotent.

---

## 4. Socratic Review Questions

### Question 1
Why are converters in Kafka Connect decoupled from the connectors themselves? What design advantage does this provide?

#### Answer
Decoupling converters from connectors allows any connector to write data in any serialization format (e.g., JSON, Avro, Protobuf, or raw string bytes) without changing the connector's source code. For example, a `JdbcSourceConnector` pulls database rows and formats them as standard Connect `Struct` objects. If you configure `value.converter = AvroConverter`, the data is written to Kafka as Avro. If you configure `value.converter = JsonConverter`, the exact same database rows are written to Kafka as JSON. This separation of concerns simplifies connector development.

### Question 2
When writing a custom SMT, why is it necessary to manage two separate methods: `applySchemaless(ConnectRecord)` and `applyWithSchema(ConnectRecord)`?

#### Answer
*   In **schemaless** mode, the record value is a mutable `Map`. SMTs can add, delete, or modify map keys directly.
*   In **with schema** mode, the record value is a typed, immutable `Struct`. You cannot add or delete fields directly because the struct is bound to its strict `Schema`. The SMT must programmatically write a new schema definition (omitting or adding fields), instantiate a new empty `Struct` based on this schema, copy the desired fields from the original struct, and return the new struct inside a new record container.

### Question 3
Under what conditions will a task rebalance be triggered by `ConnectorContext.requestTaskReconfiguration()`? How does it differ from a standard consumer group rebalance?

#### Answer
`requestTaskReconfiguration()` is triggered when a connector's background thread detects a change in the partition structure of the source system (such as adding a table or directory files). 
*   Unlike a consumer group rebalance (which is triggered automatically by the coordinator when client nodes fail or join), a Connect task reconfiguration must be requested explicitly by the connector code.
*   Once requested, the worker coordinator triggers a rebalance of the connector tasks, calling the connector's `taskConfigs()` method to map the new partition structure to active threads.

### Question 4
Explain why configuring `errors.tolerance = all` without specifying a Dead Letter Queue (DLQ) topic is considered a high-risk anti-pattern in production environments.

#### Answer
Setting `errors.tolerance = all` silently catches conversion and routing exceptions and drops the failing records. If a DLQ is not configured, these skipped records disappear completely without leaving trace logs on disk or inside topics. This makes it impossible for developers or audits to recover dropped data or detect parsing failures. In production, always configure `errors.tolerance = all` alongside a valid `errors.deadletterqueue.topic.name` and enable headers so error messages are visible.

---

## 5. Hands-on Labs: Declarative Pipelines & Custom Connectors

### Lab 5.1 — Deploy FileStreamSource Connector via REST API
First, create a mock input file containing raw purchase text strings:
```bash
mkdir -p /tmp
echo "customer-001,Streams Book,1,49.99" > /tmp/purchases.txt
```

Deploy the `FileStreamSourceConnector` using curl. This connector monitors `/tmp/purchases.txt` and writes new lines to the `purchases-raw` topic.

```bash
curl -X POST http://localhost:8083/connectors   -H "Content-Type: application/json"   -d '{
    "name": "file-source",
    "config": {
      "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
      "tasks.max": "1",
      "file": "/tmp/purchases.txt",
      "topic": "purchases-raw",
      "key.converter": "org.apache.kafka.connect.storage.StringConverter",
      "value.converter": "org.apache.kafka.connect.storage.StringConverter"
    }
  }'
```

**Verify the deployment status:**
```bash
curl -s http://localhost:8083/connectors/file-source/status
```

---

### Lab 5.2 — Add an InsertField SMT to Stamp a Timestamp
We want to update the `file-source` connector to automatically append a timestamp field named `processed_at` to the record. We will use the built-in `InsertField$Value` transform.

Submit a `PUT` request to update the connector config:

```bash
curl -X PUT http://localhost:8083/connectors/file-source/config   -H "Content-Type: application/json"   -d '{
    "connector.class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
    "tasks.max": "1",
    "file": "/tmp/purchases.txt",
    "topic": "purchases-raw",
    "key.converter": "org.apache.kafka.connect.storage.StringConverter",
    "value.converter": "org.apache.kafka.connect.json.JsonConverter",
    "value.converter.schemas.enable": "false",
    "transforms": "addTimestamp",
    "transforms.addTimestamp.type": "org.apache.kafka.connect.transforms.InsertField$Value",
    "transforms.addTimestamp.timestamp.field": "processed_at"
  }'
```

---

### Lab 5.3 — Add a FileStreamSink Connector
Deploy a `FileStreamSinkConnector` to subscribe to the `purchases-raw` topic and write the output records to `/tmp/purchases-sink.txt`.

```bash
curl -X POST http://localhost:8083/connectors   -H "Content-Type: application/json"   -d '{
    "name": "file-sink",
    "config": {
      "connector.class": "org.apache.kafka.connect.file.FileStreamSinkConnector",
      "tasks.max": "1",
      "file": "/tmp/purchases-sink.txt",
      "topics": "purchases-raw",
      "key.converter": "org.apache.kafka.connect.storage.StringConverter",
      "value.converter": "org.apache.kafka.connect.storage.StringConverter"
    }
  }'
```

Check that the output file is created and contains the updates:
```bash
cat /tmp/purchases-sink.txt
```

---

### Lab 5.4 — Implement a Custom SourceConnector for CSV Files
Create the directory structure `src/main/java/com/kafkastreams/course/connect/` in your project root.

This custom connector reads columns from a local CSV file, structures them into a Connect `Struct` record with a schema, and publishes them to a Kafka topic.

#### 1. The Connector Class: `CsvSourceConnector.java`
```java
package com.kafkastreams.course.connect;

import org.apache.kafka.common.config.ConfigDef;
import org.apache.kafka.common.config.ConfigDef.Importance;
import org.apache.kafka.common.config.ConfigDef.Type;
import org.apache.kafka.connect.connector.Task;
import org.apache.kafka.connect.source.SourceConnector;
import org.apache.kafka.connect.errors.ConnectException;
import java.util.*;

public class CsvSourceConnector extends SourceConnector {
    public static final String FILE_CONFIG = "file.path";
    public static final String TOPIC_CONFIG = "topic";
    
    private Map<String, String> configProperties;

    private static final ConfigDef CONFIG_DEF = new ConfigDef()
            .define(FILE_CONFIG, Type.STRING, Importance.HIGH, "The target CSV file path to monitor")
            .define(TOPIC_CONFIG, Type.STRING, Importance.HIGH, "The target Kafka topic");

    @Override
    public void start(Map<String, String> props) {
        this.configProperties = props;
        if (props.get(FILE_CONFIG) == null || props.get(FILE_CONFIG).isEmpty()) {
            throw new ConnectException("Missing file path config: " + FILE_CONFIG);
        }
    }

    @Override
    public Class<? extends Task> taskClass() {
        return CsvSourceTask.class;
    }

    @Override
    public List<Map<String, String>> taskConfigs(int maxTasks) {
        // Since we are reading a single CSV file, we configure a single task mapping
        List<Map<String, String>> configs = new ArrayList<>();
        Map<String, String> taskConfig = new HashMap<>(configProperties);
        configs.add(taskConfig);
        return configs;
    }

    @Override
    public void stop() {
        // Resource cleanups
    }

    @Override
    public ConfigDef config() {
        return CONFIG_DEF;
    }

    @Override
    public String version() {
        return "1.0.0";
    }
}
```

#### 2. The Task Class: `CsvSourceTask.java`
```java
package com.kafkastreams.course.connect;

import org.apache.kafka.connect.data.Schema;
import org.apache.kafka.connect.data.SchemaBuilder;
import org.apache.kafka.connect.data.Struct;
import org.apache.kafka.connect.source.SourceRecord;
import org.apache.kafka.connect.source.SourceTask;
import org.apache.kafka.connect.errors.ConnectException;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

public class CsvSourceTask extends SourceTask {
    private String filePath;
    private String topic;
    private long lastReadOffset = 0;

    private static final Schema VALUE_SCHEMA = SchemaBuilder.struct()
            .name("com.kafkastreams.course.PurchaseRecord")
            .field("customerId", Schema.STRING_SCHEMA)
            .field("item", Schema.STRING_SCHEMA)
            .field("quantity", Schema.INT32_SCHEMA)
            .field("price", Schema.FLOAT64_SCHEMA)
            .build();

    @Override
    public String version() {
        return "1.0.0";
    }

    @Override
    public void start(Map<String, String> props) {
        this.filePath = props.get(CsvSourceConnector.FILE_CONFIG);
        this.topic = props.get(CsvSourceConnector.TOPIC_CONFIG);

        // Load saved offsets from Connect framework context (resumes from crash)
        Map<String, Object> partition = Collections.singletonMap("file", filePath);
        if (context != null && context.offsetStorageReader() != null) {
            Map<String, Object> offset = context.offsetStorageReader().offset(partition);
            if (offset != null) {
                lastReadOffset = (Long) offset.get("position");
            }
        }
    }

    @Override
    public List<SourceRecord> poll() throws InterruptedException {
        // Sleep to throttle API/file access
        Thread.sleep(1000);

        if (!Files.exists(Paths.get(filePath))) {
            return null; // Return control to worker thread
        }

        List<SourceRecord> records = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(new FileReader(filePath))) {
            String line;
            long currentLineNum = 0;
            while ((line = reader.readLine()) != null) {
                currentLineNum++;
                // Skip lines we have already read in previous poll loops
                if (currentLineNum <= lastReadOffset) {
                    continue;
                }

                String[] parts = line.split(",");
                if (parts.length < 4) {
                    continue;
                }

                String custId = parts[0].trim();
                String item = parts[1].trim();
                int qty = Integer.parseInt(parts[2].trim());
                double price = Double.parseDouble(parts[3].trim());

                Struct struct = new Struct(VALUE_SCHEMA)
                        .put("customerId", custId)
                        .put("item", item)
                        .put("quantity", qty)
                        .put("price", price);

                Map<String, String> sourcePartition = Collections.singletonMap("file", filePath);
                Map<String, Long> sourceOffset = Collections.singletonMap("position", currentLineNum);

                records.add(new SourceRecord(
                        sourcePartition,
                        sourceOffset,
                        topic,
                        null,
                        Schema.STRING_SCHEMA,
                        custId,
                        VALUE_SCHEMA,
                        struct
                ));
                
                lastReadOffset = currentLineNum;
            }
        } catch (IOException e) {
            throw new ConnectException("Error reading CSV file path: " + filePath, e);
        }

        return records.isEmpty() ? null : records;
    }

    @Override
    public void stop() {
        // Close file handles or open resources
    }
}
```

---

## 6. Detailed Breakdown of Configurations

Here is what each configuration key inside the Connect JSON setup actually does:

### REST API Connector Configuration Parameters

| Property Key | Example Value | Description |
| :--- | :--- | :--- |
| `name` | `"file-source"` | A unique identifying name configured for the connector instance in the Connect cluster. |
| `connector.class` | `FileStreamSourceConnector` | The full classpath of the connector class implementing the Source/Sink pattern. |
| `tasks.max` | `"1"` | The maximum number of parallel task instances that can be created to process records. |
| `file` | `"/tmp/purchases.txt"` | The absolute file path on the local filesystem that the FileStream connector tails. |
| `topic` | `"purchases-raw"` | The Kafka topic name where the source connector writes the records. |
| `topics` | `"purchases-raw"` | A comma-separated list of topics that a sink connector subscribes to (used by sinks instead of `topic`). |
| `key.converter` | `StringConverter.class` | The class used to serialize/deserialize record keys. |
| `value.converter` | `JsonConverter.class` | The class used to serialize/deserialize record values. |
| `value.converter.schemas.enable` | `"false"` | When false, disables wrapping JSON payloads with inline schema metadata, keeping message sizes small. |
| `transforms` | `"addTimestamp"` | A list of names defining the transformations to be applied in sequence to the records. |
| `transforms.addTimestamp.type` | `InsertField$Value` | Specifies the class path of the SMT (e.g. inserting field values to the payload). |
| `transforms.addTimestamp.timestamp.field`| `"processed_at"` | The name of the new field where the SMT writes the current system timestamp. |
| `errors.tolerance` | `"all"` | Controls task tolerance to corrupt records. Setting it to `"all"` keeps the task running despite processing errors. |
| `errors.deadletterqueue.topic.name` | `"orientation_student_dlq"` | The name of the Kafka topic where corrupt or un-parseable records are written for analysis. |
| `errors.deadletterqueue.context.headers.enable`| `"true"` | Enables writing details about why the processing failed (exceptions, trace) directly in the DLQ record headers. |

---

## 7. Verification Command
To compile and package the custom connector inside your project:

```bash
mvn clean compile
```
