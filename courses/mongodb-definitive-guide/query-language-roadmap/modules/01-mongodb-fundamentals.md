# Module 01: MongoDB Fundamentals & Environment Setup

Welcome to the first module of the MongoDB Query Language (MQL) sub-course. Before writing query documents, you must understand the core concepts of document databases, BSON structures, replica set architectures, and set up your local database sandbox using Docker and GUI clients.

---

## 1. Introduction to MongoDB

### What is MongoDB?
MongoDB is a source-available, cross-platform, document-oriented database classified as a NoSQL database. Rather than storing data in fixed tabular structures of rows and columns, MongoDB stores data in flexible, JSON-like BSON documents.

### Document Database vs. Relational Database (RDBMS)

| Feature | Relational Database (RDBMS) | Document Database (MongoDB) |
| :--- | :--- | :--- |
| **Storage Unit** | Table rows (flat tuples). | Documents (hierarchical BSON records). |
| **Data Schema** | Strict, predefined schema (DDL enforced). | Dynamic, flexible schema (BSON records can vary). |
| **Relationships** | Normalized via foreign keys and joins. | Denormalized via embedded documents and arrays. |
| **Scaling** | Vertical scaling (bigger machines) is standard. | Horizontal scaling (sharding across clusters) is native. |

---

## 2. BSON Structure & Document Components

MongoDB represents documents internally and on disk in a binary format called **BSON** (Binary JSON). BSON extends JSON to support additional data types (such as `Date`, `ObjectId`, `Decimal128`, and binary data) and is optimized for speed of traversal and storage efficiency.

### Core Components:
*   **Databases**: A container that holds collections of documents.
*   **Collections**: A grouping of MongoDB documents (analogous to SQL tables). Collections do not enforce a rigid schema by default.
*   **Documents**: The basic unit of data in MongoDB, represented as key-value pairs (analogous to SQL rows).
*   **Embedded Documents**: BSON objects nested inside other documents, enabling rich hierarchical relationships without joins.
*   **Arrays**: Lists of values or embedded documents stored under a single key.

```json
{
  "_id": { "$oid": "60c72b2f9b1d8b2c8c8b4567" },
  "username": "alice",
  "joinedAt": { "$date": "2026-06-15T12:00:00Z" },
  "profile": {
    "age": 30,
    "city": "Chicago"
  },
  "roles": ["USER", "ADMIN"]
}
```

### Dynamic Schema & Flexibility Trade-offs

#### Advantages:
1.  **Iterative Velocity**: Schema can evolve instantly without running costly database migrations (`ALTER TABLE`).
2.  **Natural Representation**: Matches OOP object models directly (no complex ORM impedance mismatches).
3.  **Heterogeneous Data**: Documents in the same collection can have different fields to support dynamic attributes.

#### Disadvantages:
1.  **Application Validation Burden**: The application layer must handle missing or differently typed fields unless strict JSON Schema validation rules are configured.
2.  **Storage Overhead**: Field names are stored inside every single document, consuming extra RAM and disk space.

---

## 3. MongoDB Architecture Basics

### Databases, Collections, and Documents
MongoDB organizes data logically into databases, which contain collections, which in turn contain documents. 

### High Availability: Replica Sets
To ensure high availability and automatic failover, production MongoDB databases deploy as **Replica Sets**. A replica set is a cluster of database servers containing identical datasets.

*   **Primary Node**: The single node in a replica set that receives all write operations. Writes are recorded in the node's oplog (operations log) and replicated asynchronously to secondaries.
*   **Secondary Nodes**: Nodes that replicate the primary's oplog and apply the operations to their data files. If the primary node crashes, the secondaries hold an election and automatically vote a new primary node.

```
                  [ Client Applications ]
                        |        |
             (Writes)  v        v  (Optional Reads)
                    +-------------+
                    |   Primary   |
                    +-------------+
                       /       \
      (Oplog Sync)   /           \   (Oplog Sync)
                    v             v
             +-------------+     +-------------+
             |  Secondary  |     |  Secondary  |
             +-------------+     +-------------+
```

### Horizontal Scalability: Sharding Overview
When datasets outgrow the storage or CPU capacity of a single replica set, MongoDB scales horizontally using **Sharding**.
*   **Shards**: Replica sets that store a subset of the database's collections.
*   **Routers (`mongos`)**: Intermediary nodes that route client read/write requests to the appropriate shards.
*   **Config Servers**: Replica sets that store cluster metadata and routing rules.

---

## 4. Local Database Setup via Docker Compose

To practice querying, you can use the pre-configured **Practice Sandbox** folder located at [sandbox/](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/sandbox/) which mounts the seeding script and launches MongoDB.

