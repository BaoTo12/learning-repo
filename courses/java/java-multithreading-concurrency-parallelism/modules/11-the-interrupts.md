# The Interrupts

In the previous module, we explored the behavior of `wait` and `notify` and their purpose in thread communication. In this module, we will discuss another core concurrency concept that is frequently misunderstood: **Thread Interrupts**.

An **interrupt** is a collaborative mechanism that tells a thread it should stop what it is doing and perform a different action (typically, terminate gracefully). It is up to the programmer to decide exactly how a thread responds to an interrupt, but the standard practice is to clean up and exit.

---

## Triggering and Supporting Interruption

How do threads interrupt each other? A thread sends an interrupt by invoking the `interrupt()` method on the target `Thread` object:

```java
targetThread.interrupt();
```

For the interrupt mechanism to work properly, the thread being interrupted must actively support it. If a thread is interrupted but contains no logic to check or handle the interrupt, the signal is simply ignored.

There are two primary ways to handle thread interrupts depending on what the thread is doing:
1.  **Handling InterruptedException (for blocking operations)**
2.  **Checking the Interrupted Status Flag (for CPU-intensive operations)**

---

### 1. Handling InterruptedException

Methods that block for long periods—such as `Thread.sleep()`, `Thread.join()`, and `Object.wait()`—throw an `InterruptedException`. These methods have built-in interrupt detection.

When a thread is in a blocking state (like `TIMED_WAITING` or `WAITING`) and another thread calls `interrupt()` on it, the blocking method immediately wakes up, clears the interrupt flag, and throws an `InterruptedException`.

```java
public class StoppingThreadWithInterrupt extends Thread {
    @Override
    public void run() {
        System.out.print(Thread.currentThread().getName() + ": I am doing work ");
        while (true) {
            System.out.print(". ");
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                System.out.println("\n" + Thread.currentThread().getName() + ": I have been Interrupted!!");
                break; // Exit the loop and terminate the thread
            }
        }
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }

    public static void main(String[] args) throws InterruptedException {
        Thread t1 = new StoppingThreadWithInterrupt();
        t1.start();
        Thread.sleep(5000);
        t1.interrupt(); // Signal t1 to stop
        Thread.sleep(1000);
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }
}
```

**Output:**
```text
Thread-0: I am doing work . . . . .
Thread-0: I have been Interrupted!!
End of the thread: Thread-0!
End of the thread: main!
```

By catching the `InterruptedException` and breaking the loop, we allow the thread to clean up and exit gracefully. This is the recommended way to stop a thread (unlike the deprecated `Thread.stop()` method).

---

## The Interrupt Status Flag

The interrupt mechanism relies on an internal boolean flag called the **interrupt status flag**. 

Java provides two methods to check this flag, and understanding the difference between them is vital:
*   **`isInterrupted()` (Instance Method):** Checks the target thread's interrupt status flag. It returns `true` if the thread is interrupted, and does **not** modify the flag.
*   **`Thread.interrupted()` (Static Method):** Checks the *current* thread's interrupt status flag and **clears** it (resets it to `false`).

| Method | Type | Purpose | Modifies Flag? |
| :--- | :--- | :--- | :--- |
| `isInterrupted()` | Instance | Queries if the target thread has been interrupted. | **No** |
| `Thread.interrupted()` | Static | Queries if the current thread has been interrupted and clears the status. | **Yes** (resets to `false`) |

---

### 2. Checking the Interrupted Status Flag

If a thread is executing a long-running, non-blocking CPU loop, it will never throw an `InterruptedException`. Instead, the thread must periodically check its own interrupt status flag:

```java
public class StoppingThreadWithInterrupt2 extends Thread {
    @Override
    public void run() {
        System.out.print(Thread.currentThread().getName() + ": I am doing work ");
        while (!Thread.currentThread().isInterrupted()) { // Periodically check the flag
            System.out.print(". ");
        }
        System.out.println(Thread.currentThread().getName() + ": I have been interrupted!!");
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }

    public static void main(String[] args) throws InterruptedException {
        Thread t1 = new StoppingThreadWithInterrupt2();
        t1.start();
        Thread.sleep(10); // Let t1 do some work
        t1.interrupt(); // Interrupt t1
        Thread.sleep(1000); // Let t1 come to an end
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }
}
```

