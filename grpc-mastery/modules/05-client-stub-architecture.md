# Module 05: gRPC Client Stubs & Threading Models

## 1. What Problem This Module Solves
Modern distributed systems require different concurrency execution strategies based on call volume and latency requirements:
*   **Blocking (Synchronous) Stubs**: Block the calling thread until the server responds. If used on primary UI or request-handling threads, blocking stubs quickly freeze the system.
*   **Async Stubs**: Rely on event-driven callbacks (`StreamObserver`). However, nested callbacks lead to "callback hell" and make aggregating results from concurrent calls extremely difficult.
*   **Future (Guava ListenableFuture) Stubs**: Allow non-blocking operations but require Google's Guava library classes (`ListenableFuture`, `Futures.addCallback`), which do not integrate natively with Java 8+ standard concurrency APIs like `CompletableFuture`.

This module demonstrates how to configure the three client stub types, manage channel threading models, and build adapter wrappers to convert Guava `ListenableFuture` into standard Java `CompletableFuture` for highly readable async fan-out architectures.

---

## 2. The Three Stub Types Compared

When you compile a `.proto` service contract, the compiler generates three separate stub implementations:

1.  **Blocking Stub (`RouteGuideBlockingStub`)**:
    *   *Signature*: `Feature getFeature(Point request)`
    *   *Usage*: Simple, synchronous calls. Block the current executing thread until the message returns or times out.
2.  **Async Stub (`RouteGuideStub`)**:
    *   *Signature*: `void getFeature(Point request, StreamObserver<Feature> responseObserver)`
    *   *Usage*: Bidirectional streaming and callback-driven processing. Excellent for long-lived streams.
3.  **Future Stub (`RouteGuideFutureStub`)**:
    *   *Signature*: `ListenableFuture<Feature> getFeature(Point request)`
    *   *Usage*: Non-blocking unary calls where you want to chain, combine, or fan-out multiple independent requests concurrently.

---

## 3. Client Threading Model

Under the hood, a gRPC client channel relies on a dedicated executor to manage execution:

```
[ Application Thread ]
       │
       ▼ (Invokes FutureStub.getFeature())
[ Netty EventLoop Thread ]  ───(Sends HTTP/2 Frame over TCP)───► [ Server ]
                                                                     │
[ Client Callback Executor ] ◄──(Invoked when response arrives)──────┘
  (e.g., ForkJoinPool)
       │
       ▼
[ CompletableFuture pipeline completes ]
```

*   **Netty worker threads** handle the raw socket write operations and read response bytes.
*   The **Callback Executor** executes the callbacks triggered when the data packet arrives. By default, if no executor is supplied to the `ManagedChannelBuilder`, the client executes these callbacks on Netty's event-loop threads. This is an anti-pattern because it can easily block network IO loops.

---

## 4. Common Mistakes and Anti-Patterns
*   **Thread Starvation via Blocking Stubs**: Running blocking stub invocations inside a high-throughput reactive loop or thread-sensitive environment.
*   **Forgetting to Set Client Executor**: Leaving the client callback executor empty. If your callbacks perform parsing, logging, or database writes, you will quickly starve the Netty event loops.
*   **Creating a New Stub Instance for Every Single Call**: Stub objects are lightweight and thread-safe. You should initialize stubs once and share them across thread executors rather than instantiating them repeatedly.

---

## 5. Converting Guava Futures to Java `CompletableFuture`

To build native async pipelines in standard Java, we can construct an adapter utility class:

```java
package com.example.grpc.client;

import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

public class GrpcFutureAdapter {

    /**
     * Converts a Guava ListenableFuture to a standard Java CompletableFuture.
     */
    public static <T> CompletableFuture<T> toCompletableFuture(
            ListenableFuture<T> listenableFuture, Executor executor) {
        
        CompletableFuture<T> completableFuture = new CompletableFuture<>() {
            @Override
            public boolean cancel(boolean mayInterruptIfRunning) {
                // Propagate cancellation back to the underlying gRPC stub call
                listenableFuture.cancel(mayInterruptIfRunning);
                return super.cancel(mayInterruptIfRunning);
            }
        };

        Futures.addCallback(listenableFuture, new FutureCallback<T>() {
            @Override
            public void onSuccess(T result) {
                completableFuture.complete(result);
            }

            @Override
            public void onFailure(Throwable t) {
                completableFuture.completeExceptionally(t);
            }
        }, executor);

        return completableFuture;
    }
}
```

---

## 6. Mini-Project: Async Fan-Out Aggregator using Java CompletableFuture

**Scenario**: You are writing a gateway service that needs to query three independent gRPC services concurrently (User profile, Orders history, and Credit rating), aggregate their results, and respond to the caller.

