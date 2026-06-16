# Module 5 — Synchronization Primitives

## Metadata
* **Estimated Study Time:** 4 hours
* **Prerequisites:** Module 4
* **Learning Outcomes:**
  * Master `sync.WaitGroup` counters and avoid order dependency races.
  * Understand the internals of `sync.Mutex` (Normal vs Starvation modes).
  * Use `sync.RWMutex` correctly and understand when it degrades performance.
  * Implement lazy initialization safely using `sync.Once`.
  * Coordinate goroutines with `sync.Cond` condition variables.
  * Use the `sync/atomic` package for high-speed lock-free operations.

---

## 1. When Channels are Not Enough

Go's primary concurrency philosophy is CSP-based message passing. However, dogmatically using channels for everything can introduce performance overhead and code complexity.

### Channels vs Mutexes
* **Use Channels** when you need to orchestrate execution flow, pass ownership of data, distribute tasks, or coordinate lifecycle signals (e.g., cancellations).
* **Use Mutexes** when you need to protect a shared memory structure (like an in-memory cache, counters, or maps) where the execution logic is local, immediate, and does not block on external I/O.

Channels involve scheduler context switches, ring-buffer locks, and memory allocations. A `sync.Mutex` uses atomic CPU instructions, making it significantly faster for simple data mutations.

---

## 2. sync.WaitGroup

A `sync.WaitGroup` coordinates execution by blocking a goroutine until a collection of other spawned goroutines completes.

### The Internals
A `WaitGroup` contains a 64-bit value that acts as a counter.
* `Add(n)` increases the counter atomically.
* `Done()` decrements the counter.
* `Wait()` blocks until the counter reaches zero.

### Two Critical Rules
1. **Never Copy a WaitGroup**: A `WaitGroup` contains state. If you pass it by value to a function, it copies the internal counter, causing the goroutines to update different counters. This leads to a deadlock. Always pass it **by pointer** (`*sync.WaitGroup`).
2. **Add Before You Go**: Always call `Add(1)` in the parent goroutine *before* spawning the child goroutine with `go`. If you call `Add(1)` inside the child goroutine, the scheduler might execute `Wait()` in the parent before the child starts and increments the counter, causing the parent to return immediately.

```go
// Bad Pattern: Race Condition!
for i := 0; i < 5; i++ {
    go func() {
        wg.Add(1) // Too late! Wait() might run before this executes.
        defer wg.Done()
        // work
    }()
}
wg.Wait()
```

---

## 3. sync.Mutex Internals: Normal vs Starvation Modes

A Go Mutex is highly optimized to avoid thread blocking costs. It operates in two modes:

### Normal Mode
Lock requests are lined up in a FIFO queue. However, when a waiting goroutine is woken up to acquire the lock, it does not get it automatically. It competes directly against newly arriving goroutines that are currently executing on the CPU.
* **Advantage**: High throughput. Arriving threads are already running and can acquire the lock immediately, avoiding context switches.
* **Disadvantage**: Starvation. If a queue of waiters is long, and new threads keep arriving, a waiting thread might remain blocked for a long time.

### Starvation Mode
If a waiting goroutine fails to acquire the lock for more than **1 millisecond**, the Mutex shifts to **Starvation Mode**.
* **Advantage**: Fairness. Arriving threads do not attempt to acquire the lock and are queued directly at the tail. The lock is handed off directly from the unlocking thread to the waiter at the head of the queue.
* **Disadvantage**: Lower throughput. Every lock transition requires a thread context switch.
* **Recovery**: The Mutex returns to normal mode once the waiting queue is empty or a waiter's queue latency drops below 1ms.

---

## 4. sync.RWMutex

A reader-writer lock allows multiple readers to acquire the lock concurrently, but only a single writer can hold it.

### RWMutex Trade-off
* **Use Case**: Read-heavy caches where writes occur infrequently (<5-10% of operations).
* **When it hurts performance**: If reads are extremely fast (e.g., looking up a key in a map that takes 10ns), the atomic operations required to track the reader count on the `RWMutex` cause the CPU cache line containing the lock state to constantly bounce between cores. In this scenario, a standard `sync.Mutex` often outperforms `sync.RWMutex`.

---

## 5. sync.Once

`sync.Once` guarantees that a function is executed exactly once, regardless of how many concurrent goroutines attempt to run it. It is commonly used for lazy initialization of database connections or caches.

### Under the Hood
`sync.Once` uses a double-checked locking pattern:
```go
type Once struct {
    done uint32
    m    Mutex
}
```
1. It performs a fast atomic check on `done` (`atomic.LoadUint32`).
2. If `done == 0`, it acquires the Mutex, checks again, executes the function, and sets `done` to `1` atomically.
3. Subsequent calls bypass the Mutex entirely, making it extremely fast.

---

## 6. sync.Cond (Condition Variables)

`sync.Cond` implements a condition variable. It acts as a meeting point for goroutines waiting for or announcing a state change. It always requires an associated locking primitive (`L`).

### Methods
* `Wait()`: Atomically unlocks `L` and suspends the goroutine. When woken up, it re-acquires `L` before returning.
* `Signal()`: Wakes up the goroutine that has been waiting the longest.
* `Broadcast()`: Wakes up all waiting goroutines.

> [!WARNING]
> **Spurious Wakeups**: Always call `Wait()` inside a `for` loop checking the condition state, never an `if` statement. Goroutines can wake up spuriously without a signal being sent.

```go
cond.L.Lock()
for !stateReady { // Loop, not IF
    cond.Wait()
}
// Do work...
cond.L.Unlock()
```

