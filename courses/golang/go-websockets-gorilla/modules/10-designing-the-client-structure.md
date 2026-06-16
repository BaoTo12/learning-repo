# Module 10: Designing the Client Structure

When building stateful real-time applications, managing raw socket connections directly in your HTTP handlers leads to unmaintainable code. To build scalable chat hubs, collaborative tools, or financial tickers, you must wrap each connection in a structured representation.

This module details how to design an idiomatic Go **`Client`** structure. We will explore why wrapping connections is critical, analyze the engineering rationales behind each struct field (connection, send channel, identification, metadata, and cancellation context), study factory patterns, coordinate goroutine cleanup using context cancellation, and complete an exercise to extend the model with atomic telemetry counters and token-bucket rate limiting.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the benefits of encapsulating connection state** in a dedicated struct.
2. **Detail the role of each field** in the standard `Client` struct.
3. **Implement the Client Factory pattern** with context bindings.
4. **Coordinate read and write loops** using Go context cancellation to prevent goroutine leaks.
5. **Extend the client model** with atomic bandwidth metrics and token-bucket rate limiters.
6. **Implement concurrency protections** for shared client metadata.

---

## 1. Encapsulating Socket Connections

In a stateless REST API, each HTTP request is self-contained. The server processes the request, returns the response, and immediately discards the request context.

In a stateful WebSocket application, connections are long-lived and require managing ongoing state:
- **Identification**: Which authenticated user does this socket belong to?
- **Buffer Queue**: How do we queue messages to this client without blocking worker threads?
- **Metadata**: What are the client's current subscriptions, device types, or IP address?
- **Lifecycle Control**: How do we signal all active reader and writer goroutines to exit when a connection drops?

Wrapping the raw `websocket.Conn` in a custom `Client` struct encapsulates this state, providing a clean API for message routing and connection management.

---

## 2. Struct Fields and Engineering Rationales

Below is the standard, idiomatic layout of a Go WebSocket `Client` struct:

```go
package main

import (
	"context"
	"github.com/gorilla/websocket"
)

type Client struct {
	// 1. Raw WebSocket Connection
	conn *websocket.Conn

	// 2. Outbound Message Buffer Queue
	send chan []byte

	// 3. User Identification
	userID string

	// 4. Custom Session Metadata
	metadata map[string]interface{}

	// 5. Lifecycle Coordination Context
	ctx    context.Context
	cancel context.CancelFunc
}
```

---

### Detailed Field Analysis:

#### 1. `conn *websocket.Conn`
- **Why it exists**: Provides direct control over the underlying TCP socket.
- **Role**: Used to set deadlines, configure read limits, execute read/write operations, and handle Close handshakes.

#### 2. `send chan []byte`
- **Why it exists**: Serves as a buffered queue for outbound payloads.
- **Role**: Allows external goroutines to queue messages for the client (e.g. `client.send <- payload`) without blocking their execution flow. A dedicated write loop reads from this channel and writes to the socket sequentially.

#### 3. `userID string`
- **Why it exists**: Identifies the connected user.
- **Role**: Used by message hubs and routers to deliver messages to specific users (e.g. routing a direct message to `user_123`).

#### 4. `metadata map[string]interface{}`
- **Why it exists**: Stores dynamic parameters associated with the connection.
- **Role**: Stores session details such as client IP address, User-Agent header, authenticated roles, query parameters, or active channel subscriptions.

#### 5. `ctx context.Context` & `cancel context.CancelFunc`
- **Why it exists**: Manages the connection lifecycle.
- **Role**: When a connection drops or a client disconnects, calling `cancel()` signals all active read and write goroutines to exit, preventing orphaned goroutine leaks.

---

## 3. The Client Factory Pattern

To guarantee all fields (especially channels and contexts) are initialized correctly, implement the Client Factory pattern:

```go
// NewClient instantiates a new Client session
func NewClient(conn *websocket.Conn, userID string, parentCtx context.Context) *Client {
	// 1. Create a child context linked to the parent context
	ctx, cancel := context.WithCancel(parentCtx)

	return &Client{
		conn:     conn,
		send:     make(chan []byte, 256), // Allocate buffered queue channel
		userID:   userID,
		metadata: make(map[string]interface{}),
		ctx:      ctx,
		cancel:   cancel,
	}
}
```

