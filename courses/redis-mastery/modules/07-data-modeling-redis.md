# Module 07: Advanced Data Modeling, Leaderboards, and Time-Series

## 1. What Problem This Module Solves

Redis is a key-value store, not a relational database. It does not support native tables, foreign keys, or SQL index queries out-of-the-box. 

To model real-world domains (such as relationships, secondary indexes, time-series logs, or global leaderboards), you must design schemas manually using Redis's primitive data structures. This module covers advanced data modeling techniques and patterns.

---

## 2. Why Redis is Used Instead of Alternatives

*   **Over Relational DB Indexes (for leaderboards)**: Fetching top-ranked users in a relational database requires running `ORDER BY score DESC LIMIT N` queries. As the dataset grows, sorting millions of rows exhausts disk I/O and locks tables. Redis Sorted Sets (ZSET) maintain elements in a pre-sorted SkipList structure, resolving rank operations in logarithmic $O(\log N + M)$ time.

---

## 3. Modeling Relationships and Secondary Indexes

### 3.1 Modeling Relationships
*   **One-to-Many (1:N)**: Represented using a **Set** or **Sorted Set** mapping parent IDs to child IDs.
    *   *Example*: `user:1001:addresses` $\rightarrow$ `{"addr:50", "addr:51"}`.
*   **Many-to-Many (N:M)**: Represented using dual Sets mapping references in both directions.
    *   *Example*:
        *   `user:1001:groups` $\rightarrow$ `{"group:abc", "group:xyz"}`
        *   `group:abc:users` $\rightarrow$ `{"user:1001", "user:1002"}`

### 3.2 Secondary Indexing Pattern
To search for users by their email address rather than their primary ID:
1.  Save the user profile: `SET user:1001 "{\"name\":\"John\",\"email\":\"john@example.com\"}"`.
2.  Write a secondary lookup index String: `SET user:index:email:john@example.com "1001"`.
3.  On lookup, query the index key first, then fetch the primary profile.

---

## 4. Leaderboards using Sorted Sets (ZSET)

A Sorted Set is a collection of unique string members, each mapped to a floating-point score. Redis maintains elements in a **SkipList** and **Hashtable** structure.

```
[Sorted Set SkipList Representation]
Level 3: Head ───────────────────────────────► [Score: 75.0] ────────────────► Tail
Level 2: Head ───────────────► [Score: 40.0] ───► [Score: 75.0] ───► [Score: 90.0] ─► Tail
Level 1: Head ──► [Score: 25.0] ─► [Score: 40.0] ───► [Score: 75.0] ───► [Score: 90.0] ─► Tail
```

*   **ZSET SkipList**: The SkipList provides $O(\log N)$ search, insertion, and deletion complexity, allowing real-time ranking modifications under high concurrent writes.

### 4.1 Resolving Score Tie-Breakers
By default, if two users have the same score, Redis sorts them lexicographically by their member names. In a competitive leaderboard, you want users who achieved the score first to rank higher.
*   **The Tie-Breaker Math**: Store the score as a composite double float:
    
    $$\text{Composite Score} = \text{User Score} + \left( 1.0 - \frac{\text{Timestamp}}{\text{Future Epoch Timestamp}} \right)$$

This offset ensures that earlier timestamps result in slightly higher composite scores, acting as an automatic tie-breaker.

---

## 5. Hands-on Exercises

1.  Model an N-to-N relationship between authors and books using Redis Sets.
2.  Write a script to rank 1,000 mock players using ZSET and fetch the top 10 rankings.

---

## 6. Mini-Project: Real-Time Leaderboard with Tie-Breaker

**Scenario**: You are building a gaming leaderboard. When a player scores points, you must update their score atomically, applying a chronological tie-breaker. You will implement this using a Spring service.

### 1. Leaderboard Service Implementation (`leaderboard/LeaderboardService.java`)
```java
package com.example.redis.leaderboard;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ZSetOperations;
import org.springframework.stereotype.Service;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class LeaderboardService {

    private final StringRedisTemplate redisTemplate;
    private static final String LEADERBOARD_KEY = "game:leaderboard";
    // Fixed future epoch: 2050-01-01 00:00:00 UTC (2524608000 seconds)
    private static final long FUTURE_EPOCH = 2524608000L;

    public LeaderboardService(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    // Submit score applying chronological tie-breaker
    public void submitScore(String playerId, int rawScore) {
        long currentTimestampSeconds = System.currentTimeMillis() / 1000;
        
        // Calculate decimal offset: earlier timestamp gets higher fraction
        double tieBreaker = 1.0 - ((double) currentTimestampSeconds / FUTURE_EPOCH);
        double compositeScore = rawScore + tieBreaker;

        redisTemplate.opsForZSet().add(LEADERBOARD_KEY, playerId, compositeScore);
    }

    // Get top N players
    public Set<PlayerRank> getTopPlayers(int limit) {
        Set<ZSetOperations.TypedTuple<String>> typedTuples = 
            redisTemplate.opsForZSet().reverseRangeWithScores(LEADERBOARD_KEY, 0, limit - 1);

        if (typedTuples == null) {
            return Set.of();
        }

        return typedTuples.stream()
            .map(tuple -> new PlayerRank(
                tuple.getValue(),
                (int) Math.floor(tuple.getScore()) // Extract raw integer score
            ))
            .collect(Collectors.toSet());
    }

    public static class PlayerRank {
        public String playerId;
        public int score;

        public PlayerRank(String playerId, int score) {
            this.playerId = playerId;
            this.score = score;
        }
    }
}
```

---

## 7. Interview Questions

### Q1: What is the underlying data structure of a Redis Sorted Set (ZSET)? Why is it chosen over a binary tree?
**Answer**: A Sorted Set is backed by a **Hashtable** (providing $O(1)$ lookup for element scores) and a **SkipList** (providing logarithmic search and insertion for element ordering).
A SkipList is chosen over a binary search tree (like a Red-Black tree) because it is simpler to implement, performs efficiently under concurrent modifications, and supports range queries ($O(\log N)$ to find the start node, followed by sequential link traversals) without requiring complex tree rotations.

### Q2: How does secondary indexing in Redis introduce write amplification? How do you manage it?
**Answer**: Because Redis does not manage indexes automatically, the application must write index keys manually whenever an entity is saved, updated, or deleted. 
This is **write amplification**: saving a single user profile requires executing multiple writes to write to the index keys. If an entity is updated, old indexes must be deleted to prevent stale references, increasing network overhead. Manage this by wrapping indexing logic in Lua scripts to run updates atomically.

### Q3: Why is storing geospatial coordinates in Redis memory-efficient? How is the GEO structure mapped under the hood?
**Answer**: Redis maps geospatial coordinates (`GEOPOS`) to a single **Sorted Set** key. It converts latitude and longitude coordinates into a 52-bit integer representation using **Geohash encoding**. 
This encoding maps spatial coordinates to a 1D line, allowing Redis to evaluate distance and area searches using standard Sorted Set range scans, which is highly memory-efficient.
