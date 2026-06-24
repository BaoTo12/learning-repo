# Module 03: The Mechanics of Modern Concurrency

### Learning Objectives

- Build a custom Thread Pool (`SimpleThreadPool`) using volatile flags, thread-safe queues, and a `ThreadGroup`.
- Understand the `ThreadPoolExecutor` constructor settings and common types of pools.
- Use `Callable` and `Future` to run tasks concurrently.
- Compare `ThreadPoolExecutor` and `ForkJoinPool` (queues, deques, and LIFO vs. FIFO modes).
- Write lock-free counters using CAS (Compare-And-Swap) and `VarHandle`.
- Write recursive tasks using `RecursiveTask` to avoid thread starvation.
- Understand continuation stacks, lazy copying, and return barriers.
- Build a simple virtual thread scheduler simulation (`NanoThread` & `NanoThreadScheduler`).
- Explain how OS event loops (`epoll`, `kqueue`, `wepoll`) wake up virtual threads.

---

### Concept Explanation

#### 1. Thread Pool Basics

Creating normal Java threads (platform threads) is expensive. Each thread needs its own stack and native OS resources, taking up **1 to 2 MiB** of memory. Creating too many threads can run out of memory and crash the JVM.

A **Thread Pool** is a group of worker threads created at startup. Decoupling task submission from execution offers several advantages:

##### Key Benefits

- **Resource Control**: Limits the maximum number of active threads to prevent crashes.
- **Thread Reuse**: Recycles threads instead of creating and destroying them.
- **Queue Management**: Buffers incoming tasks in a thread-safe queue.
- **Graceful Shutdown**: Waits for active tasks to finish before stopping.
- **Simpler Code**: Lets you focus on business logic instead of thread management.

##### Traditional Pools Remain Relevant

Virtual threads are great for I/O-bound tasks, but traditional thread pools are still important. For example, a study using the **OpenLiberty** server found that its optimized traditional thread pool outperformed virtual threads in some high-load benchmarks. Learning how to use traditional pools is still a core skill.

---

#### 2. Building a Simple Thread Pool

To understand how pools work, we can build a basic one (`SimpleThreadPool`) from scratch. It needs:

1. A `BlockingQueue<Runnable>` to hold tasks.
2. A group of `Worker` threads that pull and run tasks from the queue.
3. A `volatile boolean running` flag to control shutdown.
4. A `ThreadGroup` to manage worker threads together.
5. An `AutoCloseable` interface to support try-with-resources.

##### Bounded Queue and Backpressure

Using a queue with a fixed size provides **backpressure**. If the queue is full, the `submit()` method blocks. This slows down the sender when the pool is overloaded.

##### Graceful Shutdown

The `close()` method waits until the queue is empty, sets `running = false`, and interrupts all worker threads at once using the `ThreadGroup`. This wakes them up and stops them cleanly.

---

#### 3. The Executor Framework

Java's `ThreadPoolExecutor` is the standard class for managing thread pools:

```java
public ThreadPoolExecutor(
    int corePoolSize,
    int maximumPoolSize,
    long keepAliveTime,
    TimeUnit unit,
    BlockingQueue<Runnable> workQueue,
    ThreadFactory threadFactory,
    RejectedExecutionHandler handler
)
```

##### Key Parameters

- **`corePoolSize`**: The minimum number of threads kept alive, even if idle.
- **`maximumPoolSize`**: The maximum number of threads allowed.
- **`keepAliveTime` & `unit`**: How long extra idle threads wait for tasks before shutting down.
- **`workQueue`**: The queue holding tasks (e.g., `LinkedBlockingQueue`).
- **`threadFactory`**: Creates new threads with custom names or settings.
- **`handler`**: What to do when the queue is full and no more threads can be created (e.g., aborting or running on the caller thread).

##### Sizing Strategy

- **CPU-Bound Work** (e.g., math, rendering): Match the number of CPU cores. Too many threads cause slow context switching.
- **I/O-Bound Work** (e.g., database queries): Use more threads than CPU cores, so other threads can run while some wait for I/O.

##### Common Pool Types (`java.util.concurrent.Executors`)

- **`newFixedThreadPool(n)`**: A fixed size pool. Uses an unbounded queue.
- **`newCachedThreadPool()`**: Spawns threads as needed and shuts them down when idle. Can run out of memory under sudden high load.
- **`newSingleThreadExecutor()`**: Uses exactly one thread to run tasks one after another.
- **`newScheduledThreadPool(n)`**: Runs tasks after a delay or at regular intervals.
- **`newWorkStealingPool()`**: Uses a work-stealing pool to share work across all CPU cores.

---

#### 4. Callable and Future

`Callable` is like `Runnable`, but its method can return a value and throw checked exceptions:

```java
@FunctionalInterface
public interface Callable<V> {
    V call() throws Exception;
}
```

##### Future Methods

Submitting a `Callable` returns a `Future` object:

- **`Future.get()`**: Waits for the task to finish and returns the result. This blocks the calling thread.
- **`Future.isDone()`**: Checks if the task is complete.
- **`Future.cancel()`**: Cancels the task.

To run tasks concurrently, submit them to a pool, collect their `Future` objects, and read the results:

```java
package com.example.concurrency;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.*;

public class FibonacciPipeline {
    private static final ConcurrentHashMap<Integer, Long> cache = new ConcurrentHashMap<>(
        Map.of(0, 0L, 1, 1L)
    );

    public static void main(String[] args) throws Exception {
        List<Future<Long>> futures = new ArrayList<>();
        List<Integer> targets = List.of(10, 20, 30, 40, 50);

        try (ExecutorService pool = Executors.newCachedThreadPool()) {
            for (int index : targets) {
                futures.add(pool.submit(() -> fibonacci(index)));
            }

            for (Future<Long> f : futures) {
                // Blocking get() retrieves the result once computed
                System.out.println("Computed value: " + f.get());
            }
        }
    }

    private static Long fibonacci(int n) {
        return cache.computeIfAbsent(n, k -> fibonacci(k - 1) + fibonacci(k - 2));
    }
}
```

##### How the Fibonacci Pipeline Works

