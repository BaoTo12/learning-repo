# Module 9: Gorilla Concurrency Model

Writing concurrent systems in Go requires understanding how state is shared between threads. In Gorilla WebSocket, connections are not thread-safe. If multiple goroutines attempt to read or write to a connection simultaneously, the connection will crash with concurrency panics.

This module details the Gorilla concurrency model. We will explore the One-Reader and One-Writer constraints, analyze the internal mechanics of concurrent write panics, implement synchronization strategies using both Mutexes and Go Channels, compare their trade-offs in a detailed matrix, and walk through exercises to refactor and fix broken concurrent code.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the One-Reader and One-Writer constraints** of Gorilla WebSocket connections.
2. **Describe the mechanics of frame corruption** and trace concurrent write panics.
3. **Implement Mutex-based synchronization** to serialize connection writes.
4. **Implement a Channel-based write loop** to handle outbound payloads asynchronously.
5. **Evaluate the trade-offs** between Mutexes and Channels under high load.
6. **Refactor thread-unsafe code** into thread-safe implementations.

---

## 1. The Core Concurrency Constraints

To prevent data races and protocol corruption, Gorilla WebSocket enforces the following concurrency constraints:

### 1. The One-Reader Rule
- **The Constraint**: At any given moment, **only one goroutine can read from the connection**.
- You cannot have two concurrent goroutines calling `ReadMessage()` or `NextReader()` on the same connection.
- If multiple goroutines try to read concurrently, the connection's read buffer state will corrupt, leading to protocol exceptions.

### 2. The One-Writer Rule
- **The Constraint**: At any given moment, **only one goroutine can write to the connection**.
- You cannot have two concurrent goroutines calling `WriteMessage()` or `NextWriter()` on the same connection.
- If multiple goroutines try to write concurrently, the connection throws a runtime panic.

### What is Permitted? (Bidirectional Safety)
These rules do **not** mean you cannot read and write concurrently. 
- You can have **one goroutine reading** and **one goroutine writing** to the same connection simultaneously. This is thread-safe and is the standard pattern used for bidirectional, full-duplex communication.

---

## 2. Why Concurrent Writes Cause Frame Corruption and Panics

To understand why Gorilla enforces the One-Writer rule, let us look at how frames are written to the socket.

### The Mechanics of Frame Corruption
Writing a WebSocket frame is a multi-step operation:
1. Write the frame header (FIN bit, Opcode, Payload Length).
2. Write the payload data to the connection buffer.

If two goroutines (Goroutine A and Goroutine B) attempt to write concurrently without synchronization, their write calls will interleave at the network buffer level:

```text
Unsynchronized Write Stream:
[ Header A ] [ Header B ] [ Payload A (Part 1) ] [ Payload B ] [ Payload A (Part 2) ]
```

When the client browser attempts to decode this stream, it reads `Header B` as if it were part of `Payload A`'s data, corrupting the payload. The client then attempts to parse the subsequent bytes as a new frame header. Since the bytes do not match a valid header format, the client logs a protocol error and terminates the connection.

---

### The Gorilla Concurrent Write Panic
To prevent this corruption, Gorilla tracks active writes using an internal state variable. If it detects a concurrent write, it throws a runtime panic:

```text
panic: concurrent write to websocket connection

goroutine 24 [running]:
github.com/gorilla/websocket.(*Conn).write(0xc0000a6080, 0x1, 0xc00010c000, 0xc, 0xc00010c000)
    /go/pkg/mod/github.com/gorilla/websocket@v1.5.3/conn.go:374 +0x4c5
github.com/gorilla/websocket.(*Conn).WriteMessage(0xc0000a6080, 0x1, {0xc00010c000, 0xc, 0xc})
    /go/pkg/mod/github.com/gorilla/websocket@v1.5.3/conn.go:765 +0x50
```

---

## 3. Synchronization Strategy 1: Mutexes (The Simple Lock)

The simplest way to satisfy the One-Writer rule is to serialize write operations using a **`sync.Mutex`** lock.

### The Mutex Wrapper Pattern:

```go
package main

import (
	"sync"
	"time"
	"github.com/gorilla/websocket"
)

type SafeConn struct {
	conn *websocket.Conn
	mu   sync.Mutex // Protects write operations
}

func (s *SafeConn) WriteTextMessage(payload []byte, timeout time.Duration) error {
	s.mu.Lock()
	defer s.mu.Unlock() // Ensure lock release on return

	// Enforce write deadline
	s.conn.SetWriteDeadline(time.Now().Add(timeout))
	return s.conn.WriteMessage(websocket.TextMessage, payload)
}
```

- **Pros**: Simple to write and guarantees safety.
- **Cons**: Write calls block the executing goroutine until the lock is acquired. If a slow client causes the connection buffer to fill up, the write call will block, holding the lock and causing other goroutines to block.

---

## 4. Synchronization Strategy 2: Go Channels (The Writer Loop)

