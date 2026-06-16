# Module 3: WebSocket Frames and Protocol Internals

Once the initial HTTP upgrade handshake is complete, the client and server stop parsing text-based HTTP headers. Communication transitions to a binary framing layer. Under this layer, raw application payloads (such as JSON strings, images, or files) are parsed into discrete network packets called **Frames**.

This module details the low-level structure of WebSocket frames. We will analyze the frame bit-field layout, compare Data and Control frames, study the threat model behind client-side masking, examine the XOR masking algorithm with a Go implementation, explore frame fragmentation mechanics, and walk through hands-on exercises to manually decode raw hexadecimal frames.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the need for framing** over stream-oriented TCP sockets.
2. **Deconstruct the bit-field layout** of a standard WebSocket frame.
3. **Contrast Data Frames** (Text, Binary, Continuation) and **Control Frames** (Ping, Pong, Close).
4. **Detail the security threat of cache poisoning** and explain how masking mitigates it.
5. **Implement the XOR masking algorithm** in Go.
6. **Deconstruct large application messages** into fragmented WebSocket frames using Gorilla WebSocket APIs.
7. **Manually decode raw hexadecimal frame strings** into their constituent fields and payloads.

---

## 1. Why Sockets Need Framing

A common challenge when programming raw TCP sockets is managing message boundaries.
- **TCP is Stream-Oriented**: It reads and writes a continuous stream of raw bytes.
- If a client writes two messages to a TCP connection:
  - Message 1: `"PING"`
  - Message 2: `"HELLO"`
  - The TCP layer may merge them into a single packet (`"PINGHELLO"`), or split them across packets (e.g. packet 1 containing `"PIN"` and packet 2 containing `"GHELLO"`).
- To read these messages correctly, the application must implement a framing protocol. Standard approaches include:
  - **Delimiter-Based Framing**: Appending a special byte (like `\n` or `\0`) to mark the end of a message.
  - **Length-Prefix Framing**: Prefixing every message with a fixed-width integer indicating the payload length.

### The WebSocket Approach
The WebSocket protocol (RFC 6455) utilizes a binary framing protocol.
- Every frame includes a binary header that declares the payload length, opcode, and flags.
- This allows WebSockets to handle binary payloads (which could contain arbitrary delimiter characters) safely without risk of boundary collision.

---

## 2. Anatomy of a WebSocket Frame

The following ASCII diagram illustrates the byte structure of a standard WebSocket frame. Each row represents a 32-bit (4-byte) word:

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

---

### Frame Fields Explained:

#### 1. FIN (1 bit - Bit 0)
- **What it is**: The "Final" frame indicator flag.
- **Usage**: If set to 1, this is the final fragment of a message. If set to 0, it indicates the message is fragmented, and additional frames follow.

#### 2. RSV1, RSV2, RSV3 (1 bit each - Bits 1-3)
- **What it is**: Reserved bits for protocol extensions.
- **Usage**: Must be set to 0 unless an extension is negotiated during the HTTP handshake (e.g. enabling payload compression via `permessage-deflate`, which sets `RSV1` to 1).

#### 3. Opcode (4 bits - Bits 4-7)
- **What it is**: Operation Code. Defines how the payload data should be interpreted.
- **Values**:
  - `0x0`: **Continuation Frame** (holds fragments for a message started by a previous text or binary frame).
  - `0x1`: **Text Frame** (UTF-8 encoded string).
  - `0x2`: **Binary Frame** (raw binary bytes).
  - `0x8`: **Connection Close** (requests socket shutdown).
  - `0x9`: **Ping** (heartbeat check request).
  - `0xA`: **Pong** (heartbeat pong reply).

#### 4. MASK (1 bit - Bit 8)
- **What it is**: Masking flag indicator.
- **Usage**: Declares if the payload data is scrambled. **All frames sent from client to server must be masked (set to 1)**. If a client sends an unmasked frame, the server must close the socket immediately with Close code `1002 (Protocol Error)`. Server-to-client frames must not be masked (set to 0).

