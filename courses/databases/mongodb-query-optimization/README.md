# MongoDB Query Optimization: From Beginner to Expert

> **A university-level, production-oriented course in MongoDB query performance engineering.**

This course is written for software and AI engineering students who want to understand not just *how* to optimize MongoDB queries, but *why* techniques work, *when* they apply, and *when* they become harmful. Every module emphasizes engineering judgment, internal mechanics, and real-world trade-offs over rote memorization.

---

## Who This Course Is For

| Background | Benefit |
| :--- | :--- |
| Junior engineers starting with MongoDB | Build the right mental model from day one |
| Mid-level engineers with MongoDB experience | Fill gaps, understand internals, optimize confidently |
| Senior engineers onboarding to MongoDB | Accelerate mastery of production trade-offs |
| AI engineers using MongoDB for vector/RAG workloads | Understand performance implications for AI retrieval patterns |
| Engineering leads and architects | Capacity planning, sharding decisions, cost optimization |

---

## Prerequisites

- Solid command of MongoDB CRUD operations and basic aggregation
- Familiarity with general database concepts (indexes, transactions, consistency)
- Basic understanding of operating system concepts (disk I/O, memory, CPU scheduling)
- Access to a local MongoDB 7+ instance (Docker recommended)
- Optional but helpful: Spring Boot or Node.js MongoDB driver experience

---

## Course Philosophy

This course teaches MongoDB optimization through **seven layers of depth** for every major concept:

1. **Intuition** — Build the right mental model before the mechanics
2. **Internal Mechanics** — Understand what MongoDB is actually doing
3. **Concrete Examples** — Toy, realistic, and large-scale examples with `explain()` output
4. **Trade-Off Analysis** — No technique is universally correct
5. **Comparative Reasoning** — Why this approach vs. alternatives?
6. **Production Reality** — What textbooks don't tell you
7. **Expert Perspective** — Common misconceptions, interview traps, edge cases

---

## Course Structure & Syllabus

| Module | Title | Difficulty | Est. Study Time |
| :--- | :--- | :--- | :--- |
| **01** | [Foundations of MongoDB Performance](modules/01-foundations-of-mongodb-performance.md) | Beginner | 4h |
| **02** | [Query Execution Internals](modules/02-query-execution-internals.md) | Beginner–Intermediate | 5h |
| **03** | [Understanding Explain Plans](modules/03-understanding-explain-plans.md) | Intermediate | 5h |
| **04** | [Indexing Fundamentals](modules/04-indexing-fundamentals.md) | Intermediate | 6h |
| **05** | [Compound Index Design (ESR Rule)](modules/05-compound-index-design.md) | Intermediate–Advanced | 6h |
| **06** | [Query Pattern Optimization](modules/06-query-pattern-optimization.md) | Intermediate–Advanced | 5h |
| **07** | [Aggregation Pipeline Optimization](modules/07-aggregation-pipeline-optimization.md) | Advanced | 7h |
| **08** | [Advanced Optimization Techniques](modules/08-advanced-optimization-techniques.md) | Advanced | 5h |
| **09** | [Schema Design and Query Performance](modules/09-schema-design-and-query-performance.md) | Advanced | 6h |
| **10** | [Sharding and Distributed Query Optimization](modules/10-sharding-and-distributed-optimization.md) | Advanced | 6h |
| **11** | [Monitoring and Performance Diagnosis](modules/11-monitoring-and-performance-diagnosis.md) | Advanced | 5h |
| **12** | [Expert Topics and Edge Cases](modules/12-expert-topics.md) | Expert | 6h |
| **LAB** | [Hands-On Labs](labs/README.md) | Progressive | 10h |
| **CAP** | [Capstone Project](capstone/README.md) | Expert | 15h |

**Total Estimated Study Time: ~96 hours** (self-paced, over 8–12 weeks)

---

## Local Development Environment

### Option A: Docker (Recommended for Replica Sets)

```bash
# Start a 3-node MongoDB replica set (required for transactions, change streams)
docker run -d \
  --name mongo-opt \
  -p 27017:27017 \
  mongo:7.0 \
  --replSet rs0 \
  --wiredTigerCacheSizeGB 1

# Initialize the replica set
docker exec mongo-opt mongosh --eval "rs.initiate()"
```

### Option B: Docker Compose (Full Lab Environment)

