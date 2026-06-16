# Module 06: Embedded Document Queries

In this module, we will explore querying nested and embedded documents in the MongoDB Query Language (MQL). The ability to embed documents inside other documents is a core advantage of MongoDB's document model. We will cover path traversal using Dot Notation, compare it to exact subdocument matching, explain how to index nested structures, and analyze the architectural trade-offs of embedding versus referencing.

---

## 1. Querying Nested Documents (Dot Notation vs. Exact Match)

MongoDB provides two methods for querying nested documents: Dot Notation and Exact Subdocument Matching.

### A. Dot Notation (Recommended)
#### Description
Navigates the nested hierarchy of a document by linking parent and child keys with a dot (`.`).

#### Syntax
```json
{ "parentField.childField": <value> }
```
> [!IMPORTANT]
> When using Dot Notation in a query, **you must wrap the entire path string in double quotes** (e.g. `"address.city"`). Omitting the quotes causes a JSON compilation syntax error.

#### Behavior & Mechanics
*   **Selective Match**: Only checks the specified child field. All other fields in the parent object are ignored.
*   **Order Independence**: Since it targets a specific path, it is not affected by BSON key order.
*   **Deep Traversal**: Can traverse through multiple levels of nesting recursively (e.g. `"company.department.manager.name"`).

#### Examples
Find users living in the city of `"Chicago"`:
*   **MongoDB Compass Filter**:
    ```json
    { "address.city": { "$eq": "Chicago" } }
    ```

---

### B. Exact Subdocument Match
#### Description
Compares the entire embedded document against a reference object.

#### Syntax
```json
{ "parentField": { "childField1": <value1>, "childField2": <value2> } }
```

#### Behavior & Mechanics
*   **Brittle & Order-Sensitive**: The query is highly restrictive. Keys inside the subdocument must match the database's schema **exactly and in the same order**.
    *   If a document has `{ "address": { "city": "Chicago", "zip": "60601" } }`, a query for `{ "address": { "zip": "60601", "city": "Chicago" } }` (swapped fields) **will not match**.
    *   If a new field is added to the subdocument (e.g. `state: "IL"`), the query will fail to find it because it is no longer an exact match.
*   **Recommendation**: Avoid exact subdocument matching in production applications. Always prefer **Dot Notation** to navigate nested fields.

#### Examples
Find users whose address matches the specified subdocument exactly:
*   **MongoDB Compass Filter**:
    ```json
    { "address": { "city": "Chicago", "zip": "60601" } }
    ```

---

## 2. Deeply Nested Structures

MongoDB does not enforce nesting limits, allowing objects to contain sub-objects down to maximum BSON constraints.

### Example: Nested Corporate Structure
Consider this document layout:
```json
{
  "_id": 501,
  "employee": "John Doe",
  "organization": {
    "division": {
      "department": {
        "name": "Engineering",
        "code": "ENG-402"
      }
    }
  }
}
```

To locate this document by department code:
*   **MongoDB Compass Filter**:
    ```json
    { "organization.division.department.code": "ENG-402" }
    ```

---

## 3. Indexing Nested Fields

You can index embedded fields exactly like root-level fields to avoid collection scans.

### Defining Nested Indexes in MongoDB Compass
1. Navigate to the **Indexes** tab inside your collection view in MongoDB Compass.
2. Click **Create Index**.
3. Under **Fields**, specify:
   *   *Field*: `address.city`
   *   *Type*: `1` (Ascending)
4. Click **Create Index**.

### Behavior & Mechanics
*   **Point & Range Scans**: When filtering on `{ "address.city": "Chicago" }`, the query planner uses this index to perform a standard index range scan (`IXSCAN`).
*   **Compound Indexes on Nested Paths**: You can create compound indexes mixing root-level and nested fields:
Specify multiple fields in the **Create Index** form, for example setting `status: 1` as the first field and `address.city: 1` as the second field.

---

## 4. Architectural Trade-offs: Embedding vs. Referencing

When designing MongoDB schemas, you must decide whether to nest data (Embedding) or split it across collections using unique identifier links (Referencing).

| Dimension | Embedding (Denormalized) | Referencing (Normalized) |
| :--- | :--- | :--- |
| **Data Structure** | Co-located subdocuments in a single collection. | Separate collections linked by `_id` references. |
| **Read Performance** | **High**. Single seek retrieves the entire record. No joins. | **Medium**. Requires multiple queries or `$lookup` aggregation stages. |
| **Write Atomicity** | **Atomic**. Updates to nested objects are atomic at the single-document level. | **Complex**. Requires transactions to update both collections. |
| **Data Size Limits** | Limited by the **16MB BSON size limit** for a single document. | Unbounded. Can scale indefinitely by appending referenced records. |
| **Schema Integrity** | Prone to update anomalies if duplicate data is nested. | Normalization prevents duplicate data anomalies. |

---

## 5. Schema Design Best Practices

*   **Embed when**:
    *   The relationship is one-to-one (e.g. User and Profile).
    *   The relationship is one-to-few/bounded (e.g. Product and Specifications, Order and Order Items).
    *   The data is read-heavy and updated infrequently.
*   **Reference when**:
    *   The relationship is one-to-many unbounded (e.g. Logins or Bank Transactions).
    *   The data needs to be queried independently.
    *   Embedding would cause documents to exceed the 16MB limit.
