# Module 05: Context Propagation via Scoped Values

In large applications, request details like the authenticated user, transaction ID, client IP, or tracing data must often be shared across different layers. Sharing this context implicitly across call stacks is a common requirement in framework design.

Historically, Java developers used `ThreadLocal` variables for this. However, with **Virtual Threads** and **Structured Concurrency**, `ThreadLocal` causes memory and operational issues.

In this module, we will explore **Scoped Values** (`java.lang.ScopedValue`), finalized in JDK 25. We will look at the limitations of parameter passing and `ThreadLocal`, study how Scoped Values work under the hood, examine integration patterns, and complete three hands-on labs.

---

## 1. The Context Propagation Challenge

### The Problem: Passing Context through APIs
In layered architectures (such as Controller-Service-Repository), data often needs to travel from the entry point (like an HTTP interceptor) to downstream layers (like database loggers). There are two ways to do this:

1. **Explicit Parameter Passing**: Every method in the call stack accepts context parameters.
2. **Implicit Context Passing**: Context is bound to the execution thread, letting downstream layers retrieve it when needed.

Using explicit parameter passing causes three main issues:

```
[HTTP Request] ──► Controller.handle(ReqContext) ──► Service.process(ReqContext) ──► Repository.save(ReqContext)
```

#### 1. Parameter Pollution
Every method signature in the call chain must declare context parameters (like `requestId`, `userPrincipal`, or `clientLocale`) even if the method does not use that data. This pollutes domain models with infrastructure parameters.

#### 2. Interface Brittleness
If infrastructure requirements change (for example, adding a tracing ID or security credentials), the context object must change. This forces updates to interface definitions, method calls, and tests across many classes.

#### 3. Coupling and Testability
Forcing context parameters into business interfaces couples the domain layer to framework metadata. Unit testing becomes verbose because you must create mock context objects for every test, even when the method under test ignores the context.

---

## 2. ThreadLocal: The Classical Solution & Its Limitations

To decouple business method signatures from infrastructure context, Java 1.2 introduced `ThreadLocal<T>`.

A `ThreadLocal` variable creates a thread-isolated storage area. When a thread calls `threadLocal.set(value)`, the value is placed in a thread-specific map (`ThreadLocalMap`) owned by the `Thread` instance. Any downstream method running on the same thread can call `threadLocal.get()` to retrieve it.

```
+-------------------------------------------------------------------------+
|                              JVM HEAP MEMORY                            |
|                                                                         |
|  [Thread Instance]                                                      |
|         │                                                               |
|         └─► threadLocals ──► [ThreadLocalMap]                           |
|                                     │                                   |
|                                     ├─► Entry 1: [WeakRefKey] ──► Value |
|                                     └─► Entry 2: [WeakRefKey] ──► Value |
+-------------------------------------------------------------------------+
```

### Classical ThreadLocal Lifecycle Pattern

Below is the standard, safe pattern for managing context using `ThreadLocal`:

```java
public class SecurityContextHolder {
    private static final ThreadLocal<String> CURRENT_USER = new ThreadLocal<>();

    public void handleRequest(String username, Runnable requestTask) {
        // 1. Bind value to the current thread
        CURRENT_USER.set(username);
        try {
            // 2. Execute request task downstream
            requestTask.run();
        } finally {
            // 3. CRITICAL: Prevent memory leaks by removing the reference
            CURRENT_USER.remove();
        }
    }

    public static String getCurrentUser() {
        return CURRENT_USER.get();
    }
}
```

### Under the Hood: ThreadLocal Map and Weak Reference Leaks

To understand the core problem of `ThreadLocal`, we must examine the source code of `java.lang.Thread` and `java.lang.ThreadLocal`.
Inside the `Thread` class, thread-local storage is declared as:
```java
/* ThreadLocal values pertaining to this thread. This map is maintained by the ThreadLocal class. */
ThreadLocal.ThreadLocalMap threadLocals = null;
```
The `ThreadLocalMap` is a specialized hash map that uses weak references for its keys. The entries in this map inherit from `WeakReference<ThreadLocal<?>>`:
```java
static class Entry extends WeakReference<ThreadLocal<?>> {
    /** The value associated with this ThreadLocal. */
    Object value;

    Entry(ThreadLocal<?> k, Object v) {
        super(k);
        value = v;
    }
}
```

This design introduces a critical memory leak vulnerability:

1. **Garbage Collection of Keys**:
   - The key inside the `Entry` inherits from `WeakReference<ThreadLocal<?>>`.
   - When the `ThreadLocal` reference goes out of scope and has no more strong references (for example, when a web application is undeployed), the garbage collector can reclaim the `ThreadLocal` instance.
   - After garbage collection, the key of the `Entry` becomes `null`, leaving a stale entry in the `ThreadLocalMap`.

2. **Strong Reference Retention of Values**:
   - Although the key is garbage collected and becomes `null`, the `Entry` itself (which is in the `Entry[] table` array inside `ThreadLocalMap`) remains strongly referenced.
   - The `Entry.value` field retains a **strong reference** to the value object (such as a database connection or user details).
   - Because the thread object maintains a strong reference to the `ThreadLocalMap` via `threadLocals`, the GC root chain remains active:
     $$\text{GC Root} \longrightarrow \text{Thread Instance} \longrightarrow \text{ThreadLocalMap} \longrightarrow \text{Entry[] Table} \longrightarrow \text{Entry} \longrightarrow \text{Value Object}$$
   - The garbage collector cannot reclaim the value object because a strong reference path exists from an active thread.

3. **Leaks in Pooled Threads**:
   - In web servers, worker threads are pooled and run for the lifetime of the application.
   - If you forget to call `CURRENT_USER.remove()` in a `finally` block, the strong reference remains active.
   - Stale entries are only cleaned up during other map modifications (like resizing or inserting new entries). Under a steady state, these entries might never be cleaned, leading to memory leaks.

##### Deep Dive: ThreadLocal Garbage Collection Reference Tracing and Memory Profiling

To understand why a `ThreadLocal` leak persists despite keys being marked as `WeakReference`, we must analyze how garbage collection algorithms (such as G1 GC or ZGC) trace references.

###### 1. Reference Strengths in the JVM
The JVM supports four strengths of object references:
- **Strong References**: Standard assignments (e.g., `Object obj = new Object()`). The GC never reclaims a strongly referenced object.
- **Soft References**: Encapsulated via `SoftReference`. The GC reclaims these objects *only* if the JVM is low on memory.
- **Weak References**: Encapsulated via `WeakReference`. The GC reclaims these objects during the next marking phase if they have no strong reference paths.
- **Phantom References**: Encapsulated via `PhantomReference`. Used for post-mortem cleanup.

###### 2. How the GC Processes Weak References (The Marking Phase)
During a garbage collection cycle, the collector executes a multi-phase marking process:

```
[Marking Phase Starts]
         │
         ▼
[Trace Strong Reference Paths] ──► Mark all reachable objects as ALIVE
         │
         ▼
[Scan WeakReference Objects]
         │
         ├── Is the referent (key) reachable via a strong path?
         │         ├── YES ──► Keep key ALIVE
         │         └── NO  ──► Clear referent pointer (set to null)
         ▼
[Enqueue cleared references in ReferenceQueue]
```

1. **Root Scanning**: The GC pauses threads and identifies all active GC Roots (thread stack variables, JNI references, system classloaders).
2. **Strong Path Tracing**: The collector traverses all strong reference paths. Any object reachable from a root is marked as alive.
3. **Weak Reference Processing**:
   - The collector locates all active `WeakReference` objects.
   - It checks whether the *referent* (the object pointed to by the weak reference, which is the `ThreadLocal` key in our map) is reachable via any strong paths.
   - If the key is *not* reachable via a strong reference path, the GC sets the referent pointer inside the `WeakReference` wrapper to `null`.
   - **Crucial Limitation**: The GC *only* sets the key reference pointer to `null`. The GC does not nullify the **value** field (`Entry.value`) because the value field is a standard, strong reference inside the `Entry` object. The `Entry` is still reachable via the thread's `threadLocals` map array.

###### 3. Tracing a ThreadLocal Leak in Eclipse Memory Analyzer (MAT)
When debugging a thread-local memory leak, engineers generate a heap dump (`jmap -dump:format=b,file=heap.hprof <PID>`) and load it into a profiler.

Tracing the path to GC roots for a leaked object reveals the following object graph:

```text
Class Name                                                     │ Ref Footprint
───────────────────────────────────────────────────────────────┼──────────────
java.lang.Thread  [GC Root: Active Worker Thread]              │ 2,408 bytes
  └─ threadLocals java.lang.ThreadLocal$ThreadLocalMap         │    64 bytes
       └─ table java.lang.ThreadLocal$ThreadLocalMap$Entry[16] │   128 bytes
            └─ [4] java.lang.ThreadLocal$ThreadLocalMap$Entry  │    32 bytes
                 ├─ referent = null (WeakReference Key cleared)│     0 bytes
                 └─ value com.example.LargeContextPayload      │ 2,048,128 bytes
```

###### Key Indicators of a Leak:
- **`referent = null`**: This confirms that the `ThreadLocal` instance has been garbage collected. The slot index is now stale.
- **`value`**: Points to a large domain object. Since the thread remains active, this object is pinned in memory, causing a leak.

###### 4. How Scoped Values Avoid the Reference Chain
`ScopedValue` avoids this graph entirely by shifting context from a heap-allocated hash map inside the thread to stack-based snapshots:
- When a scoped value task runs, the binding is associated with the local execution frame of the active method stack.
- When the method returns (or throws an exception), the execution frame is popped. The pointer link is updated to the parent's frame, and the binding node becomes unreachable.
- Because there is no hash map or table array inside the thread object, there are no weak-reference wrappers, no stale null-key entries, and no strong reference value traps.

### Detailed Walkthrough of SecurityContextHolder

1. **Binding Phase (`CURRENT_USER.set(username)`)**:
   - When `handleRequest()` is called, the thread executes `CURRENT_USER.set(username)`.
   - The JVM checks if the executing `Thread` has a `ThreadLocalMap` initialized. If not, it creates a new map with a default size of 16 entries and maps the `ThreadLocal` instance reference to the string `username`.
   - If the map exists, the key's hashcode determines the index in the entry table. If there is a collision, linear probing is used to find the next empty slot.

