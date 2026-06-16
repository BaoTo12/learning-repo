# Module 1: Introduction to Real-Time Systems

Real-time web applications have transitioned from luxury features to standard user expectations. From collaborative document editors and live trading platforms to multi-player gaming and instant notification dashboards, modern software requires immediate data synchronization. 

This module explores the foundational architectures of real-time communication on the web. We will examine the boundaries of the classical HTTP request-response cycle, map alternative real-time transport mechanisms, analyze their engineering trade-offs, and implement production-ready Java code to see these patterns in action.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the mechanical limitations** of traditional HTTP/1.x request-response cycles regarding latency and resource consumption.
2. **Differentiate between pull and push models** of real-time web communication.
3. **Implement short and long polling mechanisms** in Java using Spring Boot's asynchronous REST frameworks (`DeferredResult`).
4. **Deploy Server-Sent Events (SSE)** using `SseEmitter` to push real-time data from server to client.
5. **Compare the architectures** of WebSockets, Long Polling, SSE, and WebTransport to choose the correct protocol for a given network topology and latency requirement.
6. **Formulate production-grade strategies** for managing connection timeouts, load-balancer buffering, and thread pool sizing in real-time Java applications.

---

## 1. What are Real-Time Systems?

In classical web architectures, data updates are static and transactional. A client requests a page, the server returns the HTML/JSON, and the communication channel is closed. If new data arrives at the server millisecond later, the client remains oblivious until the next explicit request.

In a **real-time system**, the boundary between data generation and data consumption is minimized. We define web real-time systems as **soft real-time systems**:
* **Soft Real-Time**: Missing a deadline degrades the user experience but does not cause system failure (e.g., a chat message arriving 2 seconds late, or a stock chart lag).
* **Hard Real-Time**: Missing a deadline results in total system failure (e.g., automotive braking systems, pacemakers, flight control computers). The Java mechanisms we build on the web fall strictly under soft real-time.

```
Classical Pull (On-Demand)
Client  | ───Request───► | Server
Client  | ◄───Response── | Server (Channel closed)

Real-Time Push (Continuous)
Client  | ───Establish──► | Server (Persistent channel)
Client  | ◄───Data Event─ | Server (Immediate push)
Client  | ◄───Data Event─ | Server (Immediate push)
```

---

## 2. HTTP Request-Response (Pull) Limitations

The Hypertext Transfer Protocol (HTTP) was designed as a stateless, unidirectional document retrieval protocol. While HTTP/2 and HTTP/3 have modernized the underlying transport layers, the application-level semantics remain fundamentally bound to a **pull-based** request-response loop.

Here are the key mechanical limitations that prevent traditional HTTP from scaling for real-time systems:

### 1. Connection Establishment Overhead (TCP + TLS Handshake)
Every time a client opens a new HTTP/1.x connection to pull data:
- **TCP Three-Way Handshake**: Requires 1.5 Round Trip Times (RTT) to exchange SYN, SYN-ACK, and ACK packets.
- **TLS Handshake**: TLS 1.3 adds 1 RTT for cryptographic key exchanges. TLS 1.2 adds 2 RTTs.
- *Result*: A client must wait up to 3 RTTs before it can even transmit the HTTP request bytes. For a client on an LTE mobile connection with a 70ms ping, connection setup adds **over 200ms of latency** before database processing begins.

```
Client                             Server
  │ ─── SYN (1.5 RTT Setup) ──────► │
  │ ◄─── SYN-ACK ────────────────── │
  │ ─── ACK ──────────────────────► │
  │ ─── Client Hello (TLS 1 RTT) ─► │
  │ ◄─── Server Hello / Keys ────── │
  │ ─── HTTP GET Request ─────────► │ (Data transmission finally starts)
```

### 2. Half-Duplex Communication
HTTP is half-duplex: only one party can send data over a connection at any given time. The client sends a request, and must wait for the server's response to complete before transmitting further signals on that TCP stream. The server cannot initiate transmission.

### 3. Header Bloat
HTTP is highly verbose. Every request carries request headers:
- `User-Agent`, `Accept`, `Cookie`, `Sec-Ch-Ua`, etc.
- In modern enterprise applications, cookies containing JWT OAuth2 authorization structures can cause request headers to exceed **2 KiB to 8 KiB** in size.
- If a client polls the server every 1 second to check for updates, and the response is empty (`{"status":"no_updates"}` - 23 bytes), the system wastes kilobytes of network bandwidth transmitting redundant headers.

