# ThreadLocal in Java

In the previous modules, we explored how synchronization and volatile variables allow threads to safely share mutable data. In this module, we will examine an alternative approach to thread-safety: **Thread Confinement** using the **`ThreadLocal`** construct from the `java.lang` package.

Instead of synchronizing access to shared data, `ThreadLocal` allows us to store data individually for each thread, ensuring that each thread has its own private, isolated copy of the variable.

---

## ThreadLocal API

The `ThreadLocal` construct allows us to store data that is accessible only by a specific thread.

### Core Operations

*   **Initialization**: We can instantiate a `ThreadLocal` variable. To provide a default initial value, we can use the `ThreadLocal.withInitial()` static factory method and pass a `Supplier` to it:
    ```java
    ThreadLocal<Integer> threadLocal = ThreadLocal.withInitial(() -> 1);
    ```
*   **Writing Data (`set()`)**: A thread can store a thread-confined value:
    ```java
    threadLocalValue.set(42);
    ```
*   **Reading Data (`get()`)**: A thread can retrieve its confined value. If no value has been set for the current thread, it returns the initial value (or `null` if no initial supplier was provided):
    ```java
    Integer result = threadLocalValue.get();
    ```
*   **Cleaning Up (`remove()`)**: To prevent memory leaks and clear the thread-local value for the current thread, we call:
    ```java
    threadLocal.remove();
    ```

---

> **Mental Model: Thread-Confined Memory (The Implicit Map)**
> Think of a `ThreadLocal` instance as a specialized map where the **current executing Thread** is the implicit key. When a thread calls `threadLocal.set(value)`, it writes to its own private storage area that other threads cannot access. When it calls `threadLocal.get()`, the JVM automatically looks up the value associated with the requesting thread:
> 
> ```text
> threadLocal.get()  ==>  internalMap.get(Thread.currentThread())
> threadLocal.set(v) ==>  internalMap.put(Thread.currentThread(), v)
> ```

---

## Storing User Data: Two Approaches

To see how `ThreadLocal` works in practice, let's compare two ways of storing user-specific context data (e.g., user sessions or transaction contexts) in a multi-threaded application:
1.  Using a shared concurrent map.
2.  Using a shared `ThreadLocal` instance.

Here is the simple user context class that we want to store:

```java
public class Context {
    private String userName;

    public Context(String userName) {
        this.userName = userName;
    }

    @Override
    public String toString() {
        return "Context{userName='" + userName + "'}";
    }
}
```

---

### Approach 1: Storing User Data in a Shared Map

In this approach, we maintain a central, thread-safe `ConcurrentHashMap` where user contexts are stored, keyed by their `userId`. Each runnable task fetches user context from a repository and stores it in the shared map.

```java
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class SharedMapWithUserContext implements Runnable {
 
    public static Map<Integer, Context> userContextPerUserId = new ConcurrentHashMap<>();
    private Integer userId;
    private UserRepository userRepository = new UserRepository();

    public SharedMapWithUserContext(Integer userId) {
        this.userId = userId;
    }

    @Override
    public void run() {
        String userName = userRepository.getUserNameForUserId(userId);
        userContextPerUserId.put(userId, new Context(userName));
    }
}
```

We can test this code by starting two threads for two different user IDs and asserting that two entries are stored in the shared map:

```java
SharedMapWithUserContext firstUser = new SharedMapWithUserContext(1);
SharedMapWithUserContext secondUser = new SharedMapWithUserContext(2);

Thread t1 = new Thread(firstUser);
Thread t2 = new Thread(secondUser);

t1.start();
t2.start();
t1.join();
t2.join();

assertEquals(2, SharedMapWithUserContext.userContextPerUserId.size());
```

---

> **Problem: Shared Map Overhead and Coupling**
> While this approach works, it has several drawbacks:
> 1.  **Thread Coupling**: Every piece of code that needs the current user's context must have access to the user's ID and the central map to look up the data.
> 2.  **Contention**: Under high concurrency, threads will contend for access to the shared map, creating performance bottlenecks.
> 3.  **Memory Leak Risk**: If users log out or threads complete, we must manually clean up the map entries, otherwise the map will grow indefinitely.

