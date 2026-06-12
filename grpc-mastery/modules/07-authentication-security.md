# Module 07: Security: TLS, mTLS, and Token Authentication in Java

## 1. What Problem This Module Solves
Microservice communication must be secured against wiretapping, tampering, and unauthorized access:
*   **Eavesdropping**: Intercepting plain text network packets exposes sensitive user data.
*   **Impersonation**: Without client-identity validation, any malicious node within a private VPC can call downstream internal services.
*   **Credential Leakage**: Transmitting API keys or authentication tokens repeatedly in dynamic, unsafe structures can expose them in access logs.

This module details how to implement Transport Layer Security (TLS), Mutual TLS (mTLS), and token-based (JWT) authentication using low-level Netty handlers and gRPC interceptors.

---

## 2. Security Patterns: TLS vs mTLS vs Token Authentication
1.  **TLS (Transport Layer Security)**: The server presents a certificate to prove its identity to the client. The communication channel is encrypted.
2.  **mTLS (Mutual TLS)**: Both server and client present certificates to each other. The server validates that the client is an authorized caller, establishing a cryptographically verified client identity at the connection layer.
3.  **Token Authentication (JWT)**: Application-layer credentials. A client supplies a signed cryptographic token (JWT) inside gRPC headers (`Metadata`) to identify the user session executing the request.

```
[ mTLS Layer: Connection Establishment ]
Client (Cert C) <=======================> Server (Cert S)
- Direct verification of peer identity (cryptographic handshake)

[ Application Layer: Authorization ]
Client (Metadata: authorization = Bearer <JWT>) ----> Server
- Validates user roles, permissions, and session lifecycles
```

---

## 3. Trade-offs and Limitations
*   **CPU Overhead**: TLS encryption/decryption consumes CPU cycles. This is mitigated by using Netty’s OpenSSL (tcnative) engine instead of standard Java JDK SSL engines.
*   **Certificate Lifecycle Management**: mTLS requires managing a Private Key Infrastructure (PKI) to rotate certificates on servers and clients. Expired certificates will immediately halt all communication.

---

## 4. Common Mistakes and Anti-Patterns
*   **Using Plaintext in Production**: Disabling TLS for internal communication because it is "inside the VPC". If a single pod is compromised, the attacker can sniff all internal plain text network traffic.
*   **Re-Authenticating on Every Stream Message**: Reading and validating JWT tokens in every `onNext()` stream payload. In streaming calls, authentication must be validated only once during the initial connection handshake.
*   **Leaking Keys in Git**: Hardcoding certificate private keys or JWT signing secrets directly in configuration source files. Use secure keystores (like HashiCorp Vault or AWS KMS).

---

## 5. Bootstrapping mTLS with Netty Shaded

In pure Java, you use `GrpcSslContexts` (from `grpc-netty-shaded`) to programmatically load X.509 certificates and keys.

### 5.1 Secure Server Configuration
```java
package com.example.grpc.security;

import io.grpc.Server;
import io.grpc.netty.shaded.io.grpc.netty.GrpcSslContexts;
import io.grpc.netty.shaded.io.grpc.netty.NettyServerBuilder;
import io.grpc.netty.shaded.io.netty.handler.ssl.ClientAuth;
import io.grpc.netty.shaded.io.netty.handler.ssl.SslContext;

import java.io.File;
import java.io.IOException;

public class SecureGrpcServer {

    public static Server buildSecureServer(int port, File certChain, File privateKey, File trustStore) 
            throws IOException {
        
        // 1. Build SSL Context with client validation enabled (mTLS)
        SslContext sslContext = GrpcSslContexts.forServer(certChain, privateKey)
            .trustManager(trustStore) // Validates client certificates
            .clientAuth(ClientAuth.REQUIRE) // Enforce client identity validation
            .build();

        // 2. Instantiate Server using Netty builder
        return NettyServerBuilder.forPort(port)
            .sslContext(sslContext)
            .addService(new SecuredService())
            .build();
    }

    private static class SecuredService extends io.grpc.BindableService {
        @Override
        public io.grpc.ServerServiceDefinition bindService() {
            return io.grpc.ServerServiceDefinition.builder("SecuredService").build();
        }
    }
}
```

### 5.2 Secure Client Configuration
```java
package com.example.grpc.security;

import io.grpc.ManagedChannel;
import io.grpc.netty.shaded.io.grpc.netty.GrpcSslContexts;
import io.grpc.netty.shaded.io.grpc.netty.NettyChannelBuilder;
import io.grpc.netty.shaded.io.netty.handler.ssl.SslContext;

import java.io.File;
import javax.net.ssl.SSLException;

public class SecureGrpcClient {

    public static ManagedChannel buildSecureChannel(String host, int port, File certChain, File privateKey, File trustStore) 
            throws SSLException {

        // Build SSL context proving client identity to server
        SslContext sslContext = GrpcSslContexts.forClient()
            .keyManager(certChain, privateKey) // Prove client identity
            .trustManager(trustStore) // Validate server certificate
            .build();

        return NettyChannelBuilder.forAddress(host, port)
            .sslContext(sslContext)
            .overrideAuthority("server.domain.com") // Set target server name indicator (SNI)
            .build();
    }
}
```