### The `docker-compose.yml` Configuration
Your sandbox folder contains a `docker-compose.yml` file that mounts the [init-db.js](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/sandbox/init-db.js) initialization script into `/docker-entrypoint-initdb.d/`:

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:6.0
    container_name: mql-sandbox-db
    ports:
      - "27017:27017"
    environment:
      - MONGO_INITDB_ROOT_USERNAME=admin
      - MONGO_INITDB_ROOT_PASSWORD=secret_pass
      - MONGO_INITDB_DATABASE=store_db
    volumes:
      - mongo_data:/data/db
      - ./init-db.js:/docker-entrypoint-initdb.d/init-db.js:ro

volumes:
  mongo_data:
```

### Docker Management Commands
Navigate to the [sandbox/](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/sandbox/) directory in your shell:
*   **Start the container and seed the database**: `docker compose up -d`
*   **Verify it is running**: `docker ps`
*   **Reseed the database manually** (if volume already exists):
    ```powershell
    docker exec -i mql-sandbox-db mongosh -u admin -p secret_pass --authenticationDatabase admin < init-db.js
    ```
*   **Stop the container**: `docker compose down`

---

## 5. Connection String URIs & Option Parameters

Clients connect to MongoDB using Connection URIs. The standard format is:

```
mongodb://[username:password@]host1[:port1][,...hostN[:portN]][/[defaultauthdb][?options]]
```

### Option Parameters Reference:
*   `authSource`: Database containing user credentials (e.g. `authSource=admin`).
*   `readPreference`: Read routing mode (`primary`, `primaryPreferred`, `secondary`, `secondaryPreferred`, `nearest`).
*   `w`: Write concern level (`1` or `majority`).
*   `j`: Journal confirmation boolean (`true` or `false`).
*   `tls`: Enforces TLS connection socket encryption (`true`).

---

## 6. GUI Client Integration

### Connecting MongoDB Compass
MongoDB Compass is the official graphical administrative panel.
1. Copy the URI string:
   ```
   mongodb://admin:secret_pass@localhost:27017/?authSource=admin
   ```
2. Open Compass, click **New Connection**, paste the URI, and click **Connect**.

### Connecting DBeaver Enterprise
1. Select **New Database Connection** -> **MongoDB**.
2. Enter Host (`localhost`), Port (`27017`), Database (`store_db`), Username (`admin`), and Password (`secret_pass`).
3. DBeaver will automatically fetch the required Java MongoDB driver classes and connect.

---

## 7. The Raw MQL vs. Relational SQL Paradigm Shift

MongoDB Query Language (MQL) is sent as raw BSON document payloads across the wire. 

```
+------------------+                   +------------------+
|   SQL Database   |                   | MongoDB Database |
+------------------+                   +------------------+
|  Text queries    |                   |  BSON / JSON     |
|  "SELECT..."     |                   |  { "status": ...}|
+------------------+                   +------------------+
```

### CRUD Command Comparison Matrix

| CRUD Operation | Relational SQL Statement | Raw MQL BSON Document / command |
| :--- | :--- | :--- |
| **Create** | `INSERT INTO users (name, age) VALUES ('Alice', 30);` | `{ "insert": "users", "documents": [ { "name": "Alice", "age": 30 } ] }` |
| **Read** | `SELECT * FROM users WHERE status = 'ACTIVE';` | `{ "find": "users", "filter": { "status": "ACTIVE" } }` |
| **Update** | `UPDATE users SET status = 'VERIFIED' WHERE age > 21;` | `{ "update": "users", "updates": [ { "q": { "age": { "$gt": 21 } }, "u": { "$set": { "status": "VERIFIED" } }, "multi": true } ] }` |
| **Delete** | `DELETE FROM users WHERE status = 'INACTIVE';` | `{ "delete": "users", "deletes": [ { "q": { "status": "INACTIVE" }, "limit": 0 } ] }` |

---

## 8. Quick Verification Laboratory

Let's run a raw database command in your environment to verify setup.

### Step A: Open Mongosh Shell in Compass
At the bottom of MongoDB Compass, click on the **_MONGOSH_** tab to open the interactive JavaScript console.

### Step B: Insert Test Documents
Run the following script to create a `products` collection:
```javascript
use store_db;

db.products.insertMany([
  { "sku": "SKU-A", "category": "electronics", "price": 499.99, "inStock": true },
  { "sku": "SKU-B", "category": "furniture", "price": 120.00, "inStock": false },
  { "sku": "SKU-C", "category": "electronics", "price": 25.50, "inStock": true }
]);
```

### Step C: Execute a Raw MQL Find Command
Instead of the javascript wrapper `db.products.find()`, run the raw database command using `db.runCommand()` to verify the query engine resolves BSON filters:
```javascript
db.runCommand({
  "find": "products",
  "filter": {
    "category": "electronics",
    "price": { "$lt": 500.00 },
    "inStock": true
  }
});
```

The database engine returns a BSON cursor result document showing the matched records for `SKU-C`!
