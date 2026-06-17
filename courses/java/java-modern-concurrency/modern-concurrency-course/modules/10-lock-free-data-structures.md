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

A **lock-based** algorithm uses mutual exclusion: while Thread A holds a lock, all other threads block, burning CPU in the OS scheduler and generating context switches.

A **lock-free** algorithm guarantees that at least one thread makes progress at all times, regardless of how other threads are scheduled. If Thread A is preempted mid-operation, Thread B simply retries using the unchanged state, rather than blocking.

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

**When lock-free wins:** High contention, short critical sections, many cores.
**When lock-free loses:** Complex multi-word operations (locks remain simpler), very low contention (lock overhead is negligible), writes >> reads (CAS retries dominate).

---

## 10.2 Compare-And-Swap (CAS) — The Foundation

CAS is a single atomic CPU instruction (`LOCK CMPXCHG` on x86, `STLXR`/`LDAXR` on ARM) that atomically:
1. Reads a memory location
2. Compares it to an expected value
3. If they match: writes a new value and returns `true`
4. If they don't match: does nothing and returns `false`

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

// Classic lock-free counter using AtomicInteger
AtomicInteger counter = new AtomicInteger(0);
counter.incrementAndGet();                    // Atomic CAS-based increment
counter.compareAndSet(expected, newValue);    // Explicit CAS
counter.getAndUpdate(x -> x * 2);            // CAS loop with function

// Modern: VarHandle CAS (lower overhead, more control)
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
        // If another thread pushed between (1) and (3): CAS fails, loop retries
    }

    public T pop() {
        Node<T> currentHead;
        do {
            currentHead = head.get();          // (1) Read current head
            if (currentHead == null) return null; // Empty stack
        } while (!head.compareAndSet(currentHead, currentHead.next())); // (2) CAS: remove head
        return currentHead.value();
    }

    // Linearization point: push → successful CAS at (3)
    //                       pop  → successful CAS at (2)
    // Every operation appears to take effect at exactly one instant
}
```

**Thread-safety proof:** The only mutable shared state is `head`. It is only ever updated via CAS. If Thread A and Thread B both try to push simultaneously, only one CAS succeeds. The loser re-reads the new head (which now includes the winner's node) and retries — no data is lost, no thread blocks.

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

**Key insight — helping:** If Thread A starts advancing the tail but gets preempted, Thread B detects the lagging tail and helps advance it before its own operation. This ensures the queue always makes progress even if individual threads stall.

---

## 10.5 The ABA Problem and `AtomicStampedReference`

The ABA problem: Thread A reads value `A`, gets preempted. Thread B changes value `A → B → A`. Thread A resumes, CAS sees `A` again and succeeds — but the state has changed in a way CAS cannot detect.

```
Thread A: reads head = Node@100 (value=A)
Thread B: pops Node@100, pops Node@200 (both gone), pushes new Node@100 (same address, value=A)
Thread A: CAS(head, Node@100, newNode) → SUCCEEDS even though the stack state changed!
           The old Node@200 is now a dangling reference in newNode.next — memory corruption!
```

**Fix: `AtomicStampedReference`** (version counter alongside the reference)

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
        // ABA is now impossible: even if address matches, stamp won't
    }
}
```

**Production note:** In garbage-collected languages like Java, the classic ABA problem (address reuse) is less common because GC prevents immediate address recycling. However, logical ABA (same object recycled via object pool) still requires stamped references.

---

## 10.6 `LongAdder` vs `AtomicLong` — Striped Counters

`AtomicLong` uses a single CAS on one memory location. Under very high contention (hundreds of threads incrementing simultaneously), threads spin in retry loops competing for the same cache line.

`LongAdder` uses **cell striping**: it distributes updates across multiple `Cell` objects (one per contending thread), summing them only when `sum()` is called.

```java
import java.util.concurrent.atomic.LongAdder;
import java.util.concurrent.atomic.AtomicLong;

// Throughput comparison under 64-thread contention:
AtomicLong atomic = new AtomicLong(0);
LongAdder adder = new LongAdder();

// Thread 1–64: atomic.incrementAndGet()  →  All fight for same cache line
//   → Heavy CAS retry loop → ~15 million ops/sec on 16-core machine

// Thread 1–64: adder.increment()  →  Distributed across ~16 Cell objects
//   → Minimal contention → ~200 million ops/sec on same machine

// Reading:
long atomicValue = atomic.get();          // O(1), always exact
long adderValue = adder.sum();            // O(cells), approximate (cells updated concurrently)
long adderReset = adder.sumThenReset();   // Atomic sum + reset to 0
```

**When to use which:**

