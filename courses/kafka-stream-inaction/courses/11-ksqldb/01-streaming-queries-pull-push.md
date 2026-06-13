# Module 01: Streaming Queries: Persistent, Push, & Pull

Traditional relational databases run queries on static data, return a fixed result set, and immediately terminate. In contrast, ksqlDB is a streaming database built on Apache Kafka, designed to process continuous, infinite flows of events in real time. To accommodate different architectural patterns, ksqlDB provides three categories of queries: **Persistent**, **Push**, and **Pull** queries.

This module details the execution models, syntax, and production use cases for each query type.

---

## 1. The Three Query Categories

```
                        +----------------------------+
                        |       Input Topic          |
                        +----------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                               ksqlDB Server                                 |
|                                                                             |
|  +-----------------------------------------------------------------------+  |
|  |                           Persistent Query                            |  |
|  |  CREATE STREAM/TABLE ... AS SELECT ... EMIT CHANGES                   |  |
|  |  (Compiles to a Kafka Streams application running continuously)       |  |
|  +-----------------------------------------------------------------------+  |
|         |                                                        |          |
+---------|--------------------------------------------------------|----------+
          v                                                        v
+-------------------+                                    +--------------------+
|  Changelog / Sink |                                    | RocksDB Local State|
|  Kafka Topic      |                                    +--------------------+
+-------------------+                                              |
          |                                                        v
          v (Continuous)                                           v (Request-Resp)
+-----------------------+                                +--------------------+
|      Push Query       |                                |     Pull Query     |
|   SELECT ... FROM ... |                                | SELECT ... WHERE   |
|   EMIT CHANGES;       |                                | key = 'value';     |
+-----------------------+                                +--------------------+
```

### A. Persistent Queries
* **Definition**: A background query running continuously on the ksqlDB server that processes incoming events and **writes the results back to a new Kafka topic**.
* **Syntax**: Declared using the `CREATE STREAM AS SELECT...` or `CREATE TABLE AS SELECT...` statements.
* **Under the Hood**: Compiles directly into an active, distributed Kafka Streams application running on the ksqlDB JVM process.
* **Sharing**: Since the results are written to a topic, any standard Kafka client or subsequent ksqlDB query can consume the results.
* **Use Case**: Core business logic, data transformation (e.g. converting formats from Avro to Protobuf), and running heavy aggregations.

```sql
-- Creates a persistent table that continuously sums steps and writes to a topic
CREATE TABLE activity_leaders WITH (KEY_FORMAT='JSON') AS
  SELECT
     first_name,
     last_name,
     activity,
     SUM(steps) as total_steps
  FROM user_activity
  GROUP BY first_name, last_name, activity
  EMIT CHANGES;
```

---

### B. Push Queries
* **Definition**: A continuous query that streams results directly to the client that issued the query. **Results are not persisted to a Kafka topic**.
* **Syntax**: Starts with `SELECT ...` and ends with **`EMIT CHANGES`**.
* **Unshared Execution**: If five different clients execute the exact same push query, ksqlDB spins up five independent consumer streams.
* **Termination**: The query runs indefinitely until the client terminates the connection or a `LIMIT` clause is reached.
* **Use Case**: Real-time dashboards, diagnostic CLI polling, and alert notifications.

```sql
-- Subscription push query with a filter
SELECT first_name, last_name, total_steps
FROM activity_leaders
WHERE total_steps > 10000
EMIT CHANGES;
```

#### Pseudo-Columns in Push Queries
ksqlDB attaches system metadata to every record in a stream or table, exposing them as pseudo-columns:
* **`ROWTIME`**: The timestamp of the Kafka record (epoch milliseconds).
* **`ROWPARTITION`**: The partition ID from which the record was consumed.
* **`ROWOFFSET`**: The offset of the record in the partition.

```sql
-- Filtering push query results based on record offset and partition
SELECT * FROM user_activity
WHERE ROWPARTITION = 2 AND ROWOFFSET > 50000
EMIT CHANGES
LIMIT 10; -- Query self-terminates after 10 records
```

---

### C. Pull Queries
* **Definition**: A point-in-time query that retrieves a result from a materialized table's state store and terminates immediately (synchronous request-response).
* **Syntax**: Starts with `SELECT ...` and does **not** contain the `EMIT CHANGES` clause.
* **Storage**: Queries the local off-heap RocksDB state store of the materialized view.
* **Limitations**:
  1. Cannot use `JOIN`, `GROUP BY`, `PARTITION BY`, or `WINDOW` clauses directly in the pull query.
  2. The `WHERE` clause must target the table's primary key (unless table scans are enabled).
* **Use Case**: API lookups (e.g. fetching a user's current reward points for a mobile profile screen).

```sql
-- Point-in-time lookup of a specific key
SELECT total_steps 
FROM activity_leaders 
WHERE KEY = '{"first_name":"Jane","last_name":"Doe","activity":"Running"}';
```

---

## 2. Point-in-Time Table Scans

By default, ksqlDB restricts pull queries to key-based lookups to prevent table scans from impacting processor thread performance. If you query a non-key column, ksqlDB will block the query.

To allow querying by non-key columns, you must enable table scans at the CLI session level or in the server configuration:

```sql
-- Enable table scans for the current CLI session
SET 'ksql.query.pull.table.scan.enabled' = 'true';

-- Now this query is allowed (performs a full scan across RocksDB partitions)
SELECT * FROM activity_leaders
WHERE total_steps > 5000;
```

> [!CAUTION]
> Enabling table scans in high-throughput production environments can lead to CPU starvation and RocksDB read disk stalls. Only use it when state stores are small or during developmental prototyping.

---

## 3. Comparison Summary

| Metric / Feature | Persistent Query | Push Query | Pull Query |
|---|---|---|---|
| **Syntax Clause** | `CREATE ... AS SELECT` | `EMIT CHANGES` | `SELECT ...` (No `EMIT`) |
| **Output Type** | Kafka Topic | Client Socket Stream | Single Response |
| **Running Mode** | Continual background task | Continuous subscription | Instant termination |
| **Storage Engine** | Kafka Broker Logs | JVM Memory Buffer | rocksdb Store |
| **Resource Costs** | CPU & Disk write (Broker) | Client thread overhead | Read-disk IO |
| **Scale Mechanism** | Partitions & Consumer Groups | Client connection scaling | RocksDB partition routing |
| **Where to use** | Aggregations, Transformations | Live alerts, Dashboards | API request-response |
