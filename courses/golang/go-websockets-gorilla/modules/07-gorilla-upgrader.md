# Module 7: Gorilla Upgrader

The entry point for any WebSocket connection in Go is the **`websocket.Upgrader`**. It acts as the gatekeeper for your real-time application: it validates incoming HTTP headers, negotiates subprotocols and extensions, allocates connection buffers, enforces CORS origin rules, and hijacks the raw TCP socket from the Go HTTP server engine.

This module provides a deep dive into the Gorilla Upgrader. We will study the upgrader struct fields, trace the step-by-step execution sequence of the `Upgrade()` method, explore the security threat of Cross-Site WebSocket Hijacking (CSWSH), optimize memory allocations using Write Buffer Pools, configure subprotocols and compression, and implement a custom dynamic origin validation check.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the purpose and configuration** of the `websocket.Upgrader` struct fields.
2. **Trace the step-by-step execution sequence** of the `Upgrade()` method.
3. **Analyze the Cross-Site WebSocket Hijacking (CSWSH)** threat model and explain how origin checks mitigate it.
4. **Implement a dynamic CORS origin check** to secure handshakes.
5. **Optimize memory allocation and GC pressure** using write buffer pools.
6. **Negotiate subprotocols and frame compression** (`permessage-deflate`) during the handshake.

---

## 1. Struct Fields of `websocket.Upgrader`

The `websocket.Upgrader` configures how HTTP connections are transitioned to the WebSocket framing engine. Below is the Go definition of the struct:

```go
type Upgrader struct {
    // HandshakeTimeout specifies the duration for the handshake to complete.
    HandshakeTimeout time.Duration

    // ReadBufferSize and WriteBufferSize specify the buffer sizes in bytes.
    ReadBufferSize  int
    WriteBufferSize int

    // WriteBufferPool is a pool used to share write buffers.
    WriteBufferPool BufferPool

    // Subprotocols specifies the server's supported subprotocols in order of preference.
    Subprotocols []string

    // Error specifies the function for generating HTTP error responses.
    Error func(w http.ResponseWriter, r *http.Request, status int, reason error)

    // CheckOrigin returns true if the request Origin header is acceptable.
    CheckOrigin func(r *http.Request) bool

    // EnableCompression specifies if the server should negotiate compression.
    EnableCompression bool
}
```

---

### Detailed Field Explanations:

#### 1. HandshakeTimeout
- **Role**: Prevents slow-loris attacks during connection setup. If the handshake does not complete within this duration, the server terminates the connection.
- **Default**: If set to 0, no timeout is enforced (which can leave sockets open indefinitely if the client is slow).

#### 2. ReadBufferSize & WriteBufferSize
- **Role**: Configures the size of the intermediate read and write byte buffers allocated for the connection.
- **Default**: If set to 0, it defaults to **4096 bytes (4 KB)**.

#### 3. WriteBufferPool
- **Role**: Provides a pool for sharing write buffers between connections, reducing memory allocations on busy servers.
- **Default**: If nil, write buffers are allocated on the heap for each connection.

#### 4. Subprotocols
- **Role**: Lists the application-level subprotocols the server supports, ordered by preference.

#### 5. CheckOrigin
- **Role**: A callback function used to validate the client's `Origin` header, preventing unauthorized cross-origin connections.

#### 6. EnableCompression
- **Role**: Enables negotiation of payload compression (`permessage-deflate`).

---

## 2. Internal Mechanics of the `Upgrade()` Method

When your HTTP handler calls `upgrader.Upgrade(w, r, responseHeaders)`, the Gorilla framework executes a structured 7-step sequence:

```text
Client                                Server (HTTP Handler)               TCP Socket
  │                                             │                             │
  │ ─── HTTP GET (Upgrade request) ───────────► │ (Validates HTTP method)     │
  │                                             │ (Validates Upgrade headers) │
  │                                             │ (Validates CORS Origin)     │
  │                                             │                             │
  │                                             │ ─── Hijack connection ────► │ (TCP socket taken over)
  │                                             ◄─── Raw TCP connection ───── │
  │                                             │                             │
  │                                             │ (Calculates Accept Key)     │
  │ ◄── HTTP 101 Switching Protocols ────────── │ (Writes response to TCP)    │
  │                                             │                             │
  ▼                                             ▼                             ▼
```

### 1. HTTP Method Check
The upgrader verifies the request method. According to RFC 6455, the handshake must be an HTTP **`GET`** request. If a client sends a POST or PUT, the upgrader rejects the connection with `HTTP 405 Method Not Allowed`.

### 2. Connection and Upgrade Header Validation
The upgrader verifies the presence of the following headers:
- `Upgrade`: Must contain `"websocket"` (case-insensitive).
- `Connection`: Must contain `"Upgrade"` (case-insensitive).
If these headers are missing or malformed, the upgrader rejects the connection with `HTTP 400 Bad Request`.

### 3. Origin Check
The upgrader reads the `Origin` header. If a custom `CheckOrigin` function is defined, it calls the function. If it returns `false`, the upgrader rejects the connection with `HTTP 403 Forbidden`. If no function is defined, the upgrader uses a default check that compares the origin to the host header.

### 4. Subprotocol Selection
If the client requested subprotocols (`Sec-WebSocket-Protocol`), the upgrader compares them with the server's configured list, selects the first matching protocol, and includes it in the response header.

### 5. Connection Hijacking
The upgrader asserts the `http.ResponseWriter` is an `http.Hijacker` and calls `Hijack()`. This takes control of the raw TCP socket (`net.Conn`), detaching it from the HTTP server engine.

### 6. Accept Key Calculation
The upgrader reads the client's `Sec-WebSocket-Key`, appends the RFC 6455 magic GUID, calculates the SHA-1 hash, and base64-encodes the result.

### 7. Switching Protocols Response
The upgrader writes the `HTTP 101 Switching Protocols` response headers directly to the TCP write buffer and flushes it, transitioning the connection to the WebSocket framing engine.

---

## 3. CORS Security & Cross-Site WebSocket Hijacking (CSWSH)

A major security vulnerability in public-facing WebSocket systems is **Cross-Site WebSocket Hijacking (CSWSH)**.

### The Attack Vector:
1. A user is logged into their bank account on `securebank.com`, which stores a session identifier in a browser cookie.
2. Without logging out, the user visits a malicious site (`malicioussite.com`) in another browser tab.
3. The JavaScript on `malicioussite.com` attempts to open a WebSocket connection to `wss://securebank.com/ws`.
4. Because the request is sent to `securebank.com`, the browser **automatically includes the user's session cookies** with the handshake request.
5. If the bank server upgraded the connection without verifying the origin, the malicious script would gain access to the user's account over the WebSocket channel.

---

### Mitigating CSWSH with CheckOrigin
WebSockets are not protected by standard browser Same-Origin Policies (SOP). 

To prevent CSWSH attacks, the server must inspect the **`Origin`** header during the handshake:
- The browser automatically appends the `Origin` header to all cross-origin requests, and JavaScript cannot modify this header.
- By configuring the upgrader's `CheckOrigin` function, you can verify the connection originated from an authorized domain and reject unauthorized cross-origin connections.

```go
// Default CheckOrigin behavior in Gorilla WebSocket:
func checkSameOrigin(r *http.Request) bool {
    origin := r.Header.Get("Origin")
    if origin == "" {
        return true // Permit connections from non-browser clients (like Go/Python scripts)
    }
    u, err := url.Parse(origin)
    if err != nil {
        return false
    }
    // Compare origin host to target server host header
    return equalASCII(u.Host, r.Host)
}
```

---

## 4. Socket Buffer Tuning & Memory Pools

Each active WebSocket connection allocates read and write buffers. 

On high-concurrency servers, these buffer allocations can consume significant memory and put pressure on Go's Garbage Collector.

