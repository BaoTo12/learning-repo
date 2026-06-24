# Concurrent Collections Continued., The ConcurrentLinkedQueue

So far we have seen several concurrent collections like BlockingQueues that support producer-consumer design patterns, other collections just to support concurrent read operations like CopyOnWriteArrayList and ConcurrentHashMap. There are a lot of other concurrent collections that java.util.concurrent framework provides. And the next most important collection to understand is ConcurrentLinkedQueue. In this article, we will look at what is ConcurrentLinkedQueue and its depths.

As the name suggests, it is a queue based on linked nodes, in which all the insertions happen at end of the queue and the removals happen from the beginning of the queue in a thread-safe manner and is unbounded. This queue orders the elements in FIFO(_first-in-first-out_) manner. In simple words, it is an unbounded thread-safe queue based on linked nodes.

There are two operations that the queue supports in general: E*nqueue *that\* *puts the elements at the end of the queue and *Dequeue *that* *removes the elements from the beginning of the queue. Everyone is well aware of what a queue data structure is. But why we are emphasizing this point? There is one important thread-safe non-blocking algorithm that we discuss in this article that exploits this fact and provides concurrent *Enqueue* and *Dequeue\* operations without ever blocking each other.

The simple way to provide the thread safety is to use the intrinsic locks provided by synchronized statements and you know the consequence of this — The Performance. Due to its inherent blocking, the *Enqueue* and *Dequeue* operations block each other. But what is the other way to avoid this?

This is where the * Concurrent Queue *algorithm\* *comes into the picture*.* Please look at this research  published by them. This algorithm relies on the fact that insertions and deletions happen from far ends(*Tail* and *Head\* respectively) of the queue. So the simple logic here is that we have head and tail pointers. The head always points to the first node and the tail always points to the last node.

In a sense, the tail pointer takes care of enqueuing and the head pointer takes care of dequeuing the elements. Since we have two objects dealing with two operations independently why can’t we have the locks on each of these objects independently? So enqueue operation acquires the lock on tail and dequeue operation acquires the lock on head. This is what the \* \*algorithm specifies — Very Simple.

Further, there are two variants mentioned in the above research paper: *Blocking* and *Non-Blocking*.

**_Blocking_**: This is the case when we use locks on head or tail. Here in this case, the *enqueue* and *dequeue* operations may not block each other, but one *enqueue* operation will ever be run by a single thread because of lock, be it an intrinsic or explicit lock.

**_Non-Blocking_**: We don’t really have to go with a lock-based approach here but can go with CASing here right? In fact, Java’s ConcurrentLinkedQueue uses this approach to provide non-blocking thread safety. In this case, one *enqueue* operation will not block the other.

Since Java already implemented the non-blocking version we will here implement the blocking version and compare the performance differences between non-blocking and blocking versions.

```java
import java.util.*;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;


public class BlockingConcurrentLinkedQueue<E> extends AbstractQueue<E> implements Queue<E> {


    private final Lock HEAD_LOCK = new ReentrantLock();
    private final Lock TAIL_LOCK = new ReentrantLock();


    private int nEnqueues = 0;
    private int nDequeues = 0;


    static final class Node<E> {
        E item;
        Node<E> next;


        Node() {
        }


        Node(E item) {
            this.item = item;
        }
    }


    private Node<E> head;
    private Node<E> tail;


    public BlockingConcurrentLinkedQueue() {
        head = tail = new Node<>();
    }


    @Override
    public boolean offer(E e) {
        TAIL_LOCK.lock();
        try {
            tail.next = new Node<>(e);
            tail = tail.next;
            nEnqueues++;
            return true;
        } finally {
            TAIL_LOCK.unlock();
        }
    }


    @Override
    public E poll() {
        HEAD_LOCK.lock();
        try {
            Node<E> newHead = head.next;
            if (newHead == null) {
                return null;
            }
            E item = newHead.item;
            head = newHead;
            nDequeues++;
            return item;
        } finally {
            HEAD_LOCK.unlock();
        }
    }


    @Override
    public int size() {
        return nEnqueues - nDequeues;
    }


    @Override
    public E peek() {
        HEAD_LOCK.lock();
        try {
            if (head.next != null) {
                return head.next.item;
            }
            return null;
        } finally {
            HEAD_LOCK.unlock();
        }
    }


    @Override
    public Iterator<E> iterator() {
        return asList().iterator(); // Not a good thing to do
    }


    @Override
    public <T> T[] toArray(T[] a) {
        return asList().toArray(a); // Just for testing.
    }


    public List<E> asList() { // Just for testing.
        List<E> list = new ArrayList<>();
        for (Node<E> t = head.next; t != null; t = t.next) {
            list.add(t.item);
        }
        return list;
    }


}
```

