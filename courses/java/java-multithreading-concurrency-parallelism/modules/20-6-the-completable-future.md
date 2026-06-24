# The CompletableFuture

In previous modules, we explored `FutureTask`, which represents an asynchronous, result-bearing computation. However, retrieving a result from a traditional `Future` requires blocking the calling thread, and the interface lacks the ability to combine computations or handle errors functionally.

To address these limitations, Java 8 introduced **`CompletableFuture`**. It implements both the **`Future`** interface and the **`CompletionStage`** interface, establishing a powerful framework for writing non-blocking, asynchronous pipelines.

---

## The Evolution of Futures in Java

The differences between the traditional Java 5 `Future` and Java 8 `CompletableFuture` are summarized below:

| Feature | Traditional `Future` (Java 5) | `CompletableFuture` (Java 8) |
| :--- | :--- | :--- |
| **Non-blocking Callbacks** | No (must poll `isDone()` or block on `get()`). | Yes (using `thenApply`, `thenAccept`, etc.). |
| **Pipeline Chaining** | No. | Yes (monadic design using `thenCompose`). |
| **Combination / Merging** | No. | Yes (using `thenCombine`, `allOf`, `anyOf`). |
| **Explicit Completion** | No (managed solely by the task runner). | Yes (using `complete()` or `completeExceptionally()`). |
| **Error Propagation** | Throws checked exceptions on `get()`. | Supports functional recovery using `handle()` or `exceptionally()`. |
| **Subclassing / Subtyping** | Limited. | Enhanced in JDK 9 (e.g., `newIncompleteFuture()`, `copy()`). |

---

> **Problem: The Blocking Future Bottleneck**
> The traditional `Future` interface represents the result of an asynchronous computation, but it is difficult to orchestrate. If you need to perform a series of dependent asynchronous steps, or merge the results of multiple independent computations, you are forced to call `.get()`, which blocks the executing thread, destroys concurrency, and defeats the purpose of asynchronous execution.

---

## 1. Using CompletableFuture as a Simple Future

`CompletableFuture` implements the `Future` interface, meaning you can use it as a standard asynchronous handler but with the added ability to **manually complete** it.

You can create an empty `CompletableFuture` instance, hand it to consumers, and complete it later from any background thread:

```java
public Future<String> calculateAsync() throws InterruptedException {
    CompletableFuture<String> completableFuture = new CompletableFuture<>();

    // Spin off computation in a cached thread pool
    Executors.newCachedThreadPool().submit(() -> {
        Thread.sleep(500);
        completableFuture.complete("Hello"); // Explicit completion
        return null;
    });

    return completableFuture;
}
```

The consumer can block on `.get()` when they are ready to retrieve the result:

```java
Future<String> completableFuture = calculateAsync();
// ... execute other operations ...
String result = completableFuture.get(); // Blocks until completed
assertEquals("Hello", result);
```

If the result of a computation is already known, you can create an already-completed future immediately, which will return the value without blocking:

```java
Future<String> completableFuture = CompletableFuture.completedFuture("Hello");
String result = completableFuture.get(); // Returns "Hello" immediately
```

---

## 2. Encapsulating Computation Logic

Instead of managing threads and manual completion boilerplates, you can initiate asynchronous tasks using the static utility methods **`runAsync()`** and **`supplyAsync()`**:

*   **`runAsync(Runnable)`**: Runs a task that does not return a value. Returns a `CompletableFuture<Void>`.
*   **`supplyAsync(Supplier<T>)`**: Runs a task that returns a value of type `T`. Returns a `CompletableFuture<T>`.

```java
CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {
    // Heavy computation...
    return "Hello";
});

assertEquals("Hello", future.get());
```

---

## 3. Processing Results of Asynchronous Computations

Once an asynchronous stage completes, you can process its result using non-blocking, fluent API callbacks:

### A. Transform Results (`thenApply`)
Accepts a `Function<T, R>`, applies it to the completed result, and returns a new `CompletableFuture<R>` containing the transformed value:

```java
CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> "Hello")
    .thenApply(s -> s + " World");

assertEquals("Hello World", future.get());
```

### B. Consume Results (`thenAccept`)
Accepts a `Consumer<T>`, passes it the completed result, and returns `CompletableFuture<Void>` (useful when you do not need to return a value down the chain):

```java
CompletableFuture<Void> future = CompletableFuture.supplyAsync(() -> "Hello")
    .thenAccept(s -> System.out.println("Result: " + s));

future.get();
```

