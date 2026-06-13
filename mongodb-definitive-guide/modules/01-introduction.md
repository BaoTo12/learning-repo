# Module 01: Introduction to MongoDB (Chapter 1)

Welcome class. Today we analyze **Introduction to MongoDB (CS-529)**.

In modern enterprise architectures, the relational database model, which has dominated the industry for decades, is facing scalability bottlenecks. Traditional relational databases (RDBMS) rely heavily on a highly normalized tabular structure, enforcing strict schemas and foreign key constraints. While this ensures relational integrity, it makes horizontal scaling (scaling out) extremely complex and computationally expensive.

Today we study **Document-Oriented Database Architectures**, mapping the core design philosophies of MongoDB, contrasting scaling paradigms, and analyzing the features that set document models apart.

---

## 1. Academic Lecture: Document Databases & Scaling Paradigms

### 1. Document-Oriented vs. Relational Models
A document-oriented database replaces the concept of a "row" with a more flexible structure: the **document**. 
In MongoDB, data is represented as BSON (Binary JSON). This model has several key advantages:
*   **Embedded Documents and Arrays**: By allowing nested structures, a single document can represent complex hierarchical relationships that would require multiple table joins in a relational database.
*   **Dynamic Schemas**: There are no predefined schemas. A document's keys and values are not of fixed types or sizes. Adding or removing fields is trivial and does not require costly `ALTER TABLE` operations.

### 2. Scaling Up vs. Scaling Out
As datasets grow, engineers must choose how to scale:
*   **Scaling Up (Vertical Scaling)**: Upgrading the server hardware (adding more CPU cores, RAM, or faster disk arrays). This is simple but has physical limits and is exponentially expensive.
*   **Scaling Out (Horizontal Scaling)**: Distributing the dataset across multiple commodity servers (sharding). MongoDB was designed from the ground up to scale out. The document model makes it easier to partition data across servers, automatically balancing load and routing queries.

```text
[Scale-Up / Vertical]            [Scale-Out / Horizontal (MongoDB Sharding)]
   ┌───────────┐                         ┌───────────┐ ┌───────────┐ ┌───────────┐
   │           │                         │  Shard 1  │ │  Shard 2  │ │  Shard 3  │
   │  Bigger   │                         └───────────┘ └───────────┘ └───────────┘
   │  Server   │                                       ▲
   │           │                                       │ (Auto Balancer)
   └───────────┘                                       ▼
 (Hardware Limit)                        [Dynamically add commodity servers]
```

---

## 2. Theory vs. Production Trade-offs

Compare the operational behaviors of relational databases and MongoDB:

| Dimension / Metric | Relational Database (RDBMS) | MongoDB (Document Store) |
| :--- | :--- | :--- |
| **Schema Flexibility** | Rigid (Strict schemas, tables) | Dynamic (Schema-less, polymorphic documents) |
| **Scaling Strategy** | Typically Vertical (Scale-Up) | Native Horizontal (Scale-Out via Sharding) |
| **Complex Relationships** | Resolved at query time via `JOIN`s | Resolved at write time via Embedding / Arrays |
| **Data Integrity** | Enforced at DB level (Foreign Keys) | App-level validation (or schema validators) |
| **Transaction Boundaries** | Global ACID across tables | ACID within single documents (and sessions) |

---

## 3. How to Use: Core Scaling Design

Let us explore how MongoDB maps objects. We compare a naive relational mapping (requiring separate tables and foreign keys) against a robust embedded document schema design.

### A. The Relational Normalization (Anti-Pattern in Document DBs)
Avoid splitting tightly coupled hierarchical relationships into separate collections, which forces application-side joins:

```javascript
// DANGER: Creating separate collections for addresses requires manual joining on the client,
// which causes network overhead and defeats the advantage of document embedding.
db.users.insertOne({ _id: 1, name: "Alice" });
db.addresses.insertOne({ userId: 1, street: "123 Main St", city: "Seattle" });
```

### B. The Embedded Document Pattern (Production Pattern)
Model hierarchical data in a single document using arrays or nested subdocuments to optimize read speed:

```javascript
// Robust Pattern: A single fetch retrieves user profile and all addresses atomically.
db.users.insertOne({
  _id: 1,
  name: "Alice",
  addresses: [
    { type: "home", street: "123 Main St", city: "Seattle" },
    { type: "work", street: "456 Market St", city: "San Francisco" }
  ]
});
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Application Joins Instead of Embedded Models
*   **Why it fails**: When developers migrate from SQL to MongoDB, they often retain normalized table schemas, using IDs to reference documents in other collections. Querying these collections requires separate database operations, creating round-trip latency.
*   **Mitigation**: Embed data that is consumed together. Use references only when the referenced data is unbounded or accessed independently.

---

## 5. Socratic Review Questions

### Question 1
Why does a dynamic schema make horizontal partitioning (sharding) easier than a strict relational schema with foreign key constraints?

#### Answer
In relational databases, foreign key constraints require the database engine to check other tables across the cluster to verify referential integrity on inserts or deletes. This necessitates cross-network coordination, leading to severe latency. MongoDB's independent, self-contained document model ensures that a document contains all its context, allowing shards to operate independently without querying other cluster nodes.

---

## 6. Hands-on Challenge: Relational to Document Schema Migration

### The Challenge
In this challenge, you will design a schema migration.
Your task:
1. Write a script `migrate.js` to insert a document representing an e-commerce order.
2. The order must contain:
   - Order metadata (`orderId`, `status`).
   - Customer info nested inside the document.
   - An array of order items (each containing `product`, `quantity`, and `price`).
3. Ensure no external collections are referenced for items.

Complete the implementation stub below:

```javascript
// TODO: Implement order insertion query
db.orders.insertOne({
  // Add fields here
});
```

### Verification Query
Run the query to verify nested items count:
```javascript
const order = db.orders.findOne({ orderId: "ORD-9921" });
if (order && Array.isArray(order.items) && order.items.length > 0) {
  print("Success: Document correctly contains embedded items array.");
} else {
  print("Error: Missing nested items structure.");
}
```