2. **Downstream Invocation (`requestTask.run()`)**:
   - The thread enters the `try` block and calls `run()`. Any code running in this thread can now call `SecurityContextHolder.getCurrentUser()` to retrieve the username.
   - The retrieval walks the thread's local map and extracts the value referenced by the `ThreadLocal` key.

3. **Strict Cleanup Guarantee (`finally` block)**:
   - In the `finally` block, the thread executes `CURRENT_USER.remove()`.
   - The JVM locates the map entry corresponding to `CURRENT_USER` and removes the `Entry` reference from the table, clearing the strong reference to the value object and letting it be garbage collected immediately.
   - If this step is omitted, the reference persists, causing a memory leak when the thread is recycled back into the pool.

### Inherent Flaws of ThreadLocal

While `ThreadLocal` resolves the parameter passing problem, it introduces operational issues:

#### 1. Unconstrained Mutability
Any downstream code with access to the `ThreadLocal` variable can call `set(newValue)` or `remove()`. This means a helper utility or repository call could accidentally change or clear the context, breaking upstream assumptions. Tracking where and when a thread-local value was mutated is difficult.

```java
// Downstream code can silently corrupt parent context:
SecurityContextHolder.CURRENT_USER.set("malicious_user");
```

#### 2. Unbounded Lifetime
A thread-local value remains bound to the thread until it is explicitly cleared via `remove()`. In web servers using thread pooling, threads are reused across multiple requests. If you forget to invoke `remove()` in a `finally` block:
* **Memory Leaks**: The object referenced by the thread-local stays pinned in memory, preventing GC.
* **Security Leaks**: A subsequent request processed by the same thread will inherit the credentials of the prior user, potentially leaking access.

#### 3. Heavyweight Inheritance (InheritableThreadLocal)
When a task spawns child threads, context must often be propagated. Java provides `InheritableThreadLocal` for this purpose. When a child thread is created, the JVM copies the parent thread's `ThreadLocalMap`.
* This requires deep copying of the map entries, creating allocation overhead.
* If a parent thread spawns 1,000 child threads, the data is referenced 1,000 times, multiplying memory use.

### The Virtual Thread Breakdown

The memory overhead of `ThreadLocalMap` becomes a bottleneck when transitioning to virtual threads:

* **Platform Thread Model**: A server handles 200 concurrent requests using a pool of 200 platform threads. 200 maps inside the threads are easily managed.
* **Virtual Thread Model**: A server handles 1,000,000 concurrent requests using 1,000,000 virtual threads. If each virtual thread allocates even a small `ThreadLocalMap` containing standard metadata, the heap footprint explodes instantly:

$$\text{Memory Overhead} = 1,000,000 \text{ threads} \times \text{map overhead} \approx \text{Gigabytes of redundant heap allocations}$$

Virtual threads are designed to be cheap, lightweight, and disposable. Forcing them to carry heavy, mutable thread-local maps defeats their design objective.

---

## 3. The Scoped Value Alternative

To resolve the limitations of `ThreadLocal` in high-concurrency environments, JDK 25 finalizes **Scoped Values** (`java.lang.ScopedValue`).

A Scoped Value is a container that allows a value to be safely and implicitly passed to downstream methods for the duration of a single execution scope.

```
                    [ScopedValue.where(KEY, value)]
                                  │
                       [Dynamic Scope Starts]
                                  │
             ┌─────────────────────┼─────────────────────┐
             ▼                     ▼                     ▼
      [Service.get()]       [Repo.get()]         [Forked VThread] (Inherits link)
             │                     │                     │
             └─────────────────────┼─────────────────────┘
                                  │
                          [Dynamic Scope Ends]
                                  │
                       [Value Automatically Cleared]
```

### Core Architecture and Properties

1. **Strict Immutability**: Once a scoped value is bound to an execution scope, it cannot be modified. Downstream methods can only read the value. This guarantees thread-safety.
2. **Bounded Lifetime**: The binding is bounded by the execution of a `run()` or `call()` block. The moment the block finishes, the binding is automatically destroyed by the JVM. No manual `remove()` call is needed.
3. **Link-Based Inheritance**: When spawning concurrent subtasks via `StructuredTaskScope.fork()`, child threads inherit access to the parent's scoped values. Instead of copying map entries, the JVM establishes a pointer link back to the parent scope's stack frame. This has **zero allocation cost** at fork time.
4. **NoSuchElementException on Unbound Read**: Unlike `ThreadLocal` (which returns `null` when a variable is not set), `ScopedValue.get()` throws a `NoSuchElementException` if called outside a bound scope. This helps catch configuration errors during testing.

---

## 4. Core ScopedValue API

A `ScopedValue` is typically declared as a `private static final` field. Its constructors are private; instances are created using the `newInstance()` factory method.

```java
private static final ScopedValue<User> CURRENT_USER = ScopedValue.newInstance();
```

### Method Summary Table

| Method | Return Type | Description |
| :--- | :--- | :--- |
| `ScopedValue.newInstance()` | `ScopedValue<T>` | Creates a new unbound scoped value instance. |
| `ScopedValue.where(ScopedValue<T> key, T value)` | `ScopedValue.Carrier` | Creates a container (Carrier) storing a single binding. |
| `carrier.run(Runnable task)` | `void` | Executes a task within the carrier's bound scope. |
| `carrier.call(Callable<V> task)` | `V` | Executes a task and returns its result. |
| `scopedValue.get()` | `T` | Retrieves the bound value. Throws `NoSuchElementException` if unbound. |
| `scopedValue.isBound()` | `boolean` | Checks if the scoped value is currently bound in the current thread. |
| `scopedValue.orElse(T defaultValue)` | `T` | Returns the bound value, or the default value if unbound. |
| `scopedValue.orElseThrow(Supplier<X>)`| `T` | Returns the value, or throws a custom exception if unbound. |

### Chaining Multiple Bindings
You can bind multiple scoped values at once by chaining `where()` calls:

```java
ScopedValue.where(CURRENT_USER, user)
           .where(REQUEST_ID, reqId)
           .where(CLIENT_LOCALE, Locale.GERMANY)
           .run(() -> processRequest());
```

---

## 5. Under the Hood: Stack-Based Dynamic Bindings

Scoped Values use a stack-based lookup mechanism:

```
[Stack Frame: Main Thread]
  └─► Carrier: [CURRENT_USER -> "Alice"]
        └─► Downstream Method Calls...
              └─► get() searches parent stack frames in O(1) time
```

When a thread enters a `ScopedValue.where(KEY, value).run(...)` block, the JVM registers the binding in a per-thread snapshot pointer.

### Deep JVM Internal Execution Model

Bindings are managed through a chain of snapshot objects on the execution stack, rather than a map inside the thread object.

1. **The Binding Chain**:
   Every thread contains a hidden field (managed by the JVM) called `scopedValueBindings` that points to a node in a linked list of bindings:
   ```java
   // Conceptual representation of the JVM internal state
   class Thread {
       Object scopedValueBindings; // Points to the current binding stack node
   }
   ```
2. **Snapshot Creation on Bind**:
   When `ScopedValue.where(key, value).run(task)` runs:
   - The JVM allocates a lightweight snapshot node containing the `key`, `value`, and a reference to the previous head of the `scopedValueBindings` chain.
   - The thread's `scopedValueBindings` field is updated to point to this new snapshot node.
3. **Implicit Cleanup on Return**:
   - The `run` or `call` block executes.
   - When the block completes, the thread's `scopedValueBindings` is restored to point to the previous head pointer. The new snapshot node is immediately eligible for garbage collection. This cleanup runs in $O(1)$ time.
4. **O(1) Dynamic Lookup Performance**:
   - When a downstream layer calls `key.get()`, the JVM walks the `scopedValueBindings` chain starting from the current head.
   - Because method nesting in Java is usually shallow (typically less than 10-15 frames deep), the lookup completes in $O(1)$ time.
   - The JVM optimizes this using a thread-local lookup cache. If a scoped value is read repeatedly, the lookup is served directly from a CPU register or a cache slot, making it as fast as a direct method argument.

### Java Memory Model (JMM) happens-before Guarantees

Scoped Values guarantee clear visibility based on JMM happens-before relationships:
1. **Binding Edge**: Binding a value to a `ScopedValue` happens-before any read invocation of `get()` within the bound scope.
2. **Scope Termination Edge**: The completion of the bound task happens-before restoring the parent scope's previous bindings.
3. **Virtual Thread Inheritance Edge**: Binding a scoped value in the parent thread happens-before the execution of any subtask spawned via `StructuredTaskScope.fork()`. The spawned subtask virtual thread has immediate, read-only visibility of all scoped values bound by the parent thread before the fork.

##### Architectural Comparison: Dynamic Scoping Across Modern Runtimes

To appreciate Scoped Values, it is helpful to compare Java's stack-bounded context propagation with the mechanisms used in other programming languages.

| Language / Runtime | Mechanism Name | Lifecycle Scope | Context Inheritance Model | Runtime Overhead |
| :--- | :--- | :--- | :--- | :--- |
| **Clojure (JVM)** | Dynamic Vars (`^:dynamic`) | Thread-bound dynamic binding (`binding` blocks) | Captured via agent bindings or future bindings | High (Ref-based lookup and thread-local maps) |
| **Python (asyncio)** | Context Variables (`contextvars`) | Task-bound context frame | Copy-on-Write (CoW) mapping when spawning subtasks | Medium (Dictionary lookups and frame cloning) |
| **Scala** | Implicit/Given Parameters | Compile-time lexical scoping | Explicit signatures synthesized by the compiler | Zero runtime overhead (signature pollution remains) |
| **Java (Project Loom)** | Scoped Values (`ScopedValue`) | Stack-bounded dynamic scope (`run`/`call` blocks) | Link-based parent-pointer traversal | Near-zero (Register-based caching, $O(1)$ stack walk) |

###### 1. Clojure's Dynamic Vars
Clojure has long supported dynamic variables (declared with `^:dynamic` metadata).
- **Binding Mechanics**: The `binding` macro sets a thread-local binding for a dynamic var. Clojure uses its own thread-local map structure (`Var$Frame`) to push and pop values.
- **Inheritance**: When spawning a future or thread, Clojure captures the current dynamic bindings and merges them into the child thread's local map.
- **Loom Differences**: Because Clojure's frame maps are mutable and copy-heavy, they incur higher memory allocation overhead. Scoped Values enforce strict immutability, letting child threads share the parent's bindings via pointer link chains rather than duplicating maps.

