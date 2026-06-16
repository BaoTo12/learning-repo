# Module 16: Aggregation Expressions

In this module, we will explore aggregation expressions in MongoDB using MongoDB Compass. Aggregation expressions are operators that compute, manipulate, and validate field values inside pipeline stages (like `$project`, `$addFields`, `$set`, and `$group`). You will learn the syntax, type behaviors, null-handling mechanics, and systems optimizations for Arithmetic, String, Date, Conditional, Array, Object, and Type Conversion expressions.

---

## 1. Expression Fundamentals

Unlike stages (which partition and filter the stream of documents), **expressions** are evaluated on individual documents to yield a value. 
*   **Field Path Reference**: To reference a document's field value inside an expression, prefix the field name with a dollar sign `$` and wrap it in quotes (e.g., `"$price"`).
*   **System Variables**: Double dollar signs `$$` reference variables defined within the scope of a stage (e.g., `$$ROOT` for the current document, `$$value` in `$reduce`).

To use these expressions in MongoDB Compass, add the corresponding stage type (such as `$addFields` or `$project`) in the **Aggregation** builder, and paste the expression block inside it.

---

## 2. Arithmetic Expressions

Arithmetic expressions perform mathematical operations on numbers.

### A. `$add` / `$subtract`
#### Description
*   `$add`: Adds numbers together, or adds a number and a date (treating the number as milliseconds).
*   `$subtract`: Subtracts one number from another, or subtracts two dates (returning milliseconds difference).

#### Compass Stage Example
Choose `$addFields` from the stage dropdown:
```json
{ "totalPrice": { "$add": ["$price", "$tax", "$shipping"] } }
```

---

### B. `$multiply` / `$divide`
#### Description
*   `$multiply`: Multiplies numbers.
*   `$divide`: Divides two numbers (first argument divided by second).

#### Behavior & Mechanics (Divide-by-Zero)
*   **Exception**: If the divisor (second argument of `$divide`) is `0`, MongoDB throws a `DivideByZero` runtime query exception. Protect divisions using conditional checks (`$cond`).

#### Compass Stage Example
Choose `$addFields` from the stage dropdown:
```json
{ "discountedPrice": { "$multiply": ["$price", 0.90] } }
```

---

## 3. String Expressions

String expressions manipulate character sequences.

### A. `$concat`
#### Description
Concatenates multiple strings into a single string.

#### Behavior & Mechanics (Null Propagation)
*   **Null Rule**: If any argument in `$concat` evaluates to `null` or points to a missing field, the entire `$concat` expression evaluates to `null`. Always wrap optional fields in `$ifNull` default fallbacks before concatenating.

#### Compass Stage Example
Choose `$addFields` from the stage dropdown:
```json
{ "fullName": { "$concat": ["$firstName", " ", { "$ifNull": ["$lastName", ""] }] } }
```

---

### B. `$substrBytes` / `$toUpper` / `$toLower`
#### Description
*   `$substrBytes`: Extracts a substring from a string based on byte index and length.
*   `$toUpper` / `$toLower`: Converts casing.

#### Compass Stage Example
Choose `$addFields` from the stage dropdown:
```json
{ "userCode": { "$toUpper": { "$substrBytes": ["$email", 0, 5] } } }
```

---

## 4. Date Expressions

Date expressions extract fields from BSON Dates or convert formats.

### A. `$dateToString`
#### Description
Converts a BSON Date object to a formatted string representation.

#### Compass Stage Example
Choose `$addFields` from the stage dropdown:
```json
{ "formattedDate": { "$dateToString": { "date": "$createdAt", "format": "%Y-%m-%d" } } }
```

---

### B. `$year` / `$month` / `$dayOfMonth`
#### Description
Extracts numeric calendar components from BSON Dates.

#### Compass Stage Example
Choose `$group` from the stage dropdown:
```json
{ 
  "_id": { 
    "year": { "$year": "$createdAt" }, 
    "month": { "$month": "$createdAt" } 
  }, 
  "count": { "$sum": 1 } 
}
```

