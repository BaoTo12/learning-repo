# Course 5: Data Integration with Kafka Connect

This course explores the architecture and implementation details of Apache Kafka Connect, a framework for building highly scalable, reliable, and fault-tolerant event data pipelines between Kafka and external datastores. We will cover standalone vs. distributed modes, tasks and worker architectures, converters, serialization overhead, sink error handling/dead-letter-queues, building custom connectors with dynamic monitoring threads, and designing custom Single Message Transforms (SMTs).

## Course Syllabus

*   [Module 01: Connect Architecture, Workers, and Tasks](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/05-kafka-connect/01-connect-architecture-tasks.md)
    *   Why Kafka Connect? Eliminating boilerplate ingestion/egress code.
    *   Operational Modes: Standalone vs. Distributed (clustering, failover, task migration).
    *   Internal Topology: Workers, Connectors, Tasks, and Converters.
    *   Serialization Strategies: Schema inference (`schemas.enable=true`) vs. Schema Registry formats (Avro, Protobuf, JSON Schema).
    *   Sink Delivery Resilience: Handling database write errors, error tolerance settings (`all` vs. `none`), and Dead Letter Queues (DLQs).
*   [Module 02: Developing Custom Connectors & Dynamic Task Management](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/05-kafka-connect/02-developing-custom-connector.md)
    *   Building custom source connectors: Extending `SourceConnector`, implementing `ConfigDef`, and partitioning tasks.
    *   Creating dynamic monitoring threads to poll external system metadata and calling `ConnectorContext.requestTaskReconfiguration()`.
    *   Developing `SourceTask`: Designing custom polling loops, implementing throttling, tracking source partitions and offsets, and constructing structured schemas.
*   [Module 03: Single Message Transforms (SMTs) & Custom SMTs](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/05-kafka-connect/03-single-message-transforms.md)
    *   SMT lifecycle: Executing changes between connectors and converters.
    *   Standard SMTs: ValueToKey, ExtractField, and MaskField configurations.
    *   SMT Chaining: Ordering rules, intermediate structures, and when to shift to Kafka Streams.
    *   Writing Custom Transformations: Implementing the `Transformation` interface, handling schemaless vs. schema-embedded records, and implementing inner classes for key/value target isolation.