###### 2. Python's ContextVars
Python introduced the `contextvars` module to support concurrent context propagation in asynchronous event loops (`asyncio`).
- **Binding Mechanics**: Context variables are stored in a thread-safe `Context` object. Every asyncio Task manages its own local context frame.
- **Inheritance**: Spawning a child task clones the parent's `Context` using a Copy-on-Write (CoW) dictionary. If a child task modifies a variable, a new dictionary entry is allocated, isolating the child's changes from the parent.
- **Loom Differences**: While Python's CoW model supports mutability, it requires copying dictionary descriptors on task creation. Java's Scoped Values are fully read-only, letting child virtual threads share a parent pointer chain without map allocations.

###### 3. Scala's Implicit/Given Parameters
Scala uses compile-time resolution to pass context parameters.
- **Binding Mechanics**: The programmer defines a context value as `given` (Scala 3) or `implicit` (Scala 2). Downstream methods that declare `using` or `implicit` parameters resolve this value at compile time.
- **Inheritance**: The compiler rewrites method signatures, injecting the context value as an additional parameter. At the JVM bytecode level, this is compiled as standard parameter passing.
- **Loom Differences**: Scala's implicits have zero runtime overhead, but they cause **interface pollution** because every method in the call stack must be updated to accept the parameter. Java's Scoped Values resolve this dynamically: intermediate method signatures are completely decoupled from context definition metadata, preserving clean APIs.

###### 4. Java Scoped Values: The Synthesis
Loom's Scoped Values combine the API cleanliness of Clojure's dynamic variables with the performance efficiency of Scala's parameter passing.
By organizing bindings as an immutable linked list on the execution stack and caching lookups in CPU registers, the JVM offers a zero-allocation inheritance path that scales to millions of concurrent virtual threads, combining clean framework architecture with raw execution speed.

---

## 6. Case Studies from the Field

We will review three complete, compile-ready classes showing real-world design patterns.

### 1. TemplateProcessor: Recursion Protection
In template engines, recursive templates can cause stack overflow errors if a template references itself. We can use a `ScopedValue<Integer>` to track recursion depth and stop processing if the depth exceeds a limit.

```java
import java.util.NoSuchElementException;
import java.util.function.Supplier;

public class TemplateProcessor {

    private static final ScopedValue<Integer> RECURSION_DEPTH = ScopedValue.newInstance();
    private static final int MAX_NESTING_LEVEL = 5;

    public static class TemplateException extends RuntimeException {
        public TemplateException(String msg) { super(msg); }
    }

    public String processTemplate(String templateContent) {
        // Entry point: if unbound, initialize depth to 0
        if (!RECURSION_DEPTH.isBound()) {
            return ScopedValue.where(RECURSION_DEPTH, 0)
                              .call(() -> processTemplateInternal(templateContent));
        } else {
            return processTemplateInternal(templateContent);
        }
    }

    private String processTemplateInternal(String content) {
        int currentDepth = RECURSION_DEPTH.get();
        System.out.println("Processing template at nesting depth: " + currentDepth);

        if (currentDepth >= MAX_NESTING_LEVEL) {
            throw new TemplateException("Template nesting exceeds limit of " + MAX_NESTING_LEVEL);
        }

        // Simulate finding a nested template include directive
        if (content.contains("{{include:nested}}")) {
            // Rebind/Shadow the recursion depth value by incrementing it by 1
            String nestedResult = ScopedValue.where(RECURSION_DEPTH, currentDepth + 1)
                                             .call(() -> processTemplateInternal("Child Content"));
            return content.replace("{{include:nested}}", nestedResult);
        }

        return content + " (processed)";
    }

    public static void main(String[] args) {
        TemplateProcessor processor = new TemplateProcessor();
        
        System.out.println("--- Scenario 1: Safe Nesting ---");
        String safeTemplate = "Parent Template with nested include: {{include:nested}}";
        String result = processor.processTemplate(safeTemplate);
        System.out.println("Result: " + result);

        System.out.println("\n--- Scenario 2: Recursive Starvation ---");
        // Loop back nesting to simulate circular reference
        try {
            processor.processTemplate("Infinite: {{include:nested}} {{include:nested}} {{include:nested}} {{include:nested}} {{include:nested}} {{include:nested}}");
        } catch (TemplateException e) {
            System.err.println("Caught Expected Nesting Guard: " + e.getMessage());
        }
    }
}
```

##### Code Walkthrough: `TemplateProcessor`

1. **Lazy Initialization of Dynamic Bindings**:
   - In the entry point `processTemplate()`, the code checks `RECURSION_DEPTH.isBound()`.
   - If unbound, it initializes the chain using `ScopedValue.where(RECURSION_DEPTH, 0).call(...)`.
   - If a nested call is already running, the binding exists, and the code calls `processTemplateInternal()` directly to avoid resetting the depth.

2. **Stack Nesting Guard**:
   - Inside `processTemplateInternal()`, the code reads the current depth using `RECURSION_DEPTH.get()`.
   - If the depth is at or above `MAX_NESTING_LEVEL`, it throws a `TemplateException`. This prevents infinite recursion from causing a `StackOverflowError`.

3. **Nesting and Rebinding**:
   - When a nested template include is found, the code increments the depth using `ScopedValue.where(RECURSION_DEPTH, currentDepth + 1).call(...)`.
   - Any downstream calls to `RECURSION_DEPTH.get()` inside that call return the new incremented value.
   - When the nested call finishes, the JVM pops the binding stack, automatically restoring the previous depth without manual cleanup.

---

### 2. FlattenedTransactionExample: Nested Transaction Coordination
In transaction frameworks, **transaction flattening** is a common pattern: if a transaction is already active when a nested service method is called, the nested operation joins the existing transaction instead of starting a new one.

```java
import java.util.concurrent.StructuredTaskScope;

public class FlattenedTransactionExample {

    public record Transaction(String txId, String isolationLevel) {}

    // Transaction Holder ScopedValue
    private static final ScopedValue<Transaction> CURRENT_TX = ScopedValue.newInstance();

    public void executeBusinessTransaction() {
        Transaction outerTx = new Transaction("TX-OUTER-7788", "READ_COMMITTED");
        System.out.println("Outer method starts transaction: " + outerTx.txId());

        // Bind outer transaction
        ScopedValue.where(CURRENT_TX, outerTx).run(() -> {
            performDatabaseWrite("Insert User Profile");
            
            // Invoke nested operation
            performNestedBusinessLogic();
        });
    }

    private void performNestedBusinessLogic() {
        // Check if an existing transaction is bound
        if (CURRENT_TX.isBound()) {
            Transaction activeTx = CURRENT_TX.get();
            System.out.println("  Nested method detected active transaction. Joining: " + activeTx.txId());
            performDatabaseWrite("Insert User Settings");
        } else {
            // Fallback path: start a new transaction if called standalone
            Transaction innerTx = new Transaction("TX-INNER-1122", "SERIALIZABLE");
            System.out.println("  No active transaction. Starting new transaction: " + innerTx.txId());
            ScopedValue.where(CURRENT_TX, innerTx).run(() -> {
                performDatabaseWrite("Insert Standalone Log");
            });
        }
    }

    private void performDatabaseWrite(String statement) {
        Transaction tx = CURRENT_TX.get();
        System.out.println("    DB Write: '" + statement + "' executed under context of transaction: " + tx.txId());
    }

    public static void main(String[] args) {
        FlattenedTransactionExample example = new FlattenedTransactionExample();
        
        System.out.println("--- Scenario 1: Running nested inside outer transaction ---");
        example.executeBusinessTransaction();

        System.out.println("\n--- Scenario 2: Running nested method standalone ---");
        example.performNestedBusinessLogic();
    }
}
```

##### Code Walkthrough: `FlattenedTransactionExample`

1. **Outer Transaction Instantiation**:
   - `executeBusinessTransaction()` starts the transaction context by creating a `Transaction` record.
   - It binds this instance to `CURRENT_TX` using `ScopedValue.where(CURRENT_TX, outerTx).run(...)`. The lambda block defines the transaction boundary.

2. **Downstream Context Inspection**:
   - Within the transaction scope, the service runs `performNestedBusinessLogic()`.
   - The method checks `CURRENT_TX.isBound()`. Since it is running inside the lambda of `executeBusinessTransaction()`, `isBound()` returns `true`.
   - The method joins the active transaction by calling `CURRENT_TX.get()`, which retrieves the outer transaction reference without creating a new transaction.
   - It runs its database write under the context of the outer transaction.

3. **Standalone Fallback Path**:
   - In Scenario 2, `performNestedBusinessLogic()` is called directly from `main()`, outside of any transaction scope.
   - `CURRENT_TX.isBound()` returns `false`.
   - The method falls back to creating a local standalone transaction record and binds it using `ScopedValue.where(CURRENT_TX, innerTx).run(...)` to execute the database write.

---

### 3. SimpleGraphicsExample: Rebinding Visual Context
In UI rendering, parent components often set drawing properties (like colors or line widths) that apply to children. We can model this drawing context using Scoped Values, showing how nested components temporarily override properties without manual cleanup.

```java
import java.awt.Color;

public class SimpleGraphicsExample {

    private static final ScopedValue<Color> DRAW_COLOR = ScopedValue.newInstance();
    private static final ScopedValue<Integer> LINE_WIDTH = ScopedValue.newInstance();

    public static void drawLine(String from, String to) {
        // Fall back to defaults if drawing context is unbound
        Color color = DRAW_COLOR.orElse(Color.BLACK);
        int width = LINE_WIDTH.orElse(1);
        System.out.printf("  Line from %s to %s [Color: %s, Width: %dpx]%n", from, to, color.toString(), width);
    }

    public static void drawPanel() {
        System.out.println("Drawing Panel Container (Setting Gray Theme)...");
        ScopedValue.where(DRAW_COLOR, Color.GRAY)
                   .where(LINE_WIDTH, 2)
                   .run(() -> {
                       drawLine("PanelTop", "PanelBottom");
                       
                       // Draw nested Button inside the panel
                       drawButton("Submit");
                       
                       // Verification: panel drawing properties are restored
                       drawLine("PanelLeft", "PanelRight");
                   });
    }

    public static void drawButton(String label) {
        System.out.println("  Drawing Button '" + label + "' (Overriding Theme)...");
        // Button overrides properties locally inside its scope
        ScopedValue.where(DRAW_COLOR, Color.BLUE)
                   .where(LINE_WIDTH, 4)
                   .run(() -> {
                       drawLine("BtnLeft", "BtnRight");
                       System.out.println("    Button Label Text: '" + label + "' rendering...");
                   });
    }

    public static void main(String[] args) {
        System.out.println("--- Start Graphics Context Rendering ---");
        // Render root lines with application default values
        drawLine("RootLeft", "RootRight");

        // Render Panel (which renders buttons inside it)
        drawPanel();

        // Render final root line (verifying default context holds)
        drawLine("RootEndLeft", "RootEndRight");
    }
}
```

