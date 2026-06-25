# Optimizing Cloud Native Java: Practical Techniques for Improving JVM Application Performance

Welcome to the **Optimizing Cloud Native Java** course. This curriculum is designed to guide you from writing standard Java applications to mastering the low-level systems engineering, runtime mechanics, and distributed architecture required for high-performance cloud deployments.

This course is structured chapter-by-chapter around the second edition (2024) of the definitive book *Optimizing Cloud Native Java* by Benjamin J. Evans and James Gough. Throughout this course, you will learn to apply a quantitative, verifiable, and repeatable approach to performance tuning, moving away from guesswork and folklore.

---

## Course Syllabus & Navigation

The course is divided into 19 comprehensive modules, including the introductory chapters, advanced JVM topics, cloud deployment patterns, observability frameworks, and diagnostic appendices.

All module links below are configured with absolute file paths for direct, seamless navigation in your development environment:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **00** | [Preface & Introduction](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/00-foreword-preface-introduction.md) | Foreword by Holly Cummins, author preface, acknowledgements, and target audience alignment. |
| **01** | [Optimization & Performance Defined](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/01-optimization-and-performance-defined.md) | Performance taxonomy (Throughput, Latency, Capacity, Utilization, Efficiency, Scalability, Degradation), reading performance elbows, and cloud-native cluster dynamics. |
| **02** | [Performance Testing Methodology](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/02-performance-testing-methodology.md) | Types of performance tests, statistics for the JVM (non-normal distributions, the Hat/Elephant problem), and cognitive biases in engineering. |
| **03** | [Overview of the JVM](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/03-overview-of-the-jvm.md) | Classloading, bytecode execution, tiered JIT compilation foundations, Java Memory Model overview, Adoptium/Temurin distributions, and release cycles. |
| **04** | [Understanding Garbage Collection](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/04-understanding-garbage-collection.md) | Mark-and-sweep, object representation at runtime, Weak Generational Hypothesis, TLABs, hemispheric collection, and young/old Parallel Collectors. |
| **05** | [Advanced Garbage Collection](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/05-advanced-garbage-collection.md) | Concurrent GC theory, safepoints, tri-color marking, G1 regions/remembered sets, ultra-low latency Shenandoah & ZGC, and Eclipse OpenJ9 Balanced GC. |
| **06** | [Code Execution on the JVM](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/06-code-execution-on-the-jvm.md) | Interpreter mechanics, JIT C1/C2 compilers, method inlining, escape analysis, scalar replacement, and Ahead-of-Time (AOT) with GraalVM/Quarkus. |
| **07** | [Hardware and Operating Systems](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/07-hardware-and-operating-systems.md) | Memory hierarchy, L1/L2/L3 caches, cache lines, false sharing, TLB, branch prediction, speculative execution, OS schedulers, context switches, and system models. |
| **08** | [Components of the Cloud Stack](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/08-components-of-the-cloud-stack.md) | CNCF standards (Kubernetes, Prometheus, OpenTelemetry), hypervisors vs. containers, OS virtualization, and container image structure. |
| **09** | [Deploying Java in the Cloud](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/09-deploying-java-in-the-cloud.md) | Docker Compose, Tilt local development, Kubernetes Pod/Service lifecycles, Blue/Green & Canary deployments, and container memory limits / OOM kills. |
| **10** | [Introduction to Observability](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/10-introduction-to-observability.md) | The three pillars (metrics, logs, traces), push vs. pull architectures, and diagnosing outages (thundering herds, split-brain, cascading failures). |
| **11** | [Implementing Observability in Java](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/11-implementing-observability-in-java.md) | Micrometer registry, meters (Counters, Gauges, Timers, Summaries), Prometheus integration, OpenTelemetry Java agent, and manual/automatic tracing. |
| **12** | [Profiling](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/12-profiling.md) | Safepoint bias, execution and allocation profiling, VisualVM, JDK Mission Control (JMC), Async Profiler, JDK Flight Recorder (JFR), and Cryostat. |
| **13** | [Concurrent Performance Techniques](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/13-concurrent-performance-techniques.md) | Amdahl's law, happens-before rules, lock-free CAS, Var/Method Handles, java.util.concurrent abstractions, and Virtual Threads mechanics. |
| **14** | [Distributed Systems Techniques & Patterns](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/14-distributed-systems-techniques-and-patterns.md) | Clocks, 2PC, write-ahead logs, CAP theorem, Paxos/Raft consensus, Cassandra, Infinispan, and Kafka distributed service design. |
| **15** | [Modern Performance & The Future](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/15-modern-performance-and-the-future.md) | Structured Concurrency, Scoped Values, Project Panama (Foreign Function & Memory), Project Leyden (startup optimization), and Project Valhalla (primitive types & generic specialization). |
| **16** | [Appendix A: Microbenchmarking](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/16-appendix-a-microbenchmarking.md) | Microbenchmarking pitfalls, JVM warmup, JMH framework, annotations, and interpreting execution metrics. |
| **17** | [Appendix B: Performance Antipatterns Catalog](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/17-appendix-b-performance-antipatterns-catalog.md) | Antipatterns catalog (Distracted by Shiny/Simple, Tuning by Folklore, Blame Donkey, UAT is My Desktop, Production Data is Hard). |
| **18** | [Book Index](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/java/optimizing-cloud-native-java/modules/18-book-index.md) | Comprehensive alphabetical reference index from the original text. |

---

## Performance Diagnostic Tooling Setup

To succeed in this curriculum and complete the hands-on profiling exercises, you will require the following diagnostic parameters and open-source tools configured on your JVM runtime:

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
