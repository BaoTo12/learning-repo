# ReentrantLocks and Fairness Continued.,

We have seen the Lock interface and its implementation class ReentrantLock in . Now in this part, we will see ReentrantLock in more detail. We will see the other methods that this API offers, and then we will compare the performance comparisons between *fairness* and *non-fairness*. Here are the methods below from theLock interface.

```java
public interface Lock {
    void lock();
    void lockInterruptibly() throws InterruptedException;
    boolean tryLock();
    boolean tryLock(long timeout, TimeUnit unit) throws
                                 InterruptedException;
    void unlock();
    Condition newCondition();
}
```

We have already specified that ReenetrantLock implements all these methods and provides us the same mutual exclusion semantics and memory-visibility guarantees as synchronized. And we have also seen that we need to go withReentrantLocks for more flexible locking mechanisms and the implementation of Counter using ReentrantLock. Here we will see more examples and how we can use ReentrantLock.

We will now see the other variant of lock() method — the tryLock() . The tryLock() is overloaded — two flavors: One with timeout and the other without.

tryLock() is very useful in writing the code avoiding the deadlocks which are very fatal with the intrinsic locks provided by synchronized. With these two flavors of tryLock() method, we can implement the techniques like Timed and Polled locking that offers probabilistic deadlock avoidance.

**tryLock(): **Tries to acquire the lock, but back off if it cannot be acquired. It returns true if the lock is successfully acquired and false if it fails. The following is the typical usage idiom for tryLock().

```java
Lock lock = ...;
 if (lock.**tryLock**()) { // Enters the if block when lock is acquired
   try {
     // manipulate protected state
   } finally {
     lock.unlock();
   }
 } else {
   // perform alternative actions
 }
```

**tryLock(long timeout, TimeUnit unit): **Tries an attempt to acquire the lock. If the lock is acquired within the timeout specified, it returns immediately with the value true. If the lock is not available within the specified amount of timeout then the current thread is blocked and waits for thread scheduling purposes until one of the below three things happens.

When the lock is acquired by the current thread; or

Some other thread  the current thread, and interruption of lock acquisition is supported; or

When the specified waiting time elapses.

Here is an example of ReentrantLock.

```java
public class TransactionService {


    public boolean transferFunds(Account fromAccount, Account toAccount,
                                 double amount, long timeOutMillis)
            throws InterruptedException, InsufficientFundsException {
        long stopTimeMillis = System.currentTimeMillis() + timeOutMillis;
        while (System.currentTimeMillis() < stopTimeMillis) {
            if (fromAccount.getLock().tryLock()) {
                try {
                    if (toAccount.getLock().tryLock()) {
                        try {
                            if (fromAccount.getBalance() - amount < 0) {
                                throw new InsufficientFundsException();
                            }
                            else {
                                fromAccount.debit(amount);
                                toAccount.credit(amount);
                                return true;
                            }
                        } finally {
                            toAccount.getLock().unlock();
                        }
                    }
                } finally {
                    fromAccount.getLock().unlock();
                }
            }
            Thread.sleep(100);
        }
    }
}
```

hosted with ❤ by 

Illustration 15.1 Deadlock avoidance with tryLock

In the above example, we have used tryLock(). Unlike the lock() method, tryLock() doesn’t cause the thread to go into a blocked state. Instead, it simply returns false saying that lock is not acquired. If the call to tryLock() returns true it means the lock acquisition is successful.

In our example, we have two Account objects referred byfromAccount and toAccount both have a reference to their own ReentrantLock objects. We want to debit money from fromAccount and the credit the same to toAccount. Now we will look at three combinations of lock acquisitions for this example.

**Case-1: Thread could acquire both the locks**
If the call to tryLock() at line 8 returns true which means it acquired the lock on fromAccount , then the thread goes ahead and tries to acquire the lock on toAccount at line 10. If this is also successful then it performs the debit and credit operations from the respective Account objects. Note that, no other thread would ever interfere with these operations since both the locks are acquired by the current thread. After the work is done, the thread releases the locks on toAccount and fromAccount.

