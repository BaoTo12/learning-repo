# Module 07: Security: TLS, mTLS, and Spring Security Integration

## 1. What Problem This Module Solves
Microservice network traffic must be secured against eavesdropping, service impersonation, and unauthorized access:
*   **Plaintext Wire Sniffing**: Sending internal traffic unencrypted exposes data to attackers who compromise the container subnet.
*   **Identity Impersonation**: Failing to check client identity at the connection layer allows any microservice to query sensitive payment endpoints.
*   **Security Context Loss**: In Spring Boot, request authorization relies on thread-local security context maps. If gRPC requests do not bind to Spring Security contexts, standard method security annotations (like `@PreAuthorize`) will fail.

This module details how to configure transport encryption (TLS/mTLS) using properties and how to integrate JWT tokens with Spring Security's authorization context.

---

## 2. Security Layers: Transport vs Application

```
+-------------------------------------------------------------------+
|                        gRPC Security Envelope                     |
|                                                                   |
|   [ mTLS Connection Layer ]                                       |
|   - Client & Server exchange certificates.                         |
|   - Encrypts network payload. Verifies container identity.        |
|                                                                   |
|   [ Application / Spring Security Layer ]                         |
|   - Interceptor extracts header Metadata (Authorization: Bearer)  |
|   - Binds authenticated user to Spring SecurityContext            |
|                                                                   |
+-------------------------------------------------------------------+
```

---

## 3. Configuring mTLS via Spring Properties (`application.yml`)

Configure TLS trust manager paths and client authentication requirements directly in configuration properties:

### 3.1 Server Security Configuration
```yaml
grpc:
  server:
    port: 9090
    security:
      enabled: true
      certificate-chain-path: classpath:certs/server.crt
      private-key-path: classpath:certs/server.key
      trust-cert-collection-path: classpath:certs/ca.crt # Authority to validate client certs
      client-auth: REQUIRE # Force mutual TLS (mTLS)
```

### 3.2 Client Security Configuration
```yaml
grpc:
  client:
    user-service:
      address: 'static://localhost:9090'
      security:
        authority-override: server.domain.com
        trust-cert-collection-path: classpath:certs/ca.crt
        certificate-chain-path: classpath:certs/client.crt
        private-key-path: classpath:certs/client.key
```

---

## 4. Spring Security gRPC Context Integration

To bind authorization metadata headers (JWT) to Spring Security, implement a security interceptor:

### 4.1 Custom JWT Authentication Interceptor
```java
package com.example.grpc.security;

import io.grpc.*;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import java.util.List;

public class JwtSecurityInterceptor implements ServerInterceptor {

    private static final Metadata.Key<String> AUTH_KEY = Metadata.Key.of(
        "authorization", Metadata.ASCII_STRING_MARSHALLER
    );

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerMethodDefinition<ReqT, RespT> next) {

        String authHeader = headers.get(AUTH_KEY);

        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            call.close(
                Status.UNAUTHENTICATED.withDescription("Missing or invalid token"),
                new Metadata()
            );
            return new ServerCall.Listener<ReqT>() {};
        }

        String token = authHeader.substring(7);
        try {
            // Verify JWT (mock validation here)
            String username = validateJwt(token);

            // Create Spring Security Authentication token
            UsernamePasswordAuthenticationToken auth = new UsernamePasswordAuthenticationToken(
                username, null, List.of(new SimpleGrantedAuthority("ROLE_USER"))
            );

            // Bind to Spring Security Context
            SecurityContextHolder.getContext().setAuthentication(auth);

            return next.startCall(call, headers);
        } catch (Exception e) {
            call.close(
                Status.UNAUTHENTICATED.withDescription("Token verification failed"),
                new Metadata()
            );
            return new ServerCall.Listener<ReqT>() {};
        }
    }

    private String validateJwt(String token) {
        if ("expired-token".equals(token)) {
            throw new IllegalArgumentException("Expired");
        }
        return "jane_doe";
    }
}
```

---

### 4.2 Annotating Service Methods with `@PreAuthorize`
Configure method security and apply annotations to your `@GrpcService`:

```java
package com.example.grpc.security;

import com.example.grpc.user.v1.UserProfile;
import com.example.grpc.user.v1.UserRequest;
import com.example.grpc.user.v1.UserServiceGrpc;
import io.grpc.stub.StreamObserver;
import net.devh.boot.grpc.server.service.GrpcService;
import org.springframework.security.access.prepost.PreAuthorize;

@GrpcService
public class SecureUserService extends UserServiceGrpc.UserServiceImplBase {

    @Override
    @PreAuthorize("hasRole('ROLE_USER')") // Evaluates client context parsed by interceptor
    public void getUser(UserRequest request, StreamObserver<UserProfile> responseObserver) {
        UserProfile response = UserProfile.newBuilder()
            .setUserId(request.getUserId())
            .setEmail("authenticated-user@example.com")
            .build();
        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }
}
```

---

## 5. Common Mistakes and Anti-Patterns
*   **Neglecting Context Cleanups**: Failing to clear the security context after a request completes. Since threads are recycled, leaking security tokens can allow subsequent requests on that thread to execute using the previous user's credentials.
*   **Transmitting Sensitive Tokens over Plaintext Channels**: Storing API keys or JWTs in gRPC metadata without enforcing TLS. Metadata is transmitted as plaintext headers; always enforce TLS to protect credentials in transit.

---

## 6. Interview Questions

### Q1: How does a Spring `@GrpcService` evaluate `@PreAuthorize` annotations? What class manages this link?
**Answer**: 
During startup, the Spring container detects `@PreAuthorize` on gRPC service methods. The security starter registers a gRPC context interceptor bean (`AbstractSecurityInterceptor`). 
When a call arrives, the interceptor extracts the credentials, binds them to Spring's thread-local `SecurityContextHolder`, and executes the method. A Spring AOP proxy intercepts the method execution, calls the `AccessDecisionManager` to evaluate the expression (e.g. `hasRole('USER')`), and throws an AccessDenied exception if validation fails.

### Q2: Why is mTLS preferred over API Keys for internal service-to-service communication?
**Answer**: 
*   **API Keys**: Are static strings. If an key is exposed (logged, stored in configurations, or sniffed), an attacker can easily reuse it.
*   **mTLS**: Relies on public-key cryptography. Authentication requires proving possession of a private key via a cryptographic handshake. The private key never travels over the network. Certificates expire quickly and can be revoked dynamically via certificate revocation lists (CRLs), providing stronger zero-trust security.
