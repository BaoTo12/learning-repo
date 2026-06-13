# Module 04: Spring Boot gRPC Communication Patterns

## 1. What Problem This Module Solves
Modern distributed systems require flexible data transfer patterns:
*   **Large Dataset Download Latency**: Fetching millions of records via a single REST HTTP request risks OOM errors on both client and server.
*   **High-Volume Upload Overhead**: Uploading files or streaming sensor data using individual HTTP POST calls incurs significant header serialization overhead.
*   **Real-time Collaboration Complexity**: Building chat or live telemetry services requires configuring complex HTTP pooling, Server-Sent Events, or separate WebSockets brokers.

gRPC solves this by providing native support for four communication modes: **Unary**, **Server-Streaming**, **Client-Streaming**, and **Bidirectional Streaming** directly over a single multiplexed HTTP/2 connection.

---

## 2. The Four Communication Modes

```
[ Unary RPC ]
Client  ───(Request)───► Server
Client  ◄──(Response)─── Server

[ Server Streaming ]
Client  ───(Request)───► Server
Client  ◄─(Msg 1..Msg N)─ Server

[ Client Streaming ]
Client  ─(Msg 1..Msg N)─► Server
Client  ◄──(Response)─── Server

[ Bidirectional Streaming ]
Client  ─(Msg 1..Msg N)─► Server
Client  ◄(Msg 1..Msg N)─ Server
```

*   **Unary**: Traditional request-response.
*   **Server-Streaming**: Client sends one request, and the server returns a stream of multiple response messages.
*   **Client-Streaming**: Client sends a stream of multiple request messages, and the server returns a single response when the client completes the stream.
*   **Bidirectional Streaming**: Client and server send streams of messages to each other concurrently.

---

## 3. Trade-offs and Limitations
*   **Sticky Session Pinning**: Long-lived streams keep TCP sockets open, pinning a client to a single server instance. Standard L4 load balancers cannot distribute requests evenly across pods under these conditions; L7 proxies (like Envoy) are required to balance traffic at the stream layer.
*   **Error Handling Complexity**: Connection drops or exceptions can occur mid-stream after partial payloads have been delivered. Standard HTTP response codes cannot represent these partial failures, requiring custom application-level error tracking.

---

## 4. Common Mistakes and Anti-Patterns
*   **Thread Leaks on Stream Cancellation**: Writing to `StreamObserver.onNext()` in a loop without checking if the client disconnected or cancelled the call. This causes server thread loops to run indefinitely, leading to CPU and memory exhaustion.
    *   *Correction*: Cast the observer to `ServerCallStreamObserver` and monitor the `isCancelled()` status.
*   **Blocking inside `onNext` callbacks**: Performing heavy computation or database calls directly inside the `StreamObserver` callback methods. This blocks Netty’s worker threads, stalling network processing. Offload execution to a separate application thread pool.

---

## 5. Implementing Patterns in Spring Boot

Let's build a real-time tracking service mapping all four modes.

### 5.1 Protobuf Contract (`route_tracker.proto`)
```protobuf
syntax = "proto3";
package api.tracking.v1;

option java_multiple_files = true;
option java_package = "com.example.grpc.tracking.v1";

message Location {
  double latitude = 1;
  double longitude = 2;
}

message StatusUpdate {
  string message = 1;
}

message TravelSummary {
  int32 point_count = 1;
  double total_distance = 2;
}

service RouteTrackerService {
  rpc PingLocation(Location) returns (StatusUpdate);
  rpc StreamLocations(StatusUpdate) returns (stream Location);
  rpc RecordRoute(stream Location) returns (TravelSummary);
  rpc InteractiveChat(stream StatusUpdate) returns (stream StatusUpdate);
}
```

---

