# Module 08: Policy-as-Code & Open Policy Agent (OPA)

Welcome back class. Today we analyze **Policy-as-Code & Open Policy Agent (CS-527)**.

As corporate access control policies grow in complexity, hardcoding logical rules inside Java classes becomes a technical burden. If security auditors require access constraints to change (e.g., locking access to sensitive documents during emergency operations), engineers must rewrite security expressions, build code artifacts, and deploy new microservices. To achieve true decoupling, modern architectures utilize **Policy-as-Code**, separating authorization logic from application code using dedicated policy evaluation engines like **Open Policy Agent (OPA)**.

Today we study Policy-as-Code principles, learn OPA's declarative policy language **Rego**, and write a custom non-blocking **Spring Security `AuthorizationManager`** in Java 21 using WebClient.

---

## 1. Academic Lecture: Decoupled Authorization Engines

### 1. Code-Embedded vs. Decoupled Authorization
*   **Embedded Authorization**: Authorization rules are declared directly inside the codebase via annotations (e.g., `@PreAuthorize`) or servlet filters. Policies are tightly bound to compile cycles.
*   **Decoupled Policy-as-Code**: Policies are written in a declarative language and loaded into a standalone policy engine (OPA). When an API endpoint receives a request, it extracts context parameters (Subject, Resource, Action) and sends them to OPA as a JSON payload. OPA evaluates the policies against this JSON context and returns a simple authorization decision (`allow: true/false`).

### 2. Open Policy Agent (OPA) and the Rego Query Language
OPA is a CNFC-graduated, lightweight policy engine. It evaluates policies in a declarative language called **Rego**:
*   **Rego Features**: Designed to query complex hierarchical JSON structures. Instead of loops and nested condition trees, Rego policies are written as rules that evaluate to true or false.
*   **Example Rego Rule**:
    ```rego
    package authz

    # By default, deny access
    default allow = false

    # Allow if user is admin
    allow {
        input.user.roles[_] == "ADMIN"
    }

    # Allow recruiters to read during office hours
    allow {
        input.user.roles[_] == "RECRUITER"
        input.action == "READ"
        input.environment.hour >= 8
        input.environment.hour < 19
    }
    ```

### 3. Non-Blocking Authorization Checks
Because OPA runs as a separate service (often deployed as a sidecar process in the same pod to minimize network lag), the application must query it via HTTP. To prevent blocking the servlet's execution thread, Spring Security 6.x allows us to write non-blocking `AuthorizationManager` components utilizing reactive **WebClient** layers.

```text
[Incoming HTTP Request] ──> [Spring Security Filter Chain]
                                     │
                                     ▼
                        [OPA Authorization Manager]
                           ├── Compile JSON Context
                           │     ├── User: john_recruiter (Role: RECRUITER)
                           │     ├── Action: READ
                           │     └── Env: Hour=14
                           │
                           └── Async HTTP POST /v1/data/authz/allow ──> [OPA Daemon]
                                                                           │ (Evaluate Rego)
                                                                           ▼
[Forward to Controller] ◀────── Allow: true ─────────────────────────── [Return JSON]
```

---

## 2. Theory vs. Production Trade-offs

When adopting Policy-as-Code architectures, weigh decoupling flexibility against performance constraints:

| Authorization Strategy | Policy Centralization | Rule Language | Verification Latency | Deployment Overhead |
| :--- | :--- | :--- | :--- | :--- |
| **Spring @PreAuthorize** | Scattered in code | Java / SpEL | Very Low (In-memory checks) | Low (Part of standard code) |
| **Local OPA Sidecar** | Centralized (Git repository) | Rego (Declarative) | Low (Local loopback HTTP: <5ms) | Moderate (Requires sidecar container) |
| **Centralized OPA Server**| Centralized (Enterprise Git) | Rego (Declarative) | Moderate (Network HTTP: 10-30ms) | High (Requires OPA cluster + cache) |

---

## 3. How to Use: Non-Blocking OPA Manager in Java

Let us write a compile-grade Java 21 implementation of a custom Spring Security `AuthorizationManager` that queries OPA asynchronously using `WebClient`, preventing thread pool starvation.

### A. The Blocked HTTP Ingestion Pattern (Anti-Pattern)

Avoid executing blocking rest template calls inside custom filters. Under high concurrency, blocking the servlet thread pool will lead to API timeout cascades:

```java
package com.security.api.config;

import org.springframework.web.client.RestTemplate;

public class NaiveOpaClient {
    private final RestTemplate restTemplate = new RestTemplate();
    private final String opaUrl = "http://localhost:8181/v1/data/authz/allow";

    // DANGER: Calling restTemplate.postForObject blocks the active HTTP thread
    // until OPA responds. If OPA experiences high CPU load or network delay,
    // all servlet worker threads pool will block, freezing the entire API.
    public boolean checkOpaBlocking(Object context) {
        Boolean decision = restTemplate.postForObject(opaUrl, context, Boolean.class); // VULNERABLE
        return Boolean.TRUE.equals(decision);
    }
}
```

### B. The Hardened OPA Authorization Manager (Production Pattern)

Here is the hardened pattern. We write a custom `AuthorizationManager` class that constructs a structured context payload, executes a non-blocking POST query using `WebClient`, and returns a reactive `Mono<AuthorizationDecision>`.

```java
package com.security.api.config;

import org.springframework.http.MediaType;
import org.springframework.security.authorization.AuthorizationDecision;
import org.springframework.security.authorization.ReactiveAuthorizationManager;
import org.springframework.security.core.Authentication;
import org.springframework.security.web.server.authorization.AuthorizationContext;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.LocalTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class OpaAuthorizationManager implements ReactiveAuthorizationManager<AuthorizationContext> {

    private final WebClient webClient;
    private final String opaUrl = "/v1/data/authz/allow";

    public OpaAuthorizationManager(String opaHost) {
        // Initialize reactive HTTP client targeting OPA sidecar
        this.webClient = WebClient.builder().baseUrl(opaHost).build();
    }

    @Override
    public Mono<AuthorizationDecision> check(Mono<Authentication> authentication, AuthorizationContext context) {
        return authentication.flatMap(auth -> {
            // 1. Gather Context parameters
            String username = auth.getName();
            List<String> roles = auth.getAuthorities().stream()
                .map(a -> a.getAuthority())
                .collect(Collectors.toList());
            
            String path = context.getExchange().getRequest().getPath().value();
            String method = context.getExchange().getRequest().getMethod().name();

            // 2. Build structured OPA Input Payload JSON map
            Map<String, Object> input = new HashMap<>();
            
            Map<String, Object> userContext = new HashMap<>();
            userContext.put("username", username);
            userContext.put("roles", roles);
            
            Map<String, Object> envContext = new HashMap<>();
            envContext.put("hour", LocalTime.now().getHour());

            input.put("user", userContext);
            input.put("action", method);
            input.put("path", path);
            input.put("environment", envContext);

            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("input", input);

            // 3. Execute non-blocking POST query to OPA daemon
            return this.webClient.post()
                .uri(opaUrl)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(requestBody)
                .retrieve()
                // Parse OPA response structure: { "result": true/false }
                .bodyToMono(OpaResponse.class)
                .map(response -> new AuthorizationDecision(response.isResult()))
                // Fallback: deny access defensively if OPA service is unreachable
                .onErrorReturn(new AuthorizationDecision(false));
        }).defaultIfEmpty(new AuthorizationDecision(false));
    }

    // Static helper response mapping record (Java 21)
    private static record OpaResponse(boolean result) {}
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Failing Open on OPA Network Errors
Failing to capture OPA client HTTP exceptions, letting the authorization check fallback to allowing requests.
*   **Why it fails**: If the OPA sidecar crashes or is restarted, the client connection throws a `ConnectException`. If the catch block returns `allow = true` or skips validation, the API exposes resources, bypassing security controls completely.
*   **Mitigation**: Always implement a **Fail-Closed** security paradigm. If OPA is unreachable, log a high-severity alert and return `AuthorizationDecision(false)` immediately.

### Pitfall 2: Payload mismatch with OPA Rego schema expectations
Passing key names in the Java JSON context map that do not align with the Rego policy query constraints (e.g. passing `input.user.name` in Java but OPA evaluates `input.user.username`).
*   **Why it fails**: Rego fails silently. If a key is missing or undefined, OPA does not throw a compile exception; it simply returns `allow: false`, causing legitimate queries to be locked out.
*   **Mitigation**: Write comprehensive validation tests checking that the JSON serialization outputs match the exact structure expected by the Rego policy package schemas.

---

## 5. Socratic Review Questions

### Question 1
Why does OPA use a declarative language like Rego instead of standard procedural languages like Java or Python for policy definitions?

#### Answer
Procedural languages require step-by-step logic commands (if-else, loops), which can lead to nested code paths that are difficult for static analysis tools to verify. Rego is a query-driven language derived from Datalog. It is mathematical and side-effect free. It allows the OPA engine to optimize query execution graphs, execute parallel validations, and guarantee that policies execute deterministically without memory leakage risks.

### Question 2
What is a "sidecar deployment" pattern, and why is it crucial for minimizing OPA latency overhead?

#### Answer
In a sidecar pattern, the OPA container runs in the same Kubernetes Pod as the Java application. They share the same local network interface (`localhost`). When the Java app queries OPA, the HTTP request traverses local loopback interfaces instead of routing across external switches. This limits network latency to under 1-2 milliseconds, preventing authorization checks from slowing down API requests.

---

## 6. Hands-on Challenge: Rego Query Executor

### The Challenge
In this challenge, you will implement an OPA payload parser class in Java.
Your task:
1. Complete the `buildOpaRequest` method inside `OpaPayloadGenerator`.
2. Format the JSON structure exactly as expected by OPA's `/v1/data/authz` API endpoint (wrapping the parameters in an `"input"` parent key).
3. Validate that user names do not contain special characters to prevent schema injection.

Complete the implementation below:

```java
package com.security.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class OpaPayloadGenerator {
    private final ObjectMapper mapper = new ObjectMapper();

    public String buildOpaRequest(String username, List<String> roles, String action, String path) throws Exception {
        // Validation boundary check
        if (username == null || !username.matches("^[a-zA-Z0-9_]+$")) {
            throw new IllegalArgumentException("Invalid username format.");
        }

        // TODO: Implement JSON payload construction:
        // 1. Create a map representing user context: keys "username" and "roles".
        // 2. Create a map representing the input payload: keys "user", "action", "path".
        // 3. Create a parent envelope map containing a single key "input" that holds the input payload map.
        //    (This structure is mandatory for OPA REST API data posts).
        // 4. Use the mapper to serialize the envelope map to a JSON string and return it.

        return "";
    }
}
```

Write the serialization rule. Save the completed file and verify that the JSON string structure aligns correctly under `modules/08-policy-as-code-opa.md`.
