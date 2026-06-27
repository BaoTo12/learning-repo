# Chapter 18: Cryptographic Context Propagation with JWTs

Securing service boundaries is not enough. When a request traverses multiple downstream microservices (East-West traffic), services must verify the identity of both the calling service and the end-user who initiated the transaction. Simply passing user contexts as unencrypted HTTP headers (such as `X-User-Id: user123`) is insecure, as any compromised service can forge user headers to escalate privileges. 

To solve this, microservice architectures use **Cryptographic Context Propagation** using **JSON Web Tokens (JWT)**. This chapter covers the implementation of secure identity propagation. We will analyze the core structure of JWTs, contrast shared tokens with token exchange, self-issued tokens, and nested JWTs, and build a dedicated Security Token Service (STS) in Spring Boot. We will write custom API Gateway filters to perform token exchange, implement downstream context validation filters, propagate cryptographic context across gRPC service boundaries, configure JWKS endpoints for public key distribution, and build reactive WebClient context propagators in Spring WebFlux. Finally, we will write programmatic verification utilities using RSA and HMAC-SHA256 algorithms and construct integration tests using Mock JWT providers.

---

## Learning Objectives

By the end of this chapter, you will be able to:
1. Explain the vulnerability of plaintext header propagation and the necessity of cryptographic signatures.
2. Outline the structure of a JSON Web Token (JWT) and differentiate standard claims from custom claims.
3. Contrast context propagation architectures: Shared JWTs, Token Exchange, Self-Issued JWTs, and Nested JWTs.
4. Build a functional Security Token Service (STS) using Spring Security.
5. Expose a standardized JWKS (JSON Web Key Sets) endpoint from the STS to distribute public verification keys.
6. Write a custom Spring Cloud Gateway filter to execute OAuth 2.0 token exchanges.
7. Build a downstream Spring Security context parser to validate JWT signatures and establish authenticated context.
8. Implement a Spring WebFlux ExchangeFilterFunction to propagate JWTs across reactive WebClient boundaries.
9. Implement custom gRPC client and server interceptors to propagate JWT credentials across RPC boundaries.
10. Code a programmatic Java utility to verify JWT signatures using HMAC-SHA256 and RSA public keys.
11. Write a legacy bridge controller to exchange SAML 2.0 assertions for signed JWTs.
12. Write unit and integration tests using mocked JWT providers to verify context setup.

---

## 18.1 Vulnerabilities of Plaintext Header Propagation

In naive microservice systems, once an edge gateway authenticates a user, it forwards their identity downstream using custom HTTP headers:

```
[ Client ] --( Credentials )--> [ API Gateway ] --( X-User-Id: 1001 )--> [ Order Service ] --( X-User-Id: 1001 )--> [ Payment Service ]
                                                                                                                   ^
                                                                                                    (Forwards forged headers easily)
```

### Attack Vectors
1. **Header Injection (Lateral Privilege Escalation)**: If an attacker compromises the `Order Service` container, they can make calls directly to the `Payment Service` database, modifying the `X-User-Id` header to point to a high-privilege account (e.g. `X-User-Id: admin`).
2. **Missing Integrity**: Downstream services have no way to verify whether the user context headers were modified in transit by intermediary network nodes.
3. **Lack of Non-Repudiation**: Since headers are plaintext strings, services cannot cryptographically prove which service initiated a request or modified a transaction context.

Cryptographic context propagation solves this by enclosing user claims within a cryptographically signed payload (a JWT). Any alteration of the claims in transit invalidates the signature, alerting downstream recipients.

---

## 18.2 JWT Core Structure and Claims

A JSON Web Token (JWT) consists of three parts separated by periods (`.`): **Header**, **Payload**, and **Signature**.

```
Header.Payload.Signature
(e.g., eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiY2xpZW50X2lkIjoi..._jP7074POcRlKzoSoEB6...)
```

