# Module 06: Error Handling, Resilience & Exception Mapping

## 1. What Problem This Module Solves
When a gRPC service throws a standard Java runtime exception (such as `NullPointerException` or `IllegalArgumentException`), the server catches it and returns a generic `codes.UNKNOWN` error status to the client, concealing the cause.
Additionally, in distributed systems:
*   **Cascading Failures**: If Service A calls Service B, and Service B hangs, Service A will exhaust its threads waiting for responses.
*   **Lack of Structured Metadata**: Raw string error messages are hard for clients to parse programmatically (e.g., indicating which input field failed validation).

This module explains how to implement global exception interceptors, return the Google Rich Error model, enforce client timeouts/deadline propagation, and implement manual circuit breakers using the raw Resilience4j Java API.

---

## 2. Status Space: REST vs gRPC
*   **REST**: Uses HTTP status codes ($100-599$), which are often configured inconsistently across services (e.g., returning 200 OK with error bodies, or mixing up 401 Unauthorized vs 403 Forbidden).
*   **gRPC**: Enforces a strict set of 16 status codes (e.g., `INVALID_ARGUMENT`, `NOT_FOUND`, `ALREADY_EXISTS`, `PERMISSION_DENIED`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`). These codes are supported uniformly across all gRPC language runtimes.

---

## 3. The Google Rich Error Model
The standard gRPC status code and string description are often insufficient for complex APIs. Google defines a rich error model using a protobuf structure (`google.rpc.Status`):

```protobuf
message Status {
  int32 code = 1;        // The Status enum integer
  string message = 2;    // Developer-facing error message
  repeated google.protobuf.Any details = 3; // Arbitrary payload attachments
}
```

This allows servers to attach structured metadata, such as:
*   `BadRequest`: Specifies field-level validation failures.
*   `QuotaFailure`: Explains what rate limits were hit.
*   `ErrorInfo`: Returns structured dictionary data.

---

## 4. Common Mistakes and Anti-Patterns
*   **Leaking Database Stack Traces**: Catching SQL exceptions and passing the raw message (which contains table names, schema info, or internal IPs) directly into the error description. This presents a major security risk.
*   **Starving Callers via Missing Deadlines**: Failing to set timeouts on client stubs. If a downstream service hangs, the client thread remains occupied indefinitely, causing upstream thread exhaustion.
*   **Catching Throwable in Interceptors**: Swallowing all errors including JVM fatal errors (like `OutOfMemoryError`). Interceptors should only handle subclasses of `Exception`.

---

## 5. Global Exception Mapping using Server Interceptors

In pure Java, you implement a `ServerInterceptor` to capture service exceptions before they escape to Netty.

```java
package com.example.grpc.errors;

import io.grpc.*;
import io.grpc.protobuf.StatusProto;
import com.google.rpc.BadRequest;
import com.google.rpc.FieldViolation;

public class GlobalExceptionInterceptor implements ServerInterceptor {

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerMethodDefinition<ReqT, RespT> next) {

        // Wrap the call listener to catch exceptions during processing
        ServerCall.Listener<ReqT> delegate = next.startCall(call, headers);

        return new ForwardingServerCallListener.SimpleForwardingServerCallListener<ReqT>(delegate) {
            @Override
            public void onMessage(ReqT message) {
                try {
                    super.onMessage(message);
                } catch (Throwable t) {
                    handleException(call, t);
                }
            }

            @Override
            public void onHalfClose() {
                try {
                    super.onHalfClose();
                } catch (Throwable t) {
                    handleException(call, t);
                }
            }
        };
    }

    private <ReqT, RespT> void handleException(ServerCall<ReqT, RespT> call, Throwable t) {
        StatusRuntimeException exception;

        if (t instanceof IllegalArgumentException) {
            // 1. Construct rich error status for validation failure
            BadRequest badRequest = BadRequest.newBuilder()
                .addFieldViolations(FieldViolation.newBuilder()
                    .setField("user_id")
                    .setDescription("User ID must be numeric and positive")
                    .build())
                .build();

            com.google.rpc.Status status = com.google.rpc.Status.newBuilder()
                .setCode(Status.Code.INVALID_ARGUMENT.value())
                .setMessage("Invalid request payload parameters: " + t.getMessage())
                .addDetails(com.google.protobuf.Any.pack(badRequest))
                .build();

            exception = StatusProto.toStatusRuntimeException(status);
        } else {
            // Generic unknown translation to protect internal mechanics
            exception = Status.INTERNAL
                .withDescription("An unexpected error occurred in the service layer")
                .withCause(t)
                .asRuntimeException();
        }

        // Close the call with the formatted exception
        call.close(exception.getStatus(), exception.getTrailers());
    }
}
```

---

## 6. Deadline Propagation in Java

Unlike standard REST timeouts, gRPC uses **Deadlines**. A client sets an absolute expiration time. The gRPC client stub propagates this value down the entire microservice call chain.

```java
// Client calls Service A with a 500ms deadline
UserServiceBlockingStub stub = UserServiceGrpc.newBlockingStub(channel)
    .withDeadlineAfter(500, TimeUnit.MILLISECONDS);
