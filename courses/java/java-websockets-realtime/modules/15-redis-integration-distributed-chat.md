# Module 15: Redis Integration & Distributed Chat

In the previous module, we analyzed the challenges of horizontal scaling. When client sockets are pinned to isolated server instances, local in-memory broadcasts fail to reach all users. To solve this, we must build a cross-instance communication layer.

This module covers **Redis Pub/Sub** integration. We will analyze the Redis publish-subscribe model, configure Spring Data Redis templates and listener containers, map serialization serializers, trace cross-instance message flows, and implement a complete, compilable clustered chat server.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Explain the memory-free pattern** of Redis Pub/Sub channels and trace how messages are distributed.
2. **Configure Spring Data Redis components** (`StringRedisTemplate`, `RedisMessageListenerContainer`, `MessageListenerAdapter`) in Spring Boot.
3. **Trace the step-by-step lifecycle** of a message as it traverses client sockets, application nodes, and Redis message channels.
4. **Serialize and deserialize JSON payloads** for distributed message transmission.
5. **Implement a clustered WebSocket chat server** that synchronizes broadcasts across multiple nodes.

---

## 1. Redis Pub/Sub Architecture

Redis provides a lightweight, high-performance publish-subscribe implementation:
- **Memory-Free Channels**: Unlike traditional message brokers (such as RabbitMQ or Kafka) that store messages in queues on disk or memory until consumers acknowledge them, Redis Pub/Sub is **fire-and-forget**.
- **The Mechanic**: When a message is published to a channel, Redis instantly pushes it to all currently subscribed TCP connection sockets. If no clients are subscribed, the message is discarded immediately. This makes it extremely fast and lightweight, with near-zero memory footprint on the Redis server.
- **WebSocket Fit**: Since our application nodes keep active WebSocket connections open, they are always listening. If a node drops, the client reconnects to another active node, which establishes a new subscription to Redis. Redis Pub/Sub is the industry standard for real-time WebSocket cross-instance routing.

---

## 2. Spring Data Redis Core API

To integrate Redis Pub/Sub in a Spring Boot application, we configure three core components:

### 1. `StringRedisTemplate`
- **Role**: Used to publish messages (text strings) to a Redis channel.
- **Usage**: `redisTemplate.convertAndSend("channel-name", serializedMessageString)`.

### 2. `RedisMessageListenerContainer`
- **Role**: A container that manages the background connection listener thread pool. It monitors Redis channels for incoming messages and delegates them to registered message listeners.
- **Tuning**: In production, configure this container with a custom `TaskExecutor` to prevent thread exhaustion under high message volumes.

### 3. `MessageListenerAdapter`
- **Role**: Wraps an application bean, mapping incoming Redis channel messages to a specific method signature for processing.

---

## 3. Cross-Instance Message Delivery Flow

When User A broadcasts a message to User B across a clustered environment:

```
User A (Session 1) ──► [ Node 1 ] ──► (Publish) ──► [ Redis Channel ] ──► [ Node 2 ] ──► User B (Session 2)
```

1. **Client Ingest**: User A (connected to Node 1) sends a WebSocket frame.
2. **Local Handler**: Node 1's `TextWebSocketHandler` intercepts the message.
3. **Redis Publish**: Node 1 serializes the message and publishes it to the Redis channel `chat-broadcast` using `StringRedisTemplate`.
4. **Redis Distribution**: Redis receives the message and pushes it instantly to all subscribed application nodes (Node 1 and Node 2).
5. **Redis Listeners**: Node 2's `RedisMessageListenerContainer` reads the message from the Redis socket.
6. **Local Broadcast**: Node 2's subscriber bean deserializes the message, identifies local sessions subscribed to that room, and writes the frame to User B's socket. Node 1 also receives the message but skips routing it to User A (the sender).

---

## 4. Hands-On Mini Project: Distributed Chat Server

We will implement a complete, compilable Spring Boot distributed chat server.

The project contains:
- **`RedisConfig.java`**: Configures the connection factory, redis template, and registers `RedisMessageListenerContainer`.
- **`ChatEvent.java`**: DTO payload representing the chat event. Includes serialization helper methods.
- **`RedisMessagePublisher.java`**: Service publishing chat DTOs to the Redis channel.
- **`RedisMessageSubscriber.java`**: Intercepts Redis events, deserializes them, and routes them to local active WebSocket sessions.
- **`ClusteredChatHandler.java`**: Standard Spring WebSocket handler mapping local connections.

