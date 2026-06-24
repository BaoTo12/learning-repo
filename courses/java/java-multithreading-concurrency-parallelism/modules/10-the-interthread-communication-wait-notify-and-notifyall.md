# The Interthread Communication — wait, notify and notifyall

In  we have seen various scenarios where threads can get blocked on each other. In this part, we will see how can threads voluntarily leave the monitor and go into the WAITING state and resume — wait(), notify() & notifyall().

**Purpose of wait and notify**: A common pattern in multi-threaded programming is to have some kind of communication between the threads. So the wait and notify are more of a communication mechanism. This mechanism allows one thread to communicate to another that a particular condition or event has occurred. And the wait & notify mechanism won’t tell us what is that particular condition/event. That is where the Shared Object comes into the picture.

The most important thing to remember is that, the wait & notify mechanism doesn’t replace the behavior ofsynchronized keyword as it cannot alone solve the race condition problem that the synchronized solves. In fact, the wait & notify mechanism must be used in conjunction with the synchronized to prevent a race condition.

_The wait & notify mechanism must be used in conjunction with synchronized._

To understand the wait & notify let's look at a single producer and a single consumer problem — which is simply known as the ***producer-consumer*** problem.

The producer-consumer problem is very simple. It can be better understood with a real-world example.

## Producer-Consumer Real World Scenario:

Imagine you went to a restaurant and order multiple food items: item-1, item-2, item-3, and etc.

Now while the food items are being cooked you will be given a plate that is empty and you wait until the food items come onto your plate.

When the first set of food items are served onto the plate you start eating them. While you are at eating the serving staff will wait for the plate to be empty (partially or fully). And when you complete(means the plate is again empty), you will again wait for the next set of food items.

The above scenario is the typical producer and consumer pattern.

The serving staff that serves the food is the producer, you are the consumer and the plate is the shared resource that is getting used by serving staff for producing the food items and by you for consuming the food items.

The following figure depicts this.
![alt text](../images/image7.png)
In the programming world, the shared object can be any data structure: usually, it is a circular queue(Ring Buffer) implemented either with an array or a linked list. In our case, we implemented the shared object as an array. In our simple application, we have three entities: Producer, Consumer, and Shared Object.

**Producer: **The thread that puts elements into the array. If the array is full (the plate is full) it waits for the consumer thread to consume until some space is left for the producer to produce the elements.

**Consumer: **The thread that takes the elements from the array. If the array is empty, the consumer thread waits for the producer to produce some elements.

**Shared Object:** The data structure that holds the data and is used by both producer and consumer. The shared object in our case is of fixed size. These kinds of data structures that are limited by size are called ***Bounded Data Structures*** or ***Bound Queues***. We look at some of the bounded queues in later parts.

The following java programs demonstrate the behavior of these entities.

```java
package org.vit.threads;


import java.util.ArrayList;
import java.util.List;


public class SharedQueue<E> {


    private List<E> buffer = new ArrayList<>(10);


    private static final int MAX_BUFFER_SIZE = 10;


    public synchronized void produce(E e) throws InterruptedException {
        while (buffer.size() == MAX_BUFFER_SIZE) {
            System.out.println(Thread.currentThread().getName() + " BUFFER IS FULL. Going into Wait State!");
            wait();
        }
        buffer.add(e);
        System.out.println(Thread.currentThread().getName() + " Produced Element: " + e);
        notify();
    }


    public synchronized E consume() throws InterruptedException {
        while (buffer.size() == 0) {
            System.out.println(Thread.currentThread().getName() + " BUFFER IS EMPTY. Going into Wait State!");
            wait();
        }
        E e = buffer.remove(0);
        System.out.println(Thread.currentThread().getName() + " Consumed Element: " + e);
        notify();
        return e;
    }


}
```

hosted with ❤ by 

```java
package org.vit.threads;


import java.util.Random;


public class SharedQueueDemo {


    private static final SharedQueue<Integer> sharedQueue = new SharedQueue<>();


    public static void main(String[] args) throws InterruptedException {
        Runnable produceTask = () -> {
            int i = 1;
            while (true) {
                try {
                    sharedQueue.produce((i++));
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        };


        Runnable consumerTask = () -> {
            while (true) {
                try {
                    sharedQueue.consume();
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        };


        Thread tProducer = new Thread(produceTask, "Producer");
        Thread tConsumer = new Thread(consumerTask, "Consumer");


        tProducer.start();
        tConsumer.start();


        tProducer.join();
        tConsumer.join();


    }
}
```

