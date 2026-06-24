# The CyclicBarrier

In the previous module, we explored the three most common ways of using `CountDownLatch`. Latches focus on waiting for a set of events to occur. However, a major limitation of latches is that they are **single-use (use-once)** objects. Once a latch reaches its terminal state (count = 0), the gate remains open forever and cannot be closed or reset.

If you need a synchronization barrier that can be reset and reused multiple times, you must use a **`CyclicBarrier`**. 

---

## Latches vs. Barriers: Key Differences

To select the right synchronizer, you must understand how `CountDownLatch` and `CyclicBarrier` differ structurally, conceptually, and programmatically. 

| Feature | CountDownLatch | CyclicBarrier |
| :--- | :--- | :--- |
| **Coordination Target** | Waits for **events** to occur. | Waits for **other threads** to arrive. |
| **Thread Blocking** | Threads calling `countDown()` do **not** block; only threads calling `await()` block. | **All** threads calling `await()` block until the required number of threads arrive. |
| **Reusability** | **Single-use**. Once open, it cannot be reset or reused. | **Reusable (Cyclic)**. Resets automatically when all threads arrive, or manually via `reset()`. |
| **Barrier Action** | None supported. | Supports a **Runnable barrier action** executed when the barrier is tripped, before threads are released. |
| **Algorithmic Flow** | One-way gate (producers signal, consumers wait). | Multi-way rendezvous (all threads arrive and wait for each other). |

---

### 1. Tasks vs. Threads (Counting Target)

A crucial semantic difference is that **`CyclicBarrier` maintains a count of threads**, whereas **`CountDownLatch` maintains a count of tasks**. 

*   **CountDownLatch (Tasks)**: The latch waits for a number of tasks to complete. Because tasks are independent of the threads executing them, a **single thread** can decrement the latch multiple times by calling `countDown()` repeatedly.
*   **CyclicBarrier (Threads)**: The barrier waits for threads to arrive at a rendezvous point. The threads themselves *are* the barrier. Therefore, a single thread **cannot** count down a barrier twice. A call to `await()` blocks the thread immediately, preventing it from executing a second `await()` until the barrier is already tripped and opened by other threads.

#### CountDownLatch Task Code Proof
A single thread can decrement a CountDownLatch of size 2 to zero successfully:

```java
CountDownLatch countDownLatch = new CountDownLatch(2);
Thread t = new Thread(() -> {
    countDownLatch.countDown(); // Decrements to 1
    countDownLatch.countDown(); // Decrements to 0
});
t.start();
countDownLatch.await(); // Returns immediately since count is 0

assertEquals(0, countDownLatch.getCount()); // Passes
```

#### CyclicBarrier Thread Code Proof
A single thread attempting to trip a CyclicBarrier of size 2 by calling `await()` twice will block indefinitely at the first call, failing to trip the barrier:

```java
CyclicBarrier cyclicBarrier = new CyclicBarrier(2);
Thread t = new Thread(() -> {
    try {
        cyclicBarrier.await(); // Thread blocks here waiting for a second thread!
        cyclicBarrier.await(); // This line is never reached
    } catch (InterruptedException | BrokenBarrierException e) {
        Thread.currentThread().interrupt();
    }
});
t.start();

assertEquals(1, cyclicBarrier.getNumberWaiting()); // 1 thread is stuck waiting
assertFalse(cyclicBarrier.isBroken()); // The barrier remains untripped and intact
```

---

### 2. Reusability and Thread Pools

The second most evident difference is reusability. When the barrier trips in `CyclicBarrier`, the internal count immediately resets to its original value, allowing it to govern subsequent waves of threads. A `CountDownLatch` never resets.

#### CountDownLatch Single-Use Proof
If we submit 20 threads to a pool, each calling `countDown()` on a latch initialized to 7, the latch count drops to zero and remains there forever. It never resets:

```java
CountDownLatch countDownLatch = new CountDownLatch(7);
ExecutorService es = Executors.newFixedThreadPool(20);
List<String> outputScraper = Collections.synchronizedList(new ArrayList<>());

for (int i = 0; i < 20; i++) {
    es.execute(() -> {
        long prevValue = countDownLatch.getCount();
        countDownLatch.countDown();
        if (countDownLatch.getCount() != prevValue) {
            outputScraper.add("Count Updated");
        }
    }); 
} 
es.shutdown();

// The count only updates 7 times (from 7 down to 0). All subsequent calls are ignored.
assertTrue(outputScraper.size() <= 7); 
```

