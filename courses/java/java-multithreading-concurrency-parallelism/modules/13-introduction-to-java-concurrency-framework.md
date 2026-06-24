# Introduction to Java Concurrency Framework

Concurrency

In all the previous parts (From  to ) we have covered the basics of multithreading. From here we will explore the concurrency framework and what does it offer us. In this article, we will see an overview of the concurrency framework.

First, let's understand the difference between Multithreading and Concurrency. People use these terms very loosely. But there is a clear difference in their definitions.

Multithreading simply means there can be more than one thread running inside a process but not necessarily at the same time, maybe because of a single-core CPU. That means, though the application contains many threads, at a given point, only one thread gets executed by the CPU.

Whereas Concurrency is all about dealing with multiple threads or tasks at the same time because of the multiple CPU cores — Each core takes care of running one thread. If there are more threads in the application than the available cores then they interleave the CPU cores as per the Thread Scheduler.

Take a four-burner gas stove for example. You can cook 4 items concurrently at the same time. If you have more than four items, you have to deal with the cooking by prioritizing the items to be cooked, in which case you(the master chef) become the *ThreadScheduler*.

So, in a sense, *multithreading* is what enables *concurrency*. Without *multithreading*, there is no *concurrency*.

Then what about *parallelism*? We should not confuse concurrency with parallelism. Parallelism is about ***doing*** many sub-tasks of a single task at once whereas concurrency is about ***dealing*** with many tasks at the same time. We use parallelism mostly from a processing or computing perspective to achieve some performance.

Let us take the same example of the gas stove again. You have four burners (four cores) and let us assume two scenarios here:

**Scenario 1:** Assume that we have to cook 4 items: Item1, Item2, Item3, and Item4.

**Scenario 2:** Assume that we have to boil four liters of water.

**Scenario 1** is simple. What we do is, cook all the items at the same time using all the four burners available; Item1 on Burner1, Item2 on Burner2, and so on. This is concurrency — Dealing with multiple items(threads) at the same time.

**Scenario 2** is rather tricky though it is a single task. Think of it once. Boiling the water is a single task that can be done on a single burner. But we have four burners available. If we cook all the four liters on a single burner we will waste time and all the other 3 burners are idle. What we can do to use all these four burners effectively is, take four bowls(four threads) and distribute 1 liter of water into each of them(breaking down the large task into smaller tasks and assigning them to threads) and boil them at the same time. Once the water in all four bowels is boiled, we merge them into a single large container. So we are essentially boiling 4 liters of water taking the time equivalent to boil 1 liter of water. This is what *Parallelism* is — Breaking down a bigger task into smaller tasks, solving them, and merging the results from each task — ***The Divide and Conquer approach***. What do we achieve with this? The Performance (by leveraging the available CPU power). Java has fork-join framework to exactly deal with this kind of scenario. In fact, fork-join is the core underlying framework for all the parallel streams. It follows the work-stealing mechanism. More on this later.

**Multithreading*** is about having, running, and managing multiple threads in our application but not necessarily at the same time.*

**Concurrency*** is about dealing with multiple threads at the same time achieved with the help of multithreading. Without *multithreading,* there is no concurrency.*

**Parallelism*** is about processing or computing a single large task efficiently by leveraging the multiple CPU cores. With parallelism, we break the large task into smaller tasks and solve them in parallel. This is also only applicable when we have more than one thread.*

Java supports all the above three mechanisms. So far what we have seen from  to  is all about multithreading and can be taken as a foundation to what we will be learning from here — Concurrent programming.

## Introduction to Concurrency Framework

The Java concurrency framework is implemented under java.util.concurrent package which enables us to implement concurrent programming. This package contains two sub-packages and many other classes to support concurrency and parallelism.

**java.util.concurrent.locks: **Provides API for locking and waiting for a condition. Similar to synchronized, wait & notify.

**java.util.concurrent.atomic: **A small toolkit of classes that support ***lock-free*** thread-safe programming on single variables. We will deep dive into ***lock-free*** or ***non-blocking*** constructs in later parts. We will also see how to implement ***non-blocking thread-safe*** collections.

Apart from these two sub-packages, there are many thread-safe collection classes which we will cover in later parts: CopyOnWriteArrayList, ConcurretHashMap, ConcurrentLinkedQueue, ArrayBlockingQueue, LinkedBlockingQueue, and etc. The other most important thing to look at in this package is the Executor framework that supports various thread pools. This package offers many more. We will look at the most important things one by one in later parts. The main idea of this part is to give an introduction to Java’s concurrency framework and how it enables us to deal with concurrent programming.