### C. Execute Runnables (`thenRun`)
Accepts a `Runnable` and executes it after the stage completes, ignoring the stage's output value entirely:

```java
CompletableFuture<Void> future = CompletableFuture.supplyAsync(() -> "Hello")
    .thenRun(() -> System.out.println("Stage completed."));

future.get();
```

---

> **Mental Model: The Completion Pipeline**
> Think of a `CompletableFuture` chain as an assembly line or pipeline. Each method (like `thenApply`, `thenAccept`) represents an asynchronous stage. When a stage completes, it automatically pushes its output to the next stage in the pipeline. If any stage blocks, the pipeline continues processing asynchronously in the background.

---

## 4. Combining Futures

The power of `CompletableFuture` lies in its monadic capability to combine multiple asynchronous stages.

### A. Sequential Chaining (`thenCompose`)
If your next asynchronous stage depends on the result of the previous stage and returns another `CompletableFuture`, use **`thenCompose()`** to chain them sequentially. This flattens the nested futures (analogous to `flatMap` in Streams):

```java
CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> "Hello")
    .thenCompose(s -> CompletableFuture.supplyAsync(() -> s + " World"));

assertEquals("Hello World", future.get());
```

### B. Independent Combination (`thenCombine`)
If you want to run two independent futures in parallel and combine their results once both complete, use **`thenCombine()`**, which accepts a second future and a combining BiFunction:

```java
CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> "Hello")
    .thenCombine(CompletableFuture.supplyAsync(() -> " World"), (s1, s2) -> s1 + s2);

assertEquals("Hello World", future.get());
```

### C. Consumption of Both (`thenAcceptBoth`)
If you want to process both results but do not need to return a value down the pipeline:

```java
CompletableFuture<Void> future = CompletableFuture.supplyAsync(() -> "Hello")
    .thenAcceptBoth(CompletableFuture.supplyAsync(() -> " World"), (s1, s2) -> System.out.println(s1 + s2));
```

---

## 5. thenApply() vs. thenCompose()

While both methods return a new `CompletionStage`, their signatures and flattening behaviors differ:

*   **`thenApply()`**: Used for simple transformations (mapping). It wraps the return value inside a `CompletableFuture`. If your mapping function itself returns a `CompletableFuture`, you end up with a nested future: `CompletableFuture<CompletableFuture<R>>`.
*   **`thenCompose()`**: Used for asynchronous chaining (flattening). It takes a function that returns a `CompletableFuture` and flattens the result, returning a direct `CompletableFuture<R>`.

---

> **Insights: CompletableFuture as a Monad**
> The design of `CompletableFuture` is monadic, mirroring classes like `Optional` and `Stream`. The `thenApply()` method acts as `map()`, while `thenCompose()` acts as `flatMap()`. This structure allows you to build clean, declarative, and robust asynchronous workflows without nesting callbacks (avoiding "callback hell").

---

## 6. Running Multiple Futures in Parallel

To coordinate the execution of an arbitrary number of independent futures, you can use the static utility method **`allOf()`**:

```java
CompletableFuture<String> future1 = CompletableFuture.supplyAsync(() -> "Hello");
CompletableFuture<String> future2 = CompletableFuture.supplyAsync(() -> "Beautiful");
CompletableFuture<String> future3 = CompletableFuture.supplyAsync(() -> "World");

// Create a combined future that completes when ALL sub-futures complete
CompletableFuture<Void> combinedFuture = CompletableFuture.allOf(future1, future2, future3);

combinedFuture.get(); // Blocks until all three are done

assertTrue(future1.isDone());
assertTrue(future2.isDone());
assertTrue(future3.isDone());
```

Because `allOf()` returns `CompletableFuture<Void>`, it does not collect the results. You can combine it with Java 8 Streams and the non-blocking **`join()`** method to extract the results cleanly:

```java
String combined = Stream.of(future1, future2, future3)
    .map(CompletableFuture::join) // Extracts value (throws unchecked exceptions if failed)
    .collect(Collectors.joining(" "));

assertEquals("Hello Beautiful World", combined);
```

---

## 7. Handling Errors

Asynchronous error propagation requires a functional approach rather than standard `try-catch` blocks.

### A. Recovering with `handle()`
The **`handle()`** method acts as a recovery stage. It accepts a BiFunction that receives two arguments: the result of the computation (if successful, otherwise `null`) and the thrown exception (if failed, otherwise `null`):

