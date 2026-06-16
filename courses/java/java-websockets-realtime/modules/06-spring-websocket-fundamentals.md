# Module 6: Spring WebSocket Fundamentals

Spring Framework provides a comprehensive programming model for building WebSocket applications. Instead of dealing directly with native servlet container endpoints (like Tomcat or Jetty specifications), Spring abstracts the underlying connection mechanics into a unified API.

This module details the Spring WebSocket architecture. We will cover the configuration classes, map text and binary protocol handlers, examine the `WebSocketSession` state lifecycle, implement a SockJS fallback layer, and build an advanced Echo Server featuring connection statistics, text commands, and binary loops.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain Spring's WebSocket architecture** and trace how HTTP upgrade requests are routed to specific handler classes.
2. **Configure a WebSocket registry** in Spring Boot, defining allowed origins, registering handshake interceptors, and enabling SockJS fallbacks.
3. **Extend Spring's handler abstractions** (`TextWebSocketHandler`, `BinaryWebSocketHandler`) to build robust frame parsers.
4. **Manage session state attributes** and configure session buffer thresholds using Spring Factory Beans.
5. **Implement an advanced real-time echo server** that processes system commands, executes thread-safe broadcasts, and handles binary arrays.

---

## 1. Spring WebSocket Architecture

Spring's WebSocket support operates as an extension of Spring MVC or WebFlux. 

When a client sends an HTTP Upgrade request:
1. The request is intercepted by Spring's **`DispatcherServlet`** (or Netty server routing in reactive).
2. The servlet identifies the path mapping and delegates the request to the registered **`WebSocketHttpRequestHandler`**.
3. The request is processed by a container-specific handshake handler (e.g. `TomcatRequestUpgradeStrategy` or `JettyRequestUpgradeStrategy`), which executes the HTTP 101 upgrade handshake.
4. Once upgraded, the HTTP connection is hijacked, and the container wraps the native TCP socket in a Spring **`WebSocketSession`** instance.
5. Incoming data and control frames are dispatched directly to the corresponding **`WebSocketHandler`** bean.

```
HTTP Request  ──► [DispatcherServlet] ──► [WebSocketHttpRequestHandler]
                                                    │ (HTTP 101 Handshake Upgrade)
                                                    ▼
Client Connection ◄=============================► [WebSocketSession]
                                                    │ (Dispatches frames)
                                                    ▼
                                          [Custom WebSocketHandler]
```

---

## 2. SockJS Fallback Protocol

In production, WebSocket connections can fail due to:
- Legacy corporate firewalls that inspect traffic and block non-HTTP long-lived TCP streams.
- Old mobile network proxies that drop idle connection sockets.
- Legacy client browsers that lack native `WebSocket` API support.

To resolve this, Spring integrates with the **SockJS protocol**:
- The client-side library `sockjs-client` attempts to open a native WebSocket connection.
- If it fails, the library automatically falls back to HTTP-based emulation transports:
  1. **HTTP Streaming (XHR Streaming)**: The client makes an HTTP POST request, and the server streams events over a single open chunked HTTP response.
  2. **HTTP Long Polling (XHR Polling)**: Standard long polling loop.
- **Spring Configuration**: Enabling SockJS on the server is a single configuration line: `.withSockJS()`. Spring automatically instantiates SockJS transport controllers to handle the fallback streams.

```
                  +──► 1. WebSocket (Native)
Client (SockJS) ──┼──► 2. XHR Streaming (Chunked HTTP)
                  +──► 3. XHR Polling (Long Poll loops)
```

---

## 3. Core Configurations: `WebSocketConfigurer`

To register and configure WebSocket handlers in a Spring Boot application, you must implement the `WebSocketConfigurer` interface and annotate the configuration class with `@EnableWebSocket`.

