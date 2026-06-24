# Module 04: Structured Concurrency & StructuredTaskScope

In our previous modules, we examined how virtual threads allow us to handle blocking tasks concurrently without the overhead of native platform threads. While spawning thousands of virtual threads is trivial, managing the relationships, lifecycle, and coordination between these concurrent tasks introduces new challenges.

In this module, we will explore **Structured Concurrency**—a paradigm that treats groups of related tasks as a single unit of work. We will examine the limitations of traditional unstructured concurrency, study the `StructuredTaskScope` API in depth, design custom joining policies, analyze memory consistency effects, construct nested task hierarchies, and investigate observability tools.

---

## 1. The Challenge of Unstructured Concurrency

Java has traditionally used `ExecutorService` and `Future` for concurrency. This is called **unstructured concurrency** because tasks are independent of each other. A subtask's lifetime is not tied to its parent or sibling tasks.

### Core Problems of Unstructured Concurrency

1. **Thread/Resource Leaks**: If a parent task fails or times out, its child tasks are not automatically cleaned up. They keep running in the background, wasting CPU and memory.
2. **No Automatic Cancellation**: If one subtask fails in a group where all are needed, the others keep running. You have to cancel them manually.
3. **Slow Error Response**: If one subtask fails quickly, the parent thread still blocks waiting for other slow subtasks to finish (via `Future.get()`) before it can throw the error, wasting time.

### Visualizing the Resource Leak

Consider a web application that must fetch product details and reviews in parallel:

```
[Parent: fetchProductInfo()]
      │
      ├─► [Child 1: fetchProduct()]  ──────► (Fails after 1 second)
      │
      └─► [Child 2: fetchReviews()]  ──────► (Takes 5 seconds, continues running pointlessly)
```

### Unstructured Code Example (`ExecutorService`)

Below is a typical implementation of a product service using unstructured concurrency. It exhibits thread leaks:

```java
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

public class UnstructuredProductService {

    public record Product(Long id, String name, String description) {}
    public record Review(Long id, String comment, int rating, Long productId) {}
    public record ProductInfo(Product product, List<Review> reviews) {}

    public ProductInfo fetchProductInfo(Long productId) throws Exception {
        Instant start = Instant.now();
        System.out.println("Fetching product & reviews for id: " + productId);

        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            // Forking child tasks
            Future<Product> productTask = executor.submit(() -> fetchProduct(productId));
            Future<List<Review>> reviewsTask = executor.submit(() -> fetchReviews(productId));

            // Blocking wait
            Product product = productTask.get(); // Blocks main thread
            List<Review> reviews = reviewsTask.get(); // Blocks main thread

            return new ProductInfo(product, reviews);
        } catch (ExecutionException | InterruptedException e) {
            Throwable cause = e.getCause() != null ? e.getCause() : e;
            System.err.println("Error processing: " + cause.getMessage());
            throw new RuntimeException("Fetch failed", cause);
        } finally {
            System.out.println("Total time taken: " + Duration.between(start, Instant.now()).toMillis() + "ms");
        }
    }

    private Product fetchProduct(Long productId) throws InterruptedException {
        System.out.println(Thread.currentThread().getName() + " -> Fetching product...");
        // Simulate a database failure after 1 second
        Thread.sleep(Duration.ofSeconds(1));
        throw new RuntimeException("Database connection failed for product details");
    }

    private List<Review> fetchReviews(Long productId) throws InterruptedException {
        System.out.println(Thread.currentThread().getName() + " -> Fetching reviews...");
        // Simulate a slow database query taking 5 seconds
        Thread.sleep(Duration.ofSeconds(5));
        System.out.println(Thread.currentThread().getName() + " -> Reviews fetch complete!"); // Thread Leak! Runs even after failure.
        return List.of(new Review(1L, "Excellent!", 5, productId));
    }

    public static void main(String[] args) throws Exception {
        UnstructuredProductService service = new UnstructuredProductService();
        try {
            service.fetchProductInfo(1L);
        } catch (Exception e) {
            System.out.println("Caught Expected Service Error: " + e.getMessage());
        }
        // Keep process alive to see the background thread leak print its statement
        Thread.sleep(Duration.ofSeconds(6));
    }
}
```

##### How the Unstructured Product Service Works

1. **Spawning Tasks (`submit()`)**: We submit two tasks to the virtual executor. Since it is a virtual thread executor, it spawns a brand new virtual thread for each task instead of using a pool. The main thread immediately gets two `Future` objects.
2. **Blocking Wait**: The main thread calls `productTask.get()`, which blocks. The main thread goes to sleep, freeing its carrier thread, until the product task completes.
3. **Errors and Latency Penalty**:
   - `fetchProduct` is simulated to fail after 1 second.
   - When it fails, `productTask.get()` throws an `ExecutionException`.
   - Since the executor is inside a try-with-resources block, it automatically calls `executor.close()` when exiting the block.
   - However, `close()` blocks the main thread until all outstanding threads (like `fetchReviews`, which takes 5 seconds) finish.
   - So, the main thread is frozen from 1 second to 5 seconds just waiting for the sibling task to finish, even though we already know the overall operation failed.
   - This makes the total time **5 seconds** instead of **1 second**, wasting time and resources.

#### Console Output Analysis
When executing this unstructured code, the JVM logs show:
1. `t = 0ms` -> Spawns virtual threads for `fetchProduct` and `fetchReviews`.
2. `t = 1000ms` -> `fetchProduct` throws the database exception. The task fails.
3. `t = 5000ms` -> Sibling task prints `Reviews fetch complete!`.
4. `t = 5005ms` -> The catch block intercepts the error, printing: `Error processing: Database connection failed for product details`.
5. `t = 5006ms` -> Finally block runs: `Total time taken: 5006ms`.
6. The entire process took 5 seconds because the unstructured executor lacks cooperative cancellation support. It has to wait for all threads to terminate in `close()`, resulting in a severe response latency penalty.

---

## 2. The Promise of Structured Concurrency

Structured Concurrency addresses these issues by enforcing a strict **parent-child hierarchy** on concurrent tasks, mapping the execution control flow to the lexical scope of the code block.

```
        [Parent Scope Start]
                 │
         ┌───────┴───────┐
         ▼               ▼
    [Subtask A]     [Subtask B]
         │               │
         └───────┬───────┘
                 ▼
           [Scope Join]
                 │
         [Parent Scope End]
```

### Core Principles
1. **Task Boundaries**: All subtasks spawned within a block must finish or be cancelled before the block exits.
2. **Supervised Lifetime**: The parent task acts as a supervisor. If a subtask fails, the parent scope automatically cancels all sibling subtasks.
3. **No Orphan Threads**: When the scope closes, Java guarantees that all subtasks have terminated.
4. **Simple Code**: Code reads sequentially, and errors propagate cleanly up the stack.

---

## 3. The `StructuredTaskScope` API

Java's `StructuredTaskScope` API (a preview feature in JDK 24/25) is the core of structured concurrency. It implements `AutoCloseable` and must be used within a `try-with-resources` block.

```java
try (var scope = StructuredTaskScope.open()) {
    Subtask<Product> productTask = scope.fork(() -> fetchProduct(productId));
    Subtask<List<Review>> reviewsTask = scope.fork(() -> fetchReviews(productId));
    
    scope.join(); // Wait for all subtasks to complete or cancel
    
    // Results are only safe to access after join() returns successfully
    return new ProductInfo(productTask.get(), reviewsTask.get());
} // scope.close() is called automatically here
```

##### How StructuredTaskScope Works

1. **Binding (`open()`)**: `StructuredTaskScope.open()` creates a scope. The thread that opens it (the owner) is the only one that can call `join()` or `close()`.
2. **Spawning Tasks (`fork()`)**: `scope.fork(Callable)` spawns a task on a new virtual thread and returns a `Subtask` handle. A `Subtask` has three states:
   - `UNAVAILABLE`: Running or not started yet.
   - `SUCCESS`: Completed successfully. You can call `.get()` to get the result.
   - `FAILED`: Failed with an error. You can call `.exception()` to get the error.
   *Rule*: Calling `.get()` or `.exception()` before `scope.join()` returns throws an `IllegalStateException` to prevent race conditions.
3. **Waiting (`join()`)**: `scope.join()` blocks the parent thread (yielding its carrier thread) until all subtasks finish or the scope is cancelled. If a task fails in a fail-fast scope, the joiner cancels the scope and wakes up the parent thread early.
4. **Closing (`close()`)**: The `try-with-resources` block automatically calls `scope.close()`. This stops new forks, interrupts all running subtasks, and waits for all threads to fully terminate before letting the parent thread proceed.

### Key API Methods

