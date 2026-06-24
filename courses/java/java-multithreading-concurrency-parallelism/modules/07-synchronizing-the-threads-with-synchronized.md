# Synchronizing the Threads with synchronized

_NOTE: Please follow the content till the end as I tried to explain the things at the bytecode level._

In  we have seen the methods join, sleep, and yield with their behaviors. Now it is time to look at how the threads can be synchronized to access the shared data. In Java, shared data simply means another object that contains some data for the threads to function: For example the instance of type Counter.

But in the first place why there is a need for synchronizing the threads to access the object - the Shared Data.

Let’s imagine a common scenario of displaying the number of hits of a particular website on the UI. The backend servers need to maintain a counter that keeps track of the number of hits. And for every request, there is a request handler that runs in a specific thread that needs to access the counter object and call increment on it.

Let's look at the below example where we have two threads, accessing the same Counter object. Each thread is incrementing the counter 100000 times. At the end of both threads completing their execution, the expected output should be 200000 because each thread performs 100000 increments.

```java
package org.vit.threads;


class Counter {


    private int value;


    public void increment() {
        ++value;
    }


    public int get() {
        return value;
    }


}


public class CounterDemo {


    public static void main(String[] args) throws InterruptedException {
        Counter counter = new Counter();


        Runnable incrementTask = () -> {
            for (int i = 0; i < 100000; i++) {
                counter.increment();
            }
        };


        Thread t
= new Thread(incrementTask, "T1");
        Thread t
= new Thread(incrementTask, "T2");


        long start = System.nanoTime();
        t1.start();
        t2.start();


        t1.join(); // Wait here till T
completes
        t2.join(); // Wait here till T
completes
        long end = System.nanoTime();

        String timeTaken = String.format("%.2f", (end - start) / 1000000.0);
        System.out.println("Final Counter Value: " + counter.get() + " Time Taken: " + timeTaken + " millis");
    }


}
```

hosted with ❤ by 

The Counter object without thread synchronization

In the above code, we have created a task incrementTask (line 22–26) that increments the counter 100000 times. And we have created two threads each performing this incrementTask. So at the end of the program, we should expect the final value of the counter to be 200000. But run it multiple times and see the output. I have run it thrice and below are the outputs.

**RUN #1**Final Counter Value: 108815 Time Taken: 9.63 millis

**RUN #2** Final Counter Value: 174793 Time Taken: 3.13 millis

**RUN #3** Final Counter Value: 138996 Time Taken: 8.55 millis

You can see I have got three different results and none of the outputs has shown me the result of 200000. The place where things go sideways is the increment() method of the Counter class at line 8. This code region (In our example this is a single statement. In most of the problems it is multiple statements) is what we refer to as a region that leads to Race Condition. Though the statement ++value appears to be a single statement in the Java file, when the code is compiled, the single statement turns out to be multiple bytecodes. We can clearly see this if we can extract the bytecode of the counter class. Here is how you can do this.

Run this command against the Counter.class file.

_javap -c Counter.class_

And you will get the following output.

```java
Compiled from "CounterDemo.java"
class org.vit.threads.Counter {
  org.vit.threads.Counter();
    Code:
       0: aload_
1: invokespecial #
// Method java/lang/Object."<init>":()V
       4: return


  public void increment();
    Code:
       0: aload_
1: dup
       2: getfield      #
// Field value:I
       5: iconst_
6: iadd
       7: putfield      #
// Field value:I
      10: return


  public int get();
    Code:
       0: aload_
1: getfield      #
// Field value:I
       4: ireturn
}
```

hosted with ❤ by 

The above is the byte code of the class Counter. Look at the public void increment();. The snippet of interest is from lines 11 to 16. There are 6 bytecode instructions that represent the method body which contains the single java statement++value. Let's look at these byte codes.

**aload_0**Load reference from local variable. The _0 is the index of the local variable array in the current frame of the stack (of the current running thread).

**dup** duplicate the value onto the operand stack.

**getfield** Fetch field from the object ( which is probably this).