```java
package com.example.realtime.spring.config;

import com.example.realtime.spring.handler.ChatWebSocketHandler;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.*;
import org.springframework.web.socket.server.support.HttpSessionHandshakeInterceptor;

@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private final ChatWebSocketHandler chatHandler;

    public WebSocketConfig(ChatWebSocketHandler chatHandler) {
        this.chatHandler = chatHandler;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(chatHandler, "/ws/chat")
                // Allow connections only from trusted domains (CORS check during handshake)
                .setAllowedOrigins("https://trustedclient.com", "http://localhost:3000")
                // Copy HttpSession attributes (like logged-in user details) to WebSocketSession
                .addInterceptors(new HttpSessionHandshakeInterceptor())
                // Enable SockJS fallback support
                .withSockJS();
    }
}
```

---

## 4. Core Spring Handlers

Spring provides standard abstract classes that implement `WebSocketHandler`, allowing developers to override only the lifecycle methods they require.

### 1. `TextWebSocketHandler`
Focused on processing text frames (`TextMessage`).
- **`afterConnectionEstablished(WebSocketSession session)`**: Triggered immediately after the handshake completes. Used to register sessions or send initialization payloads.
- **`handleTextMessage(WebSocketSession session, TextMessage message)`**: Triggered when a text frame arrives. The message payload is accessed via `message.getPayload()`.
- **`afterConnectionClosed(WebSocketSession session, CloseStatus status)`**: Triggered when the socket closes. Used to remove session registrations.
- **`handleTransportError(WebSocketSession session, Throwable exception)`**: Triggered when a transport layer socket error occurs.

### 2. `BinaryWebSocketHandler`
Focused on processing binary frames (`BinaryMessage`).
- **`handleBinaryMessage(WebSocketSession session, BinaryMessage message)`**: Triggered when a binary frame arrives. The payload bytes are accessed via `message.getPayload()`. This is useful for streaming image buffers, audio, or serialized protocol formats (like Protocol Buffers).

---

## 5. The `WebSocketSession` Lifecycle

A `WebSocketSession` instance represents an open WebSocket connection. 

### 1. Session Attributes Map
During the handshake, interceptors can copy attributes into the session. These attributes are stored in a thread-safe map accessed via `session.getAttributes()`.
- For example, if a user is authenticated during the handshake, you can store their `UserPrincipal` in the map. When `@OnMessage` processes a payload, you can resolve the user's ID directly from the session attributes without re-verifying token signatures on every frame.

### 2. Sizing Session Buffer Limits
Under heavy load, clients on slow networks may lag, causing the server's output buffer to fill up. To prevent memory exhaustion, Spring allows configuring maximum frame sizes and send timeouts.

```java
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.server.standard.ServletServerContainerFactoryBean;

@Configuration
public class WebSocketContainerConfig {

    @Bean
    public ServletServerContainerFactoryBean createWebSocketContainer() {
        ServletServerContainerFactoryBean container = new ServletServerContainerFactoryBean();
        // Max text message buffer: 512 KiB (Default: 8 KiB)
        container.setMaxTextMessageBufferSize(512 * 1024);
        // Max binary message buffer: 1 MiB (Default: 8 KiB)
        container.setMaxBinaryMessageBufferSize(1024 * 1024);
        // Max send timeout: 10 seconds (Default: 20 seconds)
        container.setSendTimeLimit(10_000L);
        return container;
    }
}
```

---

## 6. Connection Rate Limiting Handshake Interceptor

To protect our WebSocket server from denial-of-service abuse (e.g. clients spinning up thousands of handshakes in loops), we can implement a custom `HandshakeInterceptor` that limits connections per client IP address.

