# Course 7: Stateful Stream Processing & Stream Joins

This course explores stateful operations in the Kafka Streams DSL. We will cover stateful aggregations (`reduce`, `aggregate`, `count`), state store caching, in-memory vs. persistent state stores, repartitioning internals and performance optimizations, stream-stream joins (inner, left-outer, outer), co-partitioning constraints, changelog topic recovery, and standby replicas for fast failover.

## Course Syllabus

*   [Module 01: Stateful Aggregations & Caching](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/07-stateful-processing/01-stateful-aggregations.md)
    *   Stateful vs. stateless processing paradigms.
    *   Aggregation operations: `reduce` (same type reductions) vs. `aggregate` (custom type aggregations with initializers).
    *   Counting metrics: `count` operator usage.
    *   The Kafka Streams memory cache layer: Deduplication, batching, and JMX flushing behaviors.
*   [Module 02: Repartitioning Internals & Optimizations](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/07-stateful-processing/02-repartitioning-internals.md)
    *   Why repartitioning happens: Key mutation triggers and partition alignment.
    *   Downstream performance costs: Network round trips and storage overhead.
    *   Proactive repartitioning via `KStream.repartition()` to resolve redundant topic creations.
    *   Applying topology optimizations (`TOPOLOGY_OPTIMIZATION_CONFIG`) to automatically streamline repartitioning pipelines.
*   [Module 03: Stream-Stream Joins & Co-partitioning](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/07-stateful-processing/03-stream-stream-joins.md)
    *   Join types in Kafka Streams: Inner, Left-Outer, and Full-Outer joins.
    *   Structuring `ValueJoiner` and `ValueJoinerWithKey` callbacks.
    *   Windowing constraints: Configuring before/after ranges in `JoinWindows`.
    *   Internal execution: State store lookups and matching lifecycles.
    *   The Co-partitioning rule: Resolving partition count mismatches between streams.
*   [Module 04: State Store Lifecycle & Durability](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/07-stateful-processing/04-state-store-changelogs.md)
    *   Underlying storage mechanics: RocksDB filesystem layout, `state.dir`, and task directory partitions.
    *   Durability design: How Kafka Streams writes updates to internal changelog topics.
    *   State store recovery: Active task rebuilds from checkpoint files vs. full changelog reconstructions.
    *   Fault tolerance: Configuring standby replicas (`num.standby.replicas`) for near-zero failovers.
    *   Customizing changelog topics: Setting retention policies to `compact,delete`.
