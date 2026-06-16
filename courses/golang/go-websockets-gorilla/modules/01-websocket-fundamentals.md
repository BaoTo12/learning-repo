# Module 1: WebSocket Fundamentals

Standard web interactions are request-driven. The client asks, and the server responds. While this stateless, pull-based model is perfect for loading static web pages, it is structurally inefficient for real-time systems.

This module details the core foundations of the **WebSocket Protocol (RFC 6455)**. We will examine the history of its standardization, analyze the limitations of HTTP, compare the TCP/HTTP/WebSocket stack layers, trace the three phases of the connection lifecycle, and explore visual mental models to solidify your understanding. We will conclude with exercises on identifying scenarios where WebSockets should **not** be used.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Define the core characteristics of WebSockets**: persistent, bidirectional, and full-duplex.
2. **Trace the history of WebSocket standardization** and explain the problems RFC 6455 solved.
3. **Contrast TCP, HTTP, and WebSocket protocol layers** on the network stack.
4. **Walk through the three phases of the connection lifecycle** (Handshake, Frame Exchange, Close).
5. **Apply visual mental models** (Phone Call, Pipe, Conveyor Belts) to describe real-time socket flows.
6. **Evaluate when WebSockets are counter-productive** and identify alternative protocols.

---

## 1. The Paradigm Shift to Real-Time Communication

The internet was originally built to share static documents.
- Under this Web 1.0 model, a browser requested a page, the server loaded it from disk, returned the HTML text, and immediately closed the socket connection.
- This stateless request-response model was simple, scalable, and easy to run over basic network hardware.

As web applications evolved into interactive Web 2.0 collaborative tools (e.g. Google Docs, Slack, live trading portals), this stateless model hit a wall.
- **The Core Problem**: Senders and receivers need to exchange messages instantly.
- If a stock price drops, the broker server must push that update to all active users.
- Under standard HTTP/1.1, the server is a passive listener. It waits for the client to send a request before it can return data.
- This unidirectional pull model introduces latency and wastes server CPU resources on empty poll requests.

---

## 2. Why Standard HTTP is Insufficient

To see why we need a dedicated real-time protocol, let us analyze the limitations of HTTP/1.1:

### 1. The Half-Duplex Bottleneck
HTTP/1.1 is fundamentally a **half-duplex** protocol.
- In a half-duplex system, communication can flow in both directions, but only **one direction at a time**.
- Think of a walkie-talkie: you must press the button to speak, and while you are speaking, you cannot hear the other person. Once you finish speaking, you say "Over" and release the button to let the other person respond.
- On a standard HTTP connection, the client sends a request. The server parses the request and writes the response. During this response phase, the client **cannot** transmit new data frames over the same channel. It must wait for the server to finish and close the stream.

### 2. HTTP Keep-Alive Limits
Many developers confuse HTTP Keep-Alive with persistent WebSockets:
- **HTTP Keep-Alive**: Allows reusing a single TCP connection for subsequent HTTP request/response loops, avoiding the overhead of renegotiating a TCP handshake for every asset (like CSS, JS, and image files).
- **The Limitation**: Although the underlying TCP connection remains open, the interaction model is still **unidirectional, stateless, and client-initiated**. The server cannot push data to the client unsolicited; it must still wait for the client to send a standard HTTP request.

### 3. HTTP/2 Multiplexing Limits
HTTP/2 introduced multiplexing, allowing multiple concurrent requests and responses over a single TCP connection.
- **Why this still fails for real-time systems**:
  - Even with HTTP/2, the core messaging model is still request-driven. The server cannot initiate a push stream for custom application events.
  - While HTTP/2 supports **Server Push**, this feature is strictly used to pre-load static assets (like CSS or JavaScript files) in the browser cache before the browser parses the HTML. It does not allow sending custom real-time events to JavaScript application code.

### 4. Connection Setup Overhead
For every standard HTTP request, the client and server must establish a TCP connection, which consumes excessive network resources. Let us analyze this setup sequence in detail.

---

## 3. TCP 3-Way Handshake and TLS Negotiation

When a client initiates a standard HTTP request, it cannot immediately transmit data. The transport layers must establish connection states first.

