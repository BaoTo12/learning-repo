# Module 02: Streams, Tables, Joins, & Schema Registry

Building real-world topologies in ksqlDB requires a deep understanding of data structures, schema serialization formats, stateful joins, and querying nested payload formats.

This module details how to declare streams and tables, integrate Confluent Schema Registry, execute streaming joins, resolve multi-column grouping challenges, and model nested JSON data.

---

## 1. Streams vs. Tables in ksqlDB

The definitions of streams and tables in ksqlDB mirror the concepts in Kafka Streams:

* **STREAM**: Represents a logical event-log. Records are appended chronologically and are independent. Keys are optional. Null values are treated as standard event payloads.
* **TABLE**: Represents a materialized view (update-log). A table requires a primary key (`PRIMARY KEY`). Records with the same key are treated as upserts. Null values represent **tombstones**, marking the key for deletion.

```sql
-- Create a base Stream against a JSON topic
CREATE STREAM user_activity (
    first_name VARCHAR,
    last_name VARCHAR,
    activity VARCHAR,
    steps INT
) WITH (
    kafka_topic='user-activity',
    value_format='JSON'
);
```

---

## 2. Schema Registry Integration

When using formats supported by Confluent Schema Registry (`AVRO`, `PROTOBUF`, `JSON_SR`), ksqlDB can automatically infer the fields and data types, removing the need to define columns manually.

```sql
-- Registering a table where key and value both use Protobuf
CREATE TABLE user_activity_table
WITH (
    kafka_topic='user_activity_proto',
    key_format='PROTOBUF',
    value_format='PROTOBUF'
);
```

### Partial Schema Reference
If the topic key is a simple scalar format (`String`, `Integer` via `KAFKA` format) but the value is in a schema registry format, you define only the key:

```sql
-- Primary key defined, value columns inferred from Avro
CREATE TABLE members (
    member_id VARCHAR PRIMARY KEY
) WITH (
    kafka_topic='rewards-members',
    key_format='KAFKA',
    value_format='AVRO'
);
```

### Changing Serialization Formats on the Fly
You can use a persistent query to change a topic's serialization format with a single line of SQL:

```sql
-- Convert an Avro stream to Protobuf format
CREATE STREAM iot_temp_protobuf WITH (value_format='PROTOBUF') AS
  SELECT * FROM iot_temp_avro;
```

---

## 3. Resolving Composite Key Aggregations

If you aggregate data grouping by multiple columns (e.g. `GROUP BY first_name, last_name, activity`), ksqlDB must generate a composite key. 

If your key format is set to `KAFKA`, the query will fail with:
* *"The 'KAFKA' format only supports a single field."*

### Solution: Schema-Backed Key Formats & `AS_VALUE()`
To resolve this, set the `KEY_FORMAT` in the `WITH` clause to a serialization format that supports composite structures (like `JSON` or `AVRO`), and use the **`AS_VALUE()`** function to ensure the key components are copied to the value portion so they are accessible by downstream clients:

```sql
CREATE TABLE activity_leaders WITH (KEY_FORMAT='JSON') AS
  SELECT
     first_name as first_name_key,
     last_name as last_name_key,
     activity as activity_key,
     AS_VALUE(first_name) as first_name,
     AS_VALUE(last_name) as last_name,
     AS_VALUE(activity) as activity,
     SUM(steps) as total_steps
  FROM user_activity
  GROUP BY first_name, last_name, activity
  EMIT CHANGES;
```

---

## 4. Streaming Joins in ksqlDB

### A. Stream-Stream Join (Tuned with Window & Grace)
Stream-stream joins require that both streams are co-partitioned. They are windowed joins and must specify the join window size and grace period:

```sql
CREATE STREAM customer_rewards AS
  SELECT 
      c.custId as customerId,
      s.total as amount,
      c.drink as drink
  FROM coffee_purchase c
  INNER JOIN store_purchase s
  WITHIN 30 MINUTES GRACE PERIOD 2 MINUTES
  ON c.custId = s.custId
  EMIT CHANGES;
```

### B. Stream-Table Join (Enrichment Lookup)
A stream-table join behaves as a lookup: every incoming stream record queries the table for enrichment. It requires that the table is keyed on the join key.

```sql
CREATE STREAM enriched_rewards AS
  SELECT 
      crs.customerId as customer_id,
      rm.first_name + ' ' + rm.last_name as name,
      crs.amount as total_purchase
  FROM customer_rewards crs
  LEFT OUTER JOIN members rm ON crs.customerId = rm.member_id
  EMIT CHANGES;
```

### C. Table-Table Foreign Key Join
Table-table joins support joining on a non-primary key value column on one side (Foreign Key Join), removing the strict co-partitioning requirements:

```sql
-- Join activity_count (primary key: last_name) and members (primary key: member_id)
-- Join is evaluated on members.last_name value column as a foreign key
CREATE TABLE members_fitness_count AS
  SELECT * 
  FROM activity_count ac 
  JOIN members rm ON ac.last_name = rm.last_name
  EMIT CHANGES;
```

---

## 5. Querying Nested Data (`STRUCT`, Maps, & Arrays)

Real-world JSON or Protobuf payloads often have nested properties. In ksqlDB, you model these structures using the `STRUCT` type and query them using the dereferencing arrow operator (`->`).

### Defining Nested Stream Schema

```sql
CREATE STREAM school_events (
    event_id INT,
    event STRUCT<
        type VARCHAR,
        date VARCHAR,
        student STRUCT<
            first_name VARCHAR,
            last_name VARCHAR,
            email VARCHAR
        >,
        class STRUCT<
            name VARCHAR,
            professor STRUCT<
                first_name VARCHAR,
                last_name VARCHAR,
                other_classes ARRAY<VARCHAR>
            >
        >
    >
) WITH (
    kafka_topic='school-events',
    value_format='JSON'
);
```

### Dereferencing Nested Elements

To query properties inside the hierarchy, use the arrow dereference syntax `->`. To access specific indices in arrays, use brackets (note: ksqlDB array indexing is **1-based**):

```sql
-- Extract nested student information and the first course from the professor's list
SELECT
    event->student->email as student_email,
    event->class->professor->other_classes[1] as suggested_course
FROM school_events
EMIT CHANGES;
```
