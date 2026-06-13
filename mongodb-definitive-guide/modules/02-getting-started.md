# Module 02: Getting Started with MongoDB (Chapter 2)

Welcome class. Today we analyze **Getting Started with MongoDB (CS-529)**.

Underneath MongoDB's JSON-like interface lies a binary serialization format called **BSON** (Binary JSON). BSON is designed to be lightweight, traversable, and efficient, supporting advanced data types that standard JSON cannot represent (like dates, regular expressions, and raw byte arrays).

Today we study **BSON Data Modeling**, learning the exact datatypes supported by the storage engine, how MongoDB identifies documents, and how to query databases in `mongosh`.

---

## 1. Academic Lecture: BSON Serialization & Document Lifecycles

### 1. BSON Internals
While standard JSON is parsed as text, BSON is stored as binary bytes. BSON encodes length prefixes for documents and arrays, allowing the database engine to skip nested elements during scans without parsing the entire payload.

### 2. The ObjectId Structure
MongoDB uses a unique identifier for the primary key `_id` called **ObjectId**. An ObjectId is a 12-byte binary value consisting of:
*   **4-byte timestamp**: Unix epoch seconds, providing natural chronological sorting.
*   **5-byte random value**: Generated per process, unique to the host machine.
*   **3-byte counter**: Incrementing sequence starting with a random value.

```text
 ┌─────────────────────────── ObjectId (12 Bytes) ───────────────────────────┐
 ├───────────────────┬───────────────────────────────┬───────────────────────┤
 │  Timestamp (4B)   │       Random Value (5B)       │     Counter (3B)      │
 └───────────────────┴───────────────────────────────┴───────────────────────┘
```

---

## 2. Theory vs. Production Trade-offs

Compare standard JSON with MongoDB BSON types:

| Dimension / Metric | JSON | BSON |
| :--- | :--- | :--- |
| **Number Resolution** | Single type (Double) | Int32, Int64, Double, Decimal128 |
| **DateTime Storage** | String (Requires parsing) | 64-bit Epoch millisecond integer |
| **Raw Binary Data** | Base64 strings (33% size bloat) | Native binary fields (`BinData`) |
| **Traversal Speed** | Slow (Text parsing) | Fast (Length prefixes enable skipping) |
| **Storage Overhead** | Low (Raw characters) | Moderate (Metadata, length byte fields) |

---

## 3. How to Use: Typing in BSON

Let us write BSON insertion queries. We contrast a type-weak query that results in parsing errors with a type-safe production schema.

### A. The Type-Weak Insertion (Anti-Pattern)
Avoid storing numeric values as generic strings, which prevents calculations:

```javascript
// DANGER: Storing numbers as strings makes mathematical operations like $inc fail.
db.inventory.insertOne({
  item: "Widget",
  price: "10.99",
  stock: "50"
});
```

### B. The Type-Safe BSON Insertion (Production Pattern)
Explicitly type values using standard integers, decimals, and date instances:

```javascript
// Robust Pattern: Numbers and Date are cast to proper binary types.
db.inventory.insertOne({
  item: "Widget",
  price: NumberDecimal("10.99"),
  stock: NumberInt(50),
  createdAt: new Date()
});
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Double Precision vs. Exact Decimals
*   **Why it fails**: Using standard floating-point numbers (`Double`) for financial math. JavaScript numbers are IEEE 754 doubles, which cause rounding errors (e.g. `0.1 + 0.2` becomes `0.30000000000000004`).
*   **Mitigation**: Always wrap currency values in `NumberDecimal()` to store them as high-precision 128-bit decimal floating points.

---

## 5. Socratic Review Questions

### Question 1
Why does MongoDB choose a distributed ObjectId generator instead of an auto-incrementing integer sequence for the `_id` field?

#### Answer
Auto-incrementing sequences require a central registry to guarantee that no duplicate IDs are generated. In a distributed sharded cluster, shards would have to lock and coordinate with each other to allocate the next ID, introducing a severe bottleneck. ObjectId can be generated independently on client drivers and shards without network communication, guaranteeing global uniqueness across nodes.

---

## 6. Hands-on Challenge: Strict Type Insertion

### The Challenge
In this challenge, you will implement type-safe document insertions.
Your task:
1. Write a script to insert a product document inside `products`.
2. The product must contain:
   - `sku` (string)
   - `inventoryCount` (strict 32-bit integer)
   - `cost` (strict Decimal128)
   - `isAvailable` (boolean)
   
Complete the implementation stub below:

```javascript
// TODO: Write insertion script using strict types
db.products.insertOne({
  // Add fields here
});
```

### Verification Query
Run the validation check:
```javascript
const doc = db.products.findOne({ sku: "SKU-8812" });
if (doc && typeof doc.inventoryCount === 'number' && doc.cost instanceof NumberDecimal) {
  print("Success: Document variables contain compile-grade BSON types.");
} else {
  print("Error: BSON type casting failed.");
}
```
