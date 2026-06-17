# Module 12: Observability & Debugging Concurrent Systems

**Difficulty:** Advanced
**Estimated Study Time:** 5 hours
**Prerequisites:** Module 02 (virtual threads), Module 03 (thread pool mechanics)

---

## Learning Objectives

By the end of this module you will be able to:
- Capture and analyze thread dumps to diagnose deadlocks and live-locks
- Use JFR (Java Flight Recorder) to profile concurrency events with zero production overhead
- Monitor thread pool health via JMX and expose custom metrics
- Use `async-profiler` to identify lock contention hotspots in CPU flame graphs
- Programmatically detect deadlocks at runtime and alert
- Diagnose virtual thread pinning using JVM flags and JFR events
- Read and interpret virtual thread thread dumps (Java 21+)

---

## 12.1 Thread Dumps — The First Diagnostic Tool

A thread dump captures the state of every thread in the JVM at a single instant. It is the first tool to reach for when:
- CPU is at 0% but requests are stuck (blocked/waiting threads)
- CPU is at 100% and no useful work is done (busy-spinning threads)
- Deadlock suspected (threads waiting on each other)

### Capturing Thread Dumps

```bash
# Method 1: jstack (works even if JVM is unresponsive)
jstack <pid> > thread-dump.txt

# Method 2: jcmd (more information, requires JVM responsiveness)
jcmd <pid> Thread.print > thread-dump.txt

# Method 3: Via HTTP endpoint (Spring Boot Actuator)
curl http://localhost:8080/actuator/threaddump

# Method 4: kill -3 (Unix only — dumps to stdout/stderr, never kills the process)
kill -3 <pid>

# Method 5: From within the JVM (programmatic)
ThreadMXBean bean = ManagementFactory.getThreadMXBean();
ThreadInfo[] infos = bean.dumpAllThreads(true, true);
```

### Anatomy of a Thread Dump Entry

```
"http-nio-8080-exec-3" #42 prio=5 os_prio=0 cpu=234ms elapsed=120s tid=0x00007f... nid=0x2bc3 waiting on condition [0x00007f...]
   java.lang.Thread.State: WAITING (parking)
        at sun.misc.Unsafe.park(Native Method)
        - parking to wait for <0x000000076b... > (a java.util.concurrent.locks.AbstractQueuedSynchronizer$ConditionObject)
        at java.util.concurrent.locks.LockSupport.park(LockSupport.java:211)
        at java.util.concurrent.locks.AbstractQueuedSynchronizer$ConditionObject.await(...)
        at java.util.concurrent.LinkedBlockingQueue.take(LinkedBlockingQueue.java:439)
        at java.util.concurrent.ThreadPoolExecutor.getTask(ThreadPoolExecutor.java:1061)
        ...

"http-nio-8080-exec-5" #44 prio=5 os_prio=0 cpu=0ms elapsed=120s tid=0x00007f... nid=0x2bc5 BLOCKED on lock
   java.lang.Thread.State: BLOCKED (on object monitor)
        at com.example.OrderService.processOrder(OrderService.java:87)
        - waiting to lock <0x000000076b...> (a com.example.OrderService)
        at ...
```

**Key fields to read:**
- **Thread State**: `RUNNABLE` (executing), `BLOCKED` (waiting for monitor), `WAITING` (parked indefinitely), `TIMED_WAITING` (parked with timeout)
- **`waiting to lock <addr>`**: This thread wants the lock at `<addr>`
- **`locked <addr>`**: This thread HOLDS the lock at `<addr>`
- **CPU time**: Threads with RUNNABLE state but zero CPU time → spinning on a lock or stuck in native code

### Detecting Deadlocks in Thread Dumps

`jstack` automatically detects and reports deadlocks:

```
Found one Java-level deadlock:
=============================
"Thread-A":
  waiting to lock monitor 0x000000076b...(a java.lang.Object),
  which is held by "Thread-B"

"Thread-B":
  waiting to lock monitor 0x000000076c...(a java.lang.Object),
  which is held by "Thread-A"

Java stack information for the threads listed above:
===================================================
"Thread-A":
        at com.example.TransferService.transfer(TransferService.java:34)
        - waiting to lock <0x000000076b...> (a java.lang.Object)
        - locked <0x000000076c...> (a java.lang.Object)
        
"Thread-B":
        at com.example.TransferService.transfer(TransferService.java:34)
        - waiting to lock <0x000000076c...> (a java.lang.Object)
        - locked <0x000000076b...> (a java.lang.Object)
```

**Reading the deadlock:** Thread-A holds lock `76c` and wants `76b`. Thread-B holds `76b` and wants `76c`. Circular dependency → deadlock.

---

## 12.2 Virtual Thread Dumps (Java 21+)

Virtual thread dumps include both virtual and carrier threads. The format differs from platform threads.

```bash
# Show virtual threads in thread dump:
jcmd <pid> Thread.print -e   # Extended format: shows virtual threads
jcmd <pid> Thread.dump_to_file -format=json threads.json  # JSON format
```

**Sample virtual thread dump entry:**

```
#89 "" virtual
      java.lang.Thread.State: WAITING (on object monitor)
      at java.base@21/jdk.internal.misc.Unsafe.park(Native Method)
      - waiting on <0x...> (a java.util.concurrent.locks.ReentrantLock$NonfairSync)
      ...CarrierThread: "ForkJoinPool-1-worker-3" #17 prio=5...

#102 "" virtual [PINNED]   ← PINNING DETECTED
      java.lang.Thread.State: RUNNABLE
      at java.base/java.net.SocketInputStream.socketRead0(Native Method)  ← native call
      at ...
      Carrier: "ForkJoinPool-1-worker-1" #15 [PINNED]
```

**Key virtual thread states:**
- **`virtual`**: Healthy — mounted on a carrier, executing
- **`virtual` + WAITING**: Unmounted — yielded carrier thread (correct behavior)
- **`virtual [PINNED]`**: Pinned to carrier — blocking the carrier thread (problem!)

---

## 12.3 Programmatic Deadlock Detection

```java
import java.lang.management.*;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

@Component // Spring service example
public class DeadlockDetector {
    private static final ThreadMXBean THREAD_MX = ManagementFactory.getThreadMXBean();
    private final ScheduledExecutorService scheduler =
        Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "deadlock-detector");
            t.setDaemon(true); // Don't prevent JVM shutdown
            return t;
        });

    @PostConstruct
    public void start() {
        // Check for deadlocks every 30 seconds
        scheduler.scheduleAtFixedRate(this::checkDeadlocks, 30, 30, TimeUnit.SECONDS);
    }

    private void checkDeadlocks() {
        long[] deadlockedIds = THREAD_MX.findDeadlockedThreads();
        if (deadlockedIds == null || deadlockedIds.length == 0) return;

        ThreadInfo[] infos = THREAD_MX.getThreadInfo(deadlockedIds, true, true);
        StringBuilder report = new StringBuilder("DEADLOCK DETECTED:\n");
        for (ThreadInfo info : infos) {
            report.append("Thread: ").append(info.getThreadName()).append("\n");
            report.append("  State: ").append(info.getThreadState()).append("\n");
            report.append("  Waiting on: ").append(info.getLockName()).append("\n");
            report.append("  Lock owner: ").append(info.getLockOwnerName()).append("\n");
            for (StackTraceElement e : info.getStackTrace()) {
                report.append("    at ").append(e).append("\n");
            }
        }
        // Alert: log, send PagerDuty notification, emit metric
        log.error(report.toString());
        metrics.counter("jvm.deadlock.detected").increment(deadlockedIds.length);
    }

    @PreDestroy
    public void stop() { scheduler.shutdown(); }
}
```

---

## 12.4 Java Flight Recorder (JFR) — Zero-Overhead Production Profiling

JFR is built into the JVM and designed for production use. It records hundreds of event types (GC, JIT, I/O, thread, lock) with < 1% overhead when configured conservatively.

