# Thread Pools and Execution Policies

In the previous module, we analyzed why the naive thread-per-request model fails under heavy load, and how the **Executor Framework** resolves these limitations. 

In this module, we will explore the core programming principle upon which the Executor Framework is built: **Separation of Concerns**. We will examine the concept of an **Execution Policy** and analyze the four primary, pre-defined thread pools provided by the Java Concurrency Utilities.

---

## Separation of Concerns

The **Separation of Concerns (SoC)** principle states that an application should be decomposed into distinct features or concerns, with each concern isolated in its own modular code block or class. 

In concurrent programming, the two primary concerns are:
1.  **The Task**: The self-contained logical unit of work to be performed (defined by a `Runnable` or `Callable` instance).
2.  **The Execution Mechanism**: The mechanism by which the task is executed (e.g., thread allocation, scheduling, and queuing).

Consider the legacy way of spawning a thread:

```java
Runnable task = () -> doWork();
Thread t1 = new Thread(task);
t1.start();
```

This code **violates** the Separation of Concerns principle because it tightly couples the task (`task`) with a specific execution mechanism (a single-use `Thread` object). 

### Disadvantages of Coupling Tasks and Threads
- **Rigid Binding**: The thread `t1` is permanently bound to the task. It cannot execute any other task throughout its lifetime.
- **Single-Use Overhead**: Once `t1` completes the task, it dies. It cannot be reused. If you have a hundred tasks, you must create a hundred separate thread objects.
- **Lack of Flexibility**: You cannot easily change *how* the task is executed (e.g., executing it on a background pool, delaying its execution, or serializing it) without rewriting the client code.

### Decoupling via the Executor Interface
The `java.util.concurrent.Executor` interface solves this by decoupling task submission from task execution:

```java
public interface Executor {
    void execute(Runnable command);
}
```

Instead of creating threads manually, client code simply submits a `Runnable` task to the `Executor` by calling `execute(task)`. The `Executor` implementation is entirely responsible for managing the worker threads, task queues, and execution details:

![Task Submission and Execution](../images/image25.png)

*Figure 21.2.1: Decoupling task submission from task execution using the Executor interface*

---

## Thread Pools in Practice

Let's look at how our concurrent server utilizes the `Executor` interface:

```java
import java.io.IOException;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

public class ThreadPoolServer {
    private static final int NTHREADS = Runtime.getRuntime().availableProcessors();
    private static final Executor pool = Executors.newFixedThreadPool(NTHREADS);

    public static void main(String[] args) throws IOException {
        ServerSocket socket = new ServerSocket(6000);
        while (true) {
            final Socket connection = socket.accept();
            Runnable clientTask = () -> handleRequest(connection);
            
            // Task Submission is decoupled from Task Execution
            pool.execute(clientTask); 
        }
    }

    private static void handleRequest(Socket connection) {
        // Request processing logic
    }
}
```

The client loop simply submits `clientTask` to the `pool`. The thread pool internally manages the worker threads and distributes the tasks. How the tasks are queued and executed is governed by the pool's **Execution Policy**.

---

## What is an Execution Policy?

An **Execution Policy** defines the "what, where, when, and how" of task execution. A thread pool encapsulates a specific execution policy, answering:
- **What** thread will the tasks be executed in?
- **In what order** should tasks be executed? (e.g., FIFO, LIFO, Priority Order)
- **How many** tasks can be executed concurrently?
- **How many** tasks can be queued pending execution?
- **Which task** should be rejected if the system is overloaded, and how should the application be notified?
- **What actions** should be taken before or after executing a task?

### Inside a Thread Pool
To enforce its execution policy, a thread pool is tightly bound to a **Work Queue** (a blocking queue holding pending tasks) and manages a pool of **worker threads**. 

Worker threads have a different lifecycle than conventional Java threads:
- A conventional thread executes its task and dies.
- A worker thread runs an infinite loop: it requests a task from the Work Queue, executes it, and immediately returns to the waiting state to take the next task.
- Worker threads do not shut down until the thread pool itself is explicitly shut down.

---

## The Four Pre-defined Thread Pools

