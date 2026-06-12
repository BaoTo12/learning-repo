# Pure Java gRPC Systems Engineering

Welcome to the **Pure Java gRPC Systems Engineering** course. This repository contains a comprehensive, production-grade syllabus designed for senior software engineers, platform architects, and distributed systems specialists.

This course moves past basic API tutorials and framework starters to focus on core gRPC-Java libraries, low-level Netty network bootstrapping, manual thread pools, thread-safe Context propagation, custom Name Resolvers, mTLS security, and unit/integration testing with JUnit 5 and Testcontainers.

---

## 🎯 Course Objectives

By the end of this course, you will be able to:
1. **Analyze HTTP/2 Networks**: Master connection multiplexing, flow control windows, and HPACK compression.
2. **Deconstruct Protobuf Serialization**: Master syntax definitions, Well-Known Types (WKTs), and forward/backward schema compatibility.
3. **Bootstrap gRPC Server & Clients**: Bootstrap `ServerBuilder` manually, configure Netty thread pools, and manage channels.
4. **Develop Streaming Topologies**: Implement Unary, Server-Streaming, Client-Streaming, and Bidirectional Streaming patterns.
5. **Architect Resilient Microservices**: Integrate exception mapping, deadlines, circuit breakers, and retries using standard Java libraries.
6. **Enforce Zero-Trust Security**: Configure Mutual TLS (mTLS) with trust cert collections, and validate JWT/OAuth2 tokens.
7. **Deploy Observability Pipelines**: Instrument metrics (Micrometer) and distributed tracing (OpenTelemetry, Jaeger).
8. **Manage Custom Discovery**: Code custom `NameResolver` providers and client-side load balancing policies.
9. **Build Non-blocking Reactive RPCs**: Adapt standard `StreamObserver` to Project Reactor (`Mono`, `Flux`) flows.
10. **Implement Advanced Testing**: Write unit and integration tests using JUnit 5, in-memory channels, and Testcontainers.

---

## 📚 Structured Syllabus & Modules

The curriculum consists of 16 comprehensive, technical modules:

| Module | Topic | File Link |
| :--- | :--- | :--- |
| **01** | gRPC Foundations & HTTP/2 Deep Dive | [01-grpc-foundations.md](./modules/01-grpc-foundations.md) |
| **02** | Protocol Buffers Deep Dive & Schema Evolution | [02-protobuf-serialization.md](./modules/02-protobuf-serialization.md) |
| **03** | Core Java gRPC Server & Client Bootstrap | [03-corejava-grpc-setup.md](./modules/03-corejava-grpc-setup.md) |
| **04** | Unary, Streaming, and Bidirectional Patterns in Java | [04-communication-patterns.md](./modules/04-communication-patterns.md) |
| **05** | Client Stub Architecture & Threading Models | [05-client-stub-architecture.md](./modules/05-client-stub-architecture.md) |
| **06** | Error Handling, Resilience & Exception Mapping | [06-error-handling.md](./modules/06-error-handling.md) |
| **07** | Security: TLS, mTLS, and Token Authentication | [07-authentication-security.md](./modules/07-authentication-security.md) |
| **08** | Interceptors & Metadata Handling in Java | [08-interceptors-middleware.md](./modules/08-interceptors-middleware.md) |
| **09** | Observability: OpenTelemetry and SLF4J in Java | [09-observability-telemetry.md](./modules/09-observability-telemetry.md) |
| **10** | Performance Engineering & Java GC Tuning | [10-performance-tuning.md](./modules/10-performance-tuning.md) |
| **11** | Service Discovery & Custom Name Resolvers | [11-service-discovery-resolvers.md](./modules/11-service-discovery-resolvers.md) |
| **12** | Microservice Communication Design Patterns | [12-microservice-communication-design.md](./modules/12-microservice-communication-design.md) |
| **13** | Reactive gRPC & Project Reactor | [13-reactive-grpc-reactor.md](./modules/13-reactive-grpc-reactor.md) |
| **14** | Testing Strategies: Unit, Integration, and Contract Testing | [14-testing-strategies.md](./modules/14-testing-strategies.md) |
| **15** | Advanced Production Operations | [15-advanced-production-topics.md](./modules/15-advanced-production-topics.md) |
| **16** | Case Studies & Graduation Capstone Project | [16-performance-tuning-capstone.md](./modules/16-performance-tuning-capstone.md) |

---

## 🛠️ Local Sandbox Infrastructure Setup

To run the labs and the final capstone project, you will need a docker-compose sandbox containing:
- **Consul**: For service registration.
- **Jaeger**: For distributed tracing.
- **Prometheus & Grafana**: For telemetry metrics.

Save the following configuration block as `docker-compose.yml` in your working directory:

```yaml
version: '3.8'

services:
  # Service Discovery Registry
  consul:
    image: hashicorp/consul:1.15.2
    container_name: grpc-consul
    ports:
      - "8500:8500"
    command: "agent -dev -client=0.0.0.0"
    networks:
      - grpc-net

  # Distributed Tracing Backend
  jaeger:
    image: jaegertracing/all-in-one:1.45
    container_name: grpc-jaeger
    ports:
      - "16686:16686" # UI
      - "4317:4317"   # OTLP gRPC collector
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    networks:
      - grpc-net

  # Metrics Engine
  prometheus:
    image: prom/prometheus:v2.44.0
    container_name: grpc-prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    networks:
      - grpc-net

  # Metrics Dashboard
  grafana:
    image: grafana/grafana:9.5.2
    container_name: grpc-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    networks:
      - grpc-net

networks:
  grpc-net:
    driver: bridge
```

---

## 📈 Graduation & System Assessment Rubrics

Projects are evaluated against four core criteria:

### 1. Schema & Toolchain Architecture (25% Weight)
*   **Optimal Protobuf Definitions**: Correct use of fields, required vs optional semantics, and packages versioning.
*   **Buf Compliance**: Linting rules configured correctly, and breaking change checks running in build pipelines.

### 2. Core Java gRPC Architecture (25% Weight)
*   **Netty Server Configuration**: Manual server bootstrapping, executor thread pools, and ManagedChannel reuse.
*   **Context Propagation**: Thread-safe context propagation using `io.grpc.Context` APIs.

### 3. Reliability and Security (25% Weight)
*   **Fault Tolerance**: Exception mapping, deadlines, circuit breakers, and retries using standard Java libraries.
*   **Security Controls**: mTLS configured with keystore/truststore verification, and custom JWT validation interceptors.

### 4. Observability & Testing (25% Weight)
*   **Telemetry Coverage**: Metrics collected using Micrometer Core, and tracing context propagated across calls.
*   **Testing Coverage**: Unit and integration tests written using JUnit 5, in-memory channels, and Testcontainers.

Let's begin! Access [Module 01: gRPC Foundations & HTTP/2 Deep Dive](./modules/01-grpc-foundations.md) to start your learning journey.
