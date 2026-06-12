# Module 08: JPA Concurrency & Explicit Locking

## 1. What Problem This Module Solves
In high-throughput concurrent environments, coordinating data modifications is critical:
*   **The Lost Update Phenomenon**: Two transactions read a row concurrently, modify different fields, and save their changes. The transaction that commits last overwrites and loses the modifications made by the first transaction.
*   **Thread Starvation via Pessimistic Locks**: Locking rows using database write locks (`SELECT ... FOR UPDATE`) blocks concurrent read and write operations, which can starve thread pools under heavy loads.
*   **Long-Running Transaction Deadlocks**: Holding database locks open while waiting for external services to respond can cause database deadlocks.

This module details optimistic locking (versioned and versionless), explicit pessimistic locking, lock timeouts, and conflict resolution techniques.

---

## 2. Optimistic Locking: Implicit & Versionless

Optimistic locking assumes conflicts are rare. It validates that no other transaction has modified the data before committing changes.

### 2.1 Implicit Versioned Locking (Standard)
Enforce optimistic locking by adding a version column annotated with `@Version` (typically an integer or timestamp) to your entity:

```java
@Entity
public class Account {
    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE)
    private Long id;

    private double balance;

    @Version
    private int version; // Incremented automatically by Hibernate on updates
}
```

When updating, Hibernate executes:
```sql
UPDATE account SET balance = 150.00, version = 2 WHERE id = 1 AND version = 1;
```
If another transaction modified the row concurrently, the version will be `2`, the update count will return `0`, and Hibernate will throw an `OptimisticLockException`.

### 2.2 Versionless Optimistic Locking (`OptimisticLockType.DIRTY`)
If you cannot add a version column to the database schema, configure Hibernate to perform versionless optimistic locking:

```java
@Entity
@DynamicUpdate
@OptimisticLocking(type = OptimisticLockType.DIRTY)
public class LegacyAccount {
    @Id
    private Long id;
    private double balance;
    private String holderName;
}
```

When updating the balance, Hibernate executes:
```sql
UPDATE legacy_account SET balance = 150.00 WHERE id = 1 AND balance = 100.00;
```
It compares the current dirty values in the `WHERE` clause to verify that the modified column has not been updated since it was loaded.

---

## 3. Explicit Lock Modes in JPA

JPA provides explicit lock modes to coordinate access dynamically:

| Lock Mode Type | Database SQL Mechanism | Concurrency Impact | Use Case |
| :--- | :--- | :--- | :--- |
| **`OPTIMISTIC`** | Validates the version column at the end of the transaction. | High concurrency. | Detects if a read row was updated by another transaction before commit. |
| **`OPTIMISTIC_FORCE_INCREMENT`** | Increments the version column on commit, even if the entity was only read. | High concurrency. | Prevents write skew when updating child records. |
| **`PESSIMISTIC_READ`** | Executes `SELECT ... FOR SHARE`. | Readers block writers; writers block readers. | Acquires a shared lock to prevent concurrent modifications. |
| **`PESSIMISTIC_WRITE`** | Executes `SELECT ... FOR UPDATE`. | Blocks all concurrent read and write locks. | Acquires an exclusive write lock to serialize updates. |
| **`PESSIMISTIC_FORCE_INCREMENT`** | Executes `SELECT ... FOR UPDATE NOWAIT` and increments version. | Blocks all concurrent locks. | Serializes access and forces version updates. |

---

## 4. Configuring Pessimistic Lock Timeouts

Pessimistic locks block other threads indefinitely by default, which can cause connection pool starvation. You should configure a **Lock Timeout** to abort blocked calls early:

```java
package com.example.jpa.locking;

import jakarta.persistence.EntityManager;
import jakarta.persistence.LockModeType;
import jakarta.persistence.PersistenceContext;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.Map;

@Service
public class BookingService {

    @PersistenceContext
    private EntityManager entityManager;

    @Transactional
    public void reserveSeat(Long seatId) {
        // Configure lock timeout to 2000 milliseconds (2 seconds)
        Map<String, Object> hints = Map.of(
            "javax.persistence.lock.timeout", 2000
        );

        // Fetch seat using exclusive write lock and timeout hint
        SeatEntity seat = entityManager.find(
            SeatEntity.class, 
            seatId, 
            LockModeType.PESSIMISTIC_WRITE, 
            hints
        );

        if (!seat.isAvailable()) {
            throw new IllegalStateException("Seat is already reserved");
        }
        seat.setAvailable(false);
    }
}
```

---

## 5. Common Mistakes and Anti-Patterns
*   **Pessimistic Locking during User Think-Time**: Acquiring a pessimistic database lock, sending a page to the user, and waiting for them to click "Submit". This keeps the database lock active, blocking other users and starving connection pools. Use **Optimistic Locking** instead.
*   **Forgetting Lock Timeouts**: Omitting lock timeouts on pessimistic locks. If the database locks a row, competing threads will block indefinitely, causing application threads to hang.

---

## 6. Interview Questions

### Q1: What is the "Write Skew" anomaly, and how does `LockModeType.OPTIMISTIC_FORCE_INCREMENT` prevent it?
**Answer**: 
*   **Write Skew**: Occurs when two transactions read the same data, make updates based on it, and commit. For example: two doctors query the database to verify if at least one doctor remains on call. Both see that two doctors are active, and both submit requests to log off concurrently. Both transactions commit, leaving zero doctors on call.
*   **Force Increment Prevention**: To prevent this, query the on-call status using `LockModeType.OPTIMISTIC_FORCE_INCREMENT`. When Transaction A reads the active list, Hibernate forces a version increment on the parent scheduling record. When Transaction B attempts to commit, its version check fails because Transaction A already incremented the version, preventing the write skew.

### Q2: What is the mechanical difference between `LockModeType.PESSIMISTIC_READ` and `LockModeType.PESSIMISTIC_WRITE` on a PostgreSQL database?
**Answer**: 
*   `PESSIMISTIC_READ` executes a `SELECT ... FOR SHARE` statement under the hood. It acquires a shared lock that allows other transactions to read the row but blocks them from modifying it.
*   `PESSIMISTIC_WRITE` executes a `SELECT ... FOR UPDATE` statement. It acquires an exclusive lock, blocking other transactions from updating, deleting, or acquiring shared/exclusive locks on the row until the transaction commits.
