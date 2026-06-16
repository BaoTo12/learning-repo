# Module 02: Thread Pool Management & Virtual Threads

Welcome back class. Today we analyze **Thread Pool Management & Virtual Threads (CS-528)**.

While reactive non-blocking frameworks (like WebFlux) solve network socket blocking bottlenecks, backend workflows often require executing synchronous, CPU-bound operations (such as processing numeric arrays, verifying cryptographic hashes, or coordinating operating system subprocesses). If these operations run on the main application thread pool, they lock the threads. In traditional Java, OS thread allocations are expensive. Under heavy traffic, this leads to complete thread pool exhaustion.

Today we study **Java 21 Virtual Threads (Project Loom)**, analyze the differences between platform and virtual threads, identify carrier thread pinning pitfalls, and configure a virtual-task executor in **Spring Boot 3.x**.

---

## 1. Academic Lecture: Platform Threads vs. Virtual Threads

### 1. The Limitation of Platform Threads
In Java, a platform thread (`java.lang.Thread`) is a thin wrapper around an operating system kernel thread.
*   **Memory Footprint**: Each platform thread reserves a fixed stack size (typically 1 Megabyte) directly in system memory. Allocating 1,000 threads consumes 1 Gigabyte of RAM regardless of whether they are working or sleeping.
*   **Context Switching Overhead**: When the OS switches CPU core execution from one thread to another, it must store registers, update memory maps, and clean cache lines, which degrades CPU throughput.

### 2. The Mechanics of Virtual Threads (Project Loom)
Java 21 introduces **Virtual Threads**—lightweight, user-mode threads managed by the Java Virtual Machine rather than the operating system.
*   **Carrier Threads**: The JVM maintains a pool of platform threads (typically matching the CPU core count) called **Carrier Threads** (backed by a ForkJoinPool).
*   **Mounting and Unmounting**: When a virtual thread executes, the JVM mounts it onto an active Carrier Thread. When the virtual thread performs a blocking operation (such as a database query, file write, or subprocess wait):
    1.  The JVM captures the blocking call.
    2.  It unmounts the virtual thread, copying its stack context to the heap.
    3.  The Carrier Thread becomes free to run other virtual threads.
    4.  Once the blocking operation completes, the JVM schedules the virtual thread to mount back onto an available Carrier Thread and resume execution.

### 3. The Carrier Pinning Pitfall
If a virtual thread performs a blocking operation while executing inside a `synchronized` block, or inside a native C-library wrapper call (JNI), the virtual thread becomes **pinned** to the carrier thread. The JVM cannot unmount it, which blocks the underlying platform thread and degrades concurrency.

```text
                  JVM User-Space Scheduler (ForkJoinPool)
                             ┌──────────────┐
                             │ Carrier Pool │ (Platform Threads)
                             └──────┬───────┘
                                    │ (Mounts)
                                    ▼
       [Virtual Thread 1] ──> Executing task...
                                    │
                       (Blocks on Database Query)
                                    │
                                    ▼ (Unmounts stack context to Heap)
       [Virtual Thread 1] ──> Idle on Heap
                                    │
                                    ▼ (Carrier Thread is released)
       [Virtual Thread 2] ──> Mounted on same Carrier Thread ──> Executing task...
```

---

## 2. Theory vs. Production Trade-offs

When managing concurrency models in Java 21, compare these threading strategies:

| Dimension / Metric | Platform Thread Pools (Fixed) | Cached Thread Pools | Virtual Threads (Project Loom) |
| :--- | :--- | :--- | :--- |
| **Max Concurrency** | Low (Limited by OS limits: ~500) | Moderate (Risks Out-of-Memory) | High (Millions of active tasks) |
| **Creation Cost** | High (Requires OS system call) | High (Requires OS system call) | Extremely Low (Simple Java object) |
| **Memory Cost** | High (1MB stack per thread) | High (1MB stack per thread) | Very Low (Bytes on JVM heap) |
| **Task Suitability** | CPU-bound computations | Variable workloads | I/O-bound blocking calls |
| **Thread Pooling** | Mandatory (Reuses threads) | Mandatory (Reuses threads) | **Anti-Pattern** (Discard after use) |

---

## 3. How to Use: Virtual Threads Task Executor

Let us write a compile-grade Java 21 Spring Configuration class that disables fixed platform thread executors and registers an task executor backed by Virtual Threads.

### A. The Constrained Platform Pool Pattern (Anti-Pattern)

Avoid configuring fixed thread pools for high-latency tasks. Once the thread count limit is hit, the application blocks incoming tasks:

```java
package com.security.api.config;

import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

public class NaiveThreadPoolConfig {
    // DANGER: Setting a fixed pool of 20 platform threads limits concurrency.
    // If 20 candidate audio processing processes are executing, the 21st task
    // is placed in a blocking queue, stalling the user experience.
    public Executor naiveExecutor() {
        return Executors.newFixedThreadPool(20); // VULNERABLE to thread exhaustion
    }
}
```

### B. The Hardened Virtual Thread Executor (Production Pattern)

Here is the hardened pattern. We configure a custom Spring `AsyncTaskExecutor` bean that spawns a new virtual thread per task, eliminating thread pooling constraints. We also write a service executing parallel tasks.

```java
package com.security.api.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.task.AsyncTaskExecutor;
import org.springframework.core.task.support.TaskExecutorAdapter;
import java.util.concurrent.Executors;

@Configuration
public class VirtualThreadConfig {

    @Bean(name = "applicationTaskExecutor")
    public AsyncTaskExecutor applicationTaskExecutor() {
        // Enforce new virtual thread creation per task
        // We use TaskExecutorAdapter to map Java's ThreadExecutor to Spring's AsyncTaskExecutor
        return new TaskExecutorAdapter(Executors.newVirtualThreadPerTaskExecutor());
    }
}
```

Now let us write the parallel coordinator service that queries Whisper and Ollama concurrently:

```java
package com.security.api.service;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.task.AsyncTaskExecutor;
import org.springframework.stereotype.Service;
import java.util.concurrent.CompletableFuture;

@Service
public class ParallelPipelineOrchestrator {

    private final AsyncTaskExecutor executor;
    private final MockModelClient mockModelClient;

    // Inject our virtual thread task executor
    public ParallelPipelineOrchestrator(
            @Qualifier("applicationTaskExecutor") AsyncTaskExecutor executor,
            MockModelClient mockModelClient) {
        this.executor = executor;
        this.mockModelClient = mockModelClient;
    }

    public CompletableFuture<PipelineResult> executeParallelInference(String audioPath, String queryPrompt) {
        // Step 1: Run Whisper STT in a virtual thread
        CompletableFuture<String> transcriptFuture = CompletableFuture.supplyAsync(
            () -> mockModelClient.runWhisperStt(audioPath), executor
        );

        // Step 2: Run Ollama prompt preprocessing in parallel
        CompletableFuture<String> promptFuture = CompletableFuture.supplyAsync(
            () -> mockModelClient.runPromptAnalysis(queryPrompt), executor
        );

        // Step 3: Combine outcomes asynchronously
        return transcriptFuture.thenCombineAsync(promptFuture, 
            (transcript, cleanPrompt) -> new PipelineResult(transcript, cleanPrompt), 
            executor
        );
    }

    // Static helper client representing slow backend processes
    @Service
    public static class MockModelClient {
        public String runWhisperStt(String path) {
            try { Thread.sleep(2000); } catch (InterruptedException e) {} // Simulate blocking I/O
            return "Parsed transcript text from: " + path;
        }

        public String runPromptAnalysis(String prompt) {
            try { Thread.sleep(1000); } catch (InterruptedException e) {}
            return "Analyzed prompt: " + prompt;
        }
    }

    public static record PipelineResult(String transcript, String promptDetails) {}
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Attempting to Pool Virtual Threads
Using `ThreadLocal` or implementing a pool structure to reuse virtual threads.
*   **Why it fails**: Virtual threads are designed to be extremely lightweight, short-lived objects. Creating a new virtual thread takes less than a microsecond. Pooling them creates memory overhead and introduces GC references, defeating their performance benefits.
*   **Mitigation**: Never pool virtual threads. Use `Executors.newVirtualThreadPerTaskExecutor()` which allocates a new thread for each task and discards it immediately upon completion.

### Pitfall 2: Pinning Carrier Threads via Synchronized Blocks
Executing slow blocking I/O calls inside a `synchronized` method block.
*   **Why it fails**: Java's virtual thread scheduler cannot unmount a thread if it is inside a `synchronized` block. The carrier thread remains pinned, blocking the platform execution pool.
*   **Mitigation**: Replace `synchronized` blocks with modern concurrency locks, such as `java.util.concurrent.locks.ReentrantLock`, which support unmounting.

---

## 5. Socratic Review Questions

### Question 1
Why is thread pooling necessary for platform threads but considered an anti-pattern for virtual threads?

#### Answer
Platform threads consume significant OS resources and stack memory (1MB each), making their creation and teardown latency-heavy and resource-intensive. Pooling allows reusing these expensive resources. Virtual threads are simple Java objects residing in the JVM heap, requiring only a few hundred bytes of memory. Creating a virtual thread is as cheap as allocating a new object instance, so pooling them introduces unnecessary overhead.

### Question 2
How does the JVM unmount a virtual thread when it encounters a blocking socket operation, and what happens to the execution stack?

#### Answer
When a virtual thread executes a blocking socket read, the JVM intercepts the call. It copies the virtual thread's stack frames from the carrier thread's system stack onto the JVM heap. The carrier thread's stack pointer is reset, freeing it to mount a different virtual thread. The blocking socket is registered with the JVM's network poller. When bytes arrive, the poller signals the scheduler to copy the stack frames back onto a carrier thread and resume execution.

---

## 6. Hands-on Challenge: Virtual Thread Parallel Task Runner

### The Challenge
In this challenge, you will implement a parallel task execution controller in Java.
Your task:
1. Complete the implementation of `runConcurrentTasks` inside `ParallelTaskRunner`.
2. Execute three tasks in parallel using the provided virtual thread `AsyncTaskExecutor`.
3. Block and wait for all tasks to complete with a timeout limit of 5 seconds.
4. Return the list of completed task result strings.

Complete the implementation below:

```java
package com.security.api;

import org.springframework.core.task.AsyncTaskExecutor;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ParallelTaskRunner {
    private final AsyncTaskExecutor executor;

    public ParallelTaskRunner(AsyncTaskExecutor executor) {
        this.executor = executor;
    }

    public List<String> runConcurrentTasks(List<RunnableTask> tasks) throws Exception {
        List<CompletableFuture<String>> futures = new ArrayList<>();

        // TODO: Implement the parallel execution:
        // 1. Loop through tasks.
        // 2. For each task, submit to the virtual thread executor:
        //    CompletableFuture.supplyAsync(task::execute, executor)
        // 3. Collect the resulting CompletableFuture objects into the futures list.
        // 4. Combine all futures using CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).
        // 5. Block execution until all complete, enforcing a timeout of 5 seconds:
        //    combinedFuture.get(5, TimeUnit.SECONDS).
        // 6. Loop through the completed futures to extract the results, add them to a list, and return it.

        return null;
    }

    public static interface RunnableTask {
        String execute();
    }
}
```

Write the parallel verifications. Save the completed file and verify that the virtual task runner handles timeouts correctly under `modules/02-thread-pools-virtual-threads.md`.
