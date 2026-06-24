# Module 12: Observability & Debugging Concurrent Systems

**Difficulty:** Advanced
**Estimated Study Time:** 6 hours
**Prerequisites:** Module 03 (virtual thread mechanics), Module 09 (JMM)

---

## Learning Objectives

By the end of this module you will be able to:
- Capture and analyze thread dumps to diagnose deadlocks and live-locks
- Use JFR (Java Flight Recorder) to profile concurrency with low overhead
- Monitor thread pool health via JMX and expose custom metrics
- Use `async-profiler` to identify lock contention hotspots in CPU flame graphs
- Programmatically detect deadlocks at runtime and alert
- Diagnose virtual thread pinning using JVM flags and JFR events
- Read and interpret virtual thread dumps (Java 21+)

---

## 12.1 Thread Dumps — The First Diagnostic Tool

A thread dump shows the state of all threads at a single instant. Use it when:
- Requests are stuck while CPU usage is low.
- CPU usage is high but no progress is made.
- A deadlock is suspected.

### Capturing Thread Dumps

```bash
# Using jcmd (recommended, zero-impact):
jcmd <pid> Thread.print > threaddump.txt

# Using jstack (JDK utility):
jstack <pid> > threaddump.txt

# On Unix (sends SIGQUIT, prints to standard out of the JVM process):
kill -3 <pid>
```

### Analyzing Thread Dumps

```
"pool-1-thread-1" #12 prio=5 os_prio=0 cpu=14.53ms elapsed=120s tid=0x00007f... nid=0x2a3f waiting on condition  [0x00007f...]
   java.lang.Thread.State: WAITING (parking)
        at jdk.internal.misc.Unsafe.park(Native Method)
        - parking to wait for  <0x000000076b...> (a java.util.concurrent.locks.AbstractQueuedSynchronizer$ConditionObject)
        at java.util.concurrent.locks.LockSupport.park(LockSupport.java:341)
        at java.util.concurrent.locks.AbstractQueuedSynchronizer$ConditionNode.block(AbstractQueuedSynchronizer.java:506)
        ...
```

**Key fields to read:**
- **Thread State**: States include `RUNNABLE`, `BLOCKED`, `WAITING`, and `TIMED_WAITING`.
- **`waiting to lock <addr>`**: This thread wants the lock at `<addr>`
- **`locked <addr>`**: This thread holds the lock at `<addr>`
- **CPU time**: Threads in `RUNNABLE` state with no CPU time may be blocked in native code.

### Detecting Deadlocks in Thread Dumps

```
Found one Java-level deadlock:
=============================
"Thread-A":
  waiting to lock monitor 0x00007f... (object 0x000000076b..., a java.lang.Object),
  which is held by "Thread-B"
"Thread-B":
  waiting to lock monitor 0x00007f... (object 0x000000076c..., a java.lang.Object),
  which is held by "Thread-A"

Java stack information for the threads listed above:
===================================================
"Thread-A":
        at com.example.Deadlock$1.run(Deadlock.java:20)
        - waiting to lock <0x000000076b...> (a java.lang.Object)
        - locked <0x000000076c...> (a java.lang.Object)
"Thread-B":
        at com.example.Deadlock$2.run(Deadlock.java:32)
        - waiting to lock <0x000000076c...> (a java.lang.Object)
        - locked <0x000000076b...> (a java.lang.Object)
```

**Reading the deadlock:** Thread-A holds lock `76c` and waits for `76b`. Thread-B holds `76b` and waits for `76c`. This circular dependency causes a deadlock.

---

## 12.2 Virtual Thread Dumps (Java 21+)

Virtual threads are not registered as OS threads, so traditional thread dumps do not list them. Instead, use the new thread dump mechanism.

### Capturing Virtual Thread Dumps

```bash
# Capture virtual threads in text format:
jcmd <pid> Thread.dump_to_file threads.txt

# Capture in JSON format (excellent for programmatic parsing):
jcmd <pid> Thread.dump_to_file -format=json threads.json
```

### Reading a Virtual Thread Dump Entry

```json
{
  "container": "<unnamed>",
  "threadId": "23",
  "name": "worker-23",
  "state": "WAITING",
  "parent": "1",
  "stackTrace": [
    "java.base\/java.lang.VirtualThread.parkOnCarrierThread(VirtualThread.java:661)",
    "java.base\/java.lang.VirtualThread.park(VirtualThread.java:593)",
    "java.base\/java.lang.System$2.park(System.java:2643)",
    "java.base\/jdk.internal.misc.Blocker.park(Blocker.java:24)",
    "java.base\/java.util.concurrent.locks.LockSupport.park(LockSupport.java:371)",
    "com.example.Service.lambda$run$0(Service.java:42)"
  ]
}
```

