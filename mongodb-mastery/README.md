# MongoDB Mastery: Architecture & Development for Software Engineers

Welcome to the **MongoDB Mastery: Architecture & Development** course. This repository contains a comprehensive, project-based curriculum designed for software engineers. It moves beyond standard "NoSQL CRUD" tutorials to build deep engineering judgment, database architecture expertise, DevOps fundamentals, and production operations skills.

---

## Course Objectives

By the end of this course, you will be able to:
1. **Design MongoDB Schemas** tailored to real application query patterns using embedding, referencing, and advanced modeling patterns.
2. **Write & Optimize Complex Queries** using modern CRUD operators and the Aggregation Framework.
3. **Design Production Indexes** using the ESR (Equality, Sort, Range) rule to avoid collection scans and in-memory sorts.
4. **Configure Transactions & Consistency** levels (Read Concern, Write Concern, Read Preference) safely.
5. **Manage High Availability & Scale** through hands-on understanding of Replication and Sharding.
6. **Implement Real-Time Architectures** using Change Streams and Outbox patterns.
7. **Integrate MongoDB with Spring Boot** using MongoRepository, MongoTemplate, Transactions, and Testcontainers.
8. **Manage Migrations & Schema Evolution** safely in zero-downtime environments.
9. **Observe, Debug, and Tune** slow queries using `explain()` and Atlas profiling tools.

---

## Course Structure & Syllabus

The course is split into 16 logical modules, each designed with problem definitions, trade-offs, exercises, and interview questions.

### 📚 Syllabus Directory

| Module | Name & Topic | File Link |
| :--- | :--- | :--- |
| **01** | MongoDB Foundations | [01-mongodb-foundations.md](./modules/01-mongodb-foundations.md) |
| **02** | CRUD and Querying | [02-crud-and-querying.md](./modules/02-crud-and-querying.md) |
| **03** | Data Modeling | [03-data-modeling.md](./modules/03-data-modeling.md) |
| **04** | Indexing and Query Performance | [04-indexing-and-query-performance.md](./modules/04-indexing-and-query-performance.md) |
| **05** | Aggregation Framework | [05-aggregation-framework.md](./modules/05-aggregation-framework.md) |
| **06** | Transactions and Consistency | [06-transactions-and-consistency.md](./modules/06-transactions-and-consistency.md) |
| **07** | Replication and High Availability | [07-replication-and-high-availability.md](./modules/07-replication-and-high-availability.md) |
| **08** | Sharding and Horizontal Scaling | [08-sharding-and-horizontal-scaling.md](./modules/08-sharding-and-horizontal-scaling.md) |
| **09** | Change Streams and Event-Driven Design | [09-change-streams-and-event-driven-design.md](./modules/09-change-streams-and-event-driven-design.md) |
| **10** | Security and Production Operations | [10-security-and-production-operations.md](./modules/10-security-and-production-operations.md) |
| **11** | Application Integration | [11-application-integration.md](./modules/11-application-integration.md) |
| **12** | Spring Boot with MongoDB | [12-spring-boot-with-mongodb.md](./modules/12-spring-boot-with-mongodb.md) |
| **13** | Testing and Migrations | [13-testing-and-migrations.md](./modules/13-testing-and-migrations.md) |
| **14** | Atlas, Search, and Vector Search | [14-atlas-search-and-vector-search.md](./modules/14-atlas-search-and-vector-search.md) |
| **15** | System Design with MongoDB | [15-system-design-with-mongodb.md](./modules/15-system-design-with-mongodb.md) |
| **16** | Production Project Capstone | [16-production-project-capstone.md](./modules/16-production-project-capstone.md) |

---

## Recommended Learning Path

This course goes from fundamental mechanics to production architecture. For best results:
1. **Complete modules sequentially** as later topics (e.g., Transactions, Sharding, Spring Boot integration) build heavily on foundational indexing and data modeling rules.
2. **Execute the Hands-on Exercises** inside each module. Setting up local instances via Docker is highly recommended.
3. **Build the mini-projects** within each module to test your practical backend engineering skills.
4. **Prepare for interviews** using the curated questions at the end of each module.

---

## 🛠️ Local Environment Deployment Guide

