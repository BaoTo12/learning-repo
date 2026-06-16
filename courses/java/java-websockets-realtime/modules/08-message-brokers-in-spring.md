# Module 8: Message Brokers in Spring

To route STOMP messages efficiently, Spring Boot implements a message broker subsystem. A systems architect must understand how Spring manages message queues internally and how to transition from local in-memory brokers to production-grade external messaging infrastructure.

This module details Spring's internal messaging channels, breaks down the lifecycle of the in-memory `SimpleBroker`, explains the integration parameters of the `StompBrokerRelay`, compares topic and queue destinations, and implements compilable configuration classes for both tuned simple and clustered RabbitMQ message brokers.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the layout of Spring's three message channels** (`clientInboundChannel`, `clientOutboundChannel`, `brokerChannel`) and trace how messages flow through them.
2. **Configure keep-alive heartbeats** and task schedulers inside an in-memory `SimpleBroker`.
3. **Deploy a `StompBrokerRelay`** to connect Spring Boot to an external message broker (RabbitMQ) over TCP sockets.
4. **Differentiate between Topic and Queue destinations** and configure private user routing (`/user/queue/*`).
5. **Map STOMP destinations** to RabbitMQ exchanges (Direct, Fanout, Topic) to coordinate microservice communication.

---

## 1. Spring's Messaging Architecture (Message Channels)

When you enable STOMP messaging in Spring Boot, the framework instantiates three independent **Message Channels** implemented as thread-pool executors. Understanding these channels is key to debugging messaging bottlenecks:

```
Client ──► [WebSocketSession] ──► [clientInboundChannel] ──► [Controller or Broker]
                                                                    │
Server ◄── [WebSocketSession] ◄── [clientOutboundChannel] ◄─────────┤ (Routes frames)
                                                                    │
                                   [brokerChannel] ◄────────────────┘
```

### 1. `clientInboundChannel`
- **Role**: Transmits messages received from client sockets to application controllers (`@MessageMapping`) or directly to the message broker.
- **Tuning**: If controllers execute blocking database queries, this channel's thread pool must be expanded to prevent incoming message backlogs.

### 2. `clientOutboundChannel`
- **Role**: Transmits messages from the server (either from controllers or the broker) to connected client sockets.
- **Tuning**: If a client is on a slow network, the thread sending messages to its socket can block. Sizing this pool correctly prevents slow clients from starving other active subscribers.

### 3. `brokerChannel`
- **Role**: Transmits messages from application controllers back to the message broker (e.g. forwarding a broadcast request).

### Executor Thread Pool Tuning Configuration:
```java
@Override
public void configureClientInboundChannel(ChannelRegistration registration) {
    registration.taskExecutor()
            .corePoolSize(16)      // Minimum active threads
            .maxPoolSize(64)       // Maximum thread count under load
            .queueCapacity(500)    // Inbound queue capacity limit
            .keepAliveSeconds(60); // Inactive thread clean timeout
}

@Override
public void configureClientOutboundChannel(ChannelRegistration registration) {
    registration.taskExecutor()
            .corePoolSize(16)
            .maxPoolSize(64)
            .queueCapacity(500);
}
```

---

## 2. SimpleBroker Mechanics

The `SimpleBroker` is Spring's default, in-memory message broker.
- **How it works**: It maintains a subscription registry map in JVM heap memory. When a client sends a `SUBSCRIBE` frame to `/topic/chat`, the broker registers the session ID. When a `SEND` frame arrives, the broker queries the map and pushes duplicate messages asynchronously onto the `clientOutboundChannel` pool.
- **Heartbeat Configuration**:
  To detect disconnected clients early, you must enable heartbeats. A heartbeat is a periodic transaction where client and server exchange pings.
  - `setHeartbeatValue(new long[]{10000, 10000})`: The first value defines the write interval (sending pings every 10 seconds), and the second value defines the read interval (expecting pings from the client every 10 seconds).
  - Enabling heartbeats requires registering a `TaskScheduler` to drive the polling events.

---

## 3. StompBrokerRelay (External Brokers Integration)

To support clustering and high availability, you must replace the in-memory broker with Spring's `StompBrokerRelayMessageHandler`.

- **The Relay Mechanism**:
  Instead of managing subscription maps in JVM heap, Spring opens a pool of persistent TCP socket connections to an external message broker (such as RabbitMQ or ActiveMQ) over port **`61613`** (the default STOMP protocol port).
  - When Client A subscribes, Server 1 forwards a `SUBSCRIBE` frame to RabbitMQ.
  - When Client B sends a message to Server 2, Server 2 forwards a `SEND` frame to RabbitMQ.
  - RabbitMQ routes the message back to Server 1's TCP stream. Server 1 reads the raw STOMP frame and dispatches it to Client A.

