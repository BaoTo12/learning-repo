# Advanced Locks: ReadWriteLock and StampedLock

In previous modules, we explored exclusive locking using `synchronized` and the basic `ReentrantLock`. While exclusive locks guarantee safety, they restrict concurrency by allowing only one thread to access critical sections at any time.

In this module, we will explore advanced lock implementations that optimize throughput for read-heavy applications: **`ReadWriteLock`** and the high-performance **`StampedLock`**.

---

## Differences Between Lock and Synchronized Block

Using the explicit `Lock` API offers several distinct advantages over traditional `synchronized` blocks:

| Feature | `synchronized` Block | Lock API (`ReentrantLock`, etc.) |
| :--- | :--- | :--- |
| **Lexical Scope** | Rigidly bound. Lock must be acquired and released in the same method block. | Flexible. Lock (`lock()`) and unlock (`unlock()`) can occur in separate methods. |
| **Fairness Policy** | No fairness support. Any thread can barge and acquire the lock. | Supports fairness. Longest-waiting threads are guaranteed priority. |
| **Non-blocking Try** | No. Threads block indefinitely if the lock is held. | Yes. `tryLock()` immediately returns `false` if the lock is unavailable. |
| **Interruption Support** | No. Waiting threads cannot be interrupted. | Yes. `lockInterruptibly()` allows waiting threads to be interrupted. |

---

> **Problem: Read Contention Bottlenecks**
> In applications with high read-to-write ratios (e.g., in-memory caches, metadata registries), using exclusive locks causes severe thread contention. Even though multiple concurrent read operations do not modify state and are safe to run in parallel, an exclusive lock serializes them, degrading performance.

---

## 1. ReadWriteLock and ReentrantReadWriteLock

The **`ReadWriteLock`** interface maintains a pair of locks to distinguish between read-only and write operations:

*   **Read Lock (Shared)**: Multiple threads can hold the read lock concurrently, as long as no thread holds the write lock.
*   **Write Lock (Exclusive)**: Only a single thread can hold the write lock. While held, no other threads can read or write.

```java
public interface ReadWriteLock {
    Lock readLock();
    Lock writeLock();
}
```

---

> **Mental Model: Shared vs. Exclusive Access**
> Think of a `ReadWriteLock` as having two gates:
> *   **The Read Gate (Shared)**: Wide open for multiple threads to pass through simultaneously, provided no writer is active.
> *   **The Write Gate (Exclusive)**: A narrow single-person turnstile. When a writer enters, both the read gate and the write gate are locked, blocking all other threads.

---

### Lock Acquisition Rules

1.  **Read Lock**: A thread can acquire the read lock if no thread holds the write lock and no threads are waiting to write.
2.  **Write Lock**: A thread can acquire the write lock only if no threads are currently reading or writing.

### Example: Thread-Safe Cache with ReadWriteLock

The class below implements a thread-safe cache using `ReentrantReadWriteLock`, allowing concurrent reads while serializing writes:

```java
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

public class SynchronizedHashMapWithReadWriteLock {

    private final Map<String, String> syncHashMap = new HashMap<>();
    private final ReadWriteLock rwLock = new ReentrantReadWriteLock();
    private final Lock readLock = rwLock.readLock();
    private final Lock writeLock = rwLock.writeLock();

    public void put(String key, String value) {
        writeLock.lock();
        try {
            syncHashMap.put(key, value);
        } finally {
            writeLock.unlock();
        }
    }

    public String remove(String key) {
        writeLock.lock();
        try {
            return syncHashMap.remove(key);
        } finally {
            writeLock.unlock();
        }
    }

    public String get(String key) {
        readLock.lock();
        try {
            return syncHashMap.get(key);
        } finally {
            readLock.unlock();
        }
    }

    public boolean containsKey(String key) {
        readLock.lock();
        try {
            return syncHashMap.containsKey(key);
        } finally {
            readLock.unlock();
        }
    }
}
```

---

### Example: Thread Simulation and Fairness Policy

