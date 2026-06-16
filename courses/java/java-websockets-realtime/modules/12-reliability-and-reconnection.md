# Module 12: Reliability and Reconnection

Real-time applications must be designed for network instability. In the real world, users pass through cellular dead zones, switch from Wi-Fi to 5G, and close their laptops mid-session. If your system assumes a perfect, uninterrupted connection, it will suffer from message loss, duplicate events, and server resource exhaustion.

This module covers the architecture of real-time reliability. We will explore how to detect stale sessions, implement client-side reconnection loops using exponential backoff with full jitter, evaluate delivery guarantees (At-Most-Once vs. At-Least-Once), and build an idempotent message deduplication filter in Java.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the threat of thundering herd reconnect storms** and how exponential backoff mitigates server overloading.
2. **Implement an exponential backoff algorithm with full jitter** in Java.
3. **Contrast delivery guarantee levels** (At-Most-Once, At-Least-Once, Exactly-Once) in stateful socket architectures.
4. **Deploy the Idempotent Consumer pattern** using cache filters to eliminate duplicate messages.
5. **Simulate network failures** to validate client reconnection loops and message recovery.

---

## 1. The Challenges of Real-Time Network Instability

In a traditional stateless REST request, network drops are easily managed: the client browser catches the connection error and prompts the user to retry. 

In WebSockets, a connection drop halts all incoming and outgoing event streams silently. This introduces two key challenges:

### 1. Detecting Stale Sessions (Half-Open Sockets)
When a client's device drops off the network without sending a TCP `FIN` packet:
- The server kernel keeps the socket in the `ESTABLISHED` state.
- The server application continues to assume the user is online.
- **The Mitigation**: The server must run heartbeat checks. If the client fails to return a pong frame within the configured heartbeat timeout window (e.g. 30 seconds), the server evicts the stale session, closing the socket and updating the presence registry.

### 2. The Reconnection Storm (Thundering Herd)
When a backend server restarts or a corporate firewall drops active connections, thousands of clients are disconnected simultaneously.
- If all clients try to reconnect **instantly and continuously**:
  - The authentication server is overwhelmed by thousands of complex cryptography handshakes per second.
  - The database is saturated by concurrent session-restore queries.
  - The server crashes again, creating a continuous cycle of restarts (Cascading Failure).
- **The Mitigation**: Clients must stagger their reconnection attempts.

---

## 2. Reconnection Strategies & Exponential Backoff

To prevent reconnect storms, clients must implement **Exponential Backoff with Jitter**.

```
Immediate Reconnect Loop (Server Overload)
Drop ──► Reconnect (0s) ──► Reconnect (0s) ──► Reconnect (0s) ──► Server Crash

Exponential Backoff with Jitter (Staggered Load)
Drop ──► Reconnect (1s + Jitter) ──► Reconnect (2s + Jitter) ──► Reconnect (4s + Jitter)
```

### The Backoff Components:
1. **Base Delay**: The initial wait time before the first reconnect attempt (e.g., 1 second).
2. **Max Delay**: The ceiling cap on the wait time (e.g., 60 seconds) so backoff does not grow to hours.
3. **Multiplier**: The factor by which the delay increases after each failed attempt (typically 2).
4. **Jitter (Randomization)**: Introducing a random variance to the delay. This is the most critical component: without jitter, thousands of clients dropped at the same millisecond will continue to reconnect at the exact same intervals, failing to break the synchronization.

### Full Jitter Formula:
According to research, **Full Jitter** provides the best load-spreading characteristics:
$$\text{Delay} = \text{Random}(0, \text{Min}(\text{MaxDelay}, \text{Base} \times 2^{\text{attempt}}))$$

### Java Backoff Implementation:
Below is a utility class showing how to calculate the next reconnect delay thread-safely:

```java
package com.example.realtime.reliability;

import java.util.concurrent.ThreadLocalRandom;

public class ReconnectBackoffCalculator {

    private final long baseDelayMs;
    private final long maxDelayMs;

    public ReconnectBackoffCalculator(long baseDelayMs, long maxDelayMs) {
        this.baseDelayMs = baseDelayMs;
        this.maxDelayMs = maxDelayMs;
    }

    /**
     * Calculates the next reconnect delay in milliseconds using the Full Jitter algorithm.
     * 
     * @param attempt The current reconnect attempt count (0-indexed).
     * @return The delay in milliseconds to wait before the next attempt.
     */
    public long getNextDelay(int attempt) {
        // Prevent integer overflow on high attempt values
        int shift = Math.min(attempt, 30); 
        
        // Calculate exponential backoff limit: base * 2^attempt
        long tempLimit = baseDelayMs * (1L << shift);
        
        // Cap the limit at maxDelayMs
        long capLimit = Math.min(maxDelayMs, tempLimit);
        
        // Apply Full Jitter: select a random value between 0 and the capLimit
        return ThreadLocalRandom.current().nextLong(0, capLimit + 1);
    }

    public static void main(String[] args) {
        ReconnectBackoffCalculator calculator = new ReconnectBackoffCalculator(1000L, 30000L);
        System.out.println("=== Simulating Full Jitter Reconnect Backoff Intervals ===");
        
        for (int attempt = 0; attempt < 8; attempt++) {
            System.out.printf("Attempt %d:%n", attempt);
            // Run multiple trials to see the random distribution (jitter)
            for (int trial = 1; trial <= 3; trial++) {
                System.out.printf("  Trial %d Delay: %d ms%n", trial, calculator.getNextDelay(attempt));
            }
        }
    }
}
```

---

## 3. Delivery Guarantees

When designing real-time pipelines, specify the target **delivery guarantee**:

### 1. At-Most-Once Delivery
- **Mechanics**: Senders transmit the message once over the socket. If the connection drops or a packet is lost, the message is gone.
- **Trade-off**: High performance, zero server-state tracking.
- **Use Cases**: GPS coordinates tracking, live metrics feeds.

### 2. At-Least-Once Delivery
- **Mechanics**:S enders transmit the message and wait for an acknowledgment (ACK frame) from the receiver. If no ACK is received within a timeout window, the sender assumes packet loss and retransmits the message.
- **Trade-off**: Guarantees delivery, but introduces **duplicate messages** if the original message was processed but the ACK packet was lost on the network.
- **Use Cases**: Chat messaging, financial trades, notification systems.

### 3. Exactly-Once Delivery
- **Mechanics**: Guarantees the message is delivered and processed exactly once. This requires coordinating At-Least-Once delivery with **Message Deduplication** at the receiver layer.

---

## 4. Message Deduplication and Idempotency

Under At-Least-Once delivery, the server must handle duplicate messages using the **Idempotent Consumer Pattern**:
- Every client message is assigned a unique, cryptographically secure **Message ID** (or Snowflake ID) before transmission.
- The server maintains a deduplication cache of recently processed Message IDs.
- When a message arrives, the server checks the cache. If the ID is present, the server discards the payload but re-acknowledges receipt to the client, preventing duplicate database writes.

### Java Deduplication Interceptor:
Below is a Spring `ChannelInterceptor` using an in-memory cache to deduplicate incoming STOMP messages:

```java
package com.example.realtime.reliability.interceptor;

import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.stereotype.Component;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class DeduplicationChannelInterceptor implements ChannelInterceptor {

    // Simple thread-safe deduplication cache mapping message IDs to processing timestamps
    // In production, replace this with a size-limited cache (like Caffeine) or Redis
    private final Map<String, Long> processedMessageIds = new ConcurrentHashMap<>();
    private static final long CACHE_TTL_MS = 600_000L; // Keep IDs in memory for 10 minutes

    @Override
    public Message<?> preSend(Message<?> message, MessageChannel channel) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(message);

        // Process only SEND commands
        if (StompCommand.SEND.equals(accessor.getCommand())) {
            // Extract the custom message ID header set by the client
            String messageId = accessor.getFirstNativeHeader("Message-Id");
            System.out.println("[Deduplicator] Processing SEND frame. Message-Id: " + messageId);

            if (messageId != null) {
                // Clean up expired cache items before checking
                cleanExpiredCache();

                // Check if the message has already been processed
                if (processedMessageIds.containsKey(messageId)) {
                    System.err.println("[Deduplicator] Duplicate message detected! Discarding frame: " + messageId);
                    
                    // Throwing an exception stops message routing to controllers
                    throw new DuplicateMessageException("Message already processed: " + messageId);
                }

                // Register the message ID in the cache
                processedMessageIds.put(messageId, System.currentTimeMillis());
            }
        }

        return message;
    }

    private void cleanExpiredCache() {
        long now = System.currentTimeMillis();
        processedMessageIds.entrySet().removeIf(entry -> (now - entry.getValue()) > CACHE_TTL_MS);
    }

    public static class DuplicateMessageException extends RuntimeException {
        public DuplicateMessageException(String message) {
            super(message);
        }
    }
}
```

