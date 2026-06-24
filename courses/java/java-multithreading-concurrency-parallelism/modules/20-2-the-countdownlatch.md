# The CountDownLatch

In the previous , we have introduced the synchronizers, their state dependency, and how AQS manages the state, FIFO queues, and the threads. Here we will see a simple synchronizer known as a ***CountDownLatch***.

As we have already mentioned in the previous , every synchronizer has a state associated with it based on which it allows or blocks the threads. So the CountDownLatch has a state called terminal state. The latch delays the progress of the intended threads until it reaches the terminal state.

The CountDownLatch is a class and contains a constructor that takes an integer. The CountDownLatch is initialized with this integer, the count, which when reaches zero, releases all the waiting threads. Reaching count zero indicates that all the events have occurred.CountDownLatch has two main methods to specify the occurrence of events.

**countDown()**:** **decrements the counter, indicating that an event has occurred.

**await()**: waits till the counter reaches zero. await() method has another variant that takes timeout.

CountDownLatch can be used in many ways. But the below three are the common practices that people use.

As a simple two-state Latch.

To wait until the specified number of threads complete their tasks.

To manage service dependency in an application.

## 1. As a Simple two-state Latch:

This can also be thought of like an on/off latch. Imagine a scenario, where we need to do some computation until some initialization has been fully done. We can do it with wait and notify. But it doesn’t provide that much greater flexibility and we will also have to write a cluttered code with synchronized blocks, with wait and notify wrapped inside try/catch blocks. Instead, a simple two-state latch can be implemented here. To configure the two-state latch, we can just simply initialize the CountDownLatch with count as 1. The thread that takes up the initialization process counts it down to zero after it completes. After which the computation process takes place. The below program illustrates this.

```java
import java.util.Random;
import java.util.concurrent.CountDownLatch;
import java.util.stream.IntStream;


public class CountDownLatchDemo
{


    private static IntStream randInts;
    private static final CountDownLatch latch = new CountDownLatch(1);


    public static void main(String[] args) throws InterruptedException {
        Thread t
= new Thread(() -> {
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            // Initialization of randInts
            randInts = new Random().ints(10000);
            System.out.println(Thread.currentThread() + ": Initialization Done");
            latch.countDown();
        }, "INITIALIZER");
        t1.start();


        // main Thread waits for the initialization to be completed.
        System.out.println(Thread.currentThread() + ": Waiting for the Initialization Task to be Completed");
        latch.await(); // main thread blocks here until latch count becomes to zero.


        // main Thread resumes here and starts the computation process.
        System.out.println(Thread.currentThread() + ": " + randInts.average().getAsDouble());
    }


}
```

hosted with ❤ by 

Illustration 20.2.1 Using CountDownLatch as a two-state latch

In the above program we have two threads: INITIALIZER and main. The main thread, at line 26, waits for the latch to reach its terminal state. The INITIALIZER thread at line 18 initializes the randInts variable and bring the count down by one. As the latch is initialized with the count as 1, it has now become zero, in other words, it has reached its terminal state, thereby allowing the main thread to proceed. Here is the output of the above program.

***Thread[main,5,main]: Waiting for the Initialization Task to be Completed******
Thread[INITIALIZER,5,main]: Initialization Done******
Thread[main,5,main]: 1.26677879283E7***

## 2. To wait until the specified number of threads complete their tasks

Assume a real-world scenario that which a group of friends from different locations wants to meet at a coffee shop. They all want to meet at a particular place and from there they want to go together to have a coffee. In this case, as every person arrives at the intended place, he/she would have to wait till all the persons arrive, and then together they would go to the coffee shop. This is exactly the scenario that we can solve with CountDownLatch — Letting all the parties arrive and then move on.

The other excellent example that we can think of is of the online multiplayer game such as *CounterStrike*. The game should only be started after the arrival of all the players. In this case, we can initialize the CountDownLatch with the number of parties to arrive and as each party arrives we will just count it down. The below program illustrates this.

