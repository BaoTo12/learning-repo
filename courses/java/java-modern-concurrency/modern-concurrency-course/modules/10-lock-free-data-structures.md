# Module 10: Lock-Free & Non-Blocking Data Structures

**Difficulty:** Advanced
**Estimated Study Time:** 6 hours
**Prerequisites:** Module 09 (Java Memory Model)

---

## Learning Objectives

By the end of this module you will be able to:
- Understand why lock-free algorithms outperform lock-based ones under high contention
- Implement a lock-free stack and queue using `AtomicReference` and CAS loops
- Choose between `AtomicLong` and `LongAdder` based on contention profile
- Use `StampedLock` for optimistic read patterns without blocking writers
- Explain `ConcurrentHashMap`'s segmented CAS + synchronized bucket strategy
- Identify and resolve the ABA problem in CAS-based algorithms

---

## 10.1 Why Lock-Free?

A **lock-based** algorithm uses mutual exclusion. While one thread holds a lock, other threads block and wait, causing context switches.

A **lock-free** algorithm guarantees that at least one thread makes progress. If one thread is paused, other threads can continue by retrying their operations.

```
Lock-based under high contention:
  Thread A:  [acquire lock] [work] [release lock]
  Thread B:  [blocked ..................] [acquire lock] [work]
  Thread C:  [blocked ..............................] [acquire lock]
  
  Cost: OS context switches, thread wake-ups, kernel mode transitions per operation

Lock-free under high contention (CAS-based):
  Thread A:  [read] [compute] [CAS→success]
  Thread B:  [read] [compute] [CAS→fail, retry] [read] [compute] [CAS→success]
  Thread C:  [read] [compute] [CAS→fail, retry] [CAS→success]
  
  Cost: CPU cycles for retry loops (all in user space, no kernel involvement)
```

**Lock-free is useful for:** high contention, short operations, and many CPU cores.
**Lock-free is less useful for:** complex operations, very low contention, or when writes outnumber reads.

---

## 10.2 Compare-And-Swap (CAS) — The Foundation

CAS is an atomic CPU instruction that:
1. Reads a memory location
2. Compares it to an expected value
3. If they match, writes a new value and returns `true`
4. If they do not match, does nothing and returns `false`

```
CAS(address, expected, new_value):
  if *address == expected:
      *address = new_value
      return true      ← Won the race
  else:
      return false     ← Lost the race, retry
```

### CAS in Java: `AtomicReference` and `VarHandle`

```java
import java.util.concurrent.atomic.AtomicReference;

// Atomic counter
AtomicInteger counter = new AtomicInteger(0);
counter.incrementAndGet();                    // Atomic CAS-based increment
counter.compareAndSet(expected, newValue);    // Explicit CAS
counter.getAndUpdate(x -> x * 2);            // CAS loop with function

// VarHandle CAS
import java.lang.invoke.*;

class AtomicNode {
    volatile int value;
    static final VarHandle VALUE;
    static {
        try { VALUE = MethodHandles.lookup().findVarHandle(AtomicNode.class, "value", int.class); }
        catch (Exception e) { throw new Error(e); }
    }

    boolean casValue(int expected, int updated) {
        return VALUE.compareAndSet(this, expected, updated);
    }
}
```

---

## 10.3 Lock-Free Stack

A Treiber stack — the canonical lock-free LIFO data structure.

```java
import java.util.concurrent.atomic.AtomicReference;

public class LockFreeStack<T> {
    // Node is immutable — no synchronization needed inside the node
    record Node<T>(T value, Node<T> next) {}

    private final AtomicReference<Node<T>> head = new AtomicReference<>(null);

    public void push(T value) {
        Node<T> newNode;
        Node<T> currentHead;
        do {
            currentHead = head.get();          // (1) Read current head
            newNode = new Node<>(value, currentHead); // (2) Create node pointing to it
        } while (!head.compareAndSet(currentHead, newNode)); // (3) CAS: retry if head changed
        // If another thread updates the head first, the CAS fails and the loop retries
    }

    public T pop() {
        Node<T> currentHead;
        do {
            currentHead = head.get();          // (1) Read current head
            if (currentHead == null) return null; // Empty stack
        } while (!head.compareAndSet(currentHead, currentHead.next())); // (2) CAS: remove head
        return currentHead.value();
    }
}
```

**Thread-safety proof:** The only shared variable is `head`, which is updated using CAS. If multiple threads try to update it at the same time, only one succeeds. Other threads retry without blocking.

---

## 10.4 Lock-Free Queue (Michael-Scott Queue)

