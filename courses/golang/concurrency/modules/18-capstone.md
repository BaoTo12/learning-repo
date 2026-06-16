# Module 18 — Capstone Project

## Metadata
* **Estimated Study Time:** 8 hours
* **Prerequisites:** Modules 0 to 17
* **Learning Outcomes:**
  * Design, build, test, and profile a production-grade concurrent system from scratch.
  * Integrate worker pools, dynamic rate limiters, context cancellations, and structured error handling.
  * Run performance audits, analyze cpu/block profiles, and optimize synchronization bottlenecks.

---

## 1. Project Selection

Choose **one** of the following options to build for your final capstone project. Each system must be written in production-grade Go code, complete with clean packaging, unit tests, and performance profiles.

---

## Option A: Concurrent Web Crawler

Build a web crawler that crawls links starting from a seed URL, parses html anchor tags, and downloads metadata concurrently.

### 1. Architectural Blueprint
```
                   [ Seed URL ]
                        |
                 [ Crawler Engine ]
                /       |        \
         [ Worker 1]  [Worker 2]  [Worker 3]
             |          |             |
             +----------+-------------+
                        |
            [ Thread-Safe State Cache ]
```

### 2. Mandatory Technical Requirements
* **Bounded Worker Pool**: Create a worker pool to fetch and process web pages. Do not spawn a goroutine per link found (unbounded).
* **Visited Cache**: Visited URLs must be tracked in a thread-safe map structure to prevent duplicate fetching or circular redirection loops.
* **Domain Rate Limiting**: Crawl requests must respect domain boundaries. Implement a dynamic token-bucket rate limiter that restricts queries to a domain (e.g., maximum 5 queries per second to `wikipedia.org`).
* **Cancellation Tree**: Use `context.Context` to propagate deadlines (e.g., abort the crawl if it runs for more than 30 seconds) and coordinate graceful exit on OS signals (`SIGINT`, `SIGTERM`).
* **Metrics Dashboard**: Expose system counters (active workers, total requests processed, bytes read, error rates, and cache hits) using atomic metrics.

---

## Option B: Distributed Log Processor

Build a pipeline processor that reads massive folders of text logs, aggregates message categories, filters anomalies, and outputs consolidated reports concurrently.

### 1. Architectural Blueprint
```
        [ Log Directory ]
                |
         [ Chunk Reader ]
                | (Lines Channel)
        [ Worker Pipeline ] (hashes/filters)
                | (Filtered Data)
         [ Output Writer ] (ordered consolidation)
```

### 2. Mandatory Technical Requirements
* **Chunked File I/O**: Stream log contents using chunked buffering. Do not read entire log files into memory at once to prevent OOM errors.
* **Pipeline Isolation**: Implement separate pipeline stages connected by buffered channels. Stage 1: Reader; Stage 2: Log Parser; Stage 3: Aggregator; Stage 4: Writer.
* **Backpressure Management**: Implement backpressure. If the Aggregator stage slows down (e.g., due to database writes), the Reader stage must pause reading files.
* **Error Aggregation**: Coordinate the pipeline using `errgroup`. If any log file contains a critical corruption error, abort the process and return the error.
* **Order Preservation**: The output report file must display aggregated log lines in chronological order, matching the input log file order, despite concurrent processing in the middle stages.

---

## 2. Implementation Guide: Step-by-Step

To complete your capstone:

### Step 1: Design the Package Structure
Structure your repository cleanly:
```
cmd/
  crawler/
    main.go      // Entrypoint, signal listening, environment config
pkg/
  crawler/
    crawler.go   // Main engine orchestrator
    pool.go      // Worker pool implementation
    cache.go     // Thread-safe visited cache
    limiter.go   // Domain rate limiter
```

### Step 2: Write Thread-Safe Components First
Implement your `VisitedCache` using a `sync.RWMutex` to protect a map of string hashes, and test it for data races under heavy parallel writes.

