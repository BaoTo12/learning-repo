# Module 23: Performance Optimization

Deploying a WebSocket server that supports thousands of concurrent connections requires minimizing CPU overhead and heap memory allocations. In Go, high memory allocation rates generate Garbage Collection (GC) pressure, triggering CPU spikes and latency pauses. When broadcasting messages to thousands of users simultaneously, serializing and framing the same payload multiple times wastes CPU cycles and memory.

This module details how to optimize the performance of Go WebSocket gateways. We will analyze memory allocations and GC pressure, reuse buffers using Gorilla's `WriteBufferPool`, optimize broadcasts using `websocket.PreparedMessage`, profile applications using `pprof`, and complete a hands-on exercise to optimize a slow server.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Analyze memory allocations** and mitigate GC latency pressure.
2. **Implement custom write buffer pools** to recycle socket buffers.
3. **Use `PreparedMessage`** to optimize concurrent message broadcasts.
4. **Instrument Go applications** with benchmarks and `pprof` profiling.
5. **Evaluate compression overheads** versus network bandwidth savings.
6. **Optimize an existing WebSocket server** for production performance.

---

## 1. Memory Allocations & GC Latency

Unlike stateless APIs, WebSockets maintain open sockets that process continuous read and write loops.

Each client connection requires memory allocations:
- **Socket Buffers**: The OS allocates TCP buffers, and Gorilla allocates application-level read/write buffers (usually 4 KB each) to stage data frames.
- **Message Slices**: Reading a message allocates a byte slice on the heap. If your gateway handles 50,000 clients receiving 10 messages per second, the server executes 500,000 heap allocations per second.

```text
  No Pooling:
  Client Write Request ──► Allocate 4KB Heap Buffer ──► Write Frame ──► Discard (GC Sweep)

  Buffer Pooling:
  Client Write Request ──► Rent 4KB Buffer from Pool ──► Write Frame ──► Return to Pool
```

### The Cost of Garbage Collection (GC)
As heap allocations increase, Go's Garbage Collector must run sweep cycles more frequently, consuming CPU cycles and triggering stop-the-world (STW) pauses. This can lead to latency spikes and connection drops on busy gateways.

---

## 2. Optimizing Allocations with Buffer Pools

Gorilla WebSocket supports recycling write buffers using custom buffer pools. Assigning a pool to the `WriteBufferPool` property in the `Upgrader` allows the gateway to reuse memory, reducing heap allocations during writes.

### Implementing `websocket.BufferPool` using `sync.Pool`:

```go
package main

import (
	"sync"
	"github.com/gorilla/websocket"
)

// Define a custom buffer pool struct
type CustomBufferPool struct {
	pool sync.Pool
}

func NewCustomBufferPool(bufferSize int) *CustomBufferPool {
	return &CustomBufferPool{
		pool: sync.Pool{
			New: func() interface{} {
				// Allocate a new byte slice of the specified size
				return make([]byte, bufferSize)
			},
		},
	}
}

// Get implements the websocket.BufferPool interface
func (bp *CustomBufferPool) Get() interface{} {
	return bp.pool.Get()
}

// Put implements the websocket.BufferPool interface
func (bp *CustomBufferPool) Put(buffer interface{}) {
	bp.pool.Put(buffer)
}
```

By assigning this pool to the upgrader:
```go
var upgrader = websocket.Upgrader{
	WriteBufferPool: NewCustomBufferPool(4096),
}
```
The server will recycle write buffers instead of allocating them on the heap for each write operation, reducing memory allocations to near-zero.

---

## 3. PreparedMessage for Concurrent Broadcasts

In a chat room or trading gateway, the same message is broadcast to thousands of clients:
```go
// Inefficient Broadcast Loop
for client := range room.clients {
    // Under the hood, WriteMessage serializes, masks, and encapsulates
    // the payload into a frame for EVERY client, wasting CPU cycles.
    client.conn.WriteMessage(websocket.TextMessage, rawPayload)
}
```
If you broadcast to 10,000 clients, the server encapsulates the message 10,000 times.

### The Solution: `PreparedMessage`
A `PreparedMessage` serializes and caches the WebSocket frame layout once. Sending the prepared message to clients bypasses the encapsulation steps, reducing CPU overhead during broadcasts:

```go
// 1. Prepare message once
preparedMsg, err := websocket.NewPreparedMessage(websocket.TextMessage, rawPayload)
if err != nil {
    return err
}

// 2. Broadcast prepared message
for client := range room.clients {
    // Bypasses framing and masking steps
    client.conn.WritePreparedMessage(preparedMsg)
}
```

This optimization reduces CPU overhead, enabling the server to handle larger broadcast spikes.

---

## 4. Profiling and Benchmarking

To optimize performance, you must measure your application's resource usage:

### 1. Go Benchmarks (`go test -bench`)
Create benchmark tests to measure execution speeds and heap allocation rates:
```go
func BenchmarkBroadcast(b *testing.B) {
	payload := []byte("Hello Benchmark")
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = websocket.NewPreparedMessage(websocket.TextMessage, payload)
	}
}
```
Run benchmarks from the command line:
```bash
go test -bench=. -benchmem
```

---

### 2. Profiling with pprof
Import `net/http/pprof` to register profiling endpoints:
```go
import _ "net/http/pprof"

func main() {
    // Starts HTTP server exposing profiling endpoints under /debug/pprof
    go func() {
        log.Println(http.ListenAndServe("localhost:6060", nil))
    }()
}
```
Use the profiling tool to analyze CPU or memory allocations:
```bash
# Analyze memory profile using the interactive CLI
go tool pprof http://localhost:6060/debug/pprof/allocs
```

---

## 5. Exercises: Optimizing an Insecure Server

In this exercise, you will optimize a slow WebSocket server that is vulnerable to memory leaks, GC pressure, and CPU starvation during broadcasts.

### The Inefficient Server:

```go
package main

import (
	"log"
	"net/http"
	"sync"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
	// SLOW: No WriteBufferPool assigned, allocating buffers on every write
}

type Client struct {
	conn *websocket.Conn
	send chan []byte
}

type ChatHub struct {
	clients map[*Client]bool
	mu      sync.RWMutex
}

func (h *ChatHub) Broadcast(payload []byte) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	for client := range h.clients {
		// SLOW: Serializes and frames payload for each client connection
		client.conn.WriteMessage(websocket.TextMessage, payload)
	}
}

func handleWS(hub *ChatHub, w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	client := &Client{conn: conn, send: make(chan []byte, 256)}
	
	hub.mu.Lock()
	hub.clients[client] = true
	hub.mu.Unlock()

	defer func() {
		hub.mu.Lock()
		delete(hub.clients, client)
		hub.mu.Unlock()
		conn.Close()
	}()

	for {
		_, payload, err := conn.ReadMessage()
		if err != nil {
			break
		}
		hub.Broadcast(payload)
	}
}

func main() {
	hub := &ChatHub{clients: make(map[*Client]bool)}
	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		handleWS(hub, w, r)
	})
	http.ListenAndServe(":8080", nil)
}
```

---

### The Optimized Server:

Below is the optimized server implementing custom buffer pooling, `PreparedMessage` broadcasts, and `pprof` profiling instrumentation:

```go
package main

import (
	"log"
	"net/http"
	_ "net/http/pprof" // 1. Import pprof for profiling
	"sync"
	"github.com/gorilla/websocket"
)

// 2. Custom Buffer Pool implementation
type CustomBufferPool struct {
	pool sync.Pool
}

func NewCustomBufferPool(size int) *CustomBufferPool {
	return &CustomBufferPool{
		pool: sync.Pool{
			New: func() interface{} {
				return make([]byte, size)
			},
		},
	}
}

func (bp *CustomBufferPool) Get() interface{} {
	return bp.pool.Get()
}

func (bp *CustomBufferPool) Put(buf interface{}) {
	bp.pool.Put(buf)
}

var secureUpgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
	// 3. Assign custom write buffer pool to reuse memory
	WriteBufferPool: NewCustomBufferPool(4096),
}

type Client struct {
	conn *websocket.Conn
	send chan []byte
}

type ChatHub struct {
	clients map[*Client]bool
	mu      sync.RWMutex
}

// 4. Optimized Broadcast using PreparedMessage
func (h *ChatHub) Broadcast(payload []byte) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	if len(h.clients) == 0 {
		return
	}

	// Prepare the message frame once
	preparedMsg, err := websocket.NewPreparedMessage(websocket.TextMessage, payload)
	if err != nil {
		log.Println("[Error] PreparedMessage generation failed:", err)
		return
	}

	for client := range h.clients {
		// Send prepared message directly to client, bypassing framing steps
		err := client.conn.WritePreparedMessage(preparedMsg)
		if err != nil {
			log.Println("[Write Error] Failed to write prepared message:", err)
		}
	}
}

func handleWS(hub *ChatHub, w http.ResponseWriter, r *http.Request) {
	conn, err := secureUpgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	client := &Client{conn: conn, send: make(chan []byte, 256)}
	
	hub.mu.Lock()
	hub.clients[client] = true
	hub.mu.Unlock()

	defer func() {
		hub.mu.Lock()
		delete(hub.clients, client)
		hub.mu.Unlock()
		conn.Close()
	}()

	for {
		_, payload, err := conn.ReadMessage()
		if err != nil {
			break
		}
		hub.Broadcast(payload)
	}
}

func main() {
	// 5. Start pprof server in a background goroutine
	go func() {
		log.Println("[Profiling] Starting pprof server on localhost:6060...")
		if err := http.ListenAndServe("localhost:6060", nil); err != nil {
			log.Println("[Profiling Error] Server failed:", err)
		}
	}()

	hub := &ChatHub{clients: make(map[*Client]bool)}
	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		handleWS(hub, w, r)
	})

	log.Println("[Gateway] Running optimized server on :8080...")
	http.ListenAndServe(":8080", nil)
}
```

---

### Line-by-Line Code Walkthrough (Optimized Server):

- **Line 5**: `_ "net/http/pprof"`
  Imports the profiling package, registering profiling endpoints under `/debug/pprof`.
- **Line 10**: `type CustomBufferPool struct { ... }`
  Defines the custom buffer pool struct to implement `websocket.BufferPool` using `sync.Pool`.
- **Line 35**: `WriteBufferPool: NewCustomBufferPool(4096)`
  Assigns our custom buffer pool to the upgrader to reuse write buffers.
- **Line 60**: `preparedMsg, err := websocket.NewPreparedMessage(...)`
  Prepares and caches the message frame layout once, bypassing framing steps on subsequent writes.
- **Line 68**: `client.conn.WritePreparedMessage(preparedMsg)`
  Sends the prepared message, reducing CPU and memory overhead during broadcasts.
- **Line 103**: `go func() { http.ListenAndServe("localhost:6060", nil) }()`
  Starts the pprof profiling server in the background.

---

## 6. Technical Interview Questions

### Question 1: PreparedMessage benefits
*How does `websocket.PreparedMessage` optimize concurrent broadcasts, and what are its trade-offs?*

**Answer**:
- **Benefits**: It serializes, frames, and masks the payload once, caching the layout so writes bypass these framing steps, reducing CPU overhead during broadcasts.
- **Trade-offs**: It requires framing message payloads beforehand, making it unsuitable for personalized messages (e.g. including client usernames in payloads).

---

### Question 2: WriteBufferPool interface
*What interface must be implemented to configure `WriteBufferPool` in Gorilla WebSocket?*

**Answer**:
It must implement the `websocket.BufferPool` interface:
```go
type BufferPool interface {
    Get() interface{}
    Put(interface{})
}
```

---

### Question 3: sync.Pool GC behavior
*Explain how the Garbage Collector interacts with Go's `sync.Pool`.*

**Answer**:
Items in `sync.Pool` are automatically cleared during Garbage Collection cycles. 

This prevents pools from leaking memory, but means cached buffers must be re-allocated after GC sweeps.

---

### Question 4: pprof profiling allocs
*How do you profile memory allocations on a running Go application using pprof?*

**Answer**:
Start the profiling server and run the pprof tool from the CLI:
`go tool pprof http://localhost:6060/debug/pprof/allocs`
This starts the interactive CLI to identify memory allocation bottlenecks.

---

### Question 5: compression trade-offs
*Evaluate the CPU and memory trade-offs of enabling payload compression (`permessage-deflate`).*

**Answer**:
- **Bandwidth**: Compression reduces payload sizes, saving network bandwidth.
- **Overhead**: Each compressed connection requires allocating slide window buffers, increasing memory usage per connection and CPU overhead. Disable compression if your gateway handles high-concurrency or high-frequency traffic.

---

### Question 6: Go Benchmarks flags
*What CLI flags must be passed to `go test` to measure memory allocation rates during benchmarks?*

**Answer**:
Pass the `-bench` and `-benchmem` flags:
`go test -bench=. -benchmem`

---

### Question 7: sync.Pool slice allocation type
*Why does `CustomBufferPool` return `interface{}` instead of direct byte slices?*

**Answer**:
Go's `sync.Pool` works with generic interfaces (`interface{}`), requiring type assertions when retrieving and returning values.

---

### Question 8: Handshake timeout cost
*Why does omitting `HandshakeTimeout` in Upgrader options invite slow-loris attacks?*

**Answer**:
Omitting the timeout allows slow clients to open sockets and delay sending handshake headers, exhausting server file descriptors and thread resources.

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
- **Reduce heap allocations** to minimize Garbage Collection pressure and prevent latency spikes.
- **Implement buffer pools** (`sync.Pool`) to recycle read/write buffers.
- **Use `PreparedMessage`** to cache frame layouts and optimize concurrent broadcasts.
- **Instrument applications** with benchmarks and `pprof` to identify performance bottlenecks.
- **Evaluate compression trade-offs** before enabling it on busy gateways.
- Protect shared client metadata from concurrent write access panics.
