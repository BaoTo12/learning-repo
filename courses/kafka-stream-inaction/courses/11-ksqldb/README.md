# Course 11: Declarative Stream Processing with ksqlDB

Welcome to **Course 11: Declarative Stream Processing with ksqlDB**. This course covers the declarative event streaming database built on top of Kafka Streams: ksqlDB. You will learn how to write SQL queries to construct continuous stream processing topologies, define materialized views, handle schema integration, and execute complex joins and nested data queries without writing Java code.

## Syllabus & Modules

1. **[Module 01: Streaming Queries: Persistent, Push, & Pull](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/11-ksqldb/01-streaming-queries-pull-push.md)**
   * Master ksqlDB's query hierarchy: Persistent queries, Push queries, and Pull queries.
   * Understand execution modes, topic-backed storage, subscription models, and request-response patterns.
   * Compare latency, state lifecycle, and resource utilization across query types.
2. **[Module 02: Streams, Tables, Joins, & Schema Registry](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/11-ksqldb/02-streams-tables-schema-registry.md)**
   * Create base streams and tables directly against backing Kafka topics.
   * Leverage Schema Registry for automatic schema inference (Avro, Protobuf, JSON Schema) and key-format conversions.
   * Implement stream-stream, stream-table, and table-table (primary and foreign key) joins.
   * Query deeply nested JSON structures using the `STRUCT` data type and dereferencing operators.

## Course Prerequisites
* Completed **Course 3: Schema Registry & Serialization** and **Course 8: KTable Joins**.
* Basic proficiency in SQL (joins, grouping, aggregations).