### 1. The TCP 3-Way Handshake
Before sending HTTP bytes, the client and server execute the standard TCP handshake:

```text
Client                                           Server
  │                                                │
  │ ─── SYN (Seq=X, ACK=0) ──────────────────────► │ (Server allocates resources)
  │                                                │
  │ ◄── SYN-ACK (Seq=Y, ACK=X+1) ───────────────── │ (Client allocates resources)
  │                                                │
  │ ─── ACK (Seq=X+1, ACK=Y+1) ──────────────────► │ (Connection: ESTABLISHED)
```

1. **`SYN`**: The client transmits a packet with the SYN flag set, containing a random initial sequence number $X$.
2. **`SYN-ACK`**: The server allocates buffers, generates sequence number $Y$, and returns a packet with both SYN and ACK flags set, acknowledging the client's packet ($ACK = X + 1$).
3. **`ACK`**: The client returns a packet with the ACK flag set, confirming receipt of the server's sequence number ($ACK = Y + 1$).

This process requires **one complete round-trip time (1 RTT)** before the first application byte can leave the client's network buffer.

### 2. Secure TLS Handshake (HTTPS)
If the connection is secure (`https://` or `wss://`), the TLS negotiation adds more delay:
- **TLS 1.2**: Requires **2 additional RTTs** to negotiate cipher suites, exchange public key certificates, verify trust chains, and calculate the symmetric session keys.
- **TLS 1.3**: Optimizes this process to **1 RTT** using pre-shared key exchanges, but still adds connection establishment delay.

If an application relies on short polling (repeatedly opening and closing connections), executing these handshakes over and over consumes massive CPU power on your servers.

---

## 4. What is WebSocket? (The Technical Definition)

A WebSocket is a **persistent, bidirectional, full-duplex communication channel** established over a single TCP connection.

Let us explore each keyword of this definition to build a solid foundation:

### 1. Persistent (Long-Lived Socket)
Unlike HTTP, where the TCP socket is closed or returned to a pool after the response is completed, a WebSocket connection remains open indefinitely.
- The handshake upgrades the protocol state engine.
- Once established, the TCP socket is kept open in the operating system's kernel memory.
- Senders and receivers can write bytes to the socket at any millisecond without executing connection handshakes.

### 2. Bidirectional (Two-Way Ingress/Egress)
In a WebSocket connection, both the client and the server are peers.
- Either side can send data at any time.
- If a stock price fluctuates, the server pushes the new price directly to the client's screen.
- If the client clicks a button, it pushes a command to the server over the same open link.

### 3. Full-Duplex (Simultaneous Exchange)
- Communication flows in both directions **simultaneously**.
- Think of a telephone call: both parties can speak at the same time, and their voices do not block each other.
- In WebSockets, the underlying TCP connection allocates separate read and write buffers, allowing the client to upload binary assets while the server is downloading text feeds over the same channel concurrently.

---

## 5. Raw TCP Sockets vs. WebSockets

Since WebSockets run over TCP, a common beginner question is: *Why not just use raw TCP sockets directly?*

While raw TCP sockets are fast and lightweight, they are not designed for web browsers:

### 1. Security Barriers
Browsers run untrusted JavaScript code downloaded from the web.
- Letting raw JavaScript open arbitrary TCP sockets to any IP address on the internet would create major security vulnerabilities (e.g. allowing malicious scripts to send spam emails via SMTP or attack local networks).
- WebSockets provide a secure abstraction layer. The browser controls connection establishment, enforces CORS origin rules, and wraps payloads in frame masks to prevent proxy poisoning attacks.

### 2. Framing and Message Boundaries
- **TCP** is a stream-oriented protocol. It does not know where one message ends and the next begins. If a client writes two separate JSON strings to a TCP socket:
  ```json
  {"user":"alice"}{"user":"bob"}
  ```
  The server reads them as a single continuous block of bytes. Senders must write custom framing code (e.g., prefixing message buffers with length indicators).
- **WebSocket** adds a binary framing layer. Every frame explicitly declares its payload length in the header, allowing the parser to reassemble messages accurately.

