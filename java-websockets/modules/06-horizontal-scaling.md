# Module 06: Horizontal Scaling — Clustered Brokers & RabbitMQ Relays

Welcome back, class. Today we analyze **Horizontal Scaling (CS-520)**.

Traditional HTTP web servers are stateless. Because of this, scaling HTTP servers horizontally behind a Round-Robin load balancer is trivial. WebSockets, however, are persistent, stateful TCP connections. A client's connection remains pinned to the specific server node that processed the initial handshake.

This presents a major challenge in clustered environments. If User A is connected to Node 1, and User B is connected to Node 2, Node 1 has no knowledge of User B's connection. If User A publishes a message, User B will never receive it. Today, we will study the stateful connection problem and configure an external **RabbitMQ STOMP Broker Relay** to synchronize messages across nodes.

---

## 1. Academic Lecture: The Stateful Connection Problem

To scale WebSockets, we must decouple connection management from message routing.

### 1. The Clustering Dilemma
If your application uses the default in-memory simple broker (`config.enableSimpleBroker("/topic")`), subscriptions and message queues are stored in the JVM heap of that specific instance.

```
       In-Memory Broker Fail Path (Clustered)
       
  Client A (Node 1) ---> Node 1 [Memory: Client A]
  Client B (Node 2) ---> Node 2 [Memory: Client B]
  
  (Client A sends message to /topic/room1. 
   Node 1 broadcasts locally, but cannot reach Node 2. 
   Client B receives nothing.)
```

### 2. The External Broker Relay Solution
To solve this, we replace the in-memory broker with a **Broker Relay**. The Spring Boot instances act as connection managers: they handle TCP handshakes, TLS termination, and unmasking. The routing of messages, however, is delegated to an external, shared message broker (like RabbitMQ) using the STOMP protocol.

```mermaid
graph TD
    A[Client A] -->|TCP Connection| B[Spring Node 1]
    C[Client B] -->|TCP Connection| D[Spring Node 2]
    
    B -->|STOMP Relay| E[Shared RabbitMQ Broker]
    D -->|STOMP Relay| E
    
    Note over E: RabbitMQ syncs subscriptions.<br/>If Node 1 sends a message,<br/>RabbitMQ relays it to Node 2<br/>to deliver to Client B.
```

1.  User A sends a message to `/topic/room1` via Node 1.
2.  Node 1 forwards the frame to the shared RabbitMQ broker over its internal STOMP TCP socket.
3.  RabbitMQ identifies all active subscribers for `/topic/room1` across all nodes.
4.  RabbitMQ pushes the message to both Node 1 and Node 2.
5.  Node 2 receives the relayed message and delivers it to User B.

---

## 2. Theory vs. Production Trade-offs

### Redis Pub/Sub vs. RabbitMQ STOMP Relay
*   **Redis Pub/Sub (Application-Level Sync)**:
    *   *Pro*: Lightweight, fast, and simple to configure if you already use Redis for caching.
    *   *Con*: You must write custom listener code in Java to intercept WebSocket sessions and broadcast messages to Redis channels, which increases application complexity.
*   **RabbitMQ STOMP Relay**:
    *   *Pro*: Fully transparent. Spring handles all relay connections automatically under the hood, and RabbitMQ provides robust queue management features.
    *   *Con*: High operational complexity. Requires maintaining a RabbitMQ cluster with high-availability configurations.

---

## 3. How to Use: Configuring a RabbitMQ Broker Relay in Spring Boot

Let us configure Spring Boot to delegate STOMP routing to an external RabbitMQ message broker.

### A. The Stateless Simple Broker (Anti-Pattern)

Avoid using the simple, in-memory broker in clustered production environments:

```java
package com.capstone.security.ws.vulnerable;

import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;

public class VulnerableClusterConfig implements WebSocketMessageBrokerConfigurer {
    @Override
    public void configureMessageBroker(MessageBrokerRegistry config) {
        // DANGER: In-memory broker does not synchronize messages across cluster nodes,
        // causing message loss in horizontal scaling.
        config.enableSimpleBroker("/topic");
        config.setApplicationDestinationPrefixes("/app");
    }
}
```

### B. The Hardened RabbitMQ Broker Relay Configuration (Production Pattern)

Here is the hardened configuration. It replaces the simple broker with the STOMP Broker Relay, pointing to a RabbitMQ cluster.

