# Production Go Concurrency: From Intermediate to Expert

Welcome to the ultimate guide on Go concurrency. This course is designed to take you from a developer who knows Go's concurrent syntax to an engineer who can architect, optimize, and debug highly concurrent, production-grade systems in Go.

## 📌 Course Goals
1. **Master the Internals**: Gain a deep mental model of the Go runtime scheduler (GMP model), goroutine stack management, and compiler memory reorderings.
2. **Write Safe Code**: Develop an intuitive understanding of the Go Memory Model and learn how to run, interpret, and resolve issues caught by Go's race detector.
3. **Design Production Patterns**: Implement classic concurrency patterns like Worker Pools, pipelines with backpressure, pub-sub systems, and future/promises.
4. **Debug & Profile**: Diagnose goroutine leaks, profile locks using `pprof`, debug trace profiles, and design deterministic tests for asynchronous systems.
5. **Architect Real-World Engines**: Implement a complete, production-grade distributed log processing pipeline with backpressure, graceful shutdown, and structured concurrency.

---

## 🛠️ Prerequisites
* **Go Proficiency**: Comfort with basic Go syntax, structs, interfaces, pointer semantics, and the standard testing package.
* **Basic Networking**: Basic familiarity with HTTP, WebSockets, and database operations.
* **Operating Systems Basic**: Understanding of processes, threads, virtual memory, and I/O.

---

## 🗺️ Course Map & Syllabus

Below is the complete module list. Each module is structured as a standalone, comprehensive learning guide with in-depth explanations, code snippets, Mermaid diagrams, exercises, and complete solutions.

| Module | Name | Focus | Est. Study Time |
|:---|:---|:---|:---|
| **0** | [Concurrency Foundations](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/00-foundations.md) | Concurrency vs. Parallelism, Threading Models, CSP Theory | 1.5 Hours |
| **1** | [How Go Concurrency Works Internally](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/01-internals.md) | GMP Model, Work Stealing, Stacks, Preemption | 2.5 Hours |
| **2** | [Goroutines in Practice](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/02-goroutines-in-practice.md) | Lifecycle, Scheduling Unpredictability, Loop Capture Pitfalls | 1.5 Hours |
| **3** | [Channels: The Core of CSP](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/03-channels-csp.md) | `hchan`, Send/Receive Queues, Buffers, CSP Philosophy | 2.5 Hours |
| **4** | [Select Statement](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/04-select-statement.md) | Non-blocking ops, Fairness, Timeouts, Multiplexing | 2.0 Hours |
| **5** | [Synchronization Primitives](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/05-synchronization-primitives.md) | Mutexes, RWMutex Starvation, WaitGroups, sync.Once, Cond, Atomics | 3.0 Hours |
| **6** | [The Go Memory Model](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/06-memory-model.md) | Happens-Before, Compiler Reordering, Visibility Guarantees | 2.0 Hours |
| **7** | [Data Races and Race Detection](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/07-data-races.md) | ThreadSanitizer, Race Mechanics, Debugging Cases | 1.5 Hours |
| **8** | [Concurrency Design Patterns](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/08-design-patterns.md) | Worker Pools, Pipelines, Semaphores, Pub-Sub, Futures | 3.0 Hours |
| **9** | [Context and Cancellation](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/09-context-cancellation.md) | Cancellation Propagation, Deadlines, Context Leaks | 2.0 Hours |
| **10** | [errgroup & Structured Concurrency](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/10-errgroup-structured-concurrency.md) | Structured Concurrency, Error Propagation, Parallel Aggregation | 1.5 Hours |
| **11** | [Preventing Goroutine Leaks](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/11-preventing-leaks.md) | Blocked Channels, Leak Profiles, Diagnostics with `goleak` | 2.0 Hours |
| **12** | [Advanced Concurrency Techniques](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/12-advanced-techniques.md) | `sync.Pool`, GC impact, Singleflight request deduplication, Lock-Free | 2.5 Hours |
| **13** | [Performance Engineering](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/13-performance-engineering.md) | Benchmarking, `benchstat`, CPU/Mutex/Block Profiles, Tracing | 3.0 Hours |
| **14** | [Testing Concurrent Code](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/14-testing-concurrent-code.md) | Virtual Clocks, Deterministic Tests, Fuzzing concurrent APIs | 2.0 Hours |
| **15** | [Concurrency in Real Systems](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/15-concurrency-in-real-systems.md) | Case Studies: WebSockets, Background Jobs, Streaming Pipelines | 3.0 Hours |
| **16** | [Reading the Go Standard Library](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/16-reading-stdlib.md) | Deep Dive: `net/http` pool, `database/sql`, atomic variables | 2.0 Hours |
| **17** | [Common Anti-Patterns](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/17-common-anti-patterns.md) | Busy Loops, Shared Mutability Abuse, Panic in Goroutines | 1.5 Hours |
| **18** | [Capstone: Distributed Log Processor](file:///c:/Users/Admin/Desktop/projects/learning-repo/courses/golang/concurrency/modules/18-capstone.md) | Implementing a pipelined, backpressured, structured Distributed Log Processor | 4.0 Hours |

---

## 📚 Recommended Resources & Readings
* **Official Documentation**:
  * [The Go Memory Model](https://golang.org/ref/mem)
  * [Go Developer Guide: Concurrency](https://go.dev/doc/concurrency)
  * [Go runtime scheduler source code](https://github.com/golang/go/blob/master/src/runtime/proc.go)
* **Essential Talks**:
  * *Concurrency is not Parallelism* by Rob Pike (2012)
  * *Go Scheduler: Implementing Asynchronous Preemption* by Austin Clements (2019)
  * *Rethinking Classical Concurrency Patterns* by Bryan C. Mills (GopherCon 2018)