hosted with ❤ by 

Illustration 17.6.1 Blocking Version of ThreadSafe Linked Queue

The above program implements the blocking version of the thread-safe linked queue, in which the enqueue(offer(e)) operation locks on TAIL and the dequeue(poll()) operation locks on HEAD. Rather than using ReentrantLock we may also use synchronized on head and tail pointers.

When the queue is initiated it creates a dummy node that both head and tail point to. Making head and tail pointing to the same node at any given point in time means that the queue is empty.

The size() method is a little interesting here. Since there are two different lock objects for offer() and poll(), we cannot use the single variable, let’s say size, to keep track of the size of the queue where *enqueue* and *dequeue *operations increment and decrements the value of size by 1 respectively. This is because the *enqueue* and *dequeue* operations happen concurrently without blocking each other they mess up the value of the variable. This is where the AtomicInteger can come and help. But we haven’t introduced them till now. So I used this trick to keep track of the number of enqueues and dequeus. And the size() method simply returns the difference between these two, as shown in the Illustration 17.6.1 at line 64.

The below is the test to compare performance differences between the blocking version (Illustration 17.6.1) and Java’s non-blocking version.

```java
package org.vit.concurrent;


import org.junit.jupiter.api.Test;
import org.vit.threads.BlockingConcurrentLinkedQueue;


import java.util.*;
import java.util.concurrent.*;


import static org.junit.jupiter.api.Assertions.assertEquals;


public class ThreadSafeLinkedQueuePerformanceTest {


    @Test
    public void testLinkedQueue() throws InterruptedException, ExecutionException {
        System.out.println("---------------------------- With Blocking Version  -------------------------");
        for (int nThreads = 1; nThreads <= 16; nThreads++) {
            Long totalTimeNanos = 0L;
            for (int i = 0; i < 10; i++) {
                totalTimeNanos += testQueue(nThreads, new BlockingConcurrentLinkedQueue<>());
            }
            System.out.printf("nThreads: %d, Average Time Taken: %.6f seconds%n", nThreads, totalTimeNanos / (10.
* 1000000000));
        }


        System.out.println("---------------------------- With Non-Blocking Version -------------------------");
        for (int nThreads = 1; nThreads <= 16; nThreads++) {
            Long totalTimeNanos = 0L;
            for (int i = 0; i < 10; i++) {
                totalTimeNanos += testQueue(nThreads, new ConcurrentLinkedQueue<>());
            }
            System.out.printf("nThreads: %d, Average Time Taken: %.5f seconds%n", nThreads, totalTimeNanos / (10.
* 1000000000));
        }
    }


    private Long testQueue(int nThreads, Queue<String> queue) throws InterruptedException, ExecutionException {
        ExecutorService pool = Executors.newFixedThreadPool(nThreads * 2);
        int approxElements = 10000000;
        int totalElements = approxElements / nThreads / 2;
        Future<Long>[] nqFutures = (Future<Long>[]) new Future[nThreads];
        Future<Long>[] dqFutures = (Future<Long>[]) new Future[nThreads];
        for (int i = 0; i < nThreads; i++) {
            nqFutures[i] = pool.submit(new EnqueueTask(totalElements, "Thread-" + i, queue));
            dqFutures[i] = pool.submit(new DequeueTask(totalElements, "Thread-" + i, queue));
        }
        Long totalTimeNanos = 0L;
        for (int i = 0; i < nThreads; i++) {
            totalTimeNanos += nqFutures[i].get();
            totalTimeNanos += dqFutures[i].get();
        }
        pool.shutdown();
        while (!pool.awaitTermination(1000, TimeUnit.MILLISECONDS)) ;
        assertEquals(0, queue.size());
        return totalTimeNanos;
    }


    static class EnqueueTask implements Callable<Long> {


        private final int nElements;
        private final String id;
        private final Queue<String> queue;


        public EnqueueTask(int nElements, String id, Queue<String> queue) {
            this.nElements = nElements;
            this.id = id;
            this.queue = queue;
        }


        @Override
        public Long call() {
            long start = System.nanoTime();
            for (int i = 1; i <= nElements; i++) {
                queue.offer(id + ": " + i);
            }
            return System.nanoTime() - start;
        }
    }


    static class DequeueTask implements Callable<Long> {


        private final int nElements;
        private final String id;
        private final Queue<String> queue;


        public DequeueTask(int nElements, String id, Queue<String> queue) {
            this.nElements = nElements;
            this.id = id;
            this.queue = queue;
        }


        @Override
        public Long call() {
            long start = System.nanoTime();
            for (int i = 1; i <= nElements; i++) {
                if (null == queue.poll()) {
                    i--;
                }
            }
            return System.nanoTime() - start;
        }
    }
}
```

