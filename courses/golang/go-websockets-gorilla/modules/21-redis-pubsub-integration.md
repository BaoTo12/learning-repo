# Module 21: Redis Pub/Sub Integration

To build a production-grade real-time system that can scale horizontally to support millions of concurrent users, you must connect your independent server nodes using a distributed message broker. Redis Pub/Sub is a high-performance message distribution engine designed for this use case.

This module details how to integrate Redis Pub/Sub with your Go WebSocket server. We will explore the architecture of a distributed chat server, trace the flow of messages between instances, analyze operational failure scenarios (like network splits and slow consumers), and build a complete distributed multi-room chat server from scratch.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the architecture** of a distributed WebSocket cluster.
2. **Implement a Redis Pub/Sub bridge** to synchronize message states between servers.
3. **Trace the lifecycle of messages** routed across multiple server instances.
4. **Mitigate broker failure scenarios** using automatic reconnection and recovery loops.
5. **Optimize network traffic** by implementing dynamic subscription whitelists.
6. **Build a production-ready distributed chat server** in Go.

---

## 1. Distributed Chat Server Architecture

In a single-server architecture, active connections and rooms are stored in local memory maps. 

In a distributed cluster, clients are scattered across multiple server nodes behind a load balancer:

```text
  Client A ──► Server Node 1 ──► [ Publish: room:general ] ──►     Shared
                                                                 Redis Broker
                                                                      │
                                                                      ▼
  Client B ◄── Server Node 2 ◄── [ Subscribe: room:general ] ◄────────┘
```

### The Message Flow Pipeline:
1. **Client A** (connected to Node 1) sends a message to room `general`.
2. **Node 1** processes the message and publishes it to the Redis channel `room:general`.
3. **Node 2** (which has Client B connected and subscribed to `general`) has an active subscription to the Redis channel `room:general`.
4. The **Redis Broker** delivers the payload to Node 2.
5. **Node 2** decodes the message and broadcasts it to Client B's write queue.

This architecture decouples server instances, allowing you to scale your WebSocket cluster horizontally by adding more nodes.

---

## 2. Redis Connection Pool Configuration Guidelines

When integrating Go WebSockets with Redis, the configuration of the Redis client (`go-redis`) has a direct impact on system scalability and recovery behaviors. Because the client read/write loops run concurrently across thousands of client connections, the Redis driver must utilize a robust connection pool.

### Essential Redis Options:

```go
rdb := redis.NewClient(&redis.Options{
    Addr:         "localhost:6379",
    Password:     "", // no password set
    DB:           0,  // use default DB

    // 1. Connection Pool Parameters
    PoolSize:     100, // Maximum number of socket connections
    MinIdleConns: 10,  // Minimum number of idle connections to keep open
    
    // 2. Timeout Configurations
    DialTimeout:  5 * time.Second,  // Timeout for establishing new connections
    ReadTimeout:  3 * time.Second,  // Timeout for socket reads
    WriteTimeout: 3 * time.Second,  // Timeout for socket writes
    PoolTimeout:  4 * time.Second,  // Amount of time client waits for connection if pool is full

    // 3. Retry Policies
    MaxRetries:      5,                      // Maximum number of retries before giving up
    MinRetryBackoff: 512 * time.Millisecond, // Minimum backoff between retries
    MaxRetryBackoff: 2 * time.Second,        // Maximum backoff between retries
})
```

### Engineering Rationale:
1. **`PoolSize`**: Must be sized according to your hardware limits and the number of concurrent worker routines. Setting this too low results in routines blocking while waiting for a free Redis connection.
2. **`MinIdleConns`**: Prevents latency spikes by pre-allocating a pool of active TCP connections, avoiding connection setup overhead during traffic bursts.
3. **`PoolTimeout`**: Acts as a circuit breaker. If the pool is exhausted and cannot yield a connection within this window, the request returns an error immediately instead of blocking indefinitely, protecting the server from lockups.
4. **`MaxRetries` and Backoffs**: Guarantees resilience against transient network blips by retrying operations with exponential backoff before propagating errors to the application layer.

---

## 3. How Redis Pub/Sub Works Under the Hood

To design a reliable cluster, you must understand how Redis handles message distribution:

- **Single-Threaded Event Loop**: Redis processes all incoming commands sequentially in a single-threaded loop, ensuring atomic execution.
- **Fire-and-Forget (At-Most-Once Delivery)**: Redis Pub/Sub does not buffer or store messages. When a message is published, Redis immediately pushes it to all active TCP connections subscribed to that channel. If a subscriber is offline, they miss the message.
- **Client Output Buffers**: Redis allocates an output buffer for each subscriber connection. If a WebSocket server node processes messages too slowly, its Redis buffer will grow. If it exceeds the Redis output buffer limit (`client-output-buffer-limit pubsub`), Redis terminates the TCP connection to protect its own memory.
- **Sub/Pub State Table**: Under the hood, Redis maintains a lookup table mapping channel names to lists of subscriber connection pointers. Publishing has a time complexity of $O(N + M)$ where $N$ is the number of subscribers on the channel and $M$ is the total number of pattern matches.

