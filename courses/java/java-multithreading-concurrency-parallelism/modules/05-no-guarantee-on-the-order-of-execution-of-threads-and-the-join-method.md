# NO Guarantee on the order of execution of threads and the join() method

In , we have seen that we can create multiple threads giving the same Runnable. Here we look at the same example and understand the order of their execution.

```java
public class MultipleThreadSameRunnableDemo {


    public static void main(String[] args) {
        MyRunnable task = new MyRunnable();
        Thread t
= new Thread(task, "t1");
        Thread t
= new Thread(task, "t2");
        Thread t
= new Thread(task, "t3");
        t1.start();
        t2.start();
        t3.start();
    }


    private static void methodOne() {
        System.out.println("In Method One");
    }


    static class MyRunnable implements Runnable {


        @Override
        public void run() {
            for (int i = 0; i < 10; i++) {
                System.out.println(String.format("From %s :: %d", Thread.currentThread().getName(), i));
            }
        }
    }
}
```

hosted with ❤ by 

Three threads t1, t2, and t3 having the same runnable.

The above code creates a single Runnable instance and three Thread instances. All three Thread instances get the same Runnable instance, and each thread is given a unique name: t1, t2, and t3. Finally, all three threads are started by invoking start() on those three instances.

Run this program multiple times, and you won’t see the same output every time. Let me rephrase. You may or may not get the same output every time you run the program. One thumb rule about threads in Java is that the order of their execution is NOT guaranteed.

Here are the few points that are to be noted.

Each thread will start and complete. Once a thread has been started, it can never be started again. We will get IllegalThreadStateException if we call start() again on the same thread instance.

Though we started t1 first, followed by t2 and t3, there is no guarantee that t1 will ever run first. It is all up to the JVM Thread Scheduler and it varies from JVM to JVM.

Once a thread is started, there is NO guarantee that it will keep executing till it’s completed. We will never know when it interleaves the CPU core. Again, this depends on the scheduler. We all know about this pretty well, right? We all learned it in our academic subject — Operating Systems.

Within each thread, the execution happens in a predictable order. But the events of different threads can mix in unpredictable ways. That is why if we run the program multiple times or on multiple machines, we may see different outputs.

There is no clear pattern in the order of their execution.

When a thread completes its run() method, the thread dies and the stack for that thread is removed from JVM’s memory.

The 4th point above is the important point to be understood. To understand this better, let's look at the sample output.

*From t2 :: 3**
****From t1 :: 3****
From t2 :: 4**
****From t1 :: 4****
From t2 :: 5**
****From t1 :: 5****
From t2 :: 6**
****From t1 :: 6****
From t2 :: 7**
****From t1 :: 7****
From t2 :: 8**
****From t1 :: 8****
From t2 :: 9*

Focus on the output fromt1. The execution order is predictable. But the way t1, t2 and t3 are getting preempted is not predictable. Here in this output, there seems to be a pattern of how they are getting executed but it will not always be the case. If you run it again, you may not see the same output. Here is the sample output of the second run.

***From t1 :: 0****
****From t1 :: 1****
****From t1 :: 2****
****From t1 :: 3******
From t1 :: 4******
From t1 :: 5******
From t1 :: 6******
From t1 :: 7******
From t1 :: 8******
From t1 :: 9******
****From t3 :: 0**
From t3 :: 1**
From t3 :: 2**
From t3 :: 3*

Hope you got it now.

*Thread execution order is NOT guaranteed.*

So all the story boils down to a single statement that the behavior is NOT guaranteed.

But …

There is a way to tell a thread not to run until some other thread has finished — the join() method.

## join()

join() is a non-static method in the classThread. It lets the current thread join onto the end of the other thread. Look at the following code snippet.

```java
Thread tj = new Thread();
tj.start();
tj.join();
```

This code takes the current thread and joins it to the end of the thread referenced by tj. This means if we assume that this code is running in themain thread inside themain() method, then the main thread will be blocked and won’t become runnable until the thread tj finishes its run() method. There is another flavor of join() that takes milliseconds to wait.

tj.join(2000) // The overloaded method

This says the current thread which is main, wait until tj is completed, but if it takes longer than 5000 milliseconds, then stop waiting and then become runnable.

Now, what is the exact state of the main thread while tj is running? Well, it depends on the flavor of join() method we are using.

***join()***: will put the current thread into WAITING state.

***join(long milliseconds)***: will put the current thread into TIMED_WAITING state.

Now that we understand how join() works let's look at a small example to understand it better.

What we want to achieve is, thread t1 should print 0–9 and main should print 0–5 but only after t1 completes.

```java
package org.vit.threads;


public class ThreadStackDemo {


    public static void main(String[] args) throws InterruptedException {
        MyRunnable task = new MyRunnable();
        Thread t
= new Thread(task, "t1");
        t1.start();
        t1.join();
        for (int i =
; i <
; i++ ){
            System.out.println("From " + Thread.currentThread().getName() + ":: " + i);
        }
    }


    private static void methodOne() {
        System.out.println("In Method One");
    }


    static class MyRunnable implements Runnable {
        @Override
        public void run() {
            for (int i = 0; i < 10; i++) {
                System.out.println(String.format("From %s :: %d", Thread.currentThread().getName(), i));
            }
        }
    }
}
```

hosted with ❤ by 

Sample Output:

From t1 :: 0
From t1 :: 1
From t1 :: 2
From t1 :: 3
From t1 :: 4
From t1 :: 5
From t1 :: 6
From t1 :: 7
From t1 :: 8
From t1 :: 9
From main:: 0
From main:: 1
From main:: 2
From main:: 3
From main:: 4

No matter, how many times we run it, we always get the same output. Because we made it so.

## Summary

A thread can only be started once. Starting a thread that is already started and completed results in IllegalThreadStateException

We cannot guarantee the order of how threads are interleaved. It all depends on the Thread Scheduler.

Once a thread is started, there is NO guarantee that it will keep executing till it’s completed. Within each thread, the execution happens in a predictable order. But the events of different threads can mix in unpredictable ways.

When a thread completes its run() method, the thread dies and the stack for that thread is removed from JVM’s memory.

Using the join() method, we can tell the current thread not to run until some other thread has finished. or We can also tell to wait for a specific amount of time using the other flavor of method — join(long milliseconds)

When we use plain join() the current thread’s state changes to WAITING. And using the join(long milliseconds), changes the current thread’s state to TIMED_WAITING.