* **`StructuredTaskScope.open()`**: Creates a scope with the default fail-fast policy (`awaitAllSuccessfulOrThrow()`). It uses virtual threads to execute forked tasks.
* **`scope.fork(Callable<T>)`**: Submits a subtask for concurrent execution, returning a `Subtask<T>` handle.
* **`scope.join()`**: Blocks the owner thread until all subtasks have completed (succeeded or failed), or the scope is canceled.
* **`scope.close()`**: Closes the scope, interrupts running tasks, and waits for them to stop.
* **`Subtask.get()`**: Returns the completed task result (throws if called before `join()` or if the subtask failed).
* **`Subtask.exception()`**: Returns the `Throwable` thrown by the subtask (throws if called before `join()`).

### Lifecycle of Scopes and Subtasks

```
[scope.open()] ──► [scope.fork()] ──► [Joiner.onFork()] ──► [Spawn VThread]
                           │                                        │
                     (Scope Canceled)                               ▼
                           │                            [Run Task Execution]
                           ▼                                        │
                    [Skip Thread Start]                             ▼
                                                        [Joiner.onComplete()]
                                                                    │
[scope.join()] ◄───────────────────────────────────────────────────┘
      │
      ├─► Success: Return results / stream
      └─► Failure: Cancel siblings ──► Interruption ──► Throw FailedException
```

---

## 4. The `Joiner` Interface & Built-in Joiners

A `Joiner` monitors subtasks and decides when the parent thread should wake up from `scope.join()`.

### The `Joiner` Interface definition

```java
public interface Joiner<T, R> {
    // Returns the result value on successful completion of join()
    R result();
    
    // Returns the exception to throw from join() when the scope fails
    Throwable exception();
    
    // Invoked by fork() before spawning a thread. Returns true to cancel the scope.
    default boolean onFork(Subtask<? extends T> subtask) {
        return false;
    }
    
    // Invoked when a subtask completes. Returns true to cancel the scope and wake join().
    default boolean onComplete(Subtask<? extends T> subtask) {
        return false;
    }
}
```

### Built-in Joining Policies

Java provides five built-in factory methods for creating common joiners:

| Joiner Factory | Scope Type / Result | Coordination Strategy | Typical Use Case |
| :--- | :--- | :--- | :--- |
| `Joiner.awaitAllSuccessfulOrThrow()` | `StructuredTaskScope<T, Void>` | All subtasks must succeed. If any subtask fails, it immediately cancels all remaining tasks and `join()` throws `FailedException`. | "All-or-nothing" execution of heterogeneous tasks (e.g., product details + reviews). |
| `Joiner.allSuccessfulOrThrow()` | `StructuredTaskScope<T, Stream<Subtask<T>>>` | Similar to the above, but on success, it returns a `Stream` of all completed subtasks. | Batch validation operations where homogeneous tasks must all succeed. |
| `Joiner.anySuccessfulResultOrThrow()` | `StructuredTaskScope<T, T>` | "First-past-the-post". The moment the first subtask succeeds, it cancels all other tasks and returns its result directly. | Replicated service queries (e.g., querying redundant DNS servers). |
| `Joiner.awaitAll()` | `StructuredTaskScope<T, Void>` | Wait for all tasks to complete, whether they succeed or fail. No automatic cancellation occurs. | Resilient servers and background notification batches where partial success is acceptable. |
| `Joiner.allUntil(Predicate<Subtask>)` | `StructuredTaskScope<T, Stream<Subtask<T>>>` | Evaluates a predicate against each subtask as it completes. The first time the predicate returns `true`, the scope is canceled. | Custom cancellation thresholds (e.g., stop if more than 2 subtasks fail). |

---

## 5. Exception Handling & Configuration in StructuredTaskScope

### Exception Handling Patterns

When a `StructuredTaskScope` fails, the parent thread's call to `join()` throws a `StructuredTaskScope.FailedException`. The original exception is accessed via `getCause()`.

#### 1. Pattern Matching for Exceptions
You can inspect the root cause using the Java pattern matching `switch` syntax:

```java
try (var scope = StructuredTaskScope.open()) {
    // fork and join tasks...
    scope.join();
} catch (StructuredTaskScope.FailedException e) {
    Throwable root = e.getCause();
    switch (root) {
        case PaymentDeclinedException pde -> handleDeclinedPayment(pde);
        case InsufficientInventoryException iie -> restockProduct(iie);
        case NetworkTimeoutException nte -> retryTransaction(nte);
        default -> logGenericError(root);
    }
} catch (InterruptedException e) {
    Thread.currentThread().interrupt();
    throw new RuntimeException("Interrupted processing", e);
}
```

#### 2. Handling Errors Locally
If an exception from a subtask is not fatal, catch it *inside* the subtask callable. This prevents the scope from shutting down:

```java
scope.fork(() -> {
    try {
        return fetchOptionalRecommendation();
    } catch (Exception e) {
        System.err.println("Failed to fetch recommendations: " + e.getMessage());
        return List.of(); // Return a safe default fallback value
    }
});
```

### Scope Configuration

You can customize the execution context of a scope using `StructuredTaskScope.open(Joiner, Function<Configuration, Configuration>)`. The `Configuration` builder supports:

1. **Custom ThreadFactory**: Useful for naming virtual threads for diagnostics.
2. **Scope Names**: Descriptive labels shown in structured thread dumps.
3. **Timeout Limits**: Imposes an absolute timeout limit on the scope, starting when the scope is opened.

```java
ThreadFactory factory = Thread.ofVirtual().name("payment-worker-", 0).factory();

try (var scope = StructuredTaskScope.open(
        Joiner.awaitAllSuccessfulOrThrow(),
        config -> config.withThreadFactory(factory)
                        .withTimeout(Duration.ofSeconds(5))
                        .withName("PaymentProcessorScope"))) {
    scope.fork(this::validateAccount);
    scope.fork(this::deductFunds);
    scope.join();
} catch (StructuredTaskScope.TimeoutException e) {
    System.err.println("Payment processing timed out after 5 seconds!");
} catch (StructuredTaskScope.FailedException e) {
    System.err.println("Payment processing failed: " + e.getCause().getMessage());
}
```

---

## 6. Custom Joiners: Implementation Guide

When the built-in policies do not fit your logic, you can write custom policies by implementing the `StructuredTaskScope.Joiner<T, R>` interface.

The coordination behavior is driven by two main event hooks:
1. `onFork(Subtask<? extends T> subtask)`: Invoked by the parent thread *before* it spawns the virtual thread for the forked task. If it returns `true`, the scope is canceled immediately and no new threads are spun up.
2. `onComplete(Subtask<? extends T> subtask)`: Invoked by a subtask virtual thread immediately when it finishes execution (whether successfully, by throwing an exception, or by being canceled). If this method returns `true`, it triggers a cooperative cancellation of all active tasks in the scope and wakes the parent thread waiting on `join()`.

Below are the implementations of five custom joiners addressing distinct coordination patterns.

---

### 1. `CollectingJoiner`
Gathers both successes and failures concurrently. This is useful for batch processing systems where you must collect results and exceptions without aborting the entire process if a subset of tasks fails.

```java
import java.util.List;
import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.StructuredTaskScope;

/**
 * A custom joiner that collects all successful results and thrown exceptions.
 * It does not trigger premature cancellation, allowing all tasks to run to completion.
 *
 * @param <T> the type of the subtask results
 */
public class CollectingJoiner<T> implements StructuredTaskScope.Joiner<T, CollectingJoiner.Result<T>> {

    private final Queue<T> successes = new ConcurrentLinkedQueue<>();
    private final Queue<Throwable> failures = new ConcurrentLinkedQueue<>();

    public record Result<T>(List<T> successes, List<Throwable> failures) {
        public boolean hasFailures() { return !failures.isEmpty(); }
    }

    @Override
    public boolean onComplete(StructuredTaskScope.Subtask<? extends T> subtask) {
        switch (subtask.state()) {
            case SUCCESS -> successes.add(subtask.get());
            case FAILED -> failures.add(subtask.exception());
            case UNAVAILABLE -> failures.add(new RuntimeException("Task canceled before execution"));
        }
        // Return false to ensure the scope does not cancel. We want all tasks to finish.
        return false; 
    }

    @Override
    public Result<T> result() {
        return new Result<>(List.copyOf(successes), List.copyOf(failures));
    }

    @Override
    public Throwable exception() {
        // Since we allow all tasks to finish, we do not have a single root failure exception.
        // We expose the first failure as a representative exception if any exist.
        return failures.isEmpty() ? null : failures.peek();
    }
}
```

