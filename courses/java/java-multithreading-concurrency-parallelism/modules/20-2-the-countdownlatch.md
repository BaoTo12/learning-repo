# The CountDownLatch

In the previous module, we introduced synchronizers, their state-dependent nature, and how the `AbstractQueuedSynchronizer` (AQS) framework coordinates threads using an internal state and a FIFO queue. In this module, we will explore one of the simplest and most commonly used synchronizers in the Java Concurrency Utilities: the **`CountDownLatch`**.

A **`CountDownLatch`** is a synchronizer that delays the progress of one or more threads until it reaches its **terminal state**. 

---

## How CountDownLatch Works

A `CountDownLatch` is initialized with a positive integer representing a **count** of events that must occur before the latch opens:

```java
CountDownLatch latch = new CountDownLatch(count);
```

The latch exposes two primary methods to coordinate threads:
*   **`countDown()`**: Decrements the internal counter by 1, indicating that one of the required events has occurred. This is a non-blocking operation.
*   **`await()`**: Causes the calling thread to block until the counter reaches zero (its terminal state). Once the count is zero, the latch opens, and all waiting threads are released. If the count is already zero, `await()` returns immediately.

### Latch Irreversibility
> [!IMPORTANT]
> **The Use-Once Property**
> A `CountDownLatch` is a **single-use (use-once)** synchronizer. Once the counter reaches zero, the latch enters its terminal state, and the gate remains open forever. 
> 
> The count cannot be reset, nor can the latch be reused. If you need a barrier that can be reset and reused cyclically, you must use a `CyclicBarrier`.

---

## Three Common Use Cases for CountDownLatch

`CountDownLatch` is highly versatile. We will explore the three most common concurrency patterns it solves.

### 1. The Simple Two-State Latch (On/Off Gate)

This pattern acts as a simple start gate. It is useful when one or more threads must wait for a single initialization task to complete before they can begin their computations. 

We implement this by initializing the `CountDownLatch` with a count of **1**:

```java
import java.util.Random;
import java.util.concurrent.CountDownLatch;
import java.util.stream.IntStream;

public class TwoStateLatchDemo {

    private static IntStream randInts;
    private static final CountDownLatch latch = new CountDownLatch(1);

    public static void main(String[] args) throws InterruptedException {
        Thread initializer = new Thread(() -> {
            try {
                Thread.sleep(1000); // Simulate heavy initialization
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                e.printStackTrace();
            }
            // Perform initialization
            randInts = new Random().ints(10000);
            System.out.println(Thread.currentThread().getName() + ": Initialization Done");
            
            // Open the gate
            latch.countDown();
        }, "INITIALIZER");
        
        initializer.start();

        // The main thread waits for the initialization to complete
        System.out.println(Thread.currentThread().getName() + ": Waiting for the Initialization Task to be Completed");
        
        latch.await(); // Blocks here until latch count reaches 0

        // The main thread resumes and performs the computation
        System.out.println(Thread.currentThread().getName() + ": Average -> " + randInts.average().getAsDouble());
    }
}
```

*Figure 20.2.1: Coordinating a single initialization event using a two-state latch*

#### Output
```text
Thread[main,5,main]: Waiting for the Initialization Task to be Completed
Thread[INITIALIZER,5,main]: Initialization Done
Thread[main,5,main]: 1.26677879283E7
```

---

### 2. Waiting for Multiple Parallel Tasks (Multi-Party Gate)

This pattern is used when a thread must wait for a group of independent, parallel tasks to complete before proceeding. 

For example, in an online multiplayer game (like *Counter-Strike*), the game session should only start after all required players have connected and arrived in the lobby. We initialize the latch with the number of expected players:

```java
import java.util.concurrent.CountDownLatch;

public class MultiPartyGateDemo {

    private static final int N_PARTIES = 4;
    private static final CountDownLatch latch = new CountDownLatch(N_PARTIES);

    public static void main(String[] args) throws InterruptedException {
        Thread party1 = new Thread(getPartyTask(), "PARTY_1");
        Thread party2 = new Thread(getPartyTask(), "PARTY_2");
        Thread party3 = new Thread(getPartyTask(), "PARTY_3");
        Thread party4 = new Thread(getPartyTask(), "PARTY_4");

        party1.start();
        party2.start();
        party3.start();
        party4.start();

        System.out.println(Thread.currentThread().getName() + ": Waiting for all parties to arrive...");
        
        latch.await(); // Blocks until all 4 parties call countDown()
        
        System.out.println("All parties have arrived. Game Started!");
    }

    private static Runnable getPartyTask() {
        return () -> {
            try {
                System.out.println(Thread.currentThread().getName() + ": I am on my way!");
                Thread.sleep((long) (Math.random() * 1000 + 500)); // Simulate travel time
                System.out.println(Thread.currentThread().getName() + ": I have arrived!");
                
                latch.countDown(); // Decrement latch count
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                e.printStackTrace();
            }
        };
    }
}
```