### 1. The Header
Contains metadata about the token, such as the algorithm used to sign it (e.g., RS256, HS256) and the token type:
```json
{
  "alg": "RS256",
  "typ": "JWT"
}
```

### 2. The Payload
Contains claims (assertions about the user or client) and metadata:
* **Subject (`sub`)**: Identifies the user.
* **Issuer (`iss`)**: Delineates the STS or authority that generated the token.
* **Audience (`aud`)**: Defines the target service that should accept this token.
* **Expiration (`exp`)**: Defines the epoch timestamp after which the token is invalid.
* **Issued At (`iat`)**: Defines when the token was generated.
* **Custom Claims**: Dynamic key-value pairs (e.g., `roles`, `tenant_id`, `client_id`).

### 3. The Signature
Generated by combining the encoded header, payload, and a secret key (or private key) using the specified algorithm. This guarantees integrity and authenticity.

---

## 18.3 Context Propagation Architectures

We evaluate four primary architectures for propagating JWT contexts between microservices:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//7e7a1824-b86d-4aca-86bf-4f061eb7456e/markdown_3/imgs/img_in_image_box_113_448_932_906.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A28Z%2F-1%2F%2F5939719b3c664bf691876414626aed3714d0c279dccf497cf35b7bfef691e8ae" alt="Image" width="77%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7.1 Propagating the end user's identity in a JWT among microservices. All the microservices in the deployment trust the STS. The API gateway exchanges the JWTs it gets from client applications for new JWTs from this STS.</div> </div>

### 1. Shared JWT (Single Audience)
The API Gateway obtains a signed JWT from the STS and propagates it to all downstream services. All services share a common audience check (e.g., `*.ecomm.com`) and trust the STS.
* **Pro**: Simple implementation.
* **Con**: If a service is compromised, it can reuse the token to call any other service in the system.

---

### 2. Token Exchange (Specific Audience)
Before making an inter-service call, a service sends its current JWT back to the STS to exchange it for a new token targeting a specific downstream service's audience (e.g., `iv.ecomm.com`).

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ca52cc6f-2fbb-47c9-aa6f-1db48ea9e60a/markdown_0/imgs/img_in_image_box_183_397_836_754.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A27Z%2F-1%2F%2F294ce7c167426422a36e667b37f68a8334d1f3962f8d310ff3473f4c18b38cfb" alt="Image" width="61%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7.2 Propagating the end user's identity in a JWT among microservices with token exchange</div> </div>

* **Pro**: Highly secure; limits token reuse.
* **Con**: High latency due to constant token exchange network calls.

---

### 3. Cross-Domain Token Exchange
When crossing trust domains, the gateway in the target domain exchanges the external token for one issued by its own STS, mapping user attributes between systems.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ca52cc6f-2fbb-47c9-aa6f-1db48ea9e60a/markdown_1/imgs/img_in_image_box_129_758_951_1167.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A28Z%2F-1%2F%2F095a2205189246c74cde9cfcfbf762c578f5cd4b5a1125d3eecbb1b56e04da6f" alt="Image" width="77%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7.3 Cross-domain authentication and user context sharing among multiple trust domains. The STS in the delivery domain trusts the STS in the ecomm domain.</div> </div>

* **Pro**: Decouples trust domain keys.
* **Con**: Requires trust agreement between domain authority servers.

---

### 4. Self-Issued JWT (Service Identity)
A service generates and signs its own JWT using its private key, indicating service-level identity for system-to-system authentication.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ca52cc6f-2fbb-47c9-aa6f-1db48ea9e60a/markdown_2/imgs/img_in_image_box_186_905_708_1209.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A28Z%2F-1%2F%2F1c2c81c5d533a0d21db9a5dab513796f666ca94bbe48c665b14ec8c285b0f9cf" alt="Image" width="49%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7.4 Self-issued JWT. The JWT is signed using the private key of the Order Processing microservice.</div> </div>

