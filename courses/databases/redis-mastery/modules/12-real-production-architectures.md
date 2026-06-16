# Module 12: Real Production Case Studies

This module details 9 real-world architectural case studies. Each case study covers the design motivation, Redis structure selections, scaling challenges, failure scenarios, and alternative solutions.

---

## 1. E-Commerce Platform Shopping Cart

### 1.1 Architecture & Redis Usage
```
[User Session] ───► [API Gateway] ───► [Cart Service] ───► [Redis Cart Cache (Hash)]
                                                                │ (Cart Checkout)
                                                                ▼
                                                          [Checkout DB (Postgres)]
```
*   **Redis Key**: `cart:v1:<user_id>`
*   **Data Type**: **Hash**. Field name is the product item SKU; value is a JSON string containing quantity and pricing snapshots.
*   **TTL**: 14 Days.

### 1.2 Architectural Rationale & Alternatives
*   **Why Redis**: Carts require high-frequency writes (adding, updating quantities, removing items) during user browsing. Writing directly to a relational database creates write amplification and lock contention. Redis Hashes support in-memory modifications with sub-millisecond latency.
*   **Alternatives**: 
    1.  *SQL database table*: Slow writes, table locks, and requires manual batch cleanups for abandoned carts.
    2.  *Client-side Cookies*: Removes server memory overhead, but limits payload size (4KB cookie limit) and poses security risks if pricing is manipulated.

### 1.3 Scaling Challenges & Failures
*   **Eviction Risk**: If the Redis eviction policy is set to `allkeys-lru` and memory saturates, active shopping carts can be evicted, degrading user experience.
    *   *Mitigation*: Use a dedicated Redis instance for carts with the `noeviction` policy, and configure alerts for memory thresholds.
*   **Data Loss**: If a master crashes before replication, active carts can be lost. Since carts are transient, this data loss is usually acceptable.

---

## 2. Social Media Live Activity Feed

### 2.1 Architecture & Redis Usage
```
[Post Service] ───(Fan-out Writes)───► [Redis User Feed (ZSET)] ◄─── [Feed Service]
                                                                          ▲
                                                                          │
                                                                   [Client Read]
```
*   **Redis Key**: `feed:user:v1:<user_id>`
*   **Data Type**: **Sorted Set (ZSET)**. Score is the post creation timestamp; value is the post ID.
*   **TTL**: 7 Days.

### 2.2 Architectural Rationale & Alternatives
*   **Why Redis**: Fetching a user's timeline requires merging posts from all followed users chronologically. Running SQL join queries across `followers` and `posts` tables scales poorly. Redis Sorted Sets maintain posts in a pre-sorted SkipList structure, allowing range scans in logarithmic time.
*   **Alternatives**:
    1.  *SQL Joins*: Scales poorly under high volume.
    2.  *NoSQL Document Store (MongoDB)*: Slow sorting under high concurrency.

### 2.3 Scaling Challenges & Failures
*   **Write Amplification (Celebrity Problem)**: When a user with 50 million followers posts, writing to 50 million user feed keys in Redis saturates the cluster.
    *   *Mitigation*: Implement a **Hybrid Push/Pull Model**. Push posts to active user feed keys in Redis for standard users. For popular users, keep posts in a separate cache and merge them client-side during read requests.

---

## 3. High-Scale URL Shortener

### 3.1 Architecture & Redis Usage
```
[Short Link GET] ───► [Redirect Service] ───► [Redis Short Index (String)]
                                                    │ (Cache Miss)
                                                    ▼
                                            [Relational DB (MySQL)]
```
*   **Redis Key**: `url:v1:<short_code>`
*   **Data Type**: **String**. Value is the target long URL string.
*   **TTL**: None (Persistent cache).

### 3.2 Architectural Rationale & Alternatives
*   **Why Redis**: Redirection services must handle millions of redirect requests with minimal latency. Redis Strings resolve lookups in sub-milliseconds.
*   **Alternatives**:
    1.  *SQL Index Lookup*: High disk read I/O under load.

### 3.3 Scaling Challenges & Failures
*   **Cache Miss Storm**: If a popular link is evicted, concurrent misses can overload the database.
    *   *Mitigation*: Use a cache-aside pattern with mutual exclusion locking to ensure only a single thread queries the database on a miss.

---

## 4. API Gateway Rate Limiter

### 4.1 Architecture & Redis Usage
```
[Incoming Request] ───► [API Gateway] ───► [Lua Rate Limit Check] ───► [Allow / Deny]
                                                   │
                                                   ▼ (Redis ZSET)
                                            [Timestamp Log]
```
*   **Redis Key**: `ratelimit:<user_id>`
*   **Data Type**: **Sorted Set (ZSET)**. Score and member are both request timestamps in milliseconds.
*   **TTL**: Capped to sliding window duration (e.g. 60 seconds).

### 4.2 Architectural Rationale & Alternatives
*   **Why Redis**: Rate limiters must run checks on every API call. Implementing this logic in Redis using Lua scripts ensures atomic checks and increments without lock contention.
*   **Alternatives**:
    1.  *Local Memory Limiters*: Lack distributed synchronization, allowing users to bypass limits by targeting different gateway instances.

### 4.3 Scaling Challenges & Failures
*   **Cluster Sharding Bottlenecks**: High traffic for a single user (e.g. DDOS target) saturates the CPU of the specific Redis shard owning that key.
    *   *Mitigation*: Implement local L1 rate limiting in the gateway memory to block high-frequency attacks early, before hitting Redis.