---

## 5. Hands-On Lab: Simulating Network Failures

In this lab, you will analyze how your client-side reconnect loops behave under simulated network drops.

### Objective:
- Observe socket drop exceptions in Chrome DevTools.
- Verify exponential backoff intervals during server restarts.

### Steps:
1. Open Chrome DevTools and navigate to the **Network** tab.
2. Connect a WebSocket client to your local Spring Boot server.
3. Filter the Network tab by **WS**.
4. In the DevTools Network throttling dropdown, change the setting from **No Throttling** to **Offline**.
5. **Analyze Client Console Logs**:
   - The browser triggers a `close` event.
   - Verify that your client's reconnect loop starts, executing reconnect attempts using increasing delay intervals.
6. Switch the throttling setting back to **No Throttling** and verify the client reconnects successfully.

---

## 6. Common Mistakes & Debugging Scenarios

### Scenario A: Reconnect Storms Crashing the Server
* **The Problem**: After a brief network outage, the Spring Boot server boots up but immediately crashes due to CPU saturation. The logs show thousands of concurrent database connection timeouts.
* **Why it happens**: The client applications implemented a basic reconnect loop with a fixed delay (e.g. `setTimeout(reconnect, 1000)`). When the network recovered, thousands of clients sent reconnect handshakes at the exact same second, overwhelming the server.
* **The Fix**: Implement the **Full Jitter** algorithm in your client-side reconnect scripts, spreading reconnect handshakes over a wider time window.

### Scenario B: Database Mutation Duplication
* **The Problem**: Users report that sending a single message sometimes causes it to appear twice in the chat history.
* **Why it happens**: The application uses At-Least-Once delivery. The client sent a message, and the server stored it in the database. However, the server crashed or the network dropped before the `ACK` frame reached the client. The client retransmitted the message. Because the server lacked a deduplication check, it processed the retransmitted message as a new entry, creating a duplicate record in the database.
* **The Fix**: Enforce unique Message IDs on the client and register a deduplication interceptor on the server.

---

## 7. Technical Interview Questions

### Question 1: Exponential Backoff Jitter
*Why is random jitter critical in an exponential backoff reconnect loop? What happens if you implement backoff without it?*

**Answer**:
Without jitter, the reconnect delay is purely deterministic (e.g., attempt 1 waits 1s, attempt 2 waits 2s, etc.). 

If a network segment drops, thousands of clients disconnect at the same millisecond. If those clients reconnect using a deterministic backoff loop, they will continue to send reconnect requests in synchronized waves (e.g., all reconnecting at 1s, then all reconnecting at 2s). This maintains high peak loads on the server. 

Adding random jitter breaks this synchronization, spreading connection attempts over a wider time window and smoothing the load curve on the server.

---

### Question 2: Idle Session Tracking
*How does a server identify a stale WebSocket connection if the client device drops offline silently without closing the socket?*

**Answer**:
A silent disconnect leaves the server socket in the `ESTABLISHED` state. To detect this:
1. **TCP Keep-Alives**: The OS kernel can send empty TCP keep-alive probes, but default OS timeouts are often too slow (typically 2 hours).
2. **Application-Level Heartbeats (Ping/Pong)**: The server sends periodic WebSocket Ping frames (e.g. every 10 seconds). The client must respond with a Pong frame. If the server does not receive a Pong within a configured timeout window, it marks the connection as stale, terminates the socket, and frees resources.

---

## Summary
- **Network drops** can cause silent connection state discrepancies, requiring heartbeats (Ping/Pong) to detect and evict stale sessions.
- **Immediate Reconnections** risk crashing servers (reconnection storms), requiring **Exponential Backoff with Full Jitter** to stagger connection requests.
- **At-Least-Once Delivery** guarantees message delivery but introduces duplicate messages when acknowledgment frames are lost.
- **Message Deduplication** uses unique Message IDs and cache filters to enforce idempotency at the receiver layer, preventing duplicate database writes.
- **Spring Interceptors** can inspect STOMP `SEND` headers to discard duplicate frames before they reach application controllers.