* **Pro**: Decouples services from the centralized STS for service authentication.
* **Con**: Recipient must manage key distribution to validate signatures.

---

### 5. Nested JWTs
To carry both the end-user identity and the calling service identity, the calling service wraps the user's token inside a self-issued JWT signed with its own private key.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//ca52cc6f-2fbb-47c9-aa6f-1db48ea9e60a/markdown_3/imgs/img_in_image_box_204_856_880_1150.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A29Z%2F-1%2F%2Fb16c50386a8dc053f9c40da39ea2800ae44399914ddefc8b8fb4662dc2af03c8" alt="Image" width="63%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7.5 A nested JWT: the Order Processing microservice creates its own JWT and embeds in it the JWT it receives from the downstream microservice (or the API gateway).</div> </div>

* **Pro**: Perfect auditing trace; tamper-proof propagation of user and service identity.
* **Con**: Complex validation logic; increases token payload size.

---

## 18.4 Building a Security Token Service (STS)

We implement a simple, Java-based Security Token Service that signs JWT access tokens using RSA public/private key pairs.

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//4e89d604-1cab-4bcb-81c6-dbfee25a2272/markdown_0/imgs/img_in_image_box_201_284_799_733.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A29Z%2F-1%2F%2F47f745e8bbb345420ac130373df34a530d924a5827d23cdf498b1c127d7ef38c" alt="Image" width="56%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7.6 STS issues a JWT access token to the web application.</div> </div>

### 1. Maven Configuration (`pom.xml`)
```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <!-- Nimbus JOSE JWT library for JWT creation and signature operations -->
    <dependency>
        <groupId>com.nimbusds</groupId>
        <artifactId>nimbus-jose-jwt</artifactId>
        <version>9.25</version>
    </dependency>
</dependencies>
```

### 2. Java Token Controller: `TokenService.java`
This controller exposes a POST `/oauth/token` endpoint to authenticate users and generate a signed access token:

```java
package com.ftgo.sts;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.JWSSigner;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;

@SpringBootApplication
@RestController
public class TokenService {

    private static RSAPrivateKey privateKey;
    public static RSAPublicKey publicKey;
    public static KeyPair keyPair;

    static {
        try {
            // Generate RSA key pair for cryptographic signing
            KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
            kpg.initialize(2048);
            keyPair = kpg.generateKeyPair();
            privateKey = (RSAPrivateKey) keyPair.getPrivate();
            publicKey = (RSAPublicKey) keyPair.getPublic();
        } catch (Exception e) {
            throw new RuntimeException("Failed to initialize cryptographic key pairs!", e);
        }
    }

    public static void main(String[] args) {
        SpringApplication.run(TokenService.class, args);
    }

    @PostMapping(value = "/oauth/token", consumes = "application/x-www-form-urlencoded")
    public ResponseEntity<Map<String, Object>> issueToken(
            @RequestHeader("Authorization") String clientAuth,
            @RequestParam("grant_type") String grantType,
            @RequestParam("username") String username,
            @RequestParam("password") String password,
            @RequestParam("scope") String scope) {

        // 1. Basic Client Application authentication
        if (clientAuth == null || !clientAuth.startsWith("Basic ")) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }

        // 2. Validate End-User Credentials
        if (!"peter".equals(username) || !"peter123".equals(password)) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).build();
        }

        try {
            // 3. Construct JWT Claims Set
            JWSSigner signer = new RSASSASigner(privateKey);
            JWTClaimsSet claimsSet = new JWTClaimsSet.Builder()
                    .subject(username)
                    .issuer("sts.ecomm.com")
                    .audience("*.ecomm.com")
                    .expirationTime(new Date(new Date().getTime() + 3600 * 1000)) // 1 hour expiry
                    .issueTime(new Date())
                    .claim("scope", scope)
                    .claim("authorities", new String[]{"ROLE_USER"})
                    .claim("client_id", "applicationid")
                    .build();

            // 4. Create and sign JWS
            SignedJWT signedJWT = new SignedJWT(new JWSHeader(JWSAlgorithm.RS256), claimsSet);
            signedJWT.sign(signer);

            Map<String, Object> response = new HashMap<>();
            response.put("access_token", signedJWT.serialize());
            response.put("token_type", "bearer");
            response.put("expires_in", 3600);
            response.put("scope", scope);

            return ResponseEntity.ok(response);

        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }
}
```

