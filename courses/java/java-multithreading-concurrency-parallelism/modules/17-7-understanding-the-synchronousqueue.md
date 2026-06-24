# Understanding the SynchronousQueue

So far we have explored commonly used concurrent collections designed to store and manage elements in memory. In this module, we will examine a highly specialized, zero-capacity concurrent collection: the **`SynchronousQueue`**.

`SynchronousQueue` is a unique and powerful synchronization tool that behaves differently from traditional queues. Rather than acting as a storage buffer for elements, it acts as a direct point of rendezvous between threads.

---

## What is a SynchronousQueue?

A **`SynchronousQueue`** is a blocking queue with a **capacity of zero**. 
- Every **`put`** operation must block until a corresponding **`take`** or **`poll`** operation is performed by another thread.
- Every **`take`** operation must block until a corresponding **`put`** or **`offer`** operation is performed by another thread.

This means that at any given moment, the queue contains no elements, nor can it hold any. It is simply a conduit that allows a producer thread and a consumer thread to hand off an element atomically.

Let's look at what happens when a single thread attempts to insert an element:

```java
import java.util.concurrent.SynchronousQueue;

public class DeadlockDemo {
    public static void main(String[] args) throws InterruptedException {
        SynchronousQueue<Integer> sq = new SynchronousQueue<>();
        
        // This call blocks indefinitely because there is no consumer waiting
        sq.put(10); 
        
        System.out.println("The element is inserted"); // This line will never execute
    }
}
```

Because there is no other thread waiting to receive the element, the calling thread blocks at `sq.put(10)` indefinitely. The same behavior occurs if a thread attempts to take an element from an empty queue:

```java
import java.util.concurrent.SynchronousQueue;

public class ConsumerBlockDemo {
    public static void main(String[] args) throws InterruptedException {
        SynchronousQueue<Integer> sq = new SynchronousQueue<>();
        
        // This call blocks indefinitely because there is no producer waiting
        sq.take(); 
        
        System.out.println("The element is retrieved"); // This line will never execute
    }
}
```

---

## Thread Rendezvous: A Working Example

To use a `SynchronousQueue` successfully, we must coordinate two threads so they can rendezvous and hand off data. Below is a working demonstration:

```java
import java.util.concurrent.SynchronousQueue;

public class SynchronousQueueDemo {

    public static void main(String[] args) throws InterruptedException {
        SynchronousQueue<Integer> sq = new SynchronousQueue<>();

        // Create a producer thread (PUTTER)
        new Thread(() -> {
            try {
                Thread.sleep(200);
                System.out.println("PUTTER: Attempting to put 10...");
                sq.put(10);
                System.out.println("PUTTER: Put 10 successfully!");

                Thread.sleep(200);
                System.out.println("PUTTER: Attempting to put 20...");
                sq.put(20);
                System.out.println("PUTTER: Put 20 successfully!");

                Thread.sleep(200);
                System.out.println("PUTTER: Attempting to put 30...");
                sq.put(30);
                System.out.println("PUTTER: Put 30 successfully!");
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                ex.printStackTrace();
            }
        }, "PUTTER").start();

        // The main thread acts as the consumer
        Thread.sleep(500); // Give the PUTTER thread time to start and block
        System.out.println("MAIN: Attempting to take...");
        System.out.println("MAIN: Received -> " + sq.take());
        
        Thread.sleep(500);
        System.out.println("MAIN: Attempting to take...");
        System.out.println("MAIN: Received -> " + sq.take());
        
        Thread.sleep(500);
        System.out.println("MAIN: Attempting to take...");
        System.out.println("MAIN: Received -> " + sq.take());
    }
}
```

### Output
```text
PUTTER: Attempting to put 10...
MAIN: Attempting to take...
PUTTER: Put 10 successfully!
MAIN: Received -> 10
PUTTER: Attempting to put 20...
MAIN: Attempting to take...
PUTTER: Put 20 successfully!
MAIN: Received -> 20
PUTTER: Attempting to put 30...
MAIN: Attempting to take...
PUTTER: Put 30 successfully!
MAIN: Received -> 30
```

