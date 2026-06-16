# Module 8: Reading and Writing Messages

Writing high-performance real-time applications requires a solid understanding of how bytes are read from and written to the socket. In Gorilla WebSocket, you can choose between high-level message buffering APIs and low-level streaming APIs. Choosing the wrong API can lead to memory exhaustion, thread deadlocks, or frame corruption.

This module details how to read and write WebSocket messages in Go. We will contrast the high-level `ReadMessage()` and `WriteMessage()` APIs with the streaming `NextReader()` and `NextWriter()` APIs, examine the blocking nature of socket operations, analyze the concurrency constraints of Gorilla connection objects, design a thread-safe write-loop architecture using Go channels, and manage timeouts using deadlines.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Contrast `ReadMessage()` and `NextReader()`** and select the appropriate API based on payload size.
2. **Contrast `WriteMessage()` and `NextWriter()`** and describe the lifecycle of stream writers.
3. **Analyze the blocking behavior** of WebSocket reads and write operations.
4. **Explain the concurrency rules** of Gorilla connections and design a thread-safe write loop.
5. **Enforce read and write deadlines** to manage socket timeouts and prevent resource leaks.
6. **Implement a production-grade, concurrency-safe echo server** featuring large-payload streaming.

---

## 1. Reading Messages: `ReadMessage()` vs `NextReader()`

To receive data over a WebSocket connection, Gorilla provides two reading APIs:

### 1. High-Level: `ReadMessage()`
`ReadMessage()` is a convenience wrapper that reads and buffers the entire message in memory before returning it:

```go
messageType, payload, err := conn.ReadMessage()
```

- **How it works**: It blocks until a complete frame or sequence of fragmented frames with the `FIN` bit set to 1 is received. It allocates a single byte slice on the heap, decodes the payload, and returns it.
- **Best Use Case**: Small, structured payloads (like JSON or protocol buffer messages under 64 KB).
- **The Drawback**: If a client sends a large file (e.g. a 50 MB image), `ReadMessage()` attempts to buffer the entire payload in RAM. If many clients do this simultaneously, it can exhaust server memory and trigger Out-Of-Memory (OOM) crashes.

---

### 2. Low-Level: `NextReader()`
`NextReader()` provides stream-based access to incoming frames:

```go
messageType, reader, err := conn.NextReader()
```

- **How it works**: Instead of buffering the payload in memory, it returns a standard `io.Reader` interface. The application reads bytes sequentially from this reader as they arrive from the network buffer.
- **Best Use Case**: Large payloads, file uploads, log streams, or media files.
- **Benefits**: Allows streaming data directly to disk, a hash calculator, or an external cloud bucket (like AWS S3) without loading the entire payload into RAM, keeping the server's memory footprint constant.

---

## 2. Writing Messages: `WriteMessage()` vs `NextWriter()`

Similarly, Gorilla offers two APIs for writing data:

### 1. High-Level: `WriteMessage()`
`WriteMessage()` writes a complete payload to the socket in a single call:

```go
err := conn.WriteMessage(websocket.TextMessage, []byte("Payload message"))
```

- **How it works**: It allocates a write buffer, wraps the payload in a WebSocket frame, writes it to the socket write buffer, and flushes it.
- **Best Use Case**: Short messages or single-frame updates.

---

### 2. Low-Level: `NextWriter()`
`NextWriter()` provides stream-based writing capabilities:

```go
writer, err := conn.NextWriter(websocket.BinaryMessage)
```

- **How it works**: It returns a standard `io.WriteCloser` interface. The application writes data in chunks using `writer.Write(chunk)`.
- **The Close Rule**: You **must call `writer.Close()`** to complete the message. Closing the writer flushes any remaining bytes and writes the final frame with the `FIN` bit set to 1.
- **Best Use Case**: Generating large dynamic JSON payloads, file downloads, or streaming binary data chunk-by-chunk.

---

## 3. Blocking Behavior and Goroutine Allocation