- **`context.WithCancel`**: Binds the client session's lifecycle to the parent application context. If the main server shuts down, the parent context cancels, automatically triggering teardown across all active client connections.

---

## 4. Context Synchronization Across Read and Write Loops

When a client connects, the server spawns two concurrent goroutines:
1. **The Read Loop**: Reads frames from the socket.
2. **The Write Loop**: Writes queued messages from the `send` channel to the socket.

If the read loop encounters an error (e.g. client disconnects), the writer goroutine must be notified to clean up and exit.

Using a cancellation context makes this synchronization simple:

```go
func (c *Client) StartLifecycle() {
	// Start the writer loop in a new goroutine
	go c.writeLoop()

	// Run the reader loop in the current goroutine (blocking)
	c.readLoop()
}

func (c *Client) readLoop() {
	defer func() {
		// 1. Trigger context cancellation on read loop exit
		c.cancel()
		c.conn.Close()
	}()

	for {
		_, _, err := c.conn.ReadMessage()
		if err != nil {
			// Read failed, exit loop
			return
		}
	}
}

func (c *Client) writeLoop() {
	defer func() {
		c.conn.Close()
	}()

	for {
		select {
		case msg, ok := <-c.send:
			if !ok {
				return
			}
			c.conn.WriteMessage(websocket.TextMessage, msg)

		case <-c.ctx.Done():
			// 2. Context was cancelled (e.g. read loop failed or server shutdown).
			// Exit loop to clean up goroutine.
			return
		}
	}
}
```

If the read loop fails, it triggers `c.cancel()`. This updates `c.ctx.Done()`, causing the write loop to select that case and exit cleanly, preventing orphaned goroutine leaks.

---

## 5. Exercises: Extending the Client Model

In this exercise, you will extend the basic Client structure to include telemetry tracking (bandwidth consumption) and token-bucket rate limiting to protect the server from abuse.

### System Requirements:
1. **Telemetry Metrics**:
   - `connectedAt time.Time` (tracks session duration).
   - `bytesSent uint64` & `bytesReceived uint64` (tracks bandwidth consumption).
2. **Thread Safety**: Telemetry counters must be updated concurrently using the **`sync/atomic`** package.
3. **Rate Limiting**: Enforce a message frequency limit (e.g., maximum 5 messages per second) using a token-bucket rate limiter from **`golang.org/x/time/rate`**.

---

### Complete Go Implementation:

```go
package main

import (
	"context"
	"io"
	"log"
	"net/http"
	"sync/atomic"
	"time"
	"github.com/gorilla/websocket"
	"golang.org/x/time/rate"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// 1. Extended Client struct
type ExtendedClient struct {
	conn      *websocket.Conn
	send      chan []byte
	userID    string
	ctx       context.Context
	cancel    context.CancelFunc
	
	// Telemetry Fields
	connectedAt   time.Time
	bytesSent     uint64 // Must be read/written using sync/atomic
	bytesReceived uint64 // Must be read/written using sync/atomic
	
	// Rate Limiting Field
	rateLimiter *rate.Limiter
}

// NewExtendedClient instantiates the extended model
func NewExtendedClient(conn *websocket.Conn, userID string, parentCtx context.Context) *ExtendedClient {
	ctx, cancel := context.WithCancel(parentCtx)
	
	return &ExtendedClient{
		conn:          conn,
		send:          make(chan []byte, 256),
		userID:        userID,
		ctx:           ctx,
		cancel:        cancel,
		connectedAt:   time.Now(),
		bytesSent:     0,
		bytesReceived: 0,
		// Configure rate limiter: limit to 5 events per second, burst capacity of 10
		rateLimiter:   rate.NewLimiter(rate.Limit(5), 10),
	}
}

func (c *ExtendedClient) startReadLoop() {
	defer func() {
		c.cancel()
		c.conn.Close()
		log.Printf("[Session Teardown] Client %s disconnected. Session duration: %v | Bytes Received: %d | Bytes Sent: %d\n",
			c.userID, time.Since(c.connectedAt), atomic.LoadUint64(&c.bytesReceived), atomic.LoadUint64(&c.bytesSent))
	}()

	for {
		messageType, reader, err := c.conn.NextReader()
		if err != nil {
			break
		}

		// Enforce Rate Limiting Check
		if !c.rateLimiter.Allow() {
			log.Printf("[Rate Limit Exceeded] Client %s throttled. Terminating connection.\n", c.userID)
			c.sendCloseFrame(1008, "Policy Violation: Rate limit exceeded")
			break
		}

		// Read and track bandwidth using atomic counters
		buf := make([]byte, 1024)
		for {
			n, err := reader.Read(buf)
			if n > 0 {
				// Atomically increment bytes received
				atomic.AddUint64(&c.bytesReceived, uint64(n))
				// Process the bytes (Echo payload to write queue for demonstration)
				c.Write(buf[:n])
			}
			if err != nil {
				if err == io.EOF {
					break
				}
				return
			}
		}
	}
}

func (c *ExtendedClient) startWriteLoop() {
	defer c.conn.Close()

	for {
		select {
		case payload, ok := <-c.send:
			if !ok {
				return
			}

			err := c.conn.WriteMessage(websocket.TextMessage, payload)
			if err != nil {
				return
			}
			// Atomically increment bytes sent
			atomic.AddUint64(&c.bytesSent, uint64(len(payload)))

		case <-c.ctx.Done():
			return
		}
	}
}

func (c *ExtendedClient) Write(payload []byte) {
	select {
	case c.send <- payload:
	default:
		log.Println("[Warning] Write queue full, dropping message")
	}
}

func (c *ExtendedClient) sendCloseFrame(code int, text string) {
	c.conn.WriteControl(
		websocket.CloseMessage,
		websocket.FormatCloseMessage(code, text),
		time.Now().Add(1*time.Second),
	)
}

func handleUpgrade(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("Upgrade failed:", err)
		return
	}

	client := NewExtendedClient(conn, "user_123", context.Background())
	go client.startWriteLoop()
	client.startReadLoop()
}

func main() {
	http.HandleFunc("/ws", handleUpgrade)
	log.Println("[Gateway] Running on :8080...")
	http.ListenAndServe(":8080", nil)
}
```

---

### Line-by-Line Code Walkthrough (Extended Server):

- **Line 26-27**: `bytesSent`, `bytesReceived`
  Telemetry metrics stored as unsigned 64-bit integers. They are updated concurrently using Go's `sync/atomic` package, ensuring thread safety without lock overhead.
- **Line 30**: `rateLimiter *rate.Limiter`
  The rate limiter field. We use a token-bucket rate limiter from the `golang.org/x/time/rate` package.
- **Line 44**: `rate.NewLimiter(rate.Limit(5), 10)`
  Configures the rate limiter: limits the client to an average of 5 messages per second, with a burst capacity of 10 tokens.
- **Line 62**: `if !c.rateLimiter.Allow() { ... }`
  A non-blocking check that returns `false` if the client has exceeded their message rate limit.
- **Line 64**: `c.sendCloseFrame(1008, ...)`
  Sends a Close control frame with code `1008 (Policy Violation)` to notify the client of the rate limit violation before closing the socket.
- **Line 73**: `atomic.AddUint64(&c.bytesReceived, uint64(n))`
  Atomically increments the bytes received counter.
- **Line 101**: `atomic.AddUint64(&c.bytesSent, uint64(len(payload)))`
  Atomically increments the bytes sent counter in the write loop.

---

## 6. Common Mistakes & Best Practices

### 1. Concurrent Map Access on Metadata
- **The Mistake**: Allowing multiple goroutines to read and write to the client's `metadata` map concurrently:
  `client.metadata["key"] = val`
- **The Risk**: Go maps are not thread-safe. Concurrent read/write access will throw a runtime panic crash.
- **The Fix**: Protect map access using a `sync.RWMutex` lock, or use Go's thread-safe **`sync.Map`** for connection metadata.

### 2. Orphaned Goroutine Leaks
- **The Mistake**: Forgetting to call the `cancel` function when a connection is closed.
- **The Risk**: The writer loop goroutine remains blocked on the `send` channel indefinitely, leaking memory and threads.
- **The Fix**: Always call `cancel()` (usually in a deferred block in the reader loop) to clean up all active goroutines.

