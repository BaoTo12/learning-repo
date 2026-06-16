# Modern Concurrency in Java: Virtual Threads, Structured Concurrency, and Beyond

## Preface

Welcome to the ultimate guide on Modern Concurrency in Java. This course is designed specifically for mid-to-senior Java developers who need to bridge the gap between traditional thread-based concurrency models and the modern virtual-thread-based paradigms introduced in JDK 21 and beyond (Project Loom).

### Who This Course Is For
This guide is written for engineers who are already familiar with standard Java concurrency concepts (e.g., `Runnable`, `Thread`, `synchronized`, and `ExecutorService`) but want to:
- Learn why classic Java platform threads cannot scale to meet modern high-throughput application requirements.
- Understand the mechanics under the hood of JVM-managed virtual threads and continuations.
- Write readable, maintainable, and declarative concurrent code using Structured Concurrency and Scoped Values.
- Successfully migrate existing systems (such as Spring Boot or Quarkus services) to utilize virtual threads safely.

### System Requirements
To run the examples and complete the labs in this course, you will need:
- **Java Development Kit (JDK) 21 or later** (LTS). Note that some advanced preview features like Structured Concurrency and Scoped Values require passing compiler and runtime flags to enable preview APIs.
- **An IDE** (such as IntelliJ IDEA, Eclipse, or VS Code) configured for Java 21.
- Maven or Gradle for dependency management if you want to run the Spring WebFlux comparison modules.

### Running Preview Features
To compile and run code that uses preview features (such as `StructuredTaskScope` and `ScopedValue`), compile using:
```bash
javac --enable-preview --release 21 YourClass.java
```
And run using:
```bash
java --enable-preview YourClass
```

---

## Module 1: Introduction — The History of Java Concurrency

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

---

#### 4. Hidden Costs of Platform Threads
Classic Java threads (now called **Platform Threads**) map 1-to-1 to operating system (OS) kernel threads. This model has several hidden scaling costs:
- **Memory Footprint**: By default, each platform thread reserves a fixed-size stack memory area outside the JVM heap (typically **1 to 2 MiB** in Linux/Unix environments). Spawning 5,000 threads immediately consumes up to 10 GiB of off-heap memory just for stack structures.
- **Context-Switch Overhead**: When the OS scheduler switches CPU execution from one thread to another, it must perform a context switch. This involves saving the current CPU register values, program counter, and stack pointer, and reloading the context of the next thread. Under high concurrency, CPU cores spend more time managing thread queues (thrashing) than executing actual business logic.
- **OS Thread Creation Limits**: Because threads are native resources, the host operating system limits the total number of threads a process can create. Once this limit (often around 10,000 to 16,000 threads on modern Linux environments) is reached, the JVM crashes with `java.lang.OutOfMemoryError: unable to create native thread`.

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
    Thread t3 = new Thread(() -> importantWork());
    
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

---

#### 8. Remaining Challenges
While `ExecutorService` prevents system crashes by capping the thread count, it introduces new problems:
1. **Blocking on `Future.get()`**: The main thread submitting the tasks is still forced to block when calling `Future.get()`. If the worker pool is exhausted, threads block on queue entries, wasting system resources.
2. **False Sharing and Cache Coherence**: Modern CPUs use cache-coherence protocols (such as MESI) to ensure all CPU cores have a synchronized view of memory. When threads in an Executor pool are scheduled across different physical CPU cores:
   - If two threads modify different variables that happen to reside within the same **cache line** (typically 64 bytes), they trigger **false sharing**.
   - The CPU cores are forced to constantly invalidate their local caches and fetch data from the slower main memory, reducing execution throughput.
3. **Lack of Composability**: `Future` does not support functional composition. You cannot easily declare: *"Run Task A, then pass its output to Task B, and if either fails, trigger Task C"* without writing complex blocking boilerplate.

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

##### The Six Drawbacks of Reactive Frameworks
1. **Steep Learning Curve**: Transitioning to reactive programming requires a massive shift in developer mindset to learn operators, schedulers, and streams.
2. **Cognitive Load**: Code becomes highly declarative, hard to parse visually, and changes the basic syntax of execution flow control (e.g., loops and try-catch).
3. **Debugging Difficulty**: Stack traces do not reflect chronological code order. They point to internal framework assembly lines rather than where the error occurred.
4. **Overcomplication Risk**: Teams often apply reactive patterns to simple CRUD services, adding needless layer wrappers.
5. **Potential Mismatch**: If database drivers (like classic JDBC) or libraries block, the reactive model's throughput benefits vanish completely.
6. **Vendor Lock-In**: Code is tightly coupled to specific library APIs (e.g., Reactor or RxJava), creating structural dependency.

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

