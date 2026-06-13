# Module 12: Microservice Communication Design

## 1. What Problem This Module Solves
Microservice topologies present structural complexity when accessed by frontend users:
*   **Protocol Mismatch**: Web browsers and mobile clients consume HTTP/JSON (REST) or WebSockets. They cannot easily speak binary gRPC natively.
*   **Network Latency (BFF)**: If a mobile client needs to call 5 different microservices to render a single dashboard page, executing 5 separate HTTP requests over mobile cellular networks introduces severe latency.
*   **Service Mesh Interception**: Setting up mTLS, retries, and rate limiting individually in every service code container leads to configuration sprawl and update friction.

This module covers microservice integration pattern designs, detailing the API Gateway, Backend-for-Frontends (BFF), and sidecar interception (Service Mesh) models, completed by a hands-on Java HTTP-to-gRPC transcoding proxy.

---

## 2. Integration Architectures Compared

### 2.1 API Gateway / Transcoder
Acts as a proxy layer that accepts REST/JSON requests from public web frontends and translates them into binary gRPC requests to communicate with internal microservices.

```
                  [ Public Web Client ]
                            │  (HTTP / JSON REST)
                            ▼
             [ API Gateway / Transcoder ]
                            │  (Binary gRPC over HTTP/2)
             ┌──────────────┴──────────────┐
             ▼                             ▼
   [Payment Service JVM]         [Account Service JVM]
```

### 2.2 Backend-for-Frontends (BFF)
A specialized Gateway tailored to a specific user interface (e.g., one BFF for the iOS App, one for the Desktop Web). The BFF aggregates downstream responses to optimize payload sizes and reduce network round-trips for mobile clients.

### 2.3 Service Mesh (Istio / Envoy)
Offloads network logic from application code to sidecar container proxies. The application communicates via plaintext localhost sockets, and the sidecar manages mTLS, retries, load balancing, and distributed tracing.

---

## 3. Trade-offs and Limitations
*   **Gateway Single Point of Failure (SPOF)**: An API Gateway introduces an extra network hop. If the Gateway experiences CPU saturation or crashes, the entire system is inaccessible.
*   **Schema Synchronization**: The Gateway must maintain references to all downstream `.proto` definitions. If a downstream service changes its schema, the Gateway must update its stubs or dynamic descriptors to prevent serialization errors.

---

## 4. Common Mistakes and Anti-Patterns
*   **Doing Heavy Business Logic in the Gateway**: Writing database queries, authentication validation logic, or formatting calculations directly in the API Gateway. The Gateway should remain a lightweight routing and serialization proxy; business logic belongs in the downstream microservices.
*   **Double Serialization**: Translating JSON to Java objects on the Gateway, then serializing those Java objects into Protobuf to call downstream services. For maximum performance, gateways should perform direct byte-level translation where possible.

---

## 5. Mini-Project: HTTP-to-gRPC Transcoding Proxy in Spring Boot

This project builds a lightweight API Gateway using a Spring Boot REST `@RestController`. The Gateway accepts a REST HTTP POST request with a JSON payload, parses it, executes a gRPC call, and returns a JSON response to the client.

### Gateway Transcoder (`TranscodingGatewayController.java`)
```java
package com.example.grpc.patterns;

import com.example.grpc.user.v1.UserProfile;
import com.example.grpc.user.v1.UserRequest;
import com.example.grpc.user.v1.UserServiceGrpc.UserServiceBlockingStub;
import net.devh.boot.grpc.client.inject.GrpcClient;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@RestController
@RequestMapping("/api/gateway")
public class TranscodingGatewayController {

    // Inject the downstream gRPC client stub
    @GrpcClient("user-service")
    private UserServiceBlockingStub userStub;

    @PostMapping("/users/{id}")
    public ResponseEntity<Map<String, Object>> transcodeGetUser(
            @PathVariable("id") int id,
            @RequestBody Map<String, String> requestBody) {

        System.out.println("[Gateway] Received REST Request for User ID: " + id);

        // 1. Map incoming HTTP parameters to Protobuf message
        UserRequest grpcRequest = UserRequest.newBuilder()
            .setUserId(id)
            .build();

        try {
            // 2. Execute downstream gRPC call
            UserProfile grpcResponse = userStub.getUser(grpcRequest);

            // 3. Transcode Protobuf response to REST JSON response map
            return ResponseEntity.ok(Map.of(
                "user_id", grpcResponse.getUserId(),
                "email", grpcResponse.getEmail(),
                "status", grpcResponse.getStatus().name()
            ));

        } catch (Exception e) {
            // Map gRPC failures to appropriate REST HTTP status code
            return ResponseEntity.status(502).body(Map.of(
                "error", "Downstream gRPC service failed",
                "message", e.getMessage()
            ));
        }
    }
}
```

To test the gateway using `curl`:
```bash
curl -X POST http://localhost:8080/api/gateway/users/15 -H "Content-Type: application/json" -d '{}'
```

---

## 6. Interview Questions

### Q1: What is the architectural difference between an API Gateway and a Service Mesh Sidecar Proxy?
**Answer**: 
*   **API Gateway**: Sits at the edge of your infrastructure (North-South traffic). It handles public traffic entering the system, providing routing, rate-limiting, and protocol translation (e.g. HTTP JSON to gRPC).
*   **Service Mesh Sidecar Proxy**: Sits alongside internal microservices (East-West traffic). It handles inter-service communication within the private network, injecting mTLS, tracing, and client load balancing without the services being aware of it.

### Q2: Why is the BFF (Backend-For-Frontend) pattern particularly useful when migrating internal microservices to gRPC?
**Answer**: 
If a mobile client needs data from multiple internal microservices, calling them directly requires HTTP-to-gRPC transcoding at the edge for each individual service.
By using a BFF pattern, the mobile client executes a single HTTP/JSON request to the BFF. The BFF (running inside the Kubernetes cluster with high-speed network access) runs concurrent, non-blocking gRPC calls to the downstream microservices, aggregates the data, filters out unused fields, and returns a single, optimized JSON payload to the mobile client, reducing latency and cellular data usage.