1. **Submitting Tasks**: We submit tasks to the pool. Each submission returns a `Future` which will hold the result later.
2. **Safe Caching (`ConcurrentHashMap`)**: Multiple threads calculate values in parallel. We use `ConcurrentHashMap.computeIfAbsent` to avoid duplicate math and keep the cache thread-safe without slow global locks.
3. **Reading Results**: The main thread loops through the futures and calls `.get()`. Since `.get()` blocks, the results are printed in order. If an early task is slow, the main thread waits for it, even if later tasks finished first.

---

#### 5. ForkJoinPool and Work-Stealing

The `ForkJoinPool` is designed for splitting large tasks into smaller ones.

##### ForkJoinPool vs. ThreadPoolExecutor

- **Private Deques**: Standard thread pools use one shared queue, which can slow down threads due to queue conflicts under heavy load. A `ForkJoinPool` gives each worker thread its own double-ended queue (**Deque**).
- **Work-Stealing**: When a thread finishes its own queue, it does not sleep. Instead, it steals tasks from other threads' queues, keeping all CPU cores busy.

##### Inside the Deque

```
   [Worker Owner Thread] (LIFO Pop or FIFO Poll)
            │
            ▼
    +-------+-------+-------+-------+-------+
    | Task1 | Task2 | Task3 | Task4 |       |  (Task Array)
    +-------+-------+-------+-------+-------+
        ▲                               ▲
        │                               │
    [base]                           [top]
        ▲
        │
   [Thief Threads] (FIFO Steal)
```

Each deque uses an array with two pointers:

1. **`top`**: Where the thread owner adds and removes tasks.
2. **`base`**: Where other threads steal tasks.

- **Adding Tasks**: The owner thread pushes tasks to the `top`. This is very fast and does not use locks.
- **Removing Tasks**: The owner thread pulls tasks from the `top` (LIFO mode). This requires no synchronization unless the queue is almost empty.
- **Stealing Tasks**: Sibling threads ("thieves") steal tasks from the **`base`** (FIFO order). They use a Compare-And-Swap (CAS) operation to grab the task. If two threads try to steal the same task, only one wins the CAS check, and the other retries elsewhere.

##### FIFO Mode for Virtual Threads

Virtual threads use a `ForkJoinPool` in **FIFO async mode** (`asyncMode = true`).

- **LIFO Mode (Default for Parallel Streams)**: Runs the newest tasks first. This keeps data in the CPU cache. But for web servers, it can cause older requests to starve as new ones arrive.
- **FIFO Mode**: Runs the oldest tasks first. This ensures fairness and prevents requests from timing out.

##### Lock-Free CAS Queues

```java
package com.example.concurrency;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;

public class AtomicCounter {
    private volatile int value = 0;
    private static final VarHandle VALUE_HANDLE;

    static {
        try {
            VALUE_HANDLE = MethodHandles.lookup()
                .findVarHandle(AtomicCounter.class, "value", int.class);
        } catch (ReflectiveOperationException e) {
            throw new Error(e);
        }
    }

    public void increment() {
        int current;
        int next;
        do {
            current = value;
            next = current + 1;
        } while (!VALUE_HANDLE.compareAndSet(this, current, next)); // Lock-free atomic loop
    }

    public int get() { return value; }
}
```

##### How CAS and VarHandle Work

1. **Direct Memory Access**: `VarHandle` points directly to the memory address of a field. This avoids standard getter/setter overhead and runs direct CPU instructions.
2. **The CAS Loop**: The thread reads a value, calculates the new value, and uses `compareAndSet` to write it. If another thread changed the value in the meantime, the write fails, and the loop retries.
3. **No Lock Overhead**: Because threads do not acquire locks, they do not block or switch to the OS kernel, which maximizes performance.

---

#### 6. CPU Caches, MESI, and Volatile

To understand how thread safety works at the hardware level, we must look at how CPU cores share memory.

##### 1. Caching Hierarchy

Cores use fast, local L1 and L2 caches and a shared L3 cache to avoid waiting for slow main memory:

```
+---------------------------------------+
|              Main Memory              |
+---------------------------------------+
                    │
                    ▼
+---------------------------------------+
|             L3 Cache (Shared)         |
+---------------------------------------+
         ▲                     ▲
         │                     │
+-----------------+   +-----------------+
| L2 Cache (Core0)|   | L2 Cache (Core1)|
+-----------------+   +-----------------+
         ▲                     ▲
         │                     │
+-----------------+   +-----------------+
| L1 Cache (Core0)|   | L1 Cache (Core1)|
+-----------------+   +-----------------+
         ▲                     ▲
         │                     │
+-----------------+   +-----------------+
|   Core 0 Regs   |   |   Core 1 Regs   |
+-----------------+   +-----------------+
```

CPUs read and write memory in 64-byte blocks called **Cache Lines**. If two cores load the same variable, they both hold a copy of its cache line. If Core 0 changes the variable, Core 1's copy becomes stale.

##### 2. The MESI Protocol

CPUs use the **MESI** protocol to keep caches in sync:

- **Modified (M)**: The line is only in this core's cache and has been changed.
- **Exclusive (E)**: The line is only in this core's cache and matches main memory.
- **Shared (S)**: The line is in multiple cores' caches and matches main memory.
- **Invalid (I)**: The data is outdated and cannot be used.

If Core 0 wants to write to a shared line, it must send an **Invalidate** message. Other cores mark their copies as `I` (Invalid) and send back an **Invalidate Acknowledge**. Core 0 can only write once all replies arrive.

##### 3. Store Buffers and Invalidation Queues

Waiting for invalidation replies slows down the CPU. Hardware designers added two optimizations:

1. **Store Buffers**: The core writes changes to a store buffer and continues executing immediately. The buffer handles the invalidation messages in the background.
2. **Invalidation Queues**: A core receiving an Invalidate message puts it in a queue and replies immediately. It processes the queue and invalidates cache lines later when convenient.

**The Problem**: Because of these buffers and queues, writes can stay hidden in a store buffer, and cores can continue reading stale data from their caches, breaking thread visibility.

##### 4. Memory Barriers (Fences)

To fix this, the CPU must be told to skip these optimizations:

- **Write Barrier**: Flushes the store buffer, forcing writes to the cache.
- **Read Barrier**: Processes the invalidation queue, marking stale cache lines as invalid.
- **Full Barrier**: Does both, preventing any instruction reordering.

##### 5. Volatile in Java

Marking a field as `volatile` tells the JVM to insert memory barriers:

- **Volatile Write**: Flushes the store buffer immediately, broadcasting changes to all cores.
- **Volatile Read**: Forces the CPU to empty its invalidation queue, ensuring it reads fresh data from memory.

