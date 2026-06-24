# ExecutorService: Lifecycle and Waiting for Threads to Finish

In previous modules, we examined the separation of concerns, the pre-defined thread pools, and how `ThreadPoolExecutor` scales. However, submitting tasks to an `ExecutorService` is only half the story. In real-world applications, you must manage the lifecycle of the executor, handle graceful shutdowns, and coordinate waiting for threads to finish their execution.

In this module, we will analyze four different mechanisms to wait for asynchronous tasks to complete and explore the industry-standard graceful shutdown pattern.

---

## Coordinating Task Completion

The table below summarizes the different mechanisms available to wait for thread pool tasks to complete:

| Mechanism | Blocking Behavior | Retrieval Order | Best Use Case |
| :--- | :--- | :--- | :--- |
| **`awaitTermination()`** | Blocks the calling thread until all tasks complete or the timeout expires. | N/A (no results returned). | Graceful shutdown of the entire thread pool. |
| **`CountDownLatch`** | Blocks the calling thread until the latch count reaches zero. | N/A (no results returned). | Coordinating external events or signaling task completion. |
| **`invokeAll()`** | Blocks the calling thread until all tasks in the collection complete. | Submission order (same as input collection). | Batch processing where all results are required to proceed. |
| **`ExecutorCompletionService`** | Blocks/polls via `.take()` or `.poll()` as tasks finish. | Completion order (first-finished, first-served). | Real-time result processing to minimize idle waiting. |

---

> **Problem: Asynchronous Shutdown Leaks**
> Initiating an executor shutdown by calling `.shutdown()` or `.shutdownNow()` is an asynchronous operation. The method returns immediately, and the JVM continues execution. If your application exits or cleans up resources (like database connections or files) immediately after, the running threads will crash or leak, causing silent data corruption and resource leaks.

---

## 1. Graceful Shutdown with awaitTermination()

To shut down an `ExecutorService` cleanly, you must stop it from accepting new tasks and wait for currently running tasks to finish. 

The standard pattern combines `shutdown()`, `awaitTermination()`, and `shutdownNow()` in a `try-catch` block:

```java
public void awaitTerminationAfterShutdown(ExecutorService threadPool) {
    // 1. Disable new tasks from being submitted
    threadPool.shutdown(); 
    try {
        // 2. Wait for existing tasks to terminate
        if (!threadPool.awaitTermination(60, TimeUnit.SECONDS)) {
            // 3. Force cancel remaining tasks if timeout expires
            threadPool.shutdownNow(); 
        }
    } catch (InterruptedException ex) {
        // 3. Force cancel if the waiting thread is interrupted
        threadPool.shutdownNow();
        Thread.currentThread().interrupt(); // Restore interrupt status
    }
}
```

---

> **Mental Model: The Three-Step Shutdown**
> Think of shutting down a thread pool like closing a restaurant:
> 1.  **`shutdown()` (Lock the front door)**: No new customers (tasks) are allowed in, but customers already inside are allowed to finish their meals.
> 2.  **`awaitTermination()` (Wait for diners to finish)**: The manager waits for a specific duration (timeout) for everyone to leave.
> 3.  **`shutdownNow()` (Turn off the lights and sweep)**: If customers refuse to leave after the timeout, the manager forces them out immediately.

---

> **Pitfalls: The Limits of shutdownNow()**
> Calling `shutdownNow()` does **not** guarantee that running threads will stop immediately. It attempts to stop active tasks by sending a `Thread.interrupt()` signal. If your task does not perform blocking operations (like `sleep()`, `wait()`, or I/O) and ignores the thread interrupt status, it will continue executing indefinitely, defying the shutdown request.

---

## 2. Waiting for Threads via CountDownLatch

If you do not want to shut down the executor, but still need the calling thread to wait for a specific batch of asynchronous tasks to complete, you can use a **`CountDownLatch`** as a coordination checkpoint:

```java
ExecutorService workerThreadPool = Executors.newFixedThreadPool(10);
CountDownLatch latch = new CountDownLatch(2); // Wait for 2 tasks

for (int i = 0; i < 2; i++) {
    workerThreadPool.submit(() -> {
        try {
            // Execute business logic...
        } finally {
            latch.countDown(); // Decrement latch count on completion
        }
    });
}

// Block the calling thread until the latch count reaches zero
latch.await(); 
```