### Starting JFR

```bash
# Start JFR at JVM startup (continuous recording, 1% overhead):
java -XX:StartFlightRecording=duration=60s,filename=recording.jfr,settings=profile MyApp

# Or attach to a running JVM:
jcmd <pid> JFR.start name=concurrency-profile duration=30s filename=/tmp/app.jfr settings=profile

# Stop and dump:
jcmd <pid> JFR.stop name=concurrency-profile

# Analyze in JDK Mission Control (JMC):
jmc   # Open recording.jfr in the GUI
```

### Key JFR Events for Concurrency

```bash
# Using jfr command-line tool to analyze events:

# 1. Find long-running synchronized blocks (monitor contention):
jfr print --events jdk.JavaMonitorWait --json app.jfr | jq '.[] | select(.duration > 10000000)' 
# Filter events where wait > 10ms (10,000,000 ns)

# 2. Find thread park/unpark cycles (virtual thread blocking):
jfr print --events jdk.VirtualThreadPinned app.jfr
# Lists every instance where a virtual thread pinned its carrier

# 3. Find thread sleep events (excessive sleeping):
jfr print --events jdk.ThreadSleep app.jfr

# 4. Lock contention events (threads blocked on synchronized):
jfr print --events jdk.JavaMonitorEnter app.jfr | grep "duration"
```

### Programmatic JFR Event Recording

```java
import jdk.jfr.*;

// Define a custom JFR event for your business logic
@Name("com.example.OrderProcessing")
@Label("Order Processing Event")
@Category("Business Events")
@Description("Records order processing time and contention")
@StackTrace(false) // Disable stack trace for performance
public class OrderProcessingEvent extends Event {
    @Label("Order ID")
    public String orderId;

    @Label("Wait Time (ms)")
    public long waitTimeMs;

    @Label("Lock Contended")
    public boolean lockContended;
}

// Use in your code:
public void processOrder(String orderId) {
    OrderProcessingEvent event = new OrderProcessingEvent();
    event.orderId = orderId;
    event.begin(); // Start timing

    long waitStart = System.currentTimeMillis();
    synchronized (orderLock) {
        event.lockContended = (waitStart != System.currentTimeMillis());
        event.waitTimeMs = System.currentTimeMillis() - waitStart;
        // ... process order ...
    }

    event.commit(); // Record the event (only if recording is enabled — zero cost otherwise)
}
```

### Virtual Thread Pinning Detection with JFR

```java
// Start the JVM with pinning event enabled:
// java -Djdk.tracePinnedThreads=full MyApp
// This prints to console when pinning occurs

// Or capture with JFR:
// jfr print --events jdk.VirtualThreadPinned app.jfr

// Sample output:
// jdk.VirtualThreadPinned {
//   startTime = 14:23:01.123
//   duration = 1 s 234 ms         ← How long the carrier was pinned!
//   eventThread = "virtual-thread-#42"
//   stackTrace = [
//     com.example.LegacyService.callSoap(LegacyService.java:87) ← synchronized block
//     com.example.OrderController.process(OrderController.java:45)
//   ]
// }
```

---

## 12.5 JMX — Thread Pool Health Monitoring

Java Management Extensions (JMX) exposes JVM internals as MBeans accessible via JConsole, JMC, or custom clients.

### Reading Thread Pool Metrics via JMX

