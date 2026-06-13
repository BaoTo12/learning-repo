# MongoDB: The Definitive Guide - Production Systems Engineering (CS-529)

Welcome to **MongoDB: The Definitive Guide - Production Systems Engineering (CS-529)**. This course is a deep, systems-level dive into MongoDB architectures, query patterns, indexing strategies, replication mechanics, and distributed sharding clusters.

The curriculum is structured directly around **Chapters 1 through 20** of the definitive text *MongoDB: The Definitive Guide (3rd Edition)*. Each chapter corresponds to a dedicated, self-contained course module, detailing the academic context, production trade-offs, configuration parameters, and hands-on shell scripts.

---

## 🚀 Getting Started: Local Environment Setup

To run the hands-on challenges and exercises, you need a local MongoDB deployment. We recommend using **Docker Compose** to spin up a single-node replica set for development.

Create a `docker-compose.yml` in your working directory:

```yaml
version: '3.8'
services:
  mongo-node:
    image: mongo:6.0
    container_name: mongo-systems-engineering
    ports:
      - "27017:27017"
    command: ["--replSet", "rs0", "--bind_ip_all"]
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 5s
      timeout: 5s
      retries: 3
```

Start the container and initiate the replica set:

```bash
docker-compose up -d
docker exec -it mongo-systems-engineering mongosh --eval "rs.initiate()"
```

Verify that you can query the database using the MongoDB Shell (`mongosh`):

```bash
docker exec -it mongo-systems-engineering mongosh
```

---

## 📂 Syllabus Navigation Index

The course consists of **20 modules** mapping directly to the first 20 chapters:

### Part I: Introduction
*   **[Module 01: Introduction to MongoDB](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/01-introduction.md)**
    *   *Core concepts*: History of NoSQL, document database design philosophies, scale-out versus scale-up models, and use cases.
*   **[Module 02: Getting Started with MongoDB](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/02-getting-started.md)**
    *   *Core concepts*: BSON serialization, documents, collections, database structure, data types, and executing the `mongosh` shell.
*   **[Module 03: Creating, Updating, and Deleting Documents](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/03-crud-modifications.md)**
    *   *Core concepts*: Atomic CRUD write operations, update modifiers (`$set`, `$inc`, `$push`, `$pull`), array positionals, upserts, and multi-document writes.
*   **[Module 04: Querying](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/04-querying.md)**
    *   *Core concepts*: Find syntax, conditional operators, regex queries, array matching, cursors, pagination, limits, and projections.

### Part II: Designing Your Application
*   **[Module 05: Indexes](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/05-indexes.md)**
    *   *Core concepts*: Single-field, compound, and multikey indexes, execution stats (`explain()`), index intersection, and build options.
*   **[Module 06: Special Index and Collection Types](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/06-special-collections.md)**
    *   *Core concepts*: 2dsphere geospatial indices, Text indices, Capped collections, TTL indices, and GridFS chunk operations.
*   **[Module 07: Introduction to the Aggregation Framework](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/07-aggregation-framework.md)**
    *   *Core concepts*: Aggregation stages (`$project`, `$unwind`, `$group`, `$facet`), accumulator math, expressions, and writing results to collections.
*   **[Module 08: Transactions](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/08-transactions.md)**
    *   *Core concepts*: Multi-document transactions, ACID compliance, session controls, isolation levels, and locking bottlenecks.
*   **[Module 09: Application Design](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/09-application-design.md)**
    *   *Core concepts*: Schema patterns (Bucket, Polymorphic, Schema Versioning), normalization vs. denormalization, cardinality mapping, and migrations.

### Part III: Replication
*   **[Module 10: Setting Up a Replica Set](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/10-replica-set-setup.md)**
    *   *Core concepts*: Cluster replica set initialization, hidden nodes, arbiters, voting priority config, and network topologies.
*   **[Module 11: Components of a Replica Set](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/11-replica-set-components.md)**
    *   *Core concepts*: Initial sync vs. Oplog synchronization, heartbeats, failovers/elections protocols, rollback files, and partition recovery.
*   **[Module 12: Connecting to a Replica Set from Your Application](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/12-connecting-replica-sets.md)**
    *   *Core concepts*: Driver connection strings, connection pooling, write concerns (`w:majority`, `j:true`), and read preference routing.
*   **[Module 13: Replica Set Administration](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/13-replica-set-administration.md)**
    *   *Core concepts*: Forcing reconfigurations, step-down queries, resizing the oplog, index building on secondaries, and replication lag metrics.

### Part IV: Sharding
*   **[Module 14: Introduction to Sharding](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/14-sharding-introduction.md)**
    *   *Core concepts*: Shared-nothing architecture, sharded cluster layout (Config servers, mongos routing, replica set shards), and scale boundaries.
*   **[Module 15: Configuring Sharding](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/15-sharding-configuration.md)**
    *   *Core concepts*: Deploying clusters, starting config/routing servers, adding shards, chunk splitting, the balancer lifecycle, and collations.
*   **[Module 16: Choosing a Shard Key](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/16-shard-key-selection.md)**
    *   *Core concepts*: Shard key evaluation, distribution patterns (ranged vs. hashed), firehose strategy mitigation, and key cardinality rules.
*   **[Module 17: Sharding Administration](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/17-sharding-administration.md)**
    *   *Core concepts*: Running `sh.status()`, tracking router network sockets, balancing chunk sizes, resolving jumbo chunks, and cleanups.

### Part V: Application Administration
*   **[Module 18: Seeing What Your Application Is Doing](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/18-application-diagnostics.md)**
    *   *Core concepts*: Query profiling, inspecting current database operations via `currentOp()`, killing threads (`killOp`), database/collection sizing, and monitoring with `mongostat`/`mongotop`.
*   **[Module 19: An Introduction to MongoDB Security](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/19-security.md)**
    *   *Core concepts*: Role-Based Access Control (RBAC), SCRAM mechanisms, client TLS/SSL handshakes, and generating cluster x.509 member certificates.
*   **[Module 20: Durability](file:///c:/Users/Admin/Desktop/projects/learning-repo/mongodb-definitive-guide/modules/20-durability.md)**
    *   *Core concepts*: WiredTiger journaling mechanics, write/read concerns durability mappings, transaction guarantees, and database corruption checks.

---

## 🎓 Grading & Assessment Criteria

Your final score in this course is based on:
1.  **Socratic Review Assignments (40%)**: Answering the review questions at the end of each module with comprehensive technical explanations.
2.  **Hands-on Challenges (60%)**: Implementing robust, high-performance query schemas, configuration files, and script validations.
