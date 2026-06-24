# ConcurrentHashMap Performance Test

In the previous module, we analyzed the internal mechanics of `ConcurrentHashMap.putVal()` and saw how it combines lock-free Compare-And-Swap (CAS) operations with fine-grained lock striping. 

To validate these theoretical benefits, we will conduct a practical experiment. We will write a benchmark to compare the write performance of a synchronized map wrapper (`Collections.synchronizedMap()`) against a `ConcurrentHashMap` under varying levels of thread contention.

---

## The Benchmark Code

Our performance test performs **one million insertions** divided equally among a pool of concurrent threads. We measure the total time taken to complete the insertions as we scale the thread count from 1 to 16.

Below is the complete JUnit benchmark implementation:

```java
import org.junit.jupiter.api.Test;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.assertEquals;

public class ConcurrentHashMapPerformanceTest {

    @Test
    public void testHashMap() throws InterruptedException, ExecutionException {
        System.out.println("---------------------------- With Collections.synchronizedMap() -------------------------");
        for (int nThreads = 1; nThreads <= 16; nThreads++) {
            long totalTimeNanos = 0L;
            for (int i = 0; i < 10; i++) {
                totalTimeNanos += testMap(nThreads, Collections.synchronizedMap(new HashMap<>()));
            }
            double averageSeconds = totalTimeNanos / (10.0 * 1_000_000_000.0);
            System.out.printf("nThreads: %d, Average Time Taken: %.6f seconds%n", nThreads, averageSeconds);
        }

        System.out.println("---------------------------- With ConcurrentHashMap -------------------------");
        for (int nThreads = 1; nThreads <= 16; nThreads++) {
            long totalTimeNanos = 0L;
            for (int i = 0; i < 10; i++) {
                totalTimeNanos += testMap(nThreads, new ConcurrentHashMap<>());
            }
            double averageSeconds = totalTimeNanos / (10.0 * 1_000_000_000.0);
            System.out.printf("nThreads: %d, Average Time Taken: %.6f seconds%n", nThreads, averageSeconds);
        }
    }

    private long testMap(int nThreads, Map<String, Integer> map) throws InterruptedException, ExecutionException {
        ExecutorService pool = Executors.newFixedThreadPool(nThreads);
        int approxElements = 1_000_000;
        int totalElements = approxElements / nThreads;
        
        @SuppressWarnings("unchecked")
        Future<Long>[] futures = (Future<Long>[]) new Future[nThreads];
        for (int i = 0; i < nThreads; i++) {
            futures[i] = pool.submit(new Task(totalElements, "Thread-" + i, map));
        }
        
        long totalTimeNanos = 0L;
        for (int i = 0; i < nThreads; i++) {
            totalTimeNanos += futures[i].get();
        }
        
        pool.shutdown();
        pool.awaitTermination(10, TimeUnit.SECONDS);
        
        assertEquals(totalElements * nThreads, map.size());
        return totalTimeNanos;
    }

    static class Task implements Callable<Long> {
        private final int nElements;
        private final String id;
        private final Map<String, Integer> map;

        public Task(int nElements, String id, Map<String, Integer> map) {
            this.nElements = nElements;
            this.id = id;
            this.map = map;
        }

        @Override
        public Long call() {
            long start = System.nanoTime();
            for (int i = 1; i <= nElements; i++) {
                map.put(id + ": " + i, i);
            }
            return System.nanoTime() - start;
        }
    }
}
```

*Figure 17.4.1: JUnit benchmark comparing Collections.synchronizedMap() and ConcurrentHashMap*

---

## Benchmark Results and Analysis

Below is the structured output showing the average time taken (in seconds) for both map implementations across 1 to 16 threads, along with the calculated speedup ratio ($\text{Time}_{\text{Synchronized}} / \text{Time}_{\text{Concurrent}}$):

| Threads | Collections.synchronizedMap() (s) | ConcurrentHashMap (s) | Speedup Ratio |
| :---: | :---: | :---: | :---: |
| **1** | 0.241617 | 0.289010 | 0.84x |
| **2** | 0.482975 | 0.493800 | 0.98x |
| **3** | 0.796638 | 0.597190 | 1.33x |
| **4** | 1.010598 | 0.760390 | 1.33x |
| **5** | 1.115971 | 0.969640 | 1.15x |
| **6** | 1.528649 | 1.036470 | 1.47x |
| **7** | 1.698244 | 1.137010 | 1.49x |
| **8** | 2.157568 | 1.169670 | 1.84x |
| **9** | 2.261998 | 1.142990 | 1.98x |
| **10** | 2.743739 | 1.080180 | 2.54x |
| **11** | 2.575613 | 1.040130 | 2.48x |
| **12** | 3.072078 | 1.174290 | 2.62x |
| **13** | 3.383775 | 0.975900 | 3.47x |
| **14** | 3.333770 | 1.179110 | 2.83x |
| **15** | 3.971915 | 0.849810 | 4.67x |
| **16** | 3.401782 | 1.044330 | 3.26x |

