# Module 02: Virtual Threads Concept & Lifecycle

## 1. What Problem This Module Solves
Modern scale demands asynchronous architectures, but writing asynchronous code introduces complexity:
*   **API Fragmentation**: Developers are forced to choose between simple blocking APIs (thread-per-request) that do not scale, or complex reactive programming models (RxJava, Reactor) that scale but are hard to write, read, and debug.
*   **The Synchronous Blocking Penalty**: When a platform thread performs a blocking I/O call, the OS kernel freezes the thread, wasting memory and CPU resources while the thread waits for the socket response.

Virtual threads resolve this by allowing you to write simple, blocking code that is executed asynchronously by the JVM under the hood.

---

## 2. Platform Threads vs Virtual Threads

*   **Platform Threads**: Map 1-to-1 to OS threads. Sized and scheduled by the operating system kernel. Reserved stack space is large (~1MB).
*   **Virtual Threads**: Managed by the JVM. Stored as ordinary objects in the JVM heap, requiring only a few hundred bytes of memory. Scheduled dynamically on top of a pool of carrier threads (which are platform threads).

---

## 3. Creating Virtual Threads in Java 21

Java 21 introduces three primary APIs to create and execute virtual threads:

### 3.1 `Thread.startVirtualThread`
Spawns and starts a virtual thread immediately:
```java
Thread.startVirtualThread(() -> {
    System.out.println("Running inside a virtual thread: " + Thread.currentThread());
});
```

### 3.2 The Thread Builder (`Thread.ofVirtual()`)
Allows you to configure the virtual thread (e.g. setting names, registering unstarted threads):
```java
Thread.Builder builder = Thread.ofVirtual().name("worker-", 1);
Thread t = builder.unstarted(() -> {
    System.out.println("Thread name: " + Thread.currentThread().getName());
});
t.start();
```

### 3.3 The Virtual Thread Executor
Replaces traditional fixed/cached thread pools for executing parallel I/O-bound tasks:
```java
try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
    executor.submit(() -> {
        // Execute I/O operation
    });
} // Automatically terminates and shuts down the executor
```

---

## 4. How Virtual Threads Work Under the Hood

When a virtual thread executes a blocking operation:

```
[ Virtual Thread Active ] (Mounted on Carrier Thread)
           │
           ▼ (Executes blocking I/O, e.g., Socket read)
[ JVM Scheduler (ForkJoinPool) ] ───(Saves call stack to Heap & Unmounts)───► [ Carrier Thread Free ]
                                                                                   │
[ Socket I/O Completes ] ◄──────────(JVM mounts stack and schedules)───────────────┘
```

1.  **Mounting**: The JVM scheduler selects an available carrier thread and mounts the virtual thread onto it. The virtual thread's stack frames are copied from the JVM heap to the carrier thread's stack.
2.  **Unmounting**: When the virtual thread hits a blocking operation, the JVM intercepts the call, saves the virtual thread's stack frames back to the JVM heap, and unmounts it from the carrier thread, freeing the carrier thread to execute other virtual threads.
3.  **Resuming**: When the I/O operation completes, the JVM schedules the virtual thread to resume, copying its stack frames back to an available carrier thread.

---

## 5. Rate Limiting with Semaphores

In traditional concurrency, thread pool limits are used to restrict concurrent access to external APIs or databases. 

With virtual threads, this approach is an anti-pattern: virtual threads are cheap and should not be pooled. To restrict concurrent access when using virtual threads, use a **Semaphore**:

```java
package com.example.concurrency.virtual;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;

public class ResourceRateLimiter {

    // Limit concurrent requests to a maximum of 5 to protect downstream services
    private final Semaphore semaphore = new Semaphore(5);

    public void callDownstreamService() {
        try {
            // Acquire permit. If no permits are available, the virtual thread blocks
            // and is unmounted from the carrier thread, conserving CPU resources.
            semaphore.acquire();
            executeHttpCall();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            semaphore.release(); // Release permit
        }
    }

    private void executeHttpCall() {
        System.out.println("Querying API... " + Thread.currentThread());
        try {
            Thread.sleep(100); // Simulate network latency
        } catch (InterruptedException ignored) {}
    }

    public static void main(String[] args) throws Exception {
        ResourceRateLimiter limiter = new ResourceRateLimiter();
        
        // Spawn 100 concurrent tasks using virtual threads
        try (ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int i = 0; i < 100; i++) {
                executor.submit(limiter::callDownstreamService);
            }
        }
    }
}
```

---

## 6. Common Mistakes and Anti-Patterns
*   **Pooling Virtual Threads**: Wrapping a virtual thread executor inside a pool structure. This is unnecessary; virtual threads are lightweight and should be created on-demand and discarded after use.
*   **Using Virtual Threads for CPU-bound tasks**: Attempting to speed up CPU-intensive calculations (like cryptography or matrix multiplication) using virtual threads. Virtual threads do not optimize CPU-bound tasks, as these tasks require continuous CPU core allocation and cannot be unmounted.

---

## 7. Interview Questions

### Q1: What happens under the hood when a virtual thread encounters a blocking method call like `Thread.sleep()` or a socket read?
**Answer**: 
When a virtual thread executes a blocking method, the JVM intercepts the call at the JDK level (virtual-thread-friendly classes like `NioSocketImpl`). 
The JVM saves the virtual thread's stack frames back to the JVM heap, and unmounts the virtual thread from its carrier thread. The carrier thread is released to execute other virtual threads. When the blocking operation completes, the JVM scheduler mounts the virtual thread's stack frames back onto an available carrier thread to resume execution.

### Q2: Why is pooling virtual threads using a fixed thread pool an anti-pattern? How should you limit concurrent requests instead?
**Answer**: 
*   **Why it's an anti-pattern**: Thread pooling was created to reduce the overhead of creating expensive platform threads. Virtual threads are cheap, ordinary Java objects managed by the JVM heap. Pooling them adds unnecessary complexity.
*   **The Solution**: Create virtual threads on-demand using `Executors.newVirtualThreadPerTaskExecutor()`. To limit concurrent requests and protect downstream resources, use a **Semaphore** or `ReentrantLock` inside the task execution logic.
