# Module 10: Real-Time Messaging Patterns

Building high-performance real-time applications requires structuring how messages flow between clients and servers. Unlike REST, where client-to-server calls always follow a direct request-response pattern, WebSockets enable multiple messaging archetypes.

This module covers advanced real-time messaging patterns. We will explore point-to-point and broadcast topologies, design request-response emulation over asynchronous socket channels, implement correlation IDs and envelope wrappers, contrast commands and events, and build a private user-to-user messaging system in Spring Boot.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Differentiate between point-to-point and broadcast messaging** and configure their routing paths.
2. **Implement request-response emulation** over asynchronous channels using correlation IDs.
3. **Design metadata envelopes** to decouple application payloads from routing routing frameworks.
4. **Contrast command and event messages** and map them to their corresponding handlers.
5. **Build a private user-to-user messaging system** using Spring's user destination mappings.

---

## 1. Messaging Archetypes in Real-Time Systems

Selecting the right messaging archetype dictates how network resources and server queues are allocated.

```
Point-to-Point (Queue)
Sender ──► [ Queue ] ──► Recipient (Delivered once to one client)

Broadcast (Topic)
Sender ──► [ Topic ] ──┬──► Subscriber A (Delivered to all)
                       ├──► Subscriber B
                       └──► Subscriber C
```

### 1. Point-to-Point Messaging (Queues)
- **Mechanics**: Messages are delivered to a specific, unique destination representing a single client.
- **Routing**: Follows a 1-to-1 pattern. Even if multiple instances of a client are active, the broker routes the message to only one socket connection.
- **Use Cases**: Dynamic task assignments, order status alerts, or private peer-to-peer conversations.

### 2. Broadcast Messaging (Topics)
- **Mechanics**: Follows the Publish-Subscribe (Pub/Sub) pattern. Senders publish a message to a shared topic.
- **Routing**: Follows a 1-to-Many pattern. The broker replicates the message frame and pushes a copy to every active subscriber.
- **Use Cases**: System news tickers, collaborative canvas drawing coordination, or public lobby chat channels.

---

## 2. Advanced Interaction Patterns

Because WebSockets are asynchronous and full-duplex, traditional HTTP request-response patterns do not exist natively. Senders throw frames onto the wire and do not block waiting for responses. To execute REST-like queries over WebSockets, you must implement application-level coordination.

### 1. Request-Response Emulation
To run a query (e.g. retrieving database profile details) over a WebSocket connection:
1. The client generates a unique **Correlation ID** (typically a UUID).
2. The client packages the request payload, attaches the Correlation ID, and registers a callback listener in its memory mapped by the ID.
3. The client sends the message to the server (e.g. to `/app/profile.get`).
4. The server receives the message, processes the request, and returns a response frame containing the same Correlation ID to the client's private user queue.
5. The client reads the response, matches the Correlation ID to its memory callback map, executes the callback, and clears the registry.

```
Client                                      Server
  │ ─── Request (Payload, CorrelationID=XYZ) ──► │ (Processes request...)
  │ ◄─── Response (Result, CorrelationID=XYZ) ─── │ (Matches ID on client)
```

### 2. The Envelope Pattern
To write clean, decoupled messaging handlers, avoid reading raw application payloads directly in routing channels. Use the **Envelope Pattern**:
- Wrap all messages in a standard outer structure (the Envelope).
- The Envelope contains routing metadata headers, leaving the core application payload untouched.

#### STOMP Metadata Envelope Example:
```json
{
  "header": {
    "messageId": "msg-994",
    "correlationId": "corr-102",
    "timestamp": 1781628104000,
    "sender": "user-22",
    "type": "USER_PROFILE_REQUEST"
  },
  "payload": {
    "userId": "target-12",
    "fields": ["email", "roles"]
  }
}
```
Using envelopes allows your routing filters and channel interceptors to inspect headers, execute rate limits, check permissions, and track trace IDs without parsing the custom application payload schema.

---

## 3. Command vs. Event Messages

In real-time systems, classify incoming payloads as either **Commands** or **Events** to prevent routing spaghetti:

### 1. Command Messages
- **Definition**: An instruction requesting the server or another node to perform an action.
- **Characteristics**:
  - Expresses intent.
  - Named in the imperative (e.g. `/app/room.kickUser`, `/app/game.start`).
  - Expects a specific outcome: either success (often returning an event) or failure (returning an error frame).
  - Routes strictly to application controller methods.