```java
package com.example.realtime.spring.interceptor;

import org.springframework.http.HttpStatus;
import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.server.HandshakeInterceptor;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

@Component
public class RateLimitHandshakeInterceptor implements HandshakeInterceptor {

    // Track active connection counts per remote IP address
    private static final Map<String, AtomicInteger> ipConnectionCounts = new ConcurrentHashMap<>();
    private static final int MAX_CONNECTIONS_PER_IP = 10;

    @Override
    public boolean beforeHandshake(ServerHttpRequest request, ServerHttpResponse response, 
                                   WebSocketHandler wsHandler, Map<String, Object> attributes) throws Exception {
        String ipAddress = request.getRemoteAddress().getAddress().getHostAddress();
        System.out.println("[Rate Limiter] Evaluating connection request from IP: " + ipAddress);

        // Fetch or initialize connection counter
        AtomicInteger counter = ipConnectionCounts.computeIfAbsent(ipAddress, k -> new AtomicInteger(0));
        
        // Check if limit exceeded
        if (counter.get() >= MAX_CONNECTIONS_PER_IP) {
            System.err.println("[Rate Limiter] Connection rejected. IP exceeded maximum limits: " + ipAddress);
            response.setStatusCode(HttpStatus.TOO_MANY_REQUESTS);
            return false; // Rejects handshake upgrade
        }

        // Increment count and register cleanup key in attributes
        counter.incrementAndGet();
        attributes.put("clientIp", ipAddress);
        return true;
    }

    @Override
    public void afterHandshake(ServerHttpRequest request, ServerHttpResponse response, 
                               WebSocketHandler wsHandler, Exception exception) {
        // no-op
    }

    /**
     * Helper method called during socket disconnect to decrement the IP counter
     */
    public static void decrementIpCount(String ipAddress) {
        if (ipAddress != null) {
            AtomicInteger counter = ipConnectionCounts.get(ipAddress);
            if (counter != null) {
                int count = counter.decrementAndGet();
                if (count <= 0) {
                    ipConnectionCounts.remove(ipAddress);
                }
            }
        }
    }
}
```

---

## 7. Hands-On Lab: Creating a Spring Boot WebSocket Server

In this lab, you will set up a basic Spring Boot WebSocket endpoint that logs lifecycle events to the console when clients connect.

### Step 1: Create the Chat Handler
Create a class extending `TextWebSocketHandler`:

```java
package com.example.realtime.spring.handler;

import org.springframework.stereotype.Component;
import org.springframework.web.socket.*;
import org.springframework.web.socket.handler.TextWebSocketHandler;

@Component
public class ChatWebSocketHandler extends TextWebSocketHandler {

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        System.out.println("[Spring WS] Session established: " + session.getId());
        session.sendMessage(new TextMessage("Connected to Spring WebSocket Server"));
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        System.out.println("[Spring WS] Message received from " + session.getId() + ": " + message.getPayload());
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) throws Exception {
        System.out.println("[Spring WS] Connection closed: " + session.getId() + " | Status: " + status);
    }
}
```

### Step 2: Test the Endpoint
1. Map this handler in your `WebSocketConfig` configuration class to the path `/ws/chat`.
2. Boot your Spring application.
3. Open a browser console on `http://localhost:8080` and run:
   ```javascript
   const ws = new WebSocket("ws://localhost:8080/ws/chat");
   ws.onmessage = (event) => console.log("Received:", event.data);
   ws.onopen = () => ws.send("Hello Server!");
   ```
4. Verify that the server logs the connection, prints `"Hello Server!"`, and the client receives the connection greeting.

---

## 8. Mini Project: Advanced Echo Server

We will build a complete, runnable Spring Boot application implementing an **Advanced Echo Server**. 

The server provides:
- **Automatic Session Tracking**: Keeps track of all active connections.
- **System Stats Tracking**: Records server uptime and message statistics.
- **System Command Dispatching**: If a client sends a message starting with `/`, the server processes it as a command:
  - `/stats` - Returns active connection counts, total messages processed, and server uptime.
  - `/broadcast <message>` - Broadcasts a message to all connected sessions (excluding the sender), protecting against concurrent write failures.
  - `/disconnect` - Triggers a clean WebSocket close handshake.
- **Binary Frame Loopback**: Echoes binary payloads back to the client, printing the byte size to the logs.

