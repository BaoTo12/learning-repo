# Module 11: Final Capstone Project — Resilient Distributed Financial Ledger

Welcome to the **Final Capstone Project** for CS-509. 

Over the past ten modules, we have built the theoretical and practical foundations of transaction systems, from local JTA/JPA boundaries, to two-phase commits, consensus engines, eventual consistency CRDTs, Sagas, logical clocks, exactly-once messaging, and fault-tolerance boundaries.

In this capstone project, you will design and implement a **Distributed Financial Ledger**. You will coordinate multiple services to guarantee that financial ledger records remain consistent, even in the presence of network partitions, database crashes, and duplicate events.

---

## 1. Capstone Architecture Overview

A financial ledger must guarantee absolute consistency. The fundamental equation of double-entry bookkeeping states that the sum of all debits must equal the sum of all credits, and the balance of an account must always equal the sum of its ledger transactions.

```
                              Capstone Architecture
                              
                                [ API Gateway ]
                                       |
                     +-----------------+-----------------+
                     |                                   |
                     v                                   v
        [ Account Balance Service ]             [ Ledger Audit Service ]
                     |                                   |
            (Locks with Redlock)                 (Reads Kafka Events)
                     |                                   |
                     v                                   v
             [ balance_db ]                      [ ledger_audit_db ]
             (Outbox Table)
                     |
            (Asynchronous Stream)
                     |
                     v
             [ Kafka Broker ] ---------------------------+
```

Our system is composed of:
1.  **Account Balance Service**: Manages customer account balances. To prevent race conditions, it acquires a **Distributed Lock** (simulating Redis Redlock) before updating balances. It writes updates and transactional **Outbox** events in a single database transaction.
2.  **Ledger Audit Service**: Consumes events from the Kafka broker and writes journal entries to its audit database.
3.  **Reconciliation Engine**: A background daemon that audits consistency. It queries both services, compares the sum of balances to the sum of journal records, and verifies integrity.

---

## 2. Capstone Design Decisions & Trade-offs

### Saga with Escrow Pattern vs. 2PC/XA
For a high-volume banking application, executing transfers via 2PC/XA across databases results in lock contention and timeouts. Instead, we use a Saga with an **Escrow Lock**:
*   *Phase 1*: Account Service checks funds and moves the transfer amount to a `PENDING_DEBIT` bucket.
*   *Phase 2*: Payment Service charges the downstream processor.
*   *Phase 3*: Account Service completes the debit or rolls back by releasing the escrow.
This isolates the account state without locking rows across multiple seconds.

---

## 3. Capstone Implementation: Core Ledger Engine

Let's write the complete, compile-grade implementation of the **Distributed Financial Ledger** in Java 21, containing the lock synchronization, outbox event generation, and core service components.

First, let's define our ledger records:

```java
package com.capstone.tx.capstone;

import java.util.UUID;

public record TransactionEvent(
    UUID transactionId,
    String accountId,
    double amount,
    String type // "DEBIT" or "CREDIT"
) {}
```

Now let us write the `AccountBalanceService` that manages updates using simulated distributed locks and outbox event publishing:

```java
package com.capstone.tx.capstone;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.locks.ReentrantLock;
import java.util.logging.Logger;

/**
 * Account Balance Service demonstrating distributed lock synchronization
 * and transactional outbox persistence.
 */
public class AccountBalanceService {
    private static final Logger LOGGER = Logger.getLogger(AccountBalanceService.class.getName());

    private final Map<String, Double> accountsDb = new HashMap<>();
    private final Map<UUID, TransactionEvent> outboxDb = new HashMap<>();
    private final ReentrantLock dbTransactionLock = new ReentrantLock();

    public AccountBalanceService() {
        accountsDb.put("ACC-100", 5000.0);
        accountsDb.put("ACC-200", 2500.0);
    }

    /**
     * Executes a secure funds transfer using a simulated lock and atomic outbox writes.
     */
    public boolean transferFunds(String source, String destination, double amount) {
        Objects.requireNonNull(source, "Source account cannot be null");
        Objects.requireNonNull(destination, "Destination account cannot be null");

        // Simulating distributed lock acquisition (e.g., Redlock on source and destination keys)
        LOGGER.info("Acquiring distributed locks for: " + source + " and " + destination);

        dbTransactionLock.lock();
        try {
            double sourceBalance = accountsDb.getOrDefault(source, 0.0);
            if (sourceBalance < amount) {
                LOGGER.warning("Transfer failed: Insufficient funds in " + source);
                return false;
            }

            // Step 1: Perform balance mutations (simulating DB update queries)
            accountsDb.put(source, sourceBalance - amount);
            accountsDb.put(destination, accountsDb.getOrDefault(destination, 0.0) + amount);

            // Step 2: Write Transaction events to Outbox table atomically
            UUID txId = UUID.randomUUID();
            TransactionEvent debitEvent = new TransactionEvent(txId, source, amount, "DEBIT");
            TransactionEvent creditEvent = new TransactionEvent(txId, destination, amount, "CREDIT");

            outboxDb.put(UUID.randomUUID(), debitEvent);
            outboxDb.put(UUID.randomUUID(), creditEvent);

            LOGGER.info("Transfer Succeeded. TxID: " + txId + ". Outbox events written.");
            return true;

        } finally {
            dbTransactionLock.unlock();
            LOGGER.info("Distributed locks released for: " + source + " and " + destination);
        }
    }

    public synchronized double getBalance(String accountId) {
        return accountsDb.getOrDefault(accountId, 0.0);
    }

    public synchronized Map<UUID, TransactionEvent> getOutboxEvents() {
        return new HashMap<>(outboxDb);
    }
}
```

