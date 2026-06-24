# Introduction to non-blocking — Compare and Swap

We have seen the CopyOnWriteArrayList in the previous . In this part, we will look at ConcurrentHashMap which is yet another beast in terms of understanding what is happening behind the scenes. But before that, we need to understand what CAS(Compare-And-Swap) is. We will dedicate this article solely to *CASing*. In the next part, we will have an in-depth understanding of putVal() method which is commonly used by all the put variants: put, putIfAbsent, putAll and etc.

## Compare-And-Swap

compare-and-swap is a technique or a tool used in multithreading to provide non-blocking thread safety. So far what we have seen with synchronized and ReentrantLock, are the blocking mechanisms. This CAS technique is even implemented at the hardware level right into the machine’s Instruction Set. For example, in the Intel x-86, it is implemented as **CMPXCHG **(compare-and-exchange) instruction. All the modern multiprocessor architectures support CAS in their instruction set. It is the most popular primitive for implementing non-blocking concurrent collections. Most of the concurrent collections in Java use CAS in combination with minimal locking(_Lock Striping_) to achieve a higher degree of concurrency.

To understand how CAS works, consider our Counter scenario, where we have two threads T1 and T2 and both are trying to increment the value of the Counter object. We know that the increment operation is NOT atomic. It actually divides into three atomic operations: READ, INCREMENT, and WRITE. And it is at the WRITE operation the CAS comes into the picture.

Let's assume that the value of the counter is now 10, and below is the execution sequence of the threads.

T1 comes and does the *READ* and *INCREMENT* operations. So it has 11 in its local stack, but not yet written back to the memory location referenced by the counter variable.

Now T2 also same. It comes and reads the value as 10 and then increments it to 11 caches it in its local stack, but not yet written back to the memory location referenced by the counter variable.

Now T1 comes and performs the CAS operation. The CAS operation accepts three values: expectedValue, newValue, and MemoryAddress in which the value needs to be updated. In our case …
****\***** the **expectedValue** is 10 which T1 read and it expects the same value to be in the memory location — That means no other thread has updated it meanwhile.
****\***** the **newValue** is 11 which is after T1 incremented in its local stack but has not yet been written to the memory location.
****\***** the **MemoryAddress** is the location to be updated — In our case it is the counter variable.
Now when T1 performs CAS operation, it first checks whether the given expectedValue matches with the actual value from the memory location that it is updating. If both are the same, that means, no other thread modified the value. So it modifies the contents of that memory location to a new given value. All this is done as a single atomic operation. The underlying native code and then the further hardware instructions ensure this. In this case, assume that T1 has been successful in the CAS operation and as a result, the counter value has now become 11.

Now T2 comes from point-2, and performs the CAS operation.
**\*\*** ***Now T2 has the expectedValue as 10 which is the old value. Note that T2 has not yet seen the value updated by T1. It is still looking at the old cached value in its own stack.
*** T2 has the newValue as 11. When CAS operation compares the expectedValue and the actual value from the memory location of the variable, it finds that both are not the same. This indicates T2 that some other thread has changed the value. In our case, T1 has updated this value to 11 a while ago. This is where the CAS operation fails without updating the value. When this happens, T2 has to take the updated value and repeat the same operation again until it is successful. So now T2 reads the value 11, which is now the expectedValue, increments it to 12, which is the newValue to be updated, and performs the CAS. Eventually, the T2’s CAS operation will be successful, and as a result, the counter value will be updated to 12.

The CAS operation also tells us whether or not the operation has been successful. In high-level languages like Java, this returns a boolean value indicating the success or failure of the operation: true means success, and false means failure. Remember, it is the programmer's responsibility to continue retrying the CAS operation in a loop until successful as the underlying instruction doesn’t ensure that the operation will be successful. It only gives us the result: true or false. In case of false the program needs to retry the CAS operation.

JVM doesn’t have any byte code to perform the CAS. It relies on native code support. The sun.misc.Unsafe class provides API to perform CAS and also to do other atomic operations. We will see this in a separate article in depth. Stay Tuned. But just to give you a glimpse of it, here is a simple API of CAS from sun.misc.Unsafe.

```java
public final boolean compareAndSwapInt(Object o, long offset,
                                       int expected,
                                       int x) {
    return *theInternalUnsafe*.compareAndSetInt(
                                 o, offset, expected, x);
}
```

![alt text](../images/image12.png)
The below pseudo-code shows how to implement the thread-safety with CAS. In fact, this is what all AtomicXXX classes are doing. We will look at them in-depth in later parts. The important thing to remember is that the variables that are participating in CAS must be volatile. In the below example, counter.getValue() should always give the latest updated value. It should be a volatile variable so that value is directly read from memory location rather than from the cache.

```java
public int increment() {
    do {
        int expectedValue = counter.getValue();*
        *int newValue = expectedValue + 1;
        boolean success = CAS(expectedValue, newValue, counter);
    } while(!success)
    return newValue;
}
```

If you just look carefully at what we said till now, nowhere did we mention the locks or monitors to provide the thread safety. So, the CAS, in a way, lets us implement the *lock-free* algorithms. You can see in the above pseudo-code, we haven’t used locks anywhere. This is called *non-blocking*. We can implement *non-blocking* or *lock-free* algorithms using CAS. The AtomicInteger, AtomicLong, AtomicDouble, and all AtomicXXX classes use this feature extensively(more in-depth coverage in later parts). The ConcurrentHashMap also uses this strategy to implement non-blocking put operations which we will discuss in the next part.

## Summary

compare-and-swap is a technique used in multithreading to implement non-blocking thread safety.

The modern multiprocessor architectures support CAS in their instruction set.

Most of the concurrent collections in Java use CAS in combination with minimal locking(_Lock Striping_) to achieve a higher degree of concurrency.

The CAS operation is an atomic operation. This atomicity is ensured by the native code and further down, the hardware instructions.

The CAS operation accepts three values: expectedValue, newValue, and MemoryAddress in which the value needs to be updated.

CAS operation first checks whether the expectedValue is equal to the original value in the specified MemoryAddress. If yes, it updates the value at the MemeoryAddress with the specified newValue and returns with boolean true. If not, it just simply returns false without updating the value.

It is the programmer’s responsibility to continue retrying the CAS operation in a loop until successful as the underlying instruction doesn’t ensure that the operation will be successful.

CAS lets us implement *lock-free* or *non-blocking* algorithms. The AtomicInteger, AtomicLong, AtomicDouble, and all AtomicXXX classes use this feature extensively. The ConcurrentHashMap also uses this strategy to implement non-blocking put operations.
