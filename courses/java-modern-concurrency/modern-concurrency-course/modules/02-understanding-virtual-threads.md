# Module 02: Understanding Virtual Threads

### Learning Objectives
- Differentiate between Platform Threads and Virtual Threads in memory allocation, scheduling algorithms, and blocking behaviors.
- Apply the four primary JDK APIs to construct, configure, and execute virtual threads.
- Define and solve concurrency throughput scenarios using Little's Law ($\lambda = N/d$).
- Trace the internal JVM mechanisms of Loom, including Continuation stack frame swaps, carrier-thread mounting, OS pollers, lazy-copying, return barriers, and `LockSupport.park()` interception.
- Implement the internal JVM `Continuation` class programmatically to understand yielding mechanics.
- Construct a custom virtual thread executor simulation (`NanoThread` & `NanoThreadScheduler`) to demonstrate carrier thread switching.
- Restructure blocking synchronizations to eliminate carrier-thread pinning using `ReentrantLock` and analyze JEP 491 (JDK 24) monitor changes.
- Evaluate the memory overhead of `ThreadLocal` variables in high-concurrency systems and replace them with modern Scoped Values.
- Configure JVM diagnostics, JFR templates, MXBean hooks, and JSON thread dumps to monitor virtual thread state.

---

### Concept Explanation

#### 1. Two Kinds of Threads: Platform vs. Virtual

With the introduction of Project Loom in JDK 21, Java concurrency supports two types of execution threads:

##### Platform Threads
- **1-to-1 Mapping**: Every platform thread maps directly to one operating system kernel thread.
- **Resource Footprint**: Heavy. Each platform thread allocates a monolithic stack frame outside the JVM heap (typically **1 to 2 MiB** in Linux/Unix). 
- **Scheduling**: Handled by the OS kernel scheduler. Context switches require switching between user mode and kernel mode, wasting CPU cache lines and registers.

##### Virtual Threads
- **M-to-N Mapping**: Millions of virtual threads run on top of a small, configured pool of platform threads called **Carrier Threads**.
- **Resource Footprint**: Lightweight. Virtual threads are ordinary Java objects allocated in the JVM heap, starting with a footprint of just a few hundred bytes.
- **Scheduling**: Managed entirely by the JVM using a specialized work-stealing `ForkJoinPool` running in **First-In, First-Out (FIFO) async mode**. This is distinct from the common `ForkJoinPool` used by Parallel Streams, which runs in Last-In, First-Out (LIFO) mode.

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
                         └───────────────────┘
```

---

#### 2. Key Architectural Differences
- **Lightweight Memory Structure**: Because their stack frames reside in the JVM heap, virtual threads do not require monolithic off-heap memory. They grow and shrink dynamically as call depth fluctuates.
- **JVM Scheduling Bypass**: The OS kernel does not know about virtual threads. The JVM schedules virtual threads, eliminating native context-switching thread overhead.
- **Blocking Tolerance**: When a virtual thread executes a blocking operation (e.g., thread sleep, socket read, database call), the JVM unmounts the virtual thread, copies its execution stack frames back to the heap, and frees the carrier thread. The carrier thread immediately runs other runnable virtual threads.
- **Seamless API Integration**: A virtual thread is a subclass of `java.lang.Thread`. All existing APIs (`Runnable`, `ThreadLocal`, `ExecutorService`) continue to work seamlessly.

---

#### 3. Setting Up Your Environment
To run virtual threads, ensure you have **JDK 21 or later** installed. For structured concurrency and scoped values (which remain preview features in modern JDKs such as JDK 24/25), you will need preview flags.

##### SDKMAN Version Management
```bash
# List available JDK versions
sdk list java

# Install a compatible JDK 21+ (e.g., OpenJDK 21.0.2)
sdk install java 21.0.2-open
sdk use java 21.0.2-open
```

##### Compiling and Running Preview Code (JDK 21+)
```bash
# Compile with preview features enabled
javac --enable-preview --release 21 YourClass.java

# Run with preview features enabled
java --enable-preview YourClass
```

---

#### 4. Creating Virtual Threads — All Four Ways

##### 1. `Thread.startVirtualThread(Runnable)`
Spawns and executes a virtual thread immediately.
```java
Thread.startVirtualThread(() -> {
    System.out.println("Executing inside: " + Thread.currentThread().threadId());
});
```

##### 2. The Builder API (`Thread.ofVirtual().start(Runnable)`)
Fluent builder style that starts execution immediately.
```java
Thread t = Thread.ofVirtual()
                 .name("worker-", 1)
                 .start(() -> System.out.println("Builder started: " + Thread.currentThread().getName()));
```

##### 3. The Builder API Deferred (`Thread.ofVirtual().unstarted(Runnable)`)
Configures the thread metadata, leaving execution deferred until `start()` is explicitly called.
```java
Thread t = Thread.ofVirtual()
                 .name("deferred-worker")
                 .unstarted(() -> System.out.println("Executing deferred: " + Thread.currentThread().getName()));