---

## 5. Notification System Message Queue

### 5.1 Architecture & Redis Usage
```
[Notify Service] ───(XADD)───► [Redis Stream (Orders)] ◄───(Consumer Group)─── [Workers]
                                                                                   │
                                                                                   ▼
                                                                           [SMS / Email API]
```
*   **Redis Key**: `notifications:stream:v1`
*   **Data Type**: **Stream**. Payload contains event type, target user, and message details.
*   **TTL**: Capped stream size (`MAXLEN 100000`).

### 5.2 Architectural Rationale & Alternatives
*   **Why Redis**: Exposing notifications requires a fast, reliable queuing layer. Redis Streams provide consumer groups, message acknowledgement, and unacknowledged backlog recovery.
*   **Alternatives**:
    1.  *RabbitMQ/Kafka*: High infrastructure overhead for simple notification queues.

### 5.3 Scaling Challenges & Failures
*   **Memory Saturation**: If consumer workers fail, the queue will grow, consuming RAM.
    *   *Mitigation*: Enforce capped streams using `MAXLEN` and set alert metrics on queue sizes.

---

## 6. Distributed Job Scheduler

### 6.1 Architecture & Redis Usage
```
[Job Service] ───► [ZADD (Score = Run Timestamp)] ───► [Redis Jobs (ZSET)]
                                                              ▲
                                                              │ (Range Poll)
                                                       [Worker Cron Daemon]
```
*   **Redis Key**: `jobs:delayed:v1`
*   **Data Type**: **Sorted Set (ZSET)**. Score is the scheduled execution epoch timestamp; value is the job payload string.

### 6.2 Architectural Rationale & Alternatives
*   **Why Redis**: Delay schedulers must poll for due tasks efficiently. Storing tasks in a Sorted Set sorted by execution timestamp allows workers to query due jobs quickly using range scans (`ZRANGEBYSCORE`).
*   **Alternatives**:
    1.  *SQL Polling*: Constantly polling relational tables with `SELECT WHERE run_time <= NOW()` queries creates high disk read overhead.

### 6.3 Scaling Challenges & Failures
*   **Duplicate Execution**: If multiple workers poll the ZSET concurrently, they can pull and execute the same job twice.
    *   *Mitigation*: Use Lua scripts to fetch and delete jobs atomically, ensuring each job is delivered to only one worker.

---

## 7. Real-Time Leaderboard

### 7.1 Architecture & Redis Usage
```
[Score Submission] ───► [ZADD / ZINCRBY] ───► [Redis Leaderboard (ZSET)]
                                                    │
                                                    ▼ (ZRANGE / ZREVRANK)
                                             [Real-time Rankings]
```
*   **Redis Key**: `rankings:v1:global`
*   **Data Type**: **Sorted Set (ZSET)**. Score is the player's composite score; member is the player ID.

### 7.2 Architectural Rationale & Alternatives
*   **Why Redis**: Sorting millions of rows in a database under high concurrent writes degrades performance. Redis Sorted Sets maintain elements in a pre-sorted SkipList structure, resolving rank operations in logarithmic time.
*   **Alternatives**:
    1.  *SQL Order By*: Heavy disk reads and table locks.

### 7.3 Scaling Challenges & Failures
*   **Memory Footprint**: Storing millions of user IDs in a Sorted Set can consume significant memory.
    *   *Mitigation*: Segment leaderboards (e.g. by region or week) to keep set sizes small.

---

## 8. Chat Application Message Store

### 8.1 Architecture & Redis Usage
```
[Chat Client] ───(RPUSH)───► [Redis Chat List] ◄───(LRANGE)─── [Chat Service]
                                    │ (History Sync)
                                    ▼
                             [Cassandra DB]
```
*   **Redis Key**: `chat:history:v1:<room_id>`
*   **Data Type**: **List**. Contains JSON strings of recent messages.
*   **TTL**: 24 Hours.

### 8.2 Architectural Rationale & Alternatives
*   **Why Redis**: Chat systems require fast writes for message inputs and fast reads for history synchronizations. Redis Lists support append operations and range reads with sub-millisecond latency.
*   **Alternatives**:
    1.  *Cassandra/DynamoDB*: Best for long-term storage, but higher latency.

### 8.3 Scaling Challenges & Failures
*   **Memory Saturation**: Unbounded chat lists can quickly saturate memory.
    *   *Mitigation*: Cap list sizes using `LTRIM` to keep only the most recent messages (e.g. last 100 messages) in Redis, archiving older messages to a database.

---

## 9. Authentication Token Cache

### 9.1 Architecture & Redis Usage
```
[Token Validate] ───► [API Gateway] ───► [Redis Token Store (String)]
                                             │ (Fast lookup)
                                             ▼
                                      [Allow Request]
```
*   **Redis Key**: `auth:token:v1:<token_hash>`
*   **Data Type**: **String**. Value contains serialized user session metadata.
*   **TTL**: Matches token expiration lifetime.

### 9.2 Architectural Rationale & Alternatives
*   **Why Redis**: Authentication checks run on every single API request. Querying a database on every call creates a performance bottleneck. Redis Strings resolve lookups in sub-milliseconds.
*   **Alternatives**:
    1.  *Database lookups*: High database read load.

### 9.3 Scaling Challenges & Failures
*   **Node Outages**: If the authentication Redis instance drops offline, all API calls fail, returning unauthorized errors.
    *   *Mitigation*: Deploy Redis Sentinel or Redis Cluster configurations to ensure high availability and automatic failover.
