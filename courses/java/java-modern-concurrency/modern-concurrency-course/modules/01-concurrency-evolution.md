# Module 01: Introduction — The History of Java Concurrency

### Learning Objectives

- Trace the history and evolution of threading paradigms in Java from version 1.0 to Project Loom.
- Identify the hidden memory and CPU costs of platform threads, and predict OutOfMemoryError failures using the Thread Limit Explorer.
- Compare the trade-offs of sequential processing, raw parallel threads, thread pooling (ExecutorService), and asynchronous pipelines (CompletableFuture).
- Evaluate reactive programming's performance benefits against its six major architecture and cognitive drawbacks.

---

### Concept Explanation

#### 1. Java Is Made of Threads

In the Java Virtual Machine (JVM), threading is not an opt-in feature; it is the bedrock of the entire runtime system. Every Java application starts with at least one thread: the `main` thread, which executes the `public static void main(String[] args)` method.

Even a trivial program that prints "Hello, World!" is running inside a thread managed by the JVM scheduler. But the JVM is also running several critical background threads:

- **Garbage Collection (GC) Threads**: Perform automatic memory management (e.g., G1 GC or ZGC threads).
- **JIT Compiler Threads**: Compile Java bytecode to native machine code on the fly for hot paths.
- **Reference Handlers & Finalizers**: Clean up resources when objects are garbage collected.
- **Signal Dispatchers & Diagnostic Threads**: Process external VM signals and handle tools like `jstack` or `jcmd`.

You can inspect the executing thread using `Thread.currentThread()`:

```java
public class MainThreadDemo {
    public static void main(String[] args) {
        System.out.println("Current Thread Name: " + Thread.currentThread().getName());
        System.out.println("Thread ID: " + Thread.currentThread().threadId());
        System.out.println("Is Virtual: " + Thread.currentThread().isVirtual());
    }
}
```

##### Step-by-Step JVM Logic Walk: `MainThreadDemo`

1. **Accessing the Context (`Thread.currentThread()`)**: When the static call to `currentThread()` is executed, the JVM inspects the current execution context to return a reference to the active `Thread` object. At the JVM level, this reads from thread-local variables or registers associated with the running thread.
2. **Retrieving String Identifiers (`getName()`)**: The `getName()` method returns a string representing the thread's registration label. For the application's root entry point, the JVM automatically maps the value `"main"` to this thread.
3. **Inspecting Lifespans via IDs (`threadId()`)**: JDK 19 deprecates the classic `getId()` method in favor of `threadId()`. This returns a sequential positive `long` value representing the thread's unique registration key within the JVM thread manager.
4. **Validating Loom Mechanics (`isVirtual()`)**: A critical inspection method added in JDK 21. The scheduler checks the internal thread state block: if the thread is mapped 1-to-1 to an OS kernel thread, it returns `false`. If it is a lightweight JVM-heap-allocated virtual thread, it returns `true`.

---

#### 2. Thread as the Backbone

The Java platform is built around a thread-centric design where the JVM maps key developer tools directly to execution threads:

- **Exceptions and Diagnostics**: Every thread maintains its own private call stack. When an exception occurs, the JVM captures the call stack of the throwing thread. This trace details the nested method invocation path, providing an essential diagnostic trail.
- **Debuggers**: Debuggers attach to active threads, allowing you to pause execution, inspect frame local variables, and step into or out of frames for a specific thread context.
- **Profilers**: Profilers sample execution states by polling active threads to identify CPU bottlenecks and lock contention hotspots.

##### Multi-frame Exception Stack Trace Example

When an error is thrown, the stack trace follows the execution thread's call frame stack downward:

```text
Exception in thread "mcj-thread" com.example.InventoryUpdateException: Database Error: Unable to update inventory
    at com.example.CallStackDemo.updateDatabase(CallStackDemo.java:33)
    at com.example.CallStackDemo.checkInventory(CallStackDemo.java:26)
    at com.example.CallStackDemo.validateOrderDetails(CallStackDemo.java:22)
    at com.example.CallStackDemo.processOrder(CallStackDemo.java:18)
    at java.base/java.lang.Thread.run(Thread.java:1583)
Caused by: java.sql.SQLException: Database connection error
    at com.example.CallStackDemo.updateDatabase(CallStackDemo.java:31)
    ... 4 more
```

---

#### 3. Genesis of Java 1.0 Threads

Java 1.0 (released in 1996) stood out because it built multi-threading directly into the language syntax and standard library. Over three decades, the API for creating platform threads has evolved through four main styles:

1. **Subclassing `Thread` (Java 1.0)**: Direct extension of the `Thread` class.
2. **Implementing `Runnable` (Java 1.0)**: Separating the task definition from the execution mechanism. This is preferred as it avoids wasting Java's single inheritance slot.
3. **Anonymous Inner Class (Java 1.1)**: Inline task definition reducing boilerplate.
4. **Lambda Shorthand (Java 8)**: Modern, functional-style declaration.

##### Compilation of Thread Creation Styles

```java
package com.example.concurrency;

public class ThreadGenesisDemo {
    public static void main(String[] args) {
        // 1. Thread Subclassing
        Thread t1 = new WorkerThread("Worker-1");

        // 2. Runnable Implementation
        Thread t2 = new Thread(new TaskRunnable(), "Worker-2");

        // 3. Anonymous Inner Class
        Thread t3 = new Thread(new Runnable() {
            @Override
            public void run() {
                System.out.println("Anonymous class running: " + Thread.currentThread().getName());
            }
        }, "Worker-3");

        // 4. Lambda Expression
        Thread t4 = new Thread(() ->
            System.out.println("Lambda running: " + Thread.currentThread().getName()),
            "Worker-4"
        );

        t1.start();
        t2.start();
        t3.start();
        t4.start();
    }
}

class WorkerThread extends Thread {
    public WorkerThread(String name) {
        super(name);
    }
    @Override
    public void run() {
        System.out.println("Subclassed Thread running: " + getName());
    }
}

class TaskRunnable implements Runnable {
    @Override
    public void run() {
        System.out.println("Runnable task running: " + Thread.currentThread().getName());
    }
}
```

##### Deep Architectural & Memory Allocation Analysis of Thread Genesis

1. **Thread Subclassing (`WorkerThread`)**:
    - **JVM Execution Details**: By extending the native `java.lang.Thread` class, the class `WorkerThread` acts both as a target execution logic definition and as a JVM thread lifecycle management node. Instantiation allocates heap memory for the thread context and maps instance metadata parameters (priority, thread name, daemon flag).
    - **Core Architectural Drawback**: Java supports only single class inheritance. Extending `Thread` consumes the subclassing slot, preventing the class from inheriting from any other domain or architectural base classes.
2. **Runnable Implementation (`TaskRunnable` / Anonymous / Lambda)**:
    - **JVM Execution Details**: Decouples the work definition (`Runnable` interface) from the execution vehicle (`Thread` class). Instantiating `new Thread(Runnable)` creates a standard thread object on the heap that stores a delegate reference to the runnable target.
    - **Anonymous Inner Class Compilation**: Generates a physical helper class file (e.g., `ThreadGenesisDemo$1.class`) during compilation. At runtime, the class loader must load and register this class, which adds minor footprint overhead.
    - **Lambda Expression Compilation**: Compiles down to an `invokedynamic` (indy) instruction. Rather than generating separate nested class files, the JVM synthesizes a private static method encapsulating the execution logic and binds it dynamically using a bootstrap method, reducing allocation and compilation pollution.
3. **The `start()` Native Lifecycle Transition**:
    - Calling `t.start()` is the critical boundary. It invokes a native private JVM hook (`start0()`).
    - **Kernel Allocation**: The JVM requests the host OS kernel to create a native OS kernel thread descriptor.
    - **Memory Stack Binding**: The OS reserves physical stack memory (defaulting to 1-2 MiB in Linux/Mac configurations) outside the JVM heap.
    - **State Transition**: The thread's state changes from `NEW` to `RUNNABLE`. The OS scheduler places the thread in its active execution queues. Once a CPU core becomes available, the OS context-switches onto this thread, executing the target `run()` method.

---

#### 4. Hidden Costs of Platform Threads

Classic Java threads (now called **Platform Threads**) map 1-to-1 to operating system (OS) kernel threads. This model has several hidden scaling costs:

- **Memory Footprint**: By default, each platform thread reserves a fixed-size stack memory area outside the JVM heap (typically **1 to 2 MiB** in Linux/Unix environments). Spawning 5,000 threads immediately consumes up to 10 GiB of off-heap memory just for stack structures.
- **Context-Switch Overhead**: When the OS scheduler switches CPU execution from one thread to another, it must perform a context switch. This involves saving the current CPU register values, program counter, and stack pointer, and reloading the context of the next thread. Under high concurrency, CPU cores spend more time managing thread queues (thrashing) than executing actual business logic.
- **OS Thread Creation Limits**: Because threads are native resources, the host operating system limits the total number of threads a process can create. Once this limit (often around 10,000 to 16,000 threads on modern Linux environments) is reached, the JVM crashes with `java.lang.OutOfMemoryError: unable to create native thread`.

##### Deep Dive: The Anatomy of OS Context Switching and Kernel-Level Thread Scheduling

To understand why platform threads scale poorly, you must trace what happens within the operating system kernel during a thread context switch. In a 1-to-1 threading model, the JVM delegates thread management entirely to the OS scheduler (such as the CFS - Completely Fair Scheduler in Linux).

###### 1. Kernel Task Structures (The `task_struct`)

