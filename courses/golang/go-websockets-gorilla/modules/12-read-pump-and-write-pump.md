# Module 12: Read Pump and Write Pump

In a production Go application, managing network connections requires a robust design that prevents thread starvation and memory leaks. The Gorilla WebSocket library uses the **Read Pump and Write Pump** pattern to handle full-duplex communication safely and efficiently.

This module details the Read Pump and Write Pump pattern. We will explore why this split-goroutine pattern exists, study the lifecycles of `readPump()` and `writePump()`, analyze the coordination mechanics that guarantee clean connection shutdowns without resource leaks, and build a complete implementation of both loops.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the purpose** of separating socket operations into read and write pumps.
2. **Implement the `readPump()` loop** to process incoming frames and handle heartbeats.
3. **Implement the `writePump()` loop** to write outgoing frames and send periodic pings.
4. **Coordinate socket teardowns** to clean up resources cleanly when a connection drops.
5. **Prevent goroutine leaks** by linking the lifecoutines of the pumps.
6. **Implement a complete, production-ready server** featuring both loops.

---

## 1. Why the Split Pump Pattern Exists

A WebSocket connection supports full-duplex communication: the client and server can read and write data concurrently.

However, socket read and write operations are blocking network calls:
- **`ReadMessage()`** blocks the executing thread until a new frame arrives from the client.
- **`WriteMessage()`** blocks if the client is slow and the TCP write buffer is full.

### The Single-Loop Bottleneck
If you attempt to read and write in a single goroutine:
```go
// Anti-Pattern: Single Loop
for {
    msgType, payload, err := conn.ReadMessage()
    // If the server blocks here waiting for incoming client frames,
    // it cannot write outgoing messages to the client!
    conn.WriteMessage(msgType, response)
}
```
If the server blocks waiting for incoming client frames, it cannot write outgoing messages to the client. This breaks asynchronous notifications and event-driven updates.

---

### The Gorilla Solution: Split Pumps
To support concurrent reads and writes, Gorilla splits connection processing into two dedicated goroutines:
1. **The Read Pump (`readPump`)**: A dedicated goroutine that runs an infinite loop calling `ReadMessage()`, consuming incoming data as fast as possible.
2. **The Write Pump (`writePump`)**: A dedicated goroutine that runs an infinite loop selecting on a channel queue and writing outbound data to the socket.

```text
               ┌─────────── Go Web Server ───────────┐
               │                                     │
Incoming Msg ──► Read Pump Goroutine ──► Hub Event   │
               │ (readPump)              Loop        │
               │                                     │
Outgoing Msg  ◄── Write Pump Goroutine ◄─ Pushes to  │
               │ (writePump)             Send Chan   │
               └─────────────────────────────────────┘
```

---

## 2. Deep Dive into `readPump()`

The **`readPump()`** goroutine is responsible for reading incoming data frames and processing connection events.

### Step-by-Step Read Pump Lifecycle:
1. **Set Message Limit**: Configure a maximum payload size limit (`conn.SetReadLimit`) to protect the server from memory exhaustion attacks.
2. **Set Initial Timeout**: Enforce an initial read timeout (`conn.SetReadDeadline`). If no data is received within this window, the socket returns a timeout error.
3. **Register Pong Handler**: Register a callback function (`conn.SetPongHandler`). When the server receives a Pong frame from the client, the callback runs and resets the read deadline, keeping the connection alive.
4. **Read Loop**: Start a blocking loop calling `ReadMessage()`.
5. **Forward Payloads**: Parse incoming payloads and forward them to the Hub.
6. **Cleanup**: If a read error occurs, the loop exits, triggers unregistration, and closes the socket.

---

## 3. Deep Dive into `writePump()`

The **`writePump()`** goroutine is responsible for writing outbound messages and sending periodic heartbeat pings.

### Step-by-Step Write Pump Lifecycle:
1. **Start Ticker**: Start a periodic timer (`time.NewTicker`) to send heartbeats slightly before the client's read deadline expires.
2. **Select Loop**: Run a loop selecting on the `send` channel and the ticker.
3. **Handle Channel Outbound**: When a payload is received from the channel:
   - Set a write deadline.
   - Write the payload to the socket.
4. **Handle Ticker Heartbeat**: When the ticker fires:
   - Set a write deadline.
   - Send a Ping control frame (`websocket.PingMessage`).
5. **Handle Channel Closure**: If the Hub closes the client's `send` channel, the write pump writes a Close control frame and exits.
6. **Cleanup**: On loop exit, the pump stops the ticker and closes the socket.

---

## 4. Shutdown Coordination and Dead Client Cleanup

A key challenge when running split goroutines is coordinating shutdown: if one loop fails, the other must be notified to exit to prevent resource leaks.

Gorilla coordinates this by leveraging channel closures and connection closures:

```text
                  [ Read Failure / Socket Timeout ]
                                 │
                                 ▼
                     readPump exits loop
                                 │
                                 ▼
                     Queues unregister request
                                 │
                                 ▼
                     Hub closes client.send channel
                                 │
                                 ▼
                     writePump detects closed channel
                                 │
                                 ▼
                     writePump writes Close and exits
```

### Case A: The Read Pump Fails First (e.g. Socket Read Timeout)
1. `ReadMessage()` returns an I/O timeout error.
2. The `readPump` loop exits.
3. The deferred block calls `hub.unregister <- client`.
4. The Hub processes the unregistration request and **closes the client's `send` channel**.
5. The `writePump` select block reads from the closed channel:
   `msg, ok := <-client.send` (returns `ok == false`).
6. The `writePump` writes a Close control frame to the client and exits cleanly.
7. Both goroutines exit, freeing memory and file descriptors.

### Case B: The Write Pump Fails First (e.g. Slow Client Timeout)
1. `WriteMessage()` returns an I/O timeout error.
2. The `writePump` loop exits.
3. The deferred block calls `conn.Close()`.
4. The active `ReadMessage()` call in `readPump` immediately unblocks and returns an error.
5. The `readPump` loop detects the error and exits.
6. The deferred block calls `hub.unregister <- client`.
7. The Hub processes the request. Since the channel is already closed, both goroutines exit cleanly.

This dual-loop coordination guarantees that **both goroutines exit cleanly, regardless of which loop encounters the failure first**, preventing resource leaks.

---

## 5. Exercises: Building Pumps from Memory

In this exercise, you will build a complete, compilable Go server implementing the Hub, client structures, and both read/write pumps.

### Complete Go Server Implementation:

```go
package main

import (
	"log"
	"net/http"
	"time"
	"github.com/gorilla/websocket"
)

const (
	writeWait      = 10 * time.Second
	pongWait       = 60 * time.Second
	pingPeriod     = (pongWait * 9) / 10
	maxMessageSize = 512
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

type Hub struct {
	clients    map[*Client]bool
	broadcast  chan []byte
	register   chan *Client
	unregister chan *Client
}

func NewHub() *Hub {
	return &Hub{
		clients:    make(map[*Client]bool),
		broadcast:  make(chan []byte),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.clients[client] = true
		case client := <-h.unregister:
			if _, exists := h.clients[client]; exists {
				delete(h.clients, client)
				close(client.send) // Notify write pump to exit
			}
		case message := <-h.broadcast:
			for client := range h.clients {
				select {
				case client.send <- message:
				default:
					close(client.send)
					delete(h.clients, client)
				}
			}
		}
	}
}

type Client struct {
	hub  *Hub
	conn *websocket.Conn
	send chan []byte
}

// readPump loops reading frames from socket
func (c *Client) readPump() {
	defer func() {
		c.hub.unregister <- c // Notify Hub to clean up client
		c.conn.Close()
	}()

	// 1. Enforce payload limits and deadlines
	c.conn.SetReadLimit(maxMessageSize)
	c.conn.SetReadDeadline(time.Now().Add(pongWait))
	
	// 2. Extend deadline on receiving Pong heartbeats
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	// 3. Start read loop
	for {
		_, message, err := c.conn.ReadMessage()
		if err != nil {
			log.Println("[Read Pump] Read error:", err)
			break
		}
		// Forward message to Hub
		c.hub.broadcast <- message
	}
}

// writePump loops writing outbound frames to socket
func (c *Client) writePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				// Hub closed our channel, send Close frame and exit
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			// Write outbound message
			err := c.conn.WriteMessage(websocket.TextMessage, message)
			if err != nil {
				log.Println("[Write Pump] Write error:", err)
				return
			}

		case <-ticker.C:
			// Send Ping heartbeat
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			err := c.conn.WriteMessage(websocket.PingMessage, nil)
			if err != nil {
				log.Println("[Write Pump] Ping error:", err)
				return
			}
		}
	}
}

func main() {
	hub := NewHub()
	go hub.Run()

	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			log.Println("Upgrade failed:", err)
			return
		}

		client := &Client{
			hub:  hub,
			conn: conn,
			send: make(chan []byte, 256),
		}

		hub.register <- client // Register client

		// Spawn pumps in separate goroutines
		go client.writePump()
		go client.readPump()
	})

	log.Println("[Gateway] Running on :8080...")
	http.ListenAndServe(":8080", nil)
}
```

---

### Line-by-Line Code Walkthrough (Pumps Server):

- **Line 66**: `func (c *Client) readPump() { ... }`
  Defines the read pump method. It runs as a dedicated goroutine and consumes incoming data frames.
- **Line 68**: `c.hub.unregister <- c`
  A deferred call that queues an unregistration request in the Hub when the read loop exits.
