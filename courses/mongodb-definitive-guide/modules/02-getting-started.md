# Module 02: Getting Started with MongoDB (Chapter 2)

Welcome class. Today we analyze **Getting Started with MongoDB (CS-529)**.

MongoDB represents and stores data as BSON (Binary JSON) on disk. BSON extends JSON by introducing strict binary representations of datatypes, such as 64-bit integers (`Long`), 128-bit decimals (`Decimal128` for currency), dates, and binary chunks. Understanding BSON data mapping in Java is essential to prevent accuracy loss during database serialization.

Today we study **BSON Type Conversions in Java**, analyzing data representation rules, ObjectId structures, and insert operations.

---

## 1. Academic Lecture: BSON Types & ObjectId Generation in Java

### 1. BSON Data Typing
Standard JavaScript/JSON only has a single numeric type (double-precision float). BSON introduces strict numerical mapping classes to support Java typed primitives:
*   `Integer` -> `BSON Int32`
*   `Long` -> `BSON Int64`
*   `BigDecimal` -> `BSON Decimal128` (Crucial to avoid floating-point errors in finance calculations)

### 2. The ObjectId Class
MongoDB's default key `_id` is an `org.bson.types.ObjectId` (12 bytes):
*   **4 bytes**: Unix timestamp (seconds).
*   **5 bytes**: Machine process identifier.
*   **3 bytes**: Incrementing counter.
In Java, calling `new ObjectId().getDate()` returns a standard `java.util.Date` instance extracted directly from the timestamp bytes, allowing chronological sorts without separate date fields.

### 3. Java-to-BSON Type Mapping Table
When working with the MongoDB Java Driver, the driver automatically translates JVM classes to corresponding BSON database representations:

| Java Native Class | BSON Type Representation | BSON Type Code | Example Usage in Java |
| :--- | :--- | :--- | :--- |
| `java.lang.String` | String (UTF-8) | `0x02` | `"John Doe"` |
| `java.lang.Integer` | Int32 (32-bit signed) | `0x10` | `42` |
| `java.lang.Long` | Int64 (64-bit signed) | `0x12` | `100000L` |
| `java.lang.Double` | Double (64-bit float) | `0x01` | `99.95` |
| `java.lang.Boolean` | Boolean | `0x08` | `true` / `false` |
| `java.util.Date` | UTC DateTime (ISODate) | `0x09` | `new java.util.Date()` |
| `org.bson.types.ObjectId` | ObjectId (12-byte binary) | `0x07` | `new ObjectId()` |
| `org.bson.types.Decimal128` | Decimal128 (Exact decimal) | `0x13` | `new Decimal128(new BigDecimal("10.99"))` |
| `java.util.List` | Array (ordered container) | `0x04` | `List.of("A", "B")` |
| `org.bson.Document` | Embedded Document (Object) | `0x03` | `new Document("key", "val")` |

```text
[12-Byte Binary ObjectId] ────> new ObjectId() ────> getDate() (Date)
                              ├── timestamp (seconds)
                              ├── random process bytes
                              └── incrementing counter
```

---

## 2. Theory vs. Production Trade-offs

Compare Java numeric mappings to database storage types:

| Java Type | BSON Type | Precision | Use Case |
| :--- | :--- | :--- | :--- |
| `double` / `Double` | Double | IEEE 754 float | General physics, floating numbers |
| `int` / `Integer` | Int32 | 32-bit signed int | Quantities, counts |
| `long` / `Long` | Int64 | 64-bit signed int | Epoch timestamps, transaction IDs |
| `BigDecimal` | Decimal128 | 128-bit IEEE 754-2008 | Currency values, financial balance |
| `String` | String | UTF-8 encoded | Text matching |

---

## 3. How to Use: Typed Insertions in Java

Let us look at BSON insertions. We contrast a type-weak document creation (which stores numbers as strings) with a type-safe database insertion using correct BSON types.

### A. The Type-Weak Document Creation (Anti-Pattern)
Avoid saving numbers as raw strings or using double variables for currencies:

```java
// DANGER: Storing cost as a double causes floating point rounding errors.
// Storing stock count as a string prevents range query filters ($gt, $lt) from behaving numerically.
Document doc = new Document("sku", "W-1")
        .append("cost", 10.99)
        .append("stock", "50");
collection.insertOne(doc);
```

### B. The Type-Safe BSON Insertion (Production Pattern)
Wrap currency values in `Decimal128` and numbers in standard integer classes:

```java
import org.bson.Document;
import org.bson.types.Decimal128;
import java.math.BigDecimal;

// Robust Pattern: Primitives are cast to strict BSON representation types.
Document doc = new Document("sku", "W-1")
        .append("cost", new Decimal128(new BigDecimal("10.99")))
        .append("stock", 50)  // Implicitly mapped to BSON Int32
        .append("registeredAt", new java.util.Date());
collection.insertOne(doc);
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: BSON Int32 vs Int64 Overflow Errors
*   **Why it fails**: Passing a Java `long` value (e.g. system milliseconds) to a document where the database expects a standard Integer. If the value exceeds the 32-bit signed integer boundary (`2,147,483,647`), it overflows, leading to negative numbers or parse errors.
*   **Mitigation**: Always ensure that long numbers (ID keys, timestamps) are typed as `Long` or stored using proper epoch Date classes.

---

## 5. Socratic Review Questions

### Question 1
Why does MongoDB enforce `ObjectId` generation on the client driver side rather than on the database server during inserts?

#### Answer
In distributed architectures, generating unique keys on the database server requires network handshakes, creating a bottleneck. The `ObjectId` is structured with unique machine identifiers, timestamps, and process IDs so that the client Java driver can generate it independently. The driver client can guarantee global uniqueness without coordinating with the cluster, maximizing insert throughput.

---

## 6. Hands-on Challenge: Strict BSON Type Insertion

### The Challenge
In this challenge, you will implement a type-safe document creator in Java.
Your task:
1. Complete `buildProductDocument` in `ProductBuilder`.
2. Construct a Document containing a strict `Integer` for stock and a `Decimal128` for cost.

Complete the implementation stub:

```java
package com.mongodb.systems;

import org.bson.Document;
import org.bson.types.Decimal128;
import java.math.BigDecimal;

public class ProductBuilder {

    public Document buildProductDocument(String sku, int stock, BigDecimal cost) {
        // TODO: Return a Document containing:
        // - "sku" (String)
        // - "stock" (Integer)
        // - "cost" (Decimal128)
        return null;
    }
}
```

### Verification Test
Verify your code with this JUnit 5 test class:

```java
package com.mongodb.systems;

import org.bson.Document;
import org.bson.types.Decimal128;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import static org.junit.jupiter.api.Assertions.*;

class ProductBuilderTest {

    @Test
    void testBuildProductDocument() {
        ProductBuilder builder = new ProductBuilder();
        BigDecimal cost = new BigDecimal("49.99");
        Document doc = builder.buildProductDocument("SKU-1", 100, cost);

        assertNotNull(doc);
        assertTrue(doc.get("stock") instanceof Integer);
        assertTrue(doc.get("cost") instanceof Decimal128);
        assertEquals(Decimal128.parse("49.99"), doc.get("cost"));
    }
}
```