In Linux, every thread is represented by a `task_struct` structure in kernel space. This structure contains all metadata for the thread:

- **Process Identifiers (PID and TGID)**: TGID (Thread Group ID) represents the process ID, while PID represents the unique thread ID.
- **CPU Register State (thread_struct)**: Stores the saved state of the CPU hardware registers (e.g., RAX, RBX, RIP, RSP, CR3) when the thread is not executing.
- **Memory Descriptor (`mm_struct`)**: Points to the page tables that define the thread's virtual memory map. Sibling threads in the same process share the same `mm_struct`, meaning they share the same virtual address space.
- **Scheduling Class & Priority**: Determines the thread's placement in scheduling runqueues.

###### 2. The Context Switch Execution Lifecycle

When a thread blocks (e.g., waiting for socket I/O) or its time slice (quantum) expires, the kernel initiates a context switch:

```
[User Space]                             [Kernel Space]
Thread A (JVM code) ──Blocking I/O Call──► System Call Interrupt
                                                │
                                                ▼
                                           Save CPU Registers
                                           to Thread A Stack Frame
                                                │
                                                ▼
                                           Run Scheduler (CFS)
                                           Select Thread B
                                                │
                                                ▼
                                           Switch Address Space
                                           (Update CR3 Register)
                                                │
                                                ▼
                                           Restore CPU Registers
                                           from Thread B Stack Frame
                                                │
                                                ▼
Thread B (JVM code) ◄──Return from Interrupt───┘
```

1. **Trap to Kernel Space**: The CPU transitions from User Mode to Kernel Mode via a system call or hardware interrupt, pushing user-space registers onto the kernel stack.
2. **State Saving**: The kernel saves the remaining CPU registers (including the instruction pointer `RIP` and stack pointer `RSP`) into Thread A's `task_struct` memory block.
3. **Running the Scheduler**: The scheduler algorithm executes to select the next thread (Thread B) from its runqueues.
4. **Memory Map Switch (Address Space Transition)**:
    - If Thread B belongs to a _different_ process, the kernel must write Thread B's page directory address to the `CR3` register on x86 CPUs. This flushes the **TLB (Translation Lookaside Buffer)**, which caches virtual-to-physical memory mappings. Subsequent memory lookups incur heavy latency penalties (TLB misses) until the cache repopulates.
    - If Thread B belongs to the _same_ process (as is the case with Java threads), the address space is not switched, avoiding the TLB flush. However, other caches are still affected.
5. **CPU Register Restoration**: The kernel loads Thread B's saved register values from its `task_struct` back onto the physical CPU registers.
6. **Return to User Space**: The CPU switches back to User Mode, jumping to Thread B's restored instruction pointer (`RIP`) to resume execution.

###### 3. The Invisible Cost: Cache Pollution and Thrashing

While switching threads within the same process avoids TLB flushes, it still suffers from **CPU Cache Pollution**:

- Each CPU core contains L1 and L2 caches holding data frequently accessed by the running thread.
- When the scheduler switches Core 0 from Thread A to Thread B, Thread B begins accessing its own memory segments. This invalidates the L1/L2 cache lines populated by Thread A, triggering cache misses.
- If the OS switches threads too frequently (a state known as **Thrashing**), the CPU spends a massive percentage of its cycles waiting for memory access, degrading throughput significantly.

###### 4. Operating System Thread Creation and Allocation Limits

Spawning platform threads also hits strict system ceilings:

- **`max_user_processes` (`ulimit -u`)**: The total process/thread limit set per user.
- **`pid_max` (`/proc/sys/kernel/pid_max`)**: The absolute maximum number of thread/process descriptors the system can assign.
- **Virtual Memory Map Count (`/proc/sys/vm/max_map_count`)**: Every thread stack is allocated as a separate virtual memory mapping. If this counter is exceeded, thread allocation fails even if physical RAM is abundant.
- When any of these bounds are breached, the OS returns native error codes, causing the JVM to halt with an `OutOfMemoryError`.

---

#### 5. Thread-per-Request Model

Most classic Java web frameworks (e.g., Spring MVC running on Tomcat, Jetty, or UnderTow) rely on the **Thread-per-Request** model. Under this architecture, the servlet container manages a bounded thread pool. Each incoming HTTP request is assigned a single thread from the pool for its entire lifecycle.

```text
[Incoming HTTP Request]
         │
         ▼
[Servlet Container Pool (OS Threads)]
┌───────────────────┬───────────────────┬───────────────────┐
│ Thread-1 (Active) │ Thread-2 (Active) │ Thread-3 (Blocked)│
└─────────┬─────────┴─────────┬─────────┴─────────┬─────────┘
          │                   │                   │
          ▼                   ▼                   ▼
    [Controller]        [Controller]        [Blocked on DB Query]
 (Processes Request) (Processes Request) (OS thread remains frozen)
```

**The Scalability Bottleneck**: If your server's thread pool is limited to 200 threads, the application can handle at most 200 concurrent requests. If all 200 threads perform a blocking I/O operation (e.g., waiting for database queries or downstream REST APIs), the pool is exhausted. Incoming requests are queued, latency spikes, and the server eventually times out—even if system CPU utilization is near 0%.

---

#### 6. Parallel Execution Strategy

To minimize the time a thread remains blocked on independent I/O tasks, we can utilize a parallel execution strategy.

Imagine a credit calculation method:

```java
public Credit calculateCredit(Long personId) {
    var person = getPerson(personId);          // blocks ~200ms
    var assets = getAssets(person);            // blocks ~200ms
    var liabilities = getLiabilities(person);  // blocks ~200ms
    importantWork();                           // blocks ~200ms (CPU/delay)
    return calculateCredits(assets, liabilities); // blocks ~200ms
}
```

Executed sequentially, this takes `200ms * 5 = 1000ms`. However, because `getAssets()`, `getLiabilities()`, and `importantWork()` are independent of each other, they can be processed concurrently.

To collect results from multiple threads without advanced executors, developers historically used raw threads combined with thread-safe wrappers like `AtomicReference` to share state:

```java
import java.util.concurrent.atomic.AtomicReference;
import java.util.List;

public Credit calculateCreditWithUnboundedThreads(Long personId) throws InterruptedException {
    var person = getPerson(personId);

    var assetsRef = new AtomicReference<List<Asset>>();
    var liabilitiesRef = new AtomicReference<List<Liability>>();

    // Spawn unbounded threads for parallel I/O
    Thread t1 = new Thread(() -> assetsRef.set(getAssets(person)));
    Thread t2 = new Thread(() -> liabilitiesRef.set(getLiabilities(person)));
    Thread t3 = new Thread(this::importantWork);

    t1.start();
    t2.start();
    t3.start();

    // Block main thread waiting for tasks to finish
    t1.join();
    t2.join();

    var credit = calculateCredits(assetsRef.get(), liabilitiesRef.get());
    t3.join(); // Ensure independent background work finishes before returning

    return credit;
}
```

##### Deep Execution Mechanics: Memory Visibility and Thread Joining

1. **The Concurrency Mechanics of `AtomicReference`**:
    - **The Problem**: Threads `t1` and `t2` execute asynchronously, updating their local stacks. Because CPU cores utilize private L1/L2 caches, a local update made by a worker thread is not guaranteed to be visible to the main executing thread, resulting in **memory visibility anomalies**.
    - **The Solution**: `AtomicReference` internally encapsulates a volatile variable reference. Under the **Java Memory Model (JMM)**, writing to a volatile field triggers a happens-before relationship. The writing thread forces its local CPU cache to flush updates to shared L3 cache/main memory, while reading threads invalidate their private CPU caches and pull the fresh values from main memory, ensuring cache coherence (MESI protocol).
2. **Coordination via `Thread.join()`**:
    - Calling `t1.join()` blocks the main thread. It places the calling thread in the `WAITING` state, register-parking it inside the OS scheduling queue.
    - When the worker thread terminates, it executes a system-level notification (`notifyAll()`) on the thread object monitor. The JVM wakes the main thread, transitioning it back to `RUNNABLE`.
    - **Independent Off-loading (`t3.join()`)**: Notice that `t3` runs `importantWork()` which is independent of the credit aggregation calculation. We postpone `t3.join()` until _after_ the credit score is computed, letting `t3` finish in the background and avoiding blocking the main thread during intermediate calculation steps.

By running tasks in parallel, the total execution time drops to roughly **600ms** (the duration of sequential steps `getPerson` + parallel blocks + `calculateCredits`).

---

#### 7. ExecutorService

Spawning raw, unbounded threads on-demand (like `new Thread(...)`) is highly dangerous in production. If an application experiences a traffic spike, it can spawn thousands of threads simultaneously, crashing the system with an `OutOfMemoryError`.

Java 5 introduced the **Executor Framework** (`java.util.concurrent`) to decouple task submission from thread management. By utilizing `Executors.newFixedThreadPool(5)`, we bound the maximum concurrency:

```java
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

public Credit calculateCreditWithExecutor(Long personId, ExecutorService executor) throws Exception {
    var person = getPerson(personId);

    // Submit tasks to the bounded queue
    Future<List<Asset>> assetsFuture = executor.submit(() -> getAssets(person));
    Future<List<Liability>> liabilitiesFuture = executor.submit(() -> getLiabilities(person));
    executor.submit(() -> importantWork());

    // Retrieve results (blocking get() calls)
    List<Asset> assets = assetsFuture.get();
    List<Liability> liabilities = liabilitiesFuture.get();

    return calculateCredits(assets, liabilities);
}
```

