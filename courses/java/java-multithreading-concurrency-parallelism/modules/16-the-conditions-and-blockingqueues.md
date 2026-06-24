# The Conditions and BlockingQueues

In the previous , we have seen the ReentrantLock with and without fairness and compared their performances. In this part, we will see a key concept that is used in conjunction with ReentrantLocks to implement the BlockingQueues — The Conditions.

First, we understand what a BlockingQueue is in the java concurrency framework, look at several implementations, understand what theCondition object is, and finally implement our own BlockingQueue.

A BlockingQueue is a type of shared collection that is used to exchange data between two or more threads while causing one or more of the threads to wait/block until the point in time when the data can be exchanged. Typically this kind of blocking happens with *bouned buffers*. We will use these kinds of collections to implement the Producer-Consumer patterns. Remember we implemented the *bounded buffers* with synchronized, wait & notify in , where one thread produces data, then adds it to a queue, and another thread consumes the data from the queue. A queue provides the means for the producer and the consumer to exchange objects. The java.util.concurrent package provides several BlockingQueue implementations that can be classified as two types:

**Bounded Queues**
■ ArrayBlockingQueue
■ LinkedBlockingDeque
■ LinkedBlockingQueue
■ PriorityBlockingQueue

**Special-Purpose Queues**
■ SynchronousQueue
■ DelayQueue
■ LinkedTransferQueue

We will only look at Bound-Queues in this part. Each of the above queues has a general behavior. The methods put() and take() cause the calling thread to be blocked; with put() the thread is blocked if the buffer(or the collection in-specific) is full and with take() if the buffer is empty. We can implement producer-consumer patterns with these collection classes very easily as below.

```java
import java.util.Random;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;


public class ArrayBlockingQueueDemo {


    public static void main(String[] args) {
        BlockingQueue<Integer> blockingQueue = new ArrayBlockingQueue<>(5);
        Thread producer = new Thread(() -> {
            new Random().ints().forEach(e -> {
                try {
                    System.out.println(Thread.currentThread() + " - Producing the element: " + e + ", Queue Size now: " + blockingQueue.size());
                    blockingQueue.put(e);
                } catch (InterruptedException ex) {
                    ex.printStackTrace();
                }
            });
        }, "PRODUCER");


        Thread consumer = new Thread(() -> {
            while (true) {
                try {
                    System.out.println(Thread.currentThread() + " - Consuming the element: " + blockingQueue.take() + ", Queue Size now: " + blockingQueue.size());
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        }, "CONSUMER");


        producer.start();
        consumer.start();
    }
}
```

hosted with ❤ by 

Illustration 16.1 ArrayBlockingQueue Demo

With BlockingQueue classes provided in java.util.concurrent package, we don’t really have to struggle to write the producer-consumer patterns. All we need to do is create the BlockingQueue object, PRODUCER thread for producing elements, and CONSUMER thread for consuming elements. All the blocking or waiting is taken care of by BlockingQueue implementations.

**ArrayBlockingQueue****
**In the above program(Illustration 16.1) we have created the ArrayBlockingQueue object which is bounded by size 5 — The Capacity. Then we have created two threads: PRODUCER that puts random numbers into the queue infinitely and CONSUMER that takes the elements and When the size of the queue reaches the capacity(in our case it is 5), the producer is blocked, and when the size is 0 the consumer is blocked. The ArrayBlockingQueue uses an array in a circular fashion, in simple words, it uses an array-based ring buffer with *put-index* and *take-index*. Here is the output snippet.

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

**LinkedBlockingQueue**
The LinkedBlockingQueue can also be used exactly the same way as ArrayBlockingQueue. It just uses the linked list behind the scenes. Replace line 8 in the above program with LinkedBlockingQueue and we will have the same behavior. If we don’t provide any size in the constructor, it will allow a maximum of Integer.MAX_VALUE nodes. The nodes will be created dynamically on each insertion.

**LinkedBlockingDeque****
**The double-ended queue supports insertions and removals from both ends.

**ProrityBlockingQueue****
**It uses the same ordering that is provided by PriorityQueue based on the heap data structure. Operations on this class make no guarantees about the ordering of elements with equal priority.

I think most of the above queues are straightforward to understand, that put() blocks if the collection is full and take() blocks if the collection is empty.

**The “**Condition"** Object:**

All these blocking queues use something known as Condition object to implement the blocking mechanism works similarly to wait & notify.

We have seen the wait-sets in  that every object has a single wait-set associated with it and is used by wait, notify, and notifyAll methods. WithCondition support added in java.util.concurrent.locks package, it allows us to have multiple wait-sets with a single lock object. A Condition object is bound to a Lock object. To obtain a Condition object for a particular  instance, we need to use its  method.

