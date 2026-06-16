# Module 14: Building a Chat Server

Building a real-time chat server requires moving beyond simple echo endpoints and designing structured message routing tables. In a production application, you must support usernames, private messaging, and dynamic rooms (channels) while keeping client message streams isolated.

This module details how to design and build a multi-room chat server in Go. We will explore the hierarchical architecture of Hubs, Rooms, and Clients, implement username and membership management, handle room joins and leaves, isolate broadcast scopes, and complete a mini-project to build a multi-room chat server with message history buffering.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the architecture** of a multi-room real-time chat server.
2. **Implement username registration** and manage active user identities.
3. **Coordinate dynamic room joins and leaves** using Go channels.
4. **Isolate broadcast message scopes** to keep channels private.
5. **Route targeted private messages** directly between users.
6. **Implement a message history buffer** to cache and stream past messages.

---

## 1. Multi-Room Chat Architecture

A multi-room chat server uses a hierarchical data model:

```text
                       ┌─────────────── Hub ────────────────┐
                       │ (Manages Rooms & Client Registry)  │
                       └─────────────────┬──────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
      ┌────── Room A ──────┐                          ┌────── Room B ──────┐
      │ (map[*Client]bool) │                          │ (map[*Client]bool) │
      └──────┬──────────┬──┘                          └──────┬──────────┬──┘
             │          │                                    │          │
             ▼          ▼                                    ▼          ▼
          Client 1   Client 2                             Client 3   Client 4
```

### 1. The Hub
The **Hub** is the root registry. It maintains a list of all active connections and a registry map of active rooms (`map[string]*Room`).

### 2. The Room
A **Room** represents a chat channel. It maintains a map of connected client pointers (`map[*Client]bool`) and manages its own broadcast, join, and leave channels. This design isolates message scopes, ensuring messages in Room A do not leak to Room B.

### 3. The Client
A **Client** represents a connected session. It parses incoming JSON frames from the socket and forwards them to the appropriate room or hub router.

---

## 2. Username & Membership Management

To route messages and display notifications (e.g. `"[Alice] has joined Room 1"`), the server must associate each connection with a username.

### 1. Username Registration
The username is typically collected during authentication or passed as a parameter during connection setup:
- The server checks if the username is taken before upgrading the connection.
- Once upgraded, the username is stored in the `Client` struct.

### 2. Joining and Leaving Rooms
Room membership changes are routed through the room's channels:
- **`join` Channel**: Receives client pointers. The room inserts the client into its local map.
- **`leave` Channel**: Receives client pointers. The room deletes the client from its map.
- When membership changes, the room broadcasts system notification frames to alert other users.

---

## 3. Mini-Project: Complete Multi-Room Chat Server

Let us build a complete, compilable Go multi-room chat server.

### Complete Go Server Implementation:

```go
package main

import (
	"encoding/json"
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

// 1. Define message models
type WSMessage struct {
	Action   string `json:"action"`   // "join", "leave", "send", "private"
	RoomName string `json:"room"`     // The room name
	Target   string `json:"target"`   // The recipient's username (for private messages)
	Content  string `json:"content"`
	Sender   string `json:"sender"`   // Added by the server
}

type Client struct {
	hub      *Hub
	conn     *websocket.Conn
	send     chan []byte
	username string
}

type Room struct {
	name       string
	clients    map[*Client]bool
	broadcast  chan []byte
	join       chan *Client
	leave      chan *Client
	history    []string     // Caches the last 10 messages
	historyMu  sync.RWMutex // Protects history slice
}

type Hub struct {
	clients    map[string]*Client // Map of online clients (username -> Client)
	rooms      map[string]*Room   // Map of active rooms
	register   chan *Client
	unregister chan *Client
	clientsMu  sync.RWMutex
	roomsMu    sync.RWMutex
}

func NewHub() *Hub {
	return &Hub{
		clients:    make(map[string]*Client),
		rooms:      make(map[string]*Room),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

func NewRoom(name string) *Room {
	return &Room{
		name:      name,
		clients:   make(map[*Client]bool),
		broadcast: make(chan []byte),
		join:      make(chan *Client),
		leave:     make(chan *Client),
		history:   make([]string, 0),
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.clientsMu.Lock()
			h.clients[client.username] = client
			h.clientsMu.Unlock()
			log.Printf("[Hub] Client registered: %s\n", client.username)

		case client := <-h.unregister:
			h.clientsMu.Lock()
			if _, exists := h.clients[client.username]; exists {
				delete(h.clients, client.username)
				close(client.send)
				log.Printf("[Hub] Client unregistered: %s\n", client.username)
			}
			h.clientsMu.Unlock()

			// Remove client from all active rooms
			h.roomsMu.RLock()
			for _, room := range h.rooms {
				room.leave <- client
			}
			h.roomsMu.RUnlock()
		}
	}
}

func (r *Room) Run() {
	for {
		select {
		case client := <-r.join:
			r.clients[client] = true
			log.Printf("[Room %s] Client joined: %s\n", r.name, client.username)
			
			// Stream message history to the newly joined client
			r.streamHistory(client)
			
			// Send join notification
			notification, _ := json.Marshal(WSMessage{
				Action:   "system",
				RoomName: r.name,
				Content:  fmt.Sprintf("%s joined the room", client.username),
			})
			r.broadcastMessage(notification)

		case client := <-r.leave:
			if _, exists := r.clients[client]; exists {
				delete(r.clients, client)
				log.Printf("[Room %s] Client left: %s\n", r.name, client.username)
				
				// Send leave notification
				notification, _ := json.Marshal(WSMessage{
					Action:   "system",
					RoomName: r.name,
					Content:  fmt.Sprintf("%s left the room", client.username),
				})
				r.broadcastMessage(notification)
			}

		case message := <-r.broadcast:
			// Append message to history
			r.appendHistory(message)
			// Send message to all room members
			r.broadcastMessage(message)
		}
	}
}

func (r *Room) broadcastMessage(message []byte) {
	for client := range r.clients {
		select {
		case client.send <- message:
		default:
			close(client.send)
			delete(r.clients, client)
		}
	}
}

func (r *Room) appendHistory(message []byte) {
	r.historyMu.Lock()
	defer r.historyMu.Unlock()
	
	var msg WSMessage
	json.Unmarshal(message, &msg)
	historyEntry := fmt.Sprintf("[%s] %s: %s", time.Now().Format("15:04"), msg.Sender, msg.Content)
	
	r.history = append(r.history, historyEntry)
	if len(r.history) > 10 {
		r.history = r.history[1:] // Keep last 10 messages
	}
}

func (r *Room) streamHistory(client *Client) {
	r.historyMu.RLock()
	defer r.historyMu.RUnlock()
	
	for _, entry := range r.history {
		historyMsg, _ := json.Marshal(WSMessage{
			Action:   "history",
			RoomName: r.name,
			Content:  entry,
		})
		client.send <- historyMsg
	}
}

func (c *Client) readPump() {
	defer func() {
		c.hub.unregister <- c
		c.conn.Close()
	}()

	for {
		_, payload, err := c.conn.ReadMessage()
		if err != nil {
			break
		}

		var msg WSMessage
		err = json.Unmarshal(payload, &msg)
		if err != nil {
			log.Println("[Client Read] Malformed payload:", err)
			continue
		}

		msg.Sender = c.username

		switch msg.Action {
		case "join":
			c.hub.roomsMu.Lock()
			room, exists := c.hub.rooms[msg.RoomName]
			if !exists {
				room = NewRoom(msg.RoomName)
				c.hub.rooms[msg.RoomName] = room
				go room.Run()
			}
			c.hub.roomsMu.Unlock()
			room.join <- c

		case "leave":
			c.hub.roomsMu.RLock()
			room, exists := c.hub.rooms[msg.RoomName]
			c.hub.roomsMu.RUnlock()
			if exists {
				room.leave <- c
			}

		case "send":
			c.hub.roomsMu.RLock()
			room, exists := c.hub.rooms[msg.RoomName]
			c.hub.roomsMu.RUnlock()
			if exists {
				responseBytes, _ := json.Marshal(msg)
				room.broadcast <- responseBytes
			}

		case "private":
			c.hub.clientsMu.RLock()
			targetClient, exists := c.hub.clients[msg.Target]
			c.hub.clientsMu.RUnlock()
			if exists {
				responseBytes, _ := json.Marshal(WSMessage{
					Action:  "private",
					Sender:  c.username,
					Content: msg.Content,
				})
				targetClient.send <- responseBytes
			}
		}
	}
}

func (c *Client) writePump() {
	defer c.conn.Close()

	for msg := range c.send {
		c.conn.WriteMessage(websocket.TextMessage, msg)
	}
}

func handleChatConnection(hub *Hub) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}

		username := r.URL.Query().Get("username")
		if username == "" {
			conn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(4000, "Username missing"))
			conn.Close()
			return
		}

		client := &Client{
			hub:      hub,
			conn:     conn,
			send:     make(chan []byte, 256),
			username: username,
		}

		hub.register <- client

		go client.writePump()
		client.readPump()
	}
}

func main() {
	hub := NewHub()
	go hub.Run()

	http.HandleFunc("/ws", handleChatConnection(hub))
	log.Println("[Chat Gateway] Running on :8080...")
	http.ListenAndServe(":8080", nil)
}
```

---

### Line-by-Line Code Walkthrough:

- **Line 28**: `type Room struct { ... }`
  Defines the Room struct. It maintains a map of clients in the room, join/leave channels, a broadcast channel, and message history.
- **Line 37**: `type Hub struct { ... }`
  Defines the root Hub struct. It maps usernames to clients and active room names to Room instances.
- **Line 92**: `go room.Run()`
  Spawns the event loop for a room in a new goroutine when a client creates or joins a new room.
- **Line 95-104**: `case client := <-r.join:`
  Adds the client to the room's client map, streams the room's message history to them, and broadcasts a system join notification to other room members.
- **Line 132**: `r.appendHistory(message)`
  Saves broadcasted messages to the room's history buffer.
- **Line 144**: `r.history = append(r.history, ...)`
  Appends messages to the history slice and trims the slice to keep only the last 10 messages.
- **Line 185**: `case "join":`
  Looks up the requested room. If it does not exist, the server instantiates it, starts its event loop, and registers the client.
- **Line 211**: `case "private":`
  Looks up the target username in the Hub's client map. If online, the server routes the message directly to their send queue, bypassing broadcasts.

---

## 4. Exercises: Extending Chat Features

To scale the server and improve the user experience:
- **Exercise**: Modify the `appendHistory` and `streamHistory` functions to buffer **the last 50 messages** in a thread-safe manner, and notify clients of room activity levels.
- **Goal**: Implement this change in the `Room` struct code.

---

## 5. Technical Interview Questions

### Question 1: Room Message Isolation
*How does this architecture ensure messages in Room A are isolated from Room B?*

**Answer**:
Each room operates as an independent actor running its own event loop and maintaining its own client map. 

When a message is broadcast, the room only iterates over clients in its local map, ensuring messages in Room A do not leak to Room B.

---

### Question 2: Locking Shared Maps
*Why does the Hub require mutex locks like `roomsMu` when modifying the `rooms` map?*

**Answer**:
The client read pumps run in separate, concurrent goroutines:
- If multiple clients join or leave rooms simultaneously, their read pumps will read and write to the Hub's `rooms` map concurrently.
- Because Go maps are not thread-safe, this concurrent access would throw runtime panics. Protecting map access with a read-write mutex lock prevents these race conditions.

---

### Question 3: Room Lifecycle Cleanup
*What happens to the room's event loop goroutine when the last client leaves? How do you prevent goroutine leaks?*

**Answer**:
In our basic implementation, the room event loop runs indefinitely even if it is empty, leaking resources. 

To prevent leaks, modify the room's leave case to check if `len(r.clients) == 0`. 

If empty, notify the Hub to delete the room from the active map and exit the room's event loop, cleaning up the goroutine.

---

### Question 4: Username Verification
*Why should username uniqueness be validated during the handshake rather than inside the read loop?*

**Answer**:
Validating username uniqueness during the handshake allows the server to reject duplicate usernames early at the HTTP layer, preventing the server from upgrading unauthorized connections and allocating resources.

---

### Question 5: Private Message Routing
*What is the time complexity of private messaging in our Hub?*

**Answer**:
Direct lookup in the Hub's client map (`h.clients[msg.Target]`) has $O(1)$ complexity, enabling efficient peer-to-peer delivery without iterating over active connections.

---

### Question 6: History Buffer Lock
*Why does the history buffer require a separate `historyMu` read-write lock?*

**Answer**:
The history buffer is read when a client joins a room (via the room event loop) and can be accessed concurrently by other operations. 

Protecting the history slice with a read-write mutex lock prevents concurrent modification race conditions.

---

### Question 7: Select default behavior
*What does the `default` case inside the `broadcastMessage` function do when a client's send queue is full?*

**Answer**:
It drops the slow client and closes their connection, preventing them from stalling the room's event loop.

---

### Question 8: Context cancel propagation?
*Why does client unregistration unregister the client from all active rooms?*

**Answer**:
If a disconnected client is not removed from room registries, the server will continue attempting to route messages to their closed channel, leaking resources and triggering errors.

---

### Question 9: Gorilla read limit chat
*Why should you configure a read limit on chat client connections?*

**Answer**:
Setting a read limit (e.g. 512 bytes for chat text) prevents malicious clients from sending huge payloads to crash the server.

---

### Question 10: Horizontal Scaling Chat
*How would you scale this multi-room chat server across multiple nodes?*

**Answer**:
A single node only knows about local clients. 

To route messages across nodes, you must deploy a shared message broker (like Redis Pub/Sub) to synchronize chat room actions between server instances.

---

## Summary
- **The Chat Server** uses a hierarchical Hub-Room-Client architecture to isolate communication channels.
- **Rooms** maintain their own client lists and manage message broadcasting within their scope.
- **Membership modifications** (joining and leaving rooms) are processed using Go channels to coordinate actions cleanly.
- **Shared registries** (rooms and online clients maps) must be protected using mutex locks to prevent concurrency panics.
- **Message history buffers** cache past messages, streaming them to clients when they join a room.
- Whitelist client domains and enforce payload limits to secure your server.
