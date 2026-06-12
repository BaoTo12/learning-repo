# Course 4: High-Performance Kafka Clients & Delivery Semantics

This course explores the architecture and implementation details of the Java KafkaProducer and KafkaConsumer clients, covering transaction logs, exactly-once delivery, partition strategies, group coordination protocols, and Admin APIs.

## Course Syllabus

*   [Module 01: Producer Architecture & Record Batching](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/04-kafka-clients/01-producer-architecture-internals.md)
    *   Producer internal pipeline: Key/Value serializers, partition routing, record accumulator batching (`linger.ms`, `batch.size`), and network I/O sender thread.
    *   Callback queues vs. blocking Futures.
*   [Module 02: Partition Routing & Custom Partitioners](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/04-kafka-clients/02-custom-partitioners.md)
    *   Default partitioning algorithms (deterministic MurmurHash2 key mapping vs. sticky batch routing).
    *   Writing and configuring custom partitioners in Java for key-based isolation.
*   [Module 03: Consumer Group Coordination & Liveliness](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/04-kafka-clients/03-consumer-group-coordination.md)
    *   Consumer group protocol: Group Coordinator broker, consumer heartbeat threads, rebalances, and state transitions.
    *   Liveliness checks (`max.poll.interval.ms` vs. `session.timeout.ms`).
    *   Static membership (`group.instance.id`) for avoiding transient cloud-environment rebalances.
*   [Module 04: Partition Assignment Protocols](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/04-kafka-clients/04-partition-assignment-strategies.md)
    *   Assignment algorithms: Range, RoundRobin, Sticky.
    *   Eager "stop-the-world" rebalancing vs. Incremental Cooperative Rebalancing (`CooperativeStickyAssignor`).
*   [Module 05: Offset Commit Management & Pipelining](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/04-kafka-clients/05-offset-commit-management.md)
    *   Offsets tracking in `__consumer_offsets` topic.
    *   Automatic commits risk of dataloss vs. manual synchronous/asynchronous commit modes.
    *   Implementing asynchronous processing pipelines with thread-safe offset tracking.
*   [Module 06: Exactly-Once Semantics (EOS)](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/04-kafka-clients/06-exactly-once-semantics.md)
    *   Idempotent producers (Producer IDs, sequence numbers, duplication filtering).
    *   Transactional API: Transaction Coordinator, transaction log, two-phase commits (`initTransactions`, `beginTransaction`, `commitTransaction`, `abortTransaction`).
    *   Consumer read isolation: `read_committed` vs. `read_uncommitted` (High Watermark vs. Last Stable Offset).
*   [Module 07: Programmatic Management & Multi-Event Clients](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/04-kafka-clients/07-admin-api-multi-types.md)
    *   Admin API for cluster inspection and topic creation/deletion.
    *   Implementing producers and consumers for topics with multiple event types (union/oneof patterns).
