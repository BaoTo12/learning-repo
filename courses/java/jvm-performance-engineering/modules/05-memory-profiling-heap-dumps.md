# Module 05: Memory Profiling & Heap Dumps — MAT Leak Suspects and Object Layouts

Welcome back, students. Today we master **Memory Diagnostics** and **Heap Dump Analysis**.

When a Java application runs out of memory (`java.lang.OutOfMemoryError: Java heap space`), you cannot fix it by simply restarting the server. You must locate the code path causing the leak. We will study how to generate heap dumps, analyze them using the **Eclipse Memory Analyzer Tool (MAT)**, trace objects back to their **GC Roots**, examine the physical layout of **Object Headers** in memory, and analyze a programmatic ThreadLocal memory leak.

---

## 1. Academic Lecture: The Mechanics of Heap Dumps

A heap dump is a binary file (usually with the `.hprof` extension) representing a complete snapshot of all objects residing in the JVM heap at a specific millisecond.

### Generating Heap Dumps

In production, you can trigger heap dumps manually using JDK command-line tools:
```bash
# Option A: Using jcmd (Recommended)
jcmd <PID> GC.heap_dump /tmp/heapdump.hprof

# Option B: Using jmap
jmap -dump:format=b,file=/tmp/heapdump.hprof <PID>
```

To capture memory state automatically when the JVM crashes due to memory exhaustion, append these flags during startup:
```bash
-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/var/log/app/dumps/
```

### Analyzing Dumps: Shallow vs. Retained Size

When loading a heap dump into analyzer tools like JProfiler or Eclipse MAT, the engine calculates two size metrics for every object:
*   **Shallow Size**: The memory consumed by the object itself (its fields and object header). It does not include the memory of referenced objects.
*   **Retained Size**: The total memory that would be freed if this specific object were garbage collected. It is the sum of the object's shallow size plus the size of all referenced objects that are reachable *only* through this object.

```
                  Retained Size Hierarchy
                  
                       [ Object A ] (Shallow: 32 bytes)
                        /        \
                       v          v
             [ Object B ]        [ Object C ] (Shallow: 64 bytes)
             (Shallow: 48 bytes)
             
    * Retained Size of A = Shallow(A) + Shallow(B) + Shallow(C) = 144 bytes.
```

### Locating GC Roots
An object is kept alive in memory as long as it is reachable via a chain of references starting from a **GC Root**. If an object is not reachable from any root, the garbage collector reclaims it.
Types of GC Roots include:
*   **Thread Stacks**: Local variables and parameters inside active method execution frames.
*   **Static Variables**: Reference fields defined inside loaded class metadata.
*   **JNI Handles**: Java objects referenced by native C/C++ libraries.

### The Physical Memory Layout of Java Objects

Every object stored on the JVM heap contains an **Object Header** consisting of:
1.  **Mark Word (64 bits)**: Stores metadata including identity hashcode, GC generational age, and locking flags.
2.  **Klass Word (64 bits or 32 bits)**: Pointer referencing the class metadata definition in Metaspace.
3.  **Compressed OOPs (Ordinary Object Pointers)**: To save space on heaps under 32GB, the JVM compresses 64-bit reference pointers to 32-bit references. This saves significant cache and memory bandwidth.

---

## 2. Theory vs. Production Trade-offs

### The Freeze Penalty of Heap Dumps
Generating a heap dump on a JVM with a large heap (e.g., 32GB or larger) requires the JVM to execute a global Stop-The-World safepoint. The JVM halts all application threads and writes the memory state to disk.
*   **Production Hazard**: Writing a 32GB file to disk can freeze the JVM for several minutes. This will trigger load balancer health check timeouts, causing the router to assume the container is dead and terminate it mid-dump, corrupting the file.
*   **Production Solution**: Run memory samplers or trigger heap dumps only after removing the target instance from active load balancer traffic pools.

---

## 3. How to Use: ThreadLocal Memory Leak in Java 21

Let's write a complete, compile-grade Java 21 class that simulates a memory leak using a `ThreadLocal` structure. This script is designed to run until it triggers an OutOfMemoryError, producing a heap dump file for analysis.

```java
package com.capstone.jvm.memory;

import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.logging.Logger;

/**
 * Class simulating a ThreadLocal memory leak.
 * To analyze the leak, run with:
 * -Xmx32m -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=leak.hprof
 */
public class ThreadLocalLeakSimulator {
    private static final Logger LOGGER = Logger.getLogger(ThreadLocalLeakSimulator.class.getName());

    // ThreadLocal mapping holding large payloads
    private static final ThreadLocal<byte[]> contextHolder = new ThreadLocal<>();

    public static void main(String[] args) throws InterruptedException {
        LOGGER.info("Starting ThreadLocal Leak Simulator...");

        // Create a fixed pool of worker threads
        ExecutorService threadPool = Executors.newFixedThreadPool(4);

        for (int i = 0; i < 1000; i++) {
            final int taskId = i;
            threadPool.submit(() -> {
                try {
                    // Simulate processing by allocating a 1MB buffer to the thread context
                    byte[] payload = new byte[1_000_000];
                    contextHolder.set(payload);

                    LOGGER.info("Task " + taskId + " executing on thread " + Thread.currentThread().getName());
                    
                    // PITFALL: We "forget" to call contextHolder.remove() here.
                    // Because thread pool threads are reused, the 1MB payload remains bound to the thread
                    // object permanently, leaking memory on every task pass.
                } catch (Throwable t) {
                    LOGGER.severe("Exception in thread task: " + t.getMessage());
                }
            });

            TimeUnit.MILLISECONDS.sleep(50);
        }

        threadPool.shutdown();
        threadPool.awaitTermination(1, TimeUnit.MINUTES);
        LOGGER.info("Simulation completed.");
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Retaining references inside static collections
Adding elements to a static `HashMap` or `ArrayList` and failing to delete them.
*   **Why it leaks**: Static variables serve as GC Roots. Objects stored inside static collections are reachable forever and can never be garbage collected.
*   **Mitigation**: Use weak reference collections like `WeakHashMap` or implement eviction policies (such as LRU eviction or time-to-live caps).

### Pitfall 2: Exposing Compressed OOPs limits
Setting heap sizes to 32GB (`-Xmx32g`).
*   **Why it fails**: When the heap crosses 32GB, the JVM can no longer address memory using 32-bit compressed pointers. It automatically falls back to 64-bit uncompressed pointers. This causes object references to consume double the size, bloating the heap footprint by up to 20% and degrading cache performance.
*   **Mitigation**: Set maximum heap sizes slightly below the threshold, typically at **31GB** (`-Xmx31g`), or jump directly to 40GB+ if you require more memory.

---

## 5. Socratic Review Questions

### Question 1
Explain the difference between **Shallow Size** and **Retained Size** of an object using a concrete example.

#### Answer
Consider an object instance `User` that contains a reference to an `Address` object.
*   **Shallow Size**: The memory footprint of the `User` object itself. On a 64-bit JVM with compressed references, it consists of: 12-byte object header, 8-byte reference pointer to the username String, 8-byte reference pointer to the `Address` object, plus alignment padding. The total shallow size is 32 bytes.
*   **Retained Size**: The shallow size of the `User` (32 bytes) plus the shallow sizes of the `Address` object and the username String, provided those objects are not referenced by any other objects in the heap. If the `Address` object is shared by another `User` instance, its size is not included in the retained size of the first `User`, because garbage collecting the first `User` would not free the shared `Address`.

### Question 2
Why are local variables on a thread stack considered **GC Roots**? What occurs when a method returns?

#### Answer
Local variables are GC Roots because they represent references actively used by the executing CPU instructions. 

When a thread executes a method, it pushes a **Stack Frame** containing its local variables onto its execution stack. The JVM must ensure that any objects referenced by these local variables are kept alive in the heap so the executing code does not read garbage.

When a method returns, its Stack Frame is popped off the thread stack. The local references inside the frame are discarded. If these were the only references pointing to the heap objects, those objects immediately become unreachable from any GC Root and are reclaimed during the next garbage collection sweep.

---

## 6. Hands-on Challenge: Leaking Map Detector

### The Challenge
In this challenge, you will implement the logic for a memory leak diagnostics helper class. 

Given a simulated heap dump (represented as a list of allocated objects with their shallow sizes and reference chains), you must write a method that identifies the "Dominator" object—the object holding the largest Retained Size—to isolate the leak suspect.

Complete the leak analyzer logic inside the class below:

```java
package com.capstone.jvm.memory.challenge;

import java.util.List;

public class HeapLeakAnalyzer {

    public record HeapObject(String id, long shallowSize, List<String> referenceIds) {}

    /**
     * Identifies the ID of the object that acts as the primary leak suspect.
     * The primary suspect is defined as the object whose reference chain
     * recursively holds the highest cumulative shallow size of unreachable child objects.
     * 
     * @param objects list of heap objects
     * @return the ID of the leak suspect object
     */
    public String locateLeakSuspect(List<HeapObject> objects) {
        String suspectId = "";
        long maxRetainedSize = 0L;

        // TODO: Complete this implementation.
        // For each object, calculate its retained size (shallow size + shallow sizes of all objects
        // that are only reachable through its referenceIds chain).
        // Return the object ID with the highest retained size.
        return suspectId;
    }
}
```

Write your code and verify the retained size analysis. Save your solution notes inside `modules/05-memory-profiling-heap-dumps.md`.