```java
package com.capstone.security.ws.secure.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.web.socket.config.annotation.EnableWebSocketMessageBroker;
import org.springframework.web.socket.config.annotation.StompEndpointRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;

@Configuration
@EnableWebSocketMessageBroker
public class ClusteredWebSocketConfig implements WebSocketMessageBrokerConfigurer {

    @Override
    public void configureMessageBroker(MessageBrokerRegistry config) {
        // Define application routing prefix for controller mapping methods
        config.setApplicationDestinationPrefixes("/app");

        // SECURE: Replace in-memory broker with external RabbitMQ Broker Relay
        config.enableStompBrokerRelay("/topic", "/queue")
                .setRelayHost("127.0.0.1")
                .setRelayPort(61613) // Default RabbitMQ STOMP plugin port
                .setClientLogin("guest")
                .setClientPasscode("guest")
                .setSystemLogin("guest")
                .setSystemPasscode("guest")
                // Define user-specific queue destination prefixes
                .setUserDestinationBroadcast("/topic/unresolved-user-destination")
                .setUserRegistryBroadcast("/topic/user-registry");
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws-stomp-cluster")
                .setAllowedOrigins("https://trusted-app.corp.com")
                .withSockJS();
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Bypassing Heartbeat Configurations on the Broker Relay
Failing to configure system heartbeats when connecting to the external RabbitMQ broker.
*   **Why it fails**: Firewalls and cloud load balancers terminate idle TCP connections after 60 seconds of inactivity. If no heartbeats are sent, RabbitMQ will silently close the relay socket, causing Spring to lose connection to the broker.
*   **Mitigation**: Always set heartbeat rates on the broker relay configurations:
    ```java
    config.enableStompBrokerRelay("/topic")
          .setSystemHeartbeatSendInterval(10000)
          .setSystemHeartbeatReceiveInterval(10000);
    ```

---

## 5. Socratic Review Questions

### Question 1
Why does horizontal scaling of WebSockets require a separate port (e.g., `61613` for RabbitMQ STOMP) instead of standard AMQP ports (like `5672`)?

#### Answer
AMQP (`5672`) is a binary queue protocol used for backend service-to-service communication. WebSockets use the text-based STOMP protocol. 
To relay STOMP frames from the browser to RabbitMQ, RabbitMQ must run the **STOMP Plugin**, which opens a dedicated listener port (`61613`). This port is configured to translate incoming STOMP frames into internal AMQP queue messages.

### Question 2
What is the purpose of `setUserDestinationBroadcast` and `setUserRegistryBroadcast` configurations in clustered environments?

#### Answer
When User A on Node 1 sends a private message to User B on Node 2 (using `/user/UserB/queue/alerts`), Node 1 does not know where User B is connected. 
*   `setUserRegistryBroadcast`: Tells the cluster nodes to share their local connection registries, enabling them to identify which node User B is connected to.
*   `setUserDestinationBroadcast`: Tells Node 1 to broadcast the user destination message across the cluster, allowing Node 2 to receive the message and deliver it to User B.

---

## 6. Hands-on Challenge: Configuring the Broker Relay

### The Challenge
In this challenge, you will write a Spring Boot configuration configuration class to set up a STOMP Broker Relay.

Your task:
1.  Complete the `configureMessageBroker` method to enable a STOMP Broker Relay.
2.  Target the relay host `rabbitmq.internal.corp` on port `61613`.
3.  Set the system credentials to username `admin` and password `safePassword123`.

Complete the configuration implementation below:

```java
package com.capstone.security.ws.challenge;

import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;

public class HardenedBrokerRelayConfig implements WebSocketMessageBrokerConfigurer {

    @Override
    public void configureMessageBroker(MessageBrokerRegistry config) {
        config.setApplicationDestinationPrefixes("/app");

        // TODO: Complete the configuration.
        // 1. Call config.enableStompBrokerRelay("/topic")
        // 2. Set the host to "rabbitmq.internal.corp" and port to 61613.
        // 3. Set clientLogin and clientPasscode to "admin" / "safePassword123".
        // 4. Set systemLogin and systemPasscode to "admin" / "safePassword123".
    }
}
```

Write the configuration methods. Save the completed class and explain why the broker relay relies on TCP persistence inside `modules/06-horizontal-scaling.md`.
