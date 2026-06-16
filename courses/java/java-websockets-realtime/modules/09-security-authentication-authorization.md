# Module 9: Security, Authentication, and Authorization

In standard stateless REST architectures, security is applied request-by-request using servlet filters. In real-time systems, we manage stateful, long-lived TCP connections. A user authorized at 10:00 AM might have their credentials revoked or their JWT token expire at 10:30 AM while the WebSocket link remains wide open.

This module covers the architecture of real-time security. We will explore how to integrate Spring Security, implement JWT and Cookie authentication, manage token expiration without dropping connections, propagate user principals, and apply threat mitigations (such as rate limiting, TLS/WSS configuration, and Cross-Site WebSocket Hijacking prevention). We will wrap up by building a fully secured chat server.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the architectural differences** between stateless REST filters and stateful WebSocket message authorization.
2. **Implement JWT token extraction and validation** inside incoming STOMP connection channels.
3. **Configure token refresh strategies** to re-verify long-lived real-time connections without socket drops.
4. **Propagate user principals** to enable secure private user routing (`/user/queue/*`).
5. **Mitigate Cross-Site WebSocket Hijacking (CSWSH)**, rate-limit clients, and enforce payload size limits.
6. **Deploy Spring Security configurations** to restrict STOMP destinations based on user roles.

---

## 1. Real-Time Security Architecture

In standard HTTP REST web applications, every transaction is authenticated individually:

```
Stateless REST Request Filtering
Client ──► [Filter: Authenticate JWT] ──► [Controller: doWork] ──► Response
```

In WebSockets, authentication is **split into two distinct phases**:

```
Stateful WebSocket Connection Security
Phase 1: HTTP Upgrade Handshake (Filter runs ONCE)
Client ──► [Upgrade Handshake Filter] ──► [TCP Socket Opened]

Phase 2: Message Frame Channel (Channel Interceptors run for EVERY frame)
Client ──► [Frame: SEND /app/chat] ──► [ChannelInterceptor: Auth Check] ──► [Controller]
```

- **Phase 1: Handshake (HTTP Level)**: Executes once when switching protocols. You can inspect cookies and headers, but standard JWT `Authorization` headers are difficult to pass here because native browser WebSockets APIs do not support sending custom headers during the initial handshake.
- **Phase 2: Channel Interception (STOMP Level)**: Executed for every STOMP frame passing through the channel. This is where you inspect custom metadata headers and validate message authorizations.

---

## 2. Authentication Paradigms in WebSockets

### 1. JWT Token Authentication (STOMP Level)
Since browsers cannot send custom headers during the HTTP upgrade handshake, the standard enterprise pattern is to establish the TCP connection, and then pass the JWT token in the headers of the first STOMP **`CONNECT`** frame:
```http
CONNECT
accept-version:1.2
Authorization:Bearer eyJhbGciOiJIUzI1NiIsIn...

^@
```
Spring's `ChannelInterceptor` intercepts this frame, parses the bearer token, validates the signature, and populates the session's security context.

### 2. Cookie-Based Authentication (Handshake Level)
If your application relies on HTTP session cookies:
- The browser automatically transmits cookies during the initial HTTP upgrade request.
- The server validates the cookie in a `HandshakeInterceptor` or servlet filter.
- **The Caveat**: Reusing session cookies exposes the application to **Cross-Site WebSocket Hijacking (CSWSH)**. Origin checking must be strictly configured to prevent malicious sites from establishing connections.

### 3. Token Expiration and Refresh Strategies
What happens when a user's JWT expires 15 minutes into a 2-hour WebSocket session?
- **Bad Practice**: Dropping the socket connection as soon as the token expires. This creates thundering herd reconnection storms on the authentication server.
- **Good Practice (Dynamic Re-Verification)**:
  1. The server allows the socket to remain open.
  2. The client application tracks token lifetimes. When the JWT is refreshed via standard REST calls, the client sends a custom STOMP message to the server containing the new token (e.g., to destination `/app/auth.refresh`).
  3. The server interceptor receives the message, re-decodes the new JWT, updates the session's `Principal` validity, and continues routing frames without socket drops.

---

## 3. Authorization and Principal Propagation

Once a user is authenticated during the STOMP handshake, their identity must be bound to the WebSocket session as a `java.security.Principal`.

- **Principal Propagation**:
  When a user sends a message to an `@MessageMapping` controller, Spring automatically extracts the session `Principal` and injects it into the controller method arguments.
- **User Destinations**:
  Binding the `Principal` enables the `/user/queue/` routing engine. When Server 1 wants to notify user "Bob", it pushes the message to `/user/Bob/queue/alerts`. The system resolves "Bob" to his active socket session ID and delivers the frame securely.

---

## 4. Real-Time Threat Mitigation & Hardening