##### Code Walkthrough: `SimpleGraphicsExample`

1. **Default Values Lookup**:
   - `drawLine()` is called. It uses `DRAW_COLOR.orElse(Color.BLACK)` and `LINE_WIDTH.orElse(1)`.
   - At the start, the first line is drawn from `RootLeft` to `RootRight`. Because no bindings are active on the stack, the method falls back to `Color.BLACK` and `1px` width.

2. **Hierarchical Theme Binding**:
   - Inside `drawPanel()`, the code binds `DRAW_COLOR` to `Color.GRAY` and `LINE_WIDTH` to `2`.
   - It calls `drawLine("PanelTop", "PanelBottom")`, which resolves the properties from the stack frame, drawing a gray, 2px line.

3. **Local Overriding (Rebinding)**:
   - `drawPanel()` calls `drawButton("Submit")`.
   - Inside `drawButton()`, the code binds `DRAW_COLOR` to `Color.BLUE` and `LINE_WIDTH` to `4` for its own scope.
   - The line inside the button is drawn in blue with a 4px width.
   - When the button's `run()` scope exits, the JVM pops the blue bindings.
   - Subsequent calls inside `drawPanel()` (like `drawLine("PanelLeft", "PanelRight")`) automatically resolve back to `Color.GRAY` and `2px`.
   - Finally, when `drawPanel()` exits, all bindings are cleared, and the final line `RootEndLeft` to `RootEndRight` renders in black and 1px width.

---

## 7. ScopedValue and Structured Concurrency

With virtual threads, tasks are often fanned out in parallel. In classic Java, passing context to child threads spawned via `ExecutorService` was expensive because it required copying thread-local maps.

With Structured Concurrency, the JVM uses **context inheritance** through stack pointer referencing:
- **Zero-Copy Reference Sharing**: When you call `StructuredTaskScope.fork()`, the JVM spawns a child virtual thread. Instead of allocating a new map or copying entries, the child thread's internal state contains a direct reference to the parent thread's active `ScopedValue` binding node on the stack.
- **Boundary Protection**: Under normal thread pools, if a parent thread spawned a child and exited, the parent's stack frame would be destroyed. If the child tried to read parent stack references, it would cause errors. Structured concurrency solves this with the strict nested boundary of `StructuredTaskScope.join()`: the parent thread cannot exit the try-with-resources scope until all child tasks finish. This guarantees the parent's stack remains valid while the child threads run.

Let us visualize this stack pointer layout:

```
[ Parent Thread Stack Frame ]
 ├─► ScopedValue Node: [KEY = "traceId", VALUE = "TX-8899"]
 │
 └─► [StructuredTaskScope Block]
       ├─► fork() ──► Spawn Child Thread 1 (Virtual Thread)
       │                └─► StackBindings Pointer ────────────────┐
       │                                                          │ (Direct reference)
       └─► fork() ──► Spawn Child Thread 2 (Virtual Thread)       ▼
                        └─► StackBindings Pointer ────────► [Parent Binding Node]
```

This stack-bound link lets child threads read variables in $O(1)$ time with zero copy cost at fork time. When the parent scope exits, the bindings are popped off the stack, keeping context sharing clean, fast, and leak-free.

```java
// Forked subtasks inherit scope context implicitly:
ScopedValue.where(CURRENT_USER, "Alice").run(() -> {
    try (var scope = StructuredTaskScope.open()) {
        scope.fork(() -> {
            // Runs on virtual thread, inherits CURRENT_USER -> "Alice"
            System.out.println("Subtask running for: " + CURRENT_USER.get());
            return null;
        });
        scope.join();
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
    }
});
```

---

## 8. Beginner-Friendly Visualization: The Backpack and Locker Analogy

To understand why Java introduced Scoped Values to replace ThreadLocals, let us look at an office analogy.

Imagine an office where workers (Threads) process requests. Each request needs specific files (like user credentials or transaction IDs) to be accessible by various departments (Service classes, Repositories).

### The ThreadLocal Model (The Office Locker)
In the traditional ThreadLocal approach:
- **The Lockers**: Every worker has their own personal metal locker next to their desk (`ThreadLocalMap`).
- **The Process**:
  - When a request arrives, the worker puts the customer's files inside their personal locker (`ThreadLocal.set()`).
  - As they do their work, different departments open the locker to read the files.
  - **The Problems**:
    1. **Forgotten Cleanup**: When the worker finishes the request, they are supposed to empty the locker. But if they forget (`ThreadLocal.remove()`), the files stay inside. Tomorrow, if the worker is assigned to a different customer, they open the locker and find yesterday's data. This causes **memory leaks** and **context leaks**.
    2. **High Cost**: If you have 10,000 workers (virtual threads), you must buy 10,000 lockers, which takes up massive office space (RAM overhead).
    3. **Expensive Copies for Helpers**: If a worker hires helpers (child threads) to assist, the worker must copy all the papers from their locker into the helpers' lockers. This copying is slow and wastes memory.

### The ScopedValue Model (The Stack-Bound Backpack)
Project Loom replaces lockers with a temporary, stack-bound backpack:
- **The Backpacks**: When a worker starts a request, they place the files inside a temporary backpack (`ScopedValue.where(KEY, value)`).
- **The Process**:
  - The worker carries the backpack with them as they walk from department to department.
  - When they call a method, they are simply giving access to the backpack. The data is **read-only** (immutable), so departments cannot change the contents.
  - **Zero-Copy Sharing**: If the worker forks child tasks, the child tasks do not get their own backpacks. Instead, they just reach into the parent's backpack while it is active. This is **zero-copy reference sharing**.
  - **Automatic Cleanup**: As soon as the worker finishes the request and exits the scope block, the backpack is automatically destroyed.
  - Because the backpack's lifetime is bound to the execution scope, it is **impossible** to forget to empty it. There are no lockers left locked, and memory is reclaimed instantly.

This is why Scoped Values are superior for virtual threads: they are lightweight, read-only, automatically cleaned up, and shared with child tasks without memory copying.

---

## 9. Logging Interoperability: Mapped Diagnostic Context (MDC) Bridging

In production applications, distributed tracing and correlation IDs are printed on every log message. Logging libraries (such as Logback or Log4j2) rely on **Mapped Diagnostic Context (MDC)**, which is backed by a standard `ThreadLocal` variable.

When migrating to Scoped Values, logging libraries do not automatically detect the scoped value context. If you read `MDC.get("traceId")` inside a virtual thread running a scoped value task, it returns `null` because the MDC ThreadLocal map is empty.

To resolve this, you can write an integration bridge that copies scoped values to the MDC map when a context scope starts, and clears them when the scope exits.

### The MDC Bridge Pattern (`MdcContextBridge.java`)

```java
package com.example.concurrency;

import org.slf4j.MDC;
import java.util.concurrent.Callable;

public class MdcContextBridge {

    public static final ScopedValue<String> TRACE_ID = ScopedValue.newInstance();
    public static final ScopedValue<String> TENANT_ID = ScopedValue.newInstance();

    public static class MdcScope implements AutoCloseable {
        private final String traceId;
        private final String tenantId;

        public MdcScope(String traceId, String tenantId) {
            this.traceId = traceId;
            this.tenantId = tenantId;
            
            // Bind context to MDC ThreadLocal
            MDC.put("traceId", traceId);
            MDC.put("tenantId", tenantId);
        }

        @Override
        public void close() {
            // Clean up MDC ThreadLocal to prevent leaks in thread pools
            MDC.remove("traceId");
            MDC.remove("tenantId");
        }
    }

    /**
     * Executes a task, bridging Scoped Values to MDC.
     */
    public static <T> T callWithMdc(String traceId, String tenantId, Callable<T> task) throws Exception {
        return ScopedValue.where(TRACE_ID, traceId)
                          .where(TENANT_ID, tenantId)
                          .call(() -> {
                              // Wrap MDC updates in a try-with-resources scope
                              try (MdcScope mdc = new MdcScope(traceId, tenantId)) {
                                  return task.call();
                              }
                          });
    }

    /**
     * Downstream service method that logs transactions.
     */
    public void processPayment(double amount) {
        // Log messages will automatically include [traceId] and [tenantId] in MDC layouts
        System.out.printf("[MDC: traceId=%s, tenantId=%s] Processing payment of $%.2f%n",
                MDC.get("traceId"), MDC.get("tenantId"), amount);
        
        // Assert scoped values are also available
        System.out.println("  ScopedValue validation: Active trace is " + TRACE_ID.get());
    }

    public static void main(String[] args) throws Exception {
        MdcContextBridge service = new MdcContextBridge();

        System.out.println("Starting MDC Bridge Execution...");
        
        callWithMdc("TX-9988", "TENANT-APAC", () -> {
            service.processPayment(1500.00);
            return null;
        });

        // Verify MDC and Scoped Values are cleared
        System.out.println("Scope exited. MDC traceId is: " + MDC.get("traceId"));
        System.out.println("Scope exited. ScopedValue isBound: " + TRACE_ID.isBound());
    }
}
```

### Walkthrough: Logging Interoperability Mechanics

1. **Dual Context Binding**:
   - `callWithMdc()` binds the trace ID and tenant ID to Scoped Values: `ScopedValue.where(TRACE_ID, traceId).where(TENANT_ID, tenantId)`.
   - Within the bounded scope, we open a try-with-resources block initializing `MdcScope`.
   - The constructor of `MdcScope` calls `MDC.put()`, writing the values to the logging framework's thread-local map.

2. **Automatic MDC Cleanup**:
   - `MdcScope` implements `AutoCloseable`.
   - When the task completes (normally or with an exception), the try-with-resources statement calls `close()`.
   - The `close()` method runs `MDC.remove()`, clearing the keys from the thread-local map. This prevents memory leaks when worker threads are recycled in a pool.

