# The Locks API — Reentrant Locks

In the previous modules, we explored the thread synchronization mechanism using the built-in `synchronized` keyword. Java 5 introduced the `java.util.concurrent.locks` package, which provides a dedicated **Lock API**. This API offers extensive, flexible locking operations that go far beyond the capabilities of the traditional `synchronized` keyword.

---

## Structured vs. Unstructured Locking

To understand why the Lock API is necessary, we must contrast two different locking paradigms:

### 1. Structured Locking (synchronized)
Structured locking enforces that all lock acquisitions and releases occur in a strict, block-structured way. This has two key rules:
1.  **Strict Order:** When multiple locks are acquired, they must be released in the exact reverse order of acquisition.
2.  **Lexical Scope:** A lock must be acquired and released within the same code block (lexical scope).

```java
synchronized (L1) {
    synchronized (L2) {
        synchronized (L3) {
            // critical section
        } // L3 is implicitly released here
    } // L2 is implicitly released here
} // L1 is implicitly released here
```

Structured locking is simple, clean, and helps avoid common locking mistakes because the JVM automatically manages lock release. However, it restricts lock management to a single code block.

### 2. Unstructured Locking (Lock API)
In complex concurrent applications, you may need a more flexible approach where locks can be acquired and released in different scopes and in any order. 

> **Mental Model: Hand-Over-Hand Locking**
> Consider traversing a concurrently accessed Doubly Linked List. To move safely through the nodes, you might need to:
> 1.  Acquire a lock on Node **A** and Node **B**.
> 2.  Release the lock on Node **A** and acquire a lock on Node **C**.
> 3.  Release the lock on Node **B** and acquire Node **D**, and so on.
> 
> This technique is called **hand-over-hand locking** or **chain locking**. It is a form of unstructured locking and is impossible to implement using traditional `synchronized` blocks because they require nested lexical scopes.

Unstructured locking gives the programmer explicit control to call `lock()` and `unlock()` in any order, across different methods, and in different scopes.

---

## Concurrency in a Doubly Linked List

Let's look at an example of a concurrent Doubly Linked List where multiple threads want to delete nodes concurrently:

*Figure 14.1: Doubly Linked List Deletion*
![alt text](../images/image10.png)

Three threads, **T1**, **T2**, and **T3**, are trying to delete nodes **B**, **C**, and **D** respectively. 
For thread **T1** to delete Node **B** safely, it must acquire locks on Node **A** (previous), Node **B** (current), and Node **C** (next) to modify their pointers without interference:

```java
// Pseudocode for thread-safe node deletion
DELETE(curr) {
    LOCK curr, curr.prev, curr.next
    curr.prev.next = curr.next;
    curr.next.prev = curr.prev;
    UNLOCK curr.prev, curr, curr.next
}
```

Why not simply use a single global mutex lock to serialize all deletions?

```java
private static final Object MUTEX = new Object();

public void removeNode(DLLNode curr) {
    synchronized(MUTEX) { // Heavy global lock
        curr.prev.next = curr.next;
        curr.next.prev = curr.prev;
    }
}
```

While simple, this global lock approach has two major drawbacks:

### 1. Thread Starvation
With `synchronized`, there is no guarantee of lock acquisition order. If multiple threads request the lock, some threads might be repeatedly passed over, leading to **thread starvation** (where a thread is blocked indefinitely). 

With the Lock API, we can configure a `ReentrantLock` with a **Fair Locking Policy**, ensuring that threads acquire the lock in a strict first-come, first-served order:

```java
private final boolean FAIRNESS = true;
private static final Lock MUTEX = new ReentrantLock(FAIRNESS);

public void removeNode(DLLNode curr) {
    MUTEX.lock();
    try {
        curr.prev.next = curr.next;
        curr.next.prev = curr.prev;
    } finally {
        MUTEX.unlock(); // Guaranteed to release
    }
}
```

### 2. Unnecessary Thread Blocking
Using a global lock blocks threads even if they are modifying completely different parts of the list.
*   `T1` deletes Node **B** (requires locks on **A**, **B**, and **C**).
*   `T4` deletes Node **E** (requires locks on **D**, **E**, and **F**).

Because their operations do not overlap, `T1` and `T4` could run in parallel. However, a global `synchronized(MUTEX)` lock forces them to execute sequentially, severely reducing throughput. 

By using the Lock API, we can lock individual nodes, allowing non-overlapping operations to proceed concurrently.

---

## The Lock Interface API

The `java.util.concurrent.locks.Lock` interface provides the following primary methods:
*   **`lock()`:** Acquires the lock. If the lock is not available, the calling thread blocks until it is.
*   **`unlock()`:** Releases the lock.

> **Pitfall: Manual Lock Release**
> Unlike `synchronized`, the JVM does not automatically release locks acquired via the Lock API. It is the programmer's responsibility to release the lock. To prevent resource leaks and deadlocks, you must **always** use the `try-finally` idiom:
> 
> ```java
> Lock lock = new ReentrantLock();
> lock.lock(); // Acquire lock above try block
> try {
>     // critical section (access protected state)
> } finally {
>     lock.unlock(); // Guaranteed to release in finally block
> }
> ```

---

## Example: Thread-Safe Counter with ReentrantLock

Here is a thread-safe counter rewritten using `ReentrantLock`:

```java
package org.vit.threads;

import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

class Counter {
    private final Lock mutex = new ReentrantLock();
    private int value;

    public void increment() {
        mutex.lock(); // Enter critical section
        try {
            ++value;
        } finally {
            mutex.unlock(); // Exit critical section
        }
    }

    public int get() {
        mutex.lock();
        try {
            return value;
        } finally {
            mutex.unlock();
        }
    }
}

public class CounterDemo {
    private static final Counter counter = new Counter();

    public static void main(String[] args) throws InterruptedException {
        Runnable incrementTask = () -> {
            for (int i = 0; i < 1000000; i++) {
                counter.increment();
            }
        };

        Thread t1 = new Thread(incrementTask, "T1");
        Thread t2 = new Thread(incrementTask, "T2");

        long start = System.nanoTime();
        t1.start();
        t2.start();

        t1.join(); // Wait here till T1 completes
        t2.join(); // Wait here till T2 completes
        long end = System.nanoTime();

        String timeTaken = String.format("%.2f", (end - start) / 1000000.0);
        System.out.println("Final Counter Value: " + counter.get() + " Time Taken: " + timeTaken + " millis");
    }
}
```

---

## Summary

*   **Structured Locking:** Handled implicitly by `synchronized` blocks. Locks are acquired and released in a strict nested order within a single lexical scope.
*   **Unstructured Locking:** Handled explicitly by the Lock API. Allows locks to be acquired and released in different scopes and in any order, enabling advanced techniques like chain locking.
*   **Explicit Management:** Locks must be manually released. The `try-finally` block is mandatory to ensure `unlock()` is always called.
*   **Starvation Avoidance:** The Lock API supports **Fair Locking Policies** to guarantee first-come, first-served lock acquisition.
*   **Unnecessary Blocking Avoidance:** Allows fine-grained locking of individual elements (like list nodes) instead of global mutexes, increasing concurrency and throughput.