#### Verification & Analysis
Run the class from your command line:
```bash
java com.example.concurrency.lab1.ThreadLimitTest
```

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

### Knowledge Check
1. **Which of the following occurs if you execute `thread.run()` directly instead of `thread.start()`?**
   - A. A new platform thread is created and run.
   - B. The thread logic executes synchronously inside the calling thread.
   - C. The JVM immediately throws a `java.lang.IllegalThreadStateException`.
   - D. The thread logic is queued inside the common ForkJoinPool.
   
2. **What is the default stack footprint allocated for a Java platform thread outside the JVM heap?**
   - A. ~100 bytes
   - B. ~1 to 2 KiB
   - C. ~1 to 2 MiB
   - D. Up to 512 MiB
   
3. **How does the `ForkJoinPool` work-stealing algorithm optimize task execution compared to standard ExecutorServices?**
   - A. It moves tasks to disks if physical RAM is fully allocated.
   - B. Idle threads steal tasks from the tail of busy threads' queues, maintaining local queue cache affinity.
   - C. It allocates JVM heap spaces only to virtual threads executing blocking DB processes.
   - D. It limits thread stacks to 2 KiB dynamically on runtime exceptions.

##### Answers
1. **B** - `run()` does not invoke thread system resources allocation; it is a regular method call executing in the main calling thread.
2. **C** - Each platform thread registers a stack pointer reservation of typically 1-2 MiB inside the system off-heap virtual memory bounds.
3. **B** - Work-stealing optimizes concurrency using a per-thread double-ended queue. Workers pop tasks locally from the head (cache affinity) and steal tasks from the tails of other deques when idle.

---

## Module 2: Understanding Virtual Threads

### Learning Objectives
- Differentiate between Platform and Virtual threads in memory footprint, scheduling mechanics, and blocking tolerance.
- Construct virtual threads using all four supported factory and builder APIs, managing the lifecycle of daemon-terminated executions.
- Formulate throughput estimations using Little's Law, and write benchmarks to verify scaling performance under high latency.
- Analyze the mechanics of pinning and context-switching, and resolve carrier-thread blocking by replacing object monitors with reentrant locking structures.
- Evaluate the risk of ThreadLocal variables in virtual threads and deploy custom diagnostics (JFR, JVM flags, MXBeans, and structured dumps) to monitor runtime performance.

---

### Concept Explanation

#### 1. Two Kinds of Threads
With the introduction of Project Loom in JDK 21, Java supports two distinct types of threads:

1. **Platform Threads**: Classic Java threads (`java.lang.Thread`). Each platform thread is a thin wrapper around a native operating system kernel thread (1:1 mapping). The OS kernel schedules execution. Platform threads are resource-heavy, reserving ~1-2 MiB stack allocations off-heap.
2. **Virtual Threads**: Lightweight, JVM-managed threads (M:N mapping). Instead of mapping directly to OS threads, millions of virtual threads share a small pool of underlying platform threads called **Carrier Threads**. The JVM manages scheduling via a specialized `ForkJoinPool` configured in FIFO/async mode.

##### Virtual Threads Mounting Mechanics
```text
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Virtual Th 1 │ │ Virtual Th 2 │ │ Virtual Th 3 │ │ Virtual Th 4 │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │                │
       ▼ (JVM schedules)▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│              JVM Scheduler: FIFO async ForkJoinPool             │
└───────────────────────┬─────────────────┬───────────────────────┘
                        │                 │ (Mounts / Unmounts)
                        ▼                 ▼
             ┌───────────────────┐ ┌───────────────────┐
             │  Carrier Thread 1 │ │  Carrier Thread 2 │  (Platform threads mapped 1:1 to OS)
             └─────────┬─────────┘ └─────────┬─────────┘
                       ▼                     ▼
             ┌───────────────────┐ ┌───────────────────┐
             │   OS Kernel Th 1  │ │   OS Kernel Th 2  │
             └───────────────────┘ └───────────────────┘
```

---

#### 2. Key Differences from Platform Threads
- **Extremely Lightweight**: Virtual threads start with an initial stack size of only a few hundred bytes stored directly in the garbage-collected JVM heap. They dynamically grow and shrink, avoiding system-level allocation limits.
- **JVM-Scheduled**: The OS scheduling queue is bypassed. The JVM's ForkJoinPool schedules virtual threads, allocating them to carrier threads as resources allow.
- **Blocking-Tolerant**: When a virtual thread executes a blocking system call (e.g., database query or sleep), the JVM automatically unmounts the virtual thread, copies its execution stack frames back to the heap, and frees the carrier thread to execute other virtual threads.
- **Seamless Integration**: A virtual thread is represented by the same `java.lang.Thread` class. Code that runs in a platform thread can run in a virtual thread without restructuring.

---

