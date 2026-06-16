# Module 02: Query Language Fundamentals & Comparison Operators

In this module, we will explore the core read operations and comparison operators of the MongoDB Query Language (MQL). You will learn the syntax, execution mechanics, type comparison rules, and indexing behaviors for basic find commands and all comparison filter operators.

---

## 1. Core Read Commands

MongoDB provides two fundamental methods for querying documents from a collection: `find()` and `findOne()`.

### A. `find()`
#### Description
Scans the collection according to the provided filter and returns a **cursor** pointing to the matching documents. A cursor is a pointer to the result set of a query, which allows clients to iterate through the results in batches.

#### Syntax
```javascript
db.collection.find(filter, projection)
```
*   `filter` (Optional): A BSON document specifying the query criteria. If empty or omitted (`{}`), all documents in the collection match.
*   `projection` (Optional): A BSON document specifying which fields to return.

#### Behavior & Mechanics
*   **Non-Blocking / Deferred Execution**: Calling `find()` does not immediately retrieve all documents. It returns a cursor. Documents are fetched from the server as the application iterates over the cursor (default batch size is 101 documents or 16MB of data, whichever comes first).
*   **Cursor Methods**: The cursor object can be chained with modifiers like `sort()`, `skip()`, and `limit()`.
*   **Index Usage**: If a suitable index exists, the database engine executes an Index Scan (`IXSCAN`). Otherwise, it executes a Collection Scan (`COLLSCAN`).

#### Examples
Retrieve all active users:
*   **MongoDB Compass Filter**:
    ```json
    { "status": "ACTIVE" }
    ```

---

### B. `findOne()`
#### Description
Scans the collection and returns the **first document** that matches the query criteria. Instead of returning a cursor, it returns the document structure itself or `null` if no match is found.

#### Syntax
```javascript
db.collection.findOne(filter, projection)
```

#### Behavior & Mechanics
*   **Early Termination**: Once the query planner finds a single document matching the filter, it halts the search and returns it immediately.
*   **No Cursor Chaining**: Since `findOne()` returns a single document (or null) directly, you cannot chain cursor methods like `.sort()`, `.limit()`, or `.skip()`.
*   **Default Limit**: Under the hood, this behaves similarly to a `find().limit(1)` operation, but yields the document directly instead of a cursor cursor-wrap.

#### Examples
Retrieve a single user by their ID:
*   **MongoDB Compass Filter**:
    ```json
    { "_id": "USR-10024" }
    ```
*(Note: Compass will automatically fetch and display the matched document in the visual list view).*

---

## 2. Equality Matching Paradigms

MQL supports equality checking for different data types.

### A. Scalar/Primitive Equality
Matches field values exactly:
*   **MongoDB Compass Filter**: `{ "age": 30 }`

### B. Embedded/Subdocument Equality
Queries the entire nested object:
*   **MongoDB Compass Filter**: `{ "address": { "city": "Chicago", "zip": "60601" } }`
*   **Behavior**: This is **order-sensitive** and requires an exact structural match. If the document has `{ "zip": "60601", "city": "Chicago" }` in a different order, it will **not** match.
*   **Recommendation**: Use **Dot Notation** to avoid order sensitivity: `{ "address.city": "Chicago" }`.

### C. Array Equality
Queries list fields:
*   **MongoDB Compass Filter**: `{ "tags": "java" }` (matches if `"java"` is present anywhere in the `tags` array).
*   **MongoDB Compass Filter (Exact Array)**: `{ "tags": ["java", "spring"] }` (matches only if the array contains exactly those two elements in that exact order).

---

## 3. Comparison Operators Reference

Comparison operators query values relative to a reference. They are defined inside a field's criteria object: `{ <field>: { <operator>: <value> } }`.

### A. `$eq` (Equals)
#### Description
Matches documents where the value of a field equals the specified value.

#### Syntax
```json
{ "<field>": { "$eq": <value> } }
```

#### Behavior & Mechanics
*   **Implicit vs. Explicit**: `{ "status": "ACTIVE" }` is equivalent to `{ "status": { "$eq": "ACTIVE" } }`.
*   **Array Matching**: If the field is an array, `$eq` matches if any single element of the array equals `<value>`.
*   **Object Identity**: When matching an embedded document, it matches if the subdocument has the exact same fields in the exact same order.

#### Examples
Find users whose username is exactly `"alice"`:
*   **MongoDB Compass Filter**:
    ```json
    { "username": { "$eq": "alice" } }
    ```

---

### B. `$ne` (Not Equal)
#### Description
Matches documents where the value of the field does not equal the specified value, including documents that do not contain the field.

#### Syntax
```json
{ "<field>": { "$ne": <value> } }
```

#### Behavior & Mechanics
*   **Non-existent Fields**: If a document does not contain the queried `<field>`, it matches the `$ne` query.
*   **Performance Impact**: `$ne` is **not selective**. Since it matches almost everything except a specific value, it usually cannot use standard index scans efficiently and forces a collection scan (`COLLSCAN`). Combine `$ne` with a selective query field whenever possible.
*   **Array Matching**: If the field is an array, `$ne` matches only if **none** of the array elements equal the specified value.

