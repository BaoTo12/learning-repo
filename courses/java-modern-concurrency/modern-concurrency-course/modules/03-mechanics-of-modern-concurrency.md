# Module 03: The Mechanics of Modern Concurrency

> "The knowledge of anything, since all things have causes, is not acquired or complete unless it is known by its causes."
> — Ibn Sina (Avicenna), *circa* 1025 A.D.

---

### Learning Objectives
- Design and construct a custom Thread Pool (`SimpleThreadPool`) utilizing volatile flags, thread-safe queues, and `ThreadGroup` coordinates.
- Analyze the `ThreadPoolExecutor` constructor parameters and evaluate factory presets (`Fixed`, `Cached`, `Single`, `Scheduled`, `WorkStealing`).
- Implement asynchronous task pipelines using `Callable` and `Future` APIs to compile concurrent processing maps.
- Describe the architectural differences between `ThreadPoolExecutor` and `ForkJoinPool`, highlighting deques and LIFO vs. FIFO work-stealing behaviors.
- Write lock-free concurrent counters using CAS (Compare-And-Swap) atomic primitives via `VarHandle`.
- Formulate recursive tasks using the `RecursiveTask` framework, eliminating thread pool deadlock starvation.
- Trace Continuation stack frame states, lazy frame restoration, and return barriers.
- Simulate virtual threads by building a custom user-space scheduler (`NanoThread` & `NanoThreadScheduler`) and verify carrier thread context switching.
- Explain how JVM-wide Read/Write pollers bridge native OS event loops (`epoll`, `kqueue`, `wepoll`) with virtual thread execution states.

---

### Concept Explanation

#### 1. Thread Pool Fundamentals

In standard Java programming, spawning a platform thread is expensive. It requires allocating native OS kernel structures and reserving 1-2 MiB of off-heap memory. Creating threads ad-hoc under load can cause resource exhaustion, crashing the JVM with an `OutOfMemoryError`.

A **Thread Pool** is a managed group of threads created at startup that remain alive throughout the application lifecycle. By holding worker threads ready and decoupling task submission from execution, thread pools offer several key advantages:

##### Key Benefits
- **Resource Control**: Caps the maximum number of concurrent execution threads, preventing the application from crashing.
- **Thread Reuse**: Avoids thread creation and teardown overhead by recycling worker threads.
- **Queue Management**: Buffers task submission spikes in a thread-safe blocking queue.
- **Graceful Shutdown**: Coordinates worker shutdowns, ensuring active tasks complete cleanly before resources are released.
- **Business Logic Decoupling**: Shifts the developer's focus from thread management to business logic.

##### The OpenLiberty Study Context
While virtual threads are designed for I/O-bound tasks, traditional thread pools remain relevant. A study using **OpenLiberty** (a cloud-native Java runtime) found that its own optimized traditional thread pool implementation performed better than virtual threads in some high-throughput test runs. This highlights why understanding and configuring traditional thread pools remains a core skill for Java platform engineers.

---

#### 2. Building a Simple Thread Pool

To understand how thread pools operate internally, we can build a basic thread pool (`SimpleThreadPool`) from scratch. It consists of:
1. A bounded `BlockingQueue<Runnable>` to hold pending tasks.
2. A pool of `Worker` threads that continuously pull tasks from the queue and run them.
3. A `volatile boolean running` flag to coordinate shutdown.
4. A `ThreadGroup` to manage worker threads collectively.
5. An implementation of `AutoCloseable` to support try-with-resources.

##### Bounded Queue and Backpressure
Our pool uses a bounded queue (`LinkedBlockingDeque(queueSize)`). The `submit()` method uses `queue.put(task)`, which blocks if the queue is full. This provides **backpressure**, slowing down the producer when the pool is overwhelmed.

##### Coordinated Shutdown
The `close()` method gracefully drains the queue by checking `!queue.isEmpty()` and waiting. Once empty, it sets `running = false` and calls `threadGroup.interrupt()`. Since all workers belong to this group, they receive the interrupt signal simultaneously, break out of queue blocks, and terminate.

---

#### 3. The Executor Framework Deep Dive

Java 5 introduced the `Executor` framework in `java.util.concurrent` to standardize thread pool management. At the core is `ThreadPoolExecutor`:

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

##### Parameters and Core Configurations
- **`corePoolSize`**: The minimum number of threads kept alive in the pool, even if idle.
- **`maximumPoolSize`**: The upper limit on active threads in the pool.
- **`keepAliveTime` & `unit`**: The duration that excess idle threads (above `corePoolSize`) wait for new tasks before terminating.
- **`workQueue`**: The queue holding tasks before execution (e.g., `LinkedBlockingQueue` or `SynchronousQueue`).
- **`threadFactory`**: Factory used to customize thread configurations (names, priority, daemon status).
- **`handler`**: The policy invoked when the queue is full and thread limits are reached (e.g., `AbortPolicy` or `CallerRunsPolicy`).

##### Sizing Strategy
- **CPU-Bound Tasks** (e.g., calculations, image processing): Sized to match available CPU cores ($N_{threads} \approx N_{cores}$). Excess threads increase context switching and cache misses, degrading performance.
- **I/O-Bound Tasks** (e.g., database queries, API calls): Sized larger than available cores ($N_{threads} > N_{cores}$), allowing idle threads waiting on I/O to yield CPU cycles to active tasks.

##### Common Factory Presets (`java.util.concurrent.Executors`)
- **`newFixedThreadPool(n)`**: core = max = $n$. Uses an unbounded `LinkedBlockingQueue`. 
- **`newCachedThreadPool()`**: core = 0, max = `Integer.MAX_VALUE`, keepAlive = 60s. Uses a `SynchronousQueue` that hands tasks directly to threads. Spawns threads dynamically, creating starvation risks under sudden spikes.
- **`newSingleThreadExecutor()`**: Runs a single worker thread, executing tasks sequentially in submission order.
- **`newScheduledThreadPool(n)`**: Sized pool using a delay queue to execute tasks after a delay or periodically.
- **`newWorkStealingPool()`**: Creates a work-stealing `ForkJoinPool` using all available processors by default.

---

#### 4. Callable and Future

Unlike `Runnable.run()`, which returns no value and cannot throw checked exceptions, `Callable.call()` is designed for value-producing asynchronous computations:

```java
@FunctionalInterface
public interface Callable<V> {
    V call() throws Exception;
}
```

##### Asynchronous Pipelines
Submitting a `Callable` to an `ExecutorService` returns a `Future` representing the pending result:
- **`Future.get()`**: A blocking call that waits until the task completes to retrieve the result.
- **`Future.isDone()`**: Checks if the task is complete.
- **`Future.cancel(boolean)`**: Attempts to cancel execution.

To run concurrent computations, we can submit multiple tasks to a pool, collect their `Future` objects, and iterate over them to retrieve results:

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

##### Code Analysis: Pipeline Submissions & Cache Safety
1. **Thread Pool Execution Map (`submit()`)**:
   - The loop iterates over target Fibonacci indices, submitting computation tasks to the cached thread pool. Each submission returns a `Future<Long>` handle representing the deferred calculation.
