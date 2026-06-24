# Volatiles

So far we have seen synchronization using locking with synchronized keyword which is a strong primitive for writing concurrent programs with less code in Java. Here in this part, we will see a weaker yet effective form of synchronization construct that Java provides — The **volatile** variables.

**NOTE: **Please read it till the End, if you want to understand volatiles in depth. Also please be careful with the similar terms ***synchronized*** and ***synchronization*** as they are here with different meanings.

**synchronized**: The Java keyword that provides the exclusive locking mechanism.

**synchronization**: A broader term that includes the use of locks(the synchronized keyword), volatile variables, explicit locks(Lock API), and atomic variables(AtomicInteger, AtomicLong etc).

The **volatile** variables are another form of synchronization but not as strong as the locks or monitors. The main aim of **volatile** is to provide an order of *Synchronization Actions*. The phrase Synchronization Action is not mine. It is actually from the **J**ava **L**anguage **S**pecification. The  section specifies various *Synchronization Actions*. But one synchronization order that is of interest, in this case, is about the volatile variables. And it goes as follows.

## Excerpt from JLS 17.4.4

A write to a volatile variable **v** *synchronizes-with* all subsequent reads of ***v*** by any thread (where “subsequent” is defined according to the synchronization order).

When I have first read this, it appeared to me as if I were reading a Sanskrit verse. Yea… the Java Language Specification is like a Sanskrit textbook — Hell lot of information is packed in a single statement. But don’t worry. Most of us (I am the first one to be included) won’t be able to understand it for the first time. But please follow it from here, you will be fine.

What it says is, *the volatile variable ensures that updates are propagated predictably to other threads*. In other words, the reader threads will always see the latest value updated by the writer thread.

What happens is, for the variables that are declared volatile, the JVM(or the Java Memory Model in specific) ensures that all threads see the most updated value for the variable. How? Well, the Java Compiler and JVM take a little extra care for those declared volatile.

First, the compiler, and runtime know that this variable is shared and that operations on it should not be reordered with other memory operations. In simple words, the Java Compiler and runtime do NOT do any extra optimizations like reordering of memory operations that appeared before the volatile variable.

Second, thevolatile variables are NOT cached in CPU core-specific registers or hardware caches(L1, L2, etc). They are written and read directly to and from the main memory.

It is because of these two things, it is ensured that the updates made by a thread(writer) will be seen by the other threads(readers). This is what people refer to as *visibility*. We have been specifying a single writer thread with volatile variables. But what if there are two writer threads? Well, volatile will not work if there are two writer threads. This is a very important point to be noted. Because with two writer threads, the variables, irrespective of being operated directly from memory or from CPU local caches, suffer from the same race condition. That is why we say it is a weaker form of synchronization and should only be used in specific scenarios, such as:

When we can ensure that only a single thread ever updates the value.

When atomicity is not needed but only visibility is needed. Because Locks provide both atomicity and visibility whereas volatile variables only provide visibility.

When we need to use flags to complete, stop, interrupt the threads, or for maintaining any other kinds of state information.

Locks provide both atomicity and visibility whereas volatile variables only provide visibility.

Using the volatile is more convenient than locking. It is more convenient in the sense that no locking is required so it cannot cause the running thread to block, making volatile variables a lighter-weight synchronization. But this advantage comes with a cost of performance. Operations on volatile variables are slightly more expensive than on nonvolatile variables because of the direct contact with main memory instead of using intermediate CPU level caches or registers. How can we prove this? Well, we can do a little experiment with a simple program of incrementing a variable one billion times.

```java
public class NonVolatileCounter {


    private static final int N_ITERATIONS = 10;
    private int value;


    public void increment() {
        value++;
    }


    public int get() {
        return value;
    }


    public static void main(String[] args) {
        NonVolatileCounter nvc = new NonVolatileCounter();
        double avgTime = 0;
        for (int k = 1; k <= N_ITERATIONS; k++) {
            long start = System.nanoTime();
            for (int i = 0; i < 1000_000_000; i++) {
                nvc.increment();
            }
            long end = System.nanoTime();
            avgTime += (end - start);
            System.out.printf("Iteration #%d:\t%.6f seconds%n", k, (end - start) / 1000000000.0);
        }
        avgTime = avgTime / N_ITERATIONS;
        avgTime /= 1000000000.0;
        System.out.printf("Average Time: %.6f", avgTime);
    }
}
```