- **Relay Configuration Parameters**:
  - **System Login / Passcode**: Used by Spring's background handlers to establish administrative queues and monitor broker health.
  - **Client Login / Passcode**: Standard credentials forwarded to the broker for individual user session validation.
  - **Virtual Host**: Defines isolated broker namespaces (e.g. `/dev`, `/prod`).
  - **Auto-Reconnect**: Configures the relay handler to automatically re-establish TCP sockets to the broker if connection drops occur.

---

## 4. Topics vs. Queues in Enterprise Systems

Destinations are mapped to different routing patterns on the broker:

### 1. Topics (`/topic/*`) - Publish-Subscribe
- Messages are broadcast to **all** active subscribers.
- Ideal for group chat rooms, live stock tickers, or system alerts.

### 2. Queues (`/queue/*`) - Point-to-Point
- Messages are delivered to **exactly one** subscriber, typically using a round-robin distribution.
- Ideal for dividing CPU-heavy processing workloads among worker threads.

### 3. Private User Queues (`/user/queue/*`)
To send a message to a specific authenticated user (e.g., Alice):
1. The server pushes a message to the destination `/user/Alice/queue/notifications`.
2. Spring's **`UserDestinationMessageHandler`** intercepts this destination.
3. It queries the `UserSessionRegistry` to locate all active WebSocket session IDs owned by "Alice".
4. It translates the destination to a unique session-specific queue (e.g. `/queue/notifications-user-session-abc123`) and routes the frame directly to Alice's connection.

---

## 5. Publish-Subscribe Routing Patterns

When integrated with RabbitMQ, STOMP destinations are mapped directly to RabbitMQ Exchanges and Routing Keys:

### 1. Topic Exchange (`amq.topic`)
Used for `/topic/*` destinations. Supports wildcard routing keys (e.g. subscribing to `/topic/chat.*` matches `chat.room1` and `chat.room2`).

### 2. Direct Exchange (`amq.direct`)
Used for `/queue/*` destinations. Delivers messages directly to the queue matching the exact routing key.

### STOMP to RabbitMQ Exchange Destination Mapping Rules:
- A `SEND` from a client to `/topic/chat` maps to a message sent to the exchange `amq.topic` with the routing key `chat`.
- A `SUBSCRIBE` from a client to `/topic/sports.*` binds a temporary queue on RabbitMQ to the `amq.topic` exchange with the binding pattern `sports.*`.

---

## 6. Hands-On Lab 1: Configuring a Tuned SimpleBroker

In this lab, you will implement a compilable configuration class that registers a custom `ThreadPoolTaskScheduler` to drive a simple in-memory broker with a 15-second heartbeat check.

### Code Implementation (`TunedSimpleBrokerConfig.java`):

```java
package com.example.realtime.broker.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.web.socket.config.annotation.*;

@Configuration
@EnableWebSocketMessageBroker
public class TunedSimpleBrokerConfig implements WebSocketMessageBrokerConfigurer {

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        // Map STOMP endpoint, allowing all origins for testing
        registry.addEndpoint("/ws-simple-tuned")
                .setAllowedOrigins("*");
    }

    @Override
    public void configureMessageBroker(MessageBrokerRegistry registry) {
        // Configure simple broker and enable 15-second heartbeats.
        // Index 0: Server sends pings every 15,000ms.
        // Index 1: Server expects pings from client every 15,000ms.
        registry.enableSimpleBroker("/topic", "/queue")
                .setHeartValue(new long[]{15000L, 15000L})
                .setTaskScheduler(heartbeatScheduler());

        registry.setApplicationDestinationPrefixes("/app");
    }

    /**
     * Scheduler bean required to drive heartbeat timing events
     */
    @Bean
    public ThreadPoolTaskScheduler heartbeatScheduler() {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
        scheduler.setPoolSize(2);
        scheduler.setThreadNamePrefix("ws-heartbeat-");
        scheduler.initialize();
        return scheduler;
    }
}
```

---

## 7. Hands-On Lab 2: Integrating an External RabbitMQ Broker

In this lab, you will implement a configuration class that replaces the in-memory SimpleBroker with an external `StompBrokerRelay` that connects to a local or remote RabbitMQ message broker on port `61613` (TCP).

### Code Implementation (`RabbitBrokerConfig.java`):