### 1. Buffer Size Tuning
- If your application transmits small payloads (e.g. under 1 KB), setting the buffer sizes to 1 KB minimizes the memory footprint per connection.
- If your application transmits large payloads (e.g. 64 KB files), setting the buffer sizes to match the payload size reduces CPU usage and system calls.

---

### 2. Optimizing with WriteBufferPool
Under standard configuration, Gorilla allocates write buffers on the heap for each connection. When the connection closes, the buffer is discarded and must be cleaned up by the Garbage Collector (GC). 

On busy servers with high connection churn, this allocation cycle can cause significant GC pressure, leading to latency spikes.

You can optimize this by configuring a **`WriteBufferPool`** using Go's `sync.Pool` to recycle buffers:

```go
package main

import (
	"sync"
	"github.com/gorilla/websocket"
)

// Custom implementation of the websocket.BufferPool interface
type SyncBufferPool struct {
	pool sync.Pool
}

func (sbp *SyncBufferPool) Get() interface{} {
	return sbp.pool.Get()
}

func (sbp *SyncBufferPool) Put(v interface{}) {
	sbp.pool.Put(v)
}

func NewSyncBufferPool(bufferSize int) *SyncBufferPool {
	return &SyncBufferPool{
		pool: sync.Pool{
			New: func() interface{} {
				// Allocate buffer slice on the heap
				return make([]byte, bufferSize)
			},
		},
	}
}
```

To use this in your application, assign the pool to the upgrader:
```go
var upgrader = websocket.Upgrader{
    ReadBufferSize:  2048,
    WriteBufferSize: 2048,
    WriteBufferPool: NewSyncBufferPool(2048), // Enable buffer recycling
}
```

Recycling write buffers using a pool reduces memory allocations to near-zero, lowering GC pressure and improving server stability under heavy load.

---

## 5. Negotiating Subprotocols and Compression

### 1. Subprotocol Negotiation
If your server exposes multiple API formats (e.g. JSON and Protobuf), you can negotiate the format during the handshake using subprotocols:
1. The client requests supported protocols using the `Sec-WebSocket-Protocol` header:
   `Sec-WebSocket-Protocol: json-v1, protobuf-v1`
2. The server compares the client's list with its supported protocols and returns the selected protocol in the response header:
   `Sec-WebSocket-Protocol: protobuf-v1`
3. The client and server then use the negotiated format for message exchange.

---

### 2. Frame Compression (`permessage-deflate`)
Enabling frame compression reduces bandwidth consumption for text payloads, but introduces memory and CPU overhead:
- **Bandwidth Savings**: Compressing text-heavy payloads (like JSON) can reduce data transfer size by up to 70%.
- **Memory Overhead**: Each compressed connection requires allocating slide window buffers for the compression state. This can increase memory usage per connection by up to 300 KB, which can lead to Out-Of-Memory crashes under high concurrency.
- **Toggle Choice**: Only enable compression if your application transmits large, highly compressible text payloads and has a sufficient memory budget.

---

## 6. Exercises: Dynamic Whitelist Origin Validator & Subprotocol Negotiator

In this exercise, you will build a production-grade upgrader that implements a dynamic domain whitelist check, negotiates custom subprotocols, and configures handshake timeouts.

### Complete Go Server Implementation:

```go
package main

import (
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"
	"github.com/gorilla/websocket"
)

// 1. Thread-safe domain whitelist registry
type OriginWhitelist struct {
	allowedDomains map[string]bool
}

func (ow *OriginWhitelist) IsAllowed(origin string) bool {
	if origin == "" {
		return false
	}
	parsedURL, err := url.Parse(origin)
	if err != nil {
		return false
	}
	
	host := parsedURL.Hostname()
	// Check if the hostname is whitelisted
	return ow.allowedDomains[host]
}

// 2. Initialize the dynamic Upgrader
var whitelist = &OriginWhitelist{
	allowedDomains: map[string]bool{
		"localhost":       true,
		"app.example.com": true,
		"dev.example.com": true,
	},
}

var productionUpgrader = websocket.Upgrader{
	HandshakeTimeout: 5 * time.Second, // Prevent slow-loris attacks
	ReadBufferSize:   2048,
	WriteBufferSize:  2048,
	Subprotocols:     []string{"json-v1", "protobuf-v1"}, // Supported protocols
	CheckOrigin: func(r *http.Request) bool {
		origin := r.Header.Get("Origin")
		return whitelist.IsAllowed(origin)
	},
	Error: func(w http.ResponseWriter, r *http.Request, status int, reason error) {
		// Log upgrade handshake failures
		log.Printf("[Handshake Refused] Status: %d | Reason: %v\n", status, reason)
		http.Error(w, "Handshake failed: "+reason.Error(), status)
	},
}

func handleSecureUpgrades(w http.ResponseWriter, r *http.Request) {
	// Upgrade connection
	conn, err := productionUpgrader.Upgrade(w, r, nil)
	if err != nil {
		// Error handler callback has already logged the error
		return
	}
	defer conn.Close()

	// Negotiated subprotocol details
	negotiatedProtocol := conn.Subprotocol()
	log.Printf("[Server] Client connected using subprotocol: %s\n", negotiatedProtocol)

	for {
		messageType, payload, err := conn.ReadMessage()
		if err != nil {
			break
		}

		// Process payload based on negotiated subprotocol
		if negotiatedProtocol == "protobuf-v1" {
			log.Println("[Protocol Layer] Processing binary protobuf bytes...")
		} else {
			log.Printf("[Protocol Layer] Processing JSON text: %s\n", payload)
		}

		// Echo message
		if err := conn.WriteMessage(messageType, payload); err != nil {
			break
		}
	}
}

func main() {
	http.HandleFunc("/ws", handleSecureUpgrades)
	log.Println("[Security Gateway] Running on :8080...")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal(err)
	}
}
```

---

### Line-by-Line Code Walkthrough:

- **Line 11-13**: `type OriginWhitelist struct { ... }`
  Defines a whitelist registry struct wrapping a map of allowed domains.
- **Line 16**: `func (ow *OriginWhitelist) IsAllowed(...)`
  Parses the client's `Origin` header and checks if the hostname matches our whitelist, returning `false` for unauthorized domains.
- **Line 37**: `HandshakeTimeout: 5 * time.Second`
  Enforces a 5-second handshake timeout to mitigate slow-loris connection starvation attacks.
- **Line 40**: `Subprotocols: []string{"json-v1", "protobuf-v1"}`
  Declares the subprotocols supported by the server, ordered by preference.
- **Line 41-44**: `CheckOrigin: func(...)`
  Enforces our whitelist validator check.
- **Line 45-48**: `Error: func(...)`
  A custom callback triggered when the handshake fails, logging the failure details and returning a formatted HTTP error response to the client.
- **Line 60**: `negotiatedProtocol := conn.Subprotocol()`
  Retrieves the selected subprotocol (e.g. `json-v1`), allowing the application to parse payloads using the correct decoder.

---

## 7. Common Upgrader Mistakes

### 1. Disabling CheckOrigin in Production
- **The Mistake**: Setting `CheckOrigin` to always return `true` in production:
  `CheckOrigin: func(r *http.Request) bool { return true }`
- **The Risk**: Exposes your application to Cross-Site WebSocket Hijacking (CSWSH) attacks, allowing malicious sites to connect on behalf of logged-in users.
- **The Fix**: Always validate origins against a whitelist in production.

### 2. Excessive Buffer Sizes Under High Concurrency
- **The Mistake**: Setting read/write buffer sizes to large values (e.g. 1 MB) for hundreds of thousands of active connections.
- **The Risk**: Exhausts server RAM quickly, leading to Out-Of-Memory crashes.
- **The Fix**: Keep buffer sizes small (e.g. 1 KB to 4 KB) for high-concurrency servers, and use `WriteBufferPool` to recycle buffers.

