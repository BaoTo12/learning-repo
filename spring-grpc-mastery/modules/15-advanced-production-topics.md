# Module 15: Advanced Operations & Rate Limiting

## 1. What Problem This Module Solves
Running gRPC microservices in production at high scale introduces structural operational challenges:
*   **Denial of Service (DoS)**: A single misconfigured internal service can query a downstream database service with millions of rapid calls, crashing the database.
*   **Breaking Schema Changes**: Upgrading service schemas without supporting legacy clients breaks production traffic.
*   **Deployment Faults**: Deploying updates globally at once risks exposing all users to bugs.
*   **Multi-Region Latency**: If a client in Europe calls a gRPC database backend located in North America, establishing connections over high-latency networks degrades response times.

This module details production strategies including rate limiting, API versioning, canary routing, and multi-region patterns, featured by a custom Java rate-limiting server interceptor.

---

## 2. API Versioning Strategies

Unlike REST APIs which utilize URL path versioning (e.g., `/v1/users`), gRPC versioning is defined inside the Protobuf package namespace:

```protobuf
// File path: api/user/v1/user.proto
syntax = "proto3";
package api.user.v1; // Package versioning namespace

message UserProfile {
  string user_id = 1;
  string display_name = 2;
}
```

```protobuf
// File path: api/user/v2/user.proto
syntax = "proto3";
package api.user.v2; // Major version increment

message UserProfile {
  string id = 1; // Modified field name/tag structure
  string first_name = 2;
  string last_name = 3;
}
```

### Routing Version Coexistence
In production, compile and register **both** versions of the service:
```java
// Server boots with both handlers registered on the same port
Server server = ServerBuilder.forPort(9090)
    .addService(new UserServiceImplV1()) // Binds package api.user.v1
    .addService(new UserServiceImplV2()) // Binds package api.user.v2
    .build();
```
This allows legacy clients to call version 1, and new clients to call version 2 concurrently on the same server process.

---

## 3. Canary Deployments & Header-Based Routing

Canary routing maps traffic dynamically. When deploying a new v2 release:
1.  The client includes a header (e.g., `x-canary-version: v2`) in its call metadata.
2.  The API Gateway or Service Mesh Proxy (Envoy) intercepts the header and routes the request to the canary deployment pod pool.
3.  If no header is present, traffic goes to the stable deployment pod pool.

---

## 4. Common Mistakes and Anti-Patterns
*   **Deleting Deprecated Proto Fields**: Deleting a field from a proto file because "no one is using it". If an old client that was not updated attempts to parse the payload, the delete will cause data corruption or parsing failures.
    *   *Correction*: Use the `reserved` keyword and deprecate fields using the `[deprecated = true]` option.
*   **Hard-Limiting Client Connections**: Configuring a hard socket connection limit. Since gRPC multiplexes all requests from a client onto a single connection, dropping a connection drops thousands of active, unrelated calls.

---

## 5. Mini-Project: Server-Side Rate-Limiting Interceptor in Spring Boot

This project builds a server-side `ServerInterceptor` implementing a thread-safe **Token Bucket** algorithm to rate-limit incoming RPC requests without external database requirements.

### Rate-Limiter Interceptor (`ServerRateLimitInterceptor.java`)
```java
package com.example.grpc.operations;

import io.grpc.*;
import net.devh.boot.grpc.server.interceptor.GrpcGlobalServerInterceptor;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

@GrpcGlobalServerInterceptor
public class ServerRateLimitInterceptor implements ServerInterceptor {

    // Token Bucket for each client ID
    private final Map<String, TokenBucket> clientBuckets = new ConcurrentHashMap<>();
    private final long capacity = 100;    // Maximum tokens
    private final long refillRate = 10;   // Refill 10 tokens per second

    public static final Metadata.Key<String> CLIENT_ID_KEY = Metadata.Key.of(
        "x-client-id", Metadata.ASCII_STRING_MARSHALLER
    );

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerMethodDefinition<ReqT, RespT> next) {

        String clientId = headers.get(CLIENT_ID_KEY);
        if (clientId == null) {
            clientId = "anonymous"; // Fallback identifier
        }

        // Get or initialize client's bucket
        TokenBucket bucket = clientBuckets.computeIfAbsent(clientId, 
            id -> new TokenBucket(capacity, refillRate));

        if (!bucket.tryConsume(1)) {
            // Reject call with RESOURCE_EXHAUSTED status
            call.close(
                Status.RESOURCE_EXHAUSTED
                    .withDescription("Rate limit exceeded. Too many concurrent RPC calls."),
                new Metadata()
            );
            return new ServerCall.Listener<ReqT>() {}; // Return inactive listener
        }

        return next.startCall(call, headers);
    }

    // Thread-safe Token Bucket implementation
    private static class TokenBucket {
        private final long capacity;
        private final long refillRate; // Tokens per second
        private final AtomicLong tokens;
        private long lastRefillTime;

        public TokenBucket(long capacity, long refillRate) {
            this.capacity = capacity;
            this.refillRate = refillRate;
            this.tokens = new AtomicLong(capacity);
            this.lastRefillTime = System.nanoTime();
        }

        public synchronized boolean tryConsume(int count) {
            refill();
            long currentTokens = tokens.get();
            if (currentTokens >= count) {
                tokens.set(currentTokens - count);
                return true;
            }
            return false;
        }

        private void refill() {
            long now = System.nanoTime();
            long elapsedNs = now - lastRefillTime;
            long elapsedSec = elapsedNs / 1_000_000_000;

            if (elapsedSec > 0) {
                long tokensToAdd = elapsedSec * refillRate;
                long newTokens = Math.min(capacity, tokens.get() + tokensToAdd);
                tokens.set(newTokens);
                lastRefillTime = now;
            }
        }
    }
}
```

---

## 6. Interview Questions

### Q1: How does package namespacing solve the issue of breaking API changes in gRPC? How does it differ from REST API versioning?
**Answer**: 
*   **REST Versioning**: Often uses path patterns (like `/v1/users` or `/v2/users`). When upgrading to v2, you must host two separate API routing paths.
*   **gRPC Versioning**: Encapsulates versioning directly in the Protobuf package namespace (e.g. `package api.user.v1` vs `package api.user.v2`). The compiler generates separate Java classes under separate package folders (`com.example.user.v1` and `com.example.user.v2`). 
Because the classes are separated, they can co-exist inside the same JVM classpath without class namespace conflicts. The gRPC server registers both service classes on the same TCP port, letting clients choose which version to query by calling the specific generated stub package name.

### Q2: Why is the Token Bucket rate-limiting algorithm preferred for protecting real-time RPC services over a fixed-window algorithm?
**Answer**: 
*   **Fixed Window**: Counts requests in static segments (e.g., max 100 requests per minute). If a client sends 100 requests at the very end of minute 1, and 100 requests at the very start of minute 2, the client successfully sends a burst of 200 requests in a fraction of a second. This "double-burst" can easily crash downstream database services.
*   **Token Bucket**: Controls requests smoothly. Tokens refill at a steady, continuous rate (e.g. 10 tokens/sec), but allow bursts up to a fixed maximum bucket capacity (e.g. 100 tokens). This prevents clients from executing double-limit bursts while handling temporary traffic surges smoothly.