**Output:**
```text
Thread-0: I am doing work . . . . . . . . . . . . . . . . . . . . . . . . .
Thread-0: I have been interrupted!!
End of the thread: Thread-0!
End of the thread: main!
```

When `t1` detects that its interrupt flag is set, it naturally exits the `while` loop, allowing clean termination.

---

> **Pitfall: Flag Clearing by Blocking Methods**
> The built-in interrupt handlers for blocking methods (like `sleep`, `wait`, `join`) **clear** the interrupt status flag before throwing an `InterruptedException`. If you catch the exception but do not re-set the flag or break the loop, the thread will run infinitely because its status has been reset.

Consider this incorrect implementation:

```java
public class StoppingThreadWithInterrupt3 extends Thread {
    @Override
    public void run() {
        System.out.print(Thread.currentThread().getName() + ": I am doing work ");
        while (!Thread.currentThread().isInterrupted()) {
            System.out.print(". ");
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                // Pitfall: The flag is cleared! isInterrupted() will return false.
                System.out.println("\n" + Thread.currentThread().getName() + ": I have been Interrupted!!");
            }
        }
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }

    public static void main(String[] args) throws InterruptedException {
        Thread t1 = new StoppingThreadWithInterrupt3();
        t1.start();
        Thread.sleep(5000);
        t1.interrupt();
        Thread.sleep(1000);
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }
}
```

**Output:**
```text
Thread-0: I am doing work . . . . .
Thread-0: I have been Interrupted!!
. End of the thread: main!
. . . . . . . . . . . . . . . (runs infinitely)
```

Because `InterruptedException` cleared the flag, the loop condition `!Thread.currentThread().isInterrupted()` remains `true` forever.

---

### The Right Way: Self-Interruption

To fix this issue without using a `break` (which might fail in nested loops), you should **re-interrupt the thread** inside the `catch` block. This restores the interrupt status flag so that the outer loops can detect it:

```java
public class StoppingThreadWithInterrupt4 extends Thread {
    @Override
    public void run() {
        System.out.print(Thread.currentThread().getName() + ": I am doing work ");
        while (!Thread.currentThread().isInterrupted()) {
            System.out.print(". ");
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                System.out.println("\n" + Thread.currentThread().getName() + " is Interrupted? " + Thread.currentThread().isInterrupted());
                Thread.currentThread().interrupt(); // Restore the flag!
                System.out.println(Thread.currentThread().getName() + ": I have been Interrupted!!");
            }
        }
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }

    public static void main(String[] args) throws InterruptedException {
        Thread t1 = new StoppingThreadWithInterrupt4();
        t1.start();
        Thread.sleep(5000);
        t1.interrupt();
        Thread.sleep(1000);
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }
}
```

**Output:**
```text
Thread-0: I am doing work . . . . .
Thread-0 is Interrupted? false
Thread-0: I have been Interrupted!!
End of the thread: Thread-0!
End of the thread: main!
```

---

## Summary

*   **Collaborative Mechanism:** Interruption is cooperative. A thread asks another to stop by calling `interrupt()`, but the target thread must implement logic to support it.
*   **Interrupt Flag:** Calling `interrupt()` sets the thread's internal interrupt status flag.
*   **Checking Flag:** Use the instance method `isInterrupted()` to check the flag. Use the static method `Thread.interrupted()` to check and clear the flag of the current thread.
*   **Flag Clearing:** Blocking methods (like `sleep()`) clear the flag before throwing `InterruptedException`.
*   **Safer Stopping:** To stop a thread safely when catching `InterruptedException`, either break the loop or call `Thread.currentThread().interrupt()` to restore the flag.