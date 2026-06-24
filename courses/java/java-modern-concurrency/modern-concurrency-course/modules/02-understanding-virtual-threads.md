# Module 02: Understanding Virtual Threads

### Learning Objectives

- Compare platform and virtual threads in memory, scheduling, and blocking.
- Use the four JDK APIs to create and run virtual threads.
- Calculate throughput using Little's Law ($\lambda = N/d$).
- Understand how Loom works under the hood (continuations, carrier threads, and blocking).
- Use the internal JVM `Continuation` class to see how yielding works.
- Build a simple virtual thread scheduler simulation.
- Fix thread pinning using `ReentrantLock` and learn about JDK 24 updates.
- Replace `ThreadLocal` with Scoped Values to save memory.
- Use diagnostics and thread dumps to monitor virtual threads.

---

### Concept Explanation

#### 1. Platform vs. Virtual Threads

JDK 21 introduces two types of threads:

##### Platform Threads

- **Mapping**: Each platform thread maps directly to one OS kernel thread.
- **Memory Use**: Heavy. Each thread gets a stack frame outside the heap (usually **1 to 2 MiB**).
- **Scheduling**: Managed by the OS. Switching between threads is slow because it requires help from the OS kernel.

##### Virtual Threads

- **Mapping**: Millions of virtual threads run on a small pool of platform threads called **Carrier Threads**.
- **Memory Use**: Lightweight. They are Java objects on the heap, using only a ==few hundred bytes==.
- **Scheduling**: Managed by the JVM using a ForkJoinPool in FIFO (First-In, First-Out) mode.

##### Carrier Thread Scheduling & Mounting Mechanics

```text
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Virtual Th 1 │   │ Virtual Th 2 │   │ Virtual Th 3 │   │ Virtual Th 4 │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                  │                  │
       └──────────────────┴────────┬─────────┴──────────────────┘
                                   ▼ (JVM Scheduler: FIFO Async ForkJoinPool)
                         ┌───────────────────┐
                         │  Carrier Thread   │ (Platform Thread)
                         └─────────┬─────────┘
                                   ▼ (1-to-1 OS Mapping)
                         ┌───────────────────┐
                         │  OS Kernel Thread │
                         └─────────┬─────────┘
```

---

#### 2. Key Differences

- **Lightweight Memory**: Because stack frames are on the heap, virtual threads do not need off-heap memory.
- **OS Bypass**: The OS does not know about virtual threads. The JVM manages them, avoiding the slow OS thread switching.
- **Blocking Tolerance**: When a virtual thread blocks (like for sleep or a database call), the JVM unmounts it from the carrier thread and saves its stack on the heap. This frees the carrier thread to run other virtual threads.
- **API Compatibility**: Virtual threads are normal Threads. Existing APIs (`Runnable`, `ThreadLocal`, `ExecutorService`) just work.

---

#### 3. Setup

To run virtual threads, install **JDK 21 or later**. For preview features like structured concurrency and scoped values, use preview flags.

##### SDKMAN Version Management

```bash
# List JDK versions
sdk list java

# Install JDK 21+
sdk install java 21.0.2-open
sdk use java 21.0.2-open
```

##### Compiling and Running Preview Code

```bash
# Compile with preview
javac --enable-preview --release 21 YourClass.java

# Run with preview
java --enable-preview YourClass
```

---

#### 4. Four Ways to Create Virtual Threads

##### 1. `Thread.startVirtualThread(Runnable)`

Runs a virtual thread immediately.

```java
Thread.startVirtualThread(() -> {
    System.out.println("Running in: " + Thread.currentThread().threadId());
});
```

##### 2. Builder API (`Thread.ofVirtual().start(Runnable)`)

Starts a named virtual thread immediately.

```java
Thread t = Thread.ofVirtual()
                 .name("worker-", 1)
                 .start(() -> System.out.println("Started: " + Thread.currentThread().getName()));
```

##### 3. Deferred Builder API (`Thread.ofVirtual().unstarted(Runnable)`)

Creates a virtual thread but does not start it yet.

```java
Thread t = Thread.ofVirtual()
                 .name("deferred-worker")
                 .unstarted(() -> System.out.println("Deferred: " + Thread.currentThread().getName()));
t.start(); // Start manually
```

##### 4. Executor Service (`Executors.newVirtualThreadPerTaskExecutor()`)

Creates an executor that runs each task in a new virtual thread.

```java
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    Future<String> future = executor.submit(() -> "Done");
    System.out.println(future.get());
}
```

##### How the Four Styles Work

1. **`Thread.startVirtualThread`**: Creates a new virtual thread with default settings and starts it immediately.
2. **`Thread.ofVirtual().name(...).start(...)`**: Uses a builder to name threads in sequence (e.g., `"worker-1"`, `"worker-2"`), which helps with debugging.
3. **`Thread.ofVirtual().unstarted(...)`**: Creates the thread object on the heap in the `NEW` state without starting it. This lets you configure it before running.
4. **`Executors.newVirtualThreadPerTaskExecutor()`**: Does not reuse threads. Every task gets its own new virtual thread. The try-with-resources block waits for all tasks to finish before closing.

> [!IMPORTANT]
> **Virtual Threads are Daemon Threads**: Virtual threads are always daemon threads. If the main thread exits, the program ends and stops all virtual threads. You must block the main thread (using `.join()` or try-with-resources) to let them finish.

---

#### 5. Thread API Changes

- **New Methods**:
    - `Thread::isVirtual`: Returns `true` for virtual threads.
    - `Thread.sleep(Duration)` and `Thread::join(Duration)`: Support the `Duration` class.
    - `Thread::threadId`: Replaces the deprecated `getId()`.
- **Thread Groups**: All virtual threads belong to a single, unchangeable group named `"VirtualThreads"`.
- **Fixed Priority and Daemon Status**: You cannot change a virtual thread's priority (always `5`) or daemon status (always `true`).

---

#### 6. Little's Law: Understanding Throughput

Little's Law is a formula that relates the number of active tasks ($N$), throughput ($\lambda$), and delay ($d$):
$$N = \lambda \times d \quad \Longrightarrow \quad \lambda = \frac{N}{d}$$

- **Platform Threads**: Limited by memory (usually ~1,000 threads max). If delay ($d$) is 500ms, max throughput is:
  $$\lambda = \frac{1000}{0.5\text{s}} = 2,000 \text{ requests/sec}$$
- **Virtual Threads**: Can scale to 1,000,000 threads. With the same 500ms delay, throughput scales massively:
  $$\lambda = \frac{1,000,000}{0.5\text{s}} = 2,000,000 \text{ requests/sec}$$

---

#### 7. Under the Hood

The JVM uses a few clever tricks to make virtual threads fast:

##### 1. Heap-Allocated Stack Frames

Platform threads use a fixed block of native memory. Virtual threads store their stacks as normal objects on the heap.

##### 2. Carrier Pool Scheduling

The JVM runs virtual threads on top of platform threads (carrier threads) using a work-stealing `ForkJoinPool` running in FIFO (First-In, First-Out) mode.

- **FIFO vs LIFO**: Normal parallel streams use LIFO (Last-In, First-Out) to keep data in CPU cache. Virtual threads use FIFO to ensure every thread gets a turn and doesn't starve.
- **Lock-Free Queues**: The queues use Compare-And-Swap (CAS) operations instead of locks to avoid slowing down.

##### Deep Dive: Inside the Carrier Scheduler

Here is how the JVM schedules millions of virtual threads:

###### 1. Scheduler and Carrier Threads

When the JVM starts, it creates a ForkJoinPool for virtual threads.

- **Size**: By default, it has one carrier thread per CPU core.
- **Customization**: You can configure this with JVM properties:
    - `-Djdk.virtualThreadScheduler.parallelism=N`: Number of carrier threads.
    - `-Djdk.virtualThreadScheduler.maxPoolSize=M`: Max temporary backup threads (default: 256).