##### Architectural Mechanics: Executor Pool Submissions & Blocking Future Resolution

1. **Task Submission (`submit()`)**:
    - When calling `executor.submit()`, the pool wraps the `Callable` task into a `FutureTask` implementation. The task is then offered to the pool's internal `BlockingQueue` (e.g., `LinkedBlockingQueue` or `SynchronousQueue`).
    - If the queue is bounded and full, the submit call may invoke the pool's `RejectedExecutionHandler`. In this example, using a `FixedThreadPool` queues tasks indefinitely, which introduces latency and memory accumulation risks under high load.
2. **Future State Transitions & `Future.get()` Blocking**:
    - A `FutureTask` transitions through states: `NEW` -> `COMPLETING` -> `NORMAL` (or `EXCEPTIONAL` / `CANCELLED`).
    - When the main thread calls `assetsFuture.get()`, it checks the state. If the task is still in `NEW` or `COMPLETING`, the calling thread registers itself on the task's waiting node queue and calls `LockSupport.park()`.
    - The OS suspends the calling thread, placing it in a sleep queue. Once a worker thread completes the task, it transitions the task state to `NORMAL`, writes the result value, and calls `LockSupport.unpark()` on the waiting threads, waking the main thread to retrieve the value.

---

#### 8. Remaining Challenges

While `ExecutorService` prevents system crashes by capping the thread count, it introduces new problems:

1. **Blocking on `Future.get()`**: The main thread submitting the tasks is still forced to block when calling `Future.get()`. If the worker pool is exhausted, threads block on queue entries, wasting system resources.
2. **False Sharing and Cache Coherence**: Modern CPUs use cache-coherence protocols (such as MESI) to ensure all CPU cores have a synchronized view of memory. When threads in an Executor pool are scheduled across different physical CPU cores:
    - If two threads modify different variables that happen to reside within the same **cache line** (typically 64 bytes), they trigger **==false sharing==**.
    - The CPU cores are forced to constantly invalidate their local caches and fetch data from the slower main memory, reducing execution throughput.
3. **Lack of Composability**: `Future` does not support functional composition. You cannot easily declare: _"Run Task A, then pass its output to Task B, and if either fails, trigger Task C"_ without writing complex blocking boilerplate.

---

#### 9. Fork/Join Pool

Introduced in Java 7, the `ForkJoinPool` is a specialized implementation of `ExecutorService` designed to maximize CPU core utilization for divide-and-conquer workloads.

##### Work-Stealing Algorithm

Unlike standard executors which share a single global blocking task queue, each worker thread in a `ForkJoinPool` maintains its own double-ended queue (**Deque**) of tasks.

- Worker threads pop tasks from the **head** of their own deque to process them locally, preserving **cache affinity**.
- If a worker thread finishes all local tasks and its deque becomes empty, it attempts to **steal** a task from the **tail** of another active thread's deque.

```text
[Thread-1 Deque]  [Head] -> [Task A] -> [Task B] -> [Tail] (Thread-1 pops from Head)
                                                      ▲
                                                      │ (Steals from Tail)
[Thread-2 Deque]  [Head] -> [Empty]                 ──┘    (Thread-2 is idle)
```

##### ForkJoinPool Basic Usage

```java
import java.util.concurrent.ForkJoinPool;

public class ForkJoinDemo {
    public static void main(String[] args) {
        ForkJoinPool pool = ForkJoinPool.commonPool();
        pool.submit(() -> {
            System.out.println("Executing inside ForkJoinPool: " + Thread.currentThread().getName());
        }).join();
    }
}
```

##### Internal Mechanics: Work-Stealing Queues and Cache Affinity

1. **The Shared Queue Bottleneck**: Standard `ThreadPoolExecutor` configurations rely on a single, shared thread-safe blocking queue. Every worker thread competes for this queue, introducing high lock contention and cache misses as threads modify the same head node.
2. **ForkJoinPool Per-Thread Deques**:
    - Each worker thread in a `ForkJoinPool` owns and manages a private, double-ended queue (**Deque**).
    - **Local FIFO/LIFO Operations**: When a worker spawns subtasks, it pushes them to the **head** of its local deque. To run tasks, the worker pops from the head of its own deque. Because the most recently created subtask's memory properties are hot in the CPU's local cache (L1/L2 caches), this maintains high **cache affinity**, avoiding expensive main memory re-reads.
3. **The Work-Stealing Protocol**:
    - If a worker's deque becomes empty, it enters the stealing loop.
    - It randomly selects another worker thread's deque and attempts to steal a task from the **tail** (LIFO/FIFO boundary). Stealing from the tail minimizes lock contention with the owner thread, which operates at the head.
    - The queue operations utilize Compare-And-Swap (CAS) instructions rather than object monitors, enabling lock-free thread coordination.

---

#### 10. CompletableFuture

To address the lack of composability in classic `Future` objects, Java 8 introduced `CompletableFuture`. It offers a fluent, declarative API to define asynchronous processing pipelines.

```java
import java.util.concurrent.CompletableFuture;
import static java.util.concurrent.CompletableFuture.*;

public CompletableFuture<Credit> calculateCreditAsync(Long personId) {
    // Pipeline execution: non-blocking configuration
    CompletableFuture<Void> work = runAsync(() -> importantWork());

    return supplyAsync(() -> getPerson(personId))
        .thenCompose(person -> {
            CompletableFuture<List<Asset>> assets = supplyAsync(() -> getAssets(person));
            CompletableFuture<List<Liability>> liabilities = supplyAsync(() -> getLiabilities(person));

            return assets.thenCombine(liabilities, (ast, liab) -> calculateCredits(ast, liab));
        });
}
```

##### Pipeline Execution & Stack Trace Muffling in CompletableFuture

1. **Monadic Composition (`thenCompose` vs `thenCombine`)**:
    - **`thenCompose()`**: Functions like flatMap. It chains dependent tasks sequentially: once `getPerson` completes, it uses its output to launch the asset/liability pipelines.
    - **`thenCombine()`**: Combines independent futures in parallel. It runs the asset and liability fetch tasks concurrently and applies `calculateCredits` as a callback once both complete.
2. **Context Hopping and Schedulers**:
    - Calls to `supplyAsync` without an explicit executor run tasks inside the global `ForkJoinPool.commonPool()`.
    - As callbacks complete, execution hops between pool threads. The thread executing `calculateCredits` might be completely different from the thread that initialized `getPerson`.
3. **The Lost Origin Stack Trace Pitfall**:
    - If an exception occurs inside `getAssets()`, the runtime captures the stack trace. However, because the task executes inside a detached worker thread, the stack trace origin (the thread that originally created the pipeline) is lost.
    - The resulting stack trace contains internal `CompletableFuture$AsyncSupply` run calls, making it difficult to debug the chronological order of execution.

##### Advantages

- **Fluent API**: Chaining handlers (`thenApply`, `thenCompose`, `thenCombineAsync`) avoids nesting callbacks.
- **Optimized Execution**: Built on top of the `ForkJoinPool` to leverage work-stealing scheduling.
- **Robust Exception Support**: Explicit recovery methods like `exceptionally()` and `handle()`.

##### Disadvantages

- **Steep Learning Curve**: Requires a complete shift from imperative to monadic thinking.
- **Blocking Boundaries**: Eventually, blocking method calls like `get()` or `join()` must be called to return to standard synchronous APIs.
- **Debugging Complexity**: Stack traces lose origin context across thread hops, making trace-point isolation in IDEs very difficult.

---

#### 11. Reactive Programming

Reactive programming goes a step further by treating execution as asynchronous, non-blocking data streams with built-in flow control (**backpressure**). In Java, this is represented by frameworks like Project Reactor and Spring WebFlux.

##### Spring WebFlux Mono Implementation

```java
import reactor.core.publisher.Mono;
import java.util.List;

public Mono<Credit> calculateCreditReactive(Long personId) {
    Mono<Void> importantWorkMono = Mono.fromRunnable(() -> importantWork());
    Mono<Person> personMono = Mono.fromSupplier(() -> getPerson(personId));

    Mono<List<Asset>> assetsMono = personMono.map(p -> getAssets(p));
    Mono<List<Liability>> liabilitiesMono = personMono.map(p -> getLiabilities(p));

    return importantWorkMono.then(
        Mono.zip(assetsMono, liabilitiesMono)
            .map(tuple -> calculateCredits(tuple.getT1(), tuple.getT2()))
        );
}
```

##### Step-by-Step Execution Walk of Reactive Pipelines

1. **The Lazy Assembly Phase**:
    - Instantiating `Mono.fromSupplier` or calling operations like `map()` does **not** execute any work. It merely builds a declarative representation of the data flow pipeline. In reactive programming: **Nothing happens until you subscribe**.
2. **The Subscription Flow**:
    - When `subscribe()` is called on the leaf node of the pipeline:
        - The subscriber sends an `onSubscribe(Subscription s)` signal upstream.
        - The subscription coordinates flow control via backpressure, requesting items via `s.request(n)`.
        - The upstream producer pushes items downstream using `onNext(T t)`.
        - The pipeline completes with `onComplete()` or fails with `onError(Throwable t)`.
3. **Execution Off-loading & Schedulers**:
    - Reactive frameworks use event loop pools (e.g., Netty event loops). If any task in this pipeline performs blocking database queries (like legacy blocking JDBC calls), it blocks the event loop, stalling the entire application.
