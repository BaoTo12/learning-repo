# Module 04: GC Log Analysis & Diagnostics — Unified Logging and GC Metrics

Welcome back, students. Today we master **Garbage Collection Log Diagnostics**.

When a Java application suffers from high latency in production, GC logs are your first line of defense. Since JDK 9, the JVM utilizes the **Unified JVM Logging Framework (`-Xlog`)** to configure all logs. We will study the structure of Unified Logging, define the core mathematical metrics of GC performance (Throughput, Allocation Rate, and Promotion Rate), analyze key log signatures, and write a Java-based parser to analyze log files.

---

## 1. Academic Lecture: The Unified Logging Specification

Prior to JDK 9, configuring GC logs was a chaotic mix of flags like `-XX:+PrintGCDetails`, `-XX:+PrintGCTimeStamps`, and `-XX:+UseGCLogFileRotation`. 

Modern JVMs unify all logging under a single flag: `-Xlog`.

The syntax for Unified Logging is structured as:
```bash
-Xlog:[selectors]:[output]:[decorators]:[output-options]
```

*   **Selectors**: Composed of `tags` and `levels`. Common tags include `gc`, `gc,metaspace`, `gc,phases`, and `safepoint`. Levels range from `off` to `trace`.
*   **Output**: Where logs are written. Can be `stdout`, `stderr`, or a physical file path (`file=gc.log`).
*   **Decorators**: Additional metadata prefixing each log line. Examples include `time` (calendar time), `uptime` (seconds since startup), and `pid`.
*   **Output-options**: Log rotation settings: file count limits and file size caps.

### Production Logging Configuration Command:
```bash
-Xlog:gc*,gc+phases=debug:file=/var/log/app/gc.log:time,uptime,pid:filecount=5,filesize=100M
```
This enables all tags starting with `gc`, captures sub-phases at `debug` level, outputs to `gc.log`, prefixes metadata with time/uptime/pid, and rotates up to 5 files at 100MB each.

### Core GC Performance Metrics

To tune a garbage collector, you must evaluate three runtime metrics:

#### 1. Throughput
Throughput is the percentage of time the CPU spends executing business application logic (Mutator threads) vs. executing garbage collection code:
$$\text{Throughput (\%)} = \left( 1 - \frac{\text{Total GC Pause Time}}{\text{Total Running Time}} \right) \times 100$$
A production JVM should aim for a throughput of **99% or higher**.

#### 2. Allocation Rate
The volume of memory allocated by application threads per second (expressed in MB/sec). 
High allocation rates force G1 or ZGC to execute frequent Young GC sweeps to clean up Eden space.

#### 3. Promotion Rate
The volume of memory promoted from the Young Generation (Eden/Survivor) to the Old Generation per second.
If the promotion rate is high, the Old Generation will fill up quickly, triggering expensive concurrent marks or mixed GC sweeps.

### Reading GC Log Signatures

When parsing a GC log, look for these critical signatures:
*   `GC (Allocation Failure)`: Indicates Eden space is full, triggering a standard Young collection. Normal.
*   `G1 Humongous Allocation`: Indicates an object larger than 50% of the region size is being written. Warning.
*   `To-space Exhaustion` (or `To-space Overflow`): G1 Survivor regions are full. The collector has no room to copy survivors, forcing them to be promoted directly into the Old Generation, which causes heap fragmentation. Warning.

---

## 2. Theory vs. Production Trade-offs

### High Logging Verbosity vs. Disk I/O Latency
Enabling `trace` level logging (`-Xlog:gc*=trace`) records every phase of garbage collection down to the microsecond.
*   **Production Problem**: On highly contested cloud drives or virtual environments, synchronous log writing can block the JVM's execution thread during safepoints, adding log-induced latency.
*   **Production Solution**: Always ensure GC logs are written to high-performance local storage (SSD or tmpfs) or configure asynchronous logging using `-XX:+UseAsyncGCLogging` (available in modern OpenJDK builds).

---

## 3. How to Use: Simulating Promotion Rate Spikes in Java 21

Let's write a complete, compile-grade Java 21 class that simulates high allocation and promotion rates. This allows you to generate dirty card refinement queues and survivor overflows for log observation.

