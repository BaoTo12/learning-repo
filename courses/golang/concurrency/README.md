# Advanced Go Concurrency Masterclass

Welcome to the Go Concurrency Course, a production-grade, in-depth guide designed to take you from an intermediate Go developer to a concurrent systems architect. 

## Course Overview
Concurrency is one of Go's primary strengths, but it is also one of the most misunderstood and misused features. This course does not merely teach syntax (like `go` and `chan`). Instead, we deep dive into the runtime scheduler (GMP model), memory layout, synchronization mechanics, happens-before guarantees, race detector internals, and real-world system patterns.

## Course Map & Syllabus

| Module | Name | Topics Covered | Est. Study Time |
|---|---|---|---|
| [Module 0](./modules/00-foundations.md) | Concurrency Foundations | Concurrency vs Parallelism, Throughput vs Latency, CPU vs I/O, Historic Models (CSP, Actor, Event Loop) | 2 hours |
| [Module 1](./modules/01-internals.md) | How Go Concurrency Works Internally | Goroutines, GMP Scheduler, Work Stealing, Stack Management, Preemption | 4 hours |
| [Module 2](./modules/02-goroutines-in-practice.md) | Goroutines in Practice | Lifecycle, Launching, Termination, Closure capture, Fire-and-Forget | 2 hours |
| [Module 3](./modules/03-channels-csp.md) | Channels: The Core of CSP | Communication vs Sharing, hchan internals, Unbuffered vs Buffered, Visualizations | 3 hours |
| [Module 4](./modules/04-select.md) | Select Statement | Random Selection, Non-blocking select, Timeouts, Fan-in, Multiplexing | 2 hours |
| [Module 5](./modules/05-sync-primitives.md) | Synchronization Primitives | WaitGroup, Mutex (Fairness/Starvation), RWMutex, Once, Cond, Atomics (CAS) | 4 hours |
| [Module 6](./modules/06-memory-model.md) | The Go Memory Model | Happens-before Relationships, Reordering, Visibility, Unsafe code | 3 hours |
| [Module 7](./modules/07-races-and-detection.md) | Data Races & Race Detection | Data Races vs Race Conditions, `go test -race`, Vector Clocks, Incidents | 2 hours |
| [Module 8](./modules/08-design-patterns.md) | Concurrency Design Patterns | Worker Pools, Fan-out/Fan-in, Pipelines, Semaphores, Pub-Sub, Futures | 4 hours |
| [Module 9](./modules/09-context-cancellation.md) | Context & Cancellation | context.Context hierarchy, Propagation, Leaks, Value passing | 3 hours |
| [Module 10](./modules/10-errgroup.md) | errgroup & Structured Concurrency | golang.org/x/sync/errgroup, Error propagation, WaitGroup comparison | 2 hours |
| [Module 11](./modules/11-preventing-leaks.md) | Preventing Goroutine Leaks | Leaking causes, Blocked channels, Profiling, Leak detection tools | 2 hours |
| [Module 12](./modules/12-advanced-techniques.md) | Advanced Concurrency | sync.Pool, singleflight request deduplication, Lock-Free CAS loops | 3 hours |
| [Module 13](./modules/13-performance-engineering.md) | Performance Engineering | Benchmarking, pprof (CPU/Mem/Block/Mutex), Execution tracing, Optimization | 4 hours |
| [Module 14](./modules/14-testing-concurrent-code.md) | Testing Concurrent Code | Flaky tests, Time abstraction, Synchronization, Fuzzing concurrent code | 3 hours |
| [Module 15](./modules/15-real-systems.md) | Concurrency in Real Systems | HTTP Request Handling, WebSockets, Job queues, Pipelines, Log processors | 4 hours |
| [Module 16](./modules/16-standard-library.md) | Reading the Go Stdlib | net/http, context, sync, database/sql code walkthroughs | 3 hours |
| [Module 17](./modules/17-common-anti-patterns.md) | Common Anti-Patterns | Goroutine-per-everything, busy waiting, overusing RWMutex, unhandled panics | 2 hours |
| [Module 18](./modules/18-capstone.md) | Capstone Project | Building a Production-Grade Concurrent System (Crawler, WebSockets, or Processor) | 8 hours |

## Course Prerequisites
* Intermediate knowledge of Go (syntax, structs, interfaces, error handling).
* Basic understanding of operating system concepts (processes, virtual memory, threads).
* Comfort with command-line tools (go CLI, curl, git).

Let's begin! Navigate to [Module 0: Concurrency Foundations](./modules/00-foundations.md) to start.