```java
import java.util.concurrent.CountDownLatch;


public class CountDownLatchDemo
{


    private static final int N_PARTIES = 4;
    private static final CountDownLatch latch = new CountDownLatch(N_PARTIES);


    public static void main(String[] args) throws InterruptedException {
        Thread party
= new Thread(getPartyTask(), "PARTY_1");
        Thread party
= new Thread(getPartyTask(), "PARTY_2");
        Thread party
= new Thread(getPartyTask(), "PARTY_3");
        Thread party
= new Thread(getPartyTask(), "PARTY_4");


        party1.start();
        party2.start();
        party3.start();
        party4.start();


        System.out.println(Thread.currentThread() + ": Waiting for all the parties ...");
        latch.await();
        System.out.println("All the parties have arrived. Game Started !!");
    }


    private static Runnable getPartyTask() {
        return () -> {
            try {
                System.out.println(Thread.currentThread() + ": I am on my way!");
                Thread.sleep(1000);
                System.out.println(Thread.currentThread() + ": I have just arrived!");
                latch.countDown();
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        };
    }
}
```

hosted with ❤ by 

Illustration 20.2.3 Using CountDownLatch as a gate waiting for all the parties to arrive

In line 6, we have initialized our latch with 4 which is the number of persons to participate in the game. And the main thread waiting on the latch (the gate), all the threads, as they are done with their task invoke *countDown()* on the latch object. As all the four threads count the latch down, the latch reaches to terminal state, as a result of which the gate opens and the main thread continues further. Here is the output of the above program.

Thread[main,5,main]: Waiting for all the parties ...
Thread[PARTY_3,5,main]: I am on my way!
Thread[PARTY_4,5,main]: I am on my way!
Thread[PARTY_2,5,main]: I am on my way!
Thread[PARTY_1,5,main]: I am on my way!
Thread[PARTY_3,5,main]: I have just arrived!
Thread[PARTY_4,5,main]: I have just arrived!
Thread[PARTY_2,5,main]: I have just arrived!
Thread[PARTY_1,5,main]: I have just arrived!
All the parties have arrived. Game Started !!

## 3. To manage service dependency in an application

CountDownLatch can be used to maintain a service dependency. Now, Don’t get confused by the word service. We are NOT at all talking about a REST-based web service or any other microservice. But the service we are talking about is more at the module level; for example, *Cache Service*, *Data Downloader* service and etc.

Imagine we have three services in our application: ***CacheService***, ***DataDownloaderService***, and ***ClientService***. Just for our ease of understanding just assume that* …*

***DataDownloaderService*** downloads some share market price data from a file preloaded CSV file.

***CacheService**** *prepares a cache with the downloaded data.

***ClientService*** serves the requests of the price of a particular stock from the Client.

If you look at the above services there is a dependency among them. Until the data is downloaded the cache cannot be prepared. Until the cache is prepared the requests can’t be served efficiently. So that means, the ***ClientService*** depends on ***CacheService*** which in turn depends on ***DataDownLoaderService***.

How can the CountDownLatch help us here in this scenario?

Well, with the CountDownLatch we can ensure that a service does not start until the other service on which it depends has started. To get this done, each service would have an associated two-state latch — The binary latch initialized with the count as 1; For example, starting ***CacheService*** would involve ﬁrst waiting on the latch for ***DataDownloaderService***, and then releasing the latch after it completes the downloading. The same is the case with the ***ClientService****, *it waits until the ***CacheService**** *is ready. This is example is rather a little complex. The below program illustrates this clearly.

