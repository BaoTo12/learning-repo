# Module 13: Performance Engineering — JMH, Little's Law & Virtual Thread Benchmarking

**Difficulty:** Advanced
**Estimated Study Time:** 5 hours
**Prerequisites:** All previous modules

---

## Learning Objectives

By the end of this module you will be able to:
- Write correct JMH benchmarks that avoid JIT dead-code elimination and false sharing
- Distinguish throughput benchmarks from latency (percentile) benchmarks
- Apply Little's Law to predict and right-size thread pools
- Measure the performance crossover point between platform threads and virtual threads
- Identify benchmark pitfalls: coordinated omission, warmup inadequacy, measurement noise
- Profile memory allocation in concurrent code using JMH `GC` profiler

---

## 13.1 Why Micro-Benchmarking Is Hard in Java

The JVM does not execute bytecode literally. It applies aggressive optimizations:
1. **JIT compilation**: Hot methods are compiled to native code after ~10,000 invocations
2. **Dead code elimination**: If the result is unused, the JIT removes the entire computation
3. **Loop unrolling and constant folding**: Loops with fixed bounds are often unrolled
4. **Escape analysis**: Objects that don't escape a method may be stack-allocated (no GC pressure)

```java
// This "benchmark" is meaningless — JIT will eliminate the entire loop:
long start = System.nanoTime();
for (int i = 0; i < 1_000_000; i++) {
    int x = i * 2; // Result never used → JIT eliminates this computation entirely
}
long duration = System.nanoTime() - start;
System.out.println(duration); // Will print ~0ns — you measured nothing

// This "benchmark" is still wrong — no warmup, single sample:
long start2 = System.nanoTime();
String result = expensiveMethod(); // Cold code path — JIT hasn't compiled it yet
long duration2 = System.nanoTime() - start2;
// First execution is 10–100x slower than steady-state → misleading result
```

**JMH (Java Microbenchmark Harness)** solves all of these problems automatically.

---

## 13.2 Setting Up JMH

```xml
<!-- pom.xml -->
<dependency>
    <groupId>org.openjdk.jmh</groupId>
    <artifactId>jmh-core</artifactId>
    <version>1.37</version>
</dependency>
<dependency>
    <groupId>org.openjdk.jmh</groupId>
    <artifactId>jmh-generator-annprocess</artifactId>
    <version>1.37</version>
    <scope>provided</scope>
</dependency>

<!-- Build fat JAR for running benchmarks: -->
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-shade-plugin</artifactId>
    <configuration>
        <finalName>benchmarks</finalName>
        <transformers>
            <transformer implementation="org.apache.maven.plugins.shade.resource.ManifestResourceTransformer">
                <mainClass>org.openjdk.jmh.Main</mainClass>
            </transformer>
        </transformers>
    </configuration>
</plugin>
```

```bash
# Build and run:
mvn clean package -q
java -jar target/benchmarks.jar

# Run specific benchmark:
java -jar target/benchmarks.jar ".*AtomicBenchmark.*"

# Run with specific options:
java -jar target/benchmarks.jar -wi 5 -i 10 -f 3 -t 8 ".*CounterBenchmark.*"
# -wi: warmup iterations  -i: measurement iterations  -f: forks  -t: threads
```

---

## 13.3 Writing Correct JMH Benchmarks

### Basic Throughput Benchmark

```java
import org.openjdk.jmh.annotations.*;
import org.openjdk.jmh.infra.Blackhole;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.*;

@BenchmarkMode(Mode.Throughput)   // Measure: operations per second
@OutputTimeUnit(TimeUnit.SECONDS)
@State(Scope.Benchmark)           // One shared state per benchmark run
@Warmup(iterations = 5, time = 1) // 5 warmup iterations (JIT compiles hot paths)
@Measurement(iterations = 10, time = 1) // 10 measurement iterations
@Fork(3)                          // Run in 3 separate JVM processes (eliminates JVM startup bias)
public class CounterBenchmark {

    AtomicLong atomicLong;
    LongAdder longAdder;

    @Setup(Level.Iteration) // Reset before each iteration
    public void setup() {
        atomicLong = new AtomicLong(0);
        longAdder = new LongAdder();
    }

    @Benchmark
    public void atomicLongIncrement() {
        atomicLong.incrementAndGet(); // Result used by JMH internally — not eliminated
    }

    @Benchmark
    public void longAdderIncrement() {
        longAdder.increment();
    }

    // WRONG: returning void when method computes a value → JIT may eliminate computation
    // Fix: use Blackhole or return the value
    @Benchmark
    public long atomicLongGet(Blackhole bh) {
        long val = atomicLong.get();
        bh.consume(val); // Blackhole prevents dead-code elimination
        return val;      // OR: return the value (JMH uses it)
    }
}
```

