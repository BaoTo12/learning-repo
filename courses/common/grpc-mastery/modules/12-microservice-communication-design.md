# Module 12: Microservice Communication Design Patterns

## 1. What Problem This Module Solves
Microservice topologies present structural complexity when accessed by frontend users:
*   **Protocol Mismatch**: Web browsers and mobile clients consume HTTP/JSON (REST) or WebSockets. They cannot easily speak binary gRPC natively without custom tooling.
*   **Network Latency (BFF)**: If a mobile client needs to call 5 different microservices to render a single dashboard page, executing 5 separate HTTP requests over mobile cellular networks introduces severe latency.
*   **Service Mesh Interception**: Setting up mTLS, retries, and rate limiting individually in every service code container leads to configuration sprawl and update friction.

This module covers microservice integration pattern designs, detailing the API Gateway, Backend-for-Frontends (BFF), and sidecar interception (Service Mesh) models, completed by a hands-on Java HTTP-to-gRPC transcoding proxy.

---

## 2. Structural Patterns Compared

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

## 5. Mini-Project: HTTP-to-gRPC Transcoding Proxy in Java

This project builds a lightweight API Gateway using Java's built-in `com.sun.net.httpserver.HttpServer`. The Gateway accepts a REST HTTP POST request with a JSON payload, parses it, executes a gRPC call, and returns a JSON response to the client.

### Gateway Transcoder (`HttpToGrpcGateway.java`)
```java
package com.example.grpc.patterns;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.stub.ClientCalls;
import io.grpc.MethodDescriptor;
import io.grpc.CallOptions;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

public class HttpToGrpcGateway {

    private final HttpServer httpServer;
    private final ManagedChannel gRpcChannel;

    public HttpToGrpcGateway(int httpPort, String grpcHost, int grpcPort) throws IOException {
        // 1. Initialize HTTP Server
        this.httpServer = HttpServer.create(new InetSocketAddress(httpPort), 0);
        
        // 2. Initialize downstream gRPC connection pool channel
        this.gRpcChannel = ManagedChannelBuilder.forAddress(grpcHost, grpcPort)
            .usePlaintext()
            .build();

        // 3. Register route /api/echo
        this.httpServer.createContext("/api/echo", new TranscodingHandler(gRpcChannel));
        this.httpServer.setExecutor(null); // Default executor
    }

    public void start() {
        httpServer.start();
        System.out.println("HTTP Gateway started on port " + httpServer.getAddress().getPort());
    }

    public void stop() {
        httpServer.stop(2);
        gRpcChannel.shutdown();
    }

    // HTTP Handler that transcodes JSON payloads to gRPC messages
    private static class TranscodingHandler implements HttpHandler {
        private final ManagedChannel channel;

        public TranscodingHandler(ManagedChannel channel) {
            this.channel = channel;
        }

        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                exchange.sendResponseHeaders(405, -1); // Method Not Allowed
                return;
            }

            // Read JSON input stream
            InputStream is = exchange.getRequestBody();
            String jsonInput = new String(is.readAllBytes(), StandardCharsets.UTF_8);

            // Simple manually parsed JSON value (e.g. {"value": "Hello"})
            String parsedValue = extractJsonValue(jsonInput, "value");
            System.out.println("[Gateway] Received HTTP JSON Request: " + jsonInput);

            // Transcode: Create gRPC string representation
            com.google.protobuf.StringValue grpcRequest = com.google.protobuf.StringValue.newBuilder()
                .setValue(parsedValue)
                .build();

            // Execute gRPC call on downstream service
            com.google.protobuf.StringValue grpcResponse;
            try {
                grpcResponse = ClientCalls.blockingUnaryCall(
                    channel,
                    channel.newCall(
                        MethodDescriptor.<com.google.protobuf.StringValue, com.google.protobuf.StringValue>newBuilder()
                            .setType(MethodDescriptor.MethodType.UNARY)
                            .setFullMethodName("EchoService/Echo")
                            .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                                com.google.protobuf.StringValue.getDefaultInstance()))
                            .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                                com.google.protobuf.StringValue.getDefaultInstance()))
                            .build(),
                        CallOptions.DEFAULT
                    ),
                    grpcRequest
                );

                // Construct JSON response body
                String jsonResponse = String.format("{\"echoed_value\":\"%s\"}", grpcResponse.getValue());
                byte[] responseBytes = jsonResponse.getBytes(StandardCharsets.UTF_8);

                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.sendResponseHeaders(200, responseBytes.length);
                OutputStream os = exchange.getResponseBody();
                os.write(responseBytes);
                os.close();

            } catch (Exception e) {
                String errorResponse = "{\"error\":\"Downstream gRPC service failed\"}";
                byte[] errorBytes = errorResponse.getBytes(StandardCharsets.UTF_8);
                exchange.sendResponseHeaders(502, errorBytes.length); // Bad Gateway
                OutputStream os = exchange.getResponseBody();
                os.write(errorBytes);
                os.close();
            }
        }

        private String extractJsonValue(String json, String key) {
            // Helper parsing logic for demonstration (non-production standard)
            String targetKey = "\"" + key + "\":";
            int keyIndex = json.indexOf(targetKey);
            if (keyIndex == -1) return "";
            int start = json.indexOf("\"", keyIndex + targetKey.length()) + 1;
            int end = json.indexOf("\"", start);
            return json.substring(start, end);
        }
    }

    public static void main(String[] args) throws Exception {
        // Start the Gateway pointing to local gRPC service on 9093
        HttpToGrpcGateway gateway = new HttpToGrpcGateway(8080, "localhost", 9093);
        gateway.start();
    }
}
```

To test the gateway using `curl`:
```bash
curl -X POST http://localhost:8080/api/echo -d '{"value":"Hello World"}'
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
