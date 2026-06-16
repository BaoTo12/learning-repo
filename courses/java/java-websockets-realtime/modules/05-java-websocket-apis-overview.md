# Module 5: Java WebSocket APIs Overview

Java offers multiple libraries and specifications for building WebSocket applications. While some projects require low-level control over raw frames, others benefit from high-level messaging abstractions. 

This module provides a comprehensive overview of the Java WebSocket ecosystem. We will compare standard Jakarta EE WebSocket specifications (`jakarta.websocket`) against the Spring WebSocket ecosystem and high-level subprotocols like STOMP. We will analyze the trade-offs of each approach and implement a thread-safe collaborative server using the Jakarta API.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the transition** from Java EE `javax.websocket` (JSR 356) to Jakarta EE `jakarta.websocket` APIs.
2. **Differentiate between annotation-based and programmatic models** in the Jakarta WebSocket specification.
3. **Compare remote interface modes**—synchronous (`Basic`) versus asynchronous (`Async`) message delivery in Jakarta sessions.
4. **Detail Spring Framework's WebSocket abstractions** and explain the role of Handshake Interceptors.
5. **Analyze the STOMP messaging protocol** and configure in-memory vs. external brokers in Spring Boot.
6. **Formulate a selection matrix** choosing between raw frame protocol handlers and high-level application abstractions.

---

## 1. The Evolution of Java WebSocket APIs

To unify WebSocket support across Java web containers (like Tomcat, Jetty, and GlassFish), the Java Community Process defined **JSR 356: Java API for WebSockets** in 2013, creating the `javax.websocket` namespace.

With the transition of Java EE to the Eclipse Foundation:
- The API was renamed to **Jakarta WebSocket**.
- In Jakarta EE 9 and Spring Boot 3+, the namespace shifted from **`javax.websocket` to `jakarta.websocket`**.
- The underlying API signatures, annotations, and lifecycle contracts remain identical, but import statements must reference the `jakarta` namespace.

---

## 2. Jakarta WebSocket API Integration Models

The Jakarta API is container-agnostic; code written using `jakarta.websocket` runs seamlessly in Tomcat, Jetty, Undertow, or WildFly. The API provides two integration models: annotation-based and programmatic.

### 1. Annotation-Based Lifecycle Model
Developers define WebSocket endpoints by annotating a Java class:
- **`@ServerEndpoint(value = "/path/{param}")`**: Declares a class as a WebSocket server endpoint. Path parameters can be resolved dynamically.
- **`@OnOpen`**: Executed when a client completes the handshake. The method receives the `Session` object.
- **`@OnMessage`**: Executed when a data frame (Text or Binary) is received.
- **`@OnClose`**: Executed when the connection is terminated.
- **`@OnError`**: Executed when an exception occurs (e.g. socket drop, framing error).

### 2. Programmatic Endpoint Model
While the annotation model is popular, the Jakarta specification supports a **programmatic endpoint model**, which is useful when you need to inject dependencies or dynamically register endpoints:
- Extend **`jakarta.websocket.Endpoint`** and override the `onOpen(Session session, EndpointConfig config)` lifecycle method.
- Implement **`MessageHandler.Whole<String>`** or `MessageHandler.Partial<ByteBuffer>` to receive incoming payloads.
- Register endpoints programmatically by implementing **`ServerApplicationConfig`**. During boot, the web container scans the classpath, executes this configuration class, and registers the returned endpoints.