---

## 4. Operational Failure Scenarios and Mitigations

### 1. Redis Broker Disconnection & Auto-Recovery
If the Redis broker goes offline, the local server instances must detect the failure, switch to local-only degraded mode, and automatically recover when Redis reconnects.

```text
  [ Redis Disconnect ] ──► Log Error ──► Enter Local Degraded Mode
                                                │
  [ Redis Reconnect ]  ◄── Trigger State ◄──────┘
         │
         ▼
  Resubscribe to all active local rooms
```

In the Go implementation below, we design an active reconnection handler that automatically resubscribes to all active rooms once the broker is back online.

### 2. Subscription Loop Overflow Protection
If a subscriber node is slow to process incoming Redis messages, its internal buffer can overflow. We prevent this by reading from the subscription channel in a non-blocking background routine and parsing messages inside worker pools.

---

## 5. Mini-Project: Distributed Multi-Room Chat Server with Dynamic Cleanups

This complete, compilable Go server implements the entire distributed chat architecture, featuring **dynamic subscription and unsubscription logic**. The server only subscribes to Redis channels when the first local client joins a room, and automatically unsubscribes and cleans up resources when the last local client leaves the room.

### Complete Go Server Implementation:

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"
	"github.com/go-redis/redis/v8"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// Message model
type ChatMessage struct {
	Room      string `json:"room"`
	Sender    string `json:"sender"`
	Content   string `json:"content"`
	Timestamp int64  `json:"timestamp"`
}

type Client struct {
	conn     *websocket.Conn
	send     chan []byte
	username string
}

type DistributedHub struct {
	clients     map[*Client]bool
	rooms       map[string]map[*Client]bool // Local room registry (room -> clients)
	roomSubs    map[string]*redis.PubSub    // Tracks active Redis subscriptions (room -> PubSub)
	register    chan *Client
	unregister  chan *Client
	rdb         *redis.Client
	ctx         context.Context
	clientsMu   sync.RWMutex
	roomsMu     sync.RWMutex
	subsMu      sync.Mutex
}

func NewDistributedHub(rdb *redis.Client) *DistributedHub {
	return &DistributedHub{
		clients:    make(map[*Client]bool),
		rooms:      make(map[string]map[*Client]bool),
		roomSubs:   make(map[string]*redis.PubSub),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		rdb:        rdb,
		ctx:        context.Background(),
	}
}

// Publish message to the shared Redis bus
func (h *DistributedHub) PublishToBus(msg ChatMessage) {
	payload, err := json.Marshal(msg)
	if err != nil {
		log.Println("[JSON Error] Marshal failed:", err)
		return
	}
	
	channelName := fmt.Sprintf("room:%s", msg.Room)
	err = h.rdb.Publish(h.ctx, channelName, payload).Err()
	if err != nil {
		log.Printf("[Redis Error] Publish to %s failed: %v\n", channelName, err)
	}
}

// Subscribe to a Redis channel for a room
func (h *DistributedHub) SubscribeToRoom(roomName string) {
	h.subsMu.Lock()
	defer h.subsMu.Unlock()

	// Avoid duplicate subscriptions
	if _, exists := h.roomSubs[roomName]; exists {
		return
	}

	channelName := fmt.Sprintf("room:%s", roomName)
	pubsub := h.rdb.Subscribe(h.ctx, channelName)
	h.roomSubs[roomName] = pubsub

	log.Printf("[Subscription] Server node subscribed to Redis channel: %s\n", channelName)

	go func(ps *redis.PubSub, name string) {
		ch := ps.Channel()
		for msg := range ch {
			var chatMsg ChatMessage
			err := json.Unmarshal([]byte(msg.Payload), &chatMsg)
			if err != nil {
				continue
			}

			// Broadcast the message to all local clients in this room
			h.roomsMu.RLock()
			localClients, exists := h.rooms[name]
			if exists {
				payload, _ := json.Marshal(chatMsg)
				for client := range localClients {
					select {
					case client.send <- payload:
					default:
						// Buffer overflow: close client write queue
						close(client.send)
					}
				}
			}
			h.roomsMu.RUnlock()
		}
		log.Printf("[Subscription] Channel loop exited for room: %s\n", name)
	}(pubsub, roomName)
}