### Understanding the Flow
No matter how many times you run this program, the threads will always execute in lockstep.
1.  The `PUTTER` thread attempts to call `sq.put(10)` and immediately blocks because the `main` thread is sleeping and not yet waiting to take.
2.  Once the `main` thread wakes up and calls `sq.take()`, the rendezvous is complete. The element `10` is passed directly from the `PUTTER` stack to the `main` thread stack, and both threads continue.
3.  This pattern repeats for values `20` and `30`.

---

## Blocking vs. Non-Blocking Operations

It is critical to distinguish between the blocking and non-blocking methods on a `SynchronousQueue`:

### Blocking Methods (Rendezvous Required)
*   **`put(E e)`**: Inserts the element, blocking until a consumer retrieves it.
*   **`take()`**: Retrieves and removes the head, blocking until a producer inserts it.

### Non-Blocking Methods (Instant Feedback)
*   **`offer(E e)`**: Attempts to insert the element. If a consumer thread is **already waiting** to receive it, the handoff occurs instantly and the method returns `true`. If no consumer is waiting, the method immediately returns `false`. It does **not** queue the element, nor does it block.
*   **`poll()`**: Attempts to retrieve the head element. If a producer thread is **already waiting** to hand off an element, the retrieval occurs instantly and the element is returned. If no producer is waiting, the method immediately returns `null`.

Let's verify this behavior:

```java
import java.util.concurrent.SynchronousQueue;

public class NonBlockingDemo {
    public static void main(String[] args) {
        SynchronousQueue<Integer> sq = new SynchronousQueue<>();
        
        // Returns false immediately because no thread is waiting to take
        System.out.println("Offer successful? " + sq.offer(10)); 
        
        // Returns null immediately because no thread is waiting to put
        System.out.println("Poll result: " + sq.poll()); 
    }
}
```

### Output
```text
Offer successful? false
Poll result: null
```

For this reason, when working with `SynchronousQueue`, you will almost exclusively use `put()` and `take()`.

---

## Unique Characteristics of SynchronousQueue

The JDK documentation highlights three unique rules that distinguish `SynchronousQueue` from other queues:

1.  **No Peeking**: The `peek()` method always returns `null`. An element is only present when you actively attempt to remove it; you cannot inspect it without removing it.
2.  **No Storage**: You cannot insert an element using any method (like `add()`) unless another thread is actively trying to remove it at that exact instant.
3.  **No Iteration**: You cannot iterate over the queue (its iterator returns an empty iterator), because there is nothing to iterate. The `size()` of the queue is always `0`.

---

## The Ping-Pong Analogy

> **Mental Model: The Ping-Pong Game of Rendezvous**
> Consider a game of Table Tennis (Ping-Pong). There are two players (threads) and a table between them (`SynchronousQueue`). 
> - A player cannot hit the ball (call `put()`) and walk away; they must wait for the opponent to return it.
> - If one player hits the ball and there is no opponent on the other side of the table, the ball flies off the table (similar to a failed `offer()`).
> - For the game to progress, both players must be present at the table, coordinating their actions in a continuous sequence of hits and returns (a series of thread rendezvous).

This makes `SynchronousQueue` the ideal tool for implementing **handoff designs** (such as passing tasks or events directly from a listener thread to a worker thread). In fact, the JDK's `Executors.newCachedThreadPool()` uses a `SynchronousQueue` to hand off incoming tasks directly to idle worker threads, ensuring that tasks are dispatched immediately without being queued in memory.

---

## Summary

*   **Zero Capacity**: `SynchronousQueue` has a capacity of zero and does not store elements. It acts as a direct point of rendezvous between threads.
*   **Blocking Handoff**: The `put()` and `take()` methods are blocking operations. A producer blocks until a consumer retrieves the element, and a consumer blocks until a producer provides one.
*   **Non-Blocking Handoff**: The `offer()` and `poll()` methods are non-blocking. They return `false` or `null` immediately unless another thread is already waiting to complete the rendezvous.
*   **API Constraints**: The `peek()` method always returns `null`, the queue size is always `0`, and the queue cannot be iterated over because no elements are stored.
*   **Handoff Designs**: Ideal for rendezvous channels and handoff architectures where data, tasks, or events must be passed directly from one thread to another without buffering delay.