# Module 04: ForkJoinPool & Continuation Mechanics

## 1. What Problem This Module Solves
To build high-performance concurrent systems, a senior engineer must understand how thread scheduling works under the hood:
*   **The OS Thread Scheduler Black-Box**: Operating system schedulers are optimized for general-purpose workloads, not specifically for high-throughput I/O-bound Java applications.
*   **Decoupling Execution Contexts**: Decoupling the execution state of a thread (its local variables, call stack) from the physical CPU execution thread requires a mechanism to suspend and resume code execution.

This module explains how the **ForkJoinPool** schedules virtual threads, details the theory of **Continuations**, and guides you through building custom virtual threads (NanoThreads) from scratch.

---

## 2. The ForkJoinPool Scheduler

Virtual threads are not scheduled by the operating system kernel. Instead, they are scheduled by the JVM using a **ForkJoinPool** carrier thread pool:

*   **FIFO Scheduling**: The carrier pool runs in First-In-First-Out (FIFO) mode.
*   **Work-Stealing**: Carrier threads execute virtual thread tasks. If a carrier thread runs out of tasks, it steals unmounted virtual threads from other carrier queues.
*   **Sizing**: By default, the carrier pool is sized to match the number of logical processors (`Runtime.getRuntime().availableProcessors()`).

---

## 3. Continuation Theory: Yielding and Resuming

A **Continuation** is a programming abstraction representing a execution state that can be suspended and resumed. It decouples code execution from physical CPU threads.

```
[ Start Execution ] ──► Executes statements...
                             │
                             ▼ (Hits yield point)
                        [ Continuation.yield() ] ──► (Saves execution stack, returns control)
                             │
                             ▼ (Scheduler resumes continuation)
[ Resume Execution ] ◄── Restores call stack and runs next statements
```

*   **Yielding**: Suspending execution at a specific point, saving the stack frames (call pointers, local variables) in heap memory, and returning control to the scheduler.
*   **Resuming**: Restoring the saved stack frames from heap memory to an execution thread and resuming execution from the yield point.

---

## 4. Mini-Project: Building Custom Virtual Threads (NanoThreads) From Scratch

To understand how Project Loom schedules threads, we can implement a custom `NanoThread` using a task runner and scheduler simulation:

### Custom NanoThread Implementation (`NanoThread.java`)
```java
package com.example.concurrency.mechanics;

import java.util.Queue;
import java.util.concurrent.*;

public class NanoThread {

    // Simple Scheduler queue
    private static final Queue<NanoTask> RUN_QUEUE = new ConcurrentLinkedQueue<>();
    private static final ExecutorService CARRIER_POOL = Executors.newFixedThreadPool(2);

    public static class NanoTask {
        private final String name;
        private final Runnable runnable;
        private int step = 0; // Simulated instruction pointer

        public NanoTask(String name, Runnable runnable) {
            this.name = name;
            this.runnable = runnable;
        }

        public void run() {
            System.out.printf("[%s] Running %s - Step %d\n", Thread.currentThread().getName(), name, step);
            
            // Execute task step logic
            runnable.run();
            step++;
            
            if (step < 3) {
                // Yield execution: enqueue task back to the run queue
                System.out.printf(" - %s is yielding...\n", name);
                RUN_QUEUE.add(this);
            } else {
                System.out.printf(" - %s has finished execution.\n", name);
            }
        }
    }

    public static void startNanoThread(String name, Runnable runnable) {
        RUN_QUEUE.add(new NanoTask(name, runnable));
    }

    public static void startScheduler() throws InterruptedException {
        // Simple loop scheduler executing tasks on carrier threads
        while (!RUN_QUEUE.isEmpty()) {
            NanoTask task = RUN_QUEUE.poll();
            if (task != null) {
                CARRIER_POOL.submit(task::run);
            }
            Thread.sleep(100); // Simulate scheduling cycles
        }
        
        CARRIER_POOL.shutdown();
        CARRIER_POOL.awaitTermination(5, TimeUnit.SECONDS);
    }

    public static void main(String[] args) throws Exception {
        System.out.println("Initializing NanoThread simulation...");
        
        startNanoThread("NanoThread-A", () -> System.out.println("   (Executing calculation)"));
        startNanoThread("NanoThread-B", () -> System.out.println("   (Reading network packet)"));

        startScheduler();
    }
}
```

---

## 5. Common Mistakes and Anti-Patterns
*   **Creating Custom Schedulers**: Attempting to override Loom's default carrier scheduler in production. Loom's `ForkJoinPool` is tuned for virtual thread workloads; custom schedulers can easily degrade performance.
*   **Assuming Thread Pools solve thread blocking**: Expecting traditional thread pools to optimize blocking operations. Thread pools recycle OS threads but do not prevent them from blocking during I/O operations.

---

## 6. Interview Questions

### Q1: What is a Continuation, and how does the JVM use it to implement virtual threads?
**Answer**: 
*   **Continuation**: An object that represents the execution state of a program (its local variables, call stack, instruction pointer) which can be suspended (yielded) and resumed at a later time.
*   **JVM Integration**: When a virtual thread executes a blocking operation, the JVM invokes the continuation's `yield()` method under the hood. This suspends execution, saves the virtual thread's stack frames back to the heap, and releases the carrier thread. When the I/O completes, the JVM invokes the continuation's `run()` method to restore the stack frames and resume execution from the yield point.

### Q2: Why is the `ForkJoinPool` carrier scheduler configured to run in FIFO (First-In-First-Out) mode, while traditional ForkJoinPools default to LIFO (Last-In-First-Out)?
**Answer**: 
*   **Traditional ForkJoinPool (LIFO)**: Optimized for divide-and-conquer tasks (like quicksort). LIFO minimizes cache misses by executing the most recently split task first, which is likely already cached in the CPU registers.
*   **Loom Scheduler (FIFO)**: Optimized for transaction-oriented, asynchronous I/O workloads. FIFO ensures fair scheduling by executing the oldest unblocked virtual thread task first, preventing task starvation.