#### Examples
Find all users whose status is not `"DELETED"`:
*   **MongoDB Compass Filter**:
    ```json
    { "status": { "$ne": "DELETED" } }
    ```

---

### C. `$gt` (Greater Than)
#### Description
Matches documents where the value of the field is greater than the specified value.

#### Syntax
```json
{ "<field>": { "$gt": <value> } }
```

#### Behavior & Mechanics
*   **Type Comparison Rules**: If the field contains a different type than `<value>`, MongoDB compares them based on the **BSON Type Comparison Order** (MinKey < Null < Numbers < Symbol/String < Object < Array < BinData < ObjectId < Boolean < Date < MaxKey).
*   **Array Matching**: If the field is an array, `$gt` matches if at least one element of the array is greater than `<value>`.
*   **Index Range Scans**: Supports highly efficient index range scans (`IXSCAN`).

#### Examples
Find products with a price greater than `100.00`:
*   **MongoDB Compass Filter**:
    ```json
    { "price": { "$gt": 100.00 } }
    ```

---

### D. `$gte` (Greater Than or Equal)
#### Description
Matches documents where the value of the field is greater than or equal to the specified value.

#### Syntax
```json
{ "<field>": { "$gte": <value> } }
```

#### Behavior & Mechanics
*   Identical to `$gt`, but includes values that are exactly equal to `<value>`.
*   Commonly used in compound range filters (e.g. `{ "age": { "$gte": 18, "$lte": 65 } }`).

#### Examples
Find users aged 18 or older:
*   **MongoDB Compass Filter**:
    ```json
    { "age": { "$gte": 18 } }
    ```

---

### E. `$lt` (Less Than)
#### Description
Matches documents where the value of the field is less than the specified value.

#### Syntax
```json
{ "<field>": { "$lt": <value> } }
```

#### Behavior & Mechanics
*   Complementary to `$gt`.
*   Performs index range scans starting from the beginning of the index up to `<value>`.
*   For arrays, matches if at least one element is less than `<value>`.

#### Examples
Find products with stock less than `10`:
*   **MongoDB Compass Filter**:
    ```json
    { "stock": { "$lt": 10 } }
    ```

---

### F. `$lte` (Less Than or Equal)
#### Description
Matches documents where the value of the field is less than or equal to the specified value.

#### Syntax
```json
{ "<field>": { "$lte": <value> } }
```

#### Behavior & Mechanics
*   Identical to `$lt`, but includes values that are exactly equal to `<value>`.

#### Examples
Find items priced $19.99 or lower:
*   **MongoDB Compass Filter**:
    ```json
    { "price": { "$lte": 19.99 } }
    ```

---

### G. `$in` (In Set)
#### Description
Matches documents where the value of a field equals any value in the specified array.

#### Syntax
```json
{ "<field>": { "$in": [ <value1>, <value2>, ... <valueN> ] } }
```

#### Behavior & Mechanics
*   **Implicit OR**: `$in` behaves like a logical OR query matching multiple equality expressions on the same field.
*   **Array Fields**: If `<field>` is an array, `$in` matches if the intersection of the document's array and the query's `$in` array is not empty (i.e. at least one element matches).
*   **Regex Compatibility**: You can use regular expression objects inside the `$in` array: `{ "tags": { "$in": [ /^java/i, "python" ] } }`.
*   **Index Utilization**: Fully utilizes indexes. The query planner performs multiple point range scans inside the index.

#### Examples
Find orders that are either `PENDING`, `SHIPPED`, or `PROCESSING`:
*   **MongoDB Compass Filter**:
    ```json
    { "status": { "$in": ["PENDING", "SHIPPED", "PROCESSING"] } }
    ```

---

### H. `$nin` (Not In Set)
#### Description
Matches documents where the field value does not equal any value in the specified array, including documents that do not contain the field.

#### Syntax
```json
{ "<field>": { "$nin": [ <value1>, <value2>, ... <valueN> ] } }
```

#### Behavior & Mechanics
*   **Non-existent Fields**: Just like `$ne`, documents missing the field will match the `$nin` query.
*   **Array Fields**: If `<field>` is an array, `$nin` matches if **none** of the elements in the document's array match any value in the `$nin` array.
*   **Performance Overhead**: Like `$ne`, `$nin` is generally **non-selective** and causes full collection scans (`COLLSCAN`) unless backed by other selective filters.

#### Examples
Find users who are not in the `GUEST` or `BANNED` roles:
*   **MongoDB Compass Filter**:
    ```json
    { "role": { "$nin": ["GUEST", "BANNED"] } }
    ```

---

## 4. Key Performance and Indexing Summary

> [!IMPORTANT]
> *   **Selective Filters**: `$eq`, `$in`, `$gt`, `$lt`, `$gte`, `$lte` can perform highly efficient index range scans (`IXSCAN`).
> *   **Non-Selective Filters**: `$ne` and `$nin` are negative matches. Because they require scanning the inverse of a target set, they usually trigger collection scans. Avoid placing them alone in high-throughput query flows.