---

### Approach 2: Storing User Data in ThreadLocal

We can rewrite the example to use a shared `ThreadLocal` instance. Each thread stores its user context directly inside the `ThreadLocal` object, removing the need for a central map.

```java
public class ThreadLocalWithUserContext implements Runnable {
 
    private static ThreadLocal<Context> userContext = new ThreadLocal<>();
    private Integer userId;
    private UserRepository userRepository = new UserRepository();

    public ThreadLocalWithUserContext(Integer userId) {
        this.userId = userId;
    }

    @Override
    public void run() {
        String userName = userRepository.getUserNameForUserId(userId);
        userContext.set(new Context(userName));
        System.out.println("thread context for given userId: " 
          + userId + " is: " + userContext.get());
    }
}
```

We can test this by starting two threads that execute the task:

```java
ThreadLocalWithUserContext firstUser = new ThreadLocalWithUserContext(1);
ThreadLocalWithUserContext secondUser = new ThreadLocalWithUserContext(2);

Thread t1 = new Thread(firstUser);
Thread t2 = new Thread(secondUser);

t1.start();
t2.start();
t1.join();
t2.join();
```

**Output:**
```text
thread context for given userId: 1 is: Context{userName='User_1'}
thread context for given userId: 2 is: Context{userName='User_2'}
```

Each thread successfully accesses its own isolated context from the same static `ThreadLocal` reference, without passing the context or the user ID around.

---

## Thread Sharing vs. Thread Confinement

The table below highlights the structural differences between sharing state with synchronization and confining state via `ThreadLocal`:

| Dimension | Shared State with Synchronization | Thread Confinement via `ThreadLocal` |
| :--- | :--- | :--- |
| **Data Sharing** | Threads share the exact same object instances. | Each thread has its own independent copy of the object. |
| **Locking Overhead** | High (threads can block waiting for locks). | Zero (no locks or synchronization needed). |
| **Memory Footprint** | Low (only one shared object instance). | Higher (one object instance per thread). |
| **Best Use Case** | Collaborative state (e.g., counters, queues). | Contextual data (e.g., user sessions, database connections, transaction contexts). |
| **Memory Leak Risk** | Low. | High (especially when used with thread pools if not cleaned up). |

---

## ThreadLocals and Thread Pools

While `ThreadLocal` provides a convenient way to achieve thread-safety, it introduces a significant safety hazard when combined with **thread pools** (like those managed by an `ExecutorService`).

### The Thread Pool Reuse Hazard

In a thread pool, threads are not destroyed when a task completes. Instead, they are returned to the pool to be reused for subsequent tasks. If a task stores a value in a `ThreadLocal` and does not clean it up, the next task executed by that same thread will inherit the dirty state left behind:

```text
Task A (Thread-1)  ==> threadLocal.set("User_A")
Task A completes   ==> Thread-1 returns to pool (WITHOUT cleanup)
Task B (Thread-1)  ==> threadLocal.get() returns "User_A"! (Information Leak / Bug)
```

This can lead to information leaks, security violations, and highly unpredictable application behavior.

---

> **Pitfalls: Thread Pool Memory Leaks**
> If a thread-local variable is not removed using `.remove()`, the object reference remains held by the thread's internal map (`ThreadLocalMap`). Since thread pool threads live for the entire lifetime of the application, any objects stored in their `ThreadLocal` fields will never be garbage collected, leading to severe memory leaks.

---

### Solution 1: Manual Cleanup (Try-Finally)

The simplest way to avoid thread pool contamination is to always wrap your `ThreadLocal` usage in a `try-finally` block, ensuring that `remove()` is called before the task exits:

```java
public void run() {
    try {
        String userName = userRepository.getUserNameForUserId(userId);
        userContext.set(new Context(userName));
        // Execute business logic...
    } finally {
        userContext.remove(); // Guaranteed cleanup
    }
}
```

---

### Solution 2: Extending ThreadPoolExecutor

For a more centralized solution, you can extend the `ThreadPoolExecutor` class and override its `afterExecute()` hook. The thread pool automatically invokes this hook after executing every runnable task, allowing you to clean up thread-local variables programmatically:

```java
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;

public class ThreadLocalAwareThreadPool extends ThreadPoolExecutor {

    public ThreadLocalAwareThreadPool(int corePoolSize, int maximumPoolSize, 
                                      long keepAliveTime, TimeUnit unit, 
                                      BlockingQueue<Runnable> workQueue) {
        super(corePoolSize, maximumPoolSize, keepAliveTime, unit, workQueue);
    }

    @Override
    protected void afterExecute(Runnable r, Throwable t) {
        super.afterExecute(r, t);
        // Call remove on each ThreadLocal to clean up the thread state
        // For example: UserContextHolder.clear();
    }
}
```

By submitting tasks to a thread-local-aware thread pool, you guarantee that threads are fully scrubbed of their confined state before being reused.

---

> **Insights: Thread Confinement as a Design Pattern**
> Thread confinement is a powerful design pattern that eliminates synchronization overhead entirely by ensuring data is never shared. By combining `ThreadLocal` with robust cleanup policies (like `afterExecute` hooks or `finally` blocks), you can design highly scalable, concurrent architectures for request-scoped data like user sessions, database transactions, and cryptographic context.

---

## ThreadLocalRandom

Generating random values is a common task in software development. While Java provides the classic **`java.util.Random`** class for this purpose, it performs poorly in highly concurrent, multi-threaded environments. To resolve this limitation, Java 7 introduced **`java.util.concurrent.ThreadLocalRandom`**.

### The Problem: Seed Contention in java.util.Random

To understand why the classic `Random` class scales poorly, let's examine its core bit-generation method, `next(int)`:

```java
private final AtomicLong seed;

protected int next(int bits) {
    long oldseed, nextseed;
    AtomicLong seed = this.seed;
    do {
        oldseed = seed.get();
        nextseed = (oldseed * multiplier + addend) & mask;
    } while (!seed.compareAndSet(oldseed, nextseed)); // CAS loop

    return (int)(nextseed >>> (48 - bits));
}
```

The bit-generation algorithm relies on a shared `AtomicLong` seed. When multiple threads concurrently attempt to generate a random number:
1.  They all read the same shared seed.
2.  They compute the next seed.
3.  They attempt to update the shared seed atomically using **Compare-And-Swap (CAS)**.
4.  Only one thread succeeds; the remaining threads fail the CAS check and are forced to spin in a loop, retrying the operation.

Under high contention, the sheer number of CAS failures and retries degrades CPU performance significantly, causing threads to waste cycles spinning.

---

> **Mental Model: The Shared Seed vs. Private Seed**
> *   **`java.util.Random`**: Imagine a group of friends trying to write on a single shared notepad (the global seed) at the exact same time. Only one person can write at a time; the others must wait and retry on failure.
> *   **`ThreadLocalRandom`**: Each friend has their own private notepad (thread-confined seed) in their pocket. They can write on it instantly without waiting or contending with anyone else.

---

### The ThreadLocalRandom Solution

`ThreadLocalRandom` combines the concepts of `ThreadLocal` and `Random`. It is isolated to the current thread, completely eliminating seed contention. 

Furthermore, `ThreadLocalRandom` does **not** allow setting or modifying the seed explicitly. Attempting to call `setSeed(long)` throws an `UnsupportedOperationException` to prevent compromising the thread-isolated random sequence.

### Generating Random Values

To use `ThreadLocalRandom`, you obtain the current thread's instance by calling the static **`ThreadLocalRandom.current()`** method, and then invoke the desired type-specific generator:

```java
// 1. Generate an unbounded random integer
int unboundedInt = ThreadLocalRandom.current().nextInt();

// 2. Generate a bounded random integer between 0 (inclusive) and 100 (exclusive)
int boundedInt = ThreadLocalRandom.current().nextInt(0, 100);

// 3. Bounded random longs and doubles
long boundedLong = ThreadLocalRandom.current().nextLong(1000L, 5000L);
double boundedDouble = ThreadLocalRandom.current().nextDouble(1.0, 10.0);

// 4. Generate normally-distributed (Gaussian) values (mean = 0.0, std dev = 1.0)
double gaussianValue = ThreadLocalRandom.current().nextGaussian();
```