The JDK `Executors` class provides static factory methods to create four pre-configured thread pool implementations:

### 1. `newFixedThreadPool(int nThreads)`
A fixed-size thread pool.
- **Worker Threads**: Creates worker threads on the fly as tasks are submitted, up to the specified limit (`nThreads`). 
- **Pool Stability**: If a worker thread dies due to an uncaught exception during task execution, the pool automatically creates a new thread to maintain the desired capacity.
- **Queuing**: Uses an unbounded FIFO queue (`LinkedBlockingQueue`). If all threads are busy, incoming tasks are queued indefinitely, which can consume significant memory under heavy load.

### 2. `newCachedThreadPool()`
An unbounded, dynamically resizing thread pool.
- **On-Demand Allocation**: Creates new worker threads as needed when tasks are submitted and no idle threads are available.
- **Thread Reuse**: Reuses idle threads once they become free.
- **Tear-Down**: Threads that remain idle for 60 seconds are terminated and removed from the pool to conserve resources.
- **Queuing**: Uses a zero-capacity `SynchronousQueue`. Tasks are handed off directly from the submitting thread to an idle worker thread. If no idle thread exists, a new thread is spawned. This pool provides maximum responsiveness but must be bounded externally to prevent infinite thread creation under extreme load.

### 3. `newSingleThreadExecutor()`
A single-threaded executor.
- **Serialization**: Manages a single worker thread to execute all submitted tasks sequentially.
- **Queuing**: Un-executed tasks are placed in an unbounded queue.
- **Guaranteed Order**: Guarantees that tasks are executed in strict FIFO order, with no two tasks running concurrently.
- **Contrast with Fixed Pool**: Unlike `newFixedThreadPool(1)`, a single-thread executor's configuration is decorated so that the pool size cannot be cast or reconfigured at runtime, ensuring strict single-threaded serialization.

### 4. `newScheduledThreadPool(int corePoolSize)`
A thread pool designed for delayed or periodic task execution.
- **Scheduling**: Supports executing tasks after a specified delay, or running them repeatedly at fixed intervals (similar to `java.util.Timer`).
- **Robustness**: Unlike `Timer` (which uses a single thread and halts completely if a task throws an exception), `ScheduledThreadPoolExecutor` manages multiple threads and handles task failures gracefully without disrupting other scheduled tasks.

---

## Code Example: Using a Fixed Thread Pool

Below is a simple program demonstrating how a fixed thread pool of size 4 processes 10 tasks concurrently:

```java
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class FixedThreadPoolDemo {

    public static void main(String[] args) {
        // Create a fixed thread pool of size 4
        ExecutorService pool = Executors.newFixedThreadPool(4);
        
        // Submit 10 tasks to the pool
        for (int i = 0; i < 10; i++) {
            pool.execute(printBinary(i));
        }
        
        // Gracefully shut down the pool, allowing active tasks to finish
        pool.shutdown();
    }

    private static Runnable printBinary(int number) {
        return () -> System.out.println(Thread.currentThread().getName() + " :: " + number + " = " + Integer.toBinaryString(number));
    }
}
```

*Figure 21.2.2: Submitting tasks to a fixed-capacity thread pool*

#### Output
```text
Thread[pool-1-thread-4,5,main] :: 3 = 11
Thread[pool-1-thread-3,5,main] :: 2 = 10
Thread[pool-1-thread-4,5,main] :: 4 = 100
Thread[pool-1-thread-3,5,main] :: 5 = 101
Thread[pool-1-thread-4,5,main] :: 6 = 110
Thread[pool-1-thread-3,5,main] :: 7 = 111
Thread[pool-1-thread-4,5,main] :: 8 = 1000
Thread[pool-1-thread-3,5,main] :: 9 = 1001
Thread[pool-1-thread-1,5,main] :: 0 = 0
Thread[pool-1-thread-2,5,main] :: 1 = 1
```

### Understanding ExecutorService
In the demo, we assign the thread pool to an instance of **`ExecutorService`**. 
`ExecutorService` is an interface that extends `Executor`. While `Executor` only defines the `execute()` method, `ExecutorService` adds comprehensive lifecycle management methods—such as `shutdown()` (graceful stop), `shutdownNow()` (forced stop), and task tracking methods (`submit()`, `invokeAll()`)—which we will examine in the next module.

