# Module 05: Structured Concurrency & StructuredTaskScope

## 1. What Problem This Module Solves
Traditional Java concurrency (using `ExecutorService`) is unstructured:
*   **Orphaned Threads**: If parent thread A spawns child thread B, and thread A throws an exception or is cancelled, child thread B continues running indefinitely, leaking resources.
*   **Cascading Failures**: There is no built-in way to propagate cancellations down a task hierarchy. If a task fails, sibling tasks continue running, wasting CPU resources.
*   **Debugging Blindness**: Thread dumps do not represent parent-child relationships, making it difficult to trace which thread spawned a failing subtask.

**Structured Concurrency** resolves this by grouping related concurrent tasks into a single unit of execution, coordinating their lifecycles, and ensuring that all threads terminate before the scope closes.

---

## 2. Unstructured vs Structured Concurrency

### 2.1 Unstructured (ExecutorService)
Tasks are submitted independently. The parent thread must manually track each `Future` and handle cancellations and exceptions individually:

```java
// Anti-Pattern: If task1 fails, task2 continues running, leaking resources
Future<String> task1 = executor.submit(this::fetchUser);
Future<Double> task2 = executor.submit(this::fetchBalance);
```

### 2.2 Structured (`StructuredTaskScope`)
Tasks are nested inside a structured scope. The scope guarantees that all child threads complete execution before control exits the scope block:

```
[ StructuredTaskScope Start ]
      ├───────► Fork Subtask A
      ├───────► Fork Subtask B
      ▼ (Scope.join() blocks until all subtasks finish or fail)
[ StructuredTaskScope End / Close ]
```

---

## 3. The `StructuredTaskScope` API & Joining Policies

`StructuredTaskScope` (available as a preview feature in Java 21) supports two main joining policies:

### 3.1 Shutdown on Failure (`ShutdownOnFailure`)
Forks subtasks in parallel. If any subtask throws an exception, the scope triggers a shutdown, cancelling all remaining active subtasks.

```java
package com.example.concurrency.structured;

import java.util.concurrent.StructuredTaskScope;
import java.util.function.Supplier;

public class ParallelDataAggregator {

    public static class UserData {
        public String name;
        public double balance;
        public UserData(String name, double balance) {
            this.name = name;
            this.balance = balance;
        }
    }

    public UserData fetchUserData(long userId) throws Exception {
        // Enforce structured lifecycle scope
        try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
            
            // Fork parallel subtasks
            StructuredTaskScope.Subtask<String> nameTask = scope.fork(() -> fetchName(userId));
            StructuredTaskScope.Subtask<Double> balanceTask = scope.fork(() -> fetchBalance(userId));

            // Wait for all subtasks to complete or any to fail
            scope.join();
            
            // Propagate exception if any subtask failed
            scope.throwIfFailed(Exception::new);

            // Access results safely (join guarantees completion)
            return new UserData(nameTask.get(), balanceTask.get());
        }
    }

    private String fetchName(long id) throws Exception {
        Thread.sleep(100);
        return "Alice";
    }

    private double fetchBalance(long id) throws Exception {
        Thread.sleep(50);
        return 1500.00;
    }
}
```

---

### 3.2 Shutdown on Success (`ShutdownOnSuccess`)
Used to query redundant services. It returns the result of the **first subtask to complete successfully** and cancels all other active subtasks.

```java
package com.example.concurrency.structured;

import java.util.concurrent.StructuredTaskScope;

public class RedundantServiceQuery {

    public String fetchFromFastestServer() throws Exception {
        try (var scope = new StructuredTaskScope.ShutdownOnSuccess<String>()) {
            
            // Fork queries to redundant servers
            scope.fork(() -> queryServer("Server-US"));
            scope.fork(() -> queryServer("Server-EU"));

            scope.join(); // Blocks until the first subtask succeeds
            
            return scope.result(); // Returns the fastest successful result
        }
    }

    private String queryServer(String serverName) throws Exception {
        // Simulating varying network latency
        int latency = serverName.contains("US") ? 150 : 50;
        Thread.sleep(latency);
        return "Payload from " + serverName;
    }
}
```

---

## 4. Custom Joiners
For complex workflows, you can implement custom joining policies by extending `StructuredTaskScope` and overriding the `handleComplete()` method. This allows you to accumulate intermediate results or trigger custom shutdown logic.

---

## 5. Common Mistakes and Anti-Patterns
*   **Forgetting to call `join()`**: Attempting to read results using `subtask.get()` before calling `scope.join()`. This will trigger an `IllegalStateException` because the subtasks may still be executing.
*   **Failing to use Try-With-Resources**: Instantiating a `StructuredTaskScope` without a try-with-resources block. This can leak thread contexts and prevent child resources from being released.

---

## 6. Interview Questions

### Q1: How does `StructuredTaskScope.ShutdownOnFailure` prevent thread leaks when a subtask encounters an exception?
**Answer**: 
When a subtask throws an exception, the scope catches the failure and invokes its internal `shutdown()` method. 
This interrupts the threads of all other active subtasks and stops the scope from accepting new tasks. The parent thread is unblocked from the `join()` call and throws the exception using `throwIfFailed()`. This ensures that all subtasks are cancelled and their resources released before the scope exits.

### Q2: Why will calling `subtask.get()` before invoking `scope.join()` trigger an `IllegalStateException`?
**Answer**: 
A `Subtask` is designed to be read only after execution is complete. Before `scope.join()` returns, subtasks may still be running. 
Calling `subtask.get()` prematurely would force blocking behavior or return incomplete data. To prevent this, the JDK enforces that the subtask state must be checked only after `join()` has guaranteed the completion or failure of all tasks in the scope.