This guarantees that:
- **Visibility**: A write to a volatile variable is immediately visible to all subsequent reads.
- **No Reordering**: The compiler and CPU cannot reorder instructions across the volatile boundary.

##### RecursiveTask and Deadlock Avoidance

Recursive tasks in normal pools can easily deadlock if all threads block waiting for subtasks (e.g., `Future.get()`). `ForkJoinPool` avoids this: when a task waits on `join()`, the worker thread runs other pending tasks or steals work instead of blocking, preventing deadlocks.

---

#### 7. Continuation Theory: Yielding and Resuming

A **Continuation** is a program's execution state (local variables, stack, and instruction pointer) that can be paused (yielded) and resumed later.

##### Memory and Stack Frame Lifecycle

- **Heap Allocation**: Virtual thread stack frames are stored as normal objects on the heap, not in off-heap memory.
- **Lazy Copying**: Copying the whole stack is slow. When a continuation resumes, the JVM only copies the top few stack frames back to the carrier thread.
- **Return Barriers**: The JVM puts return barriers at the edge of the copied frames. When the method returns, the barrier triggers and copies the next set of frames from the heap on-demand.

##### Deep Dive: Inside freeze and thaw Mechanics

###### 1. Continuation Layout on the Heap

A `Continuation` object contains:
- **`stack`**: An array storing the raw binary stack data (variables and registers).
- **`fp` (Frame Pointer) and `sp` (Stack Pointer)**: Offset pointers.
- **`pc` (Program Counter)**: The address of the next instruction.

###### 2. The Freeze Process (Yielding)

When a virtual thread blocks, the JVM calls `Continuation.yield()`, freezing the stack:

```
[Carrier Stack] (Active Execution)
┌─────────────────────────┐
│ frame 2 (fetchUser)     │ ──┐
├─────────────────────────┤   │  Freeze copies frames
│ frame 1 (processOrder)  │ ──┼───────────────────────┐
├─────────────────────────┤   │                       ▼
│ frame 0 (run)           │ ──┘             [Continuation Object on Heap]
└─────────────────────────┘                 ┌───────────────────────────┐
                                            │ [int[] stack array]       │
                                            │  [frame 0] [frame 1] ...  │
                                            └───────────────────────────┘
```

1. **Stack Walk**: The JVM walks up the carrier thread's stack to find the virtual thread's frames.
2. **Copying**: The JVM copies these frames into the heap array.
3. **Cleanup**: It clears references from the carrier thread to avoid memory leaks.
4. **Context Swap**: It resets the carrier's registers back to the ForkJoinPool scheduler, freeing the carrier thread.

###### 3. The Thaw Process (Resuming)

When a virtual thread is rescheduled, the JVM calls `Continuation.run()`, thawing the stack:

1. **Lazy Copying**: The JVM copies only the topmost frame back onto the carrier thread's stack.
2. **Return Barrier**: It injects a return barrier at the bottom of the thawed frame.
3. **Context Swap**: It updates the CPU registers to point to the thawed frame and starts running.
4. **On-Demand Thawing**: When the method returns, it hits the barrier. The JVM intercepts, copies the next parent frame from the heap, and continues.

##### Internal Continuation API Example

Java's internal `Continuation` class demonstrates this:

```java
package com.example.concurrency;

import jdk.internal.vm.Continuation;
import jdk.internal.vm.ContinuationScope;

public class ContinuationExample {
    public static void main(String[] args) {
        ContinuationScope scope = new ContinuationScope("demo-scope");

        Continuation continuation = new Continuation(scope, () -> {
            System.out.println("Line 1: Hello from continuation!");
            Continuation.yield(scope); // Pauses and returns control to the runner

            System.out.println("Line 2: Resumed continuation!");
            Continuation.yield(scope); // Pauses again

            System.out.println("Line 3: Finished execution!");
        });

        System.out.println("Main: Running first time...");
        continuation.run(); // Executes to first yield

        System.out.println("Main: Running second time...");
        continuation.run(); // Resumes to second yield

        System.out.println("Main: Running third time...");
        continuation.run(); // Completes execution
    }
}
```

##### How it Works

1. **Creation**: `new Continuation(...)` allocates the continuation on the heap.
2. **Yielding**: `Continuation.yield(scope)` saves the frames to the heap and returns control to the caller thread.
3. **Resuming**: The next `run()` call restores the frames and resumes exactly where it paused.

---

#### 8. Building NanoThread from Scratch

We can simulate Project Loom's scheduler by building a custom user-space thread framework (`NanoThread`):

- **`NanoThread`**: Wraps the continuation, providing a name and unique ID.
- **`NanoThreadScheduler`**: Manages execution. Uses a 2-thread Work-Stealing carrier pool and a single-thread scheduled executor (`IO_NOTIFIER`) to simulate asynchronous I/O completion.
- **`FileOperation`**: Simulates file transfers. When a transfer starts, the task schedules a resume callback and yields the continuation, freeing the carrier thread for other work.

---

#### 9. Virtual Threads and I/O Polling

Loom integrates blocking APIs with the OS network stack. When a virtual thread performs blocking I/O, the JDK intercepts the call:

##### `LockSupport.park()` Redirection

```java
public static void park() {
    if (Thread.currentThread().isVirtual()) {
        VirtualThreads.park(); // Yields the continuation
    } else {
        U.park(false, 0L);     // Native OS park
    }
}
```

##### Native OS Pollers

The JVM registers the blocked socket file descriptor (FD) with native pollers:
- **`epoll`** on Linux.
- **`kqueue`** on macOS.
- **`wepoll`** on Windows.

When the OS signals that I/O is ready, the poller notifies the JVM, which marks the virtual thread as runnable and schedules it back onto an available carrier thread.

---

### Hands-On Labs

#### Lab 3.1 — Build SimpleThreadPool

**Objective**: Implement a basic thread pool from scratch, complete with worker threads, task queues, a thread group, and an `AutoCloseable` interface for graceful shutdown.

##### Implementation (`SimpleThreadPool.java`)

