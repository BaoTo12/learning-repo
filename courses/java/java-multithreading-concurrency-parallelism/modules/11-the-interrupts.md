# The interrupts

In  we have seen the behavior of wait & notify and their purpose in multithreaded programming. Here we will see yet another small concept that most people get confused about — *The Interrupts*

An *interrupt* is an indication to a thread that it should stop what it is doing and do something else. It’s up to the programmer to decide exactly how a thread responds to an interrupt, but it is very common practice to make the thread stop.

But who interrupts the threads in the first place? Well, one thread interrupts the other. Because whether or not we use the threads in Java JVM creates one thread, the main thread, with which our program execution begins. So it is one thread that interrupts another thread by invoking the method interrupt() on the target thread object which is to be interrupted.

For the interrupt mechanism to work properly, the thread that is being interrupted must support the interruption. What do we mean by this? Suppose, we have two threads T1 and T2. T1 interrupts T2 by calling T2.interrupt() , then T2 must have some logic to support or handle this interrupt (since the T2 is the target thread). We call this logic the I***nterrupt Handler***. Then, how do threads implement these interrupt handlers? Well, this depends on what we want and what the thread is doing at the time of interrupt. But the common practice is to stop the thread that is being interrupted. There are two typical ways to handle the interrupts.

First, all the methods that throw InterruptedException such as: Thread.sleep(), Thread.join(), Object.wait() have the built-in interrupt handlers. All we need to do is to catch this InterruptedException and handle it in the catch block. So the exception handler (the try-catch block of InterruptedException) becomes the Interrupt Handler. As a general practice, the logic in the interrupt handler (the catch block) is written in such a way that it stops the thread itself. It is a common practice to stop the thread in InterruptHandler though it all depends on our use case. But the InterruptHandlers are the nicer way to stop the threads (gracefully without using Thread.stop() ). You all know that*Thread.stop() is not a recommended way of stopping the thread* (More on this later). The following better explains this behavior.

```java
public class StoppingThreadWithInterrupt extends Thread {


    public void run() {
        System.out.print(Thread.currentThread().getName() + ": I am doing work ");
        while (true) {
            System.out.print(". ");
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                System.out.println("\n" + Thread.currentThread().getName() + ": I have been Interrupted!!");
                break;
            }
        }
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }


    public static void main(String[] args) throws InterruptedException {
        Thread t
= new StoppingThreadWithInterrupt();
        t1.start();
        Thread.sleep(5000);
        t1.interrupt();
        Thread.sleep(1000);
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }


}
```

hosted with ❤ by 

Illustration 11.1: Stopping Threads Gracefully using Interrupts

Let us dive deep into the above program. It represents the first way of handling the interrupts — *With the methods that throw *InterruptedException*. *We have already specified that these methods (sleep, join, wait and etc) have built-in interrupt handlers. So what is happening in the above program is, the main thread creates another thread t1 (at line 18) and starts it. And the main thread sleeps for 5 seconds. The thread t1 calls Thread.sleep() in a loop (t1 goes into TIMED_WAITING state for every second). Then the main thread interrupts the t1. When a thread calls Thread.sleep() or Thread.join() or Object.wait() it goes into eitherWAITING orTIMED_WAITING state. When a thread is in one of these states and Thread.interrupt() is invoked on that thread object, the built-in interrupt handler kicks in, does some stuff, and throws the InterruptedException which we have to catch. So in our program, when the main thread calls t1.interrupt() and t1 is in TIMED_WAITINGstate(since it is intermittently calling Thread.sleep()), the built-in interrupt handlers kicks in and raises the InterruptedException. The catch block, at line 11, then breaks from the loop and completes the thread. This is what we mean by stopping the thread gracefully without calling Thread.stop(). In fact, we are not exactly stopping the thread but we are taking the thread to its completion. Here is the output of the above program.

Thread-0: I am doing work . . . . .
Thread-0: I have been Interrupted!!
End of the thread: Thread-0!
End of the thread: main!

But, I would suggest you run the program on your machines once to know the behavior exactly. We missed a few important points here about the interrupts — The Interrupt Status Flag

## The Interrupt Status Flag

The interrupt mechanism is implemented using an internal flag known as the *interrupt status*. When we invoke t1.interrupt(), it sets the interrupt status flag. This can be checked using t1.isInterrupted(). There is another static method Thread.interrupted() which also returns the boolean value stating whether the thread is interrupted or not. But the sole purpose of this static method is to clear the interrupt status flag.

People generally get confused between these two methods. So the ***instance*** method isInterrupted() is to check whether the interrupt status flag is set or not (In other words, to check whether a thread is interrupted or not) and the static method interrupted() is to clear the flag.

*Thread.isInterrupted() is an instance method to check whether the thread is interrupted or not.*

*Thread.interrupted() is a static method which when invoked clears the interrupt status flag of the current running thread.*

Now let’s have a look at the second way of handling the interrupts. What if we don’t call the methods that throw InterruptedException in our programs. Let us look at the below code.

```java
public class StoppingThreadWithInterrupt
extends Thread {


    public void run() {
        System.out.print(Thread.currentThread().getName() + ": I am doing work ");
        while (!Thread.currentThread().isInterrupted()) {
            System.out.print(". ");
        }
        System.out.println(Thread.currentThread().getName() + ": I have been interrupted!!");
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }


    public static void main(String[] args) throws InterruptedException {
        Thread t
= new StoppingThreadWithInterrupt2();
        t1.start();
        Thread.sleep(10); // Let T
do some work.
        t1.interrupt(); // Interrupt T
Thread.sleep(1000); // Let T
comes to an End
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }


}
```