### Complete Implementation:

#### 1. Redis Configuration (`RedisConfig.java`)

```java
package com.example.realtime.redis.config;

import com.example.realtime.redis.subscriber.RedisMessageSubscriber;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.data.redis.listener.adapter.MessageListenerAdapter;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

@Configuration
public class RedisConfig {

    private static final String REDIS_CHANNEL_NAME = "websocket-chat-channel";

    @Bean
    public RedisConnectionFactory redisConnectionFactory() {
        // Initialize standard Lettuce connection connection factory (default localhost:6379)
        return new LettuceConnectionFactory();
    }

    @Bean
    public StringRedisTemplate stringRedisTemplate(RedisConnectionFactory connectionFactory) {
        return new StringRedisTemplate(connectionFactory);
    }

    @Bean
    public ChannelTopic topic() {
        return new ChannelTopic(REDIS_CHANNEL_NAME);
    }

    @Bean
    public MessageListenerAdapter messageListener(RedisMessageSubscriber subscriber) {
        // Map incoming Redis messages to the 'onMessageReceived' method of our subscriber bean
        return new MessageListenerAdapter(subscriber, "onMessageReceived");
    }

    @Bean
    public RedisMessageListenerContainer redisContainer(RedisConnectionFactory connectionFactory,
                                                        MessageListenerAdapter listenerAdapter,
                                                        ChannelTopic topic) {
        RedisMessageListenerContainer container = new RedisMessageListenerContainer();
        container.setConnectionFactory(connectionFactory);
        container.addMessageListener(listenerAdapter, topic);
        
        // Define custom task executor to prevent thread pool starvation
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(20);
        executor.setQueueCapacity(50);
        executor.setThreadNamePrefix("redis-listener-");
        executor.initialize();
        container.setTaskExecutor(executor);

        return container;
    }
}
```

#### 2. Chat Event DTO (`ChatEvent.java`)

```java
package com.example.realtime.redis.model;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.time.Instant;

public class ChatEvent {

    private String senderSessionId;
    private String username;
    private String room;
    private String content;
    private Instant timestamp;

    private static final ObjectMapper objectMapper = new ObjectMapper();

    public ChatEvent() {
        this.timestamp = Instant.now();
    }

    public ChatEvent(String senderSessionId, String username, String room, String content) {
        this.senderSessionId = senderSessionId;
        this.username = username;
        this.room = room;
        this.content = content;
        this.timestamp = Instant.now();
    }

    // --- JSON Serialization Helpers ---
    public String toJson() throws IOException {
        return objectMapper.writeValueAsString(this);
    }

    public static ChatEvent fromJson(String json) throws IOException {
        return objectMapper.readValue(json, ChatEvent.class);
    }

    // --- Getters and Setters ---
    public String getSenderSessionId() { return senderSessionId; }
    public void setSenderSessionId(String senderSessionId) { this.senderSessionId = senderSessionId; }

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public String getRoom() { return room; }
    public void setRoom(String room) { this.room = room; }

    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }

    public Instant getTimestamp() { return timestamp; }
    public void setTimestamp(Instant timestamp) { this.timestamp = timestamp; }
}
```

#### 3. Redis Publisher Service (`RedisMessagePublisher.java`)

```java
package com.example.realtime.redis.publisher;

import com.example.realtime.redis.model.ChatEvent;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.stereotype.Service;
import java.io.IOException;

@Service
public class RedisMessagePublisher {

    private final StringRedisTemplate redisTemplate;
    private final ChannelTopic topic;

    public RedisMessagePublisher(StringRedisTemplate redisTemplate, ChannelTopic topic) {
        this.redisTemplate = redisTemplate;
        this.topic = topic;
    }

    /**
     * Publishes a serialized chat event to the Redis topic.
     */
    public void publish(ChatEvent event) {
        try {
            String jsonPayload = event.toJson();
            System.out.println("[Redis Publisher] Publishing event: " + jsonPayload);
            redisTemplate.convertAndSend(topic.getTopic(), jsonPayload);
        } catch (IOException e) {
            System.err.println("Failed to serialize ChatEvent: " + e.getMessage());
        }
    }
}
```

