# Module 11: User Presence and Session Tracking Systems

User presence tracking is a core feature in real-time applications like collaborative editors, team messaging boards, and multiplayer game lobbies. It requires the server to maintain a real-time list of who is currently online, what device they are using, and their active status.

This module details how to design presence tracking systems. We will cover session registries, multi-device tracking, handling network disconnect jitter without status flapping, and building a presence tracking registry using Spring Boot's session lifecycle event listeners.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Design a scalable user presence registry** that maps user principals to multiple active socket sessions.
2. **Handle network disconnect jitter** by implementing deferred status eviction timers.
3. **Trace user status transitions** (Online, Idle, Offline, Do Not Disturb) and broadcast updates.
4. **Implement Spring event listeners** to intercept connection, subscription, and disconnect events.
5. **Formulate garbage collection clean-up strategies** to prevent zombie session memory leaks in presence registries.

---

## 1. Designing a Scalable Presence System

A user presence system tracks user availability. To design this at scale, we must handle two main challenges:

### 1. Multi-Device Session Mapping
A single user (e.g. `bob`) can connect to your server from multiple devices concurrently (e.g., a phone app, a tablet, and a web browser).
- **Bad Practice**: Mapping a single username to a single session ID. If Bob logs out on his phone, the server marks him offline, terminating the browser socket.
- **Good Practice (1-to-Many Registry)**:
  - Map a single user ID (username) to a **set of active session IDs**.
  - A user is marked **Online** as long as their active session set contains $\ge 1$ entry.
  - A user is marked **Offline** only when their active session set becomes empty.

```
Multi-Device Mapping Registry
User: bob  ──►  Set of active sessions: { "session-web-10", "session-mobile-44" }
```

### 2. User Status Transitions
Track status transitions explicitly:
- **`ONLINE`**: Active connection, sending frames or heartbeats.
- **`IDLE`**: Connection active, but no user activity has occurred for a set period (e.g., 5 minutes).
- **`DND` (Do Not Disturb)**: Explicitly requested by the user.
- **`OFFLINE`**: No active connections.

---

## 2. Presence Consistency & Network Jitter

Mobile devices frequently experience transient network disconnects when passing through tunnels or switching between Wi-Fi and mobile networks.

### The "Flapping" Problem
If a device disconnects for 2 seconds and reconnects, and the server processes this instantly:
1. Bob disconnects $\rightarrow$ Server broadcasts `bob is offline` to all clients.
2. Bob reconnects $\rightarrow$ Server broadcasts `bob is online` to all clients.
3. *Result*: Client UI displays a continuous series of user status changes, creating visual distraction and wasting server CPU cycles.

### The Deferred Eviction Mitigation
To prevent status flapping due to network jitter:
- When a `SessionDisconnectEvent` occurs, do **not** mark the user offline immediately.
- Instead, place the disconnect task in a **deferred execution queue** (e.g. scheduled task executing after a 5-second delay).
- If the user reconnects within the 5-second window, cancel the deferred eviction task. The user's status remains continuously online, eliminating status flapping.

```
Deferred Eviction Timeline
Disconnect Event ──► [Wait 5 Seconds] ──► User Reconnected? ──► YES: Cancel eviction (No state change)
                                                            └──► NO : Broadcast Offline status
```

---

## 3. Heartbeats and Session Eviction

We must clean up the presence registry when sockets terminate. While standard TCP connections close gracefully, silent drops (half-open connections) require the server to evict dead links:
- If a client fails to return three consecutive heartbeats (e.g. failing to pong the server ping), the server triggers a socket ejection.
- When the container closes the socket, Spring dispatches a `SessionDisconnectEvent`. The presence registry must intercept this event to decrement the user's active device count, preventing memory leaks from zombie connections.

---

## 4. Hands-On Lab: Building a User Presence Tracker

In this lab, you will implement a complete, compilable presence tracking system in Spring Boot.

### Objective:
- Intercept WebSocket connection and disconnection events.
- Manage a thread-safe multi-device registry mapping.
- Broadcast real-time presence changes to a `/topic/presence` channel.

### Code Implementation:

#### 1. User Status Domain Model (`UserStatus.java`)
```java
package com.example.realtime.presence.model;

import java.time.Instant;
import java.util.Set;
import java.util.concurrent.CopyOnWriteArraySet;

public class UserStatus {

    public enum StatusType { ONLINE, OFFLINE, IDLE }

    private final String username;
    private StatusType status;
    private final Set<String> activeSessionIds = new CopyOnWriteArraySet<>();
    private Instant lastActiveTime;

    public UserStatus(String username) {
        this.username = username;
        this.status = StatusType.OFFLINE;
        this.lastActiveTime = Instant.now();
    }

    public synchronized void addSession(String sessionId) {
        activeSessionIds.add(sessionId);
        this.status = StatusType.ONLINE;
        this.lastActiveTime = Instant.now();
    }

    public synchronized void removeSession(String sessionId) {
        activeSessionIds.remove(sessionId);
        if (activeSessionIds.isEmpty()) {
            this.status = StatusType.OFFLINE;
        }
        this.lastActiveTime = Instant.now();
    }

    // --- Getters ---
    public String getUsername() { return username; }
    public StatusType getStatus() { return status; }
    public Set<String> getActiveSessionIds() { return activeSessionIds; }
    public Instant getLastActiveTime() { return lastActiveTime; }
    public boolean isOnline() { return this.status != StatusType.OFFLINE; }
}
```

#### 2. Presence Registry Service (`PresenceRegistry.java`)
```java
package com.example.realtime.presence.registry;

import com.example.realtime.presence.model.UserStatus;
import org.springframework.stereotype.Service;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

@Service
public class PresenceRegistry {

    // Thread-safe map storing status details per user
    private final Map<String, UserStatus> userStatusMap = new ConcurrentHashMap<>();

    public void registerSession(String username, String sessionId) {
        userStatusMap.computeIfAbsent(username, k -> new UserStatus(username))
                .addSession(sessionId);
    }

    public boolean deregisterSession(String username, String sessionId) {
        UserStatus userStatus = userStatusMap.get(username);
        if (userStatus != null) {
            userStatus.removeSession(sessionId);
            // If the user has no remaining active sessions, clean up or mark offline
            if (!userStatus.isOnline()) {
                userStatus.removeSession(sessionId);
                return true; // Indicates the user transitioned to OFFLINE
            }
        }
        return false; // User still has active sessions on other devices
    }

    public Map<String, String> getOnlineUsers() {
        return userStatusMap.entrySet().stream()
                .filter(entry -> entry.getValue().isOnline())
                .collect(Collectors.toMap(
                        Map.Entry::getKey,
                        entry -> entry.getValue().getStatus().name()
                ));
    }
}
```

#### 3. WebSocket Lifecycle Event Listener (`PresenceEventListener.java`)
```java
package com.example.realtime.presence.listener;

import com.example.realtime.presence.registry.PresenceRegistry;
import org.springframework.context.event.EventListener;
import org.springframework.messaging.simp.SimpMessageHeaderAccessor;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.messaging.*;
import java.security.Principal;
import java.util.Map;

@Component
public class PresenceEventListener {

    private final PresenceRegistry presenceRegistry;
    private final SimpMessagingTemplate messagingTemplate;

    public PresenceEventListener(PresenceRegistry presenceRegistry, SimpMessagingTemplate messagingTemplate) {
        this.presenceRegistry = presenceRegistry;
        this.messagingTemplate = messagingTemplate;
    }

    /**
     * Intercepts connection events to register new devices.
     */
    @EventListener
    public void handleSessionConnect(SessionConnectEvent event) {
        SimpMessageHeaderAccessor headers = SimpMessageHeaderAccessor.wrap(event.getMessage());
        Principal principal = headers.getUser();
        String sessionId = headers.getSessionId();

        if (principal != null && sessionId != null) {
            String username = principal.getName();
            presenceRegistry.registerSession(username, sessionId);
            
            System.out.println("[Presence Event] User connected: " + username + " (Session: " + sessionId + ")");
            
            // Broadcast the user status change
            broadcastStatusChange(username, "ONLINE");
        }
    }

    /**
     * Intercepts disconnection events to cleanup device sessions.
     */
    @EventListener
    public void handleSessionDisconnect(SessionDisconnectEvent event) {
        SimpMessageHeaderAccessor headers = SimpMessageHeaderAccessor.wrap(event.getMessage());
        Principal principal = headers.getUser();
        String sessionId = headers.getSessionId();

        if (principal != null && sessionId != null) {
            String username = principal.getName();
            
            // Deregister this specific device. Returns true if no other devices remain active.
            boolean isNowOffline = presenceRegistry.deregisterSession(username, sessionId);
            System.out.println("[Presence Event] Session disconnected: " + sessionId + " for user: " + username);

            if (isNowOffline) {
                System.out.println("[Presence Event] User is now fully OFFLINE: " + username);
                broadcastStatusChange(username, "OFFLINE");
            }
        }
    }

    /**
     * Intercepts subscriptions to push the initial online users list to the subscriber.
     */
    @EventListener
    public void handleSessionSubscribe(SessionSubscribeEvent event) {
        SimpMessageHeaderAccessor headers = SimpMessageHeaderAccessor.wrap(event.getMessage());
        String destination = headers.getDestination();
        Principal principal = headers.getUser();

        // If a client subscribes to '/topic/presence', send them the current list of online users
        if (principal != null && "/topic/presence".equals(destination)) {
            Map<String, String> onlineUsers = presenceRegistry.getOnlineUsers();
            System.out.println("[Presence Event] Pushing online user list to: " + principal.getName());
            
            messagingTemplate.convertAndSendToUser(
                    principal.getName(),
                    "/queue/presence-list",
                    onlineUsers
            );
        }
    }

    private void broadcastStatusChange(String username, String newStatus) {
        String messagePayload = "{\"username\":\"" + username + "\",\"status\":\"" + newStatus + "\"}";
        messagingTemplate.convertAndSend("/topic/presence", messagePayload);
    }
}
```

