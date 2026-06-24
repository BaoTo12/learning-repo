# The Conditions and BlockingQueues

In the previous modules, we explored the `ReentrantLock` with and without fairness and compared their performance under different concurrency levels. In this module, we will examine a key concept that is used in conjunction with `ReentrantLock` to implement thread-safe blocking collections: the **Condition** object.

We will first understand what a **BlockingQueue** is in the Java Concurrency Utilities, look at several standard JDK implementations, explore the underlying mechanics of the **Condition** object, and finally implement our own custom `BlockingQueue` from scratch.

---

## What is a BlockingQueue?

A **BlockingQueue** is a type of thread-safe, shared collection used to exchange data between producer and consumer threads. It causes threads to block or wait until the queue is in a state where the requested operation (inserting or retrieving an element) can be safely performed.

> **Mental Model: Bounded Buffers**
> A **bounded buffer** is a queue with a fixed capacity limit. 
> - If a producer thread tries to add an element to a full buffer, it must block until space becomes available.
> - If a consumer thread tries to take an element from an empty buffer, it must block until an element is produced.
> This forms the foundation of the classic **Producer-Consumer** pattern.

In Module 10, we implemented a basic bounded buffer using the `synchronized` keyword, along with `wait()` and `notify()`. The `java.util.concurrent` package provides highly optimized, production-ready `BlockingQueue` implementations, which can be categorized into two primary types:

### Bounded Queues
*   **`ArrayBlockingQueue`**: A classic bounded blocking queue backed by a circular array.
*   **`LinkedBlockingQueue`**: An optionally bounded blocking queue backed by linked nodes.
*   **`LinkedBlockingDeque`**: A thread-safe, double-ended queue (deque) that supports insertion and removal from both ends.
*   **`PriorityBlockingQueue`**: An unbounded blocking queue that uses the same ordering rules as `PriorityQueue` (using a heap structure).

### Special-Purpose Queues
*   **`SynchronousQueue`**: A zero-capacity queue where each insert operation must wait for a corresponding remove operation by another thread, and vice versa.
*   **`DelayQueue`**: An unbounded blocking queue of delayed elements, in which an element can only be taken when its delay has expired.
*   **`LinkedTransferQueue`**: An unbounded queue that combines features of `LinkedBlockingQueue` and `SynchronousQueue`, allowing producers to block until consumers receive elements.

---

## Implementing the Producer-Consumer Pattern

The core methods that define blocking behavior in a `BlockingQueue` are:
- **`put(E e)`**: Inserts the specified element into the queue, blocking the calling thread if the queue is full.
- **`take()`**: Retrieves and removes the head of the queue, blocking the calling thread if the queue is empty.

Here is a complete, working example demonstrating how easily a producer-consumer relationship can be established using `ArrayBlockingQueue`:

```java
import java.util.Random;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;

public class ArrayBlockingQueueDemo {

    public static void main(String[] args) {
        // Create a bounded queue with a capacity of 5
        BlockingQueue<Integer> blockingQueue = new ArrayBlockingQueue<>(5);

        Thread producer = new Thread(() -> {
            new Random().ints().forEach(e -> {
                try {
                    System.out.println(Thread.currentThread().getName() + " - Producing element: " + e + ", Queue Size: " + blockingQueue.size());
                    blockingQueue.put(e);
                } catch (InterruptedException ex) {
                    Thread.currentThread().interrupt();
                    ex.printStackTrace();
                }
            });
        }, "PRODUCER");

        Thread consumer = new Thread(() -> {
            while (true) {
                try {
                    Integer element = blockingQueue.take();
                    System.out.println(Thread.currentThread().getName() + " - Consuming element: " + element + ", Queue Size: " + blockingQueue.size());
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    e.printStackTrace();
                }
            }
        }, "CONSUMER");

        producer.start();
        consumer.start();
    }
}
```

*Figure 16.1: ArrayBlockingQueue Demo*

### How it Works Under the Hood
1.  **ArrayBlockingQueue**: In the demo above, we initialize the `ArrayBlockingQueue` with a fixed capacity of 5. It uses an array-based ring buffer (circular array) managed by a **put-index** and a **take-index**.
2.  **Thread Blocking**:
    - When the queue size reaches its maximum capacity (5), the `PRODUCER` thread calling `put()` is automatically blocked.
    - When the queue size drops to 0, the `CONSUMER` thread calling `take()` is automatically blocked.
3.  **No Manual Coordination**: We do not need to write complex thread coordination logic with `synchronized`, `wait()`, and `notify()`. The `BlockingQueue` implementation handles all state synchronization and thread blocking internally.