### Step 3: Integrate the Worker Pool Event Loop
Create the worker dispatcher. The dispatcher should loop over incoming target tasks, request rate-limiter tokens, and dispatch work to the pool.

### Step 4: Implement Graceful Shutdown
Configure the signal listener inside `cmd/crawler/main.go`. When an interrupt signal is received:
1. Trigger the context cancellation.
2. Wait for workers to finish active page crawls.
3. Print final crawl stats.
4. Exit cleanly.

---

## 3. Verification and Hardening Checklist

To verify your capstone matches senior engineer standards, execute the following validation steps:

### 1. Memory Safety (Race Check)
Compile and run your project tests with the race detector enabled:
```bash
go test -race -v ./pkg/...
```
Verify that the output displays **zero warnings**. Any data race is a failure.

### 2. Leak Audit
Integrate `goleak` in your package tests to verify that shutting down the crawler or log processor terminates all worker goroutines, leaving no blocked channels or timers in memory.

### 3. Performance Profiling
Write a benchmark simulating load (e.g. crawling a mock local HTTP server) and collect CPU and block profiles:
```bash
go test -bench=. -cpuprofile=cpu.pprof -blockprofile=block.pprof
```
Analyze the profiles using `go tool pprof`. Locate any locks that cause scheduler stalls and optimize them using sharding, batching, or lock-free atomics.
---

## 4. Advanced Deep Dive: Capstone Verification

Verify your capstone implementation using profiling tools. Confirm memory allocations are minimal, locks are not contended, and graceful shutdowns are clean.

### Extended Structural Analysis and Architectural Notes
To make these concepts fully practical for enterprise designs, we must trace their implications on deployment environments. When running Go binaries inside Kubernetes, container resource boundaries introduce unique scheduling quirks. For example, if a pod is configured with a CPU limit of 2.0 (equivalent to two CPU cores), the Go runtime will by default detect the physical node core count (which could be 64 cores) and configure `GOMAXPROCS` to 64. 

This core mismatch is a primary driver of latency spikes in concurrent applications. The 64 logical processors ($P$) try to schedule work, spawning multiple system threads ($M$), but the Linux CFS quota limits the container to 2 physical cores of execution time. The kernel throttles the container process, causing context switch queuing delays.
* To prevent this container throttling, always configure `GOMAXPROCS` to match the container CPU limits using library abstractions like `go.uber.org/automaxprocs` or setting the environment variable explicitly.
* Benchmark your systems under resource limitations that match production. This is the only way to catch CPU scheduling starvation issues during development.

```
  [Physical Cores: 64] ----> [Kubernetes Limit: 2.0] ----> [GOMAXPROCS set to 2]
                                                                  |
                                                       [Prevents CFS Throttling]
```

### Microsecond Garbage Collection Performance
Go's concurrent garbage collector runs concurrently with user goroutines. The GC utilizes write barriers to track pointer updates during the mark phase.
* If your application allocates millions of short-lived pointers (e.g., inside loops mapping JSON fields to struct addresses), the write barriers add CPU latency.
* Minimizing pointer structures (e.g., storing structs by value instead of pointer in maps and arrays) simplifies the GC scan phase.
* **Production Recommendation**: Design data paths using value types, arrays of structs, or flat buffers. This significantly improves execution speeds and reduces GC mark loops.

### System Integration Audits
Every concurrency primitive (channels, mutexes, waitgroups) must be audited under realistic load spikes. When load testing your service, collect metrics for:
1. **Thread Spikes**: Spawning thousands of threads indicates blocked system calls or network calls without timeouts.
2. **Memory Leak Curves**: A rising memory staircase that never stabilizes is a clear signature of leaked goroutines.
3. **Lock Wait Time**: Measured using the mutex profile, indicating that locks should be sharded or refactored to lock-free atomic buffers.

---

## 10. SRE Production Operations Manual & Failure Recovery Strategy

This section provides operational guidelines, Prometheus alert thresholds, and troubleshooting playbooks for running these concurrent systems in production environments.

