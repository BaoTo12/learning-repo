# Module 11: Advanced Synchronization Primitives

**Difficulty:** Advanced
**Estimated Study Time:** 5 hours
**Prerequisites:** Module 03 (thread pool mechanics), Module 09 (JMM)

---

## Learning Objectives

By the end of this module you will be able to:
- Choose the correct synchronization primitive for each coordination pattern
- Implement multi-phase parallel pipelines using `Phaser`
- Distinguish one-shot (`CountDownLatch`) from reusable (`CyclicBarrier`) barriers
- Use `Exchanger` for safe bidirectional data handoff between threads
- Apply `Semaphore` for resource throttling with virtual threads
- Implement `ReentrantLock` condition variables for custom waiting protocols
- Design blocking queues as coordination primitives between producers and consumers

---

## 11.1 The Coordination Primitive Taxonomy

```
Coordination Primitives
├── Counting & Barriers
│   ├── CountDownLatch  — One-shot barrier that releases threads when the count reaches zero
│   ├── CyclicBarrier   — Reusable barrier that releases threads when all parties arrive
│   └── Phaser          — Multi-phase barrier with dynamic registration
│
├── Resource Limiting
│   └── Semaphore       — Limits concurrent access using permits
│
├── Data Exchange
│   └── Exchanger       — Swaps data between two threads
│
├── Lock Variants
│   ├── ReentrantLock   — Lock with condition variables
│   └── ReentrantReadWriteLock — Allows multiple readers or one writer
│
└── Queues (Blocking)
    ├── LinkedBlockingQueue  — Unbounded/bounded FIFO
    ├── ArrayBlockingQueue   — Bounded, strict backpressure
    ├── SynchronousQueue     — Zero capacity: direct handoff between threads
    ├── PriorityBlockingQueue — Unbounded, priority-ordered
    └── DelayQueue           — Time-delayed delivery
```

---

## 11.2 `CountDownLatch` — One-Shot Barrier

`CountDownLatch` lets threads wait until a set of operations completes. It cannot be reused.

```java
import java.util.concurrent.CountDownLatch;

// Pattern 1: Start gun — one thread releases many
public class RaceStart {
    public static void main(String[] args) throws InterruptedException {
        int runners = 8;
        CountDownLatch ready = new CountDownLatch(runners); // Runners signal when ready
        CountDownLatch start = new CountDownLatch(1);        // Starter signals once

        for (int i = 0; i < runners; i++) {
            final int runnerId = i;
            Thread.startVirtualThread(() -> {
                System.out.printf("Runner %d: Ready!%n", runnerId);
                ready.countDown();             // Signal readiness
                try {
                    start.await();             // Wait for the start signal
                    System.out.printf("Runner %d: Running!%n", runnerId);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            });
        }

        ready.await();                         // Wait for all runners
        System.out.println("All ready. GO!");
        start.countDown();                     // Release all runners
    }
}
```

```java
// Pattern 2: Many workers, one waiter — wait for all tasks to complete
public class ServiceInitializer {
    public static void main(String[] args) throws InterruptedException {
        String[] services = {"DatabasePool", "CacheWarmer", "ConfigLoader", "SchemaValidator"};
        CountDownLatch allReady = new CountDownLatch(services.length);

        for (String service : services) {
            Thread.startVirtualThread(() -> {
                try {
                    initializeService(service);
                    System.out.printf("[%s] Initialized%n", service);
                } finally {
                    allReady.countDown(); // Ensure the count decreases
                }
            });
        }

        boolean completed = allReady.await(30, TimeUnit.SECONDS); // Wait with a timeout
        if (!completed) {
            throw new RuntimeException("Service initialization timed out");
        }
        System.out.println("All services ready. Starting HTTP server...");
    }

    static void initializeService(String name) {
        try { Thread.sleep((long)(Math.random() * 1000)); } // Simulate init time
        catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
}
```

**Use cases:**
- One-time initialization sequencing
- Test synchronization (simulating concurrent load)
- Waiting for async callbacks
- Cannot be reused

---

## 11.3 `CyclicBarrier` — Reusable Multi-Party Barrier

All threads must arrive before any can proceed. The barrier resets automatically for the next cycle.

