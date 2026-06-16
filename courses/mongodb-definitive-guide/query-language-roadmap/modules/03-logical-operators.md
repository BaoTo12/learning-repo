# Module 03: Logical Query Operators

In this module, we will explore logical operators in the MongoDB Query Language (MQL). Logical operators allow you to build complex search logic by combining, nesting, or negating query criteria. We will examine the syntax, execution mechanics, and index scanning behaviors of `$and`, `$or`, `$not`, and `$nor`.

---

## 1. Operator Reference

Logical operators evaluate arrays of expression documents or negate a single criteria expression.

### A. `$and` (Logical AND)
#### Description
Performs a logical `AND` operation on an array of one or more expressions and selects documents that satisfy all the expressions in the array.

#### Syntax
```json
{ "$and": [ { <expression1> }, { <expression2> }, ... { <expressionN> } ] }
```

#### Behavior & Mechanics
*   **Implicit AND vs. Explicit `$and`**:
    *   **Implicit AND**: Separating fields with commas in a query document is automatically evaluated as an `AND` operation (e.g. `{ "status": "ACTIVE", "age": 25 }`).
    *   **Explicit `$and`**: Required when targeting the same field multiple times in a query (e.g. `{ "$and": [ { "price": { "$gt": 10 } }, { "price": { "$lt": 50 } } ] }` - although the shorthand `{ "price": { "$gt": 10, "$lt": 50 } }` is also valid, explicit `$and` is required for combining multiple separate operators or nested criteria).
    *   **Overwriting Keys Constraint**: In JSON, defining the same key twice in an object causes the second definition to overwrite the first (e.g. `{ "price": { "$gt": 10 }, "price": { "$lt": 50 } }` evaluates only as `{ "price": { "$lt": 50 } }`). Use explicit `$and` or combined operator shorthand to avoid this.
*   **Short-Circuit Evaluation**: MongoDB's query engine evaluates array elements sequentially. If an expression evaluates to false, the engine short-circuits and halts evaluating subsequent expressions for that document.
*   **Index Selection**: If multiple fields inside the `$and` array are indexed, MongoDB can use index intersection (`AND_ENTRIES` or `AND_SORTED` stages) or choose the index that is most selective.

#### Examples
Find active users who have premium tiers:
*   **MongoDB Compass Filter**:
    ```json
    {
      "$and": [
        { "status": { "$eq": "ACTIVE" } },
        { "tier": { "$eq": "PREMIUM" } }
      ]
    }
    ```

---

### B. `$or` (Logical OR)
#### Description
Performs a logical `OR` operation on an array of one or more expressions and selects documents that satisfy at least one of the expressions.

#### Syntax
```json
{ "$or": [ { <expression1> }, { <expression2> }, ... { <expressionN> } ] }
```

#### Behavior & Mechanics
*   **Short-Circuit Evaluation**: If a document matches the first clause, the engine immediately matches the document and stops evaluating the rest of the array. Order your `$or` clauses by **highest likelihood of matching** or **most performant index query** to optimize speed.
*   **Index Clause Rules**: The MongoDB query planner evaluates each clause of the `$or` expression as a separate query. **To use indexes for the entire query, every single field/expression inside the `$or` array must have a supporting index.** If even one clause is unindexed, the query planner defaults to a full collection scan (`COLLSCAN`) for the entire operation.
*   **Index Union**: In the explain plan, you will see `SUBPLAN` stages and an `OR` stage combining the index scans of each clause.

#### Examples
Find users who are either in the `ADMIN` role OR have an account balance greater than `1000.00`:
*   **MongoDB Compass Filter**:
    ```json
    {
      "$or": [
        { "role": { "$eq": "ADMIN" } },
        { "balance": { "$gt": 1000.00 } }
      ]
    }
    ```

---

### C. `$not` (Logical NOT)
#### Description
Inverts the effect of a query expression and selects documents that do **not** match the query expression. This includes documents that do not contain the queried field.