You can also generate streams of random numbers using `ints()`, `longs()`, and `doubles()` methods, similar to the `Random` class.

---

### Performance Comparison (JMH Benchmark)

Let's compare the performance of `Random` and `ThreadLocalRandom` under high concurrency. We submit 1,000 tasks to an executor pool, measuring the average execution time in microseconds per operation (`us/op`):

#### Sharing a Global Random Instance
```java
Random random = new Random();
for (int i = 0; i < 1000; i++) {
    executor.submit(() -> random.nextInt());
}
```

#### Using Thread-Confined ThreadLocalRandom
```java
for (int i = 0; i < 1000; i++) {
    executor.submit(() -> ThreadLocalRandom.current().nextInt());
}
```

#### JMH Benchmark Results

| Generator | Average Execution Time (lower is better) | Performance Overhead |
| :--- | :--- | :--- |
| **`java.util.Random`** | **771.613 ± 222.220 us/op** | High contention due to CAS retries on the shared seed. |
| **`ThreadLocalRandom`** | **624.911 ± 113.268 us/op** | **~20% Faster** due to zero seed contention. |

---

### Implementation Details: How it Scales Efficiently

In early versions, `ThreadLocalRandom` maintained a dedicated instance of `Random` per thread. In Java 8 and later, the implementation was heavily optimized:

1.  **Singleton Instance**: `ThreadLocalRandom` is now a singleton. Calling `ThreadLocalRandom.current()` always returns the same global instance.
2.  **Thread-Confined Seeds**: Instead of storing the seed in a wrapper object, the **`Thread`** class itself was retrofitted to hold the seed variables directly as primitive fields:
    ```java
    public class Thread implements Runnable {
        long threadLocalRandomSeed; // Confined seed value
        int threadLocalRandomProbe; // Used internally for hashing
        int threadLocalRandomSecondarySeed; // Used by ForkJoinPool
    }
    ```
3.  **False Sharing Protection**: The fields are annotated with **`@Contended("tlr")`**. The JVM adds padding bytes around these fields to isolate them into their own CPU cache lines, preventing **false sharing** (where threads on different cores invalidate each other's caches because their variables reside in the same cache line).
4.  **Low-Level Access**: It uses `jdk.internal.misc.Unsafe` to perform fast, direct memory updates on the `Thread` fields, bypassing Reflection or `ThreadLocal` table lookup overheads.

---

> **Pitfalls: The Thread-Safe Sharing Trap**
> Never share a `ThreadLocalRandom` instance between threads. A common bug is storing the instance returned by `ThreadLocalRandom.current()` in a shared static field. Since the seed variables are looked up based on the *current executing thread*, sharing the instance will cause threads to access different offsets, but it violates the design pattern and can lead to initialization bugs. Always call `ThreadLocalRandom.current()` inline at the point of usage.

---

## Summary

*   **Thread Confinement**: A thread-safety technique where data is confined to a single thread, avoiding the need for synchronization.
*   **`ThreadLocal`**: Java's built-in construct that automates thread confinement by associating object instances with individual threads.
*   **Map Analogy**: Think of `ThreadLocal` as a map keyed by the current thread instance.
*   **The Thread Pool Pitfall**: Thread pools reuse threads. If a thread-local variable is not cleaned up via `remove()`, subsequent tasks running on the same thread will read stale data, and the objects will leak in memory.
*   **Scrubbing State**: Always use `try-finally` blocks to call `remove()` manually, or extend `ThreadPoolExecutor` and override `afterExecute()` to clear thread-local values programmatically.
*   **Seed Contention**: The classic `Random` class scales poorly under high concurrency because multiple threads compete to update a single shared seed using a CAS loop.
*   **`ThreadLocalRandom`**: Eliminates seed contention entirely by storing the seed variables directly inside each `Thread` object.
*   **Direct Inline Usage**: Always invoke `ThreadLocalRandom.current()` inline (e.g., `ThreadLocalRandom.current().nextInt()`) rather than sharing the instance across threads.
*   **Under-the-Hood Optimizations**: Leverages `@Contended` memory padding to eliminate false sharing and uses low-level `Unsafe` memory offsets for maximum execution speed.