- **Line 73-74**: `SetReadLimit`, `SetReadDeadline`
  Configures payload limits and read deadlines.
- **Line 77-80**: `SetPongHandler`
  Registers a callback to reset the read deadline when a Pong frame is received.
- **Line 83**: `for { ... }`
  Runs the blocking read loop.
- **Line 89**: `c.hub.broadcast <- message`
  Forwards incoming payloads to the Hub for broadcasting.
- **Line 95**: `func (c *Client) writePump() { ... }`
  Defines the write pump method. It runs as a dedicated goroutine and writes outbound frames.
- **Line 96**: `ticker := time.NewTicker(pingPeriod)`
  Starts a periodic timer to send Ping frames to the client.
- **Line 104**: `case message, ok := <-c.send`
  Listens for outbound messages from the channel queue. If the channel is closed, it writes a Close frame and exits.
- **Line 118**: `case <-ticker.C`
  Listens for the ticker to send periodic Ping frames.

---

## 6. Common Pitfalls & Troubleshooting

### 1. Forgetting to Stop Tickers
- **The Mistake**: Forgetting to call `ticker.Stop()` when the write pump exits:
  ```go
  // Inside writePump defer block:
  c.conn.Close() // Ticker stop is missing!
  ```
- **The Result**: The ticker keeps running in the background, preventing resource cleanup and leading to memory leaks.
- **The Fix**: Always call `ticker.Stop()` in a deferred block inside the write pump.

### 2. Spawning Pumps sequentially without `go` keyword
- **The Mistake**: Calling read and write pumps sequentially in the main thread:
  ```go
  client.writePump() // Blocks here!
  client.readPump()  // Never reached!
  ```
- **The Fix**: Spawn both pumps in separate, concurrent goroutines:
  ```go
  go client.writePump()
  go client.readPump()
  ```

---

## 7. Technical Interview Questions

### Question 1: Split Pump Pattern
*Why does Gorilla use the Read Pump and Write Pump pattern?*

**Answer**:
WebSocket operations are blocking network calls. 

Splitting connection processing into dedicated read and write goroutines allows full-duplex communication, preventing slow writes from blocking incoming reads and vice-versa.

---

### Question 2: Goroutine Leak Prevention
*Explain how a write timeout in the write pump triggers the shutdown of the read pump.*

**Answer**:
If the write pump encounters a timeout, it calls `conn.Close()`. 

This immediately unblocks the read pump's active `ReadMessage` call, returning an error that prompts the read pump to exit.

---

### Question 3: Pong Handler Deadline Reset
*Why does the pong handler reset the read deadline?*

**Answer**:
Pings and Pongs act as heartbeats. 

Resetting the read deadline on receiving a Pong frame proves the client is still online, keeping the connection active.

---

### Question 4: Ping interval calculation
*Why must the ping interval (`pingPeriod`) be shorter than the pong wait timeout (`pongWait`)?*

**Answer**:
The ping interval must be shorter than the pong wait timeout to account for network latency and prevent false timeouts.

---

### Question 5: Buffered send channel
*Why does the write pump read outbound messages from a buffered channel?*

**Answer**:
A buffered channel serves as a message queue, allowing other goroutines to queue messages without blocking their execution flow.

---

### Question 6: sync.Mutex on writePump?
*Does the write pump require a mutex lock to write frames to the connection?*

**Answer**:
No. Because the write pump is the only goroutine allowed to write to the connection, writes are serialized, satisfying the One-Writer rule without mutex locks.

---

### Question 7: Closing unbuffered channel?
*What happens if you close an unbuffered channel in the Hub?*

**Answer**:
It notifies the receiver immediately, but unbuffered channels can block senders, making buffered channels preferred for registration queues.

---

### Question 8: FormatCloseMessage status
*What close status code is sent when the write pump exits due to channel closure?*

**Answer**:
It sends code `1000 (Normal Closure)` to notify the client of a clean shutdown.

---

### Question 9: Read limit check
*How does `SetReadLimit` protect the server from memory exhaustion?*

**Answer**:
It sets a maximum limit on incoming message size. If a frame exceeds this limit, the connection returns a protocol error and closes, preventing OOM crashes.

---

### Question 10: Ticker Stop importance
*Why is calling `ticker.Stop()` critical during write pump cleanup?*

**Answer**:
It stops the timer, releasing underlying runtime resources and preventing memory leaks.

---

## Summary
- **Read and Write Pumps** run in separate goroutines to support full-duplex communication without blocking.
- **The Read Pump** manages incoming frames, payload limits, and pong deadline resets.
- **The Write Pump** handles outbound messages and sends periodic Ping heartbeats.
- **Coordinated teardown** closes channels and sockets cleanly, preventing goroutine and memory leaks.
- Always call `ticker.Stop()` to release timer resources.
- Spawn both pumps in separate, concurrent goroutines.