### 2. Event Messages
- **Definition**: A statement of fact announcing that an action has occurred or the system state has changed.
- **Characteristics**:
  - Named in the past tense (e.g. `/topic/userKicked`, `/topic/gameStarted`).
  - Read-only data feed. Senders do not expect responses.
  - Broadcasts to broad subscriber pools.

```
Command vs Event Flow
Client ──► Command: /app/kickUser ──► [Controller] ──► Event: /topic/userKicked ──► Subscribers
```

---

## 4. Hands-On Lab: Private User-to-User Messaging

In this lab, you will implement a complete, compilable Spring Boot private messaging service.

### Objective:
Build a secure routing path where Client A can target Client B specifically using Spring's dynamic user destination relay (`SimpMessagingTemplate`).

### Code Implementation:

#### 1. Configuration Class (`WebSocketConfig.java`)
```java
package com.example.realtime.patterns.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.web.socket.config.annotation.*;

@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        // Map the STOMP chat endpoint
        registry.addEndpoint("/ws-patterns")
                .setAllowedOrigins("*");
    }

    @Override
    public void configureMessageBroker(MessageBrokerRegistry registry) {
        // Enable SimpleBroker for broadcasts (/topic) and user-specific queues (/queue)
        registry.enableSimpleBroker("/topic", "/queue");
        
        // Dynamic prefix for private messaging queues targeting specific users
        registry.setUserDestinationPrefix("/user");

        registry.setApplicationDestinationPrefixes("/app");
    }
}
```

#### 2. Message Domain Model (`PrivateMessage.java`)
```java
package com.example.realtime.patterns.model;

import java.time.Instant;

public class PrivateMessage {

    private String sender;
    private String recipient;
    private String content;
    private String correlationId;
    private Instant timestamp;

    public PrivateMessage() {
        this.timestamp = Instant.now();
    }

    public PrivateMessage(String sender, String recipient, String content, String correlationId) {
        this.sender = sender;
        this.recipient = recipient;
        this.content = content;
        this.correlationId = correlationId;
        this.timestamp = Instant.now();
    }

    // --- Getters and Setters ---
    public String getSender() { return sender; }
    public void setSender(String sender) { this.sender = sender; }

    public String getRecipient() { return recipient; }
    public void setRecipient(String recipient) { this.recipient = recipient; }

    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }

    public String getCorrelationId() { return correlationId; }
    public void setCorrelationId(String correlationId) { this.correlationId = correlationId; }

    public Instant getTimestamp() { return timestamp; }
    public void setTimestamp(Instant timestamp) { this.timestamp = timestamp; }
}
```

#### 3. Message Controller (`PrivateMessageController.java`)
```java
package com.example.realtime.patterns.controller;

import com.example.realtime.patterns.model.PrivateMessage;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.messaging.simp.SimpMessageHeaderAccessor;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Controller;
import java.security.Principal;

@Controller
public class PrivateMessageController {

    private final SimpMessagingTemplate messagingTemplate;

    public PrivateMessageController(SimpMessagingTemplate messagingTemplate) {
        this.messagingTemplate = messagingTemplate;
    }

    /**
     * Client A calls "/app/message.private" to target Client B.
     */
    @MessageMapping("/message.private")
    public void sendPrivateMessage(@Payload PrivateMessage message, Principal principal, 
                                   SimpMessageHeaderAccessor headerAccessor) {
        // Resolve secure sender name from Principal connection context
        String senderName = (principal != null) ? principal.getName() : "Anonymous";
        message.setSender(senderName);

        System.out.println("[Private Message Router] From: " + senderName 
                + " | To: " + message.getRecipient() 
                + " | Content: " + message.getContent());

        // Validate recipient field
        if (message.getRecipient() == null || message.getRecipient().trim().isEmpty()) {
            sendErrorMessage(senderName, "Invalid recipient parameter.");
            return;
        }

        // Route the message to the recipient's private user queue.
        // Under the hood, Spring translates this destination from:
        // "/user/{recipient}/queue/private-messages"
        // to a session-specific queue matching the recipient's session ID:
        // "/queue/private-messages-user-session-abc"
        messagingTemplate.convertAndSendToUser(
                message.getRecipient(),                // Target Username (Principal name)
                "/queue/private-messages",             // Destination suffix
                message                                // Payload object
        );
    }

    private void sendErrorMessage(String username, String errorDescription) {
        messagingTemplate.convertAndSendToUser(
                username,
                "/queue/errors",
                "{\"error\":\"" + errorDescription + "\"}"
        );
    }
}
```