#### 4. Clustered Chat WebSocket Handler (`ClusteredChatHandler.java`)

```java
package com.example.realtime.redis.handler;

import com.example.realtime.redis.model.ChatEvent;
import com.example.realtime.redis.publisher.RedisMessagePublisher;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.*;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import java.io.IOException;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArraySet;

@Component
public class ClusteredChatHandler extends TextWebSocketHandler {

    // Registry of local active WebSocket sessions (keyed by room name)
    private static final Map<String, Set<WebSocketSession>> localRoomRegistry = new ConcurrentHashMap<>();
    
    // Reverse map to track room name per local session ID
    private static final Map<String, String> sessionRoomMap = new ConcurrentHashMap<>();

    private final RedisMessagePublisher redisPublisher;

    public ClusteredChatHandler(RedisMessagePublisher redisPublisher) {
        this.redisPublisher = redisPublisher;
    }

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        System.out.println("[WebSocket Handler] Local session established: " + session.getId());
        
        // Simulating joining a room named "general" by default
        String room = "general";
        localRoomRegistry.computeIfAbsent(room, k -> new CopyOnWriteArraySet<>()).add(session);
        sessionRoomMap.put(session.getId(), room);
        
        session.sendMessage(new TextMessage("Connected to clustered node. Room: " + room));
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        String payload = message.getPayload().trim();
        String room = sessionRoomMap.get(session.getId());
        
        if (room != null && !payload.isEmpty()) {
            // Build the distributed chat event
            ChatEvent event = new ChatEvent(
                session.getId(),          // Sender session ID (used to skip echo locally)
                "User-" + session.getId().substring(0, 4), // Mock username
                room,
                payload
            );
            
            // Publish the event to Redis, which will distribute it to all nodes in the cluster
            redisPublisher.publish(event);
        }
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) throws Exception {
        System.out.println("[WebSocket Handler] Local session closed: " + session.getId());
        String room = sessionRoomMap.remove(session.getId());
        if (room != null) {
            Set<WebSocketSession> sessions = localRoomRegistry.get(room);
            if (sessions != null) {
                sessions.remove(session);
            }
        }
    }

    /**
     * Called by the Redis Subscriber to broadcast events to local sessions.
     */
    public void broadcastLocal(ChatEvent event) {
        Set<WebSocketSession> sessions = localRoomRegistry.get(event.getRoom());
        if (sessions == null || sessions.isEmpty()) {
            return;
        }

        String broadcastPayload = "{\"sender\":\"" + event.getUsername() + "\",\"content\":\"" + event.getContent() + "\"}";
        TextMessage textMessage = new TextMessage(broadcastPayload);

        for (WebSocketSession session : sessions) {
            // Skip sending the message back to the originator local session
            if (session.getId().equals(event.getSenderSessionId())) {
                continue;
            }

            if (!session.isOpen()) {
                continue;
            }

            // Lock session writes to prevent concurrent execution conflicts
            synchronized (session) {
                try {
                    session.sendMessage(textMessage);
                } catch (IOException e) {
                    System.err.println("Broadcast failed on session " + session.getId());
                }
            }
        }
    }
}
```

#### 5. Redis Message Subscriber Service (`RedisMessageSubscriber.java`)

```java
package com.example.realtime.redis.subscriber;

import com.example.realtime.redis.handler.ClusteredChatHandler;
import com.example.realtime.redis.model.ChatEvent;
import org.springframework.stereotype.Service;
import java.io.IOException;

@Service
public class RedisMessageSubscriber {

    private final ClusteredChatHandler chatHandler;

    public RedisMessageSubscriber(ClusteredChatHandler chatHandler) {
        this.chatHandler = chatHandler;
    }

    /**
     * Triggered by the RedisMessageListenerContainer when a new message is published.
     */
    public void onMessageReceived(String message) {
        System.out.println("[Redis Subscriber] Message received from Redis channel: " + message);
        
        try {
            // 1. Deserialize the message payload
            ChatEvent event = ChatEvent.fromJson(message);
            
            // 2. Delegate to the WebSocket handler to broadcast to locally connected sessions
            chatHandler.broadcastLocal(event);
        } catch (IOException e) {
            System.err.println("Failed to deserialize incoming Redis payload: " + e.getMessage());
        }
    }
}
```