**Case-2: Thread could acquire outer lock only**
Assume that the thread acquired the lock on fromAccount(at line 8) but failed in acquiring the lock on toAccount(at line 10), then the thread will release the lock that it acquired on fromAccount(at line 25). This is why we say that tryLock can avoid the deadlocks. Because in our example, the thread never holds the lock, if it is not able to acquire the other lock. In this case, it will release the lock on fromAccount, sleeps for 100 milliseconds(at line 31), then retries till both the locks are acquired. It repeats this process until the given transaction time limit is reached, in which case, it returns false saying that the transaction is not successful.

**Case-3 — The Thread failed in acquiring the outer lock**
If the thread failed in acquiring the lock on fromAccount(at line 8), it simply sleeps for 100 milliseconds and retries acquiring the lock again. It repeats this process until the given transaction time limit is reached.

Now here in this example, we could also use the timed version of tryLockas below.

```java
while (System.currentTimeMillis() < stopTimeMillis) {
   if (fromAccount.getLock().tryLock(**100, TimeUnit.*****MILLISECONDS***)) {
      try {
         if (toAccount.getLock().tryLock(**100, TimeUnit.*****MILLISECONDS***)) {
            try {
               if (fromAccount.getBalance() - amount < 0) {
                  throw new InsufficientFundsException();
               }
               else {
                  fromAccount.debit(amount);
                  toAccount.credit(amount);
                  return true;
               }
            } finally {
               toAccount.getLock().unlock();
            }
         }
      } finally {
         fromAccount.getLock().unlock();
      }
   }
   Thread.*sleep*(100);
}
```

In this case, the call to tryLock() will block the thread for 100 milliseconds if the lock is not acquired, then returns false. But for these kinds of scenarios, the former approach(Illustration 15.1) is the recommended way to go because we need to handle the transaction timeout as well.

## Fairness

That’s the story with tryLock. Now we will look at another important feature that is provided by ReentrantLock — The Fairness. Remember the optional boolean parameter to the ReentrantLock constructor. This is for defining fairness behavior.

**Without Fairness**: The lock does not guarantee any particular *access order*. The term *access order* means the order in which threads request the lock.

**With Fairness: **The lock prefers granting access to the longest-waiting thread.

There are three very important points to be noted with *Fairness*.

The fairness of locks does not guarantee the fairness of thread scheduling. People are often confused with this that fairness means the JVM runs the first-ever thread that requested access to the lock. No, fairness is the feature provided by ReentrantLock not by the JVM. ReentrantLock internally maintains queues to favor granting access to the long-waiting thread. After the access is given, it is up to the JVM when the thread gets scheduled for running.

The multithreaded programs that use fair locks are often slower because the ReentrantLock needs to perform extra steps to ensure fairness apart from maintaining the internal blocking queues. Don’t think fairness means faster. It is actually the opposite. So we shouldn’t really get excited about the fairness of locks provided by ReentrantLock because they are often much slower. We will soon compare the performance between fairness and non-fairness. Stay tuned.

The untimed version of tryLock() does not honor the fairness setting. That means the thread that uses the untimed version of tryLock() will succeed if the lock is available even if other threads are waiting in the queue.

With that being said, we will now look at implementing the append operation of ConcurrentDoublyLinkedList, run this with and without *fairness,* and will compare the performance differences.

```java
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;


public class ConcurrentDoublyLinkedList<E> {


    private final Lock GLOBAL_MUTEX;


    private class DLLNode {


        private DLLNode prev;
        private E data;
        private DLLNode next;


        private DLLNode(DLLNode prev, E data, DLLNode next) {
            this.prev = prev;
            this.data = data;
            this.next = next;
        }


    }

    private DLLNode front;
    private DLLNode rear;


    public ConcurrentDoublyLinkedList() {
        this(true);
    }


    public ConcurrentDoublyLinkedList(boolean fairness) {
        front = rear = null;
        GLOBAL_MUTEX = new ReentrantLock(fairness);
    }


    public void append(E data) {
        GLOBAL_MUTEX.lock();
        try {
            if (rear == null || front == null) {
                front = rear = new DLLNode(null, data, null);
                return;
            }
            rear.next = new DLLNode(rear, data, null);
            rear = rear.next;
        } finally {
            GLOBAL_MUTEX.unlock();
        }
    }


    public List<E> getAsList() {
        GLOBAL_MUTEX.lock();
        try {
            List<E> list = new ArrayList<>();
            for (DLLNode temp = front; temp != null; temp = temp.next) {
                list.add(temp.data);
            }
            return list;
        } finally {
            GLOBAL_MUTEX.unlock();
        }
    }

}
```

