# Module 13: Performance Engineering — JMH, Little's Law & Virtual Thread Benchmarking

**Difficulty:** Advanced
**Estimated Study Time:** 5 hours
**Prerequisites:** All previous modules

---

## Learning Objectives

By the end of this module you will be able to:
- Write JMH benchmarks that avoid compiler optimization errors and false sharing
- Distinguish throughput benchmarks from latency benchmarks
- Apply Little's Law to size thread pools
- Measure the performance differences between platform and virtual threads
- Identify benchmark errors like coordinated omission and inadequate warmup
- Profile memory allocation using the JMH GC profiler

---

## 13.1 Why Micro-Benchmarking Is Hard in Java

The JVM optimizes code in several ways:
1. **JIT compilation**: The JVM compiles frequently run methods to native machine code.
2. **Dead code elimination**: The compiler removes calculations if their results are not used.
3. **Loop unrolling and constant folding**: The compiler pre-calculates constant math and simplifies loops.
4. **Escape analysis**: If an object does not escape a method, the compiler may allocate it on the stack instead of the heap to avoid garbage collection.

```java
// This benchmark is incorrect because the compiler will remove the loop:
long start = System.nanoTime();
for (int i = 0; i < 1_000_000; i++) {
    int x = i * 2; // Unused result is removed by the compiler
}
long duration = System.nanoTime() - start;
System.out.println(duration); // Prints ~0ns

// This benchmark is incorrect because it lacks warmup and uses a single sample:
long start2 = System.nanoTime();
String result = expensiveMethod(); // Cold code path that is not yet compiled
long duration2 = System.nanoTime() - start2;
// The first run is much slower than subsequent runs, giving a misleading result.
```

The Java Microbenchmark Harness (JMH) solves these problems.

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

### Throughput Benchmark

```java
import org.openjdk.jmh.annotations.*;
import org.openjdk.jmh.infra.Blackhole;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.*;

@BenchmarkMode(Mode.Throughput)   // Measure operations per second.
@OutputTimeUnit(TimeUnit.SECONDS)
@State(Scope.Benchmark)           // Share state across the benchmark.
@Warmup(iterations = 5, time = 1) // Run 5 warmup iterations.
@Measurement(iterations = 10, time = 1) // Run 10 measurement iterations.
@Fork(3)                          // Run in 3 separate processes to avoid startup bias.
public class CounterBenchmark {

    AtomicLong atomicLong;
    LongAdder longAdder;

    @Setup(Level.Iteration) // Reset before each iteration.
    public void setup() {
        atomicLong = new AtomicLong(0);
        longAdder = new LongAdder();
    }

    @Benchmark
    public void atomicLongIncrement() {
        atomicLong.incrementAndGet(); // JMH uses the result, so the compiler does not remove it.
    }

    @Benchmark
    public void longAdderIncrement() {
        longAdder.increment();
    }

    // Incorrect: If a method returns void, the compiler might remove the calculation.
    // Fix: use Blackhole or return the value.
    @Benchmark
    public long atomicLongGet(Blackhole bh) {
        long val = atomicLong.get();
        bh.consume(val); // A Blackhole prevents the compiler from removing the code.
        return val;      // Or return the value.
    }
}
```

### Latency (Percentile) Benchmark