---

## 5. Common Mistakes & Debugging Scenarios

### Scenario A: Message Delivery Failure on Client Subscriptions
* **The Problem**: A developer sets up a user queue subscription on the client:
  ```javascript
  stompClient.subscribe('/user/queue/private-messages', callback);
  ```
  The server pushes messages using `convertAndSendToUser("bob", "/queue/private-messages", msg)`. However, Bob never receives the messages.
* **Why it happens**:
  Spring's user destination engine relies on **Principal resolution**. When a client subscribes to `/user/queue/private-messages`, Spring checks the client connection's `Principal` object. If the client is unauthenticated, the `Principal` is `null`. Spring generates a temporary anonymous name (e.g. `user-session-xyz`), mapping the subscription to `/queue/private-messages-user-session-xyz`.
  If the server tries to route the message using the string username `"bob"`, Spring cannot resolve `"bob"` to the anonymous session name, and the frame is dropped.
* **The Fix**: Ensure your client is authenticated (e.g. using Spring Security or your JWT interceptor) before establishing the connection to populate the session `Principal`.

### Scenario B: Data Leak via Incorrect Prefix Mapping
* **The Problem**: A developer attempts to route a private message using a broadcast prefix, e.g. mapping to `/topic/private-messages/{username}`.
* **Why it happens**: While the path contains the username, `/topic/` destinations route to the message broker's Pub/Sub engine. If an attacker subscribes to the wildcard destination `/topic/private-messages/*` (or queries the broker queues), they will intercept all private messages sent to other users.
* **The Fix**: Always route private user data using the designated point-to-point user destination mapping `/user/queue/*`.

---

## 6. Technical Interview Questions

### Question 1: Emulating Request-Response over WebSockets
*Explain how to implement a synchronous Request-Response pattern over an asynchronous WebSocket connection, detailing both client and server requirements.*

**Answer**:
To emulate a synchronous Request-Response pattern over an asynchronous channel, you must implement coordination at the application layer:
1. **Client Generation**: The client generates a unique `Correlation ID` (e.g. a UUID) and attaches it to the request envelope header.
2. **Client Callback Mapping**: The client stores a callback function in a local map registry, keyed by the `Correlation ID`.
3. **Server Processing**: The server receives the request, extracts the `Correlation ID`, executes the operation, and returns the response payload carrying the *same* `Correlation ID` to the client's private user queue.
4. **Client Matching**: The client receives the response, reads the `Correlation ID` from the header envelope, fetches the matching callback from its local map registry, executes it, and removes the entry to prevent memory leaks.

---

### Question 2: Spring User Destination Translation
*How does Spring's `convertAndSendToUser()` target a specific client socket? Describe the step-by-step translation process.*

**Answer**:
1. The server calls `messagingTemplate.convertAndSendToUser("Bob", "/queue/private-messages", payload)`.
2. The template prefixes the destination, creating `/user/Bob/queue/private-messages`.
3. The message is dispatched to the `UserDestinationMessageHandler`.
4. The handler queries the `SimpUserRegistry` to locate all active WebSocket sessions associated with the username `"Bob"`.
5. For each session ID found (e.g. `session-abc123`), the handler translates the destination into a session-specific queue destination: `/queue/private-messages-user-session-abc123`.
6. The message is sent to the broker, which writes the frame directly to the matching client socket.

---

## Summary
- **Point-to-Point Messaging** routes frames to a specific client, whereas **Broadcast Messaging** replicates frames to all active topic subscribers.
- **Request-Response over WebSockets** is emulated at the application layer using **Correlation IDs** to match asynchronous responses to client requests.
- **The Envelope Pattern** wraps payloads in a standard metadata header wrapper, decoupling routing logic from core data schemas.
- **Commands** request action processing and route to controllers, while **Events** announce state changes and broadcast to topics.
- **Private User Messaging** utilizes Spring's `/user` destination mappings and principal propagation to securely route messages to specific client sessions.