WebSocket operations are blocking network calls:
- **Blocking Reads**: `conn.ReadMessage()` blocks the executing goroutine until a message arrives, the connection drops, or the read deadline expires.
- **Blocking Writes**: `conn.WriteMessage()` blocks until the payload bytes are written to the kernel's TCP write buffer. If the client is slow and the TCP window size drops to 0, write calls block until space becomes available.

### Goroutine Allocation Pattern
Because reads and writes block, a standard Go concurrency model is applied:
- Assign a **dedicated reader goroutine** to manage the connection read loop.
- If the server needs to push messages asynchronously (e.g., from a message broker), use a separate goroutine to handle writes.

---

## 4. Concurrency Implications & Write-Loop Queue Architecture

The Gorilla connection object (`*websocket.Conn`) is **not thread-safe**.

### The Concurrency Rule:
1. **One Reader**: Only one goroutine can read from the connection at a time.
2. **One Writer**: Only one goroutine can write to the connection at a time.

If multiple goroutines attempt to call write methods (such as `WriteMessage` or `NextWriter`) simultaneously, the client frames will interleave, corrupting the WebSocket frame header parsing states and causing connection crashes.

---

### The Write-Loop Queue Architecture
To allow multiple background worker goroutines to safely send messages over a single connection without lock contention, you can implement a channel-based write-loop:

```text
Worker Goroutine 1 ──► [ Push to Write Channel ] 
Worker Goroutine 2 ──► [ (Buffered Queue)      ] ──► Dedicated Write Loop Goroutine ──► Write to TCP Socket
Worker Goroutine 3 ──► [                       ]
```

Instead of writing directly to the connection, workers push payloads to a channel. A single, dedicated write-loop goroutine reads from this channel and writes to the connection sequentially, guaranteeing thread safety.

---

## 5. Connection Deadlines

To prevent stale or half-open connections from leaking server resources, you must enforce timeouts using deadlines.

### Read and Write Deadlines:
- **`SetWriteDeadline(time.Time)`**: Sets a timeout for write operations. If a write call cannot complete within this window (e.g., due to network congestion), it returns a timeout error, prompting connection cleanup.
- **`SetReadDeadline(time.Time)`**: Sets a timeout for read operations. If no data is received within this window, the read loop fails.

### Extending Deadlines
Deadlines are absolute points in time. You must **extend the deadline after every successful read or write operation** to keep the connection active.

```go
// Extend read deadline on successful message read
conn.SetReadDeadline(time.Now().Add(pongWait))
```

---

## 6. Exercises: Concurrency-Safe Streaming Echo Server

In this exercise, you will build a production-grade Echo server that implements a channel-based write queue, enforces read and write deadlines, and uses streaming readers and writers to handle large payloads safely.

### Complete Go Server Implementation:

```go
package main

import (
	"io"
	"log"
	"net/http"
	"time"
	"github.com/gorilla/websocket"
)

const (
	writeWait      = 10 * time.Second
	pongWait       = 60 * time.Second
	pingPeriod     = (pongWait * 9) / 10
	maxMessageSize = 10 * 1024 * 1024 // Cap payloads at 10 MB
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// Client represents a connected client
type Client struct {
	conn      *websocket.Conn
	writeChan chan []byte // Channel to queue outbound messages
}

// WriteSafe schedules a message for transmission
func (c *Client) WriteSafe(data []byte) {
	c.writeChan <- data
}

func handleStreamingEcho(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("[Upgrade Error]:", err)
		return
	}

	client := &Client{
		conn:      conn,
		writeChan: make(chan []byte, 256), // Buffered channel queue
	}
	defer client.conn.Close()

	// Enforce limits and deadlines
	client.conn.SetReadLimit(maxMessageSize)
	client.conn.SetReadDeadline(time.Now().Add(pongWait))
	client.conn.SetPongHandler(func(string) error {
		client.conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	// Start the dedicated writer goroutine
	go client.startWriteLoop()

	// Start the reader loop
	client.startReadLoop()
}

// startReadLoop manages the connection read loop
func (c *Client) startReadLoop() {
	for {
		// 1. Get a streaming reader for the incoming frame
		messageType, reader, err := c.conn.NextReader()
		if err != nil {
			log.Println("[Read Loop] Connection closed:", err)
			break
		}

		// 2. Extend the read deadline on successful frame detection
		c.conn.SetReadDeadline(time.Now().Add(pongWait))

		// 3. Get a streaming writer to echo the payload back
		writer, err := c.conn.NextWriter(messageType)
		if err != nil {
			log.Println("[Read Loop] Failed to allocate writer:", err)
			break
		}

		// 4. Set a write deadline on the connection
		c.conn.SetWriteDeadline(time.Now().Add(writeWait))

		// 5. Stream the payload directly from reader to writer
		// io.Copy reads chunks from the network and writes them to the socket buffer
		_, err = io.Copy(writer, reader)
		if err != nil {
			log.Println("[Read Loop] Streaming failed:", err)
			writer.Close()
			break
		}

		// 6. Close the writer to flush the frame and write the FIN bit
		err = writer.Close()
		if err != nil {
			log.Println("[Read Loop] Failed to close writer:", err)
			break
		}
	}
}

// startWriteLoop runs as a dedicated writer goroutine
func (c *Client) startWriteLoop() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.conn.Close() // Force socket closure on write failure
	}()

	for {
		select {
		case data, ok := <-c.writeChan:
			// Set write timeout
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				// The channel was closed
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			// Write outbound message
			err := c.conn.WriteMessage(websocket.TextMessage, data)
			if err != nil {
				log.Println("[Write Loop] Write failed:", err)
				return
			}

		case <-ticker.C:
			// Send Ping heartbeat
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			err := c.conn.WriteMessage(websocket.PingMessage, nil)
			if err != nil {
				log.Println("[Write Loop] Ping failed:", err)
				return
			}
		}
	}
}

func main() {
	http.HandleFunc("/ws", handleStreamingEcho)
	log.Println("[Streaming Gateway] Running on :8080...")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal(err)
	}
}
```

---

### Line-by-Line Code Walkthrough (Echo Server):

- **Line 26**: `writeChan: make(chan []byte, 256)`
  Initializes a buffered channel queue to store outbound payloads. Senders push payloads to this channel, and the write loop consumes them.
- **Line 31**: `func (c *Client) WriteSafe(data []byte)`
  A helper method that allows workers to safely queue outbound messages.
- **Line 46**: `client.conn.SetReadLimit(maxMessageSize)`
  Sets a maximum message size limit to protect the server from memory exhaustion attacks.
- **Line 53**: `go client.startWriteLoop()`
  Spawns a dedicated writer goroutine to process outbound messages and heartbeat pings sequentially, guaranteeing write thread safety.
- **Line 62**: `messageType, reader, err := c.conn.NextReader()`
  A blocking call that waits for the client to send a frame, returning a stream reader (`io.Reader`) to read bytes sequentially as they arrive.
- **Line 70**: `writer, err := c.conn.NextWriter(messageType)`
  Returns a stream writer (`io.WriteCloser`) to write the response payload to the socket in chunks.
- **Line 79**: `_, err = io.Copy(writer, reader)`
  Streams data directly from the read buffer to the write buffer in chunks (using internal 32 KB allocations), keeping the server's memory footprint minimal regardless of payload size.
- **Line 87**: `err = writer.Close()`
  Clushes the write buffer and writes the final frame with `FIN = 1`.

---

## 7. Common Reading & Writing Pitfalls

### 1. Forgetting to Close `NextWriter()`
- **The Mistake**: Writing bytes using `NextWriter()` but forgetting to call `Close()`:
  ```go
  w, _ := conn.NextWriter(websocket.TextMessage)
  w.Write([]byte("Hello"))
  // Close is missing!
  ```
