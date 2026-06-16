# Module 7: STOMP Protocol

WebSockets are transport sockets, not messaging systems. To build complex enterprise applications—where users need to subscribe to specific topics, send private notifications, or route data to dynamic rooms—you must run a subprotocol on top of the WebSocket connection. 

This module covers the **Simple Text Oriented Messaging Protocol (STOMP)**. We will analyze the anatomy of STOMP frames, explore Spring's internal subscription registry architecture, design message-routing destinations, compare in-memory simple brokers against clustered external relays, and build a secure, multi-room chat application in Spring Boot.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain why STOMP is required** to build enterprise-grade routing architectures over raw WebSockets.
2. **Break down the anatomy of a STOMP frame**, identifying commands, headers, and body segments.
3. **Map destination prefixes** to handle broadcasts (`/topic`), point-to-point queues (`/queue`), and application mappings (`/app`).
4. **Detail the lookup mechanics of Spring's `SubscriptionRegistry`** and explain subscription search complexities.
5. **Contrast the architectures** of Spring's in-memory Simple Broker and external STOMP Broker Relays (like RabbitMQ) regarding horizontal scaling.
6. **Implement a complete, secure STOMP chat server** featuring dynamic rooms and JWT channel interceptors.

---

## 1. Why STOMP Exists

Using raw WebSockets is like communicating over a raw telephone line: you have a connection, but no standard format for the data. If you write a chat application, you must define:
- How does a user join a room? (e.g. sending `{"type":"join","room":"sports"}`)
- How does a user send a private message? (e.g. sending `{"type":"private","to":"user1","body":"hello"}`)
- How does the server confirm receipt?

Every developer ends up writing a custom, proprietary JSON message parser. This increases complexity and prevents integration with standard tools.

**STOMP** solves this by defining an **application-level messaging protocol**:
- Decouples client and server using a standardized message format.
- Introduces built-in routing commands (`SEND`, `SUBSCRIBE`) and headers (`destination`).
- Integrates natively with enterprise message brokers, allowing you to route WebSocket messages to other parts of your microservice architecture (e.g. pushing a chat message directly into a RabbitMQ queue processed by background AI workers).

---

## 2. The STOMP Frame Specification (Anatomy of a Frame)

STOMP is a text-based protocol. A STOMP frame consists of a command string, a set of key-value headers, a blank line, a body payload, and a terminating null byte (`\u0000` or `^@`).

```text
COMMAND
header1:value1
header2:value2

[Optional Body Payload]
^@
```

### Core Client Frames:

#### 1. CONNECT Handshake
The client initiates the STOMP session over the upgraded WebSocket link:
```http
CONNECT
accept-version:1.2
host:server.example.com
login:alice
passcode:secret123

^@
```

#### 2. SUBSCRIBE Frame
To receive messages from a specific destination, the client subscribes. The `id` header is unique to the client session, allowing the client to map incoming messages to specific callbacks:
```http
SUBSCRIBE
id:sub-id-0
destination:/topic/sports-room

^@
```

#### 3. SEND Frame
To publish a message to a destination:
```http
SEND
destination:/topic/sports-room
content-type:application/json
content-length:37

{"author":"Alice","text":"Go team!"}^@
```

#### 4. ACK Frame
If a client subscribes using client-side acknowledgment settings, it must explicitly acknowledge receipt of messages:
```http
ACK
id:msg-1024

^@
```

#### 5. DISCONNECT Frame
```http
DISCONNECT
receipt:rc-999

^@
```

### Core Server Frames:

#### 1. CONNECTED Response
Confirming a successful STOMP session:
```http
CONNECTED
version:1.2
session:session-id-1042
heart-beat:10000,10000

^@
```

#### 2. MESSAGE Frame
Delivering a message to a subscriber:
```http
MESSAGE
subscription:sub-id-0
message-id:msg-1024
destination:/topic/sports-room
content-type:application/json

{"author":"Alice","text":"Go team!"}^@
```

#### 3. ERROR Frame
Sent by the server when a protocol or authorization error occurs. The server drops the link immediately after:
```http
ERROR
message:Invalid credentials
content-type:text/plain

Authentication token signature has expired.^@
```

---

## 3. Destinations and Topic Topologies

STOMP messages are routed using **destinations** (destination URI strings). While the STOMP specification does not dictate a strict naming format, Spring Boot establishes standard routing prefixes:

```
                  +─────────────────────────────────────+
                  |           SPRING BOOT ROUTER        |
                  |                                     |
                  |  /topic/* ──► [In-Memory Broker] ───┼─► Subscribers
                  |                                     |
                  |  /queue/* ──► [In-Memory Broker] ───┼─► Point-to-Point
                  |                                     |
                  |  /app/*   ──► [ChatController] ─────┼─► Business Logic
                  +─────────────────────────────────────+
```