**Key virtual thread states:**
- **`virtual`**: Healthy — mounted on a carrier, executing
- **`virtual` + WAITING**: Unmounted — yielded carrier thread (correct behavior)
- **`virtual [PINNED]`**: The virtual thread is pinned and blocks the carrier thread.

---

## 12.3 Programmatic Deadlock Detection

Use Java's `ThreadMXBean` to detect deadlocks programmatically and trigger alerts.

```java
import java.lang.management.*;
import java.util.concurrent.*;

public class DeadlockDetector {
    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(1);
    private final ThreadMXBean bean = ManagementFactory.getThreadMXBean();

    public void startMonitoring(long interval, TimeUnit unit) {
        scheduler.scheduleAtFixedRate(this::checkDeadlocks, interval, interval, unit);
    }

    private void checkDeadlocks() {
        long[] deadlockedThreads = bean.findDeadlockedThreads();
        if (deadlockedThreads != null) {
            System.err.printf("ALERT: Detected %d deadlocked threads!%n", deadlockedThreads.length);
            ThreadInfo[] infos = bean.getThreadInfo(deadlockedThreads, true, true);
            for (ThreadInfo info : infos) {
                System.err.println(info.toString()); // Print thread details and lock owners
            }
            triggerPagerDutyAlert(infos);
        }
    }

    private void triggerPagerDutyAlert(ThreadInfo[] infos) { /* ... */ }
}
```

**Performance warning:** `findDeadlockedThreads()` is an `O(N²)` operation where `N` is the thread count. Do not run it more than once every 10–30 seconds.

---

## 12.4 Java Flight Recorder (JFR) — Zero-Overhead Production Profiling

JFR is built into the JVM to record events with low overhead in production.

### Starting JFR

```bash
# Start JFR at JVM startup (records 2-minute buffer on exit):
java -XX:StartFlightRecording=disk=true,dumponexit=true,duration=120s,filename=prod_dump.jfr -jar app.jar

# Start/dump dynamically on running production JVM:
jcmd <pid> JFR.start name=concurrency_profile settings=profile
jcmd <pid> JFR.dump name=concurrency_profile filename=dump.jfr
jcmd <pid> JFR.stop name=concurrency_profile
```

### Profiling Lock Contention in JDK Mission Control (JMC)

1. Open `dump.jfr` in JMC.
2. Navigate to **Threads** → **Lock Instances**.
3. Look for the **Lock Thread Contention** histogram.
4. **Key Metric:** Total Wait Time & Wait Count. Identify which class is the target of the most contention.

---

## 12.5 Diagnosing Carrier Thread Pinning

Virtual threads are pinned to their carrier thread if they execute inside a `synchronized` block or call a native method. Pinning blocks the underlying OS thread, preventing other virtual threads from running on it.

### Diagnostic Method 1: JVM System Properties (Stdout Alert)

```bash
# Print stack trace when a virtual thread pins the carrier thread:
java -Djdk.tracePinnedThreads=full -jar app.jar
# Output will print the exact Java stack trace down to the synchronized block.

# Print brief one-line warning when pinning occurs:
java -Djdk.tracePinnedThreads=short -jar app.jar
```

### Diagnostic Method 2: JFR Events (JDK Mission Control)

Look for the JFR event **`jdk.VirtualThreadPinned`**:
- **Threshold**: By default, events are only recorded if pinning lasts longer than 20ms.
- **Tuning**: Lower the threshold to record shorter pinning events: `-XX:FlightRecorderOptions=stackdepth=128`

### Fixing Pinning: Replace `synchronized` with `ReentrantLock`

```java
// BROKEN: synchronized pins the carrier thread during I/O
class PinningService {
    private final Map<String, String> cache = new HashMap<>();

    public synchronized String get(String key) {
        String val = cache.get(key);
        if (val == null) {
            val = fetchFromDatabase(key); // BLOCKS during database query!
            // Result: carrier thread is pinned, other VTs cannot use this core
            cache.put(key, val);
        }
        return val;
    }
}
```

```java
// FIXED: ReentrantLock yields the carrier thread correctly during I/O
class CorrectService {
    private final Map<String, String> cache = new HashMap<>();
    private final ReentrantLock lock = new ReentrantLock();

    public String get(String key) {
        lock.lock();
        try {
            String val = cache.get(key);
            if (val == null) {
                val = fetchFromDatabase(key); // YIELDS the carrier thread correctly
                cache.put(key, val);
            }
            return val;
        } finally {
            lock.unlock();
        }
    }
}
```

---

## 12.6 Monitoring Thread Pools via JMX (Java Management Extensions)

Expose thread pool metrics programmatically to make them visible to Prometheus, Grafana, or JConsole.