```java
import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.BrokenBarrierException;

// Parallel pipeline: 4 workers process data in synchronized phases
public class PhaseSimulation {
    static final int WORKERS = 4;
    static final int PHASES = 3;

    // Optional action run when all threads arrive
    static CyclicBarrier barrier = new CyclicBarrier(WORKERS, () ->
        System.out.printf("=== Phase complete! Next phase starting. ===%n")
    );

    public static void main(String[] args) {
        for (int w = 0; w < WORKERS; w++) {
            final int workerId = w;
            Thread.startVirtualThread(() -> {
                try {
                    for (int phase = 0; phase < PHASES; phase++) {
                        // Do phase work
                        doWork(workerId, phase);

                        // Wait for ALL workers to finish this phase
                        barrier.await(); // Blocks until all threads arrive
                        // After await() returns: all workers have finished this phase
                        // The barrier has been automatically reset for the next phase
                    }
                } catch (InterruptedException | BrokenBarrierException e) {
                    Thread.currentThread().interrupt();
                }
            });
        }
    }

    static void doWork(int worker, int phase) throws InterruptedException {
        System.out.printf("Worker %d: working on phase %d%n", worker, phase);
        Thread.sleep((long)(Math.random() * 500));
    }
}
```

**`CyclicBarrier` vs `CountDownLatch`:**

| Feature | `CountDownLatch` | `CyclicBarrier` |
| :--- | :--- | :--- |
| **Reusable** | No (one-shot) | Yes (auto-reset) |
| **Who waits** | Any thread calls `await()` | ALL parties must call `await()` |
| **Barrier action** | No | Yes (optional Runnable) |
| **On exception** | No automatic break | `BrokenBarrierException` propagates |
| **Use case** | One-time synchronization | Iterative parallel algorithms |

**`BrokenBarrierException`:** If a thread is interrupted while waiting, the barrier breaks. Other waiting threads wake up with `BrokenBarrierException`. Call `barrier.reset()` or propagate the failure to handle this.

---

## 11.4 `Phaser` — Dynamic Multi-Phase Coordination

`Phaser` is a flexible barrier that supports:
- Dynamic registration of threads at runtime.
- Multiple sequential phases.
- Hierarchical phasers for large numbers of threads.
- Tiered arrivals: threads can arrive and continue without waiting (`arriveAndDeregister`)

```java
import java.util.concurrent.Phaser;

public class DataPipelineWithPhaser {
    public static void main(String[] args) throws InterruptedException {
        // 1 registered party (main thread), others register themselves
        Phaser phaser = new Phaser(1) {
            // Override to add custom phase-transition logic
            @Override
            protected boolean onAdvance(int phase, int registeredParties) {
                System.out.printf("--- Phase %d complete, %d parties remaining ---%n",
                    phase, registeredParties);
                return registeredParties == 0; // true = terminate the phaser
            }
        };

        // Dynamically spawn workers that self-register
        for (int i = 0; i < 4; i++) {
            phaser.register(); // Register before spawning (prevents race)
            final int id = i;
            Thread.startVirtualThread(() -> {
                try {
                    // Phase 0: Load data
                    System.out.printf("Worker %d: Loading data (phase %d)%n", id, phaser.getPhase());
                    Thread.sleep((long)(Math.random() * 300));
                    phaser.arriveAndAwaitAdvance(); // Arrive + wait for all → phase 1

                    // Phase 1: Validate data
                    System.out.printf("Worker %d: Validating (phase %d)%n", id, phaser.getPhase());
                    Thread.sleep((long)(Math.random() * 300));
                    phaser.arriveAndAwaitAdvance(); // Arrive + wait → phase 2

                    // Phase 2: Write output
                    System.out.printf("Worker %d: Writing output (phase %d)%n", id, phaser.getPhase());
                    Thread.sleep((long)(Math.random() * 300));
                    phaser.arriveAndDeregister(); // Done — deregister from phaser
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    phaser.arriveAndDeregister(); // Deregister on failure
                }
            });
        }

        // Main thread coordinates: advance through each phase
        phaser.arriveAndAwaitAdvance(); // Phase 0 → 1
        System.out.println("Main: All data loaded. Starting validation.");

        phaser.arriveAndAwaitAdvance(); // Phase 1 → 2
        System.out.println("Main: All validated. Starting output.");

        phaser.arriveAndDeregister();   // Main deregisters
        System.out.println("Main: Pipeline complete.");
    }
}
```

**Phaser termination:** When `onAdvance()` returns true, the phaser terminates. Subsequent `await` calls return a negative phase number.

```java
// Check if phaser is terminated:
int phase = phaser.arriveAndAwaitAdvance();
if (phase < 0) {
    System.out.println("Phaser terminated");
}
```