###### 2. Work-Stealing Internals

When a carrier thread finishes a task, it scans for new virtual threads to run:

```
[Carrier Worker Loop]
         │
         ▼
[Check Local Queue (FIFO)] ──► Found? ──► [Run Virtual Thread]
         │
         ├── NO
         ▼
[Steal from Sibling Queue] ──► Found? ──► [Steal and Run]
         │
         ├── NO
         ▼
[Check Shared Queue]       ──► Found? ──► [Run]
         │
         ├── NO
         ▼
[Park Carrier Thread (Sleep)]
```

1. **Local FIFO Queue**: The carrier thread checks its own queue and runs the oldest task (FIFO).
2. **Work-Stealing**: If its queue is empty, it randomly picks a sibling carrier thread's queue and steals a task from the end.
3. **Shared Queue**: If there is nothing to steal, it checks the shared queue for new tasks submitted from outside.
4. **Sleep**: If no tasks are found, the carrier thread goes to sleep until new work arrives.

###### 3. Carrier Over-Provisioning (Pinning Safety Valve)

If a virtual thread does something that blocks the carrier thread itself (like calling native code or using `synchronized` before JDK 24), it is **pinned**. It cannot yield, which blocks the carrier thread. This slows down the application because fewer carrier threads are available to run other virtual threads.

To prevent freezes, the JVM uses **over-provisioning**:

- **Detection**: The JVM detects when a carrier thread is blocked by a pinned virtual thread.
- **Backup Threads**: The scheduler starts a temporary backup carrier thread to replace the blocked one, keeping the pool size active.
- **Limits**: The number of backup threads is capped at 256 by default.
- **Cleanup**: When the blocking work finishes, backup threads are kept for 30 seconds and then shut down if not needed.

##### 3. Yielding

When a virtual thread blocks, the JVM intercepts the call and yields the continuation:

```java
public static void park() {
    if (Thread.currentThread().isVirtual()) {
        VirtualThreads.park(); // Yields the continuation
    } else {
        U.park(false, 0L);     // Normal OS park
    }
}
```

This pauses the virtual thread, moves its stack to the heap, and frees the carrier thread to run other tasks.

##### 4. Lazy Copying & Return Barriers

To save time, the JVM does not copy the entire stack at once:

- **Lazy Resuming**: When a virtual thread runs again, the JVM only copies the top few stack frames back to the carrier thread.
- **Return Barriers**: The JVM puts return barriers at the edge of these frames. When execution reaches the barrier, the JVM copies the next set of frames from the heap.

##### 5. OS-Level Pollers

The JVM registers blocked sockets with OS pollers (`epoll` on Linux, `kqueue` on macOS, `wepoll` on Windows). When the OS says I/O is ready, the JVM wakes up the virtual thread and schedules it back onto a carrier thread.

---

#### 8. Using the Internal Continuation Class

We can use Java's internal `Continuation` API to see how threads yield and resume.

> [!WARNING]
> These internal APIs (`jdk.internal.vm.*`) are private and may change. To run this code, you must add the `--add-exports` flag during compilation and execution.

```java
package com.example.concurrency;

import jdk.internal.vm.Continuation;
import jdk.internal.vm.ContinuationScope;

public class ContinuationExample {
    public static void main(String[] args) {
        ContinuationScope scope = new ContinuationScope("demo-scope");

        Continuation continuation = new Continuation(scope, () -> {
            System.out.println("Line 1: Hello from continuation!");
            Continuation.yield(scope); // Pause and return control to caller

            System.out.println("Line 2: Resumed!");
            Continuation.yield(scope); // Pause again

            System.out.println("Line 3: Finished!");
        });

        System.out.println("Main: Running first time...");
        continuation.run(); // Runs until first yield

        System.out.println("Main: Running second time...");
        continuation.run(); // Resumes until second yield

        System.out.println("Main: Running third time...");
        continuation.run(); // Finishes
    }
}
```

##### How Continuations Work

1. **Continuation Scope**: Groups related continuations.
2. **First Run (`continuation.run()`)**: Starts the continuation. The JVM runs the code until it hits `Continuation.yield(scope)`.
3. **Yielding (`yield()`)**: Saves the execution state, moves the stack frames to the heap, and pauses the continuation. Control returns to the caller.
4. **Resuming**: Calling `run()` again copies the stack frames from the heap back to the thread and resumes execution exactly where it paused.

##### Output

```text
Main: Running first time...
Line 1: Hello from continuation!
Main: Running second time...
Line 2: Resumed!
Main: Running third time...
Line 3: Finished!
```

---

#### 9. Async Aggregation

Traditional concurrency requires complex callback chains or reactive pipelines. With virtual threads, blocking calls like `Future.get()` are cheap. We can write clean, sequential code that runs concurrently:

```java
package com.example.concurrency;

import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

public class AsyncAggregationDemo {

    public String generatePhrase() throws Exception {
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            Callable<String> fetchAdjective = () -> {
                Thread.sleep(200); // Cheap unmounting block
                return "intelligent";
            };
            Callable<String> fetchNoun = () -> {
                Thread.sleep(200); // Cheap unmounting block
                return "concurrency";
            };

            // invokeAll runs tasks concurrently using virtual threads
            List<Future<String>> results = executor.invokeAll(List.of(fetchAdjective, fetchNoun));

            // Blocking .get() calls do not block the underlying carrier threads
            return results.get(0).get() + " " + results.get(1).get();
        }
    }
}
```

##### How Async Aggregation Works

1. **Running Tasks (`invokeAll()`)**: Runs tasks concurrently by spawning a virtual thread for each task. It pauses the caller until all tasks finish.
2. **Yielding on Sleep**: When a task calls `Thread.sleep(200)`, it yields its carrier thread. The carrier thread is free to run other work. The JVM wakes the virtual thread up when the timer expires.
3. **Getting Results (`get()`)**: Since `invokeAll()` waits for all tasks to finish, calling `.get()` returns the values immediately without blocking or wasting CPU.

---

#### 10. Structured Concurrency Preview

The `StructuredTaskScope` API (preview) helps group and run concurrent subtasks. It links their lifetimes to a parent scope. If one subtask fails, the others are cancelled automatically, preventing thread leaks:

```java
package com.example.concurrency;

import java.util.concurrent.StructuredTaskScope;
import java.util.concurrent.StructuredTaskScope.Subtask;

public class StructuredTeaser {
    public String executeParallelAggregation() throws Exception {
        // Enforces structured boundaries: all subtasks must complete or cancel before scope exits
        try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
            Subtask<String> s1 = scope.fork(() -> {
                Thread.sleep(150);
                return "Structured";
            });
            Subtask<String> s2 = scope.fork(() -> {
                Thread.sleep(150);
                return "Loom";
            });

            scope.join();           // Join both forks
            scope.throwIfFailed();  // Propagate failure if any child task crashed

            return s1.get() + " " + s2.get();
        }
    }
}
```

##### How Structured Concurrency Works

1. **Spawning Subtasks (`scope.fork()`)**: Spawns a new virtual thread nested under the parent scope.
2. **Waiting for Tasks (`scope.join()`)**: Pauses the parent thread until all subtasks finish or fail.
3. **Handling Failures (`throwIfFailed()`)**: If any subtask fails, it cancels all other subtasks in the scope and throws the error, avoiding wasted CPU.

---

#### 11. Rate Limiting

Do not pool virtual threads—it is an anti-pattern. Instead, use a **Semaphore** to limit concurrent access to databases or external APIs.

