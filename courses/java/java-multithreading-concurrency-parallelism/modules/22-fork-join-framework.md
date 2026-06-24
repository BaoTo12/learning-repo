# Guide to the Fork/Join Framework in Java

## 1. Overview

Java 7 introduced the fork/join framework. It provides tools to help speed up parallel processing by attempting to use all available processor cores. It accomplishes this **through a divide and conquer approach.**

In practice, this means that **the framework first “forks,”** recursively breaking the task into smaller independent subtasks until they are simple enough to run asynchronously.

After that, **the “join” part begins.** The results of all subtasks are recursively joined into a single result. In the case of a task that returns void, the program simply waits until every subtask runs.

To provide effective parallel execution, the fork/join framework uses a pool of threads called the *ForkJoinPool*. This pool manages worker threads of type *ForkJoinWorkerThread*.

## 2. ForkJoinPool

The *ForkJoinPool* is the heart of the framework. It is an implementation of the  that manages worker threads and provides us with tools to get information about the thread pool state and performance.

Worker threads can execute only one task at a time, but the *ForkJoinPool* doesn’t create a separate thread for every single subtask. Instead, each thread in the pool has its own double-ended queue (or , pronounced “deck”) that stores tasks.

This architecture is vital for balancing the thread’s workload with the help of the** work-stealing algorithm.**

## 2.1. Work-Stealing Algorithm

## Simply put, free threads try to “steal” work from deques of busy threads.

By default, a worker thread gets tasks from the head of its own deque. When it is empty, the thread takes a task from the tail of the deque of another busy thread or from the global entry queue since this is where the biggest pieces of work are likely to be located.

This approach minimizes the possibility that threads will compete for tasks. It also reduces the number of times the thread will have to go looking for work, as it works on the biggest available chunks of work first.

## 2.2. ForkJoinPool Instantiation

In Java 8, the most convenient way to get access to the instance of the *ForkJoinPool *is to use its static method *()*. This will provide a reference to the common pool, which is a default thread pool for every *ForkJoinTask*.

According to , using the predefined common pool reduces resource consumption since this discourages the creation of a separate thread pool per task.

```java
**ForkJoinPool** commonPool = ForkJoinPool.commonPool();
```

We can achieve the same behavior in Java 7 by creating a *ForkJoinPool* and assigning it to a *public static* field of a utility class:

```java
**public** **static** **ForkJoinPool** forkJoinPool = **new** **ForkJoinPool**(2);
```

Now we can easily access it:

```java
**ForkJoinPool** forkJoinPool = PoolUtil.forkJoinPool;
```

With *ForkJoinPool’s *constructors, we can create a custom thread pool with a specific level of parallelism, thread factory and exception handler. Here the pool has a parallelism level of 2. This means that pool will use two processor cores.

## 3. ForkJoinTask<V>

*ForkJoinTask *is the base type for tasks executed inside *ForkJoinPool*. In practice, one of its two subclasses should be extended: the *RecursiveAction* for *void *tasks and the *RecursiveTask<V>* for tasks that return a value.* *They both have an abstract method *compute() *in which the task’s logic is defined.

## 3.1. RecursiveAction

In the example below, we use a *String* called *workload* to represent the unit of work to be processed. For demonstration purposes, the task is a nonsensical one: It simply uppercases its input and logs it.

To demonstrate the forking behavior of the framework, **the example splits the task if *****workload.length()***** is larger than a specified threshold*** *using the *createSubtask()* method.

The String is recursively divided into substrings, creating *CustomRecursiveTask *instances that are based on these substrings.

As a result, the method returns a List<CustomRecursiveAction>.

The list is submitted to the *ForkJoinPool *using the *invokeAll()* method:

```java
**public** **class** **CustomRecursiveAction** **extends** **RecursiveAction** {
    **private** **String** workload = "";
    **private** **static** **final** **int** THRESHOLD = 4;
    **private** **static** **Logger** logger = 
      Logger.getAnonymousLogger();
    **public** **CustomRecursiveAction**(String workload) {
        this.workload = workload;
    }
    @Override
    **protected** **void** **compute**() {
        **if** (workload.length() > THRESHOLD) {
            ForkJoinTask.invokeAll(createSubtasks());
        } **else** {
           processing(workload);
        }
    }
    **private** List<CustomRecursiveAction> **createSubtasks**() {
        List<CustomRecursiveAction> subtasks = **new** **ArrayList**<>();
        **String** partOne = workload.substring(0, workload.length() / 2);
        **String** partTwo = workload.substring(workload.length() / 2, workload.length());
        subtasks.add(**new** **CustomRecursiveAction**(partOne));
        subtasks.add(**new** **CustomRecursiveAction**(partTwo));
        **return** subtasks;
    }
    **private** **void** **processing**(String work) {
        **String** result = work.toUpperCase();
        logger.info("This result - (" + result + ") - was processed by " 
          + Thread.currentThread().getName());
    }
}
```

