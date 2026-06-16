# Module 11: Designing the Hub

In a stateful real-time application, connections are not isolated. Senders and receivers need to exchange messages instantly. To coordinate these interactions, a real-time server requires a centralized manager to track active connections, broadcast announcements, and route messages between specific users.

This module details how to design an idiomatic Go **`Hub`**. We will explore the Hub pattern architecture, study the single-goroutine event loop pattern to modify shared state without mutex lock contention, design direct routing tables for targeted messaging, evaluate the benefits and trade-offs of this approach, and build a complete Hub implementation from scratch.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the role of the Hub pattern** in centralized session management.
2. **Implement a lock-free single-goroutine event loop** using Go channels and select blocks.
3. **Design a targeted messaging router** to deliver messages to specific users.
4. **Coordinate registration and unregistration** lifecycles to prevent memory leaks.
5. **Evaluate the trade-offs** between single-threaded event loops and lock-based registries.
6. **Implement a production-grade Hub** from scratch and explain its logic.

---

## 1. The Hub Pattern Architecture

When a client connects to a server, it has its own reader and writer goroutines.
- If Client A wants to send a message to Client B, Client A's reader goroutine cannot access Client B's socket directly.
- To route the message, there must be a centralized registry that holds references to all active connections.

### The Lock Contention Problem
A common approach is to store connections in a global map protected by a mutex lock:
```go
type MutexHub struct {
    sync.RWMutex
    clients map[string]*Client
}
```
- **The Problem**: On busy servers with high connection churn and frequent broadcasts, multiple goroutines will attempt to acquire the write lock concurrently to register new users or update client states.
- This creates lock contention, stalling goroutines and degrading server throughput.

---

### The Solution: The Single-Goroutine Event Loop
The idiomatic Go approach eliminates mutex locks by channeling all state modifications to a single dedicated background goroutine:
- Senders push registration, unregistration, and broadcast requests to Go channels.
- A single background loop reads from these channels and modifies the map sequentially.
- Because only one goroutine ever reads or writes to the map, **map access is completely lock-free**, eliminating mutex contention.

```text
Registration Channel ────► [   Hub    ]
Unregistration Channel ──► [ Event    ] ──► Modifies Client Map (Lock-Free)
Broadcast Channel ───────► [ Loop     ] ──► Pushes payloads to client queues
Direct Msg Channel ──────► [ (Select) ] ──► Routes messages to specific clients
```

---

## 2. The Hub Struct & Target Direct Routing

Below is the standard layout of a Go WebSocket `Hub` struct, supporting both broadcasts and targeted direct routing:

```go
package main

type DirectMessage struct {
	TargetUserID string // The recipient's user ID
	Payload      []byte // The message bytes
}

type Hub struct {
	// 1. Lock-free Active Clients Registry
	clients map[string]*Client

	// 2. Inbound Broadcast Channel
	broadcast chan []byte

	// 3. Inbound Targeted Message Channel
	direct chan DirectMessage

	// 4. Registration Request Channel
	register chan *Client

	// 5. Unregistration Request Channel
	unregister chan *Client
}
```

---

### Struct Fields Explained:

#### 1. `clients map[string]*Client`
- **Role**: The centralized registry matching user IDs to client instances.
- **Concurrency**: Modified exclusively inside the single-goroutine event loop, making it lock-free.

#### 2. `broadcast chan []byte`
- **Role**: An inbound channel queue for messages to be broadcast to all connected clients.

#### 3. `direct chan DirectMessage`
- **Role**: An inbound channel queue for targeted, peer-to-peer messages (e.g. routing a chat message to a specific user).

#### 4. `register chan *Client`
- **Role**: Receives registration requests when new clients connect.

#### 5. `unregister chan *Client`
- **Role**: Receives unregistration requests when clients disconnect or time out.

---

## 3. Anatomy of the Hub Event Loop

The lifecycle of the Hub is managed by the **`Run()`** method, which runs as a background goroutine and selects from the registration, unregistration, and message channels:

```go
func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			// 1. Handle Registration: Add client to registry
			h.clients[client.userID] = client

		case client := <-h.unregister:
			// 2. Handle Unregistration: Remove client and close write queue
			if _, exists := h.clients[client.userID]; exists {
				delete(h.clients, client.userID)
				close(client.send) // Close channel to terminate client write loop
			}

		case message := <-h.broadcast:
			// 3. Handle Broadcast: Push payload to all active client queues
			for _, client := range h.clients {
				select {
				case client.send <- message:
				default:
					// If the client's queue is full, drop connection
					close(client.send)
					delete(h.clients, client.userID)
				}
			}

		case msg := <-h.direct:
			// 4. Handle Direct Message: Look up recipient and route message
			if client, exists := h.clients[msg.TargetUserID]; exists {
				select {
				case client.send <- msg.Payload:
				default:
					close(client.send)
					delete(h.clients, client.TargetUserID)
				}
			}
		}
	}
}
```

---

### Processing Stages Explained:

#### 1. Registration
When a new client connects, the HTTP handler calls `h.register <- client`. The loop reads the client pointer from the channel and inserts it into the registry map.

#### 2. Unregistration
When a client disconnects, the loop removes the client from the map and **closes the client's write channel** (`close(client.send)`). This signals the client's write loop goroutine to exit and close the socket.

#### 3. Broadcasting
The loop iterates over all clients and pushes the message to each client's `send` channel.
- **The Non-Blocking Guard**: Pushing to `client.send` uses a `select` with a `default` case. If a client's buffer is full (indicating a slow client), it defaults to the overflow block, dropping the connection and deleting the client from the registry, preventing slow clients from stalling the event loop.

#### 4. Direct Message Routing
Instead of broadcasting to all users, the loop looks up the `TargetUserID` in the map. If the user is online, it queues the message in their `send` channel.

---

## 4. Benefits and Trade-offs

### Benefits:
- **Lock-Free Concurrency**: State modifications are serialized in a single goroutine, eliminating mutex lock contention and improving throughput.
- **Simple State Management**: Since only one goroutine modifies the map, there is no risk of race conditions or data corruption.

### Trade-offs:
- **Single-Thread Bottleneck**: If any case in the `select` block blocks (e.g. waiting to write to an unbuffered channel), the entire event loop stalls, blocking all registration, unregistration, and routing operations.
- **Mitigation**: Always write to buffered channels using non-blocking checks to keep the event loop running smoothly.

---

## 5. Exercises: Implementing a Hub from Scratch

In this exercise, you will implement a complete, compilable Go server featuring a central Hub, a Client struct, and handlers to upgrade connections and process broadcast and direct messages.

### Complete Go Server Implementation:

```go
package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// 1. Define Message payload formats
type ClientMessage struct {
	Action       string `json:"action"` // "broadcast" or "direct"
	TargetUserID string `json:"target"` // Used if action is "direct"
	Content      string `json:"content"`
}

type DirectMessage struct {
	TargetUserID string
	Payload      []byte
}

// 2. Define the Hub
type Hub struct {
	clients    map[string]*Client
	broadcast  chan []byte
	direct     chan DirectMessage
	register   chan *Client
	unregister chan *Client
}

func NewHub() *Hub {
	return &Hub{
		clients:    make(map[string]*Client),
		broadcast:  make(chan []byte),
		direct:     make(chan DirectMessage),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

// 3. Define the Client
type Client struct {
	hub    *Hub
	conn   *websocket.Conn
	send   chan []byte
	userID string
	ctx    context.Context
	cancel context.CancelFunc
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.clients[client.userID] = client
			log.Printf("[Hub] Registered client: %s. Active connections: %d\n", client.userID, len(h.clients))

		case client := <-h.unregister:
			if _, exists := h.clients[client.userID]; exists {
				delete(h.clients, client.userID)
				close(client.send)
				log.Printf("[Hub] Unregistered client: %s. Active connections: %d\n", client.userID, len(h.clients))
			}

		case message := <-h.broadcast:
			log.Printf("[Hub] Broadcasting message to %d clients\n", len(h.clients))
			for _, client := range h.clients {
				select {
				case client.send <- message:
				default:
					close(client.send)
					delete(h.clients, client.userID)
				}
			}

		case msg := <-h.direct:
			log.Printf("[Hub] Routing direct message to: %s\n", msg.TargetUserID)
			if client, exists := h.clients[msg.TargetUserID]; exists {
				select {
				case client.send <- msg.Payload:
				default:
					close(client.send)
					delete(h.clients, msg.TargetUserID)
				}
			} else {
				log.Printf("[Hub] Direct message routing failed: Client %s offline\n", msg.TargetUserID)
			}
		}
	}
}

func (c *Client) readLoop() {
	defer func() {
		c.hub.unregister <- c // Queue unregistration request
		c.cancel()
		c.conn.Close()
	}()

	for {
		_, payload, err := c.conn.ReadMessage()
		if err != nil {
			break
		}

		// Parse the client message payload
		var msg ClientMessage
		err = json.Unmarshal(payload, &msg)
		if err != nil {
			log.Println("[Client Read] Malformed payload:", err)
			continue
		}

		// Route message based on the requested action
		switch msg.Action {
		case "broadcast":
			responseBytes, _ := json.Marshal(map[string]string{
				"from":    c.userID,
				"content": msg.Content,
			})
			c.hub.broadcast <- responseBytes

		case "direct":
			responseBytes, _ := json.Marshal(map[string]string{
				"from":    c.userID,
				"content": msg.Content,
				"private": "true",
			})
			c.hub.direct <- DirectMessage{
				TargetUserID: msg.TargetUserID,
				Payload:      responseBytes,
			}
		}
	}
}

func (c *Client) writeLoop() {
	defer c.conn.Close()

	for {
		select {
		case msg, ok := <-c.send:
			if !ok {
				// The Hub closed our send channel
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			c.conn.WriteMessage(websocket.TextMessage, msg)

		case <-c.ctx.Done():
			return
		}
	}
}

func main() {
	hub := NewHub()
	go hub.Run() // Start the Hub event loop in the background

	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			log.Println("Upgrade failed:", err)
			return
		}

		// Extract client identity (e.g. from query param)
		userID := r.URL.Query().Get("id")
		if userID == "" {
			conn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(4000, "User ID missing"))
			conn.Close()
			return
		}

		ctx, cancel := context.WithCancel(context.Background())
		client := &Client{
			hub:    hub,
			conn:   conn,
			send:   make(chan []byte, 256),
			userID: userID,
			ctx:    ctx,
			cancel: cancel,
		}

		hub.register <- client // Queue registration request

		go client.writeLoop()
		client.readLoop()
	})

	log.Println("[Hub Gateway] Running server on :8080...")
	http.ListenAndServe(":8080", nil)
}
```

---

### Line-by-Line Code Walkthrough (Hub Server):

- **Line 26**: `type Hub struct { ... }`
  Defines the central Hub struct. It manages registration, unregistration, broadcast, and direct messaging channels.
- **Line 53**: `func (h *Hub) Run() { ... }`
  The main Hub method. It runs as a background goroutine and processes connection and messaging requests sequentially.
- **Line 55**: `select { ... }`
  Listens to the Hub's channels. Because Go select blocks are single-threaded, only one channel case is processed at a time, keeping map modifications thread-safe.
- **Line 57**: `h.clients[client.userID] = client`
  Inserts the client into the registry map.
- **Line 60-64**: `delete(h.clients, client.userID); close(client.send)`
  Removes the client from the map and closes their `send` channel to notify their write loop to exit.
- **Line 66-76**: `for _, client := range h.clients`
  Iterates over the client map and pushes the message to each client's queue.
- **Line 70**: `default: close(client.send); delete(...)`
  If a client's queue is full, the select falls back to the default block, dropping the connection and deleting the client from the registry.
- **Line 79-88**: `if client, exists := h.clients[msg.TargetUserID]; exists`
  Performs a direct lookup. If the recipient is online, it queues the message in their `send` channel, bypassing broadcasts.

---

## 6. Common Hub Implementation Mistakes

### 1. Modifying the Client Map Outside the Event Loop
- **The Mistake**: Modifying the `clients` map directly inside your HTTP upgrade handler:
  `hub.clients[userID] = client`
- **The Risk**: Go maps are not thread-safe. Modifying the map from the HTTP handler while the Hub's `Run()` goroutine is reading it will throw concurrent map read/write panics.
- **The Fix**: Always route registration and unregistration requests through the Hub's channels.