##### How `CollectingJoiner` Works
1. **Thread-Safe Collections**: Uses `ConcurrentLinkedQueue` which uses lock-free Compare-And-Swap (CAS) operations. This avoids monitor locks and prevents carrier thread pinning.
2. **Subtask State Evaluation**: Reads the state of each subtask to safely collect results or exceptions.
3. **No-Cancellation Contract**: Returns `false` in `onComplete()` to keep all tasks running.
4. **Defensive Copying**: The `result()` method returns a defensive copy of the collections using `List.copyOf()`, preventing downstream modifications.

---

### 2. `QuorumJoiner`
Completes early as soon as a required quorum (e.g., $N$ out of $M$ tasks) succeeds. This pattern is fundamental in distributed write consensus and highly available cluster coordination.

```java
import java.util.concurrent.StructuredTaskScope;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * A custom joiner that signals completion once a specified number of successful subtasks is reached.
 * Once the quorum threshold is reached, it cancels all remaining active tasks in the scope.
 *
 * @param <T> the type of subtask results
 */
public class QuorumJoiner<T> implements StructuredTaskScope.Joiner<T, Boolean> {

    private final int requiredSuccesses;
    private final AtomicInteger successCount = new AtomicInteger(0);
    private final AtomicInteger totalCount = new AtomicInteger(0);
    private volatile boolean quorumReached = false;

    public QuorumJoiner(int requiredSuccesses) {
        if (requiredSuccesses <= 0) {
            throw new IllegalArgumentException("Quorum threshold must be greater than zero");
        }
        this.requiredSuccesses = requiredSuccesses;
    }

    @Override
    public boolean onFork(StructuredTaskScope.Subtask<? extends T> subtask) {
        totalCount.incrementAndGet();
        return false;
    }

    @Override
    public boolean onComplete(StructuredTaskScope.Subtask<? extends T> subtask) {
        if (subtask.state() == StructuredTaskScope.Subtask.State.SUCCESS) {
            int current = successCount.incrementAndGet();
            if (current >= requiredSuccesses) {
                quorumReached = true;
                // Return true to trigger scope cancellation and wake the parent thread
                return true; 
            }
        }
        return false;
    }

    @Override
    public Boolean result() {
        return quorumReached;
    }

    @Override
    public Throwable exception() {
        return quorumReached ? null : new RuntimeException("Consensus Quorum not met. Successes: " 
                + successCount.get() + "/" + requiredSuccesses);
    }
}
```

##### How `QuorumJoiner` Works
1. **Atomic Counters**: Uses `AtomicInteger` for thread-safe counting without locking carrier threads.
2. **Early Cancellation**: Returns `true` from `onComplete()` when the quorum is reached. This cancels sibling tasks and wakes the parent thread early.
3. **Consensus Exception**: If the scope finishes joining but the quorum is not met, `exception()` returns a consensus failure exception.

---

### 3. `AdaptiveJoiner`
Acts as a dynamic circuit breaker. It cancels the scope early if the failure rate of completed tasks exceeds a specific percentage threshold, provided a minimum sample size is met.

```java
import java.util.List;
import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.StructuredTaskScope;

/**
 * A custom joiner that acts as an in-scope circuit breaker.
 * It cancels remaining tasks if the failure rate exceeds the threshold.
 *
 * @param <T> the type of subtask results
 */
public class AdaptiveJoiner<T> implements StructuredTaskScope.Joiner<T, CollectingJoiner.Result<T>> {

    private final double maxFailureRate; // e.g., 0.3 for 30%
    private final int minSampleSize;
    private final Queue<T> successes = new ConcurrentLinkedQueue<>();
    private final Queue<Throwable> failures = new ConcurrentLinkedQueue<>();
    private volatile boolean circuitBroken = false;

    public AdaptiveJoiner(double maxFailureRate, int minSampleSize) {
        if (maxFailureRate < 0.0 || maxFailureRate > 1.0) {
            throw new IllegalArgumentException("Failure rate must be between 0.0 and 1.0");
        }
        this.maxFailureRate = maxFailureRate;
        this.minSampleSize = minSampleSize;
    }

    @Override
    public boolean onComplete(StructuredTaskScope.Subtask<? extends T> subtask) {
        switch (subtask.state()) {
            case SUCCESS -> successes.add(subtask.get());
            case FAILED -> failures.add(subtask.exception());
            case UNAVAILABLE -> failures.add(new RuntimeException("Task canceled"));
        }

        int total = successes.size() + failures.size();
        if (total >= minSampleSize) {
            double currentFailureRate = (double) failures.size() / total;
            if (currentFailureRate > maxFailureRate) {
                circuitBroken = true;
                // Return true to break the circuit, cancel siblings, and wake up join()
                return true; 
            }
        }
        return false;
    }

    @Override
    public CollectingJoiner.Result<T> result() {
        return new CollectingJoiner.Result<>(List.copyOf(successes), List.copyOf(failures));
    }

    @Override
    public Throwable exception() {
        return circuitBroken 
            ? new RuntimeException("Circuit breaker activated: failure rate exceeded " + maxFailureRate) 
            : (failures.isEmpty() ? null : failures.peek());
    }
}
```

##### How `AdaptiveJoiner` Works
1. **Warmup Window**: `minSampleSize` prevents early cancellation from a single initial failure.
2. **Dynamic Interruption**: Cancels sibling tasks when the failure rate is too high, saving resources.
3. **State Querying**: Exposes circuit status via `exception()`, allowing systems to map failures to HTTP codes or trigger fallbacks.

---

### 4. `RateLimitedJoiner`
Uses a `Semaphore` to limit the concurrency of task execution under the scope. This prevents overloading external APIs, third-party microservices, or downstream databases.

```java
import java.util.List;
import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.Semaphore;
import java.util.concurrent.StructuredTaskScope;

/**
 * A custom joiner that enforces a maximum concurrency ceiling on forked tasks.
 *
 * @param <T> the type of subtask results
 */
public class RateLimitedJoiner<T> implements StructuredTaskScope.Joiner<T, List<T>> {

    private final Semaphore semaphore;
    private final Queue<T> results = new ConcurrentLinkedQueue<>();
    private final Queue<Throwable> failures = new ConcurrentLinkedQueue<>();

    public RateLimitedJoiner(int maxConcurrentTasks) {
        if (maxConcurrentTasks <= 0) {
            throw new IllegalArgumentException("Concurrency limit must be greater than zero");
        }
        this.semaphore = new Semaphore(maxConcurrentTasks);
    }

    @Override
    public boolean onFork(StructuredTaskScope.Subtask<? extends T> subtask) {
        try {
            // Blocks the owner (parent) thread inside fork() if concurrency limit is met.
            // When using virtual threads, blocking here is extremely cheap.
            semaphore.acquire(); 
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            // Cancel the fork attempt if interrupted
            return true; 
        }
        return false;
    }

    @Override
    public boolean onComplete(StructuredTaskScope.Subtask<? extends T> subtask) {
        try {
            switch (subtask.state()) {
                case SUCCESS -> results.add(subtask.get());
                case FAILED -> failures.add(subtask.exception());
                case UNAVAILABLE -> failures.add(new RuntimeException("Canceled"));
            }
        } finally {
            // Release the permit back to the semaphore to let other waiting forks proceed
            semaphore.release(); 
        }
        return false;
    }

    @Override
    public List<T> result() {
        return List.copyOf(results);
    }

    @Override
    public Throwable exception() {
        return failures.isEmpty() ? null : failures.peek();
    }
}
```

##### How `RateLimitedJoiner` Works
1. **Throttling**: `semaphore.acquire()` inside `onFork()` blocks the parent thread if the limit is reached.
2. **VThread Efficiency**: If the parent thread is virtual, blocking just parks it, yielding its carrier thread to run other work.
3. **Permit Release**: The `onComplete()` block wraps the permit release in a `finally` block to prevent resource leakage.

---

### 5. `ConditionalJoiner`
Evaluates a condition supplier (e.g., memory limits, CPU metrics, or database pool health checks) before spawning a new subtask. If the condition is not met, execution aborts immediately.

```java
import java.util.List;
import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.StructuredTaskScope;
import java.util.function.Supplier;

/**
 * A custom joiner that checks a health or status condition before forks.
 * If the condition evaluates to false, it aborts execution.
 *
 * @param <T> the type of subtask results
 */
public class ConditionalJoiner<T> implements StructuredTaskScope.Joiner<T, List<T>> {

    private final Supplier<Boolean> condition;
    private final Queue<T> results = new ConcurrentLinkedQueue<>();
    private final Queue<Throwable> failures = new ConcurrentLinkedQueue<>();
    private volatile boolean conditionFailed = false;

    public ConditionalJoiner(Supplier<Boolean> condition) {
        this.condition = condition;
    }

    @Override
    public boolean onFork(StructuredTaskScope.Subtask<? extends T> subtask) {
        if (!condition.get()) {
            conditionFailed = true;
            // Return true to cancel the scope immediately, preventing the thread from starting
            return true; 
        }
        return false;
    }

    @Override
    public boolean onComplete(StructuredTaskScope.Subtask<? extends T> subtask) {
        switch (subtask.state()) {
            case SUCCESS -> results.add(subtask.get());
            case FAILED -> failures.add(subtask.exception());
            case UNAVAILABLE -> failures.add(new RuntimeException("Task canceled"));
        }
        return false;
    }

    @Override
    public List<T> result() {
        return List.copyOf(results);
    }

    @Override
    public Throwable exception() {
        return conditionFailed ? new RuntimeException("Precondition failed: System condition became unhealthy") : null;
    }
}
```

