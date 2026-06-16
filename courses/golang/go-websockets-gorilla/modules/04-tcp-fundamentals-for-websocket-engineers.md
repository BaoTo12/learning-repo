# Module 4: TCP Fundamentals for WebSocket Engineers

The WebSocket protocol is a thin framing layer. In a running system, a WebSocket connection *is* a TCP connection in a specific state. Because WebSockets run directly on top of the Transmission Control Protocol (TCP), the latency, throughput, and reliability characteristics of your real-time application are dictated by the underlying TCP socket engine.

This module explores TCP fundamentals from the perspective of a real-time systems engineer. We will study the TCP three-way handshake, analyze reliable delivery and ordering guarantees, examine sliding window flow control and congestion control protocols, diagnose the threat of half-open connections, compare OS keep-alives with application-level heartbeats, and explain why TCP-level Head-of-Line (HoL) blocking introduces latency spikes. We will conclude with a hands-on lab using Wireshark to analyze raw TCP packets.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Trace the TCP three-way handshake** and explain its connection state transitions.
2. **Explain how TCP guarantees reliable, ordered delivery** using sequence numbers and retransmissions.
3. **Analyze sliding window flow control** and diagnose how slow application reads throttle write buffers.
4. **Describe the impact of TCP congestion control** (Slow Start) on fresh WebSocket connections.
5. **Diagnose half-open connections** caused by silent mobile drops and stateful firewall timeouts.
6. **Evaluate the trade-offs** between OS-level TCP Keep-Alives and application-level Ping/Pong heartbeats.
7. **Explain TCP Head-of-Line blocking** and compare it to QUIC-based WebTransport.
8. **Analyze raw network packet captures in Wireshark** to inspect handshakes and frame payloads.

---

## 1. Why WebSocket Engineers Must Understand TCP

When you write code using a library like Gorilla WebSocket, it is easy to forget about the network layer.
- You call `conn.WriteMessage(websocket.TextMessage, []byte("Hello"))` and assume the bytes arrive at the client instantly.
- In reality, the bytes are copied to a **Write Buffer** managed by the operating system kernel.
- The OS network stack packetizes these bytes into TCP segments and sends them over the network.
- If the network experiences packet loss, latency, or congestion, the underlying TCP stack modifies transmission behavior, delaying your messages.
- Understanding TCP ensures you can debug connection timeouts, latency spikes, and buffer bloat in production.

---

## 2. The TCP Three-Way Handshake

Before any application bytes (including the WebSocket HTTP Upgrade request) can be sent, the transport layers must establish connection states.

### Handshake Sequence and State Transitions:

```text
Client (Socket)                                           Server (Socket)
  │                                                           │
  │ [CLOSED]                                                  │ [LISTEN]
  │                                                           │
  │ ─── SYN (Seq=1000, ACK=0) ──────────────────────────────► │ (Allocates buffers)
  │ [SYN-SENT]                                                │ [SYN-RECEIVED]
  │                                                           │
  │ ◄── SYN-ACK (Seq=5000, ACK=1001) ──────────────────────── │ (Allocates buffers)
  │ [ESTABLISHED]                                             │
  │                                                           │
  │ ─── ACK (Seq=1001, ACK=5001) ───────────────────────────► │ [ESTABLISHED]
  │                                                           │
  ▼                                                           ▼
```

### 1. The SYN Phase
- The client initiates connection setup by sending a packet with the **`SYN` (Synchronize)** flag set.
- It generates a random Initial Sequence Number (ISN), represented as `Seq = 1000`.
- The client socket state transitions to **`SYN-SENT`**.

### 2. The SYN-ACK Phase
- The server receives the SYN packet on its listening port.
- It allocates kernel memory buffers for the socket.
- It generates its own ISN, represented as `Seq = 5000`.
- It sets both the **`SYN`** and **`ACK` (Acknowledge)** flags. It acknowledges the client's packet by setting `ACK = 1001` (client ISN + 1).
- The server socket state transitions to **`SYN-RECEIVED`**.

### 3. The ACK Phase
- The client receives the `SYN-ACK` packet.
- It allocates memory buffers and transitions to **`ESTABLISHED`**.
- It returns an **`ACK`** packet with `Seq = 1001` and `ACK = 5001` (server ISN + 1).
- The server receives the ACK packet and transitions to **`ESTABLISHED`**.

*Latency Impact*: The three-way handshake requires **1 complete Round-Trip Time (RTT)**. No application data (like the WebSocket Upgrade headers) can be sent until this handshake completes.

---

## 3. Reliable Delivery and Ordering Guarantees

TCP guarantees that all transmitted bytes are delivered to the application **reliably and in the exact order they were written**.

