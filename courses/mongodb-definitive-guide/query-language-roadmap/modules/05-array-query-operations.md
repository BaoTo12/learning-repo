# Module 05: Array Query Operations

In this module, we will explore querying array fields in the MongoDB Query Language (MQL). Arrays are first-class citizens in BSON. We will cover inclusion checks, exact matches, array size filters (including range workarounds), and multi-condition element evaluation via the `$elemMatch` operator. We will also address the indexing mechanisms and write performance trade-offs associated with Multikey Indexes.

---

## 1. Querying Arrays (Fundamentals)

Querying array fields can locate documents based on simple inclusion or exact array equality.

### A. Element Inclusion (Implicit Match)
Querying an array field using a scalar value checks if the value exists anywhere within the array.
*   **MongoDB Compass Filter**: `{ "tags": "electronics" }`

### B. Exact Array Match
Matches if the array contains exactly the specified elements in the exact specified order.
*   **MongoDB Compass Filter**: `{ "tags": ["electronics", "premium"] }`

---

## 2. Array Operator Reference

MongoDB provides specialized operators for advanced array matching: `$all`, `$size`, and `$elemMatch`.

### A. `$all` (Match All Elements)
#### Description
Matches documents where the value of a field is an array that contains **all** the specified elements, regardless of their position or order in the array.

#### Syntax
```json
{ "<field>": { "$all": [ <value1>, <value2>, ... <valueN> ] } }
```

#### Behavior & Mechanics
*   **Logical Equivalence**: An `$all` query is equivalent to an explicit `$and` query checking for the presence of each element (e.g. `{ "tags": { "$all": ["A", "B"] } }` is equivalent to `{ "$and": [ { "tags": "A" }, { "tags": "B" } ] }`).
*   **Nested Array Matching**: If the elements in the `$all` array are documents, MongoDB evaluates them using exact matching rules unless combined with `$elemMatch`.

#### Examples
Find products containing both `"electronics"` and `"premium"` tags:
*   **MongoDB Compass Filter**:
    ```json
    { "tags": { "$all": ["electronics", "premium"] } }
    ```

---

### B. `$size` (Array Length Matching)
#### Description
Matches any array that has exactly the specified number of elements.

#### Syntax
```json
{ "<field>": { "$size": <integer> } }
```

#### Behavior & Mechanics
*   **Exact Integer Match**: The `$size` operator only accepts exact, non-negative integers. It **does not** accept range operators (e.g. `{ "tags": { "$size": { "$gt": 3 } } }` is invalid and will error).
*   **Range Comparison Hack**: To query for arrays that contain more than N elements (e.g. size > 3), query for the existence of the element at index position N (index `3` since arrays are 0-indexed):
    *   **Raw MQL Filter**: `{ "tags.3": { "$exists": true } }`
*   **Index Limits**: Standard indexes **cannot** be used to satisfy `$size` queries directly. If you frequently query for array length, store an explicit `size` integer field on the document and update it during array modifications.

#### Examples
Find products that have exactly 3 tags:
*   **MongoDB Compass Filter**:
    ```json
    { "tags": { "$size": 3 } }
    ```

Find products that have more than 3 tags:
*   **MongoDB Compass Filter**:
    ```json
    { "tags.3": { "$exists": true } }
    ```

---

### C. `$elemMatch` (Multi-Condition Element Match)
#### Description
Matches documents that contain an array field with at least one element that matches all the specified query criteria.

#### Syntax
```json
{ "<field>": { "$elemMatch": { <query1>, <query2>, ... <queryN> } } }
```

#### Behavior & Mechanics
*   **The Array Condition Trap**: Consider a `ratings` array: `[4, 9, 12]`.
    *   If you query: `{ "ratings": { "$gt": 5, "$lt": 10 } }`, MongoDB matches the document because `12 > 5` (matches first condition) and `4 < 10` (matches second condition). It evaluates them across different elements.
    *   If you query: `{ "ratings": { "$elemMatch": { "$gt": 5, "$lt": 10 } } }`, the query will verify if **a single element** satisfies both conditions. In this case, `9` satisfies both, so it matches.
*   **Object Array Matching**: Essential when querying list fields that contain embedded documents, ensuring conditions target the same subdocument.

#### Examples
Find products with at least one rating between 5 and 10:
*   **MongoDB Compass Filter**:
    ```json
    { "ratings": { "$elemMatch": { "$gt": 5, "$lt": 10 } } }
    ```

Find shopping carts containing an item of category `"electronics"` with quantity of 2 or more:
*   **MongoDB Compass Filter**:
    ```json
    {
      "items": {
        "$elemMatch": {
          "category": { "$eq": "electronics" },
          "quantity": { "$gte": 2 }
        }
      }
    }
    ```

---

## 3. Indexing Arrays: Multikey Indexes

When you index an array field, MongoDB automatically creates a **Multikey Index**, indexing each individual element of the array.

### Visual Representation:
If document `doc1` has `tags: ["blue", "red"]`, the index structure creates two separate index keys mapping to `doc1`:
```
"blue" -> doc1
"red"  -> doc1
```

### Constraints & Performance Warnings:
*   **Write Amplification**: Inserting or updating documents with large arrays requires updating a separate index entry for each element. Keep arrays queryable and bounded (ideally under 100 items).
*   **Compound Multikey Constraint**: You **cannot** create a compound index where more than one field is an array. For example, if both `tags` and `categories` are arrays, indexing `{ "tags": 1, "categories": 1 }` is **blocked** by MongoDB to prevent exponential index growth.
