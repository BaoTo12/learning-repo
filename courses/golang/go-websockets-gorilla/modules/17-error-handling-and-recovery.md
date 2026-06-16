# Module 17: Error Handling and Recovery

Stateful applications must be designed to handle connection failures gracefully. Because WebSockets run over long-lived TCP connections, they are subject to frequent drops due to network noise, server restarts, client sleep states, and mobile coverage losses. If your application lacks robust error handling and recovery strategies, connection drops will lead to resource leaks and degraded user experiences.

This module details how to implement error handling and recovery for WebSockets. We will explore WebSocket close codes, handle unexpected close errors, design graceful shutdown protocols, implement client-side reconnect strategies using exponential backoff with randomized jitter to prevent thundering herd storms, and build a reconnect client wrapper.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Analyze standard RFC 6455 close codes** and handle close events correctly.
2. **Intercept unexpected close errors** in Go using the `websocket.IsUnexpectedCloseError` helper.
3. **Design a graceful shutdown protocol** to notify clients before shutting down the server.
4. **Implement an exponential backoff with randomized jitter** reconnect algorithm.
5. **Build a robust, reconnecting JavaScript client wrapper** featuring an offline message queue.

---

## 1. WebSocket Close Codes and Error Handling

When a connection is terminated, the closing party sends a Close control frame (`0x8`) containing a 2-byte unsigned integer representing the close status code.

### Standard RFC 6455 Close Codes:

| Code | Name | Description |
| :--- | :--- | :--- |
| **`1000`** | Normal Closure | The connection successfully completed its purpose. |
| **`1001`** | Going Away | The server is shutting down or the client navigated away from the page. |
| **`1002`** | Protocol Error | An endpoint terminated the connection due to a protocol violation. |
| **`1006`** | Abnormal Closure | The connection dropped without sending a Close frame (e.g. TCP timeout or RST). |
| **`1008`** | Policy Violation | An endpoint terminated the connection due to a policy violation (e.g. authentication failure). |
| **`1009`** | Message Too Big | The endpoint received a frame exceeding its configured payload size limit. |
| **`1011`** | Internal Server Error | The server encountered an unexpected error preventing it from fulfilling the request. |

---

### Intercepting Close Errors in Go
In Gorilla, read operations return an error when a connection closes. 

You must distinguish between normal closures (where the client disconnected cleanly) and unexpected closures (which indicate network or application errors). Intercept these using the `websocket.IsUnexpectedCloseError` helper:

```go
_, _, err := conn.ReadMessage()
if err != nil {
	// Filter out normal close codes (1000 and 1001).
	// Any other close code is classified as an unexpected closure.
	if websocket.IsUnexpectedCloseError(err, websocket.CloseNormalClosure, websocket.CloseGoingAway) {
		log.Printf("[Error] Unexpected connection closure: %v\n", err)
	} else {
		log.Println("[Clean Disconnection] Client disconnected cleanly.")
	}
	return
}
```

---

## 2. Graceful Shutdown Protocols

When restarting a server instance for deployment, terminating active sockets abruptly causes a connection storm as clients attempt to reconnect simultaneously, potentially crashing the new server instance.

A **graceful shutdown protocol** mitigates this:
1. Listen for system termination signals (SIGINT, SIGTERM).
2. Stop accepting new connections.
3. Iterate over active clients and send a Close frame with code **`1001 (Going Away)`**.
4. Give clients a brief window (e.g., 5 seconds) to negotiate the close handshake.
5. Terminate remaining connections and shut down the server.

```go
// Graceful close execution loop:
func (h *Hub) GracefulShutdown() {
	h.clientsMu.Lock()
	defer h.clientsMu.Unlock()

	closeMessage := websocket.FormatCloseMessage(websocket.CloseGoingAway, "Server is undergoing maintenance")

	for _, client := range h.clients {
		// Send Close frame to client
		client.conn.WriteControl(
			websocket.CloseMessage,
			closeMessage,
			time.Now().Add(1*time.Second),
		)
	}
}
```

This notifies clients of the shutdown, allowing them to reconnect to another server instance cleanly.

---

## 3. Client-Side Reconnect Strategies

If a connection is lost, the client must attempt to reconnect. However, a naive retry loop can create a thundering herd problem.

