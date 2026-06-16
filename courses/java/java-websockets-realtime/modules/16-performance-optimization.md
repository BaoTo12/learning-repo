# Module 16: Performance Optimization

Deploying a WebSocket application is only the first step. Scaling it to handle high-frequency messages under tight latency SLA budgets requires tuning the runtime. Because real-time connections are stateful and persistent, performance optimization differs significantly from stateless web services.

This module covers performance optimization for WebSockets. We will contrast throughput and latency, size JVM memory heap allocations, tune garbage collectors (ZGC) for sub-millisecond pauses, mitigate backpressure, analyze serialization overhead, and implement a custom multi-threaded WebSocket load-testing harness in Java.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Analyze the trade-offs** between message throughput and connection latency.
2. **Configure the Z Garbage Collector (ZGC)** to prevent Stop-The-World (STW) pauses from dropping active socket links.
3. **Configure thread pool sizes** for Non-blocking I/O (NIO) selectors and task executors.
4. **Implement backpressure strategies** to prevent slow clients from exhausting server output buffers.
5. **Evaluate serialization formats** (JSON vs. Protocol Buffers) to reduce CPU and network overhead.
6. **Benchmark WebSocket servers** using a custom Java load-testing simulator.

---

## 1. Throughput vs. Latency in Real-Time Systems

Performance optimization requires balancing two metrics:

- **Throughput**: The volume of messages processed by the server per second.
- **Latency**: The time taken for an individual message to travel from the sender client, through the server, and arrive at the recipient client (Round-Trip Time - RTT).

Optimizing for maximum throughput often degrades latency:
- To maximize throughput, the network stack buffers bytes, sending them in large batches to reduce system call overhead.
- This buffering increases latency because messages are delayed in the queue waiting for the buffer to fill.
- For real-time applications (such as financial trading or collaborative editors), **latency is the primary SLA metric**. The server must be tuned to disable buffering (`TCP_NODELAY` enabled on sockets) to flush packets instantly, sacrificing minor bandwidth efficiency for millisecond-level delivery speeds.

---

## 2. JVM Memory & Garbage Collection (GC) Considerations

Under high load, a WebSocket server continuously allocates short-lived objects (message envelopes, JSON strings, frame buffers). This triggers frequent garbage collection cycles.

### 1. The Threat of Stop-The-World (STW) Pauses
Traditional collectors (like Parallel GC or default G1GC configurations) occasionally halt all application execution threads to clean memory (STW pause).
- If a server has 50,000 active connections and undergoes a **300ms STW pause**:
  - The server stops reading from sockets.
  - Heartbeat checks fail, causing clients to drop connections.
  - When the GC pause ends, the server is hit by a thundering herd reconnection storm, causing a cascade failure.

### 2. Tuning for Low Latency: ZGC
To prevent STW pauses from disrupting real-time connections, use the **Z Garbage Collector (ZGC)**.
- **How it works**: ZGC performs all major garbage collection phases (marking, relocation, remapping) concurrently with application threads. It guarantees **sub-millisecond pause times** regardless of heap size, making it ideal for real-time systems.
- **Configuration**: Enable ZGC in your Java startup options:
  ```bash
  java -XX:+UseZGC -XX:+ZGenerational -Xms16g -Xmx16g -jar myapp.jar
  ```
  *(Here, `-XX:+ZGenerational` enables generational ZGC, which is highly optimized for short-lived chat payload allocations).*

---

## 3. Thread Utilization & NIO Multiplexing

Avoid blocking threads inside WebSocket event loops.

- **NIO Model**: Web servers (like Netty or Tomcat) use a small number of **Selector Threads** to monitor thousands of socket channels.
- **The Golden Rule**: **Never execute blocking database or network calls inside the selector threads**. If a selector thread blocks on a slow SQL query, it stops reading frames from all other sockets multiplexed on that thread, causing massive latency spikes.
- **Handoff**: Always hand off blocking business logic to a separate task executor thread pool, keeping selector threads free to process socket I/O.

```
Socket Byte Stream ──► [ Selector Thread ] ──► (Handoff) ──► [ Executor Pool ] ──► Database (Blocking)
                                                             (Slow queries do not block selectors)
```

---

## 4. Backpressure and Buffer Management

If the server pushes high-frequency messages (e.g. 100 messages per second) to a client on a slow or limited connection (e.g. mobile 3G):
- The client cannot read the bytes as fast as the server writes them.
- The server's TCP write buffer fills up.
- Spring Boot starts queueing messages in JVM memory.
- Without **Backpressure**, the server's output queue grows indefinitely, eventually exhausting JVM memory.

### Backpressure Mitigations:
1. **Queue Limits**: Set a strict limit on the session outbound queue (e.g., maximum 1,000 pending messages). If a client hits this limit, drop lower-priority messages or close the connection with Close Status `1008 (Policy Violation)`.
2. **TCP Window Throttling**: Stop reading frames from the client socket if the server's output buffer to that client is full, forcing the client's TCP sliding window to close.

