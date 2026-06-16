# Module 22: Kafka and Event Streaming

For applications that process massive data streams (like activity feeds, real-time metrics, financial trading dashboards, or auditing pipelines), a fire-and-forget broker like Redis Pub/Sub is not enough. You need an event streaming platform that persists messages, handles high throughput, and supports partition replay. Apache Kafka is the industry standard for this use case.

This module details how to integrate Apache Kafka with a Go WebSocket gateway. We will explore Kafka fundamentals (topics, partitions, consumer groups, and offset tracking), study WebSocket-to-Kafka fan-out architectures, manage backpressure and event ordering, and build an event streaming consumer gateway in Go.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain Kafka fundamentals** and their relevance to WebSockets.
2. **Design a high-throughput fan-out architecture** to broadcast Kafka streams.
3. **Analyze when to use Kafka** versus Redis Pub/Sub.
4. **Implement backpressure mitigations** to protect slow clients from message storms.
5. **Guarantee message ordering** across partitions and WebSocket loops.
6. **Build a compilable Kafka consumer gateway** in Go.

---

## 1. Kafka Fundamentals for WebSockets

Apache Kafka is a distributed, partitioned commit log:
- **Topics**: Categories to which messages are published.
- **Partitions**: Topics are divided into partitions to distribute scale.
- **Offset Tracking**: Pointers that track consumed messages.
- **Consumer Groups**: Multiple server instances that share the load of consuming a topic.

---

### The Fan-Out Architecture

Kafka partitions are designed to be consumed sequentially by a single thread. You cannot have thousands of clients reading from a single partition.

To scale, deploy a **Fan-Out Architecture**:
- A single background consumer loop on the Go server reads messages from the Kafka partition.
- The consumer loop forwards the messages to an internal Hub.
- The Hub iterates over its local client map and pushes the payloads to each client's write channel.

```text
               ┌─────────── Go Web Server ───────────┐
               │                                     │
  Kafka ──────►│ Consumer Loop ──► Hub Event ───────┼──► Client A
  Partition    │                    Loop (Fan-Out)   ├──► Client B
               │                                     ┼──► Client C
               └─────────────────────────────────────┘
```

This decouples Kafka consumption from client distribution, allowing the server to handle thousands of concurrent WebSocket connections from a single Kafka stream.

---

## 2. When to Use Kafka

### When Kafka Helps:
- **Event Replay**: You need to stream historical events when clients connect or reconnect.
- **High Ingestion Throughput**: You need to process massive ingestion streams (e.g. millions of metrics updates per minute).
- **Persistent Audit Logs**: Messages must be saved to disk and preserved.

### When Kafka is Unnecessary:
- **Low-Latency Peer-to-Peer Chat**: Simple chat rooms do not require log persistence or partition offsets. Redis Pub/Sub is lighter and faster for these use cases.
- **Stateless Signalling**: WebRTC signalling or notifications do not require log replay.

---

## 3. Managing Backpressure & Event Ordering

### 1. Backpressure Mitigation
- **The Problem**: Kafka can stream events at 100,000 msg/sec. A client browser on a mobile connection can only consume 10 msg/sec.
- If the server attempts to buffer all incoming messages in the client's `send` channel, it will exhaust memory and crash.
- **The Fix**: Implement backpressure checks in the Hub. If a client's write channel is full, drop the message or close the connection to protect the server's resources.

---

### 2. Guaranteeing Message Ordering
- **The Problem**: Message order is only guaranteed within a single partition.
- **The Fix**: Route related events to the same partition using a partition key (e.g. `UserID` or `RoomID`).
- In Go, channels operate on a First-In-First-Out (FIFO) basis, preserving message order from the partition to the client write loop.

---

## 4. Exercises: Streaming Kafka Events to Clients

In this exercise, you will build a Go server that integrates a Kafka consumer using the **`segmentio/kafka-go`** library and streams partition events to WebSocket clients.

### Complete Go Server Implementation:

```go
package main

import (
	"context"
	"log"
	"net/http"
	"sync"
	"time"
	"github.com/gorilla/websocket"
	"github.com/segmentio/kafka-go"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

type Client struct {
	conn *websocket.Conn
	send chan []byte
}

type KafkaHub struct {
	clients   map[*Client]bool
	clientsMu sync.RWMutex
	register  chan *Client
	unregister chan *Client
}

func NewKafkaHub() *KafkaHub {
	return &KafkaHub{
		clients:    make(map[*Client]bool),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

func (kh *KafkaHub) Run() {
	for {
		select {
		case client := <-kh.register:
			kh.clientsMu.Lock()
			kh.clients[client] = true
			kh.clientsMu.Unlock()

		case client := <-kh.unregister:
			kh.clientsMu.Lock()
			if _, exists := kh.clients[client]; exists {
				delete(kh.clients, client)
				close(client.send)
			}
			kh.clientsMu.Unlock()
		}
	}
}

// Kafka Consumer Loop
func (kh *KafkaHub) StartKafkaConsumer(ctx context.Context, brokers []string, topic string, groupID string) {
	// 1. Initialize Kafka Reader
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  brokers,
		Topic:    topic,
		GroupID:  groupID,
		MinBytes: 10e3, // 10KB
		MaxBytes: 10e6, // 10MB
		MaxWait:  1 * time.Second,
	})
	defer reader.Close()

	log.Printf("[Kafka Consumer] Subscribed to topic: %s | Group ID: %s\n", topic, groupID)

	for {
		// 2. Fetch message from partition
		msg, err := reader.ReadMessage(ctx)
		if err != nil {
			log.Println("[Kafka Consumer] Read error:", err)
			return
		}

		log.Printf("[Kafka Consumer] Fetched offset: %d | Partition: %d\n", msg.Offset, msg.Partition)

		// 3. Fan-out message to locally connected clients
		kh.clientsMu.RLock()
		for client := range kh.clients {
			select {
			case client.send <- msg.Value:
				// Message queued successfully
			default:
				// Backpressure mitigation: drop slow client to protect server resources
				close(client.send)
				kh.clientsMu.RUnlock()
				kh.clientsMu.Lock()
				delete(kh.clients, client)
				kh.clientsMu.Unlock()
				kh.clientsMu.RLock()
			}
		}
		kh.clientsMu.RUnlock()
	}
}

func (c *Client) writePump() {
	defer c.conn.Close()
	for msg := range c.send {
		c.conn.WriteMessage(websocket.TextMessage, msg)
	}
}

func handleConnection(kh *KafkaHub) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}

		client := &Client{
			conn: conn,
			send: make(chan []byte, 256),
		}

		kh.register <- client

		go client.writePump()
	}
}

func main() {
	kh := NewKafkaHub()
	go kh.Run()

	// Configure Kafka brokers and topics
	brokers := []string{"localhost:9092"}
	topic := "realtime-activity-stream"
	groupID := "websocket-gateway-group"

	// Start the Kafka consumer loop in the background
	ctx := context.Background()
	go kh.StartKafkaConsumer(ctx, brokers, topic, groupID)

	http.HandleFunc("/ws", handleConnection(kh))
	log.Println("[Kafka Gateway] Running server on :8080...")
	http.ListenAndServe(":8080", nil)
}
```