```java
import javax.management.*;
import java.lang.management.ManagementFactory;
import java.util.concurrent.*;

// Define MBean interface
public interface VirtualThreadPoolMBean {
    int getPoolSize();
    int getActiveCount();
    long getCompletedTaskCount();
    long getTaskCount();
    int getQueueSize();
}

// Implement MBean
public class VirtualThreadPool implements VirtualThreadPoolMBean {
    private final ThreadPoolExecutor pool;

    public VirtualThreadPool(ThreadPoolExecutor pool) {
        this.pool = pool;
    }

    @Override public int getPoolSize() { return pool.getPoolSize(); }
    @Override public int getActiveCount() { return pool.getActiveCount(); }
    @Override public long getCompletedTaskCount() { return pool.getCompletedTaskCount(); }
    @Override public long getTaskCount() { return pool.getTaskCount(); }
    @Override public int getQueueSize() { return pool.getQueue().size(); }

    public static void register(ThreadPoolExecutor executor, String name) throws Exception {
        MBeanServer mbs = ManagementFactory.getPlatformMBeanServer();
        ObjectName objectName = new ObjectName("com.example:type=VirtualThreadPool,name=" + name);
        VirtualThreadPool mbean = new VirtualThreadPool(executor);
        mbs.registerMBean(mbean, objectName);
    }
}
```

---

## 12.7 Diagnosing Livelock

A **livelock** occurs when active threads make no progress because they repeatedly react to each other's state changes.

```java
// Livelock example: two threads politely yield to each other forever
class PoliteThread {
    private boolean needsLock = true;

    void doWork(PoliteThread other) throws InterruptedException {
        while (needsLock) {
            // Wait for other thread to finish
            if (other.needsLock) {
                System.out.println("Other thread needs lock, yielding...");
                Thread.sleep(10); // Yield to other thread
                continue;
            }
            
            // Acquire lock and do work
            this.needsLock = false;
        }
    }
}
```

**Detection:**
- Threads remain in the `RUNNABLE` state.
- CPU usage remains high.
- No progress is made.
- Subsequent thread dumps show the same stack frames.

**Fix: Add a randomized delay.**

```java
// Shadows the method above with a randomized delay to break symmetry
void doWork(PoliteThread other) throws InterruptedException {
    Random random = new Random();
    while (needsLock) {
        if (other.needsLock) {
            System.out.println("Other thread needs lock, yielding...");
            Thread.sleep(10 + random.nextInt(20)); // Add random delay to break symmetry
            continue;
        }
        this.needsLock = false;
    }
}
```

---

## 12.8 Hands-On Labs

### Lab 12.1 — Programmatic Deadlock Resolution

Use the `DeadlockDetector` code in Section 12.3. Write a program that starts two threads, forces them into a deadlock, detects it programmatically, and resolves it by interrupting one of the threads.

### Lab 12.2 — Trace Carrier Thread Pinning

1. Compile a simple program that spawns 100 virtual threads.
2. Inside each virtual thread, perform a blocking operation (e.g., `Thread.sleep(100)`) inside a `synchronized` block.
3. Run the program with `-Djdk.tracePinnedThreads=full`.
4. Observe and parse the printed stack traces to identify the pinning source.
5. Replace `synchronized` with `ReentrantLock` and verify that the pinning output disappears.

---

## 12.9 Observability Checklist

```
Diagnostic Readiness:
  [ ] JVM runs with -XX:FlightRecorderOptions=stackdepth=128 (captures deep locks)
  [ ] Ability to capture thread dumps on production nodes without restarting
  [ ] Monitoring tools (Grafana/Prometheus) tracking thread pool queue sizes
  [ ] Pinned thread logging active in staging (-Djdk.tracePinnedThreads=short)

Log and Event Aggregation:
  [ ] Log correlation IDs passed through thread pools via Task Decorators
  [ ] Thread names contain task/request context (e.g., "request-102-worker")
```

---

## 12.10 Interview-Style Questions

**Q: Your production service has 0% CPU utilization but requests are timing out. What is your diagnosis and investigation process?**

> This indicates thread pool exhaustion. To investigate: (1) Capture a thread dump. (2) Check if threads are in `BLOCKED` or `WAITING` states. (3) Look for locks that multiple threads are waiting on. (4) Identify the thread holding that lock. (5) Check for pinned virtual threads. (6) Monitor queue size via JMX. Fixes include shortening critical sections, adding timeouts, or rate limiting.

**Q: How do you detect if virtual thread carrier thread pinning is causing a production performance degradation?**

> First, look for high latency on operations that should be fast. Since pinning blocks carrier threads (the underlying ForkJoinPool threads), it starves other virtual threads of CPU cores. Second, capture a JFR recording and check for `jdk.VirtualThreadPinned` events. If their duration or frequency is high, pinning is occurring. Third, in non-production environments, run the application with `-Djdk.tracePinnedThreads=short` or `full` to print stack traces of pinning events directly to standard out. The stack traces will reveal the exact synchronized blocks that need to be replaced with `ReentrantLock` or refactored.