### 1. Prometheus Metrics to Monitor
Always export the following metrics from your Go runtime context using the Prometheus client library:
* `go_goroutines`: The current number of active goroutines. Monitor for rapid stair-step growth.
* `go_threads`: The number of physical OS threads created by the runtime. If this climbs above 500, check for hanging filesystem or database syscalls.
* `go_memstats_heap_alloc_bytes`: In-use heap memory. Look for dynamic memory leaks caused by pinned closure scopes.
* `go_gc_duration_seconds`: Track garbage collection execution latencies. Ensure $p99$ GC execution is under 1 millisecond.

### 2. SRE Dashboard Metrics Layout
```
+-----------------------------------+-----------------------------------+
|       Active Goroutines (Count)   |        Heap Allocations (MB)      |
|  [ Alert: > 50,000 (Staircase) ]  |  [ Alert: > 80% Container limit ] |
+-----------------------------------+-----------------------------------+
|      Thread Exhaustion (M count)  |       GC Duration p99 (ms)        |
|  [ Alert: > 1000 threads ]        |  [ Alert: > 5ms execution pause ] |
+-----------------------------------+-----------------------------------+
```

### 3. Incident Alerting Thresholds
Configure your alerting engine (e.g., Prometheus Alertmanager) with these rules:
* **Goroutine Spike Alert**: Trigger a Warning level alert if `go_goroutines` increases by more than $50\%$ within a 5-minute window, and Critical if it continues to climb without returning to baseline, indicating a severe goroutine leak.
* **Lock Contention Saturation**: Trigger a Warning alert if the mutex profile wait time exceeds 250ms per lock transaction, indicating severe thread contention.
* **CFS Throttle Ratio**: Trigger an alert if the Kubernetes container throttling CPU ratio exceeds 10% of total run time, requiring immediate `GOMAXPROCS` tuning.

### 4. Step-by-Step Incident Response Playbook

When an alarm triggers indicating a service instance is saturated:

#### Step 1: Collect Diagnostics Before Restarting
Do not restart the container immediately. Collect stack dumps and profiles to isolate the issue:
```bash
# Capture full goroutine stack trace
curl -o stacks.txt http://localhost:6060/debug/pprof/goroutine?debug=2
# Collect a 30-second CPU profile
curl -o cpu.pprof http://localhost:6060/debug/pprof/profile?seconds=30
```

#### Step 2: Analyze Stack Blocker Paths
Search the `stacks.txt` file for common synchronization wait states:
* Look for `chanreceive` to identify read-channel wait states.
* Look for `chansend` to identify write-channel blocking.
* Look for `semacquire` to identify mutex and waitgroup wait blocks.

#### Step 3: Implement Safe Mitigations
* If the leak is caused by slow downstream APIs, configure client timeouts inside the http.Client transport settings.
* If lock contention is high, increase the number of worker instances to distribute the lookup load, or scale horizontal replica nodes.
* Force dynamic garbage collection if needed to release pages to the operating system:
```go
// Trigger manual GC during incident debugging
runtime.GC()
```

---

## 11. Production Case Study & Real-World Outage Analysis

This section analyzes real-world system outages caused by concurrency design failures, details the post-mortem investigations, and traces the structural fixes applied.

### 1. Incident Timeline
* **09:12 UTC**: Prometheus alerts fire for latency spikes ($p99$ response times increase from 50ms to 8.2s).
* **09:15 UTC**: Memory usage on session servers climbs in a steep linear staircase pattern, triggering OOM (Out of Memory) kills.
* **09:20 UTC**: Auto-scaling spawns new instances, which saturate and crash within 90 seconds of receiving traffic.
* **09:30 UTC**: SRE runs a manual stack dump and identifies thousands of goroutines blocked in the scheduler.