##### How `ConditionalJoiner` Works
1. **Dynamic Preconditions**: The condition is evaluated right before the subtask thread starts (e.g., check if heap usage is under 90%).
2. **Volatile Visibility**: Uses a `volatile` flag to ensure all threads see the health check failure instantly.
3. **Clean Abort**: If the condition is false, `onFork()` returns `true`, cancelling the scope and active subtasks.

---

## 7. Memory Consistency & Nested Scopes

### Memory Consistency Guarantees
`StructuredTaskScope` provides clear memory visibility contracts based on happens-before rules:

1. **Fork Happens-Before Edge**: Actions in the owner thread of a `StructuredTaskScope` *prior* to calling `fork(Runnable/Callable)` happen-before actions taken by the subtask thread.
2. **Join Happens-Before Edge**: The completion of actions in a subtask thread happens-before the retrieval of the result via `Subtask.get()` or `Subtask.exception()` by the owner thread after `join()` returns.

```
[Owner Thread]                  [Subtask Thread]
Write sharedState = 123
Call scope.fork()  ──happens-before──► Read sharedState (sees 123)
                                      Write subtaskResult = "Done"
Call scope.join()  ◄──happens-before── (Subtask Exits)
Read subtaskResult (sees "Done")
```

#### JVM Implementation of Happens-Before in StructuredTaskScope

The happens-before guarantees are implemented using memory barriers and internal synchronization mechanisms:

1. **The `fork` Barrier**:
   - At the JVM level, before launching the subtask virtual thread, the owner thread performs a write operation containing a volatile memory fence or a synchronized monitor write.
   - When the newly spawned virtual thread starts, its initial state reading acts as a memory read barrier. This invalidates its processor core's L1/L2 caches and forces a reload from the shared L3/main memory, ensuring it sees all modifications made by the owner thread prior to the `fork()` call.

2. **The `join` Barrier**:
   - When a subtask completes, it updates its state to `SUCCESS` or `FAILED` via a volatile or CAS write operation, then signals the scope flock.
   - When the subtask finishes and wakes the owner thread, the owner thread acquires the synchronization lock or reads the volatile state of the completed subtask. This acquisition acts as a memory read barrier, flushing the owner thread core's invalidation queues and loading the final output variables written by the subtask thread.

### Nested Scopes

You can nest `StructuredTaskScope` instances to construct complex execution hierarchies. The parent scope supervises the child scope's coordinator.

```
Level 1: Document Processing Scope
  ├── Level 2: Header Fetching (Subtask)
  ├── Level 2: Body Fetching (Subtask)
  └── Level 2: Document Analysis Scope (Nested Child Scope)
         ├── Level 3: Sentiment Analysis (Subtask)
         └── Level 3: Word Count Check (Subtask)
```

If the parent scope is canceled, cancellation propagates recursively to the nested scopes. This ensures that no orphan tasks continue running in the background when the main task flow has already failed.

#### Nested Scopes Code Example

```java
import java.time.Duration;
import java.util.concurrent.StructuredTaskScope;

public class DocumentProcessor {

    public record DocumentReport(String header, String body, int wordCount, String sentiment) {}

    public DocumentReport processDocument(String docId) throws Exception {
        // Level 1 Scope: Gathering
        try (var gatherScope = StructuredTaskScope.open()) {
            var headerTask = gatherScope.fork(() -> fetchHeader(docId));
            var bodyTask = gatherScope.fork(() -> fetchBody(docId));
            
            gatherScope.join();
            
            // Level 2 Scope is invoked sequentially after Level 1 completes
            return analyzeContent(headerTask.get(), bodyTask.get());
        } catch (StructuredTaskScope.FailedException e) {
            throw new RuntimeException("Document processing aborted", e.getCause());
        }
    }

    private DocumentReport analyzeContent(String header, String body) throws Exception {
        // Level 2 Scope: Nested Analysis
        try (var analysisScope = StructuredTaskScope.open()) {
            var wordCountTask = analysisScope.fork(() -> countWords(body));
            var sentimentTask = analysisScope.fork(() -> calculateSentiment(body));
            
            analysisScope.join();
            
            return new DocumentReport(header, body, wordCountTask.get(), sentimentTask.get());
        }
    }

    private String fetchHeader(String docId) throws InterruptedException {
        Thread.sleep(Duration.ofMillis(200));
        return "Header for " + docId;
    }

    private String fetchBody(String docId) throws InterruptedException {
        Thread.sleep(Duration.ofMillis(300));
        return "This is the body content of document " + docId;
    }

    private int countWords(String text) {
        return text.split("\\s+").length;
    }

    private String calculateSentiment(String text) {
        return text.contains("content") ? "Positive" : "Neutral";
    }

    public static void main(String[] args) throws Exception {
        DocumentProcessor processor = new DocumentProcessor();
        DocumentReport report = processor.processDocument("DOC-555");
        System.out.println("Result Word Count: " + report.wordCount());
        System.out.println("Result Sentiment: " + report.sentiment());
    }
}
```

##### How Nesting Task Hierarchies Work
1. **Level 1 Scope Setup**: In `processDocument()`, the primary thread opens the parent scope (`gatherScope`) and forks tasks to fetch the document header and body concurrently.
2. **Parent Coordination**: The call `gatherScope.join()` blocks the parent thread until both fetch tasks complete. The results are gathered via `headerTask.get()` and `bodyTask.get()`.
3. **Level 2 Nested Scope Setup**: The parent thread then passes these results to `analyzeContent()`, which opens a nested child scope (`analysisScope`). The child scope forks sentiment analysis and word count tasks concurrently.
4. **Cancellation Cascades**: If `gatherScope` is canceled (e.g., due to a timeout), the cancellation signals cascade down, interrupting all active child threads in `analysisScope` to ensure clean resource recovery.

---

## 8. Observability & Hierarchical Thread Dumps

Structured scopes group their threads in containers, making them easy to see in JSON thread dumps.

### Programmatic Thread Dump Generation

Using the `HotSpotDiagnosticMXBean`, you can capture structured thread dumps programmatically inside error catch blocks:

```java
import com.sun.management.HotSpotDiagnosticMXBean;
import java.io.IOException;
import java.lang.management.ManagementFactory;
import java.nio.file.Path;
import java.util.concurrent.StructuredTaskScope;

public class ProgrammaticThreadDump {

    public static void captureDump(Path outputPath) {
        try {
            HotSpotDiagnosticMXBean bean = ManagementFactory.getPlatformMXBean(HotSpotDiagnosticMXBean.class);
            bean.dumpThreads(outputPath.toAbsolutePath().toString(), HotSpotDiagnosticMXBean.ThreadDumpFormat.JSON);
            System.out.println("Hierarchical JSON Thread dump successfully saved to " + outputPath);
        } catch (IOException e) {
            System.err.println("Failed to capture thread dump: " + e.getMessage());
        }
    }
}
```

### Generating Dumps via CLI (`jcmd`)

You can generate JSON thread dumps using the terminal command:

```powershell
# Get the Java process ID (PID)
jps

# Capture the structured thread dump
jcmd <PID> Thread.dump_to_file -format=json output.json
```

### Analyzing the JSON Output

The resulting JSON file structures threads into containers matching your scopes:

```json
{
  "threadDump": {
    "processId": "14210",
    "threadContainers": [
      {
        "container": "<root>",
        "threads": [
          {
            "tid": "1",
            "name": "main",
            "stack": [
              "java.base/java.util.concurrent.StructuredTaskScopeImpl.join(StructuredTaskScopeImpl.java:243)",
              "ca.bazlur.mcj.chap4.DocumentProcessor.processDocument(DocumentProcessor.java:23)"
            ]
          }
        ]
      },
      {
        "container": "doc-gathering-scope/jdk.internal.misc.ThreadFlock$ThreadContainerImpl@78fd3572",
        "parent": "<root>",
        "owner": "1",
        "threads": [
          {
            "tid": "36",
            "name": "doc-proc-1",
            "stack": [
              "java.base/java.lang.Thread.sleep(Thread.java:574)",
              "ca.bazlur.mcj.chap4.DocumentProcessor.fetchBody(DocumentProcessor.java:69)"
            ]
          }
        ]
      }
    ]
  }
}
```
*Observe how `doc-proc-1` is explicitly grouped inside the container `doc-gathering-scope`, referencing `owner: "1"` (the main thread).*