#### 5. Payload Length (7 bits - Bits 9-15)
- **What it is**: The length of the payload data.
- **Usage**:
  - If length $\le 125$ bytes: The value is stored directly in the 7-bit field.
  - If length $= 126$ bytes: The next 16 bits (2 bytes) represent an unsigned integer storing the actual payload size (up to 65,535 bytes).
  - If length $= 127$ bytes: The next 64 bits (8 bytes) represent an unsigned integer storing the actual payload size (up to $2^{63}-1$ bytes).

#### 6. Masking Key (4 bytes - 32 bits)
- **What it is**: A random 4-byte key used to scramble the payload.
- **Usage**: Only present if the `MASK` bit is set to 1.

#### 7. Payload Data (Variable Length)
- Contains the actual application data.

---

## 3. Data Frames vs. Control Frames

RFC 6455 divides frames into two categories: **Data Frames** and **Control Frames**.

### 1. Data Frames (Opcodes `0x0`, `0x1`, `0x2`)
- **Role**: Used to transmit application-level payloads.
- **Text Frames (`0x1`)**: Wrap UTF-8 encoded text payloads. If a server receives a text frame containing invalid UTF-8 bytes, it must terminate the connection with Close code `1007 (Invalid Frame Payload)`.
- **Binary Frames (`0x2`)**: Wrap raw binary payloads (e.g. image files, Protobuf bytes).
- **Continuation Frames (`0x0`)**: Used to stream fragments of a large message.

### 2. Control Frames (Opcodes `0x8`, `0x9`, `0xA`)
- **Role**: Used to manage connection state.
- **Ping (`0x9`) & Pong (`0xA`)**: Small control frames used for heartbeat checks. If a node receives a Ping frame, it must return a Pong frame containing the exact payload bytes received in the Ping frame.
- **Close (`0x8`)**: Sent to initiate a clean shutdown.
- **Constraints on Control Frames**:
  - **No Fragmentation**: Control frames cannot be fragmented; their `FIN` bit must be set to 1.
  - **Size Limit**: Control frames are capped at **125 bytes**. This ensures they can be processed quickly without blocking data frames.

---

## 4. Why and How Clients Mask Payloads

The requirement that client-to-server frames must be masked is one of the most unique security designs of the WebSocket protocol.

### The Threat: Intermediate Proxy Cache Poisoning
In the early days of WebSockets, security researchers discovered a vulnerability involving intermediate caching proxy servers:
1. A user visits a malicious website, which runs JavaScript that opens a WebSocket connection to a server.
2. The JavaScript sends a WebSocket frame containing a payload that looks like a standard HTTP request:
   ```http
   GET /index.html HTTP/1.1
   Host: target.com
   ```
3. An intermediate caching proxy server misinterprets the payload as a new HTTP request. It forwards the request and caches the response.
4. When other users subsequently request `/index.html` from `target.com` through that proxy, the proxy returns the cached response, poisoning the cache.

### The Solution: XOR Masking
To prevent proxies from recognizing HTTP patterns in the payload, the browser masks all client frames:
- The browser generates a random 4-byte masking key for each frame using a cryptographically secure random number generator (CSPRNG).
- The browser scrambles the payload bytes on the wire using the XOR operation:
  $$D_i = U_i \oplus M_{i \pmod 4}$$
  - $D_i$: The masked byte.
  - $U_i$: The original payload byte at index $i$.
  - $M$: The 4-byte masking key.

```text
Bitwise XOR Scrambling:
Payload Byte (U_0):  0 1 0 0 1 0 0 0  (ASCII 'H')
Masking Byte (M_0):  0 0 1 1 0 1 1 1  (XOR mask key byte)
                    -----------------
Result Byte (D_0):   0 1 1 1 1 1 1 1  (Masked byte sent on wire)
```

Because the masking key is random for each frame, the payload bytes are scrambled on the wire, preventing proxies from recognizing or caching HTTP patterns.

---

### Go Implementation of Masking Math
Below is a standalone Go snippet demonstrating how to mask and unmask bytes using this XOR formula:

```go
package main

import (
	"fmt"
)

// MaskPayload applies the XOR masking algorithm in-place
func MaskPayload(payload []byte, maskingKey [4]byte) {
	for i := 0; i < len(payload); i++ {
		payload[i] ^= maskingKey[i%4]
	}
}

func main() {
	originalText := "Hello"
	payload := []byte(originalText)
	maskingKey := [4]byte{0x37, 0xFA, 0x21, 0x3D} // Example key

	fmt.Println("=== WebSocket XOR Masking Example ===")
	fmt.Printf("Original Payload: %s (Bytes: %v)\n", originalText, payload)
	fmt.Printf("Masking Key     : %v\n", maskingKey)

	// 1. Mask the payload
	MaskPayload(payload, maskingKey)
	fmt.Printf("Masked Payload  : %v\n", payload)

	// 2. Unmask the payload (XOR again with the same key restores original bytes)
	MaskPayload(payload, maskingKey)
	fmt.Printf("Unmasked Payload: %s (Bytes: %v)\n", string(payload), payload)
}
```

---

## 5. Frame Fragmentation and Gorilla Write API

When sending a large message (e.g. a 10 MB image), sending it as a single frame blocks the channel, preventing control frames (like Ping/Pong) from processing.

To prevent this, the sender can fragment the message across multiple frames:

```text
Message: [================ 15 MB Payload ================]
           /                    |                    \
Frame 1: [FIN=0, Opcode=0x2] [Frame 2: FIN=0, Opcode=0x0] [Frame 3: FIN=1, Opcode=0x0]
```

### Go Implementation of Fragmentation using Gorilla WebSocket:
In Go, the `gorilla/websocket` library provides a writer API (`NextWriter`) that handles message fragmentation automatically when writing large payloads:

```go
package main

import (
	"log"
	"github.com/gorilla/websocket"
)

func sendFragmentedPayload(conn *websocket.Conn, largeData []byte) error {
	// 1. Open a writer for the text message.
	// This allocates internal buffer channels.
	writer, err := conn.NextWriter(websocket.TextMessage)
	if err != nil {
		return err
	}

	// 2. Write chunks to the writer.
	// If the chunk exceeds the library's buffer limit, Gorilla automatically
	// flushes the buffer, sending a frame with FIN = 0.
	chunkSize := 1024
	for i := 0; i < len(largeData); i += chunkSize {
		end := i + chunkSize
		if end > len(largeData) {
			end = len(largeData)
		}
		
		_, err := writer.Write(largeData[i:end])
		if err != nil {
			writer.Close()
			return err
		}
		log.Printf("[Server] Transmitted chunk: %d to %d bytes\n", i, end)
	}

	// 3. Close the writer.
	// Closing the writer flushes the remaining bytes and writes the final frame
	// with the FIN bit set to 1.
	return writer.Close()
}
```

---

## 6. Exercises: Manual Frame Decoding

### Exercise A: Decoding a Masked Client-to-Server Frame
**Hex Capture**: `81 85 37 fa 21 3d 7f 9f 4d 51 58`

Let us decode this hex string step-by-step:

#### Step 1: Decode Byte 1 (`0x81`)
- Binary: `10000001`
- Extract **`FIN`** (Bit 0): `1` (This is the final frame).
- Extract **`RSV1, RSV2, RSV3`** (Bits 1-3): `000` (No extensions enabled).
- Extract **`Opcode`** (Bits 4-7): `0001` (`0x1` - Text Frame).

#### Step 2: Decode Byte 2 (`0x85`)
- Binary: `10000101`
- Extract **`MASK`** (Bit 0): `1` (Payload is masked, which is correct for client-to-server frames).
- Extract **`Payload Length`** (Bits 1-7): `0000101` (`5` bytes). Since it is $\le 125$, the length is 5 bytes, and no extended length fields are present.

#### Step 3: Extract the Masking Key (Bytes 3-6)
The masking key occupies the next 4 bytes:
- Hex: `37 fa 21 3d`
- **Masking Key**: `[0x37, 0xFA, 0x21, 0x3D]`

#### Step 4: Extract the Masked Payload (Bytes 7-11)
The payload occupies the final 5 bytes:
- Hex: `7f 9f 4d 51 58`
- **Masked Bytes**: `[0x7F, 0x9F, 0x4D, 0x51, 0x58]`

#### Step 5: Unmask the Payload
Apply the XOR formula to decode the payload:
- Index 0: `0x7F ^ 0x37 = 0x48` -> ASCII **'H'**
- Index 1: `0x9F ^ 0xFA = 0x65` -> ASCII **'e'**
- Index 2: `0x4D ^ 0x21 = 0x6C` -> ASCII **'l'**
- Index 3: `0x51 ^ 0x3D = 0x6C` -> ASCII **'l'**
- Index 4: `0x58 ^ 0x37 = 0x6F` -> ASCII **'o'**

*Result*: The payload matches the message `"Hello"`.

---

### Exercise B: Decoding an Unmasked Server-to-Client Frame
**Hex Capture**: `81 05 48 65 6c 6c 6f`

Let us decode this hex string step-by-step:

#### Step 1: Decode Byte 1 (`0x81`)
- Binary: `10000001`
- Extract **`FIN`** (Bit 0): `1` (This is the final frame).
- Extract **`Opcode`** (Bits 4-7): `0001` (`0x1` - Text Frame).

#### Step 2: Decode Byte 2 (`0x05`)
- Binary: `00000101`
- Extract **`MASK`** (Bit 0): `0` (Payload is unmasked, which is correct for server-to-client frames).
- Extract **`Payload Length`** (Bits 1-7): `0000101` (`5` bytes).

#### Step 3: Extract the Payload (Bytes 3-7)
Since the `MASK` bit is 0, no masking key is present. The remaining bytes are the raw payload:
- Hex: `48 65 6c 6c 6f`
- Index 0: `0x48` -> **'H'**
- Index 1: `0x65` -> **'e'**
- Index 2: `0x6c` -> **'l'**
- Index 3: `0x6c` -> **'l'**
- Index 4: `0x6f` -> **'o'**

*Result*: The payload matches the message `"Hello"`.

---

## 7. Common Mistakes & Debugging

### Scenario A: Unmasked Client Frames
* **The Problem**: A custom Go WebSocket client attempts to connect to your Gorilla WebSocket server. During connections, the server immediately drops the link and prints `websocket: close 1002 (protocol error): client sent unmasked frame`.
* **Why it happens**: According to RFC 6455, all frames sent from client to server must be masked. If a custom client skips masking, the server terminates the connection to prevent security risks.
* **The Fix**: Configure your custom client library to enable frame masking.

### Scenario B: Control Frame Payload Limits
* **The Problem**: The client attempts to close the connection and passes a close reason string. The connection drops, but the server logs a protocol exception.
* **Why it happens**: Control frames (like Close, Ping, Pong) are capped at 125 bytes. If a client attempts to pass a large close description string, it violates this limit, triggering a protocol error.
* **The Fix**: Keep control frame payloads (like close reason strings) small and within the 125-byte limit.

---

## 8. Technical Interview Questions

### Question 1: Text vs. Binary Frames
*Why does the WebSocket protocol define separate Text (0x1) and Binary (0x2) opcodes? What happens if you send invalid UTF-8 bytes in a Text frame?*

**Answer**:
- **Text Frames (`0x1`)** are used to transmit UTF-8 encoded text data (like JSON strings).
- **Binary Frames (`0x2`)** are used to transmit raw binary data (like images or Protobuf bytes).
If a server receives a Text frame containing invalid UTF-8 bytes, it must terminate the connection immediately with Close code `1007 (Invalid Frame Payload)`.

---

### Question 2: Why are Control Frames limited to 125 bytes?
*Why does RFC 6455 limit Control frames (Ping, Pong, Close) to 125 bytes and forbid them from being fragmented?*

**Answer**:
Control frames are used to manage connection state. 

Limiting them to 125 bytes and forbidding fragmentation ensures they can be processed quickly without blocking data frames. 

If control frames could be fragmented or carry large payloads, they could get stuck behind large data frames, causing heartbeats to time out and connections to drop.

---

### Question 3: Continuation Frame (Opcode 0x0)
*Explain the role of the Continuation frame (Opcode `0x0`) during message fragmentation. How does the receiver know a fragmented message is complete?*

**Answer**:
The **Continuation Frame (`0x0`)** is used to transmit fragments of a message started by a previous text or binary frame. 

The receiver knows the message is complete when it receives a frame with the **`FIN`** bit set to 1. The receiver then reassembles all collected fragments into the final message.

---

### Question 4: Client Masking Key Generation
*Why must the client generate a new random masking key for every frame? What security risk arises if a static key is reused?*

**Answer**:
Reusing a static masking key would allow attackers to analyze the byte patterns of repetitive messages, compromising the security benefits of masking. 

Generating a random masking key for each frame ensures the bytes look completely random on the wire, preventing proxies from recognizing and caching HTTP patterns.

---

### Question 5: Head-of-Line Blocking in Fragmentation
*How does frame fragmentation prevent Head-of-Line (HoL) blocking on slow or limited connections?*

**Answer**:
If a client attempts to upload a 50 MB file as a single frame, it blocks the socket write queue. 

Any other client messages (like heartbeats or chat messages) are queued until the large frame is completely sent. 

Fragmenting the large file allows interleaving control frames (like Ping/Pong) between the data fragments, keeping the connection active.

---

### Question 6: RSV Bits
*What are the `RSV1`, `RSV2`, and `RSV3` bits in the WebSocket header used for? Provide an example.*

**Answer**:
These reserved bits are used for protocol extensions. 

An example is payload compression (`permessage-deflate`). If negotiated, the server sets `RSV1` to 1 to notify the client that the payload is compressed.

---

### Question 7: Opcode Length
*Why does the WebSocket frame header dedicate 4 bits to the opcode? How many opcodes are possible, and how many are currently defined?*

**Answer**:
Dedicating 4 bits to the opcode allows for up to 16 possible values:
- Opcodes `0x0` (Continuation), `0x1` (Text), `0x2` (Binary), `0x8` (Close), `0x9` (Ping), and `0xA` (Pong) are defined.
- The remaining values are reserved for future protocol revisions.

---

### Question 8: Opcode Mismatch
*What happens if a client starts a message with a Text frame (Opcode 0x1) and sends a Continuation frame (Opcode 0x0) containing binary data?*

**Answer**:
The server must treat this as a protocol violation. 

All continuation frames must match the type of the initial frame (Text or Binary). If a mismatch occurs, the server closes the connection with Close code `1002 (Protocol Error)`.

---

### Question 9: Header Overhead Comparison
*How does the overhead of a WebSocket frame header compare to standard TCP/IP header overhead?*

**Answer**:
A WebSocket frame header adds between **2 and 14 bytes** of overhead to a message. 

In comparison, a standard TCP header adds **20 bytes**, and an IP header adds another **20 bytes**, resulting in 40 bytes of network transport overhead per packet. 

Because WebSockets sit on top of TCP, every WebSocket message carries this combined transport and framing overhead, which is why grouping updates or using binary formats is preferred for high-frequency messaging.

---

### Question 10: Nagle's Algorithm
*What is Nagle's algorithm, and how does it affect real-time WebSocket frame delivery?*

**Answer**:
Nagle's algorithm is a TCP optimization that buffers small packets to build larger segments, reducing network overhead. 

For real-time WebSockets, this buffering introduces latency. 

To prevent this delay, servers disable Nagle's algorithm by setting `TCP_NODELAY` to `true` on the socket, forcing the network stack to transmit frames instantly.

---

## Summary
- **Framing** establishes message boundaries over stream-oriented TCP sockets.
- **The WebSocket Frame Header** contains flags (`FIN`, `RSV`), an `Opcode`, a `MASK` bit, and payload length descriptors.
- **Data Frames** (Text, Binary, Continuation) carry application payloads, while **Control Frames** (Ping, Pong, Close) manage connection state.
- **Client Masking** uses XOR operations to scramble payloads, preventing caching proxy cache poisoning.
- **Fragmentation** splits large payloads across multiple frames using continuation opcodes and FIN bits.
- **Manual Decoding** of raw hexadecimal strings helps illustrate how the binary protocol is parsed at the byte level.