t.start();
```

##### 4. ExecutorService Integration (`Executors.newVirtualThreadPerTaskExecutor()`)
Creates an `ExecutorService` that spawns a new virtual thread for each task submission.
```java
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    Future<String> future = executor.submit(() -> "Task completed");
    System.out.println(future.get());
}
```

##### Line-by-Line Execution Analysis of the Four Creation Styles
1. **`Thread.startVirtualThread(Runnable)`**:
   - **JVM Actions**: This is the fastest shorthand API. Under the hood, it invokes a constructor package-private to `java.lang.Thread`, creating a new virtual thread, registering the `Runnable` task, assigning default properties (such as daemon status `true` and priority `NORM_PRIORITY`), and immediately calling `start()`. This schedules it inside the Loom ForkJoinPool.
2. **`Thread.ofVirtual().name("worker-", 1).start(Runnable)`**:
   - **JVM Actions**: The `Thread.ofVirtual()` builder returns a fluent `VirtualThreadBuilder` instance. Calling `name("worker-", 1)` configures a naming sequence. For each virtual thread started by this builder, the JVM increments the sequence (e.g., `"worker-1"`, `"worker-2"`), which is useful for debugging thread dumps.
3. **`Thread.ofVirtual().unstarted(Runnable)`**:
   - **JVM Actions**: This builder instantiates the virtual thread object on the heap but does **not** call the native native start hooks. The thread state is initialized as `NEW`. This allows developers to prepare task wrappers, set fields, or pass the thread reference to other coordinators before calling `t.start()` to transition it to `RUNNABLE`.
4. **`Executors.newVirtualThreadPerTaskExecutor()`**:
   - **JVM Actions**: Unlike traditional fixed/cached pools that reuse a set number of threads, this executor does **not** pool threads. It returns a lightweight `ThreadPerTaskExecutor` object. Each call to `submit()` or `execute()` spawns a brand new, unpooled virtual thread.
   - **The AutoCloseable Try-With-Resources Block**: The executor implements `AutoCloseable`. Upon exiting the `try` block, the main thread calls `close()`, which internally calls `shutdown()` and blocks on `awaitTermination(...)`. This ensures the main thread does not exit before all spawned virtual tasks finish execution.

> [!IMPORTANT]
> **Virtual Threads are Daemon Threads**: All virtual threads are configured as daemon threads by default, and this cannot be modified. If the main application thread exits, the JVM terminates immediately, dropping any active virtual threads. You must block the main thread (using `.join()` or try-with-resources on `ExecutorService`) to ensure execution completes.

---

#### 5. Thread API Changes
- **New Methods**:
  - `Thread::isVirtual`: Returns `true` if the thread is virtual.
  - `Thread.sleep(Duration)` and `Thread::join(Duration)`: Support modern time-based parameterization.
  - `Thread::threadId`: Replaces the deprecated `getId()`.
- **ThreadGroup Constraints**: Virtual threads belong to a single, immutable, system-level `ThreadGroup` named `"VirtualThreads"`.
- **Immutable Priority & Daemon Flags**: Calling `setPriority(int)` or `setDaemon(boolean)` on a virtual thread does not change its status (it always runs at priority `5` and is always a daemon).

---

#### 6. Throughput and Scalability via Little's Law

Little's Law is a queuing theory formula stating that the average number of items in a stable system ($N$) is equal to the average throughput ($\lambda$) multiplied by the average latency ($d$):
$$N = \lambda \times d \quad \Longrightarrow \quad \lambda = \frac{N}{d}$$

- **Traditional Thread Limits**: In a platform-thread pool, $N$ is constrained by memory (typically 1,000 threads max). If latency ($d$) is 500ms, max throughput is:
  $$\lambda = \frac{1000}{0.5\text{s}} = 2000 \text{ requests/sec}$$
- **Virtual Thread Scaling**: With virtual threads, $N$ can scale to 1,000,000 threads. Even with the same 500ms latency, the theoretical throughput limit scales massively:
  $$\lambda = \frac{1000000}{0.5\text{s}} = 2,000,000 \text{ requests/sec}$$

---

#### 7. How Virtual Threads Work Under the Hood

The secret to virtual thread scalability lies in how the JVM manages execution stacks:

##### 1. Heap-Allocated Stack Frames
Unlike platform threads that use a continuous, fixed block of native memory, virtual thread execution stacks are stored as linked objects in the JVM garbage-collected heap.

##### 2. Carrier Pool Scheduling
The JVM schedules virtual threads on carrier platform threads using a specialized `ForkJoinPool` operating in FIFO async mode (default parallelism equal to the available processor cores, configurable via `-Djdk.virtualThreadScheduler.parallelism=N`).
- **LIFO vs FIFO**: Standard parallel streams use the common pool in LIFO (Last-In, First-Out) mode to preserve CPU cache affinity. The virtual thread scheduler uses FIFO to avoid starvation.
- **Lock-Free CAS Queues**: To prevent thread contention, worker queues avoid explicit lock synch. Instead, lock-free queues manage entries using Compare-And-Swap (CAS) atomic operations.

##### Deep Dive: Inside Loom's Work-Stealing Carrier Scheduler and RunQueue Mechanics

To understand how Project Loom schedules millions of concurrent virtual threads, you must analyze the internals of its customized `ForkJoinPool` carrier scheduler and how it manages queues at the hardware level.

###### 1. Scheduler Initialization and Carrier Thread Mapping
When the JVM boots, the Project Loom runtime initializes a dedicated `ForkJoinPool` for virtual thread execution (accessible via `VirtualThread.scheduler()`).
- **Parallelism Sizing**: By default, the pool constructs worker threads equal to the available processor cores:
  $$\text{Parallelism} = \text{Runtime.getRuntime().availableProcessors()}$$
- **Thread Factory**: The pool spawns platform threads named `ForkJoinPool-1-worker-N`. These are the **Carrier Threads** onto which virtual threads are mounted.
- **Custom Properties**: You can override the default scheduler bounds using JVM properties:
  - `-Djdk.virtualThreadScheduler.parallelism=N`: Overrides carrier core counts.
  - `-Djdk.virtualThreadScheduler.maxPoolSize=M`: Caps the maximum backup threads (default: 256).

###### 2. The Worker Scanning and Work-Stealing Internals
When a carrier thread finishes its active task, it invokes the internal method `ForkJoinPool.runWorker()`. This starts a loop that executes `scan()` to locate new virtual threads to run:

```
[Carrier Worker Loop]
         │
         ▼
[Check Local Deque (FIFO)] ──► Found? ──► [Mount and Execute Virtual Thread]
         │
         ├── NO
         ▼
[Scan Sibling Deques (FIFO Steal)] ──► Found? ──► [Steal, Mount and Execute]
         │
         ├── NO
         ▼
[Check Shared Submission Queues]   ──► Found? ──► [De-queue and Execute]
         │
         ├── NO
         ▼
