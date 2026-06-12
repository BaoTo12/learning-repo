# Course 8: KTable & GlobalKTable Duality and Joins

This course explores the KTable and GlobalKTable APIs in the Kafka Streams DSL. We will cover the stream-table duality, tombstone delete semantics, KTable aggregations using adders and subtractors, GlobalKTable replication topologies, stream-table joins, table-table joins, foreign-key table joins, and resolving out-of-order join issues using versioned KTables.

## Course Syllabus

*   [Module 01: KTable Semantics, Tombstones, and Aggregations](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/08-ktable-duality/01-ktable-semantics-duality.md)
    *   Stream-Table Duality: `KStream` (insert-only) vs. `KTable` (updates/changelog stream).
    *   Tombstone delete semantics: Processing and propagating null-value records.
    *   KTable aggregations: Why grouping by primary keys is an anti-pattern.
    *   Adder and Subtractor Aggregators: Explaining why KTable rollups require removing old values before adding new values.
*   [Module 02: GlobalKTable Mechanics & Joins](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/08-ktable-duality/02-globalktable-joins.md)
    *   What is a `GlobalKTable`? Partition replication vs. KTable partition sharding.
    *   Operational profiles: Broadcast lookup caching and recovering from source topics.
    *   Stream-GlobalKTable Joins: Resolving co-partitioning constraints.
    *   Extracting lookup keys dynamically using a `KeyValueMapper`.
*   [Module 03: Stream-Table, Table-Table & Foreign-Key Joins](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/08-ktable-duality/03-stream-table-table-table-joins.md)
    *   Stream-Table Joins: Non-reciprocal lookup flows and trigger behaviors.
    *   Table-Table Joins: Primary key alignments and updates from either side.
    *   Foreign-Key Table-Table Joins: Joining tables with distinct primary keys.
    *   Foreign-key internals: Value hashing, repartition topics, composite keys, and prefix scans.
*   [Module 04: Temporal Joins & Versioned KTables](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/08-ktable-duality/04-temporal-joins-versioned-tables.md)
    *   The out-of-order data hazard: How late-arriving events join against future updates.
    *   The solution: Versioned KTables.
    *   Configuring versioned state stores with persistent retention parameters.
    *   Plugging versioned stores into the topology using `Materialized.as(versionedSupplier)`.