```java
@BenchmarkMode(Mode.SampleTime)   // Sample individual operation latencies.
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
// JMH outputs latency percentiles.
// This reveals tail latency, which average latency and throughput benchmarks hide.
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
// Incorrect: Fields on the same cache line cause false sharing, which slows down execution.
@State(Scope.Thread)
public class FalseSharingBenchmark {
    long counter1; // Both counters are likely on the same 64-byte cache line.
    long counter2;
}

// Correct: Pad fields to place them on separate cache lines.
@State(Scope.Thread)
@sun.misc.Contended  // A JVM annotation that pads the object to avoid false sharing.
public class PaddedState {
    long counter = 0;
}

// Or use manual padding.
@State(Scope.Thread)
public class ManuallyPaddedState {
    long p1, p2, p3, p4, p5, p6, p7; // 56 bytes of padding.
    volatile long counter = 0;         // The counter is now on its own cache line.
    long q1, q2, q3, q4, q5, q6, q7; // Trailing padding.
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

    @Param({"10", "100", "1000", "10000"}) // Concurrency levels.
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
                    Thread.sleep(10); // Simulate I/O work with a 10ms delay.
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

**Expected results for I/O-bound work:**

```
concurrency=10:    Platform threads perform similarly to virtual threads.
concurrency=100:   Platform threads perform similarly.
concurrency=1000:  Platform thread performance drops due to context switching and memory use.
concurrency=10000: Platform threads may run out of memory, while virtual thread throughput scales linearly.
```

**Expected results for CPU-bound work:**

```
All concurrency levels: Platform thread performance is similar to virtual thread performance.
(Virtual threads do not yield during CPU-intensive work, so they provide no advantage here)
```

---

## 13.6 Little's Law — Theoretical Thread Pool Sizing

**Little's Law:**

```
L = λ × W

Where:
  L = Average number of active requests in the system
  λ = Average arrival rate of requests per second
  W = Average response time in seconds
```

### Applying Little's Law to Thread Pools

```
Example:
  λ = 500 requests/second (throughput target)
  W = 200ms average response time (dominated by database queries)

  L = λ × W = 500 req/s × 0.2s = 100 concurrent requests in flight

  Platform thread pool: Need at least 100 threads
  Memory: 100 threads × 1MB stack = 100MB of off-heap memory

If the service calls three microservices sequentially, taking 200ms each:
  W = 600ms
  L = 500 × 0.6 = 300 threads needed
  Memory: 300MB

With virtual threads and parallel calls:
  W_parallel = 200ms (all 3 calls in parallel)
  L = 500 × 0.2 = 100 virtual threads
  Memory: 100 × ~100KB heap = 10MB (much less than platform threads)
```

**Little's Law for pool capacity planning:**

```java
// Predict queue buildup:
// If request rate spikes but the pool cannot handle the load:
// Requests queue up, causing latency to rise.

// Break-even point:
// For a given arrival rate and latency, you need a matching number of platform threads.
// Virtual threads are lightweight, but database connections remain a bottleneck.

// Database connection sizing:
// If database queries take 50ms, handling 500 requests per second requires 25 database connections.
// The default pool size of 10 in many connection pools may be too small for high throughput.
double requiredConnections = requestsPerSecond * avgDbTimeSeconds;
```

---

## 13.7 Measuring Coordinated Omission

**Coordinated omission** is a benchmarking flaw. When a system slows down, a test client that waits for each response before sending the next will send fewer requests. This reduces the number of measurements taken during slow periods, underestimating tail latency.

```java
// Incorrect: The client waits for the response, which hides latency issues during slow periods.
for (int i = 0; i < 1000; i++) {
    long start = System.nanoTime();
    callService(); // If this takes 500ms, the loop runs at 2 iterations per second.
    long latency = System.nanoTime() - start;
    record(latency); // Fewer samples are recorded during slow periods.
}

// Correct: Send requests at a fixed rate and measure latency from the intended start time.
ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(1);
long intervalNs = 1_000_000_000L / targetRatePerSecond; // 1ms for 1000 RPS
AtomicLong nextStart = new AtomicLong(System.nanoTime());

scheduler.scheduleAtFixedRate(() -> {
    long intendedStart = nextStart.getAndAdd(intervalNs);
    long actualStart = System.nanoTime();
    long schedulingDelay = actualStart - intendedStart; // Track scheduling delay.

    callService();
    long serviceTime = System.nanoTime() - actualStart;

    // Report both the service time and the total response time.
    record(serviceTime + schedulingDelay); // True end-to-end latency.
}, 0, intervalNs, TimeUnit.NANOSECONDS);

// Using HdrHistogram can help record latency percentiles accurately.
// https://github.com/HdrHistogram/HdrHistogram
```

---

## 13.8 JMH Profilers for Concurrency Analysis

```java
// Run JMH with built-in profilers:

// The GC profiler measures allocation rate and garbage collection time:
// java -jar benchmarks.jar -prof gc ".*MyBenchmark.*"
// Output includes:
//   gc.alloc.rate:   Memory allocation rate in MB/sec
//   gc.count:        Garbage collection events
//   gc.time:         Total garbage collection pause time

// The stack profiler integrates with async-profiler:
// java -jar benchmarks.jar -prof async:output=flamegraph ".*MyBenchmark.*"
// Generates a flame graph of CPU time.

// The Linux perf profiler accesses hardware counters:
// java -jar benchmarks.jar -prof perfasm ".*MyBenchmark.*"
// Shows assembly-level hotspots like cache misses and CAS retries.

// The Java Flight Recorder (JFR) profiler:
// java -jar benchmarks.jar -prof jfr ".*MyBenchmark.*"
// Generates a JFR file for the benchmark run.
```

---

## 13.9 Benchmark: Lock Contention Crossover Point

```java
// Compare StampedLock optimistic reads and ReentrantReadWriteLock under contention:
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
    @Threads(1) // JMH @Threads does not accept parameters directly.
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
// Expected: StampedLock performs better under low write contention.
//           ReentrantReadWriteLock performs similarly or better under higher write contention.
```

---

## 13.10 Production Performance Checklist

```
Before tuning:
  [ ] Establish a baseline measurement.
  [ ] Identify the bottleneck. It may be garbage collection, database, or network latency rather than concurrency.
  [ ] Measure steady-state performance after the JIT compiler warms up.

Thread pool sizing:
  [ ] Calculate thread requirements using Little's Law.
  [ ] Determine if the workload is CPU-bound or I/O-bound.
      CPU-bound: Limit pool size to the number of CPU cores.
      I/O-bound: Scale the pool size with response times.
  [ ] Use virtual threads for I/O-bound tasks.
  [ ] Size the database connection pool based on queries per second and database response times.

Lock contention:
  [ ] Keep critical sections short.
  [ ] Avoid blocking I/O inside synchronized blocks.
  [ ] Use ConcurrentHashMap instead of synchronized maps.
  [ ] Use LongAdder instead of AtomicLong for high-write-rate counters.
  [ ] Use StampedLock for read-heavy shared state.

Virtual threads:
  [ ] Avoid synchronized blocks in hot paths to prevent carrier thread pinning.
  [ ] Minimize ThreadLocal usage and consider ScopedValue instead.
  [ ] Throttle database connections using semaphores with a small pool.
  [ ] Use virtual-thread friendly clients like java.net.http.HttpClient.
```

---

## 13.11 Interview-Style Questions

**Q: What is coordinated omission and how does it affect latency measurements in concurrent systems?**

> Coordinated omission is a benchmarking flaw. When a system slows down, a test client that waits for each response before sending the next will send fewer requests. This reduces the number of measurements taken during slow periods, underestimating tail latency. In a real production system, requests arrive at a fixed rate regardless of response time. Queue buildup during slowdowns causes latency spikes that the benchmark misses. Fix: send requests at a fixed rate and measure latency from the intended start time. Tools like `wrk2`, `vegeta`, and `HdrHistogram` handle this correctly.

**Q: You're told to "tune the thread pool for maximum throughput." How do you approach this scientifically?**

> I follow three steps: (1) **Classify the workload**: Determine if it is CPU-bound (computation), I/O-bound (database, network), or mixed. For CPU-bound workloads, limit the pool size to the number of CPU cores to avoid context switching overhead. For I/O-bound workloads, use Little's Law to calculate the pool size. (2) **Measure the baseline**: Use JMH or a load tool like `wrk2` to record throughput and latency percentiles at the current pool size. (3) **Sweep pool sizes and measure**: Increase the pool size incrementally, measure performance, and plot a throughput curve to find the peak. For virtual threads, size is not the primary tuning lever. Instead, tune the database connection pool and semaphore permits. Also measure garbage collection impact, as large workloads can increase heap pressure and garbage collection overhead.
