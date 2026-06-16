# Module 20: Scaling Beyond One Server

Scaling a stateless REST API is simple: you deploy multiple instances behind a load balancer, and any server can handle any incoming request. Scaling WebSockets is more difficult: connections are stateful, long-lived, and bound to a specific server instance. If Client A is connected to Server 1, and Client B is connected to Server 2, they cannot communicate directly through their local maps.

This module details how to scale WebSocket applications beyond a single server. We will analyze why stateful hubs break at scale, study load balancer sticky sessions, design a horizontally scaled architecture using a shared Redis Pub/Sub message bus, and build a complete distributed synchronization gateway in Go.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the core challenges** of scaling stateful WebSocket connections.
2. **Describe the role of sticky sessions** in load balancer routing.
3. **Analyze resource ceilings** such as file descriptor limits (C10k and C1M limits).
4. **Design a horizontally scaled architecture** using a shared Pub/Sub bus.
5. **Implement a Redis-backed distributed synchronization loop** in Go.
6. **Synchronize message broadcasts** across multiple independent server nodes.

---

## 1. Why Hubs Break at Scale

Stateless APIs scale horizontally by adding instances behind a round-robin load balancer. 

However, WebSockets are stateful:
- A connection is a persistent TCP socket established between a client and a specific server instance's memory.
- If Server Node 1 receives a message, it can only broadcast it to clients connected to Server Node 1. It has no way of reaching clients on Server Node 2.

```text
                  ┌────────────── Load Balancer ──────────────┐
                  │                                           │
                  ▼                                           ▼
         ┌──── Server 1 ────┐                        ┌──── Server 2 ────┐
         │ (clients map)    │                        │ (clients map)    │
         └────────┬─────────┘                        └────────┬─────────┘
                  │                                           │
                  ▼                                           ▼
               Client A                                    Client B
```

If Client A sends a message intended for Client B, Server 1 cannot route it because Client B is connected to Server 2. This stateful barrier prevents independent nodes from communicating.

---

### The Resource Ceiling (C10k and C1M Limits)
Even if you run your application on a single server, you will eventually hit resource limits:
- **File Descriptors**: In Linux, each TCP socket is a file descriptor. The OS limits the maximum number of open files per process.
- **Memory Limits**: Each active connection allocates read/write buffers, consuming RAM.
- **Port Starvation**: A single IP address can support a maximum of 65,535 outbound connections.
Scaling horizontally across multiple servers is necessary to bypass these resource limits.

---

## 2. Sticky Sessions & Load Balancing

When deploying WebSockets behind a load balancer, you must configure **Sticky Sessions (Session Affinity)**:
- The initial WebSocket handshake is an HTTP upgrade request.
- The load balancer must route the handshake request to the same server node that processed any initial auth handshakes.
- Configure sticky sessions using cookie-based routing or IP hashing.
- Once the handshake upgrades to a WebSocket, the TCP tunnel is established directly between the client and the target server node.

---

## 3. Horizontal Scaling & Distributed Messaging Architecture

To scale stateful WebSockets horizontally, you must connect the independent server nodes using a **Shared Message Bus** (like Redis Pub/Sub or NATS):

```text
   Server Node 1 ──────► [ Publish: chat-channel ] ──────►   Shared Redis
         │                                                        │
         │                                                        ▼
   Broadcasts locally ◄── [ Subscribe: chat-channel ] ◄── Server Node 2
```

### The Synchronization Flow:
1. Client A sends a message to Server 1.
2. Server 1 broadcasts the message to its locally connected clients.
3. Server 1 serializes the message and publishes it to the shared Redis Pub/Sub channel.
4. Server 2 subscribes to the Redis channel. When the message arrives, Server 2 broadcasts it to its locally connected clients.

This architecture allows nodes to synchronize messages, enabling horizontal scale-out.

---

## 4. Exercises: Designing and Building a Redis Pub/Sub Sync Bus

In this exercise, you will build a Go server that integrates Redis Pub/Sub to synchronize message broadcasts across multiple server nodes.

### Complete Go Server Implementation:

```go
package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"sync"
	"github.com/go-redis/redis/v8"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// 1. Message Payload Model
type BroadcastMessage struct {
	Sender  string `json:"sender"`
	Content string `json:"content"`
}

type Client struct {
	conn *websocket.Conn
	send chan []byte
}

type RedisHub struct {
	clients   map[*Client]bool
	clientsMu sync.RWMutex
	rdb       *redis.Client
	ctx       context.Context
}

func NewRedisHub(rdb *redis.Client) *RedisHub {
	return &RedisHub{
		clients: make(map[*Client]bool),
		rdb:     rdb,
		ctx:     context.Background(),
	}
}

// 2. Publish message to Redis
func (rh *RedisHub) PublishMessage(msg BroadcastMessage) error {
	payload, err := json.Marshal(msg)
	if err != nil {
		return err
	}
	// Publish payload to Redis channel "global-ws-broadcast"
	return rh.rdb.Publish(rh.ctx, "global-ws-broadcast", payload).Err()
}

// 3. Listen to Redis channel and broadcast locally
func (rh *RedisHub) StartRedisSubscriptionLoop() {
	pubsub := rh.rdb.Subscribe(rh.ctx, "global-ws-broadcast")
	defer pubsub.Close()

	log.Println("[Redis Bus] Subscribed to global-ws-broadcast channel.")

	ch := pubsub.Channel()
	for msg := range ch {
		log.Printf("[Redis Bus] Received message: %s\n", msg.Payload)
		
		// Broadcast message to all locally connected clients
		rh.clientsMu.RLock()
		for client := range rh.clients {
			select {
			case client.send <- []byte(msg.Payload):
			default:
				close(client.send)
				// Clean up client on write failure
				rh.clientsMu.RUnlock()
				rh.clientsMu.Lock()
				delete(rh.clients, client)
				rh.clientsMu.Unlock()
				rh.clientsMu.RLock()
			}
		}
		rh.clientsMu.RUnlock()
	}
}

func (c *Client) readPump(rh *RedisHub, username string) {
	defer func() {
		rh.clientsMu.Lock()
		delete(rh.clients, c)
		rh.clientsMu.Unlock()
		c.conn.Close()
	}()

	for {
		_, payload, err := c.conn.ReadMessage()
		if err != nil {
			break
		}

		msg := BroadcastMessage{
			Sender:  username,
			Content: string(payload),
		}

		// Publish message to Redis instead of broadcasting locally
		if err := rh.PublishMessage(msg); err != nil {
			log.Println("[Error] Failed to publish message:", err)
		}
	}
}

func (c *Client) writePump() {
	defer c.conn.Close()
	for msg := range c.send {
		c.conn.WriteMessage(websocket.TextMessage, msg)
	}
}

func handleConnection(rh *RedisHub) http.HandlerFunc {
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
			conn: conn,
			send: make(chan []byte, 256),
		}

		rh.clientsMu.Lock()
		rh.clients[client] = true
		rh.clientsMu.Unlock()

		go client.writePump()
		client.readPump(rh, username)
	}
}

func main() {
	// Initialize Redis Client
	rdb := redis.NewClient(&redis.Options{
		Addr: "localhost:6379", // Redis server address
	})

	rh := NewRedisHub(rdb)
	
	// Start the Redis subscription loop in the background
	go rh.StartRedisSubscriptionLoop()

	http.HandleFunc("/ws", handleConnection(rh))
	log.Println("[Gateway Server] Running on :8080...")
	http.ListenAndServe(":8080", nil)
}
```

---

### Line-by-Line Code Walkthrough (Redis Pub/Sub Gateway):

- **Line 31**: `type RedisHub struct { ... }`
  Defines the RedisHub struct. It manages local client registries and wraps the Redis client.
- **Line 46**: `func (rh *RedisHub) PublishMessage(...)`
  Serializes messages and publishes them to the Redis channel `global-ws-broadcast`.
- **Line 56**: `func (rh *RedisHub) StartRedisSubscriptionLoop()`
  Subscribes to the Redis channel and runs a loop to consume incoming messages.
