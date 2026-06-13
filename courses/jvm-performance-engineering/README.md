# CS-515: JVM Internals & Advanced Performance Engineering

Welcome to **CS-515: JVM Internals & Advanced Performance Engineering**. I am Professor Antigravity. In this course, we will transition from writing standard Java code to managing the runtime mechanics and execution lifecycle of the Java Virtual Machine (JVM).

At senior engineering levels, code optimization requires a deep understanding of the underlying execution layer. Writing clean code is only the first step. You must understand how the Classloader loads bytecode, how the JIT compiler compiles hot paths to assembly, how memory layout governs hardware cache lines, how garbage collectors reclaim memory regions, and how to diagnose memory leaks and thread blocks under production load.

In this course, we will study **generative memory models, G1 & ZGC internal mechanics, Unified JVM Logging, heap and thread dumps, sampling/instrumentation CPU profiling (Async Profiler/JProfiler), and JIT tiered compilation optimization**.

---

## Course Syllabus & Navigation

The course is divided into 10 detailed modules and a final capstone diagnostics challenge:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [JVM Architecture & Memory Model](file:///c:/Users/Admin/Desktop/projects/learning-repo/jvm-performance-engineering/modules/01-jvm-architecture-memory-model.md) | Metaspace, Stack vs. Heap, TLABs, PLABs, JMM happens-before, and CPU cache False Sharing. |
| **02** | [G1 GC Mechanics & Foundations](file:///c:/Users/Admin/Desktop/projects/learning-repo/jvm-performance-engineering/modules/02-garbage-collection-foundations-g1.md) | Generational hypothesis, mark-sweep-compact, G1 regions, Remembered Sets, Card Tables, and Humongous allocations. |
| **03** | [Modern Low-Latency GCs](file:///c:/Users/Admin/Desktop/projects/learning-repo/jvm-performance-engineering/modules/03-modern-low-latency-gcs.md) | ZGC and Shenandoah, load barriers, colored pointers, concurrent compaction, and thread handshakes. |
| **04** | [GC Log Analysis & Diagnostics](file:///c:/Users/Admin/Desktop/projects/learning-repo/jvm-performance-engineering/modules/04-gc-log-analysis-diagnostics.md) | Unified JVM Logging configurations, GC log parsing, throughput, promotion, and allocation rates. |
| **05** | [Memory Profiling & Heap Dumps](file:///c:/Users/Admin/Desktop/projects/learning-repo/jvm-performance-engineering/modules/05-memory-profiling-heap-dumps.md) | Heap dump generation, MAT leak suspects, GC roots, and object memory header layouts (Mark Word, OOPs). |
| **06** | [CPU Profiling & Flame Graphs](file:///c:/Users/Admin/Desktop/projects/learning-repo/jvm-performance-engineering/modules/06-cpu-profiling-execution-analysis.md) | Sampling vs. Instrumentation, Async Profiler execution, Flame Graphs, and JProfiler call trees. |
| **07** | [JIT Compilation & Code Cache](file:///c:/Users/Admin/Desktop/projects/learning-repo/jvm-performance-engineering/modules/07-jit-compilation-code-cache.md) | Tiered Compilation (C1/C2), Escape Analysis, Scalar Replacement, Inlining, and disassembly inspect. |
| **08** | [Synchronization & Thread Dumps](file:///c:/Users/Admin/Desktop/projects/learning-repo/jvm-performance-engineering/modules/08-multithreading-synchronization-performance.md) | Monitor contention (biased/inflated locks), lock elision, coarsening, thread dump analysis, and deadlocks. |
| **09** | [Off-Heap Memory & Native Tracking](file:///c:/Users/Admin/Desktop/projects/learning-repo/jvm-performance-engineering/modules/09-off-heap-memory-direct-buffers.md) | Direct ByteBuffers, Panama Foreign Memory API, Unsafe, and Native Memory Tracking (NMT) diagnostics. |
| **10** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/jvm-performance-engineering/modules/10-final-capstone-performance-optimization.md) | Diagnosing, profiling, and optimizing a high-latency, leaking server to meet target SLA metrics. |

---

## Performance Diagnostic Tooling Setup

To complete the profiling exercises, you will require the following diagnostic parameters and open-source tools configured on your JVM runtime:

### 1. Unified GC Logging Parameters
To generate detailed logs for parser diagnostics, append this flag to your JVM startup command:
```bash
-Xlog:gc*,gc+phases=debug:file=gc.log:time,uptime,pid:filecount=5,filesize=100M
```

### 2. JDK Flight Recorder (JFR)
To profile allocations and CPU events with low overhead, start a Flight Recording automatically during startup:
```bash
-XX:StartFlightRecording=disk=true,dumponexit=true,filename=recording.jfr,settings=profile
```

### 3. Async Profiler Installation
For non-safepoint biased CPU profiling, download the appropriate binary for your system (e.g., Linux/macOS) and run:
```bash
# Profile CPU usage for 30 seconds and output a flame graph
./asprof -d 30 -f flamegraph.html -e cpu <PID>
```
*For Windows developers, you will use **JProfiler** or **VisualVM** sampling alongside JVM command-line tools.*

---

## Grading Criteria & Performance Success Metrics

Your performance in this course is evaluated based on the following engineering metrics:

*   **Diagnostic Precision (30%)**: Correctly isolating performance bottlenecks from logs, thread dumps, and heap analysis suspect files.
*   **Memory Efficiency (30%)**: Writing garbage-collector-friendly code. Eliminating memory leaks, reducing object promotion rates, and designing safe off-heap systems.
*   **Execution Speed & JIT Alignment (30%)**: Optimizing CPU-bound execution. Aligning loop structures to enable method inlining, vectorization, and escape analysis scalar allocation.
*   **JVM Systems Reasoning (10%)**: Demonstrating a deep understanding of memory model boundaries, lock state lifecycles, and garbage collection barrier mathematics.