```java
package com.example.concurrency;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;

public class ChuckNorrisFetcher {
    private static final int MAX_PARALLEL = 10;
    private final Semaphore semaphore = new Semaphore(MAX_PARALLEL);
    private final HttpClient client = HttpClient.newBuilder()
                                                .executor(Executors.newVirtualThreadPerTaskExecutor())
                                                .build();

    public String fetchJoke() {
        // Safe Pattern: acquire() MUST occur BEFORE the try block
        try {
            semaphore.acquire();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Task interrupted", e);
        }

        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("https://api.chucknorris.io/jokes/random"))
                    .GET()
                    .build();
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            return response.body();
        } catch (Exception e) {
            throw new RuntimeException("HTTP Request failed", e);
        } finally {
            semaphore.release(); // Guaranteed release in finally block
        }
    }
}
```

##### How Semaphore Throttling Works

1. **Rate Limiting**: Creating millions of virtual threads can overload external servers. A `Semaphore` limits how many run at once. If no permits are available, the virtual thread yields its carrier thread until a permit is released.
2. **Safe Acquire**: Always call `acquire()` before the `try` block. If `acquire()` is inside `try` and gets interrupted, the `finally` block will call `release()` without actually holding a permit. This corrupts the semaphore counter.
3. **HTTP Client**: The `HttpClient` runs tasks on virtual threads. Senders can block on network requests without blocking carrier threads.

---

#### 12. Pinning

**Pinning** happens when a virtual thread cannot unmount from its carrier thread. This locks the carrier thread, wasting OS resources if the virtual thread blocks on I/O.

##### Causes of Pinning

1. **`synchronized` Blocks/Methods (before JDK 24)**: Holding a monitor lock prevents yielding.
2. **Native Code**: Native functions run outside JVM control and pin the carrier thread.

##### Replacing `synchronized` with `ReentrantLock`

To avoid pinning, replace `synchronized` with `ReentrantLock`:

```diff
-private final Object lock = new Object();
-public void executeTask() {
-    synchronized (lock) {
-        doBlockingIO();
-    }
-}
+private final ReentrantLock lock = new ReentrantLock();
+public void executeTask() {
+    lock.lock();
+    try {
+        doBlockingIO();
+    } finally {
+        lock.unlock();
+    }
+}
```

##### JDK 24 Updates (JEP 491)

JDK 24 introduces **JEP 491**, which allows virtual threads to yield and unmount even inside `synchronized` blocks. However, native code (JNI) pinning still happens, so keep native calls short.

---

#### 13. The ThreadLocal Problem

`ThreadLocal` variables are safe in small thread pools, but virtual threads run in the millions. Storing objects in `ThreadLocal` for millions of virtual threads can quickly cause out-of-memory errors.

##### Memory Bloat Example

If 1,000,000 virtual threads each store a 500 KB object in a `ThreadLocal`, it uses **500 GB** of heap:
$$\text{Memory} = 1,000,000 \times 500 \text{ KB} = 500 \text{ GiB}$$

##### The Solution

1. Avoid `ThreadLocal` in virtual threads.
2. Pass data directly in method arguments.
3. Use **Scoped Values** (covered in Module 5) for lightweight context sharing.

---

#### 14. Monitoring and Diagnostics

##### JVM Flags

- `-Djdk.traceVirtualThreadLocals`: Logs a stack trace whenever a virtual thread uses a `ThreadLocal`.
- `-Djdk.tracePinnedThreads=full` or `short`: Logs a stack trace when a virtual thread blocks while pinned.

##### JFR Events

Use these Java Flight Recorder events to profile virtual threads:

- `jdk.VirtualThreadStart` / `jdk.VirtualThreadEnd`: Track thread lifecycles.
- `jdk.VirtualThreadPinned`: Triggers when a thread blocks while pinned (default threshold: 20ms).
- `jdk.VirtualThreadSubmitFailed`: Logs scheduling pool failures.

##### JSON Thread Dumps

Generate thread dumps including virtual threads:

```bash
jcmd <PID> Thread.dump_to_file -format=json thread_dump.json
```

These dumps are lightweight because they only focus on stack frames.

##### Programmatic Thread Dumps

You can also generate these dumps from Java code:

```java
package com.example.concurrency;

import com.sun.management.HotSpotDiagnosticMXBean;
import java.lang.management.ManagementFactory;

public class ProgrammaticDumper {
    public static void dumpVirtualThreads(String absolutePath) throws Exception {
        var mxBean = ManagementFactory.getPlatformMXBean(HotSpotDiagnosticMXBean.class);
        mxBean.dumpThreads(absolutePath, HotSpotDiagnosticMXBean.ThreadDumpFormat.JSON);
    }
}
```

---

#### 15. Migration

1. **Update Libraries**: Update JDBC drivers, HTTP clients, and logging libraries to prevent pinning.
2. **Do Not Pool Virtual Threads**: Use `Executors.newVirtualThreadPerTaskExecutor()` instead of thread pools.
3. **Use Semaphores to Throttle**: Limit concurrent access to databases or external APIs using semaphores.
4. **Isolate Pinning Code**: If you must use code that pins carrier threads (like JNI), run it in a separate platform thread pool.

---

#### 16. ForkJoinPool Work-Stealing and ManagedBlocker

Virtual threads are scheduled using a dedicated `ForkJoinPool`.

##### FIFO Mode for Fairness

Parallel streams use LIFO (Last-In, First-Out) mode to keep data in CPU cache. Virtual threads use **FIFO (First-In, First-Out)** mode. Since virtual threads usually represent separate, independent tasks (like HTTP requests), FIFO ensures fairness and prevents older tasks from waiting too long.

##### How Work-Stealing Works

1. **Local Queues**: Each carrier thread has its own private queue of virtual threads.
2. **Global Queue**: Used for tasks submitted from outside the pool.
3. **Stealing**: When a carrier thread runs out of tasks, it:
    - Pops the next task from the front (head) of its own queue.
    - If empty, it steals a task from the back (tail) of another carrier thread's queue to avoid conflicts.
    - If all local queues are empty, it checks the global queue.
    - If still empty, the carrier thread goes to sleep.

```text
=================== WORK-STEALING SCHEDULER MECHANICS ===================

  [Carrier Thread 1]                           [Carrier Thread 2]
     (Active Worker)                              (Idle Worker)
          │                                            │
          ▼                                            ▼
   Local Deque 1                                Local Deque 2
┌──────────────────┐                         ┌──────────────────┐
│ Head: Task 1     │ ◄── [Pops Next]         │                  │
│       Task 2     │                         │      (EMPTY)     │
│ Tail: Task 3     │ ◄───────────────────────┼─── [Steals Task] │
└──────────────────┘                         └──────────────────┘
```

##### Over-Provisioning and the Thread Explosion Risk

When a virtual thread blocks the carrier thread itself (like legacy database drivers or file I/O), the carrier thread cannot yield. This is called native blocking or pinning.

To keep the application running, the scheduler uses **over-provisioning**:

- The JVM detects when a carrier thread is about to block.
- It starts a **backup carrier thread** to keep the target number of active threads running.
- **The Risk**: If thousands of virtual threads block their carrier threads at the same time, the JVM will spawn thousands of backup carrier threads. This can cause high memory use, context-switching overhead, or crashes.

##### Using `ManagedBlocker`

You can wrap blocking work in the `ForkJoinPool.ManagedBlocker` interface. This tells the scheduler to spawn a backup thread if needed, keeping the system active.