#### Syntax
```json
{ "<field>": { "$not": { <expression> } } }
```
*(Note: Unlike other logical operators, `$not` is applied directly to a field, not as a top-level document key).*

#### Behavior & Mechanics
*   **Missing Fields Match**: If a document does not contain the specified field, it matches the `$not` criteria (e.g. `{ "price": { "$not": { "$gt": 50 } } }` will return documents where `price` is not greater than 50 AND documents where `price` is not defined at all).
*   **BSON Type Differences**: `$not` matches values that do not match the expression even if they are of a different BSON type.
*   **Regex Negation**: You can use `$not` to negate regular expressions: `{ "name": { "$not": /^admin/i } }`.
*   **Index Limitations**: In standard setups, queries using `$not` cannot perform efficient index range scans. The query planner must scan the entire index tree or perform a collection scan because the index does not store negation structures.

#### Examples
Find products whose price is NOT greater than `50.00`:
*   **MongoDB Compass Filter**:
    ```json
    { "price": { "$not": { "$gt": 50.00 } } }
    ```

---

### D. `$nor` (Logical NOR)
#### Description
Performs a logical `NOR` operation on an array of one or more query expressions and selects documents that fail all the expressions in the array.

#### Syntax
```json
{ "$nor": [ { <expression1> }, { <expression2> }, ... { <expressionN> } ] }
```

#### Behavior & Mechanics
*   **Behavior on Missing Fields**: The `$nor` operator matches documents even if the fields in the expressions do not exist in the documents. 
    *   Example: `{ "$nor": [ { "status": "DELETED" }, { "role": "ADMIN" } ] }` will return documents where `status` is not `"DELETED"` and `role` is not `"ADMIN"`, and it will *also* return documents that do not contain `status` or `role` fields at all.
*   **Equivalence**: `{ "$nor": [ A, B ] }` is logically equivalent to `{ "$and": [ { "$not": [ A ] }, { "$not": [ B ] } ] }`.
*   **Index Usage**: Just like `$not`, `$nor` queries generally result in collection scans unless paired with other selective, indexed filter conditions.

#### Examples
Find users who are NOT admins AND whose status is NOT `PENDING`:
*   **MongoDB Compass Filter**:
    ```json
    {
      "$nor": [
        { "role": { "$eq": "ADMIN" } },
        { "status": { "$eq": "PENDING" } }
      ]
    }
    ```

---

## 2. Advanced Combined Logic and Systems Patterns

Real-world application criteria require nesting these operators together.

### A. Combining AND and OR
To fetch active premium users, OR normal users who logged in within the last 7 days:
*   **MongoDB Compass Filter**:
    ```json
    {
      "$or": [
        { "status": "ACTIVE", "tier": "PREMIUM" },
        { 
          "tier": "STANDARD", 
          "lastLogin": { "$date": "2026-06-08T00:00:00Z" } 
        }
      ]
    }
    ```

### B. Nested Logical Conditions (E-Commerce Filter System)
Find products that are in the `"electronics"` or `"appliances"` categories, are not from a blocked brand, and are either in stock OR available for preorder:
*   **MongoDB Compass Filter**:
    ```json
    {
      "category": { "$in": ["electronics", "appliances"] },
      "brand": { "$ne": "cheap-brand" },
      "$or": [
        { "inStock": { "$eq": true } },
        { "isPreorder": { "$eq": true } }
      ]
    }
    ```

---

## 3. Performance & Index Optimization Guidelines

> [!IMPORTANT]
> *   **Implicit vs Explicit AND**: The query planner treats implicit AND (comma separated) and explicit `$and` identically. Choose implicit AND by default for cleaner, less nested queries.
> *   **$or Indexing Requirement**: Make sure that every single field referenced in an `$or` expression array has its own individual index (or starts a compound index). If any element is unindexed, the query planner will abort index range scans and scan the entire collection.
