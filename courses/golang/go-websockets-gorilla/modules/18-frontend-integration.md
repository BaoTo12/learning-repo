# Module 18: Frontend Integration

Connecting a backend WebSocket gateway to a modern frontend application requires understanding client-side state management. Unlike standard HTTP requests, WebSockets maintain stateful, persistent channels. In React and Next.js applications, you must manage connection lifecycles within component lifecycles, handle page navigations, serialize structured payloads, and synchronize UI state without triggering memory leaks or double-connection bugs.

This module details how to integrate WebSockets with React and Next.js. We will explore the browser's JavaScript WebSocket API, design a custom reusable React hook (`useWebSocket`) that handles reconnection and connection state, implement message serialization, and build a real-time chat interface.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the states and events** of the browser's JavaScript WebSocket API.
2. **Manage WebSocket lifecycles** inside React components using hooks.
3. **Design a reusable `useWebSocket` hook** featuring exponential backoff.
4. **Serialize and deserialize JSON message payloads** safely.
5. **Mitigate double-connection bugs** caused by React StrictMode.
6. **Synchronize local UI state** with real-time server events.

---

## 1. The JavaScript WebSocket API

The browser provides a native `WebSocket` API to establish and manage connections.

### Connection States (`readyState`)
A WebSocket instance maintains an internal state accessible via the `socket.readyState` property:

- **`0 (CONNECTING)`**: The connection is in the process of opening.
- **`1 (OPEN)`**: The connection is established and ready for full-duplex communication.
- **`2 (CLOSING)`**: The connection is in the process of closing.
- **`3 (CLOSED)`**: The connection is closed.

---

### Core Event Listeners
The API uses event listeners to handle connection lifecycle events:

```javascript
const socket = new WebSocket("ws://localhost:8080/ws");

// 1. Triggered on successful handshake
socket.onopen = (event) => {
    console.log("Connection established");
};

// 2. Triggered when a new frame is received
socket.onmessage = (event) => {
    console.log("Received data:", event.data);
};

// 3. Triggered when the connection closes
socket.onclose = (event) => {
    console.log(`Connection closed. Code: ${event.code}`);
};

// 4. Triggered when the connection encounters an error
socket.onerror = (error) => {
    console.error("Socket error:", error);
};
```

---

## 2. React & Next.js Integration Challenge

In a stateless client-side application, instantiating a WebSocket connection directly in the component body creates bugs:

```javascript
// Anti-Pattern: Instantiating socket in the component body
function ChatComponent() {
    const socket = new WebSocket("ws://localhost:8080/ws"); // Re-instantiates on every render!
    return <div>Chat View</div>;
}
```

- **The Problem**: React re-renders components frequently in response to state changes. Instantiating the connection in the component body causes a new socket connection to open on every render, exhausting server resources and crashing the client.

---

### The Solution: The `useWebSocket` Hook
To integrate WebSockets with React:
1. **Manage connection lifecycles in `useEffect`**: Establish the connection when the component mounts, and close it when the component unmounts.
2. **Store the socket instance in `useRef`**: `useRef` persists the socket instance across renders without triggering component re-renders.

Below is an implementation of a custom **`useWebSocket`** hook featuring exponential backoff reconnection logic:

```javascript
import { useEffect, useRef, useState, useCallback } from "react";

export function useWebSocket(url) {
    const [status, setStatus] = useState("CONNECTING");
    const [messages, setMessages] = useState([]);
    const socketRef = useRef(null);
    const attemptRef = useRef(0);

    const connect = useCallback(() => {
        setStatus("CONNECTING");
        const socket = new WebSocket(url);
        socketRef.current = socket;

        socket.onopen = () => {
            setStatus("OPEN");
            attemptRef.current = 0; // Reset reconnection attempts
        };

        socket.onmessage = (event) => {
            try {
                // Parse incoming JSON payload
                const data = JSON.parse(event.data);
                setMessages((prev) => [...prev, data]);
            } catch (err) {
                console.warn("Failed to parse incoming payload:", err);
            }
        };

        socket.onclose = () => {
            setStatus("CLOSED");
            // Schedule reconnection using exponential backoff with randomized jitter
            const backoff = Math.min(16000, 1000 * Math.pow(2, attemptRef.current));
            const jitter = backoff * (0.5 + Math.random() * 0.5);
            
            setTimeout(() => {
                attemptRef.current += 1;
                connect();
            }, jitter);
        };

        socket.onerror = () => {
            setStatus("ERROR");
        };
    }, [url]);

    useEffect(() => {
        connect();
        return () => {
            // Cleanup: Close the connection when the component unmounts
            if (socketRef.current) {
                socketRef.current.close();
            }
        };
    }, [connect]);

    // Send payload safely
    const sendMessage = useCallback((payload) => {
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify(payload));
        } else {
            console.warn("Cannot send message: socket offline");
        }
    }, []);

    return { status, messages, sendMessage };
}
```