```java
String name = null;

CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {
    if (name == null) {
        throw new RuntimeException("Computation error!");
    }
    return "Hello, " + name;
}).handle((result, exception) -> {
    // If exception occurred, return a default fallback value
    return exception != null ? "Hello, Stranger!" : result;
});

assertEquals("Hello, Stranger!", future.get());
```

### B. Exceptional Completion (`completeExceptionally`)
You can manually complete a future with an exception to signal a failure to down-stream consumers:

```java
CompletableFuture<String> future = new CompletableFuture<>();
future.completeExceptionally(new RuntimeException("Calculation failed!"));

future.get(); // Throws ExecutionException wrapping the RuntimeException
```

---

## 8. Async Methods and Executors

Most methods in the `CompletableFuture` API have two additional variants with an **`Async`** suffix:

*   **No suffix (e.g., `thenApply`)**: Executes the stage in the **calling thread** (the thread that completed the previous stage).
*   **`Async` suffix without Executor (e.g., `thenApplyAsync`)**: Executes the stage using the JVM's common fork/join pool (**`ForkJoinPool.commonPool()`**) as long as parallelism > 1.
*   **`Async` suffix with Executor (e.g., `thenApplyAsync(fn, executor)`)**: Executes the stage using a custom thread pool (**`Executor`**).

```java
CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> "Hello")
    .thenApplyAsync(s -> s + " World", customExecutor);
```

---

> **Pitfalls: Thread Starvation in the Common Pool**
> By default, the `Async` methods without an explicit executor run tasks in the `ForkJoinPool.commonPool()`. This pool is shared across the entire JVM. If you submit blocking operations (such as database calls or HTTP requests) to the common pool without specifying a custom executor, you risk starving other parts of your application of CPU threads, severely degrading JVM performance.

---

## 9. JDK 9 CompletableFuture API Enhancements

Java 9 introduced several instance and utility methods to make asynchronous workflows more robust:

### Key Instance Methods
*   **`defaultExecutor()`**: Returns the default `Executor` used for async methods if none is specified (typically `ForkJoinPool.commonPool()`).
*   **`newIncompleteFuture()`**: Returns a new, incomplete `CompletableFuture` of the same type. Useful when subclassing to maintain control over return subtypes.
*   **`copy()`**: Creates a defensive copy of a future. It reflects the completion state of the original but prevents clients from manually completing the original future.
*   **`minimalCompletionStage()`**: Returns a read-only `CompletionStage` view, throwing `UnsupportedOperationException` on any attempt to manually resolve or modify it.
*   **`completeAsync(Supplier<T> supplier, Executor executor)`**: Completes the future asynchronously using the value returned by the supplier, executed by the specified executor.
*   **`orTimeout(long timeout, TimeUnit unit)`**: Automatically completes the future exceptionally with a `TimeoutException` if it does not finish within the specified timeout period.
*   **`completeOnTimeout(T value, long timeout, TimeUnit unit)`**: Completes the future normally with a default fallback value if it does not finish within the specified timeout.

### Key Static Utility Methods
*   **`delayedExecutor(long delay, TimeUnit unit, Executor executor)`**: Returns a new executor that runs tasks on the base executor after the specified delay.
*   **`completedStage(U value)`**: Returns an already completed `CompletionStage` instance.
*   **`failedStage(Throwable ex)`**: Returns an already exceptionally completed `CompletionStage` instance.
*   **`failedFuture(Throwable ex)`**: Returns an already exceptionally completed `CompletableFuture` instance.

---

## Summary

*   **Non-Blocking Pipelines**: `CompletableFuture` enables building fluent, non-blocking asynchronous execution pipelines by implementing both `Future` and `CompletionStage`.
*   **Encapsulation**: Use `supplyAsync()` and `runAsync()` to easily dispatch tasks to background threads.
*   **Monadic Chaining**:
    *   `thenApply()` maps values (like `map()`).
    *   `thenCompose()` chains and flattens futures (like `flatMap()`).
    *   `thenCombine()` runs independent stages in parallel and combines their results.
*   **Parallel Coordination**: Use `allOf()` to wait for multiple futures, combined with `join()` and Streams to collect results cleanly.
*   **Robust Error Handling**: Use `handle()` to functionally recover from exceptions, or `completeExceptionally()` to signal downstream failures.
*   **Timeout Controls**: Use Java 9 `orTimeout()` and `completeOnTimeout()` to prevent futures from blocking indefinitely.
*   **Executor Isolation**: Always provide a custom `Executor` to `Async` methods when executing blocking tasks to avoid JVM-wide common pool starvation.
