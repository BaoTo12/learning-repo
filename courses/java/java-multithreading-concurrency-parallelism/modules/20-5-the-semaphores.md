# Semaphores

In previous modules, we explored several synchronizers designed to block or allow threads based on coordination states. In this module, we will examine another classic and highly versatile synchronizer: the **`Semaphore`** (often referred to as a **counting semaphore**).

A `Semaphore` is used to control the number of threads or concurrent activities that can access a specific resource or perform a particular action simultaneously. 

---

## How Semaphores Work

A `Semaphore` manages a set of virtual **permits**. When instantiating a semaphore, we pass the initial number of permits to the constructor:

```java
Semaphore semaphore = new Semaphore(permits);
```

The semaphore coordinates threads using two primary operations:

### 1. Acquire
Before performing an action or accessing a resource, a thread must acquire a permit by calling **`acquire()`** or **`tryAcquire()`**.
- **`acquire()`**: Acquires a permit, blocking the calling thread until a permit becomes available, or until the thread is interrupted.
- **`tryAcquire()`**: Non-blocking call that attempts to acquire a permit. It returns `true` immediately if a permit is available and acquires it; otherwise, it returns `false` immediately without blocking.
- **No Thread Restriction**: A single thread can acquire multiple permits at the same time based on availability. There is no restriction that a thread can only hold one permit.

### 2. Release
When a thread finishes its task, it must return the permit back to the semaphore by calling **`release()`**. This increments the permit count, potentially unblocking a thread waiting in the acquire queue.

Below is a conceptual illustration of a semaphore regulating access to a resource pool:

![Semaphore Concepts](../images/image24.png)

*Figure 20.5.1: Semaphore managing virtual permits to regulate concurrent thread access*

---

## Binary Semaphores (Mutexes)

A **`Binary Semaphore`** is a semaphore initialized with an initial permit count of **1**. 

It can be used as a **mutual exclusion lock (Mutex)** with **non-reentrant** locking semantics. Whichever thread holds the single permit is said to hold the lock. Under this model, the thread performs its critical section and then simply releases the permit back to the semaphore.

> **Pitfall: Non-Reentrant Deadlocks**
> Unlike a standard `ReentrantLock` (which allows the lock owner to acquire the lock multiple times), a binary semaphore is strictly non-reentrant. If the thread holding the permit attempts to acquire it again without releasing it first, the thread will block itself indefinitely, causing a deadlock.

Here is an example of implementing a thread-safe counter using a binary semaphore (mutex) to enforce mutual exclusion:

```java
import java.util.concurrent.Semaphore;

class CounterUsingMutex {
    private final Semaphore mutex;
    private int count;

    public CounterUsingMutex() {
        this.mutex = new Semaphore(1); // Binary semaphore acting as a Mutex
        this.count = 0;
    }

    public void increase() throws InterruptedException {
        mutex.acquire(); // Acquire the lock
        try {
            this.count = this.count + 1;
            Thread.sleep(1000); // Simulate processing latency
        } finally {
            mutex.release(); // Guarantee lock release
        }
    }

    public int getCount() {
        return this.count;
    }

    public boolean hasQueuedThreads() {
        return mutex.hasQueuedThreads();
    }
}
```

*Figure 20.5.2: Thread-safe Counter implementation using a binary semaphore as a Mutex*

When multiple threads attempt to access the counter concurrently, they are placed in the semaphore's internal queue. We can verify this thread queuing behavior and the correctness of the final count using a JUnit test:

```java
import org.junit.jupiter.api.Test;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;
import static org.junit.jupiter.api.Assertions.*;

public class CounterMutexTest {

    @Test
    public void whenMutexAndMultipleThreads_thenBlocked() throws InterruptedException {
        int count = 5;
        ExecutorService executorService = Executors.newFixedThreadPool(count);
        CounterUsingMutex counter = new CounterUsingMutex();

        IntStream.range(0, count)
          .forEach(user -> executorService.execute(() -> {
              try {
                  counter.increase();
              } catch (InterruptedException e) {
                  Thread.currentThread().interrupt();
                  e.printStackTrace();
              }
          }));
        executorService.shutdown();

        // Verify that competing threads are blocked in the queue
        assertTrue(counter.hasQueuedThreads());
    }

    @Test
    public void givenMutexAndMultipleThreads_ThenDelay_thenCorrectCount() throws InterruptedException {
        int count = 5;
        ExecutorService executorService = Executors.newFixedThreadPool(count);
        CounterUsingMutex counter = new CounterUsingMutex();

        IntStream.range(0, count)
          .forEach(user -> executorService.execute(() -> {
              try {
                  counter.increase();
              } catch (InterruptedException e) {
                  Thread.currentThread().interrupt();
                  e.printStackTrace();
              }
          }));
        executorService.shutdown();

        assertTrue(counter.hasQueuedThreads());
        
        // Wait for all threads to complete their work
        Thread.sleep(5000);
        
        // Verify that no threads are left in the queue and the count is correct
        assertFalse(counter.hasQueuedThreads());
        assertEquals(count, counter.getCount());
    }
}
```

*Figure 20.5.3: JUnit tests verifying thread queuing and state updates on a Mutex*

---

## Three Primary Use Cases for Semaphores

### 1. Implementing Resource Pools (e.g., Connection Pools)

A semaphore is the ideal tool for managing a fixed-size pool of expensive resources, such as database connections or network sockets. 

Below is a program demonstrating a resource pool managed by a semaphore:

```java
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Semaphore;

public class SemaphoreResourcePoolDemo {

    static class ResourcePool {
        private final int poolSize = 5;
        private final Semaphore permitter = new Semaphore(poolSize);
        private final List<Object> resources = new ArrayList<>();

        public ResourcePool() {
            // Pre-populate the pool with resources
            for (int i = 0; i < poolSize; i++) {
                resources.add(new Object());
            }
        }

        public Object getResource() {
            // Attempt to acquire a permit atomically
            if (permitter.tryAcquire()) {
                System.out.println(Thread.currentThread().getName() + ": Permit available! Acquired resource.");
                synchronized (resources) {
                    return resources.remove(0); // Safely remove from non-thread-safe ArrayList
                }
            }
            System.out.println(Thread.currentThread().getName() + ": No permits available!");
            return null;
        }

        public void returnResource(Object resource) {
            if (resource == null) return;
            synchronized (resources) {
                resources.add(resource); // Safely add back
            }
            permitter.release(); // Return permit to semaphore
            System.out.println(Thread.currentThread().getName() + ": Released resource!");
        }
    }

    public static void main(String[] args) throws InterruptedException {
        ResourcePool resourcePool = new ResourcePool();
        Object[] acquired = new Object[7];

        // Attempt to acquire 7 resources (only 5 exist in the pool)
        for (int i = 0; i < 7; i++) {
            acquired[i] = resourcePool.getResource();
        }

        // Return 5 resources back to the pool
        for (int i = 0; i < 5; i++) {
            resourcePool.returnResource(acquired[i]);
        }
    }
}
```

*Figure 20.5.4: Managing a fixed-size resource pool using a Semaphore*

#### Output
```text
main: Permit available! Acquired resource.
main: Permit available! Acquired resource.
main: Permit available! Acquired resource.
main: Permit available! Acquired resource.
main: Permit available! Acquired resource.
main: No permits available!
main: No permits available!
main: Released resource!
main: Released resource!
main: Released resource!
main: Released resource!
main: Released resource!
```

> [!WARNING]
> **Pitfall: Check-Then-Act on availablePermits()**
> In concurrent environments, never use `availablePermits() > 0` followed by `acquire()`. 
> 
> This is a classic **check-then-act race condition**. Between the time a thread checks if a permit is available and the time it calls `acquire()`, another thread may have hijacked the permit. 
> 
> To prevent this, always use **`tryAcquire()`** (which checks and acquires atomically) or call **`acquire()`** directly and handle the potential blocking or interruption.

### 2. Concurrency Rate Limiting (e.g., Login Queue)

Another common use case is rate-limiting user activities, such as restricting the number of concurrent active sessions or logins in a system to protect against resource exhaustion. 