```java
package com.example.concurrency;

import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.TimeUnit;

/**
 * Demonstrates how to use ManagedBlocker to inform the ForkJoinPool
 * scheduler that a thread is going to perform a blocking operation,
 * allowing the JVM to spawn backup carrier threads to maintain parallelism.
 */
public class ManagedBlockerDemo {

    public static class SecureResourceBlocker implements ForkJoinPool.ManagedBlocker {
        private final long sleepTimeMs;
        private boolean isDone = false;

        public SecureResourceBlocker(long sleepTimeMs) {
            this.sleepTimeMs = sleepTimeMs;
        }

        @Override
        public boolean block() throws InterruptedException {
            // Simulate a physical blocking call (e.g. JNI or legacy driver call)
            TimeUnit.MILLISECONDS.sleep(sleepTimeMs);
            isDone = true;
            return true;
        }

        @Override
        public boolean isReleasable() {
            return isDone;
        }
    }

    public static void executeBlockingTask(long sleepTimeMs) {
        SecureResourceBlocker blocker = new SecureResourceBlocker(sleepTimeMs);
        try {
            // ForkJoinPool.managedBlock manages the execution.
            // If the current thread is a carrier thread running in a ForkJoinPool,
            // the scheduler will spawn a backup platform thread to preserve parallelism.
            ForkJoinPool.managedBlock(blocker);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            System.err.println("Blocking task was interrupted: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        System.out.println("Starting ManagedBlocker Simulation...");
        long start = System.currentTimeMillis();

        // Run the blocking task wrapped in our ManagedBlocker
        executeBlockingTask(500);

        long duration = System.currentTimeMillis() - start;
        System.out.println("ManagedBlocker task completed in " + duration + " ms.");
    }
}
```

##### How `ManagedBlockerDemo` Works

1. **`ManagedBlocker` Implementation**: The `SecureResourceBlocker` class implements `ForkJoinPool.ManagedBlocker`, which requires `block()` (the blocking work) and `isReleasable()` (checks if done).
2. **Scheduler Notification**: `ForkJoinPool.managedBlock(blocker)` tells the pool this thread is about to block. If the thread is a carrier thread, the pool starts a backup carrier thread to run other tasks while this one is blocked.

---

### Hands-On Labs

#### Lab 2.1 — Virtual Thread Creation Styles

**Objective**: Create virtual threads using all four methods, see that they are daemon threads, and use `.join()` to prevent early program exit.

##### Implementation (`VirtualThreadCreationDemo.java`)

```java
package com.example.concurrency.lab2_1;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

public class VirtualThreadCreationDemo {

    public static void main(String[] args) throws Exception {
        System.out.println("=== Lab 2.1: Virtual Thread Creation Styles ===");

        // 1. Daemon thread exit demonstration
        Thread daemonThread = Thread.startVirtualThread(() -> {
            try {
                Thread.sleep(500);
                System.out.println("[DAEMON] This will NOT print if main exits too fast!");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });

        // Let the daemon start but don't join yet
        Thread.sleep(50);
        System.out.println("Main thread has started the daemon thread.");

        // 2. Style 1: Thread.startVirtualThread
        Thread t1 = Thread.startVirtualThread(() -> {
            System.out.println("Style 1 execution. Thread name: " + Thread.currentThread());
        });
        t1.join();

        // 3. Style 2: Thread.ofVirtual().start()
        Thread t2 = Thread.ofVirtual()
                          .name("custom-vt-", 1)
                          .start(() -> {
                              System.out.println("Style 2 execution. Thread name: " + Thread.currentThread().getName());
                          });
        t2.join();

        // 4. Style 3: Thread.ofVirtual().unstarted()
        Thread t3 = Thread.ofVirtual()
                          .name("deferred-vt")
                          .unstarted(() -> {
                              System.out.println("Style 3 execution. Thread name: " + Thread.currentThread().getName());
                          });
        t3.start(); // Explicitly start execution
        t3.join();

        // 5. Style 4: ExecutorService Integration
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            Future<String> future = executor.submit(() -> {
                System.out.println("Style 4 execution. Thread ID: " + Thread.currentThread().threadId());
                return "Style 4 result";
            });
            System.out.println("Future return value: " + future.get());
        } // Executor auto-close blocks until all subtasks finish

        // Join daemonThread to allow its delayed execution print to complete before main exits
        daemonThread.join();
        System.out.println("=== Lab 2.1 Complete ===");
    }
}
```

---

#### Lab 2.2 — Little's Law Benchmark

**Objective**: Build a benchmark to run 10,000 tasks with 500ms delay. Compare execution times and throughput between virtual threads and platform thread pools of different sizes.

##### Implementation (`LittleLawExample.java`)

```java
package com.example.concurrency.lab2_2;

import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.IntStream;

public class LittleLawExample {

    public static void main(String[] args) {
        int numTasks = 10000;
        int latencyMs = 500; // Simulated latency (d)

        Runnable ioBoundTask = () -> {
            try {
                // Simulate I/O sleep duration
                Thread.sleep(Duration.ofMillis(latencyMs));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        };

        System.out.println("=== Lab 2.2: Little's Law Benchmark ===");
        System.out.println("Tasks: " + numTasks + " | I/O Latency: " + latencyMs + " ms\n");

        benchmark("Virtual Threads", Executors.newVirtualThreadPerTaskExecutor(), ioBoundTask, numTasks);
        benchmark("Platform Pool (100 Threads)", Executors.newFixedThreadPool(100), ioBoundTask, numTasks);
        benchmark("Platform Pool (500 Threads)", Executors.newFixedThreadPool(500), ioBoundTask, numTasks);
        benchmark("Platform Pool (1000 Threads)", Executors.newFixedThreadPool(1000), ioBoundTask, numTasks);
    }

    private static void benchmark(String label, ExecutorService executor, Runnable task, int numTasks) {
        Instant startTime = Instant.now();
        AtomicLong completedCount = new AtomicLong(0);

        try (executor) {
            IntStream.range(0, numTasks).forEach(i -> {
                executor.submit(() -> {
                    task.run();
                    completedCount.incrementAndGet();
                });
            });
        } // blocks until shutdown completes

        Instant endTime = Instant.now();
        long elapsedMs = Duration.between(startTime, endTime).toMillis();
        double throughput = (completedCount.get() / (double) elapsedMs) * 1000.0;

        System.out.printf("%-30s - Time: %5d ms | Throughput: %8.2f tasks/s%n",
                label, elapsedMs, throughput);
    }
}
```

##### Typical Results

```text
Virtual Threads                - Time:   545 ms | Throughput: 18348.62 tasks/s
Platform Pool (100 Threads)    - Time: 50124 ms | Throughput:   199.50 tasks/s
Platform Pool (500 Threads)    - Time: 10098 ms | Throughput:   990.29 tasks/s
Platform Pool (1000 Threads)   - Time:  5062 ms | Throughput:  1975.50 tasks/s
```

---

#### Lab 2.3 — Pinning Detection & Fix

**Objective**: Write a demo showing how `synchronized` blocks cause pinning when a thread sleeps, and how replacing them with `ReentrantLock` allows the thread to yield and change carrier threads.

##### 1. Pinning Demo (`ThreadPinnedExample.java`)

```java
package com.example.concurrency.lab2_3;

import java.util.List;
import java.util.stream.IntStream;

public class ThreadPinnedExample {
    private static final Object lock = new Object();

    public static void main(String[] args) {
        System.out.println("Starting Thread Pinned Demo...");
        List<Thread> threads = IntStream.range(0, 5)
            .mapToObj(i -> Thread.ofVirtual().unstarted(() -> {
                if (i == 0) {
                    System.out.println("Before Sync block: " + Thread.currentThread());
                }

                synchronized (lock) {
                    try {
                        Thread.sleep(100); // Blocking inside synchronized causes pinning
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                }

                if (i == 0) {
                    System.out.println("After Sync block:  " + Thread.currentThread());
                }
            })).toList();

        threads.forEach(Thread::start);
        threads.forEach(t -> {
            try { t.join(); } catch (InterruptedException ignored) {}
        });
    }
}
```

##### How Pinning and the Fix Work