#### 3. Setting Up Your Environment
To compile and execute code containing virtual threads, you need **JDK 21 or later**. 
- You can manage multiple JVM versions using **SDKMAN** (Software Development Kit Manager):
  ```bash
  sdk list java
  sdk install java 21.0.2-open
  sdk use java 21.0.2-open
  ```
- *Note*: Advanced Loom features (such as Structured Concurrency and Scoped Values) are preview features as of JDK 21-25. To compile and run them, you must add the `--enable-preview` flag to your `javac` and `java` commands.

---

#### 4. Creating Virtual Threads — All Four Ways
Java provides four primary APIs to instantiate and execute virtual threads:

1. **`Thread.startVirtualThread(Runnable)`**: Spawns and starts a virtual thread immediately.
2. **`Thread.ofVirtual().start(Runnable)`**: Fluent builder configuration that starts the thread immediately.
3. **`Thread.ofVirtual().unstarted(Runnable)`**: Configures a thread without starting it immediately, allowing deferred execution.
4. **`Executors.newVirtualThreadPerTaskExecutor()`**: Returns an `ExecutorService` that spawns a new virtual thread for each submitted task.

##### Compilation of Virtual Thread Creation
```java
package com.example.concurrency;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

public class CreationStylesDemo {
    public static void main(String[] args) throws Exception {
        Runnable task = () -> System.out.println("Running in virtual thread: " 
                + Thread.currentThread().threadId());

        // Style 1: Direct instantiation and start
        Thread t1 = Thread.startVirtualThread(task);
        t1.join();

        // Style 2: Fluent builder with immediate start
        Thread t2 = Thread.ofVirtual().start(task);
        t2.join();

        // Style 3: Fluent builder, deferred execution
        Thread t3 = Thread.ofVirtual().unstarted(task);
        t3.start();
        t3.join();

        // Style 4: ExecutorService integration
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            Future<?> future = executor.submit(task);
            future.get();
        }
    }
}
```

> [!WARNING]
> **Virtual Threads are Daemon Threads**: All virtual threads are configured as daemon threads by default, and their daemon status cannot be changed. If the JVM's main thread exits, it does not wait for active daemon threads to complete. You must explicitly block the main thread (e.g., using `thread.join()` or try-with-resources on the virtual executor) to prevent premature termination.

---

#### 5. Thread API Changes
Project Loom introduces several runtime adjustments to the `Thread` API:
- **New Methods**:
  - `Thread::isVirtual`: Returns `true` if the thread is managed by the JVM.
  - `Thread.sleep(Duration)` and `Thread::join(Duration)`: Support modern time units.
  - `Thread::threadId`: Replaces the deprecated `getId()` method.
- **ThreadGroup Constraints**: All virtual threads belong to a single, immutable global `ThreadGroup` named `"VirtualThreads"`.
- **Immutable State**: Calling `setPriority(int)` or `setDaemon(boolean)` on a virtual thread does not change its priority (always `NORM_PRIORITY`) or daemon status (always `true`).

---

#### 6. Throughput and Scalability via Little's Law
Little's Law is a fundamental principle of queuing systems, stating that the average number of active items in a stable system ($N$) is the product of the average throughput ($\lambda$) and the average response time ($d$):
$$\lambda = \frac{N}{d}$$

- In a platform thread pool, $N$ is capped by the maximum pool size (typically 100 to 1,000 threads) due to memory constraints. Since we cannot easily decrease latency ($d$) for I/O operations, throughput ($\lambda$) is severely limited.
- Virtual threads allow us to scale $N$ into the millions because their memory footprint is minimal. By increasing $N$ without reducing $d$, we achieve massive throughput scaling.

##### Benchmark Experiment
Let's consider processing 10,000 tasks, each simulating 500ms of I/O latency ($d = 0.5s$):
- **Virtual Threads**: Spawns 10,000 threads. Concurrency ($N$) is nearly 10,000. Throughput $\lambda = 10,000 / 0.5 = 20,000 \text{ tasks/sec}$. Total time is ~500ms.
- **Fixed Thread Pool (1,000 threads)**: Cap $N = 1000$. Throughput $\lambda = 1000 / 0.5 = 2000 \text{ tasks/sec}$. Total time is ~5,000ms.
- **Fixed Thread Pool (100 threads)**: Cap $N = 100$. Throughput $\lambda = 100 / 0.5 = 200 \text{ tasks/sec}$. Total time is ~50,000ms.

---

#### 7. How Virtual Threads Work Under the Hood
Understanding Project Loom's internals is critical for optimizing high-throughput codebases:

1. **Heap-Allocated Stack Frames**: Unlike platform threads which utilize a continuous, fixed block of native memory, virtual thread execution stacks are stored as linked objects in the JVM garbage-collected heap.
2. **Carrier Pool Execution**: When scheduled, the JVM mounts the virtual thread onto an available platform thread (its **Carrier Thread**) belonging to a dedicated worker `ForkJoinPool` configured in FIFO async mode.
3. **Yielding Continuation**: When a virtual thread encounters a blocking call, it enters `LockSupport.park()`. Instead of blocking the native OS thread, Loom executes a **continuation yield** (`yieldContinuation()`). The JVM copies the thread's stack frames back to the heap and frees the carrier thread.
4. **JVM Read/Write Pollers**: The blocked operation is registered with native JVM pollers (such as `epoll` on Linux, `kqueue` on macOS, or `wepoll` on Windows). When the underlying network socket or channel becomes ready, the poller notifies the JVM, which re-parks and schedules the virtual thread onto an available carrier thread to resume execution.

---

#### 8. Simplifying Async Aggregation
In classical programming, fetching aggregate data (e.g., calling two API services in parallel and merging their outputs) requires complex reactive chaining or nested blocking calls. With virtual threads, calling `.get()` on a `Future` is cheap because it merely unmounts the virtual thread without locking the underlying system resources:

```java
package com.example.concurrency;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

public class AsyncAggregationDemo {
    
    public String generatePhrase() throws Exception {
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            // Submit two concurrent I/O calls
            Future<String> adjectiveFuture = executor.submit(this::fetchAdjective);
            Future<String> nounFuture = executor.submit(this::fetchNoun);
            
            // Blocking here is cheap; the executing virtual thread unmounts from its carrier
            String adjective = adjectiveFuture.get();
            String noun = nounFuture.get();
            
            return adjective + " " + noun;
        }
    }
    
    private String fetchAdjective() throws InterruptedException {
        Thread.sleep(200); // Simulate network latency
        return "modern";
    }
    
    private String fetchNoun() throws InterruptedException {
        Thread.sleep(200); // Simulate network latency
        return "java";
    }
}
```

---

#### 9. Structured Concurrency Teaser
To prevent orphaned threads and coordinate child tasks safely, JDK introduces the `StructuredTaskScope` API. This preview API ensures that if one task fails, all other subtasks within the scope are automatically cancelled:

```java
package com.example.concurrency;

import java.util.concurrent.StructuredTaskScope;

public class StructuredTeaser {
    public static void main(String[] args) {
        // StructuredTaskScope implements AutoCloseable to enforce task containment
        try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
            StructuredTaskScope.Subtask<String> s1 = scope.fork(() -> "Result A");
            StructuredTaskScope.Subtask<String> s2 = scope.fork(() -> "Result B");
            
            scope.join();           // Join all subtasks
            scope.throwIfFailed();  // Propagate exceptions if any subtask failed
            
            System.out.println(s1.get() + " & " + s2.get());
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

---

#### 10. Rate Limiting with Semaphores
Because virtual threads are cheap, we do not limit concurrency by capping thread pool sizes. However, downstream services (such as databases or third-party APIs) still have finite capacity limits.

To protect these systems, you must control access using **Semaphores**. A `Semaphore` coordinates permits, allowing a set number of virtual threads to access the resource concurrently. If all permits are acquired, subsequent threads block and safely unmount from their carrier threads.

> [!CAUTION]
> **Semaphore Pitfall**: In Java, any thread can call `release()` on a semaphore, even if it has not acquired a permit. This can artificially inflate the permit count, causing rate-limiting policies to fail. Always use the **acquire-before-try / release-in-finally** pattern to ensure permits are accurately managed.

---

#### 11. Pinning (Limitation)
**Pinning** is a major constraint in Project Loom where a virtual thread becomes "stuck" to its carrier platform thread. While pinned, the virtual thread cannot unmount. If it performs a blocking I/O operation, the underlying carrier thread is also blocked, wasting OS resources.

##### Causes of Pinning
1. **Synchronized Blocks/Methods (Pre-JDK 24)**: If a virtual thread acquires an object monitor (`synchronized`), it cannot unmount from its carrier thread. 
2. **Native Methods / Foreign Functions**: Calls to native code (using JNI or the Foreign Function API) run outside the control of the JVM scheduler, locking the carrier thread.

##### JEP 491 (JDK 24)
As of **JDK 24**, JEP 491 refactored the JVM monitor implementation so that virtual threads can unmount while inside `synchronized` blocks in most scenarios. However, native method pinning remains unavoidable.

---

#### 12. ThreadLocal Conundrum
Using `ThreadLocal` variables inside virtual threads is a common cause of memory degradation:
- Under classic environments, having 200 platform threads means only 200 copies of `ThreadLocal` variables exist.
- Under Loom, spawning 1,000,000 virtual threads means the JVM creates 1,000,000 separate `ThreadLocal` instances. If each thread-local stores a 500 KB object, this results in an immediate **500 GiB heap memory explosion**.

##### The Solution
Avoid using `ThreadLocal` variables inside virtual threads. Instead:
- Use **Scoped Values** (detailed in Module 5), which offer immutable, bounded scope lifetimes.
- Redesign the application to pass stateless execution contexts explicitly through method signatures.

---

#### 13. Monitoring & Diagnostics
Loom provides several tools to trace and debug virtual thread behavior:

- **JVM System Flags**:
  - `-Djdk.traceVirtualThreadLocals`: Prints a stack trace whenever a virtual thread accesses a `ThreadLocal` variable.
  - `-Djdk.tracePinnedThreads=full` or `-Djdk.tracePinnedThreads=short`: Logs stack traces to standard output when a virtual thread blocks while pinned.
- **Java Flight Recorder (JFR) Events**:
  - `jdk.VirtualThreadStart` and `jdk.VirtualThreadEnd`: Track lifecycle durations.
  - `jdk.VirtualThreadPinned`: Triggers when a virtual thread remains pinned for longer than a threshold (default: 20ms).
  - `jdk.VirtualThreadSubmitFailed`: Logs scheduling pool overflows.
- **Structured Dumps**:
  - Generate dumps via command line:
    ```bash
    jcmd <PID> Thread.dump_to_file -format=json thread_dump.json
    ```
    JSON structured dumps include virtual threads currently suspended on I/O.
  - Generate dumps programmatically:
    ```java
    import com.sun.management.HotSpotDiagnosticMXBean;
    import java.lang.management.ManagementFactory;

    public class DiagnosticDumper {
        public static void dump(String absolutePath) throws Exception {
            var mxBean = ManagementFactory.getPlatformMXBean(HotSpotDiagnosticMXBean.class);
            mxBean.dumpThreads(absolutePath, HotSpotDiagnosticMXBean.ThreadDumpFormat.JSON);
        }
    }
    ```

---

#### 14. Migration Tips
When transitioning a production system to virtual threads:
1. **Update Dependencies First**: Ensure libraries (JDBC drivers, HTTP clients, logging frameworks) are updated to versions that avoid pinning.
2. **Isolate Legacy Blocks**: If a library uses synchronized blocks that cause pinning under JDK 21-23, isolate those executions inside dedicated platform thread pools.
3. **Use Semaphores Judiciously**: Do not pool virtual threads. Use semaphores to rate-limit database or external API calls.
4. **Monitor System Metrics**: Track heap memory allocation rates, garbage collection pauses, and carrier thread pool utilization metrics under load.

---

### Key Diagrams & Mental Models

#### Thread State Transition on I/O Block

##### 1. Mounted State (Running)
```text
┌───────────────────────┐
│ Virtual Thread (Heap) │  ──(Mounted)──►  ┌───────────────────────┐
└───────────────────────┘                  │ Carrier Thread (OS)   │
                                           └───────────────────────┘
```

##### 2. Blocking I/O Encountered (Yielding)
```text
┌───────────────────────┐                  ┌───────────────────────┐
│ Virtual Thread (Heap) │  ◄──(Unmounted)─  │ Carrier Thread (OS)   │
│   [Stack copied back  │                  │   [Free to run other  │
│      to the heap]     │                  │    Virtual Threads]   │
└───────────────────────┘                  └───────────────────────┘
```

---

### Hands-On Code — Lab 2.1: Virtual Thread Creation Styles

#### Overview
You will implement a program that instantiates virtual threads using all four core creation styles. You will demonstrate the daemon thread termination issue and fix it using `.join()`.

#### Implementation (`VirtualThreadCreationDemo.java`)
```java
package com.example.concurrency.lab2_1;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

public class VirtualThreadCreationDemo {