2. **Concurrent Cache Isolation (`ConcurrentHashMap.computeIfAbsent`)**:
   - Multiple threads execute `fibonacci(index)` in parallel. To prevent duplicate computations and race conditions on intermediate values, the calculations utilize `ConcurrentHashMap.computeIfAbsent`.
   - Under the hood, `computeIfAbsent()` uses lock-free bucket structures with CAS operations on empty buckets. If a bucket contains a collision node, it synchronizes on the bucket head node to ensure thread-safety, allowing concurrent reads while bounding write contention.
3. **Sequential Result Processing**:
   - The main thread iterates through the futures list, calling `.get()`. Because `.get()` blocks, the print statements output calculated values sequentially. If a long calculation (like `fibonacci(50)`) is enqueued earlier, the main thread blocks on its `.get()` even if later tasks (like `fibonacci(10)`) completed earlier.

---

#### 5. ForkJoinPool Deep Dive & Work-Stealing Internals

Unlike traditional thread pools that use a single shared blocking queue, the `ForkJoinPool` is designed for fine-grained parallel processing. To understand its execution efficiency under Loom, we must analyze its queue structures and memory visibility mechanics.

##### Why ForkJoinPool differs from ThreadPoolExecutor
- **Shared Queue vs. Per-Thread Deques**: In a standard `ThreadPoolExecutor`, worker threads compete for tasks in a single queue (like `LinkedBlockingQueue`), which generates high lock contention under high request volumes. In a `ForkJoinPool`, each worker thread maintains its own double-ended task queue (**Deque**), represented as a custom `WorkQueue` structure.
- **Work-Stealing Algorithm**: When a worker thread finishes its own tasks, it does not block or sleep. Instead, it attempts to "steal" tasks from the deques of other worker threads, maximizing CPU core utilization.

##### The Anatomy of a ForkJoinPool WorkQueue Deque

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

Inside the `ForkJoinPool`, each `WorkQueue` deque is backed by a circular array of tasks, managed using two pointer indices:
1. **`top`**: The index pointing to the slot where the queue owner inserts tasks.
2. **`base`**: The index pointing to the slot where thief threads steal tasks.

* **Pushing Tasks (Owner Thread)**:
  - When a task calls `fork()` or submits a subtask, the queue owner thread writes the task reference to the array slot at index `top` and increments `top` (`top++`).
  - This write executes without acquiring locks, using a simple store instruction.

* **Popping Tasks (Owner Thread)**:
  - If the pool is configured in **LIFO (Last-In, First-Out)** mode (standard parallel streams), the owner pops tasks from the head by decrementing `top` (`top--`) and reading the task reference.
  - Since the owner thread is the only thread that writes to `top`, this pop operation requires no synchronization unless the queue is almost empty (i.e. `top` is close to `base`).

* **Stealing Tasks (Thief Threads)**:
  - When worker thread B runs out of tasks, it scans the pool to locate worker thread A's queue.
  - Sibling "thief" threads always steal tasks from the **`base`** index of the target queue in **FIFO (First-In, First-Out)** order.
  - The thief thread reads the task reference at `base` and attempts to increment `base` (`base++`) atomically using a Compare-And-Swap (CAS) instruction.
  - If multiple thieves attempt to steal from the same worker queue simultaneously, only one thief succeeds in the CAS check. Sibling threads fail and retry by scanning other queues.

##### FIFO Async Mode in Project Loom

Virtual threads are scheduled on carrier platform threads using a `ForkJoinPool` configured in **FIFO async mode** (`asyncMode = true` in ForkJoinPool constructors).

* **LIFO (Last-In, First-Out)**:
  - Under standard parallel stream calculations (e.g. recursive sorting), tasks are processed in LIFO order by the owner thread.
  - This keeps the most recently split subtasks on the same CPU core, maximizing L1/L2 cache affinity.
  - However, in transaction-oriented web applications, LIFO scheduling can lead to task starvation: older request tasks waiting in the queue are pushed back by new incoming requests.

* **FIFO (First-In, First-Out) Async Mode**:
  - In async mode, the worker owner thread polls tasks from the **`base`** index (FIFO order) rather than popping them from `top`.
  - This ensures request execution is fair, processing requests in the order of connection arrival and preventing older requests from timing out.


##### Lock-Free CAS Queues
To minimize lock contention during work stealing, the `ForkJoinPool` queue uses Compare-And-Swap (CAS) operations via `VarHandle` rather than standard locks. CAS atomically compares a memory location to an expected value and updates it only if they match, avoiding OS-level thread blocking:

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

##### Deep Execution Mechanics: Compare-And-Swap (CAS) & VarHandle Primitives
1. **VarHandle Memory Offsets**:
   - `VALUE_HANDLE` is initialized via reflection using `MethodHandles.lookup()`. It acts as a direct memory pointer to the offset of the volatile `value` field within the `AtomicCounter` class.
   - This bypasses standard field access getters/setters, invoking memory barrier instructions directly at the assembly level.
2. **The CAS Loop (`compareAndSet`)**:
   - The `increment()` method executes a lock-free retry loop. It reads the current memory value, calculates the target next value (`current + 1`), and calls `VALUE_HANDLE.compareAndSet(...)`.
   - **Hardware Level Instruction**: The JVM translates `compareAndSet` directly to target CPU atomic instructions (e.g., `LOCK CMPXCHG` on x86 architectures).
   - If another thread modified `value` between the read and write steps, the memory comparison fails, returning `false`. The loop retries, reading the new value and repeating the attempt until it successfully writes the update.
3. **Lock-Free Concurrency Benefits**:
   - Because no thread monitor lock is acquired, worker threads do not block or context-switch to the OS kernel queue, avoiding lock overhead and maximizing throughput.

##### Volatile Cache Coherence, MESI States, and Hardware Store Buffers

To truly master concurrent programming, you must look below the Java virtual layer and examine how multi-core CPUs coordinate memory states. In modern hardware, the latency gap between CPU register operations (sub-nanosecond) and main memory access (typically 50–100 nanoseconds) is vast. To prevent CPU cores from idling, chip manufacturers employ multi-level caching systems. However, this creates a major challenge: **Cache Coherence**.

###### 1. The Multi-Core CPU Caching Hierarchy

Each CPU core contains its own fast, localized L1 and L2 caches, while sharing a larger L3 cache with other cores on the same socket:

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

Memory operations do not move bytes individually; instead, they operate on fixed-size blocks called **Cache Lines** (usually 64 bytes). When Core 0 reads a variable, the entire 64-byte cache line containing that variable is fetched from main memory into Core 0's L1/L2 cache.

If Core 1 subsequently reads the same variable, it fetches the same cache line. If Core 0 then modifies this variable, Core 1's cached copy becomes stale. Without coordination, Core 1 would read outdated data, violating memory consistency.

###### 2. The MESI Coherence Protocol