### The Thundering Herd Problem
- If a server with 20,000 active connections restarts, all 20,000 clients lose their connection simultaneously.
- If all clients retry to reconnect immediately, the new server instance is hit with a storm of 20,000 connection requests, potentially crashing the server.

---

### The Solution: Exponential Backoff with Jitter
To prevent thundering herd storms, client reconnection attempts must implement two mechanisms:
1. **Exponential Backoff**: Increase the delay between reconnection attempts exponentially (e.g. 1s, 2s, 4s, 8s, up to a maximum limit).
2. **Randomized Jitter**: Add random variance to the delay to distribute connection requests over time, smoothing the load spike on the server.

```text
Reconnect Delay = Min( MaxDelay, Base * 2^Attempt )
Jitter Delay    = Reconnect Delay * ( 0.5 + Random(0, 0.5) )
```

---

## 4. Exercises: Implementing Reconnect Logic in JavaScript

In this exercise, you will build a robust JavaScript client wrapper (`ReconnectingWebSocket`) that implements exponential backoff with randomized jitter and manages an offline message queue to store outbound messages while disconnected.

### Complete JavaScript Implementation:

```javascript
class ReconnectingWebSocket {
    constructor(url, protocols = []) {
        this.url = url;
        this.protocols = protocols;
        this.socket = null;
        
        // Reconnection Configuration
        this.baseDelay = 1000;       // Base delay of 1 second
        this.maxDelay = 16000;       // Maximum delay of 16 seconds
        this.attempt = 0;            // Reconnection attempt counter
        this.offlineQueue = [];      // Stores messages sent while offline
        
        // Event Listeners
        this.listeners = {
            open: [],
            message: [],
            error: [],
            close: []
        };
        
        this.connect();
    }
    
    // 1. Establish connection
    connect() {
        console.log(`[WS Client] Connecting to ${this.url} (Attempt ${this.attempt + 1})...`);
        this.socket = new WebSocket(this.url, this.protocols);
        
        this.socket.onopen = (event) => {
            console.log("[WS Client] Connection established.");
            this.attempt = 0; // Reset reconnection attempts
            this.flushOfflineQueue();
            this.trigger("open", event);
        };
        
        this.socket.onmessage = (event) => {
            this.trigger("message", event);
        };
        
        this.socket.onerror = (error) => {
            console.error("[WS Client] Socket error encountered.");
            this.trigger("error", error);
        };
        
        this.socket.onclose = (event) => {
            console.warn(`[WS Client] Connection lost. Code: ${event.code}`);
            this.trigger("close", event);
            this.scheduleReconnect();
        };
    }
    
    // 2. Reconnection Scheduler implementing Exponential Backoff with Jitter
    scheduleReconnect() {
        // Calculate backoff: limit maximum delay
        const backoff = Math.min(this.maxDelay, this.baseDelay * Math.pow(2, this.attempt));
        
        // Add randomized jitter (random variance between 50% and 100% of backoff)
        const jitter = backoff * (0.5 + Math.random() * 0.5);
        
        console.log(`[WS Client] Scheduling reconnection in ${Math.round(jitter)}ms.`);
        
        setTimeout(() => {
            this.attempt++;
            this.connect();
        }, jitter);
    }
    
    // 3. Send payload with offline queue support
    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(data);
        } else {
            console.warn("[WS Client] Connection offline. Queueing payload.");
            this.offlineQueue.push(data);
        }
    }
    
    flushOfflineQueue() {
        console.log(`[WS Client] Flushing ${this.offlineQueue.length} queued messages.`);
        while (this.offlineQueue.length > 0 && this.socket.readyState === WebSocket.OPEN) {
            const data = this.offlineQueue.shift();
            this.socket.send(data);
        }
    }
    
    // Event management helpers
    addEventListener(event, callback) {
        if (this.listeners[event]) {
            this.listeners[event].push(callback);
        }
    }
    
    trigger(event, payload) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(cb => cb(payload));
        }
    }
    
    close() {
        if (this.socket) {
            this.socket.onclose = null; // Remove listener to prevent auto-reconnect
            this.socket.close();
            console.log("[WS Client] Graceful shutdown initiated.");
        }
    }
}
```

---

### Line-by-Line Code Walkthrough:

- **Line 21**: `this.socket.onopen = (event) => { ... }`
  Resets the reconnection attempts counter and flushes the offline message queue when a connection is successfully established.
