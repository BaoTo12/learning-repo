# Program, Process, and a Thread

Multithreading is all about executing small tasks independently inside a process. Well, there are many articles that explain what a process, thread, and concurrency mean. Let me also specify the same in simple words here.

## How a process is born?

A process takes its birth from a static file called a program that contains a specific set of instructions with its associated data. A program, being a static file residing in an auxiliary memory like a hard disk, has many extensions depending on the programming language. For example, in Java, it is a ***.class*** file or an executable ***.jar*** file that has a set of instructions telling the Operating System how to perform a task.

When we execute a program, it is loaded into the Main Memory(RAM), by the Operating System(with the concept known ). The Operating System's core called Kernel then creates the process which is the running instance of a program. In simple words, the process is just the runtime instance of our program.

## So What is a Thread

A thread is a small independent unit of execution inside a process. Multiple threads may exist within a process, running concurrently, having some local state associated with them. There may also be a global state in a process that all the threads share. Special care needs to be taken when multiple threads are writing and reading to and from this global state.

The word thread can mean two things:

**Kernel Space Threads:** Threads that run in Kernel on behalf of User Space Threads: Ex: Device Driver Threads

**User Space Threads:** Threads that run in a User Level Process. Ex: Java Threads

How threading is related to Java? Well, Java is just alike another user-level process getting managed by the operating system and has the support of multithreading. In fact, every Java process (Java application) has a default thread named ***main.*** Other threads can be created from the main thread.

## Native Thread Modelling

Java supports(From Java 1.3 version), Native Thread Modelling with the support of underlying OS especially Linux. Linux had provided support for the large concurrent execution of threads using the POSIX thread library. This library is the basis for JVM implementing the Native Thread Model and provides a one-to-one mapping between Java and Kernel threads. The native thread model implementation of JVM typically has the following characteristics.

Threads are created and managed by JVM with the support of underlying OS libraries.

With the native thread model, JVM can take full advantage of the multi-core system because threads are implemented at the system level and managed within the kernel space.

Multiple threads can run concurrently.

Thread synchronization and resource sharing become complicated. Special care needs to be taken as this can affect the overall application performance.

In the later parts, we will discuss Java Multithreading in more detail.

## Summary

A Program becomes a process when it is loaded into memory and run by the operating system.

Java is a user-level or application process that contains threads which make Java a multi-threaded programming language.

All nontrivial Java programs are multithreaded.

Java implements the Native Thread Model with the support of POSIX libraries.

Java threads are created and managed by JVM with the support of underlying OS libraries.