---

## 7. Technical Interview Questions

### Question 1: Concurrency Safe Metrics
*Why must you use `sync/atomic` or mutex locks to increment metrics like `bytesReceived`?*

**Answer**:
The client's read and write loops run in separate, concurrent goroutines. 

If both goroutines attempt to read or write to variables concurrently without synchronization, it creates a data race, leading to corrupted values or crashes. 

Using `sync/atomic` guarantees atomic operations at the hardware level, ensuring thread safety without lock overhead.

---

### Question 2: Goroutine Leak Prevention
*Explain how binding a Go context to the Client structure prevents goroutine leaks.*

**Answer**:
When a client connects, the server spawns reader and writer goroutines. 

If the connection drops, the reader loop exits and calls `cancel()`. 

The write loop listens to `<-ctx.Done()`. When cancelled, it exits cleanly, preventing the write loop goroutine from remaining blocked on the send channel.

---

### Question 3: Buffered Queue Sizing
*What is the purpose of allocating a buffered channel size of 256 for the `send` channel? What happens if it is full?*

**Answer**:
A buffered channel serves as a message queue, allowing senders to push payloads without blocking. 

If the buffer is full (e.g., due to a slow client), subsequent write attempts will block. 

To prevent stalling application workers, use a `select` statement with a `default` case to drop messages or close the connection.

---

### Question 4: sync.Map vs. map RWMutex
*When should you use `sync.Map` instead of a standard map wrapped in a `sync.RWMutex` for client metadata?*

**Answer**:
- Use a **standard map with a `sync.RWMutex`** if the metadata fields are pre-defined and writes are infrequent.
- Use **`sync.Map`** if different goroutines are frequently writing, deleting, and reading dynamic keys concurrently, as it reduces lock contention.

---

### Question 5: Token-Bucket Rate Limiter
*Explain how the token-bucket algorithm regulates message frequency in WebSockets.*

**Answer**:
The token-bucket algorithm maintains a bucket that refills with tokens at a configured rate:
- Each incoming message consumes a token.
- If tokens are available, the message is processed.
- If the bucket is empty, the message is throttled, protecting the server from denial-of-service abuse.

---

### Question 6: HTTP status 1008
*What does the close code 1008 mean? When is it used?*

**Answer**:
Close code `1008` indicates a **Policy Violation**. 

It is used to close connections when a client violates application-level rules (like rate limits or authentication timeouts).

---

### Question 7: atomic.LoadUint64
*Why is it necessary to use `atomic.LoadUint64` to read metrics instead of a direct variable read?*

**Answer**:
Directly reading a variable updated by another thread is a data race. 

Using `atomic.LoadUint64` guarantees a thread-safe, consistent read of the variable's value.

---

### Question 8: context.WithCancel vs context.WithTimeout
*Under what scenarios would you choose `context.WithCancel` over `context.WithTimeout` for a client session context?*

**Answer**:
- Use `context.WithCancel` for connection sessions, as the lifetime is determined by client behavior rather than a fixed time limit.
- Use `context.WithTimeout` to enforce handshake setup limits.

---

### Question 9: Memory leak on context cancel?
*What happens if you allocate a context using `context.WithCancel` but never call the returned `CancelFunc`?*

**Answer**:
It leaks the context allocation in memory, along with any resources associated with it, until the parent context is cancelled.

---

### Question 10: Client structure memory footprint
*How does encapsulating state in a Client structure affect memory consumption per connection?*

**Answer**:
It adds minor memory overhead (a few bytes for channels and contexts). 

However, this encapsulation is critical for managing connection lifecycles and protecting server resources from leaks, offsetting the memory cost.

---

## Summary
- **Wrapping connections** in a `Client` struct keeps connection states, queues, and identification context cohesive.
- **Outbound queues** (send channels) allow workers to push messages to clients without blocking.
- **Context cancellation** coordinates cleanup across reader and writer goroutines to prevent leaks.
- **Use atomic operations** (`sync/atomic`) to update connection metrics concurrently.
- **Enforce rate limits** (`golang.org/x/time/rate`) to protect the server from client abuse.
- Protect shared client metadata from concurrent write access panics.
