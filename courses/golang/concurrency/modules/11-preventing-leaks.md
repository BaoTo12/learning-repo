# Module 11 — Preventing Goroutine Leaks

## Metadata
* **Estimated Study Time:** 2 hours
* **Prerequisites:** Module 10
* **Learning Outcomes:**
  * Define what a Goroutine Leak is and explain its symptoms.
  * Audit code for common leak triggers (blocked sends, blocked receives, loops).
  * Use `runtime.NumGoroutine()` and stack dumps to identify leaked goroutines.
  * Diagnose leak states using heap profiling.
  * Integrate `goleak` into your unit testing framework.

---

## 1. What is a Goroutine Leak?

A **Goroutine Leak** occurs when you spawn a goroutine that blocks permanently (e.g., trying to read from a channel that will never receive data, or writing to a channel that will never be read).

### The GC Reality: Goroutines are GC Roots
In Go, the Garbage Collector (GC) automatically reclaims unused heap memory. However, the GC **does not garbage collect active goroutines**. 
* Any goroutine that is in a waiting state (e.g., blocked on a channel read, a lock, or a socket read) is treated as a **GC Root**.
* This means the goroutine's 2KB stack, any variables allocated on that stack, and all heap objects referenced by variables in the goroutine's closure are **pinned in memory forever**.

If your server leaks just one goroutine per user request, and the server receives 10,000 requests per hour, it will leak 10,000 goroutines (~20MB of RAM) every hour. Eventually, the operating system will terminate the process with an **Out Of Memory (OOM)** crash.

---

## 2. Common Leak Scenarios

### Scenario A: Send to Unbuffered Channel without Reader
A request handler spawns a background worker to query data. The handler times out and returns early. The worker completes its query and tries to write to the channel, but the reader has already left.

```go
func QueryAPI() string {
	ch := make(chan string) // Unbuffered!
	
	go func() {
		data := fetchFromNetwork()
		ch <- data // Blocks here forever if parent times out and returns!
	}()

	select {
	case res := <-ch:
		return res
	case <-time.After(50 * time.Millisecond):
		return "timeout" // Returns, leaving worker blocked in sendq
	}
}
```
* **The Fix**: Use a buffered channel: `ch := make(chan string, 1)`. The worker can write its result to the buffer and exit immediately, even if the parent has returned.

### Scenario B: Read from Nil Channel
Reading from a `nil` channel blocks the goroutine forever.
```go
var ch chan int // declared but not initialized with make()
go func() {
    val := <-ch // Blocks forever!
    fmt.Println(val)
}()
```

### Scenario C: Infinite Loops without Stop Signals
A background daemon processes tasks in a loop but has no channel listening for a cancellation signal.
```go
func startWorker(jobs <-chan int) {
    go func() {
        for j := range jobs {
            process(j)
        }
        // If the jobs channel is never closed, this loop remains blocked in recvq!
    }()
}
```

---

## 3. Diagnostic Techniques

### Method 1: Monitoring `runtime.NumGoroutine()`
Track goroutine counts at runtime. If the count grows continually under load without ever returning to a baseline, your system is leaking.

```go
fmt.Println("Active Goroutines:", runtime.NumGoroutine())
```

### Method 2: Inspecting Stack Dumps
You can force a Go process to dump its active stacks by sending a `SIGQUIT` signal to the process on Unix-like operating systems:
```bash
kill -3 <pid>
```
This prints the stack trace of every active goroutine to stdout. If you see hundreds of goroutines blocked on `chanrecv` or `chansend`, you have found your leak.

You can also retrieve stack dumps programmatically:
```go
import "runtime/pprof"
pprof.Lookup("goroutine").WriteTo(os.Stdout, 1)
```

---

## 4. Hands-on: Detecting Leaks in Unit Tests using `uber-go/goleak`

The `goleak` library parses the active goroutines before and after a test executes. If it detects any new, unexpected goroutines running after the test completes, the test fails.

