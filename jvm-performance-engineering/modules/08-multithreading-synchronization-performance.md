# Module 08: Synchronization & Thread Dumps — Lock Contention and Thread Diagnostics

Welcome back, students. Today we analyze the performance cost of concurrency and synchronization: **Monitor Contention** and **Thread Dump Analysis**.

In concurrent programming, synchronization guarantees safety, but it can introduce latency. When threads compete for shared resources, the JVM must manage lock escalation, block threads, and coordinate scheduling. We will study JVM thread states, analyze how HotSpot escalates locks, explore JIT lock optimizations (Lock Elision and Lock Coarsening), and learn how to diagnose deadlocks and thread pinning from raw **Thread Dumps**.

---

## 1. Academic Lecture: The Mechanics of JVM Locks

To coordinate thread execution, every object in Java has a **Monitor** associated with it. When a thread executes a `synchronized` block, it attempts to acquire this monitor.

### Lock Escalation in HotSpot

Acquiring a heavyweight operating system lock requires an OS context switch, which is CPU-expensive. To avoid this, HotSpot escalates lock intensity progressively:

```
[ Unlocked Object ] ---> 1. Biased Locking (Deprecated) ---> 2. Basic / Thin Lock (CAS on Stack)
                                                                     |
                                                             (High Contention)
                                                                     v
                                                          3. Inflated Lock (OS Mutex)
```

1.  **Biased Locking**: The JVM biases the monitor toward the first thread that acquires it. Subsequent lock entries by this thread execute with zero CPU overhead. *Note: Deprecated in modern JDKs due to the high cost of revoking biases.*
2.  **Basic / Thin Locking**: If another thread attempts to acquire the lock, the bias is revoked. The threads compete using a lightweight **Compare-And-Swap (CAS)** operation to write their thread ID to the object's Mark Word.
3.  **Inflated / Heavyweight Locking**: If contention is high (multiple threads spin CAS continuously), the lock is inflated. The JVM allocates a native `ObjectMonitor` structure and registers the blocked threads in an OS-level wait queue. Threads are suspended by the operating system, releasing CPU cycles but introducing context-switch latency when woken up.

### JIT Compiler Lock Optimizations

The JIT compiler executes optimizations to eliminate lock overhead:
*   **Lock Elision**: If Escape Analysis proves that the lock object does not escape the method scope, the compiler eliminates the `monitorenter` and `monitorexit` instructions entirely.
*   **Lock Coarsening**: If the compiler detects adjacent synchronized blocks on the same monitor:
    ```java
    synchronized(lock) { doX(); }
    synchronized(lock) { doY(); }
    ```
    It coarsens them into a single synchronization block to avoid repeated lock/unlock cycles:
    ```java
    synchronized(lock) { doX(); doY(); }
    ```

---

## 2. Theory vs. Production Trade-offs

### The Safepoint Cost of Biased Lock Revocation
While biased locking speeds up single-threaded executions, revoking a bias requires the JVM to execute a global Safepoint. 
*   **Production Hazard**: If your multi-threaded application has high contention on objects that were biased, the frequent safepoints required to revoke biases will halt mutator threads, degrading overall application throughput.

---

## 3. How to Use: Generating a Deadlock in Java 21

Let's write a complete, compile-grade Java 21 class that purposefully creates a **Deadlock** between two threads. You will use this code to generate and analyze thread dumps.