### 3. Web Proxy Traversal
- Raw TCP sockets use arbitrary ports. Corporate firewalls and proxies block traffic on ports other than standard web ports (80/443).
- WebSockets reuse standard HTTP upgrade handshakes, allowing them to pass through standard proxies and firewalls easily.

---

## 6. History Timeline of Web Real-Time Communication

To see how we arrived at WebSockets, let us trace the historical timeline of real-time web protocols:

### Timeline of Real-Time Milestones:

* **1999: The Introduction of XMLHttpRequest (XHR)**:
  Microsoft introduces XMLHTTP in Internet Explorer 5, allowing browsers to request XML data in the background without reloading the entire page. This enables the development of AJAX applications.
* **2000: Short Polling Hacks**:
  Developers use XHR loops (`setInterval`) to query servers periodically, causing port exhaustion and database load issues.
* **2006: Comet & Long Polling**:
  Alex Russell coins the term "Comet" to describe persistent connection patterns. Developers hold HTTP requests open to allow server pushes, but block server execution threads.
* **2009: HTML5 WebSocket Draft**:
  Ian Hickson and the WHATWG workgroup draft the initial WebSocket specification to provide a native TCP abstraction in the browser.
* **December 2011: RFC 6455 Standardization**:
  The IETF publishes RFC 6455, standardizing the WebSocket wire protocol. The W3C standardizes the JavaScript API. Firewalls and proxies adjust to route the upgraded protocol over ports 80 and 443.
* **2015: HTTP/2 Standardization**:
  HTTP/2 introduces stream multiplexing, reducing connection overhead but keeping the stateless request-driven model intact.
* **2021: HTTP/3 & WebTransport (The Future)**:
  The IETF works on WebTransport, a modern protocol built on top of HTTP/3 and QUIC (UDP) designed to complement WebSockets in high-performance use cases.

---

## 7. WebSockets vs. WebTransport (HTTP/3-Based)

As you advance as a real-time systems architect, you will encounter **WebTransport**:
- **What is it?** A modern web protocol built on top of HTTP/3 and the QUIC transport layer (which runs over UDP).
- **How it differs from WebSockets**:
  - **UDP-based**: Senders can transmit messages as **unreliable datagrams** (similar to UDP packets). If a packet is lost, the stream continues without waiting for retransmission, eliminating Head-of-Line blocking entirely. WebSockets run over TCP, so a lost packet stalls all subsequent frames until it is retransmitted.
  - **Multiplexing**: Supports multiple independent streams over a single connection. If one stream blocks, other streams continue running.
- **Why WebSockets still dominate**:
  - **Browser Support**: WebSockets are supported by virtually every browser and platform on the planet since 2012. WebTransport is still in the early stages of adoption and is not universally supported.
  - **Proxy Compatibility**: WebTransport requires UDP traffic on port 443. Many corporate firewalls block outbound UDP traffic entirely, forcing connections to fall back to WebSockets over TCP.

---

## 8. Protocol Stack Comparison: TCP vs. HTTP vs. WebSocket

WebSockets do not replace TCP or HTTP; instead, they operate on top of them.

### Network Stack Layer Mapping

```text
+------------------------------------+
| Application Layer: HTTP / STOMP    |  <-- High-level message structures
+------------------------------------+
| WebSocket Protocol (RFC 6455)      |  <-- Framing layer (binary framing)
+------------------------------------+
| Transport Layer: TCP Socket        |  <-- Reliable byte-stream transport
+------------------------------------+
| Network Layer: IP                  |  <-- Host-to-host routing
+------------------------------------+
```

- **TCP (Transport Layer)**:
  Provides a reliable, ordered, error-checked stream of raw bytes. It has no concept of message boundaries or protocol metadata.
- **HTTP (Application Layer)**:
  A text-based, stateless protocol that uses TCP to send request and response documents.
- **WebSocket (Framing Layer)**:
  Sits directly on top of the TCP socket. It begins as a standard HTTP request to upgrade the connection. Once upgraded, the HTTP parser is disabled, and WebSocket frames are sent directly over the open TCP channel.

---

## 9. Detailed Connection Lifecycle Walkthrough

A WebSocket connection transitions through three distinct phases:

### Phase 1: The Handshake (Protocol Upgrade)
The client initiates the connection by sending an HTTP GET request with upgrade headers:

#### The Client Request:
```http
GET /chat HTTP/1.1
Host: server.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
Origin: http://example.com
```

- **`Upgrade: websocket`**: Notifies the server that the client wants to switch protocols.
- **`Connection: Upgrade`**: Instructs the HTTP router that the socket connection should be kept active and upgraded.
- **`Sec-WebSocket-Key`**: A random 16-byte base64-encoded nonce used to prevent caching proxies from routing old connections.

#### The Server Response:
If the server accepts the upgrade, it responds with:
```http
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

- **`Sec-WebSocket-Accept`**: Proven confirmation that the server supports WebSockets. The value is calculated using a standard hashing formula:
  $$\text{Accept Value} = \text{Base64}\left(\text{SHA-1}\left(\text{Sec-WebSocket-Key} + \text{"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"}\right)\right)$$

#### Step-by-Step Accept Hash Calculation Example:
1. **Receive the Key**: Suppose the client key is `dGhlIHNhbXBsZSBub25jZQ==`.
2. **Append the RFC Magic GUID String**: Append the globally unique identifier specified in RFC 6455:
   `"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"`
   - Combined String:
     `"dGhlIHNhbXBsZSBub25jZQ==258EAFA5-E914-47DA-95CA-C5AB0DC85B11"`
3. **Calculate the SHA-1 Hash**: Calculate the SHA-1 hash of this combined string:
   - SHA-1 Binary Output: `0xb3 0x7a 0x4f 0x2c ...` (20 bytes).
4. **Base64 Encode**: Base64-encode the SHA-1 digest.
   - Result: `"s3pPLMBiTxaQ9kYGzzhZRbK+xOo="`.
5. **Validation**: The browser performs the same calculation. If the hashes match, the browser completes the handshake.

---

### Phase 2: Active Message Framing

Once upgraded, the socket transitions to the active framing layer. Data is wrapped in binary frames.

#### The WebSocket Frame Byte Layout (RFC 6455 Section 5.2):
The following ASCII diagram illustrates the byte structure of a WebSocket frame. Each block represents bits:

```text
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
|     Extended payload length continued, if payload len == 127  |
+-------------------------------+-------------------------------+
|                               |Masking-key, if MASK set to 1  |
+-------------------------------+-------------------------------+
| Masking-key continued         |          Payload Data         |
+-------------------------------- - - - - - - - - - - - - - - - +
:                     Payload Data continued ...                :
+---------------------------------------------------------------+
```

#### Detailed Frame Fields:
- **`FIN` (1 bit)**: Indicates if this is the final fragment of a message. If set to 1, the message is complete. If set to 0, more fragments follow.
- **`RSV1, RSV2, RSV3` (1 bit each)**: Reserved for extension negotiations (e.g. enabling frame compression). Must be 0 unless negotiated.
- **`Opcode` (4 bits)**: Defines the frame interpretation:
  - `0x0`: Continuation Frame (holds payload fragments).
  - `0x1`: Text Frame (UTF-8 strings).
  - `0x2`: Binary Frame (raw bytes).
  - `0x8`: Close Control Frame (socket teardown request).
  - `0x9`: Ping Control Frame (heartbeat ping).
  - `0xA`: Pong Control Frame (heartbeat pong reply).
- **`MASK` (1 bit)**: Defines if the payload data is masked. **All frames sent from client to server must be masked (set to 1)**. Server-to-client frames must not be masked (set to 0).
- **`Payload Length` (7 bits)**:
  - If length $\le 125$ bytes, stored directly here.
  - If length $= 126$ bytes, the next 16 bits contain the actual length.
  - If length $= 127$ bytes, the next 64 bits contain the actual length.
- **`Masking Key` (4 bytes)**: If `MASK` is 1, these random 4 bytes are used to scramble the payload.
- **`Payload Data`**: The actual application data (e.g. JSON text or raw byte array).

---

### Phase 3: The Close Handshake

To close the connection cleanly:
1. The close initiator sends a Close control frame (`0x8`) containing a status code (e.g. `1000` for normal closure).
2. The receiver reads the Close frame and returns a Close frame in response.
3. The underlying TCP socket is terminated, freeing server resources.

#### Key Close Status Codes:
* **1000 (Normal Closure)**: The connection has successfully completed its purpose.
* **1001 (Going Away)**: The server is shutting down, or the user navigated away from the page.
* **1002 (Protocol Error)**: A node received a frame that violates the protocol rules (e.g. an unmasked client frame).
* **1007 (Invalid Frame Payload)**: The received payload could not be decoded (e.g., malformed UTF-8 bytes in a text frame).
* **1009 (Message Too Big)**: A frame exceeded the maximum payload limit configured on the server.
* **1011 (Internal Error)**: The server encountered an unexpected runtime exception processing the request.

---

## 10. Visual Mental Models

To build a solid understanding of WebSockets, we can use three mental models:

### Model 1: Phone Call vs. Letters (Analogy)

```text
HTTP (Letter Exchange):
Client ──[Request Letter + Envelope]──► Post Office ──► Server
Client ◄──[Response Reply + Envelope]──◄ Post Office ◄── Server (Socket Closed)