    public static void main(String[] args) throws Exception {
        System.out.println("=== Starting Virtual Thread Creation Demo ===");

        // --- Demo 1: Daemon termination issue ---
        Thread daemonThread = Thread.startVirtualThread(() -> {
            try {
                Thread.sleep(100);
                System.out.println("Daemon Thread: This will NOT print if main exits too quickly!");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });
        
        // Let the daemon thread start, but do NOT join it yet
        Thread.sleep(20); 
        System.out.println("Main thread exiting daemon test block.");
        // If we exited here, Daemon Thread would never print.

        // --- Demo 2: Start Virtual Thread with Join ---
        Thread t1 = Thread.startVirtualThread(() -> {
            System.out.println("Style 1: Thread.startVirtualThread -> Thread ID: " + Thread.currentThread().threadId());
        });
        t1.join(); // Blocks main until t1 completes

        // --- Demo 3: Thread Builder Start ---
        Thread t2 = Thread.ofVirtual()
                .name("builder-started-", 1)
                .start(() -> {
                    System.out.println("Style 2: Thread.ofVirtual().start() -> " + Thread.currentThread().getName());
                });
        t2.join();

        // --- Demo 4: Thread Builder Unstarted ---
        Thread t3 = Thread.ofVirtual()
                .name("builder-unstarted-", 1)
                .unstarted(() -> {
                    System.out.println("Style 3: Thread.ofVirtual().unstarted() -> " + Thread.currentThread().getName());
                });
        t3.start(); // Explicitly start the thread
        t3.join();

        // --- Demo 5: Virtual Thread Executor ---
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            Future<String> future = executor.submit(() -> {
                System.out.println("Style 4: ExecutorService -> " + Thread.currentThread().getName());
                return "Completed Task";
            });
            String result = future.get();
            System.out.println("Executor Task Result: " + result);
        } // Executor auto-closes, waiting for all threads to terminate

        // Join daemonThread to clean up and print its output
        daemonThread.join();
        System.out.println("=== Demo Finished ===");
    }
}
```

---

### Hands-On Code — Lab 2.2: Little's Law Benchmark

#### Overview
You will implement a micro-benchmark class (`LittleLawExample`) that simulates 10,000 concurrent tasks. Each task introduces 500ms of simulated latency ($d = 500ms$). You will compare the execution duration and throughput (tasks/second) of virtual threads against fixed platform thread pools of sizes 100, 500, and 1,000.

#### Implementation (`LittleLawExample.java`)
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
        int taskLatencyMs = 500; // Simulated latency (d)

        Runnable ioBoundTask = () -> {
            try {
                // Simulate blocking I/O duration
                Thread.sleep(Duration.ofMillis(taskLatencyMs));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        };

        System.out.println("=== Little's Law Throughput Comparison ===");
        System.out.println("Tasks: " + numTasks + " | Latency: " + taskLatencyMs + " ms each\n");

        // Benchmark different executors
        benchmark("Virtual Threads", Executors.newVirtualThreadPerTaskExecutor(), ioBoundTask, numTasks);
        benchmark("Fixed ThreadPool (100)", Executors.newFixedThreadPool(100), ioBoundTask, numTasks);
        benchmark("Fixed ThreadPool (500)", Executors.newFixedThreadPool(500), ioBoundTask, numTasks);
        benchmark("Fixed ThreadPool (1000)", Executors.newFixedThreadPool(1000), ioBoundTask, numTasks);
    }

    private static void benchmark(String label, ExecutorService executor, Runnable task, int numTasks) {
        Instant start = Instant.now();
        AtomicLong completedTasks = new AtomicLong();

        // Submit tasks within try-with-resources to block on shutdown
        try (executor) {
            IntStream.range(0, numTasks)
                     .forEach(i -> executor.submit(() -> {
                         task.run();
                         completedTasks.incrementAndGet();
                     }));
        }

        Instant end = Instant.now();
        long duration = Duration.between(start, end).toMillis();
        double throughput = (completedTasks.get() / (double) duration) * 1000.0;

        System.out.printf("%-25s - Time: %5d ms | Throughput: %8.2f tasks/s%n", 
                label, duration, throughput);
    }
}
```

---

### Hands-On Code — Lab 2.3: Pinning Detection & Fix

#### Overview
In this lab, you will write two classes. 
1. `ThreadPinnedExample` will use a `synchronized` block containing a blocking sleep call. You will verify that the virtual thread is pinned to its carrier thread (since the worker name remains unchanged).
2. `PreventPinningExample` will replace `synchronized` with a `ReentrantLock`. You will verify that the virtual thread switches carrier threads when unmounting and remounting.
3. You will run both programs with the `-Djdk.tracePinnedThreads=short` JVM flag to monitor pinning stack traces.

#### Implementation

##### 1. Pinning Demo (`ThreadPinnedExample.java`)
```java
package com.example.concurrency.lab2_3;

import java.util.List;
import java.util.stream.IntStream;

public class ThreadPinnedExample {
    private static final Object lock = new Object();

    public static void main(String[] args) {
        List<Thread> threads = IntStream.range(0, 10)
            .mapToObj(i -> Thread.ofVirtual().unstarted(() -> {
                if (i == 0) {
                    System.out.println("Before Sync: " + Thread.currentThread());
                }
                
                // Entering synchronized pins the virtual thread to its carrier
                synchronized (lock) {
                    try {
                        Thread.sleep(50); // Simulate blocking I/O
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                }
                
                if (i == 0) {
                    System.out.println("After Sync:  " + Thread.currentThread());
                }
            })).toList();

        threads.forEach(Thread::start);
        threads.forEach(t -> {
            try { t.join(); } catch (InterruptedException ignored) {}
        });
    }
}
```