hosted with ❤ by 

Illustration 15.2 ConcurrentDoublyLinkedList with ReentrantLock

I think I don’t have to explain much in the above program. We have an overloaded constructor of ConcurrentDoublyLinkedList to accept the fairness flag. The default constructor specifies the fairness flag as true. And we have taken a GLOBAL_MUTEX — a ReentrantLock object to guard the critical regions of the code. Below is the performance test.

```java
import org.junit.jupiter.api.Test;


import java.util.concurrent.*;


import static org.junit.jupiter.api.Assertions.assertEquals;


public class ConcurrentDoublyLinkedListTest {


    @Test
    public void testDLLMultiThreaded() throws InterruptedException, ExecutionException {
        System.out.println("---------------------------- With Fairness -------------------------");
        for (int nThreads = 1; nThreads <= 16; nThreads++) {
            Long totalTimeNanos = 0L;
            for (int i = 0; i < 10; i++) {
                totalTimeNanos += testDLLMultithreaded(nThreads, true);
            }
            System.out.printf("nThreads: %d, Average Time Taken: %.6f seconds%n", nThreads, totalTimeNanos / (10.
* 1000000000));
        }


        System.out.println("---------------------------- Without Fairness -------------------------");
        for (int nThreads = 1; nThreads <= 16; nThreads++) {
            Long totalTimeNanos = 0L;
            for (int i = 0; i < 10; i++) {
                totalTimeNanos += testDLLMultithreaded(nThreads, false);
            }
            System.out.printf("nThreads: %d, Average Time Taken: %.5f seconds%n", nThreads, totalTimeNanos / (10.
* 1000000000));
        }
    }


    public Long testDLLMultithreaded(final int nThreads, final boolean fairness) throws InterruptedException, ExecutionException {
        ExecutorService pool = Executors.newFixedThreadPool(nThreads);
        int approxElements = 100000;
        int totalElements = approxElements / nThreads;
        ConcurrentDoublyLinkedList<String> dll = new ConcurrentDoublyLinkedList<>(fairness);
        Future<Long>[] futures = (Future<Long>[]) new Future[nThreads];
        for (int i = 0; i < nThreads; i++) {
            futures[i] = pool.submit(new Task(totalElements, "Thread-" + i, dll));
        }
        Long totalTimeNanos = 0L;
        for (int i = 0; i < nThreads; i++) {
            totalTimeNanos += futures[i].get();
        }
        pool.shutdown();
        while (!pool.awaitTermination(1000, TimeUnit.MILLISECONDS)) ;
        assertEquals(totalElements * nThreads, dll.getAsList().size());
        return totalTimeNanos;
    }


    static class Task implements Callable<Long> {


        private final int nElements;
        private final String id;
        private final ConcurrentDoublyLinkedList<String> dll;


        public Task(int nElements, String id, ConcurrentDoublyLinkedList<String> dll) {
            this.nElements = nElements;
            this.id = id;
            this.dll = dll;
        }


        @Override
        public Long call() {
            long start = System.nanoTime();
            for (int i = 1; i <= nElements; i++) {
                dll.append(id + ": " + i);
            }
            return System.nanoTime() - start;
        }
    }


}
```

hosted with ❤ by 

It is kind of hard for me to explain this test in words. But I will try to explain to my best. Please go through the points below to understand what this test is doing.

It performs the test with and without fairness.

It creates a thread pool 1-16 times, each time with 1–16 threads.

So what do I mean by this is, the test creates a thread pool with one thread and executes the task of inserting 100000 elements 10 times. Every time the task gets executed it returns the time taken to complete that operation. Then it averages that time, basically time / 10 will give us the average time because we are performing it 10 times. Then it creates the pool with two threads and repeats the same. Then with three threads and then four and so on. The test is basically checking the performance of multiple threads doing the inserting of 100000 elements.