---

## 3. Exercises: Building a React Chat UI

In this exercise, you will build a React chat component that integrates the `useWebSocket` hook to display connection status and stream real-time chat messages.

### Complete React Chat Component Implementation:

```jsx
import React, { useState } from "react";
import { useWebSocket } from "./useWebSocket"; // Import the custom hook

export default function ChatRoomUI() {
    const { status, messages, sendMessage } = useWebSocket("ws://localhost:8080/ws?username=Alice");
    const [inputText, setInputText] = useState("");

    const handleFormSubmit = (event) => {
        event.preventDefault(); // Prevent page reload
        if (!inputText.trim()) return;

        // Construct message payload
        const payload = {
            action: "send",
            room: "general",
            content: inputText,
        };

        sendMessage(payload);
        setInputText(""); // Clear input field
    };

    // Helper to render connection status indicators
    const renderStatusBadge = () => {
        switch (status) {
            case "OPEN":
                return <span style={{ color: "green", fontWeight: "bold" }}>● Connected</span>;
            case "CONNECTING":
                return <span style={{ color: "orange" }}>○ Connecting...</span>;
            case "CLOSED":
                return <span style={{ color: "red" }}>● Disconnected</span>;
            default:
                return <span style={{ color: "red" }}>● Error</span>;
        }
    };

    return (
        <div style={{ maxWidth: "600px", margin: "20px auto", fontFamily: "sans-serif" }}>
            <h2>Real-Time Chat Room</h2>
            <div style={{ marginBottom: "15px" }}>
                Status: {renderStatusBadge()}
            </div>

            {/* Chat Messages Viewport */}
            <div style={{
                width: "100%",
                height: "350px",
                border: "1px solid #ccc",
                borderRadius: "4px",
                overflowY: "scroll",
                padding: "10px",
                boxSizing: "border-box",
                backgroundColor: "#f9f9f9",
                marginBottom: "15px"
            }}>
                {messages.map((msg, index) => (
                    <div key={index} style={{ marginBottom: "10px" }}>
                        <span style={{ fontWeight: "bold", color: "#333" }}>{msg.sender || "System"}: </span>
                        <span>{msg.content}</span>
                    </div>
                ))}
            </div>

            {/* Message Input Form */}
            <form onSubmit={handleFormSubmit} style={{ display: "flex", gap: "10px" }}>
                <input
                    type="text"
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    placeholder="Type a message..."
                    disabled={status !== "OPEN"}
                    style={{
                        flexGrow: 1,
                        padding: "8px",
                        border: "1px solid #ccc",
                        borderRadius: "4px"
                    }}
                />
                <button
                    type="submit"
                    disabled={status !== "OPEN"}
                    style={{
                        padding: "8px 16px",
                        backgroundColor: status === "OPEN" ? "#0070f3" : "#ccc",
                        color: "white",
                        border: "none",
                        borderRadius: "4px",
                        cursor: status === "OPEN" ? "pointer" : "default"
                    }}
                >
                    Send
                </button>
            </form>
        </div>
    );
}
```

---

### Line-by-Line Code Walkthrough (React Chat UI):

- **Line 5**: `const { status, messages, sendMessage } = useWebSocket(...)`
  Integrates our custom `useWebSocket` hook, automatically managing connection lifecycles, states, and message streams.
- **Line 9**: `event.preventDefault()`
  Prevents the browser from reloading the page during form submission, keeping the connection open.
- **Line 18**: `sendMessage(payload)`
  Calls the hook's helper function to serialize the JSON message and send it over the socket.
- **Line 47-59**: `{messages.map(...)`
  Maps over the messages state array to render chat messages in the UI.
- **Line 70**: `disabled={status !== "OPEN"}`
  Disables the input field and submit button when the connection is offline to prevent users from sending messages.

---