### 5.2 Server Implementation (`RouteTrackerServiceImpl.java`)
```java
package com.example.grpc.tracking;

import com.example.grpc.tracking.v1.*;
import io.grpc.stub.ServerCallStreamObserver;
import io.grpc.stub.StreamObserver;
import net.devh.boot.grpc.server.service.GrpcService;

@GrpcService
public class RouteTrackerServiceImpl extends RouteTrackerServiceGrpc.RouteTrackerServiceImplBase {

    // 1. Unary
    @Override
    public void pingLocation(Location request, StreamObserver<StatusUpdate> responseObserver) {
        StatusUpdate update = StatusUpdate.newBuilder()
            .setMessage("Location acknowledged: " + request.getLatitude())
            .build();
        responseObserver.onNext(update);
        responseObserver.onCompleted();
    }

    // 2. Server-Streaming (Checking for client cancellations)
    @Override
    public void streamLocations(StatusUpdate request, StreamObserver<Location> responseObserver) {
        ServerCallStreamObserver<Location> serverObserver = 
            (ServerCallStreamObserver<Location>) responseObserver;

        // Register cancellation callback
        serverObserver.setOnCancelHandler(() -> System.out.println("Client cancelled location stream."));

        for (int i = 0; i < 50; i++) {
            if (serverObserver.isCancelled()) {
                System.out.println("Stopping stream, client has disconnected.");
                return;
            }

            Location loc = Location.newBuilder()
                .setLatitude(40.7128 + (i * 0.001))
                .setLongitude(-74.0060 - (i * 0.001))
                .build();
            responseObserver.onNext(loc);

            try {
                Thread.sleep(100); // Simulate coordinate updates
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
        responseObserver.onCompleted();
    }

    // 3. Client-Streaming
    @Override
    public StreamObserver<Location> recordRoute(StreamObserver<TravelSummary> responseObserver) {
        return new StreamObserver<Location>() {
            private int points = 0;

            @Override
            public void onNext(Location value) {
                points++;
                System.out.printf("Received location: Lat=%f\n", value.getLatitude());
            }

            @Override
            public void onError(Throwable t) {
                System.err.println("Client stream error: " + t.getMessage());
            }

            @Override
            public void onCompleted() {
                // Client has finished uploading coordinates. Return single summary.
                TravelSummary summary = TravelSummary.newBuilder()
                    .setPointCount(points)
                    .setTotalDistance(points * 1.5)
                    .build();
                responseObserver.onNext(summary);
                responseObserver.onCompleted();
            }
        };
    }

    // 4. Bidirectional Streaming
    @Override
    public StreamObserver<StatusUpdate> interactiveChat(StreamObserver<StatusUpdate> responseObserver) {
        return new StreamObserver<StatusUpdate>() {
            @Override
            public void onNext(StatusUpdate value) {
                System.out.println("Chat message received: " + value.getMessage());
                
                // Instantly echo back with a modification
                StatusUpdate reply = StatusUpdate.newBuilder()
                    .setMessage("[Echo] " + value.getMessage())
                    .build();
                responseObserver.onNext(reply);
            }

            @Override
            public void onError(Throwable t) {
                System.err.println("Bidi stream error: " + t.getMessage());
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

## 6. Interview Questions

### Q1: What happens mechanically at the HTTP/2 frame layer when a client cancels a running stream? How does gRPC-Java handle this?
**Answer**: 
*   **HTTP/2 layer**: The client immediately sends an `RST_STREAM` frame with the error code `CANCEL` (`0x08`) to the server.
*   **gRPC-Java layer**: Netty intercepts the `RST_STREAM` frame and cancels the corresponding gRPC context. If the server is executing a loop in a separate worker thread, this thread does not stop automatically. The application logic must check `ServerCallStreamObserver.isCancelled()` periodically or register a handler via `setOnCancelHandler()` to abort execution, preventing CPU and thread leaks.

### Q2: Why is the Client-Streaming pattern more efficient than making multiple concurrent Unary RPC calls to upload logs or metrics?
**Answer**: 
For each Unary RPC call, the client must initiate a new HTTP/2 stream, which transmits request headers (`HEADERS` frame) containing metadata (authorization tokens, tracing contexts, etc.).
With Client-Streaming, headers are sent **once** to establish the stream. Subsequent log payloads are sent as raw HTTP/2 `DATA` frames, which contain no metadata overhead. This reduces CPU serialization usage, minimizes network packet sizes, and increases ingestion throughput.
