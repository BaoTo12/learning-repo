# Liveness Hazards: Deadlock, Starvation, and Livelock

Writing thread-safe code requires ensuring that threads access shared resources without corrupting data or creating race conditions. However, correctness is only one half of writing successful concurrent applications. The other half is **liveness**.

A concurrent application's ability to execute in a timely, progressive manner is called **liveness**. A **liveness hazard** occurs when a thread enters a state where it can no longer make forward progress. 

In this module, we will explore the three primary liveness hazards in concurrent programming: **deadlock**, **starvation**, and **livelock**.

---

## 1. Deadlock

A **deadlock** occurs when two or more threads are blocked indefinitely, each waiting for a lock or resource that is held by one of the other waiting threads. Because none of the threads can release the resources they already hold, none of them can proceed.

> **Mental Model: The Dining Philosophers**
> The classic mental model for deadlock is the **Dining Philosophers Problem**. Five philosophers sit around a table, each with a single chopstick to their left. To eat, a philosopher must acquire two chopsticks. If every philosopher simultaneously picks up their left chopstick, no chopsticks remain on the table. Each philosopher holds one chopstick and waits indefinitely for the next person to release theirs, creating a complete deadlock.

---

### The Four Coffman Conditions

For a deadlock to occur, the following four conditions (known as the **Coffman conditions**) must hold simultaneously:

1.  **Mutual Exclusion**: At least one resource must be held in a non-shareable mode (only one thread can use it at a time).
2.  **Hold and Wait**: A thread holding allocated resources can request additional resources without relinquishing its current ones.
3.  **No Preemption**: Resources cannot be forcibly taken from a thread; they can only be released voluntarily by the thread holding them.
4.  **Circular Wait**: A closed chain of threads exists, where each thread holds one or more resources that are needed by the next thread in the chain.

---

### Example: Classic Deadlock in Java

The program below demonstrates a classic deadlock. Thread 1 acquires `lock1` and waits for `lock2`, while Thread 2 acquires `lock2` and waits for `lock1`:

```java
public class DeadlockDemo {
    private static final Object lock1 = new Object();
    private static final Object lock2 = new Object();

    public static void main(String[] args) {
        Thread t1 = new Thread(() -> {
            synchronized (lock1) {
                System.out.println("Thread 1: Holding lock 1...");
                try {
                    // Sleep briefly to ensure Thread 2 acquires lock 2
                    Thread.sleep(50);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
                System.out.println("Thread 1: Waiting for lock 2...");
                synchronized (lock2) {
                    System.out.println("Thread 1: Acquired lock 2!");
                }
            }
        }, "Thread-1");

        Thread t2 = new Thread(() -> {
            synchronized (lock2) {
                System.out.println("Thread 2: Holding lock 2...");
                try {
                    // Sleep briefly to ensure Thread 1 acquires lock 1
                    Thread.sleep(50);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
                System.out.println("Thread 2: Waiting for lock 1...");
                synchronized (lock1) {
                    System.out.println("Thread 2: Acquired lock 1!");
                }
            }
        }, "Thread-2");

        t1.start();
        t2.start();
    }
}
```

If you run this program, it will print:
```text
Thread 1: Holding lock 1...
Thread 2: Holding lock 2...
Thread 1: Waiting for lock 2...
Thread 2: Waiting for lock 1...
```
At this point, the application will hang indefinitely. If you capture a thread dump, both threads will show as being in the `BLOCKED` state.

---

### Deadlock Prevention and Avoidance

To prevent deadlocks, you must break at least one of the four Coffman conditions:

*   **Lock Ordering (Breaks Circular Wait)**: Always acquire locks in a strict, globally agreed-upon order. For instance, in the example above, if both Thread 1 and Thread 2 always lock `lock1` before `lock2`, a deadlock is impossible.
*   **Time-outs (Breaks Hold and Wait)**: Use the Lock API's `tryLock(long time, TimeUnit unit)` method instead of intrinsic `synchronized` blocks. If a thread cannot acquire the second lock within a specified time-out, it backs off, releases its first lock, and tries again.
*   **Reduce Lock Scope**: Keep critical sections as small as possible and avoid executing external, unknown code (like listener callbacks) while holding a lock.

---

## 2. Starvation

**Starvation** occurs when a thread is perpetually denied access to shared resources or CPU time, preventing it from making forward progress, even though it is technically ready to run. Unlike deadlock, the thread is not blocked by a mutual waiting loop; it is simply ignored or bypassed by the scheduler or lock manager.

### Common Causes of Starvation