- **The Result**: The message remains open and is never flushed to the socket. When you attempt to call `NextWriter()` again, the connection throws an error.
- **The Fix**: Always call `writer.Close()` (or use deferred close statements) when writing is complete.

### 2. Concurrent Write Panics
- **The Mistake**: Calling write methods from multiple goroutines simultaneously.
- **The Result**: Frame corruption and connection crashes.
- **The Fix**: Implement a channel-based write queue to serialize writes.

---

## 8. Technical Interview Questions

### Question 1: ReadMessage vs. NextReader
*What is the difference between `ReadMessage()` and `NextReader()`? When should you use each?*

**Answer**:
- `ReadMessage()` is a high-level helper that buffers the entire payload in memory before returning. Use it for small, structured messages (like JSON under 64 KB).
- `NextReader()` is a low-level streaming API that returns an `io.Reader`. Use it to process large payloads (like file uploads) chunk-by-chunk to prevent memory bloat.

---

### Question 2: Gorilla Concurrency Rules
*Explain the concurrency rules of the Gorilla WebSocket connection object. How do you implement thread-safe writes?*

**Answer**:
Gorilla connections are not thread-safe. 

Only one goroutine can read, and only one goroutine can write to the connection at a time. 

To implement thread-safe writes, design a write-loop architecture where workers push payloads to a Go channel, and a dedicated writer goroutine consumes from the channel and writes to the connection sequentially.

---

### Question 3: Forgetting to close NextWriter
*What happens if you fail to call `Close()` on the writer returned by `NextWriter()`?*

**Answer**:
The payload remains buffered and is not flushed to the socket. 

Subsequent attempts to open a new reader or writer on the connection will fail and return errors.

---

### Question 4: Deadlines Behavior
*What happens to a blocked `ReadMessage()` call when the connection's read deadline expires?*

**Answer**:
The read call immediately unblocks and returns an I/O timeout error, prompting the handler to clean up the connection.

---

### Question 5: Resetting deadlines
*Why must read and write deadlines be reset continuously after successful operations?*

**Answer**:
Deadlines are absolute points in time. If you do not reset them, the deadline remains fixed, and the connection will time out even if it is active.

---

### Question 6: Read Limit Protection
*How does `SetReadLimit(size)` protect your server from Out-Of-Memory (OOM) crashes?*

**Answer**:
It sets a maximum limit on incoming message size. 

If a frame exceeds this limit, the connection returns a protocol error and closes, preventing malicious clients from sending huge payloads to crash the server.

---

### Question 7: WriteMessage vs. NextWriter
*What is the difference between `WriteMessage()` and `NextWriter()`?*

**Answer**:
- `WriteMessage()` is a convenience helper that writes a complete payload in a single call.
- `NextWriter()` returns an `io.WriteCloser` to write payloads in chunks, which is useful for streaming dynamically generated data.

---

### Question 8: NextReader block
*Does calling `NextReader()` block if no message is available?*

**Answer**:
Yes. `NextReader()` blocks until a new message header frame is received, an error occurs, or the read deadline expires.

---

### Question 9: Gorilla default buffer pools
*What is the default behavior of Gorilla if no `WriteBufferPool` is configured?*

**Answer**:
It allocates a new write buffer on the heap for each connection, which can increase Garbage Collection pressure under high load.

---

### Question 10: io.Copy efficiency
*Why is `io.Copy(writer, reader)` memory-efficient when processing WebSocket streams?*

**Answer**:
It streams data in small chunks (using internal 32 KB allocations) rather than buffering the entire payload in RAM, keeping the memory footprint constant regardless of payload size.

---

## Summary
- **ReadMessage() and WriteMessage()** are convenience helpers for small payloads.
- **NextReader() and NextWriter()** are low-level streaming APIs for large payloads.
- **Gorilla connections** are not thread-safe; serialize writes using a channel-based write queue.
- **Enforce deadlines** and reset them continuously to manage connection timeouts.
- **Set read limits** to protect your server from memory exhaustion attacks.
