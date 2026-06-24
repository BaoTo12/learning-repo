# Synchronized and the depths of it — The monitors

_NOTE: Dear Readers, please follow the content till the end as I tried to explain the things at the bytecode level as this is the core of multithreading in Java. If this is understood most of the java multithreading will be a cake walk for the reader._

In  we have seen how we can make a class thread-safe using synchronized keyword. We will now have an in-depth understanding of it by looking at the bytecodes.

The first thing to understand is that when the synchronized method or block gets executed, a lock is acquired. We generally say the lock is acquired on a resource. But what is that resource? In Java, that resource is always an Object — A Java Object.

*In many books and articles, this lock is called an *Intrinsic Lock*, because the lock is acquired intrinsically without specifying (that the lock needs to be acquired). In the JVM vocabulary, it is called as the *Monitor*. Every object in Java has a monitor associated with it. In other words every Object in Java has a lock associated with it.*

So now the question again is on which object the lock is acquired? There are two answers to this question.

First, if we are using synchronized ***method***, the lock is always acquired on the object that is calling the synchronized method — this

Second, if we are using synchronized ***block***, we have to specify the object on which the lock needs to be acquired.

Now please allow me to specify one more statement which most books don’t specify. When we say the lock is acquired, what it exactly means is that the thread takes ownership of the monitor associated with it.

*NOTE: In JVM Language, the lock is called as the *Monitor*. The most important thing is that Every object in Java has a *Monitor* associated with it. This monitor is also called as Mutual Exclusion Lock.*

*Apart from the monitor, every object also has a waitset associated with it. We will look at waitsets in little more detail when we look at *wait, notify & notifyall*.*

Here in our example, we specified synchronized(this) { ++value; } , so the lock will be acquired on the object calling the method. But we can also specify our own object on which the lock is to be acquired as below.

```java
private final Object MY_OBJ = new Object();

public void increment() {
    synchronized (MY_OBJ) {
        ++value;
    }
}
With the above case, the lock is acquired on the object referred byMY_OBJ.
```

Now, we will have a look at the bytecodes of both variants: the method and theblock.

**Bytecode snapshot when using **synchronized** method:**

```java
Warning: File ./Counter.class does not contain class Counter
Compiled from "CounterDemo.java"
class org.vit.threads.Counter {
  org.vit.threads.Counter();
    Code:
       0: aload_
1: invokespecial #
// Method java/lang/Object."<init>":()V
       4: return


  public synchronized void increment();
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

There is not much difference between the synchronized version and the non-synchronized version of bytecodes except for the keyword synchronized got added to the method signature. Now let's look at the second version — the synchronized block.

**Bytecode snapshot when using **synchronized** block:**

```java
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
       2: astore_
3: monitorenter
       4: aload_
5: dup
       6: getfield      #
// Field value:I
       9: iconst_
10: iadd
      11: putfield      #
// Field value:I
      14: aload_
15: monitorexit
      16: goto
19: astore_
20: aload_
21: monitorexit
      22: aload_
23: athrow
      24: return
    Exception table:
       from    to  target type


any


any


  public int get();
    Code:
       0: aload_
1: getfield      #
// Field value:I
       4: ireturn
}
```

hosted with ❤ by 

Now observe the bytecodes of the increment method. There are two bytecodes that are of our interest.

**monitorenter** at line 13

**monitorexit**at line 21

The thread that executes monitorenter gains ownership of the monitor associated with the *object *that is specified byobjectref in the operand stack. (That is why we have two aload_0 instructions on lines 10 and 14. The extra aload_0 instruction at line 14 is to load the object mentioned in synchronized block, which is this and put it on the operand stack so that the monitorenter instruction can find the objectref on which the lock needs to be acquired). And this objectref is nothing but this in our case.

_The extra aload_0 instruction at line 14 is to load the object mentioned in synchronized block ( the this reference) and put it on the operand stack so that the monitorenter instruction can find the objectref on which the lock needs to be acquired._

_NOTE: Acquiring the lock is nothing but gaining the ownership of the monitor associated with the object._

There are three cases we need to understand on gaining ownership of the monitor.

**Another thread already gained ownership of the monitor:** If another thread already owns the monitor associated with objectref, the current thread waits until the object is unlocked, then tries again to gain the ownership. The thread is blocked and waiting for a monitor lock to enter a synchronized block or method. The thread is said to be in BLOCKED state until it gets the ownership of the monitor.

**Current thread already gained ownership of the monitor:** If the current thread already owns the monitor associated with objectref, it increments a counter in the monitor indicating the number of times this thread has entered the monitor. This feature is called the ***Reentrancy — The same thread reentering the monitor. ***So, the Intrinsic Lock is a reentrant Lock. We also have a class called ReentrantLock in java.util.concurrent.locks package that works the same way.

**No thread owns the monitor:** If the monitor associated with objectref is not owned by any thread, the current thread becomes the owner of the monitor, setting the entry count of this monitor to 1.

_If \***\*objectref\*\*** is null, \***\*monitorenter\*\*** throws a \***\*NullPointerException\*\***._

The thread that executes monitorexit must be the owner of the monitor associated with the instance referenced by objectref. When the thread executes monitorexit it decrements the entry count of the monitor associated with objectref.

If as a result, the value of the entry count is zero, the thread exits the monitor and is no longer its owner. Other threads that are blocking can now enter the monitor. Which thread can enter the monitor is in the hands of JVM now.

If *objectref* is null, *monitorexit* throws a NullPointerException.

If the thread that executes *monitorexit* is not the owner of the monitor associated with the instance referenced by *objectref*, *monitorexit* throws an IllegalMonitorStateException.

One or more monitorexit instructions may be used with a monitorenter instruction to implement a synchronized block.

The monitorenter and monitorexit instructions are not used in the implementation of synchronized methods, although they can be used to provide equivalent locking semantics. That’s why the bytecodes when using the synchronized method haven’t had much of a difference.
![alt text](../images/image5.png)

## Summary:

Every object in Java is a lock associated with it. This lock is also called an Intrinsic Lock or Monitor.

Acquiring the lock means gaining ownership of the monitor.

The thread entering into the synchronized block or synchronized method will try to gain ownership of the monitor of the object referred by objectref. For non-static synchronized methods this will always be the this object.

The Monitor or Lock or Intrinsic Lock is reentrant in nature, which means, a thread can acquire the lock that it has already acquired and it maintains the count of how many times the lock has been acquired by a specific thread.

The bytecode instructions betweenmonitorenter and monitorexit act as a guarded region (The critical section).

The monitorenter and monitorexit instructions are NOT used in the implementation of synchronized methods.
