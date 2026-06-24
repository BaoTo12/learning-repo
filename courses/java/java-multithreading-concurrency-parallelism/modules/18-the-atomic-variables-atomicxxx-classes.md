# The Atomic Variables — AtomicXXX Classes

The `java.util.concurrent.atomic` package provides a suite of classes—such as **`AtomicInteger`**, **`AtomicLong`**, **`AtomicBoolean`**, and **`AtomicReference`**—that support lock-free, thread-safe operations on single variables.

Under the hood, all these **`AtomicXXX`** classes discard traditional thread blocking and software locks in favor of hardware-level **Compare-And-Swap (CAS)** operations, which we explored in Module 17-2. In this module, we will analyze the internal architecture of atomic classes and see how they interface with low-level memory offsets.

---

## Implementing an Atomic Counter

Let's implement a thread-safe counter using `AtomicInteger`. Multiple threads will increment the counter concurrently:

```java
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.IntStream;

public class AtomicCounter {

    private final AtomicInteger counter = new AtomicInteger();

    public void increment() {
        // Performs an atomic, lock-free increment
        counter.getAndIncrement(); 
    }

    public int get() {
        return counter.get();
    }

    public static void main(String[] args) throws InterruptedException {
        AtomicCounter atomicCounter = new AtomicCounter();

        // Create two concurrent threads to increment the counter
        Thread t1 = new Thread(incrementLambda(atomicCounter, 1000), "t1");
        Thread t2 = new Thread(incrementLambda(atomicCounter, 1000), "t2");

        t1.start();
        t2.start();

        t1.join();
        t2.join();

        System.out.println("Counter now is: " + atomicCounter.get());
    }

    private static Runnable incrementLambda(AtomicCounter atomicCounter, int range) {
        return () -> IntStream.rangeClosed(1, range)
                .forEach(i -> atomicCounter.increment());
    }
}
```

*Figure 18.1: Thread-safe AtomicCounter implementation using AtomicInteger*

---

## How getAndIncrement() Works Under the Hood

The core method in our example is `counter.getAndIncrement()`. 
- In **Java 8**, this method delegates to `sun.misc.Unsafe.getAndAddInt()`.
- In **Java 9 and later**, it delegates to an internal, highly optimized version in `jdk.internal.misc.Unsafe` (utilizing VarHandles).

The **`Unsafe`** class is a collection of low-level, native methods that bypass JVM safety checks to perform direct memory manipulation. It acts as the bridge between Java and the CPU's hardware-level CAS instructions.

When a thread calls `getAndIncrement()`, the JVM executes a three-step optimistic loop:
1.  **Read (Volatile)**: The current value stored in the variable is read directly from memory (the **old value**).
2.  **Calculate**: The thread calculates the updated value (old value + 1) in its local stack.
3.  **CAS (Compare-And-Swap)**: The thread attempts to write the new value back to memory. The CPU compares the current memory value with the old value:
    - If they match, no other thread modified the variable. The CPU writes the new value and returns `true`.
    - If they do not match, another thread modified the variable first. The operation fails, returns `false`, and the thread **loops back to Step 1** to try again.

---

## Exploring the Unsafe Source Code

Let's examine the JDK source code for `Unsafe.getAndAddInt()` to see this loop in action:

```java
@HotSpotIntrinsicCandidate
public final int getAndAddInt(Object o, long offset, int delta) {
    int v;
    do {
        v = getIntVolatile(o, offset);
    } while (!weakCompareAndSetInt(o, offset, v, v + delta));
    return v;
}
```

*Figure 18.2: Volatile spin-loop inside Unsafe.getAndAddInt()*

### Understanding the Parameters

*   **`o`**: The target object on the heap (in our case, the `AtomicInteger` instance).
*   **`offset`**: The exact memory address offset of the target field within the object `o`. 

To perform direct memory operations on a private field, `AtomicInteger` must map the field's memory offset during class loading. It does so in a static block:

```java
private static final long VALUE = U.objectFieldOffset(AtomicInteger.class, "value");
```

*   **`getIntVolatile(o, offset)`**: Atomically retrieves the value of the integer field located at the memory `offset` of object `o`, using volatile memory barrier semantics to guarantee visibility.
*   **`weakCompareAndSetInt(o, offset, v, v + delta)`**: Executes the hardware-level CAS instruction. It compares the value at `offset` with `v`. If equal, it writes `v + delta` (where `delta` is 1 for an increment) and returns `true`. If a conflict occurs, it returns `false`, causing the `do-while` loop to execute again.

---

## Simplified Lock-Free Loop Logic

To understand the core behavior without low-level memory offsets, we can represent the logical flow of `getAndIncrement()` using the following simplified Java pseudocode:

```java
public final int getAndIncrement() {
    for (;;) {
        int current = get(); // Read current volatile value
        int next = current + 1; // Calculate next value
        
        // Attempt to update. If successful, return the old value.
        if (compareAndSet(current, next)) {
            return current;
        }
        // If CAS fails, loop spins and retries automatically
    }
}
```

> **Mental Model: Optimistic Spin-Locks**
> Traditional synchronization is **pessimistic**: a thread locks a resource, preventing anyone else from accessing it, even if no conflict occurs.
> 
> Atomic variables are **optimistic**: a thread attempts to update the variable assuming there is no conflict. Only if a conflict actually occurs (the CAS fails) does the thread retry. 
> 
> This retry loop is called a **spin-lock** or **optimistic spin**. It is highly efficient because the thread never sleeps or yields its CPU slice; it simply retries the cheap CAS operation instantly, maximizing throughput under low-to-medium contention.

Because `Unsafe` plays such a critical role in enabling these low-level concurrent operations, the next module is dedicated entirely to exploring `Unsafe` and its capabilities.

---

## Summary

*   **AtomicXXX Classes**: Part of the `java.util.concurrent.atomic` package, providing thread-safe, lock-free operations on single variables (`AtomicInteger`, `AtomicLong`, etc.).
*   **CAS Foundation**: Under the hood, all atomic operations rely on hardware-level Compare-And-Swap (CAS) instructions to update state atomically.
*   **Unsafe Delegation**: Native CAS operations are executed via the low-level `sun.misc.Unsafe` (Java 8) or `jdk.internal.misc.Unsafe` (Java 9+) classes.
*   **Memory Offsets**: To perform lock-free operations, atomic classes use `Unsafe.objectFieldOffset()` to map the exact memory location of their underlying private fields.
*   **Optimistic Spin Loops**: When an atomic operation fails due to concurrent modifications, the thread does not block. Instead, it spins in a retry loop, reads the updated value, and attempts the CAS again.
*   **Efficiency**: Atomic variables avoid the heavy scheduling and context-switching overhead of OS-level blocking locks, making them exceptionally fast in concurrent applications.