1. **The `synchronized` Trap (`ThreadPinnedExample`)**: Entering a `synchronized` block acquires a monitor lock. Because the virtual thread holds a monitor lock, the JVM cannot yield it. Sleeping or blocking locks the carrier thread, preventing other virtual threads from running.
2. **Fixing with `ReentrantLock` (`PreventPinningExample`)**: `ReentrantLock` is written in Java and supports yielding. When a virtual thread calls `lock.lock()` or sleeps inside the lock, it yields its carrier thread, letting other work run.
3. **Verifying with Traces**: The JVM flag `-Djdk.tracePinnedThreads=short` prints traces showing when pinning occurs. In the `ReentrantLock` fix, the carrier name changes (e.g., from `worker-1` to `worker-3`) after sleep, proving the virtual thread successfully yielded and ran on a different carrier thread.

##### 2. Pinning Fix (`PreventPinningExample.java`)

```java
package com.example.concurrency.lab2_3;

import java.util.List;
import java.util.concurrent.locks.ReentrantLock;
import java.util.stream.IntStream;

public class PreventPinningExample {
    private static final ReentrantLock lock = new ReentrantLock();

    public static void main(String[] args) {
        System.out.println("Starting Prevent Pinning Demo...");
        List<Thread> threads = IntStream.range(0, 5)
            .mapToObj(i -> Thread.ofVirtual().unstarted(() -> {
                if (i == 0) {
                    System.out.println("Before Lock: " + Thread.currentThread());
                }

                lock.lock();
                try {
                    Thread.sleep(100); // Sleep inside ReentrantLock allows unmounting
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    lock.unlock();
                }

                if (i == 0) {
                    System.out.println("After Lock:  " + Thread.currentThread());
                }
            })).toList();

        threads.forEach(Thread::start);
        threads.forEach(t -> {
            try { t.join(); } catch (InterruptedException ignored) {}
        });
    }
}
```

##### Tracing Pinning (Pre-JDK 24)

Execute using the trace flag:

```bash
java -Djdk.tracePinnedThreads=short -cp target/classes com.example.concurrency.lab2_3.ThreadPinnedExample
```

###### Output (ThreadPinnedExample)

```text
Before Sync block: VirtualThread[#21]/runnable@ForkJoinPool-1-worker-1
After Sync block:  VirtualThread[#21]/runnable@ForkJoinPool-1-worker-1
Thread[#21,ForkJoinPool-1-worker-1,5,CarrierThreads]
    java.base/java.lang.VirtualThread$VThreadContinuation.onPinned(VirtualThread.java:273)
    java.base/jdk.internal.vm.Continuation.onPinned0(Continuation.java:393)
    com.example.concurrency.lab2_3.ThreadPinnedExample.lambda$main$0(ThreadPinnedExample.java:18) <== monitors:1
```

###### Output (PreventPinningExample)

```text
Before Lock: VirtualThread[#20]/runnable@ForkJoinPool-1-worker-1
After Lock:  VirtualThread[#20]/runnable@ForkJoinPool-1-worker-3
```

---

#### Lab 2.4 / Pitfall — Semaphore Leaks

**Objective**: See how placing `acquire()` inside a `try` block causes permit leaks on interruption, and write a secure acquire-before-try implementation.

##### Implementation (`SemaphoreLeakDemo.java`)

```java
package com.example.concurrency.lab2_4;

import java.util.concurrent.Semaphore;

public class SemaphoreLeakDemo {

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Lab 2.4: Semaphore Permit Leak Demo ===");

        // 1. Broken Pattern
        Semaphore brokenSemaphore = new Semaphore(1);
        Thread brokenThread = Thread.ofVirtual().unstarted(() -> {
            try {
                // If interrupted here, code jumps to finally block
                brokenSemaphore.acquire();
                System.out.println("Broken acquired.");
            } catch (InterruptedException e) {
                System.out.println("Broken thread interrupted.");
            } finally {
                brokenSemaphore.release(); // DANGER: releases even if acquire failed!
            }
        });

        brokenThread.start();
        brokenThread.interrupt(); // Force InterruptedException inside acquire()
        brokenThread.join();

        System.out.println("Broken permits count after leak: " + brokenSemaphore.availablePermits());
        // Permit count increases to 2 (corrupted!)

        // 2. Correct Pattern
        Semaphore safeSemaphore = new Semaphore(1);
        Thread safeThread = Thread.ofVirtual().unstarted(() -> {
            try {
                safeSemaphore.acquire(); // Acquire BEFORE try block
            } catch (InterruptedException e) {
                System.out.println("Safe thread interrupted during acquisition.");
                return; // Exit early without calling release
            }

            try {
                System.out.println("Safe acquired.");
            } finally {
                safeSemaphore.release(); // Safe release
            }
        });

        safeThread.start();
        safeThread.interrupt();
        safeThread.join();

        System.out.println("Safe permits count after: " + safeSemaphore.availablePermits());
        // Permit count remains 1 (stable)
    }
}
```

##### How Semaphore Leaks and Fixes Work

1. **Broken Pattern**: Calling `brokenSemaphore.acquire()` inside the `try` block means that if it gets interrupted, execution jumps to the `finally` block and runs `release()`. Since no permit was actually acquired, this increases the permit count, breaking the rate limit.
2. **Safe Pattern**: Calling `safeSemaphore.acquire()` **before** the `try` block ensures that if it fails or gets interrupted, the thread exits without calling `release()`. The `finally` block only runs if a permit was successfully acquired.

---

#### Lab 2.5 — Custom Scheduler Simulation

**Objective**: Simulate how virtual threads mount, yield, and change carrier threads using the internal `Continuation` class and a custom scheduler.

##### 1. The custom thread class (`NanoThread.java`)

```java
package com.example.concurrency.lab2_5;

import jdk.internal.vm.Continuation;
import jdk.internal.vm.ContinuationScope;
import java.util.concurrent.atomic.AtomicInteger;

public class NanoThread {
    public static final NanoThreadScheduler SCHEDULER = new NanoThreadScheduler();
    public static final ContinuationScope SCOPE = new ContinuationScope("nanoThreadScope");
    private static final AtomicInteger COUNTER = new AtomicInteger(1);

    private final Continuation continuation;
    private final int nid;

    private NanoThread(Runnable runnable) {
        this.nid = COUNTER.getAndIncrement();
        this.continuation = new Continuation(SCOPE, runnable);
    }

    public static void start(Runnable runnable) {
        NanoThread thread = new NanoThread(runnable);
        SCHEDULER.schedule(thread);
    }

    public void run() {
        continuation.run();
    }

    public static NanoThread current() {
        return NanoThreadScheduler.CURRENT_NANO_THREAD.get();
    }

    @Override
    public String toString() {
        return "NanoThread-" + nid + " (" + Thread.currentThread().getName() + ")";
    }
}
```

##### 2. The custom scheduler (`NanoThreadScheduler.java`)

```java
package com.example.concurrency.lab2_5;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;

public class NanoThreadScheduler {
    public static final ThreadLocal<NanoThread> CURRENT_NANO_THREAD = new ThreadLocal<>();

    // Simulates an asynchronous OS level I/O notifier
    public static final ScheduledExecutorService IO_NOTIFIER = Executors.newSingleThreadScheduledExecutor();

    // A 2-thread Work-Stealing Pool representing our Carrier platform threads
    private final ExecutorService carrierPool = Executors.newWorkStealingPool(2);

    public void schedule(NanoThread thread) {
        carrierPool.submit(() -> {
            CURRENT_NANO_THREAD.set(thread);
            try {
                thread.run(); // Mounts and runs the continuation
            } finally {
                CURRENT_NANO_THREAD.remove();
            }
        });
    }
}
```

##### 3. The simulated I/O operation (`FileTransfer.java`)

