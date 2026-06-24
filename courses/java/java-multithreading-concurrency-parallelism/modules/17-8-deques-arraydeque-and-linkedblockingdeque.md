# Deques — ArrayDeque, and LinkedBlockingDeque

![alt text](../images/image21.png)
Deques (pronounced as *Deck* in short) are double-ended queues that allow efficient insertion and removal from both the head and the tail. The LinkedBlockingDeque is the thread-safe implementation of Deque that the Java Concurrency Framework provides. The other implementation which is NOT thread-safe is ArrayDeque. In this article, we will look at LinkedBlockingDeque.

As the name suggests, LinkedBlockingDeque is a blocking deque of linked nodes. And it is optionally bounded which means it depends on the programmer’s choice. It contains methods that support insertion and removal from either end.

LinkedBlockingDeque is very simple in terms of understanding what is happening inside. This collection internally maintains a Doubly-Linked List protected by a single lock. This single lock is an instance of ReentrantLock. Since it is a blocking collection it uses Condition objects on that ReentrantLock to manage the blocking of threads.

But, we already have the collections that are blocking and have the linked nodes internally. Then why the LinkedBlockingDeque? or the question should rather be why* Deques*? Well, *Deques* are for a specific purpose known as *Work Stealing*. As the blocking queues provide the support for implementing the *Producer-Consumer* pattern, the deques are for implementing *Work Stealing*. There is no use in this article if I don’t specify what is *Work Stealing*. And whenever we talk about deques we should talk about *Work Stealing*.

_Just as blocking queues are there to implement the Producer-Consumer pattern, deques are there to implement a related pattern called Work Stealing._

## Work Stealing

In the *Producer-Consumer* pattern, we have one shared work queue for all consumers.

In the *Work Stealing* pattern, every consumer has its own deque. The consumer can be a Java worker thread. If a worker reads all of the messages from its deque, it can take the messages from the *tail* of another worker's deque. But, why does it have to do it in the first place? Well, This is for efficient usage of all the workers. The workers, once they find their own deque is empty, instead of being idle they take elements from the tail of other workers’ deque so that their idle time is reduced. This is really useful when the deque contains objects representing Events or Tasks. Let’s assume that we are dealing with objects that represent the tasks to be performed where each task represents some amount of work to be done. In this case, all the workers will be used efficiently and all the tasks will be dispatched to respective task handlers efficiently without a delay as no worker is idle.

Work Stealing can be more scalable than a traditional producer-consumer pattern because the workers don’t have to block as each worker has their own deque and most of the time they access only their own deque, thereby, reducing contention.

When a worker has to access another’s queue, it does so from the tail rather than the head, further reducing contention. This means taking the elements from the tail of the deque further reduces the contention. How? Let’s say we have CA and CB both have deques DA and DB. And when CA processes the elements from its own deque DA it only takes the elements from the head of the deque. And CB when it completes the elements from its own deque DB, and tries to steal elements from DA it takes it from the tail of the queue. So the takes from the deque DA by consumers CA and CB happen from head and tail respectively, they don’t have to block on each other. The same phenomena we have seen in  with *ConcurrentLinkedQueue*’s *Michael Scott* algorithm.

Work Stealing is best suited for the scenarios in which the consumers are also the producers. All the *Fork-Join* framework is based on this fact. This is a very important point to understand. When a worker is performing some task likely results in performing another subtask. For example, a web crawler usually results in the identification of new pages to be crawled. In this scenario, when the worker thread identifies a new subtask, it pushes this task at the end of its own deque so that it can be eventually be processed by it or other workers.

So there are two main points that we explained above with work-stealing.

_Workers, when identifying a new task, push it to the end of its own deque._

_Workers, when seeing that their own deque is empty, take the elements from the tail of other workers’ deque._

Note that the work-stealing is NOT right built into LinkedBlockingDeque. The only point of the above story of Work Stealing is that Deques are the enablers of work-stealing. Using Deques the programmers still need to design the framework of workers in such a way explained above. And the Fork-Join Pool is such a framework.

That’s all the story of Work Stealing. Now coming to LinkedBlockingDeque, it can be worked as a blocking queue to implement a producer-consumer pattern. It just simply works as a Queue but the *insert* and *remove* can happen from either end.

The below simple program illustrates the methods and their operations.

```java
public static void main(String[] args) {
    **Deque**<Integer> ld = new **LinkedBlockingDeque**<Integer>();
    ld.**add**(101);
    ld.**addFirst**(100);
    ld.**addLast**(102);

    System.*out*.println("Queue Status Now: " + ld);
    System.*out*.println("Removed First: " + ld.**removeFirst**() + ", Queue Status Now: " + ld);
    System.*out*.println("Removed Last: " + ld.**removeLast**() + ", Queue Status Now: " + ld);
}
Below is the output which is self-explanatory.
```

Queue Status Now: [100, 101, 102]
Removed First: 100, Queue Status Now: [101, 102]
Removed Last: 102, Queue Status Now: [101]

The methods add, addFirst, addLast also have other variations such as, offer, offerFirst, offerLast, put, putFirst, putLast.

And remove, removeFirst, removeLast have other variations such as, poll, pollFirst, pollLast, take, takeFirst, takeLast.

The put and take versions are the blocking operations. There are two other methods supported by the Deque interface as LinkedBlockingDeque is an implementation of Deque interface. Those are push and pop both insert and remove the elements from the beginning of the queue. Basically, these are there just to represent this Deque as a Stack.

That’s all above Deques. The most important thing to remember is the Deques are enablers of implementing work-stealing paradigms.

## Summary

A Deque is a double-ended queue that allows efficient insertion and removal from both the head and the tail.

Implementations include ArrayDeque and LinkedBlockingDeque.

Just as blocking queues are there to implement the *Producer-Consumer *pattern, deques are there to implement a related pattern called *Work Stealing*.

In the *Work Stealing* pattern, every worker has its own deque.

Workers, when seeing that their own deque is empty, take the elements from the tail of other workers’ deque.

Workers, when identifying a new task, push it to the end of its own deque.

The Deques are enablers for implementing work-stealing patterns.
