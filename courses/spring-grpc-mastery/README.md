# Spring Boot gRPC Systems Engineering

Welcome to the **Spring Boot gRPC Systems Engineering** course. This repository contains a comprehensive, production-grade syllabus designed for senior software engineers, platform architects, and distributed systems specialists who build, scale, and secure enterprise microservices using Spring Boot and gRPC.

This course teaches you how to design and operate gRPC microservices with Spring Boot. You will learn to use community-standard starters, integrate Spring Security, configure custom thread executors, implement global exception maps, enforce mTLS, monitor services with Micrometer and OpenTelemetry, and deploy service discovery with Consul.

---

## 🎯 Course Objectives

By the end of this course, you will be able to:
1. **Understand HTTP/2 Internals**: Master connection multiplexing, flow control, and HPACK compression.
2. **Design Protobuf Schemas**: Master message design, Well-Known Types, and backward/forward compatibility rules.
3. **Configure Spring gRPC Servers & Clients**: Integrate gRPC with Spring Boot's dependency injection and bean lifecycles.
4. **Implement Complex Streaming**: Code Unary, Server-Streaming, Client-Streaming, and Bidirectional Streaming patterns.
5. **Architect Resilient Microservices**: Implement global exception mapping (`@GrpcAdvice`), deadlines, retries, and circuit breakers with Resilience4j.
6. **Enforce Zero-Trust Security**: Configure mTLS, Spring Security integration, and JWT extraction.
7. **Deploy Observability Pipelines**: Integrate Spring Boot Actuator, Micrometer core, OpenTelemetry, and Jaeger.
8. **Manage Service Discovery**: Route services dynamically with Consul and Kubernetes.
9. **Build Non-blocking Reactive Streams**: Integrate gRPC with Project Reactor (`Flux`, `Mono`) in Spring WebFlux.
10. **Implement Testing Frameworks**: Build automated unit and integration tests using JUnit 5, Spring Boot testing stubs, and Testcontainers.

---

## 📚 Structured Syllabus & Modules

The curriculum consists of 16 comprehensive, production-focused modules:

| Module | Topic | File Link |
| :--- | :--- | :--- |
| **01** | gRPC Fundamentals & HTTP/2 in Spring Boot | [01-grpc-fundamentals.md](./modules/01-grpc-fundamentals.md) |
| **02** | Protocol Buffers & Schema Evolution | [02-protobuf-serialization.md](./modules/02-protobuf-serialization.md) |
| **03** | Spring Boot gRPC Server & Client Setup | [03-springboot-grpc-setup.md](./modules/03-springboot-grpc-setup.md) |
| **04** | Spring Boot gRPC Communication Patterns | [04-communication-patterns.md](./modules/04-communication-patterns.md) |
| **05** | Spring gRPC Client Architecture | [05-spring-client-architecture.md](./modules/05-spring-client-architecture.md) |
| **06** | Error Handling and Reliability | [06-error-handling.md](./modules/06-error-handling.md) |
| **07** | Security: mTLS and Spring Security Integration | [07-authentication-security.md](./modules/07-authentication-security.md) |
| **08** | Interceptors & Metadata in Spring | [08-interceptors-middleware.md](./modules/08-interceptors-middleware.md) |
| **09** | Observability: Micrometer and OpenTelemetry | [09-observability-telemetry.md](./modules/09-observability-telemetry.md) |
| **10** | Performance Engineering & JVM GC Tuning | [10-performance-tuning.md](./modules/10-performance-tuning.md) |
| **11** | Service Discovery & Cloud-Native Deployment | [11-service-discovery-resolvers.md](./modules/11-service-discovery-resolvers.md) |
| **12** | Microservice Communication Design | [12-microservice-communication-design.md](./modules/12-microservice-communication-design.md) |
| **13** | Reactive gRPC & Spring WebFlux | [13-reactive-grpc-reactor.md](./modules/13-reactive-grpc-reactor.md) |
| **14** | Testing Spring gRPC Services | [14-testing-strategies.md](./modules/14-testing-strategies.md) |
| **15** | Advanced Operations & Rate Limiting | [15-advanced-production-topics.md](./modules/15-advanced-production-topics.md) |
| **16** | Case Studies & Final Capstone Project | [16-performance-tuning-capstone.md](./modules/16-performance-tuning-capstone.md) |

---

## 🛠️ Local Sandbox Infrastructure Setup

To run the hands-on labs, you will need a local Docker infrastructure. Save the following configuration block as `docker-compose.yml` in your working directory:

```yaml
version: '3.8'

services:
  # Database Storage
  postgres:
    image: postgres:15-alpine
    container_name: spring-grpc-postgres
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=grpc_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    networks:
      - grpc-net

  # Cache & Session Store
  redis:
    image: redis:7.0-alpine
    container_name: spring-grpc-redis
    ports:
      - "6379:6379"
    networks:
      - grpc-net

  # Messaging Broker
  kafka:
    image: confluentinc/cp-kafka:7.3.0
    container_name: spring-grpc-kafka
    ports:
      - "9092:9092"
    environment:
      - KAFKA_NODE_ID=1
      - KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      - KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      - KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1
      - KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS=0
      - KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1
      - KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1
      - KAFKA_PROCESS_ROLES=broker,controller
      - KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka:29093
      - KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:29092,CONTROLLER://0.0.0.0:29093,PLAINTEXT_HOST://0.0.0.0:9092
      - KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT
      - KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER
      - KAFKA_LOG_DIRS=/tmp/kraft-combined-logs
      - CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qk
    networks:
      - grpc-net

  # Registry Discovery
  consul:
    image: hashicorp/consul:1.15.2
    container_name: spring-grpc-consul
    ports:
      - "8500:8500"
    command: "agent -dev -client=0.0.0.0"
    networks:
      - grpc-net

  # Tracing Backend
  jaeger:
    image: jaegertracing/all-in-one:1.45
    container_name: spring-grpc-jaeger
    ports:
      - "16686:16686" # UI
      - "4317:4317"   # OTLP collector
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    networks:
      - grpc-net

  # Metrics Engine
  prometheus:
    image: prom/prometheus:v2.44.0
    container_name: spring-grpc-prometheus
    ports:
      - "9090:9090"
    networks:
      - grpc-net

  # Metrics Visualization
  grafana:
    image: grafana/grafana:9.5.2
    container_name: spring-grpc-grafana
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

Assessments will evaluate projects across four dimensions:

### 1. Schema Design & Evolution (25% Weight)
*   **Protobuf Integrity**: Proper naming, tag selections, nested message structures, and use of Well-Known Types.
*   **API Evolution**: Safe deprecation practices, compatibility verification, and versioning routing.

### 2. Spring Integration & Threading (25% Weight)
*   **Spring Boot Wiring**: Proper bean injection, channel sharing, starter parameter setups, and service registration.
*   **Thread Allocation**: Correct thread configurations isolating business operations from Netty IO worker pools.

### 3. Reliability and Security (25% Weight)
*   **Resilience Policies**: Robust implementation of retries, circuit breakers, backpressure, and deadline propagation.
*   **Zero-Trust Setup**: Implementation of transport security (mTLS) alongside application security (JWT and RBAC via Spring Security).

### 4. Observability & Testing (25% Weight)
*   **Observability Pipeline**: Proper tracing propagation, Micrometer latency metrics, and trace-logging linkages.
*   **Test Suite Coverage**: Complete automated verification using in-memory channels, JUnit 5, and Testcontainers.
