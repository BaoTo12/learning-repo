# Module 04: Unary, Streaming, and Bidirectional Patterns in Java

## 1. What Problem This Module Solves
Standard REST-based request-response models are severely limited when dealing with large or continuous data streams:
*   **Memory Bloat**: Downloading a 1GB dataset via a single HTTP REST response forces the entire payload into the JVM heap memory, risking Out-Of-Memory (OOM) exceptions.
*   **High Latency**: In REST, a client must wait for the entire processing run to finish before getting the first byte of response data.
*   **Inefficient Real-time Updates**: Real-time applications are forced to rely on inefficient long-polling or separate protocols like WebSockets.

gRPC solves this with native HTTP/2 stream multiplexing, supporting four communication modes: **Unary**, **Server-Streaming**, **Client-Streaming**, and **Bidirectional Streaming**, complete with flow control and backpressure capabilities.

---

## 2. Why Chosen Over REST
*   **Native Bidirectional Streams**: All four communication patterns run on a single TCP connection over HTTP/2, reducing TCP handshakes and connection overhead.
*   **True Flow Control / Backpressure**: gRPC allows the receiver to tell the sender exactly how many messages it is ready to process, preventing faster nodes from overwhelming slower nodes.
*   **Uniform API Contracts**: Streaming operations are defined exactly like normal methods in the `.proto` file.

---

## 3. Trade-offs and Limitations
*   **Load Balancing Pinning**: Long-lived streams pin a client to a single server instance. If one server receives all the streaming traffic, it will become hot while other nodes sit idle. L7 load balancing (like Envoy) or client-side load balancing is mandatory.
*   **Partial Failures**: Standard HTTP status codes do not work mid-stream. If an error occurs after sending 10 out of 100 messages, the status must be sent via trailers, requiring custom client parsing to handle partial successes.

---

## 4. Common Mistakes and Anti-Patterns
*   **Ignoring Client Cancellations**: If a client cancels a stream or times out, the server's thread loop will continue to generate and send messages, causing CPU cycles to be wasted on a closed socket.
    *   *Correction*: Cast the `StreamObserver` to `ServerCallStreamObserver` and check `isCancelled()` or use a cancellation listener.
*   **Memory Exhaustion via High-Speed Streams**: Writing to `StreamObserver.onNext()` in a rapid loop without checking if the recipient is ready. This causes outbound messages to queue up in memory buffers.
    *   *Correction*: Implement manual backpressure control using `disableAutoRequest()` and `setOnReadyHandler()`.

---

## 5. Implementing Patterns in Pure Java (No Spring)

All four streaming modes implement the core callback interface `io.grpc.stub.StreamObserver<T>`:
```java
public interface StreamObserver<V> {
    void onNext(V value);      // Invoked when a new message arrives
    void onError(Throwable t);  // Invoked when an RPC terminates with an error
    void onCompleted();        // Invoked when the sender is done sending
}
```

### 5.1 Protobuf Contract (`route_guide.proto`)
```protobuf
syntax = "proto3";
package routeguide;

option java_multiple_files = true;
option java_package = "com.example.grpc.routeguide";

message Point {
  int32 latitude = 1;
  int32 longitude = 2;
}

message Feature {
  string name = 1;
  Point location = 2;
}

message RouteSummary {
  int32 point_count = 1;
  int32 distance = 2;
}

service RouteGuide {
  // 1. Unary
  rpc GetFeature(Point) returns (Feature);

  // 2. Server-Streaming
  rpc ListFeatures(Point) returns (stream Feature);

  // 3. Client-Streaming
  rpc RecordRoute(stream Point) returns (RouteSummary);

  // 4. Bidirectional-Streaming
  rpc RouteChat(stream Feature) returns (stream Feature);
}
```

### 5.2 Server Implementations

Here is a pure Java server implementing these patterns with manual cancellation check and flow control.