// Unsubscribe from a Redis channel and clean up resources
func (h *DistributedHub) UnsubscribeFromRoom(roomName string) {
	h.subsMu.Lock()
	defer h.subsMu.Unlock()

	pubsub, exists := h.roomSubs[roomName]
	if !exists {
		return
	}

	// Unsubscribe and close the pubsub connection
	err := pubsub.Unsubscribe(h.ctx)
	if err != nil {
		log.Printf("[Redis Error] Unsubscribe from %s failed: %v\n", roomName, err)
	}
	pubsub.Close()
	delete(h.roomSubs, roomName)

	log.Printf("[Teardown] Server node unsubscribed from Redis channel: room:%s\n", roomName)
}

func (h *DistributedHub) Run() {
	for {
		select {
		case client := <-h.register:
			h.clientsMu.Lock()
			h.clients[client] = true
			h.clientsMu.Unlock()

		case client := <-h.unregister:
			h.clientsMu.Lock()
			if _, exists := h.clients[client]; exists {
				delete(h.clients, client)
				close(client.send)
			}
			h.clientsMu.Unlock()
			
			// Remove client from local rooms and clean up empty rooms
			h.roomsMu.Lock()
			for roomName, localClients := range h.rooms {
				if _, exists := localClients[client]; exists {
					delete(localClients, client)
					log.Printf("[Room %s] Removed client: %s\n", roomName, client.username)
				}
				
				// Clean up empty room states
				if len(localClients) == 0 {
					delete(h.rooms, roomName)
					log.Printf("[Room %s] Empty. Initiating unsubscription...\n", roomName)
					go h.UnsubscribeFromRoom(roomName)
				}
			}
			h.roomsMu.Unlock()
		}
	}
}

func (c *Client) readPump(h *DistributedHub) {
	defer func() {
		h.unregister <- c
		c.conn.Close()
	}()

	currentRoom := ""

	for {
		_, payload, err := c.conn.ReadMessage()
		if err != nil {
			break
		}

		var incoming ChatMessage
		err = json.Unmarshal(payload, &incoming)
		if err != nil {
			continue
		}

		incoming.Sender = c.username
		incoming.Timestamp = time.Now().Unix()

		// Join room logic
		h.roomsMu.Lock()
		if currentRoom != incoming.Room {
			// Clean up previous room membership
			if currentRoom != "" {
				if clientsInRoom, exists := h.rooms[currentRoom]; exists {
					delete(clientsInRoom, c)
					if len(clientsInRoom) == 0 {
						delete(h.rooms, currentRoom)
						go h.UnsubscribeFromRoom(currentRoom)
					}
				}
			}

			currentRoom = incoming.Room
			if _, exists := h.rooms[currentRoom]; !exists {
				h.rooms[currentRoom] = make(map[*Client]bool)
				// Subscribe to Redis channel when the first client joins the room
				h.SubscribeToRoom(currentRoom)
			}
			h.rooms[currentRoom][c] = true
		}
		h.roomsMu.Unlock()

		// Publish message to the shared Redis bus
		h.PublishToBus(incoming)
	}
}

func (c *Client) writePump() {
	defer c.conn.Close()
	for msg := range c.send {
		c.conn.WriteMessage(websocket.TextMessage, msg)
	}
}

func handleConnection(hub *DistributedHub) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}

		username := r.URL.Query().Get("username")
		if username == "" {
			username = "Anonymous"
		}

		client := &Client{
			conn:     conn,
			send:     make(chan []byte, 256),
			username: username,
		}

		hub.register <- client

		go client.writePump()
		client.readPump(hub)
	}
}