### 1. Broadcast Topics (`/topic`)
- **Pattern**: `/topic/sports-news`, `/topic/room-1`
- **Routing**: Messages are routed using **Publish-Subscribe (Pub/Sub)** semantics. Every client currently subscribed to `/topic/room-1` receives a copy of any message sent to that destination.

### 2. Point-to-Point Queues (`/queue`)
- **Pattern**: `/queue/notifications`, `/user/queue/alerts`
- **Routing**: Messages are routed using **Point-to-Point** semantics. A message is delivered to **only one** of the subscribed clients, which is ideal for workload distribution queues or user-specific private alerts.

### 3. Application Controllers Prefix (`/app`)
- **Pattern**: `/app/chat.sendMessage`, `/app/join-game`
- **Routing**: These destinations bypass the message broker. The message is routed directly to your Spring Boot `@MessageMapping` controller methods, allowing you to run business logic (e.g. database persistence, validation) before publishing the message.

---

## 4. Spring Subscription Management Internals

When a client subscribes to a destination (e.g. `SUBSCRIBE` to `/topic/room1`), Spring must store this mapping to route future messages. This is managed by the **`SubscriptionRegistry`** (specifically `SimpleAnnotationSubscriptionRegistry`).

### How Spring Tracks Subscriptions:
Spring stores subscriptions in a nested concurrent map structure:
```java
// Conceptual mapping inside SimpleAnnotationSubscriptionRegistry
Map<String, Map<String, Set<Subscription>>> registry = new ConcurrentHashMap<>();
// Key 1: Destination string (e.g. "/topic/room1")
// Key 2: Session ID (e.g. "session-abc")
// Value: Set of Subscription mappings (subscription ID, user details)
```

### The Search Process:
1. When a message is sent to `/topic/room1`, Spring's broker handler queries the registry.
2. It fetches all active sessions subscribed to that exact destination path.
3. **Path Matcher Routing**: If the destination uses path variables (e.g. `/topic/room.*`), Spring applies an Ant-style path matcher (`AntPathMatcher`). This increases search complexity:
   - For exact path matches (e.g., `/topic/room1`), lookup complexity is **$O(1)$** (direct hash map lookup).
   - For pattern path matches (e.g., `/topic/room*`), Spring must iterate through all registered destinations to apply regex evaluations, increasing CPU overhead under high concurrency. Using exact destination paths in high-throughput applications is a recommended best practice.

---

## 5. Message Brokers Architecture

When configuring Spring Boot STOMP, you must choose between an in-memory broker or an external broker relay:

### 1. Spring Simple In-Memory Broker
- **How it works**: Spring allocates concurrent maps inside the JVM heap to track client subscriptions and message queues.
- **The Bottleneck (Horizontal Scale Limit)**: 
  - If you deploy your application on a single server instance, it works fine.
  - If you scale horizontally to **three server instances** behind a load balancer, the in-memory maps are not shared. If User A connects to Server 1 and subscribes to `/topic/chat`, and User B connects to Server 2 and sends a message to `/topic/chat`, User A **will never receive the message** because Server 2's in-memory broker has no way to forward the frame to Server 1.

### 2. External STOMP Broker Relay (RabbitMQ / ActiveMQ)
- **How it works**: Spring acts as a lightweight proxy.
  - When Client A subscribes to `/topic/chat` on Server 1, Spring opens a TCP connection to an external message broker (like RabbitMQ) and registers Server 1 as a subscriber.
  - When Client B sends a message to `/topic/chat` on Server 2, Server 2 forwards the STOMP frame over TCP to RabbitMQ.
  - RabbitMQ distributes the message to all registered servers (Server 1 and Server 2), which then push it to their locally connected clients.
- **The Clustered Solution**: This enables horizontal scalability, allowing you to add as many server nodes as your traffic demands.

---

## 6. Detailed Trade-Offs: Raw WebSockets vs. STOMP

The table below highlights the trade-offs between raw protocols and STOMP:

| Feature | Raw WebSockets | STOMP Subprotocol |
| :--- | :--- | :--- |
| **Transport Overhead** | Low (2–10 byte headers) | Moderate (HTTP-like text headers) |
| **Message Routing** | Custom parser (You write JSON routes)| Standard STOMP destinations |
| **Clustering Scale** | Requires custom Redis Pub/Sub integration | Native External Broker Relay |
| **Authorization** | Handshake phase only | Handshake + channel message-level auth |
| **Client Ecosystem** | Native `WebSocket` object in browser | Requires libraries (`stompjs`, `sockjs`) |

---

## 7. Hands-On Lab: Building a Multi-Room Chat App using STOMP

In this lab, you will build a complete, runnable Spring Boot chat application utilizing the STOMP subprotocol. 

