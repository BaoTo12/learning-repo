# Module 14: Aggregation Stages

In this module, we will explore the query and transformation blocks of the Aggregation Framework using MongoDB Compass: **Stages**. Stages process streams of documents sequentially. You will learn the syntax, execution mechanics, and indexing rules for Core Stages (`$match`, `$project`, `$group`, `$sort`, `$limit`, `$skip`, `$count`), Intermediate Transformations (`$addFields`, `$set`, `$unset`), and Data Reshaping Stages (`$replaceRoot`, `$replaceWith`).

---

## 1. Building Aggregation Pipelines in MongoDB Compass

In MongoDB Compass, you build pipelines on the **Aggregation** tab:
1.  Click **Add Stage** to add a new step to the pipeline.
2.  Choose the operator (e.g. `$match`, `$group`) from the dropdown.
3.  Paste the raw BSON query block inside the stage text box.
4.  Observe the live preview panel on the right to see the documents transformed by the stage.

---

## 2. Core Stages Reference

### A. `$match`
#### Description
Filters the document stream to pass only documents matching the specified criteria to the next stage.

#### Compass Input Block
Choose `$match` from the stage dropdown:
```json
{ "status": "ACTIVE" }
```

#### Behavior & Mechanics
*   **Index Utilization**: If `$match` is the **first stage** in the pipeline, it can utilize standard single-field, compound, and multikey indexes. If placed later in the pipeline (after `$group` or `$project`), it forces collection scans.
*   **MQL Syntax Match**: The query syntax inside `$match` is identical to standard read query filters.

---

### B. `$project`
#### Description
Reshapes each document in the stream by including, excluding, or renaming fields, or computing new values using aggregation expressions.

#### Compass Input Block
Choose `$project` from the stage dropdown:
```json
{ 
  "name": 1, 
  "itemTotal": { "$multiply": ["$price", "$quantity"] },
  "_id": 0 
}
```

#### Behavior & Mechanics
*   **Mixing Rule**: Identical to read projections. You cannot mix inclusions and exclusions except for the `_id` field.
*   **Expression Evaluation**: Allows computing values (e.g. `{ "total": { "$multiply": ["$price", "$quantity"] } }`).
*   **Dot Notation**: Supports projecting nested fields: `{ "address.city": 1 }`.

---

### C. `$group`
#### Description
Groups input documents by a specified identifier expression and applies accumulator expressions (e.g. sum, average, push) to the grouped documents.

#### Compass Input Block
Choose `$group` from the stage dropdown:
```json
{
  "_id": "$customerId",
  "totalSpent": { "$sum": "$amount" },
  "orderCount": { "$sum": 1 }
}
```
*(Note: Specify the grouping key as the `_id` field. Set `_id` to `null` to calculate accumulated values across the entire input set as a single group).*

#### Accumulators Reference:
*   `$sum`: Sums up values.
*   `$avg`: Calculates the average.
*   `$min` / `$max`: Tracks minimal or maximal bounds.
*   `$push`: Accumulates values into an array.
*   `$addToSet`: Accumulates unique values into an array (sets).

#### Behavior & Mechanics
*   **Blocking Stage**: `$group` is a blocking stage. It must receive **all** documents from preceding stages before it can calculate groups and yield outputs.
*   **Memory Footprint**: High memory usage. Subject to the 100MB memory limit. Check **Allow Disk Use** in the Aggregation options (gear icon) if the dataset is large.

---

### D. `$sort`
#### Description
Sorts all input documents and passes them to the next stage in the sorted order.

#### Compass Input Block
Choose `$sort` from the stage dropdown:
```json
{ "totalSpent": -1 }
```

#### Behavior & Mechanics
*   **Blocking Stage**: Like `$group`, `$sort` must read the entire input stream before it can yield the sorted result, unless supported by an index at the start of the pipeline.
*   **RAM Limits**: If not supported by an index, the `$sort` stage is restricted to **100MB of RAM**. If it exceeds 100MB, it will error unless **Allow Disk Use** is configured in options.

---

### E. `$limit`
#### Description
Passes the first N documents to the next stage.

#### Compass Input Block
Choose `$limit` from the stage dropdown:
```json
3
```

---

### F. `$skip`
#### Description
Skips the first N documents and passes the remaining documents to the next stage.

#### Compass Input Block
Choose `$skip` from the stage dropdown:
```json
10
```

---

### G. `$count`
#### Description
Counts the number of documents passing through the stage and outputs a single document containing that count.

#### Compass Input Block
Choose `$count` from the stage dropdown:
```json
"activeCount"
```
*(Replacing the stream with a single document: `{ "activeCount": <count> }`).*

---

## 3. Intermediate Transformations

These stages append or remove fields without discarding other fields in the BSON structure.

### A. `$addFields` / `$set`
#### Description
Adds new fields to documents or updates the value of existing fields. `$set` is an exact alias for `$addFields`.

#### Compass Input Block
Choose `$addFields` or `$set` from the stage dropdown:
```json
{
  "isPremium": { "$cond": [ { "$gte": ["$totalSpent", 500] }, true, false ] }
}
```

#### Behavior & Mechanics
*   Unlike `$project`, which requires listing all fields you want to keep, `$addFields` retains all existing fields and simply appends or replaces the specified keys.

---

### B. `$unset`
#### Description
Removes specified fields from documents. It is an alias for using `$project` to exclude fields.

#### Compass Input Block
Choose `$unset` from the stage dropdown:
```json
["tempCache", "internalToken"]
```

---

## 4. Data Reshaping

These stages change the root layout of the output documents.

### A. `$replaceRoot`
#### Description
Promotes an embedded subdocument to the root level, discarding all other fields.

#### Compass Input Block
Choose `$replaceRoot` from the stage dropdown:
```json
{ "newRoot": "$profile" }
```

#### Behavior & Mechanics
*   The expression passed to `newRoot` **must resolve to a BSON object/document**. If it resolves to a string, number, null, or missing path, the stage will immediately throw a runtime exception.
*   *If the input was `{ _id: 1, name: "Alice", profile: { age: 30, city: "Chicago" } }`, the output becomes `{ age: 30, city: "Chicago" }`*.

---

### B. `$replaceWith`
#### Description
A simplified alias for `$replaceRoot`. It takes a document expression directly without requiring the `newRoot` wrapper key.

#### Compass Input Block
Choose `$replaceWith` from the stage dropdown:
```json
"$profile"
```