---

## 5. Conditional Expressions

Conditional expressions implement logical branches inside pipelines.

### A. `$cond` (If-Then-Else)
#### Description
Evaluates a boolean condition and returns either the `then` expression or the `else` expression.

#### Compass Stage Example
Choose `$addFields` from the stage dropdown:
```json
{ 
  "priceTier": { 
    "$cond": { 
      "if": { "$gte": ["$price", 100] }, 
      "then": "EXPENSIVE", 
      "else": "BUDGET" 
    } 
  } 
}
```

---

### B. `$switch` (Case Selection)
#### Description
Evaluates a list of case expressions. As soon as a case evaluates to `true`, the corresponding `then` value is returned.

#### Compass Stage Example
Choose `$addFields` from the stage dropdown:
```json
{
  "discountRate": {
    "$switch": {
      "branches": [
        { "case": { "$eq": ["$tier", "PLATINUM"] }, "then": 0.20 },
        { "case": { "$eq": ["$tier", "GOLD"] }, "then": 0.10 }
      ],
      "default": 0.05
    }
  }
}
```

---

## 6. Array Expressions

Array expressions manipulate lists in-place.

### A. `$filter`
#### Description
Filters elements from an array returning a subset that matches a boolean condition.

#### Compass Stage Example
Choose `$addFields` from the stage dropdown:
```json
{
  "highRatings": {
    "$filter": {
      "input": "$ratings",
      "as": "rating",
      "cond": { "$gte": ["$$rating", 4] }
    }
  }
}
```

---

### B. `$map` / `$reduce` / `$arrayElemAt`
#### Description
*   `$map`: Transforms every element in an array and returns the new array.
*   `$reduce`: Aggregates array elements into a single scalar value.
*   `$arrayElemAt`: Extracts the element at the specified index position.

#### Compass Stage Example
Choose `$addFields` from the stage dropdown:
```json
{
  "orderTotal": {
    "$reduce": {
      "input": "$items",
      "initialValue": 0,
      "in": { "$add": ["$$value", { "$multiply": ["$$this.price", "$$this.qty"] }] }
    }
  }
}
```

---

## 7. Object Expressions

Object expressions transform BSON documents dynamically.

### A. `$objectToArray` / `$arrayToObject`
#### Description
*   `$objectToArray`: Flattens a document into an array of `{ k: "keyName", v: "value" }` subdocuments. Essential for checking attributes dynamically when keys are unknown.
*   `$arrayToObject`: Reconstructs a document from an array of key-value tuples.

#### Compass Stage Example
Choose `$project` from the stage dropdown:
```json
{ "attributesArray": { "$objectToArray": "$specs" } }
```
*(If specs was `{ weight: 10, color: "red" }`, it yields `[{ k: "weight", v: 10 }, { k: "color", v: "red" }]`)*.

---

### B. `$mergeObjects`
#### Description
Merges multiple documents into a single document.

#### Compass Stage Example
Choose `$addFields` from the stage dropdown:
```json
{ "fullAddress": { "$mergeObjects": ["$billingAddress", "$shippingAddress"] } }
```

---

## 8. Type Conversion Expressions

Type conversions safely cast variables across BSON types.

### A. `$convert`
#### Description
Converts a value to a specified BSON type with customized error handlers and null handlers.

#### Compass Stage Example
Choose `$addFields` from the stage dropdown:
```json
{
  "cleanPrice": {
    "$convert": { 
      "input": "$price", 
      "to": "double", 
      "onError": 0.0, 
      "onNull": 0.0 
    }
  }
}
```

---

### B. `$toString` / `$toInt` / `$toDate`
#### Description
Shorthand conversions. If casting fails (e.g. converting `"not-a-number"` to int), these expressions will throw a hard runtime error, failing the entire query. Always prefer `$convert` if data cleanliness is not guaranteed.

#### Compass Stage Example
Choose `$addFields` from the stage dropdown:
```json
{ "stringId": { "$toString": "$_id" } }
```