4. **Mangled Stack Traces**:
    - Because work is divided into short callback segments executed across event loop thread pools, stack traces point to internal class handlers (like `MonoZip`, `FluxMapFuseable`) rather than the business methods, increasing debugging cognitive overhead.

##### The Six Drawbacks of Reactive Frameworks

1. **Steep Learning Curve**: Transitioning to reactive programming requires a massive shift in developer mindset to learn operators, schedulers, and streams.
2. **Cognitive Load**: Code becomes highly declarative, hard to parse visually, and changes the basic syntax of execution flow control (e.g., loops and try-catch).
3. **Debugging Difficulty**: Stack traces do not reflect chronological code order. They point to internal framework assembly lines rather than where the error occurred.
4. **Overcomplication Risk**: Teams often apply reactive patterns to simple CRUD services, adding needless layer wrappers.
5. **Potential Mismatch**: If database drivers (like classic JDBC) or libraries block, the reactive model's throughput benefits vanish completely.
6. **Vendor Lock-In**: Code is tightly coupled to specific library APIs (e.g., Reactor or RxJava), creating structural dependency.

---

### 10. A Historical Walk: How CPUs and OS Kernels Evolved to Handle Multitasking

To truly appreciate virtual threads, it helps to understand how operating systems and computer hardware evolved to run multiple programs at the same time. Concurrency is not a new idea, but the way we implement it has changed drastically over the last few decades.

#### 1. The Single-Tasking Era (e.g., MS-DOS)

In the early days of personal computing, operating systems could only run one program at a time:

- **How it worked**: When you started a program, it took complete control of the CPU, the memory, and all connected hardware. No other software could run until that program exited.
- **The Problem**: If a program froze or entered an infinite loop, the entire computer was locked. The user had to flip the physical power switch to restart. There was no concept of background tasks, music players running in the background, or real-time network listeners.

#### 2. Cooperative Multitasking (e.g., Windows 3.1, Early Mac OS)

To allow multiple programs to run together, OS designers introduced **cooperative multitasking**:

- **How it worked**: The operating system allowed multiple programs to reside in memory. However, the CPU could still only execute one program at a time. It was up to each program to voluntarily yield control back to the operating system using a command (such as `yield()`) so other programs could get a turn.
- **The Problem**: This system relied entirely on trust. If a single programmer wrote a poorly optimized loop or forgot to call the yield function, that program would hog the CPU indefinitely, freezing all other background applications. It was a fragile system where a single bad program could bring down the entire machine.

#### 3. Preemptive Multitasking (e.g., Windows 95/NT, Linux, Modern macOS)

To fix the fragility of cooperative systems, modern operating systems introduced **preemptive multitasking**:

- **How it worked**: The operating system kernel took absolute control of the CPU scheduling. It no longer trusted applications to yield. Instead, the kernel configured hardware timers to interrupt the active program every few milliseconds (a time slice or quantum). When the timer fired, the CPU executed a hardware interrupt, suspended the program, and forced it to yield control. The kernel then selected the next thread to run.
- **The Cost of Safety**: Preemptive multitasking is extremely robust. If a program freezes, the OS simply stops scheduling it, keeping the rest of the system responsive. However, suspending and restoring threads requires **OS Context Switching**:
    1. **Interrupt Entry**: The CPU switches from user-mode to kernel-mode.
    2. **Register Saving**: The kernel saves all physical CPU registers (Instruction Pointer, Stack Pointer, General Purpose Registers) into the thread's kernel data structure.
    3. **Page Table Swap**: The kernel swaps memory page tables to point to the next process's memory space, wiping CPU translation lookaside buffers (TLB).
    4. **Register Restoration**: The kernel reads the next thread's saved registers into the physical CPU and switches back to user-mode.
- This context-switching process is heavy. If you have thousands of active threads, the CPU spends more time switching between them than executing actual business logic.

#### 4. The Loop: Cooperative User-Space Scheduling (Virtual Threads)

Project Loom represents a return to cooperative scheduling, but with a crucial twist: instead of cooperative scheduling at the **operating system** level, it happens inside the **JVM user-space**:

- **How it works**: The JVM manages virtual threads. When a virtual thread runs, it mounts onto an OS thread (Carrier Thread). But when the virtual thread executes a blocking operation (such as reading a database socket), it does not block the OS carrier thread. Instead, the Java runtime intercepts the blocking call, saves the virtual thread's stack frames to the heap, and schedules another virtual thread on that carrier.
- **Why this is safe**: Unlike Windows 3.1, a frozen virtual thread cannot freeze your computer because the underlying carrier threads are still scheduled preemptively by the operating system. We get the performance of lightweight cooperative scheduling inside our application, while retaining the safety of preemptive scheduling at the OS level.

---

### 11. Beginner-Friendly Visualization: The Kitchen Chef Analogy of Thread Scheduling

To understand why traditional multi-threading behaves poorly under heavy load and how Project Loom fixes it, let us look at a simple kitchen analogy.

Imagine a restaurant kitchen tasked with preparing 10 complex meals (Requests) at the same time. Each meal requires:

1. Chopping vegetables (CPU work).
2. Waiting for water to boil (Blocking I/O).
3. Plating and garnishing (CPU work).

#### The Traditional Platform Thread Model (Multiple Chefs, Limited Stoves)

In traditional Java concurrent architectures:

- **The Stoves**: CPU cores. The kitchen only has 2 stoves.
- **The Chefs**: Platform threads. Each meal is assigned to exactly one chef.
- **The Process**:
    - You hire 10 chefs to cook the 10 meals concurrently.
    - Since there are only 2 stoves, only 2 chefs can cook at any moment.
    - To coordinate, the kitchen manager (OS kernel scheduler) blows a whistle every 10 seconds (time-slicing).
    - The active chef must stop immediately, pack up their knives, put their ingredients back in their bowls, and wipe down the station (Context switch: saving CPU registers and memory cache).
    - The next chef must unpack their ingredients, wash their hands, and start cooking.
    - **The Breakdown**: When a chef is waiting for water to boil, they are stuck at the stove doing nothing. If all chefs are waiting for water to boil, no cooking happens. If you hire 100 chefs to speed up work, they spend all their time packing and unpacking their bowls, bumping into each other, and the kitchen runs out of physical space (Thrashing and OutOfMemoryError).

#### The Cooperative Virtual Thread Model (Few Chefs, Sticky Notes)

Project Loom replaces this with a cooperative task-switching model:

- **The Chefs (Carrier Threads)**: You only hire 2 highly efficient chefs (matching your 2 physical stoves/CPU cores).
- **The Sticky Notes (Continuation Stack on the Heap)**: Instead of hiring more chefs, meals are written down on simple recipe pages (Virtual Threads) and stored on the counter (JVM heap).
- **The Process**:
    - Chef 1 starts chopping vegetables for Table 1.
    - When Table 1's water needs to boil, Chef 1 does not stand there waiting. They write a sticky note: _"Water boiling for Table 1 - step 3 is next"_, paste it on the pot, and immediately turn around to chop onions for Table 2.
    - When Table 1's water starts boiling, a buzzer sounds (OS event loop poller).
    - Whichever chef is currently free (Chef 1 or Chef 2) looks at the pot, reads the sticky note, and continues Table 1's meal from step 3.

This is the essence of virtual threads:

- **Platform threads** are the expensive physical chefs, so we keep their number small.
- **Virtual threads** are the cheap, paper sticky notes on the counter. We can have millions of sticky notes without running out of kitchen space!

---

#### 12. The Promise of Virtual Threads

Project Loom (released in JDK 21) introduces **Virtual Threads** to address platform thread limitations without requiring complex asynchronous or reactive models.

A **Virtual Thread** is a lightweight thread managed directly by the Java Virtual Machine, decoupled from physical OS threads. Instead of reserving 1-2 MiB of off-heap stack memory, virtual threads are stored as ordinary objects in the JVM heap, consuming only a few hundred bytes.

##### One-Line Migration

You can migrate existing codebases to virtual threads by replacing classic pooled executors with a virtual-thread-per-task executor:

```java
// Classic Platform Thread Pool
ExecutorService platformPool = Executors.newFixedThreadPool(200);

// Loom Virtual Thread Executor (One-line drop-in replacement)
ExecutorService virtualExecutor = Executors.newVirtualThreadPerTaskExecutor();
```

##### Key Mechanics

- **Seamless Integration**: Fully compatible with existing thread-blocking APIs.
- **JVM-Managed Scheduling**: Virtual threads are run on a pool of underlying carrier threads (platform threads) using a work-stealing `ForkJoinPool`.
- **Intelligent Yielding**: When a virtual thread performs blocking I/O (e.g., JDBC call or HTTP client socket block), the JVM automatically unmounts the virtual thread, saving its stack state on the heap, and freeing the carrier thread to execute other virtual threads.

---

### Key Diagrams & Mental Models

#### Platform Threads Model (1-to-1 Mapping)

```text
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   Java Thread   │       │   Java Thread   │       │   Java Thread   │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ OS Kernel Thread│       │ OS Kernel Thread│       │ OS Kernel Thread│  <-- Bounded resource (1MB stack)
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   CPU Core 1    │       │   CPU Core 2    │       │   CPU Core 3    │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

#### Virtual Threads Model (M-to-N Mapping)

```text
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Virt T1 │ │ Virt T2 │ │ Virt T3 │ │ Virt T4 │ │ Virt T5 │  <-- Lightweight Java objects on heap (BSON/JSON-like footprint)
└────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
     │           │           │           │           │
     └───────────┼───────────┼───────────┼───────────┘
                 ▼ (JVM Scheduler: ForkJoinPool)
         ┌───────────────┐       ┌───────────────┐
         │ Carrier Th 1  │       │ Carrier Th 2  │           <-- Platform Threads (OS Threads)
         └───────┬───────┘       └───────┬───────┘
                 │                       │
                 ▼                       ▼
         ┌───────────────┐       ┌───────────────┐
         │  CPU Core 1   │       │  CPU Core 2   │
         └───────────────┘       └───────────────┘