*Figure 20.2.2: Waiting for multiple threads to arrive at a common start gate*

#### Output
```text
Thread[main,5,main]: Waiting for all parties to arrive...
Thread[PARTY_3,5,main]: I am on my way!
Thread[PARTY_4,5,main]: I am on my way!
Thread[PARTY_2,5,main]: I am on my way!
Thread[PARTY_1,5,main]: I am on my way!
Thread[PARTY_3,5,main]: I have arrived!
Thread[PARTY_2,5,main]: I have arrived!
Thread[PARTY_4,5,main]: I have arrived!
Thread[PARTY_1,5,main]: I have arrived!
All parties have arrived. Game Started!
```

---

### 3. Managing Service Dependencies in an Application

In complex applications, services often have strict boot dependencies. For example, a `ClientService` (which handles incoming requests) cannot start until a `CacheService` is populated. In turn, the `CacheService` cannot build the cache until a `DataDownloaderService` completes downloading raw data.

We can coordinate this cascading service boot sequence using two independent binary latches:

```java
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CountDownLatch;

public class ServiceDependencyDemo {

    private static final CountDownLatch DOWNLOAD_LATCH = new CountDownLatch(1);
    private static final CountDownLatch CACHE_LATCH = new CountDownLatch(1);

    private static String downloadedData;
    private static Map<String, String> cache;

    public static void main(String[] args) throws InterruptedException {
        Thread downloader = new Thread(downloadService(), "DOWNLOADER_SERVICE");
        Thread cacheBuilder = new Thread(cacheService(), "CACHE_SERVICE");

        downloader.start();
        cacheBuilder.start();

        System.out.println(Thread.currentThread().getName() + ": Waiting for the Cache Service to complete...");
        
        CACHE_LATCH.await(); // Client service blocks until the cache is fully ready
        
        System.out.println(Thread.currentThread().getName() + ": Cache Service completed. Ready to serve client requests!");
    }

    private static Runnable downloadService() {
        return () -> {
            try {
                System.out.println(Thread.currentThread().getName() + ": Market Data download started...");
                Thread.sleep(1000); // Simulate network download
                downloadedData = "STOCK1,100.0;STOCK2,200.0;STOCK3,300.0";
                System.out.println(Thread.currentThread().getName() + ": Market Data download completed!");
                
                DOWNLOAD_LATCH.countDown(); // Signal that download is complete
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                e.printStackTrace();
            }
        };
    }

    private static Runnable cacheService() {
        return () -> {
            try {
                System.out.println(Thread.currentThread().getName() + ": Waiting for Market Data download...");
                
                DOWNLOAD_LATCH.await(); // Block until downloader calls countDown()
                
                System.out.println(Thread.currentThread().getName() + ": Building cache...");
                cache = new HashMap<>();
                for (String entry : downloadedData.split(";")) {
                    String[] kv = entry.split(",");
                    cache.put(kv[0], kv[1]);
                }
                Thread.sleep(500); // Simulate cache processing
                
                CACHE_LATCH.countDown(); // Signal that cache is ready
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                e.printStackTrace();
            }
        };
    }
}
```

*Figure 20.2.3: Coordinating cascading service startup dependencies using multiple latches*

#### Output
```text
Thread[main,5,main]: Waiting for the Cache Service to complete...
Thread[CACHE_SERVICE,5,main]: Waiting for Market Data download...
Thread[DOWNLOADER_SERVICE,5,main]: Market Data download started...
Thread[DOWNLOADER_SERVICE,5,main]: Market Data download completed!
Thread[CACHE_SERVICE,5,main]: Building cache...
Thread[main,5,main]: Cache Service completed. Ready to serve client requests!
```

---

### 4. Coordinating Simultaneous Thread Start (Simultaneous Start Gate)

In multi-threaded testing, you often need to reproduce concurrency bugs (such as race conditions) by forcing thousands of threads to execute a block of logic at the exact same time. If you simply call `.start()` on threads in a loop, the earlier threads will likely finish executing before the later ones have even been spawned.

To solve this, we can use a **Simultaneous Start Gate** pattern employing three separate latches:
1.  **`readyThreadCounter`**: Decremented by each child thread as it starts, signaling to the parent thread that the child is ready.
2.  **`callingThreadBlocker` (The Gate)**: Initialized to **1**. All child threads wait on this latch. The parent thread opens the gate by calling `countDown()`, releasing all children at once.
3.  **`completedThreadCounter`**: Decremented by each child thread as it completes, allowing the parent thread to block until the entire simulation is done.

