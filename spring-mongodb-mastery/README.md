# Spring Data MongoDB Masterclass: Production-Grade Architectures

Welcome to the **Spring Data MongoDB Masterclass**. This course is designed for backend engineers, tech leads, and systems architects who want to transition from basic CRUD queries to designing, building, and operating high-scale, resilient, and consistent distributed systems using **Spring Boot** and **Spring Data MongoDB**.

---

## Course Overview

While MongoDB is easy to start with, running it in high-scale production systems requires a deep understanding of document-oriented modeling, indexing mechanics, transactional consistency trade-offs, aggregation pipelines, reactive programming, and operational observability. This course avoids superficial API tutorials and focuses instead on **engineering judgment, performance optimization, and distributed systems patterns**.

### Prerequisites
*   Solid command over Spring Boot, Spring MVC, Spring Security, and Spring Data JPA.
*   Basic understanding of MongoDB CRUD operations, data types (BSON), and MongoDB shell (`mongosh`).
*   Familiarity with transaction management concepts (ACID).
*   Docker and Docker Compose installed locally.

---

## Course Syllabus & Navigation

The course is divided into 16 modules and a comprehensive Final Capstone Project:

| Module | Title | Core Focus Areas |
| :--- | :--- | :--- |
| **01** | [Fundamentals](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/01-spring-data-mongodb-fundamentals.md) | Mapping models, Custom Converters, `MappingMongoConverter`, `_class` logic, and auditing. |
| **02** | [Repository Deep Dive](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/02-repository-deep-dive.md) | Derived queries, `@Query`, projections, QueryDSL, Criteria API, and Custom Repository fragments. |
| **03** | [MongoTemplate Deep Dive](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/03-mongotemplate-deep-dive.md) | Low-level Criteria/Query, bulk updates, atomic positional operators, write concerns, and optimistic locking. |
| **04** | [MongoDB Data Modeling](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/04-mongodb-data-modeling.md) | Embed vs Reference, denormalization, schema versioning, time-series, and aggregate boundaries. |
| **05** | [Indexing & Performance](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/05-indexing-and-query-performance.md) | Compound index ESR rule, multi-key, explain plans, query planner, and cursor-based pagination. |
| **06** | [Aggregation Framework](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/06-aggregation-framework-with-spring.md) | Complex pipelines (`$group`, `$lookup`, `$facet`, `$graphLookup`), analytics, and expression variables. |
| **07** | [Transactions & Consistency](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/07-transactions-and-consistency.md) | Multi-document transactions, replica set requirements, read/write concerns, Outbox and Saga patterns. |
| **08** | [Reactive Spring Data MongoDB](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/08-reactive-spring-data-mongodb.md) | Project Reactor (`Mono`/`Flux`), Netty event loop threads, non-blocking I/O, WebFlux, and backpressure. |
| **09** | [Validation & Schema Control](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/09-validation-and-schema-control.md) | MongoDB JSON Schema validation, zero-downtime blue-green schema migrations, and legacy version mapping. |
| **10** | [Reliability & HA](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/10-reliability-and-high-availability.md) | Replica Set voting/failover mechanics, write durability, journaling, PITR, and client driver retries. |
| **11** | [Sharding & Scalability](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/11-sharding-and-scalability.md) | Shard key selection (hashed vs ranged), zone sharding, chunk migration, and avoiding scatter-gather queries. |
| **12** | [Security](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/12-security.md) | RBAC, TLS/SSL, Client-Side Field-Level Encryption (CSFLE), secrets management, and injection defense. |
| **13** | [Observability & Operations](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/13-observability-and-operations.md) | Spring Actuator, Micrometer driver metrics, connection pool optimization, slow query profiles, and alerting rules. |
| **14** | [Testing Strategies](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/14-testing-strategies.md) | Unit testing with `@DataMongoTest`, integration testing with Testcontainers, and migration regression tests. |
| **15** | [Advanced Production Patterns](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/15-advanced-production-patterns.md) | Multi-tenancy strategies, change streams, CDC (Kafka/Elastic), and Atlas Search/FTS integration. |
| **16** | [Real Production Case Studies](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/16-real-production-architectures.md) | E-commerce Catalog, Social Feed Fan-out, Notifications TTL, Audit Logs, and Race-free Reservation Platform. |
| **17** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/spring-mongodb-mastery/modules/17-final-capstone-project.md) | Building a production-grade catalog and reservation system with Redis caching, Kafka outbox, and Prometheus metrics. |