---

## 6. Token Authentication (JWT) in Java

To attach token authorization headers to RPC calls, gRPC provides the `CallCredentials` abstraction.

### 6.1 Custom Client `CallCredentials`
```java
package com.example.grpc.security;

import io.grpc.*;
import java.util.concurrent.Executor;

public class JwtCallCredentials extends CallCredentials {

    private final String jwtToken;

    public JwtCallCredentials(String jwtToken) {
        this.jwtToken = jwtToken;
    }

    @Override
    public void applyRequestMetadata(
            RequestInfo requestInfo,
            Executor appExecutor,
            MetadataApplier metadataApplier) {

        // Execute metadata injection in the provided executor
        appExecutor.execute(() -> {
            try {
                Metadata headers = new Metadata();
                Metadata.Key<String> authKey = Metadata.Key.of(
                    "authorization", Metadata.ASCII_STRING_MARSHALLER
                );
                headers.put(authKey, "Bearer " + jwtToken);
                metadataApplier.apply(headers);
            } catch (Throwable t) {
                metadataApplier.fail(Status.UNAUTHENTICATED.withCause(t));
            }
        });
    }
}
```

Usage:
```java
UserServiceBlockingStub secureStub = UserServiceGrpc.newBlockingStub(channel)
    .withCallCredentials(new JwtCallCredentials("my-secure-jwt-payload-string"));
```

---

### 6.2 Server JWT Validation Interceptor
```java
package com.example.grpc.security;

import io.grpc.*;

public class ServerJwtInterceptor implements ServerInterceptor {

    private static final Metadata.Key<String> AUTH_KEY = Metadata.Key.of(
        "authorization", Metadata.ASCII_STRING_MARSHALLER
    );

    // Context Key to store parsed user credentials thread-safely
    public static final Context.Key<String> USER_IDENTITY = Context.key("user-identity");

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerMethodDefinition<ReqT, RespT> next) {

        String authHeader = headers.get(AUTH_KEY);

        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            call.close(
                Status.UNAUTHENTICATED.withDescription("Missing or invalid authorization token"),
                new Metadata()
            );
            return new ServerCall.Listener<ReqT>() {}; // Return empty listener
        }

        String token = authHeader.substring(7);
        try {
            // Validate and parse token identity (mock verification here)
            String userId = validateAndParseJwt(token);

            // Bind parsed identity to thread-safe execution Context
            Context context = Context.current().withValue(USER_IDENTITY, userId);
            
            // Execute down the chain within the context
            return Contexts.interceptCall(context, call, headers, next);

        } catch (Exception e) {
            call.close(
                Status.UNAUTHENTICATED.withDescription("Token validation expired or corrupted"),
                new Metadata()
            );
            return new ServerCall.Listener<ReqT>() {};
        }
    }

    private String validateAndParseJwt(String token) {
        if ("invalid-token".equals(token)) {
            throw new IllegalArgumentException("Signature failed");
        }
        return "user_id_101"; // Parsed username
    }
}
```

---

## 7. Interview Questions

### Q1: What is the purpose of ALPN (Application-Layer Protocol Negotiation) in TLS handshakes, and why does gRPC require it?
**Answer**: 
ALPN is an extension of the TLS protocol that runs during the initial cryptographic handshake. It allows the client and server to negotiate which application protocol (e.g. HTTP/1.1, HTTP/2, or HTTP/3) they will use to communicate over the encrypted channel before any application data is sent.
gRPC mandates ALPN because it relies strictly on HTTP/2. If a client attempts to connect without ALPN capability, the server will not know to process the stream as multiplexed HTTP/2 frames, causing the connection to fall back to HTTP/1.1 or fail entirely.

### Q2: Why is the `CallCredentials` abstraction preferred over custom Client Interceptors for applying authorization headers?
**Answer**: 
While a client interceptor can manually insert headers, `CallCredentials` is designed specifically to handle security contexts. It provides:
1.  **Thread Security**: It executes asynchronously using an allocated `Executor` thread pool, preventing token fetches (like calling a secure endpoint to renew a JWT token) from blocking the Netty networking thread.
2.  **Transport Security Constraints**: The gRPC runtime automatically prevents `CallCredentials` from executing if the channel is not encrypted (does not use TLS). This prevents developers from accidentally transmitting authorization tokens in plain text over the network.
