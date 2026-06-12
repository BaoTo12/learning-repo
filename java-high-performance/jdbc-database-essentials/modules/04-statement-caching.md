# Module 04: Statement Lifecycles & Caching

## 1. What Problem This Module Solves
Executing SQL statements involves database compilation overhead:
*   **Compilation Churn**: Every SQL statement received by the database must go through parsing, compilation, and optimization to generate an execution plan. Executing dynamic query strings repeatedly causes CPU compilation churn.
*   **The Cache Eviction Loop**: If your application does not use bind parameters (e.g., sending `WHERE id = 5` and then `WHERE id = 10`), the database treats them as separate queries, rendering statement caches useless and filling memory with single-use execution plans.

This module details the statement compile lifecycle, server-side vs client-side caching, and parameter sniffing.

---

## 2. SQL Statement Lifecycle on Database

When a database receives an SQL query, it executes the following phases:

```
                  [ SQL Query String ]
                           │
                           ▼
                     [ 1. Parser ]         <--- Syntactic & semantic check
                           │
                           ▼
                    [ 2. Optimizer ]       <--- Generates execution plans
                           │
                           ▼ (Selects cheapest cost plan)
                    [ 3. Executor ]        <--- Reads/writes disk or memory pages
                           │
                           ▼
                  [ Return ResultSet ]
```

1.  **Parser**: Validates syntax, verifies table names and columns, and checks user authorization.
2.  **Optimizer**: Calculates cost estimates for access paths (e.g., full-table scan vs index scan) and generates an optimal **Execution Plan**.
3.  **Executor**: Runs the selected execution plan, retrieving data pages from memory buffers or disk.

---

## 3. Server-Side vs Client-Side Statement Caching

To avoid compile overhead, compile plans can be cached at two layers:

### 3.1 Server-Side Statement Caching
The database server caches execution plans in a shared memory region (e.g. Shared Pool in Oracle, Plan Cache in SQL Server). The cache key is the exact SQL string hash.
*   *Requirement*: You must use **Bind Parameters** (e.g., `SELECT * FROM users WHERE id = ?`). Using parameters makes the SQL string identical across requests, allowing subsequent calls to reuse the cached execution plan.

### 3.2 Client-Side Statement Caching
Located inside the application JVM at the JDBC driver or connection pool layer (e.g., HikariCP). 
When an application invokes `connection.prepareStatement(sql)`, the driver checks its local cache. If cached, it returns the existing `PreparedStatement` instance directly, avoiding a network round-trip to register and compile the statement on the database server.

---

## 4. Parameter Sniffing & Bind-Sensitive Plans

While using bind parameters enables plan caching, it introduces a performance risk known as **Parameter Sniffing**:
*   The database optimizer generates an execution plan based on the parameter values passed during the *first compilation* of the query.
*   If the data distribution is highly skewed (e.g., a status flag is `PENDING` for 0.01% of rows and `COMPLETED` for 99.9% of rows), compiling the plan using a `PENDING` parameter value selects an **Index Scan**.
*   The database caches this plan. Subsequent queries running with `COMPLETED` will reuse this Index Scan plan, resulting in poor performance compared to a full-table scan.

```
Data Distribution Skew:
- Status = 'PENDING'   (0.01% of data) ──► Optimal Plan: Index Scan
- Status = 'COMPLETED' (99.9% of data) ──► Optimal Plan: Full Table Scan

Parameter Sniffing Risk:
First compile runs with 'PENDING' ──► Plan Cache stores 'Index Scan'
Next call runs with 'COMPLETED'  ──► Reuses cached 'Index Scan' (extremely slow for 99% data)
```

---

## 5. Configuring Prepared Statement Caching in HikariCP

To enable statement caching in HikariCP and PostgreSQL, define the connection properties on the `DataSource`:

```java
package com.example.jdbc.cache;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import javax.sql.DataSource;

public class StatementCacheConfig {

    public static DataSource createCachedDataSource() {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl("jdbc:postgresql://localhost:5432/jdbc_db");
        config.setUsername("postgres");
        config.setPassword("postgres");

        // 1. Enable client-side driver statement caching
        config.addDataSourceProperty("cachePrepStmts", "true");
        // 2. Set the maximum number of statements to cache per connection
        config.addDataSourceProperty("prepStmtCacheSize", "250");
        // 3. Set the maximum SQL query string length eligible for caching
        config.addDataSourceProperty("prepStmtCacheSqlLimit", "2048");

        return new HikariDataSource(config);
    }
}
```

---

## 6. Common Mistakes and Anti-Patterns
*   **Concatenating SQL Strings**: Building queries via string concatenation (e.g. `"SELECT * FROM users WHERE status = '" + status + "'"`). This exposes the application to SQL injection, evicts other plans from the database cache, and wastes database CPU compiling identical queries.
*   **Caching Dynamic IN Clauses**: Generating dynamic lists of placeholders (e.g., `WHERE id IN (?, ?)` vs `WHERE id IN (?, ?, ?, ?)`). Each list variation is treated as a separate query, filling the plan cache with single-use plans.
    *   *Correction*: Use database arrays (like `ANY(?::int[])` in PostgreSQL) to maintain a static query structure.

---

## 7. Interview Questions

### Q1: Why is string concatenation in SQL queries (e.g., `WHERE id = ` + userId) a performance anti-pattern for database execution plans?
**Answer**: 
String concatenation makes each SQL query string unique (e.g., `WHERE id = 5` vs `WHERE id = 12`). Because database plan caches use the SQL string hash as the lookup key, the optimizer treats these as separate queries.
This forces the database to parse, compile, and generate an execution plan for every single query request, consuming significant database CPU. Additionally, it fills the plan cache memory with single-use plans, evicting active cached plans and degrading performance across the entire system.

### Q2: What is Parameter Sniffing, and how do database engines mitigate it for bind-parameterized execution plans?
**Answer**: 
*   **Parameter Sniffing**: Occurs when the optimizer compiles a parameterized query and uses the values passed in the first execution to generate and cache the execution plan. If data distribution is highly skewed, this cached plan can be highly sub-optimal for subsequent parameter values.
*   **Mitigation**: Modern database engines use several strategies:
    1.  **Plan Guide/Hints**: Forcing a specific index or full-table scan access path.
    2.  **Adaptive Query Processing**: Re-evaluating and compiling a new plan if execution metrics show the cached plan is performing poorly.
    3.  **Recompile Options**: Adding hints (like `OPTION (RECOMPILE)` in SQL Server) to force compilation on every run for queries known to use skewed parameters.
