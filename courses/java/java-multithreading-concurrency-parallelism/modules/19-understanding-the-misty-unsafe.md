# Understanding the misty Unsafe

***The name of the class Unsafe comes from the fact that it deals with. The sun.misc.Unsafe is really meant to be a low-level VM library interface designed to be used strictly within the JDK. It is not intended for external use and was not part of the supported Java public interface.***

***Most of the concurrent collection classes and the fork-join framework in java.util.concurrency are written with the help of Unsafe class. In fact, in Java 1.4, the reflections, serialization, and the NIO packages are re-written with Unsafe to improve the performance. java.math.BigInteger, java.math.BitDecimal are also rewritten with Unsafe in Java 7.***

***The sun.misc.Unsafe is really meant to be a low-level VM library interface designed to be used strictly in the JDK. It is not intended for external use.***

***Though the Unsafe is not intended for use outside the JDK, there are the libraries that uses Unsafe. But the real experts that know the low-level details can write better and safer programs with Unsafe. And below are a few such projects.***

***Cassandra******
Kafka******
Zookeeper******
LAMX Disruptor framework******
Akka******
Hibernate******
Hadoop******
HBase******
Ehcache******
Spring******
Mockito and many more.***

***There is a lot of buzz around the Unsafe class that from Java 9, it is gonna be deprecated or completely removed. If that is the case, what happens to the above projects if they have to be upgraded to later Java versions? Well, this is not only the case with Unsafe, but also all the internal APIs. But our concern is NOT to explore this now but just to understand what Unsafe can do. For more information on this please look at the ****** (JEP — JDK Enhancement Proposal).***

## The Unsafe class is capable of doing many things, such as:

## Accessing Hardware CPU feature — Compare And Swap

## Managing Native Memory

## Creating an object without running its constructor.

## Generate Classes at runtime.

## Faster Serialization

## Creating Arrays Bigger than the size of Integer.MAX_VALUE.

## Non-Blocking Concurrency

## In this article, we will look at several examples that illustrate the above points.

***Before we go into them let’s understand the Unsafe API. The API contains several methods. Some for manipulating the objects, some for classes, some for getting the low-level memory information, some for array manipulation and etc.***

## Getting the ‘Unsafe’ object

***Unsafe is a singleton class. And it has a static factory method to return us the Unsafe object. We can get the Unsafe object as below.***

## public class UnsafeDemo {
    private final Unsafe UNSAFE = Unsafe.getUnsafe();
}

***But do you think you can get the object so easily for a class that is capable of doing many low-level operations? No! When you run the above code, it throws the SecurityException as below.***

***Caused by: java.lang.SecurityException: Unsafe******
    at jdk.unsupported/sun.misc.Unsafe.getUnsafe(Unsafe.java:99)***

***Why is this? This is because there is a security check implemented in the sun.misc.Unsafe class. The below is the internal implementation of sun.misc.Unsafe.getUnsafe() method.***

```java
***public static Unsafe getUnsafe() {******
    Class<?> caller = Reflection.getCallerClass();******
    if (!VM.isSystemDomainLoader(caller.getClassLoader()))******
        throw new SecurityException("Unsafe");******
    return theUnsafe;******
}***
```

***What the above code ensures is that the class that the method Unsafe.getUnsafe() is getting called from must be loaded by the classloader that is in the system domain in which all the permissions are granted. But our UnsafeDemo class above is not loaded by the system domain class loader. Then how can we get the object of Unsafe. Well, there are two ways to get it.***

## Making our code trusted using -Xbootclasspath runtime flag.

## Using an easy hack that is all over stackoverflow.com(explained below).

## The Hack to get Unsafe object.

***We can use the below hack to get the Unsafe object. As we already specified the Unsafe is a singleton class and has the object already created with the reference variable theUnsafe and ready to eat. We can get that variable using Java reflection as below.***

```java
***Field f = Unsafe.class.getDeclaredField("theUnsafe");******
f.setAccessible(true);******
Unsafe unsafe = (Unsafe) f.get(null);***
```

***Now there is one small problem with the above code. In later versions of Java, if this variable name is changed to some other name let’s say theGreatUnsafe then our code breaks when we upgrade to that Java version. In that case, we need to modify our code with the new name, which I think is not really a big deal considering the advantages that this class offers.***

## Methods of “Unsafe”

***There are many methods that Unsafe provides. It will not look good if we specify all the methods here at once. Instead, we take a scenario to implement, discuss the methods that are useful for that scenario and implement an example with those methods.***

## 1. Managing Native Memory:

***We will implement a program in which we allocate four bytes from the native memory (outside the heap) and we set and get the values to and from that native memory. For this, we will have to look at three methods.***