## 4. Common Frontend Pitfalls & Mitigation

### 1. Double-Mounting in React StrictMode
- **The Problem**: In development mode, React StrictMode mounts and unmounts components twice on initialization to identify resource leaks.
- **The Risk**: This double-mounting instantiates two socket connections concurrently, leading to resource leaks on the server.
- **The Fix**: Ensure your `useEffect` return function closes the socket instance correctly:
  ```javascript
  useEffect(() => {
      connect();
      return () => {
          if (socketRef.current) socketRef.current.close(); // Clean up socket on unmount
      };
  }, [connect]);
  ```

---

### 2. Stale Closures in Event Listeners
- **The Problem**: In React, if you reference state variables inside event listener callbacks, they may capture values from older renders (stale closures).
- **The Rationale**: This occurs because the listener is instantiated once and does not update when state changes.
- **The Fix**: Use functional state updates (e.g. `setMessages(prev => [...prev, newMsg])`) to access the current state.

---

## 5. Technical Interview Questions

### Question 1: Socket instantiation location
*Why is it an anti-pattern to instantiate a WebSocket connection in the body of a React component?*

**Answer**:
React re-renders components in response to state changes. 

Instantiating the connection in the component body causes a new socket connection to open on every render, exhausting server resources and crashing the client.

---

### Question 2: React StrictMode Double Connections
*How does React StrictMode affect WebSocket connections, and how do you mitigate this?*

**Answer**:
React StrictMode mounts and unmounts components twice on initialization to identify resource leaks. 

To prevent this from leaving duplicate sockets open, ensure your `useEffect` return function closes the socket instance correctly during cleanup.

---

### Question 3: State Updates in Event Listeners
*Why should you use functional state updates (e.g. `setMessages(prev => [...prev, newMsg])`) inside `onmessage` callbacks?*

**Answer**:
Event listener callbacks are defined once on connection setup. 

If you reference state variables directly, they may capture values from older renders (stale closures). 

Using functional state updates allows you to safely access the current state.

---

### Question 4: useRef role
*What is the role of `useRef` in managing the WebSocket instance?*

**Answer**:
`useRef` persists the socket instance across component renders without triggering component re-renders when the socket state changes.

---

### Question 5: JSON parsing exception handling
*Why is it critical to wrap `JSON.parse` in a try-catch block inside the message callback?*

**Answer**:
If the server sends a malformed or non-JSON frame, calling `JSON.parse` directly will throw an exception, crashing the client-side JavaScript execution thread. 

Wrapping it in a try-catch block handles the exception gracefully.

---

### Question 6: ws/wss production
*Why must you run WebSockets over WSS in production?*

**Answer**:
WSS encrypts frame payloads, preventing intermediate routers and proxies from sniffing or tampering with data.

---

### Question 7: websocket.readyState closing
*What is the numeric value of `readyState` when a WebSocket connection is in the CLOSING state?*

**Answer**:
The value is `2`.

---

### Question 8: NextJS Server-Side Rendering
*Why must WebSocket instantiations be wrapped in browser checks in Next.js applications?*

**Answer**:
Next.js renders components on the server-side first (SSR). 

Since the server environment lacks browser APIs like `WebSocket`, attempting to instantiate the socket directly on the server throws exceptions. 

Mitigate this by wrapping instantiation in `useEffect` or checking `typeof window !== "undefined"`.

---

### Question 9: websocket.close() code limits
*Can you pass custom close codes to the client-side `socket.close(code, reason)` method?*

**Answer**:
Yes, but the code must be in the range `3000-4999` (reserved for application-level statuses) to prevent conflict with standard RFC codes.

---

### Question 10: State synchronization lag
*How do you prevent state synchronization lag in chat UIs under high message throughput?*

**Answer**:
Under high throughput, state updates can trigger excessive re-renders. 

Mitigate this by buffering updates in a queue and updating the state at throttled intervals.

---

## Summary
- **Manage connection lifecycles** inside `useEffect` blocks to align socket lifetimes with component lifecycles.
- **Store the socket instance** in `useRef` to persist it across renders.
- **Use functional state updates** inside event listeners to prevent stale closures.
- **Wrap `JSON.parse`** in try-catch blocks to prevent malformed payloads from crashing the UI.
- **Ensure cleanup functions** are configured correctly to mitigate double-mounting in StrictMode.
- Disable input fields and send buttons when the connection is offline.