Securing real-time sockets requires applying mitigations at different layers:

### 1. TLS/WSS (Forced Encrypted Transport)
Always force the use of secure WebSocket transport (`wss://`) in production.
- **Why**: Plain WebSockets (`ws://`) transmit data as unencrypted TCP segments. Intermediate routers can inspect, inject, or tamper with the byte stream. Additionally, standard proxies often terminate unencrypted `ws://` connections, assuming they are violating standard HTTP guidelines.

### 2. Origin Validation (Mitigating CSWSH)
To prevent unauthorized sites from triggering handshakes, validate the `Origin` header during connection setup.
```java
@Override
public void registerStompEndpoints(StompEndpointRegistry registry) {
    registry.addEndpoint("/ws")
            // Reject any origin not listed in this whitelist
            .setAllowedOrigins("https://mysecureapp.com");
}
```

### 3. Rate Limiting (Token Bucket Algorithm)
To prevent a single client session from overloading our server by sending a flood of messages, we can implement an in-memory token bucket rate limiter inside our STOMP channel interceptor.

```java
package com.example.realtime.security.limiter;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class StompRateLimiter {

    private static class TokenBucket {
        final double capacity = 20.0;     // Max burst permit size
        final double refillRate = 5.0;    // Add 5 tokens per second
        double tokens = 20.0;
        long lastRefillTime = System.currentTimeMillis();

        synchronized boolean tryConsume() {
            long now = System.currentTimeMillis();
            double secondsElapsed = (now - lastRefillTime) / 1000.0;
            lastRefillTime = now;

            // Refill tokens based on elapsed time
            tokens = Math.min(capacity, tokens + (secondsElapsed * refillRate));

            if (tokens >= 1.0) {
                tokens -= 1.0;
                return true; // Permit granted
            }
            return false; // Rate limit exceeded
        }
    }

    private final Map<String, TokenBucket> sessionBuckets = new ConcurrentHashMap<>();

    public boolean isAllowed(String sessionId) {
        return sessionBuckets.computeIfAbsent(sessionId, k -> new TokenBucket()).tryConsume();
    }

    public void removeSession(String sessionId) {
        sessionBuckets.remove(sessionId);
    }
}
```

### 4. Input Validation (XSS Prevention)
When broadcasting text messages to a room, validate and sanitize payloads.
- **Why**: If Client A sends a message containing `<script>stealCookies()</script>` and the server broadcasts it without validation, the script will execute in all other users' browsers.
- **The Fix**: Clean payload text using HTML sanitizers (like HTML Sanitive library) before broadcasting.

### 5. DoS Prevention (Message Size Limits)
Limit the maximum message size to protect JVM memory. If a client attempts to upload an 80 MB binary frame, the server heap will quickly saturate.
- In Spring, configure maximum sizes using factory settings (e.g., limiting text sizes to 64 KB and binary sizes to 256 KB).

---

## 5. Hands-On Lab: Hardening a WebSocket Configuration

In this lab, you will learn how to configure Spring Security to restrict access to WebSocket endpoints and apply connection limit policies.

### Steps:
1. Verify Spring Security dependencies are present in your project.
2. Create a secure message registry configuration extending `AbstractSecurityWebSocketMessageBrokerConfigurer` to map channel permits.
3. Configure the application container to drop connections that exceed maximum frame buffers.

---

## 6. Mini Project: Authenticated Chat with Token Security

We will implement a complete, compilable Spring Boot application featuring secure STOMP endpoints. 

The project contains:
- **`WebSecurityConfig.java`**: Configures Spring Security to permit WebSocket handshakes on `/ws-chat/**` while securing other endpoints.
- **`WebSocketSecurityConfig.java`**: Restricts STOMP message channel destinations, requiring authentication for all subscriptions and application messages.
- **`JwtAuthenticationInterceptor.java`**: Intercepts STOMP `CONNECT` frames, extracts bearer tokens from headers, validates signatures, and maps the user's `Principal` context. Includes rate limiting validation checks.
- **`SecureChatController.java`**: Handles messaging, injecting the secure `Principal` to log transmissions.

```
                              +-------------------------------------------+
                              |          SECURED STOMP SERVER             |
                              |                                           |
                              |  [WebSecurityFilterChain]                 |
                              |         │ (Permits /ws-chat)              |
                              |  [WebSocketMessageSecurity]               |
                              |         │ (Requires AUTH for topics)      |
                              |  [JwtAuthenticationInterceptor]           |
                              |         │ (Extracts & Validates Token)    |
                              |  [SecureChatController]                   |
                              +─────────────────▲─────────────────────────+
                                                │
                               STOMP CONNECT    │  STOMP MESSAGE
                               (Bearer JWT)     │  (Principal check)
                                                │
                                          +──────────+
                                          | Client   |
                                          +──────────+
```