```java
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.stream.Collectors;
import java.util.stream.Stream;

public class WaitingWorker implements Runnable {
    private final List<String> outputScraper;
    private final CountDownLatch readyThreadCounter;
    private final CountDownLatch callingThreadBlocker;
    private final CountDownLatch completedThreadCounter;

    public WaitingWorker(List<String> outputScraper, CountDownLatch readyThreadCounter,
                         CountDownLatch callingThreadBlocker, CountDownLatch completedThreadCounter) {
        this.outputScraper = outputScraper;
        this.readyThreadCounter = readyThreadCounter;
        this.callingThreadBlocker = callingThreadBlocker;
        this.completedThreadCounter = completedThreadCounter;
    }

    @Override
    public void run() {
        readyThreadCounter.countDown(); // Signal parent that this thread is ready
        try {
            callingThreadBlocker.await(); // Block here until parent opens the start gate
            doSomeWork();
            outputScraper.add("Counted down");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            completedThreadCounter.countDown(); // Signal parent that this thread is complete
        }
    }

    private void doSomeWork() {
        // Simulate computation...
    }
}
```

We can prove that this pattern forces threads to align and start simultaneously with a concurrent JUnit test:

```java
@Test
public void whenDoingLotsOfThreadsInParallel_thenStartThemAtTheSameTime() throws InterruptedException {
    List<String> outputScraper = Collections.synchronizedList(new ArrayList<>());
    CountDownLatch readyThreadCounter = new CountDownLatch(5);
    CountDownLatch callingThreadBlocker = new CountDownLatch(1);
    CountDownLatch completedThreadCounter = new CountDownLatch(5);

    List<Thread> workers = Stream
      .generate(() -> new Thread(new WaitingWorker(
        outputScraper, readyThreadCounter, callingThreadBlocker, completedThreadCounter)))
      .limit(5)
      .collect(Collectors.toList());

    workers.forEach(Thread::start);
    
    readyThreadCounter.await(); // Wait for all 5 workers to be ready and blocked at the gate
    outputScraper.add("Workers ready");
    
    callingThreadBlocker.countDown(); // Open the gate, releasing all 5 workers simultaneously!
    
    completedThreadCounter.await(); // Wait for all 5 workers to finish
    outputScraper.add("Workers complete");

    assertThat(outputScraper).containsExactly(
        "Workers ready",
        "Counted down",
        "Counted down",
        "Counted down",
        "Counted down",
        "Counted down",
        "Workers complete"
    );
}
```

---

## Timeout and Early Termination (Broken Workers)

A critical hazard when working with latches is the risk of **infinite blocking**. If a worker thread terminates in error (e.g., due to an uncaught `RuntimeException`) before decrementing the latch, the counter will never reach zero. Any thread waiting on `await()` will block indefinitely, hanging the application.

```java
public class BrokenWorker implements Runnable {
    private final CountDownLatch countDownLatch;

    public BrokenWorker(CountDownLatch countDownLatch) {
        this.countDownLatch = countDownLatch;
    }

    @Override
    public void run() {
        if (true) {
            throw new RuntimeException("Oh dear, I'm a BrokenWorker");
        }
        countDownLatch.countDown(); // This line is never reached!
    }
}
```

### Preventing Infinite Block with Timed await()

To safeguard your application, you should **never** use the untimed `await()` method in production. Instead, always specify a maximum timeout duration:

```java
CountDownLatch countDownLatch = new CountDownLatch(5);

// Start workers...

// Wait for up to 3 seconds for the latch to open
boolean completed = countDownLatch.await(3L, TimeUnit.SECONDS); 
if (!completed) {
    // Handle timeout scenario gracefully (e.g., logging, alerting, or falling back)
    System.out.println("Latch timed out before all workers completed!");
}
```

---

## Summary

*   **CountDownLatch**: A synchronizer that blocks threads until its internal counter is decremented to zero by other threads.
*   **Terminal State**: Reaching a count of zero represents the terminal state. Once reached, the latch opens, releasing all blocked threads.
*   **Single-Use (Use-Once)**: Once a latch opens, it cannot be reset or reused. The gate remains open forever.
*   **Core API**:
    - `countDown()`: Non-blocking call that decrements the counter.
    - `await()`: Blocking call that waits for the counter to reach zero. Includes a timeout variant to prevent indefinite blocking.
*   **Common Patterns**:
    - **Two-State Latch**: Acting as an on/off gate to wait for a single initialization event.
    - **Multi-Party Gate**: Waiting for a group of parallel worker threads to complete their tasks.
    - **Service Dependency**: Coordinating cascading startup sequences where services depend on the completion of prior services.