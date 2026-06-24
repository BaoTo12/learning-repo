# Creation and Running a Thread

We have already mentioned in part-1 that a thread is an independent set of instructions that has its own private state. Every Java application has at least one thread named “***main***” without ourselves creating it. But what does it exactly mean when we say a Java Thread.

Well, a Java Thread is just an instance of a Java Class named Thread.

A thread in Java is just another object of class Thread. This class offers methods to configure and operate on it. A static native method named currentThread returns the object of the Thread that is currently running.

In the below code snippet* *Thread.currentThread() will return the object of currently running java thread.

```java
Thread currentThread = Thread.currentThread();
System.out.println("Current Thread is: " + currentThread.getName());
```

When we run these two lines, we will get the output as:

Output: Current Thread is: main

So from the above output, we can see that the name of the thread is ***main ***which gets created by JVM without our intervention.

## Creating our own Threads

Creating a thread in java is as simple as creating object of the class ***Thread*** and calling ***start() ***on that object.

There are two ways how we can create a Thread in java.

Instantiating Thread class with a Runnable object

Subclassing Thread class

## 1. Instantiating Thread Class with a Runnable Object

Runnable is an interface in java that has a single abstract method named run(). The concrete subclass that implements this interface will provide the java instructions to be executed as part of the thread.

We then have to create a Thread object and provide this Runnable object as a constructor argument.

The below program demonstrates this approach.

Here, from line 11 to 16, the Greeter class provides the implementation of Runnable interface. At line 5 we created the object greeter of this Runnable class and created a Thread object by passing the greeter object as a constructor argument. And finally we called start() method on the thread object.

The start() method in Thread class creates a native thread from which it invokes the run() method overridden in our Greeter runnable class.

Running this program will give us the below output.

Hello! From thread: Thread-0

Here thread-0 is the name of the thread that we created. Thread class assigns a name if none provided. A thread name created by thread is monotonically increasing. If we created another thread it would set the thread name as thread-1. This happens inside Thread constructor. If we don’t want it to create the name, we have to provide the name to Thread constructor. Here is the java source code snippet of Thread.java

```java
public class Thread implements Runnable {
    private volatile String name;
  
    /* What will be run. */
    private Runnable target;
    /* For autonumbering anonymous threads. */
    private static int threadInitNumber;
    private static synchronized int nextThreadNum() {
        return threadInitNumber++;
    }


        
    public Thread(Runnable target) {
        this(null, target, "Thread-" + nextThreadNum(), 0);
    }


}
```

## 2. Subclassing Thread Class

As you can see the source code of Thread.java that the Thread class itself implements Runnable interface, we can directly subclass Thread and override run() method as illustrated below.

```java
package org.vit.threads;


public class ThreadSubclassDemo {
    public static void main(String[] args) throws InterruptedException {
        Thread greeterThread = new Greeter();
        greeterThread.start();
    }
}


class Greeter extends Thread {
    public void run() {
        String name = Thread.currentThread().getName();
        System.out.println("Hello! From thread: " + name);
    }
}
```

This would give us the same output as above.

## Why should we call start(), why not directly run() method ?

Well, we can call run() method directly on the thread object. But it is as good as invoking a normal method. It won’t start any new thread of execution. It just simply executes the run method in the main thread.

Invoking the start() method internally calls a native method which is responsible for creating and invoking our run() method inside a new thread context.

```java
Thread greeterThread = new Greeter();
greeterThread.run();
```

This would give us below output:

Hello! From thread: main

This shows thatrun() method is executed within the main thread itself.

## Summary

There are two ways to create threads in Java: First, by implementing Runnable Interface. Second, by subclassing Thread.

The Thread constructor will create a name for a thread if none provided.

In order to start a new thread context, we need to invoke start() on the thread object reference.

Invoking run() method on thread object reference is as good as invoking a normal method that runs in a the same thread context.