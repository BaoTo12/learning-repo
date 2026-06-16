# Module 2: Networking Foundations

Before writing high-level Java code to orchestrate real-time connections, a systems architect must master the underlying transport layer. WebSockets do not run in a vacuum; they operate directly over the Transmission Control Protocol (TCP). 

Every connection drop, latency spike, memory leak, and scaling bottleneck you will encounter in a real-time production system is rooted in the mechanics of TCP. This module details TCP fundamentals, the connection state machine, reliability guarantees, flow control, keep-alives, and operational strategies for socket tuning.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the TCP three-way handshake** and trace how maximum segment sizes (MSS) and sequence offsets are negotiated.
2. **Map the entire TCP connection state machine**, with specific focus on troubleshooting `CLOSE_WAIT` and `TIME_WAIT` resource leaks.
3. **Detail the mechanics of flow control** (sliding window) and **congestion control** (slow start, AIMD) and how they protect network nodes.
4. **Diagnose half-open connections** and configure OS-level and application-level keep-alive mechanisms to mitigate resource leakage.
5. **Analyze why WebSockets rely on TCP** and explain the mechanical trade-offs compared to UDP-based protocols.
6. **Apply kernel-level parameters (`sysctl`)** to tune TCP socket allocations, port ranges, and buffer memory for high-concurrency Java servers.

---

## 1. Why Networking Foundations Matter

In stateless REST APIs, network issues are transient. If a connection drops, the client retries the request, and the server processes it on a fresh thread. 

In real-time systems, connections are **stateful and long-lived**. The server allocates memory, file descriptors, and thread configurations for every concurrent user. If a network segment drops silently:
* The client may think the connection is open, wasting power sending packets into a black hole.
* The server may keep socket resources active indefinitely, causing **socket descriptor leaks** that eventually crash the application.
* Standard firewalls and NAT gateways silently terminate idle TCP links, dropping real-time channels without notifying either the client or the server.

Understanding how the TCP transport layer behaves under load is critical to building resilient real-time architectures.

---

## 2. TCP vs. UDP Fundamentals

At the transport layer, data is multiplexed across applications using ports. However, TCP and UDP treat data transmission in fundamentally different ways:

```
UDP: Datagram Packet Stream (Unreliable Handoff)
Application ──► [Packet 1] ──► [Packet 2] ──► [Packet 3] ──► Network

TCP: Byte Stream Channel (Reliable, Ordered Pipeline)
Application ──► [Byte Byte Byte Byte Byte Byte Byte Byte] ──► Network
```

### 1. Packet-Based (UDP) vs. Byte-Stream (TCP)
- **User Datagram Protocol (UDP)** is a connectionless, thin layer over IP. It transmits individual packets (datagrams). The boundaries of the packets sent by the application are preserved exactly on the network.
- **Transmission Control Protocol (TCP)** is connection-oriented. It abstracts the network as a continuous, ordered, bi-directional **byte stream**. The application writes bytes to a socket buffer, and the operating system's TCP stack decides how to segment those bytes into packets (segments) using the Maximum Segment Size (MSS). The boundaries of application writes are not preserved on the wire; the receiver must parse the byte stream to reconstruct messages.

### 2. Sockets and Sockets Descriptors
In Java, a TCP connection is represented by a `Socket` object, which maps to an operating system **file descriptor (FD)**. A TCP socket is uniquely identified by a 5-tuple:
$$\text{Socket 5-Tuple} = \{\text{Protocol}, \text{Source IP}, \text{Source Port}, \text{Destination IP}, \text{Destination Port}\}$$
This 5-tuple allows a single server port (e.g., port 8080) to handle hundreds of thousands of concurrent WebSocket connections, as long as the client IPs or client ports differ.

---

## 3. The Three-Way Handshake

A TCP connection must be explicitly established before any application data can flow. This is achieved via the **Three-Way Handshake**.