```

##### Deep Dive: Memory Fragmentation, Stack Scanning Pauses, and GC Interactions

When evaluating the architectural costs of platform threads, you must consider how they interact with operating system memory managers and JVM garbage collectors (GC). The overhead extends beyond simple RAM consumption to virtual memory fragmentation and garbage collection pause latency.

###### 1. Memory Mapping of Thread Stacks and Page Faults

When the JVM requests the OS to allocate a platform thread stack, it does not immediately reserve physical RAM bytes. Instead:

1. **Virtual Address Reservation**: The OS allocates a virtual memory range (e.g., 1 MiB) in the process address space.
2. **Page Table Entry (PTE) Creation**: The kernel updates page tables mapping these virtual addresses, but marks them as unallocated (demanding allocation).
3. **On-Demand Allocation (Page Faults)**: When the thread executes and writes data to its call stack frame, the CPU triggers a hardware **Page Fault**. The kernel intercepts this fault, allocates a physical 4 KiB memory page (or page frame), updates the page table, and resumes execution.

- **Resource Lock-in**: Once a physical page is allocated to a thread stack, it remains pinned in memory for the thread's lifetime. The OS cannot page it out to disk, resulting in memory fragmentation.

###### 2. Virtual Memory Address Space Fragmentation

Spawning and destroying thousands of platform threads fragments the process address space:

- Every thread stack requires a contiguous virtual memory segment.
- As threads are created and destroyed, virtual memory is allocated and released in chunks. Over time, the address space becomes fragmented, leaving small gaps of unallocated space.
- If the JVM attempts to allocate a new thread stack, it may fail with `OutOfMemoryError` even if the total free memory is abundant, simply because no single contiguous 1 MiB address segment is available.

###### 3. GC Root Scanning Pauses (The STW Bottleneck)

Garbage collectors (like G1 GC) identify reachable heap objects by tracing paths from **GC Roots**. Active thread stacks are primary GC roots:

```
[GC Roots Scanning Phase (Stop-the-World)]
        ├── Thread 1 Stack ──► Scan all execution frames ──► Identify Heap Refs
        ├── Thread 2 Stack ──► Scan all execution frames ──► Identify Heap Refs
        │   ...
        └── Thread N Stack ──► Scan all execution frames ──► Identify Heap Refs
```

- **Stack Scanning**: During a GC pause, the collector must scan the call stack frames of _every active thread_ to locate object reference pointers.
- **Scaling Bottleneck**: In applications with 10,000 platform threads, scanning 10,000 stacks (each potentially containing dozens of execution frames) creates significant CPU overhead, increasing Stop-the-World (STW) pause times.
- **Safepoints**: Before GC can scan roots, all threads must reach a **Safepoint** (a state where threads pause execution). Coordinating safepoints across thousands of active threads introduces scheduling latency, leading to "Safepoint Cleanup" pauses.

###### 4. Project Loom's GC Optimization

Loom's virtual thread stack architecture resolves these GC and memory issues:

- **No Virtual Memory Fragmentation**: Since virtual thread stack frames reside on the JVM heap as ordinary objects, they do not require contiguous virtual address space allocations from the OS, eliminating off-heap address space fragmentation.
- **Decoupled Root Scanning**:
    - The GC only needs to scan the active **Carrier Threads** as GC roots. If you have 16 carrier threads on a 16-core system, only 16 stacks are scanned during the STW root scanning phase.
    - The millions of suspended virtual thread stacks residing on the heap are scanned concurrently by the GC during its normal marking phase (using concurrent marking algorithms), keeping STW pauses low and predictable regardless of thread count.

---

### Hands-On Code — Lab 1.1: Thread Limit Explorer

#### Overview

In this lab, you will write a program that continually spawns platform threads and parks them. The goal is to reach your host operating system's thread ceiling and observe the resulting `OutOfMemoryError`.

#### Implementation (`ThreadLimitTest.java`)

```java
package com.example.concurrency.lab1;

import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.locks.LockSupport;

public class ThreadLimitTest {
    public static void main(String[] args) {
        var threadCount = new AtomicInteger(0);

        System.out.println("Attempting to spawn platform threads...");
        try {
            while (true) {
                // Define the task to run inside the thread
                Runnable task = () -> {
                    threadCount.incrementAndGet();
                    // Park keeps the thread alive and blocked without consuming CPU cycles
                    LockSupport.park();
                };

                // Create a classic Platform Thread
                Thread thread = new Thread(task);
                thread.start();
            }
        } catch (OutOfMemoryError error) {
            // Print the total threads created before crash
            System.err.println("CRASHED! Reached thread limit: " + threadCount.get());
            error.printStackTrace();
        }
    }
}
```

##### Deep Execution Mechanics: JVM Native Boundaries and OS Limits

1. **VM-Level Allocation Hook (`Thread.start0`)**:
    - When `thread.start()` is called, the JVM delegates to a native C++ function (`JVM_StartThread` which maps to `Thread.start0`). This function interfaces with the operating system APIs (e.g., `pthread_create` on Linux/POSIX, `CreateThread` on Windows).
2. **The Off-Heap Stack Footprint**:
    - Every platform thread requires a dedicated memory stack allocated outside the JVM garbage-collected heap. This stack is used to track method execution frames, local parameters, and return pointers.
    - Government variables like `-Xss` define the stack size per thread. With a default stack size of **1 MiB**, spawning 16,000 threads reserves **16 GiB of raw memory** off-heap. If the physical RAM or swap space is exhausted, the OS kernel rejects additional allocations.
3. **OS Kernel Constraints**:
    - The thread ceiling is also governed by kernel configuration safety limits:
        - On Linux: `/proc/sys/kernel/threads-max` (system-wide thread max), `/proc/sys/vm/max_map_count` (maximum memory map areas), and user process limits (`ulimit -u`).
        - Once these native limits are hit, the OS returns error code `EAGAIN`. The JVM catches this status and immediately throws `java.lang.OutOfMemoryError: unable to create native thread`.

````

#### Verification & Analysis
Run the class from your command line:
```bash
java com.example.concurrency.lab1.ThreadLimitTest
````

##### Expected Output

On common configurations, the execution output will look like this:

```text
Reached thread limit: 16363
java.lang.OutOfMemoryError: unable to create native thread: possibly out of memory or process/resource limits reached
    at java.base/java.lang.Thread.start0(Native Method)
    at java.base/java.lang.Thread.start(Thread.java:1526)
    at com.example.concurrency.lab1.ThreadLimitTest.main(ThreadLimitTest.java:21)
```

##### Explanation

1. **The OutOfMemoryError**: This error is thrown by the native VM (`Thread.start0`) when it requests the operating system kernel to allocate a new thread resource, and the OS rejects the call.
2. **OS Resource Limits**: The limit is governed by the OS configuration:
    - On Linux systems, it is dictated by shell limits (`ulimit -u` for max user processes) and kernel parameters (`/proc/sys/kernel/threads-max`).
    - Each thread reserves memory stack space (typically 1-2 MiB). Spawning 16,000 threads consumes ~16-32 GiB of off-heap system memory. If you hit physical memory limits, the system fails to allocate.

---

### Hands-On Code — Lab 1.2: Sequential vs Parallel Credit Calculator

#### Overview

You will implement a `CreditCalculatorService` that calculates a customer's credit score. The score is computed using mock methods representing calls to a database and a REST API, each introducing a simulated 200ms delay. You will write four execution styles and profile their durations using an `ExecutionTimer` utility class.

#### Implementation

##### 1. The Models (`Models.java`)

```java
package com.example.concurrency.lab2;

import java.util.List;

record Credit(double score) {}
record Person(Long id, String name) {}
record Asset(String type, double value) {}
record Liability(String type, double amount) {}
```

##### 2. The Execution Timer (`ExecutionTimer.java`)

```java
package com.example.concurrency.lab2;

import java.util.concurrent.Callable;

public class ExecutionTimer {
    public static <T> T measure(String label, Callable<T> task) throws Exception {
        long startTime = System.nanoTime();
        try {
            return task.call();
        } finally {
            long endTime = System.nanoTime();
            long duration = (endTime - startTime) / 1_000_000;
            System.out.println(label + " Execution Time: " + duration + " ms");
        }
    }
}
```

##### 3. The Calculator Service (`CreditCalculatorService.java`)