The classic non-blocking MPMC (Multi-Producer Multi-Consumer) queue used in Java's `LinkedTransferQueue`.

```java
import java.util.concurrent.atomic.AtomicReference;

public class LockFreeQueue<T> {
    record Node<T>(T value, AtomicReference<Node<T>> next) {
        Node(T value) { this(value, new AtomicReference<>(null)); }
    }

    // Sentinel node: head.value is always null (just a pointer anchor)
    private final AtomicReference<Node<T>> head;
    private final AtomicReference<Node<T>> tail;

    public LockFreeQueue() {
        Node<T> sentinel = new Node<>(null);
        head = new AtomicReference<>(sentinel);
        tail = new AtomicReference<>(sentinel);
    }

    public void enqueue(T value) {
        Node<T> newNode = new Node<>(value);
        while (true) {
            Node<T> currentTail = tail.get();
            Node<T> tailNext = currentTail.next().get();

            if (tailNext == null) {
                // Tail is truly the last node — try to link our new node
                if (currentTail.next().compareAndSet(null, newNode)) {
                    // Successfully linked — advance tail (may fail if another thread does it)
                    tail.compareAndSet(currentTail, newNode);
                    return;
                }
            } else {
                // Tail is lagging behind — help advance it
                tail.compareAndSet(currentTail, tailNext);
            }
        }
    }

    public T dequeue() {
        while (true) {
            Node<T> currentHead = head.get();
            Node<T> currentTail = tail.get();
            Node<T> headNext = currentHead.next().get();

            if (currentHead == currentTail) {
                if (headNext == null) return null; // Empty queue
                tail.compareAndSet(currentTail, headNext); // Help tail advance
            } else {
                T value = headNext.value();
                if (head.compareAndSet(currentHead, headNext)) {
                    return value;
                }
            }
        }
    }
}
```

**Key insight — helping:** If a thread is paused while advancing the tail, another thread can help advance it. This ensures the queue always makes progress.

---

## 10.5 The ABA Problem and `AtomicStampedReference`

The ABA problem occurs when a thread reads value `A` and is paused. Another thread changes the value from `A` to `B` and back to `A`. When the first thread resumes, CAS succeeds because the value is `A`, but the underlying state has changed.

```
Thread A: reads head = Node@100 (value=A)
Thread B: pops Node@100, pops Node@200 (both gone), pushes new Node@100 (same address, value=A)
Thread A: CAS(head, Node@100, newNode) → SUCCEEDS even though the stack state changed
           This can cause memory corruption.
```

**Fix: `AtomicStampedReference`** (uses a version counter alongside the reference)

```java
import java.util.concurrent.atomic.AtomicStampedReference;

class ABASafeStack<T> {
    record Node<T>(T value, Node<T> next) {}

    private final AtomicStampedReference<Node<T>> head =
        new AtomicStampedReference<>(null, 0);

    public void push(T value) {
        int[] stamp = new int[1];
        Node<T> currentHead;
        Node<T> newNode;
        do {
            currentHead = head.get(stamp);      // Read reference AND stamp
            newNode = new Node<>(value, currentHead);
        } while (!head.compareAndSet(
                currentHead, newNode,
                stamp[0], stamp[0] + 1));       // Increment stamp on each CAS
        // The stamp prevents the ABA problem even if the reference address matches.
    }
}
```

**Production note:** In Java, the classic ABA problem is rare because garbage collection prevents immediate memory reuse. However, reusing objects from a pool can still cause this issue, requiring stamped references.

---

## 10.6 `LongAdder` vs `AtomicLong` — Striped Counters

`AtomicLong` uses a single CAS on one memory location. Under high contention, threads spin in retry loops competing for the same cache line.

`LongAdder` uses **cell striping** to distribute updates across multiple cells, summing them only when `sum()` is called.

```java
import java.util.concurrent.atomic.LongAdder;
import java.util.concurrent.atomic.AtomicLong;

// Throughput comparison under 64-thread contention:
AtomicLong atomic = new AtomicLong(0);
LongAdder adder = new LongAdder();

// Thread 1–64: atomic.incrementAndGet()  →  All threads compete for the same cache line
//   → Heavy CAS retry loop → ~15 million ops/sec on 16-core machine

// Thread 1–64: adder.increment()  →  Updates are distributed across cells
//   → Minimal contention → ~200 million ops/sec on same machine

// Reading:
long atomicValue = atomic.get();          // O(1), always exact
long adderValue = adder.sum();            // O(cells), approximate under concurrent updates
long adderReset = adder.sumThenReset();   // Atomic sum + reset to 0
```