---

## 5. Serialization & Protocol Overhead

Text-based formats (like JSON) are easy to debug but expensive to process at scale:
- Parsing JSON strings allocates many short-lived objects, increasing garbage collection overhead.
- JSON payloads are verbose, consuming excessive network bandwidth.

For high-throughput clusters, replace JSON with compact binary serialization formats like **Protocol Buffers (Protobuf)** or **MessagePack**:

```text
JSON Format (Verbose text):
{"sender":"user-1","content":"Hello","timestamp":1781628104}  --> 60 bytes

Protobuf Format (Compact binary):
[0x0A, 0x06, 0x75, 0x73, 0x65, 0x72, 0x2D, 0x31, 0x12, 0x05, 0x48, 0x65, 0x6C, 0x6C, 0x6F]  --> 15 bytes
```

By reducing payload size by 75% and eliminating text parsing, binary serialization reduces both CPU overhead and network bandwidth consumption.

---

## 6. Compression & Resource Cleanup

Enabling **Per-Message Deflate (RFC 7692)** reduces network bandwidth usage, but introduces CPU and memory trade-offs:
- Each compressed session requires allocating active `Deflater` and `Inflater` objects, which retain native memory buffers.
- For thousands of active connections, this native memory overhead can exhaust server RAM.
- **The Optimization Strategy**: Enable compression only for payloads larger than 1024 bytes. Compressing tiny JSON payloads (e.g., 50 bytes) consumes CPU cycles without providing meaningful bandwidth savings.

---

## 7. Hands-On Lab: Benchmarking WebSocket Applications

In this lab, you will write a custom load-testing client in Java to benchmark your WebSocket server. The script will establish 1,000 concurrent connections, send messages periodically, measure the round-trip delivery latency, and print a performance summary.

### Code Implementation (`WebSocketLoadTester.java`):

```java
package com.example.realtime.performance.benchmark;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;

public class WebSocketLoadTester {

    private static final String SERVER_URI = "ws://127.0.0.1:8080/ws/chat"; // Target endpoint
    private static final int CONCURRENT_CONNECTIONS = 500;                  // Target load
    private static final int TEST_DURATION_SECONDS = 10;
    
    private static final AtomicLong messagesSent = new AtomicLong(0);
    private static final AtomicLong messagesReceived = new AtomicLong(0);
    private static final AtomicLong totalLatencyMs = new AtomicLong(0);
    private static final AtomicLong errorCounts = new AtomicLong(0);

    public static void main(String[] args) throws Exception {
        System.out.println("=== Starting WebSocket Load Testing Harness ===");
        System.out.println("Target URI  : " + SERVER_URI);
        System.out.println("Load Size   : " + CONCURRENT_CONNECTIONS + " concurrent connections");
        
        HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();

        ExecutorService messageExecutor = Executors.newFixedThreadPool(10);
        List<WebSocket> activeSockets = new ArrayList<>();
        
        Instant startConnect = Instant.now();
        System.out.println("Establishing connections...");

        // 1. Establish concurrent connections
        for (int i = 0; i < CONCURRENT_CONNECTIONS; i++) {
            CompletableFuture<WebSocket> wsFuture = client.newWebSocketBuilder()
                    .buildAsync(URI.create(SERVER_URI), new TestWebSocketListener());
            try {
                WebSocket ws = wsFuture.get(2, TimeUnit.SECONDS);
                activeSockets.add(ws);
            } catch (Exception e) {
                errorCounts.incrementAndGet();
            }
        }

        long connectDuration = Duration.between(startConnect, Instant.now()).toMillis();
        System.out.printf("Connections established: %d/%d (Time taken: %d ms)%n", 
                activeSockets.size(), CONCURRENT_CONNECTIONS, connectDuration);

        if (activeSockets.isEmpty()) {
            System.err.println("Failed to establish any connections. Aborting test.");
            return;
        }

        // 2. Start periodic message transmission loop
        ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor();
        scheduler.scheduleAtFixedRate(() -> {
            for (WebSocket ws : activeSockets) {
                messageExecutor.submit(() -> {
                    try {
                        long sentTime = System.currentTimeMillis();
                        String payload = "PING_TIME:" + sentTime;
                        ws.sendText(payload, true);
                        messagesSent.incrementAndGet();
                    } catch (Exception e) {
                        errorCounts.incrementAndGet();
                    }
                });
            }
        }, 1, 1, TimeUnit.SECONDS);

        // 3. Wait for test duration to complete
        Thread.sleep(TEST_DURATION_SECONDS * 1000L);
        
        // Cleanup resources
        scheduler.shutdownNow();
        messageExecutor.shutdownNow();
        
        System.out.println("Terminating connections...");
        for (WebSocket ws : activeSockets) {
            ws.sendClose(WebSocket.NORMAL_CLOSURE, "Test complete");
        }

        // 4. Print Benchmarking Report
        long totalSent = messagesSent.get();
        long totalReceived = messagesReceived.get();
        long totalErr = errorCounts.get();
        double avgLatency = (totalReceived > 0) ? (double) totalLatencyMs.get() / totalReceived : 0;

        System.out.println("\n=== Final Benchmarking Report ===");
        System.out.println("Total Messages Sent    : " + totalSent);
        System.out.println("Total Messages Received: " + totalReceived);
        System.out.println("Failed Operations      : " + totalErr);
        System.out.printf("Average Latency (RTT)  : %.2f ms%n", avgLatency);
        System.out.println("===============================");
    }

    /**
     * Listener class to measure message round-trip latency
     */
    private static class TestWebSocketListener implements WebSocket.Listener {

        @Override
        public CompletionStage<?> onText(WebSocket webSocket, CharSequence data, boolean last) {
            long receivedTime = System.currentTimeMillis();
            messagesReceived.incrementAndGet();

            String payload = data.toString();
            if (payload.startsWith("ECHO: PING_TIME:")) {
                try {
                    long sentTime = Long.parseLong(payload.substring(16));
                    long latency = receivedTime - sentTime;
                    totalLatencyMs.addAndGet(latency);
                } catch (NumberFormatException e) {
                    // ignore
                }
            }
            
            // Re-register listener for next incoming frame
            webSocket.request(1);
            return null;
        }

        @Override
        public void onError(WebSocket webSocket, Throwable error) {
            errorCounts.incrementAndGet();
        }
    }
}
```

