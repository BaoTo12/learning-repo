# The FutureTask

In the last part, we have seen ***Latches*** and ***Barriers*** and here in this part we will look at another synchronizer known as the FutureTask. As the name suggests it represents a task or a computation that is expected to be completed and return the results in the future. FutureTask enables a kind of asynchronous programming. Note that it is not a pure asynchronous in its own nature as there is no callback mechanism once the task completes. We will come back to this later. But for now, let's understand how to work with FutureTask.

FututeTask is an excellent choice to make when we want to build a ***Result-Oriented-Cache*** in which the result involves heavy computation.

Let’s say we have a multiplayer game, in which we need to compute the top scorer after the end of every five games. For this, at the end of each game, we need to compute the score for that particular game and store them in the cache to make them available for the next game. And assume that computation of score is a heavy task that collects all the information happened in the game and compute the results. And this needs to be done for every player.

There are two things to be considered in this scenario.

First, the results are to be cached and made available for the next game.

Second, the results are not be needed immediately but for the next game.

FutureTask exactly suits the scenarios like above. When you have a heavy computation task and the result is needed in the future, then FutureTask is the right candidate.

## FutureTask as a Latch

FutureTask takes an instance of Callable which represents a task that can return a result. It also acts as a ***Latch*** meaning, that the threads that request for the results will be blocked if the results are not still available as the computation is still going on. Same as latch, in which the threads wait for the latch to reach its terminal state.

_NOTE: Callable represents a \***\*task that returns results\*\***, unlike Runnable which doesn’t return any results._

**\*FutureTask acts a Latch.\*\***

- In Latch all the threads wait for the terminal state.\*\*
- In FutureTask all the threads wait for the results to be available.\*

For more information on Latch look at  article.

To understand FutureTask better, let us go point by point.

The class Hierarchy of FutureTask

The states of FutureTask

Getting Results fromFutureTask

Dealing with Exceptions thrown by Future.get()

Usages of FutureTask

## 1. The class Hierarchy of FutureTask

The first and foremost thing to talk about FutureTask is its class hierarchy. It is very important to know the Class Hierarchy to work with FutureTask, which is depicted below.
![alt text](../images/image23.png)
You can see from the above class hierarchy diagram FutureTask implements the interface RunnableFuture, which in turn is extended from Future and Runnable interfaces. So from this diagram what we need to understand is that FutureTask is a Runnable and can happily be passed as a parameter to Thread constructor as below.

FutureTask<MarketData> **\*future\*\*** *=
new FutureTask< (()->*computeScores\*);
Thread t1 = new Thread(**_future_**, "TOP_SCORE_COMPUTER");
t1.start(); // thread performs the task represented by **future**

## 2. The States of FutureTask

The second thing to talk about the FutureTask is its state. Since it is a synchronizer and every synchronizer is state-dependent, FutureTask does also have states. As we already stated, the computation represented by a FutureTask is implemented with a Callable — The result-bearing equivalent of Runnable. So the state of FutureTask depends on this Callable and can be in one of these three states: ***Waiting***, ***Running***, or ***Completed***. The ***Completed*** state can again be divided into many including; A successful *Completion*, *Cancellation*, or an *Exception*. Once a FutureTask enters the completed state, it stays in that state forever — Remember the same case as that of Latch.

**3. Getting Results from **FutureTask

The third thing to talk about FutureTask is getting the results from it. We simply use the Future.get() method on the FutureTask object but the behavior depends on the state of the task. There are three typical scenarios to be noted here.

If the task is completed before the call to get(), it returns the result immediately.

Otherwise it blocks until the task goes into the completed state and then returns the result. This is why we say that it is not pure asynchronous behavior, because it blocks. This is tricky. Note that the task is run asynchronously by another thread but the other thread which needs the result has to wait if the computation is not completed. There is no call back mechanism here.

Or it throws an exception as a result of some error in the computation. Remember the tasks described by Callable can throw exceptions.

**FutureTask Guarantees Safe Publications:\*\***
\*\*The thing here is to note from where to where the results are flowing. To put it simple, the FutureTask sends the result from the thread doing the computation to the thread(s) retrieving the result; This brings out the publication-safety concerns. But we don't have to worry about it as the speciﬁcation of FutureTask guarantees that this transfer constitutes a safe publication of the result.

## 4. Dealing with Exception raised by Future.get()

