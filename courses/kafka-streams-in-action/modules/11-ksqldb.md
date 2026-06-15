# Module 11 — ksqlDB

In this module, we will explore ksqlDB, the event streaming database for Apache Kafka. We will learn how ksqlDB allows developers to write stream processing applications using a familiar SQL syntax instead of writing Java code. We will cover the ksqlDB server-client architecture and detail the core abstractions: STREAM and TABLE. We will examine the difference between push queries, pull queries, and persistent queries. We will study streaming SQL operations including filters, windowed aggregations, and joins. Finally, we will cover Schema Registry integration, User-Defined Functions (UDFs/UDAFs/UDTFs), the `INSERT INTO` command, and managing connectors directly from ksqlDB. We will close with Socratic review questions, hands-on labs with complete SQL queries, and detailed explainer tables.

---

## 1. Academic Lecture: Stream Databases, SQL Abstractions & Persistent Queries

### Basic Level: ksqlDB Introduction, Architecture & Stream vs. Table

#### What is ksqlDB?
In previous modules, we built stream processors using Java and the Kafka Streams library. While powerful, this requires writing, packaging, compiling, and deploying Java applications.
**ksqlDB** is a specialized, event-streaming database built on top of Kafka. It provides a SQL interface that allows you to define stream processing pipelines using SQL queries. Behind the scenes, ksqlDB translates your SQL queries into standard Kafka Streams topologies and runs them automatically.

#### ksqlDB Architecture
The ksqlDB ecosystem consists of three main components:
1. **ksqlDB Server**: A distributed cluster of engine instances that run the stream processing tasks. The servers translate SQL queries into running Kafka Streams tasks and manage local state.
2. **ksqlDB REST API**: The interface used by external services to submit SQL queries, inspect status, or retrieve query results.
3. **ksqlDB CLI**: The command-line client used by developers to connect to the server REST API and execute interactive queries.

```text
  [ ksqlDB CLI ] ──► Submit SQL ──► [ ksqlDB REST API ] ──► [ ksqlDB Server ] ──► Runs Kafka Streams
```

#### Core Abstractions: STREAM vs. TABLE
Like the Kafka Streams library, ksqlDB models topics using two primary abstractions:

##### 1. STREAM
* **Definition**: An append-only stream of independent events.
* **Semantic**: Every new message written to the underlying Kafka topic is appended as a new row in the stream. Historical rows are never modified.
* **Analogy**: A ledger of bank transactions. If a customer deposits $50 twice, there are two separate rows.

##### 2. TABLE
* **Definition**: A materialized view representing the current state of keys.
* **Semantic**: Messages are treated as **upserts** (Update or Insert). A record with an existing key overwrites the previous row. A null value deletes the row (tombstone).
* **Analogy**: An account balance table. It only shows the customer's current total balance.

---

### Intermediate Level: Query Types & Schema Registry Integration

#### Query Types in ksqlDB
ksqlDB categorizes queries into three patterns depending on their execution and life cycle:

##### 1. Push Queries (`EMIT CHANGES`)
* **Behavior**: Continuous, streaming queries. When you execute a push query, the connection stays open. The server pushes new rows to your client in real-time as events arrive on the input topics.
* **Syntax**: Ends with `EMIT CHANGES`.
* **Use Case**: Real-time dashboards, alerting systems, live monitoring feeds.