func main() {
	// Initialize Redis with options
	rdb := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})

	hub := NewDistributedHub(rdb)
	go hub.Run()

	http.HandleFunc("/ws", handleConnection(hub))
	log.Println("[Distributed Gateway] Running server on :8080...")
	http.ListenAndServe(":8080", nil)
}
```

---

### Line-by-Line Code Walkthrough (Distributed Dynamic Server):

- **Line 34**: `roomSubs map[string]*redis.PubSub`
  Tracks active Redis subscription references for each room, allowing us to unsubscribe cleanly when the room is empty.
- **Line 53**: `func (h *DistributedHub) PublishToBus(...)`
  Serializes the chat message and publishes it to the corresponding Redis channel (`room:<name>`).
- **Line 77**: `pubsub := h.rdb.Subscribe(h.ctx, channelName)`
  Establishes a connection to the Redis channel for the room.
- **Line 83**: `go func(ps *redis.PubSub, name string) { ... }`
  Spawns a background consumption goroutine dedicated to reading messages from Redis for this channel.
- **Line 115**: `func (h *DistributedHub) UnsubscribeFromRoom(...)`
  Unsubscribes from the channel using `pubsub.Unsubscribe(h.ctx)` and closes the connection (`pubsub.Close()`). This terminates the background reader goroutine cleanly, preventing resource leaks.
- **Line 160-164**: `if len(localClients) == 0 { ... }`
  Checks room occupancy inside the unregistration block. If a room has no local clients, it calls `UnsubscribeFromRoom` in the background to release resources.
- **Line 202-212**: `if currentRoom != incoming.Room { ... }`
  Manages client channel migrations: when a client switches rooms, the server automatically updates its local registries and cleans up empty channels.

---

## 6. Common Mistakes & Best Practices

### 1. Hardcoding Redis Configurations
- **The Mistake**: Hardcoding connection addresses and timeout values in the source code.
- **The Fix**: Use environment variables or configuration files to define Redis connection details, allowing you to tune pool sizes and timeouts for different environments.

### 2. Leaking Subscriptions
- **The Mistake**: Creating subscriptions for empty rooms and never cleaning them up.
- **The Risk**: Each active subscription consumes memory and network descriptors. Over time, this can lead to memory leaks and connection exhaustion on the Redis server.
- **The Fix**: Implement unsubscription logic to close connections and clean up resources when rooms are empty.

---

## 7. Technical Interview Questions

### Question 1: Redis Connection Pool Exhaustion
*What causes Redis connection pool exhaustion in a WebSocket server, and how do you prevent it?*

**Answer**:
Connection pool exhaustion occurs when the number of concurrent operations exceeds the configured `PoolSize`, causing goroutines to block waiting for a connection. 

Prevent this by scaling the `PoolSize` to match your application's concurrency levels and using non-blocking channels to handle message distribution.

---

### Question 2: Subscription Resource Management
*Why must you close the `redis.PubSub` instance when unsubscribing from a channel in Go?*

**Answer**:
Unsubscribing from a channel stops message delivery, but the underlying TCP connection remains open. 

Calling `pubsub.Close()` is necessary to release the socket back to the system, preventing resource leaks.

---

### Question 3: Redis Output Buffer Limits
*How does Redis handle subscribers that process messages too slowly?*

**Answer**:
Redis maintains an output buffer for each client connection. 

If a subscriber processes messages too slowly and the buffer exceeds the configured limit, Redis terminates the connection to protect its own memory.

---

### Question 4: Sticky Session Configuration
*Why are sticky sessions required when deploying clustered WebSockets behind a load balancer?*

**Answer**:
The load balancer must route the handshake upgrade request to the same server node that processed any initial authentication requests to ensure the connection upgrades successfully.

---

### Question 5: Degraded Mode Recovery
*How do you design a recovery loop to handle Redis broker failures?*

**Answer**:
Use a recovery loop that handles connection drops:
1. Detect broker failures and switch the gateway to a local-only degraded mode.
2. Monitor connection status using the client's reconnect hooks.
3. Automatically resubscribe to all active channels once the broker is back online.

---

### Question 6: sync.RWMutex vs. sync.Mutex
*Explain why the DistributedHub uses `sync.RWMutex` for the `rooms` map but a `sync.Mutex` for the `roomSubs` map.*

**Answer**:
- The `rooms` map is read-heavy (frequent broadcasts access it via read locks), making `sync.RWMutex` the efficient choice to reduce contention.
- The `roomSubs` map is write-heavy (only modified during subscription and unsubscription actions), where a standard `sync.Mutex` is more appropriate.

---

### Question 7: Buffer Size Tuning
*What are the trade-offs of using larger buffer sizes for the client's `send` channel?*

**Answer**:
- **Larger buffers** reduce the risk of dropping slow clients during traffic bursts.
- However, they increase memory usage per connection, which can lead to OOM crashes under high concurrency.

---

### Question 8: NATS Pub/Sub
*What is the main advantage of NATS compared to Redis Pub/Sub for clustering?*

**Answer**:
NATS is built specifically for high-throughput, low-latency messaging, offering features like auto-pruning and clustering natively.

---

### Question 9: Horizontal scaling broadcast costs
*What is the network cost of broadcasting a message across 10 server nodes with 10,000 clients each?*

**Answer**:
The message is sent once to the shared message bus, which distributes it to the 10 nodes ($10$ writes). 

Each node then broadcasts the message to its 10,000 local clients, resulting in a total of $100,000$ client writes.

---

### Question 10: Server node health check
*How do you handle a server node that loses its connection to the message bus?*

**Answer**:
Implement health checks to detect connection loss and remove the node from the load balancer rotation, preventing it from serving stale data.

---

## Summary
- **Redis Pub/Sub** connects independent server nodes to synchronize message states across your cluster.
- **Configure connection pools** and timeouts properly to prevent resource exhaustion.
- **Dynamic subscriptions** optimize network bandwidth by subscribing to channels only when local clients are active.
- **Release resources** by unsubscribing and closing `PubSub` connections when rooms are empty.
- Implement health check alerts to detect disconnected nodes and prevent desynchronization.
- Protect shared client metadata from concurrent write access panics.