```java
package com.example.concurrency.lab2_5;

import jdk.internal.vm.Continuation;
import java.util.Random;
import java.util.concurrent.TimeUnit;

public class FileTransfer {
    private final Random random = new Random();

    public void transfer(String fileName) {
        System.out.println("Start transferring: " + fileName + " on " + NanoThread.current());

        NanoThread currentThread = NanoThread.current();

        // Simulate background OS network transfer. When completed, schedule the task back.
        NanoThreadScheduler.IO_NOTIFIER.schedule(() -> {
            System.out.println("I/O completed for: " + fileName + ". Rescheduling...");
            NanoThread.SCHEDULER.schedule(currentThread);
        }, random.nextInt(100) + 50, TimeUnit.MILLISECONDS);

        // Unmount phase: Clear the thread local reference and yield the continuation stack
        NanoThreadScheduler.CURRENT_NANO_THREAD.remove();
        Continuation.yield(NanoThread.SCOPE); // Worker thread is freed!

        System.out.println("Finished transferring: " + fileName + " on " + NanoThread.current());
    }
}
```

##### 4. Running the Simulation (`NanoThreadDemo.java`)

```java
package com.example.concurrency.lab2_5;

import java.time.Duration;

public class NanoThreadDemo {
    public static void main(String[] args) throws Exception {
        System.out.println("=== Lab 2.5: Custom NanoThread Scheduler Demo ===");
        FileTransfer fileTransfer = new FileTransfer();

        for (int i = 0; i < 3; i++) {
            final int fileId = i;
            NanoThread.start(() -> {
                fileTransfer.transfer("File_" + fileId);
            });
        }

        // Wait to allow scheduled async event run completions
        Thread.sleep(Duration.ofSeconds(2));
        NanoThreadScheduler.IO_NOTIFIER.shutdown();
        System.out.println("=== Simulation Complete ===");
    }
}
```

##### Run Command

```bash
# Compile and run exports parameters
javac --add-exports java.base/jdk.internal.vm=ALL-UNNAMED NanoThread*.java FileTransfer.java
java --add-exports java.base/jdk.internal.vm=ALL-UNNAMED com.example.concurrency.lab2_5.NanoThreadDemo
```

##### Expected Output

```text
=== Lab 2.5: Custom NanoThread Scheduler Demo ===
Start transferring: File_0 on NanoThread-1 (ForkJoinPool-1-worker-1)
Start transferring: File_1 on NanoThread-2 (ForkJoinPool-1-worker-2)
Start transferring: File_2 on NanoThread-3 (ForkJoinPool-1-worker-1)
I/O completed for: File_1. Rescheduling...
I/O completed for: File_0. Rescheduling...
I/O completed for: File_2. Rescheduling...
Finished transferring: File_1 on NanoThread-2 (ForkJoinPool-1-worker-1)
Finished transferring: File_0 on NanoThread-1 (ForkJoinPool-1-worker-2)
Finished transferring: File_2 on NanoThread-3 (ForkJoinPool-1-worker-1)
=== Simulation Complete ===
```

##### How the Custom Scheduler Works

1. **Mounting**: `NanoThread.start()` submits the task to a 2-thread carrier pool. A carrier thread runs the continuation (`continuation.run()`), mounting it.
2. **Simulating I/O**: `FileTransfer.transfer()` schedules a background task to simulate I/O, registering a callback to run when finished.
3. **Yielding**: The task calls `Continuation.yield(NanoThread.SCOPE)`. The JVM pauses it, saves its stack, and frees the carrier thread for other work.
4. **Rescheduling**: When the simulated I/O finishes, the callback runs and schedules the task back onto the carrier pool. It resumes exactly where it paused, often on a different carrier thread.

---

### Common Pitfalls & Anti-Patterns

#### 1. CPU-Bound Work

Virtual threads do not make CPU-bound work (like math or image processing) faster. CPU-bound tasks need constant CPU attachment and cannot yield. Running them on virtual threads just adds scheduling overhead.

#### 2. Pooling Virtual Threads

Platform threads are pooled because they are expensive. Virtual threads are cheap—just create a new one for each task and throw it away when done. Pooling them is an anti-pattern.

#### 3. ThreadLocal Memory Leaks

Using `ThreadLocal` variables with millions of virtual threads can quickly leak memory if they are not cleaned up.

##### Leak Example Code

```java
package com.example.concurrency.pitfall;

import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ThreadLocalLeakDemo {
    // Large thread-local buffer simulating a request context payload
    private static final ThreadLocal<byte[]> requestContext = new ThreadLocal<>();

    public static void main(String[] args) throws Exception {
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int i = 0; i < 100_000; i++) {
                executor.submit(() -> {
                    // Allocate 1 MB payload to the context
                    byte[] payload = new byte[1024 * 1024]; // 1 MB buffer
                    requestContext.set(payload);

                    processRequest();

                    // BUG: Failing to call requestContext.remove()!
                    // requestContext.remove();
                });
            }
        }
    }

    private static void processRequest() {
        // Mock processing logic accessing the thread-local state
        String threadInfo = Thread.currentThread().toString();
        if (threadInfo.contains("Virtual")) {
            // Read value safely
            byte[] data = requestContext.get();
        }
    }
}
```

##### How the Memory Leak Happens

1. **Heap Exhaustion**: In a traditional pool (e.g., 200 threads), leaking a 1 MB buffer by forgetting `.remove()` only wastes 200 MB. But with 100,000 virtual threads, leaking 1 MB per thread uses 100 GB of heap, quickly causing an `OutOfMemoryError`.
2. **GC Roots**: While a virtual thread is suspended (waiting on I/O), the thread object is still active in the garbage collector (GC Root). Its `ThreadLocalMap` holds a strong reference to the value, so the 1 MB buffer cannot be collected, causing massive memory bloat.
3. **Fixes**:
    - **Cleanup**: Always call `ThreadLocal.remove()` in a `finally` block.
    - **Use Scoped Values**: Replace `ThreadLocal` with `ScopedValue`. Scoped values bind values to a specific execution block. When the block exits, the values are discarded automatically, avoiding leaks.

---

### Summary

1. **Thread Types**: Platform threads map 1-to-1 to kernel threads and use 1-2 MiB of off-heap stack memory. Virtual threads map to carrier threads and use lightweight heap memory.
2. **Mounting**: The JVM runs virtual threads on carrier threads using a FIFO ForkJoinPool. They yield and unmount during blocking operations.
3. **Pinning**: Synchronized blocks (before JDK 24) and native code lock virtual threads to their carrier threads. Use `ReentrantLock` to prevent pinning.
4. **ThreadLocal Risk**: Storing large objects in `ThreadLocal` across millions of virtual threads causes memory leaks. Use `ScopedValue` instead.
5. **Diagnostics**: Use JVM flags (like `-Djdk.tracePinnedThreads`), JFR, and JSON thread dumps to monitor virtual threads.

---

### Knowledge Check - Deep Dive Scenarios

#### Question 1: CPU-Bound Overhead

An application team migrates an image transcoding queue from 32 platform threads to virtual threads. The transcoding code performs mathematical pixel modifications in memory. During testing, execution slows down and carrier threads lock up. Why?

- A. The virtual threads were blocked on network I/O, triggering garbage collection.
- B. The transcoding logic is CPU-bound and does not yield. This blocks the carrier threads, while virtual thread scheduling introduces extra management overhead.
- C. The JVM automatically limits CPU-bound virtual threads to a priority of 1.
- D. Image transcoding triggers carrier pinning.

_Answer_: **B**
_Explanation_: CPU-bound tasks do not block on I/O and cannot yield. Running them on virtual threads blocks carrier threads and adds scheduling overhead.

#### Question 2: Memory Footprint under Little's Law

An API gateway receives requests and makes a downstream HTTP call with a latency ($d$) of 200ms. To achieve a throughput ($\lambda$) of 50,000 requests per second, how many concurrent virtual threads ($N$) must the JVM support? What is the stack footprint if each virtual thread requires 1KB of heap?