Below is an implementation of a login queue using a semaphore:

```java
import java.util.concurrent.Semaphore;

class LoginQueueUsingSemaphore {
    private final Semaphore semaphore;

    public LoginQueueUsingSemaphore(int slotLimit) {
        this.semaphore = new Semaphore(slotLimit);
    }

    public boolean tryLogin() {
        // Return true if a permit is available immediately, false otherwise
        return semaphore.tryAcquire(); 
    }

    public void logout() {
        semaphore.release();
    }

    public int availableSlots() {
        return semaphore.availablePermits();
    }
}
```

*Figure 20.5.5: Login rate limiter using Semaphore.tryAcquire()*

We can test the login queue to verify that when the capacity limit is reached, further login attempts are rejected immediately instead of blocking, and that slots become available again once a user logs out:

```java
import org.junit.jupiter.api.Test;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;
import static org.junit.jupiter.api.Assertions.*;

public class LoginQueueTest {

    @Test
    public void givenLoginQueue_whenReachLimit_thenBlocked() {
        int slots = 10;
        ExecutorService executorService = Executors.newFixedThreadPool(slots);
        LoginQueueUsingSemaphore loginQueue = new LoginQueueUsingSemaphore(slots);

        IntStream.range(0, slots)
          .forEach(user -> executorService.execute(loginQueue::tryLogin));
        executorService.shutdown();

        assertEquals(0, loginQueue.availableSlots());
        assertFalse(loginQueue.tryLogin()); // Further logins are rejected
    }

    @Test
    public void givenLoginQueue_whenLogout_thenSlotsAvailable() {
        int slots = 10;
        ExecutorService executorService = Executors.newFixedThreadPool(slots);
        LoginQueueUsingSemaphore loginQueue = new LoginQueueUsingSemaphore(slots);

        IntStream.range(0, slots)
          .forEach(user -> executorService.execute(loginQueue::tryLogin));
        executorService.shutdown();
        
        assertEquals(0, loginQueue.availableSlots());
        
        // Log out one user
        loginQueue.logout();

        assertTrue(loginQueue.availableSlots() > 0);
        assertTrue(loginQueue.tryLogin()); // Slot becomes available again
    }
}
```

*Figure 20.5.6: JUnit tests verifying the login rate-limiter behavior*

### 3. Building Bounded Blocking Collections

You can turn any standard, unbounded collection (like an `ArrayList` or `HashSet`) into a bounded blocking collection by wrapping it with a semaphore. The semaphore acts as a gatekeeper, blocking threads from adding elements once the collection reaches its capacity limit.

```java
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.Semaphore;

public class BoundedBlockingArrayList<T> {
    private final List<T> list;
    private final Semaphore sem;

    public BoundedBlockingArrayList(int bound) {
        // Wrap a standard ArrayList in a synchronized decorator
        this.list = Collections.synchronizedList(new ArrayList<>());
        // Initialize the semaphore with the collection boundary size
        this.sem = new Semaphore(bound);
    }

    public boolean add(T o) throws InterruptedException {
        sem.acquire(); // Blocks if the collection is full (no permits available)
        boolean added = false;
        try {
            added = list.add(o);
            return added;
        } finally {
            // If the element was not successfully added, release the permit immediately
            if (!added) {
                sem.release(); 
            }
        }
    }

    public boolean remove(Object o) {
        boolean removed = list.remove(o);
        if (removed) {
            // Release a permit when an element is removed, allowing a blocked producer to insert
            sem.release(); 
        }
        return removed;
    }
}
```

*Figure 20.5.7: Bounding a standard ArrayList using a Semaphore*

#### How it Works
1.  **Imposing Boundaries**: The underlying `ArrayList` has no concept of a capacity limit. The bounded behavior is enforced entirely by the `Semaphore` wrapping the operations.
2.  **Acquiring on Insert**: The `add()` method must acquire a permit before inserting. If the list size equals the bound, all permits are exhausted, and subsequent `add()` calls block at `sem.acquire()`.
3.  **Releasing on Remove**: The `remove()` method releases a permit upon a successful deletion. This increments the permit count, unblocking a thread waiting in `add()`.