### 1. Sequence and Acknowledgment Numbers
- Every byte transmitted over a TCP connection is assigned a sequential number.
- If the client sends a 100-byte frame, it sets the packet's `Sequence Number` to the index of the first byte.
- The receiver must return an `ACK` packet containing the sequence number of the next byte it expects to receive.
- If the sender does not receive an acknowledgment within a specific timeout (Retransmission Timeout - RTO), it assumes the packet was lost and retransmits it.

### 2. Ordering Guarantees (The Receiver Buffer)
Packets traveling over the internet can take different routing paths, arriving out of order (e.g. packet 3 arriving after packet 4).
- The receiver's TCP stack holds out-of-order packets in a kernel buffer.
- It does **not** release packet 4 to the application layer until packet 3 arrives and is acknowledged.
- This ensures the application reads a clean, ordered stream of bytes.

---

## 4. Flow Control & Sliding Windows

What happens if a sender transmits data faster than the receiver can process it?

### The Sliding Window Mechanism
TCP implements **Flow Control** using the **Sliding Window** mechanism to prevent the sender from overwhelming the receiver's buffers:
- The receiver includes a **`Window Size` (`Win`)** field in every ACK packet.
- This field advertises the remaining space in the receiver's buffer in bytes.
- The sender is allowed to transmit up to the advertised window size without receiving an ACK.

```text
Sender Buffer:   [ Sent & ACKed ] [ Sent but unACKed (Window Size Limit) ] [ Unsent ]
                                 ▲                                        ▲
                                 └───────────── Sliding Window ───────────┘
```

### Throttling WebSocket Senders
In real-time systems, this mechanism can stall senders:
1. Suppose a Go server pushes high-frequency events to a mobile client on a slow connection.
2. The client application reads slowly from the socket.
3. The client's OS kernel buffer fills up.
4. The client's TCP stack advertises a window size of `0` in its ACK packets.
5. The Go server's TCP stack detects the zero window and stops sending packets, queuing subsequent frames in kernel memory.
6. The server's write buffer fills up, causing write calls (like `conn.WriteMessage`) to block, consuming server memory.

---

## 5. Congestion Control

Flow control prevents the sender from overwhelming the receiver. **Congestion Control** prevents the sender from overwhelming the network infrastructure (routers, switches, links).

### The Congestion Window (`cwnd`)
The sender maintains a variable called the **Congestion Window (`cwnd`)**, representing the maximum amount of data it can send before receiving an ACK.

### Congestion Control Phases:

#### 1. Slow Start
When a connection is established, the sender does not know the available network capacity.
- It sets `cwnd` to a small value (typically 10 segments, or $\approx 14$ KB).
- For every ACK received, it increases `cwnd` exponentially (doubling it every RTT).
- **Impact on WebSockets**: Fresh connections perform slower initially. If you send a large message immediately after the handshake, it takes multiple round-trips to ramp up the transmission rate.

#### 2. Congestion Avoidance (AIMD)
Once `cwnd` hits a threshold (Slow Start Threshold - ssthresh), it switches to a linear growth model (Additive Increase, Multiplicative Decrease):
- **Additive Increase**: Increases `cwnd` by 1 segment per RTT.
- **Multiplicative Decrease**: If packet loss is detected (indicating network congestion), the sender cuts `cwnd` in half immediately.

---

## 6. Half-Open Connections

A major threat to stateful WebSocket applications is the **Half-Open Connection**:
- A connection is half-open if one side has crashed or disconnected without notifying the other side.

### The Mobile Silent Drop Scenario:
1. A user is connected to a WebSocket chat server on their mobile phone.
2. The user enters an elevator, losing cell coverage instantly.
3. The phone's network card drops connection states without transmitting TCP termination packets (`FIN` or `RST`).
4. The server's TCP stack believes the client is still online, keeping the socket active in memory.
5. If the server does not write data to the client, the socket remains open indefinitely, leaking file descriptors and memory.

### Firewall Idle Timeouts
Intermediate stateful firewalls track active connection states in a NAT table.
- To conserve memory, firewalls drop connection records if no packets are sent for a specific period (e.g. 5 minutes).
- When the client attempts to write data after this timeout, the firewall rejects the packets, forcing the connection to drop.

---

## 7. Keepalive Strategies: TCP vs. Application

To detect half-open connections and prevent firewall drops, applications must implement keepalive heartbeats.