```java
package com.example.concurrency.lab2;

import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

public class CreditCalculatorService {

    // --- Mock I/O Delayed Methods ---

    private Person getPerson(Long personId) {
        simulateDelay(200);
        return new Person(personId, "Jane Doe");
    }

    private List<Asset> getAssets(Person person) {
        simulateDelay(200);
        return List.of(
            new Asset("Real Estate", 500000),
            new Asset("Stocks", 150000)
        );
    }

    private List<Liability> getLiabilities(Person person) {
        simulateDelay(200);
        return List.of(
            new Liability("Home Loan", 300000),
            new Liability("Auto Loan", 25000)
        );
    }

    private void importantWork() {
        simulateDelay(200);
    }

    private Credit calculateCredits(List<Asset> assets, List<Liability> liabilities) {
        simulateDelay(200);
        double totalAssets = assets.stream().mapToDouble(Asset::value).sum();
        double totalLiabilities = liabilities.stream().mapToDouble(Liability::amount).sum();
        double score = (totalAssets - totalLiabilities) / 1000.0;
        return new Credit(score);
    }

    private void simulateDelay(int ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new CompletionException(e);
        }
    }

    // --- Four Styles of Execution ---

    // 1. Sequential: Runs every method call one after another. Expected: ~1000ms
    public Credit calculateCredit(Long personId) {
        var person = getPerson(personId);
        var assets = getAssets(person);
        var liabilities = getLiabilities(person);
        importantWork();
        return calculateCredits(assets, liabilities);
    }

    // 2. Raw Threads: Spawns unbounded platform threads using AtomicReference. Expected: ~600ms
    public Credit calculateCreditWithUnboundedThreads(Long personId) throws InterruptedException {
        var person = getPerson(personId);

        var assetsRef = new AtomicReference<List<Asset>>();
        var liabilitiesRef = new AtomicReference<List<Liability>>();

        Thread t1 = new Thread(() -> assetsRef.set(getAssets(person)));
        Thread t2 = new Thread(() -> liabilitiesRef.set(getLiabilities(person)));
        Thread t3 = new Thread(this::importantWork);

        t1.start();
        t2.start();
        t3.start();

        t1.join();
        t2.join();

        var credit = calculateCredits(assetsRef.get(), liabilitiesRef.get());
        t3.join();

        return credit;
    }

    // 3. ExecutorService: Uses a bounded fixed thread pool. Expected: ~630ms
    public Credit calculateCreditWithExecutor(Long personId) throws Exception {
        try (ExecutorService executor = Executors.newFixedThreadPool(5)) {
            var person = getPerson(personId);

            Future<List<Asset>> assetsFuture = executor.submit(() -> getAssets(person));
            Future<List<Liability>> liabilitiesFuture = executor.submit(() -> getLiabilities(person));
            executor.submit(this::importantWork);

            return calculateCredits(assetsFuture.get(), liabilitiesFuture.get());
        }
    }

    // 4. Virtual Threads: Uses newVirtualThreadPerTaskExecutor. Expected: ~600ms
    public Credit calculateCreditWithVirtualThread(Long personId) throws Exception {
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            var person = getPerson(personId);

            Future<List<Asset>> assetsFuture = executor.submit(() -> getAssets(person));
            Future<List<Liability>> liabilitiesFuture = executor.submit(() -> getLiabilities(person));
            executor.submit(this::importantWork);

            return calculateCredits(assetsFuture.get(), liabilitiesFuture.get());
        }
    }
}
```

##### 4. The Main Demo (`CreditCalculatorDemo.java`)

```java
package com.example.concurrency.lab2;

public class CreditCalculatorDemo {
    public static void main(String[] args) throws Exception {
        CreditCalculatorService service = new CreditCalculatorService();
        Long personId = 101L;

        // Warm up and test Sequential
        ExecutionTimer.measure("Sequential", () -> service.calculateCredit(personId));

        // Test Unbounded Raw Threads
        ExecutionTimer.measure("Raw Threads", () -> service.calculateCreditWithUnboundedThreads(personId));

        // Test Executor Service
        ExecutionTimer.measure("ExecutorService (ThreadPool)", () -> service.calculateCreditWithExecutor(personId));

        // Test Virtual Threads
        ExecutionTimer.measure("Virtual Threads", () -> service.calculateCreditWithVirtualThread(personId));
    }
}
```

---

### Hands-On Code — Lab 1.3: CompletableFuture Pipeline

#### Overview

You will implement a pipeline using `CompletableFuture` to compute the credit score. You will design it asynchronously, but deliberately execute the blocking `.get()` call at the runtime boundary to inspect where the blocking occurs and understand its limitations.

#### Implementation (`CompletableFutureCalculator.java`)

```java
package com.example.concurrency.lab3;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import static java.util.concurrent.CompletableFuture.*;

public class CompletableFutureCalculator {

    public static void main(String[] args) throws Exception {
        CompletableFutureCalculator calc = new CompletableFutureCalculator();

        long startTime = System.currentTimeMillis();

        // Construct the async execution graph
        CompletableFuture<Credit> creditFuture = runAsync(() -> calc.importantWork())
            .thenCompose(voidArg -> supplyAsync(() -> calc.getPerson(1L)))
            .thenCompose(person -> {
                CompletableFuture<List<Asset>> assets = supplyAsync(() -> calc.getAssets(person));
                CompletableFuture<List<Liability>> liabilities = supplyAsync(() -> calc.getLiabilities(person));

                return assets.thenCombine(liabilities, (ast, liab) -> calc.calculateCredits(ast, liab));
            });

        System.out.println("Pipeline assembled. Non-blocking setup completed in: "
                + (System.currentTimeMillis() - startTime) + " ms");

        // Deliberately calling blocking get() at execution boundary to resolve value
        Credit credit = creditFuture.get();

        System.out.println("Credit score retrieved: " + credit.score());
        System.out.println("Total time: " + (System.currentTimeMillis() - startTime) + " ms");
    }

    // --- Mock delayed tasks ---
    private Person getPerson(Long id) { simulateDelay(200); return new Person(id, "John"); }
    private List<Asset> getAssets(Person p) { simulateDelay(200); return List.of(new Asset("Bond", 50000)); }
    private List<Liability> getLiabilities(Person p) { simulateDelay(200); return List.of(new Liability("Tax", 5000)); }
    private void importantWork() { simulateDelay(200); }
    private Credit calculateCredits(List<Asset> a, List<Liability> l) {
        simulateDelay(200);
        return new Credit((a.get(0).value() - l.get(0).amount()) / 1000.0);
    }
    private void simulateDelay(int ms) {
        try { Thread.sleep(ms); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }

    // Core records definitions
    record Credit(double score) {}
    record Person(Long id, String name) {}
    record Asset(String type, double value) {}
    record Liability(String type, double amount) {}
}
```

##### Line-by-Line Execution Analysis: `CompletableFutureCalculator`

1. **Pipeline Instantiation (`runAsync()`)**:
    - `runAsync(() -> calc.importantWork())` launches a task executing `importantWork()` asynchronously. Since no executor is passed, it utilizes a thread from `ForkJoinPool.commonPool()`. This method returns `CompletableFuture<Void>`.
2. **Sequential Chaining (`thenCompose()`)**:
    - `.thenCompose(voidArg -> supplyAsync(() -> calc.getPerson(1L)))`: Once `importantWork()` completes, this method passes the `Void` result to a function that launches `getPerson(1L)` in another asynchronous thread, returning `CompletableFuture<Person>`.
3. **Parallel Forking & Merging (`thenCombine()`)**:
    - Inside the second `thenCompose()`, when the `Person` object becomes available, the program launches two parallel calculations: `getAssets(person)` and `getLiabilities(person)`.
    - `assets.thenCombine(liabilities, ...)` aggregates their outputs. As soon as both `assets` and `liabilities` futures resolve, the combining function runs `calculateCredits(ast, liab)` to produce a single final `Credit` object.
4. **Non-blocking Setup Verification**:
    - The print statement: `"Pipeline assembled. Non-blocking setup completed in: ..."` executes almost instantly (0-2 ms). This proves that defining a `CompletableFuture` pipeline does not block the caller thread; it merely registers callbacks in memory.
5. **Blocking Value Resolution (`get()`)**:
    - Calling `creditFuture.get()` forces the main thread to stop and enter the `WAITING` state until the combined computation finishes. This blocking call is necessary at the execution boundary to fetch the score and display it.

---

### Common Pitfalls & Anti-Patterns

#### Pitfall: Calling `Thread.run()` Instead of `Thread.start()`

A common mistake when beginning Java concurrent programming is invoking `run()` directly on a thread object instead of `start()`.

##### Broken Code

```java
package com.example.concurrency.pitfall;

public class ThreadRunAntiPattern {
    public static void main(String[] args) {
        Thread thread = new Thread(() -> {
            System.out.println("Task running in thread: " + Thread.currentThread().getName());
        });

        // BUG: Calling run() runs the logic sequentially inside the MAIN thread, NOT in a new thread!
        thread.run();
    }
}
```

##### Output

```text
Task running in thread: main
```

##### Corrected Code

```java
package com.example.concurrency.pitfall;

public class ThreadStartPattern {
    public static void main(String[] args) {
        Thread thread = new Thread(() -> {
            System.out.println("Task running in thread: " + Thread.currentThread().getName());
        });

        // CORRECT: Calling start() triggers VM-level initialization and executes code asynchronously
        thread.start();
    }
}
```

##### Code Analysis: Thread Startup Mechanics

1. **Calling `run()` Directly (Anti-pattern)**:
    - When calling `thread.run()`, the Java compiler interprets this as a standard method invocation on a helper object. The execution jumps directly to the thread object's `run()` method _on the current thread_ (e.g., `main`), without allocating operating system structures. The calling thread blocks until `run()` completes.
2. **Calling `start()` (Correct Pattern)**:
    - Calling `thread.start()` executes a native synchronized registration sequence. The JVM checks if the thread has already started (throwing `IllegalThreadStateException` if it has) and invokes the OS-specific native wrapper (`start0()`). This allocates native kernel threads, sets up execution frames, and initiates the target method asynchronously in a new scheduling thread context.

