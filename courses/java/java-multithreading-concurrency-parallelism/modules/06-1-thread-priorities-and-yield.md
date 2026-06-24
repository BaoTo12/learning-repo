# Thread Priorities and yield()

In the previous module, we explored how the order of thread execution happens and how to use the `join()` method to coordinate threads. We learned that the order of execution is not naturally guaranteed. In this module, we will discuss **thread priorities** and explore how threads can cooperatively yield execution time to one another using the static `Thread.yield()` method.

---

## Thread Priorities

In Java, every thread has a priority represented by an integer from 1 to 10:
*   **`1` (Thread.MIN_PRIORITY):** The lowest possible priority.
*   **`5` (Thread.NORM_PRIORITY):** The default priority assigned to a thread.
*   **`10` (Thread.MAX_PRIORITY):** The highest possible priority.

In most operating systems and JVM implementations, the thread scheduler uses **priority-based preemptive scheduling** with time-slicing. 
*   **Preemptive Turn-Taking:** The scheduler allocates a time slice to a thread. When that time slice elapses, the thread is preempted (paused) to let another thread run.
*   **Priority Bias:** When selecting which thread to run next, the scheduler prefers threads with higher priorities.

> **Insight: Priority Preemption Mechanics**
> In most JVM schedulers, if a high-priority thread enters the `RUNNABLE` queue while a lower-priority thread is currently running, the lower-priority thread is immediately preempted and pushed back to the runnable queue, allowing the higher-priority thread to take over.

---

> **Pitfall: Platform Dependency of Priorities**
> Never rely on thread priorities to guarantee the correctness of your application. Thread scheduling is highly platform-dependent:
> *   **No Enforced Standard:** The JVM specification does not define which scheduling algorithm must be used. Schedulers are platform-dependent and vary widely.
> *   **OS Mapping Issues:** Schedulers rely on the host OS. Some operating systems have fewer than 10 priority levels, forcing the JVM to map multiple Java priorities to the same OS priority.
> *   **Thread Starvation:** Relying on priorities can cause lower-priority threads to never get CPU time (thread starvation).
> *   **Tie-Breakers:** Schedulers do not guarantee which thread gets picked first when multiple threads have the same priority.

### Setting Thread Priorities
You can get and set a thread's priority using the `getPriority()` and `setPriority(int)` instance methods:

```java
Runnable task = new FileDownloaderTask(fileUrl);
Thread worker = new Thread(task, "FileDownloader");
worker.setPriority(4); // Set custom priority
worker.start();
```

Inside the JVM, priority constants are defined in `Thread.java` as follows:

```java
public class Thread implements Runnable {
    /**
     * The minimum priority that a thread can have.
     */
    public static final int MIN_PRIORITY = 1;

    /**
     * The default priority that is assigned to a thread.
     */
    public static final int NORM_PRIORITY = 5;

    /**
     * The maximum priority that a thread can have.
     */
    public static final int MAX_PRIORITY = 10;
}
```

---

## Cooperative Threading with yield()

The static `Thread.yield()` method is a way for a thread to cooperatively say: *"I have run enough for now; let's pause and give other threads of the same priority a chance to run."*

When a thread calls `Thread.yield()`, it is voluntarily pushed out of the CPU and placed back into the `RUNNABLE` queue, allowing other threads of equal priority to run.

> **Pitfall: yield() is Merely a Hint**
> Just like thread priorities, `Thread.yield()` offers **no guarantee** of execution order. 
> *   **Advisory Only:** Schedulers are free to completely ignore a `yield()` call.
> *   **Immediate Reschedule:** If there are no other equal-priority threads in the runnable queue, or if the OS scheduler decides to favor the current thread, the yielding thread might be immediately rescheduled to run again without any other thread taking a turn.
> *   **No State Change:** Calling `yield()` never puts the thread into a blocked or waiting state. The thread's state remains **`RUNNABLE`** throughout.

---

### Comparison of Pause Mechanisms

| Method | Type | Guaranteed? | Thread State Transition | Description |
| :--- | :--- | :--- | :--- | :--- |
| `Thread.sleep(millis)` | Static | **Yes** | `RUNNABLE` $\rightarrow$ `TIMED_WAITING` | Pauses the currently running thread for at least the specified duration. |
| `Thread.yield()` | Static | **No** | Remains `RUNNABLE` | Requests the scheduler to yield CPU to another thread of equal priority. |
| `thread.join()` | Instance | **Yes** | `RUNNABLE` $\rightarrow$ `WAITING` | Blocks the calling thread until the target thread terminates. |

---

### Example: Demonstrating yield()
The following program spawns three threads that cooperatively call `Thread.yield()` every 5 iterations:

```java
public class YieldDemo {
    public static void main(String[] args) {
        Runnable r1 = () -> {
            for (int i = 1; i <= 20; i++) {
                if (0 == (i % 5)) {
                    Thread.yield();
                    System.out.println(Thread.currentThread().getName() + " State After Yield: " + Thread.currentThread().getState());
                }
                System.out.println(Thread.currentThread().getName() + " i = " + i);
            }
        };

        Thread t1 = new Thread(r1, "T1");
        Thread t2 = new Thread(r1, "T2");
        Thread t3 = new Thread(r1, "T3");

        t1.start();
        t2.start();
        t3.start();

        System.out.println(Thread.currentThread().getName() + " is finished!");
    }
}
```

### Sample Output Analysis
```text
main is finished!
T3 i = 1
T2 i = 1
T1 i = 1
T2 i = 2
T3 i = 2
T2 i = 3
T1 i = 2
T2 i = 4
T3 i = 3
T3 i = 4
T1 i = 3
T1 i = 4
T2 State After Yield: RUNNABLE
T1 State After Yield: RUNNABLE
T2 i = 5
T3 State After Yield: RUNNABLE
...
T1 i = 9
T1 State After Yield: RUNNABLE
T1 i = 10
```

> **Insight: Analyzing the Yield Output**
> Looking closely at the output, two important behaviors can be observed:
> 1.  **No State Change:** When `T1` yields, its printed state immediately after is still `RUNNABLE`. It never goes to sleep.
> 2.  **Scheduler Autonomy:** Even though `T1` called `yield()` at iteration 9, the OS immediately rescheduled it to continue executing iteration 10 without giving `T2` or `T3` a turn. This proves that `yield()` is purely advisory.

---

## Summary

*   **Priority Range:** Thread priorities are integers from 1 (lowest) to 10 (highest), defaulting to 5.
*   **Platform Dependency:** Schedulers are platform-specific. Never rely on thread priorities or `yield()` for application correctness or synchronization.
*   **Advisory Yielding:** `Thread.yield()` is a cooperative hint asking the scheduler to give equal-priority threads a turn. It can be silently ignored by the JVM.
*   **No Blocking:** Unlike `sleep()` or `join()`, `yield()` never blocks a thread; it remains in the `RUNNABLE` state.
