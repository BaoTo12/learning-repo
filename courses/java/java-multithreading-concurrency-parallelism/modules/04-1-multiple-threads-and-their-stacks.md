# Multiple Threads and Their Call Stacks

In the previous modules, we explored how threads are created and examined their lifecycle. In this module, we will dive deep into how threads execute code, manage their local variables, and maintain their independent call stacks.

---

## Thread-Private Call Stacks

Every thread in Java has its own private stack created by the Java Virtual Machine (JVM) at thread birth. No thread can access another thread's private stack.

Let's look at a simple Java application that spawns a thread named `MyThread` alongside the main thread:

```java
public class ThreadStackDemo {
    public static void main(String[] args) {
        methodOne();
        Thread t = new Thread(new MyRunnable(), "MyThread");
        t.start();
    }

    private static void methodOne() {
        System.out.println("In Method One");
    }

    static class MyRunnable implements Runnable {
        @Override
        public void run() {
            methodTwo();
        }

        private void methodTwo() {
            System.out.println("In Method Two");
        }
    }
}
```

In this program, two threads are running:
1.  **main thread:** Invokes `main()`, which in turn calls `methodOne()`, and then spawns `MyThread`.
2.  **MyThread:** Invokes the `run()` method of `MyRunnable`, which in turn calls `methodTwo()`.

Here is a visualization of how the call stacks look for each thread:

*Figure 4.1: Thread Private Stacks*
![alt text](../images/image3.png)

### What is Stored inside a JVM Stack?
The JVM stack stores **frames**. A frame is a data structure allocated every time a method is invoked. It is destroyed when the method completes. A frame contains:
*   **Local Variables Table:** Stores primitive values and object references local to the method.
*   **Operand Stack:** Used as a workspace to evaluate expressions and execute bytecode instructions.
*   **Frame Data:** Contains references to the runtime constant pool, normal method completion info, and exception dispatch tables.

---

> **Mental Model: Thread-Private Stack vs. Shared Heap**
> In Java's memory model:
> *   **Call Stacks are Private:** Every thread has its own call stack. Local variables defined inside methods (including primitives and reference variables) are stored inside the stack frames. They are completely private to the thread executing that method.
> *   **The Heap is Shared:** All objects (created with `new`) reside on the shared heap. If multiple threads hold references to the same object on the heap, they share that object's instance variables.

---

## Multiple Threads with the Same Runnable

Since local variables inside methods are stored in thread-private stack frames, multiple threads can execute the exact same `Runnable` task without interfering with each other's local variables. Each thread executes the task in its own private stack context.

Consider the following program where three threads share the same `Runnable` instance:

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

    static class MyRunnable implements Runnable {
        @Override
        public void run() {
            // 'i' is a local variable stored in each thread's private stack frame
            for (int i = 0; i < 10; i++) {
                System.out.println(String.format("From %s :: %d", Thread.currentThread().getName(), i));
            }
        }
    }
}
```

### Execution Output
Because each thread has its own copy of the local loop variable `i` in its private stack frame, their loop counters do not interfere. The console output shows interleaved counts, but each thread completes its count from 0 to 9 successfully:

```text
From t2 :: 0
From t1 :: 0
From t3 :: 0
From t2 :: 1
From t1 :: 1
From t3 :: 1
...
From t3 :: 9
```

> **Pitfall: Instance Variables vs. Local Variables**
> If a variable is defined as an **instance variable** (a field of the `MyRunnable` class) instead of a **local variable** inside the `run()` method, it resides on the heap. When multiple threads share the same `MyRunnable` instance, they will share that instance variable, leading to race conditions and unpredictable results unless synchronized.

---

## Summary

*   **Private Call Stacks:** Every thread in Java has its own private JVM stack. Stacks are completely isolated from other threads.
*   **Stack Frames:** Every method call allocates a new frame in the thread's stack to store local variables and execution state.
*   **Sharing Runnable Tasks:** Multiple threads can safely execute the same `Runnable` instance because their local variables are isolated within their private stack frames.
*   **Heap Sharing:** While stacks are private, the heap is shared. Any shared object fields must be synchronized if accessed by multiple threads.