| | `AtomicLong` | `LongAdder` |
| :--- | :--- | :--- |
| **Single writer** | ✓ | ✓ |
| **Few threads (< 8)** | ✓ Better | ✓ OK |
| **Many threads (> 16)** | Contention | ✓ Much better |
| **Exact read at any time** | ✓ | ✗ Approximate |
| **Metrics/Statistics** | ✓ | ✓ Best choice |
| **Compare-and-set semantics** | ✓ | ✗ Not supported |

### `LongAdder` Internals: Striped64

```
LongAdder internals:

  base (volatile long) ← Used when no contention
  cells (Cell[]) ← Lazily created, sized to power of 2

  increment():
    1. Try to CAS base directly (fast path, no contention)
    2. If CAS fails: probe thread's cell slot (threadLocalRandomProbe % cells.length)
    3. CAS the chosen cell
    4. If cell CAS fails: rehash probe, try another cell or expand cells array

  sum(): base + sum(cells[i].value for all i)
```

---

## 10.7 `StampedLock` — Optimistic Read Locking

`StampedLock` (Java 8+) provides three modes:
- **Write lock**: Exclusive, like `ReentrantReadWriteLock` write lock
- **Read lock**: Shared, allows concurrent readers, blocks writers
- **Optimistic read**: Zero overhead — no actual lock, just a version check

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
        long stamp = lock.tryOptimisticRead(); // Returns current version stamp
        double currentX = x;                   // Read without holding any lock
        double currentY = y;

        if (!lock.validate(stamp)) {           // Check: did a writer modify during read?
            // A write occurred — fall back to a real read lock
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

    // Read lock: use when optimistic read is too risky (e.g., complex multi-field reads)
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
  Read lock:  CAS on reader count + potential wait if writer pending → ~50ns/op
  Write lock: Exclusive acquire → ~200ns/op

StampedLock (optimistic):
  Optimistic read: 2 instructions (tryOptimisticRead + validate) → ~5ns/op
  Optimistic retry rate: 5% → avg cost ~10ns/op (weighted)
  Write lock: Same as RRW → ~200ns/op
```

**Warning:** `StampedLock` is NOT reentrant. A thread that holds a stamp and tries to acquire another lock will deadlock. Do not use inside recursive code.

---

## 10.8 `ConcurrentHashMap` Internals

`ConcurrentHashMap` in Java 8+ uses a hybrid strategy: **lock-free for most operations, bucket-level synchronization only on structural changes**.

### Read Path (Lock-Free)

```java
// get() is completely lock-free:
// 1. Compute hash → find bucket index
// 2. Read bucket head via volatile read (guaranteed visibility)
// 3. Traverse linked list or tree for key match — no locks
// 
// The entire read path uses volatile reads and CAS-inserted nodes.
// Zero lock acquisition for ANY read operation.

ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();
// get() → zero lock overhead regardless of concurrent writers
Integer value = map.get("key");
```

### Write Path (Fine-Grained Locking)

```java
// put() algorithm:
// 1. Hash key → find bucket
// 2. If bucket is EMPTY: CAS a new node into the array slot (lock-free!)
// 3. If bucket is NON-EMPTY: synchronized(bucketHead) { insert/update }
//    Only the single bucket is locked, not the entire map
//
// For a map with 16 buckets: 16 independent locks
// For a map with 512 buckets (after resize): 512 independent locks
// → Allows ~16–512 concurrent writers simultaneously

// Structural operations (resize, TreeBin conversion):
// When a bucket exceeds 8 entries → convert to Red-Black tree (TreeBin)
// This conversion uses synchronized(bucketHead) but is amortized rare
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
// WARNING: The List itself is NOT thread-safe — use CopyOnWriteArrayList if shared
```

### `ConcurrentHashMap` Size Counting

```java
// size() is NOT guaranteed to be exact during concurrent modifications
int approxSize = map.size();

// For accurate size under concurrency:
long exactCount = map.mappingCount(); // Returns long, better for large maps

// Implementation: ConcurrentHashMap uses a LongAdder-like counter
// Incremented on put, decremented on remove — approximate until all cells summed
```

---

## 10.9 `CopyOnWriteArrayList` — Optimized for Read-Heavy Collections

```java
import java.util.concurrent.CopyOnWriteArrayList;

CopyOnWriteArrayList<String> list = new CopyOnWriteArrayList<>();

// Write: copies the entire underlying array, mutates the copy, replaces atomically
list.add("event");
// Cost: O(n) for every write — suitable ONLY for rare writes

// Read: uses the current snapshot — zero synchronization
for (String s : list) { // Iterator uses a snapshot — never throws ConcurrentModificationException
    System.out.println(s);
}

// Best use case: event listener registries, configuration lists
// Reads: thousands per second
// Writes: a few per application lifecycle
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
