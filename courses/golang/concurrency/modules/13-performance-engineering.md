# Module 13 — Performance Engineering

## Metadata
* **Estimated Study Time:** 4 hours
* **Prerequisites:** Module 12
* **Learning Outcomes:**
  * Write parallel benchmarks using the Go testing framework.
  * Compare benchmark metrics using the `benchstat` tool.
  * Collect and analyze CPU, heap, block, and mutex profiles.
  * Resolve lock contention and channel blocking bottlenecks.
  * Navigate Go execution traces with `go tool trace` to inspect thread scheduling.

---

## 1. Concurrent Benchmarking

You cannot optimize what you do not measure. Go includes benchmarking capabilities within the standard `testing` package.

### Writing Parallel Benchmarks
Use the `RunParallel` helper to benchmark code executed concurrently across all available CPU cores.

```go
package main

import (
	"sync"
	"testing"
)

func BenchmarkSharedMutex(b *testing.B) {
	var mu sync.Mutex
	count := 0

	// RunParallel spawns goroutines to match GOMAXPROCS
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			mu.Lock()
			count++
			mu.Unlock()
		}
	})
}
```

Run the benchmark using the go toolchain:
```bash
go test -bench=BenchmarkSharedMutex -benchmem
```

---

## 2. Using `benchstat` for Scientific Comparisons

When optimizing code, you must verify if your changes actually improve performance or if the variance is noise. **`benchstat`** is an official Go tool that compares multiple benchmark runs and calculates statistical significance.

### How to use `benchstat`
1. Install the tool:
   ```bash
   go install golang.org/x/perf/cmd/benchstat@latest
   ```
2. Run your old code benchmarks and save the output to a file:
   ```bash
   go test -bench=. -count=5 > old.txt
   ```
3. Apply your optimizations, run the benchmarks again, and save to a new file:
   ```bash
   go test -bench=. -count=5 > new.txt
   ```
4. Compare them:
   ```bash
   benchstat old.txt new.txt
   ```
   The tool outputs the percentage change in execution speed and memory allocations, along with the statistical significance (p-value).

---

## 3. Profiling with `pprof`

Go processes can be profiled dynamically at runtime. The profile data is exposed via HTTP endpoint hooks or saved directly to files.

### Profiling Categories
* **CPU Profile**: Identifies where the CPU spends its time.
* **Heap Profile**: Identifies memory allocation hot-spots.
* **Block Profile**: Identifies where goroutines spend time blocked waiting on channels, network sockets, or filesystem I/O.
* **Mutex Profile**: Measures lock contention: how much time goroutines spend waiting to acquire a `sync.Mutex` or `sync.RWMutex`.

### Enabling Profiling via HTTP
In your server's `main.go`, import the blank initialization package:

```go
import _ "net/http/pprof"

func main() {
    // Start a dedicated diagnostic server in the background
    go func() {
        log.Println(http.ListenAndServe("localhost:6060", nil))
    }()
    
    // Your main server code...
}
```

### Collecting Profiles
To profile a running server:
1. **CPU Profile (30 seconds)**:
   ```bash
   go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30
   ```
2. **Heap Profile**:
   ```bash
   go tool pprof http://localhost:6060/debug/pprof/heap
   ```
3. **Block Profile**:
   ```bash
   go tool pprof http://localhost:6060/debug/pprof/block
   ```
4. **Mutex Profile**:
   ```bash
   go tool pprof http://localhost:6060/debug/pprof/mutex
   ```

### Analyzing with the Web GUI
Add the `-http` flag to open an interactive visualization interface (including flame graphs, top functions list, and source code annotations):
```bash
go tool pprof -http=:8080 cpu.pprof
```

---

## 4. Execution Tracing

While `pprof` gives you summary statistics, the **Go Execution Tracer** records a log of runtime scheduler events over time. This lets you visualize when goroutines wake up, context switch, run on physical threads, or trigger GC cycles.

### Collecting Trace Data
Write a trace to a file from a test execution:
```bash
go test -trace=trace.out ./...
```
Or collect it from the pprof HTTP server:
```bash
curl -o trace.out http://localhost:6060/debug/pprof/trace?seconds=5
```

### Visualizing the Trace
Open the tracer in your web browser:
```bash
go tool trace trace.out
```

```
                 [ Go Trace Web Interface ]
  - View Goroutine Analysis: traces execution latency.
  - View Network Blocking Profile: identifies socket bottlenecks.
  - View Scheduler Latency Profile: shows delays in local queues.
```

The trace interface provides a gantt chart showing every logical processor $P$ and which goroutines were running on them at any millisecond. This is useful for identifying **thread scheduling gaps** and thread synchronization blocking states.

---

## 5. Exercises

### Exercise 1: Lock Contention Resolution
Analyze the heap and mutex profiles of a concurrent program that processes logs by appending them to a shared slice protected by a single Mutex. Explain how lock contention degrades throughput as the thread count increases.

### Exercise 2: Tracing GC Pauses
Generate a trace for a program that creates millions of short-lived objects. Use `go tool trace` to inspect when GC runs, how long it pauses execution, and what percentage of CPU cycles are consumed by GC helpers.

---

## 6. Exercise Solutions

### Solution 1: Lock Contention Analysis
* **Why it fails**: As the number of concurrent goroutines increases, the time spent waiting in the queue to acquire the mutex grows exponentially. The CPU spends a large portion of its time context switching and parking/unparking threads rather than performing useful work.
* **Optimizations**:
  1. **Sharding**: Divide the cache or list into multiple shards (e.g., 16 independent slices), each protected by its own lock. Lookups are routed to a shard based on the hash of the key, decreasing contention by $16	ext{x}$.
  2. **Batching**: Workers aggregate logs locally in thread-private memory and only acquire the global lock once every $N$ items to flush them in a single batch operation.

### Solution 2: GC Trace Interpretation
* **Interpretation steps**:
  1. Run `go tool trace trace.out`.
  2. Look at the "Heap" chart. You will see a sawtooth memory pattern.
  3. Look at the "GC" row. When GC starts, you will observe brief slices where all application processors $P$ stop running user code (STW - Stop The World phases) and background workers execute sweep tasks.
  4. Note that if memory allocations are minimized using a `sync.Pool`, the intervals between GC runs will widen, and STW duration will drop, smoothing out the response latency graph.
---

## 7. Advanced Deep Dive: Resolving Bottlenecks in the Scheduler

### Analyzing Run Queue Latency
When you run a trace using `go tool trace`:
1. Look at the "Scheduler Latency" chart. It measures the duration runnable goroutines spend waiting in queues.
2. High latency indicates **scheduler starvation**: too few threads or too many blocking CPU-bound tasks.
3. **Optimizations**: Decrease work sizes, reduce dynamic allocations, or increase `GOMAXPROCS`.

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