# Module 09: Java Memory Model — The Foundation of Correct Concurrent Code

**Difficulty:** Advanced
**Estimated Study Time:** 5 hours
**Prerequisites:** Module 01 (concurrency evolution), Module 03 (JVM internals)

---

## Learning Objectives

By the end of this module you will be able to:
- Explain the Java Memory Model's `happens-before` relationship and derive visibility guarantees from it
- Predict the effect of instruction reordering by the compiler, JIT, and CPU on shared memory
- Use `volatile`, `synchronized`, and `VarHandle` correctly based on the guarantee each provides
- Identify and fix all four forms of publication safety failure
- Understand why double-checked locking was broken before Java 5 and why it works now
- Use `final` fields and immutability as a concurrency strategy

---

## 9.1 Why the Memory Model Exists

Most developers assume that a write in Thread A is immediately visible to Thread B. This assumption is wrong. Modern computing layers — the JIT compiler, the CPU execution engine, and the hardware cache hierarchy — all feel free to reorder and delay memory operations for performance. The Java Memory Model (JMM), defined in **JSR-133** and the Java Language Specification Chapter 17, is the formal contract that tells you exactly when visibility is guaranteed and when it is not.

### The Three Sources of Reordering

```
Write by Thread A                               Read by Thread B
─────────────────                               ──────────────────

Source 1: Compiler/JIT Reordering
  The JIT may move write(x=1) after write(y=2) if x and y appear
  independent. From Thread B's perspective, y=2 might be visible
  before x=1 — the opposite of source order.

Source 2: CPU Out-of-Order Execution
  Modern superscalar CPUs execute instructions out of program order
  to exploit instruction-level parallelism. Write x=1 might commit
  to the store buffer before y=2 is even issued, OR vice versa.

Source 3: Store Buffer / Invalidation Queue Lag (see Module 03)
  A write in Thread A's store buffer is invisible to Thread B until
  it drains into the shared L3 cache. Thread B might read a stale
  value from its own L1/L2 cache because the invalidation message
  hasn't been processed yet.
```

Without a memory model, every program that shares data between threads would be a data race and produce undefined behavior. The JMM defines exactly which operations create **synchronization actions** that force the hardware to flush and drain these buffers.

---

## 9.2 The Happens-Before Relationship

**Happens-before (HB)** is the JMM's core ordering concept. If operation A *happens-before* operation B, then:
1. All writes performed by A (and everything HB before A) are visible to B.
2. A is ordered before B — B cannot observe a state from before A completed.

### Built-in Happens-Before Rules

| Rule | Description |
| :--- | :--- |
| **Program Order** | Within a single thread, each action HB the next action in program order |
| **Monitor Lock** | `unlock()` of a monitor HB every subsequent `lock()` of the same monitor |
| **Volatile Write** | A `volatile` write HB every subsequent read of that same field |
| **Thread Start** | `Thread.start()` HB any action in the started thread |
| **Thread Join** | All actions in a thread HB `Thread.join()` returning in the joining thread |
| **Transitivity** | If A HB B and B HB C, then A HB C |

### Deriving Visibility from HB

```java
// Is x=42 guaranteed visible when the assertion runs?

int x = 0;
volatile boolean ready = false;

// Thread A:
x = 42;           // (1)
ready = true;     // (2) volatile write

// Thread B:
if (ready) {      // (3) volatile read
    assert x == 42; // (4) Is this guaranteed?
}
```

**Proof:**
- (1) HB (2) — program order rule (same thread)
- (2) HB (3) — volatile write HB volatile read of same field
- (3) HB (4) — program order rule (same thread)
- By transitivity: (1) HB (4) ✓

**The write `x = 42` is guaranteed visible at assertion (4).**

```java
// Negative example: Is x=42 visible without volatile?

int x = 0;
boolean ready = false; // NOT volatile

// Thread A:           // Thread B:
x = 42;               // while (!ready) {}  // spin
ready = true;         // assert x == 42;    // NOT guaranteed!
```

Without `volatile`, no HB relationship exists between Thread A's write to `ready` and Thread B's read. The JIT may hoist `ready` out of the while loop (reading it once into a register and never re-reading), creating an infinite loop. Or it may reorder `x = 42` after `ready = true`. Both are legal under the JMM.

