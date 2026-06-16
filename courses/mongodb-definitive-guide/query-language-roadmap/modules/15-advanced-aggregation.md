# Module 15: Advanced Aggregation

In this module, we will explore advanced operations in the MongoDB Aggregation Framework using MongoDB Compass. We will cover array deconstruction using `$unwind`, multi-collection queries via `$lookup`, recursive graph traversals with `$graphLookup`, multi-pipeline facets with `$facet`, and the system optimizations required to run complex pipelines efficiently.

---

## 1. Array Processing (`$unwind`)

### Description
Deconstructs an array field from the input documents to output a separate document for each element in the array.

### Compass Input Block
Choose `$unwind` from the stage dropdown:
```json
{
  "path": "$tags",
  "preserveNullAndEmptyArrays": true
}
```

### Behavior & Mechanics
*   **Document Multiplier**: If a document contains an array with 10 elements, `$unwind` will replace it with 10 separate documents. This significantly increases the document stream count.
*   **Memory Impact**: Unwinding large arrays creates high write amplification in memory, which can choke downstream stages like `$group` or `$sort`.
*   **Options**:
    *   `path`: The path of the array field (prefixed with `$` and enclosed in quotes).
    *   `includeArrayIndex` (Optional): The name of a new field to store the element's index position in the original array.
    *   `preserveNullAndEmptyArrays` (Optional): If set to `true`, if the array is missing, null, or empty, `$unwind` will output the document anyway. If `false` (default), the document is discarded.

*(For example, if the input document was `{ _id: 1, tags: ["A", "B"] }`, the output of this stage becomes two documents: `{ _id: 1, tags: "A" }` and `{ _id: 1, tags: "B" }`)*.

---

## 2. Multi-Collection Queries (`$lookup`)

### Description
Performs a left outer join to an unsharded collection in the same database.

### Compass Input Block Options

#### Option 1: Standard Equality Join
Choose `$lookup` from the stage dropdown:
```json
{
  "from": "customers",
  "localField": "customerId",
  "foreignField": "_id",
  "as": "customerDetails"
}
```

#### Option 2: Expressive Join (Custom Subquery Pipeline)
Choose `$lookup` from the stage dropdown:
```json
{
  "from": "customers",
  "let": { "custId": "$customerId" },
  "pipeline": [
    { 
      "$match": { 
        "$expr": { 
          "$and": [
            { "$eq": ["$_id", "$$custId"] },
            { "$eq": ["$tier", "PREMIUM"] }
          ]
        } 
      } 
    }
  ],
  "as": "premiumCustomerDetails"
}
```

### Behavior & Mechanics
*   **Output Array**: `$lookup` always appends the matched documents as an array field in the source document. If no matches are found, it appends an empty array `[]`.
*   **Index Requirement**: **To prevent severe performance degradation, the field specified in `foreignField` (or referenced in `$match` in an expressive join) must have a supporting index in the foreign collection.** Without an index, MongoDB executes a collection scan on the foreign collection for every single document in the pipeline stream.

---

### Comparison: MongoDB `$lookup` vs. SQL Join

| Dimension | MongoDB `$lookup` (Left Outer Join) | SQL Join (`INNER`, `LEFT`, `RIGHT`) |
| :--- | :--- | :--- |
| **Data Shape** | Hierarchical. Matched records are appended as an **array of subdocuments** in the source document. | Flat. Combines fields into a tabular row, repeating elements for one-to-many matches. |
| **Performance** | **Expensive**. Requires index-lookup seeks on a separate collection for each document flowing through the pipeline. | **Optimized**. SQL engines use query planners designed specifically for highly optimized, cached join trees. |
| **Design Intent** | Used primarily for reporting, analytics, or auditing. The schema model should embed frequently accessed data to avoid lookups in operational flows. | Fundamental. Normalization forces tables splits, requiring joins for almost every read query. |

---

## 3. Recursive Relationships (`$graphLookup`)

### Description
Performs a recursive search on a collection to traverse parent-child hierarchies, networks, or graph structures.

### Compass Input Block
Choose `$graphLookup` from the stage dropdown:
```json
{
  "from": "employees",
  "startWith": "$reportsTo",
  "connectFromField": "reportsTo",
  "connectToField": "name",
  "as": "managementChain"
}
```

---

## 4. Multi-Pipeline Operations (`$facet`)

### Description
Processes the same input document stream through multiple parallel aggregation pipelines inside a single stage. This is useful for multi-dimensional search navigation (faceted search).

### Compass Input Block
Choose `$facet` from the stage dropdown:
```json
{
  "priceRanges": [
    { "$bucket": { "groupBy": "$price", "boundaries": [0, 50, 100, 500], "default": "Expensive" } }
  ],
  "categoryCounts": [
    { "$group": { "_id": "$category", "count": { "$sum": 1 } } }
  ]
}
```

### Behavior & Mechanics
*   **Parallel Execution**: The same stream of documents is cloned and sent to each declared sub-pipeline.
*   **Blocking Outputs**: All sub-pipelines must complete before `$facet` outputs a single document containing arrays of results for each key.
*   **Index Limit**: Sub-pipelines inside `$facet` **cannot** use indexes. This is because they run on documents that have already flowed into the `$facet` stage. For maximum speed, place a `$match` stage before `$facet` to narrow down the input document set first.

---

## 5. Pipeline Optimization Best Practices

1.  **Match Early**: Place the `$match` stage as early as possible. Filtering documents early reduces the memory and CPU workload of downstream stages.
2.  **Sort and Limit Early**: Place `$sort` and `$limit` stages before any `$unwind` or `$group` stages to prevent sorting massive datasets in memory.
3.  **Index support**: Ensure fields matching in the first `$match` or `$sort` stage are indexed.
4.  **Projection Pruning**: Use a `$project` stage before `$lookup` or `$facet` to drop fields that are not needed, reducing document sizes in memory.