##### Output

```text
Task running in thread: Thread-0
```

---

### Summary

1. **Thread-Centric VM Architecture**: In Java, everything from simple main execution loops to system-level garbage collection runs on JVM threads. Exceptions, debugging tracepoint steps, and profiles map directly to individual thread stack bounds.
2. **Platform Thread Scaling Boundaries**: Platform threads act as thin Java wrappers for native operating system kernel threads. Their 1-2 MiB size bounds concurrency scaling, causing standard servers to crash under heavy load.
3. **Evolution of Concurrency Frameworks**: As applications transitioned to non-blocking I/O requirements, Java evolved from raw threads to bounded pools (`ExecutorService`), work-stealing scheduling (`ForkJoinPool`), fluent pipelines (`CompletableFuture`), and full reactive models (WebFlux).
4. **Project Loom & Virtual Threads**: Project Loom decouples threads from OS resources. By replacing platform threads with lightweight, JVM-heap-allocated virtual threads, Java developers write synchronous, readable code that scales natively to millions of concurrent tasks.

---

### 5. Reactive Programming vs. Imperative Virtual Threading

Before the finalization of Project Loom (Virtual Threads), the primary alternative for scaling Java microservices beyond the platform thread limit was **Reactive Programming** (exemplified by Project Reactor, WebFlux, and RxJava).

To make informed architectural decisions, developers must understand the mechanical trade-offs between reactive event loops and virtual-thread-based imperative concurrency.

#### The Reactive Reactor Model

Reactive programming shifts the paradigm from thread-bound execution to asynchronous event-driven streams.

- **Event Loops**: A tiny pool of event loop threads (typically matching CPU cores) processes all network and system events asynchronously.
- **Publishers and Subscribers**: Data flows are represented as `Publisher` streams (`Mono` for 0-1 elements, `Flux` for 0-N elements) that are not evaluated until a `Subscriber` listens to them.
- **Non-Blocking I/O**: Instead of blocking a thread waiting for I/O, the program registers callback handlers. When the OS finishes the network I/O, it notifies the event loop, which executes the corresponding callback stage.

##### Reactive Backpressure Mechanics

In reactive streams, backpressure prevents a fast producer from overwhelming a slow consumer. The subscriber requests a specific number of items using `Subscription.request(n)`. The publisher is bound to emit no more than $n$ elements until the subscriber calls `request` again. This avoids heap buffer overflows.

#### The Costs of Reactive Architectures

While highly performant, reactive architectures introduce significant operational complexity:

1. **Developer Cognitive Load**: Writing code using functional operators (`flatMap`, `zip`, `switchMap`) requires a complete shift in thinking compared to sequential Java.
2. **Lost Stack Traces**: Because executions are broken into callback closures dispatched across shared event loops, standard exception stack traces lose their context, making debugging in production extremely difficult.
3. **ThreadLocal Incompatibility**: Standard ThreadLocal storage is tied to physical threads. In a reactive flow, different stages of a request execute on different event loop threads, rendering ThreadLocal variables useless.
4. **Library Fragmentation**: Legacy blocking libraries (such as JDBC, Hibernate, and standard HTTP clients) cannot be used within reactive event loops without freezing the event loop itself, requiring developers to adopt specialized reactive libraries (like R2DBC).

#### Loom's Solution: Reconciling Scalability and Readability

Virtual threads eliminate this trade-off by moving the non-blocking state machine from user-space libraries (like Project Reactor) into the JVM runtime itself.
Developers write standard, imperative blocking code using standard loops, try-catch blocks, and linear execution flows. When a blocking database or HTTP call is made, the JVM unmounts the virtual thread. The underlying system gets all the performance and resource efficiency of a reactive event loop, while the developer writes and debugs clean, readable code.

| Feature                | Reactive Model (WebFlux/Reactor)    | Imperative Model (Virtual Threads)    |
| :--------------------- | :---------------------------------- | :------------------------------------ |
| **Programming Style**  | Functional, declarative streams     | Imperative, sequential                |
| **Concurrency Unit**   | Events / Callbacks                  | Lightweight Virtual Threads           |
| **Exception Handling** | Operator-level `.onErrorResume()`   | Standard Java `try-catch` blocks      |
| **Stack Traces**       | Disassociated and truncated         | Linear, full trace preserved          |
| **Context Storage**    | Reactive Subscriber Context map     | Standard Scoped Values / ThreadLocal  |
| **Blocking Safety**    | Starves event loops (dangerous)     | Yields carrier thread (safe)          |
| **Library Ecosystem**  | Limited (requires reactive drivers) | Unlimited (fully backward-compatible) |

#### Code Comparison: Reactive Stream vs. Imperative Flow

Below is a comparative showcase of the same business task: fetching user profiles, querying their account balances, and fetching transaction logs from three separate downstream APIs.

##### 1. The Reactive Approach (WebFlux)

```java
package com.example.concurrency;

import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

public class ReactiveUserService {

    private final WebClient webClient;

    public ReactiveUserService(WebClient.Builder builder) {
        this.webClient = builder.baseUrl("https://api.example.com").build();
    }

    public Mono<UserProfile> fetchUserProfileReactive(String userId) {
        return webClient.get().uri("/users/" + userId)
                .retrieve()
                .bodyToMono(User.class)
                .flatMap(user -> {
                    Mono<Double> balanceMono = webClient.get().uri("/accounts/" + user.accountId() + "/balance")
                            .retrieve()
                            .bodyToMono(Double.class)
                            .onErrorReturn(0.0);

                    Mono<String> logsMono = webClient.get().uri("/logs/" + userId)
                            .retrieve()
                            .bodyToMono(String.class)
                            .onErrorReturn("No logs");

                    return Mono.zip(balanceMono, logsMono)
                            .map(tuple -> new UserProfile(user, tuple.getT1(), tuple.getT2()));
                });
    }

    record User(String userId, String accountId, String name) {}
    record UserProfile(User user, double balance, String logs) {}
}
```

##### 2. The Imperative Virtual Thread Approach

```java
package com.example.concurrency;

import org.springframework.web.client.RestClient;
import java.util.concurrent.*;

public class ImperativeUserService {

    private final RestClient restClient;
    private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();

    public ImperativeUserService(RestClient.Builder builder) {
        this.restClient = builder.baseUrl("https://api.example.com").build();
    }

    public UserProfile fetchUserProfileImperative(String userId) {
        try {
            // 1. Fetch user data synchronously on the virtual thread
            User user = restClient.get().uri("/users/" + userId)
                    .retrieve()
                    .body(User.class);

            if (user == null) {
                throw new IllegalArgumentException("User not found: " + userId);
            }

            // 2. Fetch balance and logs in parallel using virtual threads
            Future<Double> balanceFuture = executor.submit(() -> fetchBalance(user.accountId()));
            Future<String> logsFuture = executor.submit(() -> fetchLogs(userId));

            // 3. Blocks synchronously here, yielding carrier threads until ready
            double balance = balanceFuture.get(2, TimeUnit.SECONDS);
            String logs = logsFuture.get(2, TimeUnit.SECONDS);

            return new UserProfile(user, balance, logs);

        } catch (Exception e) {
            // Standard linear stack trace preserved
            throw new RuntimeException("Failed to construct user profile", e);
        }
    }

    private double fetchBalance(String accountId) {
        try {
            return restClient.get().uri("/accounts/" + accountId + "/balance")
                    .retrieve()
                    .body(Double.class);
        } catch (Exception e) {
            return 0.0; // Graceful degradation
        }
    }

    private String fetchLogs(String userId) {
        try {
            return restClient.get().uri("/logs/" + userId)
                    .retrieve()
                    .body(String.class);
        } catch (Exception e) {
            return "No logs";
        }
    }

    record User(String userId, String accountId, String name) {}
    record UserProfile(User user, double balance, String logs) {}
}
```

##### Line-by-Line Logic Walkthrough: Concurrency Model Evolution

1. **Reactive Pipeline Assembly**:
    - In the reactive implementation, the `flatMap` and `Mono.zip` statements build an execution tree of async callbacks.
    - When `fetchUserProfileReactive` returns, no I/O has actually occurred; the request is only submitted to the network once subscribed to.
    - If an error happens inside `Mono.zip`, finding which publisher failed requires injecting specialized tracing agents, as the calling context has long since returned.

2. **Imperative Sequential Mapping**:
    - In the virtual thread model, the code is executed line-by-line. The REST query at line 17 executes synchronously, blocking the virtual thread.
    - The JVM unmounts the virtual thread, freeing the carrier.
    - Once the user data returns, the virtual thread resumes and launches two concurrent tasks using `executor.submit()`. This maps naturally to structured patterns.
    - The `future.get(2, TimeUnit.SECONDS)` calls block the calling thread, yielding carriers, which is fully safe and clean. Any exceptions are caught in a single try-catch block, generating a complete, single-thread stack trace showing the exact path from client endpoint call down to query invocation.

---

### Knowledge Check

#### Question 1: Thread Startup Mechanics

Which of the following occurs if you execute `thread.run()` directly instead of `thread.start()`?

- A. A new platform thread is created and run.
- B. The thread logic executes synchronously inside the calling thread.
- C. The JVM immediately throws a `java.lang.IllegalThreadStateException`.
- D. The thread logic is queued inside the common ForkJoinPool.

_Answer_: **B**
_Explanation_: Calling `run()` directly is a standard method invocation on a Java helper object. The code executes synchronously on the stack frame of the calling thread (e.g. `main`), without registering a native OS thread structure. Calling `start()` is required to execute native thread creation (`start0()`) and establish a separate scheduling path.