### Latency (Percentile) Benchmark

```java
@BenchmarkMode(Mode.SampleTime)   // Sample individual operation latencies
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 5, time = 2)
@Measurement(iterations = 10, time = 5)
@Fork(2)
@State(Scope.Benchmark)
public class LockLatencyBenchmark {

    ReentrantLock reentrantLock = new ReentrantLock();
    Object monitor = new Object();

    @Benchmark
    public void reentrantLockLatency() {
        reentrantLock.lock();
        try {
            // Simulate minimal critical section
        } finally {
            reentrantLock.unlock();
        }
    }

    @Benchmark
    public void synchronizedLatency() {
        synchronized (monitor) {
            // Equivalent critical section
        }
    }
}
// JMH outputs p50, p90, p99, p99.9, p99.99 latency percentiles
// This reveals tail latency, which avg/throughput benchmarks hide
```

**Benchmark modes:**

| Mode | Measures | Use when |
| :--- | :--- | :--- |
| `Throughput` | Ops/second | Maximize total work done |
| `AverageTime` | Avg time/op | Average-case performance |
| `SampleTime` | Latency percentiles | Tail latency, SLA compliance |
| `SingleShotTime` | Cold-start time | Startup, first-call cost |
| `All` | Everything above | Comprehensive analysis |

---

## 13.4 Avoiding False Sharing in Benchmarks

```java
// BROKEN: AtomicLong fields from different threads share a cache line
// → false sharing invalidates cache lines between threads → artificially high contention
@State(Scope.Thread)
public class FalseSharingBenchmark {
    long counter1; // Both counters likely on the same 64-byte cache line
    long counter2;
}

// FIXED: Pad fields to separate cache lines
@State(Scope.Thread)
@sun.misc.Contended  // JVM annotation — pads the object to avoid false sharing (JDK internal)
public class PaddedState {
    long counter = 0;
}

// Or: manual padding (portable)
@State(Scope.Thread)
public class ManuallyPaddedState {
    long p1, p2, p3, p4, p5, p6, p7; // 7 × 8 = 56 bytes padding
    volatile long counter = 0;         // 8 bytes — now on its own cache line
    long q1, q2, q3, q4, q5, q6, q7; // Trailing padding
}
```

---

## 13.5 Virtual Threads vs Platform Threads Benchmark

```java
@BenchmarkMode(Mode.Throughput)
@OutputTimeUnit(TimeUnit.SECONDS)
@Warmup(iterations = 3, time = 2)
@Measurement(iterations = 5, time = 3)
@Fork(2)
@State(Scope.Benchmark)
public class VirtualVsPlatformBenchmark {

    @Param({"10", "100", "1000", "10000"}) // Parametrize concurrency level
    int concurrency;

    @Benchmark
    public void platformThreads() throws Exception {
        try (ExecutorService pool = Executors.newFixedThreadPool(concurrency)) {
            runConcurrentTasks(pool, concurrency);
        }
    }

    @Benchmark
    public void virtualThreads() throws Exception {
        try (ExecutorService pool = Executors.newVirtualThreadPerTaskExecutor()) {
            runConcurrentTasks(pool, concurrency);
        }
    }

    private void runConcurrentTasks(ExecutorService executor, int n) throws Exception {
        CountDownLatch latch = new CountDownLatch(n);
        for (int i = 0; i < n; i++) {
            executor.submit(() -> {
                try {
                    Thread.sleep(10); // Simulate I/O-bound work (10ms latency)
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    latch.countDown();
                }
            });
        }
        latch.await();
    }
}
```

**Expected results (I/O-bound, 10ms sleep):**

```
concurrency=10:    Platform ~same as Virtual (both fit in pool)
concurrency=100:   Platform ~same (pool of 100)
concurrency=1000:  Platform degrades (context switching overhead, 1GB stack memory)
concurrency=10000: Platform likely OOM or severe degradation; Virtual: linear throughput
```

**Expected results (CPU-bound, no sleep):**

```
All concurrency levels: Platform ≈ Virtual
(Virtual threads don't yield on CPU work — no benefit over platform threads for CPU-bound tasks)
```

---

## 13.6 Little's Law — Theoretical Thread Pool Sizing

**Little's Law** (from queuing theory):