---

## Timed Semaphores (Apache Commons)

In addition to standard JDK semaphores, the Apache Commons Concurrency library provides a specialized class called **`TimedSemaphore`** (`org.apache.commons.lang3.concurrent.TimedSemaphore`).

A `TimedSemaphore` regulates access based on a **permit limit within a given time period**. 
- It maintains a pool of permits for a specified time duration (e.g., 50 permits per second).
- Once the time period expires, the semaphore **automatically resets** and releases all permits, allowing a new batch of operations to proceed.
- This is exceptionally useful for implementing **rate-limiting APIs** (such as restricting a client to 100 API requests per minute) or building delay/rate-limiting queues.

Below is an implementation of a delay/rate-limiting queue using `TimedSemaphore`:

```java
import org.apache.commons.lang3.concurrent.TimedSemaphore;
import java.util.concurrent.TimeUnit;

class DelayQueueUsingTimedSemaphore {
    private final TimedSemaphore semaphore;

    public DelayQueueUsingTimedSemaphore(long period, int slotLimit) {
        // Permits slotLimit acquisitions within the specified time period (in seconds)
        this.semaphore = new TimedSemaphore(period, TimeUnit.SECONDS, slotLimit);
    }

    public boolean tryAdd() {
        return semaphore.tryAcquire();
    }

    public int availableSlots() {
        return semaphore.getAvailablePermits();
    }
}
```

*Figure 20.5.8: Delay/Rate-Limiting Queue using Apache Commons TimedSemaphore*

### Verifying TimedSemaphore Behavior

We can verify that once the permit limit is reached within a one-second period, further attempts are blocked. However, once the one-second period passes, the semaphore automatically resets, releasing all permits:

```java
import org.junit.jupiter.api.Test;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;
import static org.junit.jupiter.api.Assertions.*;

public class TimedSemaphoreTest {

    @Test
    public void givenDelayQueue_whenReachLimit_thenBlocked() {
        int slots = 50;
        ExecutorService executorService = Executors.newFixedThreadPool(slots);
        DelayQueueUsingTimedSemaphore delayQueue = new DelayQueueUsingTimedSemaphore(1, slots);

        IntStream.range(0, slots)
          .forEach(user -> executorService.execute(delayQueue::tryAdd));
        executorService.shutdown();

        assertEquals(0, delayQueue.availableSlots());
        assertFalse(delayQueue.tryAdd()); // Limit reached, further attempts rejected
    }

    @Test
    public void givenDelayQueue_whenTimePass_thenSlotsAvailable() throws InterruptedException {
        int slots = 50;
        ExecutorService executorService = Executors.newFixedThreadPool(slots);
        DelayQueueUsingTimedSemaphore delayQueue = new DelayQueueUsingTimedSemaphore(1, slots);

        IntStream.range(0, slots)
          .forEach(user -> executorService.execute(delayQueue::tryAdd));
        executorService.shutdown();

        assertEquals(0, delayQueue.availableSlots());
        
        // Sleep for 1 second to allow the time period to reset
        Thread.sleep(1000);
        
        assertTrue(delayQueue.availableSlots() > 0);
        assertTrue(delayQueue.tryAdd()); // Permits are automatically released
    }
}
```

*Figure 20.5.9: JUnit tests verifying TimedSemaphore reset cycles*

---

## CountDownLatch vs. Semaphore

Effective coordination between threads is crucial to ensure proper synchronization, prevent data corruption, and manage system resources. Both `CountDownLatch` and `Semaphore` are powerful tools, but they solve entirely different coordination patterns.

### Key Differences

| Feature | CountDownLatch | Semaphore |
| :--- | :--- | :--- |
| **Purpose** | Synchronize one or more threads until a set of tasks completes. | Control concurrent access to shared resources or critical sections. |
| **Counting Mechanism** | Decrements a counter down to zero. | Manages a pool of virtual permits (tokens) that can go up and down. |
| **Resettability** | **Single-use**. Once the counter reaches zero, it cannot be reset or reused. | **Reusable**. Permits can be released and acquired multiple times. |
| **Dynamic Adjustment** | No. The initial count remains fixed at runtime. | Yes. Permits can be dynamically adjusted or released at runtime. |
| **Fairness Policy** | No fairness concept. | Supports **Fairness**, serving waiting threads in strict FIFO order to avoid starvation. |
| **Performance Overhead** | Extremely low (involves only decrementing a counter). | Slightly higher (requires managing a queue of waiting threads and permit states). |