To demonstrate lock acquisition, thread collaboration, and the **fairness policy** in action, we can implement a multi-threaded simulation. In this scenario, we configure a `ReentrantReadWriteLock` with fairness enabled (`true`) to ensure that threads acquire locks in the order they requested them, preventing starvation.

The simulation consists of three threads:
1.  **`Read` Thread**: Continuously attempts to acquire the read lock. If a write lock is currently active, it detects this using `isWriteLocked()`. Once it acquires the read lock, it reads and prints the shared `message` string.
2.  **`WriteA` Thread**: Periodically acquires the exclusive write lock to append the character `"a"` to the shared `message` string.
3.  **`WriteB` Thread**: Periodically acquires the exclusive write lock to append the character `"b"` to the shared `message` string.

Here is the complete Java implementation of this simulation:

```java
import java.util.concurrent.locks.ReentrantReadWriteLock;

public class ReentrantReadWriteLockExample {

    private static final ReentrantReadWriteLock lock = new ReentrantReadWriteLock(true);
    private static String message = "a";

    public static void main(String[] args) throws InterruptedException {
        Thread t1 = new Thread(new Read());
        Thread t2 = new Thread(new WriteA());
        Thread t3 = new Thread(new WriteB());

        t1.start();
        t2.start();
        t3.start();

        t1.join();
        t2.join();
        t3.join();
    }

    static class Read implements Runnable {
        @Override
        public void run() {
            for (int i = 0; i <= 10; i++) {
                if (lock.isWriteLocked()) {
                    System.out.println("I'll take the lock from Write");
                }

                lock.readLock().lock();
                try {
                    System.out.println("ReadThread " + Thread.currentThread().getId() + " ---> Message is " + message);
                } finally {
                    lock.readLock().unlock();
                }
            }
        }
    }

    static class WriteA implements Runnable {
        @Override
        public void run() {
            for (int i = 0; i <= 10; i++) {
                try {
                    lock.writeLock().lock();
                    message = message.concat("a");
                } finally {
                    lock.writeLock().unlock();
                }
            }
        }
    }

    static class WriteB implements Runnable {
        @Override
        public void run() {
            for (int i = 0; i <= 10; i++) {
                try {
                    lock.writeLock().lock();
                    message = message.concat("b");
                } finally {
                    lock.writeLock().unlock();
                }
            }
        }
    }
}
```

> **Insights: Lock Intermixing and Fairness**
> By passing `true` to the `ReentrantReadWriteLock` constructor, we enable a **fair lock** policy. This ensures that the lock favors the longest-waiting thread. In this simulation, as the reader and writer threads compete, the fair policy forces them to take turns in an ordered fashion rather than allowing one type of thread to continuously monopolize the lock.

---


> **Pitfalls: Writer Starvation**
> A significant risk with `ReentrantReadWriteLock` is **writer starvation**. If there is a continuous stream of read requests, the read lock remains constantly held. As a result, any thread waiting for the write lock will be blocked indefinitely, starving the writer.

---

## 2. StampedLock (Optimistic Locking)

Introduced in Java 8, **`StampedLock`** is a high-performance alternative to `ReentrantReadWriteLock`. It supports read/write locking but uses a **stamp** (a `long` value representing a version/state) to release locks and validate states.

Unlike `ReentrantReadWriteLock`, `StampedLock` supports **Optimistic Reading**, which completely eliminates lock acquisition overhead for read operations in the happy path.

### Example: Cache with StampedLock Pessimistic Locks

```java
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.locks.StampedLock;

public class StampedLockDemo {
    private final Map<String, String> map = new HashMap<>();
    private final StampedLock lock = new StampedLock();

    public void put(String key, String value) {
        long stamp = lock.writeLock(); // Returns a write stamp
        try {
            map.put(key, value);
        } finally {
            lock.unlockWrite(stamp); // Requires the write stamp to unlock
        }
    }

    public String get(String key) {
        long stamp = lock.readLock(); // Returns a read stamp
        try {
            return map.get(key);
        } finally {
            lock.unlockRead(stamp); // Requires the read stamp to unlock
        }
    }
}
```

