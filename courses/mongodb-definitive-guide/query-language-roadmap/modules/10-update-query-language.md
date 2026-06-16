# Module 10: Update Query Language

In this module, we will explore update operations in the MongoDB Query Language (MQL) using MongoDB Compass. We will cover how to edit documents visually using the Compass interactive document editor, and how updates map to raw database commands using MQL operators (`$set`, `$unset`, `$rename`, `$inc`, `$mul`, `$min`, `$max`, and `$currentDate`), including Upsert configurations.

---

## 1. Document Update Methods in MongoDB Compass

MongoDB Compass provides two main ways to update data:
1.  **Visual Document Editor**: Best for modifying individual documents interactively.
2.  **Raw Database Commands**: Best for executing updates via BSON queries (run in the embedded MongoDB Shell at the bottom of Compass).

---

## 2. Operation Reference

### A. Updating a Single Document

#### Visual Edit Method
*   Find the document using the **Filter** box (e.g., `{ "_id": 101 }`).
*   Hover over the target document and click the **Edit Document** (pencil) icon.
*   Edit the fields directly in the visual panel (JSON or Tree view) or add new fields.
*   Click **Update**.

#### Raw Database Command
To perform this programmatically or via the embedded shell in Compass using raw MQL commands:
```json
{
  "update": "users",
  "updates": [
    {
      "q": { "_id": 101 },
      "u": { "$set": { "status": "VERIFIED" } },
      "multi": false
    }
  ]
}
```

---

### B. Updating Multiple Documents

To update multiple documents at once, you use the raw database command structure with `multi: true`.

#### Raw Database Command
```json
{
  "update": "users",
  "updates": [
    {
      "q": { "status": "PENDING" },
      "u": { "$set": { "status": "SUSPENDED" } },
      "multi": true
    }
  ]
}
```

---

### C. Replacing a Document Entirely

`replaceOne` swaps out the entire matched document structure (excluding `_id`).

#### Visual Edit Method
*   Find the document (e.g. `{ "_id": 101 }`).
*   Click the **Edit Document** (pencil) icon.
*   Delete the unwanted fields or rewrite the document body.
*   Click **Update**.

#### Raw Database Command
```json
{
  "update": "users",
  "updates": [
    {
      "q": { "_id": 101 },
      "u": { "username": "alice_new", "email": "alice@gmail.com" },
      "multi": false
    }
  ]
}
```
*(Note: The update payload `u` for a replacement must contain only plain field-value pairs; it cannot use operators like `$set`).*

---

## 3. Update Operators Reference

When updating documents via raw database commands or the interactive editor, you use MQL update operators to mutate specific fields without replacing the entire document.

### A. Field Mutation Operators

#### 1. `$set`
##### Description
Sets the value of a field in a document. If the field does not exist, it will be created.

##### Raw Update Document
```json
{ "$set": { "status": "VERIFIED", "updatedBy": "admin" } }
```

##### Command Example
```json
{
  "update": "users",
  "updates": [
    {
      "q": { "_id": 101 },
      "u": { "$set": { "status": "VERIFIED", "updatedBy": "admin" } }
    }
  ]
}
```

---

#### 2. `$unset`
##### Description
Deletes a specified field from a document.

##### Raw Update Document
```json
{ "$unset": { "legacyToken": "" } }
```

##### Command Example
```json
{
  "update": "users",
  "updates": [
    {
      "q": { "_id": 101 },
      "u": { "$unset": { "legacyToken": "" } }
    }
  ]
}
```

---

#### 3. `$rename`
##### Description
Updates the name of a field key.

##### Raw Update Document
```json
{ "$rename": { "nickname": "alias" } }
```

##### Behavior & Mechanics
*   **Logical Move**: Can move fields into embedded documents or out of them using dot notation (e.g. `{ "$rename": { "nickname": "profile.alias" } }`).
*   **Unsetting Old Field**: Performs an atomic unset of the old field key and sets the new field key.

##### Command Example
```json
{
  "update": "users",
  "updates": [
    {
      "q": {},
      "u": { "$rename": { "nickname": "alias" } },
      "multi": true
    }
  ]
}
```

---

### B. Numeric & Date Operators

#### 1. `$inc`
##### Description
Increments or decrements a numeric field by a specified value.

##### Raw Update Document
```json
{ "$inc": { "stock": 5, "viewCount": 1 } }
```

##### Behavior & Mechanics
*   **Creation of Fields**: If the field does not exist, `$inc` creates the field and sets it to the specified number.
*   **Negative Values**: Pass a negative number to decrement the field (e.g. `{ "$inc": { "stock": -1 } }`).
*   **Type Constraint**: Only works on numeric BSON types (Double, Int, Long, Decimal). Passing a non-numeric field throws a write error.

##### Command Example
```json
{
  "update": "products",
  "updates": [
    {
      "q": { "sku": "PROD-12" },
      "u": { "$inc": { "stock": 5, "viewCount": 1 } }
    }
  ]
}
```

---

#### 2. `$mul`
##### Description
Multiplies the value of a field by a specified number factor.

##### Raw Update Document
```json
{ "$mul": { "price": 1.10 } }
```

##### Command Example
```json
{
  "update": "products",
  "updates": [
    {
      "q": { "sku": "PROD-12" },
      "u": { "$mul": { "price": 1.10 } }
    }
  ]
}
```

---

#### 3. `$min` / `$max`
##### Description
Updates the field value **only** if the specified value is less than (`$min`) or greater than (`$max`) the current value.

##### Raw Update Document
```json
{ "$max": { "highScore": 950 } }
```

##### Command Example
```json
{
  "update": "users",
  "updates": [
    {
      "q": { "_id": 201 },
      "u": { "$max": { "highScore": 950 } }
    }
  ]
}
```

---

#### 4. `$currentDate`
##### Description
Sets the field value to the current date, either as a BSON Date or a BSON Timestamp.

##### Raw Update Document
```json
{ "$currentDate": { "lastLogin": true, "writeTimestamp": { "$type": "timestamp" } } }
```
*   Setting the value to `true` defaults to a BSON Date.
*   Setting the value to `{ "$type": "timestamp" }` sets it to a BSON Timestamp.

##### Command Example
```json
{
  "update": "users",
  "updates": [
    {
      "q": { "_id": 101 },
      "u": { "$currentDate": { "lastLogin": true, "writeTimestamp": { "$type": "timestamp" } } }
    }
  ]
}
```

---

## 4. Upsert Operations (`upsert: true`)

An **Upsert** is a write option:
*   If a document matches the query filter, MongoDB applies the update operator modifications.
*   If **no** document matches the filter, MongoDB inserts a new document combining the query filter fields and the update operator fields.

### Command Example
Track a product's daily pageview count. If a tracking document for the product and date does not exist, initialize it with a pageview count of `1`:

```json
{
  "update": "pageviews",
  "updates": [
    {
      "q": { "sku": "PROD-A", "date": "2026-06-15" },
      "u": { 
        "$inc": { "pageviews": 1 }, 
        "$set": { "lastAccessed": { "$date": "2026-06-15T11:59:00Z" } } 
      },
      "upsert": true
    }
  ]
}
```
*(Note: We use the canonical BSON date representation `{ "$date": "..." }` for MongoDB Compass JSON inputs).*

#### Inserted Document Structure (on first run):
```json
{
  "_id": { "$oid": "648d7c9aef100a0012bc4ef3" },
  "sku": "PROD-A",
  "date": "2026-06-15",
  "pageviews": 1,
  "lastAccessed": { "$date": "2026-06-15T11:59:00Z" }
}
```