- A. $N = 1,000$ threads, consuming 1MB of heap space.
- B. $N = 10,000$ threads, consuming 10MB of heap space.
- C. $N = 100,000$ threads, consuming 100MB of heap space.
- D. $N = 1,000,000$ threads, consuming 1GB of heap space.

_Answer_: **B**
_Explanation_: By Little's Law: $N = \lambda \times d = 50,000 \times 0.2\text{s} = 10,000$ threads. Memory is $10,000 \times 1\text{KB} = 10\text{MB}$.

#### Question 3: Carrier Thread Pinning

A developer sees the JFR event warning: `jdk.VirtualThreadPinned`. Which Java keyword or construct is the primary source of carrier thread pinning?

- A. `volatile`
- B. `synchronized` blocks wrapping blocking I/O calls (pre-JDK 24)
- C. `ReentrantLock`
- D. `ThreadLocal`

_Answer_: **B**
_Explanation_: Holding a monitor lock (`synchronized`) prevents a virtual thread from yielding when it blocks, pinning the carrier thread.

#### Question 4: JEP 491 Monitor Changes in JDK 24

How does JEP 491 (finalized in JDK 24) change virtual thread behavior inside `synchronized` blocks?

- A. It deprecates the `synchronized` keyword.
- B. It updates the JVM scheduler to yield and unmount virtual threads even when blocking inside `synchronized` blocks, preventing carrier thread pinning.
- C. It converts all synchronized blocks into ReentrantLocks.
- D. It limits virtual threads to platform threads when monitor locks are encountered.

_Answer_: **B**
_Explanation_: JEP 491 refactors monitor locking so virtual threads can yield and unmount while holding monitors, eliminating pinning in synchronized blocks.

#### Question 5: Thread Group Constraints

A developer attempts to assign a virtual thread to a custom `ThreadGroup`. What occurs?

- A. The virtual thread is successfully added to the custom thread group.
- B. The virtual thread is created but is assigned to the immutable, system-wide `"VirtualThreads"` group, and the custom group setting is ignored.
- C. The JVM throws an `IllegalThreadStateException` at runtime.
- D. The compiler rejects the code.

_Answer_: **B**
_Explanation_: Virtual threads always belong to the immutable system group `"VirtualThreads"`. Any custom group settings are ignored.

#### Question 6: Daemon Thread Termination

Why does an application with only active virtual threads exit immediately when the main thread terminates?

- A. Virtual threads are marked as daemon threads by default, and this status cannot be changed. The JVM exits when only daemon threads remain active.
- B. The virtual threads are garbage collected.
- C. The ForkJoinPool carrier pool scheduler terminates.
- D. Virtual threads do not support background processing.

_Answer_: **A**
_Explanation_: Virtual threads are always daemon threads. The JVM exits when only daemon threads remain. You must block the main thread (using `.join()`) to let them finish.

#### Question 7: Semaphore Permit Leaks

If `semaphore.acquire()` is placed inside a `try` block whose `finally` block calls `semaphore.release()`, what happens if the thread is interrupted?

- A. The thread deadlock blocks.
- B. The permit count is corrupted because `release()` is called even if `acquire()` failed and threw an exception, releasing a permit the thread never held.
- C. The JVM throws an `IllegalMonitorStateException`.
- D. The semaphore is garbage collected.

_Answer_: **B**
_Explanation_: If interrupted inside the `try` block during `acquire()`, the thread jumps to the `finally` block and runs `release()`. This releases a permit it never successfully acquired, corrupting the counter.

#### Question 8: FIFO Async ForkJoinPool Scheduling

Why does the virtual thread scheduler run in FIFO async mode rather than LIFO mode?

- A. FIFO mode is required to access native OS network pollers.
- B. FIFO mode prevents task starvation by processing requests in their order of submission.
- C. LIFO mode does not support work-stealing.
- D. FIFO mode prevents carrier thread pinning.

_Answer_: **B**
_Explanation_: FIFO mode ensures tasks are processed fairly in order, preventing older tasks from starving.

#### Question 9: Memory Calculations for Thread-Local Bloat

If 1,000,000 virtual threads each store a 256KB buffer in a `ThreadLocal`, what is the total memory footprint on the heap?

- A. 256MB
- B. 2.56GB
- C. 256GB
- D. 2.56TB

_Answer_: **C**
_Explanation_: $1,000,000 \times 256\text{KB} = 256\text{GB}$. This shows why large thread-local allocations are dangerous with virtual threads.

#### Question 10: JVM Flag for ThreadLocal Diagnostics

Which JVM flag helps detect `ThreadLocal` usage in virtual threads?

- A. `-Djdk.tracePinnedThreads=full`
- B. `-Djdk.traceVirtualThreadLocals`
- C. `-XX:StartFlightRecording`
- D. `-Dspring.threads.virtual.enabled=true`

_Answer_: **B**
_Explanation_: `-Djdk.traceVirtualThreadLocals` logs a stack trace whenever a virtual thread reads or writes a `ThreadLocal`.

#### Question 11: OS Thread Scheduler vs JVM Virtual Thread Scheduler

How do the OS scheduler and the JVM virtual thread scheduler differ?

- A. The OS scheduler uses cooperative multitasking, while the JVM uses preemptive timeslicing.
- B. The OS scheduler uses preemptive timeslicing (forcing threads to yield CPU cycles at regular intervals), whereas the JVM's virtual thread scheduler relies on cooperative scheduling (continuations only yield when blocking on I/O or synchronized locks).
- C. The JVM scheduler uses physical CPU register swapping.
- D. None of the above.

_Answer_: **B**
_Explanation_: OS schedulers force platform threads to yield regularly (preemption). The JVM schedules virtual threads cooperatively: they run until they hit a blocking point (like I/O or locks) and yield control.

#### Question 12: Virtual Thread Priority Mapping

What happens if you call `Thread.currentThread().setPriority(Thread.MAX_PRIORITY)` inside a virtual thread?

- A. The virtual thread is prioritized by the ForkJoinPool scheduler.
- B. The call is accepted but ignored by the JVM; the priority of a virtual thread is fixed at `Thread.NORM_PRIORITY` (5) and has no effect on carrier scheduling.
- C. The JVM throws an `UnsupportedOperationException`.
- D. The priority is delegated to the OS kernel.

_Answer_: **B**
_Explanation_: Virtual threads do not support priority scheduling. Their priority is fixed at 5.

#### Question 13: Memory Visibility Across Carrier Context Shifts

If a virtual thread writes to a variable on carrier thread A, yields, and resumes on carrier thread B, what guarantees that carrier thread B sees the write?

- A) The volatile happens-before memory fence.
- B) The happens-before relationship enforced by the JVM scheduler: unmounting a virtual thread generates a release barrier, and remounting it generates an acquire barrier, ensuring full memory visibility of heap stack frames across carrier switches.
- C) The CPU cache is flushed to disk.
- D) There is no guarantee, causing race conditions.

_Answer_: **B**
_Explanation_: The JVM unmounting acts as a release barrier and remounting acts as an acquire barrier, guaranteeing carrier B sees all changes made before yielding.

#### Question 14: ReentrantLock AQS Parking vs synchronized blocks

Why does a virtual thread blocking on a `ReentrantLock` unmount successfully, while a `synchronized` block (pre-JDK 24) pins the carrier?

- A. `ReentrantLock` uses native OS kernel locks.
- B. `ReentrantLock` is written in Java and uses AQS, which delegates parking to `LockSupport.park()`. The JVM intercepts this call to yield the continuation. In contrast, `synchronized` uses native C++ ObjectMonitor locks, which are coupled to the physical platform thread stack frame.
- C. `synchronized` is a deprecated keyword.
- D. None of the above.