```
                              +---------------------------------------+
                              |         SPRING BOOT ECHO SERVER       |
                              |                                       |
                              |  [Active Sessions Registry]           |
                              |  [Message Counter / Start Time]       |
                              |         ▲                             |
                              |  +──────┴────────+                    |
                              |  | EchoHandler   |                    |
                              |  +──────┬────────+                    |
                              +─────────┼─────────────────────────────+
                                        │
             Client Commands            │      Echo / Broadcast
             (/stats, /broadcast)       ▼
                                  +──────────+
                                  | Client   |
                                  +──────────+
```

### Complete Implementation:

```java
package com.example.realtime.spring.echo;

import com.example.realtime.spring.interceptor.RateLimitHandshakeInterceptor;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.*;
import org.springframework.web.socket.config.annotation.*;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.time.Duration;
import java.time.Instant;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

@SpringBootApplication
public class EchoServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(EchoServerApplication.class, args);
    }
}

// --- Configuration ---
@Configuration
@EnableWebSocket
class WebSocketConfig implements WebSocketConfigurer {

    private final EchoWebSocketHandler echoHandler;
    private final RateLimitHandshakeInterceptor rateLimiter;

    public WebSocketConfig(EchoWebSocketHandler echoHandler, RateLimitHandshakeInterceptor rateLimiter) {
        this.echoHandler = echoHandler;
        this.rateLimiter = rateLimiter;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        // Map handler to /ws/echo, enabling rate limiting and allowing all origins
        registry.addHandler(echoHandler, "/ws/echo")
                .addInterceptors(rateLimiter)
                .setAllowedOrigins("*");
    }
}

// --- Handler Logic ---
@Component
class EchoWebSocketHandler extends TextWebSocketHandler {

    // Registry of active client sessions
    private final Set<WebSocketSession> activeSessions = ConcurrentHashMap.newKeySet();
    
    // Performance and load metrics counters
    private final AtomicLong totalMessagesProcessed = new AtomicLong(0);
    private final Instant serverStartTime = Instant.now();

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        activeSessions.add(session);
        System.out.println("[Echo Server] Session connected: " + session.getId());
        session.sendMessage(new TextMessage("ECHO_SERVER: Connection established. Total active: " + activeSessions.size()));
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        totalMessagesProcessed.incrementAndGet();
        String payload = message.getPayload().trim();

        // 1. Process System Commands
        if (payload.startsWith("/")) {
            handleCommand(session, payload);
            return;
        }

        // 2. Default Echo Loopback
        String echoResponse = "ECHO: " + payload;
        session.sendMessage(new TextMessage(echoResponse));
    }

    @Override
    protected void handleBinaryMessage(WebSocketSession session, BinaryMessage message) throws IOException {
        totalMessagesProcessed.incrementAndGet();
        ByteBuffer byteBuffer = message.getPayload();
        int byteSize = byteBuffer.remaining();
        
        System.out.println("[Echo Server] Binary frame received from " + session.getId() + " | Size: " + byteSize + " bytes");
        
        // Echo binary data back
        session.sendMessage(new BinaryMessage(byteBuffer));
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) throws Exception {
        activeSessions.remove(session);
        System.out.println("[Echo Server] Session closed: " + session.getId() + " | Status: " + status);
        
        // Clean up rate limiting count
        String clientIp = (String) session.getAttributes().get("clientIp");
        RateLimitHandshakeInterceptor.decrementIpCount(clientIp);
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) throws Exception {
        System.err.println("[Echo Server] Transport error on session: " + session.getId() + " | Error: " + exception.getMessage());
        activeSessions.remove(session);
        if (session.isOpen()) {
            session.close(CloseStatus.SERVER_ERROR);
        }
    }

    private void handleCommand(WebSocketSession session, String commandLine) throws IOException {
        String[] parts = commandLine.split(" ", 2);
        String command = parts[0].toLowerCase();

        switch (command) {
            case "/stats":
                long uptimeSeconds = Duration.between(serverStartTime, Instant.now()).toSeconds();
                String statsReport = "{\"activeConnections\":" + activeSessions.size()
                        + ",\"totalMessages\":" + totalMessagesProcessed.get()
                        + ",\"serverUptimeSeconds\":" + uptimeSeconds + "}";
                session.sendMessage(new TextMessage("STATS: " + statsReport));
                break;

            case "/broadcast":
                if (parts.length < 2) {
                    session.sendMessage(new TextMessage("ERROR: Missing broadcast message text. Syntax: /broadcast <message>"));
                    return;
                }
                String broadcastText = parts[1];
                broadcastToAll(session, broadcastText);
                break;

            case "/disconnect":
                session.sendMessage(new TextMessage("SYSTEM: Disconnecting..."));
                session.close(CloseStatus.NORMAL);
                break;

            default:
                session.sendMessage(new TextMessage("ERROR: Unknown command. Supported commands: /stats, /broadcast, /disconnect"));
        }
    }

    private void broadcastToAll(WebSocketSession sender, String text) {
        String msg = "[BROADCAST from " + sender.getId() + "]: " + text;
        TextMessage textMessage = new TextMessage(msg);

        for (WebSocketSession session : activeSessions) {
            // Skip sending the message back to the sender
            if (session.getId().equals(sender.getId())) {
                continue;
            }

            if (!session.isOpen()) {
                continue;
            }

            // Lock session writes to prevent concurrent execution conflicts
            synchronized (session) {
                try {
                    session.sendMessage(textMessage);
                } catch (IOException e) {
                    System.err.println("Broadcast write failed for session: " + session.getId() + ". Closing.");
                    try {
                        session.close(CloseStatus.SESSION_NOT_RELIABLE);
                    } catch (IOException ioException) {
                        // ignore
                    }
                }
            }
        }
    }
}
```