#### Code Example: Programmatic Endpoint and Config
```java
package com.example.realtime.api.jakarta.programmatic;

import jakarta.websocket.*;
import jakarta.websocket.server.ServerApplicationConfig;
import jakarta.websocket.server.ServerEndpointConfig;
import java.io.IOException;
import java.util.Collections;
import java.util.Set;

// 1. Programmatic Endpoint Class
public class CustomProgrammaticEndpoint extends Endpoint {

    @Override
    public void onOpen(Session session, EndpointConfig config) {
        System.out.println("[Programmatic WS] Connection opened: " + session.getId());
        
        // Register a message handler to parse incoming text frames
        session.addMessageHandler(new MessageHandler.Whole<String>() {
            @Override
            public void onMessage(String message) {
                System.out.println("[Programmatic WS] Message received: " + message);
                try {
                    // Echo message back
                    session.getBasicRemote().sendText("ECHO: " + message);
                } catch (IOException e) {
                    System.err.println("Send failed: " + e.getMessage());
                }
            }
        });
    }

    @Override
    public void onClose(Session session, CloseReason closeReason) {
        System.out.println("[Programmatic WS] Connection closed: " + session.getId());
    }

    @Override
    public void onError(Session session, Throwable thr) {
        System.err.println("[Programmatic WS] Error on session " + session.getId() + ": " + thr.getMessage());
    }
}

// 2. Server Application Config for Programmatic Registration
class MyServerAppConfig implements ServerApplicationConfig {

    @Override
    public Set<ServerEndpointConfig> getEndpointConfigs(Set<Class<? extends Endpoint>> endpointClasses) {
        // Dynamically configure and register the programmatic endpoint on path /ws/programmatic
        ServerEndpointConfig config = ServerEndpointConfig.Builder
                .create(CustomProgrammaticEndpoint.class, "/ws/programmatic")
                .build();
        return Collections.singleton(config);
    }

    @Override
    public Set<Class<?>> getAnnotatedEndpointClasses(Set<Class<?>> scanned) {
        // Return scanned annotated endpoint classes (empty list if annotations are disabled)
        return scanned;
    }
}
```

---

## 3. Web Container Session Management Internals

When a client upgrades to a WebSocket connection, the underlying web container (Tomcat or Jetty) must keep the connection state active on the JVM heap.

### 1. Tomcat WebSocket Internals (`WsSession`)
- **Session Tracking**: Tomcat stores active sessions inside a concurrent map (`WsServerContainer.sessions`).
- **Thread Model**: Tomcat utilizes two thread pools:
  - **Acceptor / Poller Threads (NIO)**: Monitor native sockets for incoming TCP bytes. When frames arrive, they read the bytes and dispatch them to the container's execution thread pool.
  - **Executor Thread Pool**: Decodes frame headers and executes application lifecycle callbacks (`@OnMessage`).
- **Buffer Memory**: Every `WsSession` allocates an internal text message buffer and binary message buffer (default 8 KiB each). If the client sends frames exceeding this size, Tomcat throws an exception and closes the connection.

### 2. Jetty WebSocket Internals (`WebSocketSession`)
- **Session Tracking**: Jetty tracks connections inside its `WebSocketSessionListener` registry.
- **Thread Model**: Jetty utilizes its **EatWhatYouKill** execution strategy, which coordinates thread handoffs between socket selectors and task execution loops on the same thread when CPU caches are warm, reducing context switching overhead under high load.

---

## 4. Message Transmission remote APIs
A client session is represented by a `jakarta.websocket.Session` object. To send messages, developers access the `RemoteEndpoint` via two styles:

### Synchronous: `Session.getBasicRemote()`
- Blocks the calling thread until the message is completely written to the TCP socket.
- **The Risk**: If two threads attempt to call `sendText()` concurrently on the same `BasicRemote` instance, the container throws a `java.lang.IllegalStateException: The remote endpoint was in state [TEXT_WRITING]`. Developers must implement explicit synchronization locks.

### Asynchronous: `Session.getAsyncRemote()`
- Non-blocking. It queues the message for delivery and returns immediately.
- Returns a `Future<Void>` or accepts a `SendHandler` to notify the application of success or failure.

---

## 5. Spring WebSocket Core Abstractions

Spring Boot provides its own integration layer on top of Jakarta WebSockets, offering unified configuration, dependency injection integration, and handler mappings.

### 1. Core Handlers
Rather than using annotations, Spring relies on the `WebSocketHandler` interface:
- **`TextWebSocketHandler`**: A helper class focused on processing text frames (`TextMessage`).
- **`BinaryWebSocketHandler`**: A helper class focused on processing binary frames (`BinaryMessage`).
- **`WebSocketSession`**: Spring's abstraction wrapping the native container session.

