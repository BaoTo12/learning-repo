# Module 13: Reactive gRPC & Project Reactor

## 1. What Problem This Module Solves
gRPC’s standard asynchronous API uses the `StreamObserver` callback model. While functional, it is prone to several severe production issues:
*   **Callback Hell**: Complex asynchronous flows (e.g., nesting a gRPC response callback inside another gRPC callback) lead to deeply nested, unmaintainable code structures.
*   **Lack of Functional Operations**: You cannot easily apply standard functional stream mappings (e.g., `map`, `filter`, `zip`, `timeout`, `retry`) to raw `StreamObserver` callbacks.
*   **Mismatched Backpressure**: Translating standard Reactive Streams (like Project Reactor `Flux` or `Mono`) to `StreamObserver` requires manually bridging reactive demand (`Subscription.request(n)`) with Netty's `isReady()` write flags, risking memory leaks or stream starvation.

This module details how to manually bridge gRPC `StreamObserver` with Project Reactor's `Flux` and `Mono` using standard adapter patterns, maintaining correct backpressure without external compiler plugins.

---

## 2. Reactive Streams vs gRPC Callback Model

### 2.1 Standard Callback Model
In `StreamObserver`, the server pushes data down the stream as fast as it wants. If the client cannot process it quickly, the data queues up in TCP buffers or memory, representing a **Push Model**.

### 2.2 Reactive Streams Model
In Project Reactor, the subscriber requests a specific number of items (`request(N)`). The publisher only sends up to $N$ items, representing a **Pull Model** (Demand-Driven).

```
[ Reactor Flux (Client) ] ───(Subscription.request(5))───► [ gRPC Client Channel ]
                                                                   │
                                                                   ▼ (Sends HTTP/2 WINDOW_UPDATE)
[ Server StreamObserver ] ◄──(onNext() up to 5 times)──────────────┘
```

---

