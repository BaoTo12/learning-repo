# Creation and Running a Thread

A thread is an independent set of instructions that has its own private state. Every Java application has at least one thread named **main** created automatically by the JVM. But what does it actually mean when we talk about a "Java Thread"?

At its core, a Java **Thread** is just an instance of the `java.lang.Thread` class.

Like any other Java class, the `Thread` class is an object residing on the heap. It offers methods to configure and operate on the underlying execution context. A static native method named `Thread.currentThread()` returns the `Thread` object representing the currently running thread.

```java
Thread currentThread = Thread.currentThread();
System.out.println("Current Thread is: " + currentThread.getName());
```

When you run these lines, you will see:

```text
Output: Current Thread is: main
```

The **main thread** is spawned by the JVM to execute the `main()` method of your application without any manual setup.

---

## Creating Our Own Threads

Creating a thread in Java is as simple as instantiating a `Thread` object and calling the `start()` method on that object.

There are two primary ways to define the task a thread will run:
1.  **Instantiating the `Thread` class with a `Runnable` object** (Recommended)
2.  **Subclassing the `Thread` class**

---

### 1. Instantiating Thread with a Runnable Object

The `Runnable` interface represents a task to be executed. It has a single abstract method named `run()`. A class implementing this interface provides the actual instructions the thread will execute.

We pass this `Runnable` implementation into the `Thread` constructor, separating the task definition from the thread mechanism.

```java
package org.vit.threads;

public class ThreadRunnableDemo {
    public static void main(String[] args) {
        // 1. Define the task
        Runnable greeter = new Greeter();
        
        // 2. Pass the task to a new Thread
        Thread thread = new Thread(greeter);
        
        // 3. Start the thread
        thread.start();
    }
}

class Greeter implements Runnable {
    @Override
    public void run() {
        String name = Thread.currentThread().getName();
        System.out.println("Hello! From thread: " + name);
    }
}
```

**Output:**
```text
Hello! From thread: Thread-0
```

> **Mental Model: Thread Object vs. Thread of Execution**
> Instantiating a `Thread` object (`new Thread()`) only creates a plain Java object on the heap. It has no execution context yet. It is only when you invoke `start()` that the JVM requests the OS to allocate a native thread, create a call stack, and begin execution.

#### Autonumbering of Threads
If you don't specify a name, the JVM automatically assigns one using a monotonically increasing counter (e.g., `Thread-0`, `Thread-1`). This autonumbering logic is handled inside the `Thread` constructor:

```java
public class Thread implements Runnable {
    private volatile String name;
    private Runnable target;
    
    /* For autonumbering anonymous threads. */
    private static int threadInitNumber;
    private static synchronized int nextThreadNum() {
        return threadInitNumber++;
    }
    
    public Thread(Runnable target) {
        this(null, target, "Thread-" + nextThreadNum(), 0);
    }
}
```

---

### 2. Subclassing the Thread Class

Since the `Thread` class itself implements the `Runnable` interface, you can create a subclass of `Thread` and override its `run()` method directly:

```java
package org.vit.threads;

public class ThreadSubclassDemo {
    public static void main(String[] args) {
        Thread greeterThread = new GreeterThread();
        greeterThread.start();
    }
}

class GreeterThread extends Thread {
    @Override
    public void run() {
        String name = Thread.currentThread().getName();
        System.out.println("Hello! From thread: " + name);
    }
}
```

This yields the same output but is generally less preferred because it limits your class from extending any other class due to Java's single inheritance rule.

---

> **Pitfall: Calling run() Directly Instead of start()**
> Calling `run()` directly on a `Thread` or `Runnable` object is a common mistake. It does **not** start a new thread. Instead, the code runs synchronously in the caller's thread (typically the `main` thread), blocking it.
> 
> ```java
> Thread greeterThread = new GreeterThread();
> greeterThread.run(); // Running on the 'main' thread!
> ```
> **Output:**
> ```text
> Hello! From thread: main
> ```
> To spawn a new thread, you must call `start()`, which internally triggers the native OS thread creation and schedules the `run()` method asynchronously.

---

## Summary

*   **Two Ways to Create Threads:** You can either implement the `Runnable` interface (recommended for clean separation of concerns) or subclass the `Thread` class.
*   **The `start()` Method:** You must invoke `start()` to create a new execution context. Calling `run()` directly runs the task synchronously on the calling thread.
*   **Thread Naming:** If you don't provide a thread name in the constructor, the JVM uses thread autonumbering to assign names like `Thread-0`, `Thread-1`, etc.