```java
package com.example.grpc.routeguide;

import io.grpc.stub.ServerCallStreamObserver;
import io.grpc.stub.StreamObserver;
import java.util.concurrent.atomic.AtomicBoolean;

public class RouteGuideService extends RouteGuideGrpc.RouteGuideImplBase {

    // 1. Unary
    @Override
    public void getFeature(Point request, StreamObserver<Feature> responseObserver) {
        Feature feature = Feature.newBuilder()
            .setName("Database Feature at " + request.getLatitude())
            .setLocation(request)
            .build();
        responseObserver.onNext(feature);
        responseObserver.onCompleted();
    }

    // 2. Server-Streaming (With Cancellation Check & Graceful Handshake)
    @Override
    public void listFeatures(Point request, StreamObserver<Feature> responseObserver) {
        // Cast to low-level observer to gain cancellation insights
        ServerCallStreamObserver<Feature> serverCallObserver = 
            (ServerCallStreamObserver<Feature>) responseObserver;

        // Register cancellation callback
        serverCallObserver.setOnCancelHandler(() -> {
            System.out.println("Client cancelled the subscription stream!");
        });

        for (int i = 0; i < 100; i++) {
            if (serverCallObserver.isCancelled()) {
                System.out.println("Stopping listFeatures: client disconnected.");
                return;
            }

            Feature feature = Feature.newBuilder()
                .setName("Feature #" + i)
                .setLocation(request)
                .build();
            responseObserver.onNext(feature);

            try {
                Thread.sleep(50); // Simulate processing latency
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
        responseObserver.onCompleted();
    }

    // 3. Client-Streaming (Collect points and return a single summary)
    @Override
    public StreamObserver<Point> recordRoute(StreamObserver<RouteSummary> responseObserver) {
        return new StreamObserver<Point>() {
            private int pointCount = 0;
            private long startTime = System.nanoTime();

            @Override
            public void onNext(Point point) {
                pointCount++;
                System.out.printf("Recorded point: %d, %d\n", point.getLatitude(), point.getLongitude());
            }

            @Override
            public void onError(Throwable t) {
                System.err.println("RecordRoute error: " + t.getMessage());
            }

            @Override
            public void onCompleted() {
                long duration = TimeUnit.NANOSECONDS.toSeconds(System.nanoTime() - startTime);
                RouteSummary summary = RouteSummary.newBuilder()
                    .setPointCount(pointCount)
                    .setDistance((int) (pointCount * 10)) // Mock distance calculation
                    .build();
                responseObserver.onNext(summary);
                responseObserver.onCompleted();
            }
        };
    }

    // 4. Bidirectional Streaming (Echo chat messages with server prefix)
    @Override
    public StreamObserver<Feature> routeChat(StreamObserver<Feature> responseObserver) {
        return new StreamObserver<Feature>() {
            @Override
            public void onNext(Feature value) {
                System.out.println("Chat received: " + value.getName());
                // Instantly echo back with a modification
                Feature response = Feature.newBuilder()
                    .setName("[Server Echo] " + value.getName())
                    .setLocation(value.getLocation())
                    .build();
                responseObserver.onNext(response);
            }

            @Override
            public void onError(Throwable t) {
                System.err.println("RouteChat error: " + t.getMessage());
            }

            @Override
            public void onCompleted() {
                responseObserver.onCompleted();
            }
        };
    }
}
```

---

## 6. Advanced Flow Control & Backpressure

To prevent memory bloat, we must manually override the default auto-flow mechanism. The following project demonstrates how to set up manual backpressure.

### Mini-Project: Flow-Controlled Server Streaming in Java
```java
package com.example.grpc.routeguide;

import io.grpc.stub.ServerCallStreamObserver;
import io.grpc.stub.StreamObserver;
import java.util.Iterator;
import java.util.List;

public class BackpressureService {

    public void streamLargeDataset(List<Feature> massiveList, StreamObserver<Feature> responseObserver) {
        ServerCallStreamObserver<Feature> serverObserver = 
            (ServerCallStreamObserver<Feature>) responseObserver;

        // 1. Disable the default automatic message delivery requests
        serverObserver.disableAutoRequest();

        // 2. Obtain database or list iterator
        Iterator<Feature> iterator = massiveList.iterator();

        // 3. Set up the on-ready handler to push data only when Netty is ready to transmit
        serverObserver.setOnReadyHandler(() -> {
            while (serverObserver.isReady() && iterator.hasNext()) {
                Feature item = iterator.next();
                serverObserver.onNext(item);
            }

            if (!iterator.hasNext()) {
                serverObserver.onCompleted();
            }
        });
    }
}
```

---

## 7. Interview Questions

### Q1: What is the mechanical difference between standard gRPC streaming and WebSockets?
**Answer**: 
*   **WebSockets**: Establish connection via an HTTP/1.1 handshake, then upgrade the TCP connection to a full-duplex custom binary framing protocol. This connection cannot be shared with regular HTTP calls; it operates as an isolated socket.
*   **gRPC Streaming**: Operates entirely over standard **HTTP/2**. Unary, streaming, and metadata requests share the *same* TCP socket connection through multiplexed streams. In addition, gRPC streaming has built-in HTTP/2 window flow control (`WINDOW_UPDATE` frames) allowing fine-grained data backpressure, which WebSockets lack.

### Q2: Why is calling `disableAutoRequest()` necessary when implementing streaming APIs that fetch records from a database?
**Answer**: 
By default, gRPC-Java uses auto-requesting, meaning the runtime automatically sends message request demands to Netty, which pulls frames as fast as the network allows. If the server queries a database yielding millions of rows and writes them using `StreamObserver.onNext()`, but the client is processing them slowly, the messages will accumulate in the server's outbound JVM memory buffer. Eventually, this will trigger an Out-Of-Memory (OOM) error. Calling `disableAutoRequest()` allows you to register an `onReadyHandler` and write data *only* when Netty’s TCP write buffers have cleared (`isReady() == true`), aligning database read rates with client intake rates.
