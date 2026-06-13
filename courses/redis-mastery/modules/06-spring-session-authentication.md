# Module 06: Spring Session, Authentication, and Token Management

## 1. What Problem This Module Solves

HTTP is a stateless protocol. To authenticate users across requests, applications must track user session state. 
*   **Session Pinning**: Storing sessions in an application instance's memory forces the load balancer to route requests from a specific user to that same instance (sticky sessions). If that instance crashes or restarts, all active user sessions are lost.
*   **JWT Revocation**: JWT tokens are stateless and self-contained. Once signed, they cannot be invalidated before they expire. If a user logs out or their token is compromised, you need a way to revoke the token immediately.

This module details how to implement **Distributed Sessions** and **JWT Blacklisting** using Redis.

---

## 2. Why Redis is Used Instead of Alternatives

*   **Over Relational DB Session Tables**: Session operations (reads/writes on every API call) are read-intensive. Relational database storage engines suffer from I/O write amplification and transaction locks under high concurrency. Redis, running in memory, resolves session operations in sub-milliseconds.
*   **Over local caches**: Redis centralizes session storage, allowing the load balancer to distribute traffic evenly across any Spring node in the cluster without session loss.

---

## 3. Spring Session Redis Architecture

Spring Session intercepts incoming servlet requests using a filter and replaces the standard `HttpSession` implementation with a wrapper backed by Redis.

```
[Request Lifecycle with Spring Session]
Client ───► Filter (Intercepts Session ID) ───► Queries Redis (Session Hash)
                                                      │
                                                      ▼
Client ◄─── REST Response ◄─── Controller ◄─── Session context injected
```

### 3.1 Redis Session Key Structure

For each session, Spring Session creates three keys:
1.  `spring:session:sessions:<session-id>`: A Hash containing session attributes (creation time, last accessed, principal metadata).
2.  `spring:session:sessions:expires:<session-id>`: A String key used to track the session expiration.
3.  `spring:session:expirations:<expiration-timestamp>`: A Set containing session IDs expiring at that specific timestamp, used for bulk cleanups.

---

## 4. JWT Blacklisting Strategy

To revoke a stateless JWT on logout, use the **JWT Blacklist Pattern**:
1.  When a user logs out, extract the JWT's signature hash.
2.  Write the hash to Redis with a TTL set to the token's remaining lifetime.
3.  On every authenticated request, check if the token hash exists in the Redis blacklist. If yes, reject the request.

---

## 5. Hands-on Exercises

1.  Inspect the hash keys created by Spring Session in Redis using `HGETALL` and describe the fields.
2.  Write a script to simulate a user session timeout and verify that the session keys are cleaned up.

---

## 6. Mini-Project: JWT Blacklist Handler

**Scenario**: You are building an authentication gateway. You must implement a JWT blacklisting system that revokes tokens on user logout and validates active tokens.

### 1. Blacklist Service Implementation (`auth/JwtBlacklistService.java`)
```java
package com.example.redis.auth;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import java.time.Duration;

@Service
public class JwtBlacklistService {

    private final StringRedisTemplate redisTemplate;
    private static final String BLACKLIST_PREFIX = "jwt:blacklist:";

    public JwtBlacklistService(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    // Revoke token by saving it to blacklist with TTL matching its remaining lifetime
    public void revokeToken(String tokenSignature, long remainingSeconds) {
        String key = BLACKLIST_PREFIX + tokenSignature;
        if (remainingSeconds > 0) {
            redisTemplate.opsForValue().set(key, "revoked", Duration.ofSeconds(remainingSeconds));
        }
    }

    // Check if token is blacklisted
    public boolean isBlacklisted(String tokenSignature) {
        String key = BLACKLIST_PREFIX + tokenSignature;
        return Boolean.TRUE.equals(redisTemplate.hasKey(key));
    }
}
```

### 2. Spring Security Interceptor (`auth/JwtInterceptor.java`)
```java
package com.example.redis.auth;

import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

@Component
public class JwtInterceptor implements HandlerInterceptor {

    private final JwtBlacklistService blacklistService;

    public JwtInterceptor(JwtBlacklistService blacklistService) {
        this.blacklistService = blacklistService;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        String authHeader = request.getHeader("Authorization");
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            return true; // Delegate authentication check to downstream filter
        }

        String token = authHeader.substring(7);
        String signature = extractSignature(token); // Helper extraction method

        // Validate token against Redis blacklist
        if (blacklistService.isBlacklisted(signature)) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.getWriter().write("Token has been revoked on logout");
            return false; // Halt request processing
        }

        return true;
    }

    private String extractSignature(String token) {
        String[] parts = token.split("\\.");
        if (parts.length == 3) {
            return parts[2]; // Return the signature portion of the JWT
        }
        return token;
    }
}
```

---

## 7. Interview Questions

### Q1: Why does Spring Session create three separate keys in Redis for a single session?
**Answer**: Spring Session manages session expirations carefully. Redis keyspace expiration notifications are fire-and-forget: if the Spring application is restarting when a session expires, it misses the event, leading to stale session cleanups.
To prevent this, Spring uses:
1.  `spring:session:sessions:<session-id>`: The primary data hash.
2.  `spring:session:sessions:expires:<session-id>`: A secondary string key with the actual TTL.
3.  `spring:session:expirations:<expiration-timestamp>`: A set containing session IDs mapped to their expiration minute.
The application polls the expirations sets periodically to clean up stale sessions that missed keyspace events, ensuring cleanup reliability.

### Q2: What is the risk of using JWT blacklisting at scale? How do you optimize memory consumption?
**Answer**:
*   *Risk*: If your application has millions of active users, storing revoked JWTs can consume significant memory.
*   *Optimization*: Store only the token's unique signature or its `jti` claim rather than the entire JWT string. Always set a TTL matching the token's remaining lifetime so that revoked tokens are deleted automatically once they expire naturally.

### Q3: How do you handle session migration when upgrading Spring applications with changes to session class models?
**Answer**: By default, Java serializer mappings throw `InvalidClassException` when class version definitions mismatch.
To prevent this:
1.  Configure Spring Session to use a JSON serializer (`Jackson2JsonRedisSerializer`).
2.  Define a stable `serialVersionUID` on session classes to support backward compatibility.
3.  Add field fallback mappings to avoid deserialization failures on missing fields.