#### 6. Spring Boot Application Bootstrapper

```java
package com.example.realtime.redis;

import com.example.realtime.redis.handler.ClusteredChatHandler;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.*;

@SpringBootApplication
public class ClusteredChatApplication {
    public static void main(String[] args) {
        SpringApplication.run(ClusteredChatApplication.class, args);
    }
}

// --- WebSocket Handler Configuration ---
@Configuration
@EnableWebSocket
class WebSocketConfig implements WebSocketConfigurer {

    private final ClusteredChatHandler chatHandler;

    public WebSocketConfig(ClusteredChatHandler chatHandler) {
        this.chatHandler = chatHandler;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        // Register handler on /ws/clustered-chat
        registry.addHandler(chatHandler, "/ws/clustered-chat")
                .setAllowedOrigins("*");
    }
}
```

---

## 5. Common Mistakes & Debugging Scenarios

### Scenario A: Infinite Broadcast Feedback Loop
* **The Problem**: When Client A sends a message, the application crashes or freezes, and the logs show the message is repeated infinitely on the console.
* **Why it happens**: When a local WebSocket message arrives, the handler publishes it to Redis. Every application server node (including the sender node) receives the event from Redis. If the sender node's subscriber method forwards the message to the local handler, and the handler republishes it to Redis, an infinite feedback loop is created.
* **The Fix**: Track the originating session ID or server node in the DTO payload. In the local broadcast method, skip routing the message back to the session matching the `senderSessionId` (as shown in lines 84–87 of the `ClusteredChatHandler` code).

### Scenario B: Deserialization Failure Drops the Stream
* **The Problem**: Distributed messaging works fine for simple text, but stops working as soon as a client sends a message containing special characters or binary payloads. The server logs throw JSON parsing exceptions.
* **Why it happens**: The `RedisMessageListenerContainer` does not swallow exceptions by default. If a message fails to deserialize, it throws an exception, blocking the background listener thread and stopping the processing of subsequent messages.
* **The Fix**: Wrap your deserialization logic in a `try-catch` block (as shown in lines 23–32 of the `RedisMessageSubscriber` code), logging failures and allowing the thread to continue processing.

---

## 6. Technical Interview Questions

### Question 1: Redis Pub/Sub vs. RabbitMQ
*Why is Redis Pub/Sub preferred over RabbitMQ queues for synchronizing live broadcasts across clustered WebSocket instances?*

**Answer**:
Redis Pub/Sub operates on a fire-and-forget, memory-free pattern. When a message is published to a channel, Redis pushes it instantly to all active socket connections and discards it. It does not store messages or track consumer acknowledgments. This aligns perfectly with live WebSocket broadcasts, where if a server node drops, its connected users are disconnected and must reconnect to a new node, making historical message buffering on the broker redundant. 

RabbitMQ, by contrast, stores messages in queues and tracks consumer acknowledgments. This introduces database write and index management overhead, which is unnecessary for transient, real-time broadcasts and limits scaling throughput.

---

### Question 2: Thread Pool Starvation in Redis Container
*What is the threat of not configuring a custom TaskExecutor in Spring's `RedisMessageListenerContainer`?*

**Answer**:
By default, `RedisMessageListenerContainer` utilizes a simple, single-threaded executor to read incoming messages from the Redis connection socket. 

If your subscriber bean executes blocking operations (such as persisting messages to a database or writing to slow client sockets), the listener thread blocks. This stops the container from reading subsequent messages from the Redis socket, causing message delivery lag across your entire cluster. 

Registering a custom, multi-threaded `TaskExecutor` (as shown in lines 43–52 of the `RedisConfig` code) ensures that incoming messages are processed concurrently, protecting connection throughput.

---

## Summary
- **Clustered WebSocket Nodes** are isolated by default, requiring a shared pub/sub layer to route messages across instances.
- **Redis Pub/Sub** is a memory-free, fire-and-forget channel system that provides low-latency, high-throughput message routing.
- **`RedisMessageListenerContainer`** monitors Redis socket connections and dispatches events to registered listener beans using thread-pool task executors.
- **Deduplication** (avoiding feedback loops) is achieved by tracking the originating session ID in the payload and skipping local echo loops.
- **Jackson ObjectMappers** handle JSON serialization and deserialization, converting DTO payloads to transportable strings.