**Hierarchical Phaser for large party counts:**
```java
// A flat phaser has higher overhead with many threads. A hierarchical tree of phasers reduces this overhead.
Phaser root = new Phaser();
Phaser child1 = new Phaser(root, 5000); // 5000 parties registered to parent
Phaser child2 = new Phaser(root, 5000); // Another 5000 parties

// Child phasers notify the parent when their threads arrive.
```

---

## 11.5 `Semaphore` — Resource Pool Throttling

`Semaphore` manages a pool of permits. `acquire()` takes a permit, blocking if none are available. `release()` returns a permit.

```java
import java.util.concurrent.Semaphore;

// Pattern: Database connection pool throttling (critical for virtual threads)
public class ThrottledResourceAccess {
    // Max 10 concurrent database connections
    private static final Semaphore DB_SEMAPHORE = new Semaphore(10);

    public String queryDatabase(String query) throws InterruptedException {
        DB_SEMAPHORE.acquire();       // Block if all permits are in use
        try {
            return executeQuery(query); // Access the resource
        } finally {
            DB_SEMAPHORE.release();   // Always release the permit in a finally block.
        }
    }

    // Non-blocking try (for optional operations)
    public Optional<String> tryQueryDatabase(String query) throws InterruptedException {
        if (DB_SEMAPHORE.tryAcquire(100, TimeUnit.MILLISECONDS)) { // Acquire with a timeout
            try {
                return Optional.of(executeQuery(query));
            } finally {
                DB_SEMAPHORE.release();
            }
        }
        return Optional.empty(); // Give up gracefully
    }

    private String executeQuery(String q) { return "result-of-" + q; }
}
```

**Fair vs Unfair Semaphore:**
```java
// Unfair (default) has higher throughput but no ordering guarantee.
Semaphore unfair = new Semaphore(10);

// Fair mode serves threads in order to prevent starvation.
Semaphore fair = new Semaphore(10, true);
// This has lower throughput due to queue overhead.
```

**Semaphore as mutex (binary semaphore):**
```java
// Any thread can release a semaphore permit. A ReentrantLock must be released by the thread that holds it.
Semaphore mutex = new Semaphore(1);
mutex.acquire();  // Thread A acquires
// ... Thread A delegates work to Thread B ...
// Thread B can legitimately release the semaphore
mutex.release();  // Thread B releases — valid!
```

---

## 11.6 `Exchanger` — Bidirectional Data Handoff

`Exchanger` lets two threads swap objects. Both threads block until they both arrive at the exchange point.

```java
import java.util.concurrent.Exchanger;

// Classic use case: double-buffering for pipeline throughput
public class DoubleBufferedPipeline {
    static final Exchanger<List<DataRecord>> exchanger = new Exchanger<>();

    public static void main(String[] args) {
        // Producer fills buffers and exchanges with consumer
        Thread.startVirtualThread(() -> {
            List<DataRecord> fillBuffer = new ArrayList<>();
            try {
                while (true) {
                    // Fill current buffer
                    for (int i = 0; i < 100; i++) {
                        fillBuffer.add(readFromSource());
                    }
                    // Exchange full buffer for an empty one (consumer gives us back the drained buffer)
                    fillBuffer = exchanger.exchange(fillBuffer); // Blocks until the other thread arrives
                    fillBuffer.clear(); // Reset the returned (now-empty) buffer
                }
            } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });

        // Consumer drains buffers and exchanges empty ones back
        Thread.startVirtualThread(() -> {
            List<DataRecord> drainBuffer = new ArrayList<>();
            try {
                while (true) {
                    drainBuffer = exchanger.exchange(drainBuffer); // Exchange empty for full
                    for (DataRecord record : drainBuffer) {
                        process(record);
                    }
                }
            } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
    }

    static DataRecord readFromSource() { return new DataRecord(); }
    static void process(DataRecord r) {}
    record DataRecord() {}
}
```

**Why `Exchanger` outperforms a shared queue here:** Using an exchanger avoids queue allocations and lock contention by swapping whole buffers at once.

**Exchanger with timeout:**
```java
try {
    T result = exchanger.exchange(myData, 5, TimeUnit.SECONDS);
} catch (TimeoutException e) {
    // Handle the timeout
}
```

---

## 11.7 `ReentrantLock` and Condition Variables

`ReentrantLock` provides features not available with `synchronized`, including timed locking, interruptible locking, and multiple conditions.