This is by far the important thing in terms of coding the exception handler. Tasks described by Callable can throw checked and unchecked exceptions and any code can throw an Error. Whatever the exception the computation logic may throw, it is always wrapped in an ExecutionException and rethrown from Future.get().

But this complicates the code in the thread that calls get(), because it must deal with two possible exceptions: ExecutionException and the unchecked CancellationException. Not only that, because the cause of the ExecutionException is returned as a Throwable, it is also an inconvenient thing to deal with.

When get() throws an ExecutionException, the cause of the exception (ex.getCause()) may fall into one of the below three categories:

A checked exception thrown by the Callable — The computation logic

A RuntimeException

An Error.

We must handle each of these cases separately. The ***Listing 5.13 ***of ***Java Concurrency in Practice*** book specifies a utility method that comes in handy here — The method **launderThrowable()** for which I am copy-pasting the code here straight away from the book.

```java
public static ***RuntimeException*** *launderThrowable*(***Throwable*** t) {
    if (t instanceof ***RuntimeException***)
        return (***RuntimeException***) t;
    else if (t instanceof ***Error***)
        throw (***Error***) t;
    else
        throw new ***IllegalStateException***("Not unchecked", t);
}
```

This utility method just encapsulates some of the messier exception-handling logic. But before calling the launderThrowable(), our code should also test for any known checked exceptions and rethrows them. That leaves only unchecked exceptions, which can be handed over to launderThrowable.

In the above code snippet, if the Throwable passed to launderThrowable is an Error, then it will be rethrown directly; if it is not a RuntimeException, it throws an IllegalStateException to indicate a logic error. That leaves only RuntimeException, which launderThrowable returns to its caller, and which the caller can do whatever it wants to — It generally rethrows it.

## 5. Uses of FutureTask

FutureTask is extensively used by the Executor framework to represent asynchronous tasks. As we already mentioned that the main use case is, the FutureTask is used to represent any potentially lengthy computation that can be started before the results are needed. We use FutureTask to perform an expensive computation whose results are needed later. By starting the computation early, we reduce the time we would have to wait, and later when you actually need the results they would be ready by then.

All the above 5 points are illustrated in the below program.

```java
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.FutureTask;


public class FutureTaskDemo {


    static class MarketDataDownloader {


        private final String LOCATION;


        // Market Data Downloader FutureTask
        private final FutureTask<MarketData> MARKET_DATA_FUTURE;


        // Market Data Downloader Thread taking the above future task
        private final Thread DOWNLOADER;


        private MarketDataDownloader(String location) {
            LOCATION = location;
            MARKET_DATA_FUTURE = new FutureTask<>(this::loadMarketData);
            DOWNLOADER = new Thread(MARKET_DATA_FUTURE, "MARKET_DATA_DOWNLOADER");
        }


        private MarketData loadMarketData() throws IOException {
            MarketData md = new MarketData();
            logInfo("Preparing the Market Data ...");
            Files.lines(Path.of(LOCATION)).forEach(md::addEntry);
            return md;
        }


        public void download() {
            // Starts the thread with the Future Task
            DOWNLOADER.start();
        }


        public MarketData getMarketData() {
            MarketData md = null;
            try {
                md = MARKET_DATA_FUTURE.get(); // A blocking call till the result is available
            } catch (InterruptedException e) {
                e.printStackTrace();
            } catch (ExecutionException e) {
                Throwable cause = e.getCause();
                // Handle all the checked exception here and then throw the
                throw launderThrowable(cause);
            }
            return md;
        }


        private RuntimeException launderThrowable(Throwable t) {
            if (t instanceof RuntimeException) return (RuntimeException) t;
            else if (t instanceof Error) throw (Error) t;
            else throw new IllegalStateException("Not unchecked", t);
        }


    }


    static class MarketData {


        private final Map<String, MarketDataEntry> cache;


        MarketData() {
            cache = new HashMap<>();
        }


        public void addEntry(String fields) {
            String[] data = fields.split(",");
            MarketDataEntry mde = new MarketDataEntry(data[0], data[1], data[2], Double.parseDouble(data[3]));
            logInfo("Downloaded and cached the Market Data Entry for " + data[0]);
            sleep(500);
            cache.put(data[0], mde);
        }


        public int getCount() {
            return cache.size();
        }


        private static class MarketDataEntry {
            private final String name;
            private final String location;
            private final String currency;
            private final double price;


            public MarketDataEntry(String name, String location, String currency, double price) {
                this.name = name;
                this.location = location;
                this.currency = currency;
                this.price = price;
            }


            // All the getters
        }


    }


    public static void sleep(long millis) {
        try {
            Thread.sleep(millis); // Simulating Heavy Computation
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }


    public static void main(String[] args) {
        MarketDataDownloader mdl = new MarketDataDownloader("src/main/resources/market_data.csv");
        mdl.download();
        logInfo("Waiting for the market data download to complete ...");
        MarketData md = mdl.getMarketData(); // A blocking call waits till the result is available.
        logInfo("Market Data downloaded successfully. Number of entries: " + md.getCount());
    }


    private static void logInfo(String msg) {
        System.out.println(LocalDateTime.now() + ": " + Thread.currentThread() + " :: " + msg);
    }


}
```