**iconst_1** Push the int constant with the value 1 to operand stack.

**iadd** Pop two int values from the operand stack and add them.

**putfield **Set field in the object (this).

For ease of our explanation, let's classify the above byte codes into three operations.

**Read Operation**: aload_0, dup, getfield

**increment Operation:** iconst_1, iadd

**Write Operation**: putfield

So in a sense, the single java statement **++value** is converted into 3 operations when it goes to JVM for execution. This is where things go out of order in the sense of multithreading.

_There are a lot of optimizations done by the JIT and JVM at run time like reordering of instructions. We will look at this part in later sections. But for now, we will only look at the concept of out of ordering from the perspective of multithreading._

The thing to remember is the single java statement ++value becomes three operations when it arrives at JVM for execution. And these three operations are getting executed by two threads: T1 and T2, interleaving the JVM randomly at any of these three operations. We will look at the two scenarios one the happy scenario and the other with some inconsistency.

## The Happy Scenario

In the happy path, what happens is, all the three operations are executed by T1 sequentially without getting disturbed by any other thread. Then T2 comes and executes the three operations in a sequence undisturbed by the other thread. Let’s say the current value of the variable is 10. The expectation is that when T1 and T2 complete their operations the counter value must be 12.

## T1 & T2 Execution Sequence in the Happy Path:

T1 reads the value which is 10

T1 Increments it 11 (Still in its local stack)

T1 Writes back to the value 11

T2 now reads the value which is 11 because T1 has written the value that is incremented.

T2 Increments it 12 (Still in its local stack)

T2 Writes back the value which is 12 in the counter object.

This is the happy path. Now let's look at the scenario where it leads to inconsistent results. Now assume the value of the counter is 12 and when the T1 & T2 complete their operations the final counter value should be 14.

## T1 & T2 Execution Sequence in the Inconsistent Scenario:

T1 reads the value which is 12

T1 Increments it 13 (Still in its local stack) and T2 pre-empted.

T2 now reads the value which is 12 because T1 has NOT written the value that it incremented.

T2 Increments it 13 (Still in its local stack) and T1 pre-empted.

T1 writes back the value 13 because that is the result that T1 has in its own stack. And T2 pre-empted.

T2 writes back the value 13 because that is the result that T2 has in its own stack.

The final value is 13 but the expected is 14. This is the scenario that we have been specifying from the beginning to be out-of-order and leads to inconsistent results. The following diagram depicts both scenarios clearly.
![alt text](../images/image4.png)
Now I hope you understood the problem. Note that we are also aware that the happy path gives us consistent results. So there are kinds of solutions.

First, somehow instruct the JVM to run that the threads are always with the order mentioned in the happy path. There are again two ways to do this.

Using synchronized keyword

Using the class ReentrantLock in java.util.concurrent.locks library.

Second, Using AtomicXXX classes that use the Compare-And-Swap (CAS) constructs.

We will park ReentrantLocks and Atomic Classes for later. Now, we will only look at synchronized keyword.

There are two ways of using the synchronized keyword.

First, to use it with methods in the method signature as below:

```java
public synchronized void increment() {
    ++value;
}
```

Second, to use a synchronized as a block as below:

```java
public void increment() {
    synchronized (this) {
        ++value;
    }
}
```

Out of these two, the latter(synchronized block) provides the flexibility of guarding the code at a finer granular level. We can put whatever statements that we think to result in inconsistency in the synchronized block rather than making the whole method synchronized.

This is only the beginning. In a later chapter, we will deep dive into synchronized keyword where we look at the byte codes and understand what is happening in JVM.

## Summary:

In JVM, the order of the threads is not guaranteed. It all depends on JVM’s Thread Scheduler.

When there are two or more threads accessing the shared data, it may lead to inconsistent results because of the fact that these threads race on each other to execute a particular block of code. This leads to a race condition.

There are two ways we can instruct JVM to execute a particular block of code without interference: synchronized and ReentrantLock

```java
synchronized can be used with methods and code blocks. It provides more flexibility with the block of code as we can deal with it at a finer granular level.
```