### Service Client Implementation (`AsyncGatewayAggregator.java`)
```java
package com.example.grpc.client;

import com.example.grpc.routeguide.Point;
import com.example.grpc.routeguide.Feature;
import com.example.grpc.routeguide.RouteGuideGrpc;
import com.example.grpc.routeguide.RouteGuideGrpc.RouteGuideFutureStub;
import com.google.common.util.concurrent.ListenableFuture;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;

import java.util.List;
import java.util.concurrent.*;
import java.util.stream.Collectors;
import java.util.stream.Stream;

public class AsyncGatewayAggregator {

    private final RouteGuideFutureStub stub;
    private final ExecutorService executorPool;

    public AsyncGatewayAggregator(ManagedChannel channel) {
        this.stub = RouteGuideGrpc.newFutureStub(channel);
        this.executorPool = Executors.newFixedThreadPool(10, new ThreadFactory() {
            private int count = 0;
            @Override
            public Thread newThread(Runnable r) {
                return new Thread(r, "aggregator-pool-" + count++);
            }
        });
    }

    public CompletableFuture<List<Feature>> fetchFeaturesConcurrently(List<Point> points) {
        // Map points to ListenableFuture and convert them to CompletableFutures
        List<CompletableFuture<Feature>> futures = points.stream()
            .map(point -> {
                ListenableFuture<Feature> guavaFuture = stub.getFeature(point);
                return GrpcFutureAdapter.toCompletableFuture(guavaFuture, executorPool);
            })
            .collect(Collectors.toList());

        // Aggregate all futures using CompletableFuture.allOf
        CompletableFuture<Void> allOf = CompletableFuture.allOf(
            futures.toArray(new CompletableFuture[0])
        );

        // Map when all are complete
        return allOf.thenApply(v -> 
            futures.stream()
                .map(CompletableFuture::join) // Non-blocking because allOf is done
                .collect(Collectors.toList())
        );
    }

    public void shutdown() {
        executorPool.shutdown();
    }

    public static void main(String[] args) throws Exception {
        ManagedChannel channel = ManagedChannelBuilder.forAddress("localhost", 9091)
            .usePlaintext()
            .build();

        AsyncGatewayAggregator aggregator = new AsyncGatewayAggregator(channel);

        List<Point> queryPoints = List.of(
            Point.newBuilder().setLatitude(10).setLongitude(20).build(),
            Point.newBuilder().setLatitude(30).setLongitude(40).build(),
            Point.newBuilder().setLatitude(50).setLongitude(60).build()
        );

        System.out.println("Starting concurrent fan-out fetch...");
        CompletableFuture<List<Feature>> combinedFuture = aggregator.fetchFeaturesConcurrently(queryPoints);

        // Register async completion handlers
        combinedFuture.whenComplete((features, ex) -> {
            if (ex != null) {
                System.err.println("Fan-out query failed: " + ex.getCause().getMessage());
            } else {
                System.out.println("Aggregated result size: " + features.size());
                features.forEach(f -> System.out.println(" - " + f.getName()));
            }
        });

        // Block main thread briefly to wait for execution to print
        try {
            combinedFuture.get(5, TimeUnit.SECONDS);
        } catch (TimeoutException e) {
            System.out.println("Aggregator timeout reached.");
        }

        aggregator.shutdown();
        channel.shutdown().awaitTermination(2, TimeUnit.SECONDS);
    }
}
```

---

## 7. Interview Questions

### Q1: Why does Guava’s `addCallback()` require you to supply an `Executor` argument, and what happens if you pass `MoreExecutors.directExecutor()`?
**Answer**: 
Guava requires an explicit executor to run the callback logic once the future completes. If you supply `MoreExecutors.directExecutor()`, the callback will execute **on the thread that completes the future**. 
In gRPC, the thread that completes the future is Netty’s worker EventLoop thread. If your callback code does anything blocking (like database access, sync logs, or HTTP parsing), running it on the direct executor will freeze Netty's IO processing pipeline, blocking all networking for the host process.

### Q2: How is client-side cancellation propagated backwards using the Future Stub?
**Answer**: 
If you cancel a standard Java `CompletableFuture` that is adapted from a `ListenableFuture`, you must explicitly call `listenableFuture.cancel(true)`. When this occurs, the gRPC client transport library catches the cancellation event and immediately transmits an HTTP/2 `RST_STREAM` frame (with error code `CANCEL`) to the server. This terminates the stream on the socket layer, signaling the server to abort service execution.
If you forget to propagate this cancellation from your CompletableFuture wrapper, the backend server will continue executing the request and waste resources.
