# Module 03: High-Performance Batch Processing

## 1. What Problem This Module Solves
Inserting or updating large datasets row-by-row is a major performance bottleneck:
*   **Network Round-Trip Latency**: Inserting 10,000 rows individually requires 10,000 separate network round-trips between the application and database. Even with a low network ping of 1ms, this adds 10 seconds of latency.
*   **Disabled Batching via Identity Columns**: Using auto-increment identity columns (`GenerationType.IDENTITY`) forces the database to assign IDs during row insert. The JDBC driver must execute each insert statement immediately to retrieve the generated ID, disabling JDBC batching.

This module details how to write batch operations using prepared statements, optimize batch sizes, and use sequence-based ID generators to enable batching.

---

## 2. Statement Batching vs PreparedStatement Batching

### 2.1 Statement Batching (Avoid in Production)
Using `Statement.addBatch(String sql)` allows you to bundle different SQL commands. However, the driver must parse and compile each SQL string individually, which prevents optimization and exposes the system to SQL injection vulnerabilities.

### 2.2 PreparedStatement Batching (Recommended)
`PreparedStatement` uses a pre-compiled SQL template. You bind parameters and add batches in a loop. The database parses the SQL template once, compiles it, and executes the batch parameters in a single round-trip.

```
Individual Inserts (10 Network Round-trips):
App ──► INSERT (Row 1) ──► DB  |  App ──► INSERT (Row 2) ──► DB ...

Batched Inserts (1 Network Round-trip):
App ──► [ Batch: INSERT Row 1, Row 2, Row 3 ... Row 10 ] ──► DB
```

---

## 3. How Auto-Generated Keys Affect Batching

Selecting the right primary key generation strategy determines whether JDBC statement batching is possible.

### 3.1 Identity Columns (Batching Disabled)
With identity columns (e.g. `BIGSERIAL` in PostgreSQL, `AUTO_INCREMENT` in MySQL), the database generates the key during insertion. 
The JDBC driver must execute each `INSERT` statement immediately to retrieve the generated key (using `Statement.RETURN_GENERATED_KEYS` or `RETURNING` clauses) so that the application has the ID of the persisted object. This requirement forces the driver to bypass batching and execute inserts row-by-row.

### 3.2 Sequences (Batching Enabled)
Database sequences are independent generators. The JDBC driver can query the sequence to allocate a block of IDs in a single round-trip (e.g. fetching 50 IDs at once) and assign them to the objects in memory. 
Because the application already knows the IDs, the JDBC driver can batch the `INSERT` statements together and execute them in a single network round-trip.

---

## 4. PostgreSQL Batch Optimization Config

In PostgreSQL, the JDBC driver does not optimize batch inserts by default; it still transmits each insert statement in the batch as a separate network protocol message.
To merge multiple inserts into a single bulk insert statement at the driver layer, you must enable `rewriteBatchedInserts` in your connection properties:

```properties
# Add this property to your JDBC URL connection string
jdbc:postgresql://localhost:5432/jdbc_db?reWriteBatchedInserts=true
```

This rewrite transforms:
```sql
INSERT INTO orders (id, total) VALUES (1, 100);
INSERT INTO orders (id, total) VALUES (2, 200);
```
into:
```sql
INSERT INTO orders (id, total) VALUES (1, 100), (2, 200);
```
This reduces database processing and network packet overhead.

---

## 5. Implementing High-Performance Batching in Java

This class demonstrates how to execute batch updates using a prepared statement, handle auto-generated keys, and manage transactional commits:

```java
package com.example.jdbc.batch;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;

public class BatchUpdateExecutor {

    private static final String DB_URL = "jdbc:postgresql://localhost:5432/jdbc_db?reWriteBatchedInserts=true";
    private static final String DB_USER = "postgres";
    private static final String DB_PASS = "postgres";

    public static void executeBatchInsert(int totalRecords, int batchSize) {
        String sql = "INSERT INTO orders (id, order_value, customer_id) VALUES (?, ?, ?)";

        try (Connection conn = DriverManager.getConnection(DB_URL, DB_USER, DB_PASS)) {
            // 1. Disable auto-commit to run batching within a single transaction
            conn.setAutoCommit(false);

            try (PreparedStatement prstmt = conn.prepareStatement(sql)) {
                for (int i = 1; i <= totalRecords; i++) {
                    prstmt.setInt(1, i);             // ID (allocated from sequence pre-fetch)
                    prstmt.setDouble(2, i * 12.5);    // order_value
                    prstmt.setInt(3, 101);            // customer_id

                    // Add parameters to the batch
                    prstmt.addBatch();

                    // Execute and commit in chunks to avoid memory bloat
                    if (i % batchSize == 0) {
                        prstmt.executeBatch();
                        conn.commit(); // Commit batch transaction segment
                    }
                }

                // Execute and commit remaining records
                prstmt.executeBatch();
                conn.commit();
                System.out.println("Batch execution successfully completed.");

            } catch (SQLException ex) {
                conn.rollback(); // Rollback transaction on failure
                throw ex;
            }

        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        // Execute 10,000 batch inserts in chunks of 50
        executeBatchInsert(10000, 50);
    }
}
```

---

## 6. Common Mistakes and Anti-Patterns
*   **Forgetting to Disable Auto-Commit**: Leaving auto-commit enabled (`setAutoCommit(true)`) during batch execution. This forces the database to open and commit a separate transaction for every batch chunk, causing high disk write and transaction log serialization overhead.
*   **Unbounded Batch Sizes**: Setting a massive batch size (e.g. 50,000 statements in a single batch). This can consume all available Java heap memory and exhaust database sort/join buffers. Use a standard batch size between **50 and 100**.

---

## 7. Interview Questions

### Q1: Why does using `GenerationType.IDENTITY` for database primary keys prevent JDBC and JPA/Hibernate from executing batch inserts?
**Answer**: 
JDBC batching relies on buffering SQL statements in memory and executing them in a single network round-trip. When using `GenerationType.IDENTITY`, the ID is generated by the database during the insert operation. 
To retrieve this generated ID and assign it to the entity object in memory, the JDBC driver must execute the `INSERT` statement immediately (so the database can generate and return the ID). Since the driver cannot wait until the batch is executed to obtain these IDs, it must bypass batching and execute each insert statement individually.

### Q2: What is the purpose of `reWriteBatchedInserts=true` in the PostgreSQL JDBC driver connection properties?
**Answer**: 
By default, when you execute a JDBC batch insert, the PostgreSQL driver sends each statement in the batch as a separate network protocol message to the database server.
Setting `reWriteBatchedInserts=true` tells the PostgreSQL JDBC driver to intercept the batch and rewrite the individual `INSERT` statements into a single, multi-row insert statement (e.g., `INSERT INTO table (x) VALUES (1), (2), (3)`). This reduces network packet overhead, cuts database parsing time, and improves insertion throughput by **2x to 3x**.