---

## 9.3 `volatile`: Visibility, Not Atomicity

`volatile` provides two guarantees:
1. **Visibility**: Every write to the field is immediately visible to all threads (no caching in registers or L1/L2).
2. **Ordering**: Writes before the volatile write HB reads after the volatile read (see above).

**`volatile` does NOT provide atomicity for compound operations.**

```java
// WRONG: volatile does not make increment atomic
class BrokenCounter {
    volatile int count = 0;

    void increment() {
        count++; // NOT atomic — this is: read → increment → write
        // Between read and write, another thread may also read and write,
        // causing lost updates even though the field is volatile
    }
}

// CORRECT: Use AtomicInteger for compound read-modify-write
class CorrectCounter {
    final AtomicInteger count = new AtomicInteger(0);

    void increment() {
        count.incrementAndGet(); // Single atomic CAS operation
    }
}
```

### When to Use `volatile`

| Scenario | Use `volatile`? |
| :--- | :--- |
| Single writer, multiple readers | ✓ Yes |
| State flag (running/stopped) | ✓ Yes |
| Compound read-modify-write (counter, swap) | ✗ No — use AtomicXxx or synchronized |
| Protecting a block of related updates | ✗ No — use synchronized |

---

## 9.4 `synchronized`: Mutual Exclusion + Full Visibility

`synchronized` provides:
1. **Mutual exclusion**: Only one thread holds the monitor at a time.
2. **Full visibility**: On acquiring a monitor lock, a thread sees all writes from the previous holder. On releasing a monitor lock, all writes are visible to the next holder.

```java
class SafeCounter {
    private int count = 0; // Does NOT need to be volatile

    synchronized void increment() {
        count++;
        // monitor release: all writes flushed and visible on next lock acquisition
    }

    synchronized int get() {
        return count;
        // monitor acquire: reads fresh state from the previous holder
    }
}
```

**Key insight:** Inside a synchronized block, ALL fields (not just volatile fields) have fresh visibility. The monitor release/acquire pair acts as a full memory barrier.

### The Monitor Memory Barrier in Hardware

```
Thread A acquires lock:
  → Full load barrier: processes entire invalidation queue
     → All previous writes by the lock holder are now visible
     
Thread A releases lock:
  → Full store barrier: flushes entire store buffer to L3 cache
     → All writes inside the synchronized block become visible to the next acquirer
```

---

## 9.5 The `final` Field Guarantee

`final` fields have a special initialization safety guarantee: if an object is **safely published** (i.e., not via a data race), then all `final` fields are guaranteed to be fully initialized, even without synchronization.

```java
// Safe: final fields are guaranteed visible after safe publication
class ImmutablePoint {
    final int x;
    final int y;

    ImmutablePoint(int x, int y) {
        this.x = x;
        this.y = y;
        // After the constructor exits, x and y are frozen — no HB required to read them
    }
}

// Safe publication: store via volatile, synchronized, or other HB relationship
volatile ImmutablePoint sharedPoint;
sharedPoint = new ImmutablePoint(3, 4); // Thread B can safely read x and y
```

**Why `final` matters for performance:** Immutable objects can be freely shared without synchronization overhead, which is why `String`, `Integer`, and most record classes are immutable.

---

## 9.6 Publication Safety: Four Failure Modes

**Unsafe publication** occurs when an object is made visible to other threads before its construction is complete. This is one of the most subtle bugs in concurrent Java.

### Failure Mode 1: Leaking `this` Reference in Constructor

```java
// BROKEN: 'this' escapes the constructor
class EventListener {
    static EventListener instance; // Shared field

    EventListener() {
        instance = this; // UNSAFE: object not yet fully constructed
        // Other threads can see 'instance' before initialization is complete
        this.setup(); // Called before fields below are set!
    }

    final String name = "listener"; // May not be visible if 'this' escaped
}

// FIX: Publish after construction is complete
class SafeEventListener {
    private SafeEventListener() {}

    static SafeEventListener create() {
        SafeEventListener l = new SafeEventListener();
        // Only publish after constructor exits — all fields are fully initialized
        return l;
    }
}
```

### Failure Mode 2: Non-Final Non-Volatile Shared Field