3. **Downstream Logging**:
   - Any log output generated by logging libraries (using the `%X{traceId}` pattern) inside the block will successfully extract the trace context, linking logs across parallel tasks.

---

## 10. Enterprise Context Propagation and Executor Decorators

### The Thread Pool Bridging Challenge
In typical architectures, asynchronous tasks are submitted to shared executors (`ThreadPoolExecutor` or `ForkJoinPool`). These executors run tasks on worker threads that are detached from the caller's context.

If a request thread sets MDC parameters or binds a `ScopedValue`, these bindings are thread-bound. As soon as a task is offloaded to an executor (like `executor.submit(runnable)`), the executor thread has an empty MDC and unbound `ScopedValue` variables, resulting in missing log context and runtime exceptions.

With `ScopedValue`, the framework provides `Carrier.run(Runnable)` or `Carrier.call(Callable)`. However, if you are fanning out tasks to an async executor, we must use a custom decorator to capture the caller's bindings and re-bind them inside the worker thread execution context.

### Capturing and Decorating Scoped Values
To bridge Scoped Values across executor boundaries, we can build custom decorators. The decorator wraps the submitted `Runnable` or `Callable` task:
1. **Capturing**: At task submission (on the parent thread), the decorator captures the active ScopedValue mappings.
2. **Re-binding**: When the worker thread runs the task, it wraps the execution in a nested `ScopedValue.where(...)` block using the captured values.
3. **MDC Synchronization**: Concurrently, the decorator copies the SLF4J MDC map, writes it to the worker thread's MDC before execution, and clears it in a `finally` block to prevent thread pool leaks.

Let's look at a complete, production-grade implementation of a Context-Aware Executor Decorator:

```java
package com.example.concurrency;

import org.slf4j.MDC;
import java.util.Map;
import java.util.concurrent.*;

/**
 * An enterprise executor service decorator that automatically propagates SLF4J MDC
 * contexts and ScopedValue scopes from the submitting thread to the executing virtual or platform thread.
 */
public class EnterpriseContextPropagator implements ExecutorService {

    public static final ScopedValue<String> USER_PRINCIPAL = ScopedValue.newInstance();
    public static final ScopedValue<String> CORRELATION_ID = ScopedValue.newInstance();

    private final ExecutorService delegate;

    public EnterpriseContextPropagator(ExecutorService delegate) {
        this.delegate = delegate;
    }

    /**
     * Decorates a Runnable to capture the caller thread's MDC and Scoped Values,
     * restoring them within the execution context of the worker thread.
     */
    private Runnable decorate(Runnable task) {
        // Capture MDC context map on the submitting thread
        Map<String, String> parentMdc = MDC.getCopyOfContextMap();
        
        // Capture Scoped Values
        boolean principalBound = USER_PRINCIPAL.isBound();
        String principal = principalBound ? USER_PRINCIPAL.get() : null;
        
        boolean correlationBound = CORRELATION_ID.isBound();
        String correlationId = correlationBound ? CORRELATION_ID.get() : null;

        return () -> {
            // Reconstruct ScopedValue bindings on the executing thread
            ScopedValue.Carrier carrier = ScopedValue.where(USER_PRINCIPAL, principal);
            if (correlationBound) {
                carrier = ScopedValue.where(CORRELATION_ID, correlationId);
            }
            
            // Execute the carrier scope
            final Map<String, String> finalParentMdc = parentMdc;
            final ScopedValue.Carrier finalCarrier = carrier;
            
            finalCarrier.run(() -> {
                // Apply parent MDC values to the executing thread
                boolean mdcApplied = false;
                if (finalParentMdc != null) {
                    MDC.setContextMap(finalParentMdc);
                    mdcApplied = true;
                }
                
                try {
                    task.run();
                } finally {
                    // Critical: Clean up MDC thread-local to prevent leaks on reused executor threads
                    if (mdcApplied) {
                        MDC.clear();
                    }
                }
            });
        };
    }

    /**
     * Decorates a Callable to capture and restore execution contexts.
     */
    private <T> Callable<T> decorate(Callable<T> task) {
        Map<String, String> parentMdc = MDC.getCopyOfContextMap();
        
        boolean principalBound = USER_PRINCIPAL.isBound();
        String principal = principalBound ? USER_PRINCIPAL.get() : null;
        
        boolean correlationBound = CORRELATION_ID.isBound();
        String correlationId = correlationBound ? CORRELATION_ID.get() : null;

        return () -> {
            ScopedValue.Carrier carrier = ScopedValue.where(USER_PRINCIPAL, principal);
            if (correlationBound) {
                carrier = ScopedValue.where(CORRELATION_ID, correlationId);
            }
            
            final Map<String, String> finalParentMdc = parentMdc;
            final ScopedValue.Carrier finalCarrier = carrier;
            
            return finalCarrier.call(() -> {
                boolean mdcApplied = false;
                if (finalParentMdc != null) {
                    MDC.setContextMap(finalParentMdc);
                    mdcApplied = true;
                }
                try {
                    return task.call();
                } finally {
                    if (mdcApplied) {
                        MDC.clear();
                    }
                }
            });
        };
    }

    // Decorating Delegate methods
    @Override
    public void execute(Runnable command) {
        delegate.execute(decorate(command));
    }

    @Override
    public <T> Future<T> submit(Callable<T> task) {
        return delegate.submit(decorate(task));
    }

    @Override
    public <T> Future<T> submit(Runnable task, T result) {
        return delegate.submit(decorate(task), result);
    }

    @Override
    public Future<?> submit(Runnable task) {
        return delegate.submit(decorate(task));
    }

    // Lifecycle methods delegated directly
    @Override public void shutdown() { delegate.shutdown(); }
    @Override public java.util.List<Runnable> shutdownNow() { return delegate.shutdownNow(); }
    @Override public boolean isShutdown() { return delegate.isShutdown(); }
    @Override public boolean isTerminated() { return delegate.isTerminated(); }
    @Override public boolean awaitTermination(long timeout, TimeUnit unit) throws InterruptedException { return delegate.awaitTermination(timeout, unit); }
    @Override public <T> java.util.List<Future<T>> invokeAll(java.util.Collection<? extends Callable<T>> tasks) throws InterruptedException { throw new UnsupportedOperationException(); }
    @Override public <T> java.util.List<Future<T>> invokeAll(java.util.Collection<? extends Callable<T>> tasks, long timeout, TimeUnit unit) throws InterruptedException { throw new UnsupportedOperationException(); }
    @Override public <T> T invokeAny(java.util.Collection<? extends Callable<T>> tasks) throws InterruptedException, ExecutionException { throw new UnsupportedOperationException(); }
    @Override public <T> T invokeAny(java.util.Collection<? extends Callable<T>> tasks, long timeout, TimeUnit unit) throws InterruptedException, ExecutionException, TimeoutException { throw new UnsupportedOperationException(); }
}
```

##### Code Walkthrough: `EnterpriseContextPropagator`

1. **Context Capture on Submission**:
   - When a task is submitted, the decorator runs `MDC.getCopyOfContextMap()` to extract the active MDC entries.
   - It captures the current `USER_PRINCIPAL` and `CORRELATION_ID` using `ScopedValue.isBound()` and `ScopedValue.get()`. This occurs on the parent thread before submitting the task to the executor.

2. **Re-binding inside the Worker Thread**:
   - The returned `Runnable` lambda runs inside the worker thread.
   - It reconstructs the `ScopedValue.Carrier` using the parent's values: `ScopedValue.Carrier carrier = ScopedValue.where(USER_PRINCIPAL, principal)`.
   - It calls `finalCarrier.run(...)` to push the bindings onto the executing thread's stack.
   - It sets the worker thread's MDC context: `MDC.setContextMap(finalParentMdc)`.

3. **Cleanup**:
   - The task runs in a try-finally block.
   - The `finally` block calls `MDC.clear()`, removing the logging context from the worker thread's thread-local storage to prevent leaks.

### Performance Footprint: Context Propagation Analysis
In systems fanning out thousands of parallel sub-requests, context propagation must be fast:
1. **MDC Copying Overhead**:
   - `MDC.getCopyOfContextMap()` copies the underlying `HashMap` (backed by a platform `ThreadLocal`). Under high loads, this can create garbage collection pressure due to map and entry allocations.
   - *Optimization*: Limit MDC usage to a few critical tracing fields (`traceId`, `spanId`) instead of storing large payloads.
2. **Scoped Value Stack-Based Lookup Overhead**:
   - Unlike `ThreadLocal` (which resolves values by indexing a map table), Scoped Values are resolved by walking the snapshot chain on the thread stack.
   - When calling `ScopedValue.get()`, the JVM traverses from the current binding head back to the root node.
   - If the nesting depth is high, lookup transitions from $O(1)$ to $O(N)$ stack traverses. However, because these references are contiguous in memory, CPU caches keep lookup latency low (typically a few nanoseconds).
   - Binding allocations are stack-scoped and can be optimized away by the JIT compiler via Escape Analysis, leading to near-zero heap allocations.

---

## 11. Memory Profile Analysis: ThreadLocal vs ScopedValue

To understand the difference in memory use, let us analyze the allocation footprints under high load.

### ThreadLocal Footprint
Every thread allocating thread-local variables maintains an active `ThreadLocalMap` containing a table array of `Entry` objects.

$$\text{ThreadLocal Footprint} = T \times \left( M_{\text{map}} + \sum (E_{\text{entry}} + O_{\text{payload}}) \right)$$

Where:
* $T$ is the number of threads.
* $M_{\text{map}}$ is the map container allocation overhead (~64 bytes).
* $E_{\text{entry}}$ is the map table array element reference size.
* $O_{\text{payload}}$ is the context payload object size.

If $T = 1,000,000$ virtual threads and we place a 500KB context payload inside:
* If each thread allocates or copies the payload, memory use increases by hundreds of megabytes.
* Forgotten cleanup means the objects remain pinned in memory, causing long GC pauses or memory exhaustion.

### ScopedValue Footprint
Scoped values do not allocate map container objects inside thread structures. Bindings are tracked via a single list pointer associated with the executing scope.

$$\text{ScopedValue Footprint} = O_{\text{payload}} + T \times (\text{Pointer Link Reference})$$

Since the payload is immutable, a single instance of the payload is created once and shared via stack pointers among all child virtual threads. This reduces memory allocations to near-zero.

---

## 12. Hands-On Labs

Compile and execute these labs using the preview flags:
```powershell
javac --enable-preview --release 25 Lab.java
java --enable-preview Lab
```