```java
package com.example.realtime.broker.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.web.socket.config.annotation.*;

@Configuration
@EnableWebSocketMessageBroker
public class RabbitBrokerConfig implements WebSocketMessageBrokerConfigurer {

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws-rabbit-relay")
                .setAllowedOrigins("*");
    }

    @Override
    public void configureMessageBroker(MessageBrokerRegistry registry) {
        // Disable in-memory broker and enable the external STOMP Broker Relay.
        // Messages starting with /topic or /queue are forwarded to RabbitMQ.
        registry.enableStompBrokerRelay("/topic", "/queue")
                .setRelayHost("127.0.0.1")       // RabbitMQ server IP address
                .setRelayPort(61613)             // Default RabbitMQ STOMP plugin port (TCP)
                .setClientLogin("guest")         // Client credentials for connection authentication
                .setClientPasscode("guest")
                .setSystemLogin("guest")         // Admin credentials for system queues creation
                .setSystemPasscode("guest")
                .setVirtualHost("/")             // Default RabbitMQ vhost
                .setSystemHeartbeatSendInterval(10000L) // System ping rate
                .setSystemHeartbeatReceiveInterval(10000L);

        // Application controllers destination prefix
        registry.setApplicationDestinationPrefixes("/app");
    }
}
```

---

## 8. Common Mistakes & Debugging Scenarios

### Scenario A: Inbound Channel Starvation Under High Load
* **The Problem**: A Spring Boot STOMP application runs fine under low traffic. However, during load spikes, message processing lags, and client heartbeats time out, causing frequent connection drops.
* **Why it happens**: By default, Spring's `clientInboundChannel` thread pool is sized dynamically based on CPU cores. If your controller methods (`@MessageMapping`) execute blocking database or HTTP operations, the inbound channel threads are locked. The channel can no longer process incoming heartbeat pings from clients. The broker assumes the client is disconnected and closes the socket.
* **The Fix**: Expand the inbound channel thread pool capacity and configure it to use non-blocking patterns, or offload blocking database operations to a separate thread pool.
  ```java
  @Override
  public void configureClientInboundChannel(ChannelRegistration registration) {
      registration.taskExecutor()
                  .corePoolSize(16)
                  .maxPoolSize(64)
                  .queueCapacity(500);
  }
  ```

### Scenario B: Missing STOMP Plugin on RabbitMQ
* **The Problem**: You deploy your application with `StompBrokerRelay` active, but the server crashes during boot, throwing a `java.net.ConnectException: Connection refused` pointing to port `61613`.
* **Why it happens**: By default, RabbitMQ only enables the AMQP protocol on port `5672`. It does not listen on the STOMP port (`61613`) until the STOMP plugin is explicitly enabled.
* **The Fix**: Enable the STOMP plugin on your RabbitMQ server:
  ```bash
  rabbitmq-plugins enable rabbitmq_stomp
  ```
  Restart RabbitMQ and verify the port is active using `ss -tlnp | grep 61613`.

---

## 9. Technical Interview Questions

### Question 1: SimpleBroker vs. StompBrokerRelay
*What are the mechanical differences in message distribution between the SimpleBroker and the StompBrokerRelay when multiple clients subscribe to the same topic?*

**Answer**:
- **`SimpleBroker`** routes messages in-memory. It maintains a subscription map on the JVM heap. When a message is sent to a topic, Spring's broker handler loops through the local map, serializes the message to a STOMP frame, and writes it directly to each client's socket using the `clientOutboundChannel` thread pool.
- **`StompBrokerRelay`** does not manage subscriptions or distribute messages itself. It delegates this logic to an external broker (like RabbitMQ). When a message is sent, Spring forwards a single STOMP `SEND` frame to RabbitMQ over a TCP socket. RabbitMQ processes the routing rules, determines which application server instances have active subscribers, and routes the message back to those servers over their respective TCP streams. The servers then push the message to their local clients.

---

### Question 2: /user/queue Destination Translation
*Explain how Spring's User Destination mapping routes private messages to specific users. What is the role of the UserSessionRegistry?*

**Answer**:
When a client sends a message to `/user/{username}/queue/notifications` (or when a controller uses `@SendToUser`), the destination is intercepted by the `UserDestinationMessageHandler`:
1. It queries the **`SimpUserRegistry`** to find the target username.
2. The registry resolves the username to a set of active WebSocket session IDs.
3. For each session ID, the handler translates the destination string into a unique, session-specific queue destination (e.g. `/queue/notifications-user-session-abc123`).
4. The translated message is routed to the broker, which delivers it to the target client. This allows routing private messages to specific users without exposing their session IDs to the sender.

---

## Summary
- **Spring's Messaging Channels** (`clientInbound`, `clientOutbound`, `brokerChannel`) manage frame processing threads.
- **`SimpleBroker`** operates in-memory on the JVM heap and requires configuring a `TaskScheduler` to drive keep-alive heartbeats.
- **`StompBrokerRelay`** delegates subscription tracking and message routing to an external broker (like RabbitMQ) over port `61613` (TCP).
- **Destinations** define routing rules: `/topic/*` for broadcasts, `/queue/*` for point-to-point queues, and `/user/queue/*` for private user messaging.
- **RabbitMQ Integration** maps STOMP destinations to default exchanges (`amq.topic` and `amq.direct`), enabling horizontal scaling in clustered environments.
- **Production Tuning** requires expanding inbound channel thread pools and enabling the STOMP plugin on the external message broker.