hosted with ❤ by 

Illustration 20.4.1 FutureTaskDemo

Here is the output of the above program.

2022-04-07T20:21:19.881249: Thread[main,5,main] :: Waiting for the market data download to complete ...
2022-04-07T20:21:19.879190: Thread[MARKET_DATA_DOWNLOADER,5,main] :: Preparing the Market Data ...
2022-04-07T20:21:20.068537: Thread[MARKET_DATA_DOWNLOADER,5,main] :: Downloaded and cached the Market Data Entry for STOCK1
2022-04-07T20:21:20.575519: Thread[MARKET_DATA_DOWNLOADER,5,main] :: Downloaded and cached the Market Data Entry for STOCK2
2022-04-07T20:21:21.076063: Thread[MARKET_DATA_DOWNLOADER,5,main] :: Downloaded and cached the Market Data Entry for STOCK3
2022-04-07T20:21:21.576534: Thread[MARKET_DATA_DOWNLOADER,5,main] :: Downloaded and cached the Market Data Entry for STOCK4
2022-04-07T20:21:22.077510: Thread[MARKET_DATA_DOWNLOADER,5,main] :: Downloaded and cached the Market Data Entry for STOCK5
2022-04-07T20:21:22.578706: Thread[MARKET_DATA_DOWNLOADER,5,main] :: Downloaded and cached the Market Data Entry for STOCK6
2022-04-07T20:21:23.111024: Thread[main,5,main] :: Market Data downloaded successfully. Number of entries: 6

To understand the above illustration lets follow through the below five points.

**Creation of FutureTask object:** As we already mentioned that FutureTask takes Callable, the line 24 in the above illustration creates the FutureTask object with the name MARKET_DATA_FUTURE . The method reference this::loadMarketData is represents the instance of Callable here.

**Creation of Thread with FutureTask**: The line 26 creates a thread referenced by DOWNLOADER with the FutureTask created above with the name MARKET_DATA_FUTURE.

**Starting the FutureTask**: Starting the thread DOWNLOADER will run the computation represented by the FutureTask as done in line 37.

**Getting the Results:** We just need to call get() on the FutureTask object that is MARKET_DATA_FUTURE.

**Handling Exception:** The get() throws ExecutionException and the caller has to handle this.

**Driver Program**: We encapsulated the FutureTask in MarketDataDownloader class to make it safer and easier to work with. The main thread from lines 109–113 creates the MarketDataDownloader object and calls download() method which in turn starts the DOWNLOADER thread that perform the computation represented by the FutureTask.

That’s all. Very simple. But I would suggest to go through the article once more and also write and run the program on your own so that you will understand it even better.

## Summary:

FutureTask implements RunnableFuture which in turn extends from Future and Runnable interfaces.

The FutureTask represents an abstract of result-bearing computation which is implemented with Callable which is an equivalent of Runnable but with the result.

FutureTask once started runs asynchronously and results will be available at the later point in time and for that Future.get() needs to be invoked.

Future.get() depends on the state of the task. If it is completed,
get returns the result immediately, and otherwise blocks until the task is completed or even throwS an exception if there is any error in the computation.

FutureTask is used by the Executor framework to represent asynchronous tasks, and can also be used to represent any potentially lengthy computation that can be started before the results are needed.

FutureTask is used to perform an expensive computation whose results are needed later; by starting the computation early, we reduce the time you would have to wait later when you actually need the results.