```java
import java.lang.management.*;
import java.util.concurrent.ThreadPoolExecutor;

public class ThreadPoolMonitor {

    // Monitor built-in JVM thread metrics
    public static void reportJvmThreads() {
        ThreadMXBean tmx = ManagementFactory.getThreadMXBean();
        System.out.printf("Live threads:     %d%n", tmx.getThreadCount());
        System.out.printf("Peak threads:     %d%n", tmx.getPeakThreadCount());
        System.out.printf("Daemon threads:   %d%n", tmx.getDaemonThreadCount());
        System.out.printf("Total started:    %d%n", tmx.getTotalStartedThreadCount());

        // Enable CPU and contention time measurement (adds overhead!)
        tmx.setThreadCpuTimeEnabled(true);
        tmx.setThreadContentionMonitoringEnabled(true);

        // Per-thread CPU usage:
        for (long id : tmx.getAllThreadIds()) {
            long cpuNs = tmx.getThreadCpuTime(id);
            long blockedMs = tmx.getThreadInfo(id).getBlockedTime();
            System.out.printf("Thread %d: CPU=%dns, Blocked=%dms%n", id, cpuNs, blockedMs);
        }
    }

    // Monitor a specific ThreadPoolExecutor via its built-in stats
    public static void reportExecutorStats(ThreadPoolExecutor pool, String name) {
        System.out.printf("[%s] Active=%d, Pool=%d, Queue=%d, Completed=%d, Max=%d%n",
            name,
            pool.getActiveCount(),       // Currently executing tasks
            pool.getPoolSize(),          // Current thread count
            pool.getQueue().size(),      // Queued tasks
            pool.getCompletedTaskCount(), // Total completed
            pool.getLargestPoolSize()    // Peak pool size
        );
    }
}
```

### Registering Custom MBeans

```java
import javax.management.*;
import java.lang.management.ManagementFactory;
import java.util.concurrent.ThreadPoolExecutor;

// MBean interface (must be named: <ClassName>MBean)
public interface VirtualThreadPoolMBean {
    int getActiveVirtualThreads();
    long getTotalSubmitted();
    double getAverageDurationMs();
}

// MBean implementation
public class VirtualThreadPool implements VirtualThreadPoolMBean {
    private final AtomicInteger activeThreads = new AtomicInteger(0);
    private final LongAdder totalSubmitted = new LongAdder();
    private final LongAdder totalDurationMs = new LongAdder();

    public Runnable wrap(Runnable task) {
        totalSubmitted.increment();
        return () -> {
            activeThreads.incrementAndGet();
            long start = System.currentTimeMillis();
            try { task.run(); }
            finally {
                activeThreads.decrementAndGet();
                totalDurationMs.add(System.currentTimeMillis() - start);
            }
        };
    }

    @Override public int getActiveVirtualThreads() { return activeThreads.get(); }
    @Override public long getTotalSubmitted() { return totalSubmitted.sum(); }
    @Override public double getAverageDurationMs() {
        long total = totalSubmitted.sum();
        return total == 0 ? 0 : (double) totalDurationMs.sum() / total;
    }

    // Register with JMX:
    public static VirtualThreadPool register(String name) throws Exception {
        VirtualThreadPool pool = new VirtualThreadPool();
        ObjectName objectName = new ObjectName("com.example:type=VirtualThreadPool,name=" + name);
        ManagementFactory.getPlatformMBeanServer().registerMBean(pool, objectName);
        return pool;
    }
}
// Now visible in JConsole under: com.example → VirtualThreadPool → name=...
```

---

## 12.6 async-profiler — Lock Contention Flame Graphs

`async-profiler` is a low-overhead sampling profiler that can profile:
- CPU time (on-CPU profiling)
- Lock contention (which locks block threads most)
- Memory allocation (which code paths allocate most)
- Wall clock time (including blocking time)

### Installation and Basic Usage

```bash
# Download: https://github.com/async-profiler/async-profiler
# Linux:
./asprof -d 30 -e cpu -f cpu-flame.html <pid>

# Profile lock contention (shows which locks block most):
./asprof -d 30 -e lock -f lock-contention.html <pid>
# Output: flame graph where width = total blocked time

# Profile virtual threads (wall-clock profiling):
./asprof -d 30 -e wall -t -f wall-clock.html <pid>
# -t includes thread names in the graph

# Profile allocation (find GC pressure from concurrency code):
./asprof -d 30 -e alloc -f allocation.html <pid>
```

### Reading a Lock Contention Flame Graph