1.  **Thread Priorities**: If the JVM scheduler favors threads with high priorities, lower-priority threads may never receive CPU execution time if high-priority threads are constantly active.
2.  **Unfair Locks (Lock Barging)**: In an **unfair lock** system (like standard `synchronized` blocks or standard `ReentrantLock`), newly arriving threads can "barge" and acquire the lock immediately if it is released, bypassing threads that have been waiting in the queue for a long time.
3.  **Infinite Loops or Long-running Lock Holders**: A thread that holds an exclusive lock while performing a very long-running operation or entering an infinite loop will starve all other threads waiting for that lock.

### Mitigation Strategies

*   **Use Fair Locking Policies**: When using the Lock API, you can enable **fairness** by passing `true` to the constructor (e.g., `new ReentrantLock(true)`). A fair lock ensures that threads acquire the lock in a strict First-In, First-Out (FIFO) order, preventing starvation.
*   **Avoid Thread Priority Manipulation**: Rely on the operating system's default thread scheduler instead of manually setting thread priorities via `Thread.setPriority()`.
*   **Keep Locks Short**: Ensure that threads release locks as quickly as possible.

---

## 3. Livelock

A **livelock** is a liveness hazard where threads continuously change their active state in response to each other, but without making any actual forward progress. 

Unlike deadlock, livelocked threads are not blocked; they are actively running on the CPU, consuming resources while doing nothing useful.

> **Mental Model: Polite Hallway Passing**
> Imagine two extremely polite people attempting to pass each other in a narrow hallway. Person A steps to their left to let Person B pass, while Person B simultaneously steps to their right (A's left) to let Person A pass. Realizing they are blocking each other, Person A steps to their right, while Person B simultaneously steps to their left. They continue this synchronized dancing indefinitely, actively moving but never passing.

---

### Example: Polite Workers in Livelock

The following code illustrates a livelock where two polite threads attempt to share a resource. When a thread notices that another thread also needs the resource, it politely releases it and waits, resulting in an infinite loop of active backing off:

```java
public class LivelockDemo {

    static class Worker implements Runnable {
        private final String name;
        private boolean active;

        public Worker(String name, boolean active) {
            this.name = name;
            this.active = active;
        }

        public String getName() {
            return name;
        }

        public boolean isActive() {
            return active;
        }

        @Override
        public void run() {
            while (active) {
                // Wait for the other worker to finish if they are active
                if (LivelockDemo.otherWorker.isActive()) {
                    System.out.println(name + " :: Polite handoff to " + LivelockDemo.otherWorker.getName());
                    try {
                        Thread.sleep(10); // Wait and retry
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                    continue;
                }

                // Perform the work
                System.out.println(name + " :: Working and completing task...");
                active = false;
            }
        }
    }

    private static Worker worker1;
    private static Worker worker2;
    private static Worker otherWorker;

    public static void main(String[] args) {
        worker1 = new Worker("Worker-1", true);
        worker2 = new Worker("Worker-2", true);

        // Simulate Worker-1 running while checking Worker-2
        Thread t1 = new Thread(worker1);
        Thread t2 = new Thread(worker2);

        // Establish the relationships
        // In a real scenario, this would represent mutually dependent tasks
        LivelockDemo.otherWorker = worker2;
        t1.start();
        
        // Switch context to show inter-dependence
        LivelockDemo.otherWorker = worker1;
        t2.start();
    }
}
```

In this scenario, both threads are constantly awake, executing their loops, printing polite handoff messages, and consuming CPU cycles, but neither ever completes their work.

### Mitigation Strategies

*   **Introduce Randomness (Jitter)**: When threads must back off and retry after a collision or conflict, introduce a randomized delay (jitter) before retrying. This breaks the synchronized timing of their state changes (a technique widely used in networking protocols like Ethernet's exponential back-off).
*   **Design a Clear Coordinator**: Use a central coordinator thread or queue to distribute resources rather than letting threads negotiate resource ownership directly.

---

## Summary

| Hazard | Thread State | CPU Consumption | Primary Cause | Resolution |
| :--- | :--- | :--- | :--- | :--- |
| **Deadlock** | `BLOCKED` / `WAITING` | Zero (Passive) | Circular dependency on exclusive locks. | Strict lock ordering, lock time-outs (`tryLock`). |
| **Starvation** | `RUNNABLE` / `WAITING` | High (other threads) | Thread priorities, unfair locks, long critical sections. | Fair locking policies, avoiding manual priorities. |
| **Livelock** | `RUNNABLE` | Extremely High (Active) | Continuous synchronized backing off and retrying. | Introducing randomized retries (jitter), central coordinators. |
