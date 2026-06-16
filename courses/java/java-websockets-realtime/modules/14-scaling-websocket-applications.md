# Module 14: Scaling WebSocket Applications

Scaling stateless REST services is simple: you deploy additional application nodes behind a round-robin load balancer. Sockets, however, are **stateful and long-lived**. Every connection binds a client directly to a specific server instance.

This module covers the challenges of scaling stateful WebSocket applications. We will analyze connection memory ceilings, evaluate load balancing affinity patterns (sticky sessions), design a distributed architecture blueprint to support 10 million concurrent users, and deploy multiple local Spring Boot instances.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the differences** between scaling stateful WebSocket connections and stateless REST APIs.
2. **Configure Nginx and HAProxy load balancers** to support sticky session affinity.
3. **Calculate memory, network port, and file descriptor requirements** to scale real-time clusters.
4. **Design a distributed systems architecture** capable of supporting 10 million concurrent active users.
5. **Deploy and run multiple server instances** locally using dynamic environment profiles.

---

## 1. The Stateful Connection Scale Ceiling

A single server instance cannot scale indefinitely. When scaling vertically (adding CPU and RAM), you will hit system-level bottlenecks:

### 1. File Descriptor (FD) Exhaustion
In Unix-like systems, "everything is a file". Every TCP connection opened to a server allocates a File Descriptor.
- If the operating system limit is set to the default (typically `1024`), the server will reject new connections once it has 1024 active users.
- **Tuning**: You must configure soft and hard limits (`ulimit -n 1000000`) in `/etc/security/limits.conf`.

### 2. TCP Buffer Memory Overhead
Each TCP socket allocates a **Read Buffer** and a **Write Buffer** in kernel space to queue incoming and outgoing network data.
- By default, Linux allocates 4 KB to 87 KB per buffer.
- If you have 100,000 active connections:
  $$\text{Memory Overhead} = 100,000 \times (\text{Read Buffer} + \text{Write Buffer})$$
  At 16 KB total buffer per socket, the OS kernel consumes **1.6 GB of RAM** just keeping the connections open, before the JVM heap is even allocated.

### 3. JVM Thread Allocations
If the server container allocates one thread per connection (blocking I/O model), having 100,000 active users requires 100,000 threads.
- Since each thread stack consumes $\approx 1$ MB of memory, this would require **100 GB of RAM** just for thread stacks.
- **The Solution**: Web containers must use Non-blocking I/O (NIO), where a small, fixed pool of worker threads multiplexes thousands of active socket channels.

---

## 2. Horizontal Scaling Challenges

To scale beyond a single server, you must deploy multiple instances. This introduces three core horizontal scaling challenges:

### 1. Connection Pinning
Once a client establishes a WebSocket connection to Instance A, all its frames must go to Instance A. The load balancer cannot route subsequent frames to Instance B, as Instance B has no record of the client's socket state.

### 2. State Isolation
If Client A is connected to Instance 1, and Client B is connected to Instance 2, they cannot communicate directly. If Client A broadcasts a message to a shared room, Instance 1 has no way of pushing the message to Client B.

### 3. Session Affinity vs. Stateless Routing
Traditional load balancers distribute HTTP requests evenly. For WebSockets, the load balancer must support **Session Affinity (Sticky Sessions)**.

---

## 3. Session Affinity and Sticky Sessions

To ensure that the initial HTTP handshake and the subsequent upgraded WebSocket connection target the same server instance, configure the load balancer for session affinity.

```
                  +─────────────────────────+
                  |      LOAD BALANCER      |
                  |                         |
                  |  [ Session Affinity ]   |
                  +────────┬────────┬───────+
                           │        │
               Cookie:     │        │ Cookie:
               node=app1   │        │ node=app2
                           ▼        ▼
                      +───────+  +───────+
                      | App 1 |  | App 2 |
                      +───────+  +───────+
```

### 1. Nginx Sticky Configuration
Nginx can bind client sessions to backend nodes using IP Hashing:
```nginx
upstream websocket_cluster {
    # Route clients based on client IP hash
    ip_hash;
    server backend1.example.com:8080;
    server backend2.example.com:8080;
}

server {
    listen 80;
    location /ws {
        proxy_pass http://websocket_cluster;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}
```

### 2. HAProxy Cookie Affinity Configuration
HAProxy can insert a cookie during the HTTP handshake to track session routing:
```haproxy
backend websocket_backend
    balance roundrobin
    # Insert a cookie named 'SERVERID' to track affinity
    cookie SERVERID insert indirect nocache
    
    server app1 10.0.0.10:8080 check cookie app1
    server app2 10.0.0.11:8080 check cookie app2
```

---

## 4. Distributed Architecture Blueprint: Supporting 10 Million Users

To scale an application to support **10,000,000 concurrent active users**, we design a multi-tiered distributed system:

### 1. The Architectural Topology

```
                         [ DNS Geo-Routing (Route 53) ]
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            ▼                                                   ▼
   [ Region 1 Load Balancer ]                          [ Region 2 Load Balancer ]
   (HAProxy Cluster - SSL Termination)                 (HAProxy Cluster)
            │                                                   │
   ┌────────┴────────┐                                 ┌────────┴────────┐
   ▼                 ▼                                 ▼                 ▼
[ App Node 1 ]    [ App Node 2 ]                    [ App Node 3 ]    [ App Node 4 ]
(Spring Boot)     (Spring Boot)                     (Spring Boot)     (Spring Boot)
   │                 │                                 │                 │
   └────────┬────────┘                                 └────────┬────────┘
            │                                                   │
            └───────────────────────┬───────────────────────────┘
                                    ▼
                      [ Redis Cluster / Kafka Bus ] (Shared Pub/Sub)
```