---

## 9. Office Analogy: The Family Vacation

To understand structured concurrency, let us look at a simple family vacation analogy.

Imagine a parent (the Parent Thread) taking their three children—Alice, Bob, and Charlie (the Subtask Threads)—on a family trip to a museum. The parent wants to coordinate three tasks:
1. Alice buys the admission tickets.
2. Bob buys drinks from the cafeteria.
3. Charlie checks the museum map.

### The Unstructured Concurrency Model (The Chaos Trip)
In traditional, unstructured concurrent programming (using standard thread pools or `ExecutorService` without scope blocks):
- The parent tells the children at the entrance: *"Go run around and do your tasks. I will wait here near the door. We will meet back when you are all done."*
- **Scenario A (A child gets lost)**: Bob goes to the cafeteria, but gets stuck in a line or wanders out of the building. The parent stands at the entrance waiting forever, unaware that Bob is lost. This is a **thread leak**.
- **Scenario B (A child gets hurt)**: Alice goes to buy tickets, but trips, scrapes her knee, and starts crying (an exception occurs). Alice cannot complete her task. However, because the children are running around independently, the parent doesn't find out until much later. Bob and Charlie keep wandering the museum doing their tasks, wasting energy and resources, even though the trip is ruined.
- **Scenario C (Leaving early)**: The parent decides they must return home immediately due to an emergency (Task cancellation). The parent leaves the building, but has no way to call Bob or Charlie back. They are left wandering the museum indefinitely as orphan threads.

### The Structured Concurrency Model (The Family Safety Rope)
In modern, structured programming (using `StructuredTaskScope`):
- The parent connects everyone together with a flexible safety rope (the Scope boundary).
- **Scenario A (A child gets hurt)**: Alice starts buying tickets but encounters an error (an exception). The moment she fails, the parent is notified immediately. The parent blows a whistle (Cooperative Cancellation), which sends a signal to Bob and Charlie: *"Stop what you are doing, cancel your tasks, and return to the entrance immediately."* Bob and Charlie stop waiting in line, and the family leaves the building together. No time or energy is wasted.
- **Scenario B (Clean exit)**: The parent cannot leave the museum without checking that all children are accounted for. The `scope.close()` method acts as the parent checking the headcount at the exit gate. It blocks until every child thread is fully returned, ensuring that no orphan threads are left behind in the system.

---

## 10. Structured Concurrency Design Blueprint: Building a Parallel Scraping and Aggregation Pipeline

Let us design a production-grade **Web Scraper and Aggregator** using `StructuredTaskScope.ShutdownOnFailure`. This service scrapes news articles from different domains concurrently, extracts their metadata, and saves them to a database.

### Resiliency Constraints
1. **Critical Fetching**: Fetching the article's core content is required. If the primary content fetch fails, the scraping transaction must abort immediately.
2. **Parallel Subtasks**: We must fork subtasks to scrape the core content and extract tags concurrently.
3. **Cooperative Interrupts**: Subtasks must monitor their execution and terminate quickly if a sibling task fails.

### Complete Implementation Blueprint
```java
package com.example.scraper;

import java.io.IOException;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.StructuredTaskScope;
import java.util.concurrent.StructuredTaskScope.Subtask;

public class ScraperCoordinator {

    public record Article(String url, String content, List<String> tags) {}

    public Article scrapeArticle(String url) throws Exception {
        System.out.println("Scraper: Beginning transaction for " + url);
        
        try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
            
            // Fork critical task 1: Scrape text content
            Subtask<String> contentTask = scope.fork(() -> {
                System.out.println("  Subtask Content: Connecting to server...");
                Thread.sleep(Duration.ofMillis(300)); // Simulate network read
                if (url.contains("malicious")) {
                    System.err.println("  Subtask Content: Connection rejected!");
                    throw new IOException("Host blocked by firewall");
                }
                System.out.println("  Subtask Content: Text fetched successfully.");
                return "Java Modern Concurrency is amazing...";
            });

            // Fork critical task 2: Extract metadata tags
            Subtask<List<String>> tagsTask = scope.fork(() -> {
                System.out.println("  Subtask Tags: Reading meta headers...");
                Thread.sleep(Duration.ofMillis(200)); // Simulate header parsing
                System.out.println("  Subtask Tags: Headers parsed.");
                return List.of("java", "concurrency", "loom");
            });

            // Block owner thread until both subtasks complete successfully
            // or one of them fails.
            scope.join();
            
            // Throw the original exception if either subtask failed
            scope.throwIfFailed();

            // Assemble and return the complete Article record
            System.out.println("Scraper: Aggregation complete for " + url);
            return new Article(url, contentTask.get(), tagsTask.get());
            
        } catch (StructuredTaskScope.FailedException e) {
            System.err.println("Scraper aborted due to error: " + e.getCause().getMessage());
            throw new RuntimeException("Scraping failed", e.getCause());
        }
    }
}
```

##### How the Scraper Coordinator Works
1. **Scope boundary**: `try (var scope = new StructuredTaskScope.ShutdownOnFailure())` opens the scope.
2. **Concurrent Forking**: Spawns tasks to fetch content and tags concurrently on virtual threads.
3. **Consensus**: `scope.join()` blocks the main thread. If one task fails, it cancels the other and resumes the parent thread early.
4. **No Leaks**: `scope.close()` ensures both threads are stopped before throwing the error.

---

## 11. Hands-On Labs

Ensure you compile and execute these labs using the preview flags:
```powershell
# Compile and run with preview flags
javac --enable-preview --release 24 Lab.java
java --enable-preview Lab
```

### Lab 4.1: Unstructured vs Structured Product Service
**Objective**: Build a product info aggregator comparing an `ExecutorService` thread-leak failure model with `StructuredTaskScope`. Simulate: reviews failing in 1s, product fetching taking 5s.

```java
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.StructuredTaskScope;

public class Lab41ProductService {

    public record Product(long id, String name) {}
    public record Review(String comment, int rating) {}
    public record ProductInfo(Product product, List<Review> reviews) {}

    // 1. Unstructured Concurrency
    public ProductInfo fetchUnstructured(long id) throws Exception {
        Instant start = Instant.now();
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            Future<Product> prodFuture = executor.submit(() -> {
                System.out.println("Unstructured: Fetching product (will take 5s)...");
                Thread.sleep(Duration.ofSeconds(5));
                System.out.println("Unstructured: Product fetch complete!");
                return new Product(id, "Premium Laptop");
            });

            Future<List<Review>> revFuture = executor.submit(() -> {
                System.out.println("Unstructured: Fetching reviews (will fail in 1s)...");
                Thread.sleep(Duration.ofSeconds(1));
                throw new RuntimeException("Reviews Database Unavailable!");
            });

            // Blocks on product first
            Product p = prodFuture.get();
            List<Review> r = revFuture.get();
            return new ProductInfo(p, r);
        } finally {
            System.out.println("Unstructured elapsed: " + Duration.between(start, Instant.now()).toMillis() + "ms");
        }
    }

    // 2. Structured Concurrency
    public ProductInfo fetchStructured(long id) throws Exception {
        Instant start = Instant.now();
        try (var scope = StructuredTaskScope.open()) {
            var prodTask = scope.fork(() -> {
                try {
                    System.out.println("Structured: Fetching product (will take 5s)...");
                    Thread.sleep(Duration.ofSeconds(5));
                    System.out.println("Structured: Product fetch complete!");
                    return new Product(id, "Premium Laptop");
                } catch (InterruptedException e) {
                    System.out.println("Structured: Product fetch caught cancellation interrupt!");
                    throw e;
                }
            });

            var revTask = scope.fork(() -> {
                System.out.println("Structured: Fetching reviews (will fail in 1s)...");
                Thread.sleep(Duration.ofSeconds(1));
                throw new RuntimeException("Reviews Database Unavailable!");
            });

            scope.join();
            return new ProductInfo(prodTask.get(), revTask.get());
        } catch (StructuredTaskScope.FailedException e) {
            System.err.println("Structured Scope aborted due to subtask failure: " + e.getCause().getMessage());
            throw new RuntimeException(e.getCause());
        } finally {
            System.out.println("Structured elapsed: " + Duration.between(start, Instant.now()).toMillis() + "ms");
        }
    }

    public static void main(String[] args) throws Exception {
        Lab41ProductService lab = new Lab41ProductService();
        System.out.println("--- Starting Unstructured Test ---");
        try {
            lab.fetchUnstructured(1L);
        } catch (Exception e) {
            System.out.println("Unstructured execution caught error.");
        }
        
        Thread.sleep(1000);
        System.out.println("\n--- Starting Structured Test ---");
        try {
            lab.fetchStructured(1L);
        } catch (Exception e) {
            System.out.println("Structured execution caught error.");
        }

        // Wait to let background logs print
        Thread.sleep(2000);
    }
}
```