### 3. Exposing JWKS Endpoint: `JwksEndpointController.java`
To allow downstream microservices to fetch the verification public key dynamically, the STS exposes a standard JSON Web Key Set (JWKS) REST endpoint:

```java
package com.ftgo.sts.controller;

import com.ftgo.sts.TokenService;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import java.util.Map;

@RestController
public class JwksEndpointController {

    @GetMapping("/.well-known/jwks.json")
    public Map<String, Object> getJwks() {
        // Build JSON Web Key object from the RSA public key
        RSAKey rsaKey = new RSAKey.Builder(TokenService.publicKey)
                .keyID("sts-key-id-01")
                .build();
        
        JWKSet jwkSet = new JWKSet(rsaKey);
        return jwkSet.toJSONObject();
    }
}
```

---

## 18.5 Custom Gateway Token Exchange Filter

In a secure architecture, external clients use **Reference Tokens** (opaque strings). The API Gateway intercepts requests and exchanges the client's reference token for a signed JWT from the STS before routing to backend microservices:

<div style="text-align: center;"><img src="https://pplines-online.bj.bcebos.com/deploy/official/paddleocr/pp-ocr-vl-16-online//b31deaec-4f50-4873-8f3a-b3b52af1cde9/markdown_1/imgs/img_in_image_box_202_555_788_1001.jpg?authorization=bce-auth-v1%2FALTAKDN8mY5KlNI7zaRpLmOqrw%2F2026-06-26T23%3A20%3A30Z%2F-1%2F%2F7a38a0a17bdf1184d019581f7fe7cfb39a355a0be7ed696c42153608480f4520" alt="Image" width="55%" /></div>

<div style="text-align: center;"><div style="text-align: center;">Figure 7.7 Token exchange with STS</div> </div>

```java
package com.ftgo.gateway.filters;

import org.springframework.cloud.gateway.filter.GatewayFilter;
import org.springframework.cloud.gateway.filter.factory.AbstractGatewayFilterFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import java.util.Map;

@Component
public class JwtExchangeGatewayFilterFactory extends AbstractGatewayFilterFactory<JwtExchangeGatewayFilterFactory.Config> {

    private final WebClient webClient;

    public JwtExchangeGatewayFilterFactory(WebClient.Builder webClientBuilder) {
        super(Config.class);
        this.webClient = webClientBuilder.baseUrl("https://localhost:8443").build();
    }

    public static class Config {
        // Configuration parameters
    }

    @Override
    public GatewayFilter apply(Config config) {
        return (exchange, chain) -> {
            String authorizationHeader = exchange.getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION);

            if (authorizationHeader == null || !authorizationHeader.startsWith("Bearer ")) {
                return chain.filter(exchange);
            }

            String opaqueToken = authorizationHeader.substring(7);

            // Execute token exchange request to STS
            return webClient.post()
                    .uri("/oauth/token")
                    .header(HttpHeaders.AUTHORIZATION, "Basic YXBwbGljYXRpb25pZDphcHBsaWNhdGlvbnNlY3JldA==")
                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                    .body(BodyInserters.fromFormData("grant_type", "token_exchange")
                            .with("subject_token", opaqueToken))
                    .retrieve()
                    .bodyToMono(Map.class)
                    .flatMap(response -> {
                        String jwtToken = (String) response.get("access_token");

                        // Mutate request headers to replace the reference token with the exchanged JWT
                        exchange.getRequest().mutate()
                                .header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtToken)
                                .build();

                        return chain.filter(exchange);
                    });
        };
    }
}
```