### Option 1: OS-Level TCP Keep-Alives
Operating systems support native TCP keep-alives via the `SO_KEEPALIVE` socket option:
- If a socket is idle, the OS kernel automatically transmits a zero-length probe packet.
- If the receiver is online, its TCP stack returns an ACK. If the receiver is dead, it returns a reset (`RST`) or fails to respond, prompting the OS to close the socket.
- **The Drawback**: Standard Linux settings are optimized for legacy systems and are too slow for real-time applications:
  - `tcp_keepalive_time` defaults to **7200 seconds (2 hours)**.
  - `tcp_keepalive_intvl` defaults to 75 seconds.
  - `tcp_keepalive_probes` defaults to 9.

---

### Option 2: Application-Level Ping/Pong Heartbeats
WebSockets solve this by implementing application-level Ping (`0x9`) and Pong (`0xA`) control frames:
- The server sends a Ping frame every 30 seconds.
- The client must respond immediately with a Pong frame.
- If the server does not receive the Pong frame within a write deadline (e.g. 10 seconds), it closes the connection.

### Comparison Matrix

| Metric | OS TCP Keepalive | Application Ping/Pong |
| :--- | :--- | :--- |
| **Layer** | Transport Layer (TCP) | Application Layer (WebSocket) |
| **Default Frequency** | 2 Hours (Tuner-dependent) | Custom (Typically 30 seconds) |
| **Proxy Traversal** | Often stripped by proxies | Traverses through proxies natively |
| **Detection Speed** | Slow (Default: 2+ Hours) | Fast (Seconds) |
| **Application Control**| None (Managed by OS kernel) | Complete (Managed by code) |

---

## 8. TCP-Level Head-of-Line (HoL) Blocking

Because TCP guarantees strict ordered delivery, it suffers from **Head-of-Line (HoL) blocking** when packets are lost.

```text
Frame Streams sent:   [ Frame 1 ] [ Frame 2 ] [ Frame 3 ] [ Frame 4 ]
Network packets:       Packet 1    Packet 2    Packet 3    Packet 4
                                                 ▲
                                             (Dropped!)
Receiver Queue:       [ Packet 1 ] [ Packet 2 ] [ Stalled... ] [ Packet 4 ]
                      (Releases 1 & 2)           (Packet 4 is held in buffer)
```

1. A client sends 4 WebSocket frames wrapped in 4 TCP packets.
2. Packet 3 is lost due to network noise.
3. Packet 4 arrives successfully.
4. The receiver's TCP stack holds Packet 4 in its buffer and **does not release it** to the WebSocket parser, waiting for Packet 3 to be retransmitted.
5. This delays all subsequent frames, causing latency spikes.

### The Solution: WebTransport (HTTP/3 QUIC)
WebTransport runs over UDP using the QUIC protocol:
- QUIC supports independent streams.
- If a packet in Stream A is lost, Stream B continues processing, eliminating TCP Head-of-Line blocking entirely.

---

## 9. Hands-On Lab: Wireshark Packet Capture Analysis

In this lab, you will capture and analyze raw TCP packets during a WebSocket connection handshake using Wireshark.

### Steps:

#### 1. Start Wireshark Capture
1. Download and install **Wireshark** (https://www.wireshark.org/).
2. Open Wireshark and select your active network interface (e.g. Loopback Adapter if running locally, or Wi-Fi/Ethernet).
3. Apply the capture filter:
   `tcp.port == 8080`
4. Click the blue shark fin icon to start capturing.

#### 2. Establish Connection
1. Start your local Go WebSocket application listening on port `8080`.
2. Connect a browser client.
3. Send a few text messages.
4. Close the browser tab to disconnect.

#### 3. Stop and Analyze Capture
1. Click the red square icon in Wireshark to stop the capture.
2. You will see a list of packets:
   - Look for the first three packets. Note the Info column:
     - `[SYN]` -> Client to Server
     - `[SYN, ACK]` -> Server to Client
     - `[ACK]` -> Client to Server
     - This is the **TCP Three-Way Handshake**.
   - Look for the fourth packet:
     - `GET /ws HTTP/1.1` -> The client HTTP upgrade request.
   - Look for the fifth packet:
     - `HTTP/1.1 101 Switching Protocols` -> The server response.
   - Look for subsequent packets:
     - WebSocket frames will be identified in the Info column as `WebSocket Text` or `WebSocket Ping/Pong`.

---

## 10. Technical Interview Questions

### Question 1: TCP Head-of-Line Blocking
*Explain TCP Head-of-Line blocking and how it impacts real-time applications.*

**Answer**:
Head-of-Line (HoL) blocking occurs because TCP guarantees strict ordered delivery. 

If a packet is lost, the receiver's TCP stack holds all subsequent packets in its buffer and does not release them to the application layer until the lost packet is retransmitted. 

For real-time applications, this delays independent messages (like game updates or chat messages) that arrived successfully, causing latency spikes.

---

### Question 2: Flow Control vs. Congestion Control
*What is the difference between Flow Control and Congestion Control in TCP?*

**Answer**:
- **Flow Control** prevents the sender from overwhelming the receiver's buffers. It uses the **Sliding Window Size (`Win`)** field in ACK packets to advertise available buffer space.
- **Congestion Control** prevents the sender from overwhelming the network infrastructure. It uses a **Congestion Window (`cwnd`)** variable, starting with a small window (Slow Start) and adjusting based on network capacity and packet loss.

---

### Question 3: Fresh Connection Latency
*Why do fresh WebSocket connections often experience throughput delays when transmitting large payloads immediately after the handshake?*

**Answer**:
This is caused by **TCP Slow Start**:
1. When a connection is established, the sender's congestion window (`cwnd`) is set to a small initial value (typically 14 KB).
2. The sender can only transmit up to this window size before waiting for ACKs.
3. The window doubles with each round-trip, taking multiple RTTs to ramp up throughput.

---

### Question 4: Detecting Half-Open Connections
*Why is a server unable to detect a half-open connection (e.g. client phone loses signal) immediately using raw TCP?*

**Answer**:
TCP does not verify connection state unless it attempts to transmit data. 

If a client drops offline silently, the socket remains open in the server kernel. 

The server will only detect the failure if it attempts to write data, fails to receive ACKs, times out, and closes the connection. To detect these failures quickly, applications must implement periodic heartbeats (like Ping/Pong frames).

---

### Question 5: OS Keep-Alive Limits
*Why are OS-level TCP keep-alives insufficient for real-time WebSocket applications?*

**Answer**:
1. **Slow Detection**: Default OS settings wait **2 hours** before sending the first probe, which is too slow for real-time detection.
2. **Proxy Interference**: Many intermediate proxies terminate TCP connections, stripping OS keep-alive probes and rendering them ineffective.

---

### Question 6: Zero Window Size
*What is a TCP Zero Window, and how does it affect a Go WebSocket server?*

**Answer**:
A TCP Zero Window occurs when a client's receiver buffer is full, advertising a window size of `0` to the server. 

The server's TCP stack stops sending packets, queuing subsequent frames in kernel memory. 

If the server continues writing data, its write buffer fills up, causing write calls (like `conn.WriteMessage`) to block, consuming server memory.

---

### Question 7: Nagle's Algorithm
*What is Nagle's algorithm, and why must WebSocket servers disable it?*

**Answer**:
Nagle's algorithm is a TCP optimization that buffers small packets to build larger segments, reducing network overhead. 

For real-time WebSockets, this buffering introduces latency. 

Servers disable Nagle's algorithm by setting `TCP_NODELAY` to `true` on the socket, forcing the network stack to transmit frames instantly.

---

### Question 8: TCP RST vs. FIN
*What is the difference between a FIN packet and an RST packet during connection teardown?*

**Answer**:
- **FIN (Finish)**: Initiates a graceful shutdown. It indicates the sender has no more data to write, but can still read data from the peer.
- **RST (Reset)**: Initiates an abrupt shutdown. It indicates an error has occurred, terminating the connection immediately and discarding any buffered data.

---

### Question 9: WebTransport Advantages
*Why does WebTransport (HTTP/3 QUIC) perform better than WebSockets under high packet loss?*

**Answer**:
WebTransport runs over UDP using the QUIC protocol. 

Unlike TCP, QUIC supports independent streams. 

If a packet in Stream A is lost, Stream B continues processing without waiting for retransmission, eliminating Head-of-Line blocking entirely.

---

### Question 10: Server Socket Buffer Tuning
*How do socket buffer size configurations affect server scaling?*

**Answer**:
Each socket allocates memory for read and write buffers. 

Larger buffers improve throughput but consume more RAM per connection. 

For high-concurrency servers, you must reduce buffer sizes (e.g. setting read/write buffers to 4 KB) to conserve RAM, allowing the server to handle more connections.

---

## Summary
- **TCP Fundamentals** dictate the performance characteristics of WebSockets.
- **The TCP Three-Way Handshake** requires 1 complete RTT to establish connection states.
- **Reliability and Ordering** guarantees prevent out-of-order data but can introduce Head-of-Line blocking.
- **Flow Control** uses sliding windows to prevent overwhelming the receiver, while **Congestion Control** uses congestion windows to prevent overwhelming the network.
- **Half-Open Connections** are detected using application-level Ping/Pong heartbeats.
- **Wireshark** is used to inspect raw TCP handshakes and frame payloads.