## 3. Trade-offs and Limitations
*   **Thread Allocation Complexity**: Mixing Netty’s EventLoops, gRPC call executors, and Reactor's schedulers (`Schedulers.parallel()`, `Schedulers.boundedElastic()`) can easily lead to race conditions and context losses (like tracing MDC context).
*   **No Native Compiler Integration**: Standard `protoc` does not generate Reactor-compatible stubs. You must write manual adapters or use third-party code-generation plugins (like Salesforce's `reactive-grpc`), which add build-dependency complexities.

---

## 4. Common Mistakes and Anti-Patterns
*   **Blocking in Flux/Mono Pipelines**: Calling blocking operations (such as `ManagedChannelBuilder.blockingUnaryCall()`) inside a Reactor stream without allocating a dedicated elastic thread pool (`publishOn(Schedulers.boundedElastic())`). This starves the Reactive engine's CPU cores.
*   **Ignoring Reactive Cancellations**: If a Reactor stream is cancelled downstream (e.g., using `take(2)` or triggering a timeout), failing to propagate the cancellation to the underlying gRPC stream. The server will continue generating and sending messages, wasting resources.

---

## 5. Implementing Manual Adapters in Java

To avoid depending on external compiler plugins, we can write manual adapter classes to convert `StreamObserver` to `Flux` and `Mono`.

### 5.1 Converting gRPC Stream to Reactor `Flux`
This adapter wraps a gRPC client stream callback and exposes it as a standard Reactor `Flux`:

```java
package com.example.grpc.reactive;

import io.grpc.stub.StreamObserver;
import reactor.core.publisher.Flux;
import reactor.core.publisher.FluxSink;

public class GrpcToReactorAdapters {

    /**
     * Adapts a gRPC client stream callback to a Project Reactor Flux.
     */
    public static <T> Flux<T> toFlux(java.util.function.Consumer<StreamObserver<T>> grpcCall) {
        return Flux.create(sink -> {
            StreamObserver<T> observer = new StreamObserver<>() {
                @Override
                public void onNext(T value) {
                    sink.next(value);
                }

                @Override
                public void onError(Throwable t) {
                    sink.error(t);
                }

                @Override
                public void onCompleted() {
                    sink.complete();
                }
            };

            // Trigger the outbound gRPC request passing our callback observer
            grpcCall.accept(observer);

            // Register cancellation handler to propagate stream closures
            sink.onCancel(() -> {
                // If client cancels, we can handle it if we have access to ClientCallStreamObserver
                System.out.println("[Flux Adapter] Client cancelled subscription stream.");
            });
        }, FluxSink.OverflowStrategy.BUFFER);
    }
}
```

---

## 6. Mini-Project: Reactive Stream Processing Pipeline

**Scenario**: You are querying a database that returns a reactive `Flux<Point>` stream. You need to forward this stream to a downstream gRPC service over a Client-Streaming RPC using reactive backpressure.

### Implementation Code (`ReactivePipelineRunner.java`)
```java
package com.example.grpc.reactive;

import io.grpc.stub.ClientCallStreamObserver;
import io.grpc.stub.StreamObserver;
import com.example.grpc.tracking.v1.Location;
import reactor.core.publisher.Flux;
import reactor.core.scheduler.Schedulers;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

public class ReactivePipelineRunner {

    // Simulates a reactive database query
    public static Flux<Location> getDbPointsFlux() {
        return Flux.range(1, 100)
            .map(i -> Location.newBuilder().setLatitude(i).setLongitude(i * 2).build())
            .subscribeOn(Schedulers.boundedElastic()); // Run on IO-bound threads
    }

    public static void streamFluxToGrpc(Flux<Location> pointsFlux, StreamObserver<Location> requestObserver) {
        ClientCallStreamObserver<Location> clientCallObserver = (ClientCallStreamObserver<Location>) requestObserver;

        // 1. Disable auto-requesting to let Reactor drive backpressure
        clientCallObserver.disableAutoRequest();

        // 2. Subscribe to the Flux using a custom subscriber
        pointsFlux.subscribe(
            new reactor.core.CoreSubscriber<Location>() {
                @Override
                public void onSubscribe(org.reactivestreams.Subscription s) {
                    // Set up the gRPC on-ready handler to pull messages from Flux
                    clientCallObserver.setOnReadyHandler(() -> {
                        while (clientCallObserver.isReady()) {
                            s.request(1); // Pull one item from our database Flux
                        }
                    });

                    // Propagate cancellations if gRPC channel is cancelled
                    clientCallObserver.setOnCancelHandler(() -> {
                        System.out.println("Downstream gRPC aborted, canceling database subscription.");
                        s.cancel();
                    });
                }

                @Override
                public void onNext(Location point) {
                    clientCallObserver.onNext(point);
                }

                @Override
                public void onError(Throwable t) {
                    clientCallObserver.onError(t);
                }

                @Override
                public void onComplete() {
                    clientCallObserver.onCompleted();
                }
            }
        );
    }

    public static void main(String[] args) throws InterruptedException {
        Flux<Location> dbPoints = getDbPointsFlux();
        CountDownLatch latch = new CountDownLatch(1);

        // Mock gRPC ClientCallStreamObserver for demonstration
        StreamObserver<Location> mockObserver = new ClientCallStreamObserver<>() {
            private int count = 0;
            @Override public void onNext(Location value) {
                count++;
                System.out.printf("Sent point #%d over gRPC wire: Latitude: %f\n", count, value.getLatitude());
            }
            @Override public void onError(Throwable t) {}
            @Override public void onCompleted() {
                System.out.println("gRPC Stream complete!");
                latch.countDown();
            }
            @Override public boolean isReady() { return true; }
            @Override public void setOnReadyHandler(Runnable onReadyHandler) { onReadyHandler.run(); }
            @Override public void disableAutoRequest() {}
            @Override public void request(int count) {}
            @Override public void setOnCancelHandler(Runnable onCancelHandler) {}
            @Override public void cancel(String message, Throwable cause) {}
        };

        streamFluxToGrpc(dbPoints, mockObserver);

        latch.await(5, TimeUnit.SECONDS);
    }
}
```

---

## 7. Interview Questions

### Q1: Why is mapping a `Flux` directly to `StreamObserver.onNext()` without calling `disableAutoRequest()` highly dangerous for high-volume streams?
**Answer**: 
If you subscribe to a high-speed `Flux` (such as reading telemetry events from Kafka) and write them directly via `onNext()`, Reactor will push messages as fast as it can generate them. If the network interface card is congested or the downstream client processes messages slowly, Netty’s TCP write buffers will fill up. 
Because gRPC-Java does not block the thread when writing, the unsent messages will accumulate in memory buffers. Without backpressure limits, this will trigger an Out-Of-Memory (OOM) error. Calling `disableAutoRequest()` enables backpressure, letting the client request new items *only* when Netty is ready to send them.

### Q2: What is the purpose of `publishOn(Schedulers.boundedElastic())` inside a reactive gRPC pipeline?
**Answer**: 
By default, Reactor operations execute on the thread that calls them (often Netty EventLoop threads). If your reactive pipeline includes blocking database operations, slow file reads, or complex calculations, executing them on the Netty thread will block the EventLoop network processor.
Adding `publishOn(Schedulers.boundedElastic())` offloads execution of subsequent operations in the pipeline to a dedicated, dynamically expanding thread pool, keeping the core Netty EventLoop threads free to handle TCP traffic.