### 2. Capacity Planning Calculations

#### Connection Memory Footprint:
Assume each active socket consumes $\approx 30$ KB (TCP buffers + JVM Session memory + frame queues).
- For 10,000,000 users, the total memory required just to keep the connections open is:
  $$10,000,000 \times 30 \text{ KB} = 300,000,000 \text{ KB} \approx 300 \text{ GB of RAM}$$
- **Sizing the Application Cluster**:
  We deploy **20 Application Nodes** (each with 32 GB RAM). Each node handles **500,000 concurrent active connections**, consuming $\approx 15$ GB of RAM for socket connections, leaving 17 GB for application execution heap.

#### Port Exhaustion Mitigation:
A single load balancer IP can only open up to 65,535 outbound TCP ports to a specific application IP. To scale to 500,000 connections per node:
- **Solution**: Configure the load balancer and application nodes to bind to **multiple Virtual IP (VIP) interfaces**. 
  If the load balancer uses 10 egress IPs and the application node listens on 5 ingress IPs, they can establish up to:
  $$\text{Max Ports} = 10 \text{ egress} \times 5 \text{ ingress} \times 65,535 \text{ ports} \approx 3,276,750 \text{ connections}$$
  This avoids port exhaustion without adding more physical network cards.

#### Shared Message Bus:
We deploy a **clustered Redis Pub/Sub** or **Apache Kafka** bus. When a message is sent to `/topic/chat` on Node 1, Node 1 publishes the event to Redis. All other application nodes subscribe to the Redis channel, receive the event, and push it to their local connected sessions.

---

## 5. Hands-On Lab: Deploying Multiple Local Instances

In this lab, you will run two local instances of your Spring Boot WebSocket application on different ports to simulate a clustered environment.

### Steps:
1. Open a terminal and build your Spring Boot jar:
   ```bash
   mvn clean package -DskipTests
   ```
2. Start **Instance 1** on port `8080`:
   ```bash
   java -jar -Dserver.port=8080 target/realtime-app-1.0.jar
   ```
3. Open a second terminal and start **Instance 2** on port `8081`:
   ```bash
   java -jar -Dserver.port=8081 target/realtime-app-1.0.jar
   ```
4. Verify both instances are active:
   - Check http://localhost:8080 and http://localhost:8081.
   - Run a test client. Notice that clients connected to port 8080 cannot communicate with clients connected to port 8081 because the instances are isolated. We will resolve this isolation in the next module.

---

## 6. Common Mistakes & Debugging Scenarios

### Scenario A: Port Exhaustion on Load Balancers
* **The Problem**: A load balancer is configured to route connections to a single backend application IP. The system works fine until the active connection count hits $\approx 60,000$. After that, all new connection attempts fail with timeouts, even though server CPU and RAM usage are low.
* **Why it happens**: A single IP address is limited to 65,535 ports. When the load balancer establishes TCP links to a single destination IP, it exhausts its ephemeral port range, preventing new connection tunnels.
* **The Fix**: Configure the load balancer and backend servers to bind to multiple virtual IP interfaces (IP Aliasing), increasing the available port combinations.

### Scenario B: Shared Session State Loss on Redeployment
* **The Problem**: When performing a rolling redeployment (shutting down Server A to redirect traffic to Server B), thousands of clients lose their active connection states, and their sessions are lost.
* **Why it happens**: Sockets are bound to the JVM memory. If Server A is stopped, the TCP connection is terminated, and the client must handshake again with Server B. If application state (like unread counts or user metadata) was stored only in the server's local memory, it is lost.
* **The Fix**: Externalize all connection metadata (like user session details, active rooms) to an external cache (like Redis), allowing clients to restore state seamlessly upon reconnecting to a new server node.

---

## 7. Technical Interview Questions

### Question 1: Sticky Sessions in WebSockets
*Why is session affinity (sticky sessions) critical for the HTTP upgrade handshake phase in WebSockets?*

**Answer**:
A WebSocket connection begins as an HTTP Upgrade request. 

If your load balancer does not enforce session affinity, the initial HTTP GET request might be routed to Server A, and the subsequent WebSocket frame or final handshake validation might be routed to Server B. Since Server B has no record of the handshake state or session authorization metadata generated on Server A, it will reject the connection. 

Enforcing sticky sessions ensures that all requests for a specific client session target the same server node, allowing the handshake to complete and the socket to remain pinned to that instance.

---

### Question 2: Port Exhaustion
*Explain the port exhaustion problem in load-balanced WebSocket clusters and how to resolve it.*

**Answer**:
A TCP socket is identified by a 5-tuple, including source IP, source port, destination IP, and destination port. 

When a load balancer proxies connections from a single IP to a single backend server IP, the source port is the only variable. Since port numbers are 16-bit integers, the load balancer is limited to $\approx 65,000$ concurrent connections to that backend server. 

To resolve this, you must configure **IP Aliasing** on both the load balancer and the backend servers, assigning multiple virtual IP addresses to the network interfaces. This increases the unique source-destination IP combinations, raising the port limit to millions of concurrent connections.

---

## Summary
- **Stateful Connections** pin client sockets to specific server instances, requiring load balancers to support **Session Affinity (Sticky Sessions)**.
- **Horizontal Scaling** breaks local in-memory communication, requiring a shared message bus to forward events across nodes.
- **Capacity Planning** for millions of users requires raising operating system file descriptor limits and tuning TCP buffer sizes.
- **Port Exhaustion** is resolved by binding load balancers and backend nodes to multiple virtual IP interfaces (IP Aliasing).
- **Externalizing State** to a shared cache (like Redis) ensures clients can restore their session state seamlessly during rolling redeployments.
