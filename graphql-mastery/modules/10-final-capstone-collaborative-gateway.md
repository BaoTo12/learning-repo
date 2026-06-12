# Module 10: Final Capstone Project — Secure Real-time Federated Gateway

Welcome to the **Final Capstone Project** for CS-512.

Over the past nine modules, we have built the systems engineering foundation of GraphQL, covering schema design, nested resolvers, N+1 query batching, mutations transactions, WebSocket streams, distributed Apollo Federation subgraphs, query complexity limits, DTO codegen, and normalized caching.

In this final capstone project, you will design and implement a **Collaborative Real-time Gateway**. You will coordinate multiple services to guarantee that client queries are parsed, validated, checked for depth/complexity, authorized using JWT context propagation, and resolved across subgraphs.

---

## 1. Capstone Architecture Overview

The Collaborative Gateway is the unified entry point for a real-time chat and e-commerce portal. It is composed of three systems:

```
                            Capstone Gateway Topology
                            
                              [ Client / Frontend ]
                                       |
                                       v
                    [ Collaborative GraphQL Gateway ]
                    - WebGraphQlInterceptor (JWT Auth)
                    - Query Depth Limiter (Max 4 levels)
                                       |
                     +-----------------+-----------------+
                     | (HTTP/JSON)                       | (WebSocket/SSE)
                     v                                   v
             [ User Subgraph ]                   [ Chat Subgraph ]
             (Catalog / DTOs)                    (Live Subscriptions)
```

1.  **Collaborative GraphQL Gateway**: Parses client JWT tokens, validates signatures, calculates query cost limits, and routes queries.
2.  **User Subgraph**: Houses user records and exposes federated `@key` entities.
3.  **Chat Subgraph**: Implements subscription mapping returning Reactor `Flux` streams over WebSocket connections.

---

## 2. Capstone Design Decisions & Trade-offs

### Centralized JWT Authentication at Gateway
We implement a **Shared Context Propagation** model:
1.  The client sends a JWT token in the HTTP Authorization header.
2.  The Gateway interceptor decodes the token, extracts the user ID and role claims, and sets Spring Security's `SecurityContext`.
3.  When routing queries to downstream subgraphs, the gateway propagates these claims in custom HTTP headers: `X-User-Id` and `X-User-Roles`.
*   *Trade-off*: Downstream subgraphs do not need to re-validate JWT signatures against public keys, reducing CPU cycles. However, the subgraphs must trust the Gateway and reject any public traffic that attempts to inject `X-User-Id` headers directly.

---

## 3. Capstone Implementation: Collaborative Gateway

Let's write the complete, compile-grade implementation of the **Collaborative Gateway** security and context parsing components in Java 21.

First, let's write our Security and User representations:

```java
package com.capstone.graphql.capstone;

import java.util.List;

public record UserContext(
    String userId,
    List<String> roles
) {}
```

```java
package com.capstone.graphql.capstone;

public record ChatMessage(
    String id,
    String senderId,
    String text
) {}
```

Now let us write the `GatewaySecurityInterceptor` that extracts JWT claims and binds them to the GraphQL request environment:

```java
package com.capstone.graphql.capstone;

import org.springframework.graphql.server.WebGraphQlHandler;
import org.springframework.graphql.server.WebGraphQlInterceptor;
import org.springframework.graphql.server.WebGraphQlRequest;
import org.springframework.graphql.server.WebGraphQlResponse;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.util.*;

/**
 * Gateway Interceptor parsing Authorization headers and injecting 
 * UserContext claims into the GraphQL execution environment.
 */
@Component
public class GatewaySecurityInterceptor implements WebGraphQlInterceptor {

    @Override
    public Mono<WebGraphQlResponse> intercept(WebGraphQlRequest request, WebGraphQlHandler next) {
        // Step 1: Extract Authorization header values
        List<String> authHeaders = request.getHeaders().get("Authorization");
        
        UserContext context = null;
        if (authHeaders != null && !authHeaders.isEmpty()) {
            String token = authHeaders.get(0);
            context = parseJwtToken(token);
        }

        // If no token is provided, assign a guest anonymous context
        if (context == null) {
            context = new UserContext("ANONYMOUS_GUEST", List.of("ROLE_GUEST"));
        }

        // Step 2: Inject the context into the GraphQL Execution Input context map
        Map<String, Object> contextMap = new HashMap<>();
        contextMap.put("userContext", context);
        
        request.configureExecutionInput((executionInput, builder) -> 
            builder.graphQLContext(contextMap).build()
        );

        return next.handle(request);
    }

    /**
     * Simulates decoding a JWT token and returning user claims.
     */
    private UserContext parseJwtToken(String token) {
        if (token.startsWith("Bearer ") && token.length() > 7) {
            String cleanToken = token.substring(7);
            // In production, validate signature using RS256/HMAC keys
            if ("admin-key-token".equals(cleanToken)) {
                return new UserContext("usr-admin-1", List.of("ROLE_USER", "ROLE_ADMIN"));
            } else if ("user-key-token".equals(cleanToken)) {
                return new UserContext("usr-normal-2", List.of("ROLE_USER"));
            }
        }
        return null;
    }
}
```

Now let us write the `ChatSubgraphController` that resolves mutations and subscriptions using the user context:

```java
package com.capstone.graphql.capstone;

import graphql.schema.GraphQLContext;
import org.springframework.graphql.data.method.annotation.Argument;
import org.springframework.graphql.data.method.annotation.MutationMapping;
import org.springframework.graphql.data.method.annotation.SubscriptionMapping;
import org.springframework.stereotype.Controller;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;

import java.util.*;
import java.util.logging.Logger;

@Controller
public class ChatSubgraphController {
    private static final Logger LOGGER = Logger.getLogger(ChatSubgraphController.class.getName());

    private final Sinks.Many<ChatMessage> chatSink = Sinks.many().multicast().onBackpressureBuffer();

    /**
     * Resolves mutation with caller context verification.
     */
    @MutationMapping
    public ChatMessage postMessage(@Argument String text, GraphQLContext context) {
        Objects.requireNonNull(text, "Message text cannot be null");
        
        // Retrieve our security context injected by the interceptor
        UserContext user = context.get("userContext");
        if (user == null || user.roles().contains("ROLE_GUEST")) {
            throw new IllegalStateException("Authentication required. Guest users cannot post messages.");
        }

        String id = UUID.randomUUID().toString();
        ChatMessage message = new ChatMessage(id, user.userId(), text);
        
        LOGGER.info("User " + user.userId() + " posted message: " + text);
        
        // Emit to subscriptions
        chatSink.tryEmitNext(message);
        
        return message;
    }

    /**
     * Resolves subscription stream.
     */
    @SubscriptionMapping
    public Flux<ChatMessage> messageFeed(GraphQLContext context) {
        UserContext user = context.get("userContext");
        if (user == null) {
            throw new IllegalStateException("Security evaluation failed.");
        }
        LOGGER.info("Opening message feed for user: " + user.userId());
        return chatSink.asFlux();
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Missing Context in WebSockets Handshake
WebSocket handshakes occur once during initial upgrade, meaning standard HTTP request headers are not sent during subsequent GraphQL frames.
*   **Symptom**: Mutations work with JWT, but subscriptions fail to read the user context because headers are missing.
*   **Mitigation**: Pass the JWT token inside the `connectionParams` parameter of the `ConnectionInit` payload. Map this parameter to the GraphQL context during connection initialization in your WebSocket config customizer.

### Pitfall 2: Memory Leak in multicast Sinks
*   **Symptom**: The JVM heap memory fills up over days.
*   **Why**: If clients open subscriptions and disconnect abruptly (due to network drops), and the Reactor multicast Sink retains stale subscriber references in its buffer.
*   **Mitigation**: Enforce client keep-alive timeouts and configure the sink to discard items or drop slow consumers.

---

## 5. Socratic Review Questions

### Question 1
Explain how the `GraphQLContext` interface facilitates data propagation across different resolvers during a query execution.

#### Answer
The `GraphQLContext` acts as a shared execution map that persists throughout the lifecycle of a single query request. 

Because resolvers execute asynchronously and can span different thread pools (especially when DataLoaders or reactive streams are active), we cannot rely on thread-local storage (`ThreadLocal`) to pass variables. 

The `GraphQLContext` is thread-safe and is carried by the execution engine to every resolver method. By injecting variables (such as authentication context, request IDs, or transaction metrics) into the context map inside a pre-execution interceptor, any child resolver down the AST tree can access the values by declaring a `GraphQLContext` argument, securing metadata consistency.

### Question 2
Why is it vital to enforce query complexity limits at the Gateway Router layer rather than letting subgraphs manage complexity limits individually?

#### Answer
If query complexity is only validated at the subgraph level:
1.  The Gateway Router must still parse the entire query and execute subqueries against other subgraphs before it hits the restricted subgraph. By then, database queries and network bandwidth have already been consumed.
2.  An attacker can split the query to request small datasets across 5 subgraphs. Each subgraph evaluates its local cost as low, but the total cumulative cost across the gateway remains extremely high, causing resource exhaustion on the gateway itself.
Enforcing complexity limits at the gateway stops expensive queries at the boundary before any subgraph is invoked.

---

## 6. Hands-on Challenge: Building a Dynamic Complexity Analyzer

### The Challenge
In this challenge, you will implement the logic for a custom **Query Complexity Analyzer**. 

You must calculate the total complexity cost of a query based on a weighted configuration map of keywords (e.g., `"adminReport"` has cost 10, `"messageFeed"` has cost 5). If the total calculated cost of the query exceeds the maximum allowed threshold of 12, your validator must throw an `IllegalStateException`.

Complete the cost aggregation logic below:

```java
package com.capstone.graphql.capstone.challenge;

import java.util.HashMap;
import java.util.Map;

public class GraphQlComplexityAnalyzer {

    private static final int MAX_COMPLEXITY_LIMIT = 12;
    private final Map<String, Integer> fieldWeights = new HashMap<>();

    public GraphQlComplexityAnalyzer() {
        // Setup weight allocations
        fieldWeights.put("adminReport", 10);
        fieldWeights.put("messageFeed", 5);
        fieldWeights.put("billingDetails", 8);
    }

    /**
     * Estimates the complexity cost of the query document string.
     * Throws IllegalStateException if the calculated cost exceeds MAX_COMPLEXITY_LIMIT.
     */
    public void evaluateQueryCost(String query) {
        if (query == null || query.isEmpty()) return;

        int totalComplexity = 0;

        // TODO: Complete this implementation.
        // 1. Iterate over the fieldWeights map keys.
        // 2. If the query string contains a key, add its mapped cost to totalComplexity.
        // 3. Throw IllegalStateException if totalComplexity > MAX_COMPLEXITY_LIMIT.
    }
}
```

Write your code and verify the cost limitation checks. Save your solution notes inside `modules/10-final-capstone-collaborative-gateway.md`.