### Objective:
- Support dynamic multi-room routing using `@DestinationVariable`.
- Secure connection requests by validating JWT tokens inside a STOMP `ChannelInterceptor` during the `CONNECT` handshake.

### Code Implementation:

#### 1. Configuration Class (`WebSocketMessageBrokerConfig.java`)

```java
package com.example.realtime.stomp.config;

import com.example.realtime.stomp.interceptor.SecurityChannelInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.ChannelRegistration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.web.socket.config.annotation.*;

@Configuration
@EnableWebSocketMessageBroker
public class WebSocketMessageBrokerConfig implements WebSocketMessageBrokerConfigurer {

    private final SecurityChannelInterceptor securityChannelInterceptor;

    public WebSocketMessageBrokerConfig(SecurityChannelInterceptor securityChannelInterceptor) {
        this.securityChannelInterceptor = securityChannelInterceptor;
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        // Register the STOMP endpoint `/ws-chat`, enabling SockJS fallback support
        registry.addEndpoint("/ws-chat")
                .setAllowedOrigins("*");
    }

    @Override
    public void configureMessageBroker(MessageBrokerRegistry registry) {
        // Enable in-memory broker for broadcast topics (/topic)
        registry.enableSimpleBroker("/topic");
        
        // Define application prefix for controller routes
        registry.setApplicationDestinationPrefixes("/app");
    }

    @Override
    public void configureClientInboundChannel(ChannelRegistration registration) {
        // Register the security interceptor on the inbound channel
        registration.interceptors(securityChannelInterceptor);
    }
}
```

#### 2. Domain Model (`ChatMessage.java`)

```java
package com.example.realtime.stomp.model;

public class ChatMessage {

    public enum MessageType { CHAT, JOIN, LEAVE }

    private String sender;
    private String content;
    private String room;
    private MessageType type;

    // --- Constructor ---
    public ChatMessage() {}

    public ChatMessage(String sender, String content, String room, MessageType type) {
        this.sender = sender;
        this.content = content;
        this.room = room;
        this.type = type;
    }

    // --- Getters and Setters ---
    public String getSender() { return sender; }
    public void setSender(String sender) { this.sender = sender; }

    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }

    public String getRoom() { return room; }
    public void setRoom(String room) { this.room = room; }

    public MessageType getType() { return type; }
    public void setType(MessageType type) { this.type = type; }
}
```

#### 3. Controller Routing (`ChatController.java`)

```java
package com.example.realtime.stomp.controller;

import com.example.realtime.stomp.model.ChatMessage;
import org.springframework.messaging.handler.annotation.DestinationVariable;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.messaging.simp.SimpMessageHeaderAccessor;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Controller;

@Controller
public class ChatController {

    private final SimpMessagingTemplate messagingTemplate;

    public ChatController(SimpMessagingTemplate messagingTemplate) {
        this.messagingTemplate = messagingTemplate;
    }

    /**
     * Handles message broadcasts to dynamic rooms.
     * Maps `/app/chat.send/{room}` to `/topic/{room}`.
     */
    @MessageMapping("/chat.send/{room}")
    public void sendMessage(@DestinationVariable String room, @Payload ChatMessage chatMessage) {
        System.out.println("[STOMP Dispatcher] Broadcast to Room: " + room + " | Msg: " + chatMessage.getContent());
        // Distribute to the dynamic destination
        messagingTemplate.convertAndSend("/topic/" + room, chatMessage);
    }

    /**
     * Handles room joins. Registers username in the session attributes.
     */
    @MessageMapping("/chat.join/{room}")
    public void joinRoom(@DestinationVariable String room, @Payload ChatMessage chatMessage, 
                         SimpMessageHeaderAccessor headerAccessor) {
        System.out.println("[STOMP Dispatcher] User joined Room: " + room + " | User: " + chatMessage.getSender());
        
        // Store username in session attributes map for tracking
        if (headerAccessor.getSessionAttributes() != null) {
            headerAccessor.getSessionAttributes().put("username", chatMessage.getSender());
            headerAccessor.getSessionAttributes().put("room", room);
        }

        messagingTemplate.convertAndSend("/topic/" + room, chatMessage);
    }
}
```

#### 4. JWT Validation Interceptor (`SecurityChannelInterceptor.java`)

