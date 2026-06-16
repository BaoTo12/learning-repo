# Module 11: Array Updates

In this module, we will explore updating array fields inside BSON documents using MongoDB Compass. While updating scalar fields is straightforward, modifying array elements requires specialized operators to add, remove, and alter elements dynamically. You will learn the mechanics of basic array update operators (`$push`, `$pull`, `$pop`, `$addToSet`), advanced positional update operators (`$`, `$[]`, `$[identifier]`), and how to apply conditional modifications using `arrayFilters`.

---

## 1. Document Update Methods in MongoDB Compass

In MongoDB Compass:
1.  **Visual Document Editor**: Hover over a document in the list view, click the **Edit Document** (pencil) icon, and modify the elements of arrays directly (or add/remove array elements using visual inputs).
2.  **Raw Database Commands**: Run raw MQL update commands (such as the `update` command) inside the **embedded MongoDB Shell** at the bottom of the Compass window.

---

## 2. Core Array Update Operators

MongoDB provides update operators to mutate array values without downloading, modifying, and re-saving the entire array from application code.

### A. `$push` & `$addToSet`
#### Description
*   `$push`: Appends a specified value to the end of an array. It allows duplicate values.
*   `$addToSet`: Appends a specified value to the end of an array **only if the value does not already exist in the array**, treating the array as a set.

#### Raw Update Document
*   **For Push**: `{ "$push": { "tags": "electronics" } }`
*   **For AddToSet**: `{ "$addToSet": { "tags": "clearance" } }`

#### Command Example
```json
{
  "update": "products",
  "updates": [
    {
      "q": { "_id": 101 },
      "u": { "$push": { "tags": "electronics" } }
    }
  ]
}
```

---

### B. `$pull` & `$pop`
#### Description
*   `$pull`: Removes all array elements that match a specified query condition or value.
*   `$pop`: Removes the first or last element of an array (`1` to pop the last element, `-1` to pop the first).

#### Raw Update Document
*   **For Pull**: `{ "$pull": { "tags": "out-of-season" } }`
*   **For Pop (Last Element)**: `{ "$pop": { "tags": 1 } }`

#### Command Example
```json
{
  "update": "products",
  "updates": [
    {
      "q": { "category": "clothing" },
      "u": { "$pull": { "tags": "out-of-season" } },
      "multi": true
    }
  ]
}
```

---

## 3. Advanced Positional Update Operators

When modifying nested objects inside arrays (e.g., updating the price of a specific item in a shopping cart), you must target specific elements inside the array.

### A. The Positional Operator (`$`)
#### Description
Identifies the **first element** in the array that matches the query filter of the update operation.

#### Behavior & Constraint:
*   **Query Link**: You **must** include the array field in the query filter (e.g., `{ "items.sku": "item-abc" }`). The positional operator `$` matches the index of the first array element that satisfies this condition.
*   **Single Match Only**: It only modifies the first matched element, not subsequent elements.

#### Command Example
Update the quantity of the item `"item-abc"` in shopping cart `202` to `5`:
```json
{
  "update": "carts",
  "updates": [
    {
      "q": { "_id": 202, "items.sku": "item-abc" },
      "u": { "$set": { "items.$.qty": 5 } }
    }
  ]
}
```

---

### B. The All Positional Operator (`$[]`)
#### Description
Identifies **all elements** in the array, applying modifications to every element regardless of index or values.

#### Command Example
Increment the count of all ratings in an array by `1` for product `303`:
```json
{
  "update": "products",
  "updates": [
    {
      "q": { "_id": 303 },
      "u": { "$inc": { "ratings.$[]": 1 } }
    }
  ]
}
```

---

### C. The Filtered Positional Operator (`$[identifier]`) & `arrayFilters`
#### Description
Identifies array elements that match the conditions defined inside the `arrayFilters` option array. This allows updating multiple specific elements within the same array in one operation.

#### Command Example
In cart `404`, discount items by 10% if their price is greater than `$100`:
```json
{
  "update": "carts",
  "updates": [
    {
      "q": { "_id": 404 },
      "u": { "$mul": { "items.$[item].price": 0.90 } },
      "arrayFilters": [ { "item.price": { "$gt": 100 } } ]
    }
  ]
}
```

---

## 4. Complex Real-World Example

Let's look at an application catalog tracking store inventory. Each store has an array of stock bins. We want to increment the quantity of a specific bin (`binId: "BIN-2"`) by `50` units, but only if the bin exists and is located at the `"MAIN_WAREHOUSE"`.

### Raw BSON Document structure:
```json
{
  "_id": 999,
  "warehouse": "MAIN_WAREHOUSE",
  "bins": [
    { "binId": "BIN-1", "qty": 100, "status": "OK" },
    { "binId": "BIN-2", "qty": 10, "status": "LOW" },
    { "binId": "BIN-3", "qty": 5, "status": "LOW" }
  ]
}
```

### Raw MQL Update Command:
```json
{
  "update": "inventory",
  "updates": [
    {
      "q": { "_id": 999, "warehouse": "MAIN_WAREHOUSE" },
      "u": { 
        "$inc": { "bins.$[b].qty": 50 },
        "$set": { "bins.$[b].status": "OK" }
      },
      "arrayFilters": [ { "b.binId": "BIN-2" } ]
    }
  ]
}
```
*(Copy-paste this raw command document directly into the embedded MongoDB Shell in Compass).*