hosted with ❤ by 

We have two classes here. One is the SharedQueue which is a thread-safe shared object. It is backed by an ArrayList of size 10 and has two methods: produce() and consume().

**produce()** method blocks if the list size is 10 meaning there is NO extra slot to put the element.

**consume()** method blocks if the list size is 0 meaning there is no element to consume.

Both of these methods use the wait & notify mechanism and we have two threads defined SharedQueueDemo class:

One thread named Producer referred by tProducer object on line 31 of SharedQueueDemo infinitely uses produce() method to put the elements. And this thread waits if the shared queue size is full. In other words, the underlying ArrayList size becomes 10, the thread waits for the consumer to take the elements from the queue. And if there is an empty slot in the queue, the Producer thread simply adds the element to the queue and notify the other threads that are waiting on the SharedQueue object.

The other thread Consumer referred by tConsumer object on line 32 of SharedQueueDemo infinitely uses consume() method to take the elements from the queue. The Consumer thread will wait if there is no element in the queue. And if it finds some elements in the queue it removes these elements one by one from the beginning of the queue(see we used remove(0) at line 27 of SharedQueue)

Now that we understand the overall structure of these two classes, let’s now understand what exactly happens when we call wait & notify.

You might have observed that wait(at line 15 & 25 )and notify(at line 19 & 29 ) are called without using any object reference in SharedQueue class. That means it is equivalent to this.wait() and this.notify() . Here the objectthis is nothing but our SharedQueue object because that is what participated in the method invocation.

Now we know wait() and notify() are from SharedQueue object, this may raise another question that we haven’t defined any such methods in SharedQueue class, but where are they coming from then? Well, these are coming from Object class — The super class of every class that we define in Java. Of course, everyone knows this. If you are not sure, look at the java/lang/Object.java file in JDK source code and you can find wait, notify, and notifyAll being the Native methods. But why am I mentioning all this is to avoid the confusion about wait and notify. There are a couple of important points that I want to mention. Please read them thoroughly as these are very very important and no other book mentions them:

Apart from monitor(Otherwise known as Intrinsic Lock. Look at  and  for more information) every object in Java has a waitset associated with it. This is another object apart from the monitor. So now, things: amonitor and a waitset are what every object in Java has. You can think of monitor as a special object and waitset as a special data structure (maybe a set as the name suggests). These two(monitor and waitset) are solely maintained by JVM for every object in Java.

**\*When a thread calls wait() on an object there are two things that happen: First, the thread that is calling the wait method **leaves the monitor\*\* that it acquired on that object. Second, the thread that calls the wait is added to the waitset (of the object on which wait is called).

At this stage, the thread goes into the WAITING state, which means it now sits in the waitset. This is one scenario where a thread goes into WAITING state. The other scenario when a thread goes into WAITING state is when the other thread calls join() on this thread (If threadA calls anotherThread.join() then threadA goes into WAITING state).

\*\*\*When a thread calls notify(), the JVM looks at the waitset associated with the object on which notify is called and picks one of threads from that waitset and adds it to the runnable queue. We cannot guarantee which thread will get picked up. It all depends upon JVM Thread Scheduler.

Here, if there are multiple threads waiting in the waitset and we want to push all the threads into the runnable state then we call notifyAll() on that object. So notify() picks up a random thread and pushes it to runnable whereas nofityall() pushes all the threads to runnable. One thing to be noted here is that the job of notify() or notifyAll() is just to push the thread to the runnable queue only. Which thread first gets executed by the JVM(RUNNING state) is again unpredictable. It solely depends on the JVM Thread Scheduler. When the thread goes into RUNNING (or getting executed by JVM) it acquires the monitor again and continues from where it left off.

So here in our case, we have only two threads Producer and Consumer that can be pushed into the waitset of SharedQueue object. The below diagram better illustrates all the flow of wait & notify.
![alt text](../images/image8.png)

## Summary

wait & notify is a common mechanism in multithreaded programming to enable communication between the threads in which one thread communicates to another thread that a particular event is occurred.

wait & notify comes in handy in implementing ***producer-consumer*** patterns.

Besides the monitor, every object in Java has a waitset associated with it.

When a thread calls wait() on an object, that thread leaves the monitor(releases the lock) on that object and the thread is added into the waitset of that object.

The thread that calls the wait() is now put into WAITING state.

When another thread calls notify() on the same object, the JVM checks the waitset associated with that object and picks any thread and pushes it into the runnable queue.