An alternative approach is the **Writer Loop** pattern, which aligns with Go's concurrency philosophy: 
> *"Do not communicate by sharing memory; instead, share memory by communicating."*

### The Writer Loop Pattern:

```go
package main

import (
	"log"
	"time"
	"github.com/gorilla/websocket"
)

type HubClient struct {
	conn      *websocket.Conn
	writeChan chan []byte // Channel buffer
}

func (hc *HubClient) Send(payload []byte) {
	hc.writeChan <- payload // Non-blocking write queue push
}

func (hc *HubClient) startWriterLoop(writeWait time.Duration) {
	defer hc.conn.Close()

	for payload := range hc.writeChan {
		hc.conn.SetWriteDeadline(time.Now().Add(writeWait))
		err := hc.conn.WriteMessage(websocket.TextMessage, payload)
		if err != nil {
			log.Println("[Writer Loop] Write failed:", err)
			return
		}
	}
}
```

- **Pros**: Senders push payloads to the channel and return immediately, without blocking. Writes are serialized by a single dedicated writer goroutine, eliminating lock contention.
- **Cons**: Requires managing channel lifecycles and buffer sizes.

---

## 5. Mutex vs. Channel Comparison

The table below contrasts the characteristics of both synchronization strategies:

| Metric | Mutex-Based Locking | Channel-Based Writer Loop |
| :--- | :--- | :--- |
| **Complexity** | Low (Minimal boilerplate) | Moderate (Requires channel lifecycle) |
| **Worker Blocking** | High (Blocks on lock acquisition) | Low (Non-blocking with buffered channels) |
| **Allocation Cost** | Low (No channel allocation) | Moderate (Allocates channel and buffers) |
| **Deadlock Risk** | Moderate | Low |
| **Best Use Case** | Low-concurrency, simple architectures | High-throughput, real-time message hubs |

---

## 6. Exercises: Fixing Broken Concurrent Code

In this exercise, you will refactor a thread-unsafe real-time server that crashes under load due to concurrent write panics.

### The Broken Code:

```go
package main

import (
	"fmt"
	"log"
	"net/http"
	"time"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

func handleTicker(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	defer conn.Close()

	// CRITICAL BUG: This loops spawns 10 concurrent goroutines
	// that all attempt to write directly to the same connection,
	// triggering concurrent write panics.
	for i := 1; i <= 10; i++ {
		go func(workerID int) {
			for {
				msg := []byte(fmt.Sprintf("Worker %d tick at %s", workerID, time.Now().String()))
				err := conn.WriteMessage(websocket.TextMessage, msg)
				if err != nil {
					return
				}
				time.Sleep(1 * time.Second)
			}
		}(i)
	}

	// Wait forever to keep connection alive
	select {}
}

func main() {
	http.HandleFunc("/ws", handleTicker)
	http.ListenAndServe(":8080", nil)
}
```

---

### Refactoring Step 1: Fixing with Mutex Wrappers
To fix this using a mutex, wrap the connection in a struct and lock write access:

```go
package main

import (
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// Thread-safe wrapper struct
type SafeConnection struct {
	conn *websocket.Conn
	mu   sync.Mutex
}

func (sc *SafeConnection) WriteMessage(messageType int, data []byte) error {
	sc.mu.Lock()
	defer sc.mu.Unlock() // Serialize write operations
	return sc.conn.WriteMessage(messageType, data)
}

func handleTickerMutex(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	
	sc := &SafeConnection{conn: conn}
	defer sc.conn.Close()

	for i := 1; i <= 10; i++ {
		go func(workerID int) {
			for {
				msg := []byte(fmt.Sprintf("Worker %d tick at %s", workerID, time.Now().String()))
				// Use the thread-safe wrapper method
				err := sc.WriteMessage(websocket.TextMessage, msg)
				if err != nil {
					return
				}
				time.Sleep(1 * time.Second)
			}
		}(i)
	}

	select {}
}
```

---

### Refactoring Step 2: Fixing with a Channel-Based Writer Loop
To fix this using channels, implement a write-loop to serialize connection writes:

```go
package main

import (
	"fmt"
	"log"
	"net/http"
	"time"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

type ChannelClient struct {
	conn      *websocket.Conn
	writeChan chan []byte
}

func (c *ChannelClient) sendLoop() {
	defer c.conn.Close()
	// Single writer loop consumes messages and writes them to the connection
	for msg := range c.writeChan {
		err := c.conn.WriteMessage(websocket.TextMessage, msg)
		if err != nil {
			log.Println("[Writer Loop] Write failed:", err)
			return
		}
	}
}

func handleTickerChannel(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}

	client := &ChannelClient{
		conn:      conn,
		writeChan: make(chan []byte, 256),
	}
	
	// Start the writer loop goroutine
	go client.sendLoop()

	for i := 1; i <= 10; i++ {
		go func(workerID int) {
			for {
				msg := []byte(fmt.Sprintf("Worker %d tick at %s", workerID, time.Now().String()))
				// Push message to the channel queue instead of writing directly to connection
				client.writeChan <- msg
				time.Sleep(1 * time.Second)
			}
		}(i)
	}

	select {}
}
```