```
Lock Contention Flame Graph (bottom = lock sites, top = caller stacks):

___ com.example.PaymentService.processPayment()       ← Top of stack (caller)
___ com.example.AuditLogger.log()                    
___ java.util.logging.Logger.log()
___ java.util.logging.StreamHandler.publish()         ← Synchronized block!
___ synchronized(this) in StreamHandler              ← This is the bottleneck
Width = 3,200ms blocked time out of 30s sample window

Diagnosis: Logging is contended. Fix: Use async logger (e.g., Log4j2 async appender)
or structure logs as events and batch-flush on a single thread.
```

---

## 12.7 Diagnosing Livelock

A **livelock** is harder to detect than a deadlock: threads are active (not BLOCKED/WAITING) but make no progress because they repeatedly react to each other's state changes.

```java
// Livelock example: two threads politely yield to each other forever
class PoliteThread {
    volatile boolean needsLock = true;

    void doWork(PoliteThread other) {
        while (needsLock) {
            if (other.needsLock) {
                // The other thread also needs the lock — back off
                needsLock = false;          // Give up
                Thread.yield();             // Let the other thread proceed
                needsLock = true;           // Try again
                // LIVELOCK: both threads are constantly yielding to each other!
            } else {
                // Got the "lock" — do work
                performWork();
                needsLock = false;
            }
        }
    }
}
```

**How to detect livelock:**
- Thread dump shows threads in `RUNNABLE` state
- CPU is high (threads are actively running)
- No actual progress (metrics: throughput = 0, latency = ∞)
- Same stack frames appear repeatedly across multiple thread dumps 30 seconds apart

**Fix: Add randomized backoff**
```java
// Randomized backoff breaks the symmetry that causes livelock
void doWork(PoliteThread other) throws InterruptedException {
    Random random = new Random();
    while (needsLock) {
        if (other.needsLock) {
            needsLock = false;
            Thread.sleep(random.nextInt(100)); // Random delay breaks symmetry
            needsLock = true;
        } else {
            performWork();
            needsLock = false;
        }
    }
}
```

---

## 12.8 Monitoring Virtual Thread Scheduler

```java
// Enable ForkJoinPool monitoring (the virtual thread scheduler):
// java -Djava.util.concurrent.ForkJoinPool.common.parallelism=8 MyApp

// Check virtual thread scheduler state programmatically:
public class VirtualThreadSchedulerMonitor {
    public static void reportSchedulerState() throws Exception {
        // The virtual thread carrier pool is accessible via reflection (internal API)
        // In production: use JFR events instead

        // Monitor via JFR VirtualThread events:
        // jdk.VirtualThreadStart      — virtual thread started
        // jdk.VirtualThreadEnd        — virtual thread completed
        // jdk.VirtualThreadPinned     — carrier pinned (PROBLEM)
        // jdk.VirtualThreadSubmitFailed — scheduler rejected submission (CRITICAL)

        // Simple diagnostic: count active virtual threads
        Thread.getAllStackTraces().entrySet().stream()
            .filter(e -> e.getKey().isVirtual())
            .forEach(e -> System.out.println("VT: " + e.getKey().getName()));
    }

    // Monitor for VirtualThreadSubmitFailed (scheduler overload):
    // This occurs when all carrier threads are pinned AND new virtual threads can't be scheduled
    // -Djdk.virtualThreadScheduler.parallelism=N   — number of carrier threads (default: CPU cores)
    // -Djdk.virtualThreadScheduler.maxPoolSize=N   — max carrier threads (for I/O-bound pinning)
}
```

---

## 12.9 Complete Observability Setup for Production