### 2. Handshake Interceptors (`HandshakeInterceptor`)
Spring integrates with the HTTP Upgrade handshake before the connection swaps protocols:
- `beforeHandshake()`: Allows inspecting request headers, validating cookies, and copying attributes from the HTTP `HttpSession` into the WebSocket session map (making them accessible during the WebSocket lifecycle).
- `afterHandshake()`: Executes post-upgrade logging or initialization.

---

## 6. High-Level Subprotocols: STOMP in Spring

WebSockets are transport-level sockets. The protocol has no built-in message-routing headers (like "to whom", "from whom", or "what topic"). Without a subprotocol, developers must write custom JSON message formats and parsing code.

To solve this, Spring supports **STOMP (Simple Text Oriented Messaging Protocol)** as a WebSocket subprotocol.

### 1. STOMP Frame Structure
STOMP is a text-based framing protocol modeled after HTTP. A STOMP frame contains a command, headers, and a body:

```http
SEND
destination:/topic/room1
content-type:application/json

{"user":"Alice","message":"Hello"}
^@
```
*(Here, `^@` is the NULL byte `\u0000` marking the frame boundary).*

### 2. Spring Integration Brokers
When using STOMP in Spring Boot:
- **`@MessageMapping("/route")`**: Maps incoming STOMP messages to specific controller methods.
- **`@SendTo("/topic/broadcast")`**: Automatically routes the return value of a controller to a destination topic.
- **The Broker**:
  - **Simple Broker**: A built-in, in-memory message broker. It is easy to configure but does not scale horizontally (cannot sync messages across multiple server nodes).
  - **External Broker (ActiveMQ / RabbitMQ)**: Spring routes STOMP frames over TCP to an external message broker, which distributes messages across all instances, enabling clustering.

---

## 7. Comparison: Raw Protocol vs. Framework Abstractions

Choosing the right layer of abstraction depends on the application's complexity, throughput requirements, and scaling needs:

### 1. Raw WebSockets (Jakarta / Spring handlers)
* **Advantages**:
  - **Maximum Performance**: Near-zero parsing overhead. Ideal for processing high-frequency data streams.
  - **Minimal Memory footprint**: No broker queues or protocol mappings are allocated.
* **Limitations**:
  - **No Out-of-the-Box Routing**: You must design a custom message format and write your own dispatcher.
  - **High Complexity**: You must manage user sessions, room maps, and connection states manually.
* **Use Cases**: Live stock tickers, telemetry updates, multiplayer game engines.

### 2. High-Level STOMP Abstraction (Spring STOMP)
* **Advantages**:
  - **Standardized Messaging**: Built-in pub/sub destinations (`/topic/...`) and point-to-point queues (`/queue/...`).
  - **Out-of-the-Box Integration**: Easily integrates with external brokers for scaling.
  - **Security Mappings**: Supports Spring Security message-level authorization rules.
* **Limitations**:
  - **Higher Overhead**: Text parsing and frame encapsulation consume additional CPU cycles.
* **Use Cases**: Multi-room chat engines, collaborative document editors, live notifications dashboards.

### Selection Matrix:

| Feature | Raw Jakarta / Spring Handler | Spring STOMP Abstraction |
| :--- | :--- | :--- |
| **Routing Protocol** | Custom (You write JSON routes) | Standard STOMP destinations |
| **Session Tracking** | Manual Concurrent Maps | Handled by spring-messaging |
| **Scale-Out Strategy**| Custom Pub/Sub (Redis/Kafka) | Native External Broker Relay |
| **Security Controls** | Interceptor check | Message-level channel interceptors |
| **Performance/Throughput**| Maximum | Moderate (Header overhead) |

---

## 8. Hands-On Lab: Building a Jakarta Collaborative Broadcast Server

In this lab, you will implement a collaborative room server using the Standard Jakarta WebSocket API. 

