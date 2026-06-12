# Module 01: gRPC Fundamentals & HTTP/2 in Spring Boot

## 1. What Problem This Module Solves
Modern web microservices rely heavily on REST over HTTP/1.1. While simple and readable, REST introduces latency, bandwidth, and resource utilization bottlenecks:
*   **Head-of-Line (HoL) Blocking**: HTTP/1.1 requires serializing requests. If request A is slow, request B queues up behind it on the same connection.
*   **Connection Bloat**: REST clients open multiple parallel TCP connections to achieve concurrency, causing high handshake latency (TCP and TLS) and exhausting server port resources.
*   **Verbosity**: JSON payloads repeat metadata keys in every single packet, wasting bandwidth.
*   **Weak Contract Enforcement**: JSON REST APIs lack a compiler-enforced schema, leading to runtime failures due to structural changes.

This module details how gRPC, running over HTTP/2, resolves these bottlenecks by introducing native multiplexing, binary framing, and compilation contracts.

---

## 2. Why gRPC was Created & Chosen Over REST
Google created gRPC (originally named **Stubby**) to connect thousands of microservices within its data centers.

```
[REST HTTP/1.1 JSON - Serial Flow]
Client ───► POST /orders (String) ───► Wait for Response ───► [Server]
* A slow transaction blocks the entire connection socket.

[gRPC HTTP/2 Protobuf - Multiplexed Flow]
Client ───► Stream 1 [HEADERS + DATA Frames] ───┐
Client ───► Stream 3 [HEADERS + DATA Frames] ───┼─► Single TCP Connection ─► [Server]
Client ───► Stream 5 [HEADERS + DATA Frames] ───┘
* Interleaved binary frames flow concurrently on a single connection.
```

### Key Protocol Architectural Advantages

*   **Multiplexing**: HTTP/2 breaks requests and responses into independent binary frames and interleaves them over a single TCP connection.
*   **Binary Framing Layer**: All communications are encoded into binary frames. This is faster to write and parse compared to textual HTTP/1.1 parsing.
*   **HPACK Compression**: Compresses request headers by utilizing static and dynamic lookup tables, eliminating redundant headers from subsequent calls.
*   **Strict Contracts**: gRPC uses the Interface Definition Language (IDL) in Protocol Buffers (`.proto` files). If the interface does not compile, you cannot launch the service.

---

## 3. Trade-offs and Limitations
*   **No Native Browser Clients**: Web browsers cannot manipulate HTTP/2 frames directly (e.g., they cannot control client-side flow control or read trailers). Connecting a browser requires Envoy and a `grpc-web` translation proxy.
*   **Binary Debugging Barrier**: Payloads are not human-readable. You cannot use standard tools like `curl` without loading the `.proto` schemas and using specialized command-line utilities like `grpcurl`.

---

## 4. When NOT to use gRPC
*   **Public API Integrations**: If your consumers are third-party developers, standard REST/JSON remains the industry standard.
*   **Static/Monolithic Systems**: If your application is a simple monolithic CRUD app, the build-step requirements of protobuf compilers and client stub generation add unnecessary complexity.

---

## 5. Integrating HTTP/2 with the Spring Container
When bootstrapping a gRPC server inside Spring Boot, the lifecycle maps as follows:

```
[ JVM Start ]
      │
      ▼
[ Spring ApplicationContext Load ]  <--- Scans for @GrpcService beans
      │
      ▼
[ gRPC Netty Server Bootstrap ]     <--- Registers scanned beans to port 9090
      │
      ▼
[ Netty Worker Thread Loop ]        <--- Intercepts incoming HTTP/2 frames
      │
      ▼
[ Spring Bean Execution ]           <--- Runs service logic inside Spring Scope
```

The community starter library scans the Spring context for classes annotated with `@GrpcService`, bundles them, and registers them directly to the Netty server during startup.

---

## 6. Common Mistakes and Anti-Patterns
*   **Running HTTP/2 without TLS (H2C)**: Deploying gRPC without TLS (using plaintext H2C) in public cloud environments. Many enterprise firewalls and load balancers do not support H2C and will silently drop or degrade connections to HTTP/1.1.
*   **Sharing Netty Worker Threads for Blocking Code**: Running database accesses or downstream REST calls inside the gRPC service thread without configuring a dedicated thread pool. This starves Netty's worker loop, blocking all other connections.

---

## 7. Hands-on Exercises
1.  Run `grpcurl` from the command line against a running gRPC server to inspect the active service definitions.
2.  Inspect a local network connection using Wireshark to locate the HTTP/2 `SETTINGS` and `HEADERS` frames.

---

## 8. Mini-Project: HTTP/2 Frame Inspector in Spring Boot
Build a simple diagnostic Controller in Spring Boot that inspects incoming HTTP/2 request properties to verify connection multiplexing.

### Implementation Code (`Http2DiagnosticController.java`)
```java
package com.example.grpc.fundamentals;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Map;

@RestController
@RequestMapping("/api/diagnostics")
public class Http2DiagnosticController {

    @GetMapping("/protocol")
    public ResponseEntity<Map<String, String>> verifyHttp2(HttpServletRequest request) {
        String protocol = request.getProtocol(); // E.g., HTTP/2.0 or HTTP/1.1
        String connectionId = request.getSession().getId();

        return ResponseEntity.ok(Map.of(
            "detected_protocol", protocol,
            "session_id", connectionId,
            "multiplex_compatible", String.valueOf("HTTP/2.0".equalsIgnoreCase(protocol))
        ));
    }
}
```

---

## 9. Interview Questions

### Q1: What is HTTP/2 Head-of-Line (HoL) blocking, and how does HTTP/2 solve the application-layer HoL blocking found in HTTP/1.1?
**Answer**: 
*   **HTTP/1.1 HoL Blocking**: Occurs at the application layer. Requests on a single TCP connection must execute serially. If the first request takes 10 seconds, all subsequent requests are blocked on that socket.
*   **HTTP/2 Solution**: Uses the **Binary Framing Layer**. HTTP/2 splits requests and responses into individual frames and interleaves them across a single TCP connection. A slow request on Stream 1 does not block frames of Stream 3 or 5 from being transmitted concurrently. (However, TCP-layer HoL blocking can still occur if packets are dropped).

### Q2: How does HPACK compress HTTP/2 headers, and why does this improve throughput for high-frequency microservice calls?
**Answer**: 
HPACK uses three strategies:
1.  **Static Table**: A predefined list of 61 common headers (like `:method: POST` or `:status: 200`).
2.  **Dynamic Table**: A FIFO table populated with custom header values sent during the session (such as `authorization` tokens).
3.  **Huffman Encoding**: Compresses custom header values using a static Huffman code.
For high-frequency microservices, headers like cookies and tokens are repeated. HPACK replaces these strings with small integer indexes pointing to the dynamic table, reducing header transmission overhead from hundreds of bytes to just a few bytes.
