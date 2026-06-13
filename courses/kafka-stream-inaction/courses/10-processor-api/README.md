# Course 10: Low-Level Topologies via the Processor API

Welcome to **Course 10: Low-Level Topologies via the Processor API**. This course covers the low-level processing capabilities of Kafka Streams. While the DSL provides a high-level abstraction for rapid development, the Processor API provides ultimate flexibility and control. 

Through this course, you will learn how to manually build topologies, manage state stores directly, schedule custom punctuated actions, and blend low-level processors into a high-level DSL topology.

## Syllabus & Modules

1. **[Module 01: Processor API Architecture & Topologies](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/10-processor-api/01-processor-api-architecture.md)**
   * Understand the tradeoffs between high-level DSL and the Processor API.
   * Learn how to programmatically define a `Topology` by adding Sources, Processors, and Sinks.
   * Wire parent-child relationships and route records to specific downstream nodes.
2. **[Module 02: Contextual Processors & State Stores](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/10-processor-api/02-context-state-stores.md)**
   * Extend `ContextualProcessor` to access task metadata and processing context.
   * Initialize, wire, and interact with Key-Value and Session state stores inside custom processors.
   * Auto-bind state stores using the `ProcessorSupplier.stores()` lifecycle.
3. **[Module 03: Punctuation & Scheduling](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/10-processor-api/03-punctuation-scheduling.md)**
   * Implement scheduled batch operations using the `Punctuator` callback interface.
   * Dive into the differences between `STREAM_TIME` and `WALL_CLOCK_TIME` punctuations.
   * Handle task execution, synchronization, and processor cancellation.
4. **[Module 04: Mixing DSL and the Processor API](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/10-processor-api/04-mixing-dsl-and-processor-api.md)**
   * Learn how to plug custom processors into a DSL pipeline using `.process()`.
   * Explore the differences between deprecated operators (`transform()`, `transformValues()`) and modern `.process()`.
   * Apply data-driven aggregations using dynamic business logic.

## Course Prerequisites
* Completed **Course 7: Stateful Stream Processing** and **Course 9: Windowing & Timestamps**.
* Familiarity with serializing/deserializing formats in Kafka.