### Objective:
Build a server endpoint `/collaborate/{room}` that tracks connected user sessions in room-specific sets, validates text messages, and broadcasts updates thread-safely to all participants in the room.

### Code Implementation (`CollaborativeServerEndpoint.java`):

```java
package com.example.realtime.api.jakarta;

import jakarta.websocket.*;
import jakarta.websocket.server.PathParam;
import jakarta.websocket.server.ServerEndpoint;
import java.io.IOException;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArraySet;

@ServerEndpoint(value = "/collaborate/{room}")
public class CollaborativeServerEndpoint {

    // Thread-safe map nesting room-specific sets of active sessions
    private static final Map<String, Set<Session>> roomRegistry = new ConcurrentHashMap<>();

    /**
     * Triggered when a new client completes the handshake.
     */
    @OnOpen
    public void onOpen(Session session, @PathParam("room") String room) {
        System.out.println("[Session Opened] ID: " + session.getId() + " joined room: " + room);
        
        // Add session to the corresponding room registry
        roomRegistry.computeIfAbsent(room, k -> new CopyOnWriteArraySet<>()).add(session);
        
        // Push welcome confirmation payload
        try {
            session.getBasicRemote().sendText("{\"status\":\"CONNECTED\",\"roomId\":\"" + room + "\"}");
        } catch (IOException e) {
            System.err.println("Failed to send welcome message to session " + session.getId());
        }
    }

    /**
     * Triggered when a client sends a text frame.
     */
    @OnMessage
    public void onMessage(String message, Session session, @PathParam("room") String room) {
        System.out.println("[Message Received] Room: " + room + " | From: " + session.getId() + " | Payload: " + message);
        
        // Validate payload content (simplistic check)
        if (message == null || message.trim().isEmpty()) {
            return;
        }

        // Broadcast to all other sessions in the same room
        broadcastToRoom(room, message, session);
    }

    /**
     * Triggered when the connection closes.
     */
    @OnClose
    public void onClose(Session session, @PathParam("room") String room, CloseReason reason) {
        System.out.println("[Session Closed] ID: " + session.getId() + " | Reason: " + reason.getReasonPhrase());
        
        Set<Session> sessions = roomRegistry.get(room);
        if (sessions != null) {
            sessions.remove(session);
            // Clean up the map entry if the room is empty
            if (sessions.isEmpty()) {
                roomRegistry.remove(room);
                System.out.println("[Registry Clean] Room " + room + " is empty. Removed entry.");
            }
        }
    }

    /**
     * Triggered when a socket error occurs.
     */
    @OnError
    public void onError(Session session, Throwable throwable) {
        System.err.println("[Socket Error] Session ID: " + (session != null ? session.getId() : "Unknown") 
                + " | Exception: " + throwable.getMessage());
    }

    /**
     * Broadcasts a message to all active sessions in the room, excluding the sender.
     */
    private void broadcastToRoom(String room, String message, Session sender) {
        Set<Session> activeSessions = roomRegistry.get(room);
        if (activeSessions == null || activeSessions.isEmpty()) {
            return;
        }

        for (Session clientSession : activeSessions) {
            // Skip sending the message back to the sender
            if (clientSession.getId().equals(sender.getId())) {
                continue;
            }

            // Verify the connection is open before attempting to transmit
            if (!clientSession.isOpen()) {
                continue;
            }

            // Lock the session object to prevent concurrent writes on BasicRemote,
            // which would cause IllegalStateException.
            synchronized (clientSession) {
                try {
                    clientSession.getBasicRemote().sendText(message);
                } catch (IOException e) {
                    System.err.println("Failed to broadcast message to session " + clientSession.getId() 
                            + ". Triggering close.");
                    try {
                        clientSession.close(new CloseReason(CloseReason.CloseCodes.UNEXPECTED_CONDITION, "Send error"));
                    } catch (IOException ie) {
                        // ignore
                    }
                }
            }
        }
    }
}
```

---

## 9. Common Mistakes & Debugging Scenarios