### 4. Head-of-Line Blocking (HOL)
- In **HTTP/1.1**, a TCP connection can only handle one request at a time. To parallelize requests, browsers open up to 6 concurrent TCP connections per domain. If all 6 connections are waiting for slow backend processing, subsequent requests are blocked in browser queues (Head-of-Line Blocking).
- In **HTTP/2**, multiplexing allows multiple logical streams over a single TCP connection, resolving application-level blocking. However, if a packet is lost at the network layer, TCP stops processing *all* streams until the lost packet is retransmitted, resulting in transport-level Head-of-Line blocking.

---

## 3. Pull-Based Real-Time Approaches: Polling

Before persistent push protocols became standard, developers simulated real-time behavior by adjusting the polling loop frequency.

### 1. Short Polling
In short polling, the client periodically sends HTTP requests to the server at fixed intervals (e.g., every 5 seconds) to check for updates.

```
Client                             Server
  │ ─── GET /updates ─────────────► │
  │ ◄─── No New Data (200 OK) ───── │
  │        (Wait 5 seconds)         │
  │ ─── GET /updates ─────────────► │
  │ ◄─── New Data (200 OK) ──────── │
```

* **How it works**: The server receives the request, queries the database or cache, returns whatever is available immediately, and closes the connection.
* **Trade-offs & Resource Footprint**:
  - **High Resource Waste**: If data changes once every hour, the client executes 720 useless requests. This floods the server with connection handlers, CPU processing cycles, and log writes.
  - **High Latency**: If an event occurs 1 millisecond after a poll response, the client will not know until the next interval expires (up to 5 seconds later).
* **When to use**: When data changes predictably at low intervals, and real-time accuracy is not critical (e.g., checking weather updates or package delivery locations).

### 2. Long Polling (Comet / Reverse Ajax)
Long polling is an optimization of short polling where the server delays its response until new data becomes available or a timeout occurs.

```
Client                             Server
  │ ─── GET /updates (Hold) ──────► │  (Server waits for data...)
  │ . . . (30 seconds pass) . . . . │
  │ ◄─── New Event (200 OK) ─────── │  (Server returns data immediately)
  │ ─── GET /updates (New Hold) ──► │  (Client immediately reconnects)
```