### Line-by-Line Logic Walkthrough (EchoServer):
1. **Dynamic Set Registry**:
   - `private final Set<WebSocketSession> activeSessions = ConcurrentHashMap.newKeySet()` initializes a thread-safe set. When users connect, `afterConnectionEstablished` adds the session, and when they disconnect, `afterConnectionClosed` removes it, preventing memory leaks.
2. **System Commands Matcher**:
   - `handleTextMessage` intercepts payloads starting with `/`. The parsed command is routed to `handleCommand()`.
   - `/stats` calculates elapsed uptime using `Duration.between()` and converts connections and metrics metrics to a JSON report.
3. **Synchronized Broadcaster**:
   - `/broadcast` extracts the message text and invokes `broadcastToAll()`. The method loops through `activeSessions` and executes `session.sendMessage()`.
   - **Critical Lock**: `synchronized(session)` prevents thread collisions. If client B sends `/broadcast` while client C is sending stats, the locks prevent concurrent writes on the same TCP socket, avoiding container state errors.
4. **Binary Loopback**:
   - `handleBinaryMessage` extracts the payload using `message.getPayload()`, reads the bytes length, logs it, and echoes it back using `session.sendMessage(new BinaryMessage(byteBuffer))`.

---

## 9. Common Mistakes & Debugging Scenarios

### Scenario A: Spring Boot Security Blocking WebSockets
* **The Problem**: A developer registers a WebSocket handler on `/ws/chat`. Standard security is enabled in Spring Boot. The WebSocket handshake fails with `HTTP 401 Unauthorized` or `HTTP 403 Forbidden` errors.
* **Why it happens**: Spring Security intercepts all HTTP routes. By default, it blocks access to unregistered paths and requires CSRF tokens for all stateful request methods. Because the WebSocket handshake starts as an HTTP GET request, Spring Security intercepts it and rejects it if it lacks authorization cookies or headers.
* **The Fix**: Update your security configuration class to permit WebSocket routes:
  ```java
  @Bean
  public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
      http
          .authorizeHttpRequests(auth -> auth
              .requestMatchers("/ws/**").permitAll() // Permit handshake upgrades
              .anyRequest().authenticated()
          )
          .csrf(csrf -> csrf.ignoringRequestMatchers("/ws/**")); // Ignore CSRF on upgrade
      return http.build();
  }
  ```