#### CyclicBarrier Reusability Proof
If we submit 20 threads to a pool, each calling `await()` on a `CyclicBarrier` initialized to 7, the barrier trips and resets repeatedly. It successfully coordinates multiple cyclic waves of threads:

```java
CyclicBarrier cyclicBarrier = new CyclicBarrier(7);
ExecutorService es = Executors.newFixedThreadPool(20);
List<String> outputScraper = Collections.synchronizedList(new ArrayList<>());

for (int i = 0; i < 20; i++) {
    es.execute(() -> {
        try {
            if (cyclicBarrier.getNumberWaiting() <= 0) {
                outputScraper.add("Count Updated"); // Added every time the barrier resets
            }
            cyclicBarrier.await(); // Tripped and reset automatically every 7 threads
        } catch (InterruptedException | BrokenBarrierException e) {
            Thread.currentThread().interrupt();
        }
    });
}
es.shutdown();

// The barrier resets multiple times, allowing more than 7 updates
assertTrue(outputScraper.size() > 7); 
```

---

## A Real-World Analogy

Consider a group of 5 friends planning to meet for pizza:

*   **CountDownLatch (Event-Based)**: Each friend eats their pizza at home (completing an event) and then travels to a rendezvous point. The latch waits for all 5 "pizza-eating" events to complete. The friends do not wait for each other to eat; they only wait for the events to be done.
*   **CyclicBarrier (Thread-Based)**: All 5 friends agree to meet at a specific street corner (the barrier point) and walk into the pizza shop together. The first friend to arrive must wait on the corner. As the second, third, and fourth arrive, they must also wait. Only when the fifth friend arrives does the group cross the barrier and enter the shop.

The street corner represents a **`CyclicBarrier`**. The threads (friends) arrive at the barrier point by calling `await()` and block until all expected threads have arrived.

---

## Key CyclicBarrier Concepts

### 1. Reaching the Barrier Point
When a thread calls `await()` on a `CyclicBarrier` instance, it has arrived at the **barrier point**. The thread is immediately blocked and placed in a wait-set until the required number of threads (the barrier capacity) have also called `await()`.

### 2. The Arrival Index
The `await()` method returns an `int` representing the **arrival index** of the thread (ranging from `parties - 1` down to `0`).
- The first thread to arrive receives `parties - 1`.
- The last thread to arrive receives `0`.
This index is highly useful for electing a "leader" thread. For example, the thread that receives an index of `0` can be elected to merge the results of the parallel computations before the next iteration begins.

### 3. The Barrier Action
A `CyclicBarrier` can be initialized with an optional `Runnable` action:

```java
CyclicBarrier barrier = new CyclicBarrier(parties, barrierAction);
```

The **barrier action** is executed atomically by the last thread to arrive (the one that trips the barrier), after all threads have arrived but *before* any blocked threads are released. This is ideal for merging parallel data sets or logging progress between phases.

---

## Code Example: Using and Resetting a CyclicBarrier

Below is a complete program demonstrating how a `CyclicBarrier` coordinates threads in batches and resets itself automatically:

```java
import java.time.LocalDateTime;
import java.util.concurrent.BrokenBarrierException;
import java.util.concurrent.CyclicBarrier;

public class CyclicBarrierDemo {

    // Initialize the barrier to wait for 2 threads, with a Runnable barrier action
    private static final CyclicBarrier BARRIER = new CyclicBarrier(2, () -> logInfo("Barrier Passed!!"));

    public static void main(String[] args) throws InterruptedException {
        Runnable task = task();

        Thread t1 = new Thread(task, "T1");
        Thread t2 = new Thread(task, "T2");
        Thread t3 = new Thread(task, "T3");
        Thread t4 = new Thread(task, "T4");

        // Start the first batch of threads
        t1.start();
        t2.start();

        t1.join();
        t2.join();

        logInfo("First Batch Completed!");
        logInfo("Barrier has been reset automatically! Waiting for the second batch...");

        // Start the second batch of threads, reusing the same barrier
        t3.start();
        t4.start();

        t3.join();
        t4.join();

        logInfo("main thread finished!");
    }

    private static Runnable task() {
        return () -> {
            try {
                logInfo("Working on subtask...");
                Thread.sleep(1000); // Simulate parallel work
                
                logInfo("Completed. Waiting at the barrier point...");
                int arrivalIndex = BARRIER.await(); // Arrive and block
                
                logInfo("Arrival Index: " + arrivalIndex);
            } catch (InterruptedException | BrokenBarrierException e) {
                Thread.currentThread().interrupt();
                e.printStackTrace();
            }
        };
    }

    private static void logInfo(String msg) {
        System.out.println(LocalDateTime.now() + ": " + Thread.currentThread().getName() + " :: " + msg);
    }
}
```