### Complete Implementation:

#### 1. Web Security Configuration (`WebSecurityConfig.java`)

```java
package com.example.realtime.security.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity
public class WebSecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable) // Disable CSRF for simplified REST ingest
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/ws-chat/**").permitAll() // Allow initial WebSocket handshake connections
                .anyRequest().authenticated()
            );
        return http.build();
    }
}
```

#### 2. Message Channel Security Config (`WebSocketSecurityConfig.java`)
*Note: In Spring Security 6, we configure message security rules by extending `AbstractSecurityWebSocketMessageBrokerConfigurer` or defining a custom `ChannelSecurityInterceptor` authorization bean.*

```java
package com.example.realtime.security.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.messaging.MessageSecurityMetadataSourceRegistry;
import org.springframework.security.config.annotation.web.socket.AbstractSecurityWebSocketMessageBrokerConfigurer;

@Configuration
public class WebSocketSecurityConfig extends AbstractSecurityWebSocketMessageBrokerConfigurer {

    @Override
    protected void configureInbound(MessageSecurityMetadataSourceRegistry messages) {
        messages
            // Permit anyone to invoke the close socket destination
            .simpDestMatchers("/app/chat.disconnect").permitAll()
            // Require ROLE_USER to subscribe to chat topics
            .simpSubscribeDestMatchers("/topic/secure.**").hasRole("USER")
            // Require ROLE_USER to send messages to application mappings
            .simpMessageDestMatchers("/app/chat.send.**").hasRole("USER")
            // Catch-all rule: any other STOMP message type requires authentication
            .anyMessage().authenticated();
    }

    @Override
    protected boolean SameOriginDisabled() {
        // Disable CSRF/Same-Origin checks for STOMP frames to simplify testing.
        // In production, keep this enabled to prevent Cross-Site Hijacking.
        return true;
    }
}
```

#### 3. JWT Channel Interceptor (`JwtAuthenticationInterceptor.java`)

```java
package com.example.realtime.security.interceptor;

import com.example.realtime.security.limiter.StompRateLimiter;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import java.security.Principal;
import java.util.List;

@Component
public class JwtAuthenticationInterceptor implements ChannelInterceptor {

    private final StompRateLimiter rateLimiter = new StompRateLimiter();

    @Override
    public Message<?> preSend(Message<?> message, MessageChannel channel) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(message);
        String sessionId = accessor.getSessionId();

        // 1. Enforce message rate limiting
        if (sessionId != null && !StompCommand.CONNECT.equals(accessor.getCommand())) {
            if (!rateLimiter.isAllowed(sessionId)) {
                System.err.println("[STOMP Security] Message rejected. Session rate limit exceeded: " + sessionId);
                throw new IllegalStateException("Rate limit exceeded. Too many messages.");
            }
        }

        // 2. Intercept CONNECT command to perform JWT authentication
        if (StompCommand.CONNECT.equals(accessor.getCommand())) {
            String authHeader = accessor.getFirstNativeHeader("Authorization");
            System.out.println("[JWT Interceptor] CONNECT intercepted. Authorization header: " + authHeader);

            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                throw new IllegalArgumentException("Access Denied: Missing Bearer Token.");
            }

            String token = authHeader.substring(7);
            
            // Simulating JWT validation logic
            if ("valid_premium_jwt".equals(token)) {
                // Build authorities list
                List<SimpleGrantedAuthority> authorities = List.of(new SimpleGrantedAuthority("ROLE_USER"));
                
                // Create user principal
                UsernamePasswordAuthenticationToken auth = new UsernamePasswordAuthenticationToken(
                    "alex_premium", // Username
                    null,
                    authorities
                );

                // Bind the authenticated principal to the STOMP session accessor
                accessor.setUser(auth);
                
                // Also update the local Spring SecurityContext for the executing thread
                SecurityContextHolder.getContext().setAuthentication(auth);
                System.out.println("[JWT Interceptor] Auth successful. Principal bound: " + auth.getName());
            } else {
                System.err.println("[JWT Interceptor] Auth failed: Token invalid.");
                throw new IllegalArgumentException("Access Denied: Token validation failed.");
            }
        }

        // Clean up rate limiter mapping on disconnect
        if (StompCommand.DISCONNECT.equals(accessor.getCommand()) && sessionId != null) {
            rateLimiter.removeSession(sessionId);
        }

        return message;
    }
}
```

#### 4. Secured Chat Controller (`SecureChatController.java`)

