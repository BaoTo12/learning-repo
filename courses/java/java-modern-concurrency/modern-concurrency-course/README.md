# Modern Concurrency in Java: Virtual Threads & Structured Concurrency

Welcome to the **Modern Concurrency in Java: Virtual Threads & Structured Concurrency** course. This repository contains a comprehensive, production-focused syllabus designed for senior software engineers, platform architects, and Java developers who build, optimize, and operate high-scale concurrent systems on modern JVM platforms.

This course is based on *Modern Concurrency in Java Virtual Threads, Structured*. It covers the transition from platform threads, under-the-hood carrier thread scheduling, synchronized pinning anomalies, continuation mechanics, StructuredTaskScope joining policies, Scoped Values context propagation, and comparisons with Reactive Streams.

---

## 🎯 Course Objectives

By the end of this course, you will be able to:
1. **Analyze Platform Thread Costs**: Understand OS 1-to-1 thread limitations, memory page overhead, and pool-context switching bottlenecks.
2. **Deploy Virtual Threads**: Configure and spawn virtual threads dynamically using Java 21 factories.
3. **Debug Thread Pinning**: Detect carrier thread pinning inside synchronized blocks and native calls.
4. **Implement ReentrantLock Migrations**: Refactor code to replace synchronized blocks with `ReentrantLock` to prevent pinning.
5. **Mitigate ThreadLocal Risks**: Trace ThreadLocal memory footprint leaks and performance risks.
6. **Master Continuation Mechanics**: Understand low-level scheduling yields and build simple virtual threads from scratch.
7. **Code Structured Concurrency**: Implement `StructuredTaskScope` scopes, handling subtask lifecycles and cancel cascades.
8. **Enforce Scoped Values**: Use the `ScopedValue` API for immutable, lightweight context sharing across threads.
9. **Contrast Virtual Threads vs Reactive**: Evaluate blocking I/O vs event-loops and determine when to use Loom vs Project Reactor.
10. **Integrate Spring Boot 3.x**: Enable and optimize virtual thread executors in Spring Boot and JTA/Tomcat pools.

---

## 📚 Structured Syllabus & Modules

The curriculum consists of 8 comprehensive, technical modules:

| Module | Topic | File Link |
| :--- | :--- | :--- |
| **01** | Evolution of Concurrency & Platform Thread Limitations | [01-concurrency-evolution.md](./modules/01-concurrency-evolution.md) |
| **02** | Virtual Threads, Pinning, and ThreadLocal | [02-understanding-virtual-threads.md](./modules/02-understanding-virtual-threads.md) |
| **03** | The Mechanics of Modern Concurrency | [03-mechanics-of-modern-concurrency.md](./modules/03-mechanics-of-modern-concurrency.md) |
| **04** | Structured Concurrency & StructuredTaskScope | [04-structured-concurrency.md](./modules/04-structured-concurrency.md) |
| **05** | Context Propagation via Scoped Values | [05-scoped-values.md](./modules/05-scoped-values.md) |
| **06** | Virtual Threads vs Reactive Programming | [06-reactive-vs-virtual-threads.md](./modules/06-reactive-vs-virtual-threads.md) |
| **07** | Modern Framework Integrations & Best Practices | [07-framework-integrations.md](./modules/07-framework-integrations.md) |
| **08** | Conclusion and Takeaways | [08-conclusion-takeaways.md](./modules/08-conclusion-takeaways.md) |


---

## 🛠️ Prerequisites & Local Execution Setup

To run the labs, compile code, and test Project Loom features, you will need **Java 21+**.

Verify your local Java environment:
```bash
java --version
# Should output openjdk 21 or later
```

Some preview features (like Structured Concurrency and Scoped Values) might require enabling preview flags during compile and execution:
```bash
javac --enable-preview --release 21 MyClass.java
java --enable-preview MyClass
```

---

## 📈 Graduation & System Assessment Rubrics

Assessments will evaluate projects across four dimensions:

### 1. Virtual Thread Deployment & Rate Limiting (25% Weight)
*   **Virtual Thread Setup**: Correct use of `Executors.newVirtualThreadPerTaskExecutor()`.
*   **Rate Limiting**: Proper use of `Semaphore` or `ReentrantLock` to protect external services instead of traditional pool boundaries.

### 2. Thread Pinning Mitigation & Monitoring (25% Weight)
*   **Pinning Prevention**: Successful refactoring of synchronized blocks to `ReentrantLock` in critical paths.
*   **Observability**: Monitoring pinning using JVM command line flags (`-Djdk.tracePinnedThreads`).

### 3. Structured Concurrency & Task Joining (25% Weight)
*   **Scope Lifecycle**: Correct implementation of `StructuredTaskScope` with appropriate joining policies (`ShutdownOnSuccess`, `ShutdownOnFailure`).
*   **Cancel Cascades**: Handling exception propagation and cancelling orphaned subtasks.

### 4. Scoped Values Context Sharing (25% Weight)
*   **Context Propagation**: Proper use of `ScopedValue` to share thread contexts across subtasks, replacing mutable `ThreadLocal` variables.
*   **Performance Sizing**: Correct thread context lifecycle management avoiding memory leaks.