If you check the below output, you will understand the test better. we can write a benchmark test using JMH. Anyways, here is the output of the above test.

-------------------------- With Fairness -------------------------
nThreads: 1, Average Time Taken: 0.024738 seconds
nThreads: 2, Average Time Taken: 0.498656 seconds
nThreads: 3, Average Time Taken: 1.055133 seconds
nThreads: 4, Average Time Taken: 1.393851 seconds
nThreads: 5, Average Time Taken: 1.875610 seconds
nThreads: 6, Average Time Taken: 2.277003 seconds
nThreads: 7, Average Time Taken: 2.560629 seconds
nThreads: 8, Average Time Taken: 2.909224 seconds
nThreads: 9, Average Time Taken: 3.178827 seconds
nThreads: 10, Average Time Taken: 3.633036 seconds
nThreads: 11, Average Time Taken: 3.981543 seconds
nThreads: 12, Average Time Taken: 4.347921 seconds
nThreads: 13, Average Time Taken: 4.741238 seconds
nThreads: 14, Average Time Taken: 5.083909 seconds
nThreads: 15, Average Time Taken: 5.443723 seconds
nThreads: 16, Average Time Taken: 5.986788 seconds
------------------------ Without Fairness -------------------------
nThreads: 1, Average Time Taken: 0.00632 seconds
nThreads: 2, Average Time Taken: 0.03480 seconds
nThreads: 3, Average Time Taken: 0.02704 seconds
nThreads: 4, Average Time Taken: 0.04301 seconds
nThreads: 5, Average Time Taken: 0.04417 seconds
nThreads: 6, Average Time Taken: 0.05442 seconds
nThreads: 7, Average Time Taken: 0.06358 seconds
nThreads: 8, Average Time Taken: 0.06685 seconds
nThreads: 9, Average Time Taken: 0.06625 seconds
nThreads: 10, Average Time Taken: 0.10528 seconds
nThreads: 11, Average Time Taken: 0.09583 seconds
nThreads: 12, Average Time Taken: 0.13354 seconds
nThreads: 13, Average Time Taken: 0.10901 seconds
nThreads: 14, Average Time Taken: 0.11782 seconds
nThreads: 15, Average Time Taken: 0.13249 seconds
nThreads: 16, Average Time Taken: 0.14194 seconds

You can see from the above output, without fairness it runs much faster than with fairness. So we need to be careful in using fairness as it makes things slower. We always need to perform benchmark tests when we want to enable fairness. In the below diagram, we take these numbers and plotted a graph, and here is how it looks like.
![alt text](../images/image11.png)
So, when we don’t think there is no scope for starvation, we should always go without fairness. Starvation is a very rare scenario though.

There are other following methods that ReentrantLock provides:

**hasQueuedThreads**(): Returns if there are any threads are waiting to acquire the lock.

**getQueueLength(): **Returns an estimate of the number of threads waiting to acquire this lock. The value is only an estimate because the number of threads may change dynamically while this method traverses internal data structures. This method is designed for use in monitoring the system state, not for synchronization control.

**isLocked()**: Queries if this lock hed by any thread.

**isHeldByCurrentThread()**: Queries if this lock is held by the current thread.

**getHoldCount()**: Queries the number of holds on this lock by the current thread.

## Summary

A ReentrantLock provides the same basic behavior and semantics as the implicit monitor lock accessed using synchronized methods and statements, but with extended capabilities.

A thread invoking lock() will return, successfully acquiring the lock, when the lock is not owned by another thread.

The method will return immediately if the current thread already owns the lock. This can be checked using methods isHeldByCurrentThread(), and getHoldCount().

If the fairness parameter set in the ReentrantLock(via constructor while creating the object), the locks prefer to grant access to the longest-waiting thread. Otherwise, this lock does not guarantee any particular access order.

The untimed  method does not honor the fairness setting. It will succeed if the lock is available even if other threads are waiting.

Programs using fair locks accessed by many threads are often much slower than those using the default setting(which is non-fairness).

That’s all about ReentrantLock. In the next part, we will see Condition objects which are similar to wait & notify constructs.