***allocateMemory(long bytes): Allocates a new block of native memory, of the given size in bytes and returns the base address of the allocated memory. This class must have a corresponding freeMemory() call to release the allocated memory back to Operating System and it is the responsibility of the caller to invoke this method. Otherwise, this leads to native memory leakages.***

## putInt(long address, int value): Puts the integervalue at the specified memory location.

## getInt(long address): Get the integer value from the specified address.

## Below is the program that illustrates these methods.

```java
import sun.misc.Unsafe;


import java.lang.reflect.Field;


public class UnsafeInteger {


    private static final Unsafe UNSAFE = getUnsafe();
    private static final int BYTES = 4;
    private long address;


    private static Unsafe getUnsafe() {
        Field f = null;
        try {
            f = Unsafe.class.getDeclaredField("theUnsafe");
            f.setAccessible(true);
            return (Unsafe) f.get(null);
        } catch (NoSuchFieldException | IllegalAccessException e) {
            e.printStackTrace();
            throw new RuntimeException(e.getMessage(), e);
        }
    }


    public void init() {
        address = UNSAFE.allocateMemory(BYTES);
    }


    public void set(int value) {
        UNSAFE.putInt(address, value);
    }


    public int get() {
        return UNSAFE.getInt(address);
    }


    public void destroy() {
        UNSAFE.freeMemory(address);
    }


    public static void main(String[] args) {
        UnsafeInteger integer = new UnsafeInteger();
        integer.init(); // Allocate
bytes Native memory
        System.out.println("Before Set: " + integer.get());
        integer.set(1000);
        System.out.println("After Set: " + integer.get());
        integer.destroy(); // Free
bytes from Native memory
    }


}
```

## hosted with ❤ by

## Illustration 19.1 Managing off-heap memory with Unsafe

***Since this is native memory that we are dealing with we provided init() and destroy() methods explicitly to allocate and free the native memory. In line 42, it calls init() to allocate 4 bytes and in line 46 it invokes destroy() that releases these 4 bytes to Operating System. In line 43 we have printed the value before setting any value and this would print some garbage value and then we set the integer 1000. Here is the output of the program.***

## Before Set: 1615194544
After Set: 1000

## 2. Avoiding the Constructor Execution in Creating an Object

***To create an object without executing the constructor we need to use allocateInstance() method. This may be useful when a class doesn’t have any public constructor.***

```java
import sun.misc.Unsafe;


import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;


public class UnsafeClassInstantiation {


    static class Demo {
        private int value;


        public Demo() {
            System.out.println("Demo Constructor Called!!");
            value = 1;
        }


    }


    public static void main(String[] args) throws InstantiationException, IllegalAccessException, NoSuchMethodException, InvocationTargetException {
        Demo d
= new Demo();
        System.out.println("D
Value: " + d1.value);


        Demo d
= Demo.class.getDeclaredConstructor(null).newInstance();
        System.out.println("D
Value: " + d2.value);


        Demo d
= (Demo) getUnsafe().allocateInstance(Demo.class);
        System.out.println("D
Value: " + d3.value);
    }


    private static Unsafe getUnsafe() {
        Field f = null;
        try {
            f = Unsafe.class.getDeclaredField("theUnsafe");
            f.setAccessible(true);
            return (Unsafe) f.get(null);
        } catch (NoSuchFieldException | IllegalAccessException e) {
            e.printStackTrace();
            throw new RuntimeException(e.getMessage(), e);
        }
    }
}
```

## hosted with ❤ by

## Illustration 19.2 Bypassing Constructor Execution while Creating Object

## And here is the output of the program.

***Demo Constructor Called!!******
D1 Value: 1******
Demo Constructor Called!!******
D2 Value: 1******
D3 Value: 0***

***You can see from the above output, the constructor has not been invoked when we used Unsafe.allocateInstance(). Now, this is funny. Think of it once.***

## What happens to all the Singleton classes in the world?

***We can still create a second object for all those singletons with the above approach, right? That’s why people say that singleton is an anti-pattern and should be carefully implemented.***

## 3. Creating arrays in Native Memory

***This is similar to what we have seen in the first scenario. This is a little more complex example of what we have seen for managing off-heap memory. But why do we need to create arrays in native memory rather than in heap? There is another advantage of this. Have you ever created an array in Java that exceeds the size of Integer.MAX_VALUE? Because the array subscript only takes an int value. For example, look at the code snippet below this would result in a compilation error saying int is expected.***

***long bigValue = (long) Integer.MAX_VALUE + Integer.MAX_VALUE;******
long[] bigArray = new long[bigValue]; // Compilation Error!!***