---

## Local Development Environment

To support multi-document transactions, read preferences, write concerns, and change streams, you **must** run MongoDB in replica set mode. Below is a production-aligned local 3-node MongoDB replica set configuration.

### Docker Compose Configuration (`docker-compose.yml`)

Create this file in your workspace directory to launch the environment:

```yaml
version: '3.8'

services:
  mongo1:
    image: mongo:6.0
    container_name: mongo1
    command: ["mongod", "--replSet", "rs0", "--bind_ip_all", "--port", "27017"]
    ports:
      - "27017:27017"
    volumes:
      - mongo1_data:/data/db
    networks:
      - mongo-network

  mongo2:
    image: mongo:6.0
    container_name: mongo2
    command: ["mongod", "--replSet", "rs0", "--bind_ip_all", "--port", "27018"]
    ports:
      - "27018:27018"
    volumes:
      - mongo2_data:/data/db
    networks:
      - mongo-network

  mongo3:
    image: mongo:6.0
    container_name: mongo3
    command: ["mongod", "--replSet", "rs0", "--bind_ip_all", "--port", "27019"]
    ports:
      - "27019:27019"
    volumes:
      - mongo3_data:/data/db
    networks:
      - mongo-network

  mongo-init:
    image: mongo:6.0
    container_name: mongo-init
    depends_on:
      - mongo1
      - mongo2
      - mongo3
    networks:
      - mongo-network
    entrypoint: [ "bash", "-c", "sleep 5 && mongosh --host mongo1:27017 --eval 'rs.initiate({_id: \"rs0\", members: [{_id: 0, host: \"mongo1:27017\", priority: 2}, {_id: 1, host: \"mongo2:27018\", priority: 1}, {_id: 2, host: \"mongo3:27019\", priority: 1}]})' && mongosh --host mongo1:27017 --eval 'rs.status()'" ]

volumes:
  mongo1_data:
  mongo2_data:
  mongo3_data:

networks:
  mongo-network:
    driver: bridge
```

### Running the Replica Set
1. Run `docker compose up -d` to launch the stack.
2. Confirm the replica set status by executing:
   ```bash
   docker exec -it mongo1 mongosh --eval "rs.status()"
   ```
3. Use the following URI in your Spring Boot application configuration (`application.yml`):
   ```yaml
   spring:
     data:
       mongodb:
         uri: mongodb://localhost:27017,localhost:27018,localhost:27019/mastery_db?replicaSet=rs0
   ```

---

## Grading Criteria & Hands-on Success Metrics

To successfully complete this course, engineers must complete the hands-on exercises and mini-projects at the end of each module. The grading rubrics are as follows:

*   **Production Code Architecture (40%)**: Correct separation between Domain (BSON mappings), Repository, Service, and DTO layers. Clean, non-leaky persistence models.
*   **Performance Optimization (30%)**: Proper index coverage (compound index ordering matching ESR), avoidance of collection scans, efficient bulk operations, and optimized aggregation pipelines.
*   **Consistency & Reliability (20%)**: Correct transaction boundary definitions, proper error recovery handling, custom concurrency controls (`@Version`), and appropriate Read/Write concerns.
*   **Observability & Testability (10%)**: Complete test suites using Testcontainers, integrated metrics hook-ins, Actuator status reports, and structured slow query logs.