WebSocket (Phone Call):
Client ──[Upgrade: Dial Call]──► Ringing... ──► Server (Connection Connected)
Client ◄================= Simultaneous speaking =================► Server
```

- **HTTP** is like exchanging letters: every message requires a new envelope, stamp, and address headers. The connection is stateless, and the server cannot contact the client until it receives a letter.
- **WebSocket** is like a phone call: you establish a connection once, and both parties can speak back and forth simultaneously. The channel remains open until one party hangs up.

### Model 2: The Hollow Pipe (Analogy)
Imagine a hollow pipe running between client and server. Once the handshake installs the pipe, either end can drop marbles (messages) into it. The marbles roll to the other end instantly, requiring no envelopes or stamps.

### Model 3: Conveyor Belts (Analogy)
Imagine two parallel, asynchronous conveyor belts operating in opposite directions. The client places messages on the outbound belt, and the server places messages on the inbound belt. Both belts run continuously and independently, enabling concurrent, bidirectional communication.

---

## 11. Hands-On: Code Execution of the Upgrade Handshake

To understand how this protocol upgrade is handled programmatically, let us look at the Go code using the standard `gorilla/websocket` library.

### Conceptual Handshake Upgrader in Go:
```go
package main

import (
	"log"
	"net/http"
	"github.com/gorilla/websocket"
)

// 1. Initialize the Upgrader configuration struct
var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024, // Sizing read socket buffer limit
	WriteBufferSize: 1024, // Sizing write socket buffer limit
	CheckOrigin: func(r *http.Request) bool {
		// Enforce CORS origin checks. returning true permits the upgrade
		return true 
	},
}