---

### Line-by-Line Code Walkthrough (Kafka Stream):

- **Line 51**: `reader := kafka.NewReader(...)`
  Initializes the Kafka Reader using the `segmentio/kafka-go` library.
- **Line 66**: `msg, err := reader.ReadMessage(ctx)`
  A blocking call that fetches the next message from the partition log and automatically commits the offset.
- **Line 75-88**: `for client := range kh.clients`
  Iterates over the local client map to distribute the message.
- **Line 77**: `case client.send <- msg.Value:`
  Pushes the message to the client's write channel queue.
- **Line 80**: `default: close(client.send); ... delete(...)`
  Enforces backpressure: if a client's write channel is full, the server drops the connection and deletes the client from the registry.

---

## 5. Common Kafka Pitfalls

### 1. Committing Offsets Too Early
- **The Problem**: If the reader commits the partition offset before the message is successfully broadcast to clients, and the server crashes, those messages are lost.
- **The Fix**: Use manual offset commits (`FetchMessage` followed by `CommitMessages`) to guarantee message delivery.

### 2. Blocked Partition Consumer Threads
- **The Problem**: If a slow WebSocket broadcast blocks the consumer thread, partition consumption halts for all clients.
- **The Fix**: Always write to client channels using non-blocking select blocks.

---

## 6. Technical Interview Questions

### Question 1: Kafka Fan-Out Architecture
*Why is a dedicated background consumer loop required when streaming Kafka topics to WebSocket clients?*

**Answer**:
Kafka partitions are designed to be consumed sequentially by a single thread. You cannot have thousands of clients reading from a partition concurrently. 

Using a dedicated background consumer loop decouples partition consumption from client distribution, allowing the server to handle thousands of concurrent WebSocket connections from a single Kafka stream.

---

### Question 2: Partition Offset commit
*Explain the difference between auto-committing offsets and manual offset commits.*

**Answer**:
- **Auto-committing** commits partition offsets periodically in the background, which is simple but can lead to message loss if the server crashes before messages are processed.
- **Manual committing** commits offsets only after the message is successfully broadcast, guaranteeing message delivery.

---

### Question 3: Message Ordering Guarantees
*How does Kafka guarantee message ordering across partitions?*

**Answer**:
Kafka only guarantees message ordering within a single partition. 

To preserve ordering, use a partition key (like `UserID` or `RoomID`) to route related events to the same partition.

---

### Question 4: Redis vs. Kafka
*When would you choose Kafka over Redis Pub/Sub for WebSockets?*

**Answer**:
Choose **Kafka** if you require message persistence, event replay, or high-throughput log processing. 

Choose **Redis Pub/Sub** for simple, low-latency messaging.

---

### Question 5: Backpressure close status
*What close code is sent when the server drops a client due to backpressure?*

**Answer**:
It sends code `1008 (Policy Violation)` to notify the client of a rate limit or buffer violation.

---

### Question 6: Segmentio kafka-go MinBytes
*What does the `MinBytes` configuration do in the Kafka reader?*

**Answer**:
It sets the minimum amount of data to fetch from the partition before returning, batching requests to reduce network overhead.

---

### Question 7: GC memory leak reader
*Why is it critical to call `reader.Close()` when shutting down the consumer loop?*

**Answer**:
It closes active TCP connections to the Kafka brokers and stops background routines, preventing resource leaks.

---

### Question 8: Consumer Group Balance
*What happens if you deploy more server instances in a consumer group than there are partitions in a topic?*

**Answer**:
The extra instances will remain idle, as each partition can only be consumed by a single thread in a consumer group at any given time.

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
- **Kafka** acts as the ingestion pipeline, and **WebSockets** act as the distribution layer.
- **Fan-Out** architectures decouple partition consumption from client distribution.
- **Ordering** is guaranteed within a partition by routing related events using partition keys.
- **Implement backpressure mitigations** (dropping slow clients) to protect server resources.
- Use manual offset commits to guarantee message delivery.
- Protect shared client metadata from concurrent write access panics.
