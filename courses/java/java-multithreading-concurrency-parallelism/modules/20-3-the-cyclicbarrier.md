# The CyclicBarrier

In the previous , we have seen the three most popular ways of using CountDownLatch. Latches mainly focus on waiting for a group of related events to complete.

The most important thing about Latches is that they are ***Use-Once*** objects; once a latch reaches its terminal state, there is no coming back. The gate is open with no closing — Any number of threads can pass through the gate.

***Any number of threads***? What does it mean and how? This is a little important to understand. Let’s say the latch is initialized with the count as 4. And we have 10 threads waiting for the latch to reach its terminal state. In this case, not all 10 threads need to bring the count down. Only 4 out of 10 threads will need to do so. When that happens the latch reaches theterminal state. As the latch reaches the terminal state, not just the four threads that brought the count down to zero but all the 10 threads will be released. Because all the 10 threads waiting for the gate to be opened. All that the threads need for them to be released is, for the latch to reach its terminal state. Hope you have understood.

Now as we said, the latches are ***Use-Once*** objects, what if we need the same functionality to be repeated more than twice or thrice. Creating those many latches would be a pathetic way of coding it. That’s where ***Barriers*** come into the picture.

***Barriers*** work very similarly to latches — In the sense that they are used to make a group of threads waiting. But they can also be reset and reused again. This is why there are called Cyclical Barriers. The textbooks only specify this difference. But apart from being cyclical, there is another important difference that we need to understand.

## Key Difference between Latch and Barrier

The key difference is that with a barrier, all the threads come at a barrier point at the same time in order to proceed. With Latches the threads don’t come at the latch point, instead, they count down the latch indicating that an event is completed. In simple words, Latches are for waiting for events; Barriers are for waiting for other threads.

*Latches are for waiting for events; barriers are for waiting for other threads.*

To make it easier to understand, let me tell you a simple real-world example. Assume that there is a group of 5 friends who want to eat the dominos pizza and meet at a specific point. There are two ways they can plan their meeting.

First, they can meet at a rendezvous point and go together to the pizza shop from there. As each person arrives they have to wait till all the five have arrived. Or …

Each of them can individually eat the pizza and come to the rendezvous point.

The first case is exactly what the CyclicBarrier solves. All the five people can be thought of as threads waiting at a barrier point.

The second is what CoundDownLatch solves. Each person eating the pizza can be thought of as completing the event. Finishing the Pizza is an event here. Here also the latch waits for all the people to finish the pizza, not their arrival.

Hope this example makes you understand the difference between *Barrier* and *Latch better*. In summary, CyclicBarrier allows a specified number of threads to wait cyclically at a barrier point.

## What does it mean by a Thread Reaching the Barrier Point?

Now, what do we exactly mean by a thread ***reaching the barrier point?*** Well, when a thread calls await() on the barrier, we say it reached the barrier point. That simple. Reiterating the same in different words, the call to await() says to the barrier that a particular thread has arrived at the point.

## The Arrival Index

await() also returns a unique arrival index at the barrier point. This is very useful when electing a leader thread that can perform a special action in the next iteration.

***Reaching the Barrier Point:**** When a thread calles await() it is said to be having arrived at the barrier point.*

***Unique Arrival Index: ****await() returns a unique arrival index that can be useful in electing a thread that can perform a specifc action in the next iteration.*

Here is the example that makes us understand the barrier even better.

```java
import java.time.LocalDateTime;
import java.util.concurrent.BrokenBarrierException;
import java.util.concurrent.CyclicBarrier;


public class CyclicBarrierDemo {


    private static final CyclicBarrier BARRIER = new CyclicBarrier(2, () -> logInfo("Barrier Passed!!"));


    public static void main(String[] args) throws InterruptedException {
        Runnable task = task();


        Thread t
= new Thread(task, "T1");
        Thread t
= new Thread(task, "T2");
        Thread t
= new Thread(task, "T3");
        Thread t
= new Thread(task, "T4");


        t1.start();
        t2.start();


        t1.join();
        t2.join();


        logInfo("First Batch Completed!");
        // BARRIER.reset();
        logInfo("Barrier has been reset! Waiting for second batch!");


        t3.start();
        t4.start();


        t3.join();
        t4.join();


        logInfo("'main' Finished!");
    }


    private static Runnable task() {
        return () -> {
            try {
                logInfo("Working ...");
                Thread.sleep(1000);
                logInfo("Completed. Waiting at the barrier point ...");
                int arrivalIndex = BARRIER.await();
                logInfo("Arrival Index: " + arrivalIndex);
            } catch (InterruptedException | BrokenBarrierException e) {
                e.printStackTrace();
            }
        };
    }


    private static void logInfo(String msg) {
        System.out.println(LocalDateTime.now() + ": " + Thread.currentThread() + " :: " + msg);
    }


}
```

