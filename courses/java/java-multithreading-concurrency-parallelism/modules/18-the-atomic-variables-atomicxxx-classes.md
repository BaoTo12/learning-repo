# The atomic variables — AtomicXXX classes

The java.util.concurrent.atomic package provides several atomic classes for different data types, such as AtomicInteger, AtomicLong, AtomicBoolean, and AtomicReference, to name a few.

All these *AtomicXXX* classes internally use CASing — The Compare-and-Swap, which we have already seen in . In this article, we will go a little deeper. So, let’s jump right in.

To start with, we will implement an atomic counter using AtomicInteger class. Look at the below AtomicCounter class which is used by multiple threads concurrently.

```java
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.IntStream;


public class AtomicCounter {


    private final AtomicInteger counter = new AtomicInteger();


    public void increment() {
        counter.getAndIncrement(); // Performs CAS Internally
    }


    public int get() {
        return counter.get();
    }


    public static void main(String[] args) throws InterruptedException {
        AtomicCounter atomicCounter = new AtomicCounter();


        Thread t
= new Thread(incrementLambda(atomicCounter, 1000));
        Thread t
= new Thread(incrementLambda(atomicCounter, 1000));


        t1.start();
        t2.start();


        t1.join();
        t2.join();


        System.out.println("Counter now is: " + atomicCounter.get());
    }


    private static Runnable incrementLambda(AtomicCounter atomicCounter, int range) {
        return () -> IntStream.rangeClosed(1, range)
                .forEach(i -> atomicCounter.increment());
    }


}
```

hosted with ❤ by 

Illustration 18.1 AtomicCounter class

The main thing in the AtomicCounter class that is of our interest is counter.getAndIncrement() at line 9. This method internally calls the getAndAddInt() on an object of type sun.misc.Unsafe class. This is the story till Java 8. From Java 9 this has been changed to jdk.internal.misc.Unsafe. There are important reasons for this which are not of our concern for now. But there will be a separate article for it.

The Unsafe class is a collection of methods for performing low-level, unsafe operations. So in our case, Unsafe.getAndAddInt() method is what actually performs the low-level CAS operation. All the *AtomicXXX* classes(in fact many of the classes in java.util.concurrent package) internally uses this Unsafe class.

This method performs three steps and the final operation is actually the CAS operation.

The actual value stored in the counter variable is copied to a temporary variable which is known to be the *old value*.

The temporary variable is incremented which is to be the new value.

***CAS: ***Compare the *old value *with the original value. If it is unchanged, then swap the old value for the new value. Otherwise, repeat the process from Step 1.

The most important thing here to be noted is, the last operation is the atomic operation. The underlying low-level code ensures this to be atomic.

Now that we understand CAS, let’s look at the source code of Unsafe.getAndAddInt() method which is copy-pasted here below just as a reference of what it exactly does.

```java
@HotSpotIntrinsicCandidate
public final int getAndAddInt(Object o, long offset, int delta) {
    int v;
    do {
        v = **getIntVolatile**(o, offset);
    } while (!**weakCompareAndSetInt**(o, offset, v, v + delta));
    return v;
}
To understand this better we need to understand the parameters o and offset.
```

**o** : refers to the object on the heap. In our case, this is our AtomicInteger object.

**offset**: Offset of the field that is in the object specified by o. If you look at AtomicInteger class source code you will see something like this.

```java
private static final long ***VALUE**** *= *U*.**objectFieldOffset**(AtomicInteger.class, "value");
```

We will have a clear understanding of this in the next article. But for now, understand that offset refers to the field named value in the AtomicInteger class.

getIntVolatile() gets the volatile variable from the specified offset, which is the value of the filed “value" in AtomcInteger class.

weakCompareAndSetInt() internally calls compareAndSetInt() which compares the copied value v with the current value at the offset and if both are equal, updates the value at the offset with v + delta.

v + delta in our case is v + 1 since this increment operation.

The following pseudo-code simplifies the above code snippet to understand it better.

```java
public final int getAndIncrement() {
    for (;;) {
        int current = get();
        int next = current + 1; 
        if (Unsafe.**compareAndSet**(current, next))
            return current;
    }
}
```

The *AtomicXXX* classes can be better understood if Unsafe class is understood. So the next article is dedicated to Unsafe.