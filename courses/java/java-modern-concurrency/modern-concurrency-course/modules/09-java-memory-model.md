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

Many developers assume a write in one thread is immediately visible to another. This is incorrect. The JIT compiler, the CPU, and the cache hierarchy reorder and delay memory operations to improve performance. The Java Memory Model (JMM) defines when memory writes become visible to other threads.

### The Three Sources of Reordering

```
Write by Thread A                               Read by Thread B
─────────────────                               ──────────────────

Source 1: Compiler/JIT Reordering
  The JIT may move write(x=1) after write(y=2) if x and y appear
  independent. From Thread B's perspective, y=2 might be visible
  before x=1 — the opposite of source order.

Source 2: CPU Out-of-Order Execution
  Modern CPUs execute instructions out of program order to exploit
  parallelism. Write x=1 might commit to the store buffer before
  y=2 is even issued, or vice versa.

Source 3: Store Buffer / Invalidation Queue Lag
  A write in Thread A's store buffer is invisible to Thread B until
  it drains into the shared L3 cache. Thread B might read a stale
  value from its own L1/L2 cache because the invalidation message
  has not been processed yet.
```

Without a memory model, concurrent programs would have data races and undefined behavior. The JMM defines synchronization actions that force the hardware to flush memory buffers.

---

## 9.2 The Happens-Before Relationship

**Happens-before (HB)** is the core ordering concept of the JMM. If operation A *happens-before* B, then:
1. Writes made before or during A are visible to B.
2. A is ordered before B, so B cannot see a state from before A finished.

### Built-in Happens-Before Rules

| Rule | Description |
| :--- | :--- |
| **Program Order** | In a single thread, each action happens-before the next action |
| **Monitor Lock** | Unlocking a monitor happens-before locking that same monitor again |
| **Volatile Write** | Writing to a volatile field happens-before reading that same field |
| **Thread Start** | Starting a thread happens-before any action in that thread |
| **Thread Join** | All actions in a thread happen-before join returns |
| **Transitivity** | If A happens-before B, and B happens-before C, then A happens-before C |

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
- By transitivity: (1) HB (4)

**The write `x = 42` is guaranteed visible at assertion (4).**

```java
// Negative example: Is x=42 visible without volatile?

int x = 0;
boolean ready = false; // NOT volatile

// Thread A:           // Thread B:
x = 42;               // while (!ready) {}  // spin
ready = true;         // assert x == 42;    // NOT guaranteed!
```

Without `volatile`, there is no happens-before relationship between the write and the read. The compiler might load the variable into a register once and never re-read it, causing an infinite loop. The compiler or CPU might also reorder the write after the flag update. Both are allowed under the JMM.

---

## 9.3 `volatile`: Visibility, Not Atomicity

`volatile` guarantees:
1. **Visibility**: Every write is immediately visible to all threads.
2. **Ordering**: Memory operations are not reordered around the volatile variable.

**`volatile` does not make compound operations atomic.**

```java
// WRONG: volatile does not make increment atomic
class BrokenCounter {
    volatile int count = 0;

    void increment() {
        count++; // Read, increment, and write. This is not atomic.
        // Another thread can read and write between these steps, causing lost updates.
    }
}

// CORRECT: Use AtomicInteger for compound read-modify-write
class CorrectCounter {
    final AtomicInteger count = new AtomicInteger(0);

    void increment() {
        count.incrementAndGet(); // Atomic increment.
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
1. **Mutual exclusion**: Only one thread can hold the lock at a time.
2. **Visibility**: Acquiring a lock reads the latest updates, and releasing a lock makes all updates visible to other threads.

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

**Key insight:** Inside a synchronized block, all variable updates are visible to other threads. Releasing and acquiring a lock acts as a memory barrier.

### The Monitor Memory Barrier in Hardware

```
Acquiring a lock:
  → Reads the latest values from memory.
     
Releasing a lock:
  → Writes all changes to memory.
```

---

## 9.5 The `final` Field Guarantee

If an object is safely published, all `final` fields are guaranteed to be fully initialized without synchronization.

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

**Why `final` matters for performance:** Immutable objects can be shared without synchronization overhead, which is why classes like `String` and `Integer` are immutable.

---

## 9.6 Publication Safety: Four Failure Modes

**Unsafe publication** happens when an object becomes visible to other threads before its constructor finishes. This can cause subtle bugs.

### Failure Mode 1: Leaking `this` Reference in Constructor

```java
// BROKEN: 'this' escapes the constructor
class EventListener {
    static EventListener instance; // Shared field