```java
package com.example.concurrency.lab3_1;

import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingDeque;

public class SimpleThreadPool implements AutoCloseable {
    private final BlockingQueue<Runnable> queue;
    private final ThreadGroup threadGroup;
    private volatile boolean running = true;

    public SimpleThreadPool(int poolSize, int queueSize) {
        this.queue = new LinkedBlockingDeque<>(queueSize);
        this.threadGroup = new ThreadGroup("SimpleThreadPool-Group");

        for (int i = 0; i < poolSize; i++) {
            Worker worker = new Worker(threadGroup, "Worker-" + i);
            worker.start();
        }
    }

    public void submit(Runnable task) {
        if (!running) {
            throw new IllegalStateException("ThreadPool has been shut down.");
        }
        try {
            queue.put(task); // Blocks if the queue is full (Backpressure)
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    public void shutdown() {
        this.running = false;
        threadGroup.interrupt(); // Interrupt all worker threads in the group
    }

    @Override
    public void close() {
        // Graceful drain: wait until all tasks in the queue are completed
        while (!queue.isEmpty()) {
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            }
        }
        shutdown();
    }

    private class Worker extends Thread {
        public Worker(ThreadGroup group, String name) {
            super(group, name);
        }

        @Override
        public void run() {
            while (running || !queue.isEmpty()) {
                try {
                    Runnable task = queue.take(); // Blocks until a task is available
                    task.run();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    if (!running) {
                        break; // Exit thread loop on shutdown
                    }
                }
            }
        }
    }

    public static void main(String[] args) throws Exception {
        System.out.println("=== Lab 3.1: Starting SimpleThreadPool ===");
        try (var threadPool = new SimpleThreadPool(4, 100)) {
            for (int i = 0; i < 20; i++) {
                final int taskId = i;
                threadPool.submit(() -> {
                    System.out.printf("Task %d executed by %s%n",
                             taskId, Thread.currentThread().getName());
                    try {
                        Thread.sleep(100);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                });
            }
        } // Auto-closes, waiting for tasks to complete
        System.out.println("SimpleThreadPool closed successfully.");
    }
}
```

##### How `SimpleThreadPool` Works

1. **Queue Capacity**: `LinkedBlockingDeque` holds tasks. If full, `queue.put()` blocks the sender, providing backpressure.
2. **Worker Group**: Workers belong to a single `ThreadGroup`, allowing us to manage and interrupt them together.
3. **Graceful Shutdown**: The `close()` method waits for the queue to empty, sets `running = false`, and interrupts all workers so they exit cleanly.

---

#### Lab 3.2 — ForkJoin Fibonacci

**Objective**: Demonstrate how submitting recursive subtasks to a `FixedThreadPool` causes thread starvation deadlocks. Resolve the deadlock using `ForkJoinPool` and `RecursiveTask`.

##### 1. Thread Pool Deadlock Demo (`DeadlockDemo.java`)

```java
package com.example.concurrency.lab3_2;

import java.util.concurrent.*;

public class DeadlockDemo {
    private static final ConcurrentHashMap<Integer, Long> cache = new ConcurrentHashMap<>();

    public static long fib(int n, ExecutorService pool) throws Exception {
        if (n <= 1) return n;

        Future<Long> f1 = pool.submit(() -> fib(n - 1, pool));
        Future<Long> f2 = pool.submit(() -> fib(n - 2, pool));

        // Thread blocks waiting for subtasks to finish, causing deadlock
        return f1.get() + f2.get();
    }

    public static void main(String[] args) {
        System.out.println("Starting FixedThreadPool Deadlock Demo...");
        try (ExecutorService pool = Executors.newFixedThreadPool(10)) {
            Future<Long> result = pool.submit(() -> fib(15, pool));
            System.out.println("Result: " + result.get(5, TimeUnit.SECONDS));
        } catch (TimeoutException e) {
            System.err.println("\nDEADLOCK DETECTED! Thread pool starved and timed out.");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

##### 2. ForkJoin Recovery (`ForkJoinFibonacci.java`)

```java
package com.example.concurrency.lab3_2;

import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.RecursiveTask;

public class ForkJoinFibonacci {

    static class FibonacciTask extends RecursiveTask<Long> {
        private final int n;

        public FibonacciTask(int n) {
            this.n = n;
        }

        @Override
        protected Long compute() {
            if (n <= 1) return (long) n;

            FibonacciTask f1 = new FibonacciTask(n - 1);
            f1.fork(); // Asynchronously submits f1 to the worker deque

            FibonacciTask f2 = new FibonacciTask(n - 2);
            // f2.compute() runs on the current thread, and f1.join() waits for f1
            return f2.compute() + f1.join();
        }
    }

    public static void main(String[] args) {
        System.out.println("Starting ForkJoinPool Fibonacci Calculation...");
        try (ForkJoinPool pool = new ForkJoinPool()) {
            long result = pool.invoke(new FibonacciTask(20));
            System.out.println("Result: " + result);
        }
    }
}
```

##### How Starvation and Work-Stealing Work

1. **Starvation Deadlock (`DeadlockDemo`)**: In a fixed pool, each recursive call consumes a thread. If all 10 threads block waiting on `.get()`, the pool is exhausted, causing a deadlock.
2. **Work-Stealing Fix (`ForkJoinFibonacci`)**: When a `ForkJoinPool` thread waits on `f1.join()`, it doesn't block. Instead, it runs other tasks from its queue or steals tasks from other workers, avoiding deadlock.

---

#### Lab 3.3 — Build NanoThread

**Objective**: Build a custom virtual thread executor using Java's internal `Continuation` class to simulate carrier thread context switching.

##### 1. NanoThread Scheduler Core (`NanoThread.java`)

```java
package com.example.concurrency.lab3_3;

import jdk.internal.vm.Continuation;
import jdk.internal.vm.ContinuationScope;
import java.util.concurrent.atomic.AtomicInteger;

public class NanoThread {
    public static final NanoThreadScheduler SCHEDULER = new NanoThreadScheduler();
    public static final ContinuationScope SCOPE = new ContinuationScope("nano-scope");
    private static final AtomicInteger COUNTER = new AtomicInteger(1);

    private final Continuation continuation;
    private final int nid;

    public NanoThread(Runnable runnable) {
        this.nid = COUNTER.getAndIncrement();
        this.continuation = new Continuation(SCOPE, runnable);
    }

    public static void start(Runnable runnable) {
        NanoThread nt = new NanoThread(runnable);
        SCHEDULER.schedule(nt);
    }

    public void run() {
        continuation.run();
    }

    public static NanoThread current() {
        return NanoThreadScheduler.CURRENT_THREAD.get();
    }