```java
package com.example.realtime.security.controller;

import org.springframework.messaging.handler.annotation.DestinationVariable;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Controller;
import java.security.Principal;

@Controller
public class SecureChatController {

    private final SimpMessagingTemplate messagingTemplate;

    public SecureChatController(SimpMessagingTemplate messagingTemplate) {
        this.messagingTemplate = messagingTemplate;
    }

    /**
     * Secure message routing. Spring automatically injects the authenticated Principal.
     */
    @MessageMapping("/chat.send.secure.{room}")
    public void sendSecureMessage(@DestinationVariable String room, @Payload String textPayload, Principal principal) {
        if (principal == null) {
            System.err.println("Secure Route Rejected: Unauthenticated access attempt!");
            return;
        }

        System.out.println("[Secure Route] Room: " + room + " | Sender: " + principal.getName() + " | Content: " + textPayload);

        String secureMessage = "{\"sender\":\"" + principal.getName() + "\",\"content\":\"" + textPayload + "\"}";
        
        // Broadcast the secure payload
        messagingTemplate.convertAndSend("/topic/secure." + room, secureMessage);
    }
}
```

---

## 7. Common Mistakes & Debugging Scenarios

### Scenario A: Principal Resolves to `null` inside `@MessageMapping`
* **The Problem**: A developer implements custom token validation in a `ChannelInterceptor`. However, inside their `@MessageMapping` controller method, calling `Principal.getName()` throws a `NullPointerException` because the `Principal` parameter is `null`.
* **Why it happens**: When creating the `UsernamePasswordAuthenticationToken` in the interceptor, the developer did not register it on the **`StompHeaderAccessor`** using `accessor.setUser(authentication)`. They only set it on the thread's local context (`SecurityContextHolder.getContext().setAuthentication()`). Since the message routing thread is different from the inbound interceptor thread, the local context is lost, and the controller receives a `null` Principal.
* **The Fix**: Always register the authenticated principal object directly on the accessor using `accessor.setUser(auth)` (as shown in line 59 of the interceptor code).

### Scenario B: CSWSH Handshake Errors (Origin Verification Failures)
* **The Problem**: You deploy a secured STOMP service to production. The mobile app connects successfully, but browser-based frontends fail to connect, returning `HTTP 403 Forbidden` errors.
* **Why it happens**: Browser-based WebSocket handshakes transmit the standard `Origin` header. Spring Boot WebSocket endpoints enforce strict CORS checks. If the client domain does not match the configured allowed origins whitelist, the server rejects the upgrade.
* **The Fix**: Configure `.setAllowedOrigins()` in your config files to whitelist client domains.

---

## 8. Technical Interview Questions

### Question 1: REST vs. WebSocket Security Architecture
*How does security authorization differ between stateless REST API requests and stateful real-time WebSockets connections? What is the role of channel interceptors?*

**Answer**:
- **Stateless REST**: Security is checked for every individual request using servlet filters. The filter reads the auth token, validates it, populates the context, executes the request, and clears the context.
- **Stateful WebSockets**: The connection is persistent. Checking security parameters only during the initial HTTP upgrade handshake is insufficient because a user's permissions can change or their token can expire while the socket remains open. 
- **Channel Interceptors** solve this by intercepting every individual STOMP frame passing through the connection. They allow you to apply security checks (like JWT validation or role-based checks) to every `SEND` or `SUBSCRIBE` command, ensuring that access control is enforced dynamically throughout the lifetime of the socket connection.

---

### Question 2: Mitigating Cross-Site WebSocket Hijacking
*What is Cross-Site WebSocket Hijacking (CSWSH)? How do you protect a Spring Boot WebSocket application against it?*

**Answer**:
**CSWSH** is a CSRF-like attack targeting WebSockets:
1. A user logged into a bank site (`bank.com`) visits a malicious site (`evil.com`).
2. `evil.com` executes JavaScript attempting to open a WebSocket connection to `bank.com/ws-api`.
3. The browser automatically attaches `bank.com` session cookies to the request.
4. If the server accepts the upgrade, the malicious site gains access to the secure socket.

**Mitigation**:
1. **Validate the `Origin` Header**: Reject any upgrade request where the `Origin` header does not match your whitelisted domain.
2. **Token-Based Authentication**: Avoid relying solely on cookies for authentication. Force clients to pass a JWT token in the headers of their first STOMP `CONNECT` frame. Since `evil.com` cannot read the user's JWT from their browser storage, it cannot authenticate.

---

## Summary
- **Stateless REST Security** runs once per request, while **Stateful WebSocket Security** requires checking both the upgrade handshake and individual STOMP frames using channel interceptors.
- **Token Authentication** is best achieved by passing a JWT token inside the STOMP `CONNECT` frame headers.
- **Principal Propagation** binds the validated authentication object to the session's `Principal`, enabling private routing (`/user/queue/*`).
- **Threat Mitigations** require forcing secure protocols (`wss://`), whitelisting origins to prevent CSWSH, rate-limiting requests (Token Bucket), sanitizing inputs against XSS, and setting message size limits.
- **Clustered Security** requires synchronizing authentication context states across all inbound message broker channels.
