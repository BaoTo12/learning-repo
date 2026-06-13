# CS-520: Java-based WebSockets Mastery

Welcome to **CS-520: Java-based WebSockets Mastery**. I am Professor Antigravity. In this course, we will transition from request-response REST APIs to stateful, full-duplex, persistent connection systems.

HTTP is fundamentally stateless and client-initiated. For real-time applications (such as collaborative documents, live chats, stock tickers, or multiplayer gaming), HTTP polling is too slow and wastes bandwidth. WebSockets solve this by upgrading a standard HTTP request to a persistent TCP connection.

In this course, we will study **RFC 6455 Protocol Foundations (handshakes, framing)**, **Jakarta WebSockets (JSR 356)**, **Spring Boot WebSockets**, **STOMP sub-protocol routing**, **WebSocket Security (JWT interceptors)**, **clustering & horizontal scaling (Redis/RabbitMQ)**, and **Reactive WebSockets in Spring WebFlux**.

---

## Course Syllabus & Navigation

The course is divided into 9 modules and a final application engineering capstone project:

| Module | Core Classification | Focus Topics |
| :--- | :--- | :--- |
| **01** | [Protocol Foundations](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-websockets/modules/01-protocol-foundations.md) | WebSocket protocol (RFC 6455), HTTP Upgrade handshakes, Frame structures (masking, opcode, fin bit). |
| **02** | [Jakarta WebSockets](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-websockets/modules/02-jakarta-websockets.md) | JSR 356 API (`@ServerEndpoint`), Session lifecycle, thread-safety, custom Encoders/Decoders. |
| **03** | [Spring WebSockets](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-websockets/modules/03-spring-websockets.md) | Spring `WebSocketHandler`, Handshake interceptors, mapping session attributes. |
| **04** | [STOMP & SockJS](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-websockets/modules/04-stomp-sockjs.md) | STOMP frames, publish-subscribe message routing, SockJS fallback transports. |
| **05** | [WebSocket Security](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-websockets/modules/05-websocket-security.md) | Securing handshakes vs STOMP connections, Spring Security JWT channel interceptors. |
| **06** | [Horizontal Scaling](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-websockets/modules/06-horizontal-scaling.md) | Stateful clustering challenges, Redis Pub/Sub, and RabbitMQ STOMP external broker relays. |
| **07** | [Reactive WebSockets](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-websockets/modules/07-reactive-websockets.md) | Spring WebFlux reactive handlers, Reactor pipelines (`Flux`/`Mono`), and backpressure. |
| **08** | [Reliability & Reconnections](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-websockets/modules/08-reliability-reconnections.md) | Load balancer timeouts, Heartbeats (Ping/Pong frame configs), client reconnection strategies. |
| **09** | [Testing & Monitoring](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-websockets/modules/09-testing-monitoring.md) | Integration testing with `WebSocketClient`, testing STOMP routes, and Prometheus connection metrics. |
| **10** | [Final Capstone Project](file:///c:/Users/Admin/Desktop/projects/learning-repo/java-websockets/modules/10-final-capstone-collaborative-editor.md) | Building a secure, clustered, collaborative document editor microservice. |

---

## Local Infrastructure Configuration

To run and scale our clustered WebSocket setups locally, we use a message broker. Place the following `docker-compose.yml` file in your project root to run **RabbitMQ with STOMP enabled** and **Redis**:

```yaml
version: '3.8'

services:
  # RabbitMQ acts as our external STOMP Message Broker Relay
  rabbitmq:
    image: rabbitmq:3.12-management
    container_name: rabbitmq_stomp
    ports:
      - "5672:5672"   # AMQP protocol
      - "15672:15672" # Management Web UI
      - "61613:61613" # STOMP Protocol Port
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    command: >
      sh -c "rabbitmq-plugins enable --offline rabbitmq_stomp rabbitmq_web_stomp && rabbitmq-server"

  # Redis acts as our lightweight Session registry and Pub/Sub sync engine
  redis:
    image: redis:7.0-alpine
    container_name: redis_ws
    ports:
      - "6379:6379"
```

Start the containers from your terminal:
```bash
docker-compose up -d
```

---

## Grading Criteria & Defensive Success Metrics

Your progress in this course is evaluated based on the following metrics:

*   **Connection Reliability (30%)**: Correctly configuring heartbeats, handling idle timeouts, and implementing robust client-side reconnection structures.
*   **Security & Interception Rigor (30%)**: Preventing anonymous connections by validating JWTs at the STOMP channel layer, and securing handshakes against CSRF.
*   **Clustering & Scaling Accuracy (20%)**: Implementing stateless brokers to synchronize active user sessions across multiple Spring Boot instances.
*   **Reactive Flow Control (20%)**: Writing non-blocking reactive stream pipelines that handle backpressure and prevent thread starvation under heavy load.