hosted with ❤ by 

Illustration 17.6.2 Performance test between Blocking and Non-Blocking version of Linked Queues

Here is the output of the test.

----------------- With Blocking Version -----------------------
nThreads: 1, Average Time Taken: 1.796719 seconds
nThreads: 2, Average Time Taken: 5.799049 seconds
nThreads: 3, Average Time Taken: 6.415782 seconds
nThreads: 4, Average Time Taken: 7.297813 seconds
nThreads: 5, Average Time Taken: 7.878246 seconds
nThreads: 6, Average Time Taken: 9.283406 seconds
nThreads: 7, Average Time Taken: 11.573031 seconds
nThreads: 8, Average Time Taken: 12.092070 seconds
nThreads: 9, Average Time Taken: 14.326374 seconds
nThreads: 10, Average Time Taken: 14.708931 seconds
nThreads: 11, Average Time Taken: 15.925581 seconds
nThreads: 12, Average Time Taken: 18.669342 seconds
nThreads: 13, Average Time Taken: 19.875975 seconds
nThreads: 14, Average Time Taken: 21.784917 seconds
nThreads: 15, Average Time Taken: 23.018592 seconds
nThreads: 16, Average Time Taken: 23.684360 seconds
----------------- With Non-Blocking Version ---------------------
nThreads: 1, Average Time Taken: 1.09719 seconds
nThreads: 2, Average Time Taken: 3.66789 seconds
nThreads: 3, Average Time Taken: 5.13038 seconds
nThreads: 4, Average Time Taken: 7.16976 seconds
nThreads: 5, Average Time Taken: 8.20706 seconds
nThreads: 6, Average Time Taken: 9.69608 seconds
nThreads: 7, Average Time Taken: 11.06583 seconds
nThreads: 8, Average Time Taken: 12.75866 seconds
nThreads: 9, Average Time Taken: 14.50294 seconds
nThreads: 10, Average Time Taken: 14.68361 seconds
nThreads: 11, Average Time Taken: 15.94937 seconds
nThreads: 12, Average Time Taken: 17.34164 seconds
nThreads: 13, Average Time Taken: 18.96385 seconds
nThreads: 14, Average Time Taken: 19.14408 seconds
nThreads: 15, Average Time Taken: 19.22650 seconds
nThreads: 16, Average Time Taken: 19.87861 seconds

Plotting these numbers gives us the below graph.
![alt text](../images/image20.png)
As you can see from the above graph, as the number of threads keeps on increasing, the ConcurrentLinkedQueue, the non-blocking version seemed to be performing better than the blocking version.

One bad thing about performance tests is you cannot really simulate real-world scenarios. For example in this version of the test, we have taken an equal number of enqueuing and dequeuing threads. But that may or may not be the real-world scenario. But still, these kinds of tests give some insights into how the collections are performing.

## Summary

ConcurrentLinkedQueue is an unbounded thread-safe queue based on linked nodes.

Java’s ConcurrentLinkedQueue uses the * Concurrent Queue *algorithm and a little modification to adapt to the Garbage Collection environments.

There are two variants of \* *Concurrent Queue:* Blocking and Non-Blocking.\*

The blocking version uses locks and the non-blocking version uses CASing.

The locks happen on the head and tail objects individually so that *enqueue* and *dequeue* operations happen concurrently without blocking each other thereby increasing the throughput.