func handleWebSocketConnection(w http.ResponseWriter, r *http.Request) {
	// 2. Execute the HTTP protocol upgrade handshake (switching to RFC 6455)
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("[Handshake Error] Upgrade failed:", err)
		return
	}
	defer conn.Close() // Guarantee socket cleanup on function return

	log.Println("[Server] Upgrade successful! WebSocket connection established.")

	// 3. Enter the persistent Frame Exchange loop
	for {
		messageType, payload, err := conn.ReadMessage()
		if err != nil {
			log.Println("[Server] Read failed or client disconnected:", err)
			break // Exits loop to trigger close handshake defer
		}

		log.Printf("[Server] Frame received: %s (Type: %d)\n", payload, messageType)

		// Echo message back to client
		if err := conn.WriteMessage(messageType, payload); err != nil {
			log.Println("[Server] Write failed:", err)
			break
		}
	}
}
```

---

## 12. Exercises: When WebSocket Should NOT Be Used

While WebSockets are powerful, using them for the wrong workload can degrade performance and complicate architecture. Analyze the following case studies:

### Case Study 1: Global News Publishing Blog
* **Scenario**: A news website displays static articles, images, and text. Users load pages once every few minutes to read content.
* **Why WebSockets should NOT be used**:
  - **No CDN Caching**: WebSocket traffic cannot be cached by Content Delivery Networks (CDNs) like Cloudflare. Standard HTTP requests allow edge nodes to cache articles, reducing database load and speeding up page loads. WebSockets force all requests back to the application server.
  - **Resource Exhaustion**: Keeping thousands of idle sockets open in server memory for users who browse a page once every 5 minutes is a waste of server resources.

### Case Study 2: User Settings Update Form
* **Scenario**: A user submits a form to update their profile username and email address.
* **Why WebSockets should NOT be used**:
  - **Over-Complexity**: A standard HTTP POST request is simple, stateless, and integrates natively with standard security filters (CSRF validation). Opening a WebSocket connection just to send a single form submit adds unnecessary architectural complexity.

### Case Study 3: Hourly Weather Ticker Widget
* **Scenario**: A weather widget on a dashboard displays the current temperature, updating once every hour.
* **Why WebSockets should NOT be used**:
  - **Low Frequency**: The update frequency is extremely low (60 minutes). Keeping a persistent WebSocket connection active in memory for an hour just to send a few bytes of metrics is a waste of server resources. A simple HTTP GET request once every hour is the most efficient choice.

### Case Study 4: High-Volume Unidirectional Sports Alerts Feed
* **Scenario**: A sports news app streams live score updates to millions of read-only users.
* **Why WebSockets should NOT be used**:
  - **SSE is Better**: Since the data flow is strictly unidirectional (server-to-client), Server-Sent Events (SSE) is a more efficient choice. SSE is lighter, supports native browser reconnections out of the box, and multiplexes over standard HTTP/2 channels.

---

## 13. Technical Interview Questions

### Question 1: WebSocket vs. HTTP/2 Multiplexing
*Since HTTP/2 supports multiplexing (sending multiple concurrent requests over a single TCP connection), why do we still need WebSockets for real-time applications?*

**Answer**:
While HTTP/2 multiplexing allows reusing a single TCP connection, it remains fundamentally **request-driven and client-initiated**:
1. The server **cannot** push data to the client without an active request stream.
2. HTTP/2 streams are half-duplex. The client cannot send data over an active stream while the server is writing the response.
3. HTTP/2 requests still carry header overhead, which is inefficient for high-frequency interactive payloads.
WebSockets provide true bidirectional, full-duplex communication with minimal framing overhead, making them the correct choice for interactive, low-latency applications.

---

### Question 2: Stateful Scalability
*What is the primary architectural challenge when scaling a WebSocket application horizontally compared to a REST API?*

**Answer**:
- **REST APIs** are stateless. Any server instance behind a round-robin load balancer can process any request because the client passes all required credentials with each request.
- **WebSocket connections** are stateful and pinned to a specific server instance. If Client A is connected to Server 1, and Client B is connected to Server 2, they cannot communicate directly. To scale horizontally, you must configure **sticky sessions** on the load balancer to keep connections pinned, and deploy a **shared message bus** (like Redis Pub/Sub) to route messages between server instances.

---

### Question 3: HTTP 101 Switching Protocols Status Code
*Explain the role of the HTTP 101 status code during the WebSocket connection setup. What happens to the TCP connection when this code is returned?*

**Answer**:
The `HTTP 101 Switching Protocols` status code is returned by the server to confirm it accepts the client's request to upgrade the connection. 

When this code is returned, the client and server stop parsing data as HTTP text requests/responses. The underlying TCP connection is kept open, and the communication format switches to the binary WebSocket framing protocol, allowing both parties to send data frames directly over the open channel.

---

### Question 4: Sec-WebSocket-Accept Hash Calculation
*Why does the WebSocket handshake include the `Sec-WebSocket-Key` and `Sec-WebSocket-Accept` headers? How is the accept hash calculated?*

**Answer**:
These headers are used to prevent caching proxies from routing old connections:
1. The client sends a random 16-byte base64-encoded nonce in `Sec-WebSocket-Key`.
2. The server appends a globally unique magic string GUID (`"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"`) to the key.
3. The server calculates the SHA-1 hash of this combined string and base64-encodes the result, returning it in `Sec-WebSocket-Accept`.
4. The client performs the same calculation. If the hashes match, the client knows the server supports WebSockets, preventing caching proxies from misrouting requests.

---

### Question 5: Keep-Alive Heartbeats
*Why are Ping and Pong control frames critical in a production WebSocket application? What problem do they solve?*

**Answer**:
Ping and Pong frames are critical for connection management:
1. **Detecting Stale Connections**: If a client device drops offline silently (e.g. losing cell service), the TCP connection remains open in the server kernel. Sending periodic Ping frames allows the server to detect dead links and reclaim memory.
2. **Preventing Timeout Closures**: Intermediate proxies and firewalls often close idle TCP connections. Sending periodic heartbeats keeps the connection active, preventing unexpected closures.

---

### Question 6: Browser Connection Limits
*How does browser connection limits under HTTP/1.1 affect Server-Sent Events (SSE) compared to WebSockets?*

**Answer**:
Under HTTP/1.1, browsers limit concurrent connections to the same domain to **6 active sockets**:
- Since **SSE** runs over standard HTTP, opening an SSE stream consumes one of these 6 sockets. If a user opens 6 tabs to the same domain, they can exhaust the browser's socket pool, blocking all standard page loads.
- **WebSockets** upgrade the connection, bypassing this HTTP limit, allowing applications to open multiple independent channels without blocking standard HTTP traffic.

---

### Question 7: Why are Client Frames Masked?
*Explain why the WebSocket protocol requires all frames sent from client to server to be masked, while frames sent from server to client are not masked.*

**Answer**:
Client frames are masked to prevent **cache-poisoning attacks** on intermediate proxies. 

If a client sends an unmasked frame containing HTTP request headers inside the WebSocket payload, an intermediate proxy might misinterpret the payload bytes as a new HTTP request, caching malicious content. 

Masking scrambles the payload bytes on the wire using a random 4-byte key, preventing proxies from recognizing pattern strings. Server frames do not need masking because client browsers are not shared caching intermediaries.

---

### Question 8: Head-of-Line Blocking
*What is Head-of-Line (HoL) blocking, and how do persistent full-duplex WebSockets eliminate it compared to standard HTTP/1.1 queues?*

**Answer**:
In HTTP/1.1, HoL blocking occurs when a client must wait for a previous request to complete before sending the next one over the same TCP connection. 

WebSockets eliminate HoL blocking at the application level by allowing concurrent, asynchronous read and write frames over the same socket. Senders can write new data frames to the write buffer at any time, even while the read buffer is downloading incoming payloads, ensuring that a slow response does not block other traffic.

---

### Question 9: Connection Multiplexing
*Does the WebSocket protocol support multiplexing (routing multiple logical channels over a single socket connection) out of the box?*

**Answer**:
No. The core WebSocket protocol (RFC 6455) does **not** support multiplexing natively. It only provides a single stream of text or binary frames. 

To run multiple logical channels over a single WebSocket connection, you must implement a subprotocol at the application layer. This is typically done using STOMP destination headers or custom JSON wrappers that contain channel routing parameters (e.g. `{"stream": "chat-room-1", "payload": ...}`).

---

### Question 10: Deadlines in Go WebSockets
*What are read and write deadlines, and why are they critical when managing WebSocket connections in Go?*

**Answer**:
Read and write deadlines are timeouts set on the underlying TCP socket:
- **Read Deadline**: The maximum time the server will wait for the client to send a frame. If the deadline expires without data arriving, the server's read call returns an error, prompting connection teardown.
- **Write Deadline**: The maximum time allowed to write a frame to the client's socket.
In Go, setting these deadlines prevents slow or dead clients from blocking goroutines indefinitely, protecting server resources.

---

## Summary
- **WebSockets** provide persistent, bidirectional, full-duplex communication over a single TCP connection.
- **RFC 6455** standardized WebSockets in 2011 to eliminate polling hacks and allow proxies to route sockets securely over ports 80 and 443.
- **WebSocket sits on top of TCP** and is established using an initial HTTP upgrade handshake.
- **Visual Models** (Phone Call, Hollow Pipe, Conveyor Belts) help describe persistent connection behavior.
- **WebSockets should not be used** for static content delivery, simple CRUD forms, or unidirectional feeds, where standard HTTP caching or SSE are more efficient.