### Scenario A: Concurrent Write Crashes on `BasicRemote`
* **The Problem**: A Jakarta WebSocket chat application runs fine with low traffic. However, during load testing, the server console is flooded with `java.lang.IllegalStateException: The remote endpoint was in state [TEXT_WRITING]` exceptions, and client connections are closed.
* **Why it happens**: According to the Jakarta WebSocket specification, `RemoteEndpoint.Basic` is **not thread-safe**. If a server attempts to write to a client socket (via `sendText()`) while another thread (e.g. processing a broadcast event or a background task) is already writing a message to the same socket, the container throws this state exception and aborts the connection.
* **The Fix**:
  1. Wrap your synchronous socket writes in a `synchronized` block keyed on the `Session` object instance (as shown in line 118 of the lab code).
  2. Alternatively, switch to the asynchronous remote interface: `session.getAsyncRemote().sendText(message)`.

### Scenario B: Memory Leak via Zombie Sessions
* **The Problem**: Over time, memory usage increases. Heap dumps reveal thousands of closed `Session` objects retained in memory.
* **Why it happens**: If a client disconnects, `@OnClose` is called. However, if your code fails to remove the closed `Session` reference from your static map or set registry, the session remains strongly referenced as a GC root, preventing the garbage collector from reclaiming the session buffers and socket structures.
* **The Fix**: Always implement removal logic in your `@OnClose` and `@OnError` methods (as shown in lines 57–67 of the lab code).

---

## 10. Technical Interview Questions

### Question 1: BasicRemote vs. AsyncRemote
*Contrast `Session.getBasicRemote()` with `Session.getAsyncRemote()` in the Jakarta WebSocket API. When would you choose one over the other?*

**Answer**:
- **`getBasicRemote()`** performs synchronous, blocking writes. It blocks the calling thread until the bytes are completely written to the TCP socket buffer. It is simpler to use but is not thread-safe. If multiple threads write to the same session concurrently, they will trigger an `IllegalStateException`.
- **`getAsyncRemote()`** performs non-blocking, asynchronous writes. It queues the message and returns immediately. It is thread-safe and prevents Tomcat threads from blocking under load.
- *Selection*: Choose `getBasicRemote()` for simple, single-threaded execution paths where you need absolute confirmation of delivery before proceeding, and ensure you wrap writes in synchronized blocks. Choose `getAsyncRemote()` for high-throughput broadcast servers to prevent thread pool starvation.

---

### Question 2: Why STOMP Over WebSockets?
*Why would you choose to use STOMP over raw WebSockets when building a chat system in Spring Boot?*

**Answer**:
WebSockets operate at the transport layer, transferring raw frames without routing headers. If you use raw WebSockets, you must design your own application protocol (e.g. defining JSON structures containing `"action": "sendMessage"`, `"to": "room_B"`) and write your own controller routing logic.

STOMP is a standardized subprotocol that defines messaging commands (`CONNECT`, `SEND`, `SUBSCRIBE`) and destination header mappings. Using STOMP allows you to leverage Spring's built-in message-routing infrastructure (mapping messages to controller methods using `@MessageMapping`) and integrate with enterprise message brokers (like RabbitMQ) for horizontal scaling, reducing development complexity.

---

## Summary
- **Jakarta WebSocket API** is the container-agnostic Java standard (`jakarta.websocket`) that utilizes annotation-based lifecycles.
- **`Session` remote interfaces** determine thread blocking behavior: synchronous `BasicRemote` requires external thread synchronization, while `AsyncRemote` queues writes non-blockingly.
- **Spring WebSocket** provides handlers (`TextWebSocketHandler`), handshake interceptors, and integrations with standard Spring Boot configs.
- **STOMP** is a messaging subprotocol that introduces frame routing headers (`destination`), enabling simple mapping controllers and integrations with RabbitMQ.
- **Raw WebSockets** maximize performance for low-overhead binary streams, while **Framework Abstractions (STOMP)** simplify session routing and pub/sub room configurations.