**When to use which:**

| Feature | `AtomicLong` | `LongAdder` |
| :--- | :--- | :--- |
| **Single writer** | ✓ Better | ✓ OK |
| **Few threads (< 8)** | ✓ Better | ✓ OK |
| **Many threads (> 16)** | Contention | ✓ Much better |
| **Exact read at any time** | ✓ | ✗ Approximate |
| **Metrics/Statistics** | ✓ | ✓ Best choice |
| **Compare-and-set semantics** | ✓ | ✗ Not supported |

### `LongAdder` Internals: Striped64

```
LongAdder internals:

  base (volatile long) ← Used when no contention
  cells (Cell[]) ← Created lazily

  increment():
    1. Try to update the base directly.
    2. If the update fails, choose a cell based on the thread.
    3. CAS the chosen cell.
    4. If the cell update fails, try another cell or expand the cells.

  sum(): base + sum(cells[i].value for all i)
```

---

## 10.7 `StampedLock` — Optimistic Read Locking

`StampedLock` provides three modes:
- **Write lock**: Exclusive, like `ReentrantReadWriteLock` write lock
- **Read lock**: Shared, allows concurrent readers, blocks writers
- **Optimistic read**: No lock is acquired, just a version check

```java
import java.util.concurrent.locks.StampedLock;

class Point {
    private double x, y;
    private final StampedLock lock = new StampedLock();

    // Write operation: exclusive lock
    void move(double deltaX, double deltaY) {
        long stamp = lock.writeLock();
        try {
            x += deltaX;
            y += deltaY;
        } finally {
            lock.unlockWrite(stamp);
        }
    }

    // Optimistic read: zero-overhead path (no actual lock acquired)
    double distanceFromOrigin() {
        long stamp = lock.tryOptimisticRead(); // Returns a version stamp
        double currentX = x;                   // Read variables without holding a lock
        double currentY = y;

        if (!lock.validate(stamp)) {           // Check if a writer modified the data
            // If a write occurred, fall back to a read lock
            stamp = lock.readLock();
            try {
                currentX = x;
                currentY = y;
            } finally {
                lock.unlockRead(stamp);
            }
        }
        return Math.sqrt(currentX * currentX + currentY * currentY);
    }

    // Use a read lock when reading complex state
    String getCoordinates() {
        long stamp = lock.readLock();
        try {
            return "(" + x + ", " + y + ")";
        } finally {
            lock.unlockRead(stamp);
        }
    }
}
```

**Performance model:**

```
Scenario: 95% reads, 5% writes, 16 threads

ReentrantReadWriteLock:
  Read lock requires a CAS and blocks if a writer is active. → ~50ns/op
  Write lock: Exclusive acquire → ~200ns/op

StampedLock (optimistic):
  Optimistic read uses a version check. → ~5ns/op
  Optimistic retry rate: 5% → avg cost ~10ns/op (weighted)
  Write lock: Same as RRW → ~200ns/op
```

**Warning:** `StampedLock` is not reentrant. Acquiring the lock recursively will cause a deadlock. Do not use inside recursive code.

---

## 10.8 `ConcurrentHashMap` Internals

`ConcurrentHashMap` is lock-free for most operations, using synchronization only at the bucket level for updates.

### Read Path (Lock-Free)

```java
// get() is completely lock-free:
// 1. Compute hash → find bucket index
// 2. Read the bucket head
// 3. Traverse linked list or tree for key match — no locks
// 
// Reads do not acquire locks.

ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();
// get() → zero lock overhead regardless of concurrent writers
Integer value = map.get("key");
```

### Write Path (Fine-Grained Locking)

```java
// put() algorithm:
// 1. Hash key → find bucket
// 2. If the bucket is empty, insert the node using CAS.
// 3. If the bucket is not empty, synchronize on the bucket head.
//    Only the target bucket is locked.
//
// For a map with 16 buckets: 16 independent locks
// For a map with 512 buckets (after resize): 512 independent locks
// → Allows concurrent writes.
```

### Atomic Compound Operations

```java
ConcurrentHashMap<String, Integer> counters = new ConcurrentHashMap<>();

// Atomic put-if-absent (lock-free CAS):
counters.putIfAbsent("hits", 0);

// Atomic compute (acquires bucket lock):
counters.compute("hits", (key, val) -> val == null ? 1 : val + 1);

// Merge (atomic conditional update):
counters.merge("hits", 1, Integer::sum);

// computeIfAbsent (lazy initialization, lock-free if bucket empty):
Map<String, List<String>> groups = new ConcurrentHashMap<>();
groups.computeIfAbsent("group-A", k -> new ArrayList<>()).add("item");
// The list itself is not thread-safe.
```