This is a simple program with increment() method which is called one billion times. We have written a simple performance test with 10 iterations, each iteration increments the value one billion times, captures the time taken, and after all iterations, we took the average time from all these iterations and here is the output. The times are mentioned in **s.SSSSSS** format(seconds.microseconds)

Iteration #1: 0.048583 seconds

Iteration #1: 0.048583 seconds

Iteration #2: 0.013297 seconds

Iteration #3: 0.000000 seconds

Iteration #4: 0.000000 seconds

Iteration #5: 0.000000 seconds

Iteration #6: 0.000000 seconds

Iteration #7: 0.000000 seconds

Iteration #8: 0.000000 seconds

Iteration #9: 0.000000 seconds

Iteration #10: 0.000000 seconds

Average Time: 0.006188

In the above output, except for the first two iterations, all the rest took almost zero microseconds. The average time is 6188 microseconds. The zero microseconds might be because of the JIT warmup — as the JIT compiler optimizes the repeated instructions. But this is not our interest. Our main interest is to check the same program with volatile variable. Let’s just add volatile keyword at line 4 as shown below, run the program once and see the performance.
![alt text](../images/image9.png)
I have run it in my local and here are the numbers.

Iteration #1: 5.394576 seconds

Iteration #2: 7.370640 seconds

Iteration #3: 7.361875 seconds

Iteration #4: 7.363614 seconds

Iteration #5: 7.363856 seconds

Iteration #6: 7.368324 seconds

Iteration #7: 7.361354 seconds

Iteration #8: 7.386989 seconds

Iteration #9: 7.368896 seconds

Iteration #10: 7.371776 seconds

Average Time: 7.171190

You can see there is significant performance degradation. It took more than 7 seconds just because of adding the volatile keyword and note that it is still a single thread updating the value. We haven’t even introduced multiple threads here. The reason for performance degradation is that, with volatile variables, JVM directly talks to the main memory which is slow compared to CPU level registers or caches, and also JIT optimizations and the instruction reordering won’t come into the picture for volatile variables.

The lighter-weight synchronization with volatile comes with the cost of performance degradation.

We will now see another example of volatile — Stopping a thread gracefully.

```java
public class StoppingThreadWithVolatileDemo {


    private static volatile boolean stopIncrementing = false;


    public static void main(String[] args) throws InterruptedException {
        Thread tIncrementer = new Thread(() -> {
            System.out.println(Thread.currentThread() + ": Started incrementing ...");
            int i = 1;
            while (!stopIncrementing) {
                i++;
            }
            System.out.println(Thread.currentThread() + ": Completed with I = " + i + ".");
        }, "INCREMENTER");


        Thread tStopper = new Thread(() -> {
            stopIncrementing = true;
            System.out.println(Thread.currentThread() + ": Set the 'stopIncrementing' flag to 'true'.");
        }, "STOPPER");


        tIncrementer.start();


        Thread.sleep(500);
        tStopper.start();


        tIncrementer.join();
        tStopper.join();


        System.out.println(Thread.currentThread() + ": Completed!");
    }
}
```

The above program is self-explanatory. Not much of an explanation is needed. We created one thread INCREMENTER that increments a value continuously(lines 9–11) until the other thread named STOPPER sets the flag *stopIncrementing* to true at line 16. Whenever the STOPPER thread sets this flag to true the INCREMENTER thread sees(because of volatile variable) and exits from the while loop. Remove the volatile keyword in line 3 and check the behavior, in which case, the INCREMENTER thread never sees the value as true and never completes. Here is the output of the above program.

Thread[INCREMENTER,5,main]: Started incrementing ...

Thread[STOPPER,5,main]: Set the 'stopIncrementing' flag to 'true'.

Thread[INCREMENTER,5,main]: Completed with I = 732098147.

Thread[main,5,main]: Completed!

So now, there are two ways to stop a thread gracefully without using built-in stop() method.

With interrupts: which we have seen in .

With volatile variables: which we have seen in the above — *Illustration 13.2*.

That is the main story of volatile variables, that they provide a weaker form of non-blocking synchronization. But there is more to it. Remember we said that volatile provides only for *visibility* but not *atomicity*. This statement is made in comparison with the *locks*. But volatile variables ensure atomicity in a special situation. Let's look at it.