The Lock interface has a method newCondition() that returns us the new Condition object. This object provides us the means for one thread to suspend execution (await) until notified by another thread(signal) that some state condition may now be true. The key property that waiting for a condition provides is that it *atomically* releases the associated lock and suspends the current thread, just like Object.wait.

The Condition object has two main methods:

**await(): **Causes the current thread to wait until it is signaled or interrupted. The lock associated with this Condition is atomically released and the current thread becomes blocked for thread scheduling purposes and lies dormant until some other thread calls signal() on the same Condition object or the current thread is interrupted by other thread. This is just like a wait() method with synchronized.

**signal():** notifies one waiting thread. As a result of this if any threads are waiting on this condition then one is selected for waking up. That thread will then re-acquire the lock and continue the stuff. The signalAll() method wakes up all the waiting threads waiting on this condition.

Lock, await, and signal work just like synchronized, wait, and notify but with synchronized there is only one wait-set associated. With Lock we can create multiple Condition objects that have the waitsets.

With that background set, let's look at how BlockingQueue can be implemented with Lock and Condition. Have a look at the below code. We have implemented our own circular array based BlockingQueue.

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


    public MyArrayBlockingQueue(int capacity) {
        this.capacity = capacity;
        items = (E[]) new Object[capacity];
        lock = new ReentrantLock();
        notEmpty = lock.newCondition();
        notFull = lock.newCondition();
    }


    public void put(E e) throws InterruptedException {
        lock.lock();
        try {
            while (count == capacity) {
                notFull.await();
            }
            items[putIndex] = e;
            if (++putIndex == capacity) {
                putIndex = 0;
            }
            count++;
            notEmpty.signal();
        } finally {
            lock.unlock();
        }
    }


    public E take() throws InterruptedException {
        lock.lock();
        try {
            while (count == 0) {
                notEmpty.await();
            }
            E e = items[takeIndex];
            if (++takeIndex == capacity) {
                takeIndex = 0;
            }
            count--;
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
                    System.out.println(Thread.currentThread() + " - Produced the element: " + e);
                } catch (InterruptedException ex) {
                    ex.printStackTrace();
                }
            });
        }, "PRODUCER");


        Thread consumer = new Thread(() -> {
            int i = 0;
            while (i++ < nElements) {
                try {
                    System.out.println(Thread.currentThread() + " - Consuming the element: ");
                    Integer e = blockingQueue.take();
                    System.out.println(Thread.currentThread() + " - Consumed the element: " + e);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        }, "CONSUMER");


        producer.start();
        consumer.start();


        // wait for producer and consumer thread to complete
        producer.join();
        consumer.join();


    }
}
```

hosted with ❤ by 

Our own implementation of ArrayBlockingQueue with ReentrantLocks and Condition objects

You can see at lines 9–11, we have declared the Lock and Condition variables and in the constructor we have initialized these variables. We have taken two condition variables here to demonstrate that we can have two wait-sets PRODUCER thread in one wait-set andCONSUMER in the other. We could have one Condition object and push the PRODUCER and CONSUMER into the same wait-set. But this would defeat the purpose of using the Condition object. In this case, we could simply go for synchrnozed keyword with wait & notify. Taking two Condition objects is an optimization because we would like to keep waiting PRODUCER and CONSUMER threads in separate wait-sets so that we can notify a single thread at a time when items or spaces become available in the buffer.

The names of the Condition variablesnotFull and notWait may be confusing for you. But we can understand if we put them in words:

notFull.await(): We call this when the queue is full to say that, *“wait till the queue is not-full because the queue is now full*”.

notEmpty.await(): We call this when the queue is empty to say that, *“wait till the queue is not-empty because the queue is now empty”.*

That’s all about the Condition objects.

## Summary

A BlockingQueue is a type of shared collection that is used to exchange data between two or more threads

As the name suggests BlockingQueue causes one or more of the threads to wait/block until the point in time when the data can be exchanged.

The Typical use case of BlockingQueue is to implement the Producer-Consumer patterns with the *Bounded Buffers*.

java.util.concurrent package provides several BlockingQueue implementations viz. ArrayBlocking, LinkedBlockingQueue, PriorityBlockingQueue, etc.

All these blocking queues use something known as Condition object to implement the blocking mechanism works similarly to wait & notify.

The Lock interface has a method newCondition() that returns us the new Condition object which provides means for one thread to suspend execution (await) until notified by another thread(signal) that some state condition may now be true.

Same as Object.wait a condition objects await() method *atomically* releases the associated lock and suspends the current thread.

signal() method notifies the waiting threads on the same Condition object.