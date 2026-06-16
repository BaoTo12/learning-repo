# Module 17 — Common Anti-Patterns

## Metadata
* **Estimated Study Time:** 2 hours
* **Prerequisites:** Module 16
* **Learning Outcomes:**
  * Audit code for the "Goroutine-per-everything" anti-pattern and implement bounding.
  * Contrast when to use `sync.Mutex` vs channels as locks.
  * Identify and refactor "Busy Waiting" spin loops.
  * Protect servers from process crashes due to unhandled panics in background workers.
  * Recognize RWMutex abuse in high-frequency cache reads.

---

## 1. Unbounded Concurrency (Goroutine-per-Everything)

### Why Developers Do It
Go goroutines are lightweight (~2KB). New Go developers often assume they can spawn millions of goroutines without consequence:
```go
// Anti-Pattern: Unbounded Spawning
func processAll(items []string) {
	for _, item := range items {
		go process(item) // Spawns infinitely without constraints
	}
}
```

### Why It Fails
If `items` contains 1,000,000 files, this spawns 1,000,000 goroutines.
* Each goroutine opens a file descriptor, exhausting the operating system's limits and crashing with `too many open files`.
* Under memory stress, the heap swells, triggering garbage collection thrashing that degrades performance.

### The Remedy
Bound your concurrency using a worker pool or a channel semaphore:
```go
func processAllBounded(items []string) {
	sem := make(chan struct{}, 100) // Max 100 concurrent tasks
	for _, item := range items {
		sem <- struct{}{}
		go func(it string) {
			defer func() { <-sem }()
			process(it)
		}(item)
	}
}
```

---

## 2. Using Channels as Locks

### Why Developers Do It
Because of the CSP advice ("share memory by communicating"), developers use a buffered channel of size 1 as a mutual exclusion lock:
```go
// Anti-Pattern: Channel as lock
type LockedCache struct {
	lock chan struct{}
	data map[string]string
}

func (c *LockedCache) Set(k, v string) {
	c.lock <- struct{}{} // Acquire lock
	c.data[k] = v
	<-c.lock            // Release lock
}
```

### Why It Fails
* **Performance**: Sending and receiving to a channel requires allocating `sudog` metadata, acquiring internal locks, and switching scheduler state under load. It runs 3x to 5x slower than a native `sync.Mutex`.
* **Readability**: It is less explicit than calling `mu.Lock()`.

### The Remedy
Use the correct tool for the job. Protect in-memory data maps using a standard `sync.Mutex`.

---

## 3. Busy Waiting (Spin-locks)

### Why Developers Do It
Waiting for a background task to complete or a state flag to flip by running an empty loop:
```go
// Anti-Pattern: Spin Lock
for !ready {
    // Wastes CPU cycles doing nothing!
}
```

### Why It Fails
This loop hogs 100% of a CPU core, generating heat and starving other goroutines on that processor $P$ from getting execution time (especially on pre-Go 1.14 schedulers).

### The Remedy
Use synchronization channels, condition variables, or wait groups:
```go
// Good Pattern: Block wait
<-readyChan // Blocks without consuming CPU cycles
```

---

## 4. Unhandled Panics in Background Goroutines

### Why Developers Do It
Spawning background goroutines to handle side-effects without error boundary checks:
```go
// Anti-Pattern: Vulnerable background task
func handleUser(user User) {
	go func() {
		saveLog(user.ID) // What happens if this panics?
	}()
}
```

### Why It Fails
In Go, an unrecovered panic inside **any** goroutine crashes the entire OS process. If `saveLog` panics, your web server, database pool, and all active user request connections crash instantly.

### The Remedy
Always implement a defer recovery block in background workers:
```go
func handleUserSafe(user User) {
	go func() {
		defer func() {
			if r := recover(); r != nil {
				log.Printf("[RECOVERY] Panic prevented in background task: %v", r)
			}
		}()
		saveLog(user.ID)
	}()
}
```

---

## 5. Exercises

### Exercise 1: RWMutex Cache Contention
Explain how a read-heavy local cache protected by a `sync.RWMutex` can perform *worse* than a standard `sync.Mutex` on a 64-core system when the cached item reads take less than 10 nanoseconds.

### Exercise 2: Refactoring Unhandled Pipeline Failures
Refactor the following loop to prevent goroutines from leaking if a file query throws an error:
```go
func QueryFiles(paths []string) error {
	ch := make(chan string)
	for _, p := range paths {
		go func(path string) {
			res, err := query(path)
			if err != nil {
				// How do we return this error safely without leaks?
			}
			ch <- res
		}(p)
	}
	return nil
}
```

---

## 6. Exercise Solutions

### Solution 1: Cache Line Bouncing
* **Why it occurs**: Every time a reader acquires `RLock()`, the runtime must atomically increment the reader count inside the `RWMutex` structure.
* On a 64-core system, this single counter's cache line must bounce between the L1/L2 caches of all active CPU cores. The atomic CAS modification cost of cache validation dominates the execution, making concurrent reads slower than serial execution.
* **Optimization**: Shard the cache into 32 separate maps, each with its own mutex, to distribute atomic access.

### Solution 2: Pipeline Refactoring with errgroup
Use `errgroup` to handle errors and coordinate worker lifetimes:
```go
package main

import (
	"context"
	"fmt"
	"golang.org/x/sync/errgroup"
)

func query(path string) (string, error) {
	if path == "bad.txt" {
		return "", fmt.Errorf("invalid path: %s", path)
	}
	return fmt.Sprintf("Data from %s", path), nil
}

func QueryFiles(paths []string) ([]string, error) {
	g, _ := errgroup.WithContext(context.Background())
	results := make([]string, len(paths))

	for i, p := range paths {
		i, p := i, p
		g.Go(func() error {
			res, err := query(p)
			if err != nil {
				return err // Aborts group automatically
			}
			results[i] = res
			return nil
		})
	}

	if err := g.Wait(); err != nil {
		return nil, err
	}
	return results, nil
}

func main() {
	paths := []string{"file1.txt", "bad.txt", "file2.txt"}
	res, err := QueryFiles(paths)
	if err != nil {
		fmt.Println("Error:", err)
	} else {
		fmt.Println("Success:", res)
	}
}
```
---

## 7. Advanced Deep Dive: Remediation Metrics

Always track system performance metrics before and after refactoring anti-patterns. Compare heap allocations, CPU usage, and context switch rates.

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