Now let's write the `LedgerAuditService` that reads events and maintains the journal:

```java
package com.capstone.tx.capstone;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.locks.ReentrantLock;
import java.util.logging.Logger;

/**
 * Service that builds a persistent journal database by consuming transaction events.
 */
public class LedgerAuditService {
    private static final Logger LOGGER = Logger.getLogger(LedgerAuditService.class.getName());

    public record JournalEntry(UUID eventId, String accountId, double amount, String type) {}

    private final List<JournalEntry> journalDb = new ArrayList<>();
    private final ReentrantLock journalLock = new ReentrantLock();

    /**
     * Appends an event to the ledger journal database.
     */
    public void recordJournalEntry(TransactionEvent event) {
        journalLock.lock();
        try {
            JournalEntry entry = new JournalEntry(event.transactionId(), event.accountId(), event.amount(), event.type());
            journalDb.add(entry);
            LOGGER.info("Journal entry recorded: " + event.accountId() + " | " + event.type() + " | " + event.amount());
        } finally {
            journalLock.unlock();
        }
    }

    public List<JournalEntry> getJournal() {
        journalLock.lock();
        try {
            return new ArrayList<>(journalDb);
        } finally {
            journalLock.unlock();
        }
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Out-of-Order outbox Events
If the outbox polling daemon uses multiple parallel execution threads to publish events to Kafka, events for a single account can arrive out of order.
*   **Symptom**: The Audit Ledger service receives a credit before the account balance service has recorded the corresponding deposit.
*   **Mitigation**: Set the Kafka partition key to the `accountId`. This ensures that all events for a specific account are processed sequentially on the same Kafka partition.

### Pitfall 2: Locking Order Deadlock
If Thread A calls `transferFunds("ACC-100", "ACC-200")` and Thread B calls `transferFunds("ACC-200", "ACC-100")` concurrently:
*   **Symptom**: Thread A locks ACC-100 and waits for ACC-200. Thread B locks ACC-200 and waits for ACC-100. Both threads hang indefinitely.
*   **Mitigation**: Always sort the account resource IDs alphabetically prior to acquiring distributed locks, ensuring all threads attempt lock acquisition in the exact same resource order.

---

## 5. Socratic Review Questions

### Question 1
Explain how the **Transactional Outbox** and **Event-Driven Reconciliation** resolve the limitations of a multi-service database setup without using 2PC.

#### Answer
In a classical JTA/XA setup, updating balances in the Account DB and writing audit trails in the Ledger DB requires a distributed transaction coordinator to lock rows across both databases.

By using the **Transactional Outbox Pattern**:
1.  The Account Balance Service updates the Account DB and inserts the transfer event into the Outbox table in the *same* database transaction. This guarantees that balance changes are only recorded if the outbox event is also stored.
2.  A background runner publishes this event to Kafka.
3.  The Ledger Audit Service reads the event from Kafka and writes it to the Ledger DB.
This decoupling allows the Account Service to handle writes at low latency. If the Ledger DB crashes, the event remains in Kafka, and the Ledger Service processes it once it recovers, achieving eventual consistency.

### Question 2
Why must we run a background **Reconciliation Engine** if the outbox pattern guarantees eventual consistency?

#### Answer
While the outbox pattern guarantees eventual consistency *under normal operations*, physical failures can still occur:
*   Network connections to the DB can drop midway through write logs.
*   A bug in the consumer service may crash it, skipping event messages.
*   A database administrator could manually edit a balance row without writing an outbox event.
The background reconciliation engine acts as a safety audit. It continuously compares the balances of the account tables against the sum of all journal entries. If a discrepancy is found, it flags the issue, halts automatic transfers for that account, and alerts operators for manual auditing.

---

## 6. Hands-on Challenge: Building the Ledger Reconciliation Engine

### The Challenge
In this challenge, you will implement the background reconciliation algorithm. 

You must write a daemon class that fetches the account balances from the `AccountBalanceService` and the journal list from the `LedgerAuditService`. It must compute the net balance for each account from the journal list:
$$\text{Calculated Balance} = \sum \text{Credits} - \sum \text{Debits}$$
And verify that this calculated balance matches the actual balance reported by the Account Service.

Complete the implementation below:

```java
package com.capstone.tx.capstone.challenge;

import com.capstone.tx.capstone.AccountBalanceService;
import com.capstone.tx.capstone.LedgerAuditService;
import java.util.HashMap;
import java.util.Map;

public class LedgerReconciler {

    private final AccountBalanceService balanceService;
    private final LedgerAuditService auditService;

    public LedgerReconciler(AccountBalanceService balanceService, LedgerAuditService auditService) {
        this.balanceService = balanceService;
        this.auditService = auditService;
    }

    /**
     * Audits the consistency between current account balances and the audit journal.
     * Computes calculated balances from journal entries:
     * - "CREDIT" adds to the account balance.
     * - "DEBIT" subtracts from the account balance.
     * 
     * Returns true if all balances match perfectly, false if a discrepancy is detected.
     */
    public boolean performReconciliation() {
        Map<String, Double> calculatedBalances = new HashMap<>();

        // TODO: Complete this implementation.
        // 1. Fetch all journal entries from auditService.getJournal().
        // 2. Aggregate the calculated balance for each account.
        //    Hint: start with initial balances or verify net journal movements.
        // 3. For each account involved in the journal, compare calculated vs. balanceService.getBalance(accountId).
        // 4. Return false if any mismatch is found.
        return false;
    }
}
```

Write your code and verify the correctness against simulated test data. Save your solution notes inside `modules/11-final-capstone-distributed-ledger.md`.