### `ConcurrentHashMap` Size Counting

```java
// The size is approximate during concurrent updates.
int approxSize = map.size();

// For accurate size under concurrency:
long exactCount = map.mappingCount(); // Returns long, better for large maps

// The counter is updated on changes and summed when read.
```

---

## 10.9 `CopyOnWriteArrayList` — Optimized for Read-Heavy Collections

```java
import java.util.concurrent.CopyOnWriteArrayList;

CopyOnWriteArrayList<String> list = new CopyOnWriteArrayList<>();

// Writes copy the array, modify the copy, and replace it.
list.add("event");
// Writes are expensive, so use this only for rare updates.

// Reads use a snapshot without synchronization.
for (String s : list) { // Iterators use a snapshot and do not throw modification exceptions.
    System.out.println(s);
}
```

---

## 10.10 Hands-On Labs

### Lab 10.1 — Benchmark AtomicLong vs LongAdder

```java
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public class CounterBenchmark {
    static final int THREADS = 32;
    static final int OPS_PER_THREAD = 1_000_000;

    public static void main(String[] args) throws Exception {
        System.out.println("Testing AtomicLong...");
        AtomicLong atomic = new AtomicLong(0);
        long atomicTime = runBenchmark(() -> atomic.incrementAndGet());
        System.out.printf("AtomicLong: %,d ms, final = %,d%n", atomicTime, atomic.get());

        System.out.println("Testing LongAdder...");
        LongAdder adder = new LongAdder();
        long adderTime = runBenchmark(() -> adder.increment());
        System.out.printf("LongAdder:  %,d ms, final = %,d%n", adderTime, adder.sum());
    }

    static long runBenchmark(Runnable op) throws Exception {
        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(THREADS);

        for (int i = 0; i < THREADS; i++) {
            Thread.startVirtualThread(() -> {
                try {
                    start.await();
                    for (int j = 0; j < OPS_PER_THREAD; j++) op.run();
                } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                finally { done.countDown(); }
            });
        }

        long startTime = System.currentTimeMillis();
        start.countDown();
        done.await();
        return System.currentTimeMillis() - startTime;
    }
}
```

### Lab 10.2 — ABA Problem Demonstration

```java
import java.util.concurrent.atomic.*;

public class ABADemo {
    record Node(int value, Node next) {}

    // Broken: susceptible to ABA
    static AtomicReference<Node> brokenHead = new AtomicReference<>(null);

    // Fixed: stamped reference
    static AtomicStampedReference<Node> safeHead = new AtomicStampedReference<>(null, 0);

    // TODO: Implement pop() for both, demonstrate ABA failure with Thread.sleep()
    // between CAS read and CAS write in Thread A, with Thread B causing A→B→A transition
}
```

---

## 10.11 Interview-Style Questions

**Q: `ConcurrentHashMap.size()` is not exact during concurrent modifications. Why, and when does this matter?**

> `ConcurrentHashMap` tracks its size using a distributed counter (similar to `LongAdder`) — a `baseCount` volatile long plus an array of `CounterCell` objects, one per contending thread. Updates are distributed across cells to reduce CAS contention. `size()` sums all cells, but during concurrent modifications, cells may be updating between each read. The result can be slightly off. For most use cases (monitoring, capacity hints), this approximation is fine. For exact counts, use `mappingCount()` and call it from a quiesced state. If exact size is critical for business logic (e.g., `if (map.size() == MAX_ALLOWED_ENTRIES) reject()`), use external `AtomicInteger` tracking alongside the map.

**Q: When would you choose `StampedLock` over `ReentrantReadWriteLock`?**

> Choose `StampedLock` when: (1) the workload is extremely read-heavy (95%+ reads), (2) the read operation is short and deterministic (can bound the number of retries), and (3) you don't need reentrancy. The optimistic read path (`tryOptimisticRead` + `validate`) acquires no lock — it reads a version stamp, does the work, and checks if a writer interfered. Under low write frequency, this is nearly zero overhead. `ReentrantReadWriteLock` is better when: (1) reads are long (optimistic retry is expensive), (2) the code is recursive (needs reentrancy), (3) fairness is required (RRW supports fair mode), or (4) you need condition variables (`RRW.readLock()` supports conditions, `StampedLock` does not).
