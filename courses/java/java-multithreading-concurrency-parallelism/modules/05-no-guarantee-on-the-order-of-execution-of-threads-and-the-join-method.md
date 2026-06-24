# NO Guarantee on the Order of Execution of Threads and the join() Method

In the previous module, we have seen that we can create multiple threads sharing the same `Runnable` instance. Here, we look at the same example and understand the order of their execution.

```java
public class MultipleThreadSameRunnableDemo {
    public static void main(String[] args) {
        MyRunnable task = new MyRunnable();
        
        // Creating three threads sharing the same task
        Thread t1 = new Thread(task, "t1");
        Thread t2 = new Thread(task, "t2");
        Thread t3 = new Thread(task, "t3");
        
        t1.start();
        t2.start();
        t3.start();
    }

    private static void methodOne() {
        System.out.println("In Method One");
    }

    static class MyRunnable implements Runnable {
        @Override
        public void run() {
            for (int i = 0; i < 10; i++) {
                System.out.println(String.format("From %s :: %d", Thread.currentThread().getName(), i));
            }
        }
    }
}
```

The above code creates a single `Runnable` instance and three `Thread` instances. All three `Thread` instances get the same `Runnable` instance, and each thread is given a unique name: `t1`, `t2`, and `t3`. Finally, all three threads are started by invoking `start()` on those three instances.

Run this program multiple times, and you won’t see the same output every time. You may or may not get the same output every time you run the program. One thumb rule about threads in Java is that the **order of their execution is NOT guaranteed**.

---

## Key Rules of Thread Execution

Here are the key points that must be noted:
1.  **Single Start Limit:** Each thread will start and complete. Once a thread has been started, it can never be started again. We will get `IllegalThreadStateException` if we call `start()` again on the same thread instance.
2.  **No Guarantee of Start Order:** Though we started `t1` first, followed by `t2` and `t3`, there is no guarantee that `t1` will ever run first. It is all up to the JVM Thread Scheduler and it varies from JVM to JVM.
3.  **No Guarantee of Execution Continuity:** Once a thread is started, there is no guarantee that it will keep executing till it’s completed. We will never know when it interleaves the CPU core. Again, this depends on the scheduler. We all know about this pretty well from our academic operating system concepts.
4.  **Mixing Event Streams:** Within each thread, the execution happens in a predictable order. But the events of different threads can mix in unpredictable ways. That is why if we run the program multiple times or on multiple machines, we may see different outputs.
5.  **No Clear Pattern:** There is no clear pattern in the order of their execution.
6.  **Thread Death and Stack Clean-up:** When a thread completes its `run()` method, the thread dies and the stack for that thread is removed from JVM’s memory.

Let's look at the sample output to understand the unpredictable mixing of event streams:

```text
From t2 :: 3
From t1 :: 3
From t2 :: 4
From t1 :: 4
From t2 :: 5
From t1 :: 5
From t2 :: 6
From t1 :: 6
From t2 :: 7
From t1 :: 7
From t2 :: 8
From t1 :: 8
From t2 :: 9
```

Focus on the output from `t1`. Within `t1` alone, the execution order is perfectly predictable (0, 1, 2, 3... 9). But the way `t1`, `t2`, and `t3` are getting preempted by the OS is not predictable. If you run it again, you may see a completely different output, such as:

```text
From t1 :: 0
From t1 :: 1
From t1 :: 2
From t1 :: 3
From t1 :: 4
From t1 :: 5
From t1 :: 6
From t1 :: 7
From t1 :: 8
From t1 :: 9
From t3 :: 0
From t3 :: 1
From t3 :: 2
From t3 :: 3
```

---

> **Pitfall: IllegalThreadStateException**
> Once a thread completes its execution and enters the `TERMINATED` state, it is dead. You cannot reuse the same `Thread` object to start the thread again. Invoking `start()` a second time on the same instance will throw an `IllegalThreadStateException`.

---

## Coordinating Thread Execution with join()

What if you want to enforce execution order? There is a way to tell the currently running thread not to run until some other thread has finished: the `join()` method.

The `join()` method is a non-static method in the `Thread` class. It lets the current thread join onto the end of another thread.

```java
Thread tj = new Thread();
tj.start();
tj.join();
```

This code takes the current thread and joins it to the end of the thread referenced by `tj`. This means if this code is running in the **main thread** inside the `main()` method, then the **main thread** will be blocked and won't become runnable until the thread `tj` finishes its `run()` method. 

There is also an overloaded version of `join()` that takes a timeout:

```java
tj.join(2000); // The overloaded method
```

This tells the current thread (e.g., `main`) to wait until `tj` is completed, but if it takes longer than 2000 milliseconds, stop waiting and resume execution.

---

> **Mental Model: Thread Join**
> Think of a thread calling `t.join()` as a manager waiting for a subordinate to finish a report. The manager (calling thread) pauses all their work and sits idle (goes into `WAITING` or `TIMED_WAITING` state) until the subordinate (thread `t`) completes their report (finishes its task). Only then does the manager resume working.

---

> **Insight: Thread States during join()**
> The state of the calling thread during a `join()` call depends on the overload used:
> *   **`join()`**: Will put the calling thread into the **`WAITING`** state.
> *   **`join(long milliseconds)`**: Will put the calling thread into the **`TIMED_WAITING`** state.

---

### Example: Enforcing Order with join()
Suppose we want to achieve the following: thread `t1` should print 0–9, and the `main` thread should print 0–4 *only* after `t1` completes.

```java
package org.vit.threads;

public class ThreadStackDemo {
    public static void main(String[] args) throws InterruptedException {
        MyRunnable task = new MyRunnable();
        Thread t1 = new Thread(task, "t1");
        
        t1.start();
        t1.join(); // main thread waits here until t1 completes
        
        for (int i = 0; i < 5; i++) {
            System.out.println("From " + Thread.currentThread().getName() + ":: " + i);
        }
    }

    private static void methodOne() {
        System.out.println("In Method One");
    }

    static class MyRunnable implements Runnable {
        @Override
        public void run() {
            for (int i = 0; i < 10; i++) {
                System.out.println(String.format("From %s :: %d", Thread.currentThread().getName(), i));
            }
        }
    }
}
```

**Output:**
```text
From t1 :: 0
From t1 :: 1
From t1 :: 2
From t1 :: 3
From t1 :: 4
From t1 :: 5
From t1 :: 6
From t1 :: 7
From t1 :: 8
From t1 :: 9
From main:: 0
From main:: 1
From main:: 2
From main:: 3
From main:: 4
```

No matter how many times you run this program, you will always get this exact output because we have explicitly synchronized the threads using `join()`.

---

## Summary

*   **No Order Guarantee:** The order in which threads are scheduled and executed is completely unpredictable and depends entirely on the OS Thread Scheduler.
*   **One-Time Start:** A thread can only be started once. Attempting to restart a terminated thread throws an `IllegalThreadStateException`.
*   **Interleaved Execution:** Once started, a thread can be preempted at any moment. Threads run concurrently and their instruction streams interleave unpredictably.
*   **Thread Join:** The `join()` method forces the calling thread to pause until the target thread terminates, transitioning the caller to the `WAITING` state.
*   **Timed Join:** The `join(long milliseconds)` method pauses the caller for at most the specified duration, transitioning the caller to the `TIMED_WAITING` state.