---

### Optimistic Reading Mechanics

In an optimistic read, the thread does **not** acquire a read lock. Instead, it obtains an optimistic read stamp, reads the shared variables, and then validates whether a write occurred during the read:

```java
public String readWithOptimisticLock(String key) {
    long stamp = lock.tryOptimisticRead(); // Non-blocking, returns stamp
    String value = map.get(key); // Read shared state without locking

    // Validate if a write occurred since tryOptimisticRead
    if (!lock.validate(stamp)) {
        // Validation failed! A write occurred. Fall back to a pessimistic read lock
        stamp = lock.readLock();
        try {
            return map.get(key);
        } finally {
            lock.unlockRead(stamp);
        }
    }
    return value; // Return value read optimistically
}
```

---

> **Insights: Optimistic Locking Efficiency**
> Optimistic reading is highly efficient because it avoids the write-barrier memory synchronization overhead of acquiring a lock. If no concurrent writes occur (which is the case for 99% of reads in typical systems), the read completes instantly. If a write does occur, the failure is detected via `validate()` and safely recovered by falling back to a pessimistic lock.

---

> **Pitfalls: StampedLock Non-Reentrancy**
> Unlike `ReentrantLock` and `ReentrantReadWriteLock`, `StampedLock` is **NOT reentrant**. If a thread holding a lock attempts to acquire the lock again, it will **self-deadlock** immediately. Never use `StampedLock` in recursive algorithms or nested methods that acquire the same lock.

---

## 3. Working with Multiple Conditions

While `synchronized` blocks are limited to a single wait-set per object via `wait()` and `notify()`, the Lock API allows you to bind **multiple `Condition` instances** to a single `Lock`. This provides fine-grained control over thread communication.

Consider a thread-safe Stack with a fixed capacity where we want to manage two distinct conditions:
1.  **`stackEmptyCondition`**: Readers wait here if the stack is empty.
2.  **`stackFullCondition`**: Writers wait here if the stack is full.

```java
import java.util.Stack;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;

public class ReentrantLockWithCondition {

    private final Stack<String> stack = new Stack<>();
    private final int CAPACITY = 5;

    private final ReentrantLock lock = new ReentrantLock();
    private final Condition stackEmptyCondition = lock.newCondition();
    private final Condition stackFullCondition = lock.newCondition();

    public void pushToStack(String item) {
        lock.lock();
        try {
            // Wait if stack is full
            while (stack.size() == CAPACITY) {
                stackFullCondition.await();
            }
            stack.push(item);
            // Signal waiting consumers that the stack is no longer empty
            stackEmptyCondition.signalAll();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            lock.unlock();
        }
    }

    public String popFromStack() {
        lock.lock();
        try {
            // Wait if stack is empty
            while (stack.size() == 0) {
                stackEmptyCondition.await();
            }
            String item = stack.pop();
            // Signal waiting producers that the stack is no longer full
            stackFullCondition.signalAll();
            return item;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return null;
        } finally {
            lock.unlock();
        }
    }
}
```

*(Note: The mechanics of Condition objects, signal routing, and custom BlockingQueue implementations are analyzed in-depth in Module 16).*

---

## Summary

*   **API Flexibility**: Explicit `Lock` implementations provide advanced features like non-blocking `tryLock()`, interruptible locking, and fairness policies that are unavailable with `synchronized`.
*   **ReadWriteLock**: Optimizes read-heavy workloads by separating read access (shared) from write access (exclusive).
*   **Writer Starvation**: A critical vulnerability in read-write locks under high read contention, which can block writer threads indefinitely.
*   **StampedLock**: A high-performance synchronization primitive that introduces optimistic reading to eliminate read-locking overhead entirely in the absence of writes.
*   **Non-Reentrancy Deadlock**: StampedLock is not reentrant; self-deadlock will occur if a thread attempts to acquire it multiple times.
*   **Multiple Conditions**: Explicit locks support generating multiple `Condition` objects, allowing precise signal routing between different groups of waiting threads.
