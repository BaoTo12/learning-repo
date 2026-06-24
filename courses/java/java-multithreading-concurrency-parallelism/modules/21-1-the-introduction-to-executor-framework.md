# The Introduction to Executor Framework

Have you ever wondered about people talking the ***ThreadPools***, ***ExecutorServices***, ***Callables***, ***Futures***, and ***SeprationOfConcerns***? And you want to know about these in-depth. Then this article is for you.

Java Concurrency Framework is a collection of micro-frameworks. One of them is the ***Executor*** Framework. The Java ***Executor*** Framework deals with distributing the tasks to the threads for their execution. But why there is a need for another framework just to run these tasks by the threads. Why can’t we simply create the threads with the Runnable or Callable representing the tasks? Well, there is the main disadvantage with it. So let’s just understand these disadvantages before delving into the ***Executor*** framework.

Suppose let’s say we want to have a simple web server that handles the requests from the clients over the socket. We can create a simple server as below.

```java
ServerSocket socket = new ServerSocket(6000);
while (true) {
Socket connection = socket.**accept**();
handleRequest(connection);
}
```

The above logic works in a sequential manner, in other words, it is ***Single-Threaded***. If two clients request at the same, they will get processed one after the other. While the server is handling a request, new connections must wait
until it ﬁnishes the current request and calls accept again. So whoever did not get the first chance will have to wait for the other request to be completed. While this logic is correct but this does not work well in production as it can handle only a single request at a time. This exhibits very poor performance and is not at all scalable. If there are 100 clients firing the requests, they keep on waiting for the other requests to be completed resulting in a very poor user experience. So that gives us where the problem lies. But let’s understand the problem furthermore.

In the above scenario, handling the client request involves many tasks that are a mix of both I/O and Computation. I/O can either be a ***Network I/O*** or ***Disk I/O***. In general, the following steps may be involved to handle a request from the client.

First, the server reads the data from the socket stream. This is a ***Network I/O****.*

Second, it processes the request. This involves computation and is CPU Bound. This step may also involve the ***Disk I/O***, in which it may be writing or reading to or from a database or file system.

Third, writes the response back into the socket stream. This is again ***Network I/O****.*

The Network I/O may be blocked sometimes due to the problems of high traffic or connectivity. In a single-threaded server, handling the I/O is the major problem. Because I/O causes blocking which not only delays the completion of the current task but also prevents pending requests from being executed at all. Imagine if this is the case, how the users feel. The users might think that the server is unavailable. Also, the CPU sits idle waiting for the I/O to be completed. So we need to make sure of two things here:

Using CPU power to the fullest extent.

Not blocking the subsequent requests.

This is where exactly we need threads. The above two points can be achieved by the use of threads. What we can do is, modify the logic to create and start a thread per every request. Every thread runs in isolation and doesn’t block the next request. Here is the modified logic.

```java
ServerSocket socket = new ServerSocket(6000);
while (true) {
final Socket connection = socket.accept(); // wait for client
**new Thread(()->***handleRequest*(connection)**)**.**start()**;
}
```

A single change in Line 4 makes a big difference. As the client sends a request we create and start a thread and then wait for the next request to arrive. What this is simply doing is dispatching the request to threads. So for each client connection, a new thread is created. This gives us better results in two main ways.

It enables the main thread to quickly dispatch the task to a thread and get ready to accept the new connections. The new requests are accepted irrespective of the completion of previous requests. This offers better responsiveness.

It enables the multiple requests to be served in parallel thereby improving the overall throughput especially when there is a lot of I/O involved.

But the thing that we need to be careful of here is the task handling logic — The handleRequest() method. It should be thread-safe and should not mess with the shared variables.

So far so good. But do you see the most important lurking problem with this piece of logic?

If you have spotted it, we are creating a hell lot of threads. This may work for a fewer or moderate number of requests. But under heavy load, this piece of logic goes haywire for various reasons:

**Heap Contamination:** Creating a thread object for every request — a lot of thread objects — may lead to Heap Contamination. If the GC daemon is not able to collect the objects as fast as the creation rate, it may lead to OutOfMemoryError.

**Frequent GC Cycles:** Frequent GC cycles brings a few other performance problems.** **First, when the GC is kicked in, it needs some computing power. That means it takes some of the CPU processing power leaving less to the runnable threads. Second, if the major GC cycle is triggered, all the running threads need to be paused as all the major GCs are Stop-The-World — Which means they pause all the running threads and resume them once the GC cycle is completed. Creating too many objects lead to frequent GC cycles which impact the overall responsiveness.

**Limit on Number of Threads:** There is also a limit on how many threads can be created. The underlying or the native platform may not support those many threads.

**Unexpected Kills by Kernals:** The kernel may think that this is a malicious application creating too many threads, taking much memory, and may kill the whole application.

**Thread Life Cycle Costs:** Maintaining the Thread Life Cycle incurs additional costs. The thread object creation takes time as opposed to the normal object. Because it is not just an object allocated from the younger generation but the JVM also has to take care of native thread object creation in the underlying OS. And no need to mention specifically the ***Context-Switching*** among the threads.

**Most of the threads sit Idle: **Since we are creating too many threads, at any given point in time, there are more runnable threads than the available processors. If it is 32 Core CPU and at a time only 32 threads are running at most and the rest sit idle. This takes a lot of memory and threads fighting for the CPU may impose other performance costs as well.

Ah, Man! That’s a lot of disadvantages. Don’t worry. We have a solution. But if you notice closely all this scalability thing revolves around ***creating too many threads***. So how we can scale our application by not creating many threads but still handling the requests efficiently? ***Executor*** framework to the rescue.

With the help of Executor’s framework, we can create ***Thread Pools*** in which a fixed number of threads would already have been created and ready to take the tasks. Just to get a glimpse of it let's look at our third version of the server logic. Here is it.

```java
 
**private static final int NTHREADS **
**= Runtime.*****getRuntime*****().availableProcessors();**
**private static final Executor pool **
**= Executors.*****newFixedThreadPool*****(NTHREADS);**
ServerSocket socket = new ServerSocket(6000);
while (true) {
final Socket connection = socket.accept();
**pool.execute(**()->*handleRequest*(connection)**);**
}
```

Line 3 describes how we create the Thread pools. Don’t worry about it now. We will have a good understanding of it in later parts. This is just an introductory article to Executors and ThreadPools. The above code solves the problem of creating many threads and can handle the requests in parallel.

Just to understand it, first, we got the number of available processors using Runtime.*getRuntime*().availableProcessors() and then created a fixed thread pool using newFixedThreadPool(). The fixed thread pool contains a specified number of threads. And this pool also contains a waiting queue to accommodate the requests more than the available threads. More on this later in upcoming parts. And line 11 describes how we submit the tasks to the pool.

That’s all the introduction to Executor Frameworks. In the next part, we will have a look at thread pools in depth.

## Summary

The Java Executor Framework deals with distributing the tasks to the threads for their execution.

Java Executor Framework solves the problem of creating and managing threads and offers better performance by dispatching the tasks to threads efficiently.

Java Executor Framework has several thread pools to fit into many situations and many factory methods to get the thread pool object which we will cover in later parts.