### Scenario B: Blocking the Client Output Buffer
* **The Problem**: A real-time dashboard freezes, and the server log prints `java.io.IOException: Broken pipe` or `java.lang.IllegalStateException: The remote endpoint was in state [TEXT_WRITING]` even when synchronization locks are configured.
* **Why it happens**: If the server pushes high-frequency messages (e.g. 50 messages per second) to a client on a slow or limited connection (e.g. mobile GPRS), the server's TCP socket buffer fills up. Spring Boot's internal buffer queues messages. If the queue size exceeds default limits (8 KiB) or the transmission timeout (20 seconds) is hit, Spring drops the connection to protect server memory.
* **The Fix**: Tune the maximum message buffer size and limit rates at the application layer:
  - Settle buffer allocations via `ServletServerContainerFactoryBean` (as shown in Section 5).
  - Implement application-level throttling to combine metrics updates into aggregate messages instead of pushing hundreds of individual frames.

---

## 10. Technical Interview Questions

### Question 1: Text vs. Binary Handlers
*What is the difference between `TextWebSocketHandler` and `BinaryWebSocketHandler` in Spring? Can a single endpoint support both types of frames?*

**Answer**:
`TextWebSocketHandler` and `BinaryWebSocketHandler` are subclasses of `AbstractWebSocketHandler` designed to simplify message handling:
- `TextWebSocketHandler` processes text frames (`TextMessage`), wrapping UTF-8 encoded string data. It rejects binary frames.
- `BinaryWebSocketHandler` processes binary frames (`BinaryMessage`), wrapping raw byte arrays or buffers. It rejects text frames.
To support both text and binary frames on a single endpoint, you must implement the parent interface `WebSocketHandler` directly (or extend `AbstractWebSocketHandler`) and override `handleMessage(WebSocketSession session, WebSocketMessage<?> message)`. You can then perform an `instanceof` check on the incoming message object type:
```java
@Override
public void handleMessage(WebSocketSession session, WebSocketMessage<?> message) throws Exception {
    if (message instanceof TextMessage) {
        handleTextMessage(session, (TextMessage) message);
    } else if (message instanceof BinaryMessage) {
        handleBinaryMessage(session, (BinaryMessage) message);
    }
}
```

---

### Question 2: WebSocketSession vs. native Servlet Session
*What is the relationship between the Spring `WebSocketSession` and the standard HTTP servlet `HttpSession`? How can you access HTTP session attributes inside a WebSocket handler?*

**Answer**:
A `WebSocketSession` is a long-lived connection abstraction wrapping a TCP socket, whereas an `HttpSession` is a short-lived, request-scoped cookie session. They are independent.

To access HTTP session attributes inside a WebSocket handler, you must register a **`HttpSessionHandshakeInterceptor`** in your configuration class. During the handshake phase (while the HTTP connection is still active), this interceptor automatically copies all attributes from the user's `HttpSession` into the WebSocket upgrade request map. These attributes are then exposed inside the WebSocket session, accessed via `session.getAttributes()`.

---

## Summary
- **Spring WebSocket Architecture** integrates with the `DispatcherServlet` to route HTTP upgrade requests to specialized handler beans.
- **`WebSocketConfigurer`** maps URLs to handlers, registers interceptors (`HttpSessionHandshakeInterceptor`), and enforces CORS rules.
- **SockJS fallbacks** emulate WebSocket channels using HTTP streaming or long polling when raw TCP links are blocked by intermediate proxies.
- **Spring Handlers** (`TextWebSocketHandler` and `BinaryWebSocketHandler`) expose clean lifecycle callbacks.
- **`WebSocketSession`** manages socket states, stores attributes, and can be tuned for frame sizes and send timeouts.
- **The Echo Server** utilizes thread-safe session sets, processes custom system commands, and executes synchronized broadcasts to avoid state errors in production.
- **Spring Security Integration** requires explicitly permitting WebSocket upgrade routes (`/ws/**`) and ignoring CSRF restrictions.