[Park Worker Thread (Sleep State)]
```

1. **Local FIFO De-queue**:
   - The worker checks its own private `WorkQueue`.
   - In Loom's FIFO async mode, the worker pops the task from the **`base`** index of its deque (the oldest queued task). This differs from standard ForkJoinPool LIFO mode where the owner pops from `top`.
2. **Work-Stealing Sibling Scan**:
   - If the local queue is empty, the worker enters the work-stealing phase.
   - It selects a random sibling worker thread's queue and attempts to steal a task from its **`base`** index.
   - It performs this operation using Compare-And-Swap (CAS) to increment `base`. If successful, the task is stolen. If another thread wins the CAS check, the scan retries on a different sibling queue.
3. **Shared Queue Retrieval**:
   - If no tasks are available to steal, the worker scans the shared external submission queues (where incoming requests from non-pool threads are enqueued).
4. **Parking and Sleep**:
   - If all scans fail, the worker thread parks itself using `LockSupport.park()`, entering an idle sleep state until new tasks are submitted.

###### 3. Carrier Over-Provisioning: The Pinning Safety Valve
A major risk in Loom is **Carrier Pinning** (e.g., executing a blocking JNI native call or a synchronized block pre-JDK 24). During pinning, the virtual thread blocks, but cannot yield its continuation. This freezes the carrier platform thread, reducing the scheduler's active worker count.

To prevent this from deadlocking the application, the Loom scheduler implements **Carrier Over-Provisioning**:
- **Pinning Detection**: The JVM monitors carrier thread states. If a virtual thread blocks while pinned, the scheduler detects the drop in active cores.
- **Backup Thread Spawning**: The scheduler dynamically spawns a temporary backup platform thread to replace the pinned carrier. This keeps the execution pool active, allowing other virtual threads to continue running.
- **Pooling Boundaries**: The number of backup threads is capped by `jdk.virtualThreadScheduler.maxPoolSize` (default: 256).
- **Idle Pruning**: Once the pinning task completes and unblocks, the backup worker thread is kept alive for a keep-alive duration (default: 30 seconds, governed by `keepAliveTime`). If no new tasks arrive, the backup thread is terminated and pruned to conserve memory.

##### 3. Continuation Yielding
When a virtual thread blocks, it delegates to `LockSupport.park()`. The JVM redirects this call:
```java
public static void park() {
    if (Thread.currentThread().isVirtual()) {
        VirtualThreads.park(); // Invokes yieldContinuation()
    } else {
        U.park(false, 0L);     // Native OS park
    }
}
```
Loom executes a **continuation yield**, pausing the virtual thread. The stack frames are moved to the heap, and the carrier thread is freed to work on other tasks.

##### 4. Lazy Copying & Return Barriers
To optimize performance, Loom does not copy the entire call stack at once.
- **Lazy Stack Resuming**: When a virtual thread is remounted, only the top few frames of the stack are copied back to the carrier.
- **Return Barriers**: The JVM injects return barriers at the boundary of un-restored frames. When execution hits a barrier, the JVM copies the next set of frames from the heap to the stack, minimizing call stack overhead.

##### 5. OS Level Pollers
The JVM registers the blocked socket file descriptor with native pollers (`epoll` on Linux, `kqueue` on macOS, or `wepoll` on Windows). Once the OS signals that I/O data is ready, the poller notifies the JVM, which marks the virtual thread as runnable and schedules it back onto an available carrier thread.

---

#### 8. Implementing the JVM internal Continuation class
To understand how continuations yield and resume control, we can inspect Java's internal Continuation API. 

> [!WARNING]
> These internal APIs (`jdk.internal.vm.*`) are not public and may change in future Java releases. To run code accessing them, you must pass `--add-exports java.base/jdk.internal.vm=ALL-UNNAMED` to the compiler and JVM.

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

##### Deep Mechanics: Inside the JVM `Continuation` Execution Lifecycle
1. **The Continuation Scope (`ContinuationScope`)**:
   - A `ContinuationScope` acts as a namespace grouping related execution flows. Continuations running in the same scope can be scheduled together, and yields can search for matching parent scopes to yield control to specific stack heights.
2. **First Invocation (`continuation.run()`)**:
   - Calling `run()` transitions the continuation to the active state. The JVM switches execution context to the continuation's runnable body.
   - Stack frame blocks are mounted, and the JVM executes instruction blocks until it encounters the static call to `Continuation.yield(scope)`.
3. **The Yield Mechanism (`yield()`)**:
   - When `yield()` is called, the JVM captures the program counter, registers, and active stack frames (containing local parameters and nested calls).
   - The stack frames are moved to the GC heap. The continuation suspends execution.
   - The execution returns back to the caller thread at the line immediately following the `run()` invocation.
4. **Resumption and Completion**:
   - Subsequent calls to `run()` copy the stack frames from the heap back onto the active thread stack, using lazy copying optimizations to restore only the required execution state.
   - Execution resumes exactly from the instruction point following the matching `yield()` call.
   - Once the runnable block finishes, the continuation enters the `DONE` state. Calling `run()` on a completed continuation throws a `NullPointerException` or `IllegalStateException`.
```

##### Output
```text
Main: Running first time...
Line 1: Hello from continuation!
Main: Running second time...
Line 2: Resumed continuation!
Main: Running third time...
Line 3: Finished execution!
```

---

#### 9. Simplifying Async Aggregation
Traditional concurrency requires complex callback chains or reactive pipelines to run parallel tasks. With virtual threads, blocking methods like `Future.get()` are cheap. We can write clean, sequential-looking code that executes concurrently:

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

##### Architectural Mechanics: Async Aggregation Execution Walk
1. **Parallel Task Dispatching (`invokeAll()`)**:
   - `invokeAll()` accepts a collection of `Callable` tasks, submits them to the virtual executor, and blocks the calling virtual thread until all tasks complete. Under the hood, this spawns two separate virtual threads: one for `fetchAdjective` and one for `fetchNoun`.
2. **Intelligent Yielding via Thread Sleep**:
   - When `Thread.sleep(200)` is called inside a virtual thread, the JVM intercepts the call. Instead of blocking the native carrier thread, Loom performs a continuation yield. The virtual thread's stack frames are copied to the heap, and the carrier thread is freed to process other tasks.
   - The JVM registers a wake-up timer with the OS pollers. Once 200ms expires, the JVM marks the virtual thread as runnable, rescheduling it on an available carrier thread.
3. **Cheap Value Resolution (`get()`)**:
   - Calling `.get()` on the futures resolves the output. Since `invokeAll()` already blocked until completion, these calls return immediately. If the tasks were still executing, calling `.get()` would pause the calling virtual thread and yield its carrier thread without consuming CPU cycles.
```

---

#### 10. Structured Concurrency Teaser
To coordinate concurrent subtasks, Java introduces the `StructuredTaskScope` API (preview feature). It links the lifetime of subtasks to the parent scope block. If a subtask fails, all other subtasks in the scope are automatically cancelled, preventing thread leaks:

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

##### Deep Execution Mechanics: Structured Containment & Exception Propagation
1. **Spawning Containment Subtasks (`scope.fork()`)**:
   - Calling `scope.fork(Callable)` instantiates a new virtual thread, mapping its lifecycle to the parent `StructuredTaskScope`. This creates a hierarchical relationship where subtasks are nested under the parent scope.
2. **Coordinated Blocking (`scope.join()`)**:
   - `scope.join()` suspends the parent virtual thread. It yields execution, unmounting from its carrier thread until all child subtasks complete or fail.
3. **Failure Propagation and Cancellation (`throwIfFailed()`)**:
   - If any subtask throws an exception, the `ShutdownOnFailure` policy triggers, automatically cancelling all remaining active subtasks in the scope.
   - Calling `throwIfFailed()` checks if a failure occurred. If so, it wraps the exception and throws it, preventing orphaned background threads from wasting CPU resources.
```

---

#### 11. Rate Limiting with Semaphores
Because virtual threads are cheap, **we do not pool them**. Pooling virtual threads is an anti-pattern. Instead, to limit concurrent access to databases or downstream services, use a **Semaphore**.

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

##### Deep Execution Mechanics: Semaphore Permit Throttling & HTTP Client Execution
1. **Strict FIFO Rate Limiting**:
   - Spawning millions of virtual threads to fetch data concurrently will overwhelm external servers.
   - The `Semaphore` controls access by maintaining a counter of available permits. When a thread calls `acquire()`, it decrements the counter. If the counter is 0, the thread blocks and yields its carrier thread until another thread releases a permit.
2. **Safe Acquire Pattern**:
   - Calling `acquire()` before the `try` block is essential. If `acquire()` throws an `InterruptedException` and is written inside the `try` block, execution jumps to the `finally` block and runs `release()`. This increases the permit count without having acquired one, corrupting the semaphore limits.
3. **HTTP Client Integration**:
   - The `HttpClient` is configured to run on a virtual-thread-per-task executor. The call to `client.send()` is blocking but lightweight, allowing the thread to unmount from its carrier thread while waiting for the network response.

---