---

## 7. Common Concurrency Pitfalls & Troubleshooting

### Pitfall A: Channel Buffer Saturation (Saturating Senders)
* **The Problem**: You implement a channel-based write loop with a channel size of `256`. Under heavy traffic, client connections slow down, the channel queue fills up, and worker goroutines block when pushing messages to the channel:
  `client.writeChan <- msg` (Blocks here!)
* **Why it happens**: If the channel is full, Go blocks the sender until the receiver reads a message. This can stall your application workers.
* **The Fix**: Use a `select` statement with a `default` case to drop messages or log warnings when the channel is full:
  ```go
  select {
  case client.writeChan <- msg:
      // Message queued successfully
  default:
      // Channel is full, handle overflow
      log.Println("[Warning] Write queue full, dropping message")
  }
  ```

---

## 8. Technical Interview Questions

### Question 1: Gorilla Write Concurrency
*Why does Gorilla WebSocket forbid concurrent writes on the same connection?*

**Answer**:
WebSocket frames consist of a header followed by payload data. 

If multiple goroutines write concurrently without synchronization, their write calls will interleave at the network buffer level, corrupting the frame headers. 

To prevent this corruption, Gorilla tracks active writes and throws a runtime panic if a concurrent write is detected.

---

### Question 2: Concurrent Read and Write
*Can one goroutine read from a connection while another writes to it concurrently?*

**Answer**:
Yes. Gorilla permits having **one goroutine reading** and **one goroutine writing** to the same connection concurrently, supporting bidirectional, full-duplex communication.

---

### Question 3: Mutex vs. Channel Performance
*Under what scenarios would you choose a Channel-based write loop over a Mutex lock wrapper?*

**Answer**:
- Choose a **Mutex wrapper** for low-concurrency, simple architectures where write operations are short and worker blocking is acceptable.
- Choose a **Channel-based write loop** for high-throughput, real-time message hubs where you need to prevent worker blocking and handle slow client timeouts gracefully.

---

### Question 4: Concurrent Read panic?
*Does Gorilla throw a runtime panic if multiple goroutines read concurrently?*

**Answer**:
No. Unlike writes, Gorilla does not throw a panic for concurrent reads. 

However, concurrent reads will corrupt the connection's internal buffer state, leading to parsing errors and protocol exceptions.

---

### Question 5: Mutex blocking bottleneck
*Why does a Mutex lock wrapper create a performance bottleneck when writing to slow clients?*

**Answer**:
If a client is slow, the write call blocks until the TCP window size increases, holding the mutex lock. 

Any other goroutines attempting to write to that connection will block on the lock, stalling application workers.

---

### Question 6: sync.Mutex lock deferred release
*Why is it critical to use `defer s.mu.Unlock()` in a Mutex-locked write method?*

**Answer**:
Using `defer` guarantees the lock is released even if the write call throws an error or panics, preventing deadlocks.

---

### Question 7: Select default behavior
*What does a `default` case inside a channel send `select` block accomplish?*

**Answer**:
It makes the channel send operation non-blocking. 

If the channel queue is full, the send falls back to the `default` case, preventing the worker goroutine from blocking.

---

### Question 8: Safe connection close?
*How do you safely shut down a Channel-based client connection to prevent panic writes on closed channels?*

**Answer**:
1. Close the write channel to notify the writer loop to shut down.
2. In the writer loop, read remaining messages from the channel.
3. Once the channel is empty, write a Close frame and close the connection.

---

### Question 9: Concurrency safety standard library?
*Does Go's standard library `net.Conn` connection object support concurrent writes?*

**Answer**:
Yes, Go's standard `net.Conn` supports concurrent writes. 

However, Gorilla's WebSocket framing wrapper sits on top of this connection, introducing state variables that make concurrent writes unsafe.

---

### Question 10: Sizing channel buffers
*How do you size channel buffers for WebSocket clients?*

**Answer**:
Channel buffer size depends on your traffic patterns:
- Set the buffer size to handle peak traffic spikes (e.g. 256 messages).
- If the buffer is consistently full, it indicates the client is slow or the connection is congested, requiring a close or drop policy.

---

## Summary
- **Gorilla connections** are not thread-safe; serialize writes using Mutexes or channels.
- **Concurrent writes** interleave bytes at the network buffer level, corrupting frame headers and triggering panics.
- **Mutexes** serialize writes by locking connection access, which is simple but can block workers on slow connections.
- **Go Channels** queue outbound payloads, which are written sequentially by a dedicated writer goroutine, keeping workers non-blocking.
- Use a `select` statement with a `default` case to handle full write queues safely.