---

## 3. Batch Execution via invokeAll()

The most direct way to execute a batch of tasks and wait for all of them to finish is using the **`invokeAll()`** method. 

This method accepts a collection of `Callable` tasks, executes them concurrently, blocks the calling thread until all of them complete, and returns a list of `Future` objects preserving the exact order of the input collection:

```java
ExecutorService workerThreadPool = Executors.newFixedThreadPool(10);

List<Callable<String>> callables = Arrays.asList(
  new DelayedCallable("fast thread", 100),  // Completes in 100ms
  new DelayedCallable("slow thread", 3000)  // Completes in 3000ms
);

long startProcessingTime = System.currentTimeMillis();

// Blocks until ALL callables complete
List<Future<String>> futures = workerThreadPool.invokeAll(callables); 

awaitTerminationAfterShutdown(workerThreadPool);

long totalProcessingTime = System.currentTimeMillis() - startProcessingTime;
assertTrue(totalProcessingTime >= 3000); // Overall time is determined by the slowest task

// Results are retrieved in the exact order of submission
assertEquals("fast thread", futures.get(0).get());
assertEquals("slow thread", futures.get(1).get());
```

---

## 4. First-Finished, First-Served via ExecutorCompletionService

While `invokeAll()` is simple, it forces you to wait for the entire batch to complete before processing any results. Furthermore, the returned futures are in submission order, meaning if you iterate over them, you might block on a slow task at index 0 even if the task at index 1 finished hours ago.

To maximize throughput, you can use **`ExecutorCompletionService`**. It wraps an `ExecutorService` and manages an internal completion queue. As soon as any task completes, its corresponding `Future` is pushed into the queue, allowing you to harvest results in **completion order** (first-finished, first-served):

```java
CompletionService<String> service = new ExecutorCompletionService<>(workerThreadPool);

List<Callable<String>> callables = Arrays.asList(
  new DelayedCallable("fast thread", 100), 
  new DelayedCallable("slow thread", 3000)
);

// Submit all tasks asynchronously
for (Callable<String> callable : callables) {
    service.submit(callable);
}

long startProcessingTime = System.currentTimeMillis();

// 1. Retrieve the first completed task (the fast thread at 100ms)
Future<String> future = service.take(); // Blocks until a task completes
String firstResponse = future.get();
long totalTime = System.currentTimeMillis() - startProcessingTime;

assertEquals("fast thread", firstResponse);
assertTrue(totalTime >= 100 && totalTime < 1000); // Processed immediately without waiting for the slow thread!

// 2. Retrieve the second completed task (the slow thread at 3000ms)
future = service.take();
String secondResponse = future.get();
totalTime = System.currentTimeMillis() - startProcessingTime;

assertEquals("slow thread", secondResponse);
assertTrue(totalTime >= 3000 && totalTime < 4000);

awaitTerminationAfterShutdown(workerThreadPool);
```

---

> **Insights: Choosing the Right Pipeline**
> *   **Use `invokeAll()`** when the downstream logic requires **all** results to proceed (e.g., aggregating monthly financial data from multiple departments).
> *   **Use `ExecutorCompletionService`** when results can be processed **independently** (e.g., rendering images, scraping web pages, or executing parallel database queries). Processing tasks as they complete keeps CPU cores fully utilized and reduces overall latency.

---

## Summary

*   **Asynchronous Shutdown**: Shutting down an executor is asynchronous. Always pair `.shutdown()` with `.awaitTermination()` to block and ensure clean resource cleanup.
*   **Interrupt-Based Termination**: `shutdownNow()` sends thread interrupts. Tasks must respect thread interrupts to stop executing.
*   **CountDownLatch Coordination**: Ideal for waiting for a fixed batch of tasks without shutting down the executor service.
*   **`invokeAll()`**: Executes a batch of tasks, blocks until all are finished, and returns their futures in the exact order of submission.
*   **`ExecutorCompletionService`**: Uses a completion queue to return task results in the order they finish (first-finished, first-served), eliminating unnecessary idle waiting.