```java
// BROKEN: not volatile, not synchronized — Thread B might see name = null
class UnsafeService {
    private String name;

    UnsafeService(String name) {
        this.name = name;
    }
}

static UnsafeService service; // Shared via plain field write

// Thread A:
service = new UnsafeService("orders"); // No HB guarantee for Thread B

// Thread B:
service.name // May be null! The JIT may reorder object reference publication
             // before the name field write inside the constructor
```

```java
// FIX 1: Make the shared field volatile
static volatile UnsafeService service;

// FIX 2: Use final fields in the class (stronger guarantee)
class SafeService {
    final String name;
    SafeService(String name) { this.name = name; }
}
```

### Failure Mode 3: Classic Double-Checked Locking (Pre-Java 5)

```java
// BROKEN before Java 5 (broken even in Java 5+ WITHOUT volatile):
class BrokenSingleton {
    private static BrokenSingleton instance;

    static BrokenSingleton getInstance() {
        if (instance == null) {          // (1) Read without lock
            synchronized (BrokenSingleton.class) {
                if (instance == null) {  // (2) Read with lock
                    instance = new BrokenSingleton(); // (3) Write with lock
                    // THE BUG: (3) can be seen by (1) as a partially constructed object
                    // JIT can reorder: allocate memory → publish reference → run constructor
                    // Thread B sees non-null instance with uninitialized fields!
                }
            }
        }
        return instance; // May return partially constructed object!
    }
}
```

```java
// CORRECT: volatile prevents the reordering that causes the bug
class CorrectSingleton {
    private static volatile CorrectSingleton instance;

    static CorrectSingleton getInstance() {
        if (instance == null) {          // (1) volatile read: safe
            synchronized (CorrectSingleton.class) {
                if (instance == null) {  // (2)
                    instance = new CorrectSingleton(); // (3) volatile write HB (1)
                    // volatile write establishes HB: constructor completes BEFORE reference is published
                }
            }
        }
        return instance;
    }
}

// BEST: Initialization-on-demand holder (zero synchronization cost, lazy, correct)
class HolderSingleton {
    private HolderSingleton() {}

    private static class Holder {
        // Class loading is guaranteed to be thread-safe by the JVM
        static final HolderSingleton INSTANCE = new HolderSingleton();
    }

    static HolderSingleton getInstance() {
        return Holder.INSTANCE; // No synchronization needed
    }
}
```

### Failure Mode 4: Mutable Object Shared Without Synchronization

```java
// BROKEN: HashMap is not thread-safe — concurrent modifications cause corruption
Map<String, String> cache = new HashMap<>();

// Thread A: cache.put("key", "value")
// Thread B: cache.get("key") — may see partial state or throw ConcurrentModificationException

// FIX: Use concurrent collection
Map<String, String> safeCache = new ConcurrentHashMap<>();

// Or: Use Collections.synchronizedMap (but individual operations are atomic, not compound operations)
Map<String, String> syncCache = Collections.synchronizedMap(new HashMap<>());
// Note: synchronized iteration still requires external synchronization:
synchronized (syncCache) {
    for (Map.Entry<String, String> entry : syncCache.entrySet()) { ... }
}
```

---

## 9.7 `VarHandle`: Fine-Grained Memory Ordering Control

Introduced in Java 9, `VarHandle` provides field-level access with explicit memory ordering modes. It replaces `sun.misc.Unsafe` for low-level concurrent programming.

```java
import java.lang.invoke.*;

class LockFreeStack<T> {
    private volatile Node<T> top = null;

    private static final VarHandle TOP;
    static {
        try {
            TOP = MethodHandles.lookup()
                .findVarHandle(LockFreeStack.class, "top", Node.class);
        } catch (ReflectiveOperationException e) {
            throw new ExceptionInInitializerError(e);
        }
    }

    record Node<T>(T value, Node<T> next) {}

    void push(T value) {
        Node<T> newNode;
        Node<T> currentTop;
        do {
            currentTop = (Node<T>) TOP.getAcquire(this); // Acquire semantics (load barrier)
            newNode = new Node<>(value, currentTop);
        } while (!TOP.compareAndSet(this, currentTop, newNode)); // CAS
    }

    T pop() {
        Node<T> currentTop;
        do {
            currentTop = (Node<T>) TOP.getAcquire(this);
            if (currentTop == null) return null;
        } while (!TOP.compareAndSet(this, currentTop, currentTop.next()));
        return currentTop.value();
    }
}
```

