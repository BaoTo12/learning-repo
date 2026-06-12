# Module 06: Context Propagation via Scoped Values

## 1. What Problem This Module Solves
Microservice contexts (such as security credentials, transaction IDs, and tracing contexts) must be passed down call chains:
*   **Parameter Pollution**: Adding context parameters to every method signature in the call stack, which couples code and complicates testing.
*   **ThreadLocal Memory Footprint**: `ThreadLocal` variables are mutable and held in memory for the lifetime of the thread. In virtual thread settings, this leads to memory bloat and leaks.
*   **Context Leakage**: Because `ThreadLocal` is mutable, any downstream method can overwrite the context value, introducing bugs and security risks.

**Scoped Values** (introduced as a preview feature in Java 21) solve this by providing immutable, lightweight, and scope-bounded context propagation.

---

## 2. ThreadLocal vs Scoped Values

| Feature | ThreadLocal | ScopedValue |
| :--- | :--- | :--- |
| **Mutability** | Mutable (`set()` / `remove()`) | Immutable (Read-only after binding) |
| **Lifecycle Scope** | Lifetime of the thread | Bound to a try-with-resources block |
| **Virtual Thread Friendly** | Poor (high memory footprint per thread) | Excellent (reuses context reference map) |
| **Context Leakage Risk** | High (leaks if not cleared) | Zero (automatically cleared on block exit) |
| **Concurrency Sharing** | Weak (manual inheritance copy) | Strong (automatically inherited by child subtasks) |

```
[ ScopedValue Binding Scope ] (ScopedValue.where(KEY, value).run(Runnable))
      │
      ├─► Method A reads value (KEY.get())
      ├─► Method B forks StructuredTaskScope (Child threads automatically inherit KEY)
      │
[ Scope Exits ] ──► Context is evicted. Memory is garbage collected.
```

---

## 3. Implementing Scoped Values in Java 21

To bind and share a context value using `ScopedValue`:

```java
package com.example.concurrency.scoped;

import java.util.concurrent.ScopedValue;

public class SecurityContextManager {

    // 1. Declare ScopedValue key
    public static final ScopedValue<String> CURRENT_USER = ScopedValue.newInstance();

    public void processRequest() {
        String principal = "jane_doe";

        // 2. Bind the value to the ScopedValue key and run the execution block
        ScopedValue.where(CURRENT_USER, principal).run(() -> {
            executeBusinessLogic();
        });
        
        // Outside the run block, CURRENT_USER.isBound() returns false
    }

    private void executeBusinessLogic() {
        // 3. Retrieve the context value. No method parameters needed.
        if (CURRENT_USER.isBound()) {
            System.out.println("Executing request for user: " + CURRENT_USER.get());
        } else {
            System.out.println("Anonymous access denied.");
        }
    }

    public static void main(String[] args) {
        SecurityContextManager manager = new SecurityContextManager();
        manager.processRequest();
    }
}
```

---

## 4. Context Sharing in Structured Concurrency

When you fork child subtasks inside a `StructuredTaskScope`, the JVM automatically shares the active `ScopedValue` context with the child threads, avoiding memory copy overhead:

```java
public void executeParallelTasks() {
    ScopedValue.where(CURRENT_USER, "admin").run(() -> {
        try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
            // Child subtasks automatically inherit the "admin" user identity
            scope.fork(() -> {
                System.out.println("Subtask running for user: " + CURRENT_USER.get());
                return null;
            });
            scope.join();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    });
}
```

---

## 5. Common Mistakes and Anti-Patterns
*   **Attempting to Rebind/Mutate inside a Scope**: Attempting to invoke a write operation like `CURRENT_USER.set()`. `ScopedValue` is immutable. To update a value, you must rebind it in a nested scope block:
    ```java
    ScopedValue.where(CURRENT_USER, "new_user").run(() -> { ... });
    ```
*   **Neglecting Scoped Value Presence Check**: Calling `ScopedValue.get()` without verifying if the value is bound (`isBound()`), which will trigger a `NoSuchElementException` if called outside the binding scope.

---

## 6. Interview Questions

### Q1: Why are Scoped Values more memory-efficient than `ThreadLocal` variables when scaling to millions of virtual threads?
**Answer**: 
*   `ThreadLocal`: Allocates a mutable map for every thread instance. When spawning millions of virtual threads, these maps generate significant memory overhead and increase garbage collection churn.
*   `ScopedValue`: Is immutable and scope-bounded. Instead of allocating a map per thread, the JVM stores the bindings in a flat lookup table. When a child thread is spawned, it points directly to the parent's binding structure on the heap without copying data, keeping the memory footprint at a minimum.

### Q2: What happens if a downstream service method attempts to call `ScopedValue.get()` when the value has not been bound? How do you prevent exceptions?
**Answer**: 
If a method calls `ScopedValue.get()` when the key is not bound to a scope, the JVM throws a `NoSuchElementException`. 
To prevent this, always verify the binding status using `ScopedValue.isBound()` or supply a default fallback value using `ScopedValue.orElse(defaultValue)` before accessing the value.