##### How `Lab41ProductService` Works
1. **Comparison of Resource Lifetimes**: In the `fetchUnstructured` method, when `revFuture` fails after 1 second, the main thread is still blocked at `prodFuture.get()`. It has no mechanism to know that a sibling thread failed, so it continues to wait for the 5-second task. In `fetchStructured`, both tasks are registered within the `StructuredTaskScope`. As soon as `revTask` fails with an exception at $t = 1\text{s}$, the scope's coordination logic intercepts this and triggers cooperative cancellation.
2. **Interruption Mechanics of Sibling Tasks**: When the scope initiates cancellation at $t = 1\text{s}$, it invokes `Thread.interrupt()` on the virtual thread running the `prodTask`. The virtual thread is currently blocked inside `Thread.sleep(5000)`. The JVM interrupts the sleep, causing the thread to wake up early and throw an `InterruptedException`.
3. **Latency and Resource Gains**: Because `prodTask` is aborted early, the parent thread's call to `scope.join()` returns immediately at $t = 1\text{s}$. The try-with-resources statement executes `scope.close()`, which blocks until both subtask virtual threads are fully terminated, avoiding any thread or resource leaks. The total elapsed time printed is approximately **1000ms**, showing a massive latency and CPU saving compared to the **5000ms** of the unstructured executor.

---

### Lab 4.2: Batch User Validation with `allSuccessfulOrThrow`
**Objective**: Validate a batch of users concurrently. If any user validation fails, the entire batch process must cancel.

```java
import java.time.Duration;
import java.util.List;
import java.util.Random;
import java.util.concurrent.StructuredTaskScope;
import java.util.concurrent.StructuredTaskScope.Joiner;
import java.util.concurrent.StructuredTaskScope.Subtask;
import java.util.stream.Stream;

public class Lab42BatchValidation {

    public record User(long id, String email, boolean isValid) {}

    public static void main(String[] args) throws Exception {
        List<User> batch = List.of(
            new User(101, "inaya@example.com", true),
            new User(102, "malicious-user", false), // Will trigger failure
            new User(103, "rushda@example.com", true)
        );

        System.out.println("Checking batch validation concurrently...");
        try (var scope = StructuredTaskScope.open(Joiner.<User>allSuccessfulOrThrow())) {
            List<Subtask<User>> tasks = batch.stream()
                .map(user -> scope.fork(() -> validateUser(user)))
                .toList();

            Stream<Subtask<User>> results = scope.join();
            System.out.println("All validations passed: " + results.map(Subtask::get).toList());
        } catch (StructuredTaskScope.FailedException e) {
            System.err.println("Batch Validation Failed: " + e.getCause().getMessage());
        }
    }

    private static User validateUser(User u) throws InterruptedException {
        System.out.println("Validating user: " + u.id());
        Thread.sleep(new Random().nextInt(500) + 100);
        if (!u.isValid()) {
            throw new IllegalArgumentException("User " + u.id() + " has invalid email format!");
        }
        return u;
    }
}
```

##### How `Lab42BatchValidation` Works
1. **Joiner Selection**: The scope uses `Joiner.allSuccessfulOrThrow()`. This requires *all* tasks to succeed; otherwise, it cancels the scope. Upon successful completion of `scope.join()`, it returns a `Stream<Subtask<User>>` containing all results.
2. **Fail-Fast Trigger**: The batch list contains a user (id 102) with `isValid = false`. The virtual thread executing `validateUser` for user 102 throws an `IllegalArgumentException`. The joiner intercepts this failure, sets the scope's state to canceled, and interrupts the sibling threads.
3. **Exception Propagation**: The catch block catches the `FailedException`. Calling `e.getCause()` retrieves the original `IllegalArgumentException` thrown by the subtask, printing the error.

---

### Lab 4.3: Multi-Channel Notification with `awaitAll`
**Objective**: Broadcast a system alert concurrently through multiple channels (SMS, Email, Push Notification). Ensure failure in one channel does not cancel delivery to others.

```java
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.StructuredTaskScope;
import java.util.concurrent.StructuredTaskScope.Joiner;

public class Lab43Notifications {

    public record DeliveryReport(String channel, boolean success, String error) {}

    public static void main(String[] args) throws Exception {
        String alertMsg = "CRITICAL SERVER OUTAGE - CODE RED";
        List<DeliveryReport> reports = new CopyOnWriteArrayList<>();

        try (var scope = StructuredTaskScope.open(Joiner.<Void>awaitAll())) {
            scope.fork(() -> {
                sendSms(alertMsg);
                reports.add(new DeliveryReport("SMS", true, null));
                return null;
            });
            scope.fork(() -> {
                sendEmail(alertMsg);
                reports.add(new DeliveryReport("EMAIL", true, null));
                return null;
            });
            scope.fork(() -> {
                sendPush(alertMsg);
                throw new RuntimeException("APNS Server Connection Reset!");
            });

            scope.join(); // Wait for all channels to complete/fail
        } catch (Exception e) {
            System.out.println("Caught unexpected error (should not happen with awaitAll): " + e.getMessage());
        }

        System.out.println("\nNotification Delivery Results:");
        reports.forEach(System.out::println);
    }

    private static void sendSms(String msg) throws InterruptedException {
        Thread.sleep(100);
        System.out.println("SMS sent: " + msg);
    }

    private static void sendEmail(String msg) throws InterruptedException {
        Thread.sleep(200);
        System.out.println("Email sent: " + msg);
    }

    private static void sendPush(String msg) throws InterruptedException {
        Thread.sleep(300);
        System.out.println("Attempting Push Notification...");
    }
}
```

##### How `Lab43Notifications` Works
1. **Wait-All Strategy**: The scope uses `Joiner.awaitAll()`. This blocks the owner thread in `scope.join()` until *all* forked tasks have completed, regardless of whether they succeeded or failed. Sibling tasks are never canceled or interrupted when one of them throws an exception.
2. **Handling Exceptions**: The task running `sendPush` throws a `RuntimeException`. The `awaitAll` joiner records the exception internally but does *not* cancel the scope or interrupt the sibling threads. SMS and Email tasks continue executing normally.
3. **Exposing Results**: When `scope.join()` returns, it does *not* throw an exception. The `reports` list contains the successful SMS and Email deliveries.

---

### Lab 4.4: Custom `QuorumJoiner` Distributed Database
**Objective**: Implement a write operation across 5 databases using the custom `QuorumJoiner`. Return success once at least 3 nodes confirm the write.

```java
import java.time.Duration;
import java.util.List;
import java.util.Random;
import java.util.concurrent.StructuredTaskScope;

public class Lab44QuorumWrite {

    public static void main(String[] args) throws Exception {
        List<String> nodes = List.of("node-A", "node-B", "node-C", "node-D", "node-E");
        int quorumSize = 3;

        System.out.println("Initiating distributed quorum write (quorum = " + quorumSize + ")...");
        try (var scope = StructuredTaskScope.open(new QuorumJoiner<Boolean>(quorumSize))) {
            for (String node : nodes) {
                scope.fork(() -> writeToNode(node, "config-key", "prod-v2"));
            }

            boolean result = scope.join();
            System.out.println("Quorum Write Succeeded: " + result);
        } catch (StructuredTaskScope.FailedException e) {
            System.err.println("Write failed: " + e.getCause().getMessage());
        }
    }

    private static Boolean writeToNode(String node, String key, String value) throws InterruptedException {
        Random r = new Random();
        Thread.sleep(r.nextInt(300) + 100);
        
        // Simulating 30% node failure rate
        if (r.nextDouble() < 0.3) {
            System.out.println("  " + node + " -> Write failure!");
            throw new RuntimeException("Node database disk full!");
        }

        System.out.println("  " + node + " -> Successfully written.");
        return true;
    }
}
```

##### How `Lab44QuorumWrite` Works
1. **Custom Quorum Integration**: The scope is opened with a custom `QuorumJoiner<Boolean>(quorumSize)` instance. The `quorumSize` is configured to `3`, representing the minimum database confirmations required.
2. **Early Cancellation**: As each task completes, the `onComplete(Subtask)` event handler is invoked. When the first three tasks complete successfully, the atomic `successCount` counter reaches `3`. Sibling tasks are canceled, and `scope.join()` returns immediately.
3. **Consensus Outcome**: Since `quorumReached` is `true`, calling `scope.join()` returns the boolean result of `true`.

---

