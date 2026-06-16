# Module 6: Setting Up Gorilla WebSocket

Setting up a development environment for real-time systems in Go requires understanding dependency management, standard project structures, and basic connection code. 

This module guides you through the process of setting up your first Go WebSocket project. We will initialize a Go module, analyze standard project folder layouts, and build a minimal working WebSocket server and browser client, explaining every line of code. We will then walk through an exercise to convert the minimal setup into a production-grade, concurrency-safe Echo server featuring Ping/Pong heartbeats.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Initialize a Go project** and manage Gorilla WebSocket dependencies using Go modules.
2. **Organize a real-time Go application** according to standard Go project layouts.
3. **Build a functional WebSocket server** in Go and explain its upgrade and framing code.
4. **Implement an HTML5 browser client** and explain its JavaScript event callbacks.
5. **Implement concurrency protections** using write mutexes to prevent socket write crashes.
6. **Configure Ping/Pong deadlines** to detect and clean up dead client connections.

---

## 1. Project Initialization and Dependency Setup

Go uses modules to manage project dependencies. Let us initialize the workspace and install the Gorilla library.

### Step-by-Step Initialization Commands:

```bash
# 1. Create a new directory for the project
mkdir go-websocket-echo
cd go-websocket-echo

# 2. Initialize the Go module
go mod init go-websocket-echo

# 3. Download and install the Gorilla WebSocket package
go get github.com/gorilla/websocket
```

---

### The `go.mod` Dependency File
After running these commands, a `go.mod` file is created in your root directory. It lists your module declaration, compiler requirements, and direct dependencies:

```go
module go-websocket-echo

go 1.25

require github.com/gorilla/websocket v1.5.3
```

- **`module go-websocket-echo`**: Defines the import path prefix for internal packages.
- **`go 1.25`**: Declares the minimum Go compiler version required to build the project.
- **`require ...`**: Explicitly locks the version of the Gorilla WebSocket dependency.

A `go.sum` file is also generated, containing SHA-256 cryptographic hashes of the downloaded dependencies to guarantee secure, reproducible builds.

---

## 2. Standard Project Folder Layout

To build scalable real-time backends, follow the standard Go project layout:

```text
go-websocket-echo/
├── cmd/
│   └── server/
│       └── main.go       <-- Server Entry Point (Starts http listener)
├── internal/
│   └── handler/
│       └── websocket.go  <-- Upgrader and Connection Read/Write loops
├── public/
│   └── index.html        <-- Frontend Browser Client
├── go.mod
└── go.sum
```

- **`cmd/`**: Contains the entry points for the application. Each subfolder here compiles into a separate executable binary.
- **`internal/`**: Contains private application logic. Packages here cannot be imported by external projects, enforcing code encapsulation.
- **`public/`**: Stores static assets (HTML, CSS, JS) served to the client browser.

---

## 3. Building Your First WebSocket Server

Let us write a minimal WebSocket server that accepts upgrades and echoes client messages back over the socket.

### The Server Code (`cmd/server/main.go`):

```go
package main

import (
	"log"
	"net/http"
	"github.com/gorilla/websocket"
)

// 1. Initialize the Upgrader config
var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all origins for local testing
	},
}

// 2. Define the WebSocket upgrade handler
func handleWebSocket(w http.ResponseWriter, r *http.Request) {
	// Upgrade standard HTTP connection to a WebSocket
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("[Error] Upgrade failed:", err)
		return
	}
	defer conn.Close() // Ensure socket cleanup

	log.Println("[Server] Client connected!")

	// 3. Enter the persistent message loop
	for {
		messageType, payload, err := conn.ReadMessage()
		if err != nil {
			log.Println("[Server] Connection closed by client:", err)
			break
		}

		log.Printf("[Server] Received: %s (Type: %d)\n", payload, messageType)

		// Echo message back to client
		err = conn.WriteMessage(messageType, payload)
		if err != nil {
			log.Println("[Server] Write failed:", err)
			break
		}
	}
}

// 4. Start the HTTP listener
func main() {
	// Register static assets handler
	http.Handle("/", http.FileServer(http.Dir("./public")))
	
	// Register websocket upgrade route
	http.HandleFunc("/ws", handleWebSocket)

	log.Println("[Server] Starting listener on :8080...")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal("[Fatal] Server crashed:", err)
	}
}
```

---

### Line-by-Line Code Walkthrough (Server):

- **Line 10**: `var upgrader = websocket.Upgrader{...}`
  Initializes the upgrader config struct. It specifies buffer sizes in bytes and origin checks.
- **Line 11-12**: `ReadBufferSize`, `WriteBufferSize`
  Configures the size of the intermediate byte buffers allocated for the socket. Larger buffers improve throughput, but consume more memory per connection.
- **Line 13-15**: `CheckOrigin: func(r *http.Request) bool { return true }`
  Enforces CORS rules during the handshake. Returning `true` allows connections from any domain, which is fine for local testing but should be configured to whitelist specific domains in production.
- **Line 19**: `func handleWebSocket(w http.ResponseWriter, r *http.Request)`
  The HTTP endpoint handler. It accepts standard HTTP writer and request objects.
- **Line 21**: `conn, err := upgrader.Upgrade(w, r, nil)`
  Performs the handshake upgrade, hijacks the connection from Go's standard HTTP server engine, writes the `101 Switching Protocols` response headers, and returns a stateful `*websocket.Conn` object.
- **Line 26**: `defer conn.Close()`
  Guarantees that the underlying TCP connection is closed cleanly when the handler function returns.
- **Line 31**: `for { ... }`
  Starts an infinite loop to process incoming WebSocket frames.
- **Line 32**: `messageType, payload, err := conn.ReadMessage()`
  A blocking call that waits for the client to send a frame. It returns:
  - `messageType`: `1` (Text Frame) or `2` (Binary Frame).
  - `payload`: The decoded byte array.
  - `err`: An error if the socket was disconnected or violated protocol rules.
- **Line 33-36**: `if err != nil { break }`
  If an error occurs, it exits the loop, triggering the deferred `conn.Close()` call.
- **Line 41**: `err = conn.WriteMessage(messageType, payload)`
  Writes the payload back to the client over the socket, echoing the message.
- **Line 50**: `http.Handle("/", http.FileServer(http.Dir("./public")))`
  Serves the static client HTML page from the `./public` directory.
- **Line 53**: `http.HandleFunc("/ws", handleWebSocket)`
  Registers the WebSocket upgrade handler on the `/ws` path.
- **Line 56**: `http.ListenAndServe(":8080", nil)`
  Starts the standard HTTP server listener on port 8080.

---

## 4. Building the Browser Client

Let us write a simple HTML/JavaScript client page to connect to our server and send messages.

### The Client Code (`public/index.html`):

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Gorilla WebSocket Client</title>
    <style>
        body { font-family: sans-serif; margin: 20px; }
        #log { width: 100%; height: 300px; border: 1px solid #ccc; overflow-y: scroll; padding: 10px; margin-bottom: 10px; }
    </style>
</head>
<body>
    <h2>WebSocket Log Viewer</h2>
    <div id="log"></div>
    <form id="messageForm">
        <input type="text" id="messageInput" placeholder="Type a message..." required autocomplete="off">
        <button type="submit">Send Message</button>
    </form>

    <script>
        // 1. Establish connection to the Go server WebSocket endpoint
        const socket = new WebSocket("ws://localhost:8080/ws");
        const logDiv = document.getElementById("log");
        const form = document.getElementById("messageForm");
        const input = document.getElementById("messageInput");

        // Helper to append messages to the screen log
        function writeToLog(message) {
            const line = document.createElement("p");
            line.textContent = message;
            logDiv.appendChild(line);
            logDiv.scrollTop = logDiv.scrollHeight; // Scroll to bottom
        }

        // 2. Register callback handlers
        socket.onopen = function(event) {
            writeToLog("[System] WebSocket connection established.");
        };

        socket.onmessage = function(event) {
            writeToLog("[Received] " + event.data);
        };

        socket.onclose = function(event) {
            writeToLog("[System] Connection closed. Code: " + event.code);
        };

        socket.onerror = function(error) {
            writeToLog("[Error] WebSocket encountered an error.");
        };

        // 3. Handle form submission to send messages
        form.addEventListener("submit", function(event) {
            event.preventDefault(); // Prevent page reload
            const val = input.value;
            socket.send(val); // Write message to socket
            writeToLog("[Sent] " + val);
            input.value = ""; // Clear input
        });
    </script>
</body>
</html>
```

---

### Line-by-Line Code Walkthrough (JavaScript Client):

- **Line 21**: `const socket = new WebSocket("ws://localhost:8080/ws");`
  Instructs the browser to open a TCP connection to the server on port 8080 and negotiate the WebSocket upgrade.
- **Line 32**: `socket.onopen = function(event) { ... };`
  A callback triggered when the handshake upgrades the connection.
- **Line 36**: `socket.onmessage = function(event) { ... };`
  A callback triggered when the client receives a frame from the server. `event.data` contains the decoded payload.
- **Line 40**: `socket.onclose = function(event) { ... };`
  A callback triggered when the connection is closed. `event.code` exposes the status code (e.g. `1000` for normal closure).
- **Line 44**: `socket.onerror = function(error) { ... };`
  A callback triggered when the connection fails (e.g. handshake rejections).
- **Line 48-54**: `form.addEventListener("submit", ...)`
  Binds a listener to the UI form. When submitted, it calls `socket.send(val)` to write the message to the socket.

---

## 5. Exercises: Implementing a Production-Grade Echo Server

While our minimal server works, it is unsafe for production:
- **No Concurrency Safety**: If multiple requests or goroutines attempt to write concurrently, it throws panic errors.
- **No Idle Detection**: If a client drops offline silently, the socket remains open in the server kernel, leaking resources.

Let us build an upgraded Echo server that wraps connections in a custom thread-safe struct with mutex locks, and implements Ping/Pong heartbeats using deadlines:

```go
package main

import (
	"log"
	"net/http"
	"sync"
	"time"
	"github.com/gorilla/websocket"
)

const (
	writeWait  = 10 * time.Second    // Time allowed to write a message
	pongWait   = 60 * time.Second    // Time allowed to read the next pong
	pingPeriod = (pongWait * 9) / 10 // Send pings slightly before timeout
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // Whitelist origins
	},
}

// 1. Thread-safe client connection wrapper
type SafeConnection struct {
	conn      *websocket.Conn
	writeMu   sync.Mutex // Mutex to serialize concurrent writes
}

// WriteMessage executes thread-safe writes using a Mutex lock
func (sc *SafeConnection) WriteMessage(messageType int, data []byte) error {
	sc.writeMu.Lock()
	defer sc.writeMu.Unlock()
	sc.conn.SetWriteDeadline(time.Now().Add(writeWait))
	return sc.conn.WriteMessage(messageType, data)
}

func handleEcho(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("[Upgrade Error]:", err)
		return
	}
	
	sc := &SafeConnection{conn: conn}
	defer sc.conn.Close()

	// 2. Configure read deadlines and Pong callbacks
	sc.conn.SetReadDeadline(time.Now().Add(pongWait))
	sc.conn.SetPongHandler(func(string) error {
		// Reset read deadline on receiving pong
		sc.conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	// 3. Start heartbeat ticker goroutine
	go startHeartbeatTicker(sc)

	// 4. Main message read loop
	for {
		messageType, payload, err := sc.conn.ReadMessage()
		if err != nil {
			log.Println("[Read Error] Socket closed:", err)
			break
		}

		log.Printf("[Echo Server] Echoing message: %s\n", payload)

		// Echo message back to client safely
		err = sc.WriteMessage(messageType, payload)
		if err != nil {
			log.Println("[Write Error]:", err)
			break
		}
	}
}

// startHeartbeatTicker sends periodic Ping frames
func startHeartbeatTicker(sc *SafeConnection) {
	ticker := time.NewTicker(pingPeriod)
	defer ticker.Stop()

	for range ticker.C {
		// Send Ping control frame (opcode 0x9)
		err := sc.WriteMessage(websocket.PingMessage, []byte{})
		if err != nil {
			log.Println("[Heartbeat Error] Failed to write Ping:", err)
			sc.conn.Close() // Force close socket on write failure
			return
		}
	}
}

func main() {
	http.HandleFunc("/ws", handleEcho)
	log.Println("[Production Echo] Starting server on :8080...")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal(err)
	}
}
```

---

### Line-by-Line Code Walkthrough (Production-Grade Server):

- **Line 22-25**: `type SafeConnection struct { ... }`
  Defines a thread-safe client connection wrapper. It combines a `websocket.Conn` pointer with a `sync.Mutex` write lock.
- **Line 28**: `func (sc *SafeConnection) WriteMessage(...)`
  Wraps the raw write method. It locks the mutex before writing to serialize writes, preventing concurrent write crashes.
- **Line 31**: `sc.conn.SetWriteDeadline(time.Now().Add(writeWait))`
  Sets a write deadline. If the socket is blocked, the write fails and returns an error instead of blocking the goroutine indefinitely.
- **Line 44**: `sc.conn.SetReadDeadline(time.Now().Add(pongWait))`
  Sets the initial read deadline. If no data (including Pong heartbeats) is received within this window, the read loop fails.
- **Line 45-49**: `sc.conn.SetPongHandler(...)`
  Registers a callback function. When the server receives a Pong frame from the client, the callback runs and resets the read deadline, keeping the connection alive.
- **Line 52**: `go startHeartbeatTicker(sc)`
  Starts a background goroutine to manage the Ping ticker.
- **Line 72-84**: `func startHeartbeatTicker(...)`
  Sends a Ping frame (`websocket.PingMessage`) to the client at regular intervals (`pingPeriod`). If the write fails (indicating the client has disconnected), it closes the socket.

---

## 6. Common Setup Errors & Troubleshooting

### Scenario A: Port Binding Conflicts
* **The Error**: `listen tcp :8080: bind: address already in use`
* **Why it happens**: Another application is already listening on port 8080 (e.g. an active Docker container or Tomcat instance).
* **The Fix**: Change the port in `http.ListenAndServe` to a free port (like `8081` or `9000`).

### Scenario B: CORS Handshake Rejections (`403 Forbidden`)
* **The Error**: Handshake fails, and the server prints origin mismatch errors.
* **Why it happens**: By default, Gorilla enforces strict host matching. If your client connects from a different domain, the upgrader rejects the connection.
* **The Fix**: Whitelist client origins in the upgrader config:
  ```go
  CheckOrigin: func(r *http.Request) bool {
      return r.Header.Get("Origin") == "https://app.example.com"
  }
  ```

---

## 7. Technical Interview Questions

### Question 1: Buffer Sizes configuration
*How do you determine the optimal read and write buffer sizes in the `websocket.Upgrader`?*

**Answer**:
Read and write buffer sizes depend on your payload patterns:
- If your application transmits small payloads (e.g. under 1 KB), setting the buffer sizes to 1 KB minimizes the memory footprint per connection.
- If your application transmits large payloads (e.g. 64 KB files), setting the buffer sizes to match the payload size reduces CPU usage and system calls.

---

### Question 2: Gorilla Concurrency Safety
*What happens if two goroutines write to the same Gorilla connection simultaneously? How do you prevent this?*

**Answer**:
Writing concurrently from multiple goroutines throws panic errors. 

To prevent this, you must protect write calls using a mutex or route payloads through a write-locking channel.

---

### Question 3: HTTP Server Hijacking
*Explain what happens to the HTTP connection lifecycle when `upgrader.Upgrade` is called.*

**Answer**:
Calling `Upgrade()` asserts the connection as an `http.Hijacker` and takes control of the socket, detaching it from Go's standard HTTP server engine. 

The server writes the `101 Switching Protocols` response headers to switch the protocol state to the WebSocket framing engine.

---

### Question 4: Client Origin Verification
*Why is verifying origin headers critical in public-facing WebSocket upgrades?*

**Answer**:
Origin checks protect your application from Cross-Site WebSocket Hijacking (CSWSH) attacks. 

If origin checks are disabled, a malicious site can establish a connection on behalf of a logged-in user, accessing sensitive data if you rely solely on cookies for authentication.

---

### Question 5: Deadlines in Go
*What is the difference between a write deadline and a read deadline in Go?*

**Answer**:
- **Write Deadline**: The maximum time allowed to write a message to the client's socket.
- **Read Deadline**: The maximum time the server will wait for the client to send a frame. If the deadline expires without data arriving, the read call returns an I/O timeout error, prompting connection cleanup.

---

### Question 6: Heartbeat Frequency
*Why is the ping interval (`pingPeriod`) shorter than the pong wait timeout (`pongWait`)?*

**Answer**:
The ping interval must be shorter than the pong wait timeout to account for network latency and prevent false timeouts:
- The server sends a Ping frame every 54 seconds.
- The client has 60 seconds to respond.
This gives the client 6 seconds of buffer to account for network latency.

---

### Question 7: go.sum File Role
*What is the purpose of the `go.sum` file in a Go project?*

**Answer**:
The `go.sum` file contains cryptographic hashes of downloaded dependencies to guarantee secure, reproducible builds, preventing tampered dependencies from being used.

---

### Question 8: Folder cmd Structure
*Why does the standard Go project layout separate `cmd/` from `internal/` packages?*

**Answer**:
- **`cmd/`** contains the entry points for the application, where each subfolder compiles into a separate executable binary.
- **`internal/`** contains private application logic. Packages here cannot be imported by external projects, enforcing clean boundary abstractions and encapsulation.

---

### Question 9: ReadMessage Blocking Behavior
*Is the `conn.ReadMessage()` call blocking or non-blocking? How does this affect server goroutine sizing?*

**Answer**:
`ReadMessage()` is a blocking call. 

Because it blocks until data is received, the server must dedicate a goroutine to manage the connection read loop. 

Go's lightweight goroutines make this model scalable, allowing thousands of concurrent goroutines to run with minimal resource overhead.

---

### Question 10: Graceful Closures
*How does Gorilla handle Close frames? Do you need to call `conn.Close()` manually after a client close frame is read?*

**Answer**:
When a client sends a Close frame:
1. `conn.ReadMessage()` returns an error indicating the close code (e.g. code `1000`).
2. The server exits its read loop.
3. The server calls the deferred `conn.Close()` method, terminating the TCP socket cleanly.

---

## Summary
- **Dependencies** are managed using Go modules, locking packages in `go.mod`.
- **Project Structure** separates application entry points in `cmd/` from private logic in `internal/`.
- **WebSocket Upgrade Handshakes** are executed using `upgrader.Upgrade`, which hijacks the underlying TCP socket.
- **Gorilla Writes** are not thread-safe. Concurrency safety must be enforced using mutexes or write channels.
- **Ping/Pong Heartbeats** manage connection health and prevent firewall timeouts.