```java
package com.capstone.jvm.threads;

import java.util.logging.Logger;

/**
 * Script simulating a classic Deadlock condition.
 * To capture and analyze the deadlock thread dump:
 * 1. Run the application: java -jar app.jar
 * 2. Generate thread dump:
 *    jcmd <PID> Thread.print > threaddump.txt
 */
public class DeadlockSimulator {
    private static final Logger LOGGER = Logger.getLogger(DeadlockSimulator.class.getName());

    private static final Object lockA = new Object();
    private static final Object lockB = new Object();

    public static void main(String[] args) {
        LOGGER.info("Starting Deadlock Simulator...");

        // Thread 1: Locks A, then attempts to lock B
        Thread thread1 = new Thread(() -> {
            synchronized (lockA) {
                LOGGER.info(Thread.currentThread().getName() + " acquired Lock A. Waiting for Lock B...");
                try {
                    Thread.sleep(100); // Allow thread2 time to lock B
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
                
                synchronized (lockB) {
                    LOGGER.info(Thread.currentThread().getName() + " acquired Lock B.");
                }
            }
        }, "WorkerThread-A");

        // Thread 2: Locks B, then attempts to lock A
        Thread thread2 = new Thread(() -> {
            synchronized (lockB) {
                LOGGER.info(Thread.currentThread().getName() + " acquired Lock B. Waiting for Lock A...");
                try {
                    Thread.sleep(100); // Allow thread1 time to lock A
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }

                synchronized (lockA) {
                    LOGGER.info(Thread.currentThread().getName() + " acquired Lock A.");
                }
            }
        }, "WorkerThread-B");

        thread1.start();
        thread2.start();
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Carrier Thread Pinning in Java 21 Virtual Threads
Executing standard `synchronized` blocks inside Java 21 Virtual Threads when calling blocking operations (like database connections or network client calls).
*   **Symptom**: Complete application throughput collapse and thread exhaustion.
*   **Why**: When a virtual thread enters a `synchronized` block and blocks, it cannot "unmount" from the physical Platform (Carrier) thread. The Carrier thread remains pinned and blocked.
*   **Mitigation**: Replace `synchronized` blocks with `ReentrantLock` for any hot paths executing blocking operations inside Virtual Threads.

### Pitfall 2: Locking on String Literals
Using `synchronized("my-lock-key")` to coordinate executions.
*   **Symptom**: Unexplained thread blockages across completely separate service instances.
*   **Why**: String literals are interned globally in the JVM string pool. You are sharing the same lock monitor across unrelated classes, causing global lock contention.
*   **Mitigation**: Always lock on private, dedicated final objects: `private final Object lock = new Object();`.

---

## 5. Socratic Review Questions

### Question 1
Explain why a thread waiting on a synchronized block is in the **`BLOCKED`** state, while a thread executing `Thread.sleep()` or waiting on `lock.wait()` is in the **`WAITING`** or **`TIMED_WAITING`** state.

#### Answer
*   **`BLOCKED`**: The thread is waiting to acquire a JVM monitor lock. This state is managed exclusively by the JVM's synchronization engine. The thread cannot continue until the lock is released and the scheduler grants it ownership of the monitor.
*   **`WAITING` / `TIMED_WAITING`**: The thread has voluntarily relinquished execution. For example, calling `object.wait()` releases the lock monitor and registers the thread in the monitor's wait queue. The thread is asleep and consumes zero CPU cycles. It will remain in this state until another thread explicitly calls `object.notifyAll()` or the timer expires.

### Question 2
How does a Thread Dump identify a Deadlock? What details does `jstack` display in its analysis report?

#### Answer
A Thread Dump lists the execution stack trace, lock references, and current state of all active JVM threads. 

When a deadlock occurs, `jstack` traverses the dependency chain of locks. It checks if there is a cycle where Thread A holds Lock 1 and waits for Lock 2, while Thread B holds Lock 2 and waits for Lock 1.

At the bottom of the dump, `jstack` prints an explicit warning section:
```
Found one Java-level deadlock:
=============================
"WorkerThread-A":
  waiting to lock monitor 0x0000018f (object 0x00000007, a java.lang.Object)
  which is held by "WorkerThread-B"
"WorkerThread-B":
  waiting to lock monitor 0x00000190 (object 0x00000008, a java.lang.Object)
  which is held by "WorkerThread-A"
```
It shows the exact thread names, the monitor addresses, and the line numbers of code that caused the blocking lock calls, allowing you to trace the deadlock source immediately.

---

## 6. Hands-on Challenge: Thread Dump Parser

### The Challenge
In this challenge, you will implement a simplified Thread Dump Parser.

Given a list of simulated thread dump lines, you must write a parser that:
1.  Identifies threads in the `"BLOCKED"` state.
2.  Extracts the thread name.
3.  Extracts the ID of the lock it is waiting to acquire.

Complete the parsing logic inside the class below:

```java
package com.capstone.jvm.threads.challenge;

import java.util.List;

public class ThreadDumpParser {

    public record BlockedThread(String threadName, String waitingLockId) {}

    /**
     * Parses thread dump lines to identify blocked threads and their target locks.
     * 
     * Line format examples:
     * - "\"WorkerThread-A\" prio=5 tid=0x1 state=BLOCKED"
     * - "  - waiting to lock <0x00000007> (a java.lang.Object)"
     */
    public BlockedThread parseBlockedThread(List<String> dumpLines) {
        String threadName = "";
        String lockId = "";

        // TODO: Complete this implementation.
        // 1. Iterate over dumpLines.
        // 2. If a line starts with "\" and contains "state=BLOCKED", extract the thread name (between quotes).
        // 3. If a line contains "waiting to lock", extract the hex address between angle brackets '<' and '>'.
        // 4. Return BlockedThread containing the extracted parameters.
        return new BlockedThread(threadName, lockId);
    }
}
```

Write your code and verify the thread dump parsing logic. Save your solution notes inside `modules/08-multithreading-synchronization-performance.md`.