### Lab 4.5: Structured Concurrency with Timeout
**Objective**: Fetch user profile data from a remote API. Configure the scope configuration with a strict 2-second timeout.

```java
import java.time.Duration;
import java.util.concurrent.StructuredTaskScope;
import java.util.concurrent.StructuredTaskScope.Joiner;

public class Lab45Timeout {

    public static void main(String[] args) throws Exception {
        System.out.println("Starting profile fetch with 2s timeout...");
        
        try (var scope = StructuredTaskScope.open(
                Joiner.<String>allSuccessfulOrThrow(),
                config -> config.withTimeout(Duration.ofSeconds(2)))) {
            
            var profileTask = scope.fork(() -> {
                System.out.println("Fetching profile image...");
                Thread.sleep(Duration.ofSeconds(1));
                return "AvatarUrl";
            });

            var statsTask = scope.fork(() -> {
                System.out.println("Fetching transaction history stats (slow)...");
                // Exceeds scope timeout of 2 seconds
                Thread.sleep(Duration.ofSeconds(4)); 
                return "StatsData";
            });

            scope.join();
            System.out.println("Results: " + profileTask.get() + ", " + statsTask.get());
        } catch (StructuredTaskScope.TimeoutException e) {
            System.err.println("API Request Canceled: Operations exceeded the 2-second timeout threshold!");
        } catch (StructuredTaskScope.FailedException e) {
            System.err.println("API Request Failed: " + e.getCause().getMessage());
        }
    }
}
```

##### How `Lab45Timeout` Works
1. **Timeout Parameter Configuration**: The `StructuredTaskScope` is configured with a strict timeout parameter of 2 seconds by passing `config -> config.withTimeout(Duration.ofSeconds(2))` as the second argument to `open()`.
2. **Timeout Interruption**: `profileTask` takes 1 second (succeeds), but `statsTask` takes 4 seconds. At $t = 2\text{s}$, the scope manager transitions the scope to the canceled state and issues cooperative interrupts. The sleeping `statsTask` thread is interrupted, throws `InterruptedException`, and terminates.
3. **Exception Handling**: The parent thread blocked on `scope.join()` is unblocked at $t = 2\text{s}$ and throws a `StructuredTaskScope.TimeoutException`, which is caught in the catch block.

---

## 12. Case Study: Building a High-Throughput Resilient Microservice Gateway

To see how all these modern abstractions fit together in a production-grade environment, we will study the architecture of a high-throughput **Microservice API Gateway**. 

The gateway must handle incoming client requests by aggregating data from several downstream domains:
1. **User Profile Service**: (Required) Fetches account information.
2. **Order History Service**: (Required) Retrieves recent purchase records.
3. **Product Recommendations**: (Optional) Gathers dynamic product suggestions from three external partners.

### Resiliency and Performance Constraints:
- **Core Requirements**: If the user profile or order service fails, the aggregate request must fail immediately.
- **Optional Fallback**: The recommendation subtask is non-critical. If it fails, the gateway should fall back to a static cached recommendations list rather than failing the client request.
- **Quorum Execution**: Recommendations are fetched from three separate partner engines. To minimize tail latency, the recommendations subtask should return as soon as **any two partners** return successful suggestions, canceling the remaining slow search.
- **Backpressure Throttle**: Downstream APIs are protected by a concurrency semaphore.
- **Context Propagation**: A tracing ID and authenticated user principal are propagated from the HTTP request thread to all spawned subthreads.

### Complete Compile-Ready Implementation (`GatewayAggregator.java`)

Here is the complete gateway coordinator implementation utilizing nested scopes, scoped values, custom joiners, and semaphores:

```java
package com.example.gateway;

import java.io.IOException;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Queue;
import java.util.Random;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.StructuredTaskScope;
import java.util.concurrent.StructuredTaskScope.Subtask;

public class GatewayAggregator {

    // Context Propagation keys
    public static final ScopedValue<String> TRACE_ID = ScopedValue.newInstance();
    public static final ScopedValue<String> USER_ROLE = ScopedValue.newInstance();

    // Throttle database or external connection footprints
    private static final Semaphore API_SEMAPHORE = new Semaphore(5);

    // Domain models
    public record UserProfile(long userId, String username, String email) {}
    public record Order(String orderId, double amount, String status) {}
    public record Recommendation(String itemId, String name, double score) {}
    public record GatewayResponse(UserProfile profile, List<Order> orders, List<Recommendation> recommendations, long elapsedMs) {}

    public static void main(String[] args) {
        GatewayAggregator gateway = new GatewayAggregator();
        System.out.println("=== Starting Gateway Request Aggregator ===");

        // Simulate incoming HTTP request thread initializing security and tracing contexts
        ScopedValue.where(TRACE_ID, "REQ-ID-999221")
                   .where(USER_ROLE, "CUSTOMER_PREMIUM")
                   .run(() -> {
                       try {
                           GatewayResponse response = gateway.aggregateRequest(42L);
                           printGatewayReport(response);
                       } catch (Exception e) {
                           System.err.println("Gateway request failed: " + e.getMessage());
                           if (e.getCause() != null) {
                               System.err.println("  Root Cause: " + e.getCause().getMessage());
                           }
                       }
                   });
     }

    /**
     * Aggregates downstream services using structured concurrency.
     */
    public GatewayResponse aggregateRequest(long userId) throws Exception {
        log("Gateway: Beginning execution for user: " + userId);
        Instant start = Instant.now();

        // 1. Open outer scope (Required domains fail-fast)
        try (var outerScope = StructuredTaskScope.open()) {
            
            // Fork critical tasks
            Subtask<UserProfile> profileTask = outerScope.fork(() -> fetchProfile(userId));
            Subtask<List<Order>> ordersTask = outerScope.fork(() -> fetchOrders(userId));
            
            // Fork optional task (Recommendations with fallback protection)
            Subtask<List<Recommendation>> recommendationsTask = outerScope.fork(() -> {
                try {
                    return fetchRecommendationsWithQuorum(userId);
                } catch (Exception e) {
                    log("Warning: Recommendations failed. Falling back to static cache. Cause: " + e.getMessage());
                    return fetchFallbackRecommendations();
                }
            });

            log("Gateway: Outer tasks forked. Blocking on join...");
            
            // Wait for all outer tasks to complete. If a required subtask throws an exception,
            // the failure bubbles up, and the scope initiates cooperative cancellation.
            outerScope.join();

            long elapsed = Duration.between(start, Instant.now()).toMillis();
            log("Gateway: All tasks completed in " + elapsed + "ms");

            // Build aggregated response
            return new GatewayResponse(
                profileTask.get(),
                ordersTask.get(),
                recommendationsTask.get(),
                elapsed
            );

        } catch (StructuredTaskScope.FailedException e) {
            log("Gateway Error: Critical aggregate component failed!");
            throw new RuntimeException("Gateway aggregation failed", e.getCause());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Gateway request interrupted", e);
        }
    }

    /**
     * Downstream fetch: User Profile (Required)
     */
    private UserProfile fetchProfile(long userId) throws Exception {
        log("Subtask Profile: Starting. Trace: " + TRACE_ID.get() + " | Role: " + USER_ROLE.get());
        Thread.sleep(Duration.ofMillis(150)); // Simulate database fetch
        log("Subtask Profile: Complete.");
        return new UserProfile(userId, "alex_pro", "alex@example.com");
    }

    /**
     * Downstream fetch: Orders (Required)
     */
    private List<Order> fetchOrders(long userId) throws Exception {
        log("Subtask Orders: Starting. Trace: " + TRACE_ID.get());
        Thread.sleep(Duration.ofMillis(200)); // Simulate REST gateway lookup
        log("Subtask Orders: Complete.");
        return List.of(
            new Order("ORD-101", 89.99, "DELIVERED"),
            new Order("ORD-102", 129.50, "PROCESSING")
        );
    }

    /**
     * Downstream fetch: Recommendations (Optional - uses inner nested scope and custom Quorum Joiner)
     */
    private List<Recommendation> fetchRecommendationsWithQuorum(long userId) throws Exception {
        log("Subtask Recommendations: Opening nested child scope...");
        int quorumSize = 2; // Return as soon as 2 of the 3 partner APIs respond successfully

        // 2. Open inner scope using custom QuorumJoiner
        try (var innerScope = StructuredTaskScope.open(new QuorumJoiner<List<Recommendation>>(quorumSize))) {
            
            // Fork requests to 3 recommendation partners concurrently
            innerScope.fork(() -> fetchFromPartner("Partner-A", userId));
            innerScope.fork(() -> fetchFromPartner("Partner-B", userId));
            innerScope.fork(() -> fetchFromPartner("Partner-C", userId));

            // Wait until quorum is achieved or all tasks fail/complete
            List<List<Recommendation>> successfulQuorums = innerScope.join();
            
            // Aggregate recommendation lists from the successful quorums
            List<Recommendation> aggregatedResults = new ArrayList<>();
            for (List<Recommendation> list : successfulQuorums) {
                aggregatedResults.addAll(list);
            }

            log("Subtask Recommendations: Quorum achieved. Aggregated " + aggregatedResults.size() + " items.");
            return aggregatedResults;

        } catch (StructuredTaskScope.FailedException e) {
            // Re-throw to trigger outer fallback execution
            throw new IOException("Quorum search failed", e.getCause());
        }
    }

    /**
     * Queries a specific recommendation partner, protecting resources via Semaphore.
     */
    private List<Recommendation> fetchFromPartner(String partnerName, long userId) throws Exception {
        log("  Partner " + partnerName + ": Requesting API permit...");
        
        // 3. Apply backpressure via Semaphore
        API_SEMAPHORE.acquire();
        try {
            log("  Partner " + partnerName + ": Permit acquired. Querying...");
            Random random = new Random();
            
            // Introduce variable network delay
            int delay = random.nextInt(200) + 100;
            Thread.sleep(Duration.ofMillis(delay));

            // Simulate occasional partner failure (e.g. Partner C fails 60% of the time)
            if (partnerName.equals("Partner-C") && random.nextDouble() < 0.6) {
                log("  Partner " + partnerName + ": Call failed!");
                throw new IOException("Partner API connection timeout");
            }

            log("  Partner " + partnerName + ": Returned successful suggestions.");
            return List.of(
                new Recommendation("REC-01", partnerName + " Suggestion 1", 0.95),
                new Recommendation("REC-02", partnerName + " Suggestion 2", 0.88)
            );
        } finally {
            API_SEMAPHORE.release();
            log("  Partner " + partnerName + ": Released API permit.");
        }
    }

    /**
     * Fallback suggestions list
     */
    private List<Recommendation> fetchFallbackRecommendations() {
        log("Fallback: Serving default static recommendations.");
        return List.of(
            new Recommendation("REC-DEFAULT-01", "Standard Echo Dot", 0.50),
            new Recommendation("REC-DEFAULT-02", "Standard Fire TV Stick", 0.45)
        );
    }

    /**
     * Helper log formatting
     */
    private static void log(String message) {
        String threadType = Thread.currentThread().isVirtual() ? "VirtualThread" : "PlatformThread";
        System.out.printf("[%s | %s] %s%n", Thread.currentThread().getName(), threadType, message);
    }

    /**
     * Report formatter
     */
    private static void printGatewayReport(GatewayResponse r) {
        System.out.println("\n=====================================================");
        System.out.println("GATEWAY RESPONSE REPORT (Completed in " + r.elapsedMs() + "ms)");
        System.out.println("USER NAME    : " + r.profile().username() + " (" + r.profile().email() + ")");
        System.out.println("ORDERS FOUND : " + r.orders().size());
        r.orders().forEach(o -> System.out.printf("  - [%s] $%.2f (%s)%n", o.orderId(), o.amount(), o.status()));
        System.out.println("RECOMMENDED  :");
        r.recommendations().forEach(rec -> System.out.printf("  - %s (Score: %.2f) [%s]%n", rec.name(), rec.score(), rec.itemId()));
        System.out.println("=====================================================\n");
     }

    /**
     * Custom Quorum Joiner that returns results as soon as 'quorum' tasks complete successfully.
     */
    public static class QuorumJoiner<T> implements StructuredTaskScope.Joiner<T, List<T>> {
        private final int quorumSize;
        private final Queue<T> results = new ConcurrentLinkedQueue<>();
        private final Queue<Throwable> exceptions = new ConcurrentLinkedQueue<>();
        private final AtomicInteger successCount = new AtomicInteger(0);
        private volatile boolean quorumReached = false;

        public QuorumJoiner(int quorumSize) {
            this.quorumSize = quorumSize;
        }

        @Override
        public boolean onFork(StructuredTaskScope.Subtask<? extends T> subtask) {
            // Allow all forks to proceed
            return false;
        }

        @Override
        public boolean onComplete(StructuredTaskScope.Subtask<? extends T> subtask) {
            if (subtask.state() == StructuredTaskScope.Subtask.State.SUCCESS) {
                results.add(subtask.get());
                int count = successCount.incrementAndGet();
                if (count >= quorumSize) {
                    quorumReached = true;
                    // Return true to cancel the scope and interrupt all running sibling subtasks
                    return true; 
                }
            } else if (subtask.state() == StructuredTaskScope.Subtask.State.FAILED) {
                exceptions.add(subtask.exception());
            }
            return false;
        }

        @Override
        public List<T> result() {
            if (!quorumReached && results.size() < quorumSize) {
                // If the quorum was not reached and there are not enough results, throw an exception
                Throwable rootCause = exceptions.peek();
                throw new StructuredTaskScope.FailedException(rootCause);
            }
            return new ArrayList<>(results);
        }

        @Override
        public Throwable exception() {
            return exceptions.peek();
        }
    }
}
```