---

### Lab 5.1 — Request Context without Parameter Pollution
**Objective**: Build a request context propagation simulator. Set the transaction properties in the Controller, and access them downstream in Service and Repository layers without passing parameters.

```java
import java.util.NoSuchElementException;

public class Lab51RequestContext {

    public record RequestContext(String traceId, String clientIp, String userRole) {}

    // Static ScopedValue holder
    public static final ScopedValue<RequestContext> WEB_CONTEXT = ScopedValue.newInstance();

    public static void main(String[] args) {
        WebController controller = new WebController();

        System.out.println("--- Request 1: Admin User ---");
        controller.handleRequest("TXN-7711", "192.168.1.1", "ADMIN");

        System.out.println("\n--- Request 2: Standalone Service Call (Unbound Context) ---");
        // Verify default fallback handling
        controller.handleStandaloneCall();
    }

    static class WebController {
        private final BusinessService service = new BusinessService();

        public void handleRequest(String traceId, String ip, String role) {
            RequestContext context = new RequestContext(traceId, ip, role);
            
            // Bind context dynamically
            ScopedValue.where(WEB_CONTEXT, context).run(() -> {
                service.executeRequestLogic();
            });
        }

        public void handleStandaloneCall() {
            // Executing service logic directly without binding context
            service.executeRequestLogic();
        }
    }

    static class BusinessService {
        private final DatabaseRepository repository = new DatabaseRepository();

        public void executeRequestLogic() {
            // Retrieve context parameters implicitly
            if (WEB_CONTEXT.isBound()) {
                RequestContext ctx = WEB_CONTEXT.get();
                System.out.println("Service: Processing request " + ctx.traceId() + " for role " + ctx.userRole());
            } else {
                System.out.println("Service: Processing request under default guest credentials.");
            }
            repository.saveAuditLog();
        }
    }

    static class DatabaseRepository {
        public void saveAuditLog() {
            // Deep downstream layer reads context implicitly or falls back to GUEST
            RequestContext ctx = WEB_CONTEXT.orElse(new RequestContext("TRACE-NONE", "127.0.0.1", "GUEST"));
            System.out.println("Repository: Saving log -> [ID: " + ctx.traceId() + " | IP: " + ctx.clientIp() + " | Role: " + ctx.userRole() + "]");
        }
    }
}
```

#### Step-by-Step Logic Walkthrough
1. **Context Initialization**:
   - We define `WEB_CONTEXT` as a `public static final ScopedValue<RequestContext>`. It acts as our context registry.
2. **Dynamic Binding**:
   - In `WebController.handleRequest()`, we create a `RequestContext` record.
   - We call `ScopedValue.where(WEB_CONTEXT, context).run(...)`. The lambda block defines the dynamic scope, and the JVM registers this binding on the calling thread's stack.
3. **Downstream Retrieval**:
   - `BusinessService` calls `WEB_CONTEXT.isBound()` to check if the context exists, printing user info if present.
   - `DatabaseRepository` calls `WEB_CONTEXT.orElse(...)`. If the context is unbound (as in Scenario 2), it returns the default guest context without throwing a `NoSuchElementException`.
4. **Scope Exiting**:
   - When the `run()` block finishes, the JVM automatically pops the binding, preventing context leaks.

---

### Lab 5.2 — ScopedValue + StructuredTaskScope
**Objective**: Bind a trace context, spawn two concurrent subtasks inside a `StructuredTaskScope` block, and verify that both subtasks inherit the binding.

```java
import java.time.Duration;
import java.util.concurrent.StructuredTaskScope;

public class Lab52ScopedStructured {

    private static final ScopedValue<String> GLOBAL_TRACE_ID = ScopedValue.newInstance();

    public static void main(String[] args) {
        System.out.println("Binding trace ID 'TX-889900'...");
        
        ScopedValue.where(GLOBAL_TRACE_ID, "TX-889900").run(() -> {
            try {
                executeConcurrentAggregation();
            } catch (Exception e) {
                System.err.println("Aggregation aborted: " + e.getMessage());
            }
        });
    }

    private static void executeConcurrentAggregation() throws Exception {
        try (var scope = StructuredTaskScope.open()) {
            
            var userTask = scope.fork(() -> {
                // Assert context inheritance on child virtual thread
                System.out.println("[" + Thread.currentThread().getName() + "] UserTask read trace: " + GLOBAL_TRACE_ID.get());
                Thread.sleep(Duration.ofMillis(100));
                return "User: Alice";
            });

            var accountTask = scope.fork(() -> {
                // Assert context inheritance on sibling child virtual thread
                System.out.println("[" + Thread.currentThread().getName() + "] AccountTask read trace: " + GLOBAL_TRACE_ID.get());
                Thread.sleep(Duration.ofMillis(120));
                return "Account: Premium";
            });

            scope.join();
            System.out.println("Compiled Results: " + userTask.get() + " | " + accountTask.get());
        }
    }
}
```

#### Step-by-Step Logic Walkthrough
1. **Binding Context**:
   - The main thread enters `ScopedValue.where(GLOBAL_TRACE_ID, "TX-889900").run(...)`, setting the parent bindings.
2. **Concurrent Forking**:
   - Inside `executeConcurrentAggregation()`, we open a `StructuredTaskScope`.
   - We fork `userTask` and `accountTask`, which tells the JVM to spawn two virtual threads.
3. **Context Inheritance**:
   - The JVM links the child virtual threads' bindings to the main thread's stack.
   - When the child threads call `GLOBAL_TRACE_ID.get()`, they traverse pointers back to the main thread's stack frame. This is **zero-copy reference sharing** with zero allocation cost.
4. **Coordination**:
   - The parent thread blocks on `scope.join()`, waiting for both child threads to finish before printing the results.

---

### Lab 5.3 — ThreadLocal vs ScopedValue Memory Profile
**Objective**: Demonstrate the memory difference between storing state inside `ThreadLocal` vs using `ScopedValue` reference sharing across 10,000 virtual threads.

```java
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class Lab53MemoryProfileDemo {

    public static class HeavyConfig {
        // Carry 500KB byte payload
        private final byte[] memoryBlock = new byte[500 * 1024]; 
    }

    private static final ThreadLocal<HeavyConfig> THREAD_LOCAL_CONFIG = new ThreadLocal<>();
    private static final ScopedValue<HeavyConfig> SCOPED_VALUE_CONFIG = ScopedValue.newInstance();

    public static void main(String[] args) throws InterruptedException {
        int threads = 10000;
        System.out.println("Starting Concurrency Memory Simulator...");
        System.out.println("Spawning " + threads + " virtual threads.");

        // 1. ScopedValue Run (Safe Reference Sharing)
        System.out.println("\nExecuting ScopedValue benchmark...");
        long memStart = Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory();
        
        HeavyConfig sharedConfig = new HeavyConfig(); // Single shared reference
        
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int i = 0; i < threads; i++) {
                executor.submit(() -> {
                    ScopedValue.where(SCOPED_VALUE_CONFIG, sharedConfig).run(() -> {
                        // Perform minimal lookup operation
                        int len = SCOPED_VALUE_CONFIG.get().memoryBlock.length;
                        if (len != 512_000) {
                            System.err.println("Validation failed!");
                        }
                    });
                });
            }
        }
        
        long memEnd = Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory();
        System.out.println("Memory consumed under ScopedValue reference mapping: " + ((memEnd - memStart) / 1024 / 1024) + " MB");
        System.out.println("Conclusion: Direct reference pointer sharing prevents duplication.");
    }
}
```

#### Step-by-Step Logic Walkthrough
1. **Heavy Configuration Payload**:
   - We create a `HeavyConfig` class containing a 500KB byte array. This simulates metadata caches, security tokens, or localization tables.
2. **Scoped Value Sharing**:
   - A single instance of `HeavyConfig` is created.
   - We loop 10,000 times, running tasks inside a virtual thread executor. Each task binds the same configuration instance to `SCOPED_VALUE_CONFIG`.
   - Because Scoped Values are immutable, they share the single reference across the scope chain, keeping memory use minimal.
3. **Comparing with ThreadLocal**:
   - If we used `ThreadLocalMap` or `InheritableThreadLocal` for 10,000 threads, each thread would allocate its own Map structure containing entry tables and bindings.
   - In workloads with deep inheritance or thread pools, this leads to heap inflation and garbage collector churn, which Scoped Values avoid.

---

## 13. Pitfalls & Knowledge Check

### Common Pitfalls

#### 1. Mutation Attempt via Compilation Error
`ScopedValue` does not expose a write method (like `set()` or `update()`). If you try to update the value directly, compilation fails:

```java
private static final ScopedValue<String> ROLE = ScopedValue.newInstance();
ROLE.set("Manager"); // COMPILE ERROR: cannot find symbol method set(String)
```
**Fix**: If context must change for a nested workflow, use the dynamic **shadowing/rebinding** pattern:
```java
ScopedValue.where(ROLE, "Employee").run(() -> {
    System.out.println(ROLE.get()); // Employee
    
    // Rebind nested block
    ScopedValue.where(ROLE, "Manager").run(() -> {
        System.out.println(ROLE.get()); // Manager
    });
});
```

#### 2. Accessing Scoped Value Outside the Bounded Lifetime Block
Invoking `.get()` outside the execution scope of the carrier throws a `NoSuchElementException`.

```java
public class UnboundReadExample {
    private static final ScopedValue<String> CONTEXT = ScopedValue.newInstance();
    
    public void execute() {
        System.out.println(CONTEXT.get()); // Throws NoSuchElementException!
    }
}
```
**Fix**: Always verify binding status using `isBound()`, or provide a default fallback value using `orElse()` or `orElseThrow()`:
```java
String value = CONTEXT.orElse("DefaultGuest");
```

### Knowledge Check

#### Question 1: ThreadLocal Scalability
Why is ThreadLocal problematic when scaled to millions of virtual threads?
- A) Virtual threads cannot compile code containing ThreadLocal.
- B) ThreadLocal forces virtual threads to allocate and copy data into memory-heavy, individual `ThreadLocalMap` structures, causing heap footprint inflation under high concurrency.
- C) ThreadLocal causes immediate CPU-bound hardware deadlocks.
- D) None of the above.