```java
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.stream.Collectors;


public class CountDownLatchDemo
{


    private static final CountDownLatch DOWNLOAD_LATCH = new CountDownLatch(1);
    private static final CountDownLatch CACHE_LATCH = new CountDownLatch(1);


    private static List<String> downloadedMarketData;
    private static Map<String, MarketData> marketDataCache;


    public static void main(String[] args) throws InterruptedException {
        Thread downloaderServiceThread = new Thread(downloadService(), "DOWNLOADER_SERVICE");
        Thread cacheServiceThread = new Thread(cacheService(), "CACHE_SERVICE");


        downloaderServiceThread.start();
        cacheServiceThread.start();


        System.out.println(Thread.currentThread() + ": Waiting for the Cache Service To complete");
        CACHE_LATCH.await();
        System.out.println(Thread.currentThread() + ": Cache Service Completed. Ready to serve the client Requests !!");
        // Client Request Serving Logic Goes here
    }


    private static Runnable downloadService() {
        return () -> {
            try {
                System.out.println(Thread.currentThread() + ": Market Data Download Started ...");
                downloadedMarketData = Files.lines(Path.of("src/main/resources/market_data.csv")).collect(Collectors.toList());
                System.out.println(Thread.currentThread() + ": Market Data Download Completed!");
                DOWNLOAD_LATCH.countDown();
            } catch (IOException e) {
                e.printStackTrace();
            }
        };
    }


    private static Runnable cacheService() {
        return () -> {
            try {
                System.out.println(Thread.currentThread() + ": Waiting for Market Data Download ...");
                DOWNLOAD_LATCH.await(); // Wait for
                marketDataCache = new HashMap<>();
                downloadedMarketData.forEach(line -> {
                    final String[] data = line.split(",");
                    MarketData md = new MarketData(data[0], data[1], data[2], Double.parseDouble(data[3]));
                    marketDataCache.put(data[0], md);
                });
                CACHE_LATCH.countDown();
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        };
    }


    static class MarketData {
        private final String name;
        private final String location;
        private final String currency;
        private final double price;


        MarketData(String name, String location, String currency, double price) {
            this.name = name;
            this.location = location;
            this.currency = currency;
            this.price = price;
        }


        public String getName() {
            return name;
        }


        public String getLocation() {
            return location;
        }


        public String getCurrency() {
            return currency;
        }


        public double getPrice() {
            return price;
        }
    }
}
```

hosted with ❤ by 

Illustration 20.2.2 Managing the service dependency using CountDownLatch

In the above program, we have three threads named DOWNLOADER_SERVICE, CACHE_SERVICE and main. The main is taken as a *ClientService* which is responsible for serving the requests from the client.

main thread waits for CACHE_SERVICE which in turn waits for DOWNLOADER_SERVICE to complete. And below is the output of the above program.

***Thread[main,5,main]: Waiting for the Cache Service To complete******
Thread[CACHE_SERVICE,5,main]: Waiting for Market Data Download ...******
Thread[DOWNLOADER_SERVICE,5,main]: Market Data Download Started ...******
Thread[DOWNLOADER_SERVICE,5,main]: Market Data Download Completed!******
Thread[main,5,main]: Cache Service Completed. Ready to serve the client Requests !!***

That’s all the three most common ways of using the CountDownLatch. The one important property of latch is that once it reaches the terminal state it cannot change its stage again. So the gate remains open forever. If we want to change the state again to the beginning we have to use CyclicBarrier which we will explain in later parts of this series.

## Summary

The CountDownLatch is initialized with a count which when reaches zero, all the waiting threads are released. Reaching count zero indicates that all the events have occurred.

CountDownLatch has two main methods to work with. **countDown()** method decrements the counter, indicating that an event has occurred. The **await()** method waits for the counter to reach zero. **await()** method has another variant that takes timeout.

There are three common ways how a CountDownLatch can be used:
a. Used as a simple two-state Latch.
b. Used to wait until the specified number of threads complete their tasks.
c. Used to manage service dependency in an application.

That's all about the CountDownLatch. In the next section, we will have a look at CyclicBarrier which is an extension of CountDownLatch.