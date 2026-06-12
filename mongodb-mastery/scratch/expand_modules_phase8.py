#!/usr/bin/env python3
import os

filepath = r"c:\Users\Admin\Desktop\projects\learning-repo\mongodb-mastery\modules\02-crud-and-querying.md"

advanced_query_guide = """
---

## 15. Advanced Query Formulation Reference Guide

### 1. Complex Array Filtering and Element Projections
When querying documents containing nested array structures, standard projection filters retrieve the *entire* array. To isolate only the specific array elements matching a criteria, you must use either the `$elemMatch` projection operator or modern aggregation projections.

#### Scenario: Fetching Specific Active Transactions
Suppose a customer document contains an array of transaction history:
```json
{
  "_id": 1001,
  "customerName": "Acme Corp",
  "transactions": [
    { "txId": "T101", "amount": 500, "status": "APPROVED" },
    { "txId": "T102", "amount": 1200, "status": "PENDING" },
    { "txId": "T103", "amount": 150, "status": "REJECTED" }
  ]
}
```
If you execute a standard query `find({ "transactions.status": "PENDING" })`, MongoDB returns the entire document including the approved and rejected items. To isolate only the pending transaction, use the `$elemMatch` projection block:
```javascript
// Query projection using $elemMatch
db.customers.find(
  { "transactions.status": "PENDING" },
  { "transactions.$": 1, "customerName": 1 }
);
```
*Note*: The positional projection operator `$` returns only the *first* matching element inside the array. If you need to filter and return multiple elements from an array (e.g. all transactions with amount > 200), use the aggregation framework with the `$filter` operator:
```javascript
db.customers.aggregate([
  { $match: { _id: 1001 } },
  {
    $project: {
      customerName: 1,
      filteredTransactions: {
        $filter: {
          input: "$transactions",
          as: "tx",
          cond: { $gt: ["$$tx.amount", 200] }
        }
      }
    }
  }
]);
```

### 2. Deep Array Updates using Filtered Positional Operators
Updating elements inside nested arrays requires precision. MongoDB provides three update operator patterns:
1.  **Positional Operator (`$`)**: Updates the first matching element identified in the query criteria.
2.  **All-Positional Operator (`$[ ]`)**: Updates all elements inside the array unconditionally.
3.  **Filtered Positional Operator (`$[<identifier>]`)**: Updates only the array elements that match a custom filter defined in the `arrayFilters` parameter list.

#### Scenario: Modifying Price in Nested Product Tiers
Suppose you want to apply a 10% discount to all variants of a product whose inventory level is below 15.
```javascript
// Document structure
{
  "_id": "PROD-102",
  "name": "Heavy Duty Boots",
  "variants": [
    { "sku": "BOOT-S", "price": 100, "stock": 5 },
    { "sku": "BOOT-M", "price": 100, "stock": 20 },
    { "sku": "BOOT-L", "price": 110, "stock": 10 }
  ]
}
```
To update the price of only the small and large variants (where stock is < 15), run:
```javascript
db.products.updateOne(
  { _id: "PROD-102" },
  { $mul: { "variants.$[elem].price": 0.90 } },
  {
    arrayFilters: [ { "elem.stock": { $lt: 15 } } ]
  }
);
```
This query modifies only index 0 and index 2 of the `variants` array in a single atomic write execution, leaving index 1 unchanged.

### 3. Bitwise Query Operators for High-Throughput Access Checks
For systems requiring fine-grained role permissions (like CMS access structures), storing permissions as arrays of strings scales poorly. Instead, compress permission profiles using binary bitmasks.

#### Bitwise Operators:
*   `$bitsAllSet`: Matches documents where all specified bit positions are set to 1.
*   `$bitsAnySet`: Matches documents where at least one of the specified bit positions is set to 1.
*   `$bitsAllClear`: Matches documents where all specified bit positions are set to 0.
*   `$bitsAnyClear`: Matches documents where at least one of the specified bit positions is set to 0.

#### Scenario: Evaluating User Security Permissions
Suppose permission bitmasks are mapped as:
*   Bit 0 (value 1): READ
*   Bit 1 (value 2): WRITE
*   Bit 2 (value 4): EXECUTE
*   Bit 3 (value 8): DELETE

A document stores the user's combined permission bitmask integer value:
```json
{ "_id": "usr-92", "name": "Admin User", "permissions": 11 } // Binary: 1011 (READ, WRITE, DELETE)
```
To query for all users who possess both WRITE (bit 1) and DELETE (bit 3) access, execute:
```javascript
db.users.find({
  permissions: { $bitsAllSet: [ 1, 3 ] } // Matches mask value 11
});
```

### 4. Query Planner Diagnostics for Unindexed Operations
Always verify that queries leverage database indexes. Run explain commands to locate suboptimal executions:
```javascript
db.customers.find({ "transactions.status": "PENDING" }).explain("executionStats");
```
*   `COLLSCAN`: The execution scanned all documents in the collection (Unindexed Query - slow).
*   `IXSCAN`: The execution scanned index keys to locate matching documents (Indexed Query - fast).
*   `FETCH`: The execution retrieved documents from storage using index pointers.
*   `PROJECTION_COVERED`: The execution returned results using only the index key data without loading documents from storage (Most optimized).
"""

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

if "Advanced Query Formulation Reference Guide" not in content:
    new_content = content.strip() + "\\n\\n" + advanced_query_guide.strip() + "\\n"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Successfully appended Advanced Query Guide to Module 2.")
else:
    print("Module 2 already contains Advanced Query Guide.")