#### Question 2: Platform Thread Memory Footprint

What is the default stack footprint allocated for a Java platform thread outside the JVM heap?

- A. ~100 bytes
- B. ~1 to 2 KiB
- C. ~1 to 2 MiB
- D. Up to 512 MiB

_Answer_: **C**
_Explanation_: In modern operating systems and Java Virtual Machines, each native platform thread allocates a virtual memory stack segment (typically 1-2 MiB size determined by the `-Xss` JVM argument). This reservation is allocated off-heap, capping scalability to a few thousand threads before system RAM is exhausted.

#### Question 3: ForkJoinPool Work-Stealing

How does the `ForkJoinPool` work-stealing algorithm optimize task execution compared to standard ExecutorServices?

- A. It moves tasks to disks if physical RAM is fully allocated.
- B. Idle threads steal tasks from the tail of busy threads' deques, maintaining local queue cache affinity.
- C. It allocates JVM heap spaces only to virtual threads executing blocking DB processes.
- D. It limits thread stacks to 2 KiB dynamically on runtime exceptions.

_Answer_: **B**
_Explanation_: ForkJoinPool assigns a double-ended work queue (deque) to each worker thread. Workers process tasks from the head of their deque to maintain CPU cache line registers, while idle threads steal tasks from the tail of busy workers' deques to maximize core utilization.

#### Question 4: Operating System Scheduling vs Virtual Thread Scheduling

How does OS pre-emptive thread scheduling differ from JVM virtual thread cooperative scheduling?

- A. The OS schedules virtual threads directly using hardware timers.
- B. The OS uses pre-emptive time slicing (scheduling quanta) on platform threads, whereas the JVM schedules virtual threads cooperatively by yielding execution when encountering blocking I/O calls.
- C. The JVM pre-empts virtual threads using OS hardware interrupts.
- D. There is no difference; they utilize the same kernel task scheduler.

_Answer_: **B**

- _Explanation_: Operating systems schedule platform threads pre-emptively, interrupting execution when a thread's time slice (quantum) expires. Virtual threads are scheduled cooperatively by the JVM: they run on carrier threads until they reach a blocking boundary (such as I/O or lock acquisition), at which point they yield execution, allowing the JVM to assign another virtual thread.

#### Question 5: ForkJoinPool FIFO vs LIFO Work Deques

What is the scheduling behavior of the work queues inside the ForkJoinPool used by virtual threads?

- A. They run strictly in LIFO order to maximize CPU register caching.
- B. They operate in FIFO (First-In, First-Out) mode to ensure fairness and prevent task starvation in request processing.
- C. They schedule tasks randomly.
- D. They run in priority queue order sorted by stack frame sizes.

_Answer_: **B**

- _Explanation_: While standard ForkJoinPool configurations (like parallel streams) use LIFO (Last-In, First-Out) work queues to maximize cache local registers, the ForkJoinPool scheduler used by virtual threads operates in FIFO mode. This ensures that web request tasks are scheduled fairly in submission order, preventing starvation of early requests.

#### Question 6: Memory Visibility in Unbounded Threads

A developer runs a loop on an unbounded thread that checks a boolean flag `stopSignal`. If another thread modifies the flag to `true`, the loop continue executing indefinitely. Why?

- A. The loop thread is starved by the OS scheduler.
- B. Without volatile markers or synchronization memory barriers, the thread caches the variable in CPU registers, and CPU cache coherence protocols (MESI) are not triggered to reload the value.
- C. The JVM garbage collector reclaims the flag variable.
- D. Native threads cannot communicate state changes.

_Answer_: **B**

- _Explanation_: Under the Java Memory Model, compiler optimizations allow threads to cache fields in registers or CPU local caches. Without a volatile marker or synchronization boundary, no memory fence instruction is generated, and there is no happens-before relation to force the thread to write or reread the variable from main memory, resulting in visibility bugs.

#### Question 7: SynchronousQueue vs LinkedBlockingQueue in ExecutorService

Under high request spikes, how does an `ExecutorService` configured with `SynchronousQueue` behave compared to one configured with `LinkedBlockingQueue`?

- A. `SynchronousQueue` buffers up to 10,000 tasks.
- B. `SynchronousQueue` acts as a direct handoff mechanism: if no thread is available to consume the task, it rejects or spawns a new thread immediately, whereas `LinkedBlockingQueue` queue tasks indefinitely, growing heap allocations.
- C. `LinkedBlockingQueue` rejects tasks instantly if all core threads are busy.
- D. They exhibit identical queueing behaviors.

_Answer_: **B**

- _Explanation_: `SynchronousQueue` has a capacity of zero. It acts as a rendezvous point between a producer and a consumer thread. If all threads are busy, it cannot accept new tasks and triggers rejection or thread expansion, preventing task queuing latencies. `LinkedBlockingQueue` retains tasks in an unbounded list, accumulating memory footprints and latency spikes.

#### Question 8: CompletableFuture Exceptional Pipelines

Why do exceptions thrown inside nested `CompletableFuture` stages often lose their original call stack trace metadata?

- A. CompletableFuture deletes exceptions to optimize execution speed.
- B. Tasks run asynchronously across different threads in the Common ForkJoinPool; since the exception occurs in a separate thread stack than the parent thread, the exception must be manually joined, separating the original context.
- C. Project Loom bans exceptions in async pipelines.
- D. None of the above.

_Answer_: **B**

- _Explanation_: In async callback chains, execution jumps across thread boundaries. When a stage throws an exception, the thread stack that caused the error is discarded, and the exception is wrapped in `CompletionException`. Unless handled with `.exceptionally()` or `.handle()`, tracing the origin through typical logs is difficult because the caller's thread is not in the stack trace.

#### Question 9: CPU-Bound vs I/O-Bound Scheduling

Why is scaling CPU-bound computations with virtual threads considered an anti-pattern?

- A. Virtual threads cannot perform mathematical operations.
- B. CPU-bound tasks do not block on I/O, preventing the virtual thread from yielding. The carrier thread remains pinned, neutralizing Loom's scalability benefits.
- C. CPU-bound calculations trigger stack overflows.
- D. The compiler rejects the code.

_Answer_: **B**

- _Explanation_: Virtual thread scaling relies on threads yielding execution during blocking calls. CPU-bound tasks run continuously on the CPU cores, keeping the carrier thread pinned. Since no yield points occur, virtual threads act as platform threads but add scheduling overhead.

#### Question 10: ThreadGroup Deprecation and Security Boundaries

What restriction does the virtual thread architecture place on the classic Java `ThreadGroup` API?

- A. Virtual threads throw exceptions if added to the default ThreadGroup.
- B. Virtual threads belong to a single, immutable, system-level thread group named `"VirtualThreads"`. Any attempt to assign them to a custom group via builder constructors is ignored.
- C. ThreadGroups are completely removed from the JDK.
- D. Only administrative threads can create ThreadGroups.

_Answer_: **B**

- _Explanation_: To simplify execution structures and prevent security leaks, all virtual threads are restricted to the immutable system group `"VirtualThreads"`. Developers cannot customize the group membership of virtual threads, which is part of JEP 444.

#### Question 11: Volatile Fields and Memory Reordering

Which hardware-level instruction behavior does the `volatile` keyword prevent to ensure happens-before memory consistency?

- A. OS pre-emptive task swaps.
- B. CPU core hardware context switching.
- C. Compile-time and runtime out-of-order instruction reordering, and CPU local cache delays by emitting memory barrier (fence) instructions.
- D. Heap memory serialization.

_Answer_: **C**

- _Explanation_: The `volatile` modifier ensures that reads and writes are not reordered by the compiler or CPU. It generates memory fence instructions (e.g., `lock addl` on x86) that force local cache writes to main memory and invalidate peer core caches, maintaining JMM consistency boundaries.

#### Question 12: unable to create new native thread

When running a traditional platform thread benchmark, the process crashes with `OutOfMemoryError: unable to create new native thread`. What system limit has been breached?

- A. The maximum size of the JVM heap (-Xmx).
- B. The OS-level thread count descriptor limit (e.g., `/proc/sys/kernel/threads-max` or `max user processes` in Linux), or system virtual memory limits due to thread stack reservations.
- C. The CPU register capacity.
- D. The network socket descriptor pool.

_Answer_: **B**

- _Explanation_: Every platform thread requires a native OS thread. If the JVM exhausts virtual memory segment mapping (due to stack sizing allocation limits) or hits OS-level thread count ceilings, the kernel refuses the allocation request, triggering the native thread allocation crash.

#### Question 13: CPU Cache line thrashing

How does CPU cache false sharing affect multithreaded application performance, and how was it solved prior to virtual threads?

- A. Threads overwrite heap pointers, solved by garbage collection.
- B. Independent variables updated by separate threads reside on the same CPU cache line (typically 64 bytes). Modifying one invalidates the cache line for other cores, causing performance-degrading cache misses. It was solved via padding or the `@Contended` annotation.
- C. Threads exhaust JVM stack frames, solved by increasing stack limits.
- D. None of the above.

_Answer_: **B**

- _Explanation_: Cache lines are the smallest unit of memory transferred to CPU caches. If two threads read/write distinct variables situated on the same cache line, writes by one core force invalidation of the cache line on the other core (MESI cache coherence). This invalidation loop degrades performance. It was solved by adding padding bytes or using the `@Contended` annotation to force alignment.

---