```yaml
# docker-compose.yml - place in your workspace root
version: '3.8'
services:
  mongo1:
    image: mongo:7.0
    container_name: opt-mongo1
    command: ["mongod", "--replSet", "rs0", "--bind_ip_all", "--wiredTigerCacheSizeGB", "1"]
    ports: ["27017:27017"]
    volumes: ["mongo1_data:/data/db"]

  mongo2:
    image: mongo:7.0
    container_name: opt-mongo2
    command: ["mongod", "--replSet", "rs0", "--bind_ip_all", "--wiredTigerCacheSizeGB", "1", "--port", "27018"]
    ports: ["27018:27018"]
    volumes: ["mongo2_data:/data/db"]

  mongo-init:
    image: mongo:7.0
    depends_on: [mongo1, mongo2]
    entrypoint: >
      bash -c "sleep 3 && mongosh --host mongo1:27017 --eval
      'rs.initiate({_id:\"rs0\",members:[{_id:0,host:\"mongo1:27017\"},{_id:1,host:\"mongo2:27018\"}]})'"

volumes:
  mongo1_data:
  mongo2_data:
```

### Dataset Generator

Each lab provides a seed script. You can generate test data:

```javascript
// seed.js — generate 1 million orders for lab exercises
use('optimization_lab');

const statuses = ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled'];
const regions  = ['us-east', 'us-west', 'eu-central', 'ap-south', 'ap-east'];
const skus     = Array.from({length: 500}, (_, i) => `SKU-${String(i).padStart(4,'0')}`);

const batch = 1000;
for (let b = 0; b < 1000; b++) {
  const docs = Array.from({length: batch}, (_, i) => ({
    orderId:    `ORD-${b * batch + i}`,
    customerId: `CUST-${Math.floor(Math.random() * 50000)}`,
    sku:        skus[Math.floor(Math.random() * skus.length)],
    quantity:   Math.floor(Math.random() * 10) + 1,
    amount:     parseFloat((Math.random() * 500 + 5).toFixed(2)),
    status:     statuses[Math.floor(Math.random() * statuses.length)],
    region:     regions[Math.floor(Math.random() * regions.length)],
    createdAt:  new Date(Date.now() - Math.random() * 365 * 24 * 3600 * 1000),
    tags:       Array.from({length: Math.floor(Math.random() * 4)}, () => `tag-${Math.floor(Math.random()*20)}`)
  }));
  db.orders.insertMany(docs);
}
print('Done: 1,000,000 orders inserted.');
```

---

## How to Use This Course

1. Read each module in order. Do not skip foundational modules even if you have experience — they establish the **mental model** used throughout the course.
2. Run every `explain()` example yourself in `mongosh`.
3. Pause at every **"Engineering Judgment Question"** and write down your own answer before reading the provided analysis.
4. Complete lab exercises before looking at hints or solutions.
5. Use the **Reflection Questions** at the end of each module to check your understanding.

---

## Grading Philosophy

There is no formal grading. The real test is operational:

> Can you look at a slow MongoDB query in production, diagnose the problem, propose a fix, reason about the trade-offs, and validate the result?

Each module's **Interview-Style Questions** section will tell you when you are ready to move forward.

---

## Glossary of Key Terms

| Term | Definition |
| :--- | :--- |
| **Working Set** | The data and indexes MongoDB needs to hold in RAM to serve requests efficiently |
| **COLLSCAN** | Collection scan — MongoDB reads every document in the collection |
| **IXSCAN** | Index scan — MongoDB traverses the B-tree index |
| **FETCH** | MongoDB uses an index to find `_id` values, then fetches full documents |
| **Covered Query** | Query fully satisfied from index data alone — no FETCH stage needed |
| **Selectivity** | Fraction of documents matched by a filter. High selectivity = few matches |
| **Cardinality** | Number of distinct values for a field |
| **ESR Rule** | Equality → Sort → Range — optimal compound index field ordering |
| **SBE** | Slot-Based Execution Engine — MongoDB's modern query execution runtime |
| **Plan Cache** | MongoDB's cache of winning query plans to avoid re-planning |
| **Scatter-Gather** | A sharded query that must be sent to all shards — expensive |
| **Shard Targeting** | A sharded query routed to exactly one shard — efficient |
| **Pushdown** | Optimizer moves a stage earlier in the pipeline to reduce data processed |