---

## Thread Pool Sizing: corePoolSize vs. maxPoolSize

When configuring custom thread pools using the JDK's `ThreadPoolExecutor` or Spring's `ThreadPoolTaskExecutor` wrapper, developers are often confused by how the pool size grows. The key to understanding this lies in three properties: **`corePoolSize`**, **`maxPoolSize`**, and **`queueCapacity`**.

### Core Concepts

*   **`corePoolSize`**: The minimum number of worker threads to keep alive in the pool, even if they are idle. If `allowCoreThreadTimeOut` is set to `true`, even core threads can time out and be terminated, reducing the active pool size to zero.
*   **`maxPoolSize`**: The absolute maximum number of threads that the pool can ever create to handle concurrent tasks.
*   **`queueCapacity`**: The capacity of the underlying blocking queue that holds tasks waiting for execution.

---

> **Problem: The Unused Max Pool Size**
> A common configuration error is setting `maxPoolSize` to a high value (e.g., 10) while leaving `queueCapacity` unbounded (the default in both JDK and Spring). Because the work queue can never fill up, the thread pool will **never** scale beyond `corePoolSize`, rendering `maxPoolSize` completely useless under heavy load.

---

> **Mental Model: The Thread Pool Growth Lifecycle**
> When a new task is submitted, the pool decides whether to spawn a thread or queue the task using the following sequential rules:
> 
> 1.  **Fewer than `corePoolSize` threads running?** Spawn a new thread to execute the task immediately (even if other threads are idle).
> 2.  **`corePoolSize` threads running?** Attempt to place the task into the work queue.
> 3.  **Queue is full?** 
>     *   If fewer than `maxPoolSize` threads are running, spawn a new thread to execute the task.
>     *   If `maxPoolSize` threads are running, reject the task (using a `RejectedExecutionHandler`).

---

### Demonstrating Pool Growth with Examples

To clarify how these properties interact, let's look at concurrent test cases using Spring's `ThreadPoolTaskExecutor`. We'll use a helper method `startThreads` to submit a specified number of sleeping tasks:

```java
public void startThreads(ThreadPoolTaskExecutor taskExecutor, CountDownLatch countDownLatch, 
  int numThreads) {
    for (int i = 0; i < numThreads; i++) {
        taskExecutor.execute(() -> {
            try {
                Thread.sleep(100L * ThreadLocalRandom.current().nextLong(1, 10));
                countDownLatch.countDown();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });
    }
}
```

#### Case 1: Default Configuration (Single Thread)
By default, the executor is configured with a `corePoolSize` of 1, an unbounded `maxPoolSize`, and an unbounded `queueCapacity`. As a result, no matter how many tasks are submitted, the pool size never exceeds 1:

```java
@Test
public void whenUsingDefaults_thenSingleThread() {
    ThreadPoolTaskExecutor taskExecutor = new ThreadPoolTaskExecutor();
    taskExecutor.afterPropertiesSet();

    CountDownLatch countDownLatch = new CountDownLatch(10);
    this.startThreads(taskExecutor, countDownLatch, 10);

    while (countDownLatch.getCount() > 0) {
        Assert.assertEquals(1, taskExecutor.getPoolSize());
    }
}
```

#### Case 2: Explicit Core Pool Size
If we set `corePoolSize` to 5 and submit 10 tasks, the pool immediately scales to 5 threads:

```java
@Test
public void whenCorePoolSizeFive_thenFiveThreads() {
    ThreadPoolTaskExecutor taskExecutor = new ThreadPoolTaskExecutor();
    taskExecutor.setCorePoolSize(5);
    taskExecutor.afterPropertiesSet();

    CountDownLatch countDownLatch = new CountDownLatch(10);
    this.startThreads(taskExecutor, countDownLatch, 10);

    while (countDownLatch.getCount() > 0) {
        Assert.assertEquals(5, taskExecutor.getPoolSize());
    }
}
```

