# Module 06: Transactions, Concurrency Control, & Isolation

## 1. What Problem This Module Solves
Managing concurrent transactions securely is the most complex task in relational database engineering:
*   **Race Conditions & Anomalies**: Multiple users modifying the same data concurrently can overwrite each other's updates (lost updates) or base changes on inconsistent data states (write skew).
*   **Performance Bottlenecks**: Solving concurrency issues by locking tables blocks concurrent read and write operations, creating system bottlenecks.
*   **Distributed Complexity**: Coordinating transactions across independent database servers requires complex two-phase commit (2PC) operations that can stall under network partitions.

This module explains how database engines manage transactions, details locking models, and presents a Java implementation of dynamic write/read routing.

---

## 2. Concurrency Control: 2PL vs MVCC

To isolate concurrent transactions, databases use one of two primary concurrency control models:

### 2.1 Two-Phase Locking (2PL)
A pessimistic model that uses physical locks to coordinate access. 
*   **Mechanics**: Readers require Shared (S) locks, and writers require Exclusive (X) locks. Shared locks can coexist, but exclusive locks block all other locks.
*   **Rule**: Once a transaction releases a lock, it cannot acquire any new locks (Two phases: growing and shrinking).
*   **Trade-off**: Readers block writers, and writers block readers, which limits system concurrency under high loads.

### 2.2 Multi-Version Concurrency Control (MVCC)
An optimistic model where modifications create a new version of the row instead of overwriting existing data.
*   **Mechanics**: When a transaction starts, it receives a read-view snapshot of the data. 
*   **Rule**: **Readers do not block writers, and writers do not block readers**. A reader scans older row versions to access a consistent snapshot of the data, while a writer inserts a new row version with an updated transaction ID timestamp.
*   **Trade-off**: Requires background database vacuuming (e.g. `VACUUM` in PostgreSQL) to clean up old, dead row versions.

---

## 3. Transaction Phenomena and Isolation Levels

### 3.1 Concurrency Phenomena

| Phenomenon | Description |
| :--- | :--- |
| **Dirty Write** | Transaction A overwrites an uncommitted value written by Transaction B. |
| **Dirty Read** | Transaction A reads changes made by Transaction B before B commits. |
| **Non-Repeatable Read** | Transaction A reads a row, Transaction B updates it, and A re-reads the row to find a different value. |
| **Phantom Read** | Transaction A executes a range query, Transaction B inserts a new matching row, and A re-runs the query to find new rows. |
| **Read Skew** | Transaction A reads table X and then table Y. Concurrently, Transaction B updates both. A sees Y's update but not X's update. |
| **Write Skew** | Transaction A and B read the same dataset and write conflicting changes back (e.g., checking if total balance > 0 before withdrawing). |
| **Lost Update** | Transaction A and B read a value, increment it, and write it back. One increment is overwritten and lost. |

---

### 3.2 SQL Isolation Levels & Phenomena mapping

| Isolation Level | Dirty Write | Dirty Read | Non-Repeatable Read | Phantom Read | Write Skew |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Read Uncommitted** | Prevented | Allowed | Allowed | Allowed | Allowed |
| **Read Committed** | Prevented | Prevented | Allowed | Allowed | Allowed |
| **Repeatable Read** | Prevented | Prevented | Prevented | Prevented (in PG) | Allowed |
| **Serializable** | Prevented | Prevented | Prevented | Prevented | Prevented |

*Note: In PostgreSQL, Repeatable Read prevents Phantom Reads as well. To prevent Write Skew, you must use the Serializable level (which uses Serializable Snapshot Isolation).*

---

## 4. Dynamic Read-Write Splitting in Java

To balance database workloads, route write transactions to the primary database and read-only transactions to read-replicas. 

This class implements a dynamic routing `DataSource` using Java `ThreadLocal` context routing:

```java
package com.example.jdbc.transactions;

import javax.sql.DataSource;
import java.io.PrintWriter;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.SQLFeatureNotSupportedException;
import java.util.logging.Logger;

public class ReadWriteRoutingDataSource implements DataSource {

    public enum DbType { MASTER, REPLICA }

    // ThreadLocal variable to track current thread's target database type
    private static final ThreadLocal<DbType> CONTEXT = new ThreadLocal<>();

    private final DataSource masterDataSource;
    private final DataSource replicaDataSource;

    public ReadWriteRoutingDataSource(DataSource master, DataSource replica) {
        this.masterDataSource = master;
        this.replicaDataSource = replica;
    }

    public static void setRoute(DbType type) {
        CONTEXT.set(type);
    }

    public static void clearRoute() {
        CONTEXT.remove();
    }

    private DataSource determineTargetDataSource() {
        DbType type = CONTEXT.get();
        if (type == DbType.REPLICA) {
            System.out.println("[Routing] Routing connection query to REPLICA database...");
            return replicaDataSource;
        }
        System.out.println("[Routing] Routing connection query to MASTER database...");
        return masterDataSource;
    }

    @Override
    public Connection getConnection() throws SQLException {
        return determineTargetDataSource().getConnection();
    }

    @Override
    public Connection getConnection(String username, String password) throws SQLException {
        return determineTargetDataSource().getConnection(username, password);
    }

    // --- Standard Delegate Boilerplate Methods ---
    @Override public int getLoginTimeout() throws SQLException { return masterDataSource.getLoginTimeout(); }
    @Override public void setLoginTimeout(int seconds) throws SQLException { masterDataSource.setLoginTimeout(seconds); }
    @Override public PrintWriter getLogWriter() throws SQLException { return masterDataSource.getLogWriter(); }
    @Override public void setLogWriter(PrintWriter out) throws SQLException { masterDataSource.setLogWriter(out); }
    @Override public Logger getParentLogger() throws SQLFeatureNotSupportedException { return masterDataSource.getParentLogger(); }
    @Override public <T> T unwrap(Class<T> iface) throws SQLException { return masterDataSource.unwrap(iface); }
    @Override public boolean isWrapperFor(Class<?> iface) throws SQLException { return masterDataSource.isWrapperFor(iface); }
}
```

Usage:
```java
public void executeWorkflow() {
    try {
        // Route read queries to replica
        ReadWriteRoutingDataSource.setRoute(DbType.REPLICA);
        // execute readOnlyStatement...

        // Route write queries to master
        ReadWriteRoutingDataSource.setRoute(DbType.MASTER);
        // execute writeStatement...
    } finally {
        ReadWriteRoutingDataSource.clearRoute(); // Clean context to prevent leaks
    }
}
```

---

## 5. Common Mistakes and Anti-Patterns
*   **Executing Reads on Master during Read-Only Queries**: Failing to mark transactions as read-only, which routes all read traffic to the primary write node and saturates its CPU.
*   **Leaking ThreadLocal State**: Forgetting to invoke `CONTEXT.remove()` in a `finally` block. This can cause subsequent requests running on that thread to inherit the previous routing context, leading to unexpected database routing.
*   **Long-Running Transactions**: Keeping transactions open while performing external API calls or waiting for user inputs. This keeps database connections leased and locks held, causing pool starvation.

---

## 6. Interview Questions

### Q1: What is the difference between a Lock-Based Serializable isolation level and PostgreSQL's Serializable Snapshot Isolation (SSI)?
**Answer**: 
*   **Lock-Based Serializable**: Uses Two-Phase Locking (2PL). It forces readers to acquire shared locks that block writers, and writers to acquire exclusive locks that block readers, enforcing serial execution by blocking concurrent operations.
*   **Serializable Snapshot Isolation (SSI)**: An optimistic concurrency control model. SSI does not use blocking locks. Transactions execute concurrently on independent data snapshots. 
SSI monitors the execution dependency graph for **read-write conflicts (si-read locks)**. If a cycle is detected that would lead to write skew, the database aborts one of the conflicting transactions during commit, preserving serializability without blocking concurrent requests.

### Q2: What is a "Lost Update" phenomenon, and how do Optimistic and Pessimistic locking prevent it?
**Answer**: 
*   **Lost Update**: Occurs when Transaction A and B read a row concurrently, modify it, and write it back. The last transaction to commit overwrites and loses the update made by the first transaction.
*   **Pessimistic Locking**: Prevents this by executing `SELECT ... FOR UPDATE` during read. This acquires an exclusive lock, forcing Transaction B to wait until Transaction A commits before it can read the row.
*   **Optimistic Locking**: Prevents this using a version column (e.g. `UPDATE table SET val = ?, version = version + 1 WHERE id = ? AND version = ?`). When Transaction B attempts to write, its update fails because the version changed. Transaction B is forced to retry the transaction.