Here is a sample output snippet demonstrating this automatic flow control:

```text
Thread[CONSUMER,5,main] - Consuming the element: -1070351876, Queue Size now: 0
Thread[PRODUCER,5,main] - Producing the element: 1824964048, Queue Size now: 1
Thread[PRODUCER,5,main] - Producing the element: -1661194747, Queue Size now: 1
Thread[CONSUMER,5,main] - Consuming the element: 1824964048, Queue Size now: 0
Thread[CONSUMER,5,main] - Consuming the element: -1661194747, Queue Size now: 0
Thread[PRODUCER,5,main] - Producing the element: 1425634979, Queue Size now: 1
Thread[PRODUCER,5,main] - Producing the element: 1935355780, Queue Size now: 1
Thread[PRODUCER,5,main] - Producing the element: -1260407238, Queue Size now: 2
Thread[PRODUCER,5,main] - Producing the element: -1589854244, Queue Size now: 3
Thread[PRODUCER,5,main] - Producing the element: -305080951, Queue Size now: 4
Thread[PRODUCER,5,main] - Producing the element: -338908732, Queue Size now: 5
Thread[CONSUMER,5,main] - Consuming the element: 1425634979, Queue Size now: 4
Thread[PRODUCER,5,main] - Producing the element: -563707394, Queue Size now: 5
```

---

## Exploring the Bounded Queue Implementations

Each bounded queue has unique characteristics that make it suitable for specific scenarios:

*   **`ArrayBlockingQueue`**: Backed by a single pre-allocated array. It has a low memory footprint because it does not create node objects dynamically, but it can suffer from write contention because it uses a single lock for both read and write operations.
*   **`LinkedBlockingQueue`**: Backed by a linked list. It uses two separate locks—one for putting elements and one for taking elements—which allows a producer and a consumer to operate concurrently. However, it incurs additional garbage collection overhead due to the dynamic creation of node objects on every insertion. If initialized without a capacity, it defaults to `Integer.MAX_VALUE`.
*   **`LinkedBlockingDeque`**: A double-ended version of the linked blocking queue. It allows threads to add or remove elements from both the head and the tail, making it useful for work-stealing patterns.
*   **`PriorityBlockingQueue`**: An unbounded queue where elements are ordered according to their natural priority or a custom `Comparator`. Although it is conceptually a blocking queue, the `put()` operation never blocks because the queue grows dynamically. Only the `take()` operation blocks when the queue is empty.

---

## The "Condition" Object

Under the hood, all standard Java blocking queues rely on the **Condition** interface (`java.util.concurrent.locks.Condition`) to coordinate thread signaling.

In Module 10, we saw that every Java object has a single **wait-set** associated with its intrinsic monitor, which is controlled via `Object.wait()`, `Object.notify()`, and `Object.notifyAll()`. 

The **Condition** interface allows us to associate **multiple wait-sets** with a single explicit `Lock` object. This provides fine-grained, target-specific thread signaling.

### Obtaining a Condition
A `Condition` instance is bound to a specific `Lock`. We obtain it using the `newCondition()` method on a `Lock` instance:

```java
Lock lock = new ReentrantLock();
Condition notFull = lock.newCondition();
Condition notEmpty = lock.newCondition();
```

### Core Condition Methods
*   **`await()`**: Suspends the calling thread. The lock associated with the `Condition` is **atomically released**, and the thread is placed into the wait-set for this specific condition. The thread remains dormant until another thread calls `signal()` or `signalAll()` on this condition, or if the thread is interrupted.
*   **`signal()`**: Wakes up one thread waiting on this condition. The awakened thread must re-acquire the associated lock before returning from `await()`.
*   **`signalAll()`**: Wakes up all threads waiting on this condition.

> **Insight: Multiple Condition Waitsets**
> By creating two separate conditions—`notFull` and `notEmpty`—we can separate the wait-sets of producers and consumers.
> - A producer thread waits on `notFull` (waiting for space to open up) and signals `notEmpty` when an item is added.
> - A consumer thread waits on `notEmpty` (waiting for an item to arrive) and signals `notFull` when an item is removed.
> 
> If we only had a single wait-set (like with intrinsic monitors), a `notify()` call could wake up a producer when we wanted to wake up a consumer, leading to unnecessary thread context switches or thread starvation (unless using the heavier `notifyAll()`).

---

## Custom Bounded Queue Implementation

Let's put this theory into practice. Below is a complete implementation of a custom circular-array-based `MyArrayBlockingQueue` using `ReentrantLock` and two `Condition` variables:

```java
import java.util.Random;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

public class MyArrayBlockingQueue<E> {

    private final int capacity;
    private final Lock lock;
    private final Condition notEmpty;
    private final Condition notFull;
    private final E[] items;

    private int putIndex;
    private int takeIndex;
    private int count;

    @SuppressWarnings("unchecked")
    public MyArrayBlockingQueue(int capacity) {
        this.capacity = capacity;
        this.items = (E[]) new Object[capacity];
        this.lock = new ReentrantLock();
        this.notEmpty = lock.newCondition();
        this.notFull = lock.newCondition();
    }

    public void put(E e) throws InterruptedException {
        lock.lock();
        try {
            // Block while the queue is full
            while (count == capacity) {
                notFull.await();
            }
            items[putIndex] = e;
            if (++putIndex == capacity) {
                putIndex = 0; // Wrap around circular array
            }
            count++;
            
            // Signal waiting consumers that the queue is no longer empty
            notEmpty.signal();
        } finally {
            lock.unlock();
        }
    }

    public E take() throws InterruptedException {
        lock.lock();
        try {
            // Block while the queue is empty
            while (count == 0) {
                notEmpty.await();
            }
            E e = items[takeIndex];
            items[takeIndex] = null; // Help GC
            if (++takeIndex == capacity) {
                takeIndex = 0; // Wrap around circular array
            }
            count--;
            
            // Signal waiting producers that the queue is no longer full
            notFull.signal();
            return e;
        } finally {
            lock.unlock();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        int nElements = 20;
        MyArrayBlockingQueue<Integer> blockingQueue = new MyArrayBlockingQueue<>(5);

        Thread producer = new Thread(() -> {
            new Random().ints(nElements).forEach(e -> {
                try {
                    blockingQueue.put(e);
                    System.out.println(Thread.currentThread().getName() + " - Produced element: " + e);
                } catch (InterruptedException ex) {
                    Thread.currentThread().interrupt();
                    ex.printStackTrace();
                }
            });
        }, "PRODUCER");

        Thread consumer = new Thread(() -> {
            int i = 0;
            while (i++ < nElements) {
                try {
                    Integer e = blockingQueue.take();
                    System.out.println(Thread.currentThread().getName() + " - Consumed element: " + e);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    e.printStackTrace();
                }
            }
        }, "CONSUMER");

        producer.start();
        consumer.start();

        producer.join();
        consumer.join();
    }
}
```

*Figure 16.2: Custom ArrayBlockingQueue implementation using ReentrantLock and Conditions*

### Deep Dive into the Code
1.  **Lock Acquisition**: Both `put()` and `take()` begin by acquiring the explicit lock (`lock.lock()`). This ensures that only one thread can modify the internal array, pointers, and counter at a time.
2.  **Guarding State with Loops**: We check the conditions (`count == capacity` and `count == 0`) inside a `while` loop rather than an `if` block. This is a critical pattern because of **spurious wakeups** (where a thread wakes up without being signaled) or because another thread might have acquired the lock first and consumed the state change before the awakened thread could run.
3.  **Explicit Signaling**:
    - In `notFull.await()`, the producer suspends its execution and atomically releases the lock. When a consumer calls `take()`, it decrements the count and calls `notFull.signal()`, waking up the producer.
    - In `notEmpty.await()`, the consumer suspends its execution. When the producer calls `put()`, it increments the count and calls `notEmpty.signal()`, waking up the consumer.
4.  **Circular Array Logic**: The `putIndex` and `takeIndex` wrap around back to `0` when they reach the array capacity, allowing us to reuse the allocated array slots infinitely.

---

## Summary

*   **BlockingQueue**: A concurrent collection designed to exchange data between threads. It automatically blocks producer threads when the queue is full and consumer threads when the queue is empty.
*   **Standard Implementations**: The JDK offers several implementations including `ArrayBlockingQueue` (array-backed, bounded), `LinkedBlockingQueue` (node-backed, optionally bounded), and `PriorityBlockingQueue` (heap-backed, priority-sorted).
*   **The Condition Object**: Part of the explicit Lock API (`java.util.concurrent.locks.Condition`), it provides a way to coordinate thread waiting and signaling.
*   **Multiple Wait-Sets**: Unlike intrinsic monitors which support only one wait-set per object, explicit locks allow the creation of multiple `Condition` objects, enabling highly optimized, target-specific thread signaling (e.g., separating producer and consumer wait-sets).
*   **Atomic Lock Release**: The `Condition.await()` method atomically releases the associated lock and suspends the thread, placing it in the wait-set. The thread must re-acquire the lock before returning from `await()`.