#### Case 3: Core Pool Size vs. Max Pool Size with Unbounded Queue
If we set `corePoolSize` to 5, `maxPoolSize` to 10, but leave `queueCapacity` unbounded, submitting 10 tasks will still only spawn 5 threads. The remaining 5 tasks are queued because the queue never fills up:

```java
@Test
public void whenCorePoolSizeFiveAndMaxPoolSizeTen_thenFiveThreads() {
    ThreadPoolTaskExecutor taskExecutor = new ThreadPoolTaskExecutor();
    taskExecutor.setCorePoolSize(5);
    taskExecutor.setMaxPoolSize(10);
    taskExecutor.afterPropertiesSet();

    CountDownLatch countDownLatch = new CountDownLatch(10);
    this.startThreads(taskExecutor, countDownLatch, 10);

    while (countDownLatch.getCount() > 0) {
        Assert.assertEquals(5, taskExecutor.getPoolSize());
    }
}
```

#### Case 4: Scale to Max Pool Size with Bounded Queue
To allow the pool to scale to `maxPoolSize`, we must define a bounded `queueCapacity` (e.g., 10). If we submit 20 tasks:
1.  The first 5 tasks spawn 5 core threads.
2.  The next 10 tasks fill the queue.
3.  The remaining 5 tasks force the executor to spawn 5 additional threads, scaling the pool to `maxPoolSize` of 10:

```java
@Test
public void whenCorePoolSizeFiveAndMaxPoolSizeTenAndQueueCapacityTen_thenTenThreads() {
    ThreadPoolTaskExecutor taskExecutor = new ThreadPoolTaskExecutor();
    taskExecutor.setCorePoolSize(5);
    taskExecutor.setMaxPoolSize(10);
    taskExecutor.setQueueCapacity(10);
    taskExecutor.afterPropertiesSet();

    CountDownLatch countDownLatch = new CountDownLatch(20);
    this.startThreads(taskExecutor, countDownLatch, 20);

    while (countDownLatch.getCount() > 0) {
        Assert.assertEquals(10, taskExecutor.getPoolSize());
    }
}
```

---

> **Pitfalls: The Bounded Queue Saturation Point**
> When using a bounded queue, you must handle task rejection. If the queue is full and active threads have reached `maxPoolSize`, any subsequent task will be rejected. Always configure a suitable `RejectedExecutionHandler` (e.g., `CallerRunsPolicy` to throttle task submission) to avoid silent failures or application crashes.

---

> **Insights: Zero-Capacity Queuing for Maximum Responsiveness**
> By setting `queueCapacity` to 0 (which internally uses a `SynchronousQueue`), tasks are handed off directly to threads. If all core threads are busy, a new thread is spawned immediately up to `maxPoolSize`. This configuration maximizes task throughput and responsiveness at the cost of higher CPU and thread allocation overhead.

---

## Summary

*   **Separation of Concerns**: A key programming principle that decouples **what** the task is (Runnable/Callable) from **how** it is executed (Executor), ensuring modularity and scalability.
*   **Decoupled Submission**: By submitting tasks to an `Executor` rather than binding them to raw `Thread` objects, threads can be reused infinitely, eliminating thread-creation latency.
*   **Execution Policy**: Encapsulated by a thread pool, it defines the rules governing thread allocation, task queuing order (FIFO, LIFO, priority), maximum concurrency, and saturation handling (rejected tasks).
*   **Worker Thread Lifecycle**: Worker threads run an infinite loop, pulling tasks from a shared blocking Work Queue and executing them. They remain alive until the pool itself is shut down.
*   **Pre-defined Pools**:
    - `FixedThreadPool`: Capped thread count, unbounded queue.
    - `CachedThreadPool`: Uncapped thread count, dynamic resizing, idle thread reclamation.
    - `SingleThreadExecutor`: Single thread, guarantees strict sequential FIFO execution.
    - `ScheduledThreadPool`: Fixed size, supports delayed and periodic execution.
*   **ExecutorService**: Extends `Executor` to provide advanced lifecycle controls (like `shutdown()`) and task tracking primitives.