---

## 8. Technical Interview Questions

### Question 1: Cross-Site WebSocket Hijacking (CSWSH)
*What is Cross-Site WebSocket Hijacking, and how does checking origin headers mitigate it?*

**Answer**:
CSWSH is a security vulnerability where a malicious site establishes a WebSocket connection to a server on behalf of a logged-in user, utilizing the user's session cookies which the browser appends automatically. 

Checking the `Origin` header allows the server to verify the connection request originates from an authorized domain and reject unauthorized cross-origin connections.

---

### Question 2: Gorilla Default CheckOrigin Behavior
*What is the default behavior of Gorilla's `Upgrader` if no `CheckOrigin` function is defined?*

**Answer**:
If `CheckOrigin` is nil, the upgrader compares the host domain in the client's `Origin` header to the domain in the target server's `Host` header. 

If they do not match, the upgrader rejects the connection with `HTTP 403 Forbidden`.

---

### Question 3: Handshake Timeout
*Why should you configure a non-zero `HandshakeTimeout` in production?*

**Answer**:
Configuring a handshake timeout prevents slow-loris connection starvation attacks, where slow clients open sockets and delay sending handshake headers to exhaust server file descriptors.

---

### Question 4: sync.Pool GC Buffer recycling
*How does setting `WriteBufferPool` optimize memory allocations on busy WebSocket servers?*

**Answer**:
It recycles write buffers using Go's `sync.Pool` instead of allocating buffers on the heap for each connection. 

This reduces heap allocations to near-zero, lowering Garbage Collection pressure and preventing latency spikes.

---

### Question 5: Subprotocol Negotiation
*How does subprotocol negotiation work when the client requests protocols the server does not support?*

**Answer**:
If there is no match between client requested protocols and server supported protocols, the server ignores the subprotocol request and does not return the `Sec-WebSocket-Protocol` header. 

The connection upgrades successfully, but operates without a negotiated subprotocol.

---

### Question 6: Permessage-Deflate Memory Footprint
*What is the primary risk of enabling `EnableCompression` under high concurrency?*

**Answer**:
Each compressed connection requires allocating slide window buffers for the compression state, which can increase memory usage per connection by up to 300 KB. 

Under high concurrency, this can exhaust server RAM and lead to Out-Of-Memory crashes.

---

### Question 7: HTTP 405 Method Not Allowed
*What HTTP status code is returned if a client attempts to upgrade using a POST request instead of GET?*

**Answer**:
The upgrader rejects the request and returns `HTTP 405 Method Not Allowed`.

---

### Question 8: WriteBufferPool interface
*What interface must a custom buffer pool implement to be assigned to `WriteBufferPool`?*

**Answer**:
It must implement the `websocket.BufferPool` interface:
```go
type BufferPool interface {
    Get() interface{}
    Put(interface{})
}
```

---

### Question 9: Hijack error handling
*What happens if the upgrader's attempt to hijack the connection returns an error?*

**Answer**:
The upgrader returns the error to the caller, triggers the error callback function (writing a `500 Internal Server Error` response), and aborts the connection.

---

### Question 10: Cookie session validation
*Why is checking origin headers critical if your application uses cookies for authentication?*

**Answer**:
Browsers automatically include cookies with cross-origin requests, exposing the application to Cross-Site WebSocket Hijacking if origin verification is disabled.

---

## Summary
- **websocket.Upgrader** manages HTTP upgrade handshakes, socket hijacking, and buffer allocations.
- **CheckOrigin** protects against Cross-Site WebSocket Hijacking (CSWSH) by validating client domains.
- **WriteBufferPool** recycles write buffers, reducing memory allocations and GC pressure.
- **Subprotocol Negotiation** matches client requested protocols with server options.
- **Frame Compression** reduces bandwidth consumption but increases memory usage per connection.
- Whitelist client origins in production to secure connections.
