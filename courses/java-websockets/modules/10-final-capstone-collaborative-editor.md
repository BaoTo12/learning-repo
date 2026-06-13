# Module 10: Capstone — Building a Clustered Collaborative Editor

Welcome to your **Final Capstone Project**, class.

You have studied WebSocket TCP handshakes, Jakarta EE JSR 356 session boundaries, Spring handler configs, STOMP routing channels, JWT security interceptors, RabbitMQ broker relays, Project Reactor non-blocking streams, heartbeat configs, and integration tests. Now, it is time to synthesize these components to build a production-ready **Clustered Collaborative Document Editor**.

In this capstone, we will analyze the system architecture of a collaborative editor, discuss operational transformation considerations, and write the backend messaging controller, secure token interceptor, and clustering relay configurations.

---

## 1. Academic Lecture: Collaborative Systems Architecture

Real-time collaborative editing (like Google Docs) requires synchronizing keystrokes across multiple users with sub-100ms latency.

### The Real-Time Synchronizer Architecture
In a clustered production environment:
1.  Users connect to the nearest server node via WebSockets.
2.  The initial handshake is upgraded anonymously, but the STOMP `CONNECT` frame requires a JWT token validated by a **ChannelInterceptor**.
3.  Once authenticated, users subscribe to a document-specific topic: `/topic/document.{docId}`.
4.  When a user types a character, their browser sends a STOMP `SEND` frame to `/app/document.{docId}.edit` containing the text delta.
5.  The node processes the edit, validates the user's permissions, and forwards the frame to the **RabbitMQ STOMP Broker Relay**.
6.  RabbitMQ broadcasts the delta event across all cluster nodes, which immediately deliver it to all active subscribers.

```
                  Clustered Synthesis Flow
                  
   Client A --------> Spring Node 1 --------> [RabbitMQ Broker Relay]
                                                      |
   Client B <-------- Spring Node 2 <-----------------+
  (Client A sends an edit. Node 1 relays to RabbitMQ, which
   broadcasts to Node 2, instantly updating Client B's screen.)
```

---

## 2. Theory vs. Production Trade-offs

### Operational Transformation (OT) vs. Conflict-Free Replicated Data Types (CRDTs)
*   **Operational Transformation (OT)**:
    *   *Pro*: Centralized server reconciles edits (e.g. inserting character "a" at index 5). Resolves positioning conflicts mathematically before broadcasting.
    *   *Con*: High CPU overhead on the server. The server must maintain a history of all document states to transform conflicting edit indexes.
*   **Conflict-Free Replicated Data Types (CRDTs)**:
    *   *Pro*: Decentralized. Clients resolve conflicts mathematically in the browser, reducing server load.
    *   *Con*: High network payload size. Every character requires unique metadata identifiers (e.g. logical clocks, parent node IDs).
*   **Production Rule**: For standard document editors, rely on CRDTs (like Yjs or Automerge) executed on the client, using the Java STOMP broker relay as a high-speed, agnostic message transport layer.

---

## 3. How to Use: The Hardened Collaborative Editor Hexagon

Let us write the complete, compile-grade Java 21 classes that implement the secure, clustered collaborative editor.

### A. The Core Messaging Model

```java
package com.capstone.security.capstone.domain;

import java.io.Serializable;

public record DocumentEdit(
    String documentId,
    String sender,
    int position,
    String content,
    String type // "INSERT" or "DELETE"
) implements Serializable {}
```

### B. The Secured Clustered Broker Configuration

Configure the JWT channel interceptor and RabbitMQ broker relay:

```java
package com.capstone.security.capstone.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.simp.config.ChannelRegistration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.messaging.support.MessageHeaderAccessor;
import org.springframework.messaging.MessageDeliveryException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.web.socket.config.annotation.EnableWebSocketMessageBroker;
import org.springframework.web.socket.config.annotation.StompEndpointRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;

import java.util.List;

@Configuration
@EnableWebSocketMessageBroker
public class CapstoneClusteredBrokerConfig implements WebSocketMessageBrokerConfigurer {

    @Override
    public void configureMessageBroker(MessageBrokerRegistry config) {
        // Route client commands to controllers
        config.setApplicationDestinationPrefixes("/app");

        // Route broadcasts to external RabbitMQ Broker Relay
        config.enableStompBrokerRelay("/topic", "/queue")
                .setRelayHost("rabbitmq.internal.corp")
                .setRelayPort(61613)
                .setClientLogin("guest")
                .setClientPasscode("guest")
                .setSystemLogin("guest")
                .setSystemPasscode("guest");
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws-collaborative")
                .setAllowedOrigins("https://editor.corp.com")
                .withSockJS();
    }

    @Override
    public void configureClientInboundChannel(ChannelRegistration registration) {
        // SECURE: Enforce JWT validation on client inbound channel connections
        registration.interceptors(new ChannelInterceptor() {
            @Override
            public Message<?> preSend(Message<?> message, MessageChannel channel) {
                StompHeaderAccessor accessor = MessageHeaderAccessor.getAccessor(message, StompHeaderAccessor.class);
                if (accessor != null && StompCommand.CONNECT.equals(accessor.getCommand())) {
                    List<String> authHeaders = accessor.getNativeHeader("Authorization");
                    if (authHeaders == null || authHeaders.isEmpty()) {
                        throw new MessageDeliveryException("Missing Authorization token.");
                    }
                    String token = authHeaders.get(0);
                    if (!token.startsWith("Bearer secret-key")) {
                        throw new MessageDeliveryException("Invalid credentials.");
                    }
                    
                    // Assign principal to session context
                    accessor.setUser(new UsernamePasswordAuthenticationToken("user_editor", null, List.of()));
                }
                return message;
            }
        });
    }
}
```