---

## 8. Common Mistakes & Debugging Scenarios

### Scenario A: JVM GC Pauses Causing Connection Drops
* **The Problem**: During load spikes, the WebSocket server drops thousands of connections. The client logs report `Connection timed out`. The server CPU is normal, but GC logs reveal Stop-The-World (STW) pauses exceeding 500ms.
* **Why it happens**: The application uses the default G1GC garbage collector. Under heavy message throughput, high object allocation rates trigger long STW pause phases. The server halts thread processing, causing keep-alive heartbeats to time out.
* **The Fix**: Enable **Generational ZGC** (`-XX:+UseZGC -XX:+ZGenerational`) to execute garbage collection concurrently with application execution threads, guaranteeing sub-millisecond pauses.

### Scenario B: Blocking Event Loop Threads
* **The Problem**: Latency spikes across all connections when a database lock occurs, even though the database is running on a separate server.
* **Why it happens**: The developer executed a blocking JpaRepository call directly inside the handler method `handleTextMessage`. Because this method executes on the container's event loop (selector) thread, the thread blocks, halting frame processing for all other connections multiplexed on that selector.
* **The Fix**: Handoff the JpaRepository task to a separate thread pool using a Java `ExecutorService`, keeping the selector thread free.

---

## 9. Technical Interview Questions

### Question 1: Latency vs. Throughput Tuning
*How do you configure socket parameters to optimize for low latency instead of high throughput in a real-time system?*

**Answer**:
To optimize for low latency:
1. **Disable Nagle's Algorithm**: Set the `TCP_NODELAY` option to `true` on the socket. This ensures that the kernel flushes bytes to the network instantly, rather than buffering data to build larger segments.
2. **Minimize Buffer Sizes**: Settle smaller read/write socket buffers to reduce queue latency.
3. **Use Non-Blocking I/O (NIO)**: Multiplex connections using event-driven selectors to keep thread context-switching overhead minimal.
4. **Use ZGC**: Run the JVM with ZGC to keep garbage collection pause times sub-millisecond.

---

### Question 2: WebSocket Backpressure
*What is backpressure in a WebSocket context? What is the risk of not implementing it on a real-time server?*

**Answer**:
**Backpressure** is the mechanism used to throttle the sender when the receiver is overwhelmed. 

If a server publishes messages faster than a slow client can read them, the server's TCP write buffer fills up. Without backpressure, the server queues pending frames in memory. If the connection remains slow, the server queue grows indefinitely, eventually causing the JVM to crash with an `OutOfMemoryError`. 

Implementing backpressure (e.g. setting queue limits or closing slow sessions) protects server memory.

---

## Summary
- **Latency Optimization** requires enabling `TCP_NODELAY` to disable Nagle's algorithm, prioritizing instant delivery over packet packing efficiency.
- **ZGC (Z Garbage Collector)** guarantees sub-millisecond STW pause times, preventing garbage collection sweeps from dropping client heartbeats.
- **Non-Blocking I/O (NIO)** multiplexes thousands of sockets on a small thread pool, but requires keeping selector threads free from blocking database calls.
- **Backpressure** prevents memory exhaustion by limiting or dropping pending messages when routing to slow clients.
- **Binary Serialization** (Protobuf) reduces CPU serialization overhead and network bandwidth consumption compared to JSON.