For any variable(volatile or non-volatile) that is of 32-bit size(a *word*) or less, all the reads and writes are implicitly atomic. That means the reads and writes of byte, short, char, int, float, and boolean are atomic. But the same is not the case with 64-bit non-volatile variables. The reads and writes of non-volatilelong and double are not atomic. This is because a single write to a non-volatile long or double value is treated as two separate writes: one to each 32-bit half. So for writing 64-bit value, JVM splits this into two 32-bit operations.

JVM guarantees the atomicity of a single read/write of the 32-bit value. But for two 32-bit operations, there is no guarantee of atomicity. This can result in a situation where a thread sees the first 32 bits of a 64-bit value from one write, and the second 32 bits from another write. That’s where volatile comes into the picture and provides the atomicity. So marking 64-bit variable, long or double, makes all the writes/reads atomic.

But, why JVM cannot perform a single 64-bit read/write in the first place? This is because of the *bytecodes* and L*ocal Variable Array*. This is some exotic content. So read it carefully.

Each *bytecode* in java is 8-bits(a byte). That is why the name ***byte-code***. So the maximum number of bytecodes that Java can have is 256(2^8 = 256). Of these 256, few are reserved for future use, not sure of the exact number, few are permanently reserved for JVM implementations to use, and the rest are for actual use. Each bytecode comprises two things: An ***opcode ***specifying the operation to be performed, and the ***operand(s). ***Operands can be any primitive type values that java provides or a reference, or a returnAddress. You know that in JVM we have a stack of frames and each frame has two main things that are of interest: *The Local Variable Array* and *Operand Stack*.

The thing with the *Local Variable Array *is, each element in this array can only hold a value of type boolean, byte, char, short, int, float, reference, or returnAddress. To hold the value of long or double it needs to use a pair of local variables. A value of type long or type double occupies two consecutive local variables.

All the above story is to arrive at this point that the value of type long or double needs two entries in the *Local Variable Array*. So it is because of the Local Variable Array the JVM can only write or read a value of type boolean, byte, char, short, int, float, reference, or returnAddress atomically in a single operation. When we make long or double values volatile, the Java Memory Model ensures the atomicity(I think it is ensured at the lower level — The system level). The same is the story with *Operand Stack*. Because the few bytecodes load the constants or values from the *Local Variable Array* onto the *Operand Stack*. Some bytecodes directly operate on the operand stack, such as **iadd** which takes two integer values from the top of the operand stack, adds them, and again pushes the result value onto the top of the operand stack.

As a bonus please read the below excerpt from JLS.

## Excerpt from JLS 17.7

Writes and reads of volatile long and double values are always atomic.

Some implementations may find it convenient to divide a single write action on a 64-bit long or double value into two write actions on adjacent 32-bit values. For efficiency's sake, this behavior is implementation-specific; an implementation of the Java Virtual Machine is free to perform writes to long and double values atomically or in two parts.

Implementations of the Java Virtual Machine are encouraged to avoid splitting 64-bit values where possible. Programmers are encouraged to declare shared 64-bit values as volatile or synchronize their programs correctly to avoid possible complications.

The last thing about volatile is, it\*\* **is a** \*\*compile-time error if a final variable is also declared volatile. Because volatile variables are meant for change. It doesn’t make any sense to make them as final.

That’s it about volatiles. I think we have covered enough and I hope you understand it thoroughly, if not, you may consider it reading again.

## Summary

```java
volatile variables provide a weaker form of non-blocking synchronization.
```

For the variables that are marked volatile, the compiler or JVM does not do any sort of optimizations like reordering with the memory operations, also the volatile variables are not cached in CPU registers or caches. There are directly operated on main-memory.

```java
volatile reads are slightly more expensive than nonvolatile reads on most current processor architectures.
volatile variable should be used only when we can ensure that only a single thread ever updates the value.
```

a) The read/write operations on the volatile or nonvolatile 32-bit values(byte, short, char, int, float, andboolean) are always atomic. b) Writes and reads of volatile long and double values are always atomic. c) Writes and reads of non-volatile long and double values are NOT atomic.

Marking the volatile variables final leads to a compile-time error.