To maintain a unified view of memory across all cores, CPUs implement hardware-level protocols, most notably **MESI** (Modified, Exclusive, Shared, Invalid). Under MESI, every cache line in an L1/L2 cache is tagged with one of four states:

| State | Name | Description |
| :--- | :--- | :--- |
| **M** | **Modified** | The cache line is present *only* in the current core's cache, and its data is dirty (modified relative to main memory). The current core has exclusive write access. |
| **E** | **Exclusive** | The cache line is present *only* in the current core's cache, but its data is clean (matches main memory). It can be transitioned to *Modified* silently. |
| **S** | **Shared** | The cache line is present in the current core's cache and potentially other cores' caches. It is clean. A core *cannot* write to a Shared line without coordination. |
| **I** | **Invalid** | The cache line contains no valid data. Reading from it triggers a cache miss, requiring a reload from L3 or main memory. |

###### State Transition Dynamics:
1. **Read Request on Shared Line**: If Core 0 wants to read a line that is in state `I`, it broadcasts a read request over the interconnect bus. If Core 1 has this line in state `M` or `E`, Core 1 responds with the data, and the state of the line in both cores becomes `S`. If Core 1 had it in state `M`, it must first write the dirty data back to main memory or transfer it directly to Core 0.
2. **Write Request on Shared Line**: If Core 0 wants to write to a cache line that is in state `S`, it cannot do so immediately. It must first broadcast an **Invalidate** message over the bus. All other cores containing that cache line must mark their local copies as `I` (Invalid) and send an **Invalidate Acknowledge** back to Core 0. Only after receiving all acknowledgments can Core 0 transition its cache line to `M` and perform the write.

###### 3. The Bottleneck: Why Store Buffers and Invalidation Queues Exist

While the MESI protocol ensures cache coherence, waiting for *Invalidate Acknowledgment* messages introduces latency. If Core 0 has to wait for Core 1, Core 2, and Core 3 to invalidate their caches and reply before it can write, the CPU pipeline stalls, wasting hundreds of execution cycles.

To avoid this, hardware engineers introduced two key optimizations:
1. **Store Buffers**: Placed between the CPU core and its L1 cache. When a core issues a write instruction, it writes the data directly to its private Store Buffer and immediately continues executing instructions, without waiting for the invalidate acknowledgments. The store buffer handles sending the invalidation requests and applying the write to the cache line once acknowledgments arrive.
2. **Invalidation Queues**: When a core receives an Invalidate message from another core, it doesn't process it immediately. Instead, it places the invalidation request into an Invalidation Queue and instantly sends back an Invalidate Acknowledge. It processes the queue elements as CPU cycles allow, transitioning its cache lines to `I` asynchronously.

###### How Store Buffers and Invalidation Queues Break Visibility:
* **Delayed Write Broadcasts**: Since writes sit in Core 0's Store Buffer, Core 1 cannot see them. Core 1 continues reading from its local cache line (which is still marked `S` because the invalidation message has not yet been processed out of Core 1's Invalidation Queue).
* **Asynchronous Invalidation**: Even if Core 0 flushes its store buffer to its cache (sending the invalidation message), the update is still invisible to Core 1 because Core 1 has not processed the invalidate message from its Invalidation Queue.

###### 4. Memory Barriers (Fences)

To force visibility and ordering when writing concurrent algorithms, the CPU must be explicitly instructed to bypass these asynchronous optimizations. This is done using **Memory Barriers** (or memory fences).

At the hardware level:
* **Store Barrier (Write Barrier)**: Flushes the local Store Buffer. The CPU stalls execution of subsequent writes until all stores currently in the buffer are written to the cache line and invalidations are acknowledged.
* **Load Barrier (Read Barrier)**: Forces the CPU to process all messages in its Invalidation Queue. This ensures that any cache lines invalidated by other cores are marked `I` before any subsequent read instructions run, forcing the CPU to fetch fresh data.
* **Full Barrier**: Performs both store and load barrier actions, preventing any instruction reordering across the fence.

On x86 architectures, CPU instructions like `MFENCE` (Memory Fence), `LFENCE` (Load Fence), and `SFENCE` (Store Fence) are used. Additionally, instructions prefixed with `LOCK` (e.g., `LOCK CMPXCHG`) implicitly act as full memory barriers by locking the local cache line/bus and flushing the store buffer.

###### 5. Mapping to the Java Memory Model (JMM)

The Java Memory Model abstracts these hardware details into readable constructs: `volatile` and `synchronized`.

When you mark a field as `volatile`:
1. **Volatile Write**: The JVM compiles the write instruction followed by a StoreLoad barrier (usually implemented as a `LOCK` prefix instruction on x86). This forces the store buffer to flush its contents to L1 cache immediately and broadcast invalidation signals to all other cores.
2. **Volatile Read**: The JVM compiles a LoadLoad/LoadStore barrier before the read instruction. This forces the CPU to empty its Invalidation Queue, marking any altered cache lines as invalid and ensuring the subsequent read loads fresh data from L3 cache or main memory.

This ensures that:
* **Happens-Before Consistency**: A write to a volatile variable *happens-before* every subsequent read of that same variable.
* **Instruction Reordering Prevention**: The compiler and the CPU are prevented from reordering reads and writes across the volatile boundary, preventing race conditions where partial object updates are read by other threads.

##### RecursiveTask and Deadlock Avoidance
Traditional pools suffer from deadlock if tasks block waiting for subtasks (e.g., `FixedThreadPool(10)` running recursive Fibonacci). Because worker threads block on `Future.get()`, the pool quickly runs out of threads.
`ForkJoinPool` resolves this: when a task calls `join()` on a subtask, the worker thread suspends the waiting task and runs other pending tasks from its queue or steals tasks from other workers, preventing deadlocks.

---

#### 6. Continuation Theory: Yielding and Resuming

A **Continuation** represents a program's execution state (its local variables, call stack, and instruction pointer) that can be paused (yielded) and resumed later.

##### Memory and Stack Frame Lifecycle
- **Heap Allocation**: Virtual thread stack frames are stored as linked objects in the JVM garbage-collected heap, rather than in monolithic off-heap OS memory.
- **Lazy Copying**: Copying deep call stacks back and forth is expensive. To optimize performance, the JVM uses lazy copying: when a continuation resumes, it only copies the top few stack frames back to the carrier thread.
- **Return Barriers**: The JVM injects return barriers at the boundary of un-restored frames. When execution hits a barrier, the JVM copies the next set of frames from the heap to the stack, minimizing call stack overhead.

##### Deep Dive: Inside the JVM Continuation freeze/thaw Mechanics and Assembly-Level Frame Management

To understand how the JVM pauses and resumes virtual threads without native OS overhead, you must examine the internal mechanisms of the **Continuation** subsystem. In OpenJDK, continuations are implemented as a mix of native C++ code in the JVM HotSpot kernel and low-level assembly code targeted to specific CPU architectures (e.g., x86_64, AArch64).