```
Client                                      Server
  │                                           │ (LISTEN state)
  │ ─── SYN (Seq=X, MSS=1460) ──────────────► │ (SYN_RCVD state)
  │ ◄─── SYN-ACK (Seq=Y, Ack=X+1) ─────────── │ (SYN_SENT state)
  │ ─── ACK (Seq=X+1, Ack=Y+1) ─────────────► │ (ESTABLISHED state)
  ▼                                           ▼
```

### Handshake Sequence:
1. **SYN (Synchronize)**: The client selects an **Initial Sequence Number (ISN)** $X$ and sends a segment with the `SYN` flag set. It also advertises its Maximum Segment Size (MSS) and window scaling parameters.
2. **SYN-ACK**: The server receives the SYN, selects its own ISN $Y$, increments the client's sequence number ($X + 1$), and returns a segment with both the `SYN` and `ACK` flags set.
3. **ACK (Acknowledgment)**: The client receives the SYN-ACK, increments the server's sequence number ($Y + 1$), and sends a final segment with the `ACK` flag set.

### Crucial Handshake Parameters:
* **Initial Sequence Number (ISN) Security**: The ISN is not starting at 0. It is generated using a secure pseudo-random algorithm based on system clocks and cryptographic keys to prevent **TCP sequence prediction attacks**, where an attacker injects malicious data into an active stream by guessing sequence offsets.
* **MSS Negotiation**: The Maximum Segment Size defines the largest payload block a network node can accept in a single packet. A standard Ethernet link has a Maximum Transmission Unit (MTU) of 1500 bytes. Subtracting the IP header (20 bytes) and TCP header (20 bytes) yields a default MSS of **1460 bytes**. If a client is on a VPN or network with smaller MTU limits, the MSS is adjusted downward during the handshake to prevent IP fragmentation.

---

## 4. The TCP Connection Lifecycle (State Machine)

A TCP connection transitions through various states on both the client and the server. Understanding these transitions is essential for diagnosing connection drops and leaks.

```
                   +---------+
                   |  CLOSED |
                   +---------+
                        │
                        ▼ (Three-Way Handshake)
                   +-------------+
                   | ESTABLISHED |
                   +-------------+
                        │
       Active Close     │     Passive Close
       (Initiator)      │     (Receiver)
            ┌───────────┴───────────┐
            ▼                       ▼
      +------------+          +------------+
      | FIN_WAIT_1 |          | CLOSE_WAIT | <-- (Danger zone: App must close)
      +------------+          +------------+
            │                       │
            ▼                       ▼
      +------------+          +------------+
      | FIN_WAIT_2 |          |  LAST_ACK  |
      +------------+          +------------+
            │                       │
            ▼                       ▼
      +------------+          +---------+
      | TIME_WAIT  |          |  CLOSED |
      +------------+          +---------+
            │
            ▼ (2 * MSL Wait)
      +---------+
      |  CLOSED |
      +---------+
```

### The Connection Teardown (Four-Way Handshake)
Unlike connection setup, closing a connection requires a four-way handshake because TCP is full-duplex. Each direction of the byte stream must be closed independently.

1. **Active Close (Initiator sends FIN)**: The initiator (e.g., client) sends a `FIN` segment, entering the `FIN_WAIT_1` state.
2. **Passive Close (Receiver sends ACK)**: The receiver (e.g., server) acknowledges the `FIN`, returning an `ACK`. The receiver enters the `CLOSE_WAIT` state, and the initiator transitions to `FIN_WAIT_2`. At this point, the connection is half-closed: the initiator can no longer send data, but the receiver can still push packets.
3. **Receiver Close (Receiver sends FIN)**: When the receiver application finishes cleaning up, it issues a socket close command, sending its own `FIN` segment to the initiator. The receiver enters `LAST_ACK`.
4. **Final Acknowledgment**: The initiator receives the receiver's `FIN`, returns a final `ACK`, and enters the `TIME_WAIT` state. The receiver receives the `ACK` and returns to `CLOSED`.