hosted with ❤ by 

Illustration 11.2 Stopping Threads Gracefully using Interrupts

The main change that you can observe between the above program and the previous one is, we just removed Thread.sleep(), the try-catch around it and the condition of the while loop checking whether the thread is interrupted or not. And here is the output of the above program.

Thread-0: I am doing work . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . Thread-0: I have been interrupted!!
End of the thread: Thread-0!
End of the thread: main!

In the above program, themain thread sleeps for 10 milliseconds and then interrupts the thread t1. When t1 finds that it is interrupted it comes out of the while loop because the condition fails.

Why can’t we use the same condition !Thread.currentThread.isInterrupted() and remove the break statement(at line 11 in Illustration 11.1) in the catch block. We can definitely use it. But there is a catch. Let’s try and modify the program in Illustration 11.1 and run it to understand it better.

```java
public class StoppingThreadWithInterrupt
extends Thread {


    public void run() {
        System.out.print(Thread.currentThread().getName() + ": I am doing work ");
        while (!Thread.currentThread().isInterrupted()) {
            System.out.print(". ");
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                System.out.println("\n" + Thread.currentThread().getName() + ": I have been Interrupted!!");
            }
        }
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }


    public static void main(String[] args) throws InterruptedException {
        Thread t
= new StoppingThreadWithInterrupt3();
        t1.start();
        Thread.sleep(5000);
        t1.interrupt();
        Thread.sleep(1000);
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }
    
}
```

hosted with ❤ by 

Illustration 11.3 Stopping the thread with interrupts

Run it in your system and check whether the thread program stops or not. In specific, check whether the thread t1 completes or not. Check the output below.

Thread-0: I am doing work . . . . .
Thread-0: I have been Interrupted!!
        . End of the thread: main!
        . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
. . . . . . . . 

The thing is, it won’t be complete. It runs infinitely. Why?

Well, the trick lies in built-in interrupt handlers — for all the methods that throw theInterruptedException. They clear the interrupt status flag.

****Very Important Note: The built-in interrupt handlers for the methods that throws InterruptedException will clear the interrupt status flag. So by the time the control comes into the catch block of InterruptedException the interrupt status flag will already have been cleared.*

So by the time the execution comes into the catch block, the interrupt status flag will already have been cleared. And the condition in the while loop will always be true. Because the isInterrupted() instance method just checks whether the flag is set or not.

So, what can be done here? Again, it depends on what we need and what our required behavior is. But in our case, we have two simple ways of fixing this.

First, We can simply set the interrupt status flag by invoking interrupt() instance method like this; Thread.currentThread().interrupt() in the catch block(ideally as a first statement in the catch block), so that, when the control comes to while loop condition it checks that the thread is interrupted and comes out of the loop.

Second, we can just simply use thebreak statement as a final statement in the catch block so that it breaks the while loop and comes out.

Either of the above two is fine. But I would upvote for the first approach. Because using break may not work if we nested loops as it only comes out of the inner loop. Hope you understand what I am trying to say.

So the below program is the complete program and a very safer way to stop the thread using interrupts.

```java


public class StoppingThreadWithInterrupt
extends Thread {


    public void run() {
        System.out.print(Thread.currentThread().getName() + ": I am doing work ");
        while (!Thread.currentThread().isInterrupted()) {
            System.out.print(". ");
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                System.out.println("\n" + Thread.currentThread().getName() + " is Interrupted? " + Thread.currentThread().isInterrupted());
                Thread.currentThread().interrupt(); // Sets the interrupt flag
                System.out.println(Thread.currentThread().getName() + ": I have been Interrupted!!");
            }
        }
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }


    public static void main(String[] args) throws InterruptedException {
        Thread t
= new StoppingThreadWithInterrupt4();
        t1.start();
        Thread.sleep(5000);
        t1.interrupt();
        Thread.sleep(1000);
        System.out.println("End of the thread: " + Thread.currentThread().getName() + "!");
    }
}
```

hosted with ❤ by 

Illustration 11.4 Stopping the thread — The safer way with interrupts

You can notice at line 11 of the above program we have printed the interrupt status flag just to prove to you that it is cleared by the built-in interrupt handler. You can check the below output which is highlighted in the ***bold-italic ***font. And at line 12 we used Thread.currentThread().interrupt() to set the interrupt status flag again as it has been cleared by the built-in interrupt handler.

Thread-0: I am doing work . . . . .
***Thread-0 is Interrupted? false***
Thread-0: I have been Interrupted!!
End of the thread: Thread-0!
End of the thread: main!

So far we have seen two ways of handling interrupts: The one with the InterruptedException and other without it. But what if we don’t provide any interrupt handler? Well, in Java, there are NO default interrupt handlers. When a thread, say T1, interrupts another thread, say T2, and if T2 doesn’t provide the interrupt handler, then nothing happens. The interrupts will simply be ignored.

## Summary

An *interrupt* is an indication to a thread that it should stop what it is doing and do something else.

It’s up to the programmer to decide exactly how a thread responds to an interrupt, but it is very common for the thread to terminate.

A thread sends an interrupt by invoking  on the Thread object for the thread to be interrupted.

For the interrupt mechanism to work correctly, the interrupted thread should implement an interrupt handler otherwise the interrupt will simply be ignored.

The methods that throw theInterruptedException have built-in interrupt handler. These built-in handlers simply clear the interrupt status flag and then throws the InterruptedException in some or the other way.