*Figure 20.3.1: Reusing a CyclicBarrier across multiple batches of threads*

#### Output
```text
2026-06-24T15:08:00.301: T2 :: Working on subtask...
2026-06-24T15:08:00.303: T1 :: Working on subtask...
2026-06-24T15:08:01.434: T2 :: Completed. Waiting at the barrier point...
2026-06-24T15:08:01.441: T1 :: Completed. Waiting at the barrier point...
2026-06-24T15:08:01.441: T1 :: Barrier Passed!!
2026-06-24T15:08:01.453: T2 :: Arrival Index: 1
2026-06-24T15:08:01.454: T1 :: Arrival Index: 0
2026-06-24T15:08:01.455: main :: First Batch Completed!
2026-06-24T15:08:01.455: main :: Barrier has been reset automatically! Waiting for the second batch...
2026-06-24T15:08:01.455: T3 :: Working on subtask...
2026-06-24T15:08:01.456: T4 :: Working on subtask...
2026-06-24T15:08:02.456: T3 :: Completed. Waiting at the barrier point...
2026-06-24T15:08:02.456: T4 :: Completed. Waiting at the barrier point...
2026-06-24T15:08:02.457: T4 :: Barrier Passed!!
2026-06-24T15:08:02.457: T4 :: Arrival Index: 0
2026-06-24T15:08:02.457: T3 :: Arrival Index: 1
2026-06-24T15:08:02.458: main :: main thread finished!
```

---

## Automatic vs. Manual Resetting

As demonstrated in the logs above, you do **not** need to call `BARRIER.reset()` manually to reuse the barrier. 
- **Automatic Reset**: As soon as the last required thread calls `await()`, the barrier is tripped, the barrier action runs, all threads are released, and the barrier **automatically resets** for the next cycle.
- **Manual Reset**: You can force a manual reset by calling `barrier.reset()`. 

### The Broken Barrier State
If a barrier is reset manually while threads are waiting, or if a waiting thread is interrupted or times out, the barrier becomes **broken**. 
- Any thread currently blocked in `await()` will immediately throw a **`BrokenBarrierException`** and return.
- Any subsequent attempt to call `await()` on a broken barrier will immediately throw a `BrokenBarrierException`.
- To reuse a broken barrier, you must call `reset()` to restore its initial state.

---

## Advanced Applications: Divide-and-Conquer Algorithms

The primary use case for `CyclicBarrier` is in parallel iterative algorithms that follow a **divide-and-conquer** approach:
1.  A large problem is broken down into $N$ independent subproblems.
2.  $N$ threads are spawned, each solving a subproblem in parallel.
3.  Each thread calls `await()` on the barrier after completing its subtask.
4.  Once all subtasks are complete, the barrier action merges the partial results.
5.  The barrier resets, and the threads immediately begin the next iteration.

This parallel stepping pattern is widely used in simulations, scientific computing, graphics rendering, and multiplayer game loops.

### Baeldung Simulation: Parallel Number Cruncher and Aggregator

To see this divide-and-conquer pattern in action, let's implement a complete simulation where multiple worker threads compute partial results in parallel, and a single aggregator thread computes their sum once all workers reach the barrier.