#### 12. Pinning (The Biggest Loom Enemy)
**Pinning** occurs when a virtual thread cannot unmount from its carrier platform thread. While pinned, the virtual thread locks the carrier thread to the OS core. If the virtual thread blocking on I/O is pinned, the underlying carrier thread is also blocked, wasting resources.

##### Causes of Pinning
1. **Synchronized Blocks/Methods (Pre-JDK 24)**: If a virtual thread acquires an object monitor (`synchronized`), it cannot yield and unmount.
2. **Native Code / Foreign Function Interface (FFI)**: Native functions execute outside the control of the JVM scheduler, pinning the carrier.

##### Synchronized Block Mitigation
To resolve pinning in synchronized blocks, replace them with `ReentrantLock`:

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

##### JEP 491 (JDK 24 updates)
JDK 24 introduced **JEP 491 (Alternative Monitor Implementations)**, which refactored monitor locks inside the JVM. This allows virtual threads to yield and unmount even when blocked inside `synchronized` blocks. However, native JNI pinning remains unavoidable and must be mitigated by keeping native calls short and non-blocking.

---

#### 13. The ThreadLocal Conundrum
Platform thread pools are small, making `ThreadLocal` variables safe. However, virtual threads are designed to run in the millions. If each virtual thread stores an instance of a class in a `ThreadLocal`, you will run out of memory.

##### Memory Bloat Demo
If 1,000,000 concurrent virtual threads each store a 500 KB object in a `ThreadLocal`, this consumes **500 GiB** of heap space:
$$\text{Memory} = 1,000,000 \times 500 \text{ KB} = 500 \text{ GiB}$$

##### The Solution
1. Avoid `ThreadLocal` variables in virtual threads.
2. Pass context explicitly through method arguments.
3. Migrate to **Scoped Values** (Module 5), which allow immutable, lightweight context propagation across execution threads.

---

#### 14. Monitoring & Diagnostics

##### JVM System Flags
- `-Djdk.traceVirtualThreadLocals`: Prints a stack trace whenever a virtual thread reads or writes a `ThreadLocal` variable.
- `-Djdk.tracePinnedThreads=full` or `-Djdk.tracePinnedThreads=short`: Prints stack traces to standard output when a virtual thread blocks while pinned.

##### Java Flight Recorder (JFR) Events
You can capture these events to profile virtual threads:
- `jdk.VirtualThreadStart` & `jdk.VirtualThreadEnd`: Track thread creation and teardown.
- `jdk.VirtualThreadPinned`: Triggers when a virtual thread blocks while pinned (default threshold: 20ms).
- `jdk.VirtualThreadSubmitFailed`: Logs scheduling pool allocation failures.

##### JSON Thread Dumps
Generate dumps containing suspended virtual threads:
```bash
jcmd <PID> Thread.dump_to_file -format=json thread_dump.json
```
JSON thread dumps are lightweight because they exclude object addresses, heap details, and native JNI pointers, focusing on thread execution stack frames.

##### Programmatic MXBean Access
You can capture thread dumps programmatically inside your Java application:
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

#### 15. Migration Tips
1. **Update Library Dependencies**: Prioritize updating JDBC drivers, HTTP client wrappers, and logging dependencies to modern versions to avoid pinning.
2. **Do Not Pool Virtual Threads**: Replace fixed and cached thread executors with `Executors.newVirtualThreadPerTaskExecutor()`.
3. **Use Semaphores for Throttling**: Protect downstream databases and APIs by restricting virtual thread concurrency using semaphores.
4. **Isolate Legacy Blocking Blocks**: If you must use a library that causes pinning (e.g., JNI blocks), isolate those executions inside dedicated platform-thread pools.


---

#### 16. ForkJoinPool Work-Stealing Internals & Queue Sizing

To fully optimize applications running millions of virtual threads, we must master how the JVM schedules virtual threads onto physical CPU cores. Virtual threads are scheduled using a dedicated `java.util.concurrent.ForkJoinPool` instance.

##### FIFO Async Mode: The Fairness Engine
The common `ForkJoinPool` (used by Parallel Streams) operates in **Last-In, First-Out (LIFO)** mode to maximize CPU cache affinity for recursive divide-and-conquer tasks. 
However, the virtual thread scheduler runs in **First-In, First-Out (FIFO) async mode**. Because virtual threads represent independent asynchronous requests (such as separate HTTP transactions), FIFO ordering ensures processing fairness and prevents older tasks from starving at the back of the queues.

##### Work-Stealing Algorithm Mechanics
The scheduler maintains a pool of platform worker threads (carrier threads), matching the number of available CPU cores by default.
1. **Local Deques**: Each carrier thread has a private, double-ended task queue (deque) of runnable virtual threads.
2. **Global Queue**: The scheduler maintains a shared global queue for external tasks submitted from non-carrier threads (e.g., netty loops or main thread).
3. **The Stealing Loop**:
   - When a carrier thread finishes its current task, it pops the next task from the *head* of its local queue (FIFO).
   - If its local queue is empty, the carrier thread scans the queues of other carrier threads.
   - It attempts to steal a task from the *tail* of a sibling carrier thread's queue. Stealing from the tail minimizes thread contention, as the owner thread is operating at the head.
   - If all local queues are empty, the carrier thread checks the shared global queue. If that is also empty, the carrier thread parks itself until a new task is submitted.

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

##### Carrier Pool Over-Provisioning & Backup Threads
A critical problem arises when a virtual thread performs an operation that blocks the carrier thread itself, preventing it from yielding. This is called **pinning** (caused by synchronized blocks or JNI calls) or **native blocking** (like file system writes on operating systems that lack non-blocking file I/O).

To prevent this from starving other ready virtual threads, the JVM scheduler implements a **carrier thread over-provisioning** mechanism:
- When a carrier thread enters a blocking native OS call or a file read, it notifies the scheduler (often via the internal `ManagedBlocker` mechanism).
- The scheduler detects that a carrier thread is about to block and temporarily spawns or activates a **backup carrier thread** from its spare reserve.
- This maintains the target parallelism level (e.g., 4 active carrier threads running on a 4-core machine) even if some carrier threads are physically blocked.
- **The Risk**: If thousands of virtual threads concurrently execute pinned synchronized blocks or native I/O, the scheduler will repeatedly spawn backup carrier threads. This leads to **thread explosion**, creating thousands of native OS threads, triggering high kernel context-switching overhead, memory starvation, and eventually crashing the JVM.

##### Programmatic Carrier Expansion via `ManagedBlocker`
To allow custom blocking operations to participate in this scheduler-managed pool expansion without starving the CPU, developers can wrap blocking tasks inside the `ForkJoinPool.ManagedBlocker` interface. This signals the ForkJoinPool to spawn a backup thread if needed.

Below is a complete class demonstrating how to implement a custom `ManagedBlocker` to safely run blocking computations on virtual threads:

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

##### Line-by-Line Logic Walkthrough: `ManagedBlockerDemo`

1. **`ForkJoinPool.ManagedBlocker` Implementation**:
   - At line 14, the class `SecureResourceBlocker` implements `ForkJoinPool.ManagedBlocker`. This interface requires two methods: `block()` and `isReleasable()`.
   - The `block()` method contains the actual blocking computation or sleep (line 24).
   - The `isReleasable()` method (line 30) returns `true` if the blocking operation has completed, notifying the pool that the thread can resume scheduling tasks.

2. **Scheduler Notification (`ForkJoinPool.managedBlock`)**:
   - At line 40, `ForkJoinPool.managedBlock(blocker)` is invoked.
   - If the calling thread is a worker thread of a ForkJoinPool, the pool intercepts this call.
   - The pool inspects its state: if there are no other active threads, it allocates and starts a new backup carrier thread.
   - The pool then calls `blocker.block()`. The current thread blocks, but the new backup carrier thread takes over, executing other tasks in the queue.
   - This prevents pool starvation and ensures the application maintains its configured parallelism.

---

### Hands-On Labs

#### Lab 2.1 — Virtual Thread Creation Styles
**Objective**: Implement all four virtual thread creation methods, demonstrate that virtual threads are daemon threads, and resolve premature termination using `.join()`.

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
**Objective**: Implement a benchmarking class (`LittleLawExample`) that simulates 10,000 I/O-bound tasks, each introducing 500ms of simulated latency. Compare execution times and throughput between virtual threads and platform thread pools of sizes 100, 500, and 1,000.

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
**Objective**: Write a pinning demo using a synchronized block with blocking sleep. Show that the virtual thread is pinned. Then, rewrite it using `ReentrantLock` to show how the virtual thread changes carrier threads upon yielding.

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

##### Deep Execution Mechanics: Thread Pinning and Lock Reparation
1. **The Synchronized Monitored Pinned Trap (`ThreadPinnedExample`)**:
   - When entering a `synchronized` block, the virtual thread acquires the object monitor (`lock`).
   - Under the hood, monitor entry operations are managed by JVM C++ code. Because the thread holds an active object monitor, the continuation scheduler cannot yield. If the virtual thread calls `Thread.sleep(100)` (which maps to blocking I/O), the carrier thread is forced to block sequentially.
   - Other virtual threads waiting in the queue cannot run because the carrier thread is blocked, defeating Loom's scalability.
2. **Mitigation via ReentrantLock (`PreventPinningExample`)**:
   - Unlike `synchronized` blocks that utilize internal monitor queues, `ReentrantLock` coordinates lock acquisition in user-space using `AbstractQueuedSynchronizer` (AQS).
   - When a virtual thread calls `lock.lock()`, it attempts to acquire a permit. If it succeeds, it proceeds.
   - When it calls `Thread.sleep(100)`, the JVM intercepts the sleep call, unmounts the virtual thread, and frees the carrier thread.
   - If other threads call `lock.lock()`, they fail to acquire the lock and are parked. Since parking inside `ReentrantLock` is blocking-tolerant, those threads yield their carriers, allowing the carrier threads to run other virtual threads.
3. **Trace Verification**:
   - Using the JVM flag `-Djdk.tracePinnedThreads=short` prints stack traces when pinning occurs, listing the exact synchronized monitor boundaries.
   - In the corrected output, noticing the carrier name change from `worker-1` before sleep to `worker-3` after sleep proves that the thread successfully unmounted and remounted onto a different carrier, verifying pinning mitigation.


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
*Note that in `PreventPinningExample`, the carrier worker thread shifts from `worker-1` to `worker-3`, proving that the virtual thread successfully unmounted and remounted.*

---

#### Lab 2.4 / Pitfall — Semaphore Release Leak
**Objective**: Verify the semaphore permit corruption pitfall. Show that if `acquire()` is wrapped inside the same try block as the rest of the business logic, permit leakage occurs on interruption. Write a secure acquire-before-try implementation.

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

##### Line-by-Line Analysis: Semaphore Leakage & Recovery Mechanics
1. **Broken Pattern Analysis**:
   - Inside the broken block, `brokenSemaphore.acquire()` is called within the `try` block.
   - If the thread is interrupted, `acquire()` throws an `InterruptedException`.
   - The thread jumps to the `finally` block and runs `brokenSemaphore.release()`.
   - Because no permit was actually acquired (the acquisition failed with an exception), calling `release()` increments the permit counter, corrupting the semaphore limits. Under high load, this causes permit inflation, allowing more concurrent threads to access the resource than allowed.
2. **Correct Pattern Analysis**:
   - Inside the safe block, `safeSemaphore.acquire()` is called **outside** the try-finally block.
   - If an `InterruptedException` occurs, the exception is caught, the thread sets its interrupt flag, and exits without executing the `finally` block, preventing permit corruption.
   - If `acquire()` completes successfully, the thread enters the `try` block, ensuring `release()` is executed exactly once to return the permit.
```

---

#### Lab 2.5 — Custom NanoThread Continuation Runner
**Objective**: Simulate how virtual threads mount, yield, and swap carrier threads during I/O operations using Java's internal `Continuation` class. Build a custom executor scheduler framework (`NanoThreadScheduler`) and verify carrier thread switching programmatically.

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
*Note that File_1 started execution on carrier `worker-2`, but after yielding for simulated network I/O, it resumed and finished executing on carrier `worker-1`. This is exactly how the JVM multiplexes virtual threads onto underlying platform threads.*

##### Step-by-Step Logic Walk: User-Space Continuation Scheduler Simulation
1. **Continuation Mounting (`NanoThread.run()`)**:
   - Spawning `NanoThread.start()` calls the scheduler's `schedule()` method.
   - The scheduler submits the task to a 2-thread Work-Stealing carrier pool (`carrierPool`).
   - The worker thread sets the thread-local context `CURRENT_NANO_THREAD` and calls `continuation.run()`. This mounts the user-space task on the carrier thread and executes it until a yield point.
2. **Simulating Async OS I/O Off-loading**:
   - Inside `FileTransfer.transfer()`, the thread initiates work and calls `IO_NOTIFIER.schedule()`, simulating background OS file transfer.
   - It registers a wake-up callback to reschedule the thread once I/O completes.
3. **Unmounting and Yielding (`Continuation.yield()`)**:
   - The worker thread clears the thread-local context and calls `Continuation.yield(NanoThread.SCOPE)`.
   - The JVM pauses the task, saves its stack frames, and returns control to the carrier thread. The carrier thread exits the execution block, becoming free to run other tasks.
4. **Rescheduling and Context Switching**:
   - Once the scheduled I/O completes, `IO_NOTIFIER` triggers the callback, submitting the task back to `carrierPool`.
   - An available carrier thread picks up the task, restores the stack frames, and resumes execution exactly where it was yielded. The print statements show that tasks can start on one carrier worker and finish on another, demonstrating Loom's thread multiplexing.

---

### Common Pitfalls & Anti-Patterns

#### 1. Running CPU-Bound Operations in Virtual Threads
Virtual threads do not make CPU-bound processing (e.g., cryptographic hashing, image processing, matrix computations) faster. CPU-bound tasks require constant thread attachment to CPU cores. Since they cannot yield on I/O, virtual threads running CPU-bound code behave like platform threads, but introduce extra scheduling overhead.

#### 2. Pooling Virtual Threads
Traditional thread pools save the overhead of starting expensive platform threads. Virtual threads are cheap to create. Do not pool them. Create a new virtual thread for each concurrent task and discard it when finished. Pooling virtual threads is an anti-pattern that restricts concurrency.

#### 3. The ThreadLocal Memory Leak Hazard

A critical mistake when adopting virtual threads is retaining intensive, high-allocation `ThreadLocal` usage patterns. Because virtual threads are designed to be disposable (constructed per task and discarded), developers often overlook the lifecycle of thread-local maps.

##### Leak Scenario Code

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

##### Deep Architectural & Memory Analysis of the Leak

1. **Heap Allocation Dynamics**:
   - In a traditional platform thread model, the thread pool size is small (e.g., 200 threads). Even if you leak a 1 MB buffer on each thread by not calling `.remove()`, the total leaked footprint is capped at `200 threads * 1 MB = 200 MB`.
   - In the virtual thread model, we spawn 100,000 threads. Because we omit `requestContext.remove()`, each virtual thread keeps a strong reference to its 1 MB payload inside its internal `ThreadLocalMap`.
   - While virtual threads are cheap, they only get garbage collected once they exit *and* all references to them are cleared. However, if a thread remains referenced (e.g., waiting in a completion queue or pinned elsewhere), or if the sheer volume of active concurrent virtual threads holding 1 MB payloads occurs simultaneously, the JVM heap is instantly exhausted, throwing `OutOfMemoryError: Java heap space`.

2. **Garbage Collection Root Pins**:
   - The JVM's GC traces references starting from active stack frames and thread objects (GC Roots).
   - If a virtual thread is suspended (parked on I/O) while holding a thread-local value, the thread object remains an active GC root.
   - The `ThreadLocalMap` entry contains a weak reference to the `ThreadLocal` key, but a **strong reference** to the value (`byte[]` payload). This means the 1 MB payload cannot be collected as long as the virtual thread is alive, causing memory bloat during long-running socket suspensions.

3. **Remediation**:
   - **Explicit Cleanup**: Always invoke `ThreadLocal.remove()` in a `finally` block to clear the thread's reference map.
   - **Adopt Scoped Values**: Transition away from `ThreadLocal` to `ScopedValue`. Scoped values do not store values in a mutable map per thread; instead, they bind values to the execution scope stack. When the scope block exits, the binding is automatically discarded, eliminating the risk of memory leaks.

---

### Summary
1. **Thread Types**: Platform threads map 1-to-1 to kernel threads, using 1-2 MiB of off-heap stack memory. Virtual threads map M-to-N to carrier platform threads, using heap memory.
2. **Mounting Mechanics**: The JVM mounts virtual threads onto carrier threads using a FIFO async `ForkJoinPool`. Virtual threads yield control and unmount during blocking I/O calls.
3. **Pinning Constraints**: Synchronized blocks (pre-JDK 24) and native method boundaries lock virtual threads to their carrier threads. Use `ReentrantLock` to prevent pinning.
4. **ThreadLocal Danger**: High virtual thread counts make `ThreadLocal` variables a memory risk. Use `ScopedValue` to pass context safely.
5. **Monitoring Tools**: Profile virtual threads using system flags like `-Djdk.tracePinnedThreads`, JFR metrics, and JSON thread dumps.

---

### Knowledge Check - Deep Dive Scenarios

#### Question 1: CPU-Bound Overhead
An application team migrates an image transcoding worker queue from a pool of 32 platform threads to a virtual thread-per-task executor. The transcoding code performs mathematical pixel modifications in memory. During load testing, execution times increase and carrier thread pools experience lockups. What explains this result?
- A. The virtual threads were blocked on network I/O, triggering garbage collection.
- B. The transcoding logic is CPU-bound and does not yield. This blocks the carrier threads, while virtual thread scheduling introduces extra management overhead.
- C. The JVM automatically limits CPU-bound virtual threads to a priority of 1.
- D. Image transcoding triggers carrier pinning.

*Answer*: **B**
*Explanation*: CPU-bound tasks do not perform blocking I/O and cannot yield their carrier threads. Running these tasks on virtual threads blocks the carrier pool, and the JVM scheduler introduces overhead without providing concurrency benefits.

#### Question 2: Memory Footprint under Little's Law
An API gateway receives requests and makes a downstream HTTP call with a latency ($d$) of 200ms. If we want to achieve a throughput ($\lambda$) of 50,000 requests per second, how many concurrent virtual threads ($N$) must the JVM support, and what is the approximate heap stack footprint if each virtual thread requires 1KB of heap memory?
- A. $N = 1,000$ threads, consuming 1MB of heap space.
- B. $N = 10,000$ threads, consuming 10MB of heap space.
- C. $N = 100,000$ threads, consuming 100MB of heap space.
- D. $N = 1,000,000$ threads, consuming 1GB of heap space.

*Answer*: **B**
*Explanation*: According to Little's Law:
$$N = \lambda \times d = 50,000 \times 0.2\text{s} = 10,000\text{ concurrent threads}$$
At 1KB per thread stack, the memory footprint is:
$$10,000 \times 1\text{KB} = 10\text{MB of heap space}$$

#### Question 3: Carrier Thread Pinning and Lock Invalidation
A developer runs a performance test on a virtual-thread-based service. The logs print a JFR event warning: `jdk.VirtualThreadPinned`. Which Java keyword or construct is the primary source of carrier thread pinning?
- A. `volatile`
- B. `synchronized` blocks wrapping blocking I/O calls (pre-JDK 24)
- C. `ReentrantLock`
- D. `ThreadLocal`

*Answer*: **B**
*Explanation*: Entering a `synchronized` block acquires an object monitor. If the thread blocks while holding this monitor (pre-JDK 24), the JVM cannot unmount it, pinning the virtual thread to its carrier thread.

#### Question 4: JEP 491 Monitor Changes in JDK 24
How does JEP 491 (finalized in JDK 24) change the behavior of virtual threads inside `synchronized` blocks?
- A. It deprecates the `synchronized` keyword.
- B. It updates the JVM scheduler to yield and unmount virtual threads even when blocking inside `synchronized` blocks, preventing carrier thread pinning.
- C. It converts all synchronized blocks into ReentrantLocks.
- D. It limits virtual threads to platform threads when monitor locks are encountered.

*Answer*: **B**
*Explanation*: JEP 491 refactors JVM monitor locking to allow virtual threads to yield and unmount while holding monitors, eliminating pinning in synchronized blocks.

#### Question 5: Thread Group Constraints
A developer attempts to create a virtual thread and assign it to a custom `ThreadGroup` to manage its lifecycle. What occurs?
- A. The virtual thread is successfully added to the custom thread group.
- B. The virtual thread is created but is assigned to the immutable, system-wide `"VirtualThreads"` group, and the custom group setting is ignored.
- C. The JVM throws an `IllegalThreadStateException` at runtime.
- D. The compiler rejects the code.

*Answer*: **B**
*Explanation*: Virtual threads belong to a single, immutable thread group called `"VirtualThreads"`. Any builder or constructor configurations attempting to assign them to another group are ignored.

#### Question 6: Daemon Thread Termination
Why does an application containing only active virtual threads exit immediately when the main thread terminates?
- A. Virtual threads are marked as daemon threads by default, and this status cannot be changed. The JVM exits when only daemon threads remain active.
- B. The virtual threads are garbage collected.
- C. The ForkJoinPool carrier pool scheduler terminates.
- D. Virtual threads do not support background processing.

*Answer*: **A**
*Explanation*: Virtual threads are daemon threads by default. The JVM exits when the only remaining active threads are daemon threads. To prevent premature termination, you must block the main thread using `.join()` or try-with-resources.

#### Question 7: Semaphore Permit Leaks
A service layer throttle uses a `Semaphore`. If the call `semaphore.acquire()` is placed inside a `try` block that has a `finally` block containing `semaphore.release()`, what error occurs if the thread is interrupted?
- A. The thread deadlock blocks.
- B. The permit count is corrupted because `release()` is called even if `acquire()` failed and threw an exception, releasing a permit the thread never held.
- C. The JVM throws an `IllegalMonitorStateException`.
- D. The semaphore is garbage collected.

*Answer*: **B**
*Explanation*: Placing `acquire()` inside the `try` block causes the thread to jump to the `finally` block if interrupted, releasing a permit it never held. `acquire()` must be called before the `try` block.

#### Question 8: FIFO Async ForkJoinPool Scheduling
Why does the virtual thread scheduler run its ForkJoinPool in FIFO async mode rather than LIFO mode?
- A. FIFO mode is required to access native OS network pollers.
- B. FIFO mode prevents task starvation by processing requests in their order of submission.
- C. LIFO mode does not support work-stealing.
- D. FIFO mode prevents carrier thread pinning.

*Answer*: **B**
*Explanation*: The virtual thread scheduler uses FIFO mode to process tasks in the order of submission, preventing starvation in transactional workloads.

#### Question 9: Memory Calculations for Thread-Local Bloat
If 1,000,000 concurrent virtual threads are spawned, and each thread allocates a `ThreadLocal` variable containing a 256KB buffer, what is the total memory footprint of these buffers on the JVM heap?
- A. 256MB
- B. 2.56GB
- C. 256GB
- D. 2.56TB

*Answer*: **C**
*Explanation*: The calculation is:
$$1,000,000 \times 256\text{KB} = 256,000,000\text{KB} \approx 256\text{GB of heap memory}$$
This demonstrates why using thread-local variables in virtual threads can lead to memory bloat.

#### Question 10: JVM Flag for ThreadLocal Diagnostics
Which JVM system flag should you enable during profiling to detect thread-local variables in virtual threads?
- A. `-Djdk.tracePinnedThreads=full`
- B. `-Djdk.traceVirtualThreadLocals`
- C. `-XX:StartFlightRecording`
- D. `-Dspring.threads.virtual.enabled=true`

*Answer*: **B**
*Explanation*: The flag `-Djdk.traceVirtualThreadLocals` prints a stack trace whenever a virtual thread reads or writes a `ThreadLocal` variable, helping developers locate memory risk areas.

#### Question 11: OS Thread Scheduler vs JVM Virtual Thread Scheduler
How does the operating system thread scheduler differ from the JVM's virtual thread scheduler in terms of execution control?
- A. The OS scheduler uses cooperative multitasking, while the JVM uses preemptive timeslicing.
- B. The OS scheduler uses preemptive timeslicing (forcing threads to yield CPU cycles at regular intervals), whereas the JVM's virtual thread scheduler relies on cooperative scheduling (continuations only yield when blocking on I/O or synchronized locks).
- C. The JVM scheduler uses physical CPU register swapping.
- D. None of the above.

*Answer*: **B**
- *Explanation*: OS schedulers use preemptive scheduling to slice CPU time among platform threads. The JVM schedules virtual threads cooperatively: a virtual thread runs on its carrier thread continuously until it hits a blocking point (like sleep, socket read, or lock acquisition), at which point it yields control. If a virtual thread runs a long CPU loop without blocking, it can hog the carrier thread indefinitely.

#### Question 12: Virtual Thread Priority Mapping
What is the outcome of invoking `Thread.currentThread().setPriority(Thread.MAX_PRIORITY)` from inside an active virtual thread?
- A. The virtual thread is prioritized by the ForkJoinPool scheduler.
- B. The call is accepted but ignored by the JVM; the priority of a virtual thread is fixed at `Thread.NORM_PRIORITY` (5) and has no effect on carrier scheduling.
- C. The JVM throws an `UnsupportedOperationException`.
- D. The priority is delegated to the OS kernel.

*Answer*: **B**
- *Explanation*: Virtual threads do not support priority scheduling. The JVM scheduler treats all virtual threads equally with a priority of 5. Calling `setPriority()` changes the value returned by `getPriority()` but has no effect on scheduling behavior.

#### Question 13: Volatile Memory Visibility Across Carrier Context Shifts
If a virtual thread writes to a non-volatile variable on carrier thread A, yields due to database I/O, and is rescheduled onto carrier thread B, what guarantees that carrier thread B sees the write?
- A) The volatile happens-before memory fence.
- B) The happens-before relationship enforced by the JVM scheduler: unmounting a virtual thread generates a release barrier, and remounting it generates an acquire barrier, ensuring full memory visibility of heap stack frames across carrier switches.
- C) The CPU cache is flushed to disk.
- D) There is no guarantee, causing race conditions.

*Answer*: **B**
- *Explanation*: The Loom framework guarantees that all stack memory changes are visible when a virtual thread is rescheduled. The unmounting phase acts as a memory release barrier, and the remounting phase acts as an acquire barrier, establishing a happens-before relationship between the state before yielding and the state after resuming.

#### Question 14: ReentrantLock AQS Parking vs synchronized blocks
Why does a virtual thread that blocks on a `ReentrantLock` unmount successfully, while blocking on a `synchronized` block (pre-JDK 24) pins the carrier thread?
- A. `ReentrantLock` uses native OS kernel locks.
- B. `ReentrantLock` is written in Java and uses AQS, which delegates parking to `LockSupport.park()`. The JVM intercepts this call to yield the continuation. In contrast, `synchronized` uses native C++ ObjectMonitor locks, which are coupled to the physical platform thread stack frame.
- C. `synchronized` is a deprecated keyword.
- D. None of the above.

*Answer*: **B**
- *Explanation*: `ReentrantLock` is implemented in Java and blocks by calling `LockSupport.park()`. The JVM intercepts this call, yields the continuation, and frees the carrier thread. `synchronized` blocks (pre-JDK 24) use native JVM monitor locks that link the monitor directly to the carrier thread's stack, preventing unmounting.

#### Question 15: Thread.join() Redirect Rules for Virtual Threads
When a platform thread invokes `join()` on a virtual thread, what is the internal JVM behavior?
- A. The platform thread blocks its native OS thread.
- B. The platform thread yields its continuation.
- C. The platform thread is parked using `LockSupport.park()`. Since it is a platform thread, it blocks the native thread; once the virtual thread exits and is garbage collected, the platform thread is unparked.
- D. The JVM crashes.

*Answer*: **C**
- *Explanation*: Joining a thread blocks the caller. If a platform thread calls `join()`, it blocks its native OS thread. If a virtual thread calls `join()`, it yields its continuation, allowing the carrier thread to run other virtual threads.

#### Question 16: ThreadGroup Name Mapping
All virtual threads are mapped to a single, system-level thread group. What is the name of this group, and what is its status?
- A. `"LoomPool"`, mutable.
- B. `"VirtualThreads"`, immutable.
- C. `"SystemGroup"`, mutable.
- D. `"CarrierGroup"`, immutable.

*Answer*: **B**
- *Explanation*: Virtual threads belong to a single system-wide `ThreadGroup` named `"VirtualThreads"`. This group is immutable and cannot be configured or overridden.

#### Question 17: Carrier Thread Pinning Mitigation in JDK 24
What JVM change in JEP 491 (JDK 24/25) mitigates pinning when encountering synchronized blocks?
- A) It removes the `synchronized` keyword.
- B) It refactors the JVM scheduler to yield and unmount virtual threads even when blocking inside `synchronized` blocks, resolving carrier thread pinning issues.
- C) It converts all monitors to spinlocks.
- D) It redirects monitors to off-heap maps.

*Answer*: **B**
- *Explanation*: JEP 491 refactors JVM monitor locking, allowing virtual threads to yield and unmount while holding monitors, eliminating pinning in synchronized blocks.

#### Question 18: VirtualThread MXBean Access
Why do standard JMX tooling metrics (like `ThreadMXBean.getThreadCount()`) return low counts even if there are 1,000,000 active virtual threads running inside the JVM?
- A) JMX is disabled when virtual threads are active.
- B) The standard `ThreadMXBean` only tracks platform threads. To query virtual threads, you must use proprietary HotSpot APIs (like `HotSpotDiagnosticMXBean`) or parse JSON thread dumps.
- C) Virtual threads are not registered in the JVM.
- D) None of the above.

*Answer*: **B**
- *Explanation*: The `ThreadMXBean` API is designed for platform threads. Because virtual threads are heap objects, they are excluded from the standard thread count to prevent breaking legacy monitoring systems. To monitor virtual threads, you must use JFR metrics or `HotSpotDiagnosticMXBean.dumpThreads`.

#### Question 19: Sleep Durations under Virtual Thread Scheduler
When a virtual thread executes `Thread.sleep(Duration.ofMillis(100))`, does it consume carrier thread execution time during the sleep?
- A. Yes, the carrier thread is blocked for 100ms.
- B. No, the virtual thread yields its continuation, frees the carrier thread, and is rescheduled only after the timer expires.
- C. Yes, but only if the carrier pool is full.
- D. None of the above.

*Answer*: **B**
- *Explanation*: Sleep is blocking-tolerant. When a virtual thread calls sleep, it yields its continuation, freeing the carrier thread to run other tasks. A scheduled executor wakes the virtual thread after the duration expires.

#### Question 20: JFR Event VirtualThreadStart Properties
What metadata attributes are captured by the `jdk.VirtualThreadStart` JFR event?
- A. The name of the database driver.
- B. The virtual thread's ID, name, and the Java thread ID of the carrier thread executing it.
- C. The heap memory usage percentage.
- D. The CPU temperature.

*Answer*: **B**
- *Explanation*: The `VirtualThreadStart` event records virtual thread creation. It captures the thread's ID, name, and carrier thread ID, helping developers trace thread relationships in profiling reports.


---

### 15. Loom Diagnostics: Reading and Understanding Thread Dumps in the Virtual Thread Era

When a traditional Java application hangs, developers generate a thread dump (using `jstack` or `kill -3`) to see what each thread is doing. Traditional thread dumps list every thread with its name, OS thread ID, and stack trace.

However, if you spawn **100,000 virtual threads**, a traditional text-based thread dump would be completely unreadable, spanning millions of lines and freezing the monitoring tools.

To solve this, Project Loom introduces a new **JSON-based thread dump format** and updates diagnostic commands to handle massive thread scales safely.

#### How to Generate a Virtual Thread Dump
Traditional `jstack` does **not** include virtual threads. To generate a dump that includes them, you must use the `jcmd` utility:

```bash
# 1. Find your Java process ID (PID)
jps

# 2. Generate a JSON-formatted thread dump including virtual threads
jcmd <PID> Thread.dump_to_file -format=json thread_dump.json
```

This command runs in user-space and streams the output directly to a file in JSON format, preventing terminal lock-up.

#### Inside the JSON Thread Dump Format
Open the generated `thread_dump.json` file. Its structure organizes threads into groups. The virtual threads are listed under the `"threads"` array. Let us look at a simplified JSON snippet representing a healthy, parked virtual thread:

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

##### Key Diagnostics Fields to Check:
1. **`"container": "<virtual>"`**: This explicitly marks the thread as a virtual thread on the heap, distinguishing it from standard platform threads (which display `"container": "<native>"`).
2. **`"state": "PARKED"`**: The thread is currently suspended and does not consume any CPU cores.
3. **`"blocker"`**: The exact Java object causing the thread to park. In this example, it is waiting on an AQS condition (such as a lock, semaphore, or queue). This is a **healthy state**; the thread is waiting for work and has unmounted from its carrier thread.

#### Tracing a Carrier Thread Pinning Bug
Now let us look at an unhealthy virtual thread. The thread is blocked waiting for database network I/O, but it is **pinned** because it is executing inside a `synchronized` block:

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

##### Critical Diagnosis Red Flags:
1. **`"state": "PINNED"`**: This is the primary indicator of thread pinning.
2. **`"carrierThread": "ForkJoinPool-1-worker-3"`**: This lists the physical carrier thread that is blocked. Because the virtual thread is pinned, `ForkJoinPool-1-worker-3` is locked to this task and cannot execute any other virtual threads, reducing application parallelism.
3. **`locked <0x0000000712345678>`**: The trace points to `locked` monitor blocks (indicated by `- locked`). Looking down the stack, we see `SimplePacketReader.readPacket` acquired a monitor lock. This synchronized block is the root cause of the pinning.

#### Diagnosing Thread Pinning: A Quick Checklist
If your virtual thread application experiences sudden latency spikes or hangs under load:
1. **Generate a JSON dump** using `jcmd`.
2. **Search for `"state": "PINNED"`** using a text editor or a simple query command (e.g., `grep -B 5 -A 10 "PINNED" thread_dump.json`).
3. **Trace the stack trace** of any pinned threads to identify `synchronized` method boundaries.
4. **Replace the synchronized locks** with `ReentrantLock` in those classes to restore thread unmounting.

---


