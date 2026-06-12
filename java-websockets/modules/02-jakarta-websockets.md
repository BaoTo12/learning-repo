# Module 02: Jakarta WebSockets — JSR 356 & Thread-Safe Sessions

Welcome back, class. Today we discuss **Jakarta WebSockets (JSR 356) (CS-520)**.

Before Spring Boot WebSocket integrations gained dominance, Java EE standardized WebSocket development under the JSR 356 specification. This standard defines declarative annotations like `@ServerEndpoint` to create socket servers and provides lifecycle hooks to handle connections.

However, many engineers deploy JSR 356 endpoints to production without understanding their threading models. They run into `IllegalStateException` errors because they attempt to write messages concurrently from multiple threads to the same connection session. Today, we will study the JSR 356 lifecycle, analyze the **Session Thread-Safety** problem, and write a thread-safe message broadcaster.

---

## 1. Academic Lecture: The JSR 356 Lifecycle & Concurrency

JSR 356 provides a standard Java API to manage full-duplex socket lifecycles.

### 1. Server Endpoint Annotations
A WebSocket endpoint is declared using `@ServerEndpoint(value = "/path")`. The server instantiates a **new instance** of the endpoint class for every client connection. It maps callbacks using annotations:
*   `@OnOpen`: Executed when the handshake completes and the session starts.
*   `@OnMessage`: Executed when a frame (Text or Binary) is received.
*   `@OnClose`: Executed when the connection closes.
*   `@OnError`: Executed when a connection failure occurs.

### 2. The Session Concurrency Conundrum
When a client connects, the container creates a `jakarta.websocket.Session` object to represent the connection. The session provides two objects to send messages:
*   `session.getBasicRemote()`: Synchronous, blocking writes.
*   `session.getAsyncRemote()`: Asynchronous, non-blocking writes.

*   **The Crucial Rule**: The JSR 356 specification states that the `RemoteEndpoint` objects returned by these methods **are not thread-safe**. If Thread A calls `session.getBasicRemote().sendText("ping")` while Thread B is calling `session.getBasicRemote().sendText("pong")` on the same session, the server throws an `IllegalStateException` ("blocking write in progress").
*   **The Solution**: You must synchronize all write operations targeting the same session, or manage writes through a thread-safe message queue.

```mermaid
graph TD
    A[Broadcast Service Thread A] -->|Attempt write to Session 1| B{Lock on Session 1?}
    C[Broadcast Service Thread B] -->|Attempt write to Session 1| B
    B -- Available -->|Acquire Lock & Send| D[session.getBasicRemote.sendText]
    B -- Blocked -->|Wait for lock release| E[Thread Waits]
```

---

## 2. Theory vs. Production Trade-offs

### Synchronous Blocking writes vs. Asynchronous writes
*   **Synchronous (`session.getBasicRemote()`)**:
    *   *Pro*: Simple flow control. You know immediately if the write succeeded or failed.
    *   *Con*: High latency. If a client has a slow network connection, your server thread blocks waiting for TCP packet acknowledgements.
*   **Asynchronous (`session.getAsyncRemote()`)**:
    *   *Pro*: Non-blocking. The thread returns immediately, while the container queues the payload in memory.
    *   *Con*: High risk of Out-Of-Memory (OOM) errors. If the server queue grows faster than the client's network speed, the JVM will run out of heap space.

---

## 3. How to Use: Thread-Safe Broadcaster and Custom Encoders

Let us write a compile-grade JSR 356 endpoint that implements custom encoders/decoders and ensures thread-safe message transmission.

### A. The Concurrent write Collision (Anti-Pattern)

Avoid this concurrent write anti-pattern. It iterates over sessions and writes messages without synchronization:

```java
package com.capstone.security.ws.vulnerable;

import jakarta.websocket.Session;
import java.io.IOException;
import java.util.Set;

public class VulnerableBroadcaster {
    public static void broadcast(Set<Session> sessions, String message) {
        for (Session session : sessions) {
            if (session.isOpen()) {
                try {
                    // DANGER: Throws IllegalStateException if another thread writes to this session concurrently!
                    session.getBasicRemote().sendText(message);
                } catch (IOException e) {
                    e.printStackTrace();
                }
            }
        }
    }
}
```

### B. The Hardened Thread-Safe Broadcaster (Production Pattern)

Here is a hardened broadcaster. It synchronizes writes on the session object to prevent concurrent collisions and uses custom Jackson Encoders/Decoders to parse JSON.

First, define the Custom Text Encoder for JSON payloads:

```java
package com.capstone.security.ws.secure.coders;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.websocket.Encoder;

/**
 * Text Encoder to translate Java objects to JSON strings.
 */
public class MessageEncoder implements Encoder.Text<Object> {
    private final ObjectMapper mapper = new ObjectMapper();

    @Override
    public String encode(Object object) throws JsonProcessingException {
        return mapper.writeValueAsString(object);
    }

    @Override
    public void init(jakarta.websocket.EndpointConfig config) {}

    @Override
    public void destroy() {}
}
```

Next, implement the Thread-Safe Endpoint:

```java
package com.capstone.security.ws.secure.endpoint;

import com.capstone.security.ws.secure.coders.MessageEncoder;
import jakarta.websocket.*;
import jakarta.websocket.server.ServerEndpoint;
import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;
import java.util.logging.Logger;

@ServerEndpoint(
    value = "/secure-chat",
    encoders = { MessageEncoder.class }
)
public class ThreadSafeChatEndpoint {
    private static final Logger LOGGER = Logger.getLogger(ThreadSafeChatEndpoint.class.getName());

    // Thread-safe map storing active sessions
    private static final Map<String, Session> SESSIONS = new ConcurrentHashMap<>();

    @OnOpen
    public void onOpen(Session session) {
        LOGGER.info("Connection established: " + session.getId());
        SESSIONS.put(session.getId(), session);
    }

    @OnClose
    public void onClose(Session session) {
        LOGGER.info("Connection closed: " + session.getId());
        SESSIONS.remove(session.getId());
    }

    @OnError
    public void onError(Session session, Throwable throwable) {
        LOGGER.log(Level.SEVERE, "Session error on: " + session.getId(), throwable);
    }

    /**
     * Broadcasts a payload to all connected clients.
     * Enforces thread-safe, synchronized writes.
     */
    public static void broadcast(Object payload) {
        for (Session session : SESSIONS.values()) {
            if (session.isOpen()) {
                // SECURE: Synchronize on the session object to prevent concurrent write collisions
                synchronized (session) {
                    try {
                        session.getBasicRemote().sendObject(payload);
                    } catch (IOException | EncodeException e) {
                        LOGGER.log(Level.WARNING, "Failed to send message to session: " + session.getId(), e);
                    }
                }
            }
        }
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Retaining References to Closed Sessions
Failing to remove a session object from your registry map inside the `@OnClose` callback.
*   **Why it fails**: It causes memory leaks. The garbage collector cannot release closed session resources, leading to Heap Exhaustion (OOM) over time.
*   **Mitigation**: Always remove sessions from connection maps in both `@OnClose` and `@OnError` methods.

---

## 5. Socratic Review Questions

### Question 1
Explain why using `session.getBasicRemote()` can block application threads for prolonged periods when dealing with slow mobile network clients.

#### Answer
`session.getBasicRemote()` executes blocking writes. When the server writes bytes to a client, the thread blocks waiting for TCP packet acknowledgements (ACKs) from the client's network. If the client is on a slow or unreliable mobile network, the server thread remains blocked. If many clients are slow, all thread pool threads will block, causing thread starvation and crashing the application.

### Question 2
What is the purpose of the JSR 356 `@OnError` annotation? Can you safely write to a session inside an `@OnError` handler?

#### Answer
The `@OnError` annotation handles connection failures, packet errors, or JSON parsing exceptions. 
Writing to a session inside an `@OnError` handler is unsafe because the error often indicates that the underlying TCP socket is broken or closing. Writing to it can trigger another write exception, leading to infinite error loops.

---

## 6. Hands-on Challenge: Implementing a Safe Broadcaster

### The Challenge
In this challenge, you will implement a thread-safe message broadcaster.

Your task is to implement the broadcast method in `ThreadSafeSessionBroadcaster`:
1.  Iterate over the active session list.
2.  Perform a check to ensure the session `isOpen()` is true.
3.  Synchronize the write to prevent concurrent write collisions on the session.

Complete the implementation below:

```java
package com.capstone.security.ws.challenge;

import jakarta.websocket.Session;
import java.io.IOException;
import java.util.List;

public class ThreadSafeSessionBroadcaster {

    /**
     * Broadcasts a text message to a list of sessions safely.
     * 
     * @param sessions The list of target client sessions
     * @param message The text message to send
     */
    public void broadcast(List<Session> sessions, String message) {
        if (sessions == null || message == null) {
            return;
        }

        for (Session session : sessions) {
            // TODO: Complete the logic.
            // 1. Check if session.isOpen() is true.
            // 2. Synchronize on the session object.
            // 3. Call session.getBasicRemote().sendText(message) inside a try-catch block.
        }
    }
}
```

Write the synchronization code. Save the completed class and explain the thread concurrency behavior of standard WebSocket servers inside `modules/02-jakarta-websockets.md`.