##### How `GatewayAggregator` Works
1. **Outer Scope Isolation**: Inside `aggregateRequest(userId)`, we instantiate the root scope: `try (var outerScope = StructuredTaskScope.open())`. We fork User Profile and Order History tasks. If either fails, `FailedException` propagates to the parent thread at `outerScope.join()`, triggering cooperative cancellation of remaining tasks.
2. **Fallback Sandbox**: The third task (fetching suggestions) is optional. We enclose it in a local `try-catch` block inside the forked lambda. If `fetchRecommendationsWithQuorum()` fails, we catch it and run `fetchFallbackRecommendations()`, returning a static recommendations list.
3. **Nested Scope and Quorum**: Inside `fetchRecommendationsWithQuorum()`, we open an inner child scope: `try (var innerScope = StructuredTaskScope.open(new QuorumJoiner<>(quorumSize)))`. We fork requests to Partners A, B, and C. Using our custom `QuorumJoiner` set to `2`, the moment any two partners complete successfully, `onComplete()` returns `true`. The inner scope cancels the third task (Partner C), avoiding its tail latency.
4. **Cascading Cancellation**: If the outer scope is canceled or times out, the cancellation signal cascades down. The JVM interrupts the coordinator thread executing the child scope, which wakes up from `innerScope.join()` and propagates the cancellation signal to all partner virtual threads.
5. **Context Inheritance**: Subtasks inherit Scoped Values (`TRACE_ID`) from the parent thread. Calling `TRACE_ID.get()` inside virtual threads resolves correctly, allowing unified logs tracing.

---

## 13. Common Pitfalls & Knowledge Check

### Common Pitfalls

#### 1. Calling `Subtask.get()` Before `scope.join()` Completes
Calling `get()` or `exception()` on a `Subtask` before `join()` returns will throw an `IllegalStateException`.

```java
// BAD PRACTICE
try (var scope = StructuredTaskScope.open()) {
    var task = scope.fork(this::fetchData);
    String data = task.get(); // Throws IllegalStateException!
    scope.join();
}
```

#### 2. Scope Thread Captivity (Wrong Thread Calls `join()`)
The owner thread of the `StructuredTaskScope` must call `join()` and `close()`. You cannot fork a task that attempts to call `join()` on its enclosing scope.

#### 3. Forgetting to Use Try-With-Resources
Always wrap scopes in try-with-resources. Leaving a scope open without calling `close()` violates the structured concurrency framework guarantees and causes resource retention.

---

### Knowledge Check

**Question 1: What happens if a subtask in a StructuredTaskScope.open() fails while another is running?**
- A) The scope ignores the failure and waits for all tasks to complete.
- B) The scope throws FailedException immediately without cancelling the other task.
- C) The scope cancels all other running subtasks by interrupting them, waits for them to terminate, and then throws FailedException from join().
- D) The JVM crashes.

**Question 2: Which built-in Joiner implements a "first-past-the-post" race policy?**
- A) `Joiner.awaitAll()`
- B) `Joiner.anySuccessfulResultOrThrow()`
- C) `Joiner.allSuccessfulOrThrow()`
- D) `Joiner.allUntil()`

**Question 3: When does the scope timeout timer begin counting down?**
- A) The moment `scope.join()` is invoked.
- B) The moment the first subtask is forked via `scope.fork()`.
- C) The moment the scope is opened via `StructuredTaskScope.open(...)`.
- D) Only after all subtasks have completed execution.

**Question 4: What happens if a thread calls Subtask.get() before calling scope.join()?**
- A) It blocks until the subtask finishes.
- B) It returns null.
- C) It throws a Checked InterruptedException.
- D) It throws an IllegalStateException.

#### Answer Key
1: C | 2: B | 3: C | 4: D

---
