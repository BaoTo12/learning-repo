# Module 12: Delete Operations

In this module, we will explore delete operations in the MongoDB Query Language (MQL) using MongoDB Compass. Removing data from a database is a critical, high-risk operation. You will learn the syntax, execution mechanics, and indexing requirements for single and multi-document deletes, safe deletion strategies, and the design considerations of the **Soft Delete Pattern** in production environments.

---

## 1. Document Deletion Methods in MongoDB Compass

MongoDB Compass provides two main ways to delete data:
1.  **Visual Document Deletion**: Best for removing individual documents interactively from the list view.
2.  **Raw Database Commands**: Best for executing deletes via BSON queries (run in the embedded MongoDB Shell at the bottom of Compass).

---

## 2. Operation Reference

### A. Deleting a Single Document

#### Visual Deletion Method
*   Find the document using the **Filter** box (e.g., `{ "_id": 101 }`).
*   Hover over the target document and click the **Delete Document** (trash can) icon.
*   Click **Delete** to confirm.

#### Raw Database Command
To perform this programmatically or via the embedded shell in Compass using raw MQL commands:
```json
{
  "delete": "users",
  "deletes": [
    {
      "q": { "_id": 101 },
      "limit": 1
    }
  ]
}
```

---

### B. Deleting Multiple Documents

#### Raw Database Command
```json
{
  "delete": "users",
  "deletes": [
    {
      "q": { "role": "GUEST", "status": "INACTIVE" },
      "limit": 0
    }
  ]
}
```
*(Setting `"limit": 0` instructs the engine to delete all matching documents).*

---

## 3. Query Indexing & Write Concerns for Deletes

### A. The Indexing Requirement
Many developers overlook that **deletes are query operations**. Before the engine can delete a document, it must locate it.
*   **COLLSCAN Risk**: If the filter passed in the delete operation is not supported by an index, the database engine will perform a Collection Scan (`COLLSCAN`). This can lock the collection and saturate storage I/O, degrading performance for concurrent users.
*   **Production Guideline**: Always ensure delete query filters align with selective indexes (e.g. compound or single-field indexes).

---

## 4. Safe Deletion Strategies

To prevent accidental data loss in production, apply these database practices:

1.  **Test Filters with a Read Query first**: Before running a destructive delete command, run a read query using the exact same filter in the Compass Filter box to verify the matched document list and count.
2.  **Apply TTL Indexes**: For automated temporal data cleanup (like expiring user sessions or logs), do not write cron scripts that execute deletes. Configure a native **TTL (Time-To-Live) Index** on a Date field, offloading the delete CPU work to MongoDB's background threads.

---

## 5. The Soft Delete Pattern

In enterprise systems, hard-deleting records is often discouraged due to audit compliance, data recovery requirements, and maintaining relational integrity.

Instead of deleting, you append a boolean flag (e.g., `"isDeleted": true`) and/or a date timestamp (e.g., `"deletedAt": Date`) to the document.

### Example Soft Delete Update (Raw Command)
```json
{
  "update": "users",
  "updates": [
    {
      "q": { "_id": 105 },
      "u": { 
        "$set": { 
          "isDeleted": true, 
          "deletedAt": { "$date": "2026-06-15T12:00:00Z" } 
        } 
      }
    }
  ]
}
```

### Indexing and Query Considerations for Soft Deletes:
1.  **Filter Updates**: Every single find query in your application must now filter out deleted records:
    *   **Filter**: `{ "status": "ACTIVE", "isDeleted": { "$ne": true } }`
2.  **Partial Index Optimization**: Create a **Partial Index** that indexes only active records (configured via the **Indexes** tab in Compass):
    *   **Fields**: `{ "email": 1 }`
    *   **Options**:
        ```json
        { "partialFilterExpression": { "isDeleted": { "$exists": false } } }
        ```
    This reduces B-Tree memory sizes significantly, optimizing covered queries for active users.
