# Synchronized on Class Objects and Thread Blocking Scenarios

In the previous module, we explored how the `synchronized` keyword works at the bytecode level in the context of instance methods and blocks. In this module, we will examine class-level synchronization using **static synchronized methods** and analyze five critical thread blocking scenarios.

---

## Static Methods and Class-Level Locking

When you synchronize a **static method**, the lock cannot be acquired on `this` because there is no instance associated with a static method context. Instead, the lock/monitor is acquired on the **Class object** (e.g., `Counter.class`). Since only one `Class` object exists per JVM per class, only one thread can execute inside a static synchronized method per class, irrespective of the number of instances it has.

Here is a `Counter` class using static synchronized methods:

```java
class Counter {
    private static int value;

    public static synchronized void increment() {
        ++value;
    }

    public static int get() {
        return value;
    }
}
```

Similarly, we can declare static synchronized methods for general mathematical operations, such as summing values:

```java
public class SynchronizedMethods {

    private static int staticSum = 0;

    public static synchronized void syncStaticCalculate() {
        staticSum = staticSum + 1;
    }
    
    public static int getStaticSum() {
        return staticSum;
    }
}
```

We can verify that this static method prevents race conditions with a concurrent JUnit test:

```java
@Test
public void givenMultiThread_whenStaticSyncMethod() throws InterruptedException {
    ExecutorService service = Executors.newCachedThreadPool();

    IntStream.range(0, 1000)
      .forEach(count -> 
        service.submit(SynchronizedMethods::syncStaticCalculate));
    service.awaitTermination(100, TimeUnit.MILLISECONDS);

    assertEquals(1000, SynchronizedMethods.getStaticSum());
}
```

Disassembling the static `increment()` method yields the following bytecode:

```text
public static synchronized void increment();
  Code:
     0: getstatic     #2                  // Field value:I
     3: iconst_1
     4: iadd
     5: putstatic     #2                  // Field value:I
     8: return
```

Just like instance synchronized methods, the JVM handles synchronization implicitly via the method access flags (in this case, combined with `ACC_STATIC`).

We can write a static method with equivalent lock semantics using a synchronized block. If the method is static, we pass the class name (e.g., `ClassName.class`) in place of an object reference, and the class object acts as the monitor:

```java
class Counter {
    private static int value;

    public static void increment() {
        synchronized (Counter.class) { // Explicit class lock
            ++value;
        }
    }
}
```

Similarly, we can implement a static synchronized block for general tasks:

```java
public class SynchronizedBlocks {

    private static int staticCount = 0;

    public static void performStaticSyncTask() {
        synchronized (SynchronizedBlocks.class) {
            staticCount = staticCount + 1;
        }
    }

    public static int getStaticCount() {
        return staticCount;
    }
}
```

We can verify that the static synchronized block passes the concurrent test suite:

```java
@Test
public void givenMultiThread_whenStaticSyncBlock() throws InterruptedException {
    ExecutorService service = Executors.newCachedThreadPool();

    IntStream.range(0, 1000)
      .forEach(count -> 
        service.submit(SynchronizedBlocks::performStaticSyncTask));
    service.awaitTermination(100, TimeUnit.MILLISECONDS);

    assertEquals(1000, SynchronizedBlocks.getStaticCount());
}
```

The bytecode for this block shows the explicit use of `monitorenter` and `monitorexit`:

```text
public static void increment();
  Code:
     0: ldc           #3                  // class org/vit/threads/Counter
     2: dup
     3: astore_0
     4: monitorenter                     // Gaining class monitor ownership
     5: getstatic     #2                  // Field value:I
     8: iconst_1
     9: iadd
    10: putstatic     #2                  // Field value:I
    13: aload_0
    14: monitorexit                      // Releasing class monitor ownership
    15: goto          23
    18: astore_1
    19: aload_0
    20: monitorexit
    21: aload_1
    22: athrow
    23: return
```

> **Insight: Lock Targets**
> Synchronizing on a class object (`Counter.class`) and synchronizing on an instance object (`this`) are completely independent locks. Gaining a lock on an instance does not block other threads from gaining a lock on the class, and vice versa.

---

## Thread Blocking Scenarios

Understanding how static and instance locks interact is a key multithreading skill. Let's analyze five common scenarios using the following class:

```java
public class ThreadBlockingDemo {
    // 1. Non-Static Synchronized method
    public synchronized void nonStaticSyncMethod1() {
        // Critical section
    }

    // 2. Non-Static Synchronized method
    public synchronized void nonStaticSyncMethod2() {
        // Critical section
    }

    // 3. Static Synchronized method
    public static synchronized void staticSyncMethod1() {
        // Critical section
    }

    // 4. Static Synchronized method
    public static synchronized void staticSyncMethod2() {
        // Critical section
    }

    // 5. Instance Methods with No Synchronization
    public void instanceMethod1() {
        // No lock
    }

    public void instanceMethod2() {
        // No lock
    }

    // 6. Synchronized block on 'this'
    public void syncBlockWithThisObject() {
        synchronized (this) {
            // Guarded by 'this'
        }
    }

    // 7. Synchronized block on Class object
    public void syncBlockWithClassObject() {
        synchronized (ThreadBlockingDemo.class) {
            // Guarded by Class object
        }
    }
}
```

Assume we have a single instance of `ThreadBlockingDemo` shared by two threads, `T1` and `T2`, executing concurrently.

---

### Scenario #1: Both threads execute non-synchronized methods
*   **Context:** `T1` is executing `instanceMethod1()` and `T2` is executing `instanceMethod2()`.
*   **Question:** Will these two threads block each other?
*   **Answer:** **No**
*   **Reason:** Since neither method uses synchronization, no monitors are acquired. The threads run concurrently without blocking. Note that if these methods mutate shared state, a race condition will occur.

---

### Scenario #2: Threads executing different synchronized instance methods
*   **Context:** While `T1` is executing `nonStaticSyncMethod1()`, `T2` attempts to execute `nonStaticSyncMethod2()`.
*   **Question:** Will these two threads block each other?
*   **Answer:** **Yes**
*   **Reason:** Both methods are instance-synchronized, meaning they both require the lock on the shared `this` object. Since `T1` holds this lock, `T2` is transitioned to the `BLOCKED` state until `T1` completes its method and releases the monitor.

---

### Scenario #3: Threads executing different synchronized static methods
*   **Context:** While `T1` is executing `staticSyncMethod1()`, `T2` attempts to execute `staticSyncMethod2()`.
*   **Question:** Will these two threads block each other?
*   **Answer:** **Yes**
*   **Reason:** Both methods are static-synchronized, meaning they both require the lock on the class object (`ThreadBlockingDemo.class`). Since `T1` holds this class lock, `T2` will be blocked until the class monitor is released.

---

### Scenario #4: One thread executes a static synchronized method and the other executes an instance synchronized method
*   **Context:** While `T1` is executing `staticSyncMethod1()`, `T2` attempts to execute `nonStaticSyncMethod1()`.
*   **Question:** Will these two threads block each other?
*   **Answer:** **No**
*   **Reason:** `T1` holds the lock on the class object (`ThreadBlockingDemo.class`), while `T2` attempts to acquire the lock on the instance object (`this`). Since these are two independent lock objects, both threads can run simultaneously without blocking.

---

### Scenario #5: One thread executes an instance synchronized method and the other executes a synchronized block on `this`
*   **Context:** While `T1` is executing `nonStaticSyncMethod1()`, `T2` attempts to execute `syncBlockWithThisObject()`.
*   **Question:** Will these two threads block each other?
*   **Answer:** **Yes**
*   **Reason:** The synchronized block explicitly requests the lock on `this`. Since `T1` already holds the lock on `this` due to the instance method synchronization, `T2` will block upon entering the synchronized block.

---

### Scenario #6: One thread executes a static synchronized method and the other executes a synchronized block on the Class object
*   **Context:** While `T1` is executing `staticSyncMethod1()`, `T2` attempts to execute `syncBlockWithClassObject()`.
*   **Question:** Will these two threads block each other?
*   **Answer:** **Yes**
*   **Reason:** The synchronized block explicitly requests the lock on `ThreadBlockingDemo.class`. Since `T1` already holds the class lock, `T2` will block upon entering the synchronized block.

Below is the lock architecture for both instance-level and class-level locking:

*Figure 9.1: Class vs Instance Locks*
![alt text](../images/image6.png)

---

## Summary

*   **Static Synchronization:** Synchronizing static methods acquires a lock on the `Class` object (`ClassName.class`), not on an object instance.
*   **Independent Locks:** Class-level locks and instance-level locks are completely independent. A thread holding an instance lock does not block a thread acquiring a class lock.
*   **Determining Blocking Behavior:** To determine if two threads will block each other, identify the exact lock object each thread is trying to acquire. If the lock targets are the same object, they will block; if different, they will not.
*   **Reentrancy Count:** The JVM maintains the monitor lock acquisition count. A thread can re-acquire a lock it already holds, incrementing the count, and releasing it only when the count returns to `0`.