```java
package com.capstone.jvm.gc;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.logging.Logger;

/**
 * Script simulating high allocation and promotion rates.
 * Run this JVM with:
 * -XX:+UseG1GC -Xms32m -Xmx32m -XX:MaxGCPauseMillis=10 -Xlog:gc*=info
 */
public class GCAllocationSimulator {
    private static final Logger LOGGER = Logger.getLogger(GCAllocationSimulator.class.getName());

    public static void main(String[] args) throws InterruptedException {
        LOGGER.info("Starting GC Allocation Simulator...");

        // Hold medium-lived references to force Young GC promotion into Old Generation
        List<String[]> promotionBuffer = new ArrayList<>();

        for (int iteration = 0; iteration < 50_000; iteration++) {
            // Step 1: Allocate high volume of short-lived objects (causes Young GC load)
            for (int i = 0; i < 1000; i++) {
                String temp1 = UUID.randomUUID().toString();
                String temp2 = UUID.randomUUID().toString();
            }

            // Step 2: Allocate objects that survive multiple Young GC cycles (promoted to Old Gen)
            if (iteration % 5 == 0) {
                String[] persistentData = new String[256];
                for (int j = 0; j < 256; j++) {
                    persistentData[j] = "PersistentDataBlock-" + j;
                }
                promotionBuffer.add(persistentData);
            }

            // Step 3: Periodically purge the buffer to prevent crash (creates Old Gen reclamation cycles)
            if (promotionBuffer.size() > 50) {
                promotionBuffer.remove(0);
            }

            if (iteration % 1000 == 0) {
                LOGGER.info("Completed simulation iteration: " + iteration);
                Thread.sleep(50); // Pause briefly to prevent immediate OOM
            }
        }

        LOGGER.info("Simulator execution finished.");
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Missing Log Rotation Boundaries
Running production JVMs with `-Xlog:gc:file=gc.log` without setting size or count limits.
*   **Symptom**: The log file grows to hundreds of gigabytes, consuming all disk space and causing the OS to halt the JVM process.
*   **Mitigation**: Always specify filecount and filesize decorators: `filecount=5,filesize=100M`.

### Pitfall 2: Overlooking GC Throughput in performance charts
Focusing exclusively on average pause times while ignoring the cumulative time spent in collection.
*   **Symptom**: Average pause is low (e.g., 5ms), but the CPU usage is 100% and queries are slow because the JVM is executing GC 50% of the time.
*   **Mitigation**: Parse logs using visualizers like **GCViewer** to compute the overall JVM throughput percentage.

---

## 5. Socratic Review Questions

### Question 1
Explain why a high **Promotion Rate** is more concerning to performance engineers than a high **Allocation Rate**.

#### Answer
A high **Allocation Rate** (e.g., 500MB/sec) means application threads are creating short-lived objects. While this forces G1 GC to run frequent Young GC cycles, Young GCs are highly efficient. G1 simply copies the small subset of surviving objects to Survivor regions and reclaims the Eden space instantly, which typically takes only a few milliseconds.

A high **Promotion Rate** means objects are surviving Young GCs and filling up the Old Generation. Collecting the Old Generation is far more expensive. G1 must execute concurrent marking phases, track cross-region pointers, and run **Mixed GC collections** (which sweep both Young and Old regions) to reclaim memory. If the promotion rate exceeds the concurrent marking reclamation rate, the heap will exhaust its memory, forcing a single-threaded **Full GC pause** that halts the application for seconds.

### Question 2
What is the difference between log selectors `-Xlog:gc` and `-Xlog:gc*` in the Unified Logging framework?

#### Answer
*   `-Xlog:gc`: Configures logging only for messages tagged exactly with the `gc` tag, omitting sub-system logging details.
*   `-Xlog:gc*`: Configures logging for any log lines containing the `gc` tag alongside *any other* sub-tags (e.g., `gc,metaspace`, `gc,phases`, `gc,heap`, `gc,ergo`). 
In production diagnostics, `-Xlog:gc*` is preferred because it captures sub-phase details (like card refinement times and copy phase durations) which are necessary for identifying specific GC bottlenecks.

---

## 6. Hands-on Challenge: Building a GC Log Parser

### The Challenge
In this challenge, you will implement a simplified GC Log Parser. 

Given a stream of simulated GC log lines, you must write a parser that:
1.  Identifies log lines representing GC pause events.
2.  Extracts the pause duration in milliseconds.
3.  Computes the average pause duration.
4.  Flags any lines that contain the keyword `"Humongous"` or `"Full GC"`.

Complete the parsing logic inside the class below:

```java
package com.capstone.jvm.gc.challenge;

import java.util.List;

public class GCLogParser {

    public record GCStatus(double averagePauseMs, boolean containsCriticalWarnings) {}

    /**
     * Parses a list of log lines and returns the aggregated GC status.
     * 
     * Simulated Log Line Format:
     * - "2026-06-12T10:00:00 [info] gc,start: GC(12) Garbage Collection (Allocation Failure)"
     * - "2026-06-12T10:00:01 [info] gc: GC(12) Pause Young (Normal) 15.4ms"
     * - "2026-06-12T10:00:02 [warn] gc: GC(13) G1 Humongous Allocation detected"
     */
    public GCStatus parseLogs(List<String> logLines) {
        double totalPauseTime = 0.0;
        int pauseCount = 0;
        boolean hasWarnings = false;

        // TODO: Complete this implementation.
        // 1. Iterate over logLines.
        // 2. If a line contains "Pause" and ends with "ms", extract the double value preceding "ms" (e.g. 15.4).
        // 3. If a line contains "Humongous" or "Full GC", set hasWarnings = true.
        // 4. Return GCStatus containing average pause and the warning flag.
        return new GCStatus(0.0, false);
    }
}
```

Write your code and verify the metric calculations. Save your solution notes inside `modules/04-gc-log-analysis-diagnostics.md`.