* **How it works**:
  1. The client opens an HTTP request to the server.
  2. The server receives the request, but instead of returning an empty response, it keeps the request open (typically using Spring's `DeferredResult` or asynchronous servlets to free thread pools).
  3. When an event occurs (e.g. database write event), the server completes the response, returning the payload.
  4. The client receives the payload and immediately issues a new long poll request to establish the next waiting loop.
  5. If no event occurs within a timeout window (e.g., 30 seconds), the server returns a 304 Not Modified status, and the client reconnects.
* **Trade-offs**:
  - **Lower latency** than short polling; events are pushed as soon as they are generated.
  - **State overhead**: The server must track millions of suspended request references.
  - **Connection spikes (Thundering Herd)**: When a popular event occurs, all waiting client connections receive the data at the same time. This forces thousands of clients to reconnect simultaneously, creating huge registration spikes on the server.

---

## 4. Push-Based Real-Time: Server-Sent Events (SSE)

Server-Sent Events (SSE) is a push technology defined as part of the HTML5 standard, enabling servers to stream unidirectional text events over a single HTTP connection.

```
Client                             Server
  │ ─── GET /stream (MIME: text/event-stream) ──► │
  │ ◄─── HTTP 200 OK (Keep-Alive) ─────────────── │
  │ ◄─── event: message \n data: msg1 \n\n ────── │  (Server pushes event)
  │ ◄─── event: message \n data: msg2 \n\n ────── │  (Server pushes event)
```

### The Protocol Mechanics
- **Unidirectional**: Only the server can send events. If the client needs to talk to the server, it must send separate HTTP REST requests.
- **MIME Type**: The connection is opened with `Accept: text/event-stream` header. The server responds with `Content-Type: text/event-stream` and keeping the connection alive.
- **Framing**: Events are sent as plain text blocks separated by double newlines (`\n\n`):
  ```http
  event: trade
  id: 1042
  data: {"symbol":"BTCUSDT","price":67230.50}
  
  ```
- **Browser Client**: Modern browsers support the native `EventSource` API, which automatically handles connection failures and reconnects using the last seen event ID (`Last-Event-ID` header).

### Alternatives & Trade-offs
* **HTTP/2 Support**: Under HTTP/1.1, browsers limit concurrent connections per domain to 6. If you open 6 SSE streams in different tabs, the browser runs out of connection slots, blocking all other site navigation. Under **HTTP/2**, multiple SSE streams are multiplexed over a single TCP connection, bypassing this limitation.
* **Firewall Compatibility**: Since SSE is standard HTTP, it traverses firewalls, load balancers, and corporate proxies without custom configurations, unlike WebSockets.

---

## 5. Full-Duplex Real-Time: WebSockets

WebSockets provide a persistent, bidirectional, full-duplex communication channel over a single TCP socket connection.

```
Client                                      Server
  │ ─── GET /ws (Upgrade: websocket) ─────► │
  │ ◄─── 101 Switching Protocols ────────── │
  │ ◄====================================► │  (Bi-directional TCP socket frames)
  │ ◄─── Data Frame (Server to Client) ─── │
  │ ─── Data Frame (Client to Server) ───► │
```

### 1. The Handshake Protocol (HTTP Upgrade)
The connection begins as a standard HTTP request containing specific upgrade headers:
```http
GET /chat HTTP/1.1
Host: server.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
```
If the server accepts the connection, it returns an HTTP `101 Switching Protocols` status code:
```http
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```
The client key is parsed, combined with a standard UUID (`258EAFA5-E914-47DA-95CA-C5AB0DC85B11`), hashed using SHA-1, and encoded using Base64 to construct the `Sec-WebSocket-Accept` header, protecting the connection against caching proxies. Once this handshake completes, the HTTP protocol parser is swapped for the binary WebSocket framer.

### 2. Protocol Footprint
* **Header Overhead**: Traditional HTTP requests carry kilobytes of headers. WebSocket frames carry only **2 to 10 bytes of frame overhead** per message, saving significant network bandwidth.
* **Duplexing**: Both client and server can transmit data concurrently over the same TCP link without waiting for responses.
* **Statefulness**: Unlike stateless HTTP, the server must keep the TCP connection open, maintaining session objects on the heap. This requires specialized load balancer configurations and connection limits tuning.

---

## 6. The Next Generation: WebTransport Overview

WebTransport is an emerging W3C API that provides low-latency, bidirectional client-server communication using the **HTTP/3** protocol.

### QUIC Protocol Foundation
WebTransport is built on top of **QUIC (Quick UDP Internet Connections)**, which runs over UDP rather than TCP.

```
+------------------------------------+
|            WEBTRANSPORT            |
+------------------------------------+
|               HTTP/3               |
+------------------------------------+
|                QUIC                |
+------------------------------------+
|                UDP                 |
+------------------------------------+
```

### Features of WebTransport:
1. **Unidirectional and Bidirectional Streams**: Clients and servers can open multiple independent streams.
2. **Datagram Support**: Allows sending out-of-order, unreliable messages (similar to UDP packet dispatching), which is ideal for real-time multiplayer gaming or live audio/video tracking where speed is prioritized over reliability.
3. **No Transport-Level Head-of-Line Blocking**: Since QUIC handles packet multiplexing at the transport layer, losing a packet on one stream does not block or slow down execution on other active streams, unlike WebSockets over TCP.

---

## 7. Push vs. Pull Communication Models

The table below summarizes the architectural characteristics of each transport model:

| Feature | Short Polling | Long Polling | Server-Sent Events (SSE) | WebSockets | WebTransport |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Direction** | Client Pull | Client Pull | Server Push (Unidirectional) | Bidirectional (Duplex) | Bidirectional (Duplex) |
| **Underlying Protocol**| HTTP/1.x or HTTP/2 | HTTP/1.x or HTTP/2 | HTTP/1.x or HTTP/2 | TCP (Socket) | HTTP/3 (QUIC / UDP) |
| **Header Footprint** | Large (Every poll) | Large (Every poll) | Small (Stream connection) | Minimal (2–10 bytes) | Minimal |
| **Latency** | High (Pool interval) | Low | Low | Extremely Low (Real-time)| Extremely Low |
| **Server State** | Stateless | Stateful (Holding req) | Stateful (Open stream) | Stateful (Open TCP) | Stateful |
| **Reconnections** | Auto (New poll) | Auto (New poll) | Built-in browser support | Manual implementation | Built-in |
| **Proxy Compatibility**| Native | Native | Native | Requires custom configs| Requires UDP configs |

---

## 8. Latency Requirements and UX Implications

Real-time systems directly impact how users interact with applications. Latency thresholds shape user perception:

- **< 100ms (Immediate)**: Perceived as instantaneous. Essential for high-frequency trading dashboards, gaming, collaborative document typing, or real-time audio signaling.
- **100ms – 300ms (Responsive)**: Perceived as lag-free. Suitable for chat messaging, interactive comments, or stock ticks.
- **300ms – 1s (Lagging)**: The delay is visible to the user. Acceptable for package tracking, live sports scores, or background document compilation.
- **> 1s (Slow)**: Users feel they are waiting. Short polling fits here.

### Mobile Performance & Battery Footprint
For mobile devices, connection frequency directly impacts battery life. Mobile radios transition through state machines:
- **Active State (High Power)**: The LTE/5G radio is fully active, consuming high battery power.
- **Tail State (Idle Waiting)**: After transmitting, the radio stays active for 5 to 15 seconds waiting for packets before going to sleep.
- **Short Polling impact**: Polling every 5 seconds keeps the mobile radio locked in the high-power state, draining the device battery in a few hours. Persistent connections (like WebSockets or multiplexed SSE over HTTP/2) allow the radio to enter low-power sleep states, waking up only when the server pushes a packet.

---

## 9. Spring Boot Code Implementations

Let us write concrete Java implementations for Short Polling, Long Polling, and Server-Sent Events using Spring Boot.

### 1. Short Polling REST API
Below is a REST controller that simulates a cache of database records. The client polls the `/api/short-poll/items` endpoint, providing the timestamp of the last message they received to pull only newer items.

```java
package com.example.realtime.poll;

import org.springframework.web.bind.annotation.*;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/short-poll")
public class ShortPollController {

    public record NewsMessage(String id, String content, Instant timestamp) {}
    
    // Thread-safe message cache
    private final List<NewsMessage> messageStorage = new CopyOnWriteArrayList<>();

    public ShortPollController() {
        // Seed mock data
        messageStorage.add(new NewsMessage("1", "Server initialized", Instant.now()));
    }

    /**
     * Endpoint for adding new events (simulating external ingest)
     */
    @PostMapping("/messages")
    public NewsMessage postMessage(@RequestBody String content) {
        NewsMessage msg = new NewsMessage(
            java.util.UUID.randomUUID().toString(),
            content,
            Instant.now()
        );
        messageStorage.add(msg);
        return msg;
    }

    /**
     * Short polling retrieval endpoint.
     * The client passes 'lastSeenEpoch' to fetch only new records.
     */
    @GetMapping("/messages")
    public List<NewsMessage> fetchUpdates(@RequestParam(required = false) Long lastSeenEpoch) {
        if (lastSeenEpoch == null) {
            return messageStorage;
        }
        Instant threshold = Instant.ofEpochMilli(lastSeenEpoch);
        return messageStorage.stream()
                .filter(msg -> msg.timestamp().isAfter(threshold))
                .collect(Collectors.toList());
    }
}
```

---

### 2. Long Polling API via `DeferredResult`
In standard Spring MVC, blocking a thread waiting for database updates will quickly exhaust the Tomcat thread pool. 

To prevent this, Spring provides `DeferredResult`. When a controller returns `DeferredResult`, the Tomcat container thread is returned to the execution pool immediately. The client's HTTP connection remains open, and the request is completed asynchronously by a custom thread pool when data is ready.

```java
package com.example.realtime.poll;

import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.context.request.async.DeferredResult;
import java.util.Map;
import java.util.Queue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;

@RestController
@RequestMapping("/api/long-poll")
public class LongPollController {

    public record AlertEvent(String id, String severity, String message) {}

    // Map to keep track of active long-polling client requests
    private final Map<String, DeferredResult<AlertEvent>> clientRequests = new ConcurrentHashMap<>();
    
    // Queue of events that have not been picked up yet
    private final Queue<AlertEvent> pendingEvents = new ConcurrentLinkedQueue<>();

    /**
     * Client registers a long poll request.
     * The connection is kept open for up to 20 seconds.
     */
    @GetMapping("/alerts")
    public DeferredResult<AlertEvent> registerClient(@RequestParam String clientId) {
        // Initialize DeferredResult with a 20-second timeout and 304 Not Modified fallback
        DeferredResult<AlertEvent> result = new DeferredResult<>(20_000L);
        
        // Timeout handler
        result.onTimeout(() -> {
            clientRequests.remove(clientId);
            result.setErrorResult(new TimeoutException("No updates available within window."));
        });

        // Completion cleanup handler
        result.onCompletion(() -> clientRequests.remove(clientId));

        // If an event is already pending, return it immediately
        AlertEvent immediateAlert = pendingEvents.poll();
        if (immediateAlert != null) {
            result.setResult(immediateAlert);
            return result;
        }

        // Otherwise, register the request and wait for server event
        clientRequests.put(clientId, result);
        return result;
    }

    /**
     * Publishes a new event to all waiting long poll clients.
     */
    @PostMapping("/alerts")
    public String publishAlert(@RequestBody AlertEvent alert) {
        if (clientRequests.isEmpty()) {
            // No clients are waiting, queue the event for the next connection
            pendingEvents.add(alert);
            return "Alert queued. No active clients connected.";
        }

        // Distribute the event to all waiting client requests
        for (Map.Entry<String, DeferredResult<AlertEvent>> entry : clientRequests.entrySet()) {
            DeferredResult<AlertEvent> clientResult = entry.getValue();
            // Complete the response asynchronously
            clientResult.setResult(alert);
        }
        return "Alert dispatched to " + clientRequests.size() + " active connections.";
    }

    @ResponseStatus(org.springframework.http.HttpStatus.NOT_MODIFIED)
    public static class TimeoutException extends RuntimeException {
        public TimeoutException(String message) {
            super(message);
        }
    }
}
```

---

### 3. Server-Sent Events API using `SseEmitter`
Spring's `SseEmitter` allows you to stream Server-Sent Events over standard HTTP connections. The client registers once, and the server retains the emitter reference to push multiple events downstream.

```java
package com.example.realtime.sse;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@RestController
@RequestMapping("/api/sse")
public class SseController {

    // Registry of active client emitters
    private final Map<String, SseEmitter> emitters = new ConcurrentHashMap<>();

    /**
     * Establish a persistent unidirectional event stream
     */
    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamUpdates(@RequestParam String clientId) {
        // Create an emitter with a 5-minute timeout
        SseEmitter emitter = new SseEmitter(300_000L);

        // Register clean-up callbacks
        emitter.onCompletion(() -> emitters.remove(clientId));
        emitter.onTimeout(() -> {
            emitter.complete();
            emitters.remove(clientId);
        });
        emitter.onError((ex) -> emitters.remove(clientId));

        // Send initial connection handshake event (avoids early timeout on some proxies)
        try {
            emitter.send(SseEmitter.event()
                    .name("INIT")
                    .data("Connection established. Listening..."));
        } catch (IOException e) {
            emitter.completeWithError(e);
            return emitter;
        }

        emitters.put(clientId, emitter);
        return emitter;
    }

    /**
     * Push updates to a specific client
     */
    @PostMapping("/push/{clientId}")
    public String pushEvent(@PathVariable String clientId, @RequestBody String data) {
        SseEmitter emitter = emitters.get(clientId);
        if (emitter == null) {
            return "Client not connected.";
        }

        try {
            emitter.send(SseEmitter.event()
                    .name("UPDATE")
                    .data(data));
            return "Event pushed successfully.";
        } catch (IOException e) {
            emitter.completeWithError(e);
            emitters.remove(clientId);
            return "Push failed. Emitter cleaned up.";
        }
    }
}
```

---

## 10. Hands-On Lab: Comparing Polling vs. WebSockets

In this lab, you will measure the network footprints of Polling vs. WebSockets to understand their performance differences in production.

### Objective:
Verify network overhead, payload bytes, and socket state counts under a simulated load of 100 updates.

### Equipment & Configuration:
* Any network protocol analyzer (such as Chrome DevTools Network Tab or Wireshark).
* A running instance of the Spring Boot REST services (Polling) and a basic WebSocket server.

### Step 1: Record Polling Network Overhead
1. Open Chrome DevTools and navigate to the **Network** tab.
2. Select the **Fetch/XHR** filter.
3. Configure your client to poll the short-polling endpoint (`/api/short-poll/messages`) every 2 seconds.
4. Let the client poll 50 times.
5. **Analyze the Metrics**:
   - Locate the **Size** column. Notice that each short poll request transmits $\approx 1.2$ KB of request headers (cookies, host, user-agent) and receives $\approx 300$ bytes of response headers, even when returning an empty payload (`[]` - 2 bytes).
   - Calculate total bytes transmitted: 
     $$\text{Total Bytes} = 50 \text{ polls} \times (1200 \text{ bytes request} + 300 \text{ bytes response}) \approx 75 \text{ KB}$$
   - Notice the CPU cycles spent spinning up connection handlers in your log output.

### Step 2: Record WebSocket Network Overhead
1. Switch your client connection to a WebSocket URL (e.g. `ws://localhost:8080/ws-endpoint`).
2. Filter the Network tab in DevTools for **WS** (WebSockets).
3. Click on the established connection name and select the **Messages** (or Frames) sub-tab.
4. Let the application receive 50 real-time events pushed by the server.
5. **Analyze the Metrics**:
   - The initial HTTP Handshake executes once, consuming $\approx 1.5$ KB.
   - Look at each subsequent frame pushed by the server. The frame size is exactly the size of the data string plus **only 2 to 4 bytes** of frame overhead.
   - Calculate total bytes transmitted:
     $$\text{Total Bytes} = 1500 \text{ bytes (handshake)} + (50 \text{ frames} \times (100 \text{ bytes payload} + 2 \text{ bytes framing})) \approx 6.6 \text{ KB}$$
   - *Result*: The WebSocket connection consumes **less than 10% of the network bandwidth** of the polling mechanism under the same message frequency.

---

## 11. Mini Project: Build a Notification System Using Polling

We will build a complete, runnable **real-time notification client-server system** using Java. The server provides both Short Polling and Long Polling endpoints to distribute targeted notifications. The client application simulates multiple users connecting to the server using different polling styles.

```
                  +-----------------------------------+
                  |      SPRING BOOT SERVER           |
                  |                                   |
                  |  [Notification Storage]           |
                  |         ▲                         |
                  |         │ (Ingests /api/notify)   |
                  |  +──────┴───────+                 |
                  |  |  Controller  |                 |
                  |  +──┬────────┬──+                 |
                  |     │        │                    |
                  +─────┼────────┼────────────────----+
                        │        │
      HTTP Short Poll   │        │   HTTP Long Poll
      (Every 2 seconds) │        │   (DeferredResult waits)
                        ▼        ▼
                +─────────+    +─────────+
                | ClientA |    | ClientB |
                +─────────+    +─────────+
```

### Server Side: Spring Boot Service Configuration
First, initialize the server application. Ensure your maven `pom.xml` contains the `spring-boot-starter-web` dependency.

```java
package com.example.realtime.notification;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.context.request.async.DeferredResult;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;

@SpringBootApplication
public class NotificationServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(NotificationServerApplication.class, args);
    }

    /**
     * Custom executor for handling long-polling asynchronous tasks
     */
    @Bean
    public ThreadPoolTaskExecutor longPollExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(50);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("LongPollAsync-");
        executor.initialize();
        return executor;
    }
}

// --- Domain Model ---
record Notification(String id, String userId, String message, Instant timestamp) {}

// --- Notification Repository Service ---
@RestController
@RequestMapping("/api/notifications")
class NotificationController {

    // Map storing client notification queues (keyed by userId)
    private final Map<String, Queue<Notification>> userQueues = new ConcurrentHashMap<>();
    
    // Map tracking active deferred results for long-poll users
    private final Map<String, List<DeferredResult<List<Notification>>>> activeRequests = new ConcurrentHashMap<>();

    /**
     * Ingest endpoint: Simulates sending a new notification to a specific user.
     */
    @PostMapping("/send")
    public Notification sendNotification(@RequestParam String userId, @RequestBody String message) {
        Notification notification = new Notification(
            UUID.randomUUID().toString(),
            userId,
            message,
            Instant.now()
        );

        // Add to the user's local queue
        userQueues.computeIfAbsent(userId, k -> new ConcurrentLinkedQueue<>()).add(notification);

        // Trigger long-polling dispatch if a request is waiting
        dispatchToLongPollers(userId);

        return notification;
    }

    /**
     * 1. Short Polling Endpoint.
     * Instantly returns whatever notifications are currently in the user's queue.
     */
    @GetMapping("/short-poll")
    public List<Notification> shortPoll(@RequestParam String userId) {
        Queue<Notification> queue = userQueues.get(userId);
        if (queue == null || queue.isEmpty()) {
            return Collections.emptyList();
        }
        
        List<Notification> list = new ArrayList<>();
        Notification msg;
        while ((msg = queue.poll()) != null) {
            list.add(msg);
        }
        return list;
    }

    /**
     * 2. Long Polling Endpoint.
     * If notifications are in the queue, returns them immediately.
     * Otherwise, holds the connection open until data arrives or the timeout occurs.
     */
    @GetMapping("/long-poll")
    public DeferredResult<List<Notification>> longPoll(@RequestParam String userId) {
        // 10-second timeout. Fallback is an empty list response (200 OK with no payload).
        DeferredResult<List<Notification>> deferredResult = new DeferredResult<>(10_000L, Collections.emptyList());

        Queue<Notification> queue = userQueues.get(userId);
        if (queue != null && !queue.isEmpty()) {
            // Deliver immediately if items exist
            List<Notification> list = new ArrayList<>();
            Notification msg;
            while ((msg = queue.poll()) != null) {
                list.add(msg);
            }
            deferredResult.setResult(list);
            return deferredResult;
        }

        // Register the request to wait for notifications
        activeRequests.computeIfAbsent(userId, k -> new CopyOnWriteArrayList<>()).add(deferredResult);

        // Clean up on timeout or completion
        deferredResult.onCompletion(() -> removeRequest(userId, deferredResult));
        deferredResult.onTimeout(() -> removeRequest(userId, deferredResult));

        return deferredResult;
    }

    private void removeRequest(String userId, DeferredResult<List<Notification>> result) {
        List<DeferredResult<List<Notification>>> list = activeRequests.get(userId);
        if (list != null) {
            list.remove(result);
        }
    }

    private synchronized void dispatchToLongPollers(String userId) {
        List<DeferredResult<List<Notification>>> waiting = activeRequests.get(userId);
        Queue<Notification> queue = userQueues.get(userId);

        if (waiting != null && !waiting.isEmpty() && queue != null && !queue.isEmpty()) {
            // Gather all pending notifications
            List<Notification> notifications = new ArrayList<>();
            Notification msg;
            while ((msg = queue.poll()) != null) {
                notifications.add(msg);
            }

            // Distribute the notifications to all waiting long poll threads
            for (DeferredResult<List<Notification>> result : waiting) {
                result.setResult(notifications);
            }
            waiting.clear();
        }
    }
}
```

---

### Client Side: Multiple Thread Polling Client
This standard Java application runs multiple threads simulating users. Thread A uses Short Polling, and Thread B uses Long Polling.

```java
package com.example.realtime.notification.client;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class NotificationClientSimulator {

    private static final String BASE_URL = "http://localhost:8080/api/notifications";
    private static final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .build();

    public static void main(String[] args) {
        System.out.println("=== Starting Notification Client Simulator ===");
        
        ExecutorService scheduler = Executors.newFixedThreadPool(2);

        // Spawn client A using Short Polling (polling every 2 seconds)
        scheduler.submit(() -> runShortPollClient("user-short-1"));

        // Spawn client B using Long Polling (blocking wait connection)
        scheduler.submit(() -> runLongPollClient("user-long-1"));
    }

    private static void runShortPollClient(String userId) {
        System.out.println("[Short-Poll] Client initialized. Polling every 2s...");
        while (!Thread.currentThread().isInterrupted()) {
            try {
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(BASE_URL + "/short-poll?userId=" + userId))
                        .GET()
                        .build();

                HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
                
                if (response.statusCode() == 200 && response.body().length() > 2) {
                    System.out.println("[Short-Poll] New Notification Received: " + response.body());
                }
                
                // Sleep for 2 seconds
                Thread.sleep(2000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                System.err.println("[Short-Poll] Error querying updates: " + e.getMessage());
            }
        }
    }

    private static void runLongPollClient(String userId) {
        System.out.println("[Long-Poll] Client initialized. Opening persistent hold loop...");
        while (!Thread.currentThread().isInterrupted()) {
            try {
                // Request has a 15-second socket timeout (exceeding server 10-second poll timeout)
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(BASE_URL + "/long-poll?userId=" + userId))
                        .timeout(Duration.ofSeconds(15))
                        .GET()
                        .build();

                HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
                
                if (response.statusCode() == 200) {
                    String body = response.body();
                    // If returning a non-empty array list
                    if (body.length() > 2) {
                        System.out.println("[Long-Poll] Event Pushed by Server: " + body);
                    } else {
                        // Empty response (304 / timeout fallback)
                        System.out.println("[Long-Poll] Timeout window reached. Reconnecting...");
                    }
                }
            } catch (Exception e) {
                System.err.println("[Long-Poll] Error, retrying connection in 1s... Details: " + e.getMessage());
                try {
                    Thread.sleep(1000);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
    }
}
```

---

## 12. Common Mistakes and Debugging Scenarios

When implementing real-time pull patterns, backend engineers frequently run into these pitfalls.

### Scenario A: Thread Pool Starvation in Long Polling
* **The Problem**: A developer implements long polling using standard blocking endpoints without async constructs (e.g., calling `Thread.sleep` or blocking on database queues inside a standard `@GetMapping` endpoint).
* **The Crash**: Under a load of 200 concurrent users, the entire Spring Boot server stops responding. All REST endpoints return connection timeouts.
* **Why it happens**: Tomcat has a default execution pool of 200 platform threads. If 200 clients long-poll the blocking endpoint, all 200 threads are locked. The server is completely starved; it cannot process any other requests, including the REST calls needed to push the updates that would free the blocked threads!
* **The Fix**: Use `DeferredResult` or `Callable` to decouple HTTP connections from execution threads, ensuring Tomcat threads are returned to the pool immediately.

### Scenario B: Memory Leaks in SSE Emitter Registries
* **The Problem**: A developer implements an SSE stream registry using a simple hash map (`Map<String, SseEmitter>`).
* **The Leak**: When users close their browser tabs or experience connection drops, the server continues to allocate heap memory, eventually crashing with an `OutOfMemoryError`.
* **Why it happens**: When a client disconnects, the JVM does not automatically remove the `SseEmitter` from custom maps. The emitter instance remains strongly referenced as a GC root in your registry map, preventing garbage collection of the emitter and its associated payload buffers.
* **The Fix**: Always register clean-up listeners (`onCompletion`, `onTimeout`, `onError`) to remove the emitter from your maps when the connection terminates.

---

## 13. Advanced Production Considerations

Operating real-time services in production requires tuning the infrastructure layer.

### 1. Load Balancer Buffer Management
Many load balancers (such as Nginx or AWS ALBs) buffer downstream responses to optimize throughput.
- **The Issue**: For long-running streams (SSE), the load balancer buffers the server events and only flushes them to the client once the buffer reaches 4KB. This destroys real-time responsiveness; events look blocked.
- **The Fix**: Disable buffering for real-time endpoints. In Nginx, configure the header:
  ```http
  X-Accel-Buffering: no
  ```
  Ensure your proxy configurations set connection timeouts (e.g., `proxy_read_timeout`) to exceed your long-polling timeout window.

### 2. Sizing Task Executors
Ensure your async thread pools are configured based on expected concurrent users and system memory limits.
- **Formula**: For $N$ active long-polling users with a timeout $T$, the maximum thread allocation $M$ of your async executor must satisfy:
  $$M \geq \text{Throughput} \times \text{Processing Time}$$
  If the thread pool is too small, incoming events will saturate the task queue, causing request drops.

---

## 14. Technical Interview Questions

### Question 1: Long Polling vs. Short Polling Resource Footprint
*Describe how Long Polling reduces CPU load on a database compared to Short Polling, and explain the trade-offs on the server.*

**Answer**:
Short polling queries the database at fixed intervals. If you have 10,000 clients polling every 2 seconds, the server executes 5,000 database queries per second, even if no data has changed. This results in high database CPU utilization and disk read overhead.

Long polling checks the database once upon request. If no updates are present, the request is parked. The server only executes a query when an ingest process signals new data (typically using an event-driven pub/sub design). This eliminates redundant polling queries.

However, the trade-off is server memory. Each open long-polling connection holds an HTTP socket and a state object on the heap, requiring proper configuration of maximum file descriptors (`nofile` limits) and keeping Tomcat threads non-blocking via `DeferredResult`.

---

### Question 2: Resolving HTTP/1.1 Connection Limits in SSE
*A developer runs a dashboard that opens 8 concurrent Server-Sent Events (SSE) streams to different service endpoints. They notice that the 7th and 8th widgets fail to load. What is the root cause and how do you resolve it?*

**Answer**:
Under HTTP/1.1, web browsers enforce a strict limit of **6 concurrent TCP connections per domain**. When the user opens 6 persistent SSE connections, they exhaust the browser's connection pool. The 7th and 8th requests are queued indefinitely by the browser.

To resolve this:
1. **Enable HTTP/2** on your server. Under HTTP/2, all 8 SSE streams are multiplexed over a single TCP connection, bypassing the connection limit.
2. If HTTP/2 is not available, consolidate the 8 endpoints into a single aggregate stream endpoint, and push structured events containing channel names (e.g., `{"channel": "widgets-A", "data": ...}`).

---

### Question 3: WebSockets vs. WebTransport over HTTP/3
*What is the primary architectural advantage of WebTransport over WebSockets when handling high-frequency realtime data packets (e.g., game positions or audio updates)?*

**Answer**:
WebSockets are built over TCP, which guarantees in-order delivery of packets. If a TCP packet is lost, the operating system stops processing all subsequent packets on the socket until the lost packet is retransmitted. This is called **Head-of-Line Blocking**, and it introduces latency spikes in high-frequency streams.

WebTransport runs over HTTP/3 (QUIC/UDP). It supports **Datagrams**, which allow sending packets unreliably and out-of-order. If a packet is lost, WebTransport continues processing other packets immediately, avoiding Head-of-Line blocking. This makes it superior for real-time applications where current data is prioritized over historical packets.

---

## Summary
- **Traditional HTTP** is pull-based, half-duplex, and carries significant header overhead, making it unsuitable for high-frequency real-time updates.
- **Short Polling** is simple but wastes server CPU and network bandwidth through constant empty requests.
- **Long Polling** holds connections open until data is ready, reducing database queries and latency but requiring asynchronous processing (`DeferredResult`) to avoid Tomcat thread pool exhaustion.
- **Server-Sent Events (SSE)** provides unidirectional push streaming using standard HTTP, offering native reconnection support but requiring HTTP/2 to scale.
- **WebSockets** provides bi-directional, full-duplex TCP channels with minimal overhead, but requires specialized state management and proxy configurations.
- **WebTransport** utilizes HTTP/3 over QUIC/UDP, eliminating Head-of-Line blocking for high-frequency streams.
