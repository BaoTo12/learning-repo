# Thread Priorities and yield()

In part-5 we have seen how the order of thread execution happens and the join() method to join the currently running thread at the end of the other thread. We have also learned that there is no guarantee in the order of threads' execution. Here in this part, we’ll have a look at the thread priorities and how we expect to gracefully threads can take their turns using the yield(). But before understanding the yield() method, it is really important to look at thread priorities.

In Java, thread priorities are just the numbers from 1 to 10 (1: being the lowest priority and 10: the highest). The scheduler in most JVMs is priority-based preemptive scheduling with some sort of time slicing. What does that mean? Preemptive essentially means turn-taking. The threads take CPU’s turn after some time elapses and which thread to take its turn next depends on the priority of the thread.

But the thread scheduling algorithm varies from JVM to JVM. And even JVM specification doesn't specify which scheduling algorithm to use. It all depends on how the thread scheduler is implemented in a particular JVM. We cannot even guarantee whether all the JVMs use thread priorities in the first place. They may also use Round-Robin with a time slice. There is no such rule enforced anywhere in JVM Spec. But in most of the JVMs, the thread scheduler does use the priorities in one important way: That is when a thread enters the runnable queue and it has higher priority than any of the threads in the queue or the higher priority than the currently running thread, then the lower priority running thread will be pushed back to the runnable queue and the highest priority running thread will be chosen to run.

In most cases, the running thread will be of equal or greater priority than the highest-priority thread in the queue. Once again, there is no guarantee and we should NOT rely on thread priorities to state the correctness of our program.

_NOTE: Never ever rely on thread priorities to guarantee the correctness of your multithreaded application. What is also not guaranteed is which thread will get picked up from the queue when all the threads have the same priority._

## Setting Thread’s Priority

The methodssetPriority() and getPriority() in the Thread class provide the interface to set and get the Thread’s priority respectively.

```java
Runnable task = new FileDownloaderTask(fileUrl);
Thread worker = new Thread(task, 'FileDownloader');
worker.setPriority(4);
worker.start();
```

hosted with ❤ by 

Sample Code for setting the thread priority

The default priority of a thread is 5 if none specified and the Thread class has the following constants that define the thread priorities.

```java
public class Thread implements Runnable {


    /**
     * The minimum priority that a thread can have.
     */
    public static final int MIN_PRIORITY = 1;


   /**
     * The default priority that is assigned to a thread.
     */
    public static final int NORM_PRIORITY = 5;


    /**
     * The maximum priority that a thread can have.
     */
    public static final int MAX_PRIORITY = 10;


}
```

hosted with ❤ by 

Now, what does the method yeild() have to do with thread priorities? Well, yield() is supposed to push the currently running thread back to the runnable queue to allow other threads of the same priority to get their turn. So the intention of using yield() is to request graceful turn-taking among equal-priority threads. But you know what yield() is just a request. There is no guarantee that this request is honored by JVM. I know you get bored of me saying ‘**_No Guarantee_**’. But that’s just the reality with Java multithreading. It all depends on how the thread scheduler is implemented in a particular JVM. So just sink this fact into your brain that there is NO guarantee yield() will pause the current thread and pick up another thread of the same priority from the runnable queue. No Guarantee.

All in all, yield() won’t ever cause the current thread to go to the waiting/sleeping/blocking state. At most yield() will cause a thread to get pushed back to the runnable queue. But again, it might or might not have an effect at all. Also, the state of the thread won’t ever have an effect. That means if you call yeild() on the current thread the state of the thread will remain RUNNABLE.

Okay, enough of No Guarantee business. Now that you understand yield(), let us revisit the other methods sleep() and join() from our previous posts (parts: , , and ).

**sleep()**: cause the current thread to pause for at least the specified duration. Puts the thread’s state to TIMED_WAITING.

**yield()**: Not guaranteed to much of anything. yield() merely a request and NOT guaranteed to be honored by JVM. But the expectation is to cause the currently running thread to leave the CPU and sit in the runnable queue so that the thread of the same priority can take its turn and gets executed by the CPU.

**join(): **A call to join() is guaranteed to cause the current thread to pause until the thread that it joins with(on which the join() method is called) completes.

Apart from these, we have methods wait() and notify() that are called on a specific object rather than a Thread class’s instance. We will talk much about these in later parts in detail when we discuss synchronization and locking.

Here is the program that illustrates yeild(). Run it multiple times and see the behavior. If you have patience, you can run it on multiple JVMs as well.

_No Guarantee _:)

```java
public class YieldDemo {


    public static void main(String[] args) {
        Runnable r
= () -> {
            for (int i = 1; i <= 20; i++) {
                if (
== (i % 5)) {
                    Thread.yield();
                    System.out.println(Thread.currentThread().getName() + " State After Yield: " + Thread.currentThread().getState());
                }
                System.out.println(Thread.currentThread().getName() + " i = " + i);
            }
        };


        Thread t
= new Thread(r1, "T1");
        Thread t
= new Thread(r1, "T2");
        Thread t
= new Thread(r1, "T3");


        t1.start();
        t2.start();
        t3.start();


        System.out.println(Thread.currentThread().getName() + " is finished!");
    }


}
```

hosted with ❤ by 

Yield Demo

In the above program, we created a Runnable with the name r1 with Lambda that prints 1 to 20 to console. Then we created and started three threads T1, T2, and T3 with this Runable.

## Sample Output:

main is finished!
T3 i = 1
T2 i = 1
T1 i = 1
T2 i = 2
T3 i = 2
T2 i = 3
T1 i = 2
T2 i = 4
T3 i = 3
T3 i = 4
T1 i = 3
T1 i = 4
T2 State After Yield: RUNNABLE
T1 State After Yield: RUNNABLE
T2 i = 5
T3 State After Yield: RUNNABLE
T2 i = 6
T1 i = 5
T2 i = 7
T3 i = 5
T2 i = 8
T1 i = 6
T1 i = 7
T1 i = 8
**T1 i = 9\*\***
T1 State After Yield: RUNNABLE\***\*
T1 i = 10\*\***
**T1 i = 11
T1 i = 12
T1 i = 13
T1 i = 14
T1 State After Yield: RUNNABLE
T1 i = 15
T1 i = 16
T1 i = 17
T1 i = 18
**T1 i = 19\***\*
T1 State After Yield: RUNNABLE\*\***
T1 i = 20\*\*
T2 i = 9
T3 i = 6
T3 i = 7
T3 i = 8
T3 i = 9

Two things we can observe from the above output. Look at the highlighted stuff in bold. When T1 is yielded, ideally another thread either T2 or T3 is expected to be executed. But T1 is continuing. And no effect on the state as well. It is still RUNNABLE.

## Summary:

Each thread in Java has priority. Thread priorities are just the numbers from 1 to 10 (1: being the lowest and 10: The highest). The default is 5 if none is specified.

The call to yield() on the current thread is expected to put the currently running thread to runnable queue and pick up any other thread with the same priority and start executing it. However, this behavior is JVM-specific.

Unlike sleep(), join(), wait(), the method yield() won’t ever cause the current thread to go into BLOCKED, WAITING, TIMED_WAITING state. The thread will always go to RUNNABLE after yeild(). In fact, there is no change in the state of the Thread.