```java
// Production-ready concurrency observability stack
@Configuration
public class ConcurrencyObservabilityConfig {

    @Bean
    @Scheduled(fixedRate = 15, timeUnit = TimeUnit.SECONDS)
    public void reportThreadMetrics() {
        ThreadMXBean tmx = ManagementFactory.getThreadMXBean();

        // Metrics (emit to Prometheus/Micrometer)
        meterRegistry.gauge("jvm.threads.live",     tmx.getThreadCount());
        meterRegistry.gauge("jvm.threads.peak",     tmx.getPeakThreadCount());
        meterRegistry.gauge("jvm.threads.daemon",   tmx.getDaemonThreadCount());

        // Check for deadlocks
        long[] deadlocked = tmx.findDeadlockedThreads();
        meterRegistry.gauge("jvm.threads.deadlocked", deadlocked != null ? deadlocked.length : 0);
        if (deadlocked != null && deadlocked.length > 0) {
            alerting.critical("DEADLOCK DETECTED", buildDeadlockReport(tmx, deadlocked));
        }

        // Virtual thread count (if using virtual threads)
        long virtualThreadCount = Thread.getAllStackTraces().keySet().stream()
            .filter(Thread::isVirtual).count();
        meterRegistry.gauge("jvm.virtual.threads.live", virtualThreadCount);
    }

    private String buildDeadlockReport(ThreadMXBean tmx, long[] ids) {
        StringBuilder sb = new StringBuilder();
        for (ThreadInfo info : tmx.getThreadInfo(ids, 20)) {
            sb.append("Thread: ").append(info.getThreadName())
              .append(" → locked: ").append(info.getLockName())
              .append(" → waiting: ").append(info.getLockName()).append("\n");
        }
        return sb.toString();
    }
}
```

---

## 12.10 Quick Reference: Symptoms → Diagnosis Tool

| Symptom | Tool | What to look for |
| :--- | :--- | :--- |
| 0% CPU, stuck requests | Thread dump | `BLOCKED` or `WAITING` threads, deadlock section |
| 100% CPU, no throughput | Thread dump + async-profiler | `RUNNABLE` threads with same stack, livelock |
| Slow response, normal CPU | JFR lock events | `jdk.JavaMonitorWait` durations > threshold |
| Virtual threads not scaling | JFR + `-Djdk.tracePinnedThreads` | `jdk.VirtualThreadPinned` events |
| Memory growing under concurrency | async-profiler (alloc) | Allocation flame graph, which code path allocates |
| Thread pool exhaustion | JMX + executor stats | `queue.size()` growing, `activeCount == maxPoolSize` |
| Production incident, no tools | kill -3 | Thread dump to stderr (works always) |

---

## 12.11 Interview-Style Questions

**Q: Your production service has 0% CPU utilization but requests are timing out. What is your diagnosis and investigation process?**

> This is the classic thread pool exhaustion pattern. Investigation: (1) Capture a thread dump immediately with `jcmd <pid> Thread.print` or `kill -3 <pid>`. (2) Count threads in `BLOCKED` or `WAITING` state — if most are waiting, the pool is exhausted or a shared resource is contended. (3) Look for a lock address that many threads are waiting on — this is the bottleneck. (4) Identify the thread that HOLDS that lock — it may be slow, deadlocked, or waiting on I/O. (5) If using virtual threads, look for `[PINNED]` markers. (6) Check the executor queue size via JMX — if `queue.size() > 0` and growing, all pool threads are busy. Resolution depends on finding the root cause: contended lock → reduce critical section; slow external call → add timeout; pool exhausted → add semaphore rate limiting or increase pool (with care).

**Q: How do you detect if virtual thread carrier thread pinning is causing a production performance degradation?**

> Three approaches: (1) **JVM flag**: Start the JVM with `-Djdk.tracePinnedThreads=full`. Every pinning event is printed to stdout with a stack trace showing which `synchronized` block caused it. (2) **JFR**: Record with `jcmd <pid> JFR.start` and filter `jdk.VirtualThreadPinned` events. The event includes duration (how long the carrier was pinned) and the stack trace of the offending code. (3) **Thread dump**: Run `jcmd <pid> Thread.print -e` and look for virtual threads marked `[PINNED]` — they are consuming carrier threads while blocked. Once identified, the fix is to replace `synchronized` blocks in the hot path with `ReentrantLock` (which triggers `LockSupport.park()` and allows the virtual thread to unmount instead of pinning), or use a non-pinning I/O approach for native calls.