*Answer*: **B**
*Explanation*: Platform threads are few, so having a `ThreadLocalMap` per thread is inexpensive. However, virtual threads are designed to scale to millions of concurrent tasks on the heap. Storing context inside `ThreadLocal` forces each virtual thread to allocate a `ThreadLocalMap` container object. This causes a massive heap allocation overhead that completely defeats the lightweight design of virtual threads.

#### Question 2: API Chaining
Which API method is used to bind multiple Scoped Values simultaneously?
- A) `ScopedValue.where().andWhere().run()`
- B) `ScopedValue.where().where().run()`
- C) `ScopedValue.bind().bind().execute()`
- D) `ScopedValue.open().fork()`

*Answer*: **B**
*Explanation*: Bindings are chained by invoking `where(key, value)` sequentially on the returned `ScopedValue.Carrier` builder object: `ScopedValue.where(KEY1, val1).where(KEY2, val2).run(task)`.

#### Question 3: Structured Context Inheritance
How do child virtual threads spawned via `StructuredTaskScope.fork()` inherit Scoped Values from their parent thread?
- A) They make complete serialized duplicates of the parent thread's values.
- B) They access values through a global, concurrent hash map using synchronized locks.
- C) They inherit access via pointer links to the parent thread's active stack frame bindings with zero copy allocation cost.
- D) They do not inherit scoped values.

*Answer*: **C**
*Explanation*: To keep thread spawning extremely cheap, the JVM does not copy parent bindings to child threads. Instead, when a subtask is forked via `StructuredTaskScope`, the JVM links the child virtual thread's `scopedValueBindings` pointer directly to the parent thread's active stack frame binding node. The child reads the context in O(1) time with zero allocation overhead at fork time.

#### Question 4: Unbound Retrieval Behavior
What is the behavior of calling `ScopedValue.get()` outside of its bound scope?
- A) It returns `null`.
- B) It blocks the thread indefinitely.
- C) It throws a `NoSuchElementException`.
- D) It throws a `NullPointerException`.

*Answer*: **C**
*Explanation*: Unlike `ThreadLocal` (which returns `null` if the variable has not been initialized for the current thread), `ScopedValue.get()` enforces strict API boundaries. Reading a scoped value outside of its bound scope throws a `NoSuchElementException` to help detect integration errors early.

#### Question 5: When to Prefer ThreadLocal
Under what circumstances should a developer continue to use `ThreadLocal` instead of `ScopedValue` in modern Java applications?
- A) When propagating transaction tracing IDs down read-only service trees.
- B) When they genuinely require mutable, writeable thread-isolated state that updates throughout a thread's lifecycle.
- C) When they want to rate limit microservice API requests.
- D) When deploying on modern JDK 25 platforms.

*Answer*: **B**
*Explanation*: Scoped Values are strictly immutable. If your design calls for a mutable scratchpad that thread components write to and mutate throughout their execution (e.g., transaction state updates or incremental parser buffers), `ThreadLocal` remains the appropriate abstraction.

#### Question 6: Context Inheritance in Unstructured Threads
A developer binds a scoped value and then spawns a thread using `new Thread().start()` or `executor.submit()`. Does the child thread inherit the scoped value?
- A) Yes, all child threads inherit scoped values automatically.
- B) No, scoped value context inheritance is only supported for concurrent subtasks spawned using the Structured Concurrency framework (`StructuredTaskScope.fork()`).
- C) Yes, but only if the child thread is a virtual thread.
- D) Only if the parent thread is a platform thread.

*Answer*: **B**
- *Explanation*: Scoped value inheritance relies on the parent-child relationships established by `StructuredTaskScope`. Unstructured threads spawned via raw `Thread` constructors or traditional executors do not participate in this stack linkage and will throw `NoSuchElementException` when attempting to access the parent thread's scoped values.

#### Question 7: Shadowing Heap Allocations
When you rebind/shadow a scoped value inside a nested scope (`ScopedValue.where(KEY, newValue).run(...)`), how does this affect memory footprint?
- A) It copies the entire parent binding list, multiplying heap allocations.
- B) It merely allocates a lightweight snapshot node on the stack, linking it back to the previous head of the binding list. The original value remains unchanged and is restored when the nested scope exits.
- C) It overrides the value globally in memory.
- D) It triggers garbage collection of all parent scopes.

*Answer*: **B**
- *Explanation*: Shadowing does not copy maps or allocate major objects. The JVM allocates a single stack-bound snapshot node containing the key, new value, and a reference pointer pointing to the previous binding head. This stack node is garbage collected as soon as the nested `run`/`call` method returns.

#### Question 8: Rebinding Scope Visibility
Consider a parent method that binds `KEY` to `"Parent"`. It calls a nested method that rebinds `KEY` to `"Child"`. When the nested method completes and execution returns to the parent method, what is the value of `KEY.get()`?
- A. `"Child"`
- B. `"Parent"`
- C. It throws `NoSuchElementException`.
- D. It returns `null`.

*Answer*: **B**
- *Explanation*: Scoped values are stack-bounded. Rebinding only shadows the value inside the nested execution frame. Once the nested `run`/`call` block returns, the snapshot node is popped off the thread's binding chain, automatically restoring the previous value (`"Parent"`) for the outer scope.

#### Question 9: Memory Leak Mitigation
Why are Scoped Values immune to the memory leak vulnerabilities associated with pooled `ThreadLocal` variables?
- A) The JVM forces automatic thread recreation.
- B) Their lifetime is strictly bound to the execution frame of a `run()` or `call()` method. The moment the method returns, the JVM pops the binding. No manual `.remove()` is needed to prevent leaks in pooled threads.
- C) Scoped Values are stored in off-heap memory.
- D) The Garbage Collector runs after every method execution.

*Answer*: **B**
- *Explanation*: ThreadLocal variables persist until `remove()` is called, causing leaks in reusable pooled threads. Scoped value lifetimes are defined by the lexical scope of the carrier's execution block. Once the block terminates (normally or exceptionally), the JVM automatically discards the binding reference.

#### Question 10: Lookup Performance Optimizations
How does the JVM guarantee O(1) read performance for Scoped Values, despite them being stored as a linked list chain of stack nodes?
- A) By keeping stack depths under 5 frames.
- B) Using a thread-local cache slot or hardware register to cache the most recently retrieved scoped values, bypassing list traversal on repeated reads.
- C) By converting the list into a HashMap at runtime.
- D) None of the above.

*Answer*: **B**
- *Explanation*: To optimize read hot paths, the JVM maintains a fast thread-local lookup cache. When a scoped value is read, the result is cached. Subsequent reads bypass walking the binding list chain and are served directly from the cache slot or CPU registers.

#### Question 11: Private Constructors and API Safety
Why does the `ScopedValue` class not expose a public constructor, forcing the use of `ScopedValue.newInstance()`?
- A) To prevent heap allocation of ScopedValue instances.
- B) To enforce API consistency and allow the JVM to manage instantiation, registration, and optimization of scoped value keys internally.
- C) Because it is an abstract class.
- D) To prevent subclassing.

*Answer*: **B**
- *Explanation*: Making constructors private and exposing `newInstance()` allows the JVM to control key creation and register them within internal scheduling maps, ensuring security boundaries and enabling cache optimizations.

#### Question 12: Checked Exceptions inside Carriers
What is the difference between executing a task via `Carrier.run()` vs `Carrier.call()`?
- A) `run()` supports returning values, while `call()` is void.
- B) `run()` accepts a `Runnable` (cannot return values or throw checked exceptions), whereas `call()` accepts a `Callable` (can return a value and propagate checked exceptions).
- C) `call()` runs asynchronously, while `run()` runs synchronously.
- D) There is no compiler-level difference.

*Answer*: **B**
- *Explanation*: The `Carrier` class exposes both methods to match execution requirements. `run(Runnable)` is for void, exception-free tasks, while `call(Callable)` allows tasks to return values and declare checked exceptions, which are bubbled up to the caller stack.

#### Question 13: Storing Mutable Objects in ScopedValues
A developer binds a `ScopedValue<List<String>>` containing a mutable `ArrayList`. What is the architectural risk?
- A) The JVM throws a compiler error.
- B) Although the ScopedValue reference is immutable, the list itself is mutable. Downstream layers can call `list.add()`, mutating the shared state and breaking thread-safety assumptions.
- C) The list is automatically cleared when accessed.
- D) None of the above.

*Answer*: **B**
- *Explanation*: Scoped Values only enforce reference immutability. If the bound object is internally mutable (like a standard `ArrayList`), downstream code can mutate the object's fields. To guarantee safety, developers should bind immutable collections (e.g. `List.copyOf()`).

#### Question 14: Null Values in ScopedValue.where()
What happens if you execute `ScopedValue.where(KEY, null).run(task)`?
- A) The JVM throws a `NullPointerException` at the `where()` call site.
- B) It binds `null` successfully. When the task calls `KEY.get()`, it returns `null`.
- C) It is equivalent to leaving the key unbound.
- D) The program fails to compile.

*Answer*: **B**
- *Explanation*: Binding a `null` value is permitted. When the task calls `KEY.get()`, it returns `null` instead of throwing a `NoSuchElementException`. However, passing a null *key* to `where()` throws a `NullPointerException`.

#### Question 15: Tracing Context in Production
When integrating tracing contexts (like OpenTelemetry SpanContext) via Scoped Values, what is the primary benefit over ThreadLocal in high-load microservices?
- A) ThreadLocal variables do not support tracing.
- B) Virtual threads executing subtasks inherit the tracing ID pointer link with zero copy overhead, preventing memory allocation spikes under heavy parallel fan-outs.
- C) Scoped Values automatically publish logs to remote servers.
- D) None of the above.

*Answer*: **B**
- *Explanation*: Large-scale microservices fan out processing to multiple parallel subtasks. Sharing trace spans via `InheritableThreadLocal` duplicates maps for thousands of virtual threads, increasing memory allocation. Scoped Values propagate the tracing pointer link with zero copy overhead.

#### Question 16: ScopedValue vs ThreadLocal GC Root Tracing
How does the Garbage Collector trace GC roots for objects stored inside `ScopedValue` bindings compared to those inside `ThreadLocal`?
- A. ScopedValue bindings are stored in off-heap native memory buffers which are not tracked by GC.
- B. For `ThreadLocal`, the values remain pinned as long as the Thread object is alive, even if the key is collected. For `ScopedValue`, the bindings are represented as a chain of stack nodes whose GC root path is cut the moment the carrier scope block exits, making the value objects instantly eligible for garbage collection.
- C. ScopedValues require calling `System.gc()` after every method.
- D. There is no difference in GC root tracing.