---

## 5. Common Mistakes & Debugging Scenarios

### Scenario A: Presence Registry Memory Leak
* **The Problem**: Over time, server memory grows. Thread diagnostics reveal that the `userStatusMap` in `PresenceRegistry` contains thousands of entries for offline users.
* **Why it happens**: When a user disconnects, `@EventListener` removes their session. If the user has no remaining active sessions, their status becomes `OFFLINE`. However, the code does not remove the `UserStatus` object reference from the registry map, retaining a large map of offline users in memory.
* **The Fix**: Update your deregistration logic to remove the user's map entry once they transition to `OFFLINE` (as shown in lines 23–27 of the `PresenceRegistry` code).

### Scenario B: Status Flapping on Quick Page Refreshes
* **The Problem**: When a user refreshes their browser page, other users receive two quick status updates: `OFFLINE` followed immediately by `ONLINE`.
* **Why it happens**: Refreshing a page closes the active WebSocket session and opens a new one. The server processes the disconnect event first, broadcasting `OFFLINE` because no other devices are active, and then processes the new connection event, broadcasting `ONLINE`.
* **The Fix**: Implement a deferred eviction timer (as described in Section 2) using a task scheduler. When `handleSessionDisconnect` runs, schedule a status broadcast update after a 5-second delay. If a new connection event for the same user arrives before the task executes, cancel the scheduled task.

---

## 6. Technical Interview Questions

### Question 1: Multi-Device Status Management
*How does a presence registry manage status updates when a user is logged into multiple devices concurrently?*

**Answer**:
A robust presence system must map a single username to a set of active WebSocket session IDs.
- When a new session connects, the session ID is added to the user's set, and the user's status transitions to `ONLINE`. If the set size was previously 0, the server broadcasts an `ONLINE` status update.
- When a session disconnects, the specific session ID is removed from the user's set. 
- The user is only marked `OFFLINE` when their active session set becomes empty. This ensures that logging out on one device does not mark the user offline on other active devices.

---

### Question 2: Spring WebSocket Event Listeners
*What is the purpose of Spring's `SessionSubscribeEvent`? How can you use it to push an initial state to a client?*

**Answer**:
Spring dispatches a `SessionSubscribeEvent` when a client sends a STOMP `SUBSCRIBE` frame. 

By registering an `@EventListener` for this event, the server can intercept the subscription request. If the client subscribes to a specific destination (e.g. `/topic/presence`), the server can query the presence registry and return the current list of online users directly to the subscriber's private user queue (using `SimpMessagingTemplate.convertAndSendToUser`). This avoids forcing the client to wait for a state broadcast event to update its UI.

---

## Summary
- **User Presence Tracking** requires mapping a user's principal to a set of active sessions to support multiple concurrent devices.
- **Spring Event Listeners** (`SessionConnectEvent`, `SessionDisconnectEvent`, `SessionSubscribeEvent`) allow intercepting WebSocket lifecycle events to update the presence registry.
- **Deferred Eviction** prevents status flapping (repeated online/offline updates) caused by network jitter or page refreshes.
- **Memory Management** requires removing user references from the presence registry once their active session count drops to zero.
- **Initial State Delivery** is achieved by intercepting subscription events and pushing the current state directly to the subscribing client.