To complete the exercises, mini-projects, and the final capstone, you will need a local multi-node MongoDB Replica Set cluster. Below is the production-grade `docker-compose.yml` specification to deploy a three-node replica set on your local machine.

### 1. Docker Compose Configuration (`docker-compose.yml`)
Save the following configuration block as `docker-compose.yml` in your working directory:
```yaml
version: '3.8'

services:
  mongo-node1:
    image: mongo:6.0.5
    container_name: mongo-node1
    command: mongod --replSet rs0 --bind_ip_all --port 27017
    ports:
      - "27017:27017"
    volumes:
      - mongo-data1:/data/db
    networks:
      - mongo-network

  mongo-node2:
    image: mongo:6.0.5
    container_name: mongo-node2
    command: mongod --replSet rs0 --bind_ip_all --port 27018
    ports:
      - "27018:27018"
    volumes:
      - mongo-data2:/data/db
    networks:
      - mongo-network

  mongo-node3:
    image: mongo:6.0.5
    container_name: mongo-node3
    command: mongod --replSet rs0 --bind_ip_all --port 27019
    ports:
      - "27019:27019"
    volumes:
      - mongo-data3:/data/db
    networks:
      - mongo-network

networks:
  mongo-network:
    driver: bridge

volumes:
  mongo-data1:
  mongo-data2:
  mongo-data3:
```

### 2. Initializing the Replica Set
After starting the containers, run this initialization script to configure consensus voting:
```bash
# Start the containers in background mode
docker-compose up -d

# Initialize replication members using mongosh on Node 1
docker exec -it mongo-node1 mongosh --eval '
  rs.initiate({
    _id: "rs0",
    members: [
      { _id: 0, host: "mongo-node1:27017", priority: 2 },
      { _id: 1, host: "mongo-node2:27018", priority: 1 },
      { _id: 2, host: "mongo-node3:27019", priority: 1 }
    ]
  });
'
```

### 3. Verification Commands
Confirm that the nodes have formed a consensus replica set:
```bash
# View replica status info
docker exec -it mongo-node1 mongosh --eval "rs.status()"
```

---

## 📈 Course Grading Criteria & Project Assessment Rubrics

To achieve mastery status in this course, you must implement all mini-projects and the final capstone telemetry pipeline. Projects are evaluated based on the following engineering criteria:

### 1. Data Schema Design (30% Weight)
*   **Optimal Modeling**: Appropriate use of embedding for bounded entities and referencing/bucketing for unbounded/growing datasets.
*   **BSON Sizing**: Document schemas must stay well below BSON allocation boundaries under scaling.
*   **Validators**: Collections must deploy JSON Schema validation constraints containing required field type controls.

### 2. Query Performance & Indexing (30% Weight)
*   **ESR Adherence**: Indexes must follow the Equality, Sort, Range rule.
*   **Explain Plans**: Aggregations and CRUD tasks must resolve as index scans (`IXSCAN`) and avoid collection scans (`COLLSCAN`).
*   **Write Amplification**: Prevent redundant secondary index structures that slow database writes.

### 3. Reliability and Operations (40% Weight)
*   **Transaction Controls**: Correct read concern (`majority`), write concern (`w: "majority"`), and retries on write conflict alerts.
*   **Observability**: Implementation of proper log auditing, diagnostics shell scripts, and performance dashboards.
*   **Zero-Downtime Upgrades**: Migrations must execute schema adjustments without system downtime.

---

## 📚 Recommended Resources and Reading Materials

For deeper study of MongoDB storage internals and distributed architectures:
*   [MongoDB Manual](https://www.mongodb.com/docs/manual/) - Official Documentation
*   [WiredTiger Storage Engine Architecture Manual](http://source.wiredtiger.com/develop/) - Internals on block manager and leaves
*   [Distributed Systems Patterns](https://martinfowler.com/articles/patterns-of-distributed-systems/) - Background on consensus protocols
*   [Spring Data MongoDB Reference Guide](https://docs.spring.io/spring-data/mongodb/docs/current/reference/html/) - Configuration guidelines

Let's begin! Open [Module 1: MongoDB Foundations](./modules/01-mongodb-foundations.md) to start your journey.