##### 2. Locking Repair (`PreventPinningExample.java`)
```java
package com.example.concurrency.lab2_3;

import java.util.List;
import java.util.concurrent.locks.ReentrantLock;
import java.util.stream.IntStream;

public class PreventPinningExample {
    private static final ReentrantLock lock = new ReentrantLock();

    public static void main(String[] args) {
        List<Thread> threads = IntStream.range(0, 10)
            .mapToObj(i -> Thread.ofVirtual().unstarted(() -> {
                if (i == 0) {
                    System.out.println("Before Lock: " + Thread.currentThread());
                }
                
                // ReentrantLock allows the virtual thread to unmount during blocking I/O
                lock.lock();
                try {
                    Thread.sleep(50); // Simulate blocking I/O
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

#### Verification Command
Execute `ThreadPinnedExample` with the pinning trace flag:
```bash
java -Djdk.tracePinnedThreads=short -cp target/classes com.example.concurrency.lab2_3.ThreadPinnedExample
```

##### Expected Output (ThreadPinnedExample)
```text
Before Sync: VirtualThread[#21]/runnable@ForkJoinPool-1-worker-1
After Sync:  VirtualThread[#21]/runnable@ForkJoinPool-1-worker-1
Thread[#21,ForkJoinPool-1-worker-1,5,CarrierThreads]
    java.base/java.lang.VirtualThread$VThreadContinuation.onPinned(VirtualThread.java:273)
    java.base/jdk.internal.vm.Continuation.onPinned0(Continuation.java:393)
    com.example.concurrency.lab2_3.ThreadPinnedExample.lambda$main$0(ThreadPinnedExample.java:18) <== monitors:1
```

Execute `PreventPinningExample`:
```bash
java -cp target/classes com.example.concurrency.lab2_3.PreventPinningExample
```

##### Expected Output (PreventPinningExample)
```text
Before Lock: VirtualThread[#20]/runnable@ForkJoinPool-1-worker-1
After Lock:  VirtualThread[#20]/runnable@ForkJoinPool-1-worker-3
```
*Note that the carrier thread changes from `worker-1` to `worker-3`, demonstrating that the virtual thread unmounted and was remounted onto a different worker.*

---

### Hands-On Code — Lab 2.4: Monitored Resource Pool & Semaphore Pitfall

#### Overview
You will implement a `MonitoredResourcePool` class that controls access to a limited pool of resources using a `Semaphore`. You will write a JUnit-like test that asserts rate-limiting compliance. Finally, you will demonstrate the semaphore release vulnerability.

#### Implementation

##### 1. The Monitored Pool (`MonitoredResourcePool.java`)
```java
package com.example.concurrency.lab2_4;

import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

public class MonitoredResourcePool {
    private final Semaphore semaphore;
    private final AtomicInteger activeConnections = new AtomicInteger(0);
    private final AtomicInteger peakConnections = new AtomicInteger(0);

    public MonitoredResourcePool(int resourceCount) {
        // Fair semaphore ensures FIFO access to permits
        this.semaphore = new Semaphore(resourceCount, true);
    }

    public void useResource(long taskDurationMs) {
        // Safe Pattern: acquire() MUST occur before the try block
        try {
            if (semaphore.tryAcquire(5, TimeUnit.SECONDS)) {
                try {
                    // Critical Section
                    int active = activeConnections.incrementAndGet();
                    updatePeak(active);

                    // Simulate database/API execution
                    Thread.sleep(taskDurationMs);
                } finally {
                    activeConnections.decrementAndGet();
                    semaphore.release(); // Return permit
                }
            } else {
                throw new RuntimeException("Timeout acquiring resource permit.");
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Task interrupted.", e);
        }
    }

    private synchronized void updatePeak(int current) {
        if (current > peakConnections.get()) {
            peakConnections.set(current);
        }
    }

    public int getPeakConnections() { return peakConnections.get(); }
    public int getAvailablePermits() { return semaphore.availablePermits(); }
    
    // Exposed for demonstrating the pitfall
    public void forceRelease() {
        semaphore.release();
    }
}
```

##### 2. The Verification Demo (`ResourcePoolTest.java`)
```java
package com.example.concurrency.lab2_4;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ResourcePoolTest {
    public static void main(String[] args) throws Exception {
        System.out.println("=== Starting Resource Pool Semaphore Test ===");
        
        MonitoredResourcePool pool = new MonitoredResourcePool(5);

        // Spawn 50 tasks seeking concurrent access to the pool
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int i = 0; i < 50; i++) {
                executor.submit(() -> pool.useResource(100));
            }
        } // Joins all tasks

        System.out.println("Execution Completed.");
        System.out.println("Peak Connections Observed: " + pool.getPeakConnections());
        System.out.println("Remaining Permits: " + pool.getAvailablePermits());

        // Assertion check
        if (pool.getPeakConnections() <= 5) {
            System.out.println("TEST PASSED: Concurrency remained bounded within the limit (5).");
        } else {
            System.err.println("TEST FAILED: Concurrency exceeded limits!");
        }

        // --- Demo the Pitfall ---
        System.out.println("\n=== Demonstrating Semaphore Pitfall ===");
        System.out.println("Available Permits Before: " + pool.getAvailablePermits());
        
        // Calling release without acquiring
        pool.forceRelease();
        System.out.println("Available Permits After: " + pool.getAvailablePermits() + " (Vulnerability Triggered!)");
        
        if (pool.getAvailablePermits() > 5) {
            System.out.println("Notice: Permit count inflated beyond original resource capacity due to loose release calls.");
        }
    }
}
```

---

### Common Pitfalls & Anti-Patterns

#### Pitfall: Releasing Semaphores in Nested Logic Without Guaranteed Acquisition
If `acquire()` is written inside the `try` block, and it throws an `InterruptedException`, the thread jumps to the `finally` block and executes `release()`. Because no permit was actually acquired, the release increments the semaphore counter, corrupting the rate-limiting bounds.

##### Broken Code
```java
package com.example.concurrency.pitfall;

import java.util.concurrent.Semaphore;

public class SemaphoreBrokenPattern {
    private final Semaphore semaphore = new Semaphore(2);

    public void executeTask() {
        try {
            // DANGER: If acquire() throws InterruptedException, finally executes anyway!
            semaphore.acquire(); 
            doImportantWork();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            // BUG: Increments permits even if acquire() failed!
            semaphore.release(); 
        }
    }

    private void doImportantWork() {}
}
```

##### Corrected Code
```java
package com.example.concurrency.pitfall;

import java.util.concurrent.Semaphore;

public class SemaphoreCorrectPattern {
    private final Semaphore semaphore = new Semaphore(2);

    public void executeTask() {
        try {
            // CORRECT: acquire() is called outside the try block that governs release
            semaphore.acquire();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return; // Exit early; no permit was acquired
        }

        try {
            doImportantWork();
        } finally {
            semaphore.release(); // Guaranteed to release exactly one valid permit
        }
    }

    private void doImportantWork() {}
}
```

---

### Summary
1. **FIFO Work-Stealing Scheduling**: Virtual threads map M:N onto carrier threads managed by a custom FIFO `ForkJoinPool`. This differs from the common ForkJoinPool used by parallel streams (which operates in LIFO mode).
2. **Mounting Mechanics**: When running, virtual threads are mounted onto platform threads. When blocking on I/O, they unmount and yield their execution frames to the GC heap, freeing the carrier thread for other tasks.
3. **Semaphore Controls**: Pooling virtual threads is an anti-pattern. Use semaphores inside tasks to enforce rate-limiting constraints on downstream services.
4. **Pinning Vectors**: Virtual threads block their carriers (pinning) when invoking native code or entering synchronized blocks (pre-JDK 24). ReentrantLock mitigates synchronized-block pinning.
5. **Memory Leak Risk**: Avoid ThreadLocal variables inside virtual threads. Spawning millions of virtual threads containing thread-locals can quickly trigger a heap memory explosion.

---

### Knowledge Check

1. **Which of the following describes Thread Pinning in Java virtual threads?**
   - A. The OS scheduler registers a virtual thread to a single CPU core.
   - B. A virtual thread cannot unmount from its carrier thread, blocking the carrier.
   - C. The garbage collector pins thread call stacks inside off-heap memory.
   - D. The JVM limits the maximum thread pool allocations.

2. **Why does using `ThreadLocal` variables inside virtual threads create a scalability risk?**
   - A. ThreadLocal blocks virtual threads from entering CPU execution.
   - B. It throws an `UnsupportedOperationException` as of JDK 21.
   - C. Spawning millions of threads creates millions of object copies, causing a memory explosion.
   - D. ThreadLocal resets thread priorities to zero.

3. **How does JEP 491 (JDK 24) change the behavior of virtual threads inside synchronized blocks?**
   - A. It deprecates the `synchronized` keyword in Java.
   - B. It allows virtual threads to unmount from their carriers when blocked inside most synchronized blocks.
   - C. It forces virtual threads to convert into platform threads.
   - D. It restricts thread groups to text formats.

##### Answers
1. **B** - Pinning occurs when a virtual thread cannot unmount from its carrier platform thread, causing the carrier thread to remain blocked on I/O.
2. **C** - Because virtual threads are spawned in large volumes, storing large objects in ThreadLocal variables duplicates the structures per thread, inflating the JVM heap.
3. **B** - JEP 491 redesigns synchronized monitor implementations so that virtual threads can yield and unmount while executing inside synchronized blocks.