```java
import java.util.concurrent.locks.*;

// Bounded blocking queue — classic condition variable pattern
public class BoundedBlockingQueue<T> {
    private final ArrayDeque<T> queue;
    private final int capacity;
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notFull  = lock.newCondition(); // Producers wait here
    private final Condition notEmpty = lock.newCondition(); // Consumers wait here

    public BoundedBlockingQueue(int capacity) {
        this.capacity = capacity;
        this.queue = new ArrayDeque<>(capacity);
    }

    public void put(T item) throws InterruptedException {
        lock.lock();
        try {
            while (queue.size() == capacity) { // Always check the condition in a loop
                notFull.await(); // Release the lock and wait. When signaled, re-acquire the lock and check the condition again.
            }
            queue.addLast(item);
            notEmpty.signal(); // Notify one waiting consumer
        } finally {
            lock.unlock();
        }
    }

    public T take() throws InterruptedException {
        lock.lock();
        try {
            while (queue.isEmpty()) { // Loop to handle spurious wakeups
                notEmpty.await();
            }
            T item = queue.removeFirst();
            notFull.signal(); // Notify one waiting producer
            return item;
        } finally {
            lock.unlock();
        }
    }

    // Non-blocking offer with timeout
    public boolean offer(T item, long timeout, TimeUnit unit) throws InterruptedException {
        lock.lock();
        try {
            long nanos = unit.toNanos(timeout);
            while (queue.size() == capacity) {
                if (nanos <= 0) return false; // Timed out
                nanos = notFull.awaitNanos(nanos); // Returns remaining nanos
            }
            queue.addLast(item);
            notEmpty.signal();
            return true;
        } finally {
            lock.unlock();
        }
    }
}
```

**Why ALWAYS use `while` not `if` for condition checks:**

```java
// WRONG: uses if — susceptible to spurious wakeups
while (true) {
    lock.lock();
    try {
        if (queue.isEmpty()) {  // ← Incorrect: Using an if statement is susceptible to spurious wakeups.
            notEmpty.await();   // A spurious wakeup can cause errors if the condition is not re-checked.
        }
        return queue.removeFirst(); // NPE or wrong state
    } finally { lock.unlock(); }
}

// CORRECT: loops until condition is actually true
while (queue.isEmpty()) {
    notEmpty.await(); // Loops until the condition is met.
}
```

**Spurious wakeups** can occur where `await()` returns without a signal. Always use a loop to verify the condition.

### `tryLock` — Non-Blocking Lock Acquisition

```java
ReentrantLock lock = new ReentrantLock();

// Fail immediately if the lock is held
if (lock.tryLock()) {
    try { /* do work */ }
    finally { lock.unlock(); }
} else {
    // Lock is held by another thread — handle gracefully
    handleLockUnavailable();
}

// Wait for the lock with a timeout
if (lock.tryLock(500, TimeUnit.MILLISECONDS)) {
    try { /* do work */ }
    finally { lock.unlock(); }
} else {
    // Timed out
}
```

---

## 11.8 Blocking Queues as Coordination Primitives

Java's blocking queue implementations are production-grade coordination tools:

```java
// Bounded queue using a single lock
BlockingQueue<Task> bounded = new ArrayBlockingQueue<>(100);

// Optioned bounded queue with separate locks for head and tail
BlockingQueue<Task> linked = new LinkedBlockingQueue<>(1000);

// Zero-capacity queue for direct handoff
BlockingQueue<Task> direct = new SynchronousQueue<>();
// Threads block until a handoff occurs

// Unbounded queue sorted by priority
BlockingQueue<Task> priority = new PriorityBlockingQueue<>();

// Queue where items are available only after a delay
DelayQueue<ScheduledTask> delayed = new DelayQueue<>();

// Scalable queue that supports direct transfer
TransferQueue<Task> transfer = new LinkedTransferQueue<>();
transfer.transfer(task); // Blocks until a consumer takes the item directly
transfer.put(task);      // Enqueues normally if no consumer waiting
```

### Choosing a Blocking Queue

```
Few producers, few consumers, bounded:   ArrayBlockingQueue
Many producers, few consumers, bounded:  LinkedBlockingQueue
Maximum throughput, many P/C:            LinkedTransferQueue
Direct handoff required:                 SynchronousQueue
Priority processing:                     PriorityBlockingQueue
Scheduled/delayed delivery:              DelayQueue
```

---

## 11.9 Complete Real-World Example: Multi-Stage ETL Pipeline

