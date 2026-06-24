# Introduction to Synchronizers

In previous modules, we explored several thread-safe collections. These collections act as containers for exchanging objects and coordinating control flow between threads. 

In this module, we will explore a dedicated category of concurrency constructs designed specifically to coordinate the execution flow of threads: **Synchronizers**. We will get a high-level overview of what a synchronizer is, examine their structural properties, and introduce the underlying framework that powers them: **AQS**.

---

## What is a Synchronizer?

A **Synchronizer** is any object that coordinates the control flow of threads based on its internal state. 

Blocking queues are a prime example of a synchronizer. They coordinate the control flow of producer and consumer threads based on the queue's emptiness or fullness (using internal `notFull` and `notEmpty` `Condition` objects).

The Java Concurrency Utilities provide a rich set of built-in synchronizer classes, each suited for specific coordination patterns:
*   **Latches (e.g., `CountDownLatch`)**: Delays the progress of threads until a set of events has occurred.
*   **Barriers (e.g., `CyclicBarrier`, `Phaser`)**: Blocks a group of threads until all threads have arrived at a common barrier point.
*   **Semaphores (e.g., `Semaphore`)**: Controls the number of threads that can access a specific resource or execute a critical section simultaneously.
*   **FutureTasks (e.g., `FutureTask`)**: Represents an asynchronous computation that blocks retrieving threads until the result is available.
*   **Exchangers (e.g., `Exchanger`)**: A two-way barrier where two threads can exchange data at a rendezvous point.

Below is a conceptual illustration of how threads arrive at and are coordinated by a synchronizer:

![Synchronizer Overview](../images/image22.png)

*Figure 20.1.1: Threads coordinating execution flow at a synchronizer boundary*

---

## Structural Properties of Synchronizers

While their behavioral patterns differ, almost all standard synchronizers share several key structural properties:

1.  **Arrival Gates**: They act as a start gate or boundary where threads arrive and wait for a specific **state change** (the start event) to occur.
2.  **State Encapsulation**: They encapsulate a synchronization state and maintain it internally.
3.  **State Manipulation**: They expose methods to manipulate this state and provide ways for threads to wait efficiently for the synchronizer to transition to the desired state.

---

## The AbstractQueuedSynchronizer (AQS) Framework

Almost all standard Java synchronizer classes are built on top of a highly optimized, low-level sub-framework: **`AbstractQueuedSynchronizer` (AQS)**.

AQS is the cornerstone of the Java Concurrency Utilities. It is a framework designed to build both explicit locks (like `ReentrantLock` and `ReentrantReadWriteLock`) and synchronizers (like `CountDownLatch`, `Semaphore`, `SynchronousQueue`, and `FutureTask`).

### The Acquire and Release Protocol
At its core, AQS coordinates threads using a simple, unified protocol based on two main operations: **acquire** and **release**.

#### 1. The Acquire Operation
The `acquire` operation is a **state-dependent** operation. If the current state of the synchronizer does not permit acquisition, the calling thread is blocked:

```java
while (synchronization state does not allow acquire) {
    enqueue current thread if not already queued;
    possibly block current thread;
}
dequeue current thread if it was queued;
```

#### 2. The Release Operation
The `release` operation is **non-blocking**. It updates the synchronization state and unblocks one or more threads waiting in the acquire queue, allowing them to proceed:

```java
update synchronization state;
if (state may permit a blocked thread to acquire) {
    unblock one or more queued threads;
}
```

---

## How AQS Manages Synchronizer State

Implementing a highly concurrent synchronizer requires careful coordination of three core responsibilities:
- Atomically managing the synchronization state.
- Blocking and unblocking threads.
- Maintaining a thread-safe FIFO queue of waiting threads.

AQS handles these details, allowing developers to focus on the specific coordination rules of their synchronizer. 

AQS manages a **single volatile integer** representing the synchronization state. It exposes three protected methods to manipulate this state atomically:
- `getState()`
- `setState(int newState)`
- `compareAndSetState(int expect, int update)` (which performs a hardware-level CAS)

This single integer represents different concepts depending on the synchronizer implementation:
- **`ReentrantLock`**: Represents the recursion count (how many times the owning thread has acquired the lock).
- **`Semaphore`**: Represents the number of available permits.
- **`CountDownLatch`**: Represents the remaining event count.
- **`FutureTask`**: Represents the current execution state of the task (e.g., `NEW`, `COMPLETING`, `NORMAL`, `EXCEPTIONAL`, `CANCELLED`).

In addition to the AQS state, synchronizers can manage their own state variables. For example, `ReentrantLock` maintains a reference to the active `Thread` object that currently owns the lock to distinguish between reentrant and contended lock acquisitions.

---

## Summary

*   **Synchronizer**: A concurrency construct designed to coordinate the control flow of threads based on an encapsulated state.
*   **Standard Synchronizers**: The JDK provides several implementations including `CountDownLatch` (latches), `CyclicBarrier` (barriers), `Semaphore` (permits), and `FutureTask` (asynchronous tasks).
*   **AQS Sub-Framework**: `AbstractQueuedSynchronizer` is the foundational framework used to build most locks and synchronizers in the Java Concurrency Utilities.
*   **Acquire & Release**: AQS coordinates threads using a state-dependent `acquire` operation (which blocks if state conditions are not met) and a non-blocking `release` operation (which updates state and wakes up blocked threads).
*   **Volatile State Integer**: AQS manages a single volatile integer representing the synchronizer's state. It allows atomic updates via CAS (`compareAndSetState`) to track locks, permits, counts, or task states.
*   **FIFO Wait Queue**: AQS maintains a highly optimized, thread-safe FIFO queue of waiting threads, shielding custom synchronizer implementations from complex low-level thread scheduling logic.
