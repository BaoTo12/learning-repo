# Module 09: Application Design (Chapter 9)

Welcome class. Today we analyze **Application Design (CS-529)**.

In relational design, normalization rules dictate that database tables must be separated to prevent redundancy (Third Normal Form). In document database systems, database joins do not scale horizontally. Application schema design is driven by access patterns—minimizing read path latency by embedding nested objects or splitting records dynamically.

Today we study **Document Schema Engineering**, analyzing cardinality mappings (1:N, N:M), contrasting normalization with denormalization, and mapping advanced schema design patterns.

---

## 1. Academic Lecture: Cardinality Boundaries & Denormalization

### 1. Modeling Cardinality: When to Embed
*   **One-to-Few (1:Few)**: E.g., user preferences. Embed as nested subdocuments.
*   **One-to-Many (1:N)**: E.g., comments on a blog post. If the number of comments is bounded (less than 1000), embed. If unbounded, use parent referencing (store `postId` inside each `Comment` document).
*   **One-to-Squillions (1:10^6)**: E.g., system logging sources. Always reference. Never store references inside an array on the parent document.

### 2. Denormalization & Read/Write Optimization
Denormalization copies data across documents to bypass query joins.
*   **The Extended Reference Pattern**: Instead of storing only a `customerId` inside an `Order` document, copy high-frequency customer details (e.g. `customerName`) directly into the `Order`. This speeds up reads, but requires a background worker to update orders if a customer updates their name.

```text
[Normalized: SQL Join]
Order ────────(Query Join)────────> Customer (Fetch name on read)

[Denormalized: Extended Reference]
Order [customerId, customerName] (Direct read, zero joins)
```

---

## 2. Theory vs. Production Trade-offs

Compare document relationship architectures:

| Dimension / Metric | Normalized Modeling (References) | Denormalized Modeling (Embedded) | Extended Reference Pattern |
| :--- | :--- | :--- | :--- |
| **Read Performance** | Low (Requires multiple queries/lookup) | Excellent (Single key query) | Very High (Bypasses parent queries) |
| **Write Performance** | High (Small independent writes) | Low (Large documents, array edits) | Moderate (Requires syncing duplicated data) |
| **Data Consistency** | Absolute (Single point of truth) | Low (Data redundancy across docs) | Eventual (Requires updating duplicated keys) |
| **Document Size Limit** | Resilient | Vulnerable to 16MB boundary | Resilient |
| **Query Complexity** | High | Low | Low |

---

## 3. How to Use: Schema Pattern Implementation

Let us design application schemas. We contrast a naive normalized array design (vulnerable to overflow) with the robust Bucket Pattern.

### A. The Overflow Array Schema (Anti-Pattern)
Avoid storing unbounded transactional events inside a single document array:

```javascript
// DANGER: The "history" array will grow indefinitely as the device logs updates.
// This will eventually exceed the 16MB document limit and slow down index lookups.
db.devices.insertOne({
  deviceId: "DEV-101",
  history: [
    { timestamp: new Date(), status: "OK", temp: 21.3 },
    { timestamp: new Date(), status: "OK", temp: 21.5 }
    // ... unbounded entries ...
  ]
});
```

### B. The Bounded Bucket Schema (Production Pattern)
Group logs into buckets by time window or size to guarantee bounded document limits:

```javascript
// Robust Pattern: Records are grouped into documents containing at most 1,000 entries.
db.deviceHistoryBuckets.updateOne(
  { deviceId: "DEV-101", count: { $lt: 1000 } },
  {
    $push: { history: { timestamp: new Date(), status: "OK", temp: 21.3 } },
    $inc: { count: 1 },
    $setOnInsert: { start: new Date() }
  },
  { upsert: true }
);
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Denormalizing Highly Volatile Fields
*   **Why it fails**: Duplicating a product's price or stock count into every `OrderItem` or `Cart` document. Prices and stock numbers change constantly. Updating thousands of active documents every time a price shifts causes write locks and data inconsistency.
*   **Mitigation**: Only denormalize fields that are static or change rarely (e.g. category names, shipping addresses). Keep volatile fields normalized.

---

## 5. Socratic Review Questions

### Question 1
In MongoDB schema design, what is the "Subset Pattern" and how does it optimize working set memory limits?

#### Answer
The Subset Pattern splits a document into two collections based on access frequency. For example, in a product database, the active working set only requires the name, price, and top 5 reviews. The rest of the 500 reviews are stored in a separate collection. By extracting these reviews, we reduce the size of the documents loaded into WiredTiger's RAM cache, keeping the memory working set small and avoiding page faults.

---

## 6. Hands-on Challenge: E-Commerce Product Schema Re-Design

### The Challenge
In this challenge, you will implement schema partitioning.
Your task:
1. Re-design a product document for a high-traffic catalogue.
2. The product has:
   - Metadata (`productId`, `sku`, `price`).
   - Customer ratings (`averageRating`).
   - Detailed user reviews (which can grow to thousands of reviews).
3. Implement a write function `insertReview` that uses parent references to store reviews in a separate `reviews` collection, updating the parent product document's `averageRating` and `reviewCount` atomically.

Complete the implementation stub below:

```javascript
function addReviewToProduct(productId, rating, comment) {
  // TODO: Implement the write sequence:
  // 1. Insert review document to "reviews" with parent reference: { productId, rating, comment }
  // 2. Update parent "products" document: increment reviewCount by 1 and adjust averageRating.
}
```

### Verification Query
Validate the reference count:
```javascript
db.products.insertOne({ _id: "P-1", reviewCount: 0, averageRating: 0 });
addReviewToProduct("P-1", 5, "Great product!");

const prod = db.products.findOne({ _id: "P-1" });
const revCount = db.reviews.countDocuments({ productId: "P-1" });

if (prod.reviewCount === 1 && revCount === 1) {
  print("Success: Unbounded reviews decoupled using parent referencing.");
} else {
  print("Error: Schema update mismatch.");
}
```