---

## 18.6 Downstream JWT Validation & Context Extraction

When a microservice receives the request, it validates the JWT signature using the public key from the STS and establishes the security context.

```java
package com.ftgo.order.security;

import com.nimbusds.jose.crypto.RSASSAVerifier;
import com.nimbusds.jwt.SignedJWT;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import javax.servlet.*;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.security.interfaces.RSAPublicKey;
import java.util.Date;
import java.util.List;
import java.util.stream.Collectors;

@Component
public class JwtContextFilter implements Filter {

    private final RSAPublicKey stsPublicKey;

    public JwtContextFilter(RSAPublicKey stsPublicKey) {
        this.stsPublicKey = stsPublicKey;
    }

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpServletRequest = (HttpServletRequest) request;
        HttpServletResponse httpServletResponse = (HttpServletResponse) response;

        String authHeader = httpServletRequest.getHeader("Authorization");

        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            try {
                String token = authHeader.substring(7);
                SignedJWT signedJWT = SignedJWT.parse(token);

                // 1. Verify Cryptographic Signature using STS Public Key
                RSASSAVerifier verifier = new RSASSAVerifier(stsPublicKey);
                if (!signedJWT.verify(verifier)) {
                    httpServletResponse.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Invalid cryptographic signature!");
                    return;
                }

                // 2. Verify Expiration Time
                Date expirationTime = signedJWT.getJWTClaimsSet().getExpirationTime();
                if (expirationTime == null || new Date().after(expirationTime)) {
                    httpServletResponse.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Token has expired!");
                    return;
                }

                // 3. Extract Subject and Authorities
                String username = signedJWT.getJWTClaimsSet().getSubject();
                @SuppressWarnings("unchecked")
                List<String> authorities = (List<String>) signedJWT.getJWTClaimsSet().getClaim("authorities");

                List<SimpleGrantedAuthority> mappedAuthorities = authorities.stream()
                        .map(SimpleGrantedAuthority::new)
                        .collect(Collectors.toList());

                // 4. Bind Authentication Context to Spring Security
                UsernamePasswordAuthenticationToken auth =
                        new UsernamePasswordAuthenticationToken(username, null, mappedAuthorities);
                SecurityContextHolder.getContext().setAuthentication(auth);

            } catch (Exception e) {
                httpServletResponse.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Token validation failed!");
                return;
            }
        }

        chain.doFilter(request, response);
    }
}
```

---

## 18.7 Propagating JWT Contexts in Reactive Spring WebFlux

In reactive systems, blocking thread-local context models (like `SecurityContextHolder`) are unusable because requests run asynchronously across different threads. Instead, WebFlux provides a reactive context map.

We write a custom `ExchangeFilterFunction` to extract the JWT from the reactive security context and inject it into outgoing Reactor `WebClient` requests:

```java
package com.ftgo.order.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.core.context.ReactiveSecurityContextHolder;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ExchangeFilterFunction;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

@Configuration
public class ReactiveWebClientConfig {

    @Bean
    public WebClient webClient() {
        return WebClient.builder()
                .baseUrl("https://localhost:8443")
                .filter(propagateJwtFilter())
                .build();
    }

    private ExchangeFilterFunction propagateJwtFilter() {
        return (request, next) -> ReactiveSecurityContextHolder.getContext()
                .map(SecurityContext::getAuthentication)
                .flatMap(authentication -> {
                    if (authentication == null || authentication.getCredentials() == null) {
                        return next.exchange(request);
                    }
                    
                    // Retrieve JWT from reactive session authentication details
                    String jwtToken = authentication.getCredentials().toString();
                    
                    ClientRequest filteredRequest = ClientRequest.from(request)
                            .header("Authorization", "Bearer " + jwtToken)
                            .build();
                    
                    return next.exchange(filteredRequest);
                })
                .switchIfEmpty(next.exchange(request));
    }
}
```