---

> **Problem: The Reusable Resource Pool Trap**
> Attempting to use a `CountDownLatch` to manage access to a limited pool of resources (like database connections) is a severe design error. Because a latch is a single-use gate, once the available resource count reaches zero and the gate opens, the latch can never be reset or closed. Any subsequent thread will bypass the gate immediately, bypassing the resource limit and crashing the system. For resource pools, a `Semaphore` is mandatory.

---

> **Insights: Choosing the Right Primitive**
> *   **Use `CountDownLatch`** when you need to coordinate **one-time events** (e.g., waiting for parallel data-loading tasks to complete before starting analysis, or blocking worker threads until a system initialization task finishes).
> *   **Use `Semaphore`** when you need to enforce a **concurrency limit** on a long-lived shared resource (e.g., limiting concurrent API calls to an external service to 10, or managing a database connection pool).

---

### Implementation Comparison

#### 1. CountDownLatch (Waiting for a Batch of Tasks)
A latch is used once to wait for a fixed number of worker tasks to finish:

```java
int numberOfTasks = 3;
CountDownLatch latch = new CountDownLatch(numberOfTasks);

for (int i = 1; i <= numberOfTasks; i++) {
    new Thread(() -> {
        System.out.println("Task completed by Thread " + Thread.currentThread().getId());
        latch.countDown(); // Decrement count
    }).start();
}

latch.await(); // Block main thread until count reaches 0
System.out.println("All tasks completed. Main thread proceeds.");

// Subsequent calls return immediately
latch.countDown();
latch.await(); // Does NOT block
System.out.println("Latch is already at zero and cannot be reset.");
```

#### 2. Semaphore (Regulating Shared Resource Access)
A semaphore dynamically controls access to resources using permits that are acquired and released repeatedly:

```java
int NUM_PERMITS = 3;
Semaphore semaphore = new Semaphore(NUM_PERMITS);

for (int i = 1; i <= 5; i++) {
    new Thread(() -> {
        try {
            semaphore.acquire(); // Acquire a permit, block if none available
            System.out.println("Thread " + Thread.currentThread().getId() + " accessing resource.");
            Thread.sleep(2000); // Simulate resource usage
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            semaphore.release(); // Return permit back to pool
        }
    }).start();
}

// Dynamically adjust permits at runtime (resetting or expanding the pool)
try {
    Thread.sleep(5000);
    semaphore.release(NUM_PERMITS); // Expand the permit count dynamically
    System.out.println("Semaphore permits expanded dynamically.");
} catch (InterruptedException e) {
    Thread.currentThread().interrupt();
}
```

---

## Summary

*   **Counting Semaphore**: A synchronizer that manages a set of virtual permits to control how many threads or concurrent activities can access a resource or execute an action simultaneously.
*   **Permit Coordination**:
    - `acquire()`: Decrements the permit count, blocking the calling thread if no permits are available.
    - `release()`: Increments the permit count, unblocking waiting threads.
    - `tryAcquire()`: Atomic check-and-acquire method that returns `false` immediately instead of blocking if no permits are available.
*   **Binary Semaphore (Mutex)**: A semaphore initialized with a permit count of 1. It provides mutual exclusion with non-reentrant locking semantics.
*   **TimedSemaphore (Apache Commons)**: A specialized semaphore that limits permit acquisition within a specific time period. It automatically resets and releases all permits when the period passes, which is ideal for API rate-limiting.
*   **Resource Pools**: Semaphores are ideal for implementing fixed-size resource pools (e.g., database connection pools) by mapping permits directly to available resource objects.
*   **Bounded Collections**: Wrapping an unbounded collection with a semaphore allows you to enforce a strict capacity limit, blocking producers when the collection is full.
