# Module 06: Error Handling and Reliability in Spring Boot

## 1. What Problem This Module Solves
In a distributed microservice topology, failures are inevitable:
*   **Obfuscated Failures**: By default, unhandled JVM exceptions thrown inside a gRPC service are caught by Netty and returned to the client as a generic `Status.UNKNOWN` error, hiding the root cause.
*   **Cascading Slowdowns**: If Service A calls Service B, and Service B hangs due to database locks, Service A's threads will block, eventually exhausting resources and bringing down the gateway.
*   **Transient Blips**: Temporary network glitches or pod restarts can cause requests to fail. Without retry loops, these transient errors impact end-users directly.

This module details how to use Spring Boot's declarative `@GrpcAdvice` annotations to build clean error responses, propagate timeouts, and deploy Resilience4j circuit breakers on client stubs.

---

## 2. Spring Declarative Global Exception Handling (`@GrpcAdvice`)

Similar to Spring MVC's `@ControllerAdvice`, the Spring gRPC starter provides the `@GrpcAdvice` container to catch runtime exceptions and map them to strict gRPC status codes:

```java
package com.example.grpc.errors;

import io.grpc.Status;
import io.grpc.StatusRuntimeException;
import net.devh.boot.grpc.server.advice.GrpcAdvice;
import net.devh.boot.grpc.server.advice.GrpcExceptionHandler;

@GrpcAdvice
public class GlobalExceptionHandler {

    // Catch standard IllegalArgumentExceptions and map them to INVALID_ARGUMENT
    @GrpcExceptionHandler(IllegalArgumentException.class)
    public Status handleIllegalArgument(IllegalArgumentException ex) {
        return Status.INVALID_ARGUMENT
            .withDescription("Invalid request parameter: " + ex.getMessage())
            .withCause(ex);
    }

    // Catch custom Business exceptions and return StatusRuntimeException
    @GrpcExceptionHandler(UserNotFoundException.class)
    public StatusRuntimeException handleUserNotFound(UserNotFoundException ex) {
        return Status.NOT_FOUND
            .withDescription(ex.getMessage())
            .asRuntimeException();
    }
}
```

---

## 3. Deadline Propagation in Spring

gRPC uses **Deadlines** rather than simple static timeouts. A client specifies an absolute time limit. The gRPC client stub propagates this value down the entire microservice execution chain automatically.

```java
// Set a 1-second deadline on the initial gateway call
UserResponse response = userStub
    .withDeadlineAfter(1, TimeUnit.SECONDS)
    .getUser(request);
```

If the request reaches Service A, and takes 600ms, the client runtime automatically updates the deadline header to 400ms before calling Service B. If the deadline expires at any node, the call terminates immediately, freeing up execution threads.

---

## 4. Resilience4j Circuit Breakers in Spring Boot

To protect your system from downstream slow services, configure a **Resilience4j Circuit Breaker** around the stub calls.

### 4.1 Configuration (`application.yml`)
```yaml
resilience4j:
  circuitbreaker:
    instances:
      userService:
        sliding-window-size: 10
        failure-rate-threshold: 50
        wait-duration-in-open-state: 10000 # Wait 10s before retrying
        record-exceptions:
          - io.grpc.StatusRuntimeException
```

### 4.2 Client Service Integration
```java
package com.example.grpc.errors;

import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import com.example.grpc.user.v1.UserProfile;
import com.example.grpc.user.v1.UserRequest;
import com.example.grpc.user.v1.UserServiceGrpc.UserServiceBlockingStub;
import net.devh.boot.grpc.client.inject.GrpcClient;
import org.springframework.stereotype.Service;

@Service
public class ResilientUserClient {

    @GrpcClient("user-service")
    private UserServiceBlockingStub userStub;

    @CircuitBreaker(name = "userService", fallbackMethod = "getUserFallback")
    public UserProfile getUserProfile(int userId) {
        UserRequest request = UserRequest.newBuilder().setUserId(userId).build();
        return userStub.getUser(request);
    }

    // Executed when the circuit breaker is open or calls fail
    public UserProfile getUserFallback(int userId, Throwable t) {
        System.err.println("Circuit Breaker Active! Fallback triggered: " + t.getMessage());
        return UserProfile.newBuilder()
            .setUserId(userId)
            .setEmail("fallback-user@example.com")
            .build();
    }
}
```

---

## 5. Common Mistakes and Anti-Patterns
*   **Swallowing Deadlines**: Catching `StatusRuntimeException` inside intermediate services and returning an empty response body instead of propagating the failure. This prevents the parent gateway from discovering that the request timed out.
*   **Mapping Unchecked Exceptions to generic Status.INTERNAL**: Returning generic internal server errors for validation faults (like checking if username is empty). Always use specific error codes (like `INVALID_ARGUMENT`) so clients can correct the inputs.

---

## 6. Interview Questions

### Q1: What is the mechanical difference between a Timeout and a gRPC Deadline?
**Answer**: 
*   **Timeout**: Is relative (e.g. "wait 500ms on this request"). If Service A has a 500ms timeout, and Service B has a 500ms timeout, and Service A takes 450ms before calling Service B, Service B will still wait another 500ms. This results in the client timing out while downstream services continue executing tasks.
*   **gRPC Deadline**: Is absolute (e.g., "complete this entire request by 10:15:30.500"). The deadline is serialized and passed in the headers. Each service checks the remaining time against the absolute deadline. If the time has expired, downstream services abort execution immediately, preventing wasted resources.

### Q2: Why is combining Resilience4j Circuit Breakers with gRPC stubs critical for microservice thread health?
**Answer**: 
gRPC clients use channels that manage sockets. If a downstream service is experiencing extreme latency (e.g. database locks), the client stub calls will block. Without a circuit breaker, client thread pools (like Tomcat servlet threads or application executors) will quickly saturate waiting for these blocked sockets to respond. 
A circuit breaker monitors failures, opens when the error rate exceeds the threshold, and short-circuits subsequent requests immediately by returning a fallback response without making network calls, preserving client thread health.