    @Override
    public String toString() {
        return "NanoThread-" + nid + " (" + Thread.currentThread().getName() + ")";
    }
}
```

##### 2. NanoThread Scheduler (`NanoThreadScheduler.java`)

```java
package com.example.concurrency.lab3_3;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;

public class NanoThreadScheduler {
    public static final ThreadLocal<NanoThread> CURRENT_THREAD = new ThreadLocal<>();
    public static final ScheduledExecutorService IO_SCHEDULER = Executors.newSingleThreadScheduledExecutor();
    private final ExecutorService carrierPool = Executors.newWorkStealingPool(2);

    public void schedule(NanoThread thread) {
        carrierPool.submit(() -> {
            CURRENT_THREAD.set(thread);
            try {
                thread.run(); // Mounts the continuation
            } finally {
                CURRENT_THREAD.remove();
            }
        });
    }

    public void shutdown() {
        carrierPool.shutdown();
        IO_SCHEDULER.shutdown();
    }
}
```

##### 3. Simulated File Transfer (`FileOperation.java`)

```java
package com.example.concurrency.lab3_3;

import jdk.internal.vm.Continuation;
import java.util.Random;
import java.util.concurrent.TimeUnit;

public class FileOperation {
    private final Random random = new Random();

    public void transfer(String fileName) {
        System.out.println("Start transferring: " + fileName + " on " + NanoThread.current());

        NanoThread currentThread = NanoThread.current();

        // Simulate async I/O. Once done, reschedule the thread.
        NanoThreadScheduler.IO_SCHEDULER.schedule(() -> {
            System.out.println("I/O ready for: " + fileName + ". Rescheduling...");
            NanoThread.SCHEDULER.schedule(currentThread);
        }, random.nextInt(100) + 50, TimeUnit.MILLISECONDS);

        // Unmount phase: Clear thread context and yield continuation
        NanoThreadScheduler.CURRENT_THREAD.remove();
        Continuation.yield(NanoThread.SCOPE); // Yields carrier thread execution

        System.out.println("Finished transferring: " + fileName + " on " + NanoThread.current());
    }
}
```

##### 4. Runner Entry Class (`NanoThreadDemo.java`)

```java
package com.example.concurrency.lab3_3;

import java.time.Duration;

public class NanoThreadDemo {
    public static void main(String[] args) throws Exception {
        System.out.println("=== Lab 3.3: Custom NanoThread Demo ===");
        FileOperation fileOperation = new FileOperation();

        for (int i = 0; i < 3; i++) {
            final int fileId = i;
            NanoThread.start(() -> {
                fileOperation.transfer("File_" + fileId);
            });
        }

        Thread.sleep(Duration.ofSeconds(2));
        NanoThread.SCHEDULER.shutdown();
        System.out.println("=== Simulation Complete ===");
    }
}
```

##### How the Custom Scheduler Works

1. **Continuation Allocation**: `NanoThread` allocates a `Continuation` on the heap inside `NanoThread.SCOPE`.
2. **Mounting**: The scheduler submits the task to a 2-thread pool (`carrierPool`). The carrier thread sets the context and calls `continuation.run()`, mounting it.
3. **Yielding**: `FileOperation` schedules a background task to simulate I/O, clears the thread context, and calls `Continuation.yield()`. The JVM pauses the task, saves its stack to the heap, and frees the carrier thread.
4. **Resuming**: When I/O completes, the callback schedules the thread back onto the pool. A carrier thread restores the stack and resumes exactly where it paused.

##### Run Command

```bash
# Export the internal JVM continuation classes to enable execution:
javac --add-exports java.base/jdk.internal.vm=ALL-UNNAMED NanoThread*.java FileOperation.java
java --add-exports java.base/jdk.internal.vm=ALL-UNNAMED com.example.concurrency.lab3_3.NanoThreadDemo
```

---

### Securing User-Space Schedulers

#### The Security Threat of Custom Continuations

Building custom schedulers introduces two major security risks:

1. **Scope Pollution**: If untrusted tasks share a `ContinuationScope`, one malicious task can yield the scope, causing a Denial of Service (DoS) for all others.
2. **Carrier Thread Leakage**: Since carrier threads are reused, sensitive data stored in `ThreadLocal` by Task A can be read by Task B if it runs on the same carrier thread.

#### Security Mitigations

1. **Unique Scopes**: Create a separate, private `ContinuationScope` for each tenant.
2. **ThreadLocal Purging**: Clear the carrier thread's `ThreadLocalMap` before and after running a task.

```java
package com.example.concurrency.lab3_3;

import jdk.internal.vm.Continuation;
import jdk.internal.vm.ContinuationScope;
import java.lang.reflect.Field;
import java.security.AccessControlContext;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.concurrent.*;

/**
 * A secure, isolated custom user-space execution gatekeeper.
 * It isolates continuation scopes per ClassLoader context and guarantees
 * that carrier thread-local variables are swept clean between task transitions.
 */
public class SecureContinuationScheduler {

    private final ExecutorService carrierPool;
    private final ConcurrentMap<ClassLoader, ContinuationScope> scopeRegistry = new ConcurrentHashMap<>();

    public SecureContinuationScheduler(int threads) {
        this.carrierPool = Executors.newFixedThreadPool(threads, r -> {
            Thread t = new Thread(r);
            t.setName("secure-carrier-" + t.getId());
            t.setDaemon(true);
            return t;
        });
    }

    /**
     * Resolves a unique ContinuationScope for the calling ClassLoader context.
     * This prevents cross-tenant continuation yielding.
     */
    private ContinuationScope getOrCreateScope(ClassLoader cl) {
        return scopeRegistry.computeIfAbsent(cl, loader ->
            new ContinuationScope("SecureScope-" + loader.hashCode() + "-" + System.nanoTime())
        );
    }

    /**
     * Clears the ThreadLocalMap of the executing carrier thread.
     * This prevents thread-local context leaks between execution cycles.
     */
    private void purgeThreadLocals() {
        try {
            Thread current = Thread.currentThread();
            Field threadLocalsField = Thread.class.getDeclaredField("threadLocals");
            threadLocalsField.setAccessible(true);
            // Nullifying the map forces the JVM to initialize a clean map on next write
            threadLocalsField.set(current, null);

            Field inheritableThreadLocalsField = Thread.class.getDeclaredField("inheritableThreadLocals");
            inheritableThreadLocalsField.setAccessible(true);
            inheritableThreadLocalsField.set(current, null);
        } catch (Exception e) {
            // Log security failure in administrative log
            System.err.println("[SECURITY ALERT] Failed to purge ThreadLocalMap on carrier: " + e.getMessage());
        }
    }

