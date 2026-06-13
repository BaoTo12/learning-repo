# Module 07: Virtual Threads vs Reactive Programming

## 1. What Problem This Module Solves
To build scalable high-throughput applications, engineers must select the right concurrency paradigm:
*   **The Complexity of Reactive Streams**: Reactive programming (Project Reactor, RxJava) scales well but introduces cognitive complexity, "callback hell", and makes stack traces unreadable.
*   **Thread Blockage Performance Costs**: Traditional blocking systems freeze threads during I/O operations, consuming memory and CPU.

This module compares the **Event-Loop Reactive** model and Project Loom's **Blocking Virtual Thread** model, detailing how each handles I/O, backpressure, and thread resources.

---

## 2. I/O Architectures: Event-Loop vs Virtual Threads

### 2.1 Reactive Event-Loop Model (Non-Blocking)
Relies on a small, fixed pool of event-loop threads (typically matching the CPU core count). 
*   **Mechanics**: A single event-loop thread registers I/O requests with the OS kernel (using selectors like `epoll` or `kqueue`) and immediately returns to process other tasks. When the I/O completes, the OS notifies the thread, which executes the corresponding callback.
*   **Throughput**: High. However, executing blocking operations (e.g. database access) on an event-loop thread freezes the loop, stalling the entire application.

```
[ Reactive Event-Loop ]
Requests ──► [ Event Loop Thread ] ──► Registers socket read (epoll) ──► Returns immediately
                                                 ▲
                                                 │ (OS notifies when bytes arrive)
                                           Executes callback
```

### 2.2 Project Loom Model (Blocking Virtual Threads)
Allows writing standard, blocking code. 
*   **Mechanics**: When a virtual thread executes a blocking I/O operation (e.g., `InputStream.read()`), the JVM intercepts the call, saves the virtual thread's stack frames back to the heap, and unmounts it from the carrier thread. The carrier thread remains free to run other tasks.
*   **Throughput**: Equivalent to the reactive model, while allowing developers to write simple, sequential code.

```
[ Virtual Threads ]
Virtual Thread ──► Executes blocking read() ──► JVM saves stack to Heap & unmounts ──► Carrier Thread free
```

---

## 3. Backpressure: Reactive Streams vs Virtual Threads

**Backpressure** is the mechanism that allows a data consumer to regulate the data emission rate of a producer to prevent memory bloat.

### 3.1 Reactive Backpressure (Pull Model)
Enforced using reactive streams interfaces (`Subscription.request(n)`). The consumer explicitly requests $N$ items from the publisher. The publisher only emits up to $N$ items, preventing memory bloat but requiring complex tracking code.

### 3.2 Virtual Thread Backpressure (Blocking Model)
Virtual threads use standard, blocking code structures (like `SynchronousQueue` or `ArrayBlockingQueue`). If the consumer is slow, the producer blocks on the queue write operation. The JVM automatically unmounts the blocked producer thread, preserving system resources.

---

## 4. Architectural Decision Guide: Loom vs WebFlux

| Metric / Scenario | Reactive (WebFlux) | Virtual Threads (Loom) |
| :--- | :--- | :--- |
| **Code Readability** | Low (Functional chaining, callback wrappers) | High (Standard procedural Java) |
| **Debugging & Profiling** | Difficult (Stack traces lose thread context) | Simple (Standard JVM stack traces and thread dumps) |
| **Downstream Blocking I/O** | Anti-Pattern (requires separate elastic pools) | Supported (automatically unmounts carrier threads) |
| **Existing Libraries Integration** | Hard (requires custom reactive drivers) | Seamless (compatible with existing JDBC/HTTP drivers) |
| **Ideal Workload** | High event-rate streaming, UI events | Standard REST APIs, database processing, microservices |

---

## 5. Common Mistakes and Anti-Patterns
*   **Assuming Virtual Threads eliminate Reactive benefits**: Replacing reactive frameworks with virtual threads in all scenarios. Reactive programming remains optimal for event-driven systems (like WebSockets, streaming analytics, or UI event handlers) that require continuous push event streams.
*   **Executing blocking code on WebFlux loops**: Mixing virtual threads with WebFlux without configuring separate execution schedulers.

---

## 6. Interview Questions

### Q1: How does backpressure propagation differ between Project Reactor (Reactive Streams) and Project Loom (Virtual Threads)?
**Answer**: 
*   **Project Reactor**: Uses a push-subscription model. The subscriber sends demand requests (`Subscription.request(n)`) upstream. The publisher only emits up to $N$ items, regulating flow at the application logic layer.
*   **Project Loom**: Uses standard, blocking Java structures. If the consumer is slow, the queue buffer fills up. When the queue is full, the producer blocks on `BlockingQueue.put()`. The JVM unmounts the blocked virtual thread, pausing the producer until the consumer reads from the queue, propagating backpressure naturally using thread blocking.

### Q2: Why is debugging and profiling reactive code significantly harder than debugging virtual thread applications?
**Answer**: 
In reactive programming, the thread initiating a task is often not the thread that executes the callbacks. When an exception occurs, the JVM stack trace only shows the execution history of the active callback thread, losing the parent context and making troubleshooting difficult.
Virtual threads are managed directly by the JVM. The JVM maintains a continuous execution context for the virtual thread. When an exception occurs, the stack trace represents the complete, sequential execution history of the virtual thread, identical to traditional platform thread dumps.