### Setting Up the Test

Create `practice/leaks/leak_test.go` and write:

```go
package leaks

import (
	"testing"
	"time"

	"github.com/uber-go/goleak"
)

func LeakingWorker() {
	ch := make(chan int) // Unbuffered
	go func() {
		ch <- 99 // Blocks forever: no one reads from ch
	}()
}

func TestWorkerLeak(t *testing.T) {
	// VerifyNone checks for leaks at the end of the test execution
	defer goleak.VerifyNone(t)

	LeakingWorker()
	
	// Give time for the goroutine to spawn and block
	time.Sleep(10 * time.Millisecond)
}
```

### Running the Test
To download the goleak package and run the test:
```bash
go get github.com/uber-go/goleak
go test -v practice/leaks/leak_test.go
```
The test will fail and output the stack trace of the leaked goroutine:
```
leak_test.go:17: found unexpected goroutines:
    [Identified Goroutine]
    goroutine 20 [chan send]:
    practice/leaks.LeakingWorker.func1()
        C:/projects/learning-repo/practice/leaks/leak_test.go:12 +0x30
```

### Fixing the Leak
Change `ch := make(chan int)` in `LeakingWorker` to `ch := make(chan int, 1)`. Re-run `go test` and observe the test passes successfully.

---

## 5. Exercises

### Exercise 1: Clean Connection Pool Shutdown
Explain how a database connection pool struct with background checkup workers (daemons checking for idle connections in a loop) can leak goroutines when the pool is closed. Write a strategy to clean up those workers.

### Exercise 2: Implementing a Safe Timeout Pipeline Stage
Given a pipeline stage that reads from an input channel and writes to an output channel, implement a cancellation check that guarantees the stage immediately returns and closes all channels if the context is cancelled, preventing worker leaks.

---

## 6. Exercise Solutions

### Solution 1: Connection Pool Daemon Shutdown
* **The Leak**: The pool struct is released by the garbage collector, but the background daemon loop is still running `time.Sleep` and checking connection lists, keeping the memory pinned.
* **The Strategy**:
  1. Add a `closeChan chan struct{}` or a `context.Context` to the pool struct.
  2. The pool's `Close()` method calls `close(closeChan)` or the context's `cancel()`.
  3. The daemon checks `select { case <-closeChan: return; default: }` on every loop cycle.

### Solution 2: Safe Pipeline Stage Implementation
```go
package main

import (
	"context"
	"fmt"
	"time"
)

func safeStage(ctx context.Context, in <-chan int) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for {
			select {
			case <-ctx.Done():
				return // Abort worker loop
			case val, ok := <-in:
				if !ok {
					return // Input channel closed
				}
				select {
				case out <- val * 2:
				case <-ctx.Done():
					return // Abort if blocked sending to output
				}
			}
		}
	}()
	return out
}

func main() {
	in := make(chan int)
	ctx, cancel := context.WithCancel(context.Background())

	out := safeStage(ctx, in)

	in <- 10
	fmt.Println("Received:", <-out)

	cancel() // Shut down stage worker
	time.Sleep(10 * time.Millisecond) // Let output channel close
	
	// Check if out channel is closed
	val, ok := <-out
	fmt.Printf("Channel closed: Value=%d, Open=%t\n", val, ok)
}
```
---

## 7. Advanced Deep Dive: Profiling and Resolving Complex Leak Topologies

### Detecting Leaks with Stack Dump Auditing
When diagnosing goroutine leaks in production:
1. Collect a stack trace:
   ```bash
   curl http://localhost:6060/debug/pprof/goroutine?debug=2 > stacks.txt
   ```
2. Parse `stacks.txt`. Group identical stack traces.
3. If you see thousands of goroutines blocked at `chanrecv` inside a database call, you have found a leak.

### The Leak-Safe Worker Strategy
Always ensure that every worker loop checking input channels has an exit condition linked to a stop signal or context cancellation, preventing hanging workers.

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