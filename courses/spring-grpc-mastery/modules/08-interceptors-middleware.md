# Module 08: Interceptors & Metadata in Spring

## 1. What Problem This Module Solves
Microservices require structured logging, tracing, auditing, and metric collection:
*   **Boilerplate Pollution**: Manually adding logging, timing, and security logic into every business service method.
*   **Context Loss**: In Spring Boot, as requests move across thread pools, standard thread-local contexts (like tracing MDC maps) are lost, resulting in disconnected trace outputs.

gRPC solves this using **Interceptors** (conceptual siblings of servlet filters). In Spring Boot, these interceptors can be registered as standard beans, allowing access to application configurations and dependencies.

---

## 2. Server & Client Interceptor Pipelines

```
  [ Outbound Client Call ]
             │
             ▼ (ClientInterceptor - Injects request Metadata)
   [ Downstream Network ]
             │
             ▼ (ServerInterceptor - Extracts Metadata & binds Context)
  [ Inbound Server Service ]
```

*   **ServerInterceptor**: Intercepts incoming requests before they reach the `@GrpcService` implementation.
*   **ClientInterceptor**: Intercepts outgoing client requests before they are written to the network.

---

## 3. Registering Interceptors as Spring Beans

In Spring Boot, any class implementing `ServerInterceptor` annotated with `@GrpcGlobalServerInterceptor` (or `@GrpcGlobalClientInterceptor` for client interceptors) is dynamically detected and added to the execution pipeline.

### 3.1 Global Server Logging Interceptor
```java
package com.example.grpc.interceptors;

import io.grpc.*;
import net.devh.boot.grpc.server.interceptor.GrpcGlobalServerInterceptor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.annotation.Order;

@Order(1) // Define execution order
@GrpcGlobalServerInterceptor
public class ServerLoggingInterceptor implements ServerInterceptor {

    private static final Logger log = LoggerFactory.getLogger(ServerLoggingInterceptor.class);

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerMethodDefinition<ReqT, RespT> next) {

        long startTime = System.currentTimeMillis();
        String methodName = call.getMethodDescriptor().getFullMethodName();

        log.info("[Server Interceptor] Incoming Call: {}", methodName);

        // Forward call, intercepting closure to log execution time
        return next.startCall(
            new ForwardingServerCall.SimpleForwardingServerCall<ReqT, RespT>(call) {
                @Override
                public void close(Status status, Metadata trailers) {
                    long duration = System.currentTimeMillis() - startTime;
                    log.info("[Server Interceptor] Completed Call: {} | Status: {} | Duration: {}ms", 
                        methodName, status.getCode(), duration);
                    super.close(status, trailers);
                }
            }, headers
        );
    }
}
```

---

### 3.2 Global Client Context Injection Interceptor
```java
package com.example.grpc.interceptors;

import io.grpc.*;
import net.devh.boot.grpc.client.interceptor.GrpcGlobalClientInterceptor;
import org.springframework.core.annotation.Order;
import java.util.UUID;

@Order(1)
@GrpcGlobalClientInterceptor
public class ClientTracingInterceptor implements ClientInterceptor {

    private static final Metadata.Key<String> CORRELATION_KEY = Metadata.Key.of(
        "x-correlation-id", Metadata.ASCII_STRING_MARSHALLER
    );

    @Override
    public <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
            MethodDescriptor<ReqT, RespT> method,
            CallOptions callOptions,
            Channel next) {

        return new ForwardingClientCall.SimpleForwardingClientCall<ReqT, RespT>(next.newCall(method, callOptions)) {
            @Override
            public void start(Listener<RespT> responseListener, Metadata headers) {
                // Generate and inject a unique transaction identifier
                String correlationId = UUID.randomUUID().toString();
                headers.put(CORRELATION_KEY, correlationId);
                super.start(responseListener, headers);
            }
        };
    }
}
```

---

## 4. Setting Interceptor Ordering

When using multiple interceptors (e.g. Logging, Security, and Metrics), execution order is critical. You configure this in Spring using:
*   **`@Order` Annotation**: Specifies precedence (lower values run first).
*   **Properties Configuration**: Setting order properties directly inside `application.yml`.

If Security is ordered *before* Logging, and validation fails, the logging interceptor will never receive the completion call. Keep logging and distributed tracing ordered first.

---

## 5. Common Mistakes and Anti-Patterns
*   **Executing Blocking Logic inside interceptCall()**: Performing database validation queries directly inside the main body of `interceptCall()`. This blocks the Netty thread.
    *   *Correction*: Perform validation checks inside the returned listener methods, offloading them to application thread pools.
*   **Swallowing Exceptions**: Catching exceptions inside interceptors and closing calls with `Status.OK` while returning incomplete payloads. Always propagate failures using `call.close(Status.INTERNAL, ...)` to ensure the client is notified.

---

## 6. Interview Questions

### Q1: What is the mechanical difference between a ServerInterceptor's `interceptCall` method and the methods of the returned `ServerCall.Listener` object?
**Answer**: 
*   `interceptCall()`: Executes once when the RPC is first established, before any request payloads are read. It is used to parse initial request metadata (headers), inject context variables, or validate credentials.
*   `ServerCall.Listener` methods (like `onMessage()` or `onHalfClose()`): Are event-driven callbacks. They execute as raw request packets arrive from the network. If the call is Client-Streaming or Bidirectional, `onMessage()` executes multiple times (once per incoming frame), allowing you to validate individual request objects.

### Q2: Why will Spring's standard `@RequestScope` bean injection fail inside a `@GrpcService` or custom gRPC interceptor?
**Answer**: 
Spring's `@RequestScope` is bound to HTTP servlets and maps dynamically to Spring MVC thread-local storage (`RequestContextHolder`). 
gRPC-Java runs on Netty EventLoops. It operates independently of standard Servlet Containers (like Tomcat) and handles requests over multiplexed streams on shared socket channels. Thus, servlet thread-local maps are empty. To share request-scoped data in gRPC, you must use `io.grpc.Context` variables instead.
