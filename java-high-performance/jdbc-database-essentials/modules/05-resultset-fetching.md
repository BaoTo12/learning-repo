# Module 05: ResultSet Fetching & Pagination

## 1. What Problem This Module Solves
Fetching datasets from databases incorrectly can quickly lead to memory exhaustion and application degradation:
*   **Memory Bloat**: By default, many JDBC drivers (like MySQL) attempt to pull the entire query result set into Java heap memory at once, risking Out-Of-Memory (OOM) errors for large queries.
*   **Slow Deep Pagination**: Standard offset-based pagination (`LIMIT 20 OFFSET 500000`) becomes slow as the offset increases, because the database must scan and discard all rows prior to the offset.
*   **Inefficient Data Fetching**: Fetching columns that are not needed (using `SELECT *`) increases network serialization sizes and CPU parsing times.

This module details ResultSet property configurations, driver fetch tuning, and high-performance keyset pagination techniques.

---

## 2. ResultSet Configurations

When constructing statements, you configure ResultSet behavior using three properties:

### 2.1 Scrollability
Determines how the cursor moves through results:
*   `TYPE_FORWARD_ONLY` (Default): The cursor can only move forward, row-by-row. This is the fastest and most memory-efficient option.
*   `TYPE_SCROLL_INSENSITIVE`: The cursor can move backward or jump to absolute positions. The ResultSet does not reflect data updates made by other transactions.
*   `TYPE_SCROLL_SENSITIVE`: The cursor can navigate in both directions, and the ResultSet reflects concurrent database modifications.

### 2.2 Changeability
*   `CONCUR_READ_ONLY` (Default): The ResultSet cannot be modified.
*   `CONCUR_UPDATABLE`: Allows updating rows using the ResultSet cursor directly (e.g., `rs.updateString()`, `rs.updateRow()`), which is slow compared to executing SQL statements.

---

## 3. Tuning Driver Fetch Sizes

The **Fetch Size** parameter tells the JDBC driver how many rows to fetch in a single network round-trip. Driver default values vary:

*   **Oracle**: Defaults to **10**. Fetching 10,000 rows requires 1,000 network round-trips. Increasing the fetch size (e.g. to 100 or 500) significantly improves query times.
*   **MySQL**: Defaults to **Integer.MIN_VALUE** or fetches the **entire ResultSet** into memory at once. To stream rows sequentially in MySQL, set the fetch size to `Integer.MIN_VALUE`.
*   **PostgreSQL**: Fetches the **entire ResultSet** into memory by default. To enable row streaming in PostgreSQL, you must **disable auto-commit** and set a positive fetch size:
    ```java
    conn.setAutoCommit(false); // Required for cursor-based streaming in PG
    stmt.setFetchSize(100);    // Stream in chunks of 100
    ```

---

## 4. Pagination Strategies: Offset vs Keyset

```
[ Offset-Based Pagination ] (LIMIT 20 OFFSET 10000)
- Database scans the first 10,000 rows, discards them, and returns the next 20 rows.
- Complexity: O(N) where N is the offset. Very slow for deep pages.

[ Keyset-Based Pagination ] (WHERE id > 10000 LIMIT 20)
- Database jumps directly to the record matching the index using B-Tree lookup.
- Complexity: O(log N). Execution speed remains constant regardless of page depth.
```

### Keyset Pagination (Recommended for High Scale)
Instead of specifying an offset, the client tracks the primary key of the last record returned (e.g., `last_seen_id`). The next query requests records matching this key:
```sql
SELECT id, name, created_at
FROM orders
WHERE id > 10050
ORDER BY id ASC
LIMIT 20;
```
If the sorting column is not unique (e.g., sorting by creation date), you must combine it with a unique identifier to prevent missing records:
```sql
WHERE (created_at = ? AND id > ?) OR (created_at > ?)
```

---

## 5. Implementing Keyset Pagination in Java

This class demonstrates how to implement keyset-based pagination using raw JDBC:

```java
package com.example.jdbc.fetching;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class KeysetPaginationExecutor {

    private static final String DB_URL = "jdbc:postgresql://localhost:5432/jdbc_db";
    private static final String DB_USER = "postgres";
    private static final String DB_PASS = "postgres";

    public static class OrderRecord {
        public int id;
        public double orderValue;
        public int customerId;
    }

    public static List<OrderRecord> fetchNextPage(int lastSeenId, int pageSize) throws SQLException {
        List<OrderRecord> page = new ArrayList<>();
        // Query filters using index match instead of OFFSET
        String sql = "SELECT id, order_value, customer_id FROM orders WHERE id > ? ORDER BY id ASC LIMIT ?";

        try (Connection conn = DriverManager.getConnection(DB_URL, DB_USER, DB_PASS);
             PreparedStatement prstmt = conn.prepareStatement(sql)) {
            
            prstmt.setInt(1, lastSeenId);
            prstmt.setInt(2, pageSize);

            try (ResultSet rs = prstmt.executeQuery()) {
                while (rs.next()) {
                    OrderRecord record = new OrderRecord();
                    record.id = rs.getInt("id");
                    record.orderValue = rs.getDouble("order_value");
                    record.customerId = rs.getInt("customer_id");
                    page.add(record);
                }
            }
        }
        return page;
    }

    public static void main(String[] args) throws SQLException {
        int pageSize = 10;
        int lastSeenId = 0; // Initialize for first page

        System.out.println("Fetching Page 1:");
        List<OrderRecord> page1 = fetchNextPage(lastSeenId, pageSize);
        page1.forEach(o -> System.out.printf(" - Order ID: %d | Value: %.2f\n", o.id, o.orderValue));

        if (!page1.isEmpty()) {
            // Retrieve the ID of the last record to query the next page
            lastSeenId = page1.get(page1.size() - 1).id;
        }

        System.out.println("\nFetching Page 2:");
        List<OrderRecord> page2 = fetchNextPage(lastSeenId, pageSize);
        page2.forEach(o -> System.out.printf(" - Order ID: %d | Value: %.2f\n", o.id, o.orderValue));
    }
}
```

---

## 6. Common Mistakes and Anti-Patterns
*   **Neglecting Fetch Size Limitations**: Running massive queries on PostgreSQL or MySQL with default fetch sizes. This can load millions of rows into JVM memory at once, triggering high GC activity or OOM exceptions.
*   **Using `LIMIT OFFSET` for API Pagination**: Exposing offset-based pagination in public web APIs. If users or scraping bots query deep pages, the database will experience high CPU and I/O load.
*   **Overfetching Columns**: Using `SELECT *` in queries to fetch all table columns, including large binary structures (like JSON or text fields), when the application only needs to read a few identifier fields.

---

## 7. Interview Questions

### Q1: Why does deep pagination using `OFFSET` (e.g., `LIMIT 20 OFFSET 500000`) perform poorly in relational databases?
**Answer**: 
Relational databases store records sequentially in pages on disk, using B-Tree indexes. When executing `LIMIT 20 OFFSET 500000`, the database optimizer cannot jump directly to row 500,000. 
It must scan the index, read the data pages, and parse the first 500,000 rows in memory before discarding them and returning the target 20 rows. As the offset increases, the query wait times and server I/O usage scale linearly ($O(N)$), degrading performance.

### Q2: Why is disabling auto-commit mandatory when configuring a custom fetch size in the PostgreSQL JDBC driver?
**Answer**: 
By default, PostgreSQL runs in auto-commit mode, executing each statement inside an isolated, short-lived transaction. To support row streaming (fetching chunks of data sequentially), the driver must create a server-side cursor. 
PostgreSQL only allows cursors to exist within an active transaction block. If auto-commit is enabled, the transaction closes immediately after the query starts, which prevents the driver from holding the cursor open to fetch subsequent chunks. Disabling auto-commit keeps the transaction active, allowing row streaming.
