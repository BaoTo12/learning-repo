# Module 08: Interceptors & Metadata Handling in Java

## 1. What Problem This Module Solves
In a microservice mesh, cross-cutting concerns (like distributed tracing correlation IDs, auth tokens, rate limits, and audit logs) should not be manually injected into every service method.
*   **Boilerplate Pollution**: Manually adding metadata parameters to every API method dirties service signatures.
*   **Context Loss**: In Java, asynchronous executions jump from Netty thread pools to application thread pools. Standard `ThreadLocal` storage loses its context during these thread hops, causing logs to lose tracing correlation IDs.

gRPC solves this using **Interceptors** (analogous to servlet filters) and **`io.grpc.Context`** (a thread-safe, hierarchical storage scope that can be propagated across thread boundaries).

---

## 2. Metadata: Headers and Trailers
In HTTP/2, gRPC transmits metadata via two header blocks:
1.  **Headers (Request/Response)**: Transmitted as HTTP/2 HEADERS at the beginning of the call.
2.  **Trailers (Response-only)**: Transmitted as HTTP/2 HEADERS at the end of the data stream, marked with the `END_STREAM` flag. Trailers contain the final gRPC status code and any downstream execution statistics.

---

## 3. The `io.grpc.Context` Model
`io.grpc.Context` is an immutable, hierarchical key-value container. It handles context propagation within a single thread and across network calls.

```
[ Thread 1: Netty Worker ]
Context.current() -> contains Trace ID "XYZ"
       │
       ▼ (Submits task to Executor Service)
[ Thread 2: Application Thread ]
- By default, ThreadLocal context is empty.
- Fix: wrap the task: Context.current().wrap(Runnable)
- Now Thread 2 has Trace ID "XYZ"
```

---

## 4. Common Mistakes and Anti-Patterns
*   **Direct Modification of Context**: Context is immutable. You cannot write `Context.current().put(...)`. You must instantiate a new context using `.withValue(...)` and bind/run within that new context.
*   **Forgetting to Close Scopes**: If you attach a context manually using `Context.attach()`, you must detach it in a `finally` block using `Context.detach()`. Failing to detach will leak context values into the shared thread pool, corrupting subsequent tasks.
*   **Using Complex Metadata Keys**: Using non-ASCII keys in Metadata without appending `-bin`. Binary metadata keys **must** end with `-bin` (e.g., `audit-record-bin`) to signal gRPC to Base64 encode the values on the wire.

---

## 5. Implementing Client and Server Interceptors

Let's build a distributed tracing mechanism using pure Java interceptors.

### 5.1 Client Interceptor: Inject Trace ID
```java
package com.example.grpc.interceptors;

import io.grpc.*;
import java.util.UUID;

public class ClientTracingInterceptor implements ClientInterceptor {

    public static final Metadata.Key<String> TRACE_ID_KEY = Metadata.Key.of(
        "x-trace-id", Metadata.ASCII_STRING_MARSHALLER
    );

    @Override
    public <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
            MethodDescriptor<ReqT, RespT> method,
            CallOptions callOptions,
            Channel next) {

        return new ForwardingClientCall.SimpleForwardingClientCall<ReqT, RespT>(next.newCall(method, callOptions)) {
            @Override
            public void start(Listener<RespT> responseListener, Metadata headers) {
                // Generate and inject tracing correlation ID into outbound headers
                String traceId = UUID.randomUUID().toString();
                headers.put(TRACE_ID_KEY, traceId);
                System.out.println("[Client Interceptor] Injected Trace ID: " + traceId);

                super.start(responseListener, headers);
            }
        };
    }
}
```

---

