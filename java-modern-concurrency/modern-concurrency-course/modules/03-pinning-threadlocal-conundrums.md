# Module 03: Thread Pinning & ThreadLocal Conundrums

## 1. What Problem This Module Solves
While virtual threads scale application throughput, they introduce distinct concurrency pitfalls:
*   **Carrier Thread Starvation (Pinning)**: If a virtual thread blocks while running inside a `synchronized` block, the JVM cannot unmount it. The underlying carrier thread remains blocked, which can lead to application starvation.
*   **ThreadLocal Memory Bloat**: In traditional architectures, `ThreadLocal` variables are used to share context. If millions of virtual threads allocate large `ThreadLocal` maps, the JVM heap will quickly exhaust, causing Out-of-Memory (OOM) errors.

This module explains carrier thread pinning, details `ThreadLocal` memory risks, and demonstrates how to monitor and resolve these issues in production.

---

## 2. Carrier Thread Pinning

**Pinning** occurs when a virtual thread is locked to its carrier thread. When pinned, the virtual thread cannot be unmounted during blocking operations, forcing the underlying platform thread to block.

```
[ Pinned State ]
Virtual Thread A (Inside synchronized block) ──(Blocks on I/O)──► Carrier Thread blocks
* The JVM cannot unmount Virtual Thread A.
* The carrier thread is frozen, preventing it from executing other tasks.
```

### 2.1 Causes of Pinning
1.  **Executing code inside a `synchronized` block or method**.
2.  **Executing native methods or foreign function calls (JNI/FFI)**.

---

## 3. Resolving Pinning with `ReentrantLock`

To prevent pinning, replace `synchronized` blocks in your critical paths with `java.util.concurrent.locks.ReentrantLock`. Unlike `synchronized`, `ReentrantLock` allows the JVM to unmount the virtual thread during blocking operations.

### 3.1 Synchronized (Triggers Pinning)
```java
public synchronized void executeTransaction() {
    executeBlockingDbCall(); // Virtual thread is pinned to the carrier thread here
}
```

### 3.2 ReentrantLock (Does NOT Trigger Pinning)
```java
package com.example.concurrency.pinning;

import java.util.concurrent.locks.ReentrantLock;

public class PinningMitigation {

    private final ReentrantLock lock = new ReentrantLock();

    public void executeTransaction() {
        lock.lock();
        try {
            executeBlockingDbCall(); // The virtual thread unmounts safely here
        } finally {
            lock.unlock();
        }
    }

    private void executeBlockingDbCall() {
        try {
            Thread.sleep(100); // Simulate database latency
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
```

---

## 4. The Conundrum of ThreadLocal Variables

`ThreadLocal` variables associate values with the current thread execution stack. 

In virtual thread architectures, this introduces two main risks:
1.  **Memory Bloat**: Spawning 100,000 virtual threads where each thread allocates a 10KB `ThreadLocal` map consumes 1GB of heap memory solely for context variables.
2.  **Inheritance Leaks**: Inheritable thread-local variables (`InheritableThreadLocal`) copy context state from parent to child threads, which can lead to memory leaks and dirty context references.

*Note: Scoped Values (introduced in Module 06) resolve these limitations by providing immutable, lightweight context propagation.*

---

## 5. Monitoring Pinning & Thread Dumps

To diagnose pinning issues in production, use the following tools:

### 5.1 JVM System Properties
Start the JVM with the `jdk.tracePinnedThreads` flag to log pinning stack traces:
```bash
# Log a full stack trace when a thread pins
java -Djdk.tracePinnedThreads=full -jar app.jar

# Log a single-line summary when a thread pins
java -Djdk.tracePinnedThreads=short -jar app.jar
```

### 5.2 Analyzing Thread Dumps using `jcmd`
Generate a thread dump to inspect virtual thread state and locate blocked carrier threads:
```bash
# Generate a JSON-formatted thread dump including virtual threads
jcmd <PID> Thread.dump_to_file -format=json thread_dump.json
```

---

## 6. Interview Questions

### Q1: Why does a `synchronized` block pin a virtual thread to its carrier thread, while `ReentrantLock` does not?
**Answer**: 
*   `synchronized`: Is a low-level JVM monitor mechanism. When a thread enters a synchronized block, the monitor lock is bound to the physical CPU thread stack registers at the native OS layer. The JVM cannot unmount the virtual thread's stack frames without corrupting this native monitor state.
*   `ReentrantLock`: Is written in Java using the AbstractQueuedSynchronizer (AQS) framework. Since it manages lock states using Java objects on the JVM heap rather than native OS monitor registers, the JVM can unmount the virtual thread during blocking operations, leaving the lock state intact on the heap.

### Q2: What is the risk of using `ThreadLocal` variables in a system that spawns millions of concurrent virtual threads?
**Answer**: 
`ThreadLocal` variables are stored in a map associated with the thread instance. In traditional platforms, the thread count is limited, keeping `ThreadLocal` memory footprints small.
When spawning millions of virtual threads, if each thread allocates memory in its `ThreadLocal` map, the collective memory footprint can easily consume the JVM heap, triggering out-of-memory errors. Additionally, because virtual threads are not pooled, the overhead of creating and garbage collecting these maps for every short-lived thread degrades performance.