- **Line 62**: `ch := pubsub.Channel()`
  Returns a Go channel to consume incoming messages from the Redis subscription.
- **Line 67-80**: `for client := range rh.clients`
  Iterates over the local client map and pushes the message to each client's send queue, synchronizing the broadcast locally.
- **Line 105**: `if err := rh.PublishMessage(msg); err != nil`
  Publishes incoming client messages to the Redis channel, synchronizing the message across all server nodes.

---

## 5. Common Scaling Pitfalls

### 1. Thundering Herd on Redis Reconnection
- If the Redis server restarts, all WebSocket server nodes lose their connection to Redis. When Redis comes back online, nodes attempt to resubscribe simultaneously.
- **Mitigation**: Implement exponential backoff in your Redis connection loops.

### 2. State Desynchronization
- If a server node loses its connection to the message bus, it will miss broadcasts, leading to desynchronization.
- **Mitigation**: Implement health check alerts to detect disconnected nodes and remove them from the load balancer rotation.

---

## 6. Technical Interview Questions

### Question 1: Stateful vs. Stateless Scaling
*Why is scaling stateful WebSockets more difficult than scaling stateless REST APIs?*

**Answer**:
- **Stateless REST APIs** can be scaled by adding servers behind a load balancer, as any server can handle any incoming request.
- **Stateful WebSockets** are bound to a specific server instance's memory. If Client A is connected to Server 1, and Client B is connected to Server 2, they cannot communicate directly through their local maps, requiring a shared message bus to synchronize messages.

---

### Question 2: Load Balancer Sticky Sessions
*Why are sticky sessions required during the WebSocket handshake?*

**Answer**:
The initial WebSocket handshake is an HTTP upgrade request. 

The load balancer must route this request to the same server node that processed any initial session setups or session verification to ensure the upgrade succeeds.

---

### Question 3: File Descriptor limits
*What is the file descriptor ceiling, and how does it limit the number of concurrent WebSocket connections?*

**Answer**:
In Linux, each TCP socket connection is represented as a file descriptor. 

The OS limits the maximum number of open files per process. If this limit is reached, the server cannot accept new connections, requiring horizontal scaling to bypass the limit.

---

### Question 4: Shared Message Bus role
*What is the role of a shared message bus (like Redis or NATS) in scaling WebSockets horizontally?*

**Answer**:
It acts as the synchronization layer between server nodes, publishing messages from one server to all other servers so they can broadcast the message to their locally connected clients.

---

### Question 5: Port Starvation limit
*Explain the port starvation limit.*

**Answer**:
A single IP address can support a maximum of 65,535 outbound connections. 

If a load balancer establishes more connections than this limit, it suffers from port starvation, requiring multiple IP addresses or load balancers to scale.

---

### Question 6: NATS vs. Redis Pub/Sub
*When would you choose NATS over Redis Pub/Sub for WebSocket synchronization?*

**Answer**:
- Choose **Redis** if you already have Redis deployed in your stack for caching or session storage.
- Choose **NATS** if you require a high-throughput, low-latency messaging engine optimized for microservice architectures.

---

### Question 7: Redis channel subscription leakage
*What happens if a subscription loop fails to close the PubSub client when exiting?*

**Answer**:
It leaks the Redis connection, eventually exhausting the Redis server's connection pool.

---

### Question 8: Sticky sessions on WSS?
*Do sticky sessions affect WSS connections after the handshake upgrades?*

**Answer**:
No. Once the handshake upgrades to a WebSocket, the TCP tunnel is established directly between the client and the target server node, bypassing load balancer routing.

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
- **Stateful WebSockets** require a shared message bus (like Redis or NATS) to synchronize messages between servers.
- **Sticky Sessions** are required during the handshake phase to route requests to the same server node.
- **System Resource limits** (file descriptors, RAM, and port constraints) limit single-server scalability.
- **Design distributed synchronization loops** using Redis Pub/Sub to broadcast messages across nodes.
- Implement health check alerts to detect disconnected nodes and prevent desynchronization.