***In these scenarios, we can use Unsafe as below to allocate bigger sizes from native memory. And of course, it is the programmers' responsibility to manage this memory in a safer manner. Note that we have used bigValue * 4 in the below example because we are allocating memory for integers. Each integer is of 4 bytes.***

```java
***long bigValue = (long) Integer.MAX_VALUE + Integer.MAX_VALUE;******
long arrBaseAddress = getUnsafe().allocateMemory(bigValue * 4);***
```

## The following code illustrates this feature.

```java
import sun.misc.Unsafe;


import java.lang.reflect.Field;


public class UnsafeHugeIntArray {


    private static final Unsafe UNSAFE = getUnsafe();
    private static final int BYTES = 4;
    private long ARR_BASE_ADDRESS;


    private static Unsafe getUnsafe() {
        Field f = null;
        try {
            f = Unsafe.class.getDeclaredField("theUnsafe");
            f.setAccessible(true);
            return (Unsafe) f.get(null);
        } catch (NoSuchFieldException | IllegalAccessException e) {
            e.printStackTrace();
            throw new RuntimeException(e.getMessage(), e);
        }
    }


    public void init(long size) {
        ARR_BASE_ADDRESS = UNSAFE.allocateMemory(size * BYTES);
    }


    public void destroy() {
        UNSAFE.freeMemory(ARR_BASE_ADDRESS);
    }


    public void insert(int value, long index) {
        UNSAFE.putInt(ARR_BASE_ADDRESS + index * BYTES, value);
    }


    public int get(long index) {
        return UNSAFE.getInt(ARR_BASE_ADDRESS + index * BYTES);
    }


    public static void main(String[] args) {
        UnsafeHugeIntArray hugeIntArray = new UnsafeHugeIntArray();
        long bigValue = (long) Integer.MAX_VALUE + 100;
        hugeIntArray.init(bigValue);


        // Set
values from
to
indexes
        for (int i = 0; i < 20; i++) {
            hugeIntArray.insert(i, i);
        }


        // Get
values from
to
indexes
        for (int i = 0; i < 20; i++) {
            System.out.print(hugeIntArray.get(i) + " ");
        }
        System.out.println();




        // Set and get the index larger than Integer.MAX_VALUE
        long someIndex = bigValue - 10;
        hugeIntArray.insert(100000, someIndex);
        System.out.println("Value at Index: " + someIndex + " is: " + hugeIntArray.get(someIndex));
        hugeIntArray.destroy();
    }
}
```

## hosted with ❤ by

## Illustration 19.3 Creating Big Arrays greater than size Integer.MAX_VALUE

***In line 24, the init() method allocates the memory. Remember the Unsafe.allocateMemory() takes the value as bytes. Since we are dealing with integers here, we needed to multiply it with BYTES which is with the value 4.***

***We have inserted the first 20 values and we read and printed them. Then we took some arbitrary index that is greater than Integer.MAX_VALUE. Then we used this index to put and set the values just to prove that we can do so.***

## 4. Getting the Field Offset Address Defined in a Class

***Understanding this section is very important as this is by far the most important and common usages of Unsafe class — Getting the field offset address in an object.***

***By now you might have understood that almost all the methods in the Unsafe class expect a long variable. This long variable can be of two types.***

***A base address of the allocated memory using allocateMemory(). This is what we have seen so far.***

***An offset address of a field inside an object. This we will look at in this example. Once we have a field address, we can set or get the values to and from it in the object that it is related to. Unsafe class has a method objectFieldOffset to get the offset address of a field defined in a class.***

***objectFieldOffset(Field f): Gives us the location of a given field in the storage allocation of its class.***

## For example, the below code snippet is from AtomicInteger class.

```java
***Field f = AtomicInteger.class.getDeclaredField("value");******
valueOffset = unsafe.objectFieldOffset(f);***
```

***Once we get this offset address we can use Unsafe.putInt() to set and Unsafe.getInt() to get the value from that offset. The below program better illustrates this.***

```java
import sun.misc.Unsafe;


import java.lang.reflect.Field;


public class UnsafeFiledOffsetDemo {


    private int unsafeValue;


    private static final Unsafe UNSAFE = getUnsafe();
    private static final long unsafeValueOffset;


    static {
        try {
            Field f = UnsafeFiledOffsetDemo.class.getDeclaredField("unsafeValue");
            unsafeValueOffset = UNSAFE.objectFieldOffset(f);
        } catch (Exception ex) {
            throw new Error(ex);
        }
    }


    private static Unsafe getUnsafe() {
        try {
            Field f = Unsafe.class.getDeclaredField("theUnsafe");
            f.setAccessible(true);
            return (Unsafe) f.get(null);
        } catch (NoSuchFieldException | IllegalAccessException e) {
            e.printStackTrace();
            throw new RuntimeException(e.getMessage(), e);
        }
    }


    public static void main(String[] args) {
        UnsafeFiledOffsetDemo obj = new UnsafeFiledOffsetDemo();
        System.out.println("Before Set: " + obj.unsafeValue);
        UNSAFE.putInt(obj, unsafeValueOffset, 1000);
        System.out.println("After Set: " + obj.unsafeValue);
    }
}
```

## hosted with ❤ by

## Illustration 19.4 Getting Field Offset Address

***This is rather a simple thing to understand. But look at line 35. This is another variant of putInt() method. This version of putInt() takes three arguments.***

***obj: The object in which the value needs to be set.******
offset: which is the field offset address.******
value: The value to be set in that offset address.***

***This variant of the putInt() method is what is used by AtomicInteger. And in the next section, we will implement our own non-blocking thread-safe integer.***

## 5. Concurrent Non-Blocking Thread-Safe Integer

***We have been telling about Compare-And-Swap and here is how to implement it using Unsafe. We can implement our own AtomicInteger with Unsafe class. For this, we need to know one important method that is compareAndSwapInt().***

***compareAndSwapInt(): Atomically updates the integer variable if it is currently holding the expected value.***

## Let’s now write our own thread-safe Integer class, and let’s call it as ConcurrentInteger.

```java
import sun.misc.Unsafe;


import java.lang.reflect.Field;


public class ConcurrentInteger {


    private volatile int val;


    private static final Unsafe UNSAFE = getUnsafe();


    private static final long valOffset;


    static {
        try {
            Field f = ConcurrentInteger.class.getDeclaredField("val");
            valOffset = UNSAFE.objectFieldOffset(f);
        } catch (Exception ex) {
            throw new Error(ex);
        }
    }


    private static Unsafe getUnsafe() {
        try {
            Field f = Unsafe.class.getDeclaredField("theUnsafe");
            f.setAccessible(true);
            return (Unsafe) f.get(null);
        } catch (NoSuchFieldException | IllegalAccessException e) {
            e.printStackTrace();
            throw new RuntimeException(e.getMessage(), e);
        }
    }


    public ConcurrentInteger() {
    }


    public ConcurrentInteger(int val) {
        this.val = val;
    }


    public final int get() {
        return val;
    }


    public int increment() {
        int expected, newVal;
        do {
            expected = UNSAFE.getIntVolatile(this, valOffset);
            newVal = expected + 1;
        } while (!UNSAFE.compareAndSwapInt(this, valOffset, expected, newVal));
        return expected;
    }


    public int decrement() {
        int expected, newVal;
        do {
            expected = UNSAFE.getIntVolatile(this, valOffset);
            newVal = expected - 1;
        } while (!UNSAFE.compareAndSwapInt(this, valOffset, expected, newVal));
        return expected;
    }


    public static void main(String[] args) throws InterruptedException {
        ConcurrentInteger uci = new ConcurrentInteger();


        Thread t
= new Thread(incrementTask(uci), "T1");
        Thread t
= new Thread(incrementTask(uci), "T2");
        Thread t
= new Thread(decrementTask(uci), "T3");


        t1.start();
        t2.start();
        t3.start();


        t1.join();
        t2.join();
        t3.join();


        System.out.println("Counter Value now is: " + uci.get());
    }


    private static Runnable incrementTask(final ConcurrentInteger uci) {
        return () -> {
            for (int i = 1; i <= 1000000; i++) {
                uci.increment();
            }
        };
    }


    private static Runnable decrementTask(final ConcurrentInteger uci) {
        return () -> {
            for (int i = 1; i <= 1000000; i++) {
                uci.decrement();
            }
        };
    }
    
}
```

## hosted with ❤ by

***Take a look at the increment() and decrement() methods above. Each method first copies the value into variable expected, adds value 1 to it and stores it into newVal, and performs CAS. The compareAndSetInt() method returns false if the expected and the original value at the specified filed offset address are not equal. And we will do these operations till the value is successfully updated. This is what is done by AtomicInteger internally.***

***And to test whether this is giving us thread-safety or not, we have created three threads: T1, T2, and T3, where T1 and T2 both increment the value 1 million times each, and T3 decrements it 1 million times. As a result, after all the thread complete their execution the final value of ConcurrentInteger should be 1000000. And here is the output.***

## Counter Value now is: 1000000

***There are lot more that we can with Unsafe. One can look at the documentation to understand more of what it offers.***