```java
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;
import java.util.concurrent.BrokenBarrierException;
import java.util.concurrent.CyclicBarrier;

public class CyclicBarrierSimulationDemo {

    private CyclicBarrier cyclicBarrier;
    
    // Thread-safe collection to hold partial results from all workers
    private final List<List<Integer>> partialResults = Collections.synchronizedList(new ArrayList<>());
    private final Random random = new Random();
    private int numPartialResults;
    private int numWorkers;

    // Worker Thread performing parallel number crunching
    class NumberCruncherThread implements Runnable {
        @Override
        public void run() {
            String thisThreadName = Thread.currentThread().getName();
            List<Integer> partialResult = new ArrayList<>();

            // Crunch numbers and store the partial result
            for (int i = 0; i < numPartialResults; i++) {    
                Integer num = random.nextInt(10);
                System.out.println(thisThreadName + ": Crunching some numbers! Final result - " + num);
                partialResult.add(num);
            }

            partialResults.add(partialResult);
            try {
                System.out.println(thisThreadName + " waiting for others to reach barrier.");
                cyclicBarrier.await(); // Register arrival and block
            } catch (InterruptedException | BrokenBarrierException e) {
                Thread.currentThread().interrupt();
                e.printStackTrace();
            }
        }
    }

    // Aggregator Thread executed when the barrier is tripped
    class AggregatorThread implements Runnable {
        @Override
        public void run() {
            String thisThreadName = Thread.currentThread().getName();
            System.out.println(thisThreadName + ": Computing sum of " + numWorkers 
              + " workers, having " + numPartialResults + " results each.");
            int sum = 0;

            for (List<Integer> threadResult : partialResults) {
                System.out.print("Adding ");
                for (Integer partialResult : threadResult) {
                    System.out.print(partialResult + " ");
                    sum += partialResult;
                }
                System.out.println();
            }
            System.out.println(thisThreadName + ": Final result = " + sum);
        }
    }

    public void runSimulation(int numWorkers, int numberOfPartialResults) {
        this.numPartialResults = numberOfPartialResults;
        this.numWorkers = numWorkers;

        // Initialize barrier with AggregatorThread as the barrier action
        this.cyclicBarrier = new CyclicBarrier(this.numWorkers, new AggregatorThread());

        System.out.println("Spawning " + this.numWorkers
          + " worker threads to compute "
          + this.numPartialResults + " partial results each");
 
        for (int i = 0; i < this.numWorkers; i++) {
            Thread worker = new Thread(new NumberCruncherThread());
            worker.setName("Thread " + i);
            worker.start();
        }
    }

    public static void main(String[] args) {
        CyclicBarrierSimulationDemo demo = new CyclicBarrierSimulationDemo();
        demo.runSimulation(5, 3);
    }
}
```

#### Simulation Output
```text
Spawning 5 worker threads to compute 3 partial results each
Thread 0: Crunching some numbers! Final result - 6
Thread 0: Crunching some numbers! Final result - 2
Thread 0: Crunching some numbers! Final result - 2
Thread 0 waiting for others to reach barrier.
Thread 1: Crunching some numbers! Final result - 2
Thread 1: Crunching some numbers! Final result - 0
Thread 1: Crunching some numbers! Final result - 5
Thread 1 waiting for others to reach barrier.
Thread 3: Crunching some numbers! Final result - 6
Thread 3: Crunching some numbers! Final result - 4
Thread 3: Crunching some numbers! Final result - 0
Thread 3 waiting for others to reach barrier.
Thread 2: Crunching some numbers! Final result - 1
Thread 2: Crunching some numbers! Final result - 1
Thread 2: Crunching some numbers! Final result - 0
Thread 2 waiting for others to reach barrier.
Thread 4: Crunching some numbers! Final result - 9
Thread 4: Crunching some numbers! Final result - 3
Thread 4: Crunching some numbers! Final result - 5
Thread 4 waiting for others to reach barrier.
Thread 4: Computing final sum of 5 workers, having 3 results each.
Adding 6 2 2 
Adding 2 0 5 
Adding 6 4 0 
Adding 1 1 0 
Adding 9 3 5 
Thread 4: Final result = 46
```

As the simulation logs demonstrate, **Thread 4** is the final thread to arrive at the barrier. It trips the barrier and is elected to execute the `AggregatorThread` barrier action, summing all partial results, before the barrier resets and all worker threads are allowed to proceed.

---

## Summary

*   **Multi-Way Rendezvous**: `CyclicBarrier` blocks a group of threads until a specified number of threads (parties) arrive at a common barrier point.
*   **Waiting for Threads**: Unlike `CountDownLatch` (which waits for events), `CyclicBarrier` is designed to make threads wait for other threads.
*   **Cyclic Reusability**: Once all threads arrive, the barrier trips, releases the threads, and resets automatically so it can be reused immediately.
*   **Barrier Action**: Supports a `Runnable` action that executes atomically when the barrier is tripped, before any blocked threads are released.
*   **Arrival Index**: The `await()` method returns the thread's arrival order index, which can be used to elect a leader thread for coordinating post-arrival tasks.
*   **Broken Barriers**: If a thread is interrupted, times out, or the barrier is manually reset under load, the barrier enters a broken state and throws `BrokenBarrierException` to all waiting threads.