    EventListener() {
        instance = this; // Unsafe: the object is not fully constructed yet
        // Other threads can see the instance before it is fully initialized.
        this.setup(); // Called before fields below are set!
    }

    final String name = "listener"; // May not be visible if 'this' escaped
}

// FIX: Publish after construction is complete
class SafeEventListener {
    private SafeEventListener() {}

    static SafeEventListener create() {
        SafeEventListener l = new SafeEventListener();
        // Publish only after the constructor finishes so all fields are initialized.
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
service.name // May be null because the compiler or CPU can publish the reference before initializing the fields.
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
                    // The bug: Another thread can see a partially constructed object.
                    // The compiler can reorder memory allocation and reference publication before running the constructor.
                    // Other threads see a non-null reference but uninitialized fields.
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
                    // The volatile write ensures the constructor finishes before the reference is published.
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
        // The JVM ensures class loading is thread-safe.
        static final HolderSingleton INSTANCE = new HolderSingleton();
    }

    static HolderSingleton getInstance() {
        return Holder.INSTANCE; // No synchronization required
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

// Or: Use Collections.synchronizedMap, though individual operations are atomic but compound operations are not.
Map<String, String> syncCache = Collections.synchronizedMap(new HashMap<>());
// Note: Iterating over a synchronized map still requires locking.
synchronized (syncCache) {
    for (Map.Entry<String, String> entry : syncCache.entrySet()) { ... }
}
```

---

## 9.7 `VarHandle`: Fine-Grained Memory Ordering Control

`VarHandle` provides field-level access with explicit memory ordering modes. It replaces `sun.misc.Unsafe` for low-level concurrent code.

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

**Engineering rule:** Use `getAcquire`/`setRelease` for lock-free structures on ARM CPUs. They are faster than full `volatile` on weakly-ordered processors while ensuring correctness.

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
```
The JMM does not guarantee that a benign race behaves correctly. The JIT compiler can cache the field in a register, so other threads never see the write. Always use volatile or synchronization.

### Pitfall 2: Long/Double Non-Atomicity (32-bit JVMs)

```java
// On 32-bit JVMs: long and double writes are NOT guaranteed atomic!
long counter = 0L; // 64-bit value, written as two 32-bit stores on 32-bit JVMs

// Thread A: counter = Long.MAX_VALUE; // May write high 32 bits then low 32 bits
// Thread B: reads counter — may observe: (high from MAX_VALUE, low from 0) = garbage value!

// FIX on 32-bit JVMs:
volatile long counter = 0L; // volatile guarantees atomic 64-bit read/write
```

On 64-bit JVMs, plain `long` and `double` operations are atomic. For portability, use `volatile` for shared `long` and `double` fields.

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
```
Letting `this` escape before the constructor finishes exposes a partially visible final field.

```java
// FIX: Factory method pattern
class ThreadSafeCorrect {
    private final Map<String, Object> data;

    private ThreadSafeCorrect() {
        this.data = new HashMap<>();
    }

    static ThreadSafeCorrect register(EventBus bus) {
        ThreadSafeCorrect obj = new ThreadSafeCorrect();
        // The constructor has finished, so the reference can be safely shared.
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
            while (!stop) { // The compiler might hoist this check, causing an infinite loop.
                count++;
            }
            System.out.println("Stopped. Count = " + count);
        });
        worker.start();

        Thread.sleep(1000);
        stop = true; // The worker thread might not see this update.
        System.out.println("Set stop = true");
        worker.join(2000);

        if (worker.isAlive()) {
            System.out.println("VISIBILITY FAILURE: worker still running!");
            worker.interrupt();
        }
    }
}
// Fix: Declare the variable as volatile.
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
            // HB chain: (1) → (2) HB (3) → (4)
        });

        writer.start();
        reader.start();
        writer.join();
        reader.join();
    }
}
```

### Lab 9.3 — Double-Checked Locking Fix Verification

Implement both broken and correct versions of a singleton. Use JMH (Module 13) to measure the performance difference between:
1. Synchronized `getInstance()` on every call
2. Volatile double-checked locking
3. Initialization-on-demand holder

Expected result: The holder pattern has near-zero overhead. Double-checked locking requires one volatile read per call. Synchronization requires acquiring a monitor lock on every call.

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