*Answer*: **B**
- *Explanation*: ThreadLocalMap entry values are strongly referenced by active threads, maintaining a strong GC root path that causes leaks in pools if not manually cleared. ScopedValue bindings are managed via dynamic pointer heads on the thread stack. Once the bounded block returns, the pointer head resets to the previous list state, cutting the reference to the snapshot node. The value is immediately collected if no other references exist.

#### Question 17: ScopedValue Rebinding/Shadowing Performance
Why does nested rebinding/shadowing of a `ScopedValue` (`ScopedValue.where(KEY, childValue)`) run in $O(1)$ time, bypassing the memory overhead associated with modifying traditional thread-local maps?
- A. The JVM bypasses compilation for nested rebindings.
- B. Rebinding does not query, resize, or clean up an internal map. It simply allocates a single lightweight node on the thread stack that holds the child value and points to the parent node, completing in constant time without modifying prior values.
- C. Shadowing is compiled as a static final class.
- D. None of the above.

*Answer*: **B**
- *Explanation*: In ThreadLocal, modifying a value requires walking a map table array, resolving collisions, and cleaning stale weak entries. ScopedValue rebinding is a simple stack push: the JVM allocates a single stack-bound snapshot node containing the key and new value, pointing back to the parent head. No maps are resized or cleared, ensuring high performance.

#### Question 18: Garbage Collection of Bound Values after Scope Exits
When a virtual thread exits a bound scope that stored a large database configuration payload, what JVM state transition ensures that the payload is eligible for garbage collection?
- A. The executor executes a manual garbage collection sweep.
- B. The thread's internal `scopedValueBindings` pointer is updated to the parent frame, removing the only reference pathway to the snapshot node containing the payload.
- C. The payload is overwritten with zero bytes.
- D. The thread group terminates.

*Answer*: **B**
- *Explanation*: ScopedValue bindings are tracked using list snapshot nodes. When the execution scope exits, the JVM restores the thread's internal `scopedValueBindings` head pointer to the previous list state. The snapshot node containing the payload reference is unlinked. Since it has no references, the payload becomes eligible for garbage collection.

#### Question 19: Interoperability of ScopedValue with ThreadLocal Logging Contexts (MDC)
Many standard enterprise logging frameworks (like Logback or Log4j2) use `ThreadLocal` variables for Mapped Diagnostic Context (MDC) propagation. When migrating to Scoped Values, how should developers bridge the context to the logging framework?
- A) They must rewrite the logging library framework from scratch.
- B) They should capture the ScopedValue context at the request entry boundary, write the parameters to the MDC map before execution, and ensure they clear the MDC keys inside a `finally` block to prevent leaks.
- C) Logging frameworks do not run inside virtual threads.
- D) MDC is automatically converted to ScopedValues by the JVM compiler.

*Answer*: **B**
- *Explanation*: MDC relies on ThreadLocal variables. When using Scoped Values for business context, you must copy values to MDC at thread boundaries:
  ```java
  ScopedValue.where(TRACE_ID, "TX-100").run(() -> {
      MDC.put("traceId", TRACE_ID.get());
      try {
          logger.info("Processing task...");
      } finally {
          MDC.remove("traceId");
      }
  });
  ```
  This guarantees that MDC logs contain the correct tracing IDs while maintaining leak-free cleanup.

#### Question 20: JFR Profiling Events for ScopedValue Context Mapping
When profiling a high-concurrency microservice under high load, which JFR event can be traced to monitor ScopedValue bindings?
- A. `jdk.ThreadPark`
- B. `jdk.ScopedValueBind` or custom JFR instrumentation events tracking binding allocations on the heap.
- C. `jdk.VirtualThreadPinned`
- D. `jdk.ThreadLocalMapResize`

*Answer*: **B**
- *Explanation*: The JVM profiles ScopedValue performance using internal metrics and custom event hooks. Monitoring these events helps identify excessive binding allocations or deep lookup traversal paths in complex execution trees.

---

## 14. Design Patterns for Context Sharing: When to use Scoped Values, ThreadLocals, and Method Parameters

When building applications, developers often need to propagate metadata (such as roles, transactions, or tracing IDs) from the entry point down to the database layer.

There are three main design patterns for context sharing in Java.

#### Pattern 1: Explicit Parameter Passing
In this pattern, context is passed as an argument to every method in the call stack.

##### Code Example:
```java
public class OrderService {
    public void processOrder(Long orderId, SecurityContext context) {
        validateOrder(orderId, context);
        saveToDatabase(orderId, context);
    }

    private void validateOrder(Long orderId, SecurityContext context) {
        if (!context.hasRole("USER")) {
            throw new SecurityException("Unauthorized");
        }
    }

    private void saveToDatabase(Long orderId, SecurityContext context) {
        System.out.println("Saving order " + orderId + " by user " + context.getUserName());
    }
}
```

* **Pros**:
  - **Type Safety and Transparency**: It is clear what dependencies a method has.
  - **Easy Testing**: You can test methods in isolation by passing arguments, without setting up thread states.
  - **No Magic**: No reflection, thread-bound maps, or special JVM features are needed.
* **Cons**:
  - **Parameter Pollution**: Every method in the stack must declare the parameter, even if it only passes it down. This leads to cluttered method signatures.

---

#### Pattern 2: ThreadLocal (Mutable & Persistent)
In this pattern, context is stored in a thread-bound map, letting methods retrieve it implicitly.

##### Code Example:
```java
public class SecurityContextHolder {
    private static final ThreadLocal<String> USERNAME = new ThreadLocal<>();

    public static void setUsername(String user) { USERNAME.set(user); }
    public static String getUsername() { return USERNAME.get(); }
    public static void clear() { USERNAME.remove(); }
}
```

* **Pros**:
  - **Clean Signatures**: Method signatures focus only on business parameters.
  - **Mutability**: The context can be updated at any point during execution.
* **Cons**:
  - **Memory Leaks**: If you do not call `clear()` in a `finally` block, data remains in the thread, causing leaks in pools.
  - **Virtual Thread Overhead**: Allocating maps for millions of virtual threads consumes too much memory.

---

#### Pattern 3: ScopedValue (Immutable & Lexically-Scoped)
This pattern binds read-only context to the execution scope of a method block.

##### Code Example:
```java
public class ScopedSecurityHolder {
    public static final ScopedValue<String> USERNAME = ScopedValue.newInstance();

    public void processRequest(String user) {
        ScopedValue.where(USERNAME, user).run(() -> {
            executeBusinessLogic();
        });
    }

    private void executeBusinessLogic() {
        System.out.println("Processing for user: " + USERNAME.get());
    }
}
```

* **Pros**:
  - **Automatic Safety**: Cleaned up automatically when the block exits, preventing leaks.
  - **Zero-Copy Inheritance**: Inherited by structured subtasks without copying maps.
  - **Memory Efficiency**: Stored as stack pointers, optimized for virtual threads.
* **Cons**:
  - **Immutability**: Values are read-only; updating a value requires nesting another scope (shadowing).
  - **Access Restrictions**: Reading outside the dynamic scope throws a `NoSuchElementException`.

---

#### Side-by-Side Comparison

| Feature | Parameter Passing | ThreadLocal | ScopedValue |
| :--- | :--- | :--- | :--- |
| **Method Signatures** | Cluttered (Polluted) | Clean | Clean |
| **Mutability** | Mutable | Mutable | Immutable |
| **Lifecycle Scope** | Explicit (Compile-time) | Unbounded (Leaky) | Lexical (Bound to block) |
| **Memory Footprint** | Near-zero | High (Map per thread) | Near-zero (Stack pointer) |
| **Loom Compatibility** | Excellent | Poor (Scalability barrier) | Excellent (Optimized) |
| **Structured Concurrency**| Explicit propagation | Expensive map copy | Zero-copy pointer sharing |

#### Decision Matrix: Which Pattern to Choose?
- Choose **Parameter Passing** for simple, shallow call stacks where only one or two components need the data.
- Choose **ScopedValue** for cross-cutting request metadata (like tracing IDs or credentials) that must propagate deeply down service stacks without cluttering signatures, especially on virtual threads.
- Choose **ThreadLocal** only if you genuinely need mutable, thread-confined state that must be updated dynamically within the thread lifecycle (such as transaction state managers).

---

## 15. Scoped Values under the Microscope: How JIT Compiler Escape Analysis optimizes bindings

While Scoped Values provide API benefits, their implementation is optimized by the JVM's **Just-In-Time (JIT) Compiler** to ensure near-zero runtime overhead.

The JIT compiler optimizes the execution paths of scoped value binding scopes:

#### 1. Escape Analysis (EA)
When you run a binding block:
```java
ScopedValue.where(TRACE_ID, "TX-100").run(() -> {
    executeTask();
});
```
The compiler analyzes the lambda runnable and the `ScopedValue.Carrier` instance. During compilation, the JIT runs **Escape Analysis**:
- It analyzes the scope of the `Carrier` object and the lambda.
- Since the lambda only runs within the `run()` method and is not assigned to a field or returned, the JIT detects that these objects **do not escape the compiling thread stack**.

#### 2. Scalar Replacement
Once Escape Analysis proves the carrier and closure objects do not escape the stack, the JIT compiler applies **Scalar Replacement**:
- The JVM decomposes the carrier object into its individual fields.
- Instead of allocating the `Carrier` object on the heap, the fields are placed directly in CPU registers or on the stack.
- This eliminates heap allocation overhead. The garbage collector never has to scan or clean up these short-lived objects.

#### 3. Lock Elimination
In traditional `ThreadLocalMap` lookups, threads must synchronize or run CAS operations when resizing maps or resolving collisions.
Because Scoped Values are immutable and stack-bound, lookups use simple stack traversal. The JIT compiler detects that no concurrent modifications are possible, and eliminates internal lock or barrier instructions, compiling lookups down to direct memory reads.

#### 4. Method Inlining
When calling `TRACE_ID.get()`, the JIT compiler attempts to **inline** the method:
- It replaces the method call with the actual body of the lookup logic.
- If the scope depth is constant, the compiler flattens the pointer dereferencing sequence.
- This reduces the lookup to a direct offset memory read, making scoped value lookups run at the speed of standard local variable reads.

This combination of stack-based design and JIT optimization makes Scoped Values extremely efficient, letting Java applications handle millions of context mappings with zero garbage collection overhead.