    /**
     * Submits an isolated user task to the secure scheduler.
     */
    public void submit(Runnable userTask, ClassLoader executionContextLoader) {
        ContinuationScope scope = getOrCreateScope(executionContextLoader);

        carrierPool.submit(() -> {
            // 1. Purge any stale contexts from the carrier thread prior to mounting
            purgeThreadLocals();

            // 2. Set the context ClassLoader for current execution
            Thread.currentThread().setContextClassLoader(executionContextLoader);

            // 3. Create isolated continuation
            Continuation continuation = new Continuation(scope, () -> {
                try {
                    userTask.run();
                } finally {
                    // Cleanup stack variables
                    purgeThreadLocals();
                }
            });

            // 4. Mount and run continuation
            try {
                continuation.run();
            } finally {
                // 5. Final purge on unmounting to protect recycled thread
                purgeThreadLocals();
            }
        });
    }

    public void shutdown() {
        carrierPool.shutdown();
    }
}
```

##### How `SecureContinuationScheduler` Works

1. **ClassLoader Scope Isolation**: Maps each ClassLoader to a unique `ContinuationScope`. Tasks from one class loader cannot yield scopes belonging to another.
2. **Reflection-Based Purging**: Uses reflection to set the carrier thread's `threadLocals` map to `null` before and after execution, ensuring no data leaks between tasks.
3. **Double Purging**: Purges before running, inside the task, and on unmount, keeping the recycled carrier thread clean.

---

### Common Pitfalls & Anti-Patterns

#### 1. Calling `compute()` on both subtasks

```java
// Anti-Pattern: calling compute() on both tasks runs them sequentially, losing parallelism!
FibonacciTask f1 = new FibonacciTask(n - 1);
FibonacciTask f2 = new FibonacciTask(n - 2);
long r1 = f1.compute();
long r2 = f2.compute();
return r1 + r2;
```

This runs tasks sequentially. To run them in parallel, `fork()` the first task (putting it in the work-stealing queue) and call `compute()` on the second task (running it on the current thread):

```java
f1.fork(); // Submits f1 to the queue asynchronously
long r2 = f2.compute(); // Runs f2 immediately on this thread
long r1 = f1.join(); // Waits for f1
return r1 + r2;
```

#### 2. Unbounded Queues in ThreadPoolExecutor

Using a thread pool with an unbounded queue (like `LinkedBlockingQueue` without a size) means the pool will never create more than the core number of threads. Under sudden spikes, tasks will pile up in the queue, leading to memory bloat and eventual out-of-memory errors.

---

### Summary

1. **Thread Pools**: Bounded pools manage threads and queues to prevent system resource exhaustion.
2. **ForkJoinPool vs. Traditional Pools**: ThreadPoolExecutor uses a single global queue, whereas ForkJoinPool uses worker-specific deques and work-stealing to minimize thread contention.
3. **Loom Scheduling**: Virtual threads run on carrier platform threads scheduled by a FIFO async `ForkJoinPool`.
4. **Continuations**: Pause and resume execution. When blocking, the JVM yields continuation stacks to the heap and lazy-copies frames back when resuming.
5. **Native I/O Pollers**: Thread unmounting integrates with native OS event loops (`epoll`, `kqueue`, `wepoll`) to wake virtual threads when I/O completes.

---

### Knowledge Check - Deep Dive Scenarios

#### Question 1: Unbounded Queue Saturation

A system uses a `FixedThreadPool` of size 50 with an unbounded `LinkedBlockingQueue`. If database write times increase from 5ms to 500ms under a load of 5,000 requests per second, what happens?

- A. The pool rejects additional requests using the default `AbortPolicy`.
- B. The core pool size dynamically scales up to 5,000 threads.
- C. The queue accumulates millions of tasks, leading to memory leaks and a JVM crash with `java.lang.OutOfMemoryError: Java heap space`.
- D. Tasks are completed in LIFO order, bypassing latency bottlenecks.

*Answer*: **C**
*Explanation*: Bounded pools with unbounded queues never create extra threads or reject tasks. When execution slows down, tasks accumulate in the queue until memory is exhausted.

#### Question 2: CAS Contention on Multi-Core Systems

A developer replaces a synchronized block counter with a lock-free CAS loop using `VarHandle.compareAndSet`. Under heavy load (128 threads on a 64-core system), performance degrades compared to lower thread counts. Why?

- A. The OS kernel scheduler suspends worker threads inside the CAS instructions.
- B. High hardware cache contention causes CPU cores to execute repeated retry loops (spin-lock starvation) while processing the atomic check, saturating the cache coherence bus.
- C. VarHandle allocations saturate heap space.
- D. Volatile fields require native JNI context switches.

*Answer*: **B**
*Explanation*: With high contention, many threads fail the CAS check and retry. This loop consumes CPU cycles and generates massive bus traffic as cores keep synchronizing their cache lines (cache coherence overhead).

#### Question 3: Continuation Lazy Copying and Return Barriers

How is stack recovery managed when a suspended continuation resumes?

- A. The JVM copies the entire call stack from the heap back onto the carrier thread stack at once.
- B. The JVM copies only the top stack frames to the carrier thread, injecting a return barrier on the heap boundaries. When execution hits this barrier, the JVM copies the next set of frames from the heap, minimizing overhead.
- C. The JVM ignores stack variables and resolves values dynamically using reflections.
- D. Stack memory maps are redirected to off-heap native memory caches.

*Answer*: **B**
*Explanation*: To optimize performance, the JVM copies only the top frames upon resuming, using return barriers to copy older frames on-demand.

#### Question 4: LIFO vs FIFO Work-Stealing Scheduling

Why does the virtual thread scheduler use FIFO async mode while parallel streams use LIFO mode?

- A. LIFO mode is required to process socket connections concurrently.
- B. FIFO mode prevents task starvation by ensuring that older request tasks waiting in the scheduler queue are processed first. LIFO mode can lead to delayed requests if new tasks are continuously submitted.
- C. FIFO mode allocates less heap memory.
- D. LIFO mode forces threads to pin carriers.

*Answer*: **B**
*Explanation*: FIFO mode ensures fairness in web applications, preventing older requests from timing out. Parallel streams use LIFO to maximize CPU cache affinity.

#### Question 5: ForkJoinPool Deadlock Starvation

Why do recursive calculations deadlock in a `FixedThreadPool` but work in a `ForkJoinPool`?

- A. ForkJoinPool dynamically increases its thread count to `Integer.MAX_VALUE`.
- B. ForkJoinPool worker threads use cooperative scheduling: when a task blocks on `join()`, the worker thread suspends the task and executes other pending tasks in its deque or steals tasks from other worker queues, preventing starvation.
- C. ForkJoinPool bypasses JVM thread local variables.
- D. FixedThreadPool does not support record structures.

*Answer*: **B**
*Explanation*: `ForkJoinPool` workers use cooperative scheduling to run other tasks when a task blocks on `join()`. `ThreadPoolExecutor` workers simply block on `Future.get()`, leading to starvation deadlocks.

#### Question 6: Redirection of `LockSupport.park()`

When a virtual thread executes a blocking call, what prevents the OS thread from blocking?

- A. The thread executes a native JNI bypass loop.
- B. The JVM redirects `LockSupport.park()` calls: if the current thread is virtual, it yields the continuation, saves stack frames on the heap, and frees the carrier thread.
- C. The JVM throws an `IllegalStateException` to abort the transaction.
- D. The thread is converted to a platform thread.

*Answer*: **B**
*Explanation*: The JVM intercepts the blocking call, yields the continuation to the heap, and frees the carrier thread to run other virtual threads.

#### Question 7: VarHandle Memory Barriers

Which VarHandle access mode provides atomic compare-and-set operations with both acquire and release memory consistency?

- A. `getOpaque`
- B. `setVolatile`
- C. `compareAndSet`
- D. `getAcquire`

*Answer*: **C**
*Explanation*: `VarHandle.compareAndSet` enforces memory visibility barriers equivalent to volatile reads and writes, ensuring acquire/release semantics.

#### Question 8: OS Event Loops and Virtual Threads

How does the JVM wake up a suspended virtual thread once its blocking I/O completes?

- A. The JVM continually polls the thread's heap state in a spin-lock loop.
- B. The JVM registers the socket's file descriptor with native OS event loops (like `epoll` or `kqueue`). When the OS signals that data is ready, the JVM schedules the virtual thread back onto an available carrier thread.
- C. The virtual thread is woken by garbage collector threads.
- D. The database driver interrupts the ForkJoinPool worker thread.

*Answer*: **B**
*Explanation*: The JVM integrates virtual thread scheduling with native OS event loops to park and unpark threads efficiently without CPU-intensive polling.

#### Question 9: Sizing Fixed Thread Pools for CPU-bound Tasks

What is the optimal size for a fixed thread pool executing CPU-bound tasks on a 16-core machine?

- A. ~16 threads
- B. ~160 threads
- C. ~1,000 threads
- D. ~10,000 threads

*Answer*: **A**
*Explanation*: CPU-bound tasks keep cores fully busy. Sizing the pool to match the physical core count minimizes context switching and cache invalidation.

#### Question 10: Custom User-Space Scheduler Mounts

In our `NanoThreadScheduler` simulation, how did we emulate carrier thread context switching when a file transfer blocked?

- A. By creating a new native OS thread for each file.
- B. By scheduling a wake-up callback with a scheduled executor and calling `Continuation.yield()`, which saved the stack state on the heap and freed the carrier thread.
- C. By calling `Thread.stop()` on the carrier thread.
- D. By synchronizing on the class monitor lock.

*Answer*: **B**
*Explanation*: The simulation uses a scheduled executor to trigger resume callbacks and calling `Continuation.yield()` to suspend execution, freeing the carrier thread to run other tasks.

#### Question 11: Work-Stealing Queue Access Contention

In a `ForkJoinPool`, workers pop tasks from the head of their own deque but steal from the tail of other workers' deques. What does this optimize?

- A. It minimizes OS-level kernel locks by allocating separate CPU registers.
- B. It limits CPU cache line invalidations and false sharing by keeping hot local tasks grouped on the worker's CPU core cache while external steal operations query distant tail elements, reducing L1/L2 cache contention.
- C. It increases the priority of garbage collection sweeps on queue nodes.
- D. It disables volatile memory fences.

*Answer*: **B**
*Explanation*: Owner threads access the head of their deque (LIFO), maximizing cache locality. Thieves steal from the tail (FIFO). Keeping these operations far apart in memory avoids cache coherence conflicts and false sharing.

#### Question 12: ForkJoinPool Common Pool Sizing in Containers

A microservice runs on a Kubernetes container limited to 2 cores. The host server has 64 cores. If the code uses a parallel stream (which defaults to `ForkJoinPool.commonPool()`), what happens?

- A. The parallelism defaults to 2 cores.
- B. The JVM queries the host system's hardware configuration, allocating 63 worker threads (64 cores - 1). This over-provisions threads inside the container, causing extreme CPU context switching, throttling penalties, and high response times.
- C. The parallelism is dynamically resized based on load.
- D. The common pool is disabled.

*Answer*: **B**
*Explanation*: On older or misconfigured runtimes, the JVM detects the full 64-core host and creates 63 threads. Competing for 2 cores causes massive context switching and OS CPU throttling, degrading performance.

#### Question 13: Volatile Memory Visibility

Two threads share a mutable variable: `private int status = 0;`. Thread A writes `status = 1`, and Thread B loops: `while(status == 0) {}`. Why can Thread B loop indefinitely without a `volatile` modifier?

- A. Because Thread A's execution was terminated by the OS scheduler.
- B. The CPU core running Thread B stores the initial value of `status` in its local register or L1 cache, and without a volatile read memory barrier, the hardware has no instruction to invalidate its cache line or query the updated main memory location.
- C. The JMM disables cross-core memory buses.
- D. The variable is garbage collected.

*Answer*: **B**
*Explanation*: Without `volatile`, the CPU caches the value in local registers or L1 cache. It has no instruction to invalidate its cache line or read the updated main memory location.

#### Question 14: CallerRunsPolicy Rejection Handler

An application uses a `CallerRunsPolicy` rejection handler. Under a database outage, all database threads block. What is the impact?

- A. The executor throws a `RejectedExecutionException`, aborting the request.
- B. The executor discards the tasks silently, letting the request thread complete immediately.
- C. The thread that submitted the task executes the task itself within its own thread context. If the task blocks (e.g. database timeout), the submitter thread blocks, naturally throttling the incoming request pipeline.
- D. The executor spawns a temporary virtual thread.

*Answer*: **C**
*Explanation*: The task is run by the caller thread that submitted it. If that thread blocks executing the task, it cannot submit new tasks, providing natural backpressure.

#### Question 15: Memory Stack Frame Layout in Continuations

How does the JVM handle variables and reference pointers when saving a continuation's stack state to the heap?

- A. It serializes all objects into JSON format and dumps them to the disk.
- B. It copies the execution stack frame, converting primitive variables to objects.
- C. It preserves the exact stack frames, separating primitive values from object references. Object reference pointers in the stack frame are registered as garbage collection roots (GC roots) to prevent the GC from reclaiming the objects while the continuation is parked.
- D. It copies references but discards primitives.

*Answer*: **C**
*Explanation*: The JVM preserves the exact stack frames on the heap, registering object references as GC roots to prevent the garbage collector from reclaiming them while the continuation is parked.

---

### 17. Office Analogy: The Whiteboard and Intercom

To understand why CPU cache coherence and the `volatile` keyword are necessary, let us use a simple office analogy.

Imagine a large bank office with:
- **A Master Ledger**: A physical book locked in the office vault (Main Memory). Writing to it is slow because you have to walk to the vault (Latency: 50–100ns).
- **Two Managers**: Manager A and Manager B (CPU Core 0 and Core 1).
- **Personal Whiteboards**: Each manager has a whiteboard in their own private office (L1/L2 Cache). Reading and writing to their own whiteboard is almost instant (Latency: sub-nanosecond).
- **The Task**: Both managers must keep track of a shared variable: `status`.

#### Scenario 1: The Out-of-Sync Whiteboards (No Volatile)

- Both managers walk to the vault, read `status = 0`, and write it on their own whiteboards.
- Manager A decides to update the status to `1`.
- To save time, Manager A does not walk to the vault. Instead, they write `status = 1` on a sticky note on their desk (Store Buffer) and update their local whiteboard to `status = 1`.
- Manager A thinks the job is done.
- However, Manager B is still sitting in their own office, looking at their own whiteboard which still reads `status = 0`. Manager B makes decisions based on stale data.
- Eventually, the sticky note is written to the ledger, but until then, the two offices are out of sync.

#### Scenario 2: The Intercom System (With Volatile)

By marking the `status` variable as `volatile` in Java, the JVM installs a strict **Intercom System** (Memory Barriers):

1. **Volatile Write (Shouting over the Intercom)**:
    - When Manager A updates `status = 1`, the volatile keyword prevents them from just leaving a sticky note.
    - Instead, they must immediately announce the change over the intercom.
    - Manager A shouts: _"I am updating status to 1! Erase your whiteboards!"_
    - This immediately forces Manager B's whiteboard to be wiped clean (Invalid state).
    - Manager A then walks to the vault and updates the ledger.
2. **Volatile Read (Checking the Master Ledger)**:
    - When Manager B wants to read `status`, they look at their whiteboard and see it is empty.
    - Manager B is forced to walk to the vault and read the updated value (`status = 1`) directly from the master ledger.

#### Why is this necessary?

Without this intercom system, different CPU cores would work with conflicting data, leading to infinite loops or incorrect results. The `volatile` keyword coordinates caches at the hardware level, ensuring updates are instantly visible.

---

### 18. Under the Hood: How Continuations Freeze and Thaw

Every virtual thread wraps an internal JVM `Continuation` instance. Let us trace the step-by-step logic of how the JVM freezes (yields) and thaws (resumes) a continuation stack.

#### 1. The Yielding Process (Freezing the Stack)

When a virtual thread executes a blocking read:
1. **Interception**: The blocking code calls `LockSupport.park()`.
2. **Yield Request**: `VirtualThread.park()` delegates to `Continuation.yield(SCOPE)`.
3. **Transition**: The JVM transitions to C++ runtime execution inside the HotSpot VM.
4. **Copying Stack Frames**:
    - The JVM reads the carrier thread's physical stack.
    - It identifies all stack frames belonging to the virtual thread.
    - It copies these frames (including variables and references) into a heap-allocated array called a **`StackChunk`**.
5. **Patching Addresses**: The JVM scans the copied frames and updates reference pointers to point to their new locations on the heap.
6. **Clearing the Carrier**: The JVM clears the virtual thread's frames from the carrier thread's stack and resets its registers, freeing the carrier thread to run other virtual threads.

#### 2. The Rescheduling Process (Thawing the Stack)

When I/O completes:
1. **Rescheduling**: The JVM marks the virtual thread as runnable and submits it to the `ForkJoinPool` worker queue.
2. **Mounting**: A carrier thread picks up the task and calls `Continuation.run()`.
3. **Transition**: The JVM enters the thaw phase in C++.
4. **Restoring Stack Frames**:
    - The JVM reads the saved `StackChunk` from the heap.
    - It copies the frames back onto the carrier thread's stack.
    - **Return Barrier**: To save time, the JVM copies only the topmost frame and sets a return barrier. When that method returns, the barrier triggers and thaws the next frame dynamically.
5. **Updating Registers**: The JVM updates the physical CPU registers to point to the restored stack frame and the instruction directly following the `Continuation.yield()` call.
6. **Resume**: Execution resumes seamlessly.

#### Visual Memory Layout of a Context Shift

```text
  [ CARRIER THREAD STACK ]                      [ JVM HEAP ]
+--------------------------+           +--------------------------+
|  FJP Scheduler Loop      |           |                          |
+--------------------------+           |                          |
|  VirtualThread.run()     |           |                          |
+--------------------------+           |                          |
|  BusinessService.work()  | ──Yield─► |  Saved StackChunk        |
+--------------------------+           |  - BusinessService.work()|
|  SocketInputStream.read()|           |  - SocketInputStream()   |
+--------------------------+           +--------------------------+
            │                                       ▲
            │                                       │
            └───────────(Copies frames)─────────────┘
```

By storing suspended thread stacks as simple objects on the heap, the JVM avoids allocating a dedicated 1MB native stack memory range for each task, allowing applications to scale to millions of concurrent operations.

---