```
L = λ × W

Where:
  L = Average number of items in the system (concurrent requests)
  λ = Average arrival rate (requests/second)
  W = Average time each item spends in the system (latency in seconds)
```

### Applying Little's Law to Thread Pools

```
Example: Your service must handle:
  λ = 500 requests/second (throughput target)
  W = 200ms average response time (latency, dominated by DB query)

  L = λ × W = 500 req/s × 0.2s = 100 concurrent requests in flight

  Platform thread pool: Need at least 100 threads
  Memory: 100 threads × 1MB stack = 100MB off-heap (reasonable)

New scenario: Service now calls 3 microservices, each 200ms:
  W = 600ms (sequential calls)
  L = 500 × 0.6 = 300 threads needed
  Memory: 300MB

  With virtual threads + parallel calls:
  W_parallel = 200ms (all 3 calls in parallel via StructuredTaskScope)
  L = 500 × 0.2 = 100 virtual threads (same as before)
  Memory: 100 × ~100KB heap = 10MB (10x less than platform thread pool)
```

**Little's Law for pool capacity planning:**

```java
// Predict queue buildup:
// If λ suddenly spikes to 1000 req/s but pool can only handle 500 concurrent:
// L_arrived = 1000 × 0.2 = 200 needed, but pool = 100
// → Excess 100 requests/second queue up → queue grows unbounded → latency grows

// Break-even point: when to add capacity
// At λ=N req/s, W=T seconds: need N×T threads in platform model
// With virtual threads: L = N×T virtual threads (cheap), but DB connections still limited

// Database connection sizing:
// DB query time: 50ms → for 500 req/s: need 500 × 0.05 = 25 DB connections
// This is why HikariCP default pool size 10 is often too small for high-throughput services
double requiredConnections = requestsPerSecond * avgDbTimeSeconds;
```

---

## 13.7 Measuring Coordinated Omission

**Coordinated omission** is a subtle benchmarking flaw: when the system is slow, you measure FEWER samples (because slow responses reduce call rate). The result underestimates tail latency.

```java
// WRONG: Coordinated omission — if response takes 500ms, we only call 2 times/sec
// This hides the latency problem because slow periods have fewer measurements
for (int i = 0; i < 1000; i++) {
    long start = System.nanoTime();
    callService(); // If this takes 500ms, loop runs at 2 iterations/sec
    long latency = System.nanoTime() - start;
    record(latency); // Only 2 samples/sec when service is slow!
}

// CORRECT: Fixed-rate scheduling — measure latency from intended start time
ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(1);
long intervalNs = 1_000_000_000L / targetRatePerSecond; // e.g., 1ms for 1000 RPS
AtomicLong nextStart = new AtomicLong(System.nanoTime());

scheduler.scheduleAtFixedRate(() -> {
    long intendedStart = nextStart.getAndAdd(intervalNs);
    long actualStart = System.nanoTime();
    long schedulingDelay = actualStart - intendedStart; // Track this separately!

    callService();
    long serviceTime = System.nanoTime() - actualStart;

    // Report BOTH: service time AND total response time (including scheduling delay)
    record(serviceTime + schedulingDelay); // True end-to-end latency
}, 0, intervalNs, TimeUnit.NANOSECONDS);

// Better: Use HdrHistogram (HDR = High Dynamic Range) for correct latency recording
// HdrHistogram is specifically designed to handle coordinated omission:
// https://github.com/HdrHistogram/HdrHistogram
```

---

## 13.8 JMH Profilers for Concurrency Analysis

```java
// Run JMH with built-in profilers:

// GC pressure profiler (measures allocation rate and GC time):
// java -jar benchmarks.jar -prof gc ".*MyBenchmark.*"
// Output includes:
//   gc.alloc.rate:   MB/sec allocated (high = GC pressure)
//   gc.count:        GC events during benchmark
//   gc.time:         Total GC pause time

// Stack profiler (async-profiler integration):
// java -jar benchmarks.jar -prof async:output=flamegraph ".*MyBenchmark.*"
// Generates flame graph showing where CPU time is spent

// Linux perf profiler (hardware PMU counters):
// java -jar benchmarks.jar -prof perfasm ".*MyBenchmark.*"
// Shows assembly-level hotspots including cache misses and CAS retries

// JFR profiler:
// java -jar benchmarks.jar -prof jfr ".*MyBenchmark.*"
// Generates a .jfr file per benchmark run
```

---

## 13.9 Benchmark: Lock Contention Crossover Point