We can use this pattern to develop our own *RecursiveAction* classes. To do this, we create an object that represents the total amount of work, chose a suitable threshold, define a method to divide the work and define a method to do the work.

## 3.2. RecursiveTask<V>

For tasks that return a value, the logic here is similar.

The difference is that the result for each subtask is united in a single result:

```java
**public** **class** **CustomRecursiveTask** **extends** **RecursiveTask**<Integer> {
    **private** **int**[] arr;
    **private** **static** **final** **int** THRESHOLD = 20;
    **public** **CustomRecursiveTask**(**int**[] arr) {
        this.arr = arr;
    }
    @Override
    **protected** Integer **compute**() {
        **if** (arr.length > THRESHOLD) {
            **return** ForkJoinTask.invokeAll(createSubtasks())
              .stream()
              .mapToInt(ForkJoinTask::join)
              .sum();
        } **else** {
            **return** processing(arr);
        }
    }
    **private** Collection<CustomRecursiveTask> **createSubtasks**() {
        List<CustomRecursiveTask> dividedTasks = **new** **ArrayList**<>();
        dividedTasks.add(**new** **CustomRecursiveTask**(
          Arrays.copyOfRange(arr, 0, arr.length / 2)));
        dividedTasks.add(**new** **CustomRecursiveTask**(
          Arrays.copyOfRange(arr, arr.length / 2, arr.length)));
        **return** dividedTasks;
    }
    **private** Integer **processing**(**int**[] arr) {
        **return** Arrays.stream(arr)
          .filter(a -> a >
&& a < 27)
          .map(a -> a * 10)
          .sum();
    }
}
```

In this example, we use an array stored in the *arr *field of the *CustomRecursiveTask *class to represent the work. The *createSubtasks()* method recursively divides the task into smaller pieces of work until each piece is smaller than the threshold. Then the *invokeAll() *method submits the subtasks to the common pool and returns a list of .

To trigger execution, the *join()* method is called for each subtask.

We’ve accomplished this here using Java 8’s . We use the *sum()* method as a representation of combining sub results into the final result.

## 4. Submitting Tasks to the ForkJoinPool

We can use a few approaches to submit tasks to the thread pool.

Let’s start with the ***submit() ***or ***execute()**** *method (their use cases are the same):

```java
forkJoinPool.execute(customRecursiveTask);
**int** result = customRecursiveTask.join();
```

The ***invoke()**** *method forks the task and waits for the result, and doesn’t need any manual joining:

```java
**int** result = forkJoinPool.invoke(customRecursiveTask);
```

The ***invokeAll()*** method is the most convenient way to submit a sequence of *ForkJoinTasks* to the *ForkJoinPool*. It takes tasks as parameters (two tasks, var args or a collection), forks and then returns a collection of *Future* objects in the order in which they were produced.

Alternatively, we can use separate ***fork() *****and *****join()*** methods. The *fork()* method submits a task to a pool, but it doesn’t trigger its execution. We must use the *join() *method for this purpose.

In the case of *RecursiveAction*, the *join() *returns nothing but* null*; for *RecursiveTask<V>*, it returns the result of the task’s execution:

```java
customRecursiveTaskFirst.fork();
result = customRecursiveTaskLast.join();
```

Here we used the *invokeAll() *method to submit a sequence of subtasks to the pool. We can do the same job with *fork()* and *join()*, though this has consequences for the ordering of the results.

To avoid confusion, it is generally a good idea to use *invokeAll()* method to submit more than one task to the *ForkJoinPool*.

## 5. Conclusion

Using the fork/join framework can speed up processing of large tasks, but to achieve this outcome, we should follow some guidelines:

**Use as few thread pools as possible. **In most cases, the best decision is to use one thread pool per application or system.

**Use the default common thread pool** if no specific tuning is needed.

**Use a reasonable threshold** for splitting *ForkJoinTask* into subtasks.

## Avoid any blocking in ForkJoinTasks.