### VarHandle Memory Ordering Modes

| Method | Semantics | Hardware Cost |
| :--- | :--- | :--- |
| `get()` / `set()` | Plain — no ordering | Zero |
| `getOpaque()` / `setOpaque()` | Atomicity within thread only | Minimal |
| `getAcquire()` / `setRelease()` | One-way barrier (Acquire-Release) | Low (no full fence on x86) |
| `getVolatile()` / `setVolatile()` | Full volatile semantics | Medium |
| `compareAndSet()` | Full CAS with full barriers | Medium |

**Engineering rule:** Prefer `getAcquire`/`setRelease` for lock-free data structures on ARM architectures — they are cheaper than full `volatile` on weakly-ordered CPUs while still maintaining correctness.

---

## 9.8 Common JMM Pitfalls for Senior Engineers

### Pitfall 1: Benign Data Races (Incorrect Reasoning)

```java
// "This is fine — worst case it sets the value twice"
class LazyLoader {
    private Config config;

    Config getConfig() {
        if (config == null) { // DATA RACE: reading without synchronization
            config = loadConfig(); // DATA RACE: writing without synchronization
        }
        return config;
    }
}
// The JMM does NOT guarantee that a "benign" race produces any particular behavior.
// The JIT can cache 'config' in a register indefinitely (Thread B never sees the write).
// Always use volatile or synchronization — even for "harmless" races.
```

### Pitfall 2: Long/Double Non-Atomicity (32-bit JVMs)

```java
// On 32-bit JVMs: long and double writes are NOT guaranteed atomic!
long counter = 0L; // 64-bit value, written as two 32-bit stores on 32-bit JVMs

// Thread A: counter = Long.MAX_VALUE; // May write high 32 bits then low 32 bits
// Thread B: reads counter — may observe: (high from MAX_VALUE, low from 0) = garbage value!

// FIX on 32-bit JVMs:
volatile long counter = 0L; // volatile guarantees atomic 64-bit read/write
```

On 64-bit JVMs (which is the practical standard), plain `long` and `double` operations are atomic. But for maximum portability: always use `volatile` for shared `long`/`double` fields.

### Pitfall 3: Partially Constructed Object via `synchronized`

```java
// WRONG: synchronized does not prevent 'this' escape
class ThreadSafeBroken {
    private final Map<String, Object> data = new HashMap<>();

    ThreadSafeBroken(EventBus bus) {
        bus.register(this); // 'this' escapes before constructor completes
        // Between register() and end of constructor, bus may call methods on 'this'
        // while 'data' is still being initialized by the super constructor
    }
}
// Even though HashMap is in a final field, 'this' escape before
// constructor completes exposes a partially visible final field.

// FIX: Factory method pattern
class ThreadSafeCorrect {
    private final Map<String, Object> data;

    private ThreadSafeCorrect() {
        this.data = new HashMap<>();
    }

    static ThreadSafeCorrect register(EventBus bus) {
        ThreadSafeCorrect obj = new ThreadSafeCorrect();
        // Constructor is complete — 'this' can now safely escape
        bus.register(obj);
        return obj;
    }
}
```

---

## 9.9 Hands-On Labs

### Lab 9.1 — Observe Memory Visibility Failure

```java
// This program may loop forever on some JVMs and JIT configurations:
public class VisibilityFailure {
    static boolean stop = false; // NOT volatile

    public static void main(String[] args) throws InterruptedException {
        Thread worker = new Thread(() -> {
            long count = 0;
            while (!stop) { // JIT may hoist this to: if (!stop) { while (true) {} }
                count++;
            }
            System.out.println("Stopped. Count = " + count);
        });
        worker.start();

        Thread.sleep(1000);
        stop = true; // Worker thread may NEVER see this update!
        System.out.println("Set stop = true");
        worker.join(2000);

        if (worker.isAlive()) {
            System.out.println("VISIBILITY FAILURE: worker still running!");
            worker.interrupt();
        }
    }
}
// Fix: change 'static boolean stop' to 'static volatile boolean stop'
```

### Lab 9.2 — Validate HB with Phaser

```java
import java.util.concurrent.Phaser;

// Demonstrate happens-before via Phaser arrival/advance
public class HappensBefore {
    static int sharedData = 0;
    static final Phaser PHASER = new Phaser(2); // 2 parties

    public static void main(String[] args) throws InterruptedException {
        Thread writer = new Thread(() -> {
            sharedData = 42;       // (1) Write
            PHASER.arriveAndAwaitAdvance(); // (2) HB barrier
        });

        Thread reader = new Thread(() -> {
            PHASER.arriveAndAwaitAdvance(); // (3) HB barrier — both threads pass together
            System.out.println(sharedData); // (4) Must print 42
            // HB chain: (1) → (2) HB (3) → (4) ✓
        });

        writer.start();
        reader.start();
        writer.join();
        reader.join();
    }
}
```

### Lab 9.3 — Double-Checked Locking Fix Verification

Implement both broken and correct versions of a singleton. Use JMH (Module 11) to measure the performance difference between:
1. Synchronized `getInstance()` on every call
2. Volatile double-checked locking
3. Initialization-on-demand holder

Expected result: Holder pattern ≈ zero overhead (single class-load check), DCL ≈ 1 volatile read per call, synchronized ≈ monitor acquire per call.

---

## 9.10 Knowledge Check

1. Thread A writes `x = 10` then `y = 20`. Thread B reads `y` and sees `20`. Is Thread B guaranteed to see `x = 10`? Under what condition?
2. Why does making `count++` on a volatile field NOT make the increment thread-safe?
3. What two reorderings does `volatile` on the singleton prevent in the double-checked locking pattern?
4. What is the JMM guarantee for `final` fields after safe publication?
5. What is the difference between `VarHandle.getAcquire()` and `VarHandle.getVolatile()`?

---

## 9.11 Interview-Style Questions

**Q: Two developers are arguing. Developer A says: "I don't need volatile because I'm using a 64-bit JVM and long reads/writes are atomic." Developer B says: "Atomicity and visibility are different things." Who is correct?**

> Developer B is correct. On a 64-bit JVM, `long` and `double` reads/writes are indeed atomic (a single machine instruction). However, atomicity does not imply visibility. Without `volatile`, the JIT compiler may cache the value in a CPU register for the reading thread, preventing it from ever seeing the write. Thread B's register may hold the old value indefinitely. Atomicity prevents tearing (seeing half of a 64-bit write); visibility (via the happens-before relationship) ensures that once written, other threads can see the new value. You need `volatile` for shared `long` fields to ensure both atomicity (on 32-bit JVMs) and visibility (on all JVMs).

**Q: Explain why the double-checked locking pattern for singletons was broken before Java 5 and what specific change in Java 5 fixed it.**

> Before Java 5 (Java Memory Model revision JSR-133), the JMM did not guarantee that writes inside a synchronized block were ordered before the publication of the reference outside the synchronized block. The JIT could legally reorder the singleton's constructor operations relative to the assignment `instance = new Singleton()`, causing a thread to see a non-null `instance` reference pointing to an object whose fields were not yet initialized. JSR-133 strengthened the JMM by: (1) strengthening volatile semantics to include a store-load barrier — a volatile write cannot be reordered before any prior write (constructors complete before the volatile assignment is visible), and (2) defining the happens-before relationship precisely. With `volatile`, the volatile write to `instance` HB every subsequent volatile read, guaranteeing that the fully constructed object is visible to any thread that reads a non-null `instance` reference.

**Q: What is "safe publication" and how many ways can you safely publish an object in Java?**

> Safe publication means making an object reference visible to other threads in a way that guarantees they see a fully initialized object (all fields with their correct values). There are exactly four ways: (1) Store the reference in a `volatile` or `AtomicReference` field. (2) Store the reference in a `final` field of a properly constructed object. (3) Store the reference in a field that is properly guarded by a lock (`synchronized`), where readers also hold the same lock when reading. (4) Use a static initializer or class-loading mechanism (e.g., static final field initialization, enum constants). Anything else — including assigning to a plain (non-volatile, non-synchronized) field — may leave other threads seeing a partially constructed object.