_Answer_: **B**
_Explanation_: `ReentrantLock` uses `LockSupport.park()` which the JVM intercepts to yield the continuation. `synchronized` blocks (pre-JDK 24) use native monitor locks tied to the platform thread stack, preventing yielding.

#### Question 15: Thread.join() Redirect Rules for Virtual Threads

What is the internal JVM behavior when a platform thread calls `join()` on a virtual thread?

- A. The platform thread blocks its native OS thread.
- B. The platform thread yields its continuation.
- C. The platform thread is parked using `LockSupport.park()`. Since it is a platform thread, it blocks the native thread; once the virtual thread exits and is garbage collected, the platform thread is unparked.
- D. The JVM crashes.

_Answer_: **C**
_Explanation_: Calling `join()` on a virtual thread parks the platform thread, blocking its native OS thread until the virtual thread finishes.

#### Question 16: ThreadGroup Name Mapping

What is the name of the system-level thread group for virtual threads?

- A. `"LoomPool"`, mutable.
- B. `"VirtualThreads"`, immutable.
- C. `"SystemGroup"`, mutable.
- D. `"CarrierGroup"`, immutable.

_Answer_: **B**
_Explanation_: All virtual threads belong to the unchangeable system group named `"VirtualThreads"`.

#### Question 17: Carrier Thread Pinning Mitigation in JDK 24

What JVM change in JEP 491 (JDK 24/25) mitigates pinning in synchronized blocks?

- A) It removes the `synchronized` keyword.
- B) It refactors the JVM scheduler to yield and unmount virtual threads even when blocking inside `synchronized` blocks, resolving carrier thread pinning issues.
- C) It converts all monitors to spinlocks.
- D) It redirects monitors to off-heap maps.

_Answer_: **B**
_Explanation_: JEP 491 refactors monitors to allow virtual threads to yield and unmount even while holding them.

#### Question 18: VirtualThread MXBean Access

Why does `ThreadMXBean.getThreadCount()` return low counts even with 1,000,000 active virtual threads?

- A) JMX is disabled when virtual threads are active.
- B) The standard `ThreadMXBean` only tracks platform threads. To query virtual threads, you must use proprietary HotSpot APIs (like `HotSpotDiagnosticMXBean`) or parse JSON thread dumps.
- C) Virtual threads are not registered in the JVM.
- D) None of the above.

_Answer_: **B**
_Explanation_: `ThreadMXBean` only tracks platform threads. Virtual threads are excluded to prevent breaking legacy monitoring tools. Use JFR or `HotSpotDiagnosticMXBean` instead.

#### Question 19: Sleep Durations under Virtual Thread Scheduler

Does a virtual thread running `Thread.sleep(Duration)` block the carrier thread?

- A. Yes, the carrier thread is blocked.
- B. No, the virtual thread yields its continuation, freeing the carrier thread, and is rescheduled only after the timer expires.
- C. Yes, but only if the carrier pool is full.
- D. None of the above.

_Answer_: **B**
_Explanation_: Sleep is blocking-tolerant. The virtual thread yields its continuation and frees the carrier thread. The JVM schedules it back when the timer expires.

#### Question 20: JFR Event VirtualThreadStart Properties

What metadata attributes are captured by the `jdk.VirtualThreadStart` JFR event?

- A. The name of the database driver.
- B. The virtual thread's ID, name, and the Java thread ID of the carrier thread executing it.
- C. The heap memory usage percentage.
- D. The CPU temperature.

_Answer_: **B**
_Explanation_: The event records the virtual thread's ID, name, and its carrier thread ID for debugging.

---

### 17. Loom Diagnostics: Understanding Thread Dumps

Traditional thread dumps (`jstack`) list every thread and stack trace, which is unreadable if you have 100,000 virtual threads.

Loom solves this with a **JSON-based thread dump format** designed to handle massive thread counts safely.

#### How to Generate a Virtual Thread Dump

Traditional `jstack` does **not** include virtual threads. To generate a dump that includes them, use the `jcmd` utility:

```bash
# 1. Find your Java process ID (PID)
jps

# 2. Generate a JSON thread dump including virtual threads
jcmd <PID> Thread.dump_to_file -format=json thread_dump.json
```

This streams the dump directly to a JSON file in user-space, avoiding freezes.

#### Inside the JSON Thread Dump Format

Here is a simplified JSON snippet representing a healthy, parked virtual thread:

```json
{
    "container": "<virtual>",
    "threadId": 124,
    "name": "payment-worker-4",
    "state": "PARKED",
    "blocker": "java.util.concurrent.locks.AbstractQueuedSynchronizer$ConditionObject",
    "stackTrace": [
        "java.base/java.lang.VirtualThread.parkOnCarrierThread(VirtualThread.java:661)",
        "java.base/java.lang.VirtualThread.park(VirtualThread.java:593)",
        "java.base/java.lang.System$2.park(System.java:2643)",
        "java.base/java.util.concurrent.locks.LockSupport.park(LockSupport.java:219)",
        "java.base/java.util.concurrent.locks.AbstractQueuedSynchronizer$ConditionNode.block(AbstractQueuedSynchronizer.java:506)",
        "java.base/java.util.concurrent.ForkJoinPool.managedBlock(ForkJoinPool.java:3464)",
        "java.base/java.util.concurrent.locks.AbstractQueuedSynchronizer$ConditionObject.await(ConditionObject.java:1623)",
        "com.example.concurrency.PaymentService.lambda$process$0(PaymentService.java:42)"
    ]
}
```

##### Key Fields to Check:

1. **`"container": "<virtual>"`**: Marks it as a virtual thread on the heap (instead of `"container": "<native>"`).
2. **`"state": "PARKED"`**: The thread is suspended and does not use CPU.
3. **`"blocker"`**: The object the thread is waiting on (like a lock or queue). This is healthy; the thread has yielded its carrier.

#### Finding a Pinning Bug in the Dump

Here is an unhealthy virtual thread. It is blocked on I/O, but it is **pinned** because it is executing inside a `synchronized` block:

```json
{
    "container": "<virtual>",
    "threadId": 128,
    "name": "db-query-thread",
    "state": "PINNED",
    "carrierThread": "ForkJoinPool-1-worker-3",
    "stackTrace": [
        "java.base/java.lang.VirtualThread.parkOnCarrierThread(VirtualThread.java:661)",
        "java.base/java.lang.VirtualThread.park(VirtualThread.java:593)",
        "java.base/java.lang.System$2.park(System.java:2643)",
        "java.base/java.util.concurrent.locks.LockSupport.park(LockSupport.java:219)",
        "java.base/java.net.socket.SocketInputStream.read(SocketInputStream.java:172)",
        "com.mysql.cj.protocol.a.SimplePacketReader.readPacket(SimplePacketReader.java:63) - locked <0x0000000712345678> (a com.mysql.cj.protocol.a.SimplePacketReader)",
        "com.mysql.cj.protocol.a.NativeProtocol.readPacket(NativeProtocol.java:581)",
        "com.example.concurrency.DbService.fetchUser(DbService.java:31)"
    ]
}
```

##### Red Flags in the JSON:

1. **`"state": "PINNED"`**: Shows the thread is pinned and cannot yield.
2. **`"carrierThread": "..."`**: Shows the carrier thread is blocked and cannot run other tasks.
3. **`locked <...>`**: Points to the `synchronized` lock causing the pinning.

#### Diagnosing Thread Pinning: A Quick Checklist

If your application experiences sudden latency spikes or hangs:

1. **Generate a JSON dump** using `jcmd`.
2. **Search for `"state": "PINNED"`** (e.g., `grep -B 5 -A 10 "PINNED" thread_dump.json`).
3. **Trace the stack** of pinned threads to find `synchronized` blocks.
4. **Replace the synchronized locks** with `ReentrantLock` to allow yielding.