```java
// At what contention level does StampedLock optimistic read beat ReentrantReadWriteLock?
@BenchmarkMode(Mode.Throughput)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@State(Scope.Benchmark)
@Warmup(iterations = 5, time = 1)
@Measurement(iterations = 10, time = 1)
@Fork(3)
public class LockCrossoverBenchmark {

    // Workload: 90% reads, 10% writes
    @Param({"1", "4", "8", "16", "32"}) int threads;

    private double x = 1.0, y = 1.0;
    private final StampedLock stampedLock = new StampedLock();
    private final ReentrantReadWriteLock rwLock = new ReentrantReadWriteLock();

    @Benchmark
    @Threads(1) // JMH @Threads doesn't accept @Param — parametrize differently in practice
    public double stampedOptimisticRead() {
        long stamp = stampedLock.tryOptimisticRead();
        double cx = x, cy = y;
        if (!stampedLock.validate(stamp)) {
            stamp = stampedLock.readLock();
            try { cx = x; cy = y; } finally { stampedLock.unlockRead(stamp); }
        }
        return Math.sqrt(cx * cx + cy * cy);
    }

    @Benchmark
    public double rrwLockRead() {
        rwLock.readLock().lock();
        try { return Math.sqrt(x * x + y * y); }
        finally { rwLock.readLock().unlock(); }
    }
}
// Expected: StampedLock wins at low write contention (< 5% writes)
//           RRW comparable or better at moderate write contention (> 20% writes)
```

---

## 13.10 Production Performance Checklist

```
Before tuning:
  [ ] Do you have a baseline measurement? (Cannot improve what you cannot measure)
  [ ] Is the bottleneck actually concurrency? (Profile first — may be GC, DB, or network)
  [ ] Are you measuring steady-state? (JIT warms up after ~10,000 invocations)

Thread pool sizing:
  [ ] Calculated L = λ × W for your traffic pattern?
  [ ] Is the bottleneck CPU-bound or I/O-bound?
      CPU-bound: pool_size ≈ CPU_cores (no more)
      I/O-bound: pool_size = λ × W (scale with response time)
  [ ] Using virtual threads for I/O-bound tasks?
  [ ] Database connection pool sized via Little's Law? (connections = λ × db_time)

Lock contention:
  [ ] Lock critical sections are as short as possible?
  [ ] No blocking I/O inside synchronized blocks?
  [ ] ConcurrentHashMap instead of synchronized HashMap?
  [ ] LongAdder instead of AtomicLong for high-write-rate counters?
  [ ] StampedLock for read-heavy shared state?

Virtual thread specific:
  [ ] No synchronized blocks in hot paths? (Causes carrier thread pinning)
  [ ] ThreadLocal usage minimized? (Replace with ScopedValue)
  [ ] Database connection pool properly throttled? (Semaphore + small pool)
  [ ] HTTP client is virtual-thread friendly? (Use java.net.http.HttpClient)
```

---

## 13.11 Interview-Style Questions

**Q: What is coordinated omission and how does it affect latency measurements in concurrent systems?**

> Coordinated omission is a systematic underreporting of tail latency in benchmarks and load tests. It occurs when the measurement tool only generates a new request after the previous one completes. When the system slows down (high latency), fewer requests are sent per second — meaning fewer samples are collected during the slow period. The result: the 99th percentile looks acceptable because you simply measured less during the slow periods. In a real production system, requests arrive at a fixed rate regardless of response time — so queue buildup during slowdowns causes latency spikes that the benchmark misses. Fix: use scheduled, fixed-rate request generation and record the latency from the intended start time (not actual start). Tools like `wrk2`, `vegeta`, and `HdrHistogram` handle this correctly.

**Q: You're told to "tune the thread pool for maximum throughput." How do you approach this scientifically?**

> I follow three steps: (1) **Classify the workload**: Is it CPU-bound (computation), I/O-bound (DB, network), or mixed? CPU-bound optimal = CPU cores (more threads cause context switching overhead). I/O-bound optimal = λ × W (Little's Law). (2) **Measure the baseline**: Use JMH (for micro) or a load tool like wrk2 (for macro) at the current pool size. Record throughput, p50, p99, and p99.9 latency. (3) **Sweep pool sizes and measure**: Increment pool size by 25%, measure again, plot a throughput curve. It will peak and then decline (from context switching). The peak is the optimal. For virtual threads: size is not the tuning lever — tune the DB connection pool and Semaphore permits instead, because virtual threads themselves don't exhaust. Also measure GC impact — large pools under load increase heap pressure from per-request allocations, which shifts GC overhead.