hosted with ❤ by 

Illustration 20.3.1 CyclicBarrier demo with Resetting the Barrier

The above program demonstrated two things: First, the behavior of CyclicBarrier and second, the resetting of CyclicBarrier.

To start the barrier CyclicBarrier we just have to create the object of the CyclicBarrier. It takes two arguments.

***Count:*** The number of threads to wait at the barrier as shown in ***Line-7*** in the above program. We have initialized it with 2

***Action:*** Optional parameter of type Runnable that should be performed when the barrier is successfully passed — That is all the threads reached the barrier point. We have provided a Lambda here at ***Line 7*** which is an instance of Runnable***. ***It just prints a simple message***.***

As each thread finishes its task it just calls await() on the barrier object as shown in line 42. A thread calling await() indicates that it has reached the barrier point and waiting there for all the threads to reach the same point — Which means all the threads should call await(). We have created two batches of threads: the first batch with two threads **T1** and **T2** and the other batch with **T3** and **T4**. We just took this approach just to demonstrate that the barrier could be reset as we have been specifying right from the beginning of the article.

As the first batch completes the main thread resets the barrier at **Line-24** and starts the other batch. The below output shows it clearly.

2022-04-02T21:08:00.301290: Thread[T2,5,main] :: Working ...
2022-04-02T21:08:00.303180: Thread[T1,5,main] :: Working ...
2022-04-02T21:08:01.434358: Thread[T2,5,main] :: Completed. Waiting at the barrier point ...
2022-04-02T21:08:01.441738: Thread[T1,5,main] :: Completed. Waiting at the barrier point ...
2022-04-02T21:08:01.441919: Thread[T1,5,main] :: Barrier Passed!!
2022-04-02T21:08:01.453456: Thread[T2,5,main] :: Arrival Index: 1
2022-04-02T21:08:01.454209: Thread[T1,5,main] :: Arrival Index: 0
2022-04-02T21:08:01.455273: Thread[main,5,main] :: First Batch Completed!
2022-04-02T21:08:01.455451: Thread[main,5,main] :: Barrier has been reset! Waiting for second batch!
2022-04-02T21:08:01.455905: Thread[T3,5,main] :: Working ...
2022-04-02T21:08:01.456231: Thread[T4,5,main] :: Working ...
2022-04-02T21:08:02.456182: Thread[T3,5,main] :: Completed. Waiting at the barrier point ...
2022-04-02T21:08:02.456657: Thread[T4,5,main] :: Completed. Waiting at the barrier point ...
2022-04-02T21:08:02.457197: Thread[T4,5,main] :: Barrier Passed!!
2022-04-02T21:08:02.457596: Thread[T4,5,main] :: Arrival Index: 0
2022-04-02T21:08:02.457666: Thread[T3,5,main] :: Arrival Index: 1
2022-04-02T21:08:02.458262: Thread[main,5,main] :: 'main' Finished!

Now there is a catch here. You don’t really have to explicitly reset the barrier as we did it in **Line-24**. As the barrier passes (all the threads reach the barrier point — all the threads made a call await()), it will get reset automatically.

*The barrier resets automatically as all the threads reach the barrier point. No explicit reset is required in this case.*

One last thing to understand in terms of programming with CyclicBarrier is the BrokenBarrierException. This comes when we use the timeout version of await method. When the await times out or a thread blocked in await is interrupted, the barrier is said to be broken and all outstanding calls to await will terminate with BrokenBarrierException.

**Other Uses of **CyclicBarrier

The one other important use of CyclicBarrier comes in designing the parallel iterative algorithms that follow the divide and conquer approach — Which breaks down a problem into a number of independent subproblems and these subproblems are solved in parallel by different threads. Threads call await on the barrier after they complete their individual subtask and blocks until all the threads have reached the barrier point. The ForkJoinPool uses this technique.

Also, the CyclicBarrier is extensively used in gaming and simulation development.

## Summary

CyclicBarrier allows all threads to meet at the barrier point.

When a thread calles await() it is said to be having arrived at the barrier point.

If all the threads arrive at the barrier point, the barrier has been successfully passed, in which case all threads are released. And the barrier is reset automatically so it can be used again.

CyclicBarrier also lets you pass a barrier action to the constructor; this is a Runnable that is executed (in one of the subtask threads) when the barrier is successfully passed but before the blocked threads are released.

If the barrier is successfully passed, await returns a unique arrival index for each thread, which can be used to “elect” a leader that takes some special action in the next iteration.

If a call to await times out or a thread blocked in await is interrupted, then the barrier is considered broken and all outstanding calls to await terminate with BrokenBarrierException.

That’s all about CyclicBarrier. In the next part, we will have a look at the FutureTask.