###### 1. Memory Layout of a Continuation on the Heap
When a virtual thread is executing, its call stack resides on the physical stack of the carrier platform thread. When it yields, the JVM moves these frames into the `Continuation` object located on the garbage-collected heap.

The `Continuation` object contains:
- **`stack`**: A primitive array (`int[]` or reference array) that stores the raw binary data of the execution frames (local variables, operand stack values, and physical CPU registers).
- **`fp` (Frame Pointer) and `sp` (Stack Pointer)**: Offset pointers into the stack array.
- **`pc` (Program Counter)**: The address of the next bytecode instruction to execute.
- **`parent`**: A pointer to the parent continuation, supporting nested execution.

###### 2. The Yielding Process: "Freeze"
When a virtual thread calls a blocking operation (e.g., `Thread.sleep()` or reading a socket), it eventually calls the native method `Continuation.yield()`. This triggers the **Freeze** operation in the JVM HotSpot kernel:

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

1. **Stack Walk**: The JVM starts at the active frame pointer (`RSP` register) and walks up the call stack to identify all frames belonging to this continuation.
2. **Dynamic Chunk Allocation**: If the continuation's internal stack array is too small or does not exist, the JVM allocates or resizes a stack chunk on the heap.
3. **Frame Copying**: The JVM copies the stack frames, including local variables, execution state, and metadata, into the heap array.
4. **Register Cleanup**: The JVM clears references to the virtual thread stack from the carrier thread's registries to prevent memory leaks and ensure the GC can sweep dead objects.
5. **Frame Unmounting**: The assembly-level yield routine swaps the CPU's stack pointer (`RSP`) and frame pointer (`RBP`) registers back to the carrier thread's original execution frames, returning control to the ForkJoinPool scheduler.

###### 3. The Resuming Process: "Thaw"
When the blocking operation completes, the virtual thread is scheduled back onto a carrier thread. When the carrier thread starts running the task, it calls `Continuation.run()`, initiating the **Thaw** operation:

1. **Stack Reconstitution**: The JVM reads the saved metadata from the heap `Continuation` object.
2. **Lazy Copying**: Rather than copying all stack frames back to the carrier stack (which would be slow if the stack is deep), the JVM copies only the **topmost frame** (the current execution frame) back onto the carrier thread's stack.
3. **Return Barrier Injection**:
   - To handle the missing, un-copied frames, the JVM injects a **Return Barrier** at the bottom of the thawed frame.
   - The CPU's return address register is modified to point to a special JVM runtime stub instead of the actual caller method.
4. **Assembly Context Swap**: The assembly stub swaps the CPU stack pointer register to point to the newly thawed frame, updates the program counter register, and executes.
5. **On-Demand Thawing (Hitting the Return Barrier)**:
   - When the active method completes and attempts to return to its caller, the CPU execution hits the modified return address, jumping to the JVM return barrier stub.
   - The stub intercepts execution, pauses, walks the heap continuation stack to copy the next parent frame onto the carrier stack, restores the actual return address, and resumes.
   - This lazy on-demand thawing minimizes copy overhead, ensuring that yielding and resuming operations execute in sub-microsecond times.

##### Internal Continuation API Example
Java's internal `Continuation` class demonstrates this yielding behavior:

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

##### Code Analysis: Low-Level Continuation Transitions
1. **Instance Instantiation**:
   - `new Continuation(scope, Runnable)` allocates a continuation instance on the JVM heap. The second argument defines the entry point execution logic.
2. **Pausing Execution (`Continuation.yield()`)**:
   - Calling `Continuation.yield(scope)` pauses execution. The JVM saves the continuation's execution frames (local variables, program counter, and stack offset) on the heap.
   - The call returns control to the caller thread, resuming execution directly after the `continuation.run()` call in `main()`.
3. **Restoring Context**:
   - The subsequent `continuation.run()` call restores the program counter and stack frames. The JVM execution resumes exactly at the instruction following the matching `yield()` call.

---

#### 7. Building NanoThread from Scratch

We can simulate Project Loom's scheduler by building a custom user-space thread framework (`NanoThread`):
- **`NanoThread`**: Wraps the continuation, providing a name and unique ID.
- **`NanoThreadScheduler`**: Manages execution. Uses a 2-thread Work-Stealing carrier pool and a single-thread scheduled executor (`IO_NOTIFIER`) to simulate asynchronous I/O completion.
- **`FileOperation`**: Simulates file transfers. When a transfer starts, the task schedules a resume callback and yields the continuation, freeing the carrier thread for other work.

---

#### 8. Virtual Threads and I/O Polling

Loom integrates blocking APIs with the OS network stack. When a virtual thread performs blocking I/O, the JDK intercepts the call:

##### `LockSupport.park()` Redirection
```java
public static void park() {
    if (Thread.currentThread().isVirtual()) {
        VirtualThreads.park(); // Invokes yieldContinuation()
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

When the OS signals that I/O is ready, the poller notifies the JVM, which marks the virtual thread as runnable and schedules it back onto an available carrier thread to resume execution.

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

##### Line-by-Line Code walk: `SimpleThreadPool`
1. **Queue Initialization & Bound Capacity**:
   - `new LinkedBlockingDeque<>(queueSize)` initializes a double-ended blocking queue. In `submit()`, when the queue is full, the thread blocks on `queue.put(task)`. This provides **backpressure**, preventing memory exhaustion.
2. **Worker Creation and Thread Groups**:
   - The constructor spawns a set number of `Worker` threads. Passing `threadGroup` maps them to a single management group. This allows the program to target active workers simultaneously.
3. **Graceful Shutdown Drainage (`close()`)**:
   - The thread pool implements `AutoCloseable`. Upon exiting the try-with-resources block, `close()` is executed.
   - It polls `!queue.isEmpty()`, waiting for active tasks to complete.
   - It then invokes `shutdown()`, setting `running = false` and calling `threadGroup.interrupt()`.
4. **Interruption Recovery**:
   - The worker threads block on `queue.take()`. When interrupted, they catch `InterruptedException`, check if `running` is false, and break the loop to terminate cleanly.

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

##### Deep Analysis: Starvation Deadlocks vs Work-Stealing Recovery
1. **Starvation Deadlock Mechanics (`DeadlockDemo`)**:
   - Inside `DeadlockDemo`, recursive Fibonacci tasks are submitted to a `FixedThreadPool(10)`.
   - To compute `fib(15)`, the worker thread submits `fib(14)` and `fib(13)` to the executor and blocks on `f1.get() + f2.get()`.
   - Because each recursive call consumes a thread, the thread pool is quickly exhausted. If all 10 threads are blocked waiting for results from the queue, no threads are available to run the tasks in the queue, causing a **starvation deadlock**.
2. **ForkJoin Work-Stealing Mitigation (`ForkJoinFibonacci`)**:
   - `ForkJoinPool` resolves this via cooperative scheduling.
   - In `FibonacciTask`, the first subtask is pushed to the worker's deque via `f1.fork()`.
   - The current thread executes the second subtask immediately using `f2.compute()`.
   - When calling `f1.join()`, instead of blocking the thread, the `ForkJoinPool` worker checks if the task is complete. If not, the worker executes other pending tasks from its deque or steals tasks from other worker queues, preventing thread starvation.

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

##### Step-by-Step Logic Walk: User-Space Continuation Scheduler Simulation

1. **Thread Registration and Continuation Allocation**:
   - At line 536, the class constructor `NanoThread(Runnable)` instantiates a `NanoThread` and allocates a JDK-internal `Continuation` on the JVM heap.
   - It specifies `NanoThread.SCOPE` as the execution boundary context, ensuring that any yields within this task only affect this specific logical execution pipeline rather than other concurrent tasks.
   - The thread is submitted to `NanoThread.SCHEDULER.schedule(NanoThread)`, initializing its entry into the active task queue.

2. **Mounting Tasks onto Carrier Threads**:
   - Inside `NanoThreadScheduler.java` (line 569), the task manager maintains a pool of platform carrier threads: `carrierPool = Executors.newWorkStealingPool(2)`.
   - When `schedule()` is invoked, the scheduler submits a task wrapper to the carrier pool.
   - When a carrier thread picks up the task, it registers the `NanoThread` instance in its thread-local context via `CURRENT_THREAD.set(thread)`.
   - It then invokes `thread.run()`, which mounts the heap-allocated continuation stack onto the current carrier thread. The JVM swaps registers and begins executing the task's runnable target.

3. **Asynchronous I/O Execution and Cooperative Unmounting**:
   - Inside `FileOperation.transfer()`, the program prints a log identifying the active `NanoThread` context.
   - To simulate a non-blocking background read, the task schedules a resume callback with `IO_SCHEDULER.schedule(...)` (line 609). This callback registers the worker thread for execution once the mock connection completes.
   - The task then executes `NanoThreadScheduler.CURRENT_THREAD.remove()` to clean up thread-local variables.
   - Line 616 invokes `Continuation.yield(NanoThread.SCOPE)`. The JVM catches the yield instruction, freezes the virtual execution frame (storing instruction pointers and local variables back to the heap), restores the caller's stack frame on the carrier thread, and returns control back to the scheduler.
   - The carrier thread is immediately freed and returns to its work-stealing pool to execute other pending tasks.

4. **Rescheduling and Context Restoration**:
   - Once the scheduled timer expires, the `IO_SCHEDULER` worker thread executes the callback, which calls `NanoThread.SCHEDULER.schedule(currentThread)`.
   - This schedules the suspended continuation back onto the carrier pool.
   - An available carrier thread grabs the task, maps `CURRENT_THREAD` again, and invokes `thread.run()`.
   - The JVM reads the saved stack metadata from the heap, reconstructs the thread's stack frame on the carrier thread, updates the instruction pointer, and resumes execution directly after the `Continuation.yield()` statement.
   - The thread outputs the final message, completing the simulated execution cycle.

##### Run Command
```bash
# Export the internal JVM continuation classes to enable execution:
javac --add-exports java.base/jdk.internal.vm=ALL-UNNAMED NanoThread*.java FileOperation.java
java --add-exports java.base/jdk.internal.vm=ALL-UNNAMED com.example.concurrency.lab3_3.NanoThreadDemo
```


---

### Securing User-Space Schedulers: Class Loaders & Continuation Scopes to Prevent Security Leakage

#### The Security Threat of Custom Continuations
When building custom cooperative user-space schedulers (like our `NanoThread` or servlet engines built on JVM internals), we introduce two major security vulnerabilities:
1. **Continuation Scope Pollution**:
   - `Continuation` execution is bounded by a `ContinuationScope`.
   - If multiple untrusted tasks (e.g. in a plugin-based architecture or multi-tenant system) run within the same `ContinuationScope`, one malicious task can invoke `Continuation.yield(scope)` using the shared scope reference. 
   - This yields the stack of the host container or sibling plugins, leading to Denial of Service (DoS) or thread hijack exploits.
2. **Carrier Thread Context Leakage**:
   - Platform carrier threads are pooled and reused across tasks.
   - If Task A (loaded by ClassLoader A) stores sensitive information in a `ThreadLocal` on a carrier thread, and Task B (loaded by ClassLoader B) is subsequently scheduled on the same carrier thread, Task B can call `ThreadLocal.get()` to read Task A's private security credentials, database configurations, or authenticated user mappings.
   - This breaks classloader isolation boundaries and leaks tenant data.

#### Architectural Mitigation: Scope Encapsulation and ThreadLocal Purging
To secure custom user-space continuation runtimes, we must enforce two guardrails:
1. **Unique Scope Instantiation**:
   - Every tenant or classloader context must instantiate its own private, non-shared `ContinuationScope`.
   - Scopes must not be exposed to user tasks. Instead, wrap them in a package-private context.
2. **Carrier Thread Cleaning Hook**:
   - Before executing `Continuation.run()`, the scheduler must purge all `ThreadLocal` mappings belonging to prior tasks.
   - This can be achieved by using Java reflection to access and clear `ThreadLocalMap` or wrapping tasks in custom isolation gates.

Let's look at a complete, secure implementation of an isolated user-space scheduler featuring class loader context partitioning and thread cleaning:

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

##### Line-by-Line Code Walkthrough: `SecureContinuationScheduler`

1. **ClassLoader Partitioning (`getOrCreateScope`)**:
   - At line 31, the registry uses a `ConcurrentHashMap` mapping ClassLoaders to `ContinuationScope` instances.
   - When a plugin is loaded, it gets a dedicated ClassLoader. Line 32 instantiates a uniquely named `ContinuationScope` based on the hash of that loader and a nanosecond timestamp.
   - This ensures that if Plugin A attempts to yield by invoking `Continuation.yield(scope)`, it must pass its *own* scope. It cannot yield the scope of Plugin B because it does not have a reference to Plugin B's scope instance.

2. **Reflection-Based ThreadLocal Map Purging (`purgeThreadLocals`)**:
   - At line 42, the executor retrieves the active `Thread` object running the task.
   - Lines 43-45 retrieve the private `threadLocals` field declared in `java.lang.Thread` via reflection.
   - By calling `threadLocalsField.set(current, null)`, the scheduler completely discards the worker thread's internal `ThreadLocalMap`.
   - Lines 47-49 execute the same purge operation for `inheritableThreadLocals`.
   - This guarantees that no credentials, tracing details, or classloader references persist, preventing Memory Leaks and security escalations.

3. **Double Purging Life Cycle (`submit`)**:
   - The scheduler runs a strict security lifecycle:
     - **Pre-execution purge** (line 59): Guarantees that any leftovers from previous runs are eliminated before class-loading starts.
     - **Execution mapping** (line 62): Assigns the thread's class loader to match the task context.
     - **Post-run purge** (line 67): Clears values inside the continuation's run method finally block.
     - **Post-unmount purge** (line 78): Runs in a final block in the carrier execution thread to sweep thread-local variables if the continuation yields.

---

### Common Pitfalls & Anti-Patterns

#### 1. Calling `compute()` on both RecursiveTask subtasks
When using `ForkJoinPool`, developers often write:
```java
// Anti-Pattern: calling compute() on both tasks executes them sequentially, losing parallelism!
FibonacciTask f1 = new FibonacciTask(n - 1);
FibonacciTask f2 = new FibonacciTask(n - 2);
long r1 = f1.compute(); 
long r2 = f2.compute();
return r1 + r2;
```
This causes sequential execution on a single thread. The correct pattern is to call `fork()` on the first task (pushing it to the work-stealing queue) and `compute()` on the second task (executing it immediately on the current thread), and then call `join()` on the first task:
```java
f1.fork(); // Asynchronously submits f1 to the queue
long r2 = f2.compute(); // Computes f2 immediately on the current thread
long r1 = f1.join(); // Joins the result of f1
return r1 + r2;
```

#### 2. Reusing a ThreadPoolExecutor core queue without bounding
Reusing fixed executors without setting an explicit capacity on the constructor's `workQueue` (e.g., passing an unbounded `LinkedBlockingQueue`) introduces latency risks. Under load spikes, the queue stores millions of tasks, leading to memory accumulation and GC pressure, defeating the purpose of thread bounds.

---

### Summary
1. **Thread Pools**: Bounded pools manage threads and queues to prevent system resource exhaustion.
2. **ForkJoinPool vs. Traditional Pools**: ThreadPoolExecutor uses a single global queue, whereas ForkJoinPool uses worker-specific deques and work-stealing to minimize thread contention.
3. **Loom Scheduling**: Virtual threads run on carrier platform threads scheduled by a FIFO async `ForkJoinPool`.
4. **Continuations**: PAUSE and RESUME execution. When blocking, the JVM yields continuation stacks to the heap and lazy-copies frames back when resuming.
5. **Native I/O Pollers**: Thread unmounting integrates with native OS event loops (`epoll`, `kqueue`, `wepoll`) to wake virtual threads when I/O completes.

---

### Knowledge Check - Deep Dive Scenarios

#### Question 1: Unbounded Queue Saturation
A system architect designs a backend routing system using a `FixedThreadPool` of size 50. The pool receives incoming requests and submits them via a constructor wrapping an unbounded `LinkedBlockingQueue`. If the average database write time increases from 5ms to 500ms due to connection pool blocking:
Which of the following occurs under a steady load of 5,000 requests per second?
- A. The pool rejects additional requests using the default `AbortPolicy`.
- B. The core pool size dynamically scales up to 5,000 threads.
- C. The queue accumulates millions of tasks, leading to memory leaks and a JVM crash with `java.lang.OutOfMemoryError: Java heap space`.
- D. Tasks are completed in LIFO order, bypassing latency bottlenecks.

*Answer*: **C**
*Explanation*: Bounded thread pools using an unbounded queue will never trigger thread creation beyond `corePoolSize` nor trigger the `RejectedExecutionHandler`. Instead, when execution slows down, requests accumulate indefinitely in the queue, consuming heap space until memory is exhausted.

#### Question 2: CAS Contention on Multi-Core Systems
An execution log service counts transactions using a volatile integer and increments it using a standard synchronizing monitor block. To optimize throughput, a developer replaces this wrapper with a lock-free CAS loop using `VarHandle.compareAndSet`. Under a benchmark with 128 concurrent threads running on a 64-core system, performance degrades compared to lower thread counts. What JVM-level event explains this degradation?
- A. The OS kernel scheduler suspends worker threads inside the CAS instructions.
- B. High hardware cache contention causes CPU cores to execute repeated retry loops (spin-lock starvation) while processing the atomic check, saturating the cache coherence bus.
- C. VarHandle allocations saturate heap space.
- D. Volatile fields require native JNI context switches.

*Answer*: **B**
*Explanation*: Under extreme concurrency, multiple threads attempt to write to the same memory offset. Only one thread succeeds in each iteration, forcing the other 127 threads to fail the CAS check and retry. This loop consumes CPU cycles and generates bus traffic as cores synchronize their cache lines, causing performance degradation.

#### Question 3: Continuation Lazy Copying and Return Barriers
During virtual thread execution, the JVM optimizes resume performance using a lazy stack copying mechanism. How is stack recovery coordinated when a nested continuation resumes?
- A. The JVM copies the entire call stack from the heap back onto the carrier thread stack at once.
- B. The JVM copies only the top stack frames to the carrier thread, injecting a return barrier on the heap boundaries. When execution hits this barrier, the JVM copies the next set of frames from the heap, minimizing overhead.
- C. The JVM ignores stack variables and resolves values dynamically using reflections.
- D. Stack memory maps are redirected to off-heap native memory caches.

*Answer*: **B**
*Explanation*: Lazy stack recovery is a core optimization in Project Loom. Instead of copying deep stacks on every yield and resume, the JVM copies only the top frames and uses return barriers to copy remaining frames on-demand, reducing execution overhead.

#### Question 4: LIFO vs FIFO Work-Stealing Scheduling
Traditional parallel streams execute divide-and-conquer tasks using a ForkJoinPool in LIFO (Last-In, First-Out) mode, whereas the Project Loom virtual thread scheduler uses FIFO (First-In, First-Out) async mode. What is the reason for this scheduling difference?
- A. LIFO mode is required to process socket connections concurrently.
- B. FIFO mode prevents task starvation by ensuring that older request tasks waiting in the scheduler queue are processed first. LIFO mode can lead to delayed requests if new tasks are continuously submitted.
- C. FIFO mode allocates less heap memory.
- D. LIFO mode forces threads to pin carriers.

*Answer*: **B**
*Explanation*: In web request environments, processing tasks in FIFO order is essential to prevent task starvation. In contrast, parallel stream calculations benefit from LIFO mode because it keeps hot variables in the CPU cache, maximizing cache affinity.

#### Question 5: ForkJoinPool Deadlock Starvation
Why does executing a recursive calculation (like Fibonacci) inside a `FixedThreadPool` lead to deadlock under load, whereas the same calculation executes successfully in a `ForkJoinPool`?
- A. ForkJoinPool dynamically increases its thread count to `Integer.MAX_VALUE`.
- B. ForkJoinPool worker threads use cooperative scheduling: when a task blocks on `join()`, the worker thread suspends the task and executes other pending tasks in its deque or steals tasks from other worker queues, preventing starvation.
- C. ForkJoinPool bypasses JVM thread local variables.
- D. FixedThreadPool does not support record structures.

*Answer*: **B**
*Explanation*: `ForkJoinPool` workers use cooperative scheduling to execute other tasks when a task blocks on `join()`. In contrast, `ThreadPoolExecutor` worker threads block on `Future.get()`, causing starvation deadlocks if the pool is exhausted.

#### Question 6: Redirection of `LockSupport.park()`
When a virtual thread executes a blocking database call or network read, what JVM sequence prevents the underlying operating system thread from blocking?
- A. The thread executes a native JNI bypass loop.
- B. The JVM redirects `LockSupport.park()` calls: if the current thread is virtual, it yields the continuation, saves stack frames on the heap, and frees the carrier thread.
- C. The JVM throws an `IllegalStateException` to abort the transaction.
- D. The thread is converted to a platform thread.

*Answer*: **B**
*Explanation*: When a virtual thread blocks, the JVM intercepts the call and yields the continuation, moving its stack frames to the heap and freeing the carrier thread. The carrier thread then runs other virtual threads.

#### Question 7: VarHandle Memory Barriers
Which VarHandle access mode provides atomic compare-and-set operations with both acquire and release memory consistency semantics?
- A. `getOpaque`
- B. `setVolatile`
- C. `compareAndSet`
- D. `getAcquire`

*Answer*: **C**
*Explanation*: `VarHandle.compareAndSet` enforces memory visibility barriers equivalent to volatile reads and writes, ensuring acquire/release semantics.

#### Question 8: OS Event Loops and Virtual Threads
How does the JVM wake up a suspended virtual thread once its blocking socket read operation receives data from the network?
- A. The JVM continually polls the thread's heap state in a spin-lock loop.
- B. The JVM registers the socket's file descriptor with native OS event loops (like `epoll` or `kqueue`). When the OS signals that data is ready, the JVM schedules the virtual thread back onto an available carrier thread.
- C. The virtual thread is woken by garbage collector threads.
- D. The database driver interrupts the ForkJoinPool worker thread.

*Answer*: **B**
*Explanation*: The JVM integrates virtual thread scheduling with native OS event loops to park and unpark threads efficiently without CPU-intensive polling.

#### Question 9: Sizing Fixed Thread Pools for CPU-bound Tasks
For a purely CPU-bound workload (such as image rendering), what is the optimal size for a fixed thread pool on a machine with 16 physical CPU cores?
- A. ~16 threads
- B. ~160 threads
- C. ~1,000 threads
- D. ~10,000 threads

*Answer*: **A**
*Explanation*: CPU-bound tasks keep processor cores active. Sizing the pool to match available physical cores minimizes context switching and cache invalidations, maximizing throughput.

#### Question 10: Custom User-Space Scheduler Mounts
In our custom `NanoThreadScheduler` simulation, how did we emulate carrier thread context switching when a file transfer operation blocked?
- A. By creating a new native OS thread for each file.
- B. By scheduling a wake-up callback with a scheduled executor and calling `Continuation.yield()`, which saved the stack state on the heap and freed the carrier thread.
- C. By calling `Thread.stop()` on the carrier thread.
- D. By synchronizing on the class monitor lock.

*Answer*: **B**
*Explanation*: The `NanoThread` simulation emulates Project Loom by using a scheduled executor to trigger resume callbacks and calling `Continuation.yield()` to suspend execution, freeing the carrier thread to run other tasks.

#### Question 11: Work-Stealing Queue Access Contention
In a `ForkJoinPool` configured with LIFO worker queues, worker threads pop tasks from the head of their own double-ended queue (deque) but steal from the tail of other workers' deques. What hardware-level memory behavior does this difference optimize?
- A. It minimizes OS-level kernel locks by allocating separate CPU registers.
- B. It limits CPU cache line invalidations and false sharing by keeping hot local tasks grouped on the worker's CPU core cache while external steal operations query distant tail elements, reducing L1/L2 cache contention.
- C. It increases the priority of garbage collection sweeps on queue nodes.
- D. It disables volatile memory fences.

*Answer*: **B**
- *Explanation*: In a work-stealing queue, the owner thread accesses the head of its deque in LIFO order, which maximizes cache locality (since the task was recently created and its data resides in cache). Other threads steal in FIFO order from the tail of the deque. Because the head and tail are far apart in memory, operations at the head and tail rarely update the same cache lines, avoiding cache coherence ping-pong (MESI protocol invalidations) and minimizing false sharing.

#### Question 12: ForkJoinPool Common Pool Sizing in Container Environments
A developer runs a microservice on a Kubernetes cluster. The container is configured with a CPU limit of 2 cores. Inside the application, the code executes a parallel stream, which defaults to the `ForkJoinPool.commonPool()`. If the physical server hosting the container has 64 CPU cores, what is the default parallelism level of the common pool, and how does this affect application performance?
- A. The parallelism defaults to 2 cores.
- B. The JVM queries the host system's hardware configuration, allocating 63 worker threads (64 cores - 1). This over-provisions threads inside the container, causing extreme CPU context switching, throttling penalties, and high response times.
- C. The parallelism is dynamically resized based on load.
- D. The common pool is disabled.

*Answer*: **B**
- *Explanation*: Traditionally, the JVM determines `Runtime.getRuntime().availableProcessors()` by querying the host OS. On older JDK versions or misconfigured containers, the JVM detects the full physical host (64 cores), initializing the common pool with 63 threads. When these 63 threads compete for the 2 physical cores assigned to the container, the container is heavily throttled by the OS scheduler, degrading performance. Modern container-aware JDKs resolve this, but the behavior can be overridden using `-Djava.util.concurrent.ForkJoinPool.common.parallelism=2`.

#### Question 13: CPU Register Memory Visibility and Volatile Fences
Two platform threads share a mutable variable: `private int status = 0;`. Thread A updates `status = 1`, and Thread B waits in a loop: `while(status == 0) {}`. Why can Thread B loop indefinitely on multi-core architectures without a `volatile` modifier or synchronization, even if Thread A successfully writes the change to memory?
- A. Because Thread A's execution was terminated by the OS scheduler.
- B. The CPU core running Thread B stores the initial value of `status` in its local register or L1 cache, and without a volatile read memory barrier, the hardware has no instruction to invalidate its cache line or query the updated main memory location.
- C. The JMM disables cross-core memory buses.
- D. The variable is garbage collected.

*Answer*: **B**
- *Explanation*: Without a `volatile` modifier, the Java Compiler and the CPU are free to optimize execution by caching the variable value in registers or L1 cache. The CPU core executing Thread B has no synchronization fence instruction (like `MFENCE` or memory reads) to check the coherence bus (MESI) or refresh its cache. Thread A's write might only reside in its core's store buffer, never being forced to main memory or broadcast to other caches.

#### Question 14: ThreadPoolExecutor custom RejectedExecutionHandler configurations
An enterprise application submits requests to a `ThreadPoolExecutor` using a `CallerRunsPolicy` rejection handler. Under a sudden database outage, all database threads block. What is the impact of the `CallerRunsPolicy` on the thread submitting the tasks?
- A. The executor throws a `RejectedExecutionException`, aborting the request.
- B. The executor discards the tasks silently, letting the request thread complete immediately.
- C. The thread that submitted the task executes the task itself within its own thread context. If the task blocks (e.g. database timeout), the submitter thread blocks, naturally throttling the incoming request pipeline.
- D. The executor spawns a temporary virtual thread.

*Answer*: **C**
- *Explanation*: The `CallerRunsPolicy` is a natural backpressure mechanism. When the thread pool queue is full and active threads are saturated, the task is executed by the caller thread that invoked `executor.submit()` or `execute()`. If that thread is busy executing the blocked task, it cannot submit new tasks, slowing down the producer and preventing memory starvation.

#### Question 15: Memory Stack Frame Layout in Continuations
How does the JVM handle local primitive variables and object reference pointers when saving a continuation's stack state onto the heap during a yield?
- A. It serializes all objects into JSON format and dumps them to the disk.
- B. It copies the execution stack frame, converting primitive variables to objects.
- C. It preserves the exact stack frames, separating primitive values from object references. Object reference pointers in the stack frame are registered as garbage collection roots (GC roots) to prevent the GC from reclaiming the objects while the continuation is parked.
- D. It copies references but discards primitives.

*Answer*: **C**
- *Explanation*: When a continuation yields, its call stack is moved to the heap. To ensure garbage collection correctness, the JVM must identify references within the heap-allocated stack frame. These references act as GC roots. If the GC sweeps the heap while the continuation is suspended, it traces these pointers to keep the objects alive. Primitive variables are kept as raw binary data in the stack frames.


### 9. Beginner-Friendly Visualization: The Whiteboard and Intercom Analogy

To understand why CPU cache coherence and the `volatile` keyword are necessary, let us step out of assembly-level memory barriers and use a simple office analogy.

Imagine a large bank office with:
- **A Master Ledger**: A physical book locked in the office vault (Main Memory). Writing to it is slow because you have to walk to the vault, unlock it, and write (Latency: 50–100ns).
- **Two Department Managers**: Manager A and Manager B (CPU Core 0 and Core 1).
- **Personal Whiteboards**: Each manager has a whiteboard in their own private office (L1/L2 Cache). Reading and writing to their own whiteboard is almost instant (Latency: sub-nanosecond).
- **The Task**: Both managers must keep track of a shared variable: `status`.

#### Scenario 1: The Out-of-Sync Whiteboards (No Volatile)
- Both managers walk to the vault, read `status = 0` from the master ledger, and write `status = 0` on their own local whiteboards. They are now sharing this information (MESI "Shared" state).
- Manager A decides to update the status to `1`.
- To save time, Manager A does not walk all the way to the vault immediately. Instead, they write `status = 1` on a sticky note on their desk (Store Buffer) and update their local whiteboard to `status = 1`.
- Manager A thinks the job is done.
- However, Manager B is still sitting in their own office, looking at their own whiteboard which still reads `status = 0`. Manager B makes decisions based on stale data because they have no idea Manager A made an update.
- Eventually, the sticky note is processed and written to the master ledger, but until then, the two offices are out of sync.

#### Scenario 2: The Intercom System (With Volatile)
By marking the `status` variable as `volatile` in Java, the JVM installs a strict **Intercom System** (Memory Barriers):
1. **Volatile Write (Shouting over the Intercom)**:
   - When Manager A updates `status = 1`, the volatile keyword prevents them from just leaving a sticky note on their desk.
   - Instead, the intercom immediately sounds across the office (Memory Barrier/Lock prefix).
   - Manager A shouts: *"I am updating status to 1! Erase your whiteboards!"*
   - This signal immediately forces Manager B's whiteboard to be wiped clean (MESI transitions to the "Invalid" state).
   - Manager A then walks to the vault and updates the master ledger.
2. **Volatile Read (Checking the Master Ledger)**:
   - When Manager B wants to read `status`, they look at their whiteboard and see it is empty (Invalid).
   - Because of the `volatile` read barrier, Manager B is forced to walk to the vault and read the updated value (`status = 1`) directly from the master ledger, writing it back onto their whiteboard.

#### Why is this necessary?
Without this intercom system, multi-core CPUs would suffer from severe memory visibility bugs where one core's updates are completely invisible to other cores, leading to infinite loops or inconsistent states. The `volatile` keyword coordinates caches at the hardware level, ensuring that updates are instantly broadcast and read fresh.


---

### 10. Under the Hood: How Java's internal Continuation Class freezes and thaws your stack

While we speak of virtual threads yielding and resuming, the heavy lifting inside the HotSpot JVM is managed by a private API called **Continuations** (primarily the `jdk.internal.vm.Continuation` class). 

A `Continuation` represents a program's execution state that can be suspended and resumed at will by the runtime. Every virtual thread wraps a `Continuation` instance.

Let us trace the precise step-by-step logic of how the JVM freezes (yields) and thaws (resumes) a continuation at the stack memory level.

#### 1. The Yielding Process (Freezing the Stack)
When a virtual thread executes a blocking socket read:
1. **The Interception**: The blocking code calls `LockSupport.park()`.
2. **The Yield Request**: `VirtualThread.park()` delegates to `Continuation.yield(SCOPE)`.
3. **Transition to Native**: The JVM transitions to C++ runtime execution inside the HotSpot VM.
4. **Copying Stack Frames**:
   - The JVM reads the current physical stack of the **Carrier Thread**.
   - It identifies all execution stack frames belonging to the virtual thread (everything above the virtual thread's run entry frame).
   - It copies these frames (including local primitive variables and object references) into a contiguous heap-allocated memory array called a **`StackChunk`**.
5. **Patching Pointer Addresses**:
   - Because stack frames are moved from physical memory to heap memory, memory address pointers change.
   - The JVM scans the copied frames and patches reference pointers to ensure they point to the correct locations on the heap.
6. **Clearing the Carrier**:
   - The JVM clears the carrier thread's physical stack frames associated with the virtual thread.
   - It resets the carrier's **Stack Pointer (SP)** and **Instruction Pointer (IP)** registers back to the ForkJoinPool scheduler loop.
   - The carrier thread is now free to execute another virtual thread.

#### 2. The Rescheduling Process (Thawing the Stack)
When the operating system notifies the JVM that the socket read has completed:
1. **Rescheduling**: The JVM marks the virtual thread as runnable and submits it to the `ForkJoinPool` worker queue.
2. **Mounting**: A carrier thread picks up the task and calls `Continuation.run()`.
3. **Transition to Native**: The JVM enters the thaw phase in C++.
4. **Restoring Stack Frames**:
   - The JVM reads the saved `StackChunk` from the heap.
   - It copies the stack frames back onto the physical stack of the carrier thread.
   - **Return Barrier Optimization**: To minimize copy overhead, the JVM does not copy the entire stack at once if it is deep. It copies only the top frames and sets a **Return Barrier**. When the methods return, the barrier triggers and thaws the next segment dynamically.
5. **Updating CPU Registers**:
   - The JVM updates the physical CPU registers: the Stack Pointer (SP) points to the newly restored stack frame, and the Instruction Pointer (IP) points to the assembly instruction directly following the `Continuation.yield()` call.
6. **Resume**: Execution resumes seamlessly.

#### Visual Memory Layout of a Context Switch
Below is a conceptual layout showing how stack frames shift between the physical carrier stack and the JVM heap during a yield-resume cycle:

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