```

If Service A queries Service B, the gRPC runtime automatically forwards the *remaining* time window to Service B. If 200ms were consumed in A, B receives a deadline of 300ms. If B detects that the deadline is already expired, it aborts execution immediately, preventing wasted work.

---

## 7. Resilience with Resilience4j (Manual Client Wrap)

In pure Java, you wrap your stub calls using Resilience4j's core functional API:

```java
package com.example.grpc.errors;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.grpc.ManagedChannel;
import io.grpc.StatusRuntimeException;
import com.example.grpc.routeguide.Point;
import com.example.grpc.routeguide.Feature;
import com.example.grpc.routeguide.RouteGuideGrpc;
import com.example.grpc.routeguide.RouteGuideGrpc.RouteGuideBlockingStub;

import java.time.Duration;
import java.util.concurrent.Callable;

public class ResilientClientExecutor {

    private final RouteGuideBlockingStub stub;
    private final CircuitBreaker circuitBreaker;

    public ResilientClientExecutor(ManagedChannel channel) {
        this.stub = RouteGuideGrpc.newBlockingStub(channel);

        // Define Circuit Breaker Configuration manually
        CircuitBreakerConfig config = CircuitBreakerConfig.custom()
            .failureRateThreshold(50) // Open circuit if 50% calls fail
            .waitDurationInOpenState(Duration.ofSeconds(5))
            .slidingWindowSize(10)
            .recordExceptions(StatusRuntimeException.class) // Monitor gRPC network/internal failures
            .build();

        this.circuitBreaker = CircuitBreaker.of("routeGuideService", config);
    }

    public Feature getFeatureResiliently(Point point) {
        Callable<Feature> callable = CircuitBreaker.decorateCallable(circuitBreaker, () -> stub.getFeature(point));
        
        try {
            return callable.call();
        } catch (Exception e) {
            System.err.println("Circuit Breaker blocked call or request failed: " + e.getMessage());
            // Return fallback feature in case of failure or open circuit
            return Feature.newBuilder().setName("Fallback Static Location").build();
        }
    }
}
```

---

## 8. Interview Questions

### Q1: What is the difference between `Status.withDescription()` and mapping via `StatusProto.toStatusRuntimeException()`?
**Answer**: 
*   `Status.withDescription()` is part of the standard core gRPC library. It only supports returning a single standard enum code (e.g. `INVALID_ARGUMENT`) and a textual description string over the HTTP/2 headers/trailers.
*   `StatusProto.toStatusRuntimeException()` is part of the Google Rich Error Model. It serializes a complete protobuf `google.rpc.Status` message, allowing you to attach metadata payloads (such as custom error envelopes, field violations, or audit records) packed as `Any` objects. The client can unpack these details programmatically to determine the exact cause of failure.

### Q2: How does a downstream service detect that its parent deadline has expired, and why is this useful?
**Answer**: 
When a client sets a deadline, gRPC transmits a `grpc-timeout` header containing the timeout duration. Each downstream node subtracts its execution elapsed time and updates this header for subsequent downstream calls.
A downstream service can check if the deadline has passed by calling `Context.current().getDeadline().isExpired()`. If true, the service should immediately halt database transactions, file streams, or computations, avoiding unnecessary utilization of resources for a request that the client has already abandoned.
