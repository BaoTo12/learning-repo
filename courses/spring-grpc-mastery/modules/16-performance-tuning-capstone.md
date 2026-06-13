# Module 16: Case Studies & Final Capstone Project

## 1. Five Production Case Studies

### 1.1 E-Commerce: High-Throughput Inventory Reservation System
*   **Topologies**: Checkout Service, Inventory Service, and Payment Service.
*   **Communication Flow**: Client -> Checkout Service (Unary over HTTP/JSON Gateway) -> Inventory Service (Bidirectional streaming over gRPC for in-memory ledger lock reservation) -> Payment Service (Unary over gRPC with mTLS).
*   **Why gRPC**: Reduces latency to ~2ms per transaction. Multiplexing prevents database connection pool exhaustion.
*   **Scaling Challenges**: Maintaining inventory state consistencies under split-second scaling runs. Resolved by caching inventory ledgers dynamically in Redis.
*   **Failure Scenario**: Downstream payment gateway halts. Addressed by isolating downstream threads using Resilience4j circuit breakers.
*   **Observability**: OpenTelemetry spans correlate Checkout, Inventory, and Payment steps.

---

### 1.2 Ride-Hailing: Real-time Geolocation Matching Engine
*   **Topologies**: Driver Service, Matching Service, and Passenger Service.
*   **Communication Flow**: Drivers (Client streaming coordinate updates) -> Driver Service -> Redis Geo Index. Passengers (Server streaming driver query lists) -> Passenger Service -> Matching Service.
*   **Why gRPC**: Dynamic streaming avoids header serialization overhead.
*   **Scaling Challenges**: Balancing active persistent connection sockets across nodes. Resolved by routing traffic via Envoy L7 load balancing.
*   **Failure Scenario**: Core matcher fails. Mitigated by setting client reconnection exponential backoffs with random jitter.
*   **Observability**: Micrometer counts active location stream allocations.

---

### 1.3 Banking Platform: Account Ledger & Fraud Analysis
*   **Topologies**: Account Service, Transaction Service, and Fraud Detection Service.
*   **Communication Flow**: Client -> Transaction Service (Unary gRPC) -> Fraud Detection (Asynchronous parallel gRPC future stubs checking history) -> Account Service (Unary JPA transaction).
*   **Why gRPC**: Strong compilation schema contracts prevent transactional API drifts.
*   **Scaling Challenges**: High cryptographic verification CPU costs during mTLS handshakes. Mitigated by using Netty's OpenSSL (tcnative) engine.
*   **Failure Scenario**: Fraud analyzer times out. Addressed by propagating deadlines to abort transactional locks early.
*   **Observability**: Trace ID correlation MDC mapping links ledger updates to fraud reports.

---

### 1.4 Real-Time Chat Platform: Messaging & Presence Services
*   **Topologies**: Messaging Service, Presence Service, and Notification Service.
*   **Communication Flow**: Clients (Bidirectional gRPC chat stream) -> Messaging Service. Presence (Unary ping checks) -> Presence Service. Offline notifications -> Kafka -> Notification Service.
*   **Why gRPC**: Bidirectional streaming runs natively on standard HTTP/2 DATA frames.
*   **Scaling Challenges**: Thundering herd socket reconnect storms when presence servers restart. Mitigated by applying random jitter reconnect retry loops.
*   **Failure Scenario**: Network partition isolates presence databases. Mitigated by returning offline fallback statuses.
*   **Observability**: Grafana dashboards track concurrent stream allocations.

---

### 1.5 Video Streaming Platform: Recommendation & Analytics Ingestion
*   **Topologies**: User Service, Recommendation Service, and Analytics Service.
*   **Communication Flow**: Client -> User Service. Client playback tracking events -> Analytics Service (High-volume client streaming). Recommendation Service (Unary query).
*   **Why gRPC**: Fast binary serialization handles telemetry metrics.
*   **Scaling Challenges**: Ingestion rate saturates network card buffer limits. Mitigated by applying manual flow control (disableAutoRequest) on analytics streams.
*   **Failure Scenario**: Recommendation service fails. Mitigated by returning static popular recommendations as fallback.
*   **Observability**: Prometheus tracking of bytes ingested per second.

---

## 2. Final Capstone Project: Production-Grade Microservices Platform

### 2.1 Project Objective
You will build a production-grade, thread-safe, and secured **E-Commerce Order Ledger platform** using **Spring Boot and gRPC**.

```
[ Client Gateway ] ===( HTTP/JSON )===> [ Spring Gateway BFF ]
                                               │
                                       ( mTLS gRPC + JWT )
                                               ▼
                                     [ Order Service JVM ]
                                               │
                                     ( Bidi Stream gRPC )
                                               ▼
                                   [ Inventory Service JVM ]
```

### 2.2 Core Architectural Requirements

1.  **Service-to-Service gRPC mTLS**:
    *   Secure communication between Gateway, Order, and Inventory services.
    *   Configure trust stores, keystores, and cert validation directly in `application.yml`.
2.  **Spring Security Integration**:
    *   Extract JWT tokens in a server interceptor.
    *   Bind the parsed user identity to Spring's `SecurityContextHolder`.
    *   Protect service endpoints using `@PreAuthorize("hasRole('ROLE_ADMIN')")`.
3.  **Bidirectional Inventory Streaming**:
    *   The Order service streams order requests to the Inventory service.
    *   The Inventory service reserves items reactively and streams status updates back.
    *   Implement **manual backpressure** on the streams using `disableAutoRequest()` and `setOnReadyHandler()` to handle network congestion safely.
4.  **Resilience Policies**:
    *   Configure Resilience4j circuit breakers and retries on client stubs.
    *   Propagate absolute deadlines downstream; verify that downstream operations abort if the parent request's deadline has expired.
5.  **Observability Pipeline**:
    *   Instrument metrics collection using Spring Boot Actuator and Micrometer.
    *   Link trace contexts to SLF4J MDC to output correlation trace IDs in logs.
    *   Export tracing spans to Jaeger via OpenTelemetry OTLP exporters.
6.  **Automated Testing**:
    *   Write unit tests using in-process server channels and JUnit 5.
    *   Write integration tests using Testcontainers to spin up actual PostgreSQL databases and Kafka message brokers.
7.  **Deployment Configuration**:
    *   Configure Kubernetes deployment manifests. Use **Headless Services** (`clusterIP: None`) to support client-side round-robin load balancing.
