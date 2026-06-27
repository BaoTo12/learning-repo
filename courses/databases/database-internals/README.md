# Database Internals

A Deep Dive into How Distributed Data Systems Work

---

## 📖 Course Overview & Preface

Distributed database systems are an integral part of most businesses and the vast majority of software applications. These applications provide logic and a user interface, while database systems take care of data integrity, consistency, and redundancy.

Back in 2000, choosing a database meant selecting from just a few options, mostly relational databases, where the differences between them were relatively small. While their functionality and use cases were similar, some focused on horizontal scaling (scaling out) — improving performance and increasing capacity by running multiple database instances acting as a single logical unit (such as the Gamma Database Machine Project, Teradata, Greenplum, and Parallel DB2). Today, horizontal scaling remains a critical property driven by cloud-based services, where it is often easier to add a new instance to a cluster than to scale vertically (scaling up) by moving to a larger, more powerful machine.

Around 2010, a new class of eventually consistent databases emerged, and terms such as **NoSQL** and **Big Data** grew in popularity. Over the last 15 years, the open-source community, large internet companies, and database vendors have created a vast ecosystem of databases and tools. The Amazon Dynamo paper, published in 2007, significantly impacted the database community, inspiring variants such as Apache Cassandra, Project Voldemort, and Riak. Today, the field is evolving again toward highly scalable and performant databases capable of executing complex queries with stronger consistency guarantees.

---

## 👥 Audience & Motivation

### Who This Is For

This course is designed for software developers, reliability engineers, architects, engineering managers, and curious minds who build software that uses database systems. Understanding database internals helps you troubleshoot, identify, and avoid potential risks and bottlenecks. Having a solid grasp of how these systems work enables you to form hypotheses, validate them, find root causes, and work productively with infrastructure components.

### Why Study These Concepts?

Fundamental concepts, proofs, and algorithms in databases never grow old. New algorithms are often created by finding flaws or room for improvement in classical ones, so knowing the history helps you understand current designs and motivations better. Having a common language and terminology serves as a shortcut, allowing engineers to focus attention on higher-level problems.

---

## 🎯 Scope & Structure

### Course Scope

This curriculum focuses on the algorithms and concepts used in all kinds of database systems, with a concentration on the storage engine and the components responsible for distribution. It concentrates on database internals rather than relational query planning or query languages.

### Course Structure

The curriculum is divided into two core areas:

- **Part I: Storage Engines**: Discusses node-local processes, focusing on the storage engine—the component responsible for storing, retrieving, and managing data in memory and on disk. Topics include B-Trees, page layouts, B-Tree variants, and log-structured storage (LSM trees).
- **Part II: Distributed Systems**: Explores how to organize multiple nodes into a database cluster. Topics include failure detection, leader election, replication, consistency models, eventual consistency (including anti-entropy and gossip protocols), database transactions, and consensus algorithms.

---

## 📦 Part I: Storage Engines & Trade-Offs

### Understanding Storage Engines

The storage engine (or database engine) is the software component of a DBMS responsible for storing, retrieving, and managing data in memory and on disk. It offers a simple data manipulation API (allowing users to create, update, delete, and retrieve records) upon which higher-level subsystems build schemas, query languages, indexing, and transactions.

Using pluggable storage engines has enabled database developers to bootstrap database systems using existing engines (such as BerkeleyDB, LevelDB, RocksDB, LMDB, and Sophia) and concentrate on other subsystems. For example, MySQL supports InnoDB, MyISAM, and MyRocks, while MongoDB supports WiredTiger and In-Memory engines.

### Comparing Databases & Benchmarking

Every database system has distinct strengths and weaknesses. When comparing databases, it is essential to simulate real-world workloads against them, measure key performance metrics, and run long-running tests to detect potential scalability or durability issues. Key variables to evaluate include:

- Schema and record sizes
- Number of concurrent clients
- Types of queries and access patterns
- Rates of read and write queries

To evaluate performance and correctness under concurrent workloads, the industry uses standard benchmarks such as **TPC-C** (an OLTP benchmark simulating warehouse and order management transactions) and frameworks like the **Yahoo! Cloud Serving Benchmark (YCSB)**.

### Designing under Constraints

Designing a storage engine involves navigating numerous trade-offs. For example, saving records in the order of insertion is fast for writes, but retrieving them in lexicographical order requires sorting. Storage engine designs must balance read latency, write latency, density (the amount of stored data per node), and operational simplicity.

---

## 📚 Structured Syllabus & Modules

The curriculum consists of 16 comprehensive, technical modules:

| Module | Topic                                                               | File Link                                                                                        |
| :----- | :------------------------------------------------------------------ | :----------------------------------------------------------------------------------------------- |
| **01** | Chapter 1. Introduction and Overview                                | [01-introduction-and-overview.md](./modules/01-introduction-and-overview.md)                     |
| **02** | Chapter 2. B-Tree Basics                                            | [02-b-tree-basics.md](./modules/02-b-tree-basics.md)                                             |
| **03** | Chapter 3. File Formats                                             | [03-file-formats.md](./modules/03-file-formats.md)                                               |
| **04** | Chapter 4. Implementing B-Trees                                     | [04-implementing-b-trees.md](./modules/04-implementing-b-trees.md)                               |
| **05** | Chapter 5. Transaction Processing and Recovery                      | [05-transaction-processing-and-recovery.md](./modules/05-transaction-processing-and-recovery.md) |
| **06** | Chapter 6. B-Tree Variants                                          | [06-b-tree-variants.md](./modules/06-b-tree-variants.md)                                         |
| **07** | Chapter 7. Log-Structured Storage                                   | [07-log-structured-storage.md](./modules/07-log-structured-storage.md)                           |
| **08** | Part II. Distributed Systems & Chapter 8. Introduction and Overview | [08-distributed-systems-overview.md](./modules/08-distributed-systems-overview.md)               |
| **09** | Chapter 9. Failure Detection                                        | [09-failure-detection.md](./modules/09-failure-detection.md)                                     |
| **10** | Chapter 10. Leader Election                                         | [10-leader-election.md](./modules/10-leader-election.md)                                         |
| **11** | Chapter 11. Replication and Consistency                             | [11-replication-and-consistency.md](./modules/11-replication-and-consistency.md)                 |
| **12** | Chapter 12. Anti-Entropy and Dissemination                          | [12-anti-entropy-and-dissemination.md](./modules/12-anti-entropy-and-dissemination.md)           |
| **13** | Chapter 13. Distributed Transactions                                | [13-distributed-transactions.md](./modules/13-distributed-transactions.md)                       |
| **14** | Chapter 14. Consensus                                               | [14-consensus.md](./modules/14-consensus.md)                                                     |