### C. The Collaborative Editor Controller

```java
package com.capstone.security.capstone.controllers;

import com.capstone.security.capstone.domain.DocumentEdit;
import org.springframework.messaging.handler.annotation.DestinationVariable;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Controller;

import java.security.Principal;
import java.util.logging.Logger;

@Controller
public class CollaborativeEditorController {
    private static final Logger LOGGER = Logger.getLogger(CollaborativeEditorController.class.getName());

    private final SimpMessagingTemplate messagingTemplate;

    public CollaborativeEditorController(SimpMessagingTemplate messagingTemplate) {
        this.messagingTemplate = messagingTemplate;
    }

    /**
     * Maps to client edits targeting: /app/document.{docId}.edit
     * Validates input permissions and broadcasts the edit to the document room.
     */
    @MessageMapping("/document.{docId}.edit")
    public void processDocumentEdit(
            @DestinationVariable String docId,
            @Payload DocumentEdit edit,
            Principal principal) {
        
        // SECURE: Validate that user principal context matches edit details
        String username = principal.getName();
        LOGGER.info("Processing edit from user: " + username + " on document: " + docId);

        // Map safe verified attributes to edit record
        DocumentEdit validatedEdit = new DocumentEdit(
            docId,
            username,
            edit.position(),
            edit.content(),
            edit.type()
        );

        // Broadcast verified edit to all subscribers connected across the broker cluster
        messagingTemplate.convertAndSend("/topic/document." + docId + ".updates", validatedEdit);
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Bypassing size limits on text payloads
Allowing clients to submit unlimited payload sizes in their STOMP frames (e.g. pasting a 50MB file).
*   **Why it fails**: Large payloads consume massive JVM memory during deserialization, blocking the message channel and crashing the node with Out-Of-Memory (OOM) errors.
*   **Mitigation**: Enforce strict payload size limits in your WebSocket container configuration:
    ```java
    @Override
    public void configureWebSocketTransport(WebSocketTransportRegistration registration) {
        registration.setMessageSizeLimit(64 * 1024); // Cap message size at 64KB
    }
    ```

---

## 5. Socratic Review Questions

### Question 1
Why does establishing the WebSocket handshake anonymously, and then authenticating inside the STOMP CONNECT frame, protect systems from Cross-Site Request Forgery (CSRF)?

#### Answer
CSRF rely on the browser automatically attaching session cookies to HTTP requests (including WebSocket handshake requests). 
By upgrading the socket anonymously and disabling cookie authentication, we eliminate cookie-based session hijack vectors. The client is forced to transmit their credentials explicitly as a header inside the binary STOMP `CONNECT` frame, which standard cross-origin scripts cannot forge without reading the token from client-side memory.

### Question 2
What is the difference between `/topic` and `/queue` routing paths in RabbitMQ STOMP deployments?

#### Answer
*   `/topic`: Maps to RabbitMQ **Topic Exchanges** (broadcasts to all active subscribers). Ideal for collaborative rooms where every user needs to see every edit.
*   `/queue`: Maps to RabbitMQ **Direct Exchanges** (point-to-point queues). If multiple consumers subscribe to `/queue/updates`, RabbitMQ will round-robin messages, delivering each message to exactly one consumer. Ideal for worker task distribution.

---

## 6. Hands-on Challenge: Hardening the Capstone Controller

### The Challenge
In this final capstone challenge, you will implement the validation block for the collaborative edit handler.

Your task is to write the edit processor logic in `CapstoneEditController`:
1.  Verify that the editor username extracted from the `Principal` context matches the sender specified in the `DocumentEdit` payload.
2.  If they do not match, throw an `IllegalArgumentException` to block potential impersonation attacks.
3.  Otherwise, route the payload to `/topic/doc.{docId}.updates` using `SimpMessagingTemplate`.

Complete the implementation below:

```java
package com.capstone.security.capstone.challenge;

import com.capstone.security.capstone.domain.DocumentEdit;
import org.springframework.messaging.handler.annotation.DestinationVariable;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Controller;
import java.security.Principal;

@Controller
public class CapstoneEditController {

    private final SimpMessagingTemplate template;

    public CapstoneEditController(SimpMessagingTemplate template) {
        this.template = template;
    }

    public void handleEdit(
            @DestinationVariable String docId, 
            DocumentEdit edit, 
            Principal principal) {
        
        // TODO: Complete the validation check.
        // 1. Verify principal is not null and has a name.
        // 2. Assert that principal.getName() is equal to edit.sender().
        //    (If they do not match, throw new IllegalArgumentException("Impersonation detected"))
        // 3. Send the verified edit payload to the destination: "/topic/doc." + docId + ".updates"
    }
}
```

Write the verification check. Save the completed controller and describe your validation strategy inside `modules/10-final-capstone-collaborative-editor.md`.
