# Course 13: Distributed State Queries with Interactive Queries

Welcome to **Course 13: Distributed State Queries with Interactive Queries**. In stateful stream processing, applications build up dynamic, real-time views of data in local state stores. Instead of exporting this data to external databases just for querying, Kafka Streams allows you to query these state stores directly via **Interactive Queries (IQ)**.

Through this course, you will learn how to turn your stream processing instances into a distributed, queryable database layer, query local states using the modern IQv2 API, and design an RPC routing layer to retrieve keys partitioned across different remote instances.

## Syllabus & Modules

1. **[Module 01: Materializing & Querying Local State](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/13-interactive-queries/01-local-state-querying.md)**
   * Learn the prerequisites to enable Interactive Queries: store naming with `Materialized.as()`.
   * Master the modern IQv2 API and understand its key query structures (`KeyQuery`, `RangeQuery`, `WindowKeyQuery`, `WindowRangeQuery`).
   * Build a Spring Boot REST controller to expose local state store data over HTTP endpoints.
2. **[Module 02: Distributed State Metadata & RPC Routing](file:///c:/Users/Admin/Desktop/projects/learning-repo/kafka-stream-inaction/courses/13-interactive-queries/02-distributed-metadata-rpc.md)**
   * Explore how state is distributed across partitions and application instances.
   * Query cluster metadata with `queryMetadataForKey()` to locate host partitions.
   * Build an RPC request forwarding layer using Spring's `RestTemplate` to query remote sibling instances.
   * Implement failover lookups targeting standby tasks for high availability.

## Course Prerequisites
* Completed **Course 7: Stateful Stream Processing** and **Course 12: Enterprise Integration with Spring Kafka**.
* Knowledge of HTTP protocols and Spring MVC controllers.
