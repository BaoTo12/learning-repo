# Module 19: Binary Protocols

Most web applications use text-based **JSON** for real-time messaging. While JSON is human-readable and easy to debug, it is computationally expensive to serialize/deserialize and verbose, consuming unnecessary bandwidth. For high-frequency, low-latency applications (like multiplayer games, financial tickers, or IoT telemetry), text-based formats become a bottleneck.

This module details how to use binary protocols over WebSockets. We will compare JSON, MessagePack, Protocol Buffers (Protobuf), CBOR, and Custom byte formats, analyze their performance trade-offs, and complete an exercise to replace JSON message exchanges with Protocol Buffers in both the Go server and JavaScript client.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Analyze the performance limitations** of text-based JSON.
2. **Evaluate the trade-offs** between JSON, MessagePack, Protobuf, and CBOR.
3. **Write Protocol Buffers schemas** (`.proto` files) to define message structures.
4. **Configure Gorilla WebSocket** to handle binary frames (`websocket.BinaryMessage`).
5. **Serialize and deserialize Protobuf messages** on the Go server and JavaScript client.
6. **Implement binary message loops** to optimize network bandwidth.

---

## 1. Comparing Serialization Protocols

WebSockets support two frame types for payload data: **Text Frames** (`0x1`) and **Binary Frames** (`0x2`).

Text-based systems use Text frames to transmit string-encoded JSON payloads. Binary-based systems use Binary frames to transmit packed byte streams, bypassing browser string decoding.

---

### The Contenders:

#### 1. JSON (JavaScript Object Notation)
- **Format**: Text-based.
- **Pros**: Highly compatible; human-readable; easy to debug; native support in browsers.
- **Cons**: Verbose (transmits field names in every message); slow to parse (requires string tokenization and reflection in Go).

#### 2. MessagePack
- **Format**: Binary-serialized JSON.
- **Pros**: Schema-less (like JSON); smaller and faster to parse than JSON; field names are compressed.
- **Cons**: Still transmits field names (though compressed); not human-readable.

#### 3. Protocol Buffers (Protobuf)
- **Format**: Strongly typed, compiled binary schema.
- **Pros**: Extremely fast to serialize/deserialize; minimal payload size (does not transmit field names; fields are identified by integer tags); automatic code generation in multiple languages.
- **Cons**: Requires defining and compiling schema files (`.proto`); harder to debug as payloads are binary.

#### 4. CBOR (Concise Binary Object Representation)
- **Format**: Standardized binary format (similar to MessagePack).
- **Pros**: Standardized by the IETF (RFC 8949); self-describing; supports nested arrays and maps.
- **Cons**: Slightly larger payload size than Protobuf.

---

## 2. Serialization Protocols Comparison Matrix

The table below contrasts the characteristics of these serialization options:

| Metric | JSON | MessagePack | Protocol Buffers | CBOR |
| :--- | :--- | :--- | :--- | :--- |
| **Data Type** | Text | Binary | Binary | Binary |
| **Payload Size** | Large (100%) | Moderate (~60%) | Small (~30%) | Moderate (~60%) |
| **CPU Parsing Speed** | Slow | Fast | Extremely Fast | Fast |
| **Schema Required** | No | No | Yes (`.proto`) | No |
| **Human Readable** | Yes | No | No | No |
| **Go Code Generation** | No (Uses reflection) | No | Yes (`protoc`) | No |

---

## 3. Protocol Buffers Integration

To use Protocol Buffers, you must define your message structures in a `.proto` schema file.

### The Chat Schema (`proto/chat.proto`):

```protobuf
syntax = "proto3";

package chat;

// Generate Go package output path
option go_package = "./chat";

message ChatMessage {
    string sender = 1;
    string content = 2;
    int64 timestamp = 3;
}
```

### Compiling the Schema:
To compile the schema into Go structures, run the following compiler command:
```bash
protoc --go_out=. proto/chat.proto
```
This generates a `chat/chat.pb.go` file containing the Go struct definitions and helper methods for serialization.

---

## 4. Exercises: Replacing JSON with Protobuf

In this exercise, you will replace a JSON message loop with Protocol Buffers:
1. **The Server**: Reads binary frames, decodes the Protobuf payload, and echoes it back as a binary frame.
2. **The Client**: Encodes a message to binary using Protobuf, sends it, and parses the binary response.

---

### Complete Go Server Implementation:

```go
package main

import (
	"log"
	"net/http"
	"time"
	"github.com/gorilla/websocket"
	"google.golang.org/protobuf/proto"

	// Import the generated protobuf package
	"go-websocket-binary/chat"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

func handleBinaryEcho(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("Upgrade failed:", err)
		return
	}
	defer conn.Close()

	log.Println("[Server] Secure Binary Connection established.")

	for {
		// 1. Read incoming frame
		messageType, payload, err := conn.ReadMessage()
		if err != nil {
			break
		}

		// Verify frame type is Binary (opcode 0x2)
		if messageType != websocket.BinaryMessage {
			log.Println("[Warning] Received non-binary frame type, ignoring.")
			continue
		}

		// 2. Decode binary payload into Protobuf struct
		var clientMsg chat.ChatMessage
		err = proto.Unmarshal(payload, &clientMsg)
		if err != nil {
			log.Println("[Protobuf Error] Unmarshal failed:", err)
			continue
		}

		log.Printf("[Protobuf Decoded] Sender: %s | Content: %s | Time: %d\n",
			clientMsg.Sender, clientMsg.Content, clientMsg.Timestamp)

		// Create response message
		responseMsg := &chat.ChatMessage{
			Sender:    "Server Echo",
			Content:   "Processed: " + clientMsg.Content,
			Timestamp: time.Now().Unix(),
		}

		// 3. Serialize response to binary
		binaryBytes, err := proto.Marshal(responseMsg)
		if err != nil {
			log.Println("[Protobuf Error] Marshal failed:", err)
			continue
		}

		// 4. Write binary frame to socket
		err = conn.WriteMessage(websocket.BinaryMessage, binaryBytes)
		if err != nil {
			break
		}
	}
}

func main() {
	http.HandleFunc("/ws", handleBinaryEcho)
	log.Println("[Binary Gateway] Running on :8080...")
	http.ListenAndServe(":8080", nil)
}
```

---

### Complete JavaScript Client Implementation:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WebSocket Protobuf Client</title>
    <!-- Include protobuf.js CDN for client-side parsing -->
    <script src="https://cdn.jsdelivr.net/npm/protobufjs@7.X.X/dist/protobuf.min.js"></script>
</head>
<body>
    <h2>Protobuf Binary Log</h2>
    <div id="log"></div>

    <script>
        const logDiv = document.getElementById("log");

        function writeToLog(msg) {
            const p = document.createElement("p");
            p.textContent = msg;
            logDiv.appendChild(p);
        }

        // 1. Load the protobuf schema definition
        protobuf.load("proto/chat.proto", function(err, root) {
            if (err) throw err;

            // Obtain the message type reference
            const ChatMessage = root.lookupType("chat.ChatMessage");

            // 2. Connect to the WebSocket server
            const socket = new WebSocket("ws://localhost:8080/ws");
            
            // Set binary type to arraybuffer (receives frames as ArrayBuffer objects)
            socket.binaryType = "arraybuffer";

            socket.onopen = () => {
                writeToLog("[System] Connected. Sending binary Protobuf frame...");

                // Create a message payload matching the schema fields
                const payload = {
                    sender: "Alice",
                    content: "Hello from the binary browser!",
                    timestamp: Date.now()
                };

                // Validate payload structure
                const errMsg = ChatMessage.verify(payload);
                if (errMsg) throw Error(errMsg);

                // Encode message to binary byte array (Uint8Array)
                const message = ChatMessage.create(payload);
                const buffer = ChatMessage.encode(message).finish();

                // Write binary payload to socket
                socket.send(buffer);
                writeToLog("[Sent] Binary Protobuf bytes: " + buffer.length + " bytes.");
            };

            socket.onmessage = (event) => {
                // event.data contains the binary ArrayBuffer payload
                const binaryBytes = new Uint8Array(event.data);
                
                // 3. Decode binary payload
                const message = ChatMessage.decode(binaryBytes);
                
                writeToLog(`[Received] Sender: ${message.sender} | Content: ${message.content} | Time: ${message.timestamp}`);
            };
        });
    </script>
</body>
</html>
```

---

### Line-by-Line Code Walkthrough (Protobuf Integration):

- **Line 37**: `messageType, payload, err := conn.ReadMessage()`
  A blocking call that reads the incoming frame payload from the socket.
- **Line 43**: `if messageType != websocket.BinaryMessage`
  Verifies the frame opcode is `0x2 (Binary Frame)`. If it is a text frame, the server rejects it.
- **Line 50**: `err = proto.Unmarshal(payload, &clientMsg)`
  Decodes the binary payload byte slice into the generated Go struct `chat.ChatMessage`.
- **Line 64**: `binaryBytes, err := proto.Marshal(responseMsg)`
  Serializes the response struct into a binary byte slice.
- **Line 71**: `err = conn.WriteMessage(websocket.BinaryMessage, binaryBytes)`
  Writes the binary payload to the socket as a binary frame (`websocket.BinaryMessage`).
- **Line 33**: `socket.binaryType = "arraybuffer";`
  Instructs the browser to deliver incoming binary frames as standard JavaScript `ArrayBuffer` objects.
- **Line 47**: `const buffer = ChatMessage.encode(message).finish();`
  Serializes the JavaScript object into a binary `Uint8Array` byte buffer.

---

## 5. Technical Interview Questions

### Question 1: Text vs. Binary Frames
*What is the difference between a WebSocket text frame and a binary frame? How does this affect serialization formats?*

**Answer**:
- **Text Frames** (`0x1`) transmit UTF-8 encoded text strings. Use them for text-based formats like JSON.
- **Binary Frames** (`0x2`) transmit raw byte streams, bypassing browser string decoding. Use them for binary formats like Protobuf or MessagePack to save bandwidth and CPU cycles.

---

### Question 2: JSON Reflection Overhead
*Why is JSON serialization computationally expensive in Go compared to Protocol Buffers?*

**Answer**:
Go's standard library `encoding/json` uses reflection to inspect struct fields at runtime and dynamically map fields, which consumes CPU cycles. 

Protocol Buffers compile schemas to static Go code beforehand, performing direct byte offsets and assignments during serialization, which is significantly faster.

---

### Question 3: Protobuf Bandwidth Savings
*Explain how Protocol Buffers achieve smaller payload sizes compared to JSON.*

**Answer**:
- JSON transmits field names (e.g. `{"username": "Alice"}`) in every message, consuming bandwidth.
- Protocol Buffers omit field names, identifying fields by compact integer tags (e.g., tag `1` representing `username`). 

---

### Question 4: socket.binaryType ArrayBuffer vs. Blob
*What is the difference between setting `socket.binaryType` to "arraybuffer" versus "blob"?*

**Answer**:
- **`arraybuffer`**: Delivers binary data as a fixed-length raw binary buffer, allowing direct manipulation of bytes.
- **`blob`**: Delivers binary data as a raw data file-like object, which is useful for streaming large files or media payloads.

---

### Question 5: MessagePack vs. Protobuf
*When would you choose MessagePack over Protocol Buffers?*

**Answer**:
- Choose **MessagePack** if you need a schema-less binary format that is easy to implement and does not require compiling schema files.
- Choose **Protocol Buffers** if you require absolute minimum payload sizes and static type safety.

---

### Question 6: CBOR IETF standard
*What is CBOR, and what is its primary advantage?*

**Answer**:
CBOR (RFC 8949) is a standardized binary format optimized for compact size and fast parsing, making it popular for IoT and constrained environments.

---

### Question 7: protoc option go_package
*What does the `option go_package` directive do in a `.proto` schema file?*

**Answer**:
It specifies the package import path for the generated Go files.

---

### Question 8: proto.Unmarshal performance
*What error is returned if `proto.Unmarshal` receives bytes that do not match the compiled schema?*

**Answer**:
It returns a decoding error, prompting the application to discard the frame.

---

### Question 9: Custom binary protocols
*What is the main advantage of designing a custom binary protocol instead of using Protobuf?*

**Answer**:
It allows packing bytes manually down to the bit level, yielding the absolute smallest payload sizes, which is common in high-performance multiplayer game loops.

---

### Question 10: Debugging binary protocols
*How do you debug binary payloads over WebSockets?*

**Answer**:
Since binary payloads are not human-readable, you must use Wireshark or browser developer tools to capture the bytes and decode them using your schema definitions.

---

## Summary
- **Binary Protocols** (like Protobuf or MessagePack) reduce payload size and CPU usage compared to JSON.
- **Protocol Buffers** compile schemas to static code, omitting field names to save bandwidth.
- **Configure the socket binary type** to `arraybuffer` on the client side to receive binary frames.
- Use `proto.Marshal` and `proto.Unmarshal` to serialize and deserialize messages.
- Always validate binary frames to ensure they match your schema definitions.
- Protect shared client metadata from concurrent write access panics.