### 5.2 Server Interceptor: Capture Trace ID & Bind to Context
```java
package com.example.grpc.interceptors;

import io.grpc.*;

public class ServerTracingInterceptor implements ServerInterceptor {

    private static final Metadata.Key<String> TRACE_ID_KEY = Metadata.Key.of(
        "x-trace-id", Metadata.ASCII_STRING_MARSHALLER
    );

    // Thread-safe Context Key to hold trace ID
    public static final Context.Key<String> CONTEXT_TRACE_ID = Context.key("context-trace-id");

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerMethodDefinition<ReqT, RespT> next) {

        String traceId = headers.get(TRACE_ID_KEY);
        if (traceId == null) {
            traceId = "generated-" + java.util.UUID.randomUUID();
        }

        System.out.println("[Server Interceptor] Extracted Trace ID: " + traceId);

        // Bind tracing identity to a new Context child node
        Context context = Context.current().withValue(CONTEXT_TRACE_ID, traceId);

        // Execute downstream service methods under this context
        return Contexts.interceptCall(context, call, headers, next);
    }
}
```

---

## 6. Thread-Safe Context Propagation across Executors

When you delegate work from a gRPC service thread to a custom executor pool, the thread-local state is lost. You must manually wrap the runnable tasks.

```java
package com.example.grpc.interceptors;

import io.grpc.Context;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ContextWorkerThread {

    private final ExecutorService executor = Executors.newFixedThreadPool(2);

    public void processAsynchronously() {
        // Assume context contains trace ID "correlation-123"
        Context currentContext = Context.current();

        // Wrap task to capture the current thread's context and inject it into the worker thread
        Runnable task = currentContext.wrap(() -> {
            String traceId = ServerTracingInterceptor.CONTEXT_TRACE_ID.get();
            System.out.printf("[%s] Running async task. Extracted Trace ID: %s\n", 
                Thread.currentThread().getName(), traceId);
        });

        executor.submit(task);
    }

    public void shutdown() {
        executor.shutdown();
    }
}
```

---

## 7. Mini-Project: Header-Trailer Correlation Diagnostic Tool
Create a client-server simulation that generates a transaction identifier, sends it in headers, reads it on the server, logs it, and returns a processed trailer back to the client.