### Diagnostic State Deep Dives:

#### 1. TIME_WAIT State
When the initiator of the close enters `TIME_WAIT`, the socket remains active in the operating system kernel for a duration equal to **2 * Maximum Segment Lifetime (2MSL)**, which defaults to 1–4 minutes depending on OS configurations.
* **Why it exists**: 
  1. **Reliability**: If the final `ACK` is lost on the network, the receiver will retransmit its `FIN`. The initiator must remain in `TIME_WAIT` to resend the `ACK`. If the socket closed instantly, the retransmitted `FIN` would trigger a `RST` (Reset) packet, indicating an error.
  2. **Security & Data Integrity**: It prevents "stale" packets from an old connection (which might have been delayed on the network) from being mistakenly accepted by a new socket utilizing the same IP/port 5-tuple.
* **The Scale Ceiling**: If a server terminates 20,000 connections quickly, it will have 20,000 sockets locked in `TIME_WAIT` for minutes, depleting available local ports and socket descriptors.

#### 2. CLOSE_WAIT State
The `CLOSE_WAIT` state exists on the passive close receiver. 
* **The Indicator**: If a socket is stuck in `CLOSE_WAIT`, it means the operating system kernel received a `FIN` packet from the remote client, acknowledged it, and is now waiting for the **local application** to invoke `socket.close()`.
* **The Root Cause**: Sockets stuck in `CLOSE_WAIT` represent an **application code bug**. The Java code has leaked the socket reference or is blocked on other logic, failing to close the connection descriptor. Sockets in `CLOSE_WAIT` do not time out; they remain in memory until the application process is restarted.

---

## 5. Reliability and Ordering Guarantees

TCP guarantees that data is delivered to the application in the exact order it was sent, without duplication or gaps, even if the underlying IP packets arrive out-of-order or are lost.

### 1. Sequence Tracking & Offset Assembly
Every byte sent over a TCP connection is assigned a sequence number.
* If a sender writes a 3000-byte buffer over an MSS-1460 link, the OS segments it into three packets:
  - Packet 1: Seq = 1001, Payload = 1460 bytes.
  - Packet 2: Seq = 2461, Payload = 1460 bytes.
  - Packet 3: Seq = 3921, Payload = 80 bytes.
* If Packet 2 is delayed and Packet 3 arrives first, the receiver's TCP buffer stores Packet 3 but delays delivering it to the Java application. Once Packet 2 is retransmitted and arrives, the OS reassembles the stream in order and releases the bytes to the application's `InputStream`.

### 2. Acknowledgment (ACK) & Retransmissions
- The receiver sends `ACK` packets indicating the next expected sequence number.
- **Retransmission Timeout (RTO)**: The sender maintains an RTO timer. If an ACK for a sent segment is not received before the timer expires, the sender retransmits the segment. The RTO dynamically adjusts using round-trip time measurements (RTT).
- **Fast Retransmit**: If a packet is lost, subsequent packets trigger duplicate ACKs from the receiver (requesting the missing sequence number). If the sender receives **3 duplicate ACKs**, it assumes packet loss has occurred and retransmits the missing segment immediately without waiting for the RTO timer to expire.

```
Sender                                    Receiver
  │ ─── Seq=1001 (1460 bytes) ──────────► │ (Arrives)
  │ ─── Seq=2461 (Lost) ────────────────► │ (Dropped)
  │ ─── Seq=3921 (80 bytes) ────────────► │ (Arrives out of order)
  │ ◄─── ACK=2461 (Dup ACK 1) ─────────── │ (Requesting missing block)
  │ ─── Seq=4001 (Next) ────────────────► │ (Arrives)
  │ ◄─── ACK=2461 (Dup ACK 2) ─────────── │ (Requesting missing block)
  │ ◄─── ACK=2461 (Dup ACK 3) ─────────── │ (Triggers Fast Retransmit!)
  │ ─── Seq=2461 (Retransmission) ──────► │ (Arrives, buffer reassembled)
  │ ◄─── ACK=4081 ─────────────────────── │ (Acks all packets up to date)
```

