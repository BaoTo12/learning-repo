# MongoDB MQL Practice Sandbox

This sandbox provides a fully configured local MongoDB environment pre-seeded with 470 documents. The datasets align exactly with the schema designs, indexes, aggregates, updates, and transactions described in Modules 2 through 19 of the sub-course.

---

## 📂 Sandbox Contents

*   [docker-compose.yml](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/sandbox/docker-compose.yml): Spins up a MongoDB 6.0 container and mounts the seeding script.
*   [init-db.js](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/mongodb-definitive-guide/query-language-roadmap/sandbox/init-db.js): A database initialization script that creates the `store_db` database and seeds it with:
    *   **50 users** (in `users` collection) with nested addresses, status, and soft-delete fields.
    *   **100 products** (in `products` collection) with ratings arrays and dynamic specs.
    *   **300 orders** (in `orders` collection) containing arrays of items and amounts.
    *   **10 inventory items** (in `inventory` collection) for array-filtering exercises.
    *   **10 employees** (in `employees` collection) with reporting relationships to test recursive queries.

---

## 🚀 How to Run and Seed with Docker

### Scenario A: Starting Fresh (First-Time Startup)
If you do not have any existing volumes for this database, the database image will automatically detect and execute the initialization script on startup.

1.  Open your terminal and navigate to this sandbox folder:
    ```powershell
    cd courses/mongodb-definitive-guide/query-language-roadmap/sandbox
    ```
2.  Start the container in the background:
    ```powershell
    docker compose up -d
    ```
3.  Wait a few seconds for the seeding to complete. You can verify it by checking the logs:
    ```powershell
    docker logs mql-sandbox-db
    ```

---

### Scenario B: Reseeding / Volume Already Exists
If you have already started the container once, the automatic init script **will not run again** because the data volume is not empty. To reset and reseed the data, execute the script manually inside the running container:

Run this command directly from your host machine:
```powershell
docker exec -i mql-sandbox-db mongosh -u admin -p secret_pass --authenticationDatabase admin < init-db.js
```
*(This command streams the `init-db.js` file into the container's shell interpreter, dropping the old collections and regenerating the fresh dataset).*

---

## 🛠️ Connecting GUI Clients

### 1. MongoDB Compass
1.  Open MongoDB Compass.
2.  Click **New Connection**.
3.  Paste the following connection string:
    ```
    mongodb://admin:secret_pass@localhost:27017/?authSource=admin
    ```
4.  Click **Connect**.
5.  Select the **`store_db`** database from the left-hand navigation pane to browse the seeded collections.

### 2. Embedded MongoDB Shell (Mongosh)
If you prefer running command queries, open the **_MONGOSH_** drawer at the bottom of the Compass window and type:
```javascript
use store_db;
```

---

## 🧹 Tearing Down
To stop the sandbox and free up resources:
```powershell
docker compose down
```

To delete the container and **erase all data/volumes** (for a clean slate next time):
```powershell
docker compose down -v
```