### Complete Sandbox Runner (`CorrelationSandbox.java`)
```java
package com.example.grpc.interceptors;

import io.grpc.*;
import io.grpc.stub.StreamObserver;
import java.io.IOException;
import java.util.concurrent.TimeUnit;

public class CorrelationSandbox {

    private static final Metadata.Key<String> CLIENT_SENT_KEY = Metadata.Key.of("client-sent-bin", Metadata.BINARY_MARSHALLER);
    private static final Metadata.Key<String> SERVER_RETURNED_KEY = Metadata.Key.of("server-returned-bin", Metadata.BINARY_MARSHALLER);

    // Mock Service
    public static class EchoService extends io.grpc.BindableService {
        @Override
        public ServerServiceDefinition bindService() {
            return ServerServiceDefinition.builder("EchoService")
                .addMethod(
                    MethodDescriptor.<String, String>newBuilder()
                        .setType(MethodDescriptor.MethodType.UNARY)
                        .setFullMethodName("EchoService/Echo")
                        .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                            com.google.protobuf.StringValue.getDefaultInstance()))
                        .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                            com.google.protobuf.StringValue.getDefaultInstance()))
                        .build(),
                    ServerCalls.asyncUnaryCall((request, responseObserver) -> {
                        // Return response
                        responseObserver.onNext(request);
                        responseObserver.onCompleted();
                    })
                ).build();
        }
    }

    // Server interceptor sending trailers
    public static class TrailerServerInterceptor implements ServerInterceptor {
        @Override
        public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
                ServerCall<ReqT, RespT> call,
                Metadata headers,
                ServerMethodDefinition<ReqT, RespT> next) {

            // Read client's binary header
            byte[] clientBytes = headers.get(Metadata.Key.of("client-sent-bin", Metadata.BINARY_MARSHALLER));
            String clientVal = clientBytes != null ? new String(clientBytes) : "none";
            System.out.println("Server read client metadata: " + clientVal);

            // Forward call, intercepting close to append trailers
            return next.startCall(new ForwardingServerCall.SimpleForwardingServerCall<ReqT, RespT>(call) {
                @Override
                public void close(Status status, Metadata trailers) {
                    trailers.put(SERVER_RETURNED_KEY, "Acknowledged: " + clientVal);
                    super.close(status, trailers);
                }
            }, headers);
        }
    }

    public static void main(String[] args) throws IOException, InterruptedException {
        // Start Server
        Server server = ServerBuilder.forPort(9093)
            .addService(ServerInterceptors.intercept(new EchoService(), new TrailerServerInterceptor()))
            .build().start();

        // Start Client Channel with client interceptor
        ClientInterceptor clientInterceptor = new ClientInterceptor() {
            @Override
            public <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
                    MethodDescriptor<ReqT, RespT> method, CallOptions callOptions, Channel next) {
                return new ForwardingClientCall.SimpleForwardingClientCall<ReqT, RespT>(next.newCall(method, callOptions)) {
                    @Override
                    public void start(Listener<RespT> responseListener, Metadata headers) {
                        headers.put(CLIENT_SENT_KEY, "Transaction-ID-9999");
                        super.start(new ForwardingClientCallListener.SimpleForwardingClientCallListener<RespT>(responseListener) {
                            @Override
                            public void onClose(Status status, Metadata trailers) {
                                byte[] serverBytes = trailers.get(SERVER_RETURNED_KEY);
                                String serverVal = serverBytes != null ? new String(serverBytes) : "none";
                                System.out.println("Client read server trailer: " + serverVal);
                                super.onClose(status, trailers);
                            }
                        }, headers);
                    }
                };
            }
        };

        ManagedChannel channel = ManagedChannelBuilder.forAddress("localhost", 9093)
            .usePlaintext()
            .intercept(clientInterceptor)
            .build();

        // Execute Unary Call
        io.grpc.stub.ClientCalls.blockingUnaryCall(
            channel,
            channel.newCall(
                MethodDescriptor.<com.google.protobuf.StringValue, com.google.protobuf.StringValue>newBuilder()
                    .setType(MethodDescriptor.MethodType.UNARY)
                    .setFullMethodName("EchoService/Echo")
                    .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                        com.google.protobuf.StringValue.getDefaultInstance()))
                    .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                        com.google.protobuf.StringValue.getDefaultInstance()))
                    .build(),
                CallOptions.DEFAULT
            ),
            com.google.protobuf.StringValue.newBuilder().setValue("Ping").build()
        );

        channel.shutdown().awaitTermination(2, TimeUnit.SECONDS);
        server.shutdown().awaitTermination(2, TimeUnit.SECONDS);
    }
}
```

---

## 8. Interview Questions

### Q1: What is the difference between Metadata headers and trailers in gRPC? When should you use trailers?
**Answer**: 
*   **Headers**: Sent at the very beginning of the RPC call before any payload messages are transmitted. They are used for authentication tokens, routing parameters, and tracing correlation IDs.
*   **Trailers**: Sent at the very end of the RPC call, after all message payloads have been serialized and pushed down the socket. Trailers are used to send the final RPC status and any metadata generated during execution (like database row update metrics, rate limit updates, or detailed error objects).
You must use trailers whenever the metadata value depends on executing the RPC logic (e.g. error violations, execution times, resource usages).

### Q2: Why will a standard `ThreadLocal` variable fail to propagate inside a gRPC service method when using asynchronous stubs or custom executors? How does `io.grpc.Context` solve this?
**Answer**: 
`ThreadLocal` ties variable scopes to the physical CPU execution thread. When a gRPC service calls asynchronous stubs or offloads database queries to a thread pool, execution leaps onto a new worker thread. The new thread does not inherit the parent thread's `ThreadLocal` memory.
`io.grpc.Context` solves this by decoupling context storage from the physical thread stack. It represents an immutable tree scope. By using helper methods like `context.wrap(Runnable)` or `Context.current().withValue()`, developers can explicitly attach and serialize the context values across threads and executors, ensuring tracing IDs remain correlated throughout the lifecycle of the request.