### 2. Post-Mortem Investigation & Root Cause
By inspecting the stack dump file (`stacks.txt`), engineers located the deadlock trace:
```
goroutine 14302 [chan send]:
pkg/services/session.FetchSessionData(0xc00018a3e0, 0x1)
    /src/pkg/services/session/session.go:44 +0x80
```
* **The Root Cause**: The request handler used a timeout mechanism, returning immediately if a downstream session query took longer than 100ms.
* However, the background goroutine querying the database was writing its output to an **unbuffered channel**.
* Once the handler timed out and returned, no receiver was listening to the channel.
* The query worker attempted to write the data payload to the channel, blocking permanently.
* This blocked goroutine pinned its execution stack, local variables, and database connection pools in memory.
* As request rates increased, memory usage climbed until the server crashed.

### 3. Immediate Mitigation and Long-Term Remediation
To recover the system during the outage:
* SRE rolled back the deployment to the previous stable release to clear active connections.
* The unbuffered channel `make(chan SessionResult)` was refactored to a buffered channel of capacity 1: `make(chan SessionResult, 1)`.
* This allowed the background worker to write its result to the buffer and exit immediately, preventing worker leaks regardless of handler timeouts.
* Static analysis checks were added to the CI/CD pipeline to flag any channel creation without explicit capacity checks.

---

## 12. Code Review Checklist & Concurrency Audit Guide

Use this checklist during pull request reviews to audit concurrent code modifications for safety, resource leaks, and execution efficiency.

### 1. Goroutine Safety and Lifetimes
* [ ] **Explicit Lifetime**: Is the lifetime of the spawned goroutine bounded by a parent context or WaitGroup?
* [ ] **Panic Boundary**: Does every background goroutine have an active deferred panic recovery block (`recover()`)?
* [ ] **Stack Size Hygiene**: Does the goroutine copy massive local variables onto its stack? (Check escape analysis reports).

### 2. Channel Communication Patterns
* [ ] **Cap Margins**: For every buffered channel, is the capacity size justified, or is it masking a consumer processing bottleneck?
* [ ] **Unbuffered Handoff**: Does every unbuffered channel have a matching, active reader/writer running concurrently to prevent deadlocks?
* [ ] **Nil and Close**: Are there pathways where a read or write occurs on a `nil` channel, or a write occurs on a closed channel?

### 3. Mutex and State Locking
* [ ] **Locker Scope**: Is the critical section protected by `Lock()` and `Unlock()` as short as possible?
* [ ] **Defer Alignment**: Is `defer mu.Unlock()` called immediately after `mu.Lock()` to prevent lock holding leaks on panics or early returns?
* [ ] **Copy Protection**: Is the struct containing the `Mutex` or `WaitGroup` passed by value (copied), violating state safety?

### 4. Code Review Metric Summary Table
| Audit Target | Expected Pattern | Potential Vulnerability |
|---|---|---|
| **Worker Loops** | Listen to `ctx.Done()` for exit | Infinite loop block leak |
| **Atomics** | Use for primitive mutations | Lack of happens-before memory visibility |
| **Timeouts** | Inject timeout parameters | Permanent connection blocks |\n### Additional Production Case Studies and Engineering Insights
In high-throughput microservices, execution path visibility is critical. When auditing system performance, engineers frequently trace metrics across multiple endpoints. 
* Always monitor resource utilization patterns during traffic bursts.
* Ensure thread counts do not exceed pool limits under simulated network failures.
* Establish baseline metrics in staging environments before rolling out concurrency changes to production clusters.
* Use distributed tracing tools (e.g., OpenTelemetry, Jaeger) to identify bottleneck propagation across RPC boundaries.
* Document system topology diagrams and share them with the operations team to facilitate incident triage.

```
  [Ingress HTTP Traffic] ----> [Distributed Rate Limiter] ----> [Service Worker Nodes]
                                                                        |
                                                           [Prometheus Metrics Export]
```

#### Incident Recovery Strategy
1. **Isolate Node**: Immediately route traffic away from the failing instance.
2. **Collect Heap Dumps**: Extract runtime statistics for offline memory leak analysis.
3. **Graceful Restart**: Restart the service to release system descriptors.
4. **Log Analysis**: Verify error counts returned by downstream query pools.\n