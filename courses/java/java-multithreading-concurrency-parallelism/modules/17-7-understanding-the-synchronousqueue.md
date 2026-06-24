# Understanding the SynchronousQueue

Ping-Pong The real-world analogy for **SynchrnousQueue**

So far we have seen commonly used concurrent collections. There is another special-purpose concurrent collection that we need to understand — The SynchronousQueue

SynchronousQueue is a little trickier to understand. But follow this article along. I am sure you will understand it better. In the end, we also have a real-world analogy for this.

The first thing is that it is a blocking queue in which every put operation is blocked until a corresponding take or poll operation is performed. In simple words, every insertion is blocked until a corresponding removal operation is performed. And every removal is blocked until the corresponding insertion is performed. That means, at any given point in time, there is either one or no element in the queue.

Let’s take the following code snippet.

```java
public static void main(String[] args) throws InterruptedException {
    SynchronousQueue<Integer> sq = new SynchronousQueue<>();
    sq.put(10);
    System.*out*.println("The element
is inserted");
}
```

When you run the above code you won’t get any output. Because sq.put() blocks the current thread until the element is removed by some other thread. The removal operation can either be sq.take() or sq.poll()

Now in the same way the sq.take() method blocks the current thread until insertion is performed by some other thread. The insertion operation can either be sq.put() or sq.offer(). So the below code snippet doesn’t output anything. It simply blocks at line 3.

```java
public static void main(String[] args) throws InterruptedException {
    SynchronousQueue<Integer> sq = new SynchronousQueue<>();
    sq.take();
    System.*out*.println("The element
is inserted");
}
```

Now let’s look at an example where the SynchronousQueue has put() and take() operations happen in sync with each other.

```java
import java.util.concurrent.SynchronousQueue;


public class SynchronousQueueDemo {


    public static void main(String[] args) throws InterruptedException {
        SynchronousQueue<Integer> sq = new SynchronousQueue<>();
        new Thread(() -> {
            try {
                Thread.sleep(200);
                sq.put(10);
                System.out.println("PUT : " + 10);


                Thread.sleep(200);
                sq.put(20);
                System.out.println("PUT : " + 20);


                Thread.sleep(200);
                sq.put(30);
                System.out.println("PUT : " + 30);


                Thread.sleep(200);
                sq.put(40);
                System.out.println("PUT : " + 40);


                Thread.sleep(200);
                sq.put(50);
                System.out.println("PUT : " + 50);
            } catch (InterruptedException ex) {
                ex.printStackTrace();
            }
        }, "PUTTER").start();


        System.out.println("TAKE: " + sq.take());
        System.out.println("TAKE: " + sq.take());
        System.out.println("TAKE: " + sq.take());
        System.out.println("TAKE: " + sq.take());
        System.out.println("TAKE: " + sq.take());


    }


}
```

hosted with ❤ by 

In the above program, we have two threads: The main thread, which is trying to take the elements from the SynchronousQueue (from lines 33 to 37) and the thread PUTTER trying to put the elements into the queue (from lines 7 to 31).

Below is the output.

PUT : 10
TAKE: 10
PUT : 20
TAKE: 20
PUT : 30
TAKE: 30
PUT : 40
TAKE: 40
PUT : 50
TAKE: 50

No matter how many times we run the program you will get the same output. Because both threads rendezvous with each other. The PUTTER blocks after the first put at line 10, until the main thread invokes take() at line 33.

And the take(), at line 34, blocks until the PUTTER invokes put() at line 14 and so on.

This is pretty interesting. Here we have just played with integers. Imagine you have a scenario where you need some java objects that carries some data, event, task, or any behavior from one thread to another. These are very well suited to implement the handoff designs.

Now there is another important thing to be understood here. put() and take() are the only blocking operations here. offer() and poll() are NOT blocking calls.

That means if we invoke offer(), and there is no other thread that is already waiting to capture it, then the element will go in the air. Repeating it in other words, if you use offer(), there must be another thread that should already be waiting for it to take. Otherwise, there is no use in using offer(). It simply returns false. Look at the below code snippet which outputs false.

```java
public static void main(String[] args) throws InterruptedException {
    SynchronousQueue<Integer> sq = new SynchronousQueue<>();
    System.*out*.println(**sq.offer(10)**);
}
```

The same applies to poll(). If we call poll(), the expectation is that there is another thread that should already have invoked put and waiting for it to consume. Otherwise poll() returns null. So the below program returns null.

```java
public static void main(String[] args) throws InterruptedException {
    SynchronousQueue<Integer> sq = new SynchronousQueue<>();
    System.*out*.println(**sq.poll()**);
}
```

So every non-blocking operation(offer/poll) that we do with SynchronousQueue should have a counter blocking operation(take/put) already performed and waiting. So mostly with SynchronousQueue, we will only be using put() and take().

And finally, the method peek() will always return null. The Java Doc specifies these points which are kind of funny but very important to understand.

*From **
1. You cannot peek at a synchronous queue because an element is only present when you try to remove it.**
2. You cannot insert an element (using any method) unless another thread is trying to remove it;**
3. You cannot iterate as there is nothing to iterate.*

So, basically, you cannot do much with SynchronousQueue. But this is a very powerful tool to implement something like rendezvous channels. If you are familiar with , this is very much similar to that.

So now that you understand what is a SynchronousQueue is, let me give you a real-world analogy here. You are very well aware of the game *Table Tennis, *right? Which is* *otherwise known as *PING-PONG*. There are two players and there is a table between them on which the game happens. You can think of the players as two threads and the table as SynchronousQueue. Imagine, how it feels like having only one player in the game. The ball that is hit by the player is never gonna come back if there is no opponent player that returns the ball. The same happens with SynchronousQueue’s put() or offer(). Hope you understood most of it. If not you can go through the points once again then you will understand it better.

## Summary

SynchronousQueue is a blocking queue and it doesn’t have capacity.

put() and take() are blocking calls.

The put() method blocks the current thread until the corresponding poll() or take() invoked.

The take() method blocks the current thread until the corresponding put() or offer() invoked.

offer() and poll() are NOT blocking calls.

offer() expects that there is already a thread waiting to take the element. If no thread waiting, offer() simply returns false indicating it hasn’t inserted the element.

poll() expects that there is already a thread that has put the element and waiting for it to be consumed. If no other thread waiting, it simply returns null.

SynchronousQueue is a best-suited tool to implement something like rendezvous channels. Or in other words, it is best suited for handing off an event or task, or information from one thread to another.

Working with SynchronousQueue is just like two threads are playing a ping-pong game.