---

## 6. Flow Control & Congestion Control

To prevent fast senders from overwhelming slow receivers or congesting the network infrastructure, TCP implements dynamic throttling.

### 1. Flow Control: The Sliding Window
Flow control prevents the sender from overflowing the receiver's memory buffer.
- The receiver advertises its available buffer space in the **Window Size (Win)** field of every TCP header.
- The sender is strictly restricted: it can have no more than `Win` unacknowledged bytes in transit.
- **Zero Window**: If the Java application is slow in reading from the socket `InputStream`, the OS buffer fills up. The receiver advertises a `Window Size = 0`. The sender stops transmitting immediately and sends periodic **Window Probes** to check when space becomes available.

```
[ Sent & ACKed ] [ Sent, UnACKed (In-Transit) ] [ Allowed, Not Yet Sent ] [ Blocked ]
─────────────────► ◄──────────────── sliding window size ──────────────►
```

### 2. Congestion Control: Protecting the Network
Congestion control prevents senders from overloading routers and switches along the network path.
- The sender maintains a **Congestion Window (Cwnd)** size.
- **Slow Start**: When a connection starts, the sender sets `Cwnd` to a small value (e.g., 10 segments). For every ACK received, `Cwnd` doubles, growing exponentially until it hits the slow-start threshold (`ssthresh`).
- **Congestion Avoidance (AIMD)**: After hitting `ssthresh`, `Cwnd` grows linearly (+1 segment per RTT). If packet loss occurs (indicated by duplicate ACKs or RTO timeouts), the sender assumes network congestion, drops `Cwnd` by 50% (Multiplicative Decrease), and resets `ssthresh`.
- **Modern Algorithms**: Linux default servers utilize **Cubic** or Google's **BBR (Bottleneck Bandwidth and RTT)** congestion control algorithms. BBR measures actual physical throughput and RTT to maximize transmission rates without causing packet loss, reducing buffer bloat latency.

---

## 7. Keep-Alives and Half-Open Connections

One of the most common causes of resource leakage in real-time servers is the **Half-Open Connection** (or silent disconnect).

### The Silent Disconnect Scenario
If a user is connected to a WebSocket chat server:
1. The user's device loses power or drops off cell coverage (e.g., entering an elevator).
2. Because the device drops offline instantly, it has no time to send a TCP `FIN` packet to close the connection.
3. The server's OS socket remains open. Since no data is actively flowing, the server has no way of knowing the client is gone.
4. **The Consequence**: The socket remains in the `ESTABLISHED` state. If this occurs thousands of times, the server accumulates dead connections, eventually hitting file descriptor limits.

### 1. OS-Level TCP Keep-Alives
To detect silent disconnects, the operating system kernel can send periodic probing packets.
- **Mechanics**: If a socket is idle for a set period, the OS sends an empty TCP ACK probe. If the client does not respond after multiple attempts, the connection is closed.
- **Default OS Parameters (Linux)**:
  - `tcp_keepalive_time`: 7200 seconds (2 hours before first probe).
  - `tcp_keepalive_intvl`: 75 seconds (interval between probes).
  - `tcp_keepalive_probes`: 9 probes (number of failures before drop).
- *Critical Problem*: Waiting **2 hours** to detect a disconnected socket is too slow for high-concurrency real-time systems.

### 2. Why Application-Level Keep-Alives (WebSocket Ping/Pong) Are Required
While you can tune OS-level TCP keep-alive parameters downward in the kernel, application-level heartbeats (WebSocket Ping/Pong frames) are still required in production:
1. **NAT Timeout Prevention**: Home routers and corporate firewalls maintain Network Address Translation (NAT) maps. Idle maps are cleared after 30 to 300 seconds. If no data flows, the gateway drops the mapping, and subsequent server packets cannot reach the client. Application-level pings (e.g., every 30 seconds) keep the NAT map active.
2. **Intermediate Proxy Integrity**: Reverse proxies (like Nginx, HAProxy, or cloud load balancers) operate at the application layer. They often ignore raw TCP level probes and close idle HTTP/WebSocket connections after 60 seconds of inactivity. Application-level messages are required to reset proxy idle timers.
3. **Application Thread Health**: A TCP keep-alive only confirms that the client's *kernel* is alive. It does not verify that the client application is responding or that the browser's thread is not frozen.

---

## 8. Why WebSockets Use TCP

WebSockets are designed to run over TCP because of its underlying stream characteristics:

1. **Stateful Connection Integrity**: WebSockets are connection-oriented. The HTTP upgrade handshake requires a reliable, stateful channel to transition protocol modes, which TCP naturally provides.
2. **Message Boundary Framing**: WebSockets pack messages into structured binary frames. Because TCP guarantees ordered byte delivery, the WebSocket frame parser can safely read frame headers, identify payload lengths, and reassemble large messages across multiple segments without losing boundary synchronization.
3. **Loss Recovery Guarantees**: WebSocket applications assume that sent messages are received. If WebSockets utilized raw UDP, application developers would have to write custom packet sequence numbers, acknowledgment listeners, and retransmission managers to guarantee message delivery.

---

## 9. Hands-On Lab: Socket Inspection and Network Traffic Analysis

In this lab, you will inspect active TCP sockets on your operating system, observe connection state transitions, and analyze how network changes impact socket lifecycles.

### Exercise 1: Tracing Socket Lifecycle States
We will locate and observe active TCP connection states using standard operating system terminal tools.

#### 1. List Active Listening Ports
Open a terminal (Powershell on Windows, or Bash on Linux/macOS) and execute the command to locate active listening ports:

* **On Windows (PowerShell)**:
  ```powershell
  netstat -ano | Select-String "LISTENING"
  ```
* **On Linux / macOS (Terminal)**:
  ```bash
  ss -tlnp
  # or using netstat
  netstat -tuln
  ```

#### 2. Trace WebSocket Socket State Transitions
1. Start your Spring Boot application from Module 1. Ensure it is listening on port `8080`.
2. Connect a WebSocket client to `ws://localhost:8080/api/sse/stream` or any WebSocket endpoint.
3. In your terminal, query connections on port 8080 to locate the active link:
   - **Linux**: `ss -tpa | grep 8080`
   - **Windows**: `netstat -ano | FindStr "8080"`
4. **Identify the State**: You will see the socket listed as **`ESTABLISHED`** with a specific PID.
   ```text
   TCP    127.0.0.1:8080     127.0.0.1:51234    ESTABLISHED     12432
   ```
   *(Here, 51234 is the client's ephemeral port, and 12432 is the Java process PID).*

5. **Observe `TIME_WAIT`**:
   - Close the client application connection gracefully.
   - Run the query command in your terminal again immediately.
   - You will see the socket transition to **`TIME_WAIT`**. It will remain in this state for up to 2 minutes before the operating system releases the file descriptor.

6. **Observe `CLOSE_WAIT`**:
   - Establish a new connection.
   - Force the client process to crash (e.g. kill the client terminal or task).
   - If the server application has a bug where it catches the disconnection exception but fails to close the session registry object, run the query command.
   - You will see the socket stuck in **`CLOSE_WAIT`**. It will remain stuck indefinitely until the Spring Boot server process is stopped.

---

### Exercise 2: Simulating Packet Loss and TCP Head-of-Line Blocking
In this conceptual exercise, we will trace the latency profile of a WebSocket connection when packet loss is introduced on the network.

#### 1. Setup Network Emulation
On Linux, we can inject artificial packet loss using the traffic control (`tc`) kernel tool. We inject **10% packet loss** on our network interface:
```bash
sudo tc qdisc add dev eth0 root netem loss 10%
```

#### 2. Run WebSocket Aggregator
1. Run a high-frequency WebSocket client that receives 10 messages per second from the server.
2. Monitor the arrival times of messages on the client console.
3. **Analyze the Latency Spikes**:
   - In a clean network environment, messages arrive at regular 100ms intervals.
   - With 10% packet loss, notice that messages do not arrive steadily. Instead, there is a freeze (no messages arrive for 300ms–600ms), followed by a sudden burst of 3–5 messages arriving at the same time.
4. **Explain the Latency Profile**:
   - When a packet containing Message $N$ is lost on the wire, the client's OS TCP buffer receives subsequent packets containing Messages $N+1$ and $N+2$.
   - Because TCP enforces **strict ordering guarantees**, the OS kernel blocks delivery of Messages $N+1$ and $N+2$ to the Java application.
   - The messages remain blocked in the kernel buffer until the retransmission handshake completes and Message $N$ is successfully received. This is **Head-of-Line Blocking** at the transport layer, demonstrating the primary latency challenge of WebSockets under unstable network conditions.

#### 3. Cleanup Network Emulation
Ensure you remove the packet loss rule to restore normal network conditions:
```bash
sudo tc qdisc del dev eth0 root
```

---

## 10. Common Mistakes & Debugging Scenarios

### Scenario A: File Descriptor Leaks ("Too many open files")
* **The Problem**: A high-traffic WebSocket application runs fine for hours, then suddenly crashes, throwing a `java.io.IOException: Too many open files`. All subsequent connection attempts are rejected.
* **Why it happens**: Every active TCP socket requires a **File Descriptor (FD)**. By default, Unix-like operating systems set a safety limit on the number of file descriptors a process can open (often defaulting to **1024**). Under high concurrency, as active connections exceed 1024, the JVM fails to open new descriptors, crashing the application.
* **The Fix**:
  1. Increase the OS file descriptor limits. Edit `/etc/security/limits.conf` to set soft and hard limits:
     ```text
     * soft nofile 65536
     * hard nofile 65536
     ```
  2. Verify your Java process limits at runtime:
     ```bash
     cat /proc/<PID>/limits | grep "Max open files"
     ```

### Scenario B: Stranded CLOSE_WAIT Sockets
* **The Problem**: A developer notices that the server's memory usage grows steadily over days. Running `ss -s` reveals thousands of sockets stuck in `CLOSE_WAIT`.
* **Why it happens**: When a client loses connection, the client's TCP stack sends a `FIN` packet. The server kernel receives it and transitions the socket to `CLOSE_WAIT`. However, if the Spring Boot application logic catches the socket exception but fails to close the active session resource, the JVM never releases the file descriptor. The socket remains stuck in `CLOSE_WAIT` indefinitely, leaking memory.
* **The Fix**: Ensure all socket exceptions or connection timeouts execute a `close()` command inside a `finally` block or clean-up listener, freeing the connection descriptor.

---

## 11. Production Kernel Tuning (`sysctl.conf`)

To scale a Java WebSocket application to handle tens of thousands of concurrent connections, you must tune the Linux kernel network settings. Add these configurations to `/etc/sysctl.conf` and apply them using `sysctl -p`:

```ini
# 1. Expand the local port range for outgoing connections
net.ipv4.ip_local_port_range = 1024 65535

# 2. Allow recycling of sockets in TIME_WAIT state for outgoing connections
net.ipv4.tcp_tw_reuse = 1

# 3. Decrease the timeout window a socket spends in FIN_WAIT_2 state
net.ipv4.tcp_fin_timeout = 15

# 4. Increase the maximum backlog queue of connection requests
net.core.somaxconn = 32768

# 5. Increase maximum queue of incoming packets on the interface
net.core.netdev_max_backlog = 16384

# 6. Tune TCP memory buffer ranges (min, default, max bytes)
# Allocates adequate buffer space for large numbers of concurrent links
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
```

---

## 12. Technical Interview Questions

### Question 1: Sizing TIME_WAIT vs CLOSE_WAIT
*What is the structural difference between a socket stuck in `TIME_WAIT` versus one stuck in `CLOSE_WAIT`? Which one can be resolved through application code changes?*

**Answer**:
- **`TIME_WAIT`** occurs on the socket of the system that initiated the connection close (Active Close). It is a normal state managed by the operating system kernel, which keeps the port reserved for 2MSL to ensure stale packets are cleared and the final `ACK` is reliably delivered. It cannot be resolved directly by application code, but its impact can be minimized by enabling `SO_REUSEADDR` socket options or recycling ports (`tcp_tw_reuse`).
- **`CLOSE_WAIT`** occurs on the socket of the system receiving the close signal (Passive Close). It indicates that the remote peer has closed its end of the connection, but the local application has not yet closed its socket. This is a **software bug** that must be resolved in application code by ensuring that all disconnect events trigger a socket `close()` command.

---

### Question 2: The SYN Flood Attack
*Explain how the TCP three-way handshake can be exploited for a Denial of Service (DoS) attack, and how modern operating systems mitigate it.*

**Answer**:
A **SYN Flood Attack** exploits the stateful nature of the TCP three-way handshake:
1. An attacker sends a flood of `SYN` packets to a server port, using spoofed (fake) source IP addresses.
2. The server receives each `SYN` packet, allocates memory resources for a connection state, and sends a `SYN-ACK` to the spoofed IP.
3. The server enters the `SYN_RCVD` state and waits for the final `ACK` to arrive. Since the source IP is spoofed, the `ACK` never arrives.
4. The server's connection queue (SYN backlog) fills up with half-open connections, preventing legitimate users from completing handshakes.

**Mitigation**: Modern kernels utilize **SYN Cookies**:
- When the SYN queue fills up, the server stops allocating connection state memory.
- Instead, the server encodes connection parameters into the sequence number of the `SYN-ACK` packet (a hash of the source IP, port, and a secret timestamp).
- When a legitimate client returns the final `ACK`, the server extracts the hashed data to verify the connection and allocates resources only then, preventing resource exhaustion during a flood.

---

### Question 3: Why WebSockets Rely on Keep-Alives
*Why are application-level heartbeats (ping/pong) required for WebSocket connections if the underlying TCP protocol already supports keep-alive probes?*

**Answer**:
OS-level TCP keep-alive probes only verify that the remote kernel is active. They do not ensure the application layer is healthy (e.g., if a browser tab is frozen or the application thread is blocked). 

Additionally, intermediate network boxes (NAT routers, firewalls, reverse proxies) operate at the application layer. They frequently terminate connections that are idle for more than 60 seconds, ignoring low-level TCP keep-alives. Application-level WebSocket ping/pong frames transmit real payload data, keeping NAT maps active and resetting idle timeouts on proxies.

---

## Summary
- **TCP** provides a reliable, ordered, bi-directional byte-stream channel, which is the foundation WebSockets require to stream structured frames.
- **The Connection Lifecycle** features critical transitional states: `TIME_WAIT` is a kernel safety hold for active closes, whereas `CLOSE_WAIT` represents an application-level socket leak.
- **Flow Control** utilizes the sliding window size to prevent receiver buffer overflow, while **Congestion Control** adjusts the congestion window (`Cwnd`) dynamically to prevent network congestion.
- **Half-Open Connections** occur when a client drops offline silently, leaving server sockets stranded in the `ESTABLISHED` state unless detected by keep-alive probes or application-level ping/pong heartbeats.
- **Production Scaling** requires raising operating system file descriptor limits and tuning TCP buffer sizes and backlog queues in `/etc/sysctl.conf`.
