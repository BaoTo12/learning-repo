# Life Cycle of a Thread and the Thread Class API

The `java.lang.Thread` class provides a rich set of static and instance methods to manage, configure, and inspect threads throughout their lifecycle.

## Thread Class API Overview

### Static Methods

These methods operate on the thread that is currently executing the code.

| Method               | Return Type | Description                                                                                     |
| :------------------- | :---------- | :---------------------------------------------------------------------------------------------- |
| `currentThread()`    | `Thread`    | Returns a reference to the currently executing thread object.                                   |
| `activeCount()`      | `int`       | Returns an estimate of the number of active threads in the current thread group.                |
| `sleep(long millis)` | `void`      | Temporarily pauses execution of the current thread for a specified duration.                    |
| `yield()`            | `void`      | Hints to the thread scheduler that the current thread is willing to yield its CPU share.        |
| `interrupted()`      | `boolean`   | Tests whether the current thread has been interrupted, and clears the interrupted status.       |
| `dumpStack()`        | `void`      | Prints a stack trace of the current thread to the standard error stream (useful for debugging). |

### Instance Methods

These methods operate on a specific thread instance.

| Method            | Return Type | Description                                                                        |
| :---------------- | :---------- | :--------------------------------------------------------------------------------- |
| `start()`         | `void`      | Spawns a new native thread and schedules it to run its `run()` method.             |
| `getId()`         | `long`      | Returns a unique identifier for the thread.                                        |
| `getName()`       | `String`    | Returns the name of the thread.                                                    |
| `getPriority()`   | `int`       | Returns the thread's priority value.                                               |
| `isAlive()`       | `boolean`   | Checks if the thread has been started and has not yet died.                        |
| `interrupt()`     | `void`      | Interrupts the thread.                                                             |
| `isInterrupted()` | `boolean`   | Checks if the thread has been interrupted without clearing the interrupted status. |
| `join()`          | `void`      | Blocks the caller thread until this target thread completes execution.             |

---

## The Thread Lifecycle States

The lifecycle of a Java thread is governed by six distinct states, represented by the `Thread.State` enum:

```java
public class Thread implements Runnable {
    public enum State {
        NEW,
        RUNNABLE,
        BLOCKED,
        WAITING,
        TIMED_WAITING,
        TERMINATED;
    }
}
```

Let's trace the states using a concrete example:

```java
public class Greeter extends Thread {
    @Override
    public void run() {
        for (int i = 0; i < 10_000_000; i++) {
            if (i == 1_000_000) {
                try {
                    Thread.sleep(1000); // Transitions thread to TIMED_WAITING
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        }
    }
}

// 1. NEW State
Thread greeterThread = new Greeter();
```

---

### 1. NEW

When you instantiate a `Thread` class, the thread is in the `NEW` state. It is a plain Java object residing on the heap and does not have an execution context (no call stack, PC register, etc.). The method `isAlive()` returns `false`.

---

### 2. RUNNABLE

In order to transition a thread into an active state, you must call `start()`.

```java
greeterThread.start();
```

Once `start()` is invoked, the thread enters the `RUNNABLE` state and `isAlive()` returns `true`.

> **Mental Model: The RUNNABLE State**
> A thread in the `RUNNABLE` state is ready to run, but it may or may not be actively executing code at any given microsecond. It is under the control of the OS Thread Scheduler. The thread might be actively running on a CPU core, or it might be waiting in the OS queue for its next CPU time slice. Both scenarios fall under the `RUNNABLE` state in Java.

---

### 3. TIMED_WAITING

When a running thread executes a time-based blocking method like `Thread.sleep(duration)`, it voluntarily relinquishes the CPU and enters the `TIMED_WAITING` state.

> **Pitfall: Calling sleep() on a Thread Reference**
> Because `sleep()` is a **static** method, it always puts the _currently executing_ thread to sleep. Calling it on a thread reference is highly misleading and a common source of bugs:
>
> ```java
> Thread t = new Thread(task);
> t.start();
> t.sleep(1000); // Pitfall: This puts the 'main' thread to sleep, NOT thread 't'!
> ```
>
> Always invoke it as `Thread.sleep(1000)` to make it clear that the current thread is sleeping.

When the sleep duration expires, the thread is awakened and transitioned back to the `RUNNABLE` state, waiting for the OS scheduler to assign it a CPU core to resume.

---

### 4. TERMINATED

A thread enters the `TERMINATED` state once its `run()` method finishes executing, either by completing successfully or by throwing an unhandled exception. Once terminated, the thread is dead; it cannot be restarted, and calling `start()` on it again will throw an `IllegalThreadStateException`. The `isAlive()` method returns `false`.

### Thread Lifecycle Diagram

Below is the transition flow of a thread's lifecycle:

_Figure 3.1: Thread Lifecycle_
![alt text](../images/image2.png)

---

## Summary

- **NEW State:** The thread object exists but has no OS execution context. `isAlive()` is `false`.
- **RUNNABLE State:** The thread is active, executing in the JVM, or waiting for OS resources (like CPU time slices). `isAlive()` is `true`.
- **TIMED_WAITING State:** The thread is temporarily suspended due to a timed block (like `Thread.sleep()`).
- **TERMINATED State:** The thread has completed its `run()` method and is dead. It cannot be resurrected.