---

## 18.8 Interprocess Cryptographic Context Propagation with gRPC

When microservices communicate using high-performance **gRPC**, we propagate the JWT context using **gRPC Metadata (headers)** rather than HTTP headers.

We write a client interceptor (`JwtClientInterceptor`) to inject the JWT from ThreadLocal storage into the call's metadata, and a server interceptor (`JwtServerInterceptor`) to extract, validate, and bind it to the thread context of the RPC execution.

### 1. gRPC Client-Side Context Interceptor
```java
package com.ftgo.order.grpc;

import io.grpc.*;
import org.springframework.security.core.context.SecurityContextHolder;

public class JwtClientInterceptor implements ClientInterceptor {

    private static final Metadata.Key<String> AUTH_HEADER_KEY =
            Metadata.Key.of("Authorization", Metadata.ASCII_STRING_MARSHALLER);

    @Override
    public <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
            MethodDescriptor<ReqT, RespT> method, CallOptions callOptions, Channel next) {
        
        return new ForwardingClientCall.SimpleForwardingClientCall<ReqT, RespT>(next.newCall(method, callOptions)) {
            @Override
            public void start(Listener<RespT> responseListener, Metadata headers) {
                // Read current token from Spring Security ThreadLocal
                if (SecurityContextHolder.getContext().getAuthentication() != null) {
                    Object credentials = SecurityContextHolder.getContext().getAuthentication().getCredentials();
                    if (credentials != null) {
                        headers.put(AUTH_HEADER_KEY, "Bearer " + credentials.toString());
                    }
                }
                super.start(responseListener, headers);
            }
        };
    }
}
```

---

### 2. gRPC Server-Side Validation Interceptor
```java
package com.ftgo.order.grpc;

import com.nimbusds.jose.crypto.RSASSAVerifier;
import com.nimbusds.jwt.SignedJWT;
import io.grpc.*;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import java.security.interfaces.RSAPublicKey;
import java.util.List;
import java.util.stream.Collectors;

public class JwtServerInterceptor implements ServerInterceptor {

    private static final Metadata.Key<String> AUTH_HEADER_KEY =
            Metadata.Key.of("Authorization", Metadata.ASCII_STRING_MARSHALLER);

    private final RSAPublicKey verificationKey;

    public JwtServerInterceptor(RSAPublicKey verificationKey) {
        this.verificationKey = verificationKey;
    }

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call, Metadata headers, ServerCallHandler<ReqT, RespT> next) {

        String authHeader = headers.get(AUTH_HEADER_KEY);

        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            call.close(Status.UNAUTHENTICATED.withDescription("Missing Authorization metadata!"), new Metadata());
            return new ServerCall.Listener<ReqT>() {};
        }

        try {
            String token = authHeader.substring(7);
            SignedJWT signedJWT = SignedJWT.parse(token);

            // Verify JWT Signature
            RSASSAVerifier verifier = new RSASSAVerifier(verificationKey);
            if (!signedJWT.verify(verifier)) {
                call.close(Status.UNAUTHENTICATED.withDescription("Invalid JWT Signature!"), new Metadata());
                return new ServerCall.Listener<ReqT>() {};
            }

            // Extract claims and map to security context
            String user = signedJWT.getJWTClaimsSet().getSubject();
            @SuppressWarnings("unchecked")
            List<String> roles = (List<String>) signedJWT.getJWTClaimsSet().getClaim("authorities");

            List<SimpleGrantedAuthority> authorities = roles.stream()
                    .map(SimpleGrantedAuthority::new)
                    .collect(Collectors.toList());

            UsernamePasswordAuthenticationToken auth = new UsernamePasswordAuthenticationToken(user, token, authorities);
            SecurityContextHolder.getContext().setAuthentication(auth);

        } catch (Exception e) {
            call.close(Status.UNAUTHENTICATED.withDescription("Token validation failed!"), new Metadata());
            return new ServerCall.Listener<ReqT>() {};
        }

        try {
            return next.startCall(call, headers);
        } finally {
            // Clear context thread-local after RPC executes
            SecurityContextHolder.clearContext();
        }
    }
}
```