### 2. Double Closing client.send Channels
- **The Mistake**: Calling `close(client.send)` in the unregistration block, and again in the client's read loop defer block.
- **The Risk**: Closing an already closed channel in Go triggers a runtime panic.
- **The Fix**: Only close the client's `send` channel inside the Hub's unregistration block, as it is the single coordinator for connection lifecycles.

---

## 7. Technical Interview Questions

### Question 1: Single-Goroutine Event Loop
*Explain the advantage of using a single-goroutine select loop in the Hub instead of a map protected by a global mutex lock.*

**Answer**:
A single-goroutine select loop serializes map modifications. 

Because only one goroutine modifies the map, map access is completely lock-free, eliminating mutex lock contention and improving throughput on busy servers.

---

### Question 2: Channel closing safety
*Why is it dangerous to close the client's write channel (`send`) from the client's read loop instead of the Hub loop?*

**Answer**:
If the channel is closed from the read loop while the Hub is broadcasting, the Hub will attempt to write to a closed channel, triggering a runtime panic. 

The Hub must serve as the single coordinator for closing write channels.

---

### Question 3: Non-Blocking Broadcasts
*Explain how the `select` statement with a `default` case protects the Hub from blocking during broadcasts.*

**Answer**:
If a client is on a slow connection, their `send` channel queue can fill up. 

If the Hub attempted to write to a full channel without a default block, the write would block, stalling the entire event loop. 

Using a `select` statement with a `default` case allows the Hub to skip slow clients or drop their connections, keeping the loop running smoothly.

---

### Question 4: Mutex Map Scalability
*At what scale does a Mutex-locked map registry degrade compared to a single-goroutine event loop?*

**Answer**:
At high scale (e.g. thousands of concurrent users sending high-frequency messages), multiple goroutines will attempt to acquire the lock concurrently to modify or read the map, leading to lock contention and stalling threads.

---

### Question 5: Direct Routing Lookup Cost
*What is the time complexity of direct message routing in our Hub compared to broadcasting?*

**Answer**:
- **Direct Message Routing**: $O(1)$ time complexity, as it performs a direct lookup in the registry map.
- **Broadcasting**: $O(N)$ time complexity, as it must iterate over all active connections.

---

### Question 6: Unbuffered Hub channels?
*What happens if you use unbuffered channels for registration and unregistration in the Hub?*

**Answer**:
If the Hub's event loop is busy processing a broadcast, HTTP upgrade handlers will block when attempting to write to the registration channel, slowing down connection setup. 

Using buffered channels prevents this blockage.

---

### Question 7: GC memory leak registry
*What happens if a disconnected client is not deleted from the Hub's registry map?*

**Answer**:
The Garbage Collector cannot clean up the client connection object, leading to memory leaks and resource exhaustion over time.

---

### Question 8: sync.Map vs. Single Goroutine
*Why not use `sync.Map` to manage the client registry?*

**Answer**:
While `sync.Map` is thread-safe, it is optimized for read-heavy keys that are rarely updated. 

In a WebSocket hub where connections join and leave frequently, a single-goroutine event loop provides better performance.

---

### Question 9: Closing write loops
*How does closing the client `send` channel notify the writer loop to exit?*

**Answer**:
Reading from a closed channel returns the zero value and a boolean flag set to `false`. 

The write loop detects this flag and exits cleanly:
```go
msg, ok := <-c.send
if !ok { return }
```

---

### Question 10: Scaling Horizontally
*What is the primary challenge when scaling this Hub architecture horizontally across multiple server nodes?*

**Answer**:
A single Hub instance only knows about clients connected to its local server. 

To route messages across multiple servers, you must deploy a shared message bus (like Redis Pub/Sub) to synchronize messages between server nodes.

---

## Summary
- **The Hub** acts as the central manager, tracking client registrations and routing messages.
- **The Single-Goroutine Event Loop** serializes state modifications, keeping map access lock-free.
- **Direct message routing** looks up recipients by user ID, enabling targeted peer-to-peer delivery.
- **Protect the event loop** from blocking by writing to client channels using non-blocking select blocks.
- **Clean up client resources** during unregistration to prevent memory leaks.
- Always route registration and unregistration requests through the Hub's channels.