```java
import java.util.concurrent.*;

// 3-stage pipeline: Extract → Transform → Load
// Each stage runs concurrently; blocking queues provide natural backpressure
public class ETLPipeline {
    static final int BUFFER = 200;
    static final BlockingQueue<RawRecord> raw = new ArrayBlockingQueue<>(BUFFER);
    static final BlockingQueue<ProcessedRecord> processed = new ArrayBlockingQueue<>(BUFFER);

    // Poison pill pattern for shutdown
    static final RawRecord RAW_POISON = new RawRecord("POISON");
    static final ProcessedRecord PROC_POISON = new ProcessedRecord("POISON");

    record RawRecord(String data) {}
    record ProcessedRecord(String data) {}

    public static void main(String[] args) throws Exception {
        int workers = 4;
        CountDownLatch done = new CountDownLatch(3); // 3 stages

        // Stage 1: Extractor (1 thread)
        Thread.startVirtualThread(() -> {
            try {
                for (int i = 0; i < 10_000; i++) {
                    raw.put(new RawRecord("row-" + i)); // Blocks if the queue is full.
                }
                // Send one poison pill per transformer
                for (int i = 0; i < workers; i++) raw.put(RAW_POISON);
            } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            finally { done.countDown(); }
        });

        // Stage 2: Transformers (N threads)
        CountDownLatch transformsDone = new CountDownLatch(workers);
        for (int i = 0; i < workers; i++) {
            Thread.startVirtualThread(() -> {
                try {
                    while (true) {
                        RawRecord record = raw.take();
                        if (record == RAW_POISON) break;
                        processed.put(new ProcessedRecord(record.data().toUpperCase()));
                    }
                } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                finally {
                    if (transformsDone.countDown() == 0) { // Last transformer sends poison
                        try { processed.put(PROC_POISON); } catch (InterruptedException e) {}
                    }
                }
            });
        }

        // Stage 3: Loader (1 thread)
        Thread.startVirtualThread(() -> {
            try {
                while (true) {
                    ProcessedRecord record = processed.take();
                    if (record == PROC_POISON) break;
                    loadToDatabase(record);
                }
            } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            finally { done.countDown(); }
        });

        done.await(); // Wait for extractor and loader to complete
        System.out.println("ETL pipeline complete.");
    }

    static void loadToDatabase(ProcessedRecord r) { /* ... */ }
}
```

---

## 11.10 Knowledge Check

1. Why must condition variable checks always use `while` instead of `if`?
2. What happens to other threads waiting on a `CyclicBarrier` when one thread is interrupted?
3. Can a `Semaphore` be released by a different thread than the one that acquired it? Can `ReentrantLock`?
4. What makes `Phaser` superior to `CyclicBarrier` for iterative algorithms with a variable number of participants?
5. When would you use `SynchronousQueue` over `LinkedBlockingQueue`?

---

## 11.11 Interview-Style Questions

**Q: Explain the poison pill pattern and when it is preferable to using `ExecutorService.shutdown()`.**

> The poison pill pattern places a sentinel value (a special "stop processing" object) into a blocking queue to signal workers to terminate. Workers drain and process normally until they receive the poison pill, then exit. It is preferable to `ExecutorService.shutdown()` when: (1) the queue may contain items that must be drained before termination (shutdown only prevents new submissions, but it does not drain), (2) worker threads are not owned by an ExecutorService (e.g., they are virtual threads started directly), (3) you need ordered shutdown — all items before the pill are processed, then workers stop cleanly. The limitation: you must send exactly one poison pill per worker thread. If you don't know the exact number of workers, use a `CountDownLatch` to coordinate instead.

**Q: You have 8 virtual threads all waiting on a `CyclicBarrier` at phase 3. One thread throws an `Exception` before calling `await()`. What happens to the other 7 threads?**

> The 7 threads continue waiting indefinitely at the barrier — the barrier has no automatic mechanism to detect that one party has failed without calling `await()`. The barrier is "broken" only when a thread calls `await()` and is interrupted, or calls `await()` and is timed out. If one thread fails silently without calling `await()`, the other 7 threads will wait forever (deadlock). The correct pattern is: wrap the entire task in try-finally and always call `await()` (or `barrier.reset()`) in the finally block, even on failure. Better: wrap in try-catch and call `phaser.arrive()` unconditionally (fail-fast with a flag that other threads check after advance). `Phaser` handles this better than `CyclicBarrier` because you can deregister a failed party without breaking other waiting parties.