- **Line 37**: `this.socket.onclose = (event) => { ... }`
  Triggers a reconnection attempt when the connection is lost.
- **Line 45**: `const backoff = Math.min(this.maxDelay, this.baseDelay * Math.pow(2, this.attempt))`
  Calculates the exponential backoff delay, capping the maximum delay at 16 seconds.
- **Line 48**: `const jitter = backoff * (0.5 + Math.random() * 0.5)`
  Adds randomized jitter (random variance between 50% and 100% of backoff) to distribute reconnection attempts and prevent connection storms.
- **Line 60**: `send(data)`
  Checks the socket state. If online, the payload is sent. If offline, the payload is appended to the `offlineQueue` to be sent when the connection is re-established.

---

## 5. Technical Interview Questions

### Question 1: CloseError vs UnexpectedCloseError
*What is the difference between `websocket.CloseError` and `websocket.UnexpectedCloseError` in Gorilla?*

**Answer**:
- `CloseError` is a struct wrapping standard close codes returned by the socket read loop.
- `UnexpectedCloseError` is a classification helper used to identify close codes that indicate abnormal termination (such as code `1006`), allowing you to filter out normal close codes (like `1000` and `1001`).

---

### Question 2: Close code 1006
*What does close code 1006 mean? Can a client send code 1006 over the wire?*

**Answer**:
Close code `1006` indicates an **Abnormal Closure**, where the connection dropped without sending a Close frame (e.g. due to TCP resets, network drops, or crashes). 

Clients cannot transmit code `1006` over the wire; it is generated locally by the client or server network stack to indicate an abnormal disconnection.

---

### Question 3: Thundering Herd Mitigation
*What is the thundering herd problem, and how does adding randomized jitter mitigate it?*

**Answer**:
The thundering herd problem occurs when a server restarts, causing thousands of disconnected clients to attempt to reconnect simultaneously, overloading the server. 

Adding randomized jitter distributes the reconnection attempts over time, smoothing the load spike on the server.

---

### Question 4: Normal close codes
*Why should close codes 1000 and 1001 be excluded from error logging?*

**Answer**:
- Code `1000` indicates a normal clean disconnection.
- Code `1001` indicates the client is going away (e.g., closing a tab or browser).
These are expected user actions and should not be logged as system errors.

---

### Question 5: Graceful Close Handshake
*Explain the network steps of a graceful WebSocket close handshake.*

**Answer**:
1. One party sends a Close control frame.
2. The recipient stops sending data, echoes the Close frame back, and closes the TCP socket.

---

### Question 6: writePump on normal close
*How does the read pump notify the write pump to exit during a clean shutdown?*

**Answer**:
The read pump forwards the unregistration request to the Hub, which closes the client's `send` channel. 

The write pump detects the closed channel and exits cleanly.

---

### Question 7: Offline queue overflow
*What is the primary risk of using an unbounded offline message queue?*

**Answer**:
An unbounded queue can consume massive browser RAM if the connection remains offline for a long period, potentially crashing the client browser tab. 

To prevent this, cap the queue size (e.g., maximum 100 messages) and drop old messages when the limit is exceeded.

---

### Question 8: 1011 Close Code
*When does the server return close code 1011?*

**Answer**:
Close code `1011` indicates an **Internal Server Error**, and is returned when the server encounters an unexpected condition that prevents it from fulfilling the request.

---

### Question 9: Gorilla default close handler
*What does the default close handler do in Gorilla WebSocket?*

**Answer**:
It automatically writes a Close control frame back to the client and exits, facilitating the clean closing handshake.

---

### Question 10: Ticker Stop importance
*Why must you call `ticker.Stop()` during pump teardown?*

**Answer**:
It stops the timer, releasing underlying runtime resources and preventing memory leaks.

---

## Summary
- **Close Codes** (RFC 6455) indicate the reason for connection termination, allowing you to debug disconnections.
- **IsUnexpectedCloseError** helps filter out normal clean disconnections from network errors.
- **Graceful Shutdowns** notify clients of server maintenance, allowing them to reconnect to another node cleanly.
- **Prevent Thundering Herd storms** by implementing client-side exponential backoff with randomized jitter.
- **Implement offline message queues** to store outbound messages while disconnected.
- Cap the offline queue size to prevent browser memory exhaustion.