```java
package com.example.realtime.stomp.interceptor;

import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.stereotype.Component;

@Component
public class SecurityChannelInterceptor implements ChannelInterceptor {

    @Override
    public Message<?> preSend(Message<?> message, MessageChannel channel) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(message);

        // 1. Intercept only connection establishment command (CONNECT)
        if (StompCommand.CONNECT.equals(accessor.getCommand())) {
            // Extract the native Authorization header sent in the STOMP CONNECT frame
            String authToken = accessor.getFirstNativeHeader("Authorization");
            System.out.println("[STOMP Security] CONNECT request intercepted. Token: " + authToken);

            // 2. Validate token (Simulating a JWT check)
            if (authToken == null || !authToken.startsWith("Bearer secret_jwt_token")) {
                System.err.println("[STOMP Security] Authentication failed. Dropping connection.");
                // Throw an exception to drop the connection during the handshake
                throw new IllegalArgumentException("Unauthorized: Invalid STOMP credentials.");
            }
            
            System.out.println("[STOMP Security] Authentication successful.");
        }

        return message;
    }
}
```

---

## 8. Common Mistakes & Debugging Scenarios

### Scenario A: HTTP Handshake Permitted, but STOMP Connection Dropped
* **The Problem**: A client initiates a connection. The browser Network tab shows the HTTP upgrade handshake completes successfully (status code `101 Switching Protocols`), but the WebSocket is closed immediately after. The client console logs `Error: Lost connection to ws://...`.
* **Why it happens**: This occurs when the HTTP handshake is allowed, but the STOMP `CONNECT` frame is rejected by an inbound channel interceptor (like our `SecurityChannelInterceptor`). The TCP connection is established, but as soon as the client transmits the `CONNECT` STOMP frame, the interceptor throws an exception, forcing the server to drop the link.
* **The Fix**: Check your server logs. Look for authorization exceptions in your `ChannelInterceptor` class and verify that the client is attaching the correct `Authorization` header to the STOMP connection frame.

### Scenario B: Messages Sent to Mapped Routes Are Ignored
* **The Problem**: A developer maps a route `@MessageMapping("/chat")`. The client sends a STOMP message to `/chat` but the controller method is never executed.
* **Why it happens**: Spring configurations require prefixing client-bound controller messages with the designated application prefix configured in `MessageBrokerRegistry`. If `setApplicationDestinationPrefixes("/app")` is set, the client **must** send messages to `/app/chat` for the router to match the controller method.
* **The Fix**: Ensure your client libraries target destinations containing the correct prefixes:
  ```javascript
  stompClient.publish({
      destination: '/app/chat.send/roomA', // Includes the '/app' prefix
      body: JSON.stringify(payload)
  });
  ```

---

## 9. Technical Interview Questions

### Question 1: Simple Broker vs. Broker Relay
*Why is Spring's simple message broker unsuitable for clustered deployment environments? How does an external STOMP broker relay solve this issue?*

**Answer**:
- **`SimpleBroker`** routes messages in-memory. It maintains a subscription map on the JVM heap. When a message is sent to a topic, Spring's broker handler loops through the local map, serializes the message to a STOMP frame, and writes it directly to each client's socket using the `clientOutboundChannel` thread pool.
- **`StompBrokerRelay`** does not manage subscriptions or distribute messages itself. It delegates this logic to an external broker (like RabbitMQ). When a message is sent, Spring forwards a single STOMP `SEND` frame to RabbitMQ over a TCP socket. RabbitMQ processes the routing rules, determines which application server instances have active subscribers, and routes the message back to those servers over their respective TCP streams. The servers then push the message to their local clients.

---

### Question 2: ChannelInterceptor vs. HandshakeInterceptor
*What is the difference between a `HandshakeInterceptor` and a `ChannelInterceptor` in a Spring STOMP architecture? When would you use each for security validation?*

**Answer**:
- **`HandshakeInterceptor`** operates at the **HTTP protocol level** before the WebSocket connection is established. It has access to the HTTP request and response objects. Use this interceptor to inspect cookies, HTTP headers, or validate session states before upgrading the protocol.
- **`ChannelInterceptor`** operates at the **message channel level** after the WebSocket is open. It intercepts individual STOMP frames (`CONNECT`, `SEND`, `SUBSCRIBE`) as they pass through the inbound channel. Use this interceptor to validate message-level authentication headers (like JWT tokens passed in STOMP headers) and enforce subscription-level authorization rules.

---

## Summary
- **STOMP** is an application subprotocol that introduces standardized messaging frames (`CONNECT`, `SUBSCRIBE`, `SEND`, `ACK`, `DISCONNECT`) on top of WebSockets.
- **Destination Prefixes** map routing rules: `/topic` for broadcasts, `/queue` for point-to-point queues, and `/app` for application controllers.
- **Spring's Subscription Registry** maps active client subscriptions inside nested maps, where dynamic path matches require regex checks that increase search CPU overhead.
- **Horizontal Scaling** requires swapping the in-memory Simple Broker for an external **STOMP Broker Relay** (like RabbitMQ) to distribute messages across clustered server nodes.
- **Handshake Interceptors** validate connections at the HTTP level during upgrade, while **Channel Interceptors** validate security credentials at the message level during STOMP frame processing.