### Key Insights from the Data

> **Insight: Single-Thread Overhead**
> At **1 thread**, `Collections.synchronizedMap()` is slightly faster than `ConcurrentHashMap` (0.24s vs 0.28s). 
> - This is because a single thread incurs no contention. 
> - The synchronized wrapper uses simple intrinsic locking which the JVM optimizes heavily (biased locking/lock elision). 
> - `ConcurrentHashMap` has slightly higher baseline algorithmic complexity due to its hash-spreading, CAS loops, and volatile read checks.

> **Insight: Scalability and Throughput**
> As the thread count scales, the performance of `Collections.synchronizedMap()` degrades rapidly (taking 3.40s at 16 threads). This occurs because all threads are serialized, fighting for a single lock, resulting in massive thread contention and blocking.
>
> In contrast, `ConcurrentHashMap` scales exceptionally well, maintaining an execution time of around 0.84s to 1.17s even at 16 threads. This represents a **3x to 4.6x speedup** under high contention, due to lock striping and lock-free CAS insertions.

Below is the charted performance comparison, visually showing that lower execution times represent higher throughput:

![Performance Chart](../images/image14.png)

*Figure 17.4.2: Performance chart comparing execution times (lower is better)*

---

## CPU Load and Thread State Analysis

To understand why `ConcurrentHashMap` outperforms `Collections.synchronizedMap()` so dramatically, we must observe how the operating system schedules these threads on the CPU cores.

We run this test on an **8-logical-core machine** (a 4-physical-core CPU with Hyper-Threading enabled). We monitor logical core utilization using the **`htop`** utility.

### 1. Idle State
When the benchmark is not running, the CPU cores are almost entirely idle. The system load is negligible:

![CPU Idle State](../images/image15.png)

*Figure 17.4.3: CPU cores in an idle state before the benchmark*

### 2. Under Load: Collections.synchronizedMap()
Here is the CPU utilization snapshot while the test is running with 10 threads using `Collections.synchronizedMap()`:

![CPU Load Synchronized Map](../images/image16.png)

*Figure 17.4.4: CPU load during synchronized map test (notice low, uneven utilization)*

Even though 10 active threads are running, the CPU cores are barely utilized. This is a classic symptom of lock contention:
- Only **one** thread can hold the synchronized lock and execute at any given moment.
- The remaining **nine** threads are forced into the `BLOCKED` state, sleeping and waiting for the lock.
- Because only one thread runs at a time, the system cannot utilize the multi-core architecture, resulting in poor throughput and low CPU efficiency.

### 3. Under Load: ConcurrentHashMap
Here is the CPU utilization snapshot while the test is running with 10 threads using `ConcurrentHashMap`:

![CPU Load ConcurrentHashMap](../images/image17.png)

*Figure 17.4.5: CPU load during ConcurrentHashMap test (notice maximum, even utilization across all cores)*

Notice the stark contrast: **all 8 logical cores are pinned at nearly 100% utilization**. 

Because `ConcurrentHashMap` uses lock striping (locking individual bins) and CAS, the threads do not block each other.
- Up to 16 threads can write to different bins of the map simultaneously without any interference.
- The threads remain in the `RUNNABLE` state, executing in parallel.
- The application fully utilizes the available hardware processing power, resulting in maximum throughput and massive performance gains.

---

## Summary

*   **Serialized Bottleneck**: `Collections.synchronizedMap()` serializes all write operations on a single monitor lock. This creates a bottleneck under thread contention, leaving CPU cores idle while threads sit in a `BLOCKED` state.
*   **Massive Scalability**: `ConcurrentHashMap` utilizes lock-free CAS operations for empty bins and independent locks for non-empty bins (lock striping). This allows threads to run concurrently in a `RUNNABLE` state without blocking.
*   **Hardware Utilization**: As verified by `htop`, `ConcurrentHashMap` fully saturates all logical CPU cores, translating multi-core processing power directly into application throughput.
*   **Single-Thread Baseline**: Under zero contention (1 thread), the synchronized wrapper can be slightly faster due to its simplicity, but it does not scale. `ConcurrentHashMap` is the clear choice for multi-threaded, high-contention environments.
