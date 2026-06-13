# Course 6: Developing Streams with Kafka Streams DSL

This course covers the essentials of building stream processing applications using the high-level Kafka Streams DSL. We will explore processor topologies (DAGs), application configuration, stateless transformations (mapping, filtering, flatmapping), stream splitting and merging, dynamic message routing, topology node naming, custom Serde implementation, and Schema Registry integration.

## Course Syllabus

*   [Module 01: Streams Architecture & Topology](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/06-developing-streams/01-streams-architecture-topology.md)
    *   Concepts of Directed Acyclic Graphs (DAGs) in stream processing: Source, Processor, and Sink nodes.
    *   Client-side execution vs. broker-side clustering.
    *   The "Yelling" App: A step-by-step walkthrough of topology construction.
    *   Configurations: The role of `application.id` and `bootstrap.servers`.
    *   Application lifecycle: Initializing, starting, and closing `KafkaStreams` instances.
*   [Module 02: Stateless Transformations & Stream Processing](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/06-developing-streams/02-stateless-transformations.md)
    *   Overview of stateless operators: `mapValues`, `map`, `filter`, `filterNot`, `flatMap`, `flatMapValues`, and `selectKey`.
    *   Understanding the side-effects of key modification: Key mutation vs. key preservation, and downstream repartitioning implications.
    *   Production Case Study: ZMart transaction processor with credit-card masking and inventory flat-mapping.
*   [Module 03: Topology Naming, Branching & Dynamic Routing](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/06-developing-streams/03-dynamic-routing-naming.md)
    *   Branching/Splitting pipelines: Using `split()`, `branch()`, and terminal conditions (`defaultBranch`, `noDefaultBranch`).
    *   Merging streams back together with `merge()`.
    *   Topology inspection: Visualizing graph descriptions via `Topology.describe()`.
    *   Naming nodes: Using `Named.as()`, `Consumed.withName()`, and `Produced.withName()` to ensure clean topology descriptions and stable state stores.
    *   Dynamic Routing: Programmatic topic selection using `TopicNameExtractor` and record metadata/headers from `RecordContext`.
*   [Module 04: Serialization & Schema Registry Integration](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/06-developing-streams/04-streams-serde-schema-registry.md)
    *   The Serde lifecycle: Why Kafka Streams encapsulates both serializers and deserializers.
    *   Developing custom Serdes using `Serdes.serdeFrom()`.
    *   Integrating Confluent Schema Registry with client Serdes (`KafkaAvroSerde`, `KafkaProtobufSerde`, `KafkaJsonSchemaSerde`).
    *   Managing schema configuration properties and enforcing schema compatibility checks in stream topologies.