---

## 18.9 Programmatic Cryptographic Token Validation

For lightweight helper scripts or services running outside large frameworks, you can parse and validate tokens programmatically using standard algorithms (HMAC-SHA256 or RSA):

```java
package com.ftgo.order.security;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.crypto.MACVerifier;
import com.nimbusds.jose.crypto.RSASSAVerifier;
import com.nimbusds.jwt.SignedJWT;
import java.security.interfaces.RSAPublicKey;

public class ProgrammaticTokenVerifier {

    // 1. Validate HMAC-SHA256 Token
    public static boolean verifyHmacToken(String token, String sharedSecret) {
        try {
            SignedJWT signedJWT = SignedJWT.parse(token);
            MACVerifier verifier = new MACVerifier(sharedSecret.getBytes());
            return signedJWT.verify(verifier) && JWSAlgorithm.HS256.equals(signedJWT.getHeader().getAlgorithm());
        } catch (Exception e) {
            return false;
        }
    }

    // 2. Validate RSA-SHA256 Token
    public static boolean verifyRsaToken(String token, RSAPublicKey publicKey) {
        try {
            SignedJWT signedJWT = SignedJWT.parse(token);
            RSASSAVerifier verifier = new RSASSAVerifier(publicKey);
            return signedJWT.verify(verifier) && JWSAlgorithm.RS256.equals(signedJWT.getHeader().getAlgorithm());
        } catch (Exception e) {
            return false;
        }
    }
}
```

---

## 18.10 Legacy Migration: SAML-to-JWT Token Bridge

When migrating legacy enterprise applications to a microservices architecture, you will often need to bridge trust domains by exchanging XML-based **SAML 2.0 Assertions** for signed JSON Web Tokens.

The following controller (`SamlTokenBridgeController`) parses a validated SAML request and uses the subject details to mint a signed JWT for use in backend microservices:

```java
package com.ftgo.sts.migration;

import com.ftgo.sts.TokenService;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.nimbusds.jose.crypto.RSASSASigner;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;

@RestController
public class SamlTokenBridgeController {

    private final RSAPrivateKey privateKey;

    public SamlTokenBridgeController() {
        this.privateKey = (RSAPrivateKey) TokenService.keyPair.getPrivate();
    }

    @PostMapping(value = "/api/v1/bridge/saml", consumes = "application/xml")
    public ResponseEntity<Map<String, Object>> exchangeSamlForJwt(@RequestBody String samlXml) {
        try {
            // 1. Parse SAML XML Document (naive validation for demonstration)
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true);
            DocumentBuilder builder = factory.newDocumentBuilder();
            Document doc = builder.parse(new ByteArrayInputStream(samlXml.getBytes(StandardCharsets.UTF_8)));

            // Extract the Subject (NameID) from SAML Assertion
            Element nameIdElement = (Element) doc.getElementsByTagNameNS("urn:oasis:names:tc:SAML:2.0:assertion", "NameID").item(0);
            if (nameIdElement == null) {
                return ResponseEntity.status(HttpStatus.BAD_REQUEST).build(); // Missing user context
            }
            String username = nameIdElement.getTextContent();

            // 2. Map SAML context and mint fresh JWT
            JWTClaimsSet claimsSet = new JWTClaimsSet.Builder()
                    .subject(username)
                    .issuer("bridge.ecomm.com")
                    .audience("*.ecomm.com")
                    .expirationTime(new Date(new Date().getTime() + 1800 * 1000)) // 30 mins expiry
                    .issueTime(new Date())
                    .claim("authorities", new String[]{"ROLE_USER"})
                    .claim("origin", "SAML_ASSERTION_EXCHANGE")
                    .build();

            SignedJWT signedJWT = new SignedJWT(new JWSHeader(JWSAlgorithm.RS256), claimsSet);
            signedJWT.sign(new RSASSASigner(privateKey));

            Map<String, Object> response = new HashMap<>();
            response.put("access_token", signedJWT.serialize());
            response.put("token_type", "bearer");
            response.put("expires_in", 1800);

            return ResponseEntity.ok(response);

        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }
}
```