##### 2. Pull Queries
* **Behavior**: Point-in-time lookup queries. When you execute a pull query, the server looks up the current value from the materialized state store of a TABLE, returns the result immediately, and closes the connection. It acts like a query in a traditional database (such as PostgreSQL).
* **Use Case**: Point lookups (e.g., retrieving a user's current profile details or credit score).

##### 3. Persistent Queries
* **Behavior**: Queries that run continuously inside the ksqlDB server. They consume from an input stream/table, process the records, and write the output rows to a new Kafka topic.
* **Syntax**: Defined using `CREATE STREAM AS SELECT` (CSAS) or `CREATE TABLE AS SELECT` (CTAS).
* **Use Case**: Production stream transformations, filters, and aggregations that must run 24/7.

```text
  [ Input Stream ] ──► Persistent Query (CSAS/CTAS) ──► Writes Output ──► [ Output Topic ]
```

#### Schema Registry Integration
By default, ksqlDB can process raw JSON or delimited text. However, for production-grade schema enforcement, it integrates directly with Confluent Schema Registry.
When defining a stream, you specify `VALUE_FORMAT='AVRO'`. ksqlDB will automatically query the Schema Registry, fetch the schema structure, and map the Avro fields to SQL columns, saving you from defining every column type manually:

```sql
CREATE STREAM purchases WITH (
    KAFKA_TOPIC = 'purchases',
    VALUE_FORMAT = 'AVRO'
);
```

---

### Advanced Level: Streaming SQL Operations, UDFs & Connector Management

#### Streaming SQL Operations

##### Windowing in ksqlDB
ksqlDB allows you to aggregate streams over time windows using the `WINDOW` clause. It supports three window geometries:
* **TUMBLING**: Fixed-size, non-overlapping windows.
  ```sql
  WINDOW TUMBLING (SIZE 5 MINUTES)
  ```
* **HOPPING**: Fixed-size, overlapping windows defined by a size and hop.
  ```sql
  WINDOW HOPPING (SIZE 5 MINUTES, ADVANCE BY 1 MINUTE)
  ```
* **SESSION**: Dynamic windows defined by inactivity gaps.
  ```sql
  WINDOW SESSION (30 MINUTES)
  ```

##### Joins
ksqlDB supports SQL join syntax to combine streams and tables:
* **Stream-Stream Joins**: Combines two append-only streams. Requires a `WITHIN` window clause (e.g., join events that occur within 5 minutes of each other).
* **Stream-Table Joins**: Enriches a stream with lookup details from a table (asymmetric join).

#### User-Defined Functions (UDFs, UDAFs, UDTFs)
To extend the SQL language, you can write custom functions in Java, package them as JAR files, and drop them into the ksqlDB server's extension directory:
* **UDF (Scalar Function)**: Accepts one value and returns one value (e.g., `UPPER(name)`).
* **UDAF (Aggregate Function)**: Accepts multiple rows and returns one aggregated value (e.g., `SUM(price)`).
* **UDTF (Tabular Function)**: Accepts one row and splits it into multiple rows (e.g., `EXPLODE(list)`).

#### Managing Connectors directly from SQL
Instead of calling Kafka Connect's REST API using `curl`, ksqlDB allows you to deploy and manage connectors directly using SQL statements:

```sql
CREATE SOURCE CONNECTOR mysql-source WITH (
    'connector.class' = 'io.debezium.connector.mysql.MySqlConnector',
    'database.hostname' = 'localhost',
    ...
);
```

---

## 2. Theory & Production Best Practices

### STREAM vs. TABLE Comparison

| Attribute | STREAM | TABLE |
| :--- | :--- | :--- |
| **Abstaction Type** | Event Log (append-only) | Materialized View (upsert) |
| **Insert Behavior** | Every record adds a new row | Matching key overwrites row |
| **Tombstone (Null) Behavior**| Appended as a row with null values | Deletes the row from state store |
| **Primary Use Case** | Transaction streams, sensor feeds | Account balances, user state. |

### Push Queries vs. Pull Queries

| Query Feature | Push Query (`EMIT CHANGES`) | Pull Query |
| :--- | :--- | :--- |
| **Connection Life** | Kept open (active streaming) | Closes immediately (point-in-time) |
| **Query Target** | Directly on incoming stream/topic | On materialized table state store |
| **Execution Cost** | High (continuous CPU task) | Low (single index scan) |
| **Output Type** | Continuous rows | Single row match |

---

## 3. Common Errors & Troubleshooting

### 1. `SerializationException` or Schema Mismatch
* **Symptom**: ksqlDB queries start but output rows contain null values or show deserialization errors.
* **Root Cause**: The data format in the Kafka topic does not match the `VALUE_FORMAT` specified in the stream definition, or the Schema Registry cannot be reached.
* **Fix**: Verify your Schema Registry connection property `ksql.schema.registry.url` in the server configuration, and make sure your producer writes Avro records.

### 2. ksqlDB Server Out-of-Memory (OOM) / Thread Starvation
* **Symptom**: Push queries crash with timeouts, or the CLI disconnects.
* **Root Cause**: Running too many concurrent push queries (`EMIT CHANGES`) or persistent queries without sizing server memory. Each persistent query compiles to an active thread pool.
* **Fix**: Scale ksqlDB servers horizontally, or limit the number of active push queries. Use pull queries instead of push queries whenever possible for REST interfaces.

### 3. State Desynchronization during Rebalances
* **Symptom**: Pull queries return stale data or empty results temporarily.
* **Root Cause**: When a ksqlDB server instance restarts, partitions are rebalanced. While the server is rebuilding its local RocksDB store from the changelog topic, pull queries for keys on those partitions will miss the latest updates.
* **Fix**: Enable standby replicas in the server configuration:
  ```properties
  ksql.streams.num.standby.replicas=1
  ```

---

## 4. Socratic Review Questions

### Question 1
*When you run a persistent query like `CREATE STREAM high_value_purchases AS SELECT * FROM purchases WHERE price > 50`, what happens on the underlying Kafka brokers?*
* **Answer**: ksqlDB automatically creates a new Kafka topic named `HIGH_VALUE_PURCHASES` on the broker. The server then spins up a persistent stream processing task (a Kafka Streams thread) that reads from the `purchases` topic, applies the filter, and writes matching records to the new topic continuously.

### Question 2
*Why does ksqlDB require a `WITHIN` clause for stream-stream joins, but not for stream-table joins?*
* **Answer**: In a stream-stream join, both sides are infinite event logs. To prevent the server from keeping all history in memory forever, you must define a time boundary (window) to join records. In a stream-table join, the table is a finite materialized view. The stream event simply looks up the current active state in the table, which requires no time window.

### Question 3
*What is the database cost difference between running a Push Query vs. a Pull Query on a ksqlDB server?*
* **Answer**: A push query creates a continuous, active stream processor task. It consumes CPU cycles and network bandwidth indefinitely as long as the client connection stays open. A pull query is a simple, low-cost index scan against the local RocksDB state store. It returns the current state immediately and releases resources, making it highly suitable for high-throughput REST APIs.

### Question 4
*How does setting the `TIMESTAMP` property in a `WITH` clause affect ksqlDB processing?*
* **Answer**: By default, ksqlDB uses the record metadata timestamp (broker ingestion time). Setting `TIMESTAMP='purchaseDate'` tells ksqlDB to extract the time from the `purchaseDate` field inside the record value payload. This converts the query pipeline to use event-time processing, which is critical for window calculations and out-of-order data handling.

### Question 5
*Can a ksqlDB table be queried using a pull query if it was created without a key?*
* **Answer**: No. Pull queries require a primary key lookup (e.g., `WHERE key = 'value'`). If a table is created without a primary key, ksqlDB cannot build a key-based index store, and point-in-time pull queries will be rejected.

---

## 5. Hands-on Labs

### Lab 11.1 — Create a stream over the purchases topic

#### Scenario
We will register a stream named `purchases` over the Kafka topic `"purchases"`. The topic uses Avro serialization, and we will map the record's event time to the `purchaseDate` payload field.

#### SQL Statement
Execute the following query in the ksqlDB CLI:

```sql
CREATE STREAM purchases (
    customerId VARCHAR KEY,
    itemPurchased VARCHAR,
    quantity INT,
    price DOUBLE,
    purchaseDate BIGINT
) WITH (
    KAFKA_TOPIC = 'purchases',
    VALUE_FORMAT = 'AVRO',
    TIMESTAMP = 'purchaseDate'
);
```

#### Explaining Configuration Parameters
The following table explains the parameter properties used in the statement:

| Parameter Name | Value | Purpose |
| :--- | :--- | :--- |
| `customerId VARCHAR KEY` | `KEY` marker | Declares the `customerId` column as the primary message key of the stream. |
| `KAFKA_TOPIC` | `'purchases'` | Tells ksqlDB which underlying Kafka topic to consume from. |
| `VALUE_FORMAT` | `'AVRO'` | Tells ksqlDB to read schema details from Confluent Schema Registry and decode records using Avro. |
| `TIMESTAMP` | `'purchaseDate'` | Overrides metadata timestamps, configuring event-time processing using the `purchaseDate` column. |

---

### Lab 11.2 — Filter high-value purchases (persistent query)

#### Scenario
We will create a persistent filter query that reads from the `purchases` stream, filters for orders where the total cost is greater than $50.00, and writes the results to a new stream and topic named `high_value_purchases`.

#### SQL Statement
Execute the following query in the ksqlDB CLI:

```sql
CREATE STREAM high_value_purchases AS
    SELECT * FROM purchases
    WHERE price * quantity > 50.00
    EMIT CHANGES;
```

#### Step-by-Step SQL Walkthrough
1. **`CREATE STREAM ... AS`**: Instructs the server to compile a persistent query, register a new stream metadata name, and automatically create a backing Kafka topic named `HIGH_VALUE_PURCHASES` on the brokers.
2. **`SELECT * FROM purchases`**: Directs the processing task to consume rows from the input stream.
3. **`WHERE price * quantity > 50.00`**: Applies a mathematical filter on each record. Only matching rows are kept.
4. **`EMIT CHANGES`**: Ensures the query runs continuously, streaming updates to the destination topic.

---

### Lab 11.3 — Count purchases per customer in 5-minute tumbling windows

#### Scenario
We will create a persistent table named `purchase_counts` that counts total transactions and sums the total spending per customer within 5-minute tumbling windows.

#### SQL Statement
Execute the following query in the ksqlDB CLI:

```sql
CREATE TABLE purchase_counts AS
    SELECT customerId,
           COUNT(*) AS purchase_count,
           SUM(price * quantity) AS total_spend
    FROM purchases
    WINDOW TUMBLING (SIZE 5 MINUTES)
    GROUP BY customerId
    EMIT CHANGES;
```

#### Step-by-Step SQL Walkthrough
1. **`CREATE TABLE ... AS`**: Materializes a state store table on the ksqlDB server to track aggregations. Creates a backing compacted changelog topic on the brokers.
2. **`WINDOW TUMBLING (SIZE 5 MINUTES)`**: Buckets the input stream into non-overlapping 5-minute intervals.
3. **`COUNT(*)` and `SUM(...)`**: Calculates aggregate values for each customer key inside the active window.
4. **`GROUP BY customerId`**: Sets the aggregation grouping key.

---

### Lab 11.4 — Push query (continuous stream subscription)

#### Scenario
We will run a push query to monitor the first 10 rows arriving on our `high_value_purchases` stream in real-time.

#### SQL Statement
Execute the following query in the ksqlDB CLI:

```sql
SELECT * FROM high_value_purchases EMIT CHANGES LIMIT 10;
```

*Note: The CLI connection remains open, printing new matching rows as they arrive, and terminates once 10 rows have been received.*

---

### Lab 11.5 — Pull query on the materialized table

#### Scenario
We will run a point-in-time pull query to scan the materialized `purchase_counts` table and retrieve the current total purchase statistics for `'customer-001'`.

#### SQL Statement
Execute the following query in the ksqlDB CLI:

```sql
SELECT * FROM purchase_counts WHERE customerId = 'customer-001';
```

*Note: This query reads directly from the server's local RocksDB memory index and returns the result table immediately, without opening a continuous stream.*
