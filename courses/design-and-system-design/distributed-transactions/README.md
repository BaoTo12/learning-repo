# CS-509: Java Distributed Systems & Transaction Management

Welcome to **CS-509: Java Distributed Systems & Transaction Management**. I am Professor Antigravity. In this course, we will bridge the gap between classical computer science theory and modern cloud-native software engineering.

In single-node environments, managing data consistency is straightforward. The CPU, memory, and database are locally co-located on a single physical host, allowing us to rely on local ACID transactions. However, as applications scale horizontally, we must coordinate state changes across separate physical systems separated by unreliable networks. Managing transactions and data consistency in distributed systems introduces complex challenges: network partitions, clock drift, node failures, and consensus coordination.

This course is designed to teach you **engineering judgment, distributed systems theory, and Java 21 implementation patterns** to design, build, and operate resilient distributed architectures.

---

## Course Syllabus & Navigation

The course is divided into 11 modules and a final capstone project:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [Java Transaction Fundamentals](file:///c:/Users/Admin/Desktop/projects/learning-repo/distributed-transactions/modules/01-java-transaction-fundamentals.md) | JDBC/JPA ACID operations, `@Transactional` boundaries, transaction propagation and isolation levels. |
| **02** | [Two-Phase Commit & XA](file:///c:/Users/Admin/Desktop/projects/learning-repo/distributed-transactions/modules/02-two-phase-commit-and-xa.md) | Two-Phase Commit (2PC) protocol mechanics, JTA XA transactions, coordinators (Narayana/Atomikos), and 3PC. |
| **03** | [Consensus & Coordination](file:///c:/Users/Admin/Desktop/projects/learning-repo/distributed-transactions/modules/03-distributed-consensus-raft-paxos.md) | Distributed consensus models, Paxos, Raft, and leader election using Apache ZooKeeper & Curator. |
| **04** | [CAP & PACELC Theorems](file:///c:/Users/Admin/Desktop/projects/learning-repo/distributed-transactions/modules/04-cap-pacelc-consistency-models.md) | CAP & PACELC tradeoffs, CP vs. AP classifications, and read/write consistency levels. |
| **05** | [Eventual Consistency & CRDTs](file:///c:/Users/Admin/Desktop/projects/learning-repo/distributed-transactions/modules/05-eventual-consistency-crdts-vectors.md) | Conflict-Free Replicated Data Types (CRDTs), Vector Clocks, and Version Vectors. |
| **06** | [Saga Pattern](file:///c:/Users/Admin/Desktop/projects/learning-repo/distributed-transactions/modules/06-saga-orchestration-choreography.md) | Distributed transactions without lock contention, Sagas (Orchestrated vs. Choreographed), and compensations. |
| **07** | [Distributed Locking](file:///c:/Users/Admin/Desktop/projects/learning-repo/distributed-transactions/modules/07-distributed-locking-redlock-zookeeper.md) | Distributed locks, Redlock algorithm (Redisson), ZooKeeper `InterProcessMutex`, and fencing tokens. |
| **08** | [Clock Synchronization & Order](file:///c:/Users/Admin/Desktop/projects/learning-repo/distributed-transactions/modules/08-clocks-ordering-logical-timestamps.md) | Physical clock drift, NTP, logical clocks (Lamport timestamps, Vector clocks), and Spanner's TrueTime. |
| **09** | [Exactly-Once Messaging](file:///c:/Users/Admin/Desktop/projects/learning-repo/distributed-transactions/modules/09-asynchronous-messaging-exactly-once.md) | Message delivery semantics, Exactly-Once Semantics (EOS) in Kafka, outbox/inbox deduplication. |
| **10** | [Resilience & Fault Tolerance](file:///c:/Users/Admin/Desktop/projects/learning-repo/distributed-transactions/modules/10-fault-tolerance-resilience.md) | Throttling and fault containment: Rate Limiter, Circuit Breaker, Retry, and Bulkhead using Resilience4j. |
| **11** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/distributed-transactions/modules/11-final-capstone-distributed-ledger.md) | Building a production-grade *Distributed Financial Ledger* with outbox event publishers and Redlock synchronization. |

---

## Local Development Infrastructure

To complete the coding exercises and challenges, you must run the local distributed infrastructure stack. Below is the multi-container configuration containing PostgreSQL, Redis, ZooKeeper, and Kafka.

### Docker Compose Configuration (`docker-compose.yml`)

Create this file in your root workspace:

```yaml
version: '3.8'

services:
  # ZooKeeper (Kafka Coordination)
  zookeeper:
    image: confluentinc/cp-zookeeper:7.3.0
    container_name: zookeeper_coord
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"
    networks:
      - tx-network

  # Kafka Broker (Event streaming & Sagas)
  kafka:
    image: confluentinc/cp-kafka:7.3.0
    container_name: kafka_broker
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_INTERNAL:PLAINTEXT
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092,PLAINTEXT_INTERNAL://kafka:29092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
    networks:
      - tx-network

  # Redis (Distributed Locking)
  redis:
    image: redis:7.0-alpine
    container_name: redis_lock
    ports:
      - "6379:6379"
    networks:
      - tx-network

  # PostgreSQL (JTA XA databases & Outbox tables)
  postgres:
    image: postgres:15-alpine
    container_name: postgres_db
    environment:
      POSTGRES_USER: pguser
      POSTGRES_PASSWORD: pgpassword
      POSTGRES_DB: bank_ledger
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - tx-network

volumes:
  pgdata:

networks:
  tx-network:
    driver: bridge
```

---

## Grading Criteria & Hands-on Success Metrics

Your performance in this course is evaluated based on the following engineering metrics:

*   **Concurrency Control and Thread Safety (35%)**: Designing race-free structures. Proper use of Java concurrency primitives, distributed lock implementations, and thread-pool isolation boundaries.
*   **Consistency Architecture (35%)**: Implementing correct transactional boundaries. Ensuring database transaction rollbacks execute correctly under failures, and outbox event publishing guarantees at-least-once delivery.
*   **Distributed Systems Reasoning (20%)**: Demonstrating a deep understanding of CAP/PACELC tradeoffs, logical ordering, and consensus voter mechanics.
*   **Modern Java Implementation (10%)**: Using Java 21 features (records, virtual threads, pattern matching switches) to keep distributed systems code clean and readable.
