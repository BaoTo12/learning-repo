# Module 09: Sorting and Pagination

In this module, we will study sorting and pagination operations in the MongoDB Query Language (MQL) using MongoDB Compass. We will cover sorting directions, compound multi-field ordering, and the strict **32MB in-memory sort limit**. We will also compare **Offset Pagination** and **Cursor-based (Keyset) Pagination**, explaining their system trade-offs and how to design high-performance paginated API endpoints.

---

## 1. Operation Reference

In MongoDB Compass, sorting, limiting, and skipping matching documents are configured inside the **Query Options** panel (click the **Options** button next to the Filter bar).

### A. Sorting
#### Description
Specifies the order in which matching documents are returned by the query.

#### Compass Fields
*   **Filter**: `{ "category": "electronics" }`
*   **Sort**: `{ "price": 1 }`

#### Behavior & Mechanics
*   **Sort Directions**: Set a field value to `1` for **Ascending** (A-Z, low-to-high) or `-1` for **Descending** (Z-A, high-to-low).
*   **Compound Sorting**: When sorting by multiple fields, MongoDB evaluates them in the order specified in the sort document. For example, sorting by `{ "age": -1, "name": 1 }` first sorts by age descending, and then sorts users of the same age alphabetically by name ascending.
*   **Compound Index Sort Alignment Rule**: For compound sort keys, the sort directions in the query must match the compound index definition (either in the exact same direction or the exact reverse direction) to utilize the index efficiently.
    *   Suppose you have a compound index: `{ "age": 1, "score": -1 }`.
    *   *Index-Optimized Sorts*:
        *   **Sort**: `{ "age": 1, "score": -1 }` (Matches index exactly)
        *   **Sort**: `{ "age": -1, "score": 1 }` (Reverse of index exactly)
    *   *In-Memory Sorts (Fails Index Alignment)*:
        *   **Sort**: `{ "age": 1, "score": 1 }` (Mixed directions)
        *   **Sort**: `{ "age": -1, "score": -1 }` (Mixed directions)

---

### B. Limit
#### Description
Sets the maximum number of documents the query will return to the client.

#### Compass Fields
*   **Filter**: `{}`
*   **Sort**: `{ "price": 1 }`
*   **Limit**: `5`

#### Behavior & Mechanics
*   **Performance Optimization**: Setting a limit allows WiredTiger to stop scanning documents early once the threshold is reached.
*   **Default Limit**: Entering `0` or leaving the Limit field blank in Compass is equivalent to setting no limit.

---

### C. Skip
#### Description
Instructs the database engine to bypass a specified number of matching documents before returning results.

#### Compass Fields
*   **Filter**: `{ "status": "ACTIVE" }`
*   **Skip**: `20`

#### Behavior & Mechanics
*   **Performance Overhead**: To skip N documents, the database must scan and count N records before returning the next set. As N grows large, query performance degrades significantly (O(N) time complexity).

---

## 2. The 32MB In-Memory Sort Limit

If a query's sort operation cannot use an index, MongoDB must sort the matched documents in memory.

In MongoDB Compass:
*   Navigate to the **Explain Plan** tab.
*   Click **Explain**.
*   If sorting in memory, you will see a `SORT` stage in the visual plan detail instead of a simple `IXSCAN`.
*   **The RAM Restriction**: MongoDB restricts in-memory sorts to a maximum of **32MB of RAM**. If the dataset matching your filter is large and sorting it in RAM exceeds 32MB, the query will immediately fail and throw a `QueryExceededMemoryLimitNoTailable` exception.
*   **Mitigation**: Always create indexes on fields that you sort by. If sorting on `{ age: -1 }`, ensure `age` is indexed to enable an index-ordered scan that requires 0 bytes of sort memory.

---

## 3. Pagination Strategies: Offset vs. Cursor

Applications use pagination to split large datasets into manageable pages.

### A. Offset-based Pagination (Skip & Limit)
##### Mechanics
Skips a calculated number of records to reach the desired page:
`skip = (pageNumber - 1) * pageSize`.

*   **Compass Implementation**: Configure **Limit** to page size (e.g. `10`) and **Skip** to the offset (e.g. `20` for page 3).
*   **Pros**:
    *   Simple to implement.
    *   Supports jumping directly to arbitrary pages (e.g. Page 15).
*   **Cons**:
    *   **O(N) Decay**: To fetch page 10,000 (skip 100,000), WiredTiger must load 100,010 documents from disk/cache, count them, discard the first 100,000, and return 10. This causes massive CPU and disk IO load.
    *   **Data Drift**: If records are inserted or deleted while a user is paginating, the offsets shift, causing items to be duplicated or skipped.

---

### B. Cursor-based Pagination (Keyset Pagination)
##### Mechanics
Filters on a unique, sequential property of the last seen document (e.g. `_id` or a compound index of a timestamp + `_id`) to fetch the next batch.

*   **Pros**:
    *   **O(1) Performance**: Queries start scanning directly from the last seen cursor value. Performance remains constant regardless of page depth.
    *   **No Data Drift**: Insertions or deletions do not shift page boundaries, ensuring consistent feeds.
*   **Cons**:
    *   Cannot jump to arbitrary page numbers (e.g. "Go to Page 7"). Only supports "Next" and "Previous" actions.

#### Keyset Query Blueprint (MongoDB Compass)
Fetch the next page of users sorted by `_id`, where the last seen document ID was `"648d7c9aef100a0012bc4ef1"`:
*   **Filter**:
    ```json
    { "_id": { "$gt": { "$oid": "648d7c9aef100a0012bc4ef1" } } }
    ```
*   **Sort**: `{ "_id": 1 }`
*   **Limit**: `10`

---

## 4. Real-World API Pagination Design

When designing high-throughput REST or GraphQL APIs, return pagination metadata alongside the payload.

### Example API Response
```json
{
  "data": [
    { "_id": "648d7c9aef100a0012bc4ef1", "username": "alice" },
    { "_id": "648d7c9aef100a0012bc4ef2", "username": "bob" }
  ],
  "pagination": {
    "nextCursor": "648d7c9aef100a0012bc4ef2",
    "pageSize": 2,
    "hasNext": true
  }
}
```

Clients fetch the next page by passing the `nextCursor` value as a query parameter:
`/api/users?cursor=648d7c9aef100a0012bc4ef2&limit=2`.
The server decodes this cursor and queries MongoDB using keyset pagination filters.