---

## 18.11 Integration Testing with Mock JWT Providers

We write a test class (`PaymentsControllerSecurityTest`) verifying that our downstream endpoints block invalid tokens but permit requests containing valid credentials:

```java
package com.ftgo.order.security;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.web.servlet.MockMvc;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
public class OrderEndpointSecurityTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    public void anonymousRequestsShouldBeRejectedWithUnauthorized() throws Exception {
        mockMvc.perform(get("/orders/11"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    public void requestsWithValidTokenShouldBeAllowed() throws Exception {
        mockMvc.perform(get("/orders/11")
                .with(SecurityMockMvcRequestPostProcessors.jwt()
                        .jwt(jwt -> jwt.claim("scope", "user")))) // Inject Mock JWT
                .andExpect(status().isOk());
    }
}
```

---

## 18.11 OWASP Top 10 API Security Mitigations in JWT Context Propagation

By implementing cryptographic context propagation using JWTs, the architecture mitigates several critical vulnerabilities defined in the **OWASP API Security Top 10**:

1. **API1:2019 Broken Object Level Authorization (BOLA)**:
   - *Mitigation*: Our user context interceptors extract the `sub` (Subject / User ID) claim from the validated JWT and bind it to a thread-local variable. Controller methods query database records and compare the owner identifier of the record against this thread-local ID, preventing users from accessing orders belonging to other consumers.
2. **API2:2019 Broken User Authentication**:
   - *Mitigation*: All backend services reject requests that do not present a cryptographically signed JWT. Signature validity is verified against public keys retrieved from the central JWKS endpoint.
3. **API5:2019 Broken Function Level Authorization (BFLA)**:
   - *Mitigation*: Access to high-privilege endpoints (e.g. administrative order cancellation overrides) is restricted using Spring Security's method-level annotations (e.g. `@PreAuthorize("hasRole('ADMIN')")`). The authorization engine matches these constraints against the client roles/scopes populated inside the verified JWT token claims.

---

## Chapter Summary

* Plaintext header propagation is vulnerable to injection attacks, lack of integrity verification, and lack of non-repudiation.
* **JSON Web Tokens (JWT)** provide a cryptographically signed wrapper to propagate user and service claims securely across microservices.
* Key context propagation architectures include **Shared JWTs**, **Token Exchange** (swapping user tokens for audience-specific tokens), **Self-Issued JWTs** (asserting service identity), and **Nested JWTs** (nesting user tokens inside service signatures).
* A **Security Token Service (STS)** can mint tokens using private keys and expose public keys via standard **JWKS endpoints**.
* **API Gateways** can dynamically exchange opaque client reference tokens for signed backend JWTs using exchange filters.
* Reactive microservices use **Spring WebFlux ExchangeFilterFunctions** to propagate tokens asynchronously using Reactor context maps.
* Interprocess **gRPC** calls propagate security context within metadata headers using client and server interceptors.
* Cryptographic validation can be implemented programmatically using nimbus JWS verifiers or wrapped inside spring MVC controller filters.
* Legacy authentication contexts can be exchanged for JWT access tokens using custom **SAML-to-JWT Bridge controllers**.
* **OWASP Top 10 Mitigations** prevent BOLA, BFLA, and Broken User Authentication through validation filters and token scope enforcement.