---

## 7. The `sync/atomic` Package

Atomics provide low-level lock-free operations executed directly by hardware instructions (e.g., CAS).

### Compare-And-Swap (CAS)
CAS compares the value at a memory address to an expected value. If they match, it replaces the value with a new one. It returns `true` on success.

```go
package main

import (
	"fmt"
	"sync/atomic"
)

func main() {
	var count int32 = 10

	// Compare count with 10. If equal, set to 20
	swapped := atomic.CompareAndSwapInt32(&count, 10, 20)
	fmt.Printf("Swapped: %t, Value: %d\n", swapped, count)

	// This attempt will fail because count is now 20
	swapped = atomic.CompareAndSwapInt32(&count, 10, 30)
	fmt.Printf("Swapped: %t, Value: %d\n", swapped, count)
}
```

---

## 8. Hands-on: Building a Thread-Safe Memory Cache

Let's build a thread-safe local cache using a `sync.RWMutex` to allow concurrent reading while ensuring safe single-writer access.

Create `practice/sync_primitives/main.go` and write:

```go
package main

import (
	"fmt"
	"sync"
	"time"
)

type SafeCache struct {
	mu   sync.RWMutex
	data map[string]string
}

func NewSafeCache() *SafeCache {
	return &SafeCache{
		data: make(map[string]string),
	}
}

func (c *SafeCache) Set(key, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.data[key] = value
}

func (c *SafeCache) Get(key string) (string, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	val, ok := c.data[key]
	return val, ok
}

func main() {
	cache := NewSafeCache()
	var wg sync.WaitGroup

	// Start 5 writers
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			cache.Set(fmt.Sprintf("key-%d", id), fmt.Sprintf("value-%d", id))
			time.Sleep(10 * time.Millisecond)
		}(i)
	}

	// Start 10 readers
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			for j := 0; j < 3; j++ {
				val, found := cache.Get("key-2")
				if found {
					fmt.Printf("Reader %d read key-2 = %s\n", id, val)
				} else {
					fmt.Printf("Reader %d read key-2 = Not Found\n", id)
				}
				time.Sleep(5 * time.Millisecond)
			}
		}(i)
	}

	wg.Wait()
	fmt.Println("All operations finished.")
}
```

---

## 9. Exercises

### Exercise 1: WaitGroup copy bug
Run the code below and observe the compiler/runtime warning. Fix it.
```go
package main

import (
	"fmt"
	"sync"
)

func worker(id int, wg sync.WaitGroup) { // BUG
	defer wg.Done()
	fmt.Println(id)
}

func main() {
	var wg sync.WaitGroup
	for i := 0; i < 3; i++ {
		wg.Add(1)
		go worker(i, wg)
	}
	wg.Wait()
}
```

### Exercise 2: Mutex vs Atomics Benchmark
Write a benchmark testing an increment operation performed inside a loop run concurrently. Compare the speed of acquiring a `sync.Mutex` against using `atomic.AddInt64`.

---

## 10. Exercise Solutions

### Solution 1: WaitGroup copy fix
Pass the `WaitGroup` by pointer `*sync.WaitGroup` to avoid copying:
```go
package main

import (
	"fmt"
	"sync"
)

func worker(id int, wg *sync.WaitGroup) {
	defer wg.Done()
	fmt.Println(id)
}

func main() {
	var wg sync.WaitGroup
	for i := 0; i < 3; i++ {
		wg.Add(1)
		go worker(i, &wg)
	}
	wg.Wait()
}
```

### Solution 2: Benchmark comparison snippet
Create a file `bench_test.go`:
```go
package main

import (
	"sync"
	"sync/atomic"
	"testing"
)

func BenchmarkMutex(b *testing.B) {
	var mu sync.Mutex
	var count int64 = 0

	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			mu.Lock()
			count++
			mu.Unlock()
		}
	})
}

func BenchmarkAtomic(b *testing.B) {
	var count int64 = 0

	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			atomic.AddInt64(&count, 1)
		}
	})
}
```
Run `go test -bench=.`. You will find the atomic implementation is significantly faster due to execution directly at the CPU instruction register level.
---

## 11. Advanced Deep Dive: CPU Cache Coherence (MESI) and Instruction Pipelines

### The MESI Cache Coherence Protocol
To coordinate data visibility across multi-core processors, CPUs use cache coherence protocols. The most common is **MESI** (Modified, Exclusive, Shared, Invalid):
* **Modified (M)**: The cache line is present only in the current cache and contains modified data (dirty).
* **Exclusive (E)**: The cache line is present only in the current cache and matches main memory (clean).
* **Shared (S)**: The cache line is present in other caches and matches main memory.
* **Invalid (I)**: The cache line does not contain valid data.

When a goroutine modifies a counter using `sync/atomic` (e.g., `atomic.AddInt64`):
1. The core executes a locked hardware instruction (like `LOCK XADD` on x86).
2. The CPU core invalidates the cache line across all other CPU cores, shifting their cache lines containing the counter address to the **Invalid (I)** state.
3. The writing core updates its local cache line, setting it to **Modified (M)**.
4. When other cores attempt to read the counter, they experience a cache miss, forcing them to reload the updated cache line from the writer's cache.

This cycle, known as **Cache Line Bouncing**, degrades performance if multiple threads write to the same memory location concurrently.

### Memory Ordering and Fences
CPUs execute instructions out-of-order to maximize throughput. They use **Memory Fences** (or barriers) to enforce ordering. Atomics insert memory barriers, preventing the CPU from reordering